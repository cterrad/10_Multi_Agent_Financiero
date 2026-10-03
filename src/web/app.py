import os
from typing import List, Dict, Any
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

from src.graph.workflow import cargar_regimen, run_stock_analysis
from src.utils.report_generator import ReportGenerator
from src.config import OUTPUT_DIR

app = FastAPI(
    title="Multi-Agent Stock Analysis Platform",
    description="Sistema Multi-Agente Financiero con LangGraph y Reconciliación Multi-Fuente",
    version="1.0.0"
)

# Configurar estáticos y plantillas
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

reporter = ReportGenerator()

class AnalysisRequest(BaseModel):
    tickers: List[str]

@app.get("/")
async def home(request: Request):
    """Página principal del dashboard web."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "multi_agent_financiero"}

@app.post("/api/analyze")
async def analyze_stocks(payload: AnalysisRequest):
    """API Endpoint para ejecutar análisis multi-agente en tiempo real."""
    tickers = [t.strip().upper() for t in payload.tickers if t.strip()]
    if not tickers:
        return JSONResponse(status_code=400, content={"error": "Lista de tickers vacía"})

    # Régimen de volatilidad: dato DE LOTE, así que se resuelve una sola vez
    # para toda la petición y no una por ticker. Es la única capa de lote que el
    # dashboard cablea; `benchmark_data`, `macro_data` y `reflexion_data` siguen
    # con su valor por defecto, y por eso el dashboard sigue produciendo un
    # dictamen DISTINTO del de la CLI sobre el mismo valor. Ver `CLAUDE.md`,
    # «Los tres puntos de entrada NO son equivalentes».
    #
    # Se cablea este y no los otros por una razón concreta: el veto de régimen
    # puede TOPAR un dictamen en MANTENER, y un dashboard que emitiera COMPRA
    # FUERTE en mitad de un episodio de pánico mientras la CLI emite MANTENER
    # sobre el mismo valor sería una divergencia difícil de defender.
    regimen = cargar_regimen()

    results = []
    for ticker in tickers:
        try:
            res = run_stock_analysis(ticker, regimen_data=regimen)
            results.append(res)
        except Exception as e:
            results.append({
                "ticker": ticker,
                "workflow_status": "ERROR",
                "error_message": str(e),
                "passed_fundamental_gatekeeper": False,
                "final_decision": {"rating": "ERROR", "summary": f"Error: {e}"}
            })

    # Guardar reporte actualizado
    report_path = reporter.generate_daily_selection(results)

    return {
        "status": "SUCCESS",
        "count": len(results),
        "results": results,
        "report_file": report_path
    }

@app.get("/api/report/download")
async def download_report():
    filepath = os.path.join(OUTPUT_DIR, "daily_selection.md")
    if os.path.exists(filepath):
        return FileResponse(filepath, filename="daily_selection.md", media_type="text/markdown")
    return JSONResponse(status_code=404, content={"error": "Informe no disponible todavía"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
