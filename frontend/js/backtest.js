/**
 * Backtest Lab - run predefined strategies against historical prices.
 */

const BT_API = (window.API_BASE_URL || 'http://localhost:8000/api');
let btChart = null;
let btStrategies = [];
let btPortfolioTickers = [];

async function initBacktest() {
    // Strategies
    try {
        const stratResp = await fetch(`${BT_API}/backtest/strategies`);
        const stratData = await stratResp.json();
        btStrategies = stratData.strategies || [];
        const sel = document.getElementById('btStrategy');
        sel.innerHTML = btStrategies.map(s => `<option value="${s.key}">${s.name}</option>`).join('');
        sel.onchange = renderBtParams;
        renderBtParams();
    } catch (err) {
        console.error('Could not load strategies:', err);
    }

    // Tickers from user's portfolio
    try {
        const posResp = await fetch(`${BT_API}/positions`);
        const positions = await posResp.json();
        btPortfolioTickers = positions.map(p => ({
            ticker: p.ticker,
            type: p.type,
            broker: p.broker,
            asset_name: p.asset_name || p.ticker,
        }));
        renderBtTickers();
    } catch (err) {
        console.error('Could not load portfolio tickers:', err);
    }

    // Period toggle
    document.getElementById('btPeriod').onchange = (e) => {
        document.getElementById('btCustomDates').style.display = e.target.value === 'custom' ? 'flex' : 'none';
    };
}

function renderBtParams() {
    const sel = document.getElementById('btStrategy');
    const desc = document.getElementById('btStrategyDesc');
    const paramsContainer = document.getElementById('btParams');
    const strat = btStrategies.find(s => s.key === sel.value);
    if (!strat) {
        desc.textContent = '';
        paramsContainer.innerHTML = '';
        return;
    }
    desc.textContent = strat.description;

    const specs = strat.param_specs || {};
    const html = Object.entries(specs).map(([key, spec]) => {
        const step = spec.type === 'integer' ? 1 : 0.01;
        const min = spec.min ?? '';
        const max = spec.max ?? '';
        const def = spec.default ?? '';
        return `
            <div class="form-group">
                <label>${key}</label>
                <input type="number" id="btParam_${key}" value="${def}" step="${step}" min="${min}" max="${max}">
                ${spec.description ? `<small class="text-muted">${spec.description}</small>` : ''}
            </div>
        `;
    }).join('');
    paramsContainer.innerHTML = html;
}

function renderBtTickers() {
    const container = document.getElementById('btTickerList');
    if (!container) return;
    if (btPortfolioTickers.length === 0) {
        container.innerHTML = '<span class="text-muted">No hay activos en cartera. Añade alguno primero.</span>';
        return;
    }
    container.innerHTML = btPortfolioTickers.map(t => `
        <label class="ticker-chip" style="display:inline-flex; align-items:center; gap:6px; padding:6px 12px; background:var(--bg-tertiary); border-radius:20px; cursor:pointer;">
            <input type="checkbox" data-ticker="${t.ticker}" data-type="${t.type}" checked style="margin:0;">
            <span style="font-family: var(--font-mono); font-size:13px;">${t.ticker}</span>
            <span class="text-muted" style="font-size:11px;">${t.type}</span>
        </label>
    `).join('');
}

function getBtConfig() {
    const strategyKey = document.getElementById('btStrategy').value;
    const period = document.getElementById('btPeriod').value;

    let startDate, endDate = null;
    if (period === 'custom') {
        startDate = document.getElementById('btStartDate').value;
        endDate = document.getElementById('btEndDate').value || null;
        if (!startDate) throw new Error('Selecciona una fecha de inicio');
    } else {
        const years = { '1y': 1, '3y': 3, '5y': 5 }[period] || 3;
        const d = new Date();
        d.setFullYear(d.getFullYear() - years);
        startDate = d.toISOString().split('T')[0];
    }

    const tickerCheckboxes = document.querySelectorAll('#btTickerList input[type=checkbox]:checked');
    const tickers = Array.from(tickerCheckboxes).map(cb => cb.dataset.ticker);
    const asset_types = {};
    tickerCheckboxes.forEach(cb => { asset_types[cb.dataset.ticker] = cb.dataset.type; });

    if (tickers.length === 0) throw new Error('Selecciona al menos 1 activo');

    const params = {};
    document.querySelectorAll('[id^="btParam_"]').forEach(input => {
        const key = input.id.replace('btParam_', '');
        const v = input.value;
        params[key] = isNaN(Number(v)) ? v : Number(v);
    });

    return { strategy: strategyKey, tickers, asset_types, start_date: startDate, end_date: endDate, params };
}

async function runBacktest() {
    const btn = document.getElementById('btRunBtn');
    const loading = document.getElementById('btLoading');
    const results = document.getElementById('btResults');

    let config;
    try {
        config = getBtConfig();
    } catch (err) {
        alert(err.message);
        return;
    }

    btn.disabled = true;
    loading.style.display = 'block';
    results.style.display = 'none';

    try {
        const resp = await fetch(`${BT_API}/backtest/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);

        renderBtResults(data);
    } catch (err) {
        alert('Error en backtest: ' + err.message);
    } finally {
        btn.disabled = false;
        loading.style.display = 'none';
    }
}

function renderBtResults(data) {
    const m = data.metrics || {};
    const fmt = (v, sign = false) => {
        if (v === undefined || v === null) return '—';
        const s = sign && v > 0 ? '+' : '';
        return `${s}${Number(v).toLocaleString('es-ES', { maximumFractionDigits: 2 })}`;
    };

    document.getElementById('btMetrics').innerHTML = `
        <div class="kpi-item">
            <span class="kpi-label">💰 Valor final</span>
            <span class="kpi-value">${fmt(m.final_value_eur)} €</span>
            <span class="kpi-help">Sobre ${fmt(m.net_invested_eur)} € invertidos</span>
        </div>
        <div class="kpi-item">
            <span class="kpi-label">📈 Return total</span>
            <span class="kpi-value ${m.total_return_pct >= 0 ? 'positive' : 'negative'}">${fmt(m.total_return_pct, true)}%</span>
            <span class="kpi-help">CAGR ${fmt(m.cagr_pct, true)}%</span>
        </div>
        <div class="kpi-item">
            <span class="kpi-label">⚖️ Sharpe</span>
            <span class="kpi-value ${m.sharpe_ratio >= 1 ? 'positive' : ''}">${fmt(m.sharpe_ratio)}</span>
            <span class="kpi-help">Vol ${fmt(m.volatility_pct)}%</span>
        </div>
        <div class="kpi-item">
            <span class="kpi-label">📉 Max DD</span>
            <span class="kpi-value negative">${fmt(m.max_drawdown_pct)}%</span>
            <span class="kpi-help">${m.n_trades || 0} trades en ${fmt(m.years_covered)}y</span>
        </div>
    `;

    const ctx = document.getElementById('btChart');
    if (btChart) btChart.destroy();
    btChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.equity_curve.map(p => p.date),
            datasets: [{
                label: 'Equity (€)',
                data: data.equity_curve.map(p => p.value),
                borderColor: '#00d4aa',
                backgroundColor: 'rgba(0, 212, 170, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.2,
                pointRadius: 0,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { maxTicksLimit: 8, color: '#64748b' }, grid: { display: false } },
                y: { ticks: { color: '#64748b', callback: v => v.toLocaleString('es-ES') + ' €' }, grid: { color: '#1e293b' } },
            },
        },
    });

    const tbody = document.getElementById('btTradesBody');
    tbody.innerHTML = data.trades.slice(0, 50).map(t => `
        <tr>
            <td>${t.date}</td>
            <td><span class="type-badge ${t.action}">${t.action}</span></td>
            <td>${getAssetName(t.ticker) || `<code>${t.ticker}</code>`}${getAssetName(t.ticker) ? ` <code class="text-muted" style="font-size:12px;">${t.ticker}</code>` : ''}</td>
            <td class="text-right mono">${Number(t.amount_eur).toLocaleString('es-ES', { maximumFractionDigits: 2 })}</td>
            <td class="text-right mono">${Number(t.price).toLocaleString('es-ES', { maximumFractionDigits: 4 })}</td>
            <td class="text-right mono">${Number(t.shares).toLocaleString('es-ES', { maximumFractionDigits: 8 })}</td>
        </tr>
    `).join('');

    document.getElementById('btResults').style.display = 'block';
}

document.addEventListener('DOMContentLoaded', () => {
    // Init when the Backtest tab is clicked for the first time
    const nav = document.querySelector('[data-page="backtest"]');
    if (nav) {
        nav.addEventListener('click', () => {
            if (!nav.dataset.btInit) {
                initBacktest();
                nav.dataset.btInit = '1';
            }
        }, { once: false });
    }
});
