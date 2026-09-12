/**
 * Asset Analysis - Individual asset charts and analysis
 */

// Use the global API_BASE_URL from app.js (loaded first)
const ASSET_API = window.API_BASE_URL || CONFIG?.API_BASE_URL || 'http://localhost:8000/api';
let assetChart = null;
let currentAssetPeriod = '3mo';
let currentAssetData = null;

// ASSET_DISPLAY_NAMES lives in app.js (loaded before this file) — single
// source of truth shared by every page. Do not redeclare it here.

/**
 * Initialize asset analysis when page loads
 */
function initAssetAnalysis() {
    loadAssetSelector();
    setupPeriodButtons();
    setupChartTypeToggle();
    loadAssetQuickCards();
    loadBenchmarkChart();
    loadRiskAndCorrelation();
    loadAdvancedAnalytics();
    loadPortfolioRiskMetrics();
    loadHoldingsCatalysts();
    loadAttribution();
    loadStressTest();
}

/**
 * Load assets into selector dropdown
 */
async function loadAssetSelector() {
    const selector = document.getElementById('assetSelector');
    if (!selector) return;
    
    try {
        const response = await fetch(`${ASSET_API}/positions`);
        const positions = await response.json();
        
        selector.innerHTML = '<option value="">-- Elige un activo --</option>';
        
        positions.forEach(pos => {
            const displayName = ASSET_DISPLAY_NAMES[pos.ticker]?.name || pos.ticker;
            const option = document.createElement('option');
            option.value = pos.ticker;
            option.textContent = `${displayName} (${pos.ticker})`;
            option.dataset.type = pos.type;
            selector.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading assets:', error);
    }
}

/**
 * Setup period button click handlers
 */
function setupPeriodButtons() {
    const container = document.getElementById('assetPeriodButtons');
    if (!container) return;
    
    container.addEventListener('click', (e) => {
        if (e.target.classList.contains('period-btn')) {
            // Update active state
            container.querySelectorAll('.period-btn').forEach(btn => btn.classList.remove('active'));
            e.target.classList.add('active');
            
            // Load new period
            currentAssetPeriod = e.target.dataset.period;
            loadAssetChart();
        }
    });
}

/**
 * Load chart for selected asset
 */
async function loadAssetChart() {
    const selector = document.getElementById('assetSelector');
    const ticker = selector?.value;
    
    if (!ticker) {
        showChartPlaceholder();
        return;
    }
    
    const assetType = selector.options[selector.selectedIndex].dataset.type;
    
    try {
        // Show loading state
        showChartLoading();
        
        // Fetch historical data
        const response = await fetch(
            `${ASSET_API}/asset/${ticker}/history?period=${currentAssetPeriod}&asset_type=${assetType}`
        );
        
        if (!response.ok) {
            throw new Error('Failed to fetch asset data');
        }
        
        const data = await response.json();
        currentAssetData = data;
        
        // Update UI
        updateAssetInfo(ticker, data);
        renderAssetChart(data);
        
        // Show action buttons
        document.getElementById('assetActions').style.display = 'flex';
        
    } catch (error) {
        console.error('Error loading asset chart:', error);
        showChartError(error.message, ticker);
    }
}

/**
 * Update asset information panel
 */
async function updateAssetInfo(ticker, data) {
    const panel = document.getElementById('assetInfoPanel');
    panel.style.display = 'block';
    
    const assetInfo = ASSET_DISPLAY_NAMES[ticker] || { name: ticker, icon: '📊', color: '#2C4A6E' };
    
    // Update basic info
    document.getElementById('assetIconLarge').textContent = assetInfo.icon;
    document.getElementById('assetIconLarge').style.background = `linear-gradient(135deg, ${assetInfo.color}33, ${assetInfo.color}11)`;
    document.getElementById('assetIconLarge').style.color = assetInfo.color;
    document.getElementById('assetName').textContent = assetInfo.name;
    document.getElementById('assetTickerBadge').textContent = ticker;
    
    // Update price info
    if (data.current) {
        const price = data.current.price || data.current.price_eur || 0;
        const change = data.current.change_percent || data.current.change_24h || 0;
        
        document.getElementById('assetCurrentPrice').textContent = formatCurrencyLocal(price);
        
        const changeEl = document.getElementById('assetPriceChange');
        changeEl.textContent = `${change >= 0 ? '+' : ''}${change.toFixed(2)}%`;
        changeEl.className = `price-change ${change >= 0 ? 'positive' : 'negative'}`;
    }
    
    // Get position data
    try {
        const portfolioRes = await fetch(`${ASSET_API}/portfolio`);
        const portfolio = await portfolioRes.json();
        
        const position = portfolio.positions?.find(p => p.ticker === ticker);
        if (position) {
            document.getElementById('assetPosition').textContent = 
                `${position.quantity.toFixed(position.type === 'crypto' ? 6 : 4)} unidades`;
            document.getElementById('assetValue').textContent = formatCurrencyLocal(position.market_value);
            
            const gainLossEl = document.getElementById('assetGainLoss');
            gainLossEl.textContent = `${position.gain_loss >= 0 ? '+' : ''}${formatCurrencyLocal(position.gain_loss)} (${position.gain_loss_pct.toFixed(2)}%)`;
            gainLossEl.className = `stat-value ${position.gain_loss >= 0 ? 'positive' : 'negative'}`;
            
            document.getElementById('assetWeight').textContent = `${position.weight.toFixed(1)}%`;
        }
    } catch (error) {
        console.error('Error loading position data:', error);
    }
}

/**
 * Render the asset chart
 */
// Current chart type for TradingView ('candles' | 'area')
let currentChartType = 'candles';
let tvChart = null;
let tvSeries = null;

function setupChartTypeToggle() {
    const container = document.getElementById('chartTypeToggle');
    if (!container) return;
    container.addEventListener('click', (e) => {
        if (e.target.dataset.charttype) {
            container.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            currentChartType = e.target.dataset.charttype;
            if (currentAssetData) renderAssetChart(currentAssetData);
        }
    });
}

function renderTradingViewChart(data) {
    const tvContainer = document.getElementById('tvChartContainer');
    const canvas = document.getElementById('assetHistoryChart');
    const placeholder = document.querySelector('.chart-placeholder');
    if (placeholder) placeholder.style.display = 'none';
    if (canvas) canvas.style.display = 'none';
    tvContainer.style.display = 'block';

    // Clean previous chart
    if (tvChart) {
        try { tvChart.remove(); } catch (e) { /* noop */ }
        tvChart = null;
        tvSeries = null;
    }
    tvContainer.innerHTML = '';

    const chart = LightweightCharts.createChart(tvContainer, {
        width: tvContainer.clientWidth,
        height: 400,
        layout: {
            background: { color: 'transparent' },
            textColor: '#746E63',
        },
        grid: {
            vertLines: { color: 'rgba(30, 41, 59, 0.5)' },
            horzLines: { color: 'rgba(30, 41, 59, 0.5)' },
        },
        rightPriceScale: { borderColor: '#D8D0C0' },
        timeScale: { borderColor: '#D8D0C0', timeVisible: false },
        crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    });
    tvChart = chart;

    const history = data.history || [];
    const hasOHLC = history.length > 0 && history[0].open !== undefined && history[0].high !== undefined;

    if (currentChartType === 'candles' && hasOHLC) {
        const series = chart.addCandlestickSeries({
            upColor: '#2C4A6E', downColor: '#C6473C',
            borderUpColor: '#2C4A6E', borderDownColor: '#C6473C',
            wickUpColor: '#2C4A6E', wickDownColor: '#C6473C',
        });
        series.setData(history.map(h => ({
            time: h.date,
            open: h.open, high: h.high, low: h.low, close: h.close,
        })));
        tvSeries = series;
    } else {
        // Area chart (also used when only close prices are available, e.g. crypto from CoinGecko)
        const firstPrice = history[0]?.close ?? history[0]?.price ?? 0;
        const lastPrice = history[history.length - 1]?.close ?? history[history.length - 1]?.price ?? 0;
        const up = lastPrice >= firstPrice;
        const color = up ? '#2C4A6E' : '#C6473C';
        const series = chart.addAreaSeries({
            lineColor: color,
            topColor: up ? 'rgba(44, 74, 110,0.4)' : 'rgba(198, 71, 60,0.4)',
            bottomColor: 'rgba(0,0,0,0)',
            lineWidth: 2,
        });
        series.setData(history.map(h => ({
            time: h.date,
            value: h.close ?? h.price,
        })));
        tvSeries = series;
    }

    chart.timeScale().fitContent();

    // Responsive resize
    if (!tvContainer._resizeHandler) {
        tvContainer._resizeHandler = () => {
            if (tvChart) tvChart.applyOptions({ width: tvContainer.clientWidth });
        };
        window.addEventListener('resize', tvContainer._resizeHandler);
    }
}

function renderAssetChart(data) {
    // Prefer TradingView lightweight-charts; fall back to Chart.js if the lib didn't load
    if (typeof LightweightCharts !== 'undefined') {
        try {
            renderTradingViewChart(data);
            return;
        } catch (err) {
            console.warn('TradingView chart failed, falling back to Chart.js:', err);
        }
    }

    const canvas = document.getElementById('assetHistoryChart');
    const tvContainer = document.getElementById('tvChartContainer');
    const placeholder = document.querySelector('.chart-placeholder');

    if (tvContainer) tvContainer.style.display = 'none';
    if (placeholder) placeholder.style.display = 'none';
    canvas.style.display = 'block';

    // Destroy existing chart
    if (assetChart && typeof assetChart.destroy === 'function') {
        assetChart.destroy();
    }

    const ctx = canvas.getContext('2d');
    const assetInfo = ASSET_DISPLAY_NAMES[data.ticker] || { color: '#2C4A6E' };
    
    // Prepare data
    const labels = data.history.map(h => h.date);
    const prices = data.history.map(h => h.close || h.price);
    
    // Calculate gradient
    const gradient = ctx.createLinearGradient(0, 0, 0, 400);
    gradient.addColorStop(0, `${assetInfo.color}40`);
    gradient.addColorStop(1, `${assetInfo.color}00`);
    
    // Determine if price went up or down
    const firstPrice = prices[0];
    const lastPrice = prices[prices.length - 1];
    const lineColor = lastPrice >= firstPrice ? '#2C4A6E' : '#C6473C';
    
    assetChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: data.ticker,
                data: prices,
                borderColor: lineColor,
                backgroundColor: gradient,
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 6,
                pointHoverBackgroundColor: lineColor,
                pointHoverBorderColor: '#fff',
                pointHoverBorderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: '#EFEBE3',
                    titleColor: '#746E63',
                    bodyColor: '#2B2822',
                    borderColor: '#D8D0C0',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: false,
                    callbacks: {
                        title: function(context) {
                            return formatDateLocal(context[0].label);
                        },
                        label: function(context) {
                            return formatCurrencyLocal(context.raw);
                        }
                    }
                }
            },
            scales: {
                x: {
                    title: { display: true, text: 'Fecha', color: '#8A8275', font: { size: 12, weight: '600' } },
                    grid: { display: false },
                    ticks: {
                        color: '#9C9689',
                        maxTicksLimit: 8,
                        callback: function(value, index) {
                            const date = this.getLabelForValue(value);
                            return new Date(date).toLocaleDateString('es-ES', { day: '2-digit', month: 'short' });
                        }
                    }
                },
                y: {
                    title: { display: true, text: 'Precio', color: '#8A8275', font: { size: 12, weight: '600' } },
                    grid: { color: '#EFEBE3' },
                    ticks: {
                        color: '#9C9689',
                        callback: function(value) {
                            return formatCurrencyLocal(value);
                        }
                    }
                }
            }
        }
    });
}

/**
 * Load quick asset cards
 */
async function loadAssetQuickCards() {
    const grid = document.getElementById('assetCardsGrid');
    if (!grid) return;
    
    try {
        const response = await fetch(`${ASSET_API}/portfolio`);
        const portfolio = await response.json();
        
        if (!portfolio.positions || portfolio.positions.length === 0) {
            grid.innerHTML = '<p class="no-data">No hay activos en tu cartera</p>';
            return;
        }
        
        grid.innerHTML = portfolio.positions.map(pos => {
            const info = ASSET_DISPLAY_NAMES[pos.ticker] || { name: pos.ticker, icon: '📊', color: '#2C4A6E' };
            const changeClass = pos.day_change_pct >= 0 ? 'positive' : 'negative';
            const changeSign = pos.day_change_pct >= 0 ? '+' : '';
            
            return `
                <div class="asset-quick-card" onclick="selectAsset('${pos.ticker}')" style="--accent-color: ${info.color}">
                    <div class="quick-card-header">
                        <span class="quick-card-icon">${info.icon}</span>
                        <span class="quick-card-ticker">${info.name}</span>
                    </div>
                    <div class="quick-card-name">${pos.ticker}</div>
                    <div class="quick-card-price">${formatCurrencyLocal(pos.current_price)}</div>
                    <div class="quick-card-change ${changeClass}">
                        ${changeSign}${pos.day_change_pct.toFixed(2)}% hoy
                    </div>
                    <div class="quick-card-value">
                        Tu posición: ${formatCurrencyLocal(pos.market_value)}
                    </div>
                </div>
            `;
        }).join('');
        
    } catch (error) {
        console.error('Error loading asset cards:', error);
        grid.innerHTML = '<p class="error">Error al cargar los activos</p>';
    }
}

/**
 * Select an asset from quick cards
 */
function selectAsset(ticker) {
    const selector = document.getElementById('assetSelector');
    if (selector) {
        selector.value = ticker;
        loadAssetChart();
        
        // Scroll to chart
        document.querySelector('.asset-chart-card')?.scrollIntoView({ behavior: 'smooth' });
    }
}

/**
 * Show buy advice modal
 */
function showBuyAdvice() {
    if (!currentAssetData) return;
    
    const ticker = currentAssetData.ticker;
    const history = currentAssetData.history;
    
    // Simple analysis
    const prices = history.map(h => h.close || h.price);
    const currentPrice = prices[prices.length - 1];
    const avgPrice = prices.reduce((a, b) => a + b, 0) / prices.length;
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);
    
    const percentFromMin = ((currentPrice - minPrice) / minPrice * 100).toFixed(1);
    const percentFromMax = ((currentPrice - maxPrice) / maxPrice * 100).toFixed(1);
    const percentFromAvg = ((currentPrice - avgPrice) / avgPrice * 100).toFixed(1);
    
    let advice = '';
    let adviceClass = '';
    
    if (currentPrice < avgPrice * 0.95) {
        advice = '🟢 El precio está por debajo de la media. Podría ser buen momento para comprar.';
        adviceClass = 'advice-buy';
    } else if (currentPrice > avgPrice * 1.1) {
        advice = '🔴 El precio está significativamente por encima de la media. Considera esperar una corrección.';
        adviceClass = 'advice-wait';
    } else {
        advice = '🟡 El precio está cerca de la media. Puedes comprar gradualmente (DCA).';
        adviceClass = 'advice-neutral';
    }
    
    // Show as toast or modal
    const message = `
        📊 Análisis de ${ticker}
        
        Precio actual: ${formatCurrencyLocal(currentPrice)}
        Precio medio (${currentAssetPeriod}): ${formatCurrencyLocal(avgPrice)}
        
        📈 Desde mínimo: ${percentFromMin}%
        📉 Desde máximo: ${percentFromMax}%
        ⚖️ Vs media: ${percentFromAvg}%
        
        ${advice}
        
        ⚠️ Esto no es consejo financiero. Haz tu propia investigación.
    `;
    
    alert(message);
}

/**
 * Show detailed analysis
 */
function showDetailedAnalysis() {
    if (!currentAssetData) return;
    const ticker = currentAssetData.ticker;
    const name = ASSET_DISPLAY_NAMES[ticker]?.name || ticker;
    openDeepAnalysis(ticker, name);
}

// Helper functions
function showChartPlaceholder() {
    const placeholder = document.querySelector('.chart-placeholder');
    const canvas = document.getElementById('assetHistoryChart');
    const panel = document.getElementById('assetInfoPanel');
    const actions = document.getElementById('assetActions');
    
    if (placeholder) placeholder.style.display = 'flex';
    if (canvas) canvas.style.display = 'none';
    if (panel) panel.style.display = 'none';
    if (actions) actions.style.display = 'none';
}

function showChartLoading() {
    const placeholder = document.querySelector('.chart-placeholder');
    if (placeholder) {
        placeholder.innerHTML = '<span class="placeholder-icon">⏳</span><p>Cargando datos...</p>';
        placeholder.style.display = 'flex';
    }
}

function showChartError(message, ticker = null) {
    const placeholder = document.querySelector('.chart-placeholder');
    if (placeholder) {
        // Check if it's a data availability issue for ETFs
        const isDataUnavailable = message.includes('No historical data') || message.includes('Failed to fetch');
        const isEtfOrFund = ticker && ['SGLD.L', 'LYX0F.DE', 'IE00BYX5NX33'].includes(ticker.toUpperCase());
        
        if (isDataUnavailable && isEtfOrFund) {
            placeholder.innerHTML = `
                <span class="placeholder-icon">📊</span>
                <p style="font-weight: 600; margin-bottom: 8px;">Historial no disponible para ${ticker}</p>
                <p style="font-size: 0.9em; color: var(--text-muted); max-width: 400px; text-align: center;">
                    Los datos históricos de ETFs europeos no están disponibles temporalmente. 
                    El precio actual se muestra correctamente en el Dashboard.
                </p>
                <p style="font-size: 0.85em; color: var(--text-muted); margin-top: 12px;">
                    💡 Las criptos (BTC, ETH, etc.) sí tienen gráficas disponibles.
                </p>
            `;
        } else if (isDataUnavailable) {
            placeholder.innerHTML = `
                <span class="placeholder-icon">⏳</span>
                <p style="font-weight: 600; margin-bottom: 8px;">Cargando datos de ${ticker || 'activo'}...</p>
                <p style="font-size: 0.9em; color: var(--text-muted);">
                    Puede tardar hasta 60 segundos debido a límites de la API.
                </p>
            `;
        } else {
            placeholder.innerHTML = `<span class="placeholder-icon">❌</span><p>Error: ${message}</p>`;
        }
        placeholder.style.display = 'flex';
    }
}

function formatCurrencyLocal(value) {
    return new Intl.NumberFormat('es-ES', {
        style: 'currency',
        currency: 'EUR',
        minimumFractionDigits: 2,
        maximumFractionDigits: value < 1 ? 6 : 2
    }).format(value);
}

function formatDateLocal(dateStr) {
    return new Date(dateStr).toLocaleDateString('es-ES', {
        day: '2-digit',
        month: 'short',
        year: 'numeric'
    });
}

/**
 * "Rendimiento vs Benchmark" — your portfolio's daily value history vs the
 * S&P 500 over the same window, both indexed to 0% at the common start date.
 */
let benchmarkChartInstance = null;
async function loadBenchmarkChart() {
    const canvas = document.getElementById('benchmarkChart');
    if (!canvas || typeof Chart === 'undefined') return;
    try {
        const [histResp, spyResp] = await Promise.all([
            fetch(`${ASSET_API}/portfolio/history?days=90`),
            fetch(`${ASSET_API}/asset/SPY/history?period=3mo&asset_type=stock`),
        ]);
        const hist = await histResp.json();
        const spy = await spyResp.json();
        const portfolioSeries = hist.history || [];
        const spyByDate = {};
        (spy.history || []).forEach(h => { spyByDate[h.date] = h.close; });
        const aligned = portfolioSeries.filter(p => spyByDate[p.date] !== undefined);
        if (aligned.length < 2) return;

        const baseP = aligned[0].value;
        const baseS = spyByDate[aligned[0].date];
        const labels = aligned.map(p => p.date);
        const portfolioPct = aligned.map(p => (p.value / baseP - 1) * 100);
        const spyPct = aligned.map(p => (spyByDate[p.date] / baseS - 1) * 100);

        if (benchmarkChartInstance) benchmarkChartInstance.destroy();
        benchmarkChartInstance = new Chart(canvas.getContext('2d'), {
            type: 'line',
            data: {
                labels,
                datasets: [
                    { label: 'Tu cartera', data: portfolioPct, borderColor: '#2C4A6E', backgroundColor: 'transparent', tension: 0.2, pointRadius: 0, borderWidth: 2 },
                    { label: 'S&P 500', data: spyPct, borderColor: '#746E63', backgroundColor: 'transparent', tension: 0.2, pointRadius: 0, borderWidth: 2, borderDash: [4, 4] },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: true, labels: { color: '#746E63', boxWidth: 12 } } },
                scales: {
                    x: { title: { display: true, text: 'Fecha', color: '#8A8275', font: { size: 12, weight: '600' } }, ticks: { display: false }, grid: { display: false } },
                    y: { title: { display: true, text: 'Rentabilidad acumulada (%)', color: '#8A8275', font: { size: 12, weight: '600' } }, ticks: { color: '#746E63', callback: v => `${v.toFixed(0)}%` }, grid: { color: 'rgba(148,163,184,0.1)' } },
                },
            },
        });
    } catch (err) {
        console.error('benchmark chart failed:', err);
    }
}

/**
 * "Distribución de Riesgo" (real annualized volatility, weighted by position
 * size — not the hardcoded 30/45/25 this used to show) + "Correlación de
 * Activos" — both come from the same /portfolio/risk-analysis call.
 */
async function loadRiskAndCorrelation() {
    try {
        const resp = await fetch(`${ASSET_API}/portfolio/risk-analysis`);
        const data = await resp.json();
        renderRiskDistribution(data.risk_distribution || {});
        renderCorrelationMatrix(data.correlation || {});
        renderRiskReturnScatter(data.risk_by_ticker || {}, data.return_by_ticker || {}, data.weight_by_ticker || {});
    } catch (err) {
        console.error('risk/correlation load failed:', err);
    }
}

function renderRiskDistribution(dist) {
    const map = { low: 'riskLow', medium: 'riskMedium', high: 'riskHigh' };
    for (const [key, elId] of Object.entries(map)) {
        const pct = dist[key] || 0;
        const pctEl = document.getElementById(elId);
        if (!pctEl) continue;
        pctEl.textContent = `${pct.toFixed(1)}%`;
        const fillEl = pctEl.closest('.risk-item')?.querySelector('.risk-fill');
        if (fillEl) fillEl.style.width = `${pct}%`;
    }
}

function renderCorrelationMatrix(correlation) {
    const container = document.getElementById('correlationMatrix');
    if (!container) return;
    const tickers = correlation.tickers || [];
    const matrix = correlation.matrix || [];
    if (!tickers.length || !matrix.length) {
        container.innerHTML = '<p class="text-muted">Aún no hay suficiente histórico para calcular correlaciones.</p>';
        return;
    }
    const N = Math.min(8, tickers.length); // top holdings only — an 18x18 grid doesn't fit a small card
    const colorFor = (v) => v >= 0
        ? `rgba(44, 74, 110, ${Math.min(Math.abs(v), 1) * 0.6})`
        : `rgba(198, 71, 60, ${Math.min(Math.abs(v), 1) * 0.6})`;
    // Raw ISINs/tickers (IE00BYX5NX33, LYX0F.DE...) mean nothing at a glance —
    // always show the human name here, ticker only as a hover tooltip.
    const label = (t) => {
        const info = ASSET_DISPLAY_NAMES[t?.toUpperCase()];
        return info ? `${info.icon} ${info.short || info.name}` : t;
    };

    let html = '<div style="overflow-x:auto"><table class="correlation-table"><thead><tr><th></th>';
    for (let j = 0; j < N; j++) html += `<th title="${tickers[j]}">${label(tickers[j])}</th>`;
    html += '</tr></thead><tbody>';
    for (let i = 0; i < N; i++) {
        html += `<tr><th title="${tickers[i]}">${label(tickers[i])}</th>`;
        for (let j = 0; j < N; j++) {
            const v = matrix[i]?.[j];
            const cell = v != null ? v.toFixed(2) : '-';
            html += `<td style="background:${v != null ? colorFor(v) : 'transparent'}" title="${label(tickers[i])} vs ${label(tickers[j])}">${cell}</td>`;
        }
        html += '</tr>';
    }
    html += '</tbody></table></div>';
    container.innerHTML = html;
}

// ============ Analítica avanzada (gráficos de nivel profesional) ============
const _advCharts = {};
const ADV = { blue: '#2C4A6E', green: '#16a34a', red: '#dc2626', ink: '#2b2822', grid: 'rgba(43,40,34,0.08)', muted: '#6b6560' };

function _destroyAdv(id) {
    if (_advCharts[id]) { try { _advCharts[id].destroy(); } catch (e) {} delete _advCharts[id]; }
}

function _noData(canvasId, msg) {
    const c = document.getElementById(canvasId);
    if (!c) return;
    _destroyAdv(canvasId);
    const ctx = c.getContext('2d');
    ctx.clearRect(0, 0, c.width, c.height);
    ctx.fillStyle = ADV.muted; ctx.font = '12px Outfit, sans-serif'; ctx.textAlign = 'center';
    ctx.fillText(msg, (c.width || 200) / 2, (c.height || 80) / 2);
}

function _dailyReturns(history) {
    const vals = (history || []).map(h => h.value).filter(v => v > 0);
    const rets = [];
    for (let i = 1; i < vals.length; i++) rets.push((vals[i] - vals[i - 1]) / vals[i - 1]);
    return rets;
}

async function loadPortfolioRiskMetrics() {
    const el = document.getElementById('portfolioRiskMetrics');
    if (!el) return;
    let d;
    try {
        const r = await fetch(`${ASSET_API}/portfolio/risk-metrics`);
        if (!r.ok) { el.innerHTML = '<p class="text-muted">No disponible ahora mismo.</p>'; return; }
        d = await r.json();
    } catch (e) { el.innerHTML = '<p class="text-muted">No disponible ahora mismo.</p>'; return; }
    if (d.status !== 'ready') {
        el.innerHTML = `<p class="text-muted">Necesita más histórico de cartera (${d.days_tracked || 0} días registrados) — se va construyendo cada día.</p>`;
        return;
    }
    const num = (v) => v == null ? '—' : (+v).toFixed(2);
    const tile = (label, value, sub) => `<div style="background:rgba(43,40,34,0.03); border-radius:8px; padding:10px 12px; min-width:118px; flex:1;">
        <div style="font-size:11px; color:var(--text-secondary);">${label}</div>
        <div style="font-size:18px; font-weight:700; margin-top:2px;">${value}</div>
        ${sub ? `<div style="font-size:10.5px; color:var(--text-tertiary); margin-top:1px;">${sub}</div>` : ''}
    </div>`;
    el.innerHTML = `<div style="display:flex; gap:8px; flex-wrap:wrap;">
        ${tile('Volatilidad anual', d.volatility_pct + '%', 'cuánto oscila')}
        ${tile('Máx. drawdown', d.max_drawdown_pct + '%', 'peor caída desde máximo')}
        ${tile('Sharpe', num(d.sharpe), 'retorno / riesgo')}
        ${tile('Sortino', num(d.sortino), 'penaliza solo caídas')}
        ${tile('Calmar', num(d.calmar), 'retorno / peor caída')}
        ${tile('VaR 95% diario', d.var_95_pct + '%', 'pérdida diaria extrema')}
        ${tile('CVaR 95%', d.cvar_95_pct + '%', 'media del peor 5% de días')}
        ${tile('Beta', num(d.beta), `vs ${d.benchmark}`)}
        ${tile('Alpha anual', d.alpha_annual_pct == null ? '—' : d.alpha_annual_pct + '%', `vs ${d.benchmark}`)}
    </div>
    <p class="text-muted" style="font-size:10.5px; margin:8px 0 0;">Sobre ${d.n_returns} días de retorno reales (excluye días de aportación). Benchmark: ${d.benchmark}.</p>`;
}

async function loadStressTest() {
    const el = document.getElementById('stressTestContent');
    if (!el) return;
    let d;
    try {
        const r = await fetch(`${ASSET_API}/portfolio/stress-test`);
        if (!r.ok) { el.innerHTML = '<p class="text-muted">No disponible.</p>'; return; }
        d = await r.json();
    } catch (e) { el.innerHTML = '<p class="text-muted">No disponible.</p>'; return; }
    const sc = d.scenarios || [];
    if (!sc.length) { el.innerHTML = '<p class="text-muted">Sin posiciones para simular.</p>'; return; }
    const fmt = (v) => (v >= 0 ? '+' : '') + Math.round(v).toLocaleString('es-ES') + ' €';
    const rows = sc.map(s => {
        const color = s.impact_eur >= 0 ? 'var(--positive)' : 'var(--negative)';
        return `<div style="display:flex; justify-content:space-between; gap:8px; align-items:baseline; margin:6px 0; padding:8px 10px; background:rgba(43,40,34,0.03); border-radius:8px; flex-wrap:wrap;">
            <div><strong>${s.name}</strong> <span class="text-muted" style="font-size:12px;">${s.desc}</span>${s.note ? `<br><span class="text-muted" style="font-size:10.5px;">${s.note}</span>` : ''}</div>
            <div style="text-align:right;"><span class="mono" style="color:${color}; font-weight:600;">${fmt(s.impact_eur)} (${s.impact_pct}%)</span><br><span class="text-muted" style="font-size:11px;">quedaría en ${Math.round(s.new_value).toLocaleString('es-ES')} €</span></div>
        </div>`;
    }).join('');
    el.innerHTML = `<p style="font-size:13px; margin:0 0 6px;">Valor actual: <strong>${Math.round(d.total_value).toLocaleString('es-ES')} €</strong></p>${rows}`;
}

async function loadAttribution() {
    const el = document.getElementById('attributionContent');
    if (!el) return;
    let d;
    try {
        const r = await fetch(`${ASSET_API}/portfolio/attribution`);
        if (!r.ok) { el.innerHTML = '<p class="text-muted">No disponible.</p>'; return; }
        d = await r.json();
    } catch (e) { el.innerHTML = '<p class="text-muted">No disponible.</p>'; return; }
    const pos = d.by_position || [];
    if (!pos.length) { el.innerHTML = '<p class="text-muted">Sin posiciones.</p>'; return; }
    const maxAbs = Math.max(...pos.map(p => Math.abs(p.gain_loss_eur)), 1);
    const fmt = (v) => (v >= 0 ? '+' : '') + Math.round(v).toLocaleString('es-ES') + ' €';
    const rows = pos.map(p => {
        const w = Math.round(Math.abs(p.gain_loss_eur) / maxAbs * 100);
        const color = p.gain_loss_eur >= 0 ? 'var(--positive)' : 'var(--negative)';
        return `<div style="display:flex; align-items:center; gap:8px; margin:4px 0; font-size:12.5px;">
            <span style="flex:0 0 140px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${p.name}">${p.name}</span>
            <span style="flex:1; background:rgba(43,40,34,0.05); border-radius:4px; height:14px; position:relative;">
                <span style="position:absolute; left:0; top:0; height:14px; width:${w}%; background:${color}; border-radius:4px;"></span>
            </span>
            <span class="mono" style="flex:0 0 92px; text-align:right; color:${color};">${fmt(p.gain_loss_eur)}</span>
            <span class="mono text-muted" style="flex:0 0 52px; text-align:right;">${p.contribution_pct}%</span>
        </div>`;
    }).join('');
    const tsum = (d.by_type || []).map(t =>
        `${t.type}: <strong style="color:${t.gain_loss_eur >= 0 ? 'var(--positive)' : 'var(--negative)'};">${fmt(t.gain_loss_eur)}</strong>`
    ).join(' · ');
    el.innerHTML = `<p style="font-size:13px; margin:0 0 8px;">P/L total: <strong>${fmt(d.total_gain_loss_eur)}</strong></p>
        ${rows}
        ${tsum ? `<p class="text-muted" style="font-size:11.5px; margin:10px 0 0;">Por tipo: ${tsum}</p>` : ''}
        <p class="text-muted" style="font-size:10.5px; margin:6px 0 0;">El % es la contribución al P/L <em>neto</em> — puede pasar de 100% si hay posiciones que restan.</p>`;
}

async function loadHoldingsCatalysts() {
    const el = document.getElementById('holdingsCatalysts');
    if (!el) return;
    let ev;
    try {
        const r = await fetch(`${ASSET_API}/portfolio/catalysts`);
        if (!r.ok) { el.innerHTML = '<p class="text-muted">No disponible ahora mismo.</p>'; return; }
        ev = (await r.json()).events || [];
    } catch (e) { el.innerHTML = '<p class="text-muted">No disponible ahora mismo.</p>'; return; }
    if (!ev.length) {
        el.innerHTML = '<p class="text-muted">Sin eventos próximos detectados (o tu cartera es de ETFs/fondos, que no publican estas fechas).</p>';
        return;
    }
    const daysTo = (iso) => Math.round((new Date(iso) - new Date()) / 86400000);
    el.innerHTML = `<div class="table-container"><table class="manager-table">
        <thead><tr><th>Activo</th><th>Evento</th><th class="text-right">Fecha</th><th class="text-right">En</th></tr></thead>
        <tbody>${ev.map(e => {
            const dd = daysTo(e.date);
            const soon = e.event === 'Resultados' && dd >= 0 && dd <= 14;
            const icon = e.event === 'Resultados' ? '📊' : '💰';
            return `<tr${soon ? ' style="background:rgba(198,71,60,0.08);"' : ''}>
                <td>${e.name} <span class="text-muted mono" style="font-size:11px;">${e.ticker}</span></td>
                <td>${icon} ${e.event}${soon ? ' ⚠️' : ''}</td>
                <td class="text-right mono">${e.date}</td>
                <td class="text-right mono">${dd}d</td></tr>`;
        }).join('')}</tbody></table></div>`;
}

async function loadAdvancedAnalytics() {
    let history = [];
    try {
        const r = await fetch(`${ASSET_API}/portfolio/history?days=365`);
        if (r.ok) history = (await r.json()).history || [];
    } catch (e) { /* silent: charts show their own "sin datos" state */ }
    renderUnderwater(history);
    renderMonthlyHeatmap(history);
    renderReturnDistribution(history);
    renderRollingChart(history);
}

function renderUnderwater(history) {
    if (!history || history.length < 3) return _noData('underwaterChart', 'Necesita más histórico de cartera.');
    let peak = -Infinity; const labels = [], dd = [];
    for (const h of history) {
        if (h.value == null) continue;
        peak = Math.max(peak, h.value);
        labels.push(h.date);
        dd.push(peak > 0 ? (h.value - peak) / peak * 100 : 0);
    }
    _destroyAdv('underwaterChart');
    _advCharts['underwaterChart'] = new Chart(document.getElementById('underwaterChart').getContext('2d'), {
        type: 'line',
        data: { labels, datasets: [{ data: dd, borderColor: ADV.red, backgroundColor: 'rgba(220,38,38,0.15)', fill: true, pointRadius: 0, borderWidth: 1.5, tension: 0.1 }] },
        options: {
            maintainAspectRatio: false,
            plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => `Drawdown: ${c.parsed.y.toFixed(2)}%` } } },
            scales: {
                x: { title: { display: true, text: 'Fecha', color: ADV.muted, font: { size: 12, weight: '600' } }, ticks: { maxTicksLimit: 6, color: ADV.muted }, grid: { display: false } },
                y: { max: 0, title: { display: true, text: 'Caída desde máximo (%)', color: ADV.muted, font: { size: 12, weight: '600' } }, ticks: { color: ADV.muted, callback: v => v + '%' }, grid: { color: ADV.grid } },
            },
        },
    });
}

function renderRiskReturnScatter(riskByTicker, returnByTicker, weightByTicker) {
    const el = document.getElementById('riskReturnChart');
    if (!el) return;
    const tickers = Object.keys(riskByTicker || {}).filter(t => returnByTicker && returnByTicker[t] != null);
    if (!tickers.length) return _noData('riskReturnChart', 'Necesita histórico de posiciones.');
    const nameOf = (t) => { const info = ASSET_DISPLAY_NAMES[t?.toUpperCase()]; return info ? (info.short || info.name) : t; };
    const maxW = Math.max(...tickers.map(t => (weightByTicker && weightByTicker[t]) || 1), 1);
    const points = tickers.map(t => ({
        x: riskByTicker[t], y: returnByTicker[t],
        r: 5 + 14 * Math.sqrt(((weightByTicker && weightByTicker[t]) || 1) / maxW),
        _t: nameOf(t),
    }));
    const colors = points.map(p => p.y >= 0 ? 'rgba(22,163,74,0.55)' : 'rgba(220,38,38,0.55)');
    _destroyAdv('riskReturnChart');
    _advCharts['riskReturnChart'] = new Chart(el.getContext('2d'), {
        type: 'bubble',
        data: { datasets: [{ data: points, backgroundColor: colors, borderColor: ADV.blue, borderWidth: 1 }] },
        options: {
            maintainAspectRatio: false,
            plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => `${c.raw._t}: vol ${c.raw.x.toFixed(0)}% · ret ${c.raw.y >= 0 ? '+' : ''}${c.raw.y.toFixed(1)}%` } } },
            scales: {
                x: { title: { display: true, text: 'Volatilidad anualizada (%)', color: ADV.muted }, ticks: { color: ADV.muted }, grid: { color: ADV.grid } },
                y: { title: { display: true, text: 'Retorno 3m (%)', color: ADV.muted }, ticks: { color: ADV.muted, callback: v => v + '%' }, grid: { color: ADV.grid } },
            },
        },
    });
}

function renderMonthlyHeatmap(history) {
    const el = document.getElementById('monthlyHeatmap');
    if (!el) return;
    const byMonth = {};
    for (const h of (history || [])) { if (h.value != null) byMonth[h.date.slice(0, 7)] = h.value; }
    const months = Object.keys(byMonth).sort();
    if (months.length < 2) { el.innerHTML = '<p class="text-muted">Necesita al menos 2 meses de histórico.</p>'; return; }
    const ret = {};
    for (let i = 1; i < months.length; i++) {
        const prev = byMonth[months[i - 1]], cur = byMonth[months[i]];
        if (prev > 0) ret[months[i]] = (cur - prev) / prev * 100;
    }
    const years = [...new Set(months.map(m => m.slice(0, 4)))].sort();
    const MN = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
    const color = (v) => v == null ? 'transparent'
        : v >= 0 ? `rgba(22,163,74,${Math.min(Math.abs(v) / 8, 1) * 0.7 + 0.05})`
                 : `rgba(220,38,38,${Math.min(Math.abs(v) / 8, 1) * 0.7 + 0.05})`;
    let html = '<div style="overflow-x:auto"><table class="mheat"><thead><tr><th></th>' + MN.map(m => `<th>${m}</th>`).join('') + '</tr></thead><tbody>';
    for (const y of years) {
        html += `<tr><th>${y}</th>`;
        for (let m = 1; m <= 12; m++) {
            const key = `${y}-${String(m).padStart(2, '0')}`;
            const v = ret[key];
            html += `<td style="background:${color(v)}" title="${key}">${v == null ? '' : (v >= 0 ? '+' : '') + v.toFixed(1)}</td>`;
        }
        html += '</tr>';
    }
    html += '</tbody></table></div>';
    el.innerHTML = html;
}

function renderReturnDistribution(history) {
    const rets = _dailyReturns(history).map(r => r * 100);
    if (rets.length < 10) return _noData('returnDistChart', 'Necesita más histórico diario.');
    const sorted = [...rets].sort((a, b) => a - b);
    const var95 = sorted[Math.floor(0.05 * sorted.length)];
    const min = Math.min(...rets), max = Math.max(...rets);
    const bins = 21, width = (max - min) / bins || 1;
    const counts = new Array(bins).fill(0);
    for (const r of rets) counts[Math.min(bins - 1, Math.floor((r - min) / width))]++;
    const labels = counts.map((_, i) => (min + (i + 0.5) * width).toFixed(1));
    const colors = counts.map((_, i) => (min + (i + 0.5) * width) < var95 ? 'rgba(220,38,38,0.75)' : ADV.blue);
    _destroyAdv('returnDistChart');
    _advCharts['returnDistChart'] = new Chart(document.getElementById('returnDistChart').getContext('2d'), {
        type: 'bar',
        data: { labels, datasets: [{ data: counts, backgroundColor: colors, borderWidth: 0, barPercentage: 1, categoryPercentage: 1 }] },
        options: {
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { title: items => `Retorno diario ~${items[0].label}%`, label: c => `${c.parsed.y} días` } },
                subtitle: { display: true, text: `VaR 95% diario: ${var95.toFixed(2)}%`, color: ADV.red, font: { size: 12, weight: 'bold' } },
            },
            scales: {
                x: { title: { display: true, text: 'Retorno diario (%)', color: ADV.muted, font: { size: 12, weight: '600' } }, ticks: { maxTicksLimit: 7, color: ADV.muted, callback: function (v) { return this.getLabelForValue(v) + '%'; } }, grid: { display: false } },
                y: { title: { display: true, text: 'Frecuencia (nº de días)', color: ADV.muted, font: { size: 12, weight: '600' } }, ticks: { color: ADV.muted }, grid: { color: ADV.grid } },
            },
        },
    });
}

function renderRollingChart(history) {
    const rets = _dailyReturns(history);
    const W = 30;
    if (rets.length < W + 5) return _noData('rollingChart', 'Necesita 35+ días de histórico.');
    const labels = [], vol = [], sharpe = [];
    for (let i = W; i <= rets.length; i++) {
        const win = rets.slice(i - W, i);
        const mean = win.reduce((a, b) => a + b, 0) / W;
        const sd = Math.sqrt(win.reduce((a, b) => a + (b - mean) ** 2, 0) / W);
        labels.push((history[i] && history[i].date) || '');
        vol.push(sd * Math.sqrt(252) * 100);
        sharpe.push(sd > 0 ? (mean / sd) * Math.sqrt(252) : 0);
    }
    _destroyAdv('rollingChart');
    _advCharts['rollingChart'] = new Chart(document.getElementById('rollingChart').getContext('2d'), {
        type: 'line',
        data: {
            labels, datasets: [
                { label: 'Volatilidad anual (%)', data: vol, borderColor: ADV.red, backgroundColor: 'transparent', pointRadius: 0, borderWidth: 1.5, yAxisID: 'y', tension: 0.15 },
                { label: 'Sharpe (30d)', data: sharpe, borderColor: ADV.blue, backgroundColor: 'transparent', pointRadius: 0, borderWidth: 1.5, yAxisID: 'y1', tension: 0.15 },
            ],
        },
        options: {
            maintainAspectRatio: false,
            plugins: { legend: { display: true, labels: { color: ADV.muted, boxWidth: 12, font: { size: 11 } } } },
            scales: {
                x: { title: { display: true, text: 'Fecha', color: ADV.muted, font: { size: 12, weight: '600' } }, ticks: { maxTicksLimit: 6, color: ADV.muted }, grid: { display: false } },
                y: { position: 'left', ticks: { color: ADV.red, callback: v => v + '%' }, grid: { color: ADV.grid }, title: { display: true, text: 'Volatilidad anual (%)', color: ADV.red, font: { size: 12, weight: '600' } } },
                y1: { position: 'right', ticks: { color: ADV.blue }, grid: { display: false }, title: { display: true, text: 'Sharpe (30d)', color: ADV.blue, font: { size: 12, weight: '600' } } },
            },
        },
    });
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Initialize when analysis page is shown
    const analysisLink = document.querySelector('[data-page="analysis"]');
    if (analysisLink) {
        analysisLink.addEventListener('click', () => {
            setTimeout(initAssetAnalysis, 200);
        });
    }
    
    // Also check if we're already on analysis page
    setTimeout(() => {
        const analysisPage = document.getElementById('page-analysis');
        if (analysisPage && analysisPage.classList.contains('active')) {
            initAssetAnalysis();
        }
    }, 500);
});

// Expose functions globally for HTML onclick handlers
window.loadAssetChart = loadAssetChart;
window.selectAsset = selectAsset;
window.showBuyAdvice = showBuyAdvice;
window.showDetailedAnalysis = showDetailedAnalysis;
window.initAssetAnalysis = initAssetAnalysis;

