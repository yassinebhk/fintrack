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

// Retry transient failures (flaky mobile network, or the backend restarting
// mid-deploy) before giving up. Retries on network error / 5xx; returns 4xx
// (e.g. 401/404) as-is so the caller can handle it. This is what makes a deep
// link opened during a brief blip load correctly instead of showing "sin
// conexión" with empty data.
async function assetDetailFetch(url, opts, tries = 3) {
    let lastErr;
    for (let i = 0; i < tries; i++) {
        try {
            const resp = await fetch(url, opts);
            if (resp.status >= 500) throw new Error(`HTTP ${resp.status}`);
            return resp;
        } catch (e) {
            lastErr = e;
            if (i < tries - 1) await new Promise((r) => setTimeout(r, 600 * (i + 1)));
        }
    }
    throw lastErr;
}

// Reload the current asset detail (used by the "Reintentar" buttons on error).
window.retryAssetDetail = () => { if (currentAssetDetailTicker) showAssetDetail(currentAssetDetailTicker); };

const _RETRY_BTN = '<button onclick="retryAssetDetail()" class="btn-secondary" style="margin-top:10px;">🔄 Reintentar</button>';

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
    const info = ASSET_DISPLAY_NAMES[ticker] || { name: ticker, icon: '📊', color: '#2C4A6E' };
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
        const resp = await assetDetailFetch(`${ASSET_DETAIL_API}/portfolio`);
        if (resp.status === 401) {
            document.getElementById('assetDetailPrice').textContent = 'Sesión caducada';
            document.getElementById('assetDetailGainLoss').innerHTML =
                'Recarga la app para iniciar sesión. ' + _RETRY_BTN;
            return;
        }
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
        document.getElementById('assetDetailPrice').textContent = '—';
        document.getElementById('assetDetailGainLoss').innerHTML =
            'No se pudieron cargar los datos de tu posición. ' + _RETRY_BTN;
    }
}

function renderAssetDetailMarketSeries(chart, history) {
    const hasOHLC = history.length > 0 && history[0].open !== undefined && history[0].high !== undefined;
    if (hasOHLC) {
        const series = chart.addCandlestickSeries({
            upColor: '#2C4A6E', downColor: '#C6473C',
            borderUpColor: '#2C4A6E', borderDownColor: '#C6473C',
            wickUpColor: '#2C4A6E', wickDownColor: '#C6473C',
        });
        series.setData(history.map(h => ({ time: h.date, open: h.open, high: h.high, low: h.low, close: h.close })));
        return series;
    } else {
        const firstPrice = history[0]?.close ?? history[0]?.price ?? 0;
        const lastPrice = history[history.length - 1]?.close ?? history[history.length - 1]?.price ?? 0;
        const up = lastPrice >= firstPrice;
        const series = chart.addAreaSeries({
            lineColor: up ? '#2C4A6E' : '#C6473C',
            topColor: up ? 'rgba(44, 74, 110,0.4)' : 'rgba(198, 71, 60,0.4)',
            bottomColor: 'rgba(0,0,0,0)',
            lineWidth: 2,
        });
        series.setData(history.map(h => ({ time: h.date, value: h.close ?? h.price })));
        return series;
    }
}

// Mark each real buy/sell on the market-price chart, at its exact date — so
// you see where on the real price curve you actually entered/exited, not just
// your position value over time (that's the separate chart below).
async function loadAssetDetailTradeMarkers(ticker, series, historyDates) {
    if (!series || !historyDates.length) return;
    try {
        const resp = await assetDetailFetch(`${ASSET_DETAIL_API}/transactions?ticker=${encodeURIComponent(ticker)}`, { cache: 'no-store' });
        if (resp.status === 401) return;
        const txs = await resp.json();
        if (!Array.isArray(txs) || !txs.length) return;

        // Chart bars only exist for trading days; a transaction on a weekend/holiday
        // (or before the fetched window) snaps to the nearest earlier bar so the
        // marker always renders instead of silently vanishing.
        const dates = historyDates.slice().sort();
        const snapToChart = (isoDate) => {
            let best = null;
            for (const d of dates) {
                if (d <= isoDate) best = d; else break;
            }
            return best || dates[0];
        };
        const fmtQty = (n) => (n || 0).toLocaleString('es-ES', { maximumFractionDigits: 6 });
        const fmtPrice = (n, cur) => `${(n || 0).toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}${cur ? ' ' + cur : ''}`;

        const markers = txs
            .filter(t => t.type === 'buy' || t.type === 'sell')
            .map(t => {
                const day = (t.executed_at || '').slice(0, 10);
                if (!day) return null;
                const isBuy = t.type === 'buy';
                return {
                    time: snapToChart(day),
                    position: isBuy ? 'belowBar' : 'aboveBar',
                    color: isBuy ? '#4A9B8E' : '#C6473C',
                    shape: isBuy ? 'arrowUp' : 'arrowDown',
                    text: `${isBuy ? 'Compra' : 'Venta'} ${fmtQty(t.quantity)} @ ${fmtPrice(t.price, t.currency)}`,
                };
            })
            .filter(Boolean)
            .sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0));
        if (markers.length) series.setMarkers(markers);
    } catch (err) {
        console.error('asset detail trade markers failed:', err);
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
            layout: { background: { color: 'transparent' }, textColor: '#746E63' },
            grid: { vertLines: { color: 'rgba(30,41,59,0.5)' }, horzLines: { color: 'rgba(30,41,59,0.5)' } },
            rightPriceScale: { borderColor: '#D8D0C0' },
            timeScale: { borderColor: '#D8D0C0' },
            crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
        });
        assetDetailTvChart = chart;
        const series = renderAssetDetailMarketSeries(chart, history);
        chart.timeScale().fitContent();
        loadAssetDetailTradeMarkers(ticker, series, history.map(h => h.date));

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
        const resp = await assetDetailFetch(`${ASSET_DETAIL_API}/portfolio/position-history/${ticker}?days=1825`);
        if (resp.status === 401) {
            wrapper.innerHTML = `<p class="text-muted" style="padding:20px;">Sesión caducada — recarga la app para iniciar sesión.</p>`;
            return;
        }
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
                        borderColor: '#2C4A6E', backgroundColor: 'rgba(44, 74, 110,0.1)',
                        fill: true, tension: 0.2, pointRadius: 0, borderWidth: 2,
                    },
                    {
                        label: 'Coste acumulado (aportado)', data: hist.map(h => h.cost_basis),
                        borderColor: '#746E63', backgroundColor: 'transparent',
                        borderDash: [4, 4], tension: 0.2, pointRadius: 0, borderWidth: 2,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: true, labels: { color: '#746E63', boxWidth: 12 } } },
                scales: {
                    x: { title: { display: true, text: 'Fecha', color: '#8A8275', font: { size: 12, weight: '600' } }, ticks: { maxTicksLimit: 8, color: '#9C9689' }, grid: { display: false } },
                    y: { title: { display: true, text: 'Valor de la posición (€)', color: '#8A8275', font: { size: 12, weight: '600' } }, ticks: { color: '#9C9689', callback: v => formatCurrency(v) }, grid: { color: '#EFEBE3' } },
                },
            },
        });
        const oldNote = document.getElementById('assetDetailPosNote');
        if (oldNote) oldNote.remove();
        if (data.synthetic) {
            const p = document.createElement('p');
            p.id = 'assetDetailPosNote';
            p.className = 'text-muted';
            p.style.cssText = 'font-size:11px; margin-top:6px;';
            p.textContent = 'Histórico aproximado: no hay compras individuales registradas, se asume la posición actual mantenida durante el periodo. Importa tu histórico de transacciones para verlo exacto.';
            wrapper.appendChild(p);
        }
    } catch (err) {
        console.error('asset detail position chart failed:', err);
        wrapper.innerHTML = '<p class="text-muted" style="padding:20px; color:var(--negative);">No se pudo cargar el histórico de tu posición.<br>' + _RETRY_BTN + '</p>';
    }
}

async function loadAssetDetailTransactions(ticker) {
    const tbody = document.getElementById('assetDetailTxBody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted" style="padding:20px;">Cargando…</td></tr>';
    try {
        const resp = await assetDetailFetch(`${ASSET_DETAIL_API}/transactions?ticker=${encodeURIComponent(ticker)}`, { cache: 'no-store' });
        if (resp.status === 401) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted" style="padding:20px;">Sesión caducada — recarga la app para iniciar sesión.</td></tr>';
            return;
        }
        const txs = await resp.json();
        if (!resp.ok) throw new Error(txs.detail || `HTTP ${resp.status}`);
        if (!Array.isArray(txs) || !txs.length) {
            // No per-trade record. If the position exists, show a single derived
            // row (current holding) so the section isn't empty, plus a note. The
            // real per-trade breakdown needs a transaction-history import.
            const fmt0 = (n, d = 2) => (n || 0).toLocaleString('es-ES', { minimumFractionDigits: d, maximumFractionDigits: d });
            try {
                const posResp = await assetDetailFetch(`${ASSET_DETAIL_API}/portfolio`);
                const portfolio = await posResp.json();
                const pos = portfolio.positions?.find(p => p.ticker === ticker);
                if (pos) {
                    const qty = pos.quantity || 0;
                    const avg = pos.avg_price || (pos.cost_basis && qty ? pos.cost_basis / qty : 0);
                    const cur = pos.currency || 'EUR';
                    tbody.innerHTML = `
                        <tr>
                            <td>—</td>
                            <td>📦 Posición actual</td>
                            <td class="text-right mono">${fmt0(qty, 6)}</td>
                            <td class="text-right mono">${fmt0(avg)} ${cur}</td>
                            <td class="text-right mono">${fmt0(qty * avg)} ${cur}</td>
                            <td>${pos.broker || '—'}</td>
                        </tr>
                        <tr><td colspan="6" class="text-muted" style="padding:10px 8px; font-size:11px;">
                            Resumen derivado de tu posición actual — no hay compras individuales registradas.
                            Importa tu histórico de transacciones (p. ej. el export de Revolut) para ver cada aportación con su fecha y precio.
                        </td></tr>`;
                    return;
                }
            } catch (e) { /* fall through to generic message */ }
            tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted" style="padding:20px;">Sin aportaciones registradas para este activo.</td></tr>`;
            return;
        }
        const typeLabel = {
            buy: '🟢 Compra', sell: '🔴 Venta', dividend: '💰 Dividendo',
            deposit: '⬆️ Ingreso', withdrawal: '⬇️ Retirada', fee: '💸 Comisión',
        };
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
        tbody.innerHTML = `<tr><td colspan="6" class="text-center" style="padding:20px; color:var(--negative);">No se pudieron cargar: ${err.message}<br>${_RETRY_BTN}</td></tr>`;
    }
}

window.showAssetDetail = showAssetDetail;
