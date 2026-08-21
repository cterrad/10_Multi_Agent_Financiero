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
    FundamentalStore, PriceStore, TodayFundamentalStore,
    rebalance_dates, trading_calendar,
)
from src.backtest.engine import (
    BacktestConfig, buy_and_hold, equal_weight, random_signal_benchmark, run_backtest,
)
from src.backtest.replay import (
    HistoricalReplayer, Signal, assert_llm_is_decision_neutral, disable_llm,
)
from src.backtest.report import generate_report

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
                      n_universe: int, years: float, avg_exposure: float = 0.0) -> List[str]:
    lims: List[str] = []

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
            "**La exposición sigue siendo emergente, aunque ya no arbitraria.** El Fund "
            "Manager emite ahora un peso NUMÉRICO por posición, derivado de un presupuesto "
            "de riesgo (riesgo asumible / distancia al stop, escalado por volatilidad), y "
            "`src/portfolio/construccion.py` aplica límites por sector, penalización por "
            "correlación y un tope de exposición bruta. Pero el backtest recorre un ticker "
            "cada vez: la exposición del "
            f"{avg_exposure:.0%} sigue siendo consecuencia de cuántas señales de compra "
            "aparecen, no de una decisión de asignación agregada. Integrar la capa de "
            "cartera en el motor histórico es trabajo pendiente.")

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
        "**Contrastes múltiples.** Se han evaluado varios regímenes, frecuencias y niveles de "
        "coste sobre el mismo periodo histórico. El p-valor mostrado no está corregido por "
        "multiplicidad: interprétese como orientativo, no como una prueba formal.")

    return lims


NEXT_STEPS = [
    "PRIORIDAD 1 — investigar la ordenación del rating. Antes de tocar stops, sizing o "
    "costes, comprobar si el event study mantiene el orden invertido (VENTA FUERTE rindiendo "
    "más que COMPRA FUERTE) en otros universos y periodos. Si se confirma, el problema está "
    "en la señal y ningún ajuste de gestión de cartera lo arreglará.",
    "Contrastar la hipótesis más probable de esa inversión: el gatekeeper exige crecimiento "
    "de ingresos ≥5% y margen neto ≥3%, lo que descarta sistemáticamente los valores de "
    "estilo *value* y las recuperaciones cíclicas, que son justamente los que más rindieron "
    "en varios tramos del periodo. Es un sesgo de estilo, no un fallo de implementación.",
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
    "Integrar `src/portfolio/construccion.py` en el motor histórico. Hoy el backtest "
    "dimensiona posición a posición con el peso que emite el Fund Manager, pero no aplica "
    "los límites por sector, la penalización por correlación ni el presupuesto de riesgo "
    "agregado que sí se aplican en vivo. Hasta que se integre, el backtest mide una cartera "
    "más concentrada que la que el sistema recomendaría hoy.",
    "Sustituir `SECTOR_NORMAS` por la mediana calculada sobre un conjunto de comparables en "
    "cada fecha. Es lo que convierte el contexto sectorial de una referencia estática en una "
    "valoración relativa point-in-time, y elimina el anacronismo declarado en las "
    "limitaciones.",
    "Revalidar el sistema completo tras la incorporación del Analista de Calidad a la "
    "decisión. El track record publicado corresponde a la versión anterior, en la que el "
    "rating salía de momentum y RSI únicamente; las cifras de rendimiento no son "
    "transferibles a la versión actual hasta ejecutar de nuevo el régimen `pit`.",
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
    p.add_argument("--tickers", type=str, default="", help="Lista separada por comas (por defecto, universo interno)")
    p.add_argument("--start", type=str, default="2015-01-01")
    p.add_argument("--end", type=str, default="2025-12-31")
    p.add_argument("--rebalance", type=str, default="monthly", choices=["weekly", "monthly", "quarterly"])
    p.add_argument("--regime", type=str, default="pit", choices=["pit", "technical_only", "biased"])
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--costs-bps", type=float, default=10.0, help="Coste total ida (comisión+slippage), se reparte al 50%%")
    p.add_argument("--max-holding-days", type=int, default=None)
    p.add_argument("--mc-runs", type=int, default=1000, help="Muestras del Monte Carlo aleatorio")
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
    replayer = HistoricalReplayer(prices, fundamentals, mode=args.regime, sector_map=sector_map)

    by_date: Dict[pd.Timestamp, List[Signal]] = {}
    for i, d in enumerate(rebals):
        by_date[d] = replayer.signals_for_date(tickers, d)
        if not args.quiet and (i % 12 == 0 or i == len(rebals) - 1):
            n = len(by_date[d])
            nb = sum(1 for s in by_date[d] if s.is_buy)
            print(f"    {d.date()}  con señal={n:3d}  compras={nb:3d}")
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
                         slippage_bps=half, max_holding_days=args.max_holding_days)
    pre = PrecomputedReplayer(by_date, replayer.skips)
    res = run_backtest(pre, tickers, calendar, rebals, price_data, cfg, verbose=not args.quiet)

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
                         price_data, c, verbose=False)
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
    limitations = build_limitations(args.regime, tstats_trades.get("n_trades", 0),
                                    res["skips"], len(tickers), years, avg_exposure)

    # ---------- Informe ----------
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
        "skips": res["skips"],
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
