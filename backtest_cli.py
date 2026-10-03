"""
CLI del backtest del sistema multi-agente.

Ejemplos
--------
    python backtest_cli.py --start 2015-01-01 --end 2025-12-31 --regime pit
    python backtest_cli.py --tickers AAPL,MSFT,NVDA --rebalance weekly --costs-bps 25
    python backtest_cli.py --regime biased      # contraste con look-ahead, etiquetado

El primer arranque descarga precios y companyfacts de la SEC a `data/cache/`.
A partir de ahí `--offline` reproduce el estudio sin red y bit a bit idéntico.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd

from src.backtest import metrics as M
from src.backtest.data import (
    COTStore, FREDStore, FundamentalStore, PriceStore, TodayFundamentalStore,
    rebalance_dates, trading_calendar,
)
from src.backtest.engine import (
    BacktestConfig, buy_and_hold, equal_weight, random_signal_benchmark, run_backtest,
)
from src.backtest.replay import (
    HistoricalReplayer, Signal, assert_llm_is_decision_neutral, disable_llm,
)
from src.backtest.report import generate_report
from src.config import (
    META_REENTRENAR_CADA_DIAS,
    ORDEN_LIMITADA_VIDA_SESIONES,
    REFLEXION_HORIZONTE_SESIONES,
    RIESGO_POR_POSICION_PCT,
)
from src.memoria import MemoriaReflexion, resolver_desde_precios
from src.meta import BancoDeEtiquetas, VARIABLES_META, entrenar

# Universo por defecto: grandes capitalizaciones estadounidenses con historia
# larga y cobertura XBRL completa en EDGAR.
#
# SESGO DE SUPERVIVENCIA DECLARADO: es una lista fija elegida HOY. Excluye por
# construcción a las empresas que quebraron, fueron excluidas de cotización o
# absorbidas durante el periodo (Lehman, GE tras su desplome, First Republic,
# Bed Bath & Beyond...). Cualquier resultado positivo está inflado por esto y no
# hay corrección posible sin las composiciones históricas del índice, que son de
# pago. Se documenta en el informe en lugar de disimularse.
DEFAULT_UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "ADBE", "CRM",
    "AMD", "INTC", "CSCO", "ORCL", "QCOM", "TXN", "IBM", "NOW", "INTU", "AMAT",
    "JPM", "BAC", "WFC", "GS", "V", "MA", "AXP",
    "JNJ", "UNH", "PFE", "ABBV", "MRK", "LLY", "TMO",
    "WMT", "HD", "PG", "KO", "PEP", "MCD", "NKE", "COST",
    "XOM", "CVX", "CAT", "BA", "HON", "GE", "UPS", "DIS",
]

BENCHMARK = "SPY"


class PrecomputedReplayer:
    """
    Sirve señales ya calculadas. Permite reejecutar el motor de cartera con
    distintos costes o parámetros sin recalcular el replay, que es la parte cara
    — y garantiza que todas las variantes comparan exactamente las mismas
    señales.
    """

    def __init__(self, by_date: Dict[pd.Timestamp, List[Signal]], skips: Dict[str, int]):
        self.by_date = by_date
        self.skips = skips

    def signals_for_date(self, tickers, date):  # noqa: ARG002
        return self.by_date.get(pd.Timestamp(date), [])


def resumen_reflexion(memoria, by_date: Dict[pd.Timestamp, List[Signal]]) -> Dict[str, Any]:
    """
    Cuánto llegó a actuar la memoria de reflexión durante el estudio.

    Es diagnóstico, no rendimiento. Una capa que no recortó nunca y una que
    recortó y no mejoró el resultado son dos conclusiones distintas, y sin estas
    cifras el informe no puede distinguirlas: la primera pide más histórico o un
    umbral más bajo, la segunda pide retirar la capa.
    """
    total = sum(len(v) for v in by_date.values())
    if memoria is None:
        return {"activa": False,
                "motivo": "desactivada por defecto tras el contraste de 2015-2025; "
                          "se activa con --con-reflexion",
                "senales_evaluadas": total}

    factores = [s.factor_reflexion for v in by_date.values() for s in v]
    recortadas = [f for f in factores if f < 1.0]
    desenlazadas = sum(1 for o in memoria.observaciones if o.retorno_exceso is not None)
    primera = next((str(pd.Timestamp(d).date()) for d in sorted(by_date)
                    for s in by_date[d] if s.factor_reflexion < 1.0), None)

    return {
        "activa": True,
        "horizonte_sesiones": REFLEXION_HORIZONTE_SESIONES,
        "senales_evaluadas": total,
        "observaciones_anotadas": len(memoria.observaciones),
        "observaciones_desenlazadas": desenlazadas,
        "senales_recortadas": len(recortadas),
        "pct_senales_recortadas": (len(recortadas) / total) if total else 0.0,
        "factor_medio_cuando_recorta": (sum(recortadas) / len(recortadas)) if recortadas else None,
        "primer_recorte": primera,
        "media_global_final": round(memoria._global.media, 5) if memoria._global.n else None,
    }


def load_sector_map(tickers: List[str], offline: bool) -> Dict[str, str]:
    """
    Sector actual de cada ticker, para la atribución.

    Se usa el sector de HOY también para el pasado. Es una imprecisión menor y
    declarada: los cambios de clasificación GICS son raros y no afectan a
    ninguna decisión, solo al desglose descriptivo.
    """
    store = TodayFundamentalStore(offline=offline)
    out = {}
    for t in tickers:
        path = store.cache_dir / f"{t.upper()}.json"
        if not path.exists() and not offline:
            store.as_of(t, pd.Timestamp("2020-01-01"))
        if path.exists():
            try:
                info = json.loads(path.read_text(encoding="utf-8"))
                out[t.upper()] = info.get("sector") or "Desconocido"
            except Exception:
                out[t.upper()] = "Desconocido"
    return out


def build_limitations(regime: str, n_trades: int, skips: Dict[str, int],
                      n_universe: int, years: float, avg_exposure: float = 0.0,
                      reflexion: Dict[str, Any] = None) -> List[str]:
    lims: List[str] = []

    refl = reflexion or {}
    if refl.get("activa"):
        pct = refl.get("pct_senales_recortadas") or 0.0
        lims.append(
            "**Esta ejecución lleva ACTIVA la memoria de reflexión, que el contraste de "
            "2015-2025 refutó** (`--con-reflexion`). Con ella el percentil frente a selección "
            "aleatoria cayó de 7.4 a 3.1 y la expectativa por operación de +1.23% a +0.95%. "
            f"Hoy recorta el {pct:.1%} de las señales. El resultado de abajo NO es el del "
            "sistema tal y como se entrega: para eso, ejecutar sin esa bandera.")
        lims.append(
            "**La memoria de reflexión se calibra sobre el MISMO histórico que evalúa.** "
            "Aunque respete la disciplina point-in-time —solo entran observaciones cuyo "
            "desenlace ya ocurrió, y `test_la_memoria_respeta_la_fecha_de_desenlace` lo fija— "
            "el resultado no es enteramente fuera de muestra. Cualquier lectura de esta capa, "
            "incluida la negativa, exigiría validación walk-forward para ser concluyente.")
    elif refl:
        lims.append(
            "**La memoria de reflexión está desactivada**, que es la configuración de "
            "entrega. Se implementó como traducción determinista de la *low-level reflection* "
            "de FinAgent y se midió contra su contrafactual exacto sobre 2015-2025: empeoró "
            "las dos métricas de selección (percentil aleatorio 7.4 → 3.1, expectativa "
            "+1.23% → +0.95%) además del CAGR, el Sharpe y el drawdown. El código, sus tests "
            "y este contraste se conservan; la capa no decide. **Ese resultado negativo es "
            "publicable y no debe suavizarse: es exactamente el contraste que los dos papers "
            "de referencia no llegan a ejecutar.**")

    if avg_exposure < 0.6:
        idle = 1 - avg_exposure
        lims.append(
            f"**La liquidez ociosa no renta nada, y es la mayor parte de la cartera.** La "
            f"exposición bruta media es del {avg_exposure:.1%}, así que un {idle:.0%} del "
            "capital permanece en efectivo al 0%. Remunerarlo a letras del Tesoro (~2% medio "
            f"en 2015-2025) añadiría del orden de {idle * 0.02:.1%} anual al resultado. La "
            "conclusión no cambia, pero la cifra publicada es algo más pesimista de lo que "
            "sería con una gestión de tesorería realista.")
        lims.append(
            "**La exposición es una CONSECUENCIA del presupuesto de riesgo, no un objetivo.** "
            "El motor histórico dimensiona ya con `src/portfolio/construccion.py` —la misma "
            "capa que corre en vivo: límites por sector, penalización por correlación y "
            "presupuesto de riesgo agregado—, así que la cartera simulada es la que el "
            "sistema recomendaría hoy. Pero el tamaño de cada posición sale de arriesgar un "
            f"{RIESGO_POR_POSICION_PCT:.2%} del patrimonio contra la distancia al stop, y con "
            f"pocas señales simultáneas eso deja la exposición bruta en el {avg_exposure:.0%}. "
            "**El sistema no define qué hacer con el resto**, y esa es una decisión de diseño "
            "que falta: una estrategia estructuralmente invertida a un tercio no puede "
            "compararse contra un índice invertido al 100% sin decirlo. Las métricas "
            "ajustadas por riesgo (Sharpe, Sortino) son la comparación honesta; el CAGR "
            "absoluto no lo es.")

    if regime == "pit":
        lims.append(
            "**Divergencia de definición fundamental.** Producción lee métricas TTM de "
            "`yfinance.info`; el backtest usa cifras ANUALES (10-K) point-in-time de SEC EDGAR, "
            "porque el TTM histórico de yfinance no es recuperable retroactivamente. El "
            "gatekeeper se evalúa por tanto con una ventana contable distinta a la de "
            "producción: los ratings del backtest son fieles a la *lógica* del sistema, no "
            "necesariamente idénticos a los que habría emitido en directo.")
    elif regime == "biased":
        lims.append(
            "**LOOK-AHEAD FUNDAMENTAL DELIBERADO.** Este régimen aplica los fundamentales de "
            "HOY a todo el pasado, que es lo que haría el código de producción tal cual. El "
            "gatekeeper filtra el pasado sabiendo qué empresas acabaron siendo rentables. "
            "Los resultados NO son alcanzables y sirven solo para medir el tamaño del sesgo.")
    else:
        lims.append(
            "**Gatekeeper neutralizado.** Este régimen desactiva el filtro fundamental para "
            "aislar la capa técnica. No mide el sistema completo, sino la mitad de él.")

    lims.append(
        "**El ajuste de entrada que este estudio mide NO es el que produce la cadena de "
        "opciones.** El Analista de Posicionamiento elige el nivel entre cuatro candidatos: "
        "soporte de open interest, max pain, punto de inflexión de la gamma y **soporte "
        "estructural del precio**. Los tres primeros salen de la cadena, cuyo histórico por "
        "ticker es de pago, así que en el estudio están siempre ausentes. El cuarto sale del "
        "OHLCV y sí es reconstruible point-in-time, y por eso el ajuste de entrada por fin se "
        "mide — pero se mide **con soportes de precio, no con open interest**. Son dos niveles "
        "distintos y el informe no los promedia: lo que estas cifras evalúan es la regla de "
        "entrada apoyada en la estructura del precio. La versión que corre en vivo, con cadena "
        "disponible, elegirá a veces otro nivel.")

    lims.append(
        "**Medido: esperar al soporte NO mejora el resultado, y probablemente lo empeora.** "
        "Sobre las 936 señales de compra del régimen `pit`, con los stops y objetivos del "
        "propio Fund Manager y 10 pb de costes, entrar al nivel MEJORA la operación "
        "(expectativa +1.70% frente a +1.34%, factor de beneficio 1.53 frente a 1.43) y "
        "EMPEORA el valor esperado por señal (+0.78% frente a +1.34%), porque lo que la orden "
        "no rellena es precisamente lo que sube: esas señales habrían rendido +3.56% con un "
        "**59.6% de acierto** frente al 45.3% de la línea base. La selección adversa cancela "
        "exactamente la mejora de precio. Por eso `--con-entrada-limitada` existe pero está "
        "DESACTIVADA por defecto: es una medición, no una preferencia.")

    lims.append(
        "**Del posicionamiento en futuros solo se mide el veto.** El bloque macro sí es "
        "reconstruible: `COTStore` filtra los informes de la CFTC por fecha de PUBLICACIÓN "
        "(viernes) y no por la del informe (martes), que es el mismo par `filed`/`end` de los "
        "hechos XBRL. Lo que el estudio mide es por tanto el veto que topa en COMPRA con "
        "viento macro fuertemente en contra; la dirección macro, por sí sola, no elige nivel.")

    lims.append(
        "**Del régimen de volatilidad se mide el 100%, y es la única capa de la que puede "
        "decirse.** `VIXCLS` y `VXVCLS` llegan por ALFRED, cuyos parámetros de tiempo real "
        "devuelven la serie tal y como se conocía en una fecha y adjuntan a cada observación "
        "su fecha de publicación. Verificado contra la API: la observación semanal del "
        "miércoles 2020-03-25 es invisible consultando ese mismo día y aparece el 26. El "
        "retardo no hay que modelarlo, hay que no estorbarlo, y `FREDStore` invoca la MISMA "
        "función de selección de producción con `as_of` en lugar de reimplementarla.")

    lims.append(
        "**La curva de volatilidad no es reconstruible antes de 2014.** `VXVCLS` observa desde "
        "2007 pero su ARCHIVO en ALFRED empieza en 2014: pedir 2013 devuelve «the series does "
        "not exist in ALFRED». No afecta a la ventana del estudio, que empieza en 2015, pero sí "
        "acota cualquier extensión hacia atrás. Cuando falta, `ratio_curva` es `None` y el "
        "agravamiento por curva invertida no se aplica — nunca se asume contango.")

    lims.append(
        "**El meta-modelo está DESACTIVADO, y es una medición, no una duda de diseño.** "
        "`--con-meta` activa el meta-etiquetado de López de Prado con reentrenamiento "
        "walk-forward, CV purgada con embargo y pesos por unicidad. En las OCHO ventanas "
        "con muestra suficiente la AUC en validación cruzada purgada salió por DEBAJO de "
        "0.5 —0.40, 0.40, 0.45, 0.45, 0.47, 0.47, 0.44, 0.47— así que la barrera de "
        "`META_VENTAJA_MINIMA_AUC` impidió entregar artefacto en todas ellas y el factor "
        "se quedó en 1.0. Ejecutar con y sin la bandera produce cifras idénticas. "
        "**La lectura es que las 23 variables que el sistema conoce al emitir una señal no "
        "contienen información utilizable sobre si esa compra concreta acabará en "
        "beneficio**, lo que es coherente con el hallazgo ya publicado de que el rating "
        "tampoco ordena el rendimiento futuro.")

    lims.append(
        "**La caché del COT no cubría siete de los once años del estudio, y ahora sí.** "
        "`data/cache/cot/` solo contenía 2022-2026, así que el veto macro que este informe "
        "afirmaba medir estuvo INERTE de 2015 a 2021. Recargada de 2013 en adelante con la "
        "misma función de producción, el veto actúa: **la tasa de acierto sube 2.5 puntos** "
        "(47.3% → 49.8%) sobre 532 operaciones, la expectativa pasa de +1.283% a +1.291% "
        "y el percentil frente a selección aleatoria de 16.6 a 17.7 — las dos últimas, "
        "mejoras marginales. El drawdown empeora de −15.57% a −16.15%. **El valor de esta "
        "corrección no es el rendimiento sino la corrección misma: un informe que afirmaba "
        "medir un veto que llevaba siete años inerte estaba equivocado, y lo seguía "
        "estando aunque el efecto resulte modesto.**")

    lims.append(
        "**Del sesgo macro se mide la pata de ÍNDICE; la SECTORIAL falta antes de 2022.** "
        "Los nombres de mercado de la CFTC cambiaron: el patrón `COPPER- #1` no casa con "
        "`COPPER-GRADE #1`, ni `NAT GAS NYME` con `NATURAL GAS`, ni `UST 10Y NOTE` con "
        "`10-YEAR U.S. TREASURY NOTES`. Los patrones estaban verificados contra "
        "`deacot2025.zip` y solo contra ese. El contrato de índice —`E-MINI S&P 500`, que "
        "reciben TODOS los valores— sí resuelve con 520 semanas, así que el sesgo macro se "
        "calcula para todos; lo que falta es la pata sectorial de energía, materiales y "
        "financieras en el primer tramo del estudio.")

    lims.append(
        "**El freno por drawdown está implementado y es INERTE EN PRODUCCIÓN.** "
        "`drawdown_guard` traducido a un factor que solo recorta la exposición. El "
        "backtest conoce la curva de capital; producción NO: el sistema emite "
        "recomendaciones, no gestiona una cartera y no sabe su patrimonio. Cablearlo solo "
        "en el estudio sería una variable de decisión medida aquí y ausente en vivo — la "
        "imagen especular exacta de la divergencia del ajuste de entrada. Por eso el "
        "parámetro es opcional y neutro por defecto, y por eso estas cifras NO lo "
        "incluyen.")

    lims.append(
        "**El sesgo de reajuste retroactivo de los precios sigue SIN CUANTIFICAR.** yfinance "
        "sirve precios ajustados por splits y dividendos con la información de hoy, así que el "
        "precio de 2015 que se descarga hoy no es el que vio un observador de 2015. Afecta por "
        "igual a los indicadores técnicos y a los soportes estructurales. La Fase 1 buscó una "
        "fuente EOD independiente para acotarlo y la única gratuita probada está tras un "
        "desafío anti-bot, así que la magnitud del efecto es desconocida.")

    lims.append(
        "**El signo de la exposición gamma es una convención, no una medición.** Se asume que "
        "los creadores de mercado están largos gamma en calls y cortos en puts. Es la "
        "convención estándar del sector, pero la cadena publica open interest y no quién está "
        "en cada lado de cada contrato. Si esa convención falla en un valor concreto, el punto "
        "de inflexión calculado apunta al lado contrario. Solo afecta a producción: en el "
        "backtest no hay cadena.")

    lims.append(
        "**Los percentiles de put/call y de skew necesitan histórico propio.** Se calculan "
        "sobre la caché acumulativa de cadenas diarias, así que una instalación nueva no puede "
        "emitirlos hasta acumular `OPCIONES_MINIMO_DIAS_HISTORICO` observaciones. Hasta "
        "entonces se declaran DATOS_INSUFICIENTES en lugar de asumir el percentil 50, y el "
        "sesgo de opciones se apoya solo en el punto de inflexión de la gamma.")

    lims.append(
        "**El mapa sector→futuro es sectorial, no industrial.** Bancos y REITs comparten la "
        "entrada del bono a 10 años pese a no responder igual al mismo contrato, y «Basic "
        "Materials» mezcla mineras de metales industriales con químicas. Los sectores sin "
        "contrato correlato claro no reciben pata sectorial y se evalúan solo con el índice: "
        "se declara NO_APLICABLE en lugar de forzar un proxy.")

    lims.append(
        "**Normas sectoriales estáticas.** El contexto de valoración compara cada múltiplo "
        "contra una mediana de largo plazo del mercado estadounidense (`SECTOR_NORMAS` en "
        "`src/config.py`), no contra la mediana viva del sector en la fecha simulada. En un "
        "backtest de once años eso introduce un anacronismo: el P/E mediano del software en "
        "2015 no era el de 2025. Las etiquetas de estilo ordenan y contextualizan, pero no "
        "deben leerse como una valoración relativa exacta.")

    lims.append(
        "**Coste de capital constante.** El ROIC se compara contra un WACC de referencia "
        "único (`WACC_REFERENCIA`) en lugar de estimarlo por empresa y por fecha. Es una "
        "decisión consciente —la dispersión de un WACC estimado con beta y estructura de "
        "capital superaría la señal que aporta— pero implica que «crea valor» significa "
        "«supera un umbral fijo», no «supera su propio coste de capital».")

    lims.append(
        f"**Sesgo de supervivencia.** El universo son {n_universe} valores seleccionados hoy "
        "por su relevancia actual. Las empresas que quebraron o fueron excluidas nunca entran "
        "en la muestra, lo que infla el resultado en una magnitud no cuantificada aquí "
        "(la literatura sitúa el efecto entre 1 y 4 puntos de CAGR según periodo y universo).")

    if n_trades < 100:
        lims.append(
            f"**Muestra pequeña.** {n_trades} operaciones en {years:.1f} años. Con este tamaño "
            "el intervalo de confianza del Sharpe es tan ancho que no permite descartar el azar.")

    lims.append(
        "**Deuda/Capital ausente se trata como 0.0.** Se replica el comportamiento de "
        "producción (`info.get(\"debtToEquity\", 0.0)`), lo que hace que el filtro de "
        "apalancamiento se salte silenciosamente cuando el dato falta en EDGAR, en lugar de "
        "rechazar el valor.")

    lims.append(
        "**Finnhub ausente en el backtest.** No hay histórico point-in-time gratuito, así que "
        "el `confidence_score` de la reconciliación difiere del de producción. Verificado en "
        "la Fase 1 que no altera ninguna decisión (solo añade texto), pero es una divergencia real.")

    lims.append(
        "**Analista de Noticias excluido del backtest.** El grafo de producción ejecuta un "
        "nodo `news_analysis` que este replay NO recorre. Dos de sus tres fuentes (Google News "
        "RSS y Tavily) son buscadores \"de hoy\": no existe forma asequible de recuperar qué "
        "estaba publicado y visible en una fecha pasada, y sus corpus indexados hoy omiten lo "
        "que se borró y fechan por republicación, no por el hecho. Solo el 8-K con Ítem 2.02 "
        "tiene `filed` exacto y sería reconstruible. Por eso las noticias son hoy una CAPA "
        "ASESORA: aparecen en el informe diario y alimentan el debate, pero no tocan `rating` "
        "ni `position_size_pct`, de modo que su ausencia aquí no altera ni una sola señal. "
        "La contrapartida es que el valor predictivo de esa capa está SIN MEDIR: no hay "
        "ninguna evidencia en este informe de que las noticias aporten nada.")

    lims.append(
        "**Sin datos intradía.** Cuando stop y objetivo se tocan en la misma sesión se asume "
        "que saltó el stop. Es conservador, pero desconoce el orden real y sesga el resultado "
        "a la baja en una cuantía desconocida.")

    lims.append(
        "**Costes estimados, no reales.** Comisión y slippage son parámetros fijos en puntos "
        "básicos. No modelan impacto de mercado, y para tamaños grandes de cartera el "
        "deslizamiento real crecería con el volumen.")

    if skips:
        lims.append(
            f"**Cobertura incompleta de señales.** Descartes por falta de datos: {skips}. "
            "Los tickers sin fundamentales publicados en una fecha simplemente no generan "
            "señal, lo que reduce el universo efectivo en los primeros años del estudio.")

    lims.append(
        "**El percentil frente a selección aleatoria arrastra ruido de muestreo.** La misma "
        "estrategia —mismo CAGR al cuarto decimal, mismas 532 operaciones, misma "
        "expectativa— da percentil 20.3 con 300 muestras de Monte Carlo y 17.7 con 1000. "
        "Son del orden de 2.6 puntos de ruido. Las cifras publicadas usan siempre las 1000 "
        "por defecto, y **una diferencia de percentil por debajo de uno o dos puntos entre "
        "configuraciones no es interpretable.**")

    lims.append(
        "**Contrastes múltiples.** Se han evaluado varios regímenes, frecuencias y niveles de "
        "coste sobre el mismo periodo histórico. El p-valor mostrado no está corregido por "
        "multiplicidad: interprétese como orientativo, no como una prueba formal.")

    return lims


NEXT_STEPS = [
    "RESUELTO — la regla de ejecución de ÓRDENES LIMITADAS ya está en `engine.py`. La orden "
    "lleva como límite el `precio_entrada_objetivo`, vive `vida_orden_sesiones` sesiones, se "
    "rellena a la apertura si esta abre por debajo del límite, al límite si el mínimo lo toca, "
    "y **se cancela sin abrir posición** si expira. Esa tercera rama es la que hace honesta la "
    "comparación. Se activa con `--con-entrada-limitada` y está DESACTIVADA por defecto porque "
    "la medición la desaconseja, no porque falte código.",
    "NO comprar histórico de cadenas de opciones todavía. La pregunta que justificaba el gasto "
    "—«¿mejora el resultado entrar más abajo?»— ya tiene respuesta medida, y es que NO: sobre "
    "las 936 señales de compra del estudio, entrar al soporte mejora la operación (+1.70% "
    "frente a +1.34% de expectativa) y empeora el valor esperado por señal (+0.78% frente a "
    "+1.34%), porque lo que la orden no rellena acierta el 59.6% de las veces. Un nivel MEJOR "
    "—de open interest en vez de de precio— podría cambiar la magnitud, pero tendría que "
    "invertir el signo de la selección adversa para cambiar la conclusión, y no hay ninguna "
    "razón para esperar que lo haga. Reconsiderarlo solo con evidencia en vivo.",
    "Ampliar los patrones de `SECTOR_A_FUTURO` para que casen con las DOS convenciones "
    "de nombres de la CFTC (`COPPER-GRADE #1` y `COPPER- #1`, `NATURAL GAS` y "
    "`NAT GAS NYME`, `10-YEAR U.S. TREASURY NOTES` y `UST 10Y NOTE`). `_elegir_mercado` "
    "ya resuelve la ambigüedad quedándose con el de mayor interés abierto, así que el "
    "mecanismo existe. NO se hizo en esta revalidación porque cambiaría el dosier macro de "
    "producción sin medirlo, y el presupuesto de ensayos ya estaba gastado: hacerlo exige "
    "su propio contraste.",
    "Reevaluar el meta-etiquetado con OTRO universo o con etiquetas de horizonte más "
    "corto. Lo medido aquí es que las 23 variables del sistema no separan las compras que "
    "funcionan de las que no, con AUC bajo 0.5 en ocho ventanas. Antes de volver a "
    "intentarlo conviene resolver la pregunta de la que depende: **por qué el rating no "
    "ordena el rendimiento futuro**. Un meta-modelo sobre los insumos de una señal cuya "
    "dirección no ordena difícilmente puede ordenar él.",
    "Decidir qué hacer con el freno por drawdown. Está implementado y probado pero es "
    "inerte en producción porque el sistema no gestiona una cartera. Las dos salidas "
    "honestas son: persistir una curva de capital en producción —lo que exige que el "
    "sistema sepa qué se ejecutó, y hoy no lo sabe— o retirarlo. Dejarlo activo solo en el "
    "backtest no es una de ellas.",
    "PRIORIDAD 1 DE ESTA REVALIDACIÓN — validar walk-forward el umbral de TENSION del "
    "régimen de volatilidad. El barrido midió que subirlo de 25 a 30 es la MEJOR de las "
    "trece configuraciones evaluadas (expectativa +1.44% frente a +1.28%, percentil 24.3 "
    "frente a 16.7), y que bajarlo a 20 no cambia absolutamente nada. La explicación es "
    "mecánica: `_clasificar_regimen` toma el MÁXIMO de los escalones por nivel y por "
    "z-score, y en esta ventana manda el z-score, así que bajar el corte de nivel queda "
    "enmascarado y subirlo hasta 30 deja el escalón TENSION casi inerte. La lectura sería "
    "que el escalón TENSION perjudica y solo el de PANICO aporta. **Pero se entrega 25, "
    "que es el valor fijado ANTES de medir**: tres puntos de una curva sobre el mismo "
    "histórico no acreditan un óptimo, acreditan que se ha buscado uno, y adoptar el que "
    "mejor midió sería el defecto que este proyecto ya documentó tres veces. La validación "
    "que lo resolvería: fijar el umbral con datos hasta 2019 y evaluar 2020-2025 sin "
    "volver a mirarlo.",
    "Comprobar si la bandera `soporte_lejano` merece existir. Duplicar su umbral de 1.5 a "
    "3.0 ATR mueve UNA operación de 535 y deja el acierto en 47.2% frente a 47.3%: es "
    "prácticamente inerte, así que el +2.7pp de acierto que aporta el Analista de "
    "Estructura viene del nivel de entrada y no de ella. O se reformula para que actúe, o "
    "se retira: una bandera que no dispara es código que hay que mantener sin contrapartida.",
    "Investigar por qué la selección adversa cancela EXACTAMENTE la mejora de precio. Lo "
    "llamativo de la medición no es que la regla limitada pierda por coste de oportunidad "
    "—eso era previsible— sino que la rentabilidad CONDICIONADA a operar sea prácticamente "
    "idéntica en las tres reglas (+1.71% a mercado, +1.76% al límite, +1.71% con recuperación "
    "confirmada). Si eso se sostiene en otro universo, dice algo sobre la eficiencia del precio "
    "de entrada a barra diaria que va mucho más allá de este sistema.",
    "Construir el `NewsStore` point-in-time sobre el índice diario de EDGAR "
    "(`edgar/daily-index/{año}/QTR{n}/form.{fecha}.idx`), que la Fase 1 acreditó como "
    "PIT-NATIVE: cada presentación viene con su fecha exacta y el archivo llega a 1994. Cubre "
    "resultados y hechos relevantes, no prensa general. Construirlo NO autoriza por sí solo a "
    "conectar las noticias a la decisión: siguen siendo asesoras hasta que el almacén cubra la "
    "ventana y `test_news_report_does_not_alter_decision` se retire deliberadamente.",
    "Validar empíricamente la convención de signo de la exposición gamma contrastando el "
    "`gamma_flip` calculado contra el comportamiento observado del precio en una muestra de "
    "valores, antes de darle más peso en la elección de nivel.",
    "Afinar el mapa sector→futuro a nivel de INDUSTRIA. Bancos y REITs no responden igual al "
    "bono a 10 años, y una aerolínea y una petrolera tienen signos opuestos frente al crudo "
    "pese a caer en sectores distintos hoy por casualidad.",
    "HIPÓTESIS DESCARTADA CON DATOS: la reflexión de bajo nivel de FinAgent (arXiv:2402.18485), "
    "traducida a reglas deterministas y medida contra su contrafactual exacto sobre 2015-2025, "
    "EMPEORA la selección: percentil frente a señales aleatorias 7.4 → 3.1, expectativa por "
    "operación +1.23% → +0.95%, drawdown −13.8% → −18.0%. La capa actuó (recortó el 18.3% de "
    "las señales con factor medio ×0.93), así que no es un problema de activación. La lectura "
    "más probable es que el rendimiento relativo de un perfil a un mes REVIERTE en lugar de "
    "persistir. La línea de investigación honesta no es invertir el signo sobre el mismo "
    "histórico —eso es el defecto metodológico de los papers de referencia— sino declarar la "
    "hipótesis contraria de antemano y contrastarla con validación walk-forward sobre "
    "2020-2025, o con otro horizonte de desenlace que el de 21 sesiones.",
    "PRIORIDAD 1 — investigar la ordenación del rating. Antes de tocar stops, sizing o "
    "costes, comprobar si el event study mantiene el orden invertido (VENTA FUERTE rindiendo "
    "más que COMPRA FUERTE) en otros universos y periodos. Si se confirma, el problema está "
    "en la señal y ningún ajuste de gestión de cartera lo arreglará.",
    "HIPÓTESIS DESCARTADA CON DATOS: no es un sesgo contra el *value*. La atribución por "
    "estilo (`attr_estilo`) muestra que las operaciones etiquetadas VALOR son las de MEJOR "
    "rentabilidad media del sistema, y que el lastre está en CRECIMIENTO, con rentabilidad "
    "media negativa pese a un número de operaciones similar. La línea de investigación "
    "correcta es por qué el sistema paga múltiplos de crecimiento que después no se "
    "materializan: revisar el peso del momentum en la puntuación compuesta y el umbral de "
    "PEG que habilita GARP.",
    "Medir por separado el efecto del stop de 2·ATR. Con más de la mitad de las salidas "
    "disparadas por stop y una tenencia media inferior a 20 sesiones, el sistema puede estar "
    "cortando posiciones ganadoras antes de que maduren. Ejecutar una variante sin stop y "
    "otra con stop por tiempo para aislarlo.",
    "Contratar o reconstruir las composiciones históricas del índice (CRSP, Norgate, "
    "Sharadar) para eliminar el sesgo de supervivencia, que hoy es el sesgo residual dominante.",
    "Sustituir los fundamentales anuales por TTM point-in-time encadenando los cuatro "
    "trimestres XBRL disponibles en cada fecha, para acercar el backtest a la definición "
    "exacta que usa producción.",
    "Validación walk-forward: fijar los umbrales del gatekeeper con datos hasta 2019 y "
    "evaluar 2020-2025 como out-of-sample estricto, sin volver a mirar el periodo de test.",
    "Añadir datos intradía (o al menos barras horarias) para resolver correctamente el "
    "orden entre stop y objetivo dentro de la misma sesión.",
    "Definir una política explícita para el capital no invertido. La exposición bruta que "
    "produce el presupuesto de riesgo es estructuralmente baja, y hoy el remanente se queda "
    "en efectivo al 0%. Las tres opciones razonables —remunerarlo a letras, invertirlo en el "
    "índice como posición residual, o subir el riesgo por posición— tienen implicaciones muy "
    "distintas y ninguna está tomada. Mientras no se decida, el CAGR absoluto compara una "
    "cartera a un tercio de exposición contra un índice al 100%.",
    "Sustituir `SECTOR_NORMAS` por la mediana calculada sobre un conjunto de comparables en "
    "cada fecha. Es lo que convierte el contexto sectorial de una referencia estática en una "
    "valoración relativa point-in-time, y elimina el anacronismo declarado en las "
    "limitaciones.",
    "Investigar por qué el rating sigue sin ordenar el rendimiento futuro pese a que la "
    "convicción fundamental ya entra en la decisión. La incorporación del Analista de "
    "Calidad mejoró notablemente el perfil de riesgo —el Sharpe casi se dobló y el drawdown "
    "máximo se redujo a la mitad— pero el orden de las categorías sigue invertido. Eso apunta "
    "a que el problema no está en la calidad del análisis fundamental sino en el corte que "
    "convierte la convicción en rating, o en el horizonte al que se mide: doce meses puede ser "
    "un plazo inadecuado para señales cuya tenencia media es de 33 sesiones.",
    "Reconstruir el riesgo legal y regulatorio de forma point-in-time desde EDGAR (8-K "
    "Ítem 8.01 y el apartado de Procedimientos Legales del 10-K). Es la única vía para que un "
    "litigio material entre en la decisión sin romper el backtest: a diferencia de la prensa, "
    "esas presentaciones tienen fecha `filed` exacta.",
    "Construir un `NewsStore` point-in-time antes de dejar que las noticias entren en la "
    "decisión. El único camino barato es el histórico completo de 8-K/10-Q de EDGAR filtrado "
    "por `filed <= t` (mismo patrón que `FundamentalStore`), que cubre resultados y hechos "
    "relevantes pero no prensa general; el resto exigiría un proveedor de archivo de noticias "
    "con marca temporal (RavenPack, Dow Jones DNA). Hasta entonces, subir el Analista de "
    "Noticias de capa asesora a variable de decisión dejaría el sistema sin backtest válido.",
    "Medir la capa de noticias por separado con un event study sobre los 8-K con Ítem 2.02, "
    "que sí son reconstruibles point-in-time: comparar el rendimiento a 1, 5 y 20 sesiones "
    "tras la presentación frente al resto del universo. Es la forma de saber si la "
    "`impact_probability` correlaciona con algo antes de darle peso en el rating.",
    "Ampliar el universo más allá de las megacaps estadounidenses y comprobar si el resultado "
    "sobrevive en small caps, donde los costes y el slippage son materialmente mayores.",
    "Ejecutar paper trading en directo durante 6-12 meses y comparar las señales reales con "
    "las que el replay produce para esas mismas fechas: es la única validación no retrospectiva.",
]


def main() -> int:
    p = argparse.ArgumentParser(description="Backtest del sistema multi-agente financiero")
    p.add_argument("--con-meta", action="store_true",
                   help="activa el meta-modelo con reentrenamiento walk-forward. "
                        "DESACTIVADO por defecto, igual que la memoria de reflexión: "
                        "una capa que modula el tamaño no se enciende hasta que su "
                        "contraste lo justifique")
    p.add_argument("--sin-estructura", action="store_true",
                   help="ablacion: omite el Analista de Estructura, de modo que el "
                        "nivel de entrada vuelve a depender solo de la cadena de "
                        "opciones (es decir, no hay nivel en el backtest)")
    p.add_argument("--sin-regimen", action="store_true",
                   help="omite la serie de volatilidad implicita: sin veto de regimen")
    p.add_argument("--con-entrada-limitada", action="store_true",
                   help="ejecuta el precio de entrada objetivo como orden LIMITADA "
                        "con vida acotada; si expira, la posicion NO se abre. Por "
                        "defecto se rellena a la apertura de t+1, que es el "
                        "comportamiento historico")
    p.add_argument("--vida-orden", type=int, default=ORDEN_LIMITADA_VIDA_SESIONES,
                   help="sesiones que vive una orden limitada antes de cancelarse")
    p.add_argument("--tickers", type=str, default="", help="Lista separada por comas (por defecto, universo interno)")
    p.add_argument("--start", type=str, default="2015-01-01")
    p.add_argument("--end", type=str, default="2025-12-31")
    p.add_argument("--rebalance", type=str, default="monthly", choices=["weekly", "monthly", "quarterly"])
    p.add_argument("--regime", type=str, default="pit", choices=["pit", "technical_only", "biased"])
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--costs-bps", type=float, default=10.0, help="Coste total ida (comisión+slippage), se reparte al 50%%")
    p.add_argument("--max-holding-days", type=int, default=None)
    p.add_argument("--mc-runs", type=int, default=1000, help="Muestras del Monte Carlo aleatorio")
    p.add_argument("--con-reflexion", action="store_true",
                   help="Activa la memoria de reflexión. DESACTIVADA POR DEFECTO porque el "
                        "contraste 2015-2025 la refutó: empeoró el percentil frente a "
                        "selección aleatoria (7.4 -> 3.1) y la expectativa por operación "
                        "(+1.23%% -> +0.95%%). Se conserva como bandera para reevaluarla con "
                        "otro universo, otro horizonte o validación walk-forward")
    p.add_argument("--offline", action="store_true", help="Solo caché en disco, sin red")
    p.add_argument("--out", type=str, default="output")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args()

    tickers = ([t.strip().upper() for t in args.tickers.split(",") if t.strip()]
               if args.tickers else list(DEFAULT_UNIVERSE))

    print("=" * 72)
    print(" BACKTEST DEL SISTEMA MULTI-AGENTE — capa de solo lectura")
    print("=" * 72)

    # ---------- Fase 1: verificación de neutralidad del LLM ----------
    print("\n[1/6] Verificando que el LLM no interviene en la decisión...")
    check = assert_llm_is_decision_neutral()
    if not check["neutral"]:
        print("  ✗ HIPÓTESIS REFUTADA. El LLM altera variables de decisión:")
        print(f"    {check['divergences']}")
        print("  El backtest no puede correr en modo heurístico. Abortando.")
        return 1
    print("  ✓ Confirmado: el LLM solo sobrescribe `summary`/`synthesis`.")
    print("    El replay es determinista, reproducible y de coste cero.")
    disable_llm()

    # ---------- Datos ----------
    print(f"\n[2/6] Cargando precios ({len(tickers)} valores + {BENCHMARK})...")
    prices = PriceStore(offline=args.offline)
    price_data: Dict[str, pd.DataFrame] = {}
    for t in tickers + [BENCHMARK]:
        df = prices.load(t, args.start, args.end)
        if df is not None:
            price_data[t.upper()] = df
    tickers = [t for t in tickers if t in price_data]
    if not tickers:
        print("  ✗ Sin datos de precios. ¿Falta red o caché?")
        return 1
    print(f"  ✓ {len(tickers)} valores con historia utilizable.")

    calendar = trading_calendar(prices, tickers + [BENCHMARK], args.start, args.end)
    rebals = rebalance_dates(calendar, args.rebalance)
    print(f"  ✓ {len(calendar)} sesiones, {len(rebals)} fechas de rebalanceo ({args.rebalance}).")

    if args.regime == "biased":
        fundamentals = TodayFundamentalStore(offline=args.offline)
    else:
        fundamentals = FundamentalStore(offline=args.offline)

    sector_map = load_sector_map(tickers, args.offline)

    # ---------- Fase 3: replay ----------
    print(f"\n[3/6] Reproduciendo decisiones históricas (régimen: {args.regime})...")
    if args.regime != "biased" and not args.offline:
        print("  Descargando companyfacts de SEC EDGAR en la primera pasada (puede tardar)...")
    # Posicionamiento en futuros point-in-time. El régimen technical_only lo
    # omite: allí la capa fundamental está neutralizada y añadir un veto macro
    # mezclaría dos mediciones distintas, por el mismo motivo por el que
    # `TodayFundamentalStore` no devuelve estados financieros.
    cot_store = COTStore(offline=args.offline) if args.regime == "pit" else None
    # Regimen de volatilidad point-in-time. Mismo criterio que el COT: se omite
    # en `technical_only`, donde la capa fundamental esta neutralizada y anadir
    # un veto de regimen mezclaria dos mediciones distintas.
    #
    # A DIFERENCIA de la cadena de opciones, esta serie SI es reconstruible:
    # ALFRED devuelve el valor tal y como se conocia en la fecha y cada
    # observacion trae la suya de publicacion. De este bloque el estudio mide el
    # 100% de la logica, no la mitad.
    fred_store = (FREDStore(offline=args.offline)
                  if (args.regime == "pit" and not args.sin_regimen) else None)
    replayer = HistoricalReplayer(prices, fundamentals, mode=args.regime,
                                  sector_map=sector_map, cot_store=cot_store,
                                  fred_store=fred_store,
                                  con_estructura=not args.sin_estructura)

    # Memoria de reflexión. Se construye SOBRE LA MARCHA, en el mismo recorrido
    # temporal del replay, y ese orden es la propiedad que la hace válida:
    #
    #   consolidar(t) → dosier(t) → decidir(t) → anotar las señales de t
    #
    # Anotar antes de decidir metería la señal de hoy en el dosier de hoy, que
    # es la forma más silenciosa de look-ahead que admite esta capa. Y consolidar
    # solo incorpora observaciones cuya fecha de DESENLACE ya pasó, nunca las que
    # simplemente se emitieron: es el mismo `filed <= t` de los hechos XBRL
    # aplicado a la consecuencia en vez de a la publicación.
    memoria = (MemoriaReflexion(resolver=resolver_desde_precios(price_data, BENCHMARK))
               if args.con_reflexion else None)

    # Banco de etiquetas del meta-modelo. Mismo patrón temporal que la memoria de
    # reflexión y por el mismo motivo:
    #
    #   resolver(t) → conjunto(t) → reentrenar si toca → decidir(t) → anotar(t)
    #
    # Anotar antes de decidir metería la señal de hoy en el conjunto de
    # entrenamiento de hoy; entrenar con etiquetas cuya barrera aún no se ha
    # resuelto sería mirar el futuro. `BancoDeEtiquetas.conjunto()` filtra por
    # fecha de DESENLACE, no de emisión, y ahí está toda la disciplina.
    def _barras_futuras(ticker: str, desde: pd.Timestamp) -> List[Dict[str, Any]]:
        df = price_data.get(ticker.upper())
        if df is None:
            return []
        fut = df.loc[df.index > desde]
        return [{"fecha": str(i.date()), "high": float(r["High"]),
                 "low": float(r["Low"]), "close": float(r["Close"])}
                for i, r in fut.iterrows()]

    banco = BancoDeEtiquetas(resolver=_barras_futuras) if args.con_meta else None
    proximo_reentreno: Optional[pd.Timestamp] = None
    meta_diag: List[Dict[str, Any]] = []

    by_date: Dict[pd.Timestamp, List[Signal]] = {}
    for i, d in enumerate(rebals):
        if memoria is not None:
            replayer.reflexion_dosier = memoria.dosier(d)
        if banco is not None:
            # 1. Resolver lo que ya se sabe cómo terminó en `d`.
            banco.resolver_hasta(d)
            # 2. Reentrenar si toca, SOLO con etiquetas ya desenlazadas.
            if proximo_reentreno is None or d >= proximo_reentreno:
                art, diag = entrenar(banco.conjunto(d), VARIABLES_META, d)
                replayer.meta_artefacto = art
                diag["fecha"] = str(d.date())
                diag["artefacto"] = bool(art)
                meta_diag.append(diag)
                proximo_reentreno = d + pd.Timedelta(days=META_REENTRENAR_CADA_DIAS)
                if not args.quiet:
                    print(f"    [meta] {d.date()}: "
                          + (f"modelo con {art.n_muestras} etiquetas, "
                             f"AUC CV {art.metricas_cv.get('auc_media')}, "
                             f"tasa base {art.tasa_base:.1%}" if art
                             else f"sin modelo — {diag.get('motivo')}"))
        # 3. Decidir.
        by_date[d] = replayer.signals_for_date(tickers, d)
        # 4. Anotar, DESPUÉS de decidir.
        if memoria is not None:
            memoria.anotar_senales(by_date[d], calendar)
        if banco is not None:
            banco.anotar_senales(by_date[d])
        if not args.quiet and (i % 12 == 0 or i == len(rebals) - 1):
            n = len(by_date[d])
            nb = sum(1 for s in by_date[d] if s.is_buy)
            rec = sum(1 for s in by_date[d] if s.factor_reflexion < 1.0)
            print(f"    {d.date()}  con señal={n:3d}  compras={nb:3d}  recortadas={rec:3d}")
    total_signals = sum(len(v) for v in by_date.values())
    total_buys = sum(1 for v in by_date.values() for s in v if s.is_buy)
    print(f"  ✓ {total_signals} señales evaluadas, {total_buys} de compra "
          f"({total_buys / total_signals * 100:.1f}%)." if total_signals else "  ✗ Sin señales.")
    if replayer.skips:
        print(f"  Descartes: {replayer.skips}")
    if total_signals == 0:
        return 1

    # ---------- Simulación ----------
    print("\n[4/6] Simulando la cartera...")
    half = args.costs_bps / 2.0
    cfg = BacktestConfig(initial_capital=args.capital, commission_bps=half,
                         slippage_bps=half, max_holding_days=args.max_holding_days,
                         usar_entrada_limitada=args.con_entrada_limitada,
                         vida_orden_sesiones=args.vida_orden)
    pre = PrecomputedReplayer(by_date, replayer.skips)
    # La capa de cartera se desactiva en `technical_only`: allí el Analista de
    # Calidad no interviene, todas las convicciones son nulas y no habría nada
    # que ordenar. En los otros dos regímenes el dimensionamiento pasa por
    # `PortfolioConstructor`, la misma capa que corre en vivo.
    usar_cartera = args.regime != "technical_only"
    res = run_backtest(pre, tickers, calendar, rebals, price_data, cfg,
                       verbose=not args.quiet, usar_capa_de_cartera=usar_cartera)

    equity = res["equity"]
    trades = res["trades"]
    if equity.empty:
        print("  ✗ Curva de capital vacía.")
        return 1

    # ---------- Métricas y benchmarks ----------
    print("\n[5/6] Calculando métricas, benchmarks y significancia...")
    spy = buy_and_hold(price_data, BENCHMARK, equity.index, args.capital)
    ew = equal_weight(price_data, tickers, equity.index, args.capital)

    summary = {
        "strategy": M.performance_summary(equity, spy if len(spy) > 1 else None),
        "spy": M.performance_summary(spy) if len(spy) > 1 else {},
        "equal_weight": M.performance_summary(ew) if len(ew) > 1 else {},
    }
    tstats_trades = M.trade_stats(trades)

    # La nula aleatoria replica el perfil observado de la estrategia: mismo
    # número medio de posiciones simultáneas, misma tenencia media y misma
    # exposición bruta media. Así el contraste mide selección de valores, no
    # diferencia de exposición al mercado.
    avg_exposure = float(res["exposure"].mean()) if len(res["exposure"]) else 0.0
    avg_open = float(res["n_open"].mean()) if len(res["n_open"]) else 0.0
    n_pos_typical = max(1, int(round(avg_open)))
    avg_hold = int(tstats_trades.get("avg_holding_days", 30) or 30)
    mc = random_signal_benchmark(price_data, tickers, equity.index,
                                 n_positions=n_pos_typical, avg_holding_days=avg_hold,
                                 gross_exposure=avg_exposure, cfg=cfg, n_runs=args.mc_runs)
    random_test = M.percentile_vs_random(summary["strategy"].get("cagr", 0.0), mc["cagrs"])

    all_signals = [s for v in by_date.values() for s in v]
    ev = M.event_study(all_signals, price_data)

    # Subperiodos
    sub_defs = [
        ("Pre-COVID 2015-2019", "2015-01-01", "2019-12-31"),
        ("Crash COVID 2020-02→2020-04", "2020-02-01", "2020-04-30"),
        ("Recuperación 2020-2021", "2020-05-01", "2021-12-31"),
        ("Bajista 2022", "2022-01-01", "2022-12-31"),
        ("Post-2023", "2023-01-01", "2026-12-31"),
    ]
    sub_rows = {}
    for label, s0, s1 in sub_defs:
        seg = equity.loc[(equity.index >= s0) & (equity.index <= s1)]
        seg_spy = spy.loc[(spy.index >= s0) & (spy.index <= s1)] if len(spy) else pd.Series(dtype=float)
        if len(seg) < 20:
            continue
        sub_rows[label] = {
            "Retorno estrategia": seg.iloc[-1] / seg.iloc[0] - 1,
            "Retorno SPY": (seg_spy.iloc[-1] / seg_spy.iloc[0] - 1) if len(seg_spy) > 1 else np.nan,
            "Sharpe": M.sharpe(M.daily_returns(seg)),
            "Máx. drawdown": M.max_drawdown(seg),
        }
    subperiods = pd.DataFrame(sub_rows).T
    subperiods.index.name = "Subperiodo"

    # Sensibilidad a costes: mismas señales, motor reejecutado.
    print("  Sensibilidad a costes de transacción...")
    sens_rows = {}
    for bps in (0.0, 5.0, 10.0, 25.0):
        c = BacktestConfig(initial_capital=args.capital, commission_bps=bps / 2,
                           slippage_bps=bps / 2, max_holding_days=args.max_holding_days)
        r = run_backtest(PrecomputedReplayer(by_date, {}), tickers, calendar, rebals,
                         price_data, c, verbose=False,
                         usar_capa_de_cartera=usar_cartera)
        if not r["equity"].empty:
            sens_rows[f"{bps:.0f} bps ida y vuelta"] = {
                "CAGR": M.cagr(r["equity"]),
                "Sharpe": M.sharpe(M.daily_returns(r["equity"])),
                "Máx. drawdown": M.max_drawdown(r["equity"]),
                "Capital final": float(r["equity"].iloc[-1]),
            }
    sensitivity = pd.DataFrame(sens_rows).T
    sensitivity.index.name = "Nivel de coste"

    years = summary["strategy"].get("years", 0.0)
    refl_stats = resumen_reflexion(memoria, by_date)
    limitations = build_limitations(args.regime, tstats_trades.get("n_trades", 0),
                                    res["skips"], len(tickers), years, avg_exposure,
                                    refl_stats)

    # ---------- Informe ----------
    # Vintage de cada serie externa que alimenta la decisión. Es el registro que
    # permite diagnosticar dos ejecuciones que discrepen: si el COT o la serie de
    # volatilidad cambiaron de contenido entre una y otra, aquí se ve. NO lleva
    # reloj de pared: la salida persistida tiene que ser idéntica byte a byte
    # entre dos ejecuciones `--offline`.
    vintages: Dict[str, str] = {
        "precios": f"caché yfinance {args.start}..{args.end}",
        "fundamentales": ("SEC EDGAR companyfacts, filed<=t"
                          if args.regime != "biased" else "yfinance.info de HOY (SESGADO)"),
        "cot": "CFTC, filtrado por fecha_publicacion" if cot_store else "no usado",
        "volatilidad": ("ALFRED output_type=4, filtrado por fecha_publicacion"
                        if fred_store else "no usado"),
        "opciones": "ausente (histórico por ticker de pago)",
    }

    print("\n[6/6] Generando informe...")
    results: Dict[str, Any] = {
        "regime": args.regime,
        "config": {"tickers": len(tickers), "start": args.start, "end": args.end,
                   "rebalance": args.rebalance, "costs_bps_round_trip": args.costs_bps,
                   "capital": args.capital, "max_holding_days": args.max_holding_days,
                   "mc_runs": args.mc_runs, "benchmark": BENCHMARK},
        "command": ("python backtest_cli.py "
                    f"--start {args.start} --end {args.end} --rebalance {args.rebalance} "
                    f"--regime {args.regime} --costs-bps {args.costs_bps} "
                    f"--capital {args.capital:.0f} --mc-runs {args.mc_runs}"
                    + (f" --tickers {args.tickers}" if args.tickers else "")),
        "equity": equity,
        "curves": {"Estrategia": equity, "SPY comprar y mantener": spy,
                   "Universo equiponderado": ew},
        "summary": summary,
        "trades": trades,
        "trade_stats": tstats_trades,
        "random_test": random_test,
        "random_cagrs": mc["cagrs"],
        "bootstrap": M.bootstrap_cagr(equity),
        "attr_rating": M.attribution(trades, "rating"),
        # Atribucion por ESTILO: responde si el sistema pierde dinero en valor,
        # en crecimiento o de forma transversal. El informe anterior planteaba
        # esa hipotesis en NEXT_STEPS pero no podia medirla, porque las
        # operaciones no arrastraban la etiqueta.
        "attr_estilo": M.attribution(trades, "estilo"),
        "attr_sector": M.attribution(trades, "sector"),
        "attr_exit": M.attribution(trades, "exit_reason"),
        "attr_year": M.attribution_by_year(trades),
        "event_study": ev,
        "subperiods": subperiods,
        "sensitivity": sensitivity,
        "avg_exposure": avg_exposure,
        "avg_open_positions": avg_open,
        "mc_profile": {"n_positions": n_pos_typical, "avg_holding_days": avg_hold,
                       "gross_exposure": avg_exposure},
        "turnover": M.turnover(trades, equity),
        "total_costs": res["total_costs"],
        # Actividad de la memoria de reflexión. Sin estas cifras no se puede
        # distinguir «la capa no ayuda» de «la capa nunca llegó a actuar», que
        # son diagnósticos distintos con remedios distintos.
        "reflexion": refl_stats,
        "skips": res["skips"],
        # Órdenes limitadas que expiraron sin rellenarse. Cero cuando la entrada
        # limitada está desactivada, que es el valor por defecto. Sin esta cifra
        # el informe no puede decir cuántas señales se dejaron pasar, y una regla
        # que solo opera cuando el precio le viene encima parecería mejor de lo
        # que es.
        "ordenes_expiradas": res.get("ordenes_expiradas", 0),
        # Vintage de cada serie externa. Dos ejecuciones que discrepen se
        # diagnostican con esto en vez de discutirse.
        "vintages": vintages,
        # Actividad del meta-modelo. Igual que con la reflexión, sin estas cifras
        # no se puede distinguir «la capa no ayuda» de «la capa nunca llegó a
        # entrenar», que son diagnósticos distintos con remedios distintos.
        "meta": {"activo": banco is not None,
                 "reentrenamientos": meta_diag,
                 "etiquetas_anotadas": len(banco.etiquetas) if banco else 0,
                 "etiquetas_resueltas": (sum(1 for e in banco.etiquetas if e.resuelta)
                                         if banco else 0)},
        "limitations": limitations,
        "next_steps": NEXT_STEPS,
    }
    path = generate_report(results, Path(args.out))

    s = summary["strategy"]
    b = summary["spy"]
    print("\n" + "=" * 72)
    print(f" Régimen        : {args.regime}")
    print(f" CAGR estrategia: {s.get('cagr', 0) * 100:6.2f}%   |  SPY: {b.get('cagr', 0) * 100:6.2f}%")
    print(f" Sharpe         : {s.get('sharpe', 0):6.2f}    |  SPY: {b.get('sharpe', 0):6.2f}")
    print(f" Máx. drawdown  : {s.get('max_drawdown', 0) * 100:6.2f}%   |  SPY: {b.get('max_drawdown', 0) * 100:6.2f}%")
    print(f" Operaciones    : {tstats_trades.get('n_trades', 0)}  "
          f"(acierto {tstats_trades.get('hit_rate', 0) * 100:.1f}%, "
          f"equilibrio {M.breakeven_hit_rate() * 100:.1f}%)")
    print(f" Percentil vs aleatorio: {random_test.get('percentil_vs_aleatorio', 0):.1f}")
    print(f"\n Informe: {path}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
