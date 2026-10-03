"""
Agente Analista de Estructura de Precio.

QUÉ RESUELVE
------------
El `nivel_referencia` del ajuste de entrada tenía **un solo proveedor**: la
cadena de opciones. Los tres candidatos de `_ajustar_entrada` —soporte de open
interest, punto de inflexión de la gamma y max pain— salen los tres de ella. Así
que la ausencia de cadena no degradaba el bloque: lo anulaba.

Y como el histórico de cadenas por ticker es de pago (`output/FUENTES_DATOS.md`,
iteración 18), en el backtest la cadena está **siempre** ausente y el ajuste de
entrada era **siempre** `None`. El estudio medía un sistema sin ajuste de
entrada mientras producción sí lo aplicaba: la limitación nº 5 del informe, y la
divergencia más importante entre lo que se evalúa y lo que se decide.

Este agente aporta el **cuarto candidato**, derivado del OHLCV que el sistema ya
tiene point-in-time, ya cacheado y ya protegido por
`test_no_lookahead_future_prices_do_not_change_past_signal`. Es la traducción a
barra diaria de `add_liquidity` y `_causal_levels` del repositorio 07.

POR QUÉ VA DESPUÉS DEL ANALISTA TÉCNICO Y ANTES DEL POSICIONAMIENTO
--------------------------------------------------------------------
Es una cadena de dependencias de datos real, no una preferencia:

  · consume `close` y `atr` del informe técnico para expresar la distancia al
    soporte en unidades de volatilidad, que es la única forma de compararla
    entre valores;
  · `posicionamiento` consume su `soporte` como candidato de nivel y su
    `soporte_lejano` como bandera de sobreextensión.

Reordenarlo no produce un error: produce otro precio de entrada. Es el mismo
argumento que obliga a `posicionamiento` a seguir a `technical`.

CAPA DE DECISIÓN, Y POR DOS VÍAS QUE SOLO CIERRAN
--------------------------------------------------
1. `soporte` entra en `ajustar_precio_entrada` como un candidato más, con la
   misma regla de «el más alto por debajo del precio». El ajuste sigue acotado a
   `AJUSTE_MAXIMO_ATR` y sigue pasando por `min(0.0, ajuste)`:
   **estructuralmente no puede subir la entrada.**
2. `soporte_lejano` se une por `or` a `sobreextendido`, en la misma familia que
   el RSI extremo y el techo del canal de open interest: prohíbe perseguir el
   precio, nunca lo habilita.

LO QUE ESTE AGENTE NO AFIRMA
-----------------------------
Que esperar al soporte mejore el resultado. Medido sobre las 936 señales de
compra del régimen `pit`, con los stops del propio Fund Manager y 10 pb de
costes: entrar al nivel **mejora la operación** (expectativa +1.70% frente a
+1.34%) y **empeora el valor esperado por señal** (+0.78% frente a +1.34%),
porque lo que la orden no rellena es justo lo que sube — esas señales habrían
rendido +3.56% con un 59.6% de acierto. Este agente existe para que el estudio
pueda MEDIR esa disyuntiva, no para dar por buena una de las dos ramas.

INVARIANTE
----------
Ninguna de esas cifras depende del LLM. El modelo solo sobrescribe `summary`, y
siempre después de que todo esté calculado. Se verifica en
`assert_llm_is_decision_neutral()`.
"""

from typing import Any, Dict, List, Optional

from src.agents.base import AgenteBase, Traza
from src.config import (
    NIVELES_MINIMO_SESIONES,
    SOPORTE_LEJANO_ATR,
    get_llm,  # noqa: F401  - resuelto por modulo; ver AgenteBase._obtener_llm
    texto_de_respuesta_llm,  # noqa: F401
)
from src.prompts import SYSTEM_ESTRUCTURA, prompt_estructura
from src.state import FinancialAnalysisState

NO_APLICABLE = "NO_APLICABLE"


class StructureAnalystAgent(AgenteBase):
    """
    Soportes estructurales del precio y distancia a ellos.

    Capa de DECISIÓN: su soporte alimenta el precio de entrada objetivo y su
    bandera de soporte lejano prohíbe perseguir.
    """

    nombre = "estructura"
    rol = "Analista de Estructura de Precio"
    system_prompt = SYSTEM_ESTRUCTURA

    # ------------------------------------------------------------------ #
    def decidir(self, state: FinancialAnalysisState, traza: Traza) -> Dict[str, Any]:
        ticker = state.get("ticker", "UNKNOWN")
        tech = state.get("technical_report", {}) or {}
        raw_tech = state.get("yfinance_data", {}).get("technical", {}) or {}
        # Los mínimos previos los calcula la INGESTA sobre la misma ventana OHLC
        # con la que se calculan los indicadores técnicos —`minimos_previos` en
        # `src/tools/niveles.py`—, igual que la cadena de opciones la recolecta
        # el nodo de ingesta y no el agente. Este agente es puro.
        niveles_crudos = state.get("yfinance_data", {}).get("niveles_precio", {}) or {}

        precio = tech.get("close") or raw_tech.get("close") or 0.0
        atr = tech.get("atr") or raw_tech.get("atr") or 0.0
        sma_50 = raw_tech.get("sma_50")
        sma_200 = raw_tech.get("sma_200")
        bb_inferior = raw_tech.get("bb_lower")

        minimos = {k: v for k, v in niveles_crudos.items() if k.startswith("minimo_")}
        hay_minimos = any(v is not None for v in minimos.values())

        if not precio:
            return self._vacio(ticker, precio, atr,
                               "sin precio de referencia: la estructura no se evalúa")

        soportes = self.usar_tool("identificar_soportes", {
            "minimos": minimos, "precio": precio, "sma_50": sma_50,
            "sma_200": sma_200, "bb_inferior": bb_inferior}, traza)

        distancia = self.usar_tool("medir_distancia_soporte", {
            "precio": precio, "soporte": soportes.get("soporte"), "atr": atr}, traza)

        clasificacion = self.usar_tool("clasificar_estructura", {
            "distancia_atr": distancia.get("distancia_atr")}, traza)

        estado = ("SUCCESS" if soportes.get("soporte") is not None
                  else "DATOS_INSUFICIENTES")
        informe: Dict[str, Any] = {
            "status": estado,
            "precio": round(precio, 2),
            "atr": round(atr, 2) if atr else None,
            "sesiones_minimas": NIVELES_MINIMO_SESIONES,
            "minimos_disponibles": hay_minimos,
            # --- variables de DECISION -----------------------------------
            "soporte": soportes.get("soporte"),
            "soporte_origen": soportes.get("origen"),
            "soporte_lejano": bool(clasificacion.get("soporte_lejano")),
            # --- descriptivas ---------------------------------------------
            "distancia_pct": distancia.get("distancia_pct"),
            "distancia_atr": distancia.get("distancia_atr"),
            "estructura": clasificacion.get("estructura"),
            "resistencia": soportes.get("resistencia"),
            "candidatos": soportes.get("candidatos"),
            "candidatos_por_debajo": soportes.get("por_debajo"),
            "umbral_soporte_lejano_atr": SOPORTE_LEJANO_ATR,
            "motivo": soportes.get("motivo") or clasificacion.get("motivo"),
        }
        informe["signals"] = self._signals(informe)
        resumen = self._resumen(ticker, informe)
        informe["resumen_determinista"] = resumen
        informe["summary"] = resumen
        return informe

    # ------------------------------------------------------------------ #
    @staticmethod
    def _vacio(ticker: str, precio: float, atr: float, motivo: str) -> Dict[str, Any]:
        """
        Degradación completa: ningún candidato de nivel y ninguna bandera.

        El comportamiento resultante es IDÉNTICO al previo a este agente, que es
        justo lo que fija `test_sin_estructura_el_ajuste_de_entrada_no_cambia`.
        No hay valores por defecto: un soporte de 0.0 afirmaría que el valor
        puede caer a nada, y eso es el defecto que `src/data/magnitudes.py`
        corrige.
        """
        resumen = (f"Estructura de precio de {ticker}: no evaluable. {motivo}. "
                   f"No se aporta ningún nivel de referencia ni ninguna bandera, "
                   f"de modo que el precio de entrada se resuelve exactamente igual "
                   f"que sin este análisis.")
        return {
            "status": NO_APLICABLE,
            "precio": round(precio, 2) if precio else None,
            "atr": round(atr, 2) if atr else None,
            "sesiones_minimas": NIVELES_MINIMO_SESIONES,
            "minimos_disponibles": False,
            "soporte": None, "soporte_origen": NO_APLICABLE, "soporte_lejano": False,
            "distancia_pct": None, "distancia_atr": None,
            "estructura": "SIN_REFERENCIA", "resistencia": None,
            "candidatos": {}, "candidatos_por_debajo": [],
            "umbral_soporte_lejano_atr": SOPORTE_LEJANO_ATR,
            "motivo": motivo,
            "signals": [f"Estructura no evaluable: {motivo}"],
            "resumen_determinista": resumen,
            "summary": resumen,
        }

    @staticmethod
    def _signals(informe: Dict[str, Any]) -> List[str]:
        senales: List[str] = []
        if informe.get("soporte") is None:
            senales.append(f"Sin soporte estructural por debajo del precio: "
                           f"{informe.get('motivo')}")
        else:
            senales.append(
                f"Soporte más cercano {informe['soporte_origen']} en "
                f"${informe['soporte']:.2f}, a {informe['distancia_pct']:.2%}"
                + (f" ({informe['distancia_atr']:.2f} ATR)"
                   if informe.get("distancia_atr") is not None else ""))
        otros = informe.get("candidatos_por_debajo") or []
        if len(otros) > 1:
            senales.append("Otros soportes por debajo: " + ", ".join(
                f"{c['origen']} ${c['nivel']:.2f}" for c in otros[1:4]))
        if informe.get("resistencia") is not None:
            senales.append(f"Primera referencia por encima: "
                           f"${informe['resistencia']:.2f}")
        senales.append(f"Estructura: {informe.get('estructura')}"
                       + (" — SOPORTE LEJANO: prohíbe perseguir el precio"
                          if informe.get("soporte_lejano") else ""))
        return senales

    @staticmethod
    def _resumen(ticker: str, informe: Dict[str, Any]) -> str:
        if informe.get("soporte") is None:
            return (f"Estructura de precio de {ticker}: el valor cotiza en "
                    f"${informe.get('precio'):.2f} por debajo de todas sus "
                    f"referencias estructurales, así que no se aporta ningún nivel "
                    f"de entrada. {informe.get('motivo') or ''}".strip())
        d_atr = informe.get("distancia_atr")
        return (
            f"Estructura de precio de {ticker}: el soporte más cercano es "
            f"{informe['soporte_origen']} en ${informe['soporte']:.2f}, a "
            f"{informe['distancia_pct']:.2%} del precio"
            + (f" ({d_atr:.2f} ATR)" if d_atr is not None else "")
            + f", lo que sitúa al valor como {informe.get('estructura')}."
            + (" El soporte queda lo bastante lejos como para prohibir perseguir "
               "el precio a mercado." if informe.get("soporte_lejano") else ""))

    # ------------------------------------------------------------------ #
    def prompt_usuario(self, state: FinancialAnalysisState,
                       informe: Dict[str, Any]) -> str:
        return prompt_estructura(state.get("ticker", "UNKNOWN"), informe)

    def resumen_de_log(self, informe: Dict[str, Any]) -> str:
        d = informe.get("distancia_atr")
        s = informe.get("soporte")
        return (f"soporte {informe.get('soporte_origen')} "
                f"{'n/d' if s is None else f'${s:.2f}'} · "
                f"distancia {'n/d' if d is None else f'{d:.2f} ATR'} · "
                f"{informe.get('estructura')}")
