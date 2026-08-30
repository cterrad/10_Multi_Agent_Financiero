"""
Agente Analista de Noticias.

Estima la PROBABILIDAD de que la información pública reciente de una empresa
repercuta en un movimiento del precio de su acción.

Dónde vive el scorer
--------------------
Las funciones de puntuación —categoría, credibilidad, decaimiento,
corroboración, ruido y agregación— están en `src/tools/noticias.py`, expuestas
como las tools `puntuar_noticias` y `agregar_impacto_noticias`. Se reexportan
desde aquí porque son el contrato público de este agente y los tests las
importan por este nombre.

Contrato con el resto del sistema
---------------------------------
Este agente respeta la invariante que sostiene el proyecto: **ninguna variable
de decisión depende del LLM**. El orden de ejecución es el mismo que en los
otros agentes y no admite excepciones:

  1. Se fija la categoría de cada ítem por diccionario de palabras clave.
  2. Se fija la credibilidad por tipo de fuente, el decaimiento por antigüedad
     y el bonus por corroboración, todo con constantes de `src/config.py`.
  3. Se fija la dirección probable con un léxico cerrado de severidad.
  4. Se agrega la probabilidad de impacto y se clasifica en ALTA/MEDIA/BAJA.
  5. SOLO ENTONCES, si `get_llm()` no es None, el LLM reescribe `summary`.

El LLM no toca `impact_probability`, `impact_classification`,
`direction_classification`, `catalysts` ni ninguna cifra intermedia. Se verifica
en tiempo de ejecución en `assert_llm_is_decision_neutral()`
(`src/backtest/replay.py`), igual que para los demás agentes.

El agente es PURO: no hace red. Recibe en `state["news_data"]` el payload ya
recolectado y deduplicado por `src/data/news/aggregator.py`, exactamente igual
que el gatekeeper recibe los fundamentales ya reconciliados por el nodo de
ingesta. Eso lo hace testeable sin red y reproducible. Ninguna de las tools que
invoca sale a la red: la recolección la hace `obtener_noticias`, que es del nodo
de ingesta, no de este agente.

Capa ASESORA (v1)
-----------------
`news_report` se publica en el informe y se ofrece como argumento adicional al
debate, pero NO altera la tabla de rating ni `position_size_pct` del Fund
Manager. El motivo está en `output/AUDIT.md` y en `build_limitations()`: no
existe fuente de noticias histórica point-in-time asequible para Google News ni
Tavily, así que una señal de noticias que entrara en la decisión sería
imposible de backtestear y rompería la correspondencia entre lo que el backtest
mide y lo que producción hace.
"""

from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from src.agents.base import AgenteBase, Traza
from src.config import (
    get_llm,  # noqa: F401  — resuelto por módulo; ver AgenteBase._obtener_llm
    texto_de_respuesta_llm,  # noqa: F401
)
from src.prompts import SYSTEM_NOTICIAS, prompt_noticias
from src.state import FinancialAnalysisState

# Reexportado: es el contrato público del agente y lo que los tests importan.
from src.tools.noticias import (  # noqa: F401
    CATEGORIA_POR_DEFECTO,
    agregar_probabilidad,
    clasificar_categoria,
    clasificar_impacto,
    decaimiento,
    dias_de_antiguedad,
    direccion_agregada,
    es_ruido_promocional,
    factor_corroboracion,
    inferir_direccion_item,
    puntuar_item,
)


class NewsAnalystAgent(AgenteBase):
    """
    Agente Analista de Noticias: convierte un dosier de prensa en una
    probabilidad de impacto auditable.

    Capa asesora: informa al debate y al informe final, pero no modifica el
    rating ni el tamaño de posición.
    """

    nombre = "noticias"
    rol = "Analista de Noticias"
    system_prompt = SYSTEM_NOTICIAS

    # ------------------------------------------------------------------ #
    def decidir(self, state: FinancialAnalysisState, traza: Traza) -> Dict[str, Any]:
        ticker = state.get("ticker", "UNKNOWN")
        news_data = state.get("news_data", {}) or {}
        empresa = news_data.get("empresa") or state.get("company_name", ticker)
        as_of = news_data.get("as_of") or date.today().isoformat()
        items = news_data.get("items", []) or []

        puntuados = self.usar_tool("puntuar_noticias",
                                   {"items": items, "as_of": as_of}, traza)
        agregado = self.usar_tool("agregar_impacto_noticias",
                                  {"items_puntuados": puntuados}, traza)
        probabilidad = agregado["impact_probability"]
        impacto = agregado["impact_classification"]
        direccion = agregado["direction_classification"]
        desequilibrio = agregado["direction_imbalance"]

        catalizadores = [
            {
                "titular": i.get("titulo", ""),
                "url": i.get("url", ""),
                "categoria": i["categoria"],
                "fecha": i.get("fecha"),
                "fuente": i.get("fuente", ""),
                "tipo_fuente": i.get("tipo_fuente", "DESCONOCIDA"),
                "direccion": i["direccion"],
                "n_corroboraciones": i.get("n_corroboraciones", 1),
                "probabilidad_impacto": i["probabilidad_impacto"],
            }
            for i in puntuados[:3]
        ]

        conteo_categorias: Dict[str, int] = {}
        for i in puntuados:
            conteo_categorias[i["categoria"]] = conteo_categorias.get(i["categoria"], 0) + 1

        signals = [
            f"{i['categoria']} ({i.get('fecha') or 's/f'}, {i.get('tipo_fuente')}, "
            f"p={i['probabilidad_impacto']:.2f}): {i.get('titulo', '')[:110]}"
            for i in puntuados[:5]
        ]

        estado_datos = news_data.get("status", "SIN_DATOS")
        fuentes_ok = news_data.get("fuentes_ok", [])
        fuentes_fallidas = news_data.get("fuentes_fallidas", [])

        if not puntuados:
            summary = (
                f"Análisis de Noticias de {ticker}: sin ítems en la ventana de "
                f"{news_data.get('ventana_dias', 0)} días. Probabilidad de impacto por "
                f"noticias: BAJA (0.00). Estado de la búsqueda: {estado_datos}."
            )
        else:
            summary = (
                f"Análisis de Noticias de {ticker} ({empresa}): probabilidad de impacto "
                f"{impacto} ({probabilidad:.2f}) con dirección probable {direccion} "
                f"(desequilibrio {desequilibrio:+.2f}) sobre {len(puntuados)} noticia(s) "
                f"de los últimos {news_data.get('ventana_dias', 0)} días. "
                f"Catalizadores: {'; '.join(c['titular'][:90] for c in catalizadores)}."
            )
        if fuentes_fallidas:
            summary += (
                " Informe DEGRADADO: no respondieron "
                + ", ".join(f["buscador"] for f in fuentes_fallidas) + "."
            )

        return {
            "status": estado_datos,
            "company_name": empresa,
            "as_of": as_of,
            "window_days": news_data.get("ventana_dias", 0),
            "impact_probability": probabilidad,
            "impact_classification": impacto,
            "direction_classification": direccion,
            "direction_imbalance": desequilibrio,
            "catalysts": catalizadores,
            "scored_items": puntuados,
            "n_items": len(puntuados),
            "category_counts": conteo_categorias,
            "sources_ok": fuentes_ok,
            "sources_failed": fuentes_fallidas,
            "from_cache": news_data.get("desde_cache", False),
            # Marca explícita de que esta capa no entra en la decisión (v1).
            "advisory_only": True,
            "signals": signals,
            "resumen_determinista": summary,
            "summary": summary,
        }

    # ------------------------------------------------------------------ #
    def prompt_usuario(self, state: FinancialAnalysisState,
                       informe: Dict[str, Any]) -> str:
        return prompt_noticias(state.get("ticker", "UNKNOWN"),
                               informe.get("company_name", ""), informe)

    def resumen_de_log(self, informe: Dict[str, Any]) -> str:
        fallidas = ", ".join(f["buscador"] for f in informe.get("sources_failed", [])) or "ninguna"
        return (f"{informe.get('n_items', 0)} noticia(s) · "
                f"impacto {informe.get('impact_classification')} "
                f"({informe.get('impact_probability', 0.0):.2f}) · "
                f"dirección {informe.get('direction_classification')} · "
                f"fuentes sin respuesta: {fallidas}")
