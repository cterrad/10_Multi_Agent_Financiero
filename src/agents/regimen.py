"""
Agente Analista de Régimen de Volatilidad.

QUÉ RESUELVE
------------
El sistema no tenía **ninguna** medida de estrés sistémico. El dosier COT mide
posicionamiento POR CONTRATO —cuánto están largos los especuladores del E-mini o
del crudo—, que es una pregunta distinta de «en qué estado está el mercado». Un
valor puede tener el posicionamiento a favor y estar en mitad de una
capitulación.

Es la traducción del *anti-falling-knife gate* de `src/macro/regime.py` del
repositorio 07 (*Bear Trap*): en un régimen de pánico, lo que parece una trampa
—o una oportunidad— suele ser una capitulación real. Allí es una puerta binaria
(`vix_level <= 35 AND vix_z <= 2`); aquí son cuatro etiquetas y **dos mecanismos
que solo cierran**, porque este sistema necesita distinguir «no perseguir el
precio» de «no comprar».

LA FUENTE ES POINT-IN-TIME DE VERDAD, Y ESA ES LA DIFERENCIA
-------------------------------------------------------------
`VIXCLS` y `VXVCLS` llegan por ALFRED, cuyos parámetros de tiempo real devuelven
la serie **tal y como se conocía** en una fecha, con la fecha de publicación por
observación. Verificado: la observación semanal del miércoles 2020-03-25 es
invisible consultando ese mismo día y aparece el 26; el cierre diario del VIX es
visible el mismo día. El retardo no hay que modelarlo, hay que no estorbarlo.

Consecuencia práctica: **de este agente el estudio mide el 100% de la lógica**,
no la mitad. Es la diferencia con el Analista de Posicionamiento, cuyo bloque de
opciones no es reconstruible con fuentes gratuitas.

EL DOSIER ES DE LOTE; EL DICTAMEN ES POR TICKER
------------------------------------------------
El nivel del VIX de una fecha es idéntico para las cincuenta empresas de la
ejecución, así que `regimen_data` lo resuelve **una vez** quien orquesta el
bucle y viaja en el estado inicial, igual que `benchmark_data`, `futures_data` y
`reflexion_data`. Descargarlo dentro del grafo sería pedir la misma serie de
FRED una vez por valor.

Pero el dictamen sí es por valor: dentro del mismo régimen, uno que se mueve el
doble que el mercado no está en la misma situación que otro que se mueve la
mitad. De ahí `volatilidad_relativa`.

POR QUÉ VA EN EL FAN-OUT Y NO EN LA RAMA APROBADA
--------------------------------------------------
No hay dependencia de datos que lo fuerce a ir después de nada: solo consume
`regimen_data` (del estado inicial) y `volatilidad_anual` (de la ingesta). Y
colocarlo antes del enrutado condicional deja su lectura disponible **también
para los valores rechazados**, que es el mismo motivo por el que
`quality_analysis` va antes del gatekeeper: el régimen de mercado es justo lo
que se quiere leer sobre una empresa que no pasa el filtro.

Escribe `regimen_report` (clave propia, un solo escritor), `logs`
(`operator.add`) y `messages` (`add_messages`). **No escribe
`workflow_status`**, que es un escalar sin reductor y lo escribe el gatekeeper
en ese mismo superstep — la misma restricción que ya cumple `news_analysis`.

CAPA DE DECISIÓN, POR DOS VÍAS QUE SOLO CIERRAN
------------------------------------------------
1. `regimen_clasificacion` entra en `aplicar_vetos`: PANICO topa en MANTENER,
   TENSION topa en COMPRA. Nunca sube nada.
2. `puerta_regimen` cerrada se une a `sobreextendido` en el posicionamiento y
   prohíbe perseguir el precio. Nunca lo habilita.

INVARIANTE
----------
Ninguna de esas cifras depende del LLM. El modelo solo sobrescribe `summary`.
Se verifica en `assert_llm_is_decision_neutral()`.
"""

from typing import Any, Dict, List, Optional

from src.agents.base import AgenteBase, Traza
from src.config import (
    REGIMEN_VENTANA_ZSCORE,
    SERIE_VOLATILIDAD,
    SERIE_VOLATILIDAD_3M,
    get_llm,  # noqa: F401  - resuelto por modulo; ver AgenteBase._obtener_llm
    texto_de_respuesta_llm,  # noqa: F401
)
from src.prompts import SYSTEM_REGIMEN, prompt_regimen
from src.state import FinancialAnalysisState

NO_APLICABLE = "NO_APLICABLE"


class RegimeAnalystAgent(AgenteBase):
    """
    Régimen de volatilidad del mercado y su lectura para un valor concreto.

    Capa de DECISIÓN: su clasificación habilita un veto que solo baja y su
    puerta prohíbe perseguir el precio.
    """

    nombre = "regimen"
    rol = "Analista de Régimen de Volatilidad"
    system_prompt = SYSTEM_REGIMEN

    # ------------------------------------------------------------------ #
    def decidir(self, state: FinancialAnalysisState, traza: Traza) -> Dict[str, Any]:
        ticker = state.get("ticker", "UNKNOWN")
        dosier = state.get("regimen_data", {}) or {}
        raw_tech = state.get("yfinance_data", {}).get("technical", {}) or {}
        volatilidad_anual = raw_tech.get("volatilidad_anual")

        series = (dosier.get("series") or {})
        nombre_corto = dosier.get("serie_volatilidad") or SERIE_VOLATILIDAD
        nombre_largo = dosier.get("serie_volatilidad_3m") or SERIE_VOLATILIDAD_3M
        obs_corto = (series.get(nombre_corto) or {}).get("observaciones") or []
        obs_largo = (series.get(nombre_largo) or {}).get("observaciones") or []

        if not obs_corto:
            motivo = (dosier.get("fallos") or ["dosier de régimen ausente"])[0]
            return self._vacio(ticker, volatilidad_anual, motivo)

        z = self.usar_tool("calcular_zscore_volatilidad", {
            "observaciones": obs_corto, "ventana": REGIMEN_VENTANA_ZSCORE}, traza)

        nivel_largo = (float(obs_largo[-1]["valor"])
                       if obs_largo and obs_largo[-1].get("valor") is not None else None)
        curva = self.usar_tool("medir_curva_volatilidad", {
            "nivel_corto": z.get("nivel"), "nivel_largo": nivel_largo}, traza)

        clasificado = self.usar_tool("clasificar_regimen_volatilidad", {
            "nivel": z.get("nivel"), "z": z.get("z"),
            "invertida": bool(curva.get("invertida"))}, traza)

        relativa = self.usar_tool("medir_volatilidad_relativa", {
            "volatilidad_anual": volatilidad_anual,
            "nivel_volatilidad": z.get("nivel")}, traza)

        informe: Dict[str, Any] = {
            "status": "SUCCESS" if z.get("nivel") is not None else "DATOS_INSUFICIENTES",
            # --- variables de DECISION -----------------------------------
            "regimen_clasificacion": clasificado.get("clasificacion"),
            "puerta_regimen": bool(clasificado.get("puerta_abierta", True)),
            # --- descriptivas ---------------------------------------------
            "serie_volatilidad": nombre_corto,
            "serie_volatilidad_3m": nombre_largo,
            "nivel_volatilidad": z.get("nivel"),
            "zscore_volatilidad": z.get("z"),
            "media_volatilidad": z.get("media"),
            "desviacion_tipica": z.get("desviacion_tipica"),
            "n_observaciones": z.get("n_observaciones"),
            "ventana_zscore": REGIMEN_VENTANA_ZSCORE,
            "nivel_volatilidad_3m": nivel_largo,
            "ratio_curva": curva.get("ratio_curva"),
            "curva_invertida": bool(curva.get("invertida")),
            "volatilidad_anual": volatilidad_anual,
            "volatilidad_relativa": relativa.get("volatilidad_relativa"),
            "escalon": clasificado.get("escalon"),
            "escalon_por_nivel": clasificado.get("escalon_por_nivel"),
            "escalon_por_zscore": clasificado.get("escalon_por_zscore"),
            "agravado_por_curva": clasificado.get("agravado_por_curva"),
            "as_of": dosier.get("as_of"),
            "fallos": dosier.get("fallos", []),
            "motivo": z.get("motivo") or clasificado.get("motivo"),
        }
        informe["signals"] = self._signals(informe)
        resumen = self._resumen(ticker, informe)
        informe["resumen_determinista"] = resumen
        informe["summary"] = resumen
        return informe

    # ------------------------------------------------------------------ #
    @staticmethod
    def _vacio(ticker: str, volatilidad_anual: Optional[float],
               motivo: str) -> Dict[str, Any]:
        """
        Degradación completa: la puerta queda ABIERTA y no se dispara ningún veto.

        Abierta y no cerrada: cerrar por precaución ante la ausencia de dato
        convertiría una laguna de cobertura en una restricción de cartera, que
        es la forma inversa del defecto «ausencia ≠ cero». Sin dosier, el sistema
        se comporta **exactamente** como antes de que este agente existiera, que
        es lo que fija `test_sin_regimen_el_rating_no_cambia`.
        """
        resumen = (f"Régimen de volatilidad no evaluable para {ticker}: {motivo}. "
                   f"No se emite clasificación y la puerta queda abierta, de modo que "
                   f"ni el dictamen ni el precio de entrada se ven afectados.")
        return {
            "status": NO_APLICABLE,
            "regimen_clasificacion": NO_APLICABLE,
            "puerta_regimen": True,
            "serie_volatilidad": SERIE_VOLATILIDAD,
            "serie_volatilidad_3m": SERIE_VOLATILIDAD_3M,
            "nivel_volatilidad": None, "zscore_volatilidad": None,
            "media_volatilidad": None, "desviacion_tipica": None,
            "n_observaciones": 0, "ventana_zscore": REGIMEN_VENTANA_ZSCORE,
            "nivel_volatilidad_3m": None, "ratio_curva": None,
            "curva_invertida": False, "volatilidad_anual": volatilidad_anual,
            "volatilidad_relativa": None, "escalon": None,
            "escalon_por_nivel": None, "escalon_por_zscore": None,
            "agravado_por_curva": False, "as_of": None, "fallos": [motivo],
            "motivo": motivo,
            "signals": [f"Régimen no evaluable: {motivo}"],
            "resumen_determinista": resumen,
            "summary": resumen,
        }

    @staticmethod
    def _signals(informe: Dict[str, Any]) -> List[str]:
        senales: List[str] = []
        nivel, z = informe.get("nivel_volatilidad"), informe.get("zscore_volatilidad")
        if nivel is None:
            senales.append(f"Volatilidad implícita no disponible: {informe.get('motivo')}")
        else:
            senales.append(
                f"{informe['serie_volatilidad']} en {nivel:.2f} puntos"
                + (f", z={z:+.2f} sobre {informe['ventana_zscore']} sesiones"
                   if z is not None
                   else f" (z no evaluable: {informe.get('motivo')})"))
        if informe.get("ratio_curva") is not None:
            senales.append(
                f"Curva de volatilidad {informe['ratio_curva']:.3f} "
                + ("(INVERTIDA: el estrés es inmediato, no de fondo)"
                   if informe["curva_invertida"] else "(en contango)"))
        if informe.get("volatilidad_relativa") is not None:
            senales.append(
                f"Volatilidad del valor {informe['volatilidad_relativa']:.2f}x "
                f"la implícita del mercado")
        senales.append(
            f"Régimen: {informe.get('regimen_clasificacion')} · puerta "
            + ("abierta" if informe.get("puerta_regimen")
               else "CERRADA (prohíbe perseguir el precio)"))
        return senales

    @staticmethod
    def _resumen(ticker: str, informe: Dict[str, Any]) -> str:
        nivel = informe.get("nivel_volatilidad")
        if nivel is None:
            return (f"Régimen de volatilidad no evaluable para {ticker}: "
                    f"{informe.get('motivo')}. La puerta queda abierta y no se aplica "
                    f"ningún recorte.")
        z = informe.get("zscore_volatilidad")
        rel = informe.get("volatilidad_relativa")
        return (
            f"El mercado cotiza en régimen {informe['regimen_clasificacion']} con la "
            f"volatilidad implícita a un mes en {nivel:.2f} puntos"
            + (f" y un z-score de {z:+.2f} sobre {informe['ventana_zscore']} sesiones"
               if z is not None else " y un z-score no evaluable")
            + ("; la curva está invertida, señal de que el estrés es inmediato y no de "
               "fondo" if informe.get("curva_invertida") else "")
            + (f". {ticker} se mueve {rel:.2f} veces lo que implica el mercado"
               if rel is not None else f". La volatilidad relativa de {ticker} no es "
                                       f"calculable")
            + ("; la puerta de régimen está cerrada y prohíbe perseguir el precio."
               if not informe.get("puerta_regimen") else "."))

    # ------------------------------------------------------------------ #
    def prompt_usuario(self, state: FinancialAnalysisState,
                       informe: Dict[str, Any]) -> str:
        return prompt_regimen(state.get("ticker", "UNKNOWN"), informe)

    def resumen_de_log(self, informe: Dict[str, Any]) -> str:
        z = informe.get("zscore_volatilidad")
        return (f"regimen {informe.get('regimen_clasificacion')} · "
                f"nivel {informe.get('nivel_volatilidad')} · "
                f"z {'n/d' if z is None else f'{z:+.2f}'} · "
                f"puerta {'abierta' if informe.get('puerta_regimen') else 'cerrada'}")
