/**
 * 👀 Watchlist — assets you track (but don't own yet), each shown with its live
 * "setup" signal (RSI, trend vs SMA200, 52w range, ADX) so you can see what's
 * setting up for an entry. Technical signals, not recommendations.
 */
const WATCHLIST_API = window.API_BASE_URL || '/api';

async function loadWatchlist() {
    const el = document.getElementById('watchlistContent');
    if (!el) return;
    el.innerHTML = watchlistFormHtml() + '<p class="text-muted">Cargando señales…</p>';
    wireWatchlistForm();
    let items = [];
    try {
        const r = await fetch(`${WATCHLIST_API}/watchlist`);
        if (r.ok) items = (await r.json()).items || [];
    } catch (e) { /* render form anyway */ }
    el.innerHTML = watchlistFormHtml() + watchlistListHtml(items);
    wireWatchlistForm();
    const ex = document.getElementById('watchlistExport');
    if (ex && window.exportToolbarHTML) ex.innerHTML = exportToolbarHTML('watchlistContent', 'watchlist');
    if (items.length && typeof renderSparkline === 'function') loadWatchlistSparklines(items);
}

// Real recent-trend sparklines per row — same renderSparkline() the portfolio
// dashboard uses, but fetched via the generic (not portfolio-only) history
// endpoint since a watched ticker isn't necessarily something you own.
const _watchSparkCache = new Map();
async function loadWatchlistSparklines(items) {
    await Promise.all(items.map(async (it) => {
        const cell = document.querySelector(`[data-watch-spark="${it.ticker}"]`);
        if (!cell) return;
        const cached = _watchSparkCache.get(it.ticker);
        if (cached) { cell.innerHTML = renderSparkline(cached.values, cached.up); return; }
        try {
            const resp = await fetch(`${WATCHLIST_API}/asset/${encodeURIComponent(it.ticker)}/history?period=1mo&asset_type=auto`, { cache: 'no-store' });
            if (!resp.ok) return;
            const data = await resp.json();
            const values = (data.history || []).map(h => h.close ?? h.price).filter(v => v > 0);
            if (values.length < 2) return;
            const up = values[values.length - 1] >= values[0];
            _watchSparkCache.set(it.ticker, { values, up });
            cell.innerHTML = renderSparkline(values, up);
        } catch (err) { /* a missing sparkline isn't worth surfacing as an error */ }
    }));
}

function watchlistFormHtml() {
    return `<div class="card" style="margin-bottom:16px;">
        <h3>➕ Añadir a la watchlist</h3>
        <p class="text-muted" style="font-size:12px; margin:-4px 0 10px;">Activos que vigilas para (quizá) comprar. Verás su <strong>setup de entrada</strong> en vivo.</p>
        <div style="display:flex; gap:10px; flex-wrap:wrap; align-items:flex-end;">
            <div class="form-group"><label>Ticker</label><input id="wTicker" placeholder="NVDA" style="text-transform:uppercase;"></div>
            <div class="form-group"><label>Nombre (opc)</label><input id="wName" placeholder="Nvidia"></div>
            <div class="form-group" style="flex:1; min-width:180px;"><label>Nota (opc)</label><input id="wNote" placeholder="esperar pullback a la media de 200"></div>
            <button class="btn-primary" id="wSubmit">Añadir</button>
        </div>
        <span id="wMsg" style="font-size:13px;"></span>
        <div style="margin-top:10px; padding-top:10px; border-top:1px solid rgba(43,40,34,0.08);">
            <button class="btn-secondary" id="wImportHistory">📥 Importar mi histórico de inversiones</button>
            <span class="text-muted" style="font-size:11.5px; margin-left:8px;">Añade todo lo que ya has comprado alguna vez (actual o vendido) que aún no esté aquí — no toca lo que ya tengas ni lo que hayas quitado antes.</span>
            <span id="wImportMsg" style="font-size:13px; display:block; margin-top:4px;"></span>
        </div>
    </div>`;
}

function watchlistListHtml(items) {
    if (!items.length) return '<p class="text-muted">Tu watchlist está vacía. Añade un activo arriba ☝️</p>';
    const num = (v, d = 1) => (v == null ? '—' : (+v).toFixed(d));
    const rows = items.map(it => {
        const c = it.setup || '';
        const color = c.startsWith('🟢') ? 'var(--positive)' : c.startsWith('🔵') ? 'var(--info)' : c.startsWith('🟡') ? 'var(--warning)' : 'var(--text-secondary)';
        return `<tr>
            <td>${it.name} <span class="text-muted mono" style="font-size:11px;">${it.ticker}</span>${it.note ? `<br><span class="text-muted" style="font-size:11px;">${it.note}</span>` : ''}</td>
            <td data-watch-spark="${it.ticker}"></td>
            <td class="text-right mono">${it.price != null ? num(it.price, 2) : '—'}</td>
            <td class="text-right mono ${(it.ret_3m || 0) >= 0 ? 'value-positive' : 'value-negative'}">${it.ret_3m != null ? (it.ret_3m >= 0 ? '+' : '') + it.ret_3m + '%' : '—'}</td>
            <td class="text-right mono">${it.rsi != null ? num(it.rsi, 0) : '—'}</td>
            <td class="text-right mono">${it.range_pos_52w != null ? num(it.range_pos_52w, 0) + '%' : '—'}</td>
            <td class="text-right mono">${it.adx != null ? num(it.adx, 0) : '—'}</td>
            <td style="color:${color}; font-weight:600;">${it.setup}</td>
            <td class="text-right"><button class="btn-secondary" style="background:transparent; color:var(--negative); padding:2px 8px;" onclick="deleteWatch(${it.id})" title="Quitar">✕</button></td>
        </tr>`;
    }).join('');
    return `<div class="card"><div class="table-container"><table class="manager-table">
        <thead><tr><th>Activo</th><th>Tendencia (1m)</th><th class="text-right">Precio</th><th class="text-right">3m</th><th class="text-right">RSI</th><th class="text-right">Rango 52s</th><th class="text-right">ADX</th><th>Setup</th><th></th></tr></thead>
        <tbody>${rows}</tbody></table></div>
        <p class="text-muted" style="font-size:10.5px; margin:8px 0 0;">Setup: 🟢 posible entrada · 🔵 fuerza/ruptura · 🟡 cerca de mínimos · gris sin setup claro. Son señales técnicas objetivas, no una recomendación.</p>
    </div>`;
}

function wireWatchlistForm() {
    const importBtn = document.getElementById('wImportHistory');
    if (importBtn) {
        importBtn.onclick = async () => {
            const msg = document.getElementById('wImportMsg');
            importBtn.disabled = true;
            if (msg) { msg.textContent = 'Revisando tu histórico…'; msg.style.color = 'var(--text-secondary)'; }
            try {
                const r = await fetch(`${WATCHLIST_API}/watchlist/import-history`, { method: 'POST' });
                if (!r.ok) throw new Error();
                const data = await r.json();
                if (msg) {
                    msg.textContent = data.count > 0
                        ? `✓ Añadidos ${data.count}: ${data.added.join(', ')}`
                        : 'Ya estaba todo — no había nada nuevo que añadir.';
                    msg.style.color = 'var(--positive)';
                }
                await loadWatchlist();
            } catch (e) {
                if (msg) { msg.textContent = 'No se pudo importar el histórico.'; msg.style.color = 'var(--negative)'; }
                importBtn.disabled = false;
            }
        };
    }

    const btn = document.getElementById('wSubmit');
    if (!btn) return;
    btn.onclick = async () => {
        const ticker = (document.getElementById('wTicker').value || '').trim();
        const msg = document.getElementById('wMsg');
        if (!ticker) { msg.textContent = 'Escribe un ticker.'; msg.style.color = 'var(--negative)'; return; }
        btn.disabled = true; msg.textContent = 'Añadiendo…'; msg.style.color = 'var(--text-secondary)';
        try {
            const r = await fetch(`${WATCHLIST_API}/watchlist`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ticker, name: document.getElementById('wName').value.trim(), note: document.getElementById('wNote').value.trim() }),
            });
            if (!r.ok) throw new Error();
            await loadWatchlist();
        } catch (e) { msg.textContent = 'No se pudo añadir.'; msg.style.color = 'var(--negative)'; btn.disabled = false; }
    };
}

async function deleteWatch(id) {
    try { await fetch(`${WATCHLIST_API}/watchlist/${id}`, { method: 'DELETE' }); await loadWatchlist(); } catch (e) { /* noop */ }
}

document.addEventListener('DOMContentLoaded', () => {
    const link = document.querySelector('[data-page="watchlist"]');
    if (link) link.addEventListener('click', () => setTimeout(loadWatchlist, 150));
    setTimeout(() => {
        const p = document.getElementById('page-watchlist');
        if (p && p.classList.contains('active')) loadWatchlist();
    }, 500);
});
