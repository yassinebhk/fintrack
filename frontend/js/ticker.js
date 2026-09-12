/**
 * Ticker tape — scrolling strip of the user's own live positions
 * (real prices/day-change from /api/portfolio, never invented data).
 */
const TICKER_API = (window.API_BASE_URL || 'http://localhost:8000/api');

function tickerFormatPrice(v, currency) {
    if (v === null || v === undefined) return '—';
    const decimals = Math.abs(v) < 1 ? 4 : 2;
    return Number(v).toLocaleString('es-ES', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) + (currency ? ' ' + currency : '');
}

async function initTicker() {
    const wrap = document.getElementById('tapeWrap');
    const track = document.getElementById('tapeTrack');
    if (!wrap || !track) return;

    try {
        const resp = await fetch(`${TICKER_API}/portfolio`, { credentials: 'same-origin' });
        if (!resp.ok) { wrap.style.display = 'none'; return; }
        const data = await resp.json();
        const positions = (data.positions || []).filter(p => p.current_price != null);
        if (positions.length === 0) { wrap.style.display = 'none'; return; }

        // Biggest positions first (already sorted by the API, but sort defensively
        // in case future callers filter/reorder before this runs).
        positions.sort((a, b) => (b.market_value_base || 0) - (a.market_value_base || 0));

        const items = positions.map(p => {
            const pct = p.day_change_pct;
            const up = pct === null || pct === undefined ? null : pct >= 0;
            const cls = up === null ? '' : (up ? 'tape-up' : 'tape-down');
            const arrow = up === null ? '' : (up ? '↑' : '↓');
            const pctTxt = (pct === null || pct === undefined) ? '—' : `${pct > 0 ? '+' : ''}${pct.toFixed(2)}%`;
            return `<span class="tape-item"><b>${escapeHtml(p.ticker)}</b><span>${tickerFormatPrice(p.current_price, p.currency)}</span><span class="${cls}">${arrow} ${pctTxt}</span></span>`;
        }).join('');

        track.innerHTML = items + items; // duplicated for a seamless scroll loop
        wrap.style.display = '';
    } catch (err) {
        console.error('Error loading ticker tape:', err);
        wrap.style.display = 'none';
    }
}

function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

window.initTicker = initTicker;
