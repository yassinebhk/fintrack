/**
 * Personal Finance Dashboard v2.0 - Frontend Application
 * Handles data fetching, chart rendering, and UI updates
 */

// Configuration - Auto-detects production vs development
const isProduction = window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1';
const API_BASE_URL = isProduction 
    ? 'https://fintrack-vnvx.onrender.com/api'
    : 'http://localhost:8000/api';

const CONFIG = {
    API_BASE_URL: API_BASE_URL,
    REFRESH_INTERVAL: 60000, // 1 minute
    CHART_COLORS: ['#00d4aa', '#6366f1', '#f59e0b', '#ec4899', '#8b5cf6', '#14b8a6'],
};

console.log('FinTrack API URL:', CONFIG.API_BASE_URL);

// Export for other scripts
window.API_BASE_URL = CONFIG.API_BASE_URL;

// State
let portfolioData = null;
let charts = {
    portfolio: null,
    type: null,
    broker: null,
    currency: null,
    benchmark: null
};
let currentPeriod = 30;
let sortColumn = 'market_value';
let sortDirection = 'desc';

// Diccionario de nombres descriptivos para activos
const ASSET_NAMES = {
    // Cryptos
    'BTC': 'Bitcoin',
    'ETH': 'Ethereum',
    'SOL': 'Solana',
    'DOGE': 'Dogecoin',
    'PEPE': 'Pepe',
    'XRP': 'Ripple',
    'ADA': 'Cardano',
    
    // ETFs Trade Republic (Oro)
    'SGLD.L': 'Oro Físico (WisdomTree)',
    
    // ETFs Trade Republic (MSCI World)
    'LYX0F.DE': 'MSCI World (Amundi)',
    
    // Fondos MyInvestor
    'IE00BYX5NX33': 'Vanguard S&P 500',
    'IE00B4ND3602': 'iShares MSCI World',
    
    // Acciones populares
    'AAPL': 'Apple',
    'MSFT': 'Microsoft',
    'GOOGL': 'Google',
    'NVDA': 'Nvidia',
    'TSLA': 'Tesla',
};

function getAssetName(ticker) {
    return ASSET_NAMES[ticker?.toUpperCase()] || null;
}

function getTickerIcon(ticker, type) {
    const icons = {
        'BTC': '₿', 'ETH': 'Ξ', 'SOL': '◎', 'DOGE': '🐕', 'PEPE': '🐸',
    };
    if (icons[ticker?.toUpperCase()]) return icons[ticker.toUpperCase()];
    if (type === 'crypto') return '🪙';
    if (type === 'etf') return '📊';
    if (type === 'fund') return '📈';
    return ticker?.substring(0, 2).toUpperCase() || '??';
}

// Utility Functions
function formatCurrency(value, currency = 'EUR') {
    return new Intl.NumberFormat('es-ES', {
        style: 'currency',
        currency: currency,
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(value);
}

function formatNumber(value, decimals = 2) {
    return new Intl.NumberFormat('es-ES', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    }).format(value);
}

function formatPercent(value) {
    const sign = value >= 0 ? '+' : '';
    return `${sign}${formatNumber(value)}%`;
}

function formatDate(dateStr) {
    return new Date(dateStr).toLocaleDateString('es-ES', {
        day: '2-digit',
        month: 'short',
        year: 'numeric'
    });
}

function formatTime(dateStr) {
    return new Date(dateStr).toLocaleTimeString('es-ES', {
        hour: '2-digit',
        minute: '2-digit'
    });
}

// API Functions
async function fetchAPI(endpoint) {
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}${endpoint}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error(`API Error (${endpoint}):`, error);
        throw error;
    }
}

async function fetchPortfolio() {
    return fetchAPI('/portfolio');
}

async function fetchHistory(days = 365) {
    return fetchAPI(`/portfolio/history?days=${days}`);
}

async function refreshData() {
    return fetchAPI('/refresh');
}

// UI Update Functions
function updateStatus(online) {
    const dot = document.getElementById('statusDot');
    const text = document.getElementById('statusText');
    
    if (dot && text) {
        if (online) {
            dot.className = 'status-dot online';
            text.textContent = 'Conectado';
        } else {
            dot.className = 'status-dot offline';
            text.textContent = 'Sin conexión';
        }
    }
}

function updateLastUpdate(timestamp) {
    const el = document.getElementById('lastUpdate');
    if (el) {
        el.textContent = formatTime(timestamp);
    }
}

function updateSummary(data) {
    // Total Value
    const totalValueEl = document.getElementById('totalValue');
    if (totalValueEl) {
        totalValueEl.innerHTML = formatCurrency(data.total_value, data.base_currency);
    }
    
    // Base Currency
    const baseCurrencyEl = document.getElementById('baseCurrency');
    if (baseCurrencyEl) {
        baseCurrencyEl.textContent = data.base_currency;
    }
    
    // Daily Change
    const dailyEl = document.getElementById('dailyChange');
    if (dailyEl) {
        const dailyClass = data.daily_change >= 0 ? 'positive' : 'negative';
        dailyEl.className = `change-daily ${dailyClass}`;
        dailyEl.innerHTML = `Hoy: ${formatPercent(data.daily_change_pct)} (${formatCurrency(data.daily_change, data.base_currency)})`;
    }
    
    // Total Gain/Loss
    const totalEl = document.getElementById('totalGainLoss');
    if (totalEl) {
        const totalClass = data.total_gain_loss >= 0 ? 'positive' : 'negative';
        totalEl.className = `change-total ${totalClass}`;
        totalEl.innerHTML = `Total: ${formatPercent(data.total_gain_loss_pct)} (${formatCurrency(data.total_gain_loss, data.base_currency)})`;
    }
    
    // Positions count
    const positionsCountEl = document.getElementById('positionsCount');
    if (positionsCountEl) {
        positionsCountEl.textContent = data.positions?.length || 0;
    }
}

function updateKPIs(kpis) {
    // CAGR
    const cagrEl = document.getElementById('cagr');
    if (cagrEl) {
        cagrEl.textContent = kpis.cagr ? `${formatNumber(kpis.cagr)}%` : 'N/A';
        cagrEl.className = `kpi-value ${kpis.cagr >= 0 ? 'positive' : 'negative'}`;
    }
    
    // Max Drawdown
    const ddEl = document.getElementById('maxDrawdown');
    if (ddEl) {
        ddEl.textContent = kpis.max_drawdown ? `-${formatNumber(kpis.max_drawdown)}%` : 'N/A';
        ddEl.className = 'kpi-value negative';
    }
    
    // Volatility
    const volEl = document.getElementById('volatility');
    if (volEl) {
        volEl.textContent = kpis.volatility ? `${formatNumber(kpis.volatility)}%` : 'N/A';
    }
    
    // Sharpe Ratio
    const sharpeEl = document.getElementById('sharpeRatio');
    if (sharpeEl) {
        sharpeEl.textContent = kpis.sharpe_ratio ? formatNumber(kpis.sharpe_ratio) : 'N/A';
        sharpeEl.className = `kpi-value ${kpis.sharpe_ratio >= 1 ? 'positive' : ''}`;
    }
    
    // Best/Worst day for analysis page
    const bestDayEl = document.getElementById('bestDay');
    if (bestDayEl) {
        bestDayEl.textContent = kpis.best_day ? formatPercent(kpis.best_day) : '+0.00%';
    }
    
    const worstDayEl = document.getElementById('worstDay');
    if (worstDayEl) {
        worstDayEl.textContent = kpis.worst_day ? formatPercent(kpis.worst_day) : '-0.00%';
    }
}

function updateQuickStats(data) {
    if (!data.positions || data.positions.length === 0) return;
    
    // Best performer
    const bestPerformer = data.positions.reduce((best, pos) => 
        pos.gain_loss_pct > (best?.gain_loss_pct || -Infinity) ? pos : best
    , null);
    
    const bestEl = document.getElementById('bestPerformer');
    if (bestEl && bestPerformer) {
        bestEl.innerHTML = `<span style="color: var(--positive)">${bestPerformer.ticker}</span> ${formatPercent(bestPerformer.gain_loss_pct)}`;
    }
    
    // Worst performer
    const worstPerformer = data.positions.reduce((worst, pos) => 
        pos.gain_loss_pct < (worst?.gain_loss_pct || Infinity) ? pos : worst
    , null);
    
    const worstEl = document.getElementById('worstPerformer');
    if (worstEl && worstPerformer) {
        worstEl.innerHTML = `<span style="color: var(--negative)">${worstPerformer.ticker}</span> ${formatPercent(worstPerformer.gain_loss_pct)}`;
    }
}

function updatePositionsTable(positions) {
    const tbody = document.getElementById('positionsBody');
    if (!tbody) return;
    
    if (!positions || positions.length === 0) {
        tbody.innerHTML = '<tr><td colspan="11" class="loading-row">No hay posiciones</td></tr>';
        return;
    }
    
    // Apply filters
    const typeFilter = document.getElementById('filterType')?.value || 'all';
    const brokerFilter = document.getElementById('filterBroker')?.value || 'all';
    const searchTerm = document.getElementById('searchPositions')?.value?.toLowerCase() || '';
    
    let filtered = positions;
    if (typeFilter !== 'all') {
        filtered = filtered.filter(p => p.type === typeFilter);
    }
    if (brokerFilter !== 'all') {
        filtered = filtered.filter(p => p.broker === brokerFilter);
    }
    if (searchTerm) {
        filtered = filtered.filter(p => 
            p.ticker.toLowerCase().includes(searchTerm) ||
            (p.name && p.name.toLowerCase().includes(searchTerm))
        );
    }
    
    // Sort
    filtered.sort((a, b) => {
        let aVal = a[sortColumn];
        let bVal = b[sortColumn];
        
        if (typeof aVal === 'string') {
            aVal = aVal.toLowerCase();
            bVal = bVal.toLowerCase();
        }
        
        if (sortDirection === 'asc') {
            return aVal > bVal ? 1 : -1;
        }
        return aVal < bVal ? 1 : -1;
    });
    
    tbody.innerHTML = filtered.map(pos => {
        const assetName = getAssetName(pos.ticker) || pos.name || pos.ticker;
        const icon = getTickerIcon(pos.ticker, pos.type);
        const typeName = {'crypto': 'Crypto', 'etf': 'ETF', 'fund': 'Fondo', 'stock': 'Acción'}[pos.type] || pos.type;
        
        return `
        <tr>
            <td>
                <div class="ticker-cell">
                    <div class="ticker-icon">${icon}</div>
                    <div class="ticker-info">
                        <span class="ticker-symbol">${pos.ticker}</span>
                        <span class="ticker-name">${assetName}</span>
                    </div>
                </div>
            </td>
            <td><span class="type-badge ${pos.type}">${typeName}</span></td>
            <td><span class="broker-name">${pos.broker}</span></td>
            <td class="text-right mono">${formatNumber(pos.quantity, pos.type === 'crypto' ? 6 : 2)}</td>
            <td class="text-right mono">${formatNumber(pos.avg_price)}</td>
            <td class="text-right mono">${formatNumber(pos.current_price)}</td>
            <td class="text-right mono">${formatCurrency(pos.market_value, pos.currency)}</td>
            <td class="text-right mono ${pos.gain_loss >= 0 ? 'value-positive' : 'value-negative'}">
                ${formatCurrency(pos.gain_loss, pos.currency)}
            </td>
            <td class="text-right mono ${pos.gain_loss_pct >= 0 ? 'value-positive' : 'value-negative'}">
                ${formatPercent(pos.gain_loss_pct)}
            </td>
            <td class="text-right mono ${pos.day_change_pct >= 0 ? 'value-positive' : 'value-negative'}">
                ${formatPercent(pos.day_change_pct)}
            </td>
            <td class="text-right mono">${formatNumber(pos.weight)}%</td>
        </tr>
    `}).join('');
}

function updateBrokerFilter(brokers) {
    const select = document.getElementById('filterBroker');
    if (!select) return;
    
    const currentValue = select.value;
    
    select.innerHTML = '<option value="all">Todos los brokers</option>' +
        Object.keys(brokers).map(broker => 
            `<option value="${broker}">${broker}</option>`
        ).join('');
    
    select.value = currentValue;
}

function updateTopMovers(positions) {
    const container = document.getElementById('topMovers');
    if (!container || !positions) return;
    
    const sorted = [...positions].sort((a, b) => Math.abs(b.day_change_pct) - Math.abs(a.day_change_pct));
    const topMovers = sorted.slice(0, 5);
    
    container.innerHTML = topMovers.map(pos => `
        <div class="mover-item" style="display: flex; justify-content: space-between; padding: 10px; background: var(--bg-tertiary); border-radius: 8px; margin-bottom: 8px;">
            <span style="font-family: var(--font-mono); font-weight: 600;">${pos.ticker}</span>
            <span class="${pos.day_change_pct >= 0 ? 'value-positive' : 'value-negative'}" style="font-family: var(--font-mono);">
                ${formatPercent(pos.day_change_pct)}
            </span>
        </div>
    `).join('');
}

// Chart Functions
function createPortfolioChart(history) {
    const ctx = document.getElementById('portfolioChart');
    if (!ctx) return;
    
    if (charts.portfolio && typeof charts.portfolio.destroy === 'function') {
        charts.portfolio.destroy();
    }
    
    // Filter by period
    let filteredHistory = history;
    if (currentPeriod !== 'all') {
        const cutoff = new Date();
        cutoff.setDate(cutoff.getDate() - currentPeriod);
        filteredHistory = history.filter(h => new Date(h.date) >= cutoff);
    }
    
    const labels = filteredHistory.map(h => h.date);
    const values = filteredHistory.map(h => h.value);
    
    // Calculate gradient
    const gradient = ctx.getContext('2d').createLinearGradient(0, 0, 0, 350);
    gradient.addColorStop(0, 'rgba(0, 212, 170, 0.3)');
    gradient.addColorStop(1, 'rgba(0, 212, 170, 0)');
    
    charts.portfolio = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Valor de Cartera',
                data: values,
                borderColor: '#00d4aa',
                backgroundColor: gradient,
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 6,
                pointHoverBackgroundColor: '#00d4aa',
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
                            return formatDate(context[0].label);
                        },
                        label: function(context) {
                            return formatCurrency(context.raw, 'EUR');
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        color: '#64748b',
                        maxTicksLimit: 8,
                        callback: function(value, index) {
                            const date = new Date(this.getLabelForValue(value));
                            return date.toLocaleDateString('es-ES', { month: 'short', day: 'numeric' });
                        }
                    }
                },
                y: {
                    grid: {
                        color: '#1e293b'
                    },
                    ticks: {
                        color: '#64748b',
                        callback: function(value) {
                            return formatCurrency(value, 'EUR');
                        }
                    }
                }
            }
        }
    });
}

function createDoughnutChart(canvasId, data, legendId) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    
    const chartKey = canvasId.replace('Chart', '');
    if (charts[chartKey] && typeof charts[chartKey].destroy === 'function') {
        charts[chartKey].destroy();
    }
    
    const labels = Object.keys(data);
    const values = labels.map(k => data[k].value || data[k].weight);
    const weights = labels.map(k => data[k].weight);
    
    const chart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: CONFIG.CHART_COLORS.slice(0, labels.length),
                borderColor: '#151d2c',
                borderWidth: 3,
                hoverBorderColor: '#1a253a',
                hoverBorderWidth: 3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '70%',
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
                    callbacks: {
                        label: function(context) {
                            const weight = weights[context.dataIndex];
                            return `${weight}%`;
                        }
                    }
                }
            }
        }
    });
    
    charts[chartKey] = chart;
    
    // Update legend
    const legendEl = document.getElementById(legendId);
    if (legendEl) {
        legendEl.innerHTML = labels.map((label, i) => `
            <div class="legend-item">
                <span class="legend-color" style="background: ${CONFIG.CHART_COLORS[i]}"></span>
                <span class="legend-label">${label}</span>
                <span class="legend-value">${formatNumber(weights[i])}%</span>
            </div>
        `).join('');
    }
}

// Export to CSV
function exportToCSV() {
    if (!portfolioData || !portfolioData.positions) return;
    
    const headers = ['Ticker', 'Nombre', 'Tipo', 'Broker', 'Cantidad', 'Precio Medio', 'Precio Actual', 'Valor', 'P/L', 'P/L %', 'Peso %'];
    const rows = portfolioData.positions.map(p => [
        p.ticker,
        p.name,
        p.type,
        p.broker,
        p.quantity,
        p.avg_price,
        p.current_price,
        p.market_value,
        p.gain_loss,
        p.gain_loss_pct,
        p.weight
    ]);
    
    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    
    const link = document.createElement('a');
    link.href = url;
    link.download = `portfolio_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
    
    URL.revokeObjectURL(url);
    
    if (window.showToast) {
        window.showToast('CSV exportado correctamente', 'success');
    }
}

// Main Functions
async function loadDashboard() {
    try {
        updateStatus(false);
        
        // Fetch portfolio data
        portfolioData = await fetchPortfolio();
        
        // Update UI
        updateSummary(portfolioData);
        updateKPIs(portfolioData.kpis);
        updateQuickStats(portfolioData);
        updatePositionsTable(portfolioData.positions);
        updateBrokerFilter(portfolioData.by_broker);
        updateLastUpdate(portfolioData.last_updated);
        updateTopMovers(portfolioData.positions);
        
        // Create distribution charts
        if (portfolioData.by_type && Object.keys(portfolioData.by_type).length > 0) {
            createDoughnutChart('typeChart', portfolioData.by_type, 'typeLegend');
        }
        if (portfolioData.by_broker && Object.keys(portfolioData.by_broker).length > 0) {
            createDoughnutChart('brokerChart', portfolioData.by_broker, 'brokerLegend');
        }
        if (portfolioData.by_currency && Object.keys(portfolioData.by_currency).length > 0) {
            createDoughnutChart('currencyChart', portfolioData.by_currency, 'currencyLegend');
        }
        
        // Fetch and create history chart
        const historyData = await fetchHistory(365);
        if (historyData.history && historyData.history.length > 0) {
            createPortfolioChart(historyData.history);
        }
        
        updateStatus(true);
        
    } catch (error) {
        console.error('Error loading dashboard:', error);
        updateStatus(false);
        
        // Show error state
        const totalValueEl = document.getElementById('totalValue');
        if (totalValueEl) {
            totalValueEl.innerHTML = '<span class="value-loading">Error al cargar datos</span>';
        }
    }
}

async function handleRefresh() {
    const btn = document.getElementById('btnRefresh');
    const overlay = document.getElementById('loadingOverlay');
    
    if (btn) btn.classList.add('loading');
    if (overlay) overlay.classList.add('active');
    
    try {
        await refreshData();
        await loadDashboard();
        if (window.showToast) {
            window.showToast('Datos actualizados correctamente', 'success');
        }
    } catch (error) {
        console.error('Error refreshing:', error);
        if (window.showToast) {
            window.showToast('Error al actualizar datos', 'error');
        }
    } finally {
        if (btn) btn.classList.remove('loading');
        if (overlay) overlay.classList.remove('active');
    }
}

function handlePeriodChange(period) {
    currentPeriod = period === 'all' ? 'all' : parseInt(period);
    
    // Update active button
    document.querySelectorAll('.chart-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.period === String(period));
    });
    
    // Reload history chart
    if (portfolioData) {
        fetchHistory(period === 'all' ? 3650 : 365).then(data => {
            if (data.history) {
                createPortfolioChart(data.history);
            }
        });
    }
}

function handleFilterChange() {
    if (portfolioData) {
        updatePositionsTable(portfolioData.positions);
    }
}

function handleSort(column) {
    if (sortColumn === column) {
        sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
        sortColumn = column;
        sortDirection = 'desc';
    }
    
    if (portfolioData) {
        updatePositionsTable(portfolioData.positions);
    }
}

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    // Initial load
    loadDashboard();
    
    // Refresh button
    const btnRefresh = document.getElementById('btnRefresh');
    if (btnRefresh) {
        btnRefresh.addEventListener('click', handleRefresh);
    }
    
    // Period buttons
    document.querySelectorAll('.chart-btn').forEach(btn => {
        btn.addEventListener('click', () => handlePeriodChange(btn.dataset.period));
    });
    
    // Filters
    const filterType = document.getElementById('filterType');
    const filterBroker = document.getElementById('filterBroker');
    const searchPositions = document.getElementById('searchPositions');
    
    if (filterType) filterType.addEventListener('change', handleFilterChange);
    if (filterBroker) filterBroker.addEventListener('change', handleFilterChange);
    if (searchPositions) searchPositions.addEventListener('input', handleFilterChange);
    
    // Table sorting
    document.querySelectorAll('.positions-table th[data-sort]').forEach(th => {
        th.addEventListener('click', () => handleSort(th.dataset.sort));
    });
    
    // Export CSV
    const btnExport = document.getElementById('btnExportCSV');
    if (btnExport) {
        btnExport.addEventListener('click', exportToCSV);
    }
    
    // Auto-refresh every minute
    setInterval(loadDashboard, CONFIG.REFRESH_INTERVAL);
});

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Press 'R' to refresh
    if ((e.key === 'r' || e.key === 'R') && !e.ctrlKey && !e.metaKey) {
        const activeElement = document.activeElement;
        if (activeElement.tagName !== 'INPUT' && activeElement.tagName !== 'TEXTAREA') {
            handleRefresh();
        }
    }
});
