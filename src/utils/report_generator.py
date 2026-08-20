import os
import json
from datetime import datetime
from typing import List, Dict, Any
from src.config import OUTPUT_DIR
from src.state import FinancialAnalysisState

class ReportGenerator:
    """Genera informes ejecutivos en formato Markdown (daily_selection.md) y JSON."""

    def generate_daily_selection(self, results: List[FinancialAnalysisState], filename: str = "daily_selection.md") -> str:
        filepath = os.path.join(OUTPUT_DIR, filename)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        md_lines = [
            f"# 📈 Informe Ejecutivo: Selección Diaria de Élite Multi-Agente",
            f"**Fecha de Análisis:** `{now_str}`",
            f"**Sistema:** Pipeline de Selección de Élite (LangGraph + Multi-Vendor Data)",
            "",
            "---",
            "",
            "## 📊 Resumen Ejecutivo de Tickers",
            "",
            "| Ticker | Empresa | Filtro Fundamental | Momentum Técnico | Dictamen Final | Tamaño Posición | Stop-Loss | Take-Profit |",
            "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |"
        ]

        for res in results:
            ticker = res.get("ticker", "N/A")
            company = res.get("company_name", ticker)
            fund_passed = "✅ APROBADO" if res.get("passed_fundamental_gatekeeper") else "❌ RECHAZADO"
            tech_report = res.get("technical_report", {})
            momentum = tech_report.get("momentum_classification", "N/A") if res.get("passed_fundamental_gatekeeper") else "N/A"
            final = res.get("final_decision", {})
            rating = final.get("rating", "N/A")
            pos_size = final.get("position_size_pct", "0%")
            sl = f"${final.get('stop_loss_atr')}" if final.get('stop_loss_atr') else "N/A"
            tp = f"${final.get('take_profit_atr')}" if final.get('take_profit_atr') else "N/A"

            md_lines.append(f"| **{ticker}** | {company} | {fund_passed} | {momentum} | **{rating}** | {pos_size} | {sl} | {tp} |")

        md_lines.extend([
            "",
            "---",
            "",
            "## 🔍 Desglose Detallado por Empresa",
            ""
        ])

        for res in results:
            ticker = res.get("ticker", "N/A")
            company = res.get("company_name", ticker)
            fund = res.get("fundamental_report", {})
            tech = res.get("technical_report", {})
            debate = res.get("debate_report", {})
            final = res.get("final_decision", {})
            rec = res.get("reconciliation_data", {})

            md_lines.extend([
                f"### 🏢 {ticker} - {company}",
                f"- **Sector / Industria:** {res.get('sector', 'N/A')} / {res.get('industry', 'N/A')}",
                f"- **Confianza en Datos Multi-Fuente:** `{rec.get('confidence_score', 1.0)*100:.0f}%` (Fuentes: {', '.join(rec.get('sources_consulted', []))})",
                "",
                "#### 1. Capa Gatekeeper Fundamental",
                f"- **Resultado:** {fund.get('status', 'N/A')}",
                f"- **Resumen:** {fund.get('summary', 'N/A')}",
                ""
            ])

            if res.get("passed_fundamental_gatekeeper"):
                md_lines.extend([
                    "#### 2. Analista Técnico de Momentum",
                    f"- **Clasificación:** `{tech.get('momentum_classification')}`",
                    f"- **RSI (14):** `{tech.get('rsi')}` | **MACD Hist:** `{tech.get('macd_hist')}` | **ATR:** `${tech.get('atr')}`",
                    f"- **Resumen:** {tech.get('summary', 'N/A')}",
                    "",
                    "#### 3. Capa de Debate y Mitigación de Sesgos",
                    f"- 🐂 **Tesis Alcista:** {debate.get('bullish_case', 'N/A')}",
                    f"- 🐻 **Tesis Bajista:** {debate.get('bearish_case', 'N/A')}",
                    f"- ⚖️ **Síntesis del Debate:** {debate.get('synthesis', 'N/A')}",
                    ""
                ])

            md_lines.extend([
                "#### 4. Dictamen Final del Fund Manager",
                f"- 🎯 **Recomendación:** `{final.get('rating')}`",
                f"- 💰 **Asignación Recomendada:** `{final.get('position_size_pct')}`",
                f"- 🛡️ **Parámetros de Riesgo ATR:** Stop-Loss: `${final.get('stop_loss_atr', 'N/A')}` | Take-Profit: `${final.get('take_profit_atr', 'N/A')}`",
                f"- 📝 **Justificación:** {final.get('summary')}",
                "",
                "---",
                ""
            ])

        content = "\n".join(md_lines)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        # También guardar versión JSON
        json_path = os.path.join(OUTPUT_DIR, "daily_selection.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"[ReportGenerator] Informe Markdown generado exitosamente en: {filepath}")
        return filepath
