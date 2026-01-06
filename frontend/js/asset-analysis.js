/**
 * Asset Analysis - Individual asset charts and analysis
 */

// Use the global API_BASE_URL from app.js (loaded first)
const ASSET_API = window.API_BASE_URL || CONFIG?.API_BASE_URL || 'http://localhost:8000/api';
let assetChart = null;
let currentAssetPeriod = '3mo';
let currentAssetData = null;

// Asset name mapping
const ASSET_DISPLAY_NAMES = {
    'BTC': { name: 'Bitcoin', icon: '₿', color: '#f7931a' },
    'ETH': { name: 'Ethereum', icon: 'Ξ', color: '#627eea' },
    'SOL': { name: 'Solana', icon: '◎', color: '#00ffa3' },
    'DOGE': { name: 'Dogecoin', icon: '🐕', color: '#c3a634' },
    'PEPE': { name: 'Pepe', icon: '🐸', color: '#4caf50' },
    'SGLD.L': { name: 'Oro Físico (WisdomTree)', icon: '🥇', color: '#ffd700' },
    'LYX0F.DE': { name: 'MSCI World (Amundi)', icon: '🌍', color: '#2196f3' },
    'IE00BYX5NX33': { name: 'Vanguard S&P 500', icon: '🇺🇸', color: '#1976d2' },
};

/**
 * Initialize asset analysis when page loads
 */
function initAssetAnalysis() {
    loadAssetSelector();
    setupPeriodButtons();
    loadAssetQuickCards();
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
        showChartError(error.message);
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
function renderAssetChart(data) {
    const canvas = document.getElementById('assetHistoryChart');
    const placeholder = document.querySelector('.chart-placeholder');
    
    if (placeholder) placeholder.style.display = 'none';
    canvas.style.display = 'block';
    
    // Destroy existing chart
    if (assetChart) {
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

function showChartError(message) {
    const placeholder = document.querySelector('.chart-placeholder');
    if (placeholder) {
        placeholder.innerHTML = `<span class="placeholder-icon">❌</span><p>Error: ${message}</p>`;
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

