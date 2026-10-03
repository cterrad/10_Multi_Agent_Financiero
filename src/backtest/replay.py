"""
Reconstrucción histórica del `FinancialAnalysisState` y ejecución de los
agentes REALES sobre él.

Este módulo es deliberadamente delgado: no contiene una sola regla de decisión.
Su único trabajo es fabricar, para una fecha `t`, un estado indistinguible del
que `node_ingest_and_reconcile` habría producido ese día, y después recorrer el
mismo camino que `build_financial_workflow()`:

    ingest → gatekeeper → [route_after_gatekeeper] → technical → debate → fund_manager

INCLUSIÓN DEL ANALISTA DE CALIDAD
---------------------------------
Desde que la convicción fundamental entra en el rating y en el tamaño de
posición, el `QualityAnalystAgent` es una variable de DECISIÓN y el replay lo
ejecuta como cualquier otro agente. Sus insumos —F-Score de Piotroski, Z-Score
de Altman, ROIC, devengos— se reconstruyen point-in-time en
`FundamentalStore.estados_financieros()`, con el mismo filtro `filed <= t` que
el resto de los fundamentales. Ejecutarlo con datos de hoy habría metido
look-ahead por la puerta de atrás.

Cuando un ticker no tiene estados financieros reconstruibles en la fecha `t`,
el agente devuelve `DATOS_INSUFICIENTES` y el Fund Manager limita el dictamen a
MANTENER. Esa degradación es deliberada: el sistema no debe operar con
convicción que no puede justificar.

EL ANALISTA DE POSICIONAMIENTO ENTRA A MEDIAS, Y ESO HAY QUE DECIRLO
--------------------------------------------------------------------
Ese agente es capa de DECISIÓN: su `precio_entrada_objetivo` alimenta
`calcular_niveles_riesgo`, y su `sesgo_macro_clasificacion` habilita un veto.
Pero sus dos bloques no son igual de reconstruibles:

  · BLOQUE MACRO (COT de la CFTC). SÍ es point-in-time. `COTStore`
    (`src/backtest/data.py`) filtra por FECHA DE PUBLICACIÓN —no por la del
    informe—, que es el mismo par `filed`/`end` de los hechos XBRL. El replay lo
    ejecuta y su veto se mide.

  · BLOQUE DE OPCIONES. NO lo es. yfinance publica la cadena de hoy y el
    histórico de open interest y volatilidad implícita es de pago. Aquí
    `options_data` se declara ausente.

La consecuencia es concreta y no se disimula: **el nivel de precio sale
EXCLUSIVAMENTE de la cadena**, así que sin ella no hay nivel, el ajuste es
`None` y el precio de entrada ES el de mercado. En el backtest, por tanto, el
Fund Manager se comporta exactamente como antes de que este agente existiera, y
lo único de esta capa que el estudio mide es el veto macro.

Eso deja una parte de la lógica viva sin medir, y es una diferencia real entre
lo que decide producción y lo que el estudio evalúa. Está declarado en
`build_limitations()`. La vía para cerrarla es un almacén de cadenas
point-in-time; mientras no exista, ninguna cifra de rendimiento publicada puede
atribuirse al ajuste de entrada.

EXCLUSIÓN DELIBERADA DEL ANALISTA DE NOTICIAS
---------------------------------------------
El grafo de producción incorpora un nodo `news_analysis` en paralelo al
gatekeeper. **El replay NO lo ejecuta, y esto es una decisión de diseño, no un
olvido.**

Dos de sus tres fuentes (Google News RSS y Tavily) son buscadores "de hoy": no
existe forma asequible de preguntarles qué se publicaba y era visible en una
fecha `t` de 2017. Reconstruir un dosier de prensa histórico con ellos
inyectaría look-ahead por dos vías simultáneas — el corpus indexado hoy excluye
lo que se borró y ordena por relevancia actual, y las fechas de los agregadores
son de republicación, no del hecho. Solo el 8-K con Ítem 2.02 tiene `filed`
exacto y sería reconstruible; con una sola de las tres fuentes el informe no
sería el que produce producción.

Por eso el Analista de Noticias es una CAPA ASESORA: informa al debate y al
informe final, pero no toca `rating` ni `position_size_pct`. Mientras eso se
mantenga, su ausencia en el replay no altera ni una sola señal, y el backtest
sigue midiendo exactamente la lógica que decide en producción. Si alguna vez se
conecta a la decisión, este backtest deja de ser válido hasta que exista un
`NewsStore` point-in-time. Queda declarado en `build_limitations()` y en
`NEXT_STEPS` de `backtest_cli.py`.

Hallazgo de la Fase 1 en el que se apoya todo lo demás
------------------------------------------------------
En los seis agentes el LLM solo sobrescribe campos de texto, y siempre DESPUÉS
de que las variables de decisión estén fijadas.

Ese orden ya no depende de que cada agente lo respete por su cuenta: lo impone
`AgenteBase.analyze()` (`src/agents/base.py`), que llama a `decidir()` —todo el
cálculo determinista— y solo después a `_redactar()`. El LLM únicamente puede
escribir la clave que el agente declara en `campo_texto`: `summary` en cinco de
ellos, `synthesis` en el debate. La versión anterior de este docstring
enumeraba línea por línea dónde ocurría en cada fichero, y esa lista quedaba
obsoleta con cualquier edición.

Los agentes invocan ahora tools reales (`src/tools/`), pero el PLAN de llamadas
lo escribe el código, no el modelo: `usar_tool()` emite los `tool_calls` con
nombre y argumentos fijos. La forma es la de un ReAct; la sustancia, la de una
función pura. El único ReAct de verdad del sistema —`src/agents/investigador.py`—
está fuera de la ruta de decisión y este replay no lo ejecuta.

`texto` sale de `src.config.texto_de_respuesta_llm()`, que aplana la respuesta
del proveedor a cadena y devuelve None si no hay nada utilizable — en ese caso
se conserva el resumen determinista. Es un ajuste de formato, no de contenido:
no puede introducir dependencia del LLM en ninguna decisión.

Ninguna variable de decisión depende del LLM. Por tanto ejecutar con
`get_llm() -> None` produce EXACTAMENTE los mismos ratings que producción, de
forma determinista, reproducible y a coste cero. `disable_llm()` lo garantiza y
`assert_llm_is_decision_neutral()` lo verifica en tiempo de ejecución en vez de
confiar en la lectura del código.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

import src.agents.debate as debate_mod
import src.agents.estructura as estructura_mod
import src.agents.fund_manager as fm_mod
import src.agents.investigador as investigador_mod
import src.agents.fundamental as fund_mod
import src.agents.news as news_mod
import src.agents.posicionamiento as pos_mod
import src.agents.quality as quality_mod
import src.agents.regimen as regimen_mod
import src.agents.technical as tech_mod
from src.data.fetcher import DataFetcher
from src.data.reconciler import DataReconciler
from src.graph.workflow import route_after_gatekeeper
from src.meta.variables import variables_de_senal
from src.tools.niveles import minimos_previos

# Filas mínimas en la ventana. Con >= 200 sesiones, `min(50, len)` y
# `min(200, len)` de `_add_technical_indicators` resuelven a 50 y 200, que es lo
# que ocurre en producción con `period="1y"` (~252 sesiones). Por debajo de 200
# las medias cambian silenciosamente de definición y el replay dejaría de ser
# fiel: esas fechas se descartan en lugar de producir una señal distinta.
MIN_WINDOW_ROWS = 200

BUY_RATINGS = ("COMPRA FUERTE", "COMPRA")


def disable_llm() -> None:
    """
    Fuerza el motor heurístico determinista en los cinco agentes.

    Se parchea el símbolo `get_llm` importado en cada módulo de agente (no
    `src.config.get_llm`), porque `from src.config import get_llm` fija el
    nombre en el espacio del módulo importador.

    Incluye a `src.agents.news` aunque el replay no ejecute su nodo: la
    verificación de neutralidad sí lo recorre, y dejarlo sin parchear abriría
    una llamada de red y de coste a mitad de un backtest offline.

    Incluye también a `src.agents.investigador` por el mismo motivo y con más
    razón: es el único agente ReAct del sistema, encadena varias llamadas al
    proveedor por invocación y no tiene motor heurístico al que degradar. Con el
    parche puesto, `modelo_con_tools()` levanta `LLMNoConfigurado` en lugar de
    abrir una factura en mitad de un backtest offline. El replay no lo ejecuta
    —es capa asesora, como las noticias— y este parche cierra la vía por si
    alguien lo conectara sin reparar en ello.
    """
    for mod in (fund_mod, quality_mod, tech_mod, news_mod, pos_mod, debate_mod,
                fm_mod, investigador_mod, estructura_mod, regimen_mod):
        mod.get_llm = lambda: None


def assert_llm_is_decision_neutral() -> Dict[str, Any]:
    """
    Verificación empírica de la hipótesis de la Fase 1.

    Ejecuta los agentes sobre un estado sintético dos veces: una con
    `get_llm() -> None` y otra con un LLM falso que devuelve texto constante y
    reconocible. Si alguna variable de decisión cambia, la hipótesis es falsa y
    el backtest no puede correr en modo heurístico.

    Cobertura del Analista de Noticias
    ---------------------------------
    El recorrido incluye al `NewsAnalystAgent` aunque el replay no ejecute su
    nodo, y lo hace por dos motivos distintos:

      1. Verificar que su propio dictamen (`impact_probability`,
         `impact_classification`, `direction_classification`, `catalysts`) es
         independiente del LLM, igual que el de los otros cuatro.
      2. Verificar la premisa que justifica excluirlo del backtest: con un
         `news_report` presente en el estado, `rating`, `position_size_pct` y
         los niveles de stop/objetivo tienen que salir IGUALES que sin él. La
         comparación directa con y sin informe de noticias la hace
         `test_news_report_does_not_alter_decision` en tests/test_news_analyst.py.

    El agente de noticias es puro: consume `state["news_data"]`, que aquí se
    fabrica sintéticamente. No toca la red.
    """
    import copy

    class _FakeLLM:
        def invoke(self, prompt):  # noqa: ARG002
            class _R:
                content = "TEXTO_FALSO_DE_VERIFICACION"
            return _R()

    state = _synthetic_state()
    modulos = (fund_mod, quality_mod, tech_mod, news_mod, pos_mod, debate_mod, fm_mod,
               estructura_mod, regimen_mod)
    originals = {mod.__name__: mod.get_llm for mod in modulos}

    def _run(llm_factory):
        for mod in modulos:
            mod.get_llm = llm_factory
        s = copy.deepcopy(state)
        # El nodo de calidad corre ANTES del gatekeeper, igual que en el grafo
        # de producción: sus banderas rojas deben estar en el estado cuando el
        # filtro fundamental se evalúa.
        qr = quality_mod.QualityAnalystAgent().analyze(s)
        s["quality_report"] = qr
        fr = fund_mod.FundamentalAnalystAgent().analyze(s)
        s["fundamental_report"] = fr
        s["passed_fundamental_gatekeeper"] = fr["passed_gatekeeper"]
        # En producción el nodo de noticias corre en paralelo al gatekeeper, así
        # que su informe ya está en el estado cuando se ramifica. El régimen es
        # la tercera rama del mismo fan-out y sigue el mismo orden.
        nr = news_mod.NewsAnalystAgent().analyze(s)
        s["news_report"] = nr
        rr = regimen_mod.RegimeAnalystAgent().analyze(s)
        s["regimen_report"] = rr
        pr, er = {}, {}
        if route_after_gatekeeper(s) == "technical_analysis":
            s["technical_report"] = tech_mod.TechnicalAnalystAgent().analyze(s)
            # La estructura va entre el tecnico y el posicionamiento, igual que
            # en el grafo de produccion: consume el close y el ATR, y su soporte
            # es candidato de nivel para el ajuste de entrada.
            er = estructura_mod.StructureAnalystAgent().analyze(s)
            s["estructura_report"] = er
            # El posicionamiento va entre la estructura y el debate: consume el
            # momentum, el ATR y el soporte estructural.
            pr = pos_mod.PositioningAnalystAgent().analyze(s)
            s["positioning_report"] = pr
            s["debate_report"] = debate_mod.DebateUnitAgent().analyze(s)
        fd = fm_mod.FundManagerAgent().analyze(s)
        return {
            "passed_gatekeeper": fr["passed_gatekeeper"],
            "momentum_classification": s.get("technical_report", {}).get("momentum_classification"),
            "rating": fd["rating"],
            "position_size_pct": fd["position_size_pct"],
            "peso_objetivo": fd["peso_objetivo"],
            "stop_loss_atr": fd["stop_loss_atr"],
            "take_profit_atr": fd["take_profit_atr"],
            # Factor de la memoria de reflexión. Multiplica el peso en la capa
            # de cartera y habilita un veto, así que es variable de decisión con
            # los mismos derechos que el rating: si el LLM lo moviera, el
            # backtest mediría una cartera distinta de la que se recomienda.
            "factor_reflexion": fd.get("factor_reflexion"),
            # Variables de decisión del Analista de Calidad. Se comparan con y
            # sin LLM igual que las demás: desde que alimentan el rating, que
            # sean independientes del modelo deja de ser una propiedad
            # deseable y pasa a ser un requisito del backtest.
            "quality_style": qr["style_classification"],
            "quality_conviccion": (qr.get("conviccion_fundamental") or {}).get("valor"),
            "quality_puntuaciones": tuple(
                (k, qr["puntuaciones"].get(k))
                for k in ("calidad", "valoracion", "crecimiento", "solvencia")
            ),
            "quality_piotroski": qr["piotroski"]["score"],
            "quality_altman": qr["altman"]["z"],
            "quality_banderas": tuple(qr["banderas_rojas"]),
            "news_impact_probability": nr["impact_probability"],
            "news_impact_classification": nr["impact_classification"],
            "news_direction_classification": nr["direction_classification"],
            "news_direction_imbalance": nr["direction_imbalance"],
            # Variables de decision del Analista de Posicionamiento. Desde
            # que `precio_entrada_objetivo` alimenta `calcular_niveles_riesgo`,
            # que sean independientes del modelo es un REQUISITO, no una
            # propiedad deseable: `stop_loss_atr` y `take_profit_atr`, que ya
            # se comparan arriba, cuelgan directamente de ellas.
            "pos_sesgo_macro": pr.get("sesgo_macro"),
            "pos_sesgo_macro_cls": pr.get("sesgo_macro_clasificacion"),
            "pos_sesgo_opciones": pr.get("sesgo_opciones"),
            "pos_entrada_cls": pr.get("entrada_clasificacion"),
            "pos_confluencia": pr.get("confluencia"),
            "pos_nivel": pr.get("nivel_referencia"),
            "pos_nivel_origen": pr.get("nivel_origen"),
            "pos_ajuste_pct": pr.get("ajuste_entrada_pct"),
            "pos_precio_entrada": pr.get("precio_entrada_objetivo"),
            "pos_gamma_flip": pr.get("gamma_flip"),
            "pos_max_pain": pr.get("max_pain"),
            # Variables de decision del Analista de Estructura. `soporte` es
            # candidato de nivel en `ajustar_precio_entrada` —y el UNICO
            # disponible en el backtest— y `soporte_lejano` se une por `or` a la
            # sobreextension. Si el LLM moviera cualquiera de las dos, el precio
            # de entrada y con el los niveles de riesgo dependerian del modelo.
            "est_soporte": er.get("soporte"),
            "est_soporte_origen": er.get("soporte_origen"),
            "est_soporte_lejano": er.get("soporte_lejano"),
            "est_distancia_atr": er.get("distancia_atr"),
            "est_estructura": er.get("estructura"),
            # Variables de decision del Analista de Regimen. La clasificacion
            # habilita un veto que solo baja y la puerta prohibe perseguir el
            # precio: ambas cuelgan de la serie de volatilidad, no del modelo.
            "reg_clasificacion": rr.get("regimen_clasificacion"),
            "reg_puerta": rr.get("puerta_regimen"),
            "reg_nivel": rr.get("nivel_volatilidad"),
            "reg_zscore": rr.get("zscore_volatilidad"),
            "reg_curva_invertida": rr.get("curva_invertida"),
            "reg_volatilidad_relativa": rr.get("volatilidad_relativa"),
            "news_catalysts": tuple(
                (c["titular"], c["categoria"], c["direccion"], c["probabilidad_impacto"])
                for c in nr["catalysts"]
            ),
        }

    try:
        heuristic = _run(lambda: None)
        with_llm = _run(lambda: _FakeLLM())
    finally:
        por_nombre = {m.__name__: m for m in modulos}
        for name, fn in originals.items():
            por_nombre[name].get_llm = fn

    diffs = {k: (heuristic[k], with_llm[k]) for k in heuristic if heuristic[k] != with_llm[k]}
    return {
        "neutral": not diffs,
        "heuristic": heuristic,
        "with_llm": with_llm,
        "divergences": diffs,
    }


def _synthetic_futures() -> Dict[str, Any]:
    """
    Dosier COT sintético con fechas FIJAS.

    Fijas por el mismo motivo que el dosier de prensa las lleva fijas: si la
    ventana dependiera del día en que se ejecuta la verificación, el z-score
    cambiaría entre ejecuciones y la comparación con y sin LLM dejaría de ser
    reproducible.

    La serie tiene 80 semanas —por encima de `COT_MINIMO_SEMANAS`— para que el
    z-score sea evaluable y la verificación recorra de verdad las ramas del
    agente en lugar de quedarse en NO_APLICABLE.
    """
    from src.config import FUTURO_INDICE

    def serie(base: int, amplitud: int) -> List[Dict[str, Any]]:
        filas = []
        d = pd.Timestamp("2022-09-06")
        for i in range(80):
            fecha = d + pd.Timedelta(weeks=i)
            # Oscilación determinista, sin aleatoriedad ni dependencia del reloj.
            desvio = amplitud * ((i % 7) - 3)
            filas.append({
                "mercado": "SINTETICO",
                "fecha_informe": fecha.strftime("%Y-%m-%d"),
                "fecha_publicacion": (fecha + pd.Timedelta(days=3)).strftime("%Y-%m-%d"),
                "no_comercial_largos": base + desvio,
                "no_comercial_cortos": base - desvio,
                "comercial_largos": base, "comercial_cortos": base,
                "interes_abierto": 1_000_000,
            })
        return filas

    return {
        "status": "SUCCESS", "as_of": "2024-03-15", "ventana_semanas": 156,
        "fuentes_ok": [FUTURO_INDICE["contrato"]], "fuentes_fallidas": [],
        "contratos": {
            FUTURO_INDICE["contrato"]: {
                "contrato": FUTURO_INDICE["contrato"], "cot_mercado": FUTURO_INDICE["cot"],
                "signo": 1, "papel": "indice", "sectores": [],
                "cot": {"mercado": "SINTETICO", "n_semanas": 80,
                        "serie": serie(200_000, 4_000), "fallos": []},
                "precio": {"disponible": False, "motivo": "no solicitado"},
            },
        },
    }


def _synthetic_options() -> Dict[str, Any]:
    """
    Cadena de opciones sintética con histórico suficiente para los percentiles.

    Sin los 60 días de histórico, el put/call y el skew saldrían
    DATOS_INSUFICIENTES y la verificación no recorrería el bloque que produce el
    nivel de precio, que es justamente el que se quiere cubrir.
    """
    contratos: List[Dict[str, Any]] = []
    for k in range(80, 125, 5):
        for tipo, oi in (("call", 400 + 10 * (120 - k)), ("put", 400 + 10 * (k - 80))):
            contratos.append({
                "tipo": tipo, "strike": float(k), "vencimiento": "2024-04-05",
                "dias": 21, "open_interest": int(oi), "volumen": int(oi // 4),
                "iv": round(0.30 + 0.002 * abs(100 - k), 4),
            })
    agregados = {
        "oi_calls": sum(c["open_interest"] for c in contratos if c["tipo"] == "call"),
        "oi_puts": sum(c["open_interest"] for c in contratos if c["tipo"] == "put"),
        "vol_calls": sum(c["volumen"] for c in contratos if c["tipo"] == "call"),
        "vol_puts": sum(c["volumen"] for c in contratos if c["tipo"] == "put"),
        "iv_call_otm": 0.32, "iv_put_otm": 0.35,
        "vencimiento_referencia": "2024-04-05", "spot": 100.0,
    }
    historico = [{
        "fecha": f"2024-01-{(i % 28) + 1:02d}",
        "oi_calls": 10_000, "oi_puts": 9_000 + 20 * i,
        "vol_calls": 2_000, "vol_puts": 1_800,
        "iv_call_otm": 0.32, "iv_put_otm": 0.34 + 0.0002 * i,
    } for i in range(70)]
    return {
        "disponible": True, "motivo": None, "ticker": "TEST", "as_of": "2024-03-15",
        "spot": 100.0, "ventana_dias": 45,
        "vencimientos": [{"fecha": "2024-04-05", "dias": 21,
                          "n_contratos": len(contratos)}],
        "contratos": contratos,
        "oi_total": sum(c["open_interest"] for c in contratos),
        "agregados": agregados, "historico": historico,
        "n_dias_historico": len(historico), "minimo_dias_historico": 60,
        "desde_cache": False,
    }


def _synthetic_reflexion() -> Dict[str, Any]:
    """
    Dosier de memoria de reflexión sintético para la verificación de
    neutralidad.

    Las celdas tienen muestra por encima de `REFLEXION_MUESTRA_MINIMA` para que
    la tool recorra su rama activa, y una de ellas —CRECIMIENTO— es
    deliberadamente negativa, que es el hallazgo real que `attr_estilo` publica
    sobre el histórico del sistema. Así la verificación comprueba el camino en
    el que la capa SÍ recorta, no solo el neutro.
    """
    return {
        "as_of": "2024-06-28",
        "horizonte_sesiones": 21,
        "n_total": 900,
        "media_global": 0.001,
        "muestra_minima": 40,
        "contraccion_k": 40,
        "evaluable": True,
        "motivo": None,
        "tabla": {
            "estilo": {
                "CALIDAD_COMPUESTA": {"n": 180, "media": 0.012, "error_tipico": 0.004},
                "GARP": {"n": 140, "media": 0.004, "error_tipico": 0.005},
                "CRECIMIENTO": {"n": 160, "media": -0.021, "error_tipico": 0.006},
                "MIXTA": {"n": 220, "media": 0.000, "error_tipico": 0.004},
            },
            "momentum": {
                "ALCISTA_FUERTE": {"n": 150, "media": 0.007, "error_tipico": 0.005},
                "ALCISTA": {"n": 210, "media": 0.002, "error_tipico": 0.004},
                "NEUTRAL": {"n": 300, "media": -0.003, "error_tipico": 0.003},
                "BAJISTA": {"n": 120, "media": -0.015, "error_tipico": 0.006},
            },
        },
    }


def _synthetic_regimen() -> Dict[str, Any]:
    """
    Dosier de régimen sintético con fechas y valores FIJOS.

    Fijos por el mismo motivo que las fechas del dosier COT y las del dosier de
    prensa: una serie que cambiara entre ejecuciones haría irreproducible la
    comparación con y sin LLM.

    La serie se construye con un nivel medio bajo y un tramo final elevado, de
    modo que el z-score cae en zona de PANICO: así la verificación recorre el
    camino en el que el veto SÍ actúa (tope en MANTENER), y no solo el neutro. Con
    la curva en contango, para que el agravamiento por inversión quede como rama aparte.
    """
    def _serie(serie: str, valores: List[float], desde: int) -> Dict[str, Any]:
        obs = []
        for i, v in enumerate(valores):
            dia = desde + i
            # Fechas sintéticas correlativas dentro de un mismo mes ficticio; lo
            # único que el scorer usa es el ORDEN y el último valor.
            fecha = f"2024-{(dia // 28) + 1:02d}-{(dia % 28) + 1:02d}"
            obs.append({"serie": serie, "fecha": fecha,
                        "fecha_publicacion": fecha, "valor": round(v, 2)})
        return {"serie": serie, "as_of": "2024-06-28",
                "n_observaciones": len(obs), "observaciones": obs, "fallos": []}

    base = [14.0 + 0.5 * ((i * 7) % 5) for i in range(70)]
    corto = base + [22.5, 23.0, 24.0, 26.5, 27.0]
    largo = [v + 2.0 for v in base] + [24.0, 24.5, 25.5, 27.5, 28.0]
    return {
        "disponible": True,
        "as_of": "2024-06-28",
        "series": {"VIXCLS": _serie("VIXCLS", corto, 0),
                   "VXVCLS": _serie("VXVCLS", largo, 0)},
        "fallos": [],
        "serie_volatilidad": "VIXCLS",
        "serie_volatilidad_3m": "VXVCLS",
    }


def _synthetic_state() -> Dict[str, Any]:
    """Estado mínimo que atraviesa la rama aprobada del grafo."""
    tech = {
        "close": 100.0, "rsi": 60.0, "macd": 1.5, "macd_signal": 1.0, "macd_hist": 0.5,
        "bb_upper": 105.0, "bb_lower": 95.0, "atr": 2.0,
        "sma_50": 95.0, "sma_200": 90.0, "volume_rel": 1.2,
        "dist_sma_50_pct": 0.0526, "dist_sma_200_pct": 0.1111,
        "pendiente_sma_50": 0.03, "posicion_rango_52w": 0.75,
        "volatilidad_anual": 0.28, "atr_pct": 0.02,
    }
    fundamentals = {"revenue_growth": 0.20, "net_margin": 0.15, "debt_to_equity": 1.0,
                    "roe": 0.30, "pe_ratio": 25.0, "market_cap": 1.0e10,
                    "gross_margin": 0.55, "operating_margin": 0.25,
                    "price_to_book": 3.0, "ev_to_ebitda": 12.0,
                    "enterprise_value": 1.1e10, "trailing_eps": 4.0,
                    "book_value_per_share": 20.0, "current_ratio": 2.0,
                    "earnings_growth": 0.22, "dividend_yield": 0.01,
                    "free_cashflow": 6.0e8, "operating_cashflow": 9.0e8,
                    "total_debt": 2.0e9}

    # Estados financieros sintéticos de dos ejercicios: sin ellos el Analista
    # de Calidad devolvería DATOS_INSUFICIENTES y la verificación no recorrería
    # ninguna de sus ramas de decisión.
    def _s(v, f=0.85):
        return [v, v * f]

    estados = {
        "disponible": True, "bloques_ok": ["balance", "resultados", "flujos"],
        "bloques_fallidos": [],
        "balance": {
            "activos_totales": _s(1.0e10), "pasivos_totales": _s(4.0e9),
            "patrimonio": _s(6.0e9), "activo_corriente": _s(3.0e9),
            "pasivo_corriente": _s(1.2e9), "beneficios_retenidos": _s(3.5e9),
            "deuda_largo_plazo": _s(1.8e9), "deuda_total": _s(2.0e9),
            "acciones_emitidas": _s(5.0e8, 1.005), "efectivo": _s(1.0e9),
            "inmovilizado": _s(3.0e9), "fondo_comercio": [], "intangibles": [],
        },
        "resultados": {
            "ingresos": _s(5.0e9), "beneficio_bruto": _s(2.75e9), "ebit": _s(1.25e9),
            "beneficio_neto": _s(7.5e8), "gastos_financieros": _s(8.0e7),
            "impuestos": _s(2.0e8), "beneficio_antes_impuestos": _s(9.5e8),
        },
        "flujos": {
            "flujo_operativo": _s(9.0e8), "capex": _s(-3.0e8),
            "flujo_libre": _s(6.0e8), "dividendos_pagados": [], "recompras": [],
        },
    }
    return {
        "ticker": "TEST",
        "sector": "Technology",
        "industry": "Software - Infrastructure",
        "yfinance_data": {"status": "SUCCESS", "fundamentals": fundamentals,
                          "technical": tech, "estados_financieros": estados,
                          # Mínimos previos sintéticos. El de 10 sesiones queda
                          # por debajo del precio y por encima de la SMA50, así
                          # que gana la elección de soporte y la verificación
                          # recorre la rama en la que SÍ hay nivel estructural.
                          "niveles_precio": {"minimo_10": 97.5, "minimo_21": 94.0,
                                             "minimo_63": 88.0},
                          "price_history_summary": {
                              "change_1m_pct": 0.02, "change_3m_pct": 0.06,
                              "change_6m_pct": 0.12, "change_12m_pct": 0.25,
                              "min_52w": 70.0, "max_52w": 110.0,
                              "close_today": 100.0, "sesiones": 252}},
        "sec_edgar_data": {"status": "NOT_USED"},
        "reconciliation_data": {
            "status": "SINGLE_VENDOR_FALLBACK", "ticker": "TEST", "confidence_score": 1.0,
            "sources_consulted": ["yfinance"], "discrepancies": [],
            "reconciled_metrics": dict(fundamentals),
        },
        # Dosier de prensa sintético: fechas fijas y `as_of` fijo, para que la
        # antigüedad (y por tanto el decaimiento) no dependa del día en que se
        # ejecute la verificación.
        "news_data": {
            "status": "SUCCESS", "ticker": "TEST", "empresa": "Test Corp",
            "as_of": "2024-03-15", "ventana_dias": 30,
            "fuentes_ok": ["sec_8k", "google_news_rss"], "fuentes_fallidas": [],
            "desde_cache": False,
            "items": [
                {"titulo": "Test Corp presenta el formulario 8-K (Item 2.02: Results of "
                           "Operations and Financial Condition)",
                 "url": "https://www.sec.gov/Archives/edgar/data/1/x.htm",
                 "fuente": "SEC EDGAR (8-K)", "fecha": "2024-03-14",
                 "extracto": "Presentacion oficial ante la SEC.", "tipo_fuente": "SEC_8K",
                 "buscadores": ["sec_8k"], "n_corroboraciones": 1,
                 "categoria_forzada": "RESULTADOS"},
                {"titulo": "Test Corp beats estimates and raises full-year guidance",
                 "url": "https://www.reuters.com/test", "fuente": "Reuters",
                 "fecha": "2024-03-13", "extracto": "Record revenue and strong demand.",
                 "tipo_fuente": "MEDIO_TIER1", "buscadores": ["google_news_rss"],
                 "n_corroboraciones": 2},
            ],
            "n_brutos": 2, "n_items": 2,
        },
        "futures_data": _synthetic_futures(),
        "options_data": _synthetic_options(),
        # Dosier de reflexión sintético, con muestras por encima del mínimo para
        # que la verificación de neutralidad recorra el camino REAL de la tool y
        # no su rama degradada. Los números son fijos por el mismo motivo que las
        # fechas del dosier COT: una tabla que cambiara entre ejecuciones haría
        # irreproducible la comparación con y sin LLM.
        "reflexion_data": _synthetic_reflexion(),
        # Dosier de régimen sintético, construido para caer en PANICO: así la
        # verificación recorre el camino en el que el veto de régimen SÍ recorta
        # y la puerta SÍ se cierra, no solo el neutro.
        "regimen_data": _synthetic_regimen(),
        "logs": [], "passed_fundamental_gatekeeper": False,
    }


# --------------------------------------------------------------------------- #
@dataclass
class Signal:
    ticker: str
    date: pd.Timestamp
    rating: str
    momentum: Optional[str]
    passed_gatekeeper: bool
    close: float
    atr: float
    rsi: float
    stop_loss: Optional[float]
    take_profit: Optional[float]
    target_weight: float
    sector: str = "Desconocido"
    fundamentals_as_of: Optional[str] = None
    fundamentals_filed: Optional[str] = None
    # Dictamen del Analista de Calidad. Se arrastra hasta el registro de
    # operaciones para poder atribuir el resultado por estilo de inversión, que
    # es la pregunta que el informe anterior no podía responder: ¿el sistema
    # pierde dinero en valor, en crecimiento o en ambos?
    estilo: Optional[str] = None
    conviccion: Optional[float] = None
    banderas_rojas: int = 0
    # Volatilidad anualizada realizada. La capa de cartera la necesita para
    # estimar la matriz de covarianzas y el ratio de diversificación.
    volatilidad: Optional[float] = None
    # Dictamen del Analista de Posicionamiento. En el replay solo el bloque
    # macro es reconstruible, así que `entrada_clasificacion` es NO_APLICABLE
    # salvo que alguna vez exista un almacén de cadenas point-in-time. Se
    # arrastra hasta el registro de operaciones para poder atribuir el resultado
    # por régimen macro, igual que se hace por estilo.
    sesgo_macro: Optional[str] = None
    entrada_clasificacion: Optional[str] = None
    # Precio de entrada objetivo. Antes NO viajaba, y esa era la razón real de
    # que el ajuste de entrada fuera inmedible: aunque hubiera existido un nivel,
    # el motor no habría tenido a dónde llevarlo. `build_orders` lo convierte
    # ahora en el límite de una orden con vida acotada, y `process_open` la
    # rellena o la cancela. Es `NEXT_STEPS` #1.
    #
    # `None` significa «entrada a mercado», que es el comportamiento previo
    # exacto; nunca se colapsa con el precio de cierre, por el mismo motivo por
    # el que `ajuste_entrada_pct = 0.0` y `None` no son lo mismo.
    precio_entrada_objetivo: Optional[float] = None
    ajuste_entrada_pct: Optional[float] = None
    nivel_origen: Optional[str] = None
    # Dictamen del Analista de Estructura y del Analista de Régimen. Se arrastran
    # al registro de operaciones para poder atribuir el resultado por estructura
    # y por régimen de mercado, igual que se hace por estilo.
    estructura: Optional[str] = None
    distancia_soporte_atr: Optional[float] = None
    regimen: Optional[str] = None
    # Variables del meta-modelo y horizonte de la operación. Viajan hasta
    # `BancoDeEtiquetas`, que las guarda para el reentrenamiento walk-forward.
    # El horizonte es el que el propio Fund Manager emitió: la etiqueta mide la
    # operación que el sistema HABRÍA abierto, no una genérica.
    variables_meta: Dict[str, Any] = field(default_factory=dict)
    horizonte_dias: int = 63
    # Factor del meta-modelo con el que se emitió esta señal. Como
    # `factor_reflexion`, viaja SIN aplicar hasta `PortfolioConstructor`.
    factor_meta: float = 1.0
    # Factor de la memoria de reflexión con el que se emitió esta señal. Viaja
    # hasta `PortfolioConstructor`, que es quien lo aplica y reasigna. Se
    # arrastra además al registro para poder responder cuánto recortó realmente
    # la capa a lo largo del estudio, en vez de suponerlo.
    factor_reflexion: float = 1.0

    @property
    def is_buy(self) -> bool:
        return self.rating in BUY_RATINGS


# El Fund Manager emitía el tamaño como CADENA («8.0% - 10.0%»), así que el
# backtest tenía que mantener su propia tabla de pesos — una regla de decisión
# duplicada fuera de `src/agents/`, justo lo que la arquitectura prohíbe. Ahora
# emite `peso_objetivo` numérico y el replay lo consume directamente. La tabla
# se conserva solo como respaldo para estados antiguos sin ese campo.
WEIGHT_BY_RATING = {"COMPRA FUERTE": 0.09, "COMPRA": 0.055}


class HistoricalReplayer:
    """
    Reproduce la decisión del sistema para (ticker, fecha).

    Modos de datos (`mode`):
      - "pit"            : fundamentales point-in-time de SEC EDGAR. Régimen
                           limpio. Es el resultado principal.
      - "technical_only" : gatekeeper neutralizado (passed=True). Aísla el valor
                           de la capa técnica sin contaminación fundamental.
      - "biased"         : fundamentales de HOY aplicados al pasado. Es lo que
                           haría producción tal cual. LOOK-AHEAD: solo contraste.
    """

    def __init__(self, price_store, fundamental_store, mode: str = "pit",
                 sector_map: Optional[Dict[str, str]] = None,
                 cot_store=None, fred_store=None, con_estructura: bool = True):
        if mode not in ("pit", "technical_only", "biased"):
            raise ValueError(f"Modo desconocido: {mode}")
        self.prices = price_store
        self.fundamentals = fundamental_store
        self.mode = mode
        self.sector_map = sector_map or {}
        # Almacén COT point-in-time. Opcional: sin él la pata macro se declara
        # no aplicable y el agente degrada, que es el mismo comportamiento que
        # en producción cuando la CFTC no responde.
        self.cot_store = cot_store
        # Almacén de volatilidad implícita point-in-time. Opcional por el mismo
        # criterio que `cot_store`: sin él el Analista de Régimen declara
        # NO_APLICABLE, deja la puerta abierta y no dispara ningún veto, que es
        # el mismo comportamiento que en producción cuando FRED no responde.
        self.fred_store = fred_store
        # Interruptor de ABLACION del Analista de Estructura, de la misma
        # familia que `cot_store=None` y `mode="technical_only"`: existe para
        # poder atribuir su efecto por separado en el estudio, y para fijar en un
        # test que sin el el sistema se comporta EXACTAMENTE como antes de que
        # existiera. No es una opcion de produccion.
        self.con_estructura = con_estructura

        # Dosier de la memoria de reflexión para la fecha que se está
        # reproduciendo. Lo INYECTA quien orquesta el bucle, no el replayer,
        # porque la memoria es acumulativa y su consolidación depende del orden
        # temporal del recorrido — exactamente el mismo motivo por el que el
        # dosier macro se resuelve una vez por ejecución y no por ticker.
        # Vacío = capa inactiva y neutra, que es el estado de una instalación
        # recién puesta en marcha.
        self.reflexion_dosier: Dict[str, Any] = {}

        # Artefacto del meta-modelo vigente para la fecha que se reproduce. Lo
        # INYECTA quien orquesta el bucle, por el mismo motivo que el dosier de
        # reflexión: el reentrenamiento walk-forward depende del recorrido
        # temporal, y el replayer no lo conoce. `None` = capa inactiva y factor
        # 1.0, que es el estado de una instalación sin modelo entrenado.
        self.meta_artefacto = None

        # Instancias de los componentes REALES.
        # `con_estados_financieros=False`: en el replay los estados vienen de
        # `FundamentalStore.estados_financieros()` reconstruidos point-in-time,
        # nunca de yfinance. Dejar el fetcher pidiéndolos abriría una llamada de
        # red con datos de HOY en mitad de un backtest offline.
        self.fetcher = DataFetcher(con_estados_financieros=False)
        self.reconciler = DataReconciler()
        self.fundamental_agent = fund_mod.FundamentalAnalystAgent()
        self.quality_agent = quality_mod.QualityAnalystAgent()
        self.technical_agent = tech_mod.TechnicalAnalystAgent()
        self.estructura_agent = estructura_mod.StructureAnalystAgent()
        self.regimen_agent = regimen_mod.RegimeAnalystAgent()
        self.posicionamiento_agent = pos_mod.PositioningAnalystAgent()
        self.debate_agent = debate_mod.DebateUnitAgent()
        self.fund_manager_agent = fm_mod.FundManagerAgent()

        self.skips: Dict[str, int] = {}

    def _skip(self, reason: str) -> None:
        self.skips[reason] = self.skips.get(reason, 0) + 1

    @staticmethod
    def _retorno(window: pd.DataFrame, sesiones: int) -> Optional[float]:
        """
        Rentabilidad a `sesiones` vista sobre la ventana que termina en `t`.

        Devuelve None —no 0.0— cuando no hay histórico suficiente: el Analista
        Técnico distingue «no evaluable» de «rentabilidad nula» y puntúa cada
        caso de forma distinta.
        """
        if len(window) <= sesiones:
            return None
        base = float(window["Close"].iloc[-1 - sesiones])
        if not base:
            return None
        return round(float(window["Close"].iloc[-1]) / base - 1.0, 4)

    def build_state(self, ticker: str, date: pd.Timestamp) -> Optional[Dict[str, Any]]:
        """Estado equivalente al de `node_ingest_and_reconcile` en la fecha `date`."""
        window = self.prices.window(ticker, date, lookback_days=365)
        if window is None or len(window) < MIN_WINDOW_ROWS:
            self._skip("historia_insuficiente")
            return None

        # Indicadores calculados por la MISMA función que usa producción, sobre
        # una ventana que termina en `date`. Copia defensiva: pandas escribiría
        # las columnas de indicadores sobre el DataFrame cacheado.
        df = self.fetcher._add_technical_indicators(window.copy())
        technical = self.fetcher._extract_latest_tech_metrics(df)

        if self.mode == "technical_only":
            fundamentals = {"revenue_growth": None, "net_margin": None,
                            "debt_to_equity": None, "roe": None, "pe_ratio": None,
                            "market_cap": 0, "available": True,
                            "as_of_period_end": None, "filed": None}
            sec_payload = {"status": "NOT_USED", "source": "SEC EDGAR"}
            estados = {"disponible": False, "bloques_ok": [],
                       "bloques_fallidos": ["balance", "resultados", "flujos"],
                       "balance": {}, "resultados": {}, "flujos": {},
                       "motivo": "modo technical_only: la capa fundamental está neutralizada"}
        else:
            fundamentals = self.fundamentals.as_of(ticker, date)
            if not fundamentals.get("available"):
                self._skip("sin_fundamentales")
                return None
            sec_payload = self.fundamentals.sec_payload(ticker, date)
            # Estados financieros point-in-time para el Analista de Calidad.
            estados = self.fundamentals.estados_financieros(ticker, date)

        yf_data = {
            "status": "SUCCESS",
            "ticker": ticker.upper(),
            "company_name": ticker.upper(),
            "sector": self.sector_map.get(ticker.upper(), "Desconocido"),
            "industry": "Desconocido",
            "current_price": float(window["Close"].iloc[-1]),
            "fundamentals": {k: fundamentals[k] for k in
                             ("revenue_growth", "net_margin", "debt_to_equity", "roe",
                              "pe_ratio", "market_cap")},
            "technical": technical,
            "estados_financieros": estados,
            # Mínimos de las N sesiones ANTERIORES, calculados con la MISMA
            # función pura que usa `DataFetcher.fetch_all` en producción
            # (`src.tools.niveles.minimos_previos`) sobre la misma ventana que
            # ya se ha cortado en `date` inclusive. Una segunda implementación
            # sería el bug de clase que la arquitectura prohíbe.
            "niveles_precio": minimos_previos(df),
            "price_history_summary": {
                "min_52w": float(window["Low"].min()),
                "max_52w": float(window["High"].max()),
                "close_today": float(window["Close"].iloc[-1]),
                "change_1m_pct": self._retorno(window, 20),
                "change_3m_pct": self._retorno(window, 63),
                "change_6m_pct": self._retorno(window, 126),
                "change_12m_pct": self._retorno(window, 252),
                "sesiones": int(len(window)),
            },
        }

        # Finnhub no ofrece histórico point-in-time gratuito: se declara ausente.
        # Solo altera `confidence_score`, que en la Fase 1 se verificó que no
        # interviene en ninguna decisión (fundamental.py:41-42 únicamente añade
        # un motivo al texto).
        fh_data = {"status": "NOT_AVAILABLE_IN_BACKTEST", "source": "Finnhub"}

        rec = self.reconciler.reconcile(ticker, yf_data, sec_payload, fh_data)

        return {
            "ticker": ticker.upper(),
            "company_name": yf_data["company_name"],
            "sector": yf_data["sector"],
            "industry": yf_data["industry"],
            "yfinance_data": yf_data,
            "sec_edgar_data": sec_payload,
            "finnhub_data": fh_data,
            "reconciliation_data": rec,
            # Posicionamiento en futuros conocible en `date`: el COTStore filtra
            # por fecha de PUBLICACIÓN del informe, nunca por la del informe.
            "futures_data": (self.cot_store.contexto(date) if self.cot_store else {}),
            # Régimen de volatilidad conocible en `date`. A diferencia de la
            # cadena de opciones, ESTA capa sí es reconstruible point-in-time:
            # ALFRED devuelve la serie tal y como se conocía y `FREDStore` invoca
            # la MISMA función de selección de producción con `as_of`.
            "regimen_data": (self.fred_store.contexto(date) if self.fred_store else {}),
            # Cadena de opciones: no reconstruible point-in-time con fuentes
            # gratuitas. Se declara ausente CON SU MOTIVO en vez de omitirse,
            # para que el informe del backtest pueda decir por qué el ajuste de
            # entrada es siempre nulo en el estudio.
            "options_data": {
                "disponible": False, "ticker": ticker.upper(),
                "motivo": ("sin histórico de cadenas de opciones point-in-time: "
                           "el open interest y la volatilidad implícita históricos "
                           "son de pago"),
                "contratos": [], "agregados": {}, "historico": [],
                "n_dias_historico": 0,
            },
            # Memoria de reflexión conocible en `date`. A diferencia de la cadena
            # de opciones, esta capa SÍ es reconstruible point-in-time: solo
            # entran observaciones cuya fecha de desenlace es anterior o igual a
            # `date`, y quien garantiza ese filtro es `MemoriaReflexion`.
            "reflexion_data": self.reflexion_dosier or {},
            "workflow_status": "INGESTED",
            # Sin `news_data` ni `news_report`: el nodo de noticias queda fuera
            # del replay a propósito (ver el encabezado del módulo). Los agentes
            # que los consultan lo hacen con `.get()` y un valor por defecto, de
            # modo que su ausencia reproduce el comportamiento previo exacto.
            "passed_fundamental_gatekeeper": False,
            "logs": [],
            # Cierres de la ventana YA CORTADA en `date` inclusive, para la
            # diferenciación fraccional. Va con prefijo `_` y se consume con
            # `pop`: no es un dato de análisis sino un insumo del meta-modelo, y
            # dejarlo en el estado lo metería en `daily_selection.json`.
            "_cierres_ffd": [float(x) for x in window["Close"].tolist()],
            "_fundamentals_meta": {
                "as_of_period_end": fundamentals.get("as_of_period_end"),
                "filed": fundamentals.get("filed"),
            },
        }

    def signal(self, ticker: str, date) -> Optional[Signal]:
        """Recorre el grafo real y devuelve la señal resultante."""
        date = pd.Timestamp(date)
        state = self.build_state(ticker, date)
        if state is None:
            return None

        # Analista de Calidad: mismo lugar que en el grafo de producción, entre
        # la ingesta y el gatekeeper, para que sus banderas rojas estén
        # disponibles también en la rama de rechazo.
        state["quality_report"] = self.quality_agent.analyze(state)

        # Analista de Régimen: tercera rama del fan-out en el grafo de
        # producción, así que corre antes del enrutado y su lectura queda
        # disponible también para los valores rechazados.
        state["regimen_report"] = self.regimen_agent.analyze(state)

        if self.mode == "technical_only":
            # Gatekeeper neutralizado: se omite el nodo fundamental y se fuerza
            # la rama aprobada. Los agentes técnico, de debate y fund manager se
            # ejecutan sin modificar.
            state["fundamental_report"] = {
                "passed_gatekeeper": True, "status": "NEUTRALIZADO",
                "metrics": state["reconciliation_data"]["reconciled_metrics"],
                "reasons": [], "confidence_score": 1.0, "discrepancies": [],
                "summary": "Gatekeeper fundamental neutralizado (modo technical_only).",
            }
            state["passed_fundamental_gatekeeper"] = True
        else:
            report = self.fundamental_agent.analyze(state)
            state["fundamental_report"] = report
            state["passed_fundamental_gatekeeper"] = report["passed_gatekeeper"]

        if route_after_gatekeeper(state) == "technical_analysis":
            state["technical_report"] = self.technical_agent.analyze(state)
            # Mismo lugar que en el grafo de producción: entre el técnico y el
            # posicionamiento, porque consume `close` y `atr` y su `soporte` es
            # candidato de nivel para el ajuste de entrada.
            if self.con_estructura:
                state["estructura_report"] = self.estructura_agent.analyze(state)
            # Mismo lugar que en el grafo de producción: entre la estructura y el
            # debate, porque consume `momentum_score`, `sobreextendido`, `atr` y
            # el soporte estructural.
            state["positioning_report"] = self.posicionamiento_agent.analyze(state)
            state["debate_report"] = self.debate_agent.analyze(state)

        # Variables del meta-modelo. Se extraen SIEMPRE —también en la rama de
        # rechazo, donde quedarán casi todas a `None`— porque son el insumo del
        # banco de etiquetas, y ese banco solo anota compras: la asimetría la
        # resuelve `anotar_senales`, no este punto.
        vars_meta = variables_de_senal(state, frac_diff=self._frac_diff(state))
        state["meta_data"] = self._meta(vars_meta)

        decision = self.fund_manager_agent.analyze(state)

        tech = state["yfinance_data"]["technical"]
        meta = state["_fundamentals_meta"]
        quality = state.get("quality_report", {}) or {}
        posicion = state.get("positioning_report", {}) or {}
        estructura = state.get("estructura_report", {}) or {}
        regimen = state.get("regimen_report", {}) or {}
        return Signal(
            ticker=ticker.upper(),
            date=date,
            rating=decision["rating"],
            momentum=state.get("technical_report", {}).get("momentum_classification"),
            passed_gatekeeper=state["passed_fundamental_gatekeeper"],
            close=float(tech["close"]),
            atr=float(tech["atr"]),
            rsi=float(tech["rsi"]),
            stop_loss=decision["stop_loss_atr"],
            take_profit=decision["take_profit_atr"],
            # Peso numérico emitido por el propio Fund Manager, ya escalado por
            # convicción, volatilidad y presupuesto de riesgo.
            target_weight=decision.get(
                "peso_objetivo", WEIGHT_BY_RATING.get(decision["rating"], 0.0)),
            sector=state["sector"],
            fundamentals_as_of=meta.get("as_of_period_end"),
            fundamentals_filed=meta.get("filed"),
            estilo=quality.get("style_classification"),
            conviccion=(quality.get("conviccion_fundamental") or {}).get("valor"),
            banderas_rojas=len(quality.get("banderas_rojas", [])),
            volatilidad=tech.get("volatilidad_anual"),
            sesgo_macro=posicion.get("sesgo_macro_clasificacion"),
            entrada_clasificacion=posicion.get("entrada_clasificacion"),
            # El precio de entrada objetivo llega ahora hasta el motor. La
            # comprobación es `is None` y NO `or`, igual que en el Fund Manager:
            # un objetivo de 0.0 es un dato corrupto, no una ausencia.
            precio_entrada_objetivo=posicion.get("precio_entrada_objetivo"),
            ajuste_entrada_pct=posicion.get("ajuste_entrada_pct"),
            nivel_origen=posicion.get("nivel_origen"),
            estructura=estructura.get("estructura"),
            distancia_soporte_atr=estructura.get("distancia_atr"),
            regimen=regimen.get("regimen_clasificacion"),
            variables_meta=vars_meta,
            horizonte_dias=int(decision.get("horizonte_dias") or 63),
            factor_meta=float(decision.get("factor_meta") or 1.0),
            factor_reflexion=float(decision.get("factor_reflexion") or 1.0),
        )

    def _frac_diff(self, state: Dict[str, Any]) -> Optional[float]:
        """
        Diferenciación fraccional del último cierre (AFML cap. 5).

        Se calcula sobre la MISMA ventana que ya está cortada en `t` inclusive,
        así que no puede mirar más allá de lo que la señal ya conoce. El `d` está
        fijado en `FFD_D`: buscarlo sobre la ventana que después se evalúa sería
        un ensayo más sin contar en el recuento del Sharpe deflactado.
        """
        cierres = state.pop("_cierres_ffd", None)
        if not cierres:
            return None
        from src.config import FFD_D, FFD_UMBRAL
        from src.tools.niveles import frac_diff_ultimo
        return frac_diff_ultimo(cierres, FFD_D, FFD_UMBRAL)

    def _meta(self, variables: Dict[str, Any]) -> Dict[str, Any]:
        """
        Probabilidad del meta-modelo para esta señal, o el neutro declarado.

        Sin artefacto devuelve `{}`, y el Fund Manager traduce eso a factor 1.0
        con `evaluable=False`. No se inventa una probabilidad: sustituirla por
        0.5 metería en la decisión un número que parecería una predicción.
        """
        if self.meta_artefacto is None:
            return {}
        p = self.meta_artefacto.probabilidad(variables)
        if p is None:
            return {}
        return {"probabilidad": p, "tasa_base": self.meta_artefacto.tasa_base,
                "entrenado_hasta": self.meta_artefacto.entrenado_hasta,
                "n_muestras": self.meta_artefacto.n_muestras}

    def signals_for_date(self, tickers: List[str], date) -> List[Signal]:
        out = []
        for t in tickers:
            try:
                s = self.signal(t, date)
            except Exception as exc:
                self._skip(f"excepcion:{type(exc).__name__}")
                continue
            if s is not None:
                out.append(s)
        return out
