"""
Logging estructurado de los agentes.

QUÉ SUSTITUYE
-------------
El sistema anterior registraba con `logs.append("[Agente] texto")`: cadenas
sueltas dentro del estado, sin nivel, sin marca de tiempo, sin correlación por
ticker y sin ninguna constancia de qué cálculo produjo qué número. Servía para
imprimir en el informe y para nada más. En particular no permitía responder a la
pregunta que se hace siempre que un dictamen sorprende: *¿de dónde ha salido
esta cifra?*

Ahora hay dos canales con propósitos distintos y deliberadamente separados:

  · `logging` estándar de Python → consola y `output/logs/{fecha}_{ticker}.jsonl`.
    Un registro por evento, con `duracion_ms`, argumentos y resultado resumido.
    Es la traza de auditoría.
  · La lista `logs` del estado → sigue existiendo, pero solo como resumen
    legible que el informe imprime. Ya no es la fuente de verdad.

POR QUÉ JSONL Y NO TEXTO
------------------------
Porque la traza se consulta con herramientas, no leyéndola. Un `.jsonl` se filtra
por ticker, por agente o por tool con una línea de código; un log de texto exige
expresiones regulares que se rompen en cuanto alguien cambia una cadena.

POR QUÉ ESTÁ APAGADO POR DEFECTO EN EL BACKTEST
-----------------------------------------------
Un backtest de 2015 a 2025 recorre ~50 valores en ~130 rebalanceos, y cada
análisis invoca del orden de quince tools. Son cientos de miles de registros que
no aportan nada al estudio y que multiplicarían su duración por el coste de
escribir a disco. `configurar_logging` no se llama desde `backtest_cli.py`, y
sin configurar, el logger no escribe fichero: solo propaga a los handlers que
haya, que en el backtest no hay ninguno.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from src.config import OUTPUT_DIR

LOG_DIR = Path(OUTPUT_DIR) / "logs"

# Nombre raíz. Los agentes cuelgan de él (`agentes.calidad`, `agentes.tecnico`),
# de modo que subir o bajar el nivel de uno solo es trivial.
RAIZ = "agentes"

# Campos que ya viajan en el registro estructurado y que por tanto no deben
# duplicarse dentro de `extra` al serializar.
_ESTANDAR = frozenset(vars(logging.LogRecord("", 0, "", 0, "", (), None)).keys()) | {
    "message", "asctime", "taskName",
}


class FormateadorJSONL(logging.Formatter):
    """Un objeto JSON por línea, con todo lo que el agente haya adjuntado."""

    def format(self, record: logging.LogRecord) -> str:
        salida: Dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created).isoformat(timespec="milliseconds"),
            "nivel": record.levelname,
            "logger": record.name,
            "mensaje": record.getMessage(),
        }
        for k, v in record.__dict__.items():
            if k not in _ESTANDAR and not k.startswith("_"):
                salida[k] = v
        if record.exc_info:
            salida["excepcion"] = self.formatException(record.exc_info)
        # `default=str` porque un argumento de tool puede traer un Timestamp de
        # pandas o un numpy.float64, y un fallo de serialización no puede tumbar
        # el análisis: la traza es un medio, no el resultado.
        return json.dumps(salida, ensure_ascii=False, default=str)


class FormateadorConsola(logging.Formatter):
    """Línea legible para la terminal. La traza completa está en el JSONL."""

    def format(self, record: logging.LogRecord) -> str:
        agente = getattr(record, "agente", "-")
        ticker = getattr(record, "ticker", "-")
        cabecera = f"[{ticker}/{agente}]"
        detalle = ""
        tool = getattr(record, "tool", None)
        ms = getattr(record, "duracion_ms", None)
        if tool:
            detalle = f" · tool={tool}"
            if ms is not None:
                detalle += f" ({ms} ms)"
        return f"{cabecera} {record.getMessage()}{detalle}"


def configurar_logging(nivel: str = "INFO", ticker: Optional[str] = None,
                       a_consola: bool = True, a_fichero: bool = True) -> logging.Logger:
    """
    Prepara el logger raíz de los agentes. Idempotente por (nivel, ticker).

    `ticker` solo decide el NOMBRE del fichero, no filtra nada: en una ejecución
    por lotes conviene pasar `None` y obtener un único `..._lote.jsonl` con todos
    los valores, que es lo que permite comparar dos tickers sin abrir dos
    ficheros.
    """
    logger = logging.getLogger(RAIZ)
    # El nivel del LOGGER se deja en DEBUG y el filtrado se hace en cada
    # handler. Ponerlo en el logger silenciaba también el fichero: pedir una
    # consola tranquila (`nivel="WARNING"`) dejaba el JSONL vacío, que es
    # exactamente lo contrario de lo que se quiere en una ejecución larga.
    logger.setLevel(logging.DEBUG)
    # Sin esto, cada llamada añadiría un handler más y cada línea saldría
    # duplicada tantas veces como se hubiera configurado.
    for h in list(logger.handlers):
        logger.removeHandler(h)
        h.close()
    logger.propagate = False

    if a_consola:
        consola = logging.StreamHandler()
        consola.setFormatter(FormateadorConsola())
        consola.setLevel(getattr(logging, nivel.upper(), logging.INFO))
        logger.addHandler(consola)

    if a_fichero:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        sufijo = (ticker or "lote").upper()
        ruta = LOG_DIR / f"{datetime.now():%Y-%m-%d}_{sufijo}.jsonl"
        fichero = logging.FileHandler(ruta, encoding="utf-8")
        fichero.setFormatter(FormateadorJSONL())
        # El fichero se queda con TODO, incluidos los `tool_call` de nivel DEBUG:
        # es la traza de auditoría, y una traza con huecos no sirve para auditar.
        fichero.setLevel(logging.DEBUG)
        logger.addHandler(fichero)
        logger.debug("Traza estructurada en %s", ruta, extra={"evento": "inicio_traza"})

    return logger


class _AdaptadorQueFusiona(logging.LoggerAdapter):
    """
    `LoggerAdapter` que SUMA su contexto al `extra` del punto de llamada.

    El adaptador de la biblioteca estándar hace `kwargs["extra"] = self.extra`,
    es decir, SUSTITUYE. Con él, un `log.info("tool_result", extra={"tool": ...,
    "duracion_ms": ...})` llegaba al fichero convertido en `{"agente": ...,
    "ticker": ...}` y nada más: el JSONL registraba que algo había pasado pero
    no qué tool, ni cuánto tardó, ni qué devolvió — justo lo que la traza existe
    para conservar. Se detectó leyendo el primer fichero generado.
    """

    def process(self, msg, kwargs):
        fusionado = {**self.extra, **(kwargs.get("extra") or {})}
        # `logging` REVIENTA con KeyError si `extra` trae una clave que ya existe
        # en `LogRecord` —`args`, `name`, `module`, `levelname`...—. Pasó con
        # `extra={"args": ...}` al registrar una llamada a tool: el análisis
        # entero se detenía por una clave del log. Renombrar en vez de fallar es
        # lo correcto aquí: la traza es un medio, nunca el motivo por el que un
        # dictamen deja de emitirse.
        kwargs["extra"] = {(f"{k}_" if k in _ESTANDAR else k): v
                           for k, v in fusionado.items()}
        return msg, kwargs


def logger_de_agente(agente: str, ticker: str) -> logging.LoggerAdapter:
    """
    Logger con `agente` y `ticker` ya inyectados en cada registro.

    Se usa un adaptador y no un logger normal para que ningún punto de llamada
    tenga que acordarse de repetir el ticker: olvidarlo una sola vez deja un
    evento huérfano que ya no se puede correlacionar con su análisis.
    """
    return _AdaptadorQueFusiona(
        logging.getLogger(f"{RAIZ}.{agente}"),
        {"agente": agente, "ticker": (ticker or "?").upper()},
    )


def ruta_de_traza(ticker: Optional[str] = None,
                  dia: Optional[str] = None) -> Path:
    """Ruta del JSONL de una ejecución, para que el informe pueda enlazarla."""
    return LOG_DIR / f"{dia or f'{datetime.now():%Y-%m-%d}'}_{(ticker or 'lote').upper()}.jsonl"
