"""
Agente Analista de Calidad y Valoración.

Es la capa que faltaba entre «los fundamentales pasan el filtro» y «cuánto
compro». El gatekeeper solo respondía sí/no sobre tres ratios; nada distinguía
una compañía con P/E 17, margen del 55% y deuda del 19% de otra con P/E 270,
margen del 8% y deuda del 172%. Ambas salían APROBADO y recibían el mismo
dictamen y el mismo tamaño de posición.

Este agente convierte los estados financieros en cuatro puntuaciones de 0 a 100
—calidad, valoración, crecimiento y solvencia—, las combina en una convicción
fundamental y emite una etiqueta de estilo (VALOR, CRECIMIENTO, GARP,
CALIDAD_COMPUESTA...) que el Fund Manager usa para dimensionar y para elegir los
múltiplos de riesgo.

DÓNDE VIVE AHORA CADA ESCUELA
-----------------------------
Las siete escuelas están en `src/tools/calidad.py`, una tool por escuela:
`calcular_piotroski`, `calcular_altman`, `calcular_graham`, `calcular_buffett`,
`calcular_lynch`, `calcular_greenblatt` y `calcular_devengos_sloan`. Los cuerpos
son los mismos de siempre; lo que cambia es que son invocables por separado,
quedan en la traza con su duración y su resultado, y el agente investigador
puede consultarlas.

Este módulo conserva lo que corresponde a un agente y no a un cálculo: el ORDEN
de las llamadas, el ensamblado del informe y la redacción.

El orden importa. Las puntuaciones necesitan las siete escuelas ya calculadas;
las banderas rojas necesitan las puntuaciones; el estilo necesita las banderas;
y la convicción necesita el estilo y la cobertura. Reordenar las llamadas no
produce un error: produce un dictamen distinto.

INVARIANTE DEL PROYECTO
-----------------------
Ninguna de las variables anteriores depende del LLM. El modelo solo puede
sobrescribir `summary`, y siempre DESPUÉS de que todo esté calculado. Se
verifica en `assert_llm_is_decision_neutral()`.

DISCIPLINA DE DATOS
-------------------
Toda magnitud ausente es `None` y se propaga como tal: una puntuación se
calcula sobre los componentes disponibles y declara su propia cobertura. Por
debajo de `COBERTURA_MINIMA_ESTILO` el agente devuelve `DATOS_INSUFICIENTES`
en lugar de clasificar con huecos, porque una etiqueta de estilo apoyada en dos
de doce métricas es peor que ninguna etiqueta.
"""

from typing import Any, Dict, List, Optional

from src.agents.base import AgenteBase, Traza
from src.config import (
    COBERTURA_MINIMA_ESTILO,
    SECTOR_DESCONOCIDO,
    get_llm,  # noqa: F401  — resuelto por módulo; ver AgenteBase._obtener_llm
    texto_de_respuesta_llm,  # noqa: F401
)
from src.prompts import SYSTEM_CALIDAD, prompt_calidad
from src.state import FinancialAnalysisState
from src.tools.calidad import ESTILOS, _resumen_determinista

__all__ = ["QualityAnalystAgent", "ESTILOS"]


class QualityAnalystAgent(AgenteBase):
    """
    Analista de Calidad y Valoración.

    Puro: consume el estado ya reconciliado y no toca la red, igual que el
    gatekeeper y el analista técnico. Ninguna de las tools que invoca está en
    `src/tools/extraccion.py`, que es donde vive todo lo que sí sale a la red.
    """

    nombre = "calidad"
    rol = "Analista de Calidad y Valoración"
    system_prompt = SYSTEM_CALIDAD

    # ------------------------------------------------------------------ #
    def decidir(self, state: FinancialAnalysisState, traza: Traza) -> Dict[str, Any]:
        ticker = state.get("ticker", "UNKNOWN")
        sector = state.get("sector") or SECTOR_DESCONOCIDO
        industria = state.get("industry") or "Desconocida"

        yf_data = state.get("yfinance_data", {}) or {}
        fundamentals = yf_data.get("fundamentals", {}) or {}
        estados = yf_data.get("estados_financieros", {}) or {}
        tecnico = yf_data.get("technical", {}) or {}
        sec = state.get("sec_edgar_data", {}) or {}
        rec = state.get("reconciliation_data", {}) or {}
        metricas_rec = rec.get("reconciled_metrics", {}) or {}

        # --- 1. Mapa de magnitudes. Todo lo demás se apoya en él -----------
        # Viaja serializado (`detalle_magnitudes`) precisamente para que quepa en
        # el ToolMessage: la traza conserva de qué fuente salió cada número.
        base = self.usar_tool("construir_magnitudes_base", {
            "fundamentales": fundamentals,
            "estados_financieros": estados,
            "hechos_sec": sec,
            "metricas_reconciliadas": metricas_rec,
            "tecnico": tecnico,
        }, traza)

        # --- 2. Las siete escuelas, independientes entre sí ---------------
        piotroski = self.usar_tool("calcular_piotroski", {
            "estados_financieros": estados, "hechos_sec": sec}, traza)
        altman = self.usar_tool("calcular_altman", {
            "magnitudes": base, "estados_financieros": estados, "sector": sector}, traza)
        graham = self.usar_tool("calcular_graham", {
            "magnitudes": base, "fundamentales": fundamentals}, traza)
        greenblatt = self.usar_tool("calcular_greenblatt", {"magnitudes": base}, traza)
        buffett = self.usar_tool("calcular_buffett", {
            "magnitudes": base, "estados_financieros": estados}, traza)
        lynch = self.usar_tool("calcular_lynch", {
            "magnitudes": base, "sector": sector}, traza)
        devengos = self.usar_tool("calcular_devengos_sloan", {"magnitudes": base}, traza)
        contexto = self.usar_tool("calcular_contexto_sectorial", {
            "magnitudes": base, "sector": sector}, traza)

        # --- 3. Agregación. A partir de aquí el orden es obligatorio -------
        agregado = self.usar_tool("calcular_puntuaciones", {
            "magnitudes": base, "piotroski": piotroski, "altman": altman,
            "graham": graham, "greenblatt": greenblatt, "buffett": buffett,
            "lynch": lynch, "devengos": devengos}, traza)
        puntuaciones = agregado["puntuaciones"]
        coberturas = agregado["coberturas"]

        # Componentes sueltos de valoración: el clasificador de estilo necesita
        # distinguir los múltiplos de titular del compuesto. La trampa de valor
        # se detecta con P/E, P/VC y EV/EBITDA, no con la puntuación compuesta,
        # porque esta incluye el rendimiento del flujo de caja libre —malo en una
        # trampa de valor— y acaba promediando la señal de alarma con la de
        # reclamo hasta dejar el caso sin etiquetar.
        componentes_valoracion = puntuaciones.get("valoracion_componentes", {})
        cobertura_global = round(
            sum(coberturas.values()) / len(coberturas) if coberturas else 0.0, 3
        )

        banderas = self.usar_tool("detectar_banderas_rojas", {
            "magnitudes": base, "piotroski": piotroski, "altman": altman,
            "devengos": devengos, "buffett": buffett}, traza)

        estilo_res = self.usar_tool("clasificar_estilo", {
            "puntuaciones": puntuaciones, "magnitudes": base, "lynch": lynch,
            "sector": sector, "cobertura": cobertura_global,
            "banderas_rojas": banderas,
            "componentes_valoracion": componentes_valoracion,
            "altman": altman}, traza)
        estilo = estilo_res["estilo"]
        etiquetas_sec = estilo_res["etiquetas_secundarias"]
        motivo_estilo = estilo_res["motivo"]

        conviccion = self.usar_tool("calcular_conviccion", {
            "puntuaciones": puntuaciones, "cobertura": cobertura_global,
            "banderas_rojas": banderas,
            "confianza_datos": rec.get("confidence_score", 1.0)}, traza)

        status = "OK" if cobertura_global >= COBERTURA_MINIMA_ESTILO else "DATOS_INSUFICIENTES"

        summary = _resumen_determinista(
            ticker, estilo, puntuaciones, conviccion, piotroski, altman,
            graham, buffett, lynch, banderas, cobertura_global, status
        )

        return {
            "status": status,
            "sector": sector,
            "industria": industria,
            # `base` ya viene serializado con `disponible`; se aplana a valor o
            # None para conservar exactamente la forma que consumía el informe.
            "metricas": {k: d.get("valor") for k, d in base.items()},
            "magnitudes_detalle": base,
            "piotroski": piotroski,
            "altman": altman,
            "graham": graham,
            "greenblatt": greenblatt,
            "buffett": buffett,
            "lynch": lynch,
            "devengos": devengos,
            "contexto_sectorial": contexto,
            "puntuaciones": puntuaciones,
            "cobertura_por_bloque": coberturas,
            "cobertura_global": cobertura_global,
            "conviccion_fundamental": conviccion,
            "style_classification": estilo,
            "etiquetas_secundarias": etiquetas_sec,
            "style_rationale": motivo_estilo,
            "banderas_rojas": banderas,
            "resumen_determinista": summary,
            "summary": summary,
        }

    # ------------------------------------------------------------------ #
    def prompt_usuario(self, state: FinancialAnalysisState,
                       informe: Dict[str, Any]) -> str:
        return prompt_calidad(state.get("ticker", "UNKNOWN"),
                              informe.get("sector", SECTOR_DESCONOCIDO),
                              informe.get("industria", "Desconocida"), informe)

    def resumen_de_log(self, informe: Dict[str, Any]) -> str:
        conviccion = (informe.get("conviccion_fundamental") or {}).get("valor")
        return (f"estilo {informe.get('style_classification')} · "
                f"convicción {conviccion} · "
                f"Piotroski {(informe.get('piotroski') or {}).get('score')} · "
                f"Altman {(informe.get('altman') or {}).get('zona')} · "
                f"cobertura {informe.get('cobertura_global', 0.0):.0%}")
