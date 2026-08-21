"""
Punto de entrada del análisis en vivo.

Antes recorría los tickers de forma independiente y volcaba una ficha por
valor. Ahora, además, carga UNA sola vez la referencia de mercado, construye la
cartera agregada con la matriz de correlaciones real y genera el informe
completo. La diferencia importa: recomendar cuatro posiciones sin mirar cómo se
relacionan entre sí es recomendar concentración disfrazada de diversificación.
"""

import argparse
import sys

# Codificación UTF-8 para la consola de Windows: los informes llevan acentos y
# emoji, y cp1252 los rompe.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from src.config import CAPITAL_BASE
from src.data.fetcher import DataFetcher
from src.graph.workflow import cargar_benchmark, run_stock_analysis
from src.portfolio import PortfolioConstructor
from src.utils.report_generator import ReportGenerator


def main():
    parser = argparse.ArgumentParser(
        description="Sistema Multi-Agente de Análisis Financiero de Selección de Élite")
    parser.add_argument("--tickers", "-t", type=str, default="NVDA,AAPL,MSFT,TSLA,INTC",
                        help="Lista de tickers separados por comas (ej. NVDA,AAPL,MSFT)")
    parser.add_argument("--benchmark", "-b", type=str, default="SPY",
                        help="Índice de referencia para el momentum relativo (por defecto SPY)")
    parser.add_argument("--capital", type=float, default=CAPITAL_BASE,
                        help="Capital de referencia para dimensionar la cartera")
    parser.add_argument("--sin-benchmark", action="store_true",
                        help="Omite la descarga del índice; el momentum se reporta en absoluto")
    parser.add_argument("--sin-cartera", action="store_true",
                        help="Omite la construcción de cartera y el cálculo de correlaciones")
    args = parser.parse_args()

    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]

    print("\n=======================================================")
    print(" SISTEMA MULTI-AGENTE DE ANÁLISIS FINANCIERO (LangGraph)")
    print("=======================================================\n")
    print(f" Analizando {len(tickers)} empresa(s): {', '.join(tickers)}\n")

    # --- Referencia de mercado, una sola vez para todo el lote ------------
    benchmark = {}
    if not args.sin_benchmark:
        print(f"[0/{len(tickers)}] Cargando referencia de mercado ({args.benchmark})...")
        benchmark = cargar_benchmark(args.benchmark)
        if benchmark:
            r12 = benchmark.get("change_12m_pct")
            print(f"    -> {benchmark['ticker']}: 12m "
                  f"{f'{r12:+.1%}' if r12 is not None else 'n/d'}\n")
        else:
            print("    -> No disponible. El momentum se calculará en términos absolutos.\n")

    resultados = []
    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/{len(tickers)}] Procesando {ticker}...")
        try:
            res = run_stock_analysis(ticker, benchmark_data=benchmark)
            resultados.append(res)

            fd = res.get("final_decision", {}) or {}
            q = res.get("quality_report", {}) or {}
            fr = res.get("fundamental_report", {}) or {}
            conviccion = (q.get("conviccion_fundamental") or {}).get("valor")

            print(f"    -> Filtro fundamental: {fr.get('status', 'N/A')}")
            print(f"    -> Estilo: {q.get('style_classification', 'n/d')} "
                  f"(convicción {conviccion if conviccion is not None else 'n/d'}/100)")
            print(f"    -> Dictamen: {fd.get('rating', 'N/A')} "
                  f"| peso {fd.get('peso_objetivo', 0.0):.2%}")
            if q.get("banderas_rojas"):
                print(f"    -> Banderas rojas: {len(q['banderas_rojas'])}")
            print()
        except Exception as e:
            print(f"    ERROR al analizar {ticker}: {type(e).__name__}: {e}\n")

    # --- Cartera agregada -------------------------------------------------
    cartera = None
    if resultados and not args.sin_cartera:
        print("Construyendo cartera (correlaciones, límites sectoriales, presupuesto de riesgo)...")
        series = {}
        try:
            series = DataFetcher().fetch_series_precios([r.get("ticker") for r in resultados])
        except Exception as e:
            print(f"    Advertencia: no se pudieron descargar las series conjuntas ({e}). "
                  f"La cartera se construirá sin penalización por correlación.")
        cartera = PortfolioConstructor(capital=args.capital).construir(resultados, series)
        print(f"    -> {len(cartera.posiciones)} posición(es) · "
              f"exposición bruta {cartera.exposicion_bruta:.2%} · "
              f"liquidez {cartera.liquidez:.2%} · "
              f"riesgo agregado {cartera.riesgo_total:.2%}\n")

    reporter = ReportGenerator()
    ruta = reporter.generate_daily_selection(resultados, cartera=cartera, benchmark=benchmark)

    print("=======================================================")
    print(f" Análisis completado. Informe: {ruta}")
    print("=======================================================\n")


if __name__ == "__main__":
    main()
