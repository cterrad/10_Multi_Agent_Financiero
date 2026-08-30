"""
Punto de entrada del análisis en vivo.

Antes recorría los tickers de forma independiente y volcaba una ficha por
valor. Ahora, además, carga UNA sola vez la referencia de mercado, construye la
cartera agregada con la matriz de correlaciones real y genera tres documentos:
el resumen ejecutivo, el informe completo y una ficha de detalle por compañía
con la traza de las herramientas que produjeron cada dictamen.

La diferencia importa: recomendar cuatro posiciones sin mirar cómo se
relacionan entre sí es recomendar concentración disfrazada de diversificación.
"""

import argparse
import os
import sys

# Codificación UTF-8 para la consola de Windows: los informes llevan acentos y
# emoji, y cp1252 los rompe.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from src.config import CAPITAL_BASE, OUTPUT_DIR
from src.data.fetcher import DataFetcher
from src.graph.workflow import cargar_benchmark, run_stock_analysis
from src.portfolio import PortfolioConstructor
from src.utils.logging_agentes import configurar_logging, ruta_de_traza
from src.utils.report_generator import ReportGenerator

SIN_DATO = "n/d"


def _tabla_ejecutiva(resultados):
    """Resumen ejecutivo en terminal: una línea por valor, la decisión primero."""
    if not resultados:
        return

    cab = (f"{'TICKER':<8}{'ESTILO':<22}{'CONV':>6}{'MOM':>7}"
           f"{'DICTAMEN':>16}{'PESO':>8}{'STOP':>10}{'OBJETIVO':>10}")
    print("\n" + "=" * len(cab))
    print(" RESUMEN EJECUTIVO")
    print("=" * len(cab))
    print(cab)
    print("-" * len(cab))

    for r in resultados:
        q = r.get("quality_report", {}) or {}
        t = r.get("technical_report", {}) or {}
        fd = r.get("final_decision", {}) or {}
        conv = (q.get("conviccion_fundamental") or {}).get("valor")
        mom = t.get("momentum_score")
        stop = fd.get("stop_loss_atr")
        objetivo = fd.get("take_profit_atr")
        print(
            f"{r.get('ticker', '?'):<8}"
            f"{(q.get('style_classification') or SIN_DATO)[:21]:<22}"
            f"{(f'{conv:.0f}' if conv is not None else SIN_DATO):>6}"
            f"{(f'{mom:+.0f}' if mom is not None else SIN_DATO):>7}"
            f"{fd.get('rating', SIN_DATO):>16}"
            f"{fd.get('peso_objetivo', 0.0):>7.2%} "
            f"{(f'${stop:.2f}' if stop else SIN_DATO):>10}"
            f"{(f'${objetivo:.2f}' if objetivo else SIN_DATO):>10}"
        )
    print("-" * len(cab))


def _mostrar_detalle(ticker: str) -> int:
    """Vuelca por pantalla la ficha pormenorizada de un valor ya analizado."""
    ruta = os.path.join(OUTPUT_DIR, "detalle", f"{ticker.upper()}.md")
    if not os.path.exists(ruta):
        print(f"\nNo hay ficha de {ticker.upper()} en {ruta}.")
        print("Analízalo primero:  python cli.py --tickers " + ticker.upper())
        return 1
    with open(ruta, encoding="utf-8") as f:
        print(f.read())
    return 0


def _investigar(ticker: str, pregunta: str) -> int:
    """
    Agente ReAct asesor, bajo demanda.

    Fuera de la ejecución diaria a propósito: encadena varias llamadas al
    proveedor y exige clave. Su respuesta no altera ningún rating, ningún peso
    ni ningún nivel de riesgo — ver `src/agents/investigador.py`.
    """
    from src.agents.investigador import LLMNoConfigurado
    from src.graph.investigacion import investigar

    print(f"\n[Investigador] {ticker.upper()}: {pregunta}\n")
    try:
        r = investigar(ticker, pregunta)
    except LLMNoConfigurado as e:
        print(f"  {e}")
        return 1

    print(f"  Herramientas consultadas: {', '.join(r['tools_invocadas']) or 'ninguna'}\n")
    print(r["respuesta"])
    print("\n  (Capa asesora: esta respuesta no modifica ningún dictamen del sistema.)\n")
    return 0


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
    parser.add_argument("--detalle", type=str, metavar="TICKER",
                        help="Vuelca por pantalla la ficha pormenorizada de un valor ya analizado")
    parser.add_argument("--investigar", type=str, nargs=2, metavar=("TICKER", "PREGUNTA"),
                        help="Agente ReAct asesor: responde una pregunta consultando las "
                             "herramientas reales. Requiere LLM configurado y no altera "
                             "ningún dictamen")
    parser.add_argument("--log", type=str, default="WARNING",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Detalle del log en CONSOLA. El fichero JSONL de "
                             "output/logs/ se escribe siempre completo")
    args = parser.parse_args()

    # Los dos modos de consulta no analizan nada: salen antes de tocar la red.
    if args.detalle:
        return _mostrar_detalle(args.detalle)
    if args.investigar:
        configurar_logging(args.log, args.investigar[0])
        return _investigar(args.investigar[0], args.investigar[1])

    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    configurar_logging(args.log, ticker=tickers[0] if len(tickers) == 1 else None)

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
            n_tools = sum(len((r or {}).get("_traza", {}).get("tools", []))
                          for r in (q, fr, res.get("technical_report"),
                                    res.get("news_report"), res.get("debate_report"), fd))

            print(f"    -> Filtro fundamental: {fr.get('status', 'N/A')}")
            print(f"    -> Estilo: {q.get('style_classification', 'n/d')} "
                  f"(convicción {conviccion if conviccion is not None else 'n/d'}/100)")
            print(f"    -> Dictamen: {fd.get('rating', 'N/A')} "
                  f"| peso {fd.get('peso_objetivo', 0.0):.2%}")
            print(f"    -> {n_tools} herramienta(s) invocada(s) · "
                  f"{len(res.get('messages', []))} mensaje(s) en la traza")
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

    _tabla_ejecutiva(resultados)

    print(f"\n Resumen ejecutivo : {ruta}")
    print(f" Informe completo  : {os.path.join(OUTPUT_DIR, 'daily_selection.md')}")
    print(f" Detalle por valor : {os.path.join(OUTPUT_DIR, 'detalle')}"
          f"  (o `python cli.py --detalle {tickers[0]}`)")
    print(f" Traza estructurada: {ruta_de_traza(tickers[0] if len(tickers) == 1 else None)}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
