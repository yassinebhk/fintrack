/**
 * Asset Detail — dedicated per-asset page reached by clicking a position
 * anywhere in the app. Shows market price, the user's OWN position value over
 * time (distinct from raw market price — reflects when they actually bought),
 * and their contributions/transactions for that one ticker.
 */
const ASSET_DETAIL_API = window.API_BASE_URL || 'http://localhost:8000/api';
let assetDetailTvChart = null;
let assetDetailPositionChart = null;
let currentAssetDetailTicker = null;

function showAssetDetail(ticker) {
    if (!ticker) return;
    currentAssetDetailTicker = ticker.toUpperCase();

    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    const page = document.getElementById('page-asset-detail');
    if (page) page.classList.add('active');

    const info = ASSET_DISPLAY_NAMES[currentAssetDetailTicker];
    const titleEl = document.getElementById('pageTitle');
    if (titleEl) titleEl.textContent = info ? info.name : currentAssetDetailTicker;

    try { history.replaceState(null, '', '#asset/' + currentAssetDetailTicker); } catch (e) { /* noop */ }

    loadAssetDetailHeader(currentAssetDetailTicker);
    loadAssetDetailMarketChart(currentAssetDetailTicker);
    loadAssetDetailPositionChart(currentAssetDetailTicker);
    loadAssetDetailTransactions(currentAssetDetailTicker);

    if (window.innerWidth <= 900) {
        document.querySelector('.sidebar')?.classList.remove('open');
    }
}

async function loadAssetDetailHeader(ticker) {
    const info = ASSET_DISPLAY_NAMES[ticker] || { name: ticker, icon: '📊', color: '#00d4aa' };
    document.getElementById('assetDetailIcon').textContent = info.icon;
    document.getElementById('assetDetailIcon').style.background = `linear-gradient(135deg, ${info.color}33, ${info.color}11)`;
    document.getElementById('assetDetailIcon').style.color = info.color;
    document.getElementById('assetDetailName').textContent = info.name;
    document.getElementById('assetDetailTicker').textContent = ticker;
    document.getElementById('assetDetailPageTitle').textContent = `📊 ${info.name}`;
    document.getElementById('assetDetailDeepBtn').onclick = () => openDeepAnalysis(ticker, info.name);

    const aboutSection = document.getElementById('assetDetailAboutSection');
    const aboutEl = document.getElementById('assetDetailAbout');
    if (info.about) {
        aboutEl.textContent = info.about;
        aboutSection.style.display = '';
    } else {
        aboutSection.style.display = 'none';
    }

    try {
        const resp = await fetch(`${ASSET_DETAIL_API}/portfolio`);
        const portfolio = await resp.json();
        const position = portfolio.positions?.find(p => p.ticker === ticker);

        if (position) {
            document.getElementById('assetDetailPrice').textContent = formatCurrency(position.current_price);
            const changeEl = document.getElementById('assetDetailChange');
            const chg = position.day_change_pct || 0;
            changeEl.textContent = `${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%`;
            changeEl.className = `price-change ${chg >= 0 ? 'positive' : 'negative'}`;
            document.getElementById('assetDetailQty').textContent =
                `${position.quantity.toFixed(position.type === 'crypto' ? 6 : 4)} unidades`;
            document.getElementById('assetDetailValue').textContent = formatCurrency(position.market_value);
            const glEl = document.getElementById('assetDetailGainLoss');
            glEl.textContent = `${position.gain_loss >= 0 ? '+' : ''}${formatCurrency(position.gain_loss)} (${position.gain_loss_pct.toFixed(2)}%)`;
            glEl.className = `stat-value ${position.gain_loss >= 0 ? 'positive' : 'negative'}`;
            document.getElementById('assetDetailWeight').textContent = `${position.weight.toFixed(1)}%`;
        } else {
            // Position fully exited (or never held under this exact ticker) — still
            // show market data above, just no live P/L to report.
            ['assetDetailPrice', 'assetDetailQty', 'assetDetailValue', 'assetDetailGainLoss', 'assetDetailWeight'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.textContent = '—';
            });
            document.getElementById('assetDetailChange').textContent = '';
        }
    } catch (err) {
        console.error('asset detail header failed:', err);
    }
}

function renderAssetDetailMarketSeries(chart, history) {
    const hasOHLC = history.length > 0 && history[0].open !== undefined && history[0].high !== undefined;
    if (hasOHLC) {
        const series = chart.addCandlestickSeries({
            upColor: '#00d4aa', downColor: '#ef4444',
            borderUpColor: '#00d4aa', borderDownColor: '#ef4444',
            wickUpColor: '#00d4aa', wickDownColor: '#ef4444',
        });
        series.setData(history.map(h => ({ time: h.date, open: h.open, high: h.high, low: h.low, close: h.close })));
    } else {
        const firstPrice = history[0]?.close ?? history[0]?.price ?? 0;
        const lastPrice = history[history.length - 1]?.close ?? history[history.length - 1]?.price ?? 0;
        const up = lastPrice >= firstPrice;
        const series = chart.addAreaSeries({
            lineColor: up ? '#00d4aa' : '#ef4444',
            topColor: up ? 'rgba(0,212,170,0.4)' : 'rgba(239,68,68,0.4)',
            bottomColor: 'rgba(0,0,0,0)',
            lineWidth: 2,
        });
        series.setData(history.map(h => ({ time: h.date, value: h.close ?? h.price })));
    }
}

async function loadAssetDetailMarketChart(ticker) {
    const container = document.getElementById('assetDetailTvContainer');
    if (!container || typeof LightweightCharts === 'undefined') return;
    try {
        const resp = await fetch(`${ASSET_DETAIL_API}/asset/${ticker}/history?period=1y&asset_type=auto`);
        const data = await resp.json();
        const history = data.history || [];
        if (!history.length) return;

        if (assetDetailTvChart) {
            try { assetDetailTvChart.remove(); } catch (e) { /* noop */ }
            assetDetailTvChart = null;
        }
        container.innerHTML = '';

        const chart = LightweightCharts.createChart(container, {
            width: container.clientWidth,
            height: 400,
            layout: { background: { color: 'transparent' }, textColor: '#94a3b8' },
            grid: { vertLines: { color: 'rgba(30,41,59,0.5)' }, horzLines: { color: 'rgba(30,41,59,0.5)' } },
            rightPriceScale: { borderColor: '#334155' },
            timeScale: { borderColor: '#334155' },
            crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
        });
        assetDetailTvChart = chart;
        renderAssetDetailMarketSeries(chart, history);
        chart.timeScale().fitContent();

        if (!container._resizeHandler) {
            container._resizeHandler = () => {
                if (assetDetailTvChart) assetDetailTvChart.applyOptions({ width: container.clientWidth });
            };
            window.addEventListener('resize', container._resizeHandler);
        }
    } catch (err) {
        console.error('asset detail market chart failed:', err);
    }
}

async function loadAssetDetailPositionChart(ticker) {
    const canvas = document.getElementById('assetDetailPositionChart');
    if (!canvas || typeof Chart === 'undefined') return;
    const wrapper = canvas.parentElement;
    try {
        const resp = await fetch(`${ASSET_DETAIL_API}/portfolio/position-history/${ticker}?days=1825`);
        const data = await resp.json();
        const hist = data.history || [];

        if (assetDetailPositionChart) {
            assetDetailPositionChart.destroy();
            assetDetailPositionChart = null;
        }
        if (!hist.length) {
            wrapper.innerHTML = data.has_transactions === false && data.current_quantity > 0
                ? `<p class="text-muted" style="padding:20px;">Tienes ${data.current_quantity} unidades, pero no hay compras individuales registradas para reconstruir el histórico — probablemente porque llegaron a tu cuenta por depósito/transferencia en vez de una compra ejecutada en el propio broker (Kraken, por ejemplo, solo registra operaciones reales, no depósitos).</p>`
                : '<p class="text-muted" style="padding:20px;">Aún no hay histórico de posición para este activo (¿lo compraste hoy?).</p>';
            return;
        }
        if (!canvas.isConnected) {
            wrapper.innerHTML = '<canvas id="assetDetailPositionChart"></canvas>';
        }
        const ctx = document.getElementById('assetDetailPositionChart').getContext('2d');
        assetDetailPositionChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: hist.map(h => h.date),
                datasets: [
                    {
                        label: 'Valor de tu posición', data: hist.map(h => h.value),
                        borderColor: '#00d4aa', backgroundColor: 'rgba(0,212,170,0.1)',
                        fill: true, tension: 0.2, pointRadius: 0, borderWidth: 2,
                    },
                    {
                        label: 'Coste acumulado (aportado)', data: hist.map(h => h.cost_basis),
                        borderColor: '#94a3b8', backgroundColor: 'transparent',
                        borderDash: [4, 4], tension: 0.2, pointRadius: 0, borderWidth: 2,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: true, labels: { color: '#94a3b8', boxWidth: 12 } } },
                scales: {
                    x: { ticks: { maxTicksLimit: 8, color: '#64748b' }, grid: { display: false } },
                    y: { ticks: { color: '#64748b', callback: v => formatCurrency(v) }, grid: { color: '#1e293b' } },
                },
            },
        });
    } catch (err) {
        console.error('asset detail position chart failed:', err);
        wrapper.innerHTML = '<p class="text-muted" style="padding:20px; color:#ef4444;">No se pudo cargar el histórico de tu posición.</p>';
    }
}

async function loadAssetDetailTransactions(ticker) {
    const tbody = document.getElementById('assetDetailTxBody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted" style="padding:20px;">Cargando…</td></tr>';
    try {
        const resp = await fetch(`${ASSET_DETAIL_API}/transactions?ticker=${encodeURIComponent(ticker)}`, { cache: 'no-store' });
        const txs = await resp.json();
        if (!resp.ok) throw new Error(txs.detail || `HTTP ${resp.status}`);
        if (!Array.isArray(txs) || !txs.length) {
            let msg = 'Sin aportaciones registradas para este activo.';
            try {
                const posResp = await fetch(`${ASSET_DETAIL_API}/portfolio`);
                const portfolio = await posResp.json();
                if (portfolio.positions?.some(p => p.ticker === ticker)) {
                    msg = 'Tienes esta posición, pero no hay compras individuales registradas — probablemente llegó por depósito/transferencia en vez de una compra ejecutada en el propio broker, que solo registra operaciones reales.';
                }
            } catch (e) { /* keep generic message */ }
            tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted" style="padding:20px;">${msg}</td></tr>`;
            return;
        }
        const typeLabel = { buy: '🟢 Compra', sell: '🔴 Venta', dividend: '💰 Dividendo' };
        const fmt = (n, d = 2) => (n || 0).toLocaleString('es-ES', { minimumFractionDigits: d, maximumFractionDigits: d });
        tbody.innerHTML = txs.map(t => `
            <tr>
                <td>${(t.executed_at || '').slice(0, 10)}</td>
                <td>${typeLabel[t.type] || t.type}</td>
                <td class="text-right mono">${fmt(t.quantity, 6)}</td>
                <td class="text-right mono">${fmt(t.price)} ${t.currency || 'EUR'}</td>
                <td class="text-right mono">${fmt((t.quantity || 0) * (t.price || 0))} ${t.currency || 'EUR'}</td>
                <td>${t.broker || '—'}</td>
            </tr>
        `).join('');
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center" style="padding:20px; color:#ef4444;">No se pudieron cargar: ${err.message}</td></tr>`;
    }
}

window.showAssetDetail = showAssetDetail;
