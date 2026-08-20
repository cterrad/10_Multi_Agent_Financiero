import argparse
import sys
import io

# Configurar codificación UTF-8 para consola Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from typing import List
from src.graph.workflow import run_stock_analysis
from src.utils.report_generator import ReportGenerator

def main():
    parser = argparse.ArgumentParser(description="Sistema Multi-Agente de Análisis Financiero de Selección de Élite")
    parser.add_argument("--tickers", "-t", type=str, default="NVDA,AAPL,MSFT,TSLA,INTC", help="Lista de tickers separados por comas (ej. NVDA,AAPL,MSFT)")
    args = parser.parse_args()

    ticker_list = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]

    print("\n=======================================================")
    print(" 🚀 SISTEMA MULTI-AGENTE DE ANÁLISIS FINANCIERO (LangGraph)")
    print("=======================================================\n")
    print(f" Analizando {len(ticker_list)} empresa(s): {', '.join(ticker_list)}\n")

    results = []
    for idx, ticker in enumerate(ticker_list, 1):
        print(f"[{idx}/{len(ticker_list)}] 🔍 Procesando {ticker}...")
        try:
            res = run_stock_analysis(ticker)
            results.append(res)
            
            
            final = res.get("final_decision", {})
            rating = final.get("rating", "N/A")
            fund_passed = "APROBADO" if res.get("passed_fundamental_gatekeeper") else "RECHAZADO"
            
            print(f"    -> Filtro Gatekeeper: {fund_passed}")
            print(f"    -> Dictamen Final: {rating}\n")
        except Exception as e:
            print(f"    ❌ Error al analizar {ticker}: {e}\n")

    # Generar Informe Final
    reporter = ReportGenerator()
    report_path = reporter.generate_daily_selection(results)

    print("=======================================================")
    print(f" ✅ Análisis Completado. Informe guardado en: {report_path}")
    print("=======================================================\n")

if __name__ == "__main__":
    main()
