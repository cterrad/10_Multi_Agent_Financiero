"""
Capa de ingesta del bloque macro del Analista de Posicionamiento.

Recolecta, para un conjunto CERRADO de contratos de futuros, dos cosas: la serie
semanal de posicionamiento COT de la CFTC y el precio del futuro continuo.

Ninguna regla de decision vive aqui. El z-score, el signo sectorial y la
clasificacion del sesgo estan en `src/tools/futuros.py`, que es donde el
proyecto guarda las reglas. Este modulo es el equivalente de
`src/data/news/` para el bloque macro, y su tool de red —`obtener_contexto_macro`—
vive en `src/tools/extraccion.py` como todas las demas.

EL DATO NO ES POR TICKER
------------------------
El sesgo del futuro del petroleo es el mismo para todas las energeticas que se
analicen en la misma ejecucion, y el COT se publica una vez por semana. Por eso
`recolectar_macro()` se llama UNA vez por ejecucion desde el orquestador
(`cli.py`, junto a `cargar_benchmark`) y el resultado viaja en el estado
inicial, igual que `benchmark_data`. Repetirlo por ticker seria descargar el
mismo fichero de la CFTC cincuenta veces.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Any, Dict, List, Optional

from src.config import (
    COT_VENTANA_SEMANAS,
    FUTURO_INDICE,
    SECTOR_A_FUTURO,
)
from src.data.futuros import cache, continuos, cot

__all__ = ["recolectar_macro", "contratos_requeridos", "cache", "cot", "continuos"]


def contratos_requeridos() -> Dict[str, Dict[str, Any]]:
    """
    Conjunto cerrado de contratos que el sistema puede necesitar.

    Es la union del contrato de indice —que aplica a todos los sectores— y de
    los del mapa sectorial. Son media docena, asi que se descargan todos de una
    vez: resolver perezosamente por sector obligaria a conocer los sectores
    antes de la ingesta, que es justo lo que aun no se sabe cuando este dosier
    se resuelve.
    """
    fuera: Dict[str, Dict[str, Any]] = {
        FUTURO_INDICE["contrato"]: {**FUTURO_INDICE, "papel": "indice"}
    }
    for sector, cfg in SECTOR_A_FUTURO.items():
        entrada = fuera.setdefault(cfg["contrato"], {**cfg, "papel": "sectorial",
                                                    "sectores": []})
        entrada.setdefault("sectores", []).append(sector)
    return fuera


def recolectar_macro(as_of: Optional[str] = None, offline: bool = False,
                     contratos: Optional[List[str]] = None,
                     semanas: int = COT_VENTANA_SEMANAS,
                     directorio_cot: Optional[Any] = None,
                     directorio_precios: Optional[Any] = None,
                     con_precios: bool = True) -> Dict[str, Any]:
    """
    Dosier macro compartido por todos los tickers de la ejecucion.

    `as_of` filtra el COT por FECHA DE PUBLICACION (no por la del informe). En
    produccion se omite; el backtest lo pasa siempre.

    Cada contrato se recolecta con su propio try/except: la caida de uno no
    tumba el dosier, exactamente igual que en el agregador de noticias. El peor
    caso es `status="SIN_DATOS"` con los motivos declarados.
    """
    as_of = as_of or date.today().isoformat()
    requeridos = contratos_requeridos()
    if contratos:
        requeridos = {k: v for k, v in requeridos.items() if k in set(contratos)}

    salida: Dict[str, Any] = {}
    fallidas: List[Dict[str, str]] = []

    def uno(codigo: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
        try:
            serie = cot.serie_semanal(cfg["cot"], as_of=as_of, semanas=semanas,
                                      offline=offline, directorio=directorio_cot)
        except Exception as exc:
            serie = {"mercado": cfg["cot"], "n_semanas": 0, "serie": [],
                     "fallos": [f"{type(exc).__name__}: {exc}"]}
        if not con_precios:
            # El backtest no lo pide: el precio del continuo no interviene en
            # ninguna decision y descargarlo por fecha de rebalanceo serian
            # cientos de peticiones inutiles.
            precio = {"disponible": False, "contrato": codigo,
                      "motivo": "no solicitado"}
        else:
            try:
                precio = continuos.precio_continuo(codigo, dia=as_of, offline=offline,
                                                   directorio=directorio_precios)
            except Exception as exc:
                precio = {"disponible": False, "contrato": codigo,
                          "motivo": f"{type(exc).__name__}: {exc}"}
        return {"contrato": codigo, "cot_mercado": cfg["cot"], "signo": cfg["signo"],
                "papel": cfg.get("papel"), "sectores": cfg.get("sectores", []),
                "cot": serie, "precio": precio}

    with ThreadPoolExecutor(max_workers=min(6, max(1, len(requeridos)))) as pool:
        futuros = {codigo: pool.submit(uno, codigo, cfg)
                   for codigo, cfg in requeridos.items()}
        for codigo, fut in futuros.items():
            try:
                salida[codigo] = fut.result()
            except Exception as exc:
                fallidas.append({"fuente": codigo, "motivo": f"{type(exc).__name__}: {exc}"})

    for codigo, datos in salida.items():
        for fallo in datos["cot"].get("fallos", []):
            fallidas.append({"fuente": f"{codigo}/cot", "motivo": fallo})
        if con_precios and not datos["precio"].get("disponible"):
            fallidas.append({"fuente": f"{codigo}/precio",
                             "motivo": datos["precio"].get("motivo", "no disponible")})

    con_cot = [c for c, d in salida.items() if d["cot"].get("n_semanas")]
    estado = "SUCCESS" if con_cot and not fallidas else \
             "DEGRADADO" if con_cot else "SIN_DATOS"

    return {
        "status": estado,
        "as_of": as_of,
        "contratos": salida,
        "fuentes_ok": sorted(con_cot),
        "fuentes_fallidas": fallidas,
        "ventana_semanas": semanas,
    }
