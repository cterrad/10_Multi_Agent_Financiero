# Walkthrough: Sistema Multi-Agente de Análisis Financiero y Recomendación de Acciones

El **Pipeline de Selección de Élite** ha sido implementado exitosamente. Es un sistema multi-agente de arquitectura jerárquica con máquinas de estado construida en **LangGraph**, empaquetada en **Docker** y con soporte nativo para **Hugging Face (Open Source)**, Ollama, OpenAI y Gemini.

---

## 🏛️ Arquitectura del Sistema e Integración Multi-Fuente

```mermaid
graph TD
    A[Ticker de Entrada] --> B[Ingesta Multi-Fuente: SEC EDGAR + Finnhub + yfinance]
    B --> CC[Consistency Checker - Reconciliación Cruzada]
    CC --> C1[Gatekeeper Fundamental]
    C1 -->|Rechazado: Salud Débil / Inconsistencia| D1[Estado Final: VENTA / VENTA FUERTE - Detiene Cómputo]
    C1 -->|Aprobado: Crecimiento y Margen OK| E1[Analista Técnico de Momentum]
    E1 --> F1[Unidad de Debate: Bullish vs Bearish]
    F1 --> G1[Síntesis de Mitigación de Sesgos]
    G1 --> H1[Fund Manager - Decisión Final & Riesgo ATR]
    H1 --> I1[Generación de daily_selection.md / JSON]
    I1 --> J1[Clasificación: COMPRA FUERTE | COMPRA | MANTENER | VENTA | VENTA FUERTE]
```

---

## ⭐️ Características Clave Implementadas

1. **Ingesta Multi-Fuente y Consistency Checker**:
   - **SEC EDGAR API (Oficial)**: Consulta directa de reportes 10-K y 10-Q de la SEC para datos auditados de balances y estados de resultados.
   - **Finnhub API**: Obtención de ratios fundamentales y perfil de empresa.
   - **yfinance**: Extracción de precios históricos e indicadores técnicos.
   - **DataReconciler**: Valida consistencia cruzada entre las fuentes y asigna una puntuación de confianza (`100%`, `85%`, etc.).

2. **Filtro Gatekeeper Fundamental (Ahorro de Cómputo)**:
   - Evalúa `Crecimiento de Ingresos (YoY)`, `Margen Neto`, y `Deuda/Capital`.
   - Si la empresa no cumple los criterios (p. ej. Intel por margen neto negativo de -19.8% o NVIDIA por Deuda/Capital elevado), el flujo **detiene** el análisis técnico y el debate, ahorrando costos computacionales.

3. **Analista Técnico de Momentum (ISA)**:
   - Calcula **RSI (14)**, **MACD (12,26,9)**, **Bandas de Bollinger (20,2)**, **Medias Móviles (SMA 50/200)** y **ATR (14)**.

4. **Capa de Debate (Bullish vs Bearish)**:
   - **Bullish Researcher**: Argumenta la tesis alcista.
   - **Bearish Researcher**: Actúa como abogado del diablo identificando sobrevaloración P/E o resistencias.

5. **Fund Manager (5 Decisiones Estrictas & Riesgo ATR)**:
   - Asigna una de las 5 categorías requeridas:
     - `COMPRA FUERTE` (Strong Buy)
     - `COMPRA` (Buy)
     - `MANTENER` (Hold)
     - `VENTA` (Sell)
     - `VENTA FUERTE` (Strong Sell)
   - Calcula automáticamente precio **Stop-Loss** (`Precio - 2.0 * ATR`) y **Take-Profit** (`Precio + 3.5 * ATR`) junto con el porcentaje de cartera recomendado.

---

## 🔬 Resultados de Verificación y Pruebas

### 1. Pruebas Unitarias (`pytest tests/`)
Se ejecutaron 4 pruebas automáticas con **100% de aprobación**:
- `test_fetcher.py`: Verificación de cálculo de RSI, MACD, Bandas de Bollinger y ATR.
- `test_reconciler.py`: Verificación de consistencia multi-proveedor y detección de discrepancias.
- `test_workflow.py`: Verificación de ejecución del grafo de estados de LangGraph y asignación de dictamen final.

```
collected 4 items
tests\test_fetcher.py .                                                  [ 25%]
tests\test_reconciler.py ..                                              [ 75%]
tests\test_workflow.py .                                                 [100%]
============================== 4 passed in 3.08s ==============================
```

### 2. Ejecución Real CLI por Lotes (`cli.py`)
Resultados del análisis ejecutable para `NVDA`, `AAPL`, `TSLA` e `INTC`:

| Ticker | Empresa | Gatekeeper | Momentum | Dictamen Final | Posición | Stop-Loss ATR | Take-Profit ATR |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **NVDA** | NVIDIA Corp | ❌ RECHAZADO | N/A | **VENTA** | 0.0% | N/A | N/A |
| **AAPL** | Apple Inc. | ✅ APROBADO | NEUTRAL | **MANTENER** | 2.0% - 3.0% | $294.63 | $346.05 |
| **TSLA** | Tesla, Inc. | ✅ APROBADO | NEUTRAL | **MANTENER** | 2.0% - 3.0% | $298.70 | $380.87 |
| **INTC** | Intel Corp | ❌ RECHAZADO | N/A | **VENTA FUERTE** | 0.0% | N/A | N/A |

### 3. Informe Generado
El informe completo en Markdown se guardó en [daily_selection.md](file:///c:/Users/cterr/Documents/10_Multi_Agent_Financiero/output/daily_selection.md).

---

## 🚀 Cómo Ejecutar el Proyecto

### Opción A: Vía Línea de Comandos (CLI)
```bash
python cli.py --tickers NVDA,AAPL,MSFT,TSLA,INTC
```

### Opción B: Dashboard Web Interactivo
```bash
python -m src.web.app
```
Abre en tu navegador `http://localhost:8000` para acceder a la interfaz futurista dark mode con stream de registros en tiempo real.

### Opción C: Despliegue en Docker
```bash
docker-compose up --build
```
