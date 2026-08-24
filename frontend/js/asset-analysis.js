/**
 * Asset Analysis - Individual asset charts and analysis
 */

// Use the global API_BASE_URL from app.js (loaded first)
const ASSET_API = window.API_BASE_URL || CONFIG?.API_BASE_URL || 'http://localhost:8000/api';
let assetChart = null;
let currentAssetPeriod = '3mo';
let currentAssetData = null;

// Asset name mapping — verified 2026-08 against the real Trade Republic /
// MyInvestor transaction history (do not "correct" without re-checking a CSV
// export; LYX0F.DE and IE00BYX5NX33 were previously swapped here for months).
const ASSET_DISPLAY_NAMES = {
    'BTC': { name: 'Bitcoin', icon: '₿', color: '#f7931a' },
    'ETH': { name: 'Ethereum', icon: 'Ξ', color: '#627eea' },
    'SOL': { name: 'Solana', icon: '◎', color: '#00ffa3' },
    'DOGE': { name: 'Dogecoin', icon: '🐕', color: '#c3a634' },
    'PEPE': { name: 'Pepe', icon: '🐸', color: '#4caf50' },
    'IE00BYX5NX33': { name: 'Fidelity MSCI World P-Acc', icon: '🌍', color: '#2196f3' },
    'IE00B4ND3602': { name: 'iShares Physical Gold ETC', icon: '🥇', color: '#ffd700' },
    'LYX0F.DE': { name: 'Amundi Nasdaq-100', icon: '📈', color: '#1976d2' },
    'VVSM.DE': { name: 'VanEck Semiconductor', icon: '💾', color: '#9c27b0' },
    'QDVF.DE': { name: 'iShares S&P500 Energy', icon: '⚡', color: '#ff9800' },
    'NUKL.DE': { name: 'VanEck Uranium & Nuclear', icon: '☢️', color: '#8bc34a' },
    'BTEC.L': { name: 'iShares Nasdaq Biotech', icon: '🧬', color: '#00bcd4' },
    'COPX.L': { name: 'Global X Copper Miners', icon: '🔶', color: '#b87333' },
    'JEDI.DE': { name: 'VanEck Space Innovators', icon: '🚀', color: '#673ab7' },
    'PLTR': { name: 'Palantir Technologies', icon: '🔮', color: '#000000' },
    'SPCX': { name: 'SpaceX', icon: '🛰️', color: '#005288' },
    'USPY.DE': { name: 'L&G Cyber Security', icon: '🔐', color: '#607d8b' },
    'IEAA.L': { name: 'iShares Core € Corp Bond', icon: '🏦', color: '#795548' },
};

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
            option.textContent = `${pos.ticker} - ${displayName}`;
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
    
    const assetInfo = ASSET_DISPLAY_NAMES[ticker] || { name: ticker, icon: '📊', color: '#00d4aa' };
    
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
            textColor: '#94a3b8',
        },
        grid: {
            vertLines: { color: 'rgba(30, 41, 59, 0.5)' },
            horzLines: { color: 'rgba(30, 41, 59, 0.5)' },
        },
        rightPriceScale: { borderColor: '#334155' },
        timeScale: { borderColor: '#334155', timeVisible: false },
        crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    });
    tvChart = chart;

    const history = data.history || [];
    const hasOHLC = history.length > 0 && history[0].open !== undefined && history[0].high !== undefined;

    if (currentChartType === 'candles' && hasOHLC) {
        const series = chart.addCandlestickSeries({
            upColor: '#00d4aa', downColor: '#ef4444',
            borderUpColor: '#00d4aa', borderDownColor: '#ef4444',
            wickUpColor: '#00d4aa', wickDownColor: '#ef4444',
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
        const color = up ? '#00d4aa' : '#ef4444';
        const series = chart.addAreaSeries({
            lineColor: color,
            topColor: up ? 'rgba(0,212,170,0.4)' : 'rgba(239,68,68,0.4)',
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
    const assetInfo = ASSET_DISPLAY_NAMES[data.ticker] || { color: '#00d4aa' };
    
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
    const lineColor = lastPrice >= firstPrice ? '#00d4aa' : '#ef4444';
    
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
                    backgroundColor: '#1a2332',
                    titleColor: '#94a3b8',
                    bodyColor: '#f8fafc',
                    borderColor: '#334155',
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
                    grid: { display: false },
                    ticks: {
                        color: '#64748b',
                        maxTicksLimit: 8,
                        callback: function(value, index) {
                            const date = this.getLabelForValue(value);
                            return new Date(date).toLocaleDateString('es-ES', { day: '2-digit', month: 'short' });
                        }
                    }
                },
                y: {
                    grid: { color: '#1e293b' },
                    ticks: {
                        color: '#64748b',
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
            const info = ASSET_DISPLAY_NAMES[pos.ticker] || { name: pos.ticker, icon: '📊', color: '#00d4aa' };
            const changeClass = pos.day_change_pct >= 0 ? 'positive' : 'negative';
            const changeSign = pos.day_change_pct >= 0 ? '+' : '';
            
            return `
                <div class="asset-quick-card" onclick="selectAsset('${pos.ticker}')" style="--accent-color: ${info.color}">
                    <div class="quick-card-header">
                        <span class="quick-card-icon">${info.icon}</span>
                        <span class="quick-card-ticker">${pos.ticker}</span>
                    </div>
                    <div class="quick-card-name">${info.name}</div>
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
    // Navigate to AI advisor with context
    if (currentAssetData) {
        const ticker = currentAssetData.ticker;
        // Could open AI advisor with pre-filled question
        alert(`Para un análisis detallado de ${ticker}, ve a la sección "Asesor IA" y pregunta sobre este activo.`);
    }
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
                    { label: 'Tu cartera', data: portfolioPct, borderColor: '#00d4aa', backgroundColor: 'transparent', tension: 0.2, pointRadius: 0, borderWidth: 2 },
                    { label: 'S&P 500', data: spyPct, borderColor: '#94a3b8', backgroundColor: 'transparent', tension: 0.2, pointRadius: 0, borderWidth: 2, borderDash: [4, 4] },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: true, labels: { color: '#94a3b8', boxWidth: 12 } } },
                scales: {
                    x: { display: false },
                    y: { ticks: { color: '#94a3b8', callback: v => `${v.toFixed(0)}%` }, grid: { color: 'rgba(148,163,184,0.1)' } },
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
        ? `rgba(0, 212, 170, ${Math.min(Math.abs(v), 1) * 0.6})`
        : `rgba(239, 68, 68, ${Math.min(Math.abs(v), 1) * 0.6})`;

    let html = '<div style="overflow-x:auto"><table class="correlation-table"><thead><tr><th></th>';
    for (let j = 0; j < N; j++) html += `<th>${tickers[j]}</th>`;
    html += '</tr></thead><tbody>';
    for (let i = 0; i < N; i++) {
        html += `<tr><th>${tickers[i]}</th>`;
        for (let j = 0; j < N; j++) {
            const v = matrix[i]?.[j];
            const label = v != null ? v.toFixed(2) : '-';
            html += `<td style="background:${v != null ? colorFor(v) : 'transparent'}" title="${tickers[i]} vs ${tickers[j]}">${label}</td>`;
        }
        html += '</tr>';
    }
    html += '</tbody></table></div>';
    container.innerHTML = html;
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

