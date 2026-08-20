document.addEventListener("DOMContentLoaded", () => {
    const analyzeBtn = document.getElementById("analyzeBtn");
    const tickerInput = document.getElementById("tickerInput");
    const progressSection = document.getElementById("progressSection");
    const progressBar = document.getElementById("progressBar");
    const terminalLogs = document.getElementById("terminalLogs");
    const resultsSection = document.getElementById("resultsSection");

    analyzeBtn.addEventListener("click", () => {
        const inputVal = tickerInput.value.trim();
        if (!inputVal) return;

        const tickers = inputVal.split(",").map(t => t.trim()).filter(Boolean);
        if (tickers.length === 0) return;

        startAnalysis(tickers);
    });
});

function setTickers(tickersStr) {
    document.getElementById("tickerInput").value = tickersStr;
}

async function startAnalysis(tickers) {
    const progressSection = document.getElementById("progressSection");
    const progressBar = document.getElementById("progressBar");
    const terminalLogs = document.getElementById("terminalLogs");
    const resultsSection = document.getElementById("resultsSection");
    const analyzeBtn = document.getElementById("analyzeBtn");

    analyzeBtn.disabled = true;
    progressSection.classList.remove("hidden");
    resultsSection.innerHTML = "";
    terminalLogs.innerHTML = "";
    progressBar.style.width = "20%";

    appendLog(`[Orquestador] Iniciando Pipeline de Selección para: ${tickers.join(", ")}`);
    appendLog(`[Multi-Vendor] Consultando SEC EDGAR API, Finnhub API e yfinance...`);

    try {
        progressBar.style.width = "50%";
        const res = await fetch("/api/analyze", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ tickers: tickers })
        });

        progressBar.style.width = "90%";
        const data = await res.json();

        if (data.status === "SUCCESS") {
            progressBar.style.width = "100%";
            appendLog(`[Completado] Se analizaron exitosamente ${data.count} empresas.`);
            setTimeout(() => {
                progressSection.classList.add("hidden");
            }, 1200);

            renderResults(data.results);
        } else {
            appendLog(`[Error] ${data.error || 'Error al procesar el análisis'}`);
        }
    } catch (err) {
        appendLog(`[Error de Conexión] ${err.message}`);
    } finally {
        analyzeBtn.disabled = false;
    }
}

function appendLog(msg) {
    const terminalLogs = document.getElementById("terminalLogs");
    const item = document.createElement("div");
    item.className = "terminal-log-item";
    const time = new Date().toLocaleTimeString();
    item.innerHTML = `<span style="color: #60a5fa;">[${time}]</span> ${msg}`;
    terminalLogs.appendChild(item);
    terminalLogs.scrollTop = terminalLogs.scrollHeight;
}

function renderResults(results) {
    const resultsSection = document.getElementById("resultsSection");
    resultsSection.innerHTML = "";

    results.forEach(res => {
        const ticker = res.ticker || "N/A";
        const company = res.company_name || ticker;
        const gatekeeperPassed = res.passed_fundamental_gatekeeper;
        const fund = res.fundamental_report || {};
        const tech = res.technical_report || {};
        const debate = res.debate_report || {};
        const final = res.final_decision || {};
        const rec = res.reconciliation_data || {};

        const rating = final.rating || "VENTA";
        const ratingClass = getRatingClass(rating);

        const card = document.createElement("div");
        card.className = `glass-card stock-card ${ratingClass}`;

        card.innerHTML = `
            <div class="card-header">
                <div class="card-ticker-name">
                    <span class="ticker-symbol">${ticker}</span>
                    <span class="company-title">${company} (${res.sector || 'S/D'})</span>
                </div>
                <div class="decision-badge badge-${ratingClass}">
                    ${rating}
                </div>
            </div>

            <div class="card-grid">
                <!-- Box 1: Reconciliación & Gatekeeper -->
                <div class="card-sub-box">
                    <div class="box-title"><i class="fa-solid fa-shield-halved"></i> Gatekeeper Fundamental</div>
                    <div class="metric-row">
                        <span class="metric-label">Estado Filtro:</span>
                        <span class="metric-val" style="color: ${gatekeeperPassed ? '#34d399' : '#f87171'}">
                            ${gatekeeperPassed ? '✅ APROBADO' : '❌ RECHAZADO'}
                        </span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Confianza Datos:</span>
                        <span class="metric-val">${(rec.confidence_score * 100 || 100).toFixed(0)}%</span>
                    </div>
                    <p style="font-size: 0.8rem; color: #9ca3af; margin-top: 6px;">${fund.summary || ''}</p>
                </div>

                <!-- Box 2: Momentum Técnico -->
                <div class="card-sub-box">
                    <div class="box-title"><i class="fa-solid fa-chart-candlestick"></i> Momentum Técnico (ISA)</div>
                    <div class="metric-row">
                        <span class="metric-label">Clasificación:</span>
                        <span class="metric-val" style="color: #60a5fa;">${tech.momentum_classification || 'N/A'}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">RSI (14):</span>
                        <span class="metric-val">${tech.rsi !== undefined ? tech.rsi : 'N/A'}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">MACD Hist:</span>
                        <span class="metric-val">${tech.macd_hist !== undefined ? tech.macd_hist : 'N/A'}</span>
                    </div>
                </div>

                <!-- Box 3: Gestión de Riesgo ATR -->
                <div class="card-sub-box">
                    <div class="box-title"><i class="fa-solid fa-vault"></i> Asignación & Riesgo ATR</div>
                    <div class="metric-row">
                        <span class="metric-label">Posición Sugerida:</span>
                        <span class="metric-val" style="color: #fbbf24;">${final.position_size_pct || '0%'}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Stop-Loss (ATR):</span>
                        <span class="metric-val" style="color: #f87171;">${final.stop_loss_atr ? '$' + final.stop_loss_atr : 'N/A'}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Take-Profit (ATR):</span>
                        <span class="metric-val" style="color: #34d399;">${final.take_profit_atr ? '$' + final.take_profit_atr : 'N/A'}</span>
                    </div>
                </div>
            </div>

            ${gatekeeperPassed ? `
            <div style="margin-top: 14px; background: rgba(15, 23, 42, 0.4); padding: 12px; border-radius: 8px; font-size: 0.85rem;">
                <strong style="color: #93c5fd;"><i class="fa-solid fa-comments"></i> Síntesis del Debate (Bull vs Bear):</strong>
                <p style="color: #d1d5db; margin-top: 4px;">${debate.synthesis || ''}</p>
            </div>
            ` : ''}
        `;

        resultsSection.appendChild(card);
    });
}

function getRatingClass(rating) {
    switch (rating) {
        case "COMPRA FUERTE": return "compra-fuerte";
        case "COMPRA": return "compra";
        case "MANTENER": return "mantener";
        case "VENTA": return "venta";
        case "VENTA FUERTE": return "venta-fuerte";
        default: return "venta";
    }
}
