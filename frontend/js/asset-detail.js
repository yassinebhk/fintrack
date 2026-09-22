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
    renderAssetStatsStrip(currentAssetDetailTicker, document.getElementById('assetDetailStatsStrip'));
    if (window.renderFavButton) {
        window.renderFavButton(document.getElementById('assetDetailFav'),
            currentAssetDetailTicker, info ? info.name : currentAssetDetailTicker);
    }

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
        // No curated Spanish summary for this ticker — fall back to Yahoo's own
        // real business/fund/coin description rather than showing nothing.
        loadAssetAboutFallback(ticker, aboutSection, aboutEl);
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
            // Market price stays in the asset's own listing currency (how everyone
            // quotes it, e.g. $ for TSM) — but the position's value/gain are what THIS
            // portfolio holds, so those must be the euro-converted _base fields, not
            // the raw native-currency ones, or a USD position's value shows with a €
            // symbol slapped on an unconverted dollar number.
            document.getElementById('assetDetailPrice').textContent = formatCurrency(position.current_price, position.currency);
            const changeEl = document.getElementById('assetDetailChange');
            const chg = position.day_change_pct || 0;
            changeEl.textContent = `${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%`;
            changeEl.className = `price-change ${chg >= 0 ? 'positive' : 'negative'}`;
            document.getElementById('assetDetailQty').textContent =
                `${position.quantity.toFixed(position.type === 'crypto' ? 6 : 4)} unidades`;
            document.getElementById('assetDetailValue').textContent = formatCurrency(position.market_value_base);
            const glEl = document.getElementById('assetDetailGainLoss');
            glEl.textContent = `${position.gain_loss_base >= 0 ? '+' : ''}${formatCurrency(position.gain_loss_base)} (${position.gain_loss_pct.toFixed(2)}%)`;
            glEl.className = `stat-value ${position.gain_loss_base >= 0 ? 'positive' : 'negative'}`;
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

// Real "qué es esto" text when there's no curated static one — Yahoo's own
// business/fund/coin summary (never generated by us). Shared by every page
// that shows an about-section fallback for an arbitrary (not-curated) ticker.
async function loadAssetAboutFallback(ticker, sectionEl, textEl) {
    if (!sectionEl || !textEl) return;
    try {
        const base = window.API_BASE_URL || 'http://localhost:8000/api';
        const resp = await fetch(`${base}/asset/${encodeURIComponent(ticker)}/stats?asset_type=auto`, { cache: 'no-store' });
        if (!resp.ok) return;
        const s = await resp.json();
        const d = s && s.description;
        if (!d || !d.summary) return;
        const meta = [d.long_name, d.sector || d.category, d.industry || d.fund_family].filter(Boolean).join(' · ');
        textEl.innerHTML = `${meta ? `<p style="margin:0 0 8px; font-size:12px; color:var(--text-secondary);">${meta}</p>` : ''}<p style="margin:0;">${d.summary}</p>`;
        sectionEl.style.display = '';
    } catch (err) { /* no description available — leave the section hidden */ }
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

// Rolling-mean SMA over the CLOSE prices already loaded for the chart — same
// 50/200-session windows the quant engine itself uses (asset_analysis.py's
// _build_charts), computed client-side so no extra backend round-trip is
// needed. Returns [] when there aren't enough bars yet (e.g. a 1M range).
function computeSMASeries(history, period) {
    const closes = history.map(h => h.close ?? h.price);
    const out = [];
    for (let i = period - 1; i < closes.length; i++) {
        let sum = 0, ok = true;
        for (let j = i - period + 1; j <= i; j++) {
            if (closes[j] == null) { ok = false; break; }
            sum += closes[j];
        }
        if (ok) out.push({ time: history[i].date, value: sum / period });
    }
    return out;
}

// Draw SMA50 (gold, dashed) and SMA200 (terracotta, dashed) on top of the price
// series — same colors as the static chart in the deep-analysis modal, just
// interactive here. Shared by both the asset-detail and asset-analysis pages.
function addSMAOverlays(chart, history) {
    const sma50 = computeSMASeries(history, 50);
    const sma200 = computeSMASeries(history, 200);
    if (sma50.length) {
        const s = chart.addLineSeries({
            color: '#C99A3E', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed,
            priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
        });
        s.setData(sma50);
    }
    if (sma200.length) {
        const s = chart.addLineSeries({
            color: '#C6473C', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed,
            priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
        });
        s.setData(sma200);
    }
}

// Floating O/H/L/C (or price) readout that follows the crosshair, TradingView-
// style. Reuses one overlay div per container — safe to call again after a
// chart is torn down and recreated (container.innerHTML='' wipes it along
// with the old chart, so no stale subscriptions pile up).
function attachCrosshairLegend(chart, container, history, timeKey = 'date') {
    if (!container || !history.length) return;
    let legend = container.querySelector('.tv-crosshair-legend');
    if (!legend) {
        legend = document.createElement('div');
        legend.className = 'tv-crosshair-legend';
        legend.style.cssText = 'position:absolute; top:6px; left:6px; z-index:2; font-size:11px; font-family:monospace; background:rgba(245,241,233,0.9); border:1px solid rgba(43,40,34,0.12); border-radius:6px; padding:3px 8px; pointer-events:none; white-space:nowrap;';
        container.style.position = container.style.position || 'relative';
        container.appendChild(legend);
    }
    const byTime = {};
    history.forEach(h => { byTime[h[timeKey]] = h; });
    const fmt = (n) => (n == null ? '—' : (+n).toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
    const label = (h) => timeKey === 'time'
        ? new Date(h.time * 1000).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })
        : h.date;
    const render = (h) => {
        if (!h) { legend.style.display = 'none'; return; }
        legend.style.display = 'block';
        if (h.open !== undefined && h.high !== undefined) {
            legend.style.color = h.close >= h.open ? '#2C4A6E' : '#C6473C';
            legend.textContent = `${label(h)}  O ${fmt(h.open)}  H ${fmt(h.high)}  L ${fmt(h.low)}  C ${fmt(h.close)}`;
        } else {
            legend.style.color = '#2B2822';
            legend.textContent = `${label(h)}  ${fmt(h.close ?? h.price)}`;
        }
    };
    render(history[history.length - 1]);
    chart.subscribeCrosshairMove((param) => {
        render(param && param.time != null ? byTime[param.time] : history[history.length - 1]);
    });
}

// Mark each real buy/sell on the market-price chart, at its exact date — so
// you see where on the real price curve you actually entered/exited, not just
// your position value over time (that's the separate chart below).
function _fmtMarketCap(n) {
    if (n == null) return null;
    const abs = Math.abs(n);
    if (abs >= 1e12) return (n / 1e12).toFixed(2) + 'T';
    if (abs >= 1e9) return (n / 1e9).toFixed(2) + 'B';
    if (abs >= 1e6) return (n / 1e6).toFixed(1) + 'M';
    return n.toLocaleString('es-ES');
}

function _fmtVolume(n) {
    if (n == null) return null;
    const abs = Math.abs(n);
    if (abs >= 1e9) return (n / 1e9).toFixed(2) + 'B';
    if (abs >= 1e6) return (n / 1e6).toFixed(1) + 'M';
    if (abs >= 1e3) return (n / 1e3).toFixed(0) + 'K';
    return String(Math.round(n));
}

// Small stats strip (day/52-week range, avg volume, market cap, PER, dividend,
// insider sentiment, next earnings/ex-dividend) shown below the interactive
// price chart — one lightweight endpoint so the main history call stays fast.
// Every field is optional; a missing one is simply left out, never guessed.
// Shared by both the asset-detail and "Analiza cualquier activo" pages.
async function renderAssetStatsStrip(ticker, containerEl) {
    if (!containerEl) return;
    containerEl.innerHTML = '';
    try {
        const base = window.API_BASE_URL || 'http://localhost:8000/api';
        const resp = await fetch(`${base}/asset/${encodeURIComponent(ticker)}/stats?asset_type=auto`, { cache: 'no-store' });
        if (!resp.ok) return;
        const s = await resp.json();
        if (!s || !Object.keys(s).length) return;

        const fmtP = (n) => (n == null ? null : (+n).toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
        const chips = [];
        if (s.day_low != null && s.day_high != null) chips.push(['Rango del día', `${fmtP(s.day_low)} – ${fmtP(s.day_high)}`]);
        if (s.year_low != null && s.year_high != null) chips.push(['Rango 52 semanas', `${fmtP(s.year_low)} – ${fmtP(s.year_high)}`]);
        const vol = s.avg_volume_10d ?? s.avg_volume_3m;
        if (vol != null) chips.push(['Volumen medio', _fmtVolume(vol)]);
        if (s.market_cap != null) chips.push(['Market cap', _fmtMarketCap(s.market_cap)]);
        if (s.pe_ratio != null) chips.push(['PER', (+s.pe_ratio).toFixed(1)]);
        if (s.dividend_yield != null) chips.push(['Dividendo', (+s.dividend_yield).toFixed(2) + '%']);
        if (s.insider_mspr != null) {
            const mspr = +s.insider_mspr;
            chips.push(['Insiders' + (s.insider_month ? ` (${s.insider_month})` : ''),
                (mspr >= 0 ? '+' : '') + mspr.toFixed(0) + (mspr >= 20 ? ' 🟢' : mspr <= -20 ? ' 🔴' : '')]);
        }

        const daysTo = (iso) => Math.round((new Date(iso) - new Date()) / 86400000);
        const catalystBits = [];
        if (s.next_earnings) {
            const dd = daysTo(s.next_earnings);
            const soon = dd >= 0 && dd <= 14;
            catalystBits.push(`<span${soon ? ' style="color:var(--negative); font-weight:600;"' : ''}>📊 Resultados ${s.next_earnings}${dd >= 0 ? ` (en ${dd}d)` : ''}${soon ? ' ⚠️' : ''}</span>`);
        }
        if (s.next_ex_dividend) {
            const dd = daysTo(s.next_ex_dividend);
            if (dd >= 0) catalystBits.push(`💰 Ex-dividendo ${s.next_ex_dividend} (en ${dd}d)`);
        }

        const chipsHtml = chips.map(([label, value]) =>
            `<span style="background:rgba(43,40,34,0.05); border-radius:6px; padding:3px 9px; font-size:11.5px; white-space:nowrap;">${label}: <strong>${value}</strong></span>`
        ).join('');

        containerEl.innerHTML = `
            ${chipsHtml ? `<div style="display:flex; gap:6px; flex-wrap:wrap; margin-top:8px;">${chipsHtml}</div>` : ''}
            ${catalystBits.length ? `<div style="font-size:11.5px; margin-top:6px; color:var(--text-secondary);">📅 Próximos catalizadores: ${catalystBits.join(' · ')}</div>` : ''}
        `;
        return s;
    } catch (err) {
        console.error('asset stats strip failed:', err);
        return null;
    }
}

async function loadAssetDetailTradeMarkers(ticker, series, historyDates) {
    if (!series || !historyDates.length) return;
    try {
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

        const resp = await assetDetailFetch(`${ASSET_DETAIL_API}/transactions?ticker=${encodeURIComponent(ticker)}`, { cache: 'no-store' });
        if (resp.status === 401) return;
        const txs = await resp.json();

        let markers = (Array.isArray(txs) ? txs : [])
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
            .filter(Boolean);

        // No individual trade recorded (true for most positions reconstructed in
        // bulk after the Neon DB incident — see position_data_integrity memory) —
        // fall back to ONE marker at the position's creation date, using a
        // distinct shape/color and explicit "≈ aprox." wording so it's never
        // mistaken for a real logged trade.
        if (!markers.length) {
            try {
                const posResp = await assetDetailFetch(`${ASSET_DETAIL_API}/portfolio`);
                if (posResp.status !== 401) {
                    const portfolio = await posResp.json();
                    const pos = portfolio.positions?.find(p => p.ticker === ticker);
                    if (pos && pos.created_at && pos.quantity > 0) {
                        markers = [{
                            time: snapToChart(pos.created_at.slice(0, 10)),
                            position: 'belowBar',
                            color: '#9C9689',
                            shape: 'circle',
                            text: `≈ ${fmtQty(pos.quantity)} @ ${fmtPrice(pos.avg_price, pos.currency)} (posición reconstruida, no tu fecha real de compra)`,
                        }];
                    }
                }
            } catch (e) { /* keep no markers rather than fail the whole chart */ }
        }

        // With many trades the per-marker text labels pile up, overlapping each
        // other, the crosshair legend and the caption/buttons below. Past a small
        // count, keep only the arrows (you still see WHERE you bought/sold) — the
        // exact qty/price of each is in the "Tus aportaciones" table below.
        const MAX_LABELS = 6;
        const showLabels = markers.length <= MAX_LABELS;
        if (!showLabels) markers = markers.map(m => ({ ...m, text: undefined }));

        markers.sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0));
        if (markers.length) series.setMarkers(markers);
        _setTradeMarkerNote(showLabels ? 0 : markers.length);
    } catch (err) {
        console.error('asset detail trade markers failed:', err);
    }
}

// Toggle the "many trades → arrows only" hint shown under the market chart.
function _setTradeMarkerNote(count) {
    const note = document.getElementById('assetDetailMarkerNote');
    if (!note) return;
    if (count) {
        note.textContent = `ℹ️ ${count} operaciones en este activo: se muestran solo las flechas para no saturar el gráfico. El detalle (cantidad y precio de cada una) está en la tabla «Tus aportaciones» de abajo.`;
        note.style.display = '';
    } else {
        note.textContent = '';
        note.style.display = 'none';
    }
}

function loadAssetDetailMarketChart(ticker) {
    const container = document.getElementById('assetDetailTvContainer');
    if (!container) return;
    // The container had a fixed 400px height for the old single chart; mountPriceChart
    // now builds its own range bar + canvas, so let it size itself.
    container.style.height = '';
    mountPriceChart(container, ticker, { height: 400, defaultPeriod: '1y', withTradeMarkers: true });
}

// Reusable interactive price chart with time-range toggles (Hoy / 1S / 1M / 3M /
// 6M / 1A / 2A / 5A / Máx). Pulls each range live from /asset/{ticker}/history
// (the backend already serves every one of these periods, intraday included), so
// the chart is dynamic instead of a fixed 1-year snapshot or a static image.
// Shared by the asset-detail page and the deep-analysis modal.
const PRICE_CHART_PERIODS = [
    ['1d', 'Hoy'], ['5d', '1S'], ['1mo', '1M'], ['3mo', '3M'],
    ['6mo', '6M'], ['1y', '1A'], ['2y', '2A'], ['5y', '5A'], ['max', 'Máx'],
];

function _drawPriceSeries(chart, history, timeKey) {
    const hasOHLC = history.length > 0 && history[0].open !== undefined && history[0].high !== undefined;
    if (hasOHLC) {
        const s = chart.addCandlestickSeries({
            upColor: '#2C4A6E', downColor: '#C6473C',
            borderUpColor: '#2C4A6E', borderDownColor: '#C6473C',
            wickUpColor: '#2C4A6E', wickDownColor: '#C6473C',
        });
        s.setData(history.map(h => ({ time: h[timeKey], open: h.open, high: h.high, low: h.low, close: h.close })));
        return s;
    }
    const first = history[0]?.close ?? history[0]?.price ?? 0;
    const last = history[history.length - 1]?.close ?? history[history.length - 1]?.price ?? 0;
    const up = last >= first;
    const s = chart.addAreaSeries({
        lineColor: up ? '#2C4A6E' : '#C6473C',
        topColor: up ? 'rgba(44, 74, 110,0.4)' : 'rgba(198, 71, 60,0.4)',
        bottomColor: 'rgba(0,0,0,0)', lineWidth: 2,
    });
    s.setData(history.map(h => ({ time: h[timeKey], value: h.close ?? h.price })));
    return s;
}

function mountPriceChart(container, ticker, opts = {}) {
    if (!container || typeof LightweightCharts === 'undefined') return null;
    const height = opts.height || 380;
    const defaultPeriod = opts.defaultPeriod || '1y';
    const withMarkers = !!opts.withTradeMarkers;

    container.innerHTML = `
        <div class="pchart-ranges" role="tablist" aria-label="Rango temporal">
            ${PRICE_CHART_PERIODS.map(([p, label]) =>
                `<button type="button" class="pchart-range-btn" data-period="${p}">${label}</button>`).join('')}
        </div>
        <div class="pchart-canvas" style="position:relative; width:100%; height:${height}px;"></div>`;
    const rangesEl = container.querySelector('.pchart-ranges');
    const canvasEl = container.querySelector('.pchart-canvas');
    let chart = null;
    let resizeHandler = null;

    async function draw(period) {
        rangesEl.querySelectorAll('.pchart-range-btn').forEach(b =>
            b.classList.toggle('active', b.dataset.period === period));
        canvasEl.innerHTML = '<p class="text-muted" style="position:absolute; top:50%; left:0; right:0; text-align:center; transform:translateY(-50%); margin:0;">Cargando…</p>';
        try {
            const resp = await assetDetailFetch(
                `${ASSET_DETAIL_API}/asset/${encodeURIComponent(ticker)}/history?period=${period}&asset_type=auto`,
                { cache: 'no-store' });
            if (resp.status === 401) { canvasEl.innerHTML = '<p class="text-muted" style="padding:20px;">Inicia sesión para ver el gráfico.</p>'; return; }
            const data = await resp.json();
            const history = data.history || [];
            if (chart) { try { chart.remove(); } catch (e) { /* noop */ } chart = null; }
            canvasEl.innerHTML = '';
            if (!history.length) {
                canvasEl.innerHTML = '<p class="text-muted" style="padding:20px;">Sin datos para este rango.</p>';
                return;
            }
            const useTime = !!data.intraday;
            const timeKey = useTime ? 'time' : 'date';
            chart = LightweightCharts.createChart(canvasEl, {
                width: canvasEl.clientWidth, height,
                layout: { background: { color: 'transparent' }, textColor: '#746E63' },
                grid: { vertLines: { color: 'rgba(30,41,59,0.5)' }, horzLines: { color: 'rgba(30,41,59,0.5)' } },
                rightPriceScale: { borderColor: '#D8D0C0' },
                timeScale: { borderColor: '#D8D0C0', timeVisible: useTime, secondsVisible: false },
                crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
            });
            const series = _drawPriceSeries(chart, history, timeKey);
            if (!useTime) addSMAOverlays(chart, history);  // SMA50/200 need daily bars
            attachCrosshairLegend(chart, canvasEl, history, timeKey);
            chart.timeScale().fitContent();
            // Trade markers only make sense on the asset-detail chart, and only for
            // daily bars (a buy date snaps to a daily bar, not an intraday candle).
            if (withMarkers && !useTime) loadAssetDetailTradeMarkers(ticker, series, history.map(h => h.date));
            else if (withMarkers) _setTradeMarkerNote(0);
            if (!resizeHandler) {
                resizeHandler = () => { if (chart) chart.applyOptions({ width: canvasEl.clientWidth }); };
                window.addEventListener('resize', resizeHandler);
            }
        } catch (err) {
            console.error('price chart failed:', err);
            canvasEl.innerHTML = '<p class="text-muted" style="padding:20px; color:var(--negative);">No se pudo cargar el gráfico. ' + _RETRY_BTN + '</p>';
        }
    }

    rangesEl.querySelectorAll('.pchart-range-btn').forEach(b =>
        b.addEventListener('click', () => draw(b.dataset.period)));
    draw(defaultPeriod);
    return { draw };
}
window.mountPriceChart = mountPriceChart;

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
    const foot = document.getElementById('assetDetailTxFoot');
    if (foot) foot.innerHTML = '';
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
        renderAssetDetailTxFooter(txs);
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center" style="padding:20px; color:var(--negative);">No se pudieron cargar: ${err.message}<br>${_RETRY_BTN}</td></tr>`;
    }
}

// Totals footer for this single asset's transactions: net units held (buys −
// sells — meaningful here since it's ONE ticker) and the money invested /
// received, grouped by currency.
function renderAssetDetailTxFooter(txs) {
    const foot = document.getElementById('assetDetailTxFoot');
    if (!foot) return;
    const real = (Array.isArray(txs) ? txs : []).filter(t => t && t.type);
    if (!real.length) { foot.innerHTML = ''; return; }

    const money = t => (t.quantity || 0) * (t.price || 0);
    const netUnits = real.reduce((s, t) =>
        s + ((t.type === 'buy' ? 1 : t.type === 'sell' ? -1 : 0) * (t.quantity || 0)), 0);
    const buys = sumByCurrency(real.filter(t => t.type === 'buy'), money, t => t.currency);
    const sells = sumByCurrency(real.filter(t => t.type === 'sell'), money, t => t.currency);
    const divs = sumByCurrency(real.filter(t => t.type === 'dividend'), money, t => t.currency);

    const lines = [];
    if (Object.keys(buys).length) lines.push(`<span class="text-muted">Invertido</span>${formatByCurrency(buys)}`);
    if (Object.keys(sells).length) lines.push(`<span class="text-muted">Vendido</span>${formatByCurrency(sells)}`);
    if (Object.keys(divs).length) lines.push(`<span class="text-muted">Dividendos</span>${formatByCurrency(divs)}`);
    const fmt6 = n => (n || 0).toLocaleString('es-ES', { maximumFractionDigits: 6 });
    const n = real.length;

    foot.innerHTML = `<tr class="totals-row">
        <td colspan="2" style="font-weight:600;">Σ Totales · ${n} mov.</td>
        <td class="text-right mono" title="Unidades netas (compras − ventas)">${fmt6(netUnits)}</td>
        <td></td>
        <td class="text-right mono" style="line-height:1.75;">${lines.join('<br>') || '—'}</td>
        <td></td>
    </tr>`;
}

window.showAssetDetail = showAssetDetail;
