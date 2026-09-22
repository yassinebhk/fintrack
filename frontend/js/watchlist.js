/**
 * 👀 Watchlist — assets you track (but don't own yet), each shown with its live
 * "setup" signal (RSI, trend vs SMA200, 52w range, ADX) so you can see what's
 * setting up for an entry. Technical signals, not recommendations.
 */
const WATCHLIST_API = window.API_BASE_URL || '/api';

// ⭐ Favorite / watchlist quick-toggle — reusable across the app (asset-detail
// page, deep-analysis modal). One click adds the asset to the watchlist, another
// removes it. Relies on the idempotent POST (get-or-create, returns the id), so
// it works with no prior lookup; the light /watchlist/ids endpoint, when present,
// is used only to paint the correct INITIAL state (☆ vs ⭐).
let _watchIdsCache = null;
async function _watchIds(force) {
    if (_watchIdsCache && !force) return _watchIdsCache;
    try {
        const r = await fetch(`${WATCHLIST_API}/watchlist/ids`);
        if (r.ok) {
            const items = (await r.json()).items || [];
            _watchIdsCache = new Map(items.map(it => [String(it.ticker).toUpperCase(), it.id]));
            return _watchIdsCache;
        }
    } catch (e) { /* endpoint not deployed yet — degrade to no pre-check */ }
    return null;  // membership unknown
}

async function renderFavButton(container, ticker, name) {
    if (!container) return;
    const T = String(ticker || '').toUpperCase();
    if (!T) { container.innerHTML = ''; return; }
    container.innerHTML = `<button type="button" class="btn-action fav-btn">☆ Guardar en watchlist</button>`;
    const btn = container.querySelector('.fav-btn');
    const paint = (on) => {
        btn.dataset.on = on ? '1' : '0';
        btn.classList.toggle('is-fav', on);
        btn.innerHTML = on ? '⭐ En tu watchlist' : '☆ Guardar en watchlist';
        btn.title = on ? 'Quitar de la watchlist' : 'Guardar en la watchlist (favorito)';
    };
    paint(false);
    const ids = await _watchIds();
    if (ids && ids.has(T)) { btn.dataset.wid = ids.get(T); paint(true); }

    btn.addEventListener('click', async () => {
        const on = btn.dataset.on === '1';
        btn.disabled = true;
        btn.innerHTML = '…';
        try {
            if (on) {
                const id = btn.dataset.wid;
                if (id) await fetch(`${WATCHLIST_API}/watchlist/${id}`, { method: 'DELETE' });
                delete btn.dataset.wid;
                if (_watchIdsCache) _watchIdsCache.delete(T);
                paint(false);
            } else {
                const r = await fetch(`${WATCHLIST_API}/watchlist`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ticker: T, name: name || '' }),
                });
                if (!r.ok) throw new Error();
                const d = await r.json();
                btn.dataset.wid = d.id;
                if (_watchIdsCache) _watchIdsCache.set(T, d.id);
                paint(true);
            }
        } catch (e) {
            btn.innerHTML = '⚠️ No se pudo';
            setTimeout(() => paint(btn.dataset.on === '1'), 1500);
        }
        btn.disabled = false;
    });
}
window.renderFavButton = renderFavButton;

// ===== 📌 Chinchetas (pins): date+price snapshots per watched asset =====
// One asset can have many pins over time; each captures the price server-side at
// the moment you pin it, so you can track evolution from the day it caught your eye.
async function pinAsset(ticker, note) {
    const r = await fetch(`${WATCHLIST_API}/watchlist/${encodeURIComponent(ticker)}/pin`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note: note || '' }),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
}
async function fetchPins(ticker) {
    const r = await fetch(`${WATCHLIST_API}/watchlist/${encodeURIComponent(ticker)}/pins`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return (await r.json()).items || [];
}
async function deletePin(pinId) {
    const r = await fetch(`${WATCHLIST_API}/watchlist/pins/${pinId}`, { method: 'DELETE' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return true;
}
async function _currentPriceFor(ticker) {
    try {
        const r = await fetch(`${WATCHLIST_API}/asset/${encodeURIComponent(ticker)}/history?period=5d&asset_type=auto`, { cache: 'no-store' });
        if (!r.ok) return null;
        const d = await r.json();
        if (d.current && d.current.price != null) return d.current.price;
        const h = d.history || [];
        return h.length ? (h[h.length - 1].close ?? h[h.length - 1].price) : null;
    } catch (e) { return null; }
}

// Render the pins panel for one ticker: a "📌 Fijar precio de hoy" button + the
// list of existing pins (date · price · Δ% vs ahora), each removable. Degrades to
// a friendly note if the backend endpoints aren't deployed yet.
async function renderPinsSection(container, ticker, opts = {}) {
    if (!container) return;
    const T = String(ticker || '').toUpperCase();
    container.innerHTML = `
        <div class="pins-head">
            <button type="button" class="btn-secondary pin-add-btn">📌 Fijar precio de hoy</button>
            <span class="pins-msg" style="font-size:12px;"></span>
        </div>
        <div class="pins-list"></div>`;
    const addBtn = container.querySelector('.pin-add-btn');
    const msg = container.querySelector('.pins-msg');
    const listEl = container.querySelector('.pins-list');
    let current = opts.currentPrice != null ? opts.currentPrice : null;

    async function paint() {
        let pins;
        try { pins = await fetchPins(T); }
        catch (e) {
            listEl.innerHTML = '<p class="text-muted" style="font-size:12px; margin:6px 0 0;">Las chinchetas estarán disponibles en cuanto se actualice la app (recarga en unos minutos).</p>';
            addBtn.disabled = true;
            return;
        }
        if (current == null) current = await _currentPriceFor(T);
        if (!pins.length) {
            listEl.innerHTML = '<p class="text-muted" style="font-size:12px; margin:6px 0 0;">Sin chinchetas. Pulsa «📌 Fijar precio de hoy» para empezar a seguirlo desde hoy.</p>';
            return;
        }
        const money = (p) => p.price == null ? '—'
            : (+p.price).toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + (p.currency ? ' ' + p.currency : '');
        listEl.innerHTML = pins.map(p => {
            const date = (p.pinned_at || '').slice(0, 10);
            // pin.price and `current` are both in the asset's native currency (Yahoo
            // quote), so the % is apples-to-apples without any FX conversion.
            const chg = (current != null && p.price) ? ((current - p.price) / p.price * 100) : null;
            const chgHtml = chg == null ? '' : `<span class="mono ${chg >= 0 ? 'value-positive' : 'value-negative'}" title="Variación desde que la fijaste">${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%</span>`;
            const note = p.note ? ` <span class="text-muted">— ${(p.note + '').replace(/</g, '&lt;')}</span>` : '';
            return `<div class="pin-row">
                <span>📌 <strong>${date}</strong> · ${money(p)}${note}</span>
                <span style="display:flex; gap:10px; align-items:center;">${chgHtml}<button type="button" class="pin-del" title="Quitar chincheta" data-pin="${p.id}">✕</button></span>
            </div>`;
        }).join('');
        listEl.querySelectorAll('.pin-del').forEach(b => b.addEventListener('click', async () => {
            b.disabled = true;
            try { await deletePin(b.dataset.pin); await paint(); } catch (e) { b.disabled = false; }
        }));
    }

    addBtn.addEventListener('click', async () => {
        addBtn.disabled = true; msg.textContent = 'Fijando…'; msg.style.color = 'var(--text-secondary)';
        try {
            const p = await pinAsset(T, '');
            // Ensure it's also in the watchlist (pinning implies tracking).
            if (_watchIdsCache && !_watchIdsCache.has(T)) { try { await fetch(`${WATCHLIST_API}/watchlist`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ticker: T }) }); } catch (e) {} }
            const captured = (p && p.price != null)
                ? p.price.toLocaleString('es-ES', { maximumFractionDigits: 2 }) + (p.currency ? ' ' + p.currency : '')
                : 'precio no disponible';
            msg.textContent = `✓ Guardada (${captured})`;
            msg.style.color = 'var(--positive)';
            await paint();
        } catch (e) {
            msg.textContent = 'No se pudo fijar ahora.'; msg.style.color = 'var(--negative)';
        }
        setTimeout(() => { msg.textContent = ''; }, 3500);
        addBtn.disabled = false;
    });

    paint();
}
window.renderPinsSection = renderPinsSection;

// Expand/collapse a watchlist row's pins panel (loaded lazily on first open).
function toggleWatchPins(ticker, price) {
    const T = String(ticker);
    const row = document.getElementById(`wpins-row-${T}`);
    if (!row) return;
    row.hidden = !row.hidden;
    if (!row.hidden && !row.dataset.loaded) {
        row.dataset.loaded = '1';
        renderPinsSection(document.getElementById(`wpins-${T}`), T, { currentPrice: price });
    }
}
window.toggleWatchPins = toggleWatchPins;

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
            <td><span class="ticker-link" onclick="showAssetDetail('${it.ticker}')" style="cursor:pointer;" title="Ver detalle de ${(it.name || it.ticker).replace(/"/g, '&quot;')}">${it.name} <span class="text-muted mono" style="font-size:11px;">${it.ticker}</span></span>${it.note ? `<br><span class="text-muted" style="font-size:11px;">${it.note}</span>` : ''}</td>
            <td data-watch-spark="${it.ticker}"></td>
            <td class="text-right mono">${it.price != null ? num(it.price, 2) : '—'}</td>
            <td class="text-right mono ${(it.ret_3m || 0) >= 0 ? 'value-positive' : 'value-negative'}">${it.ret_3m != null ? (it.ret_3m >= 0 ? '+' : '') + it.ret_3m + '%' : '—'}</td>
            <td class="text-right mono">${it.rsi != null ? num(it.rsi, 0) : '—'}</td>
            <td class="text-right mono">${it.range_pos_52w != null ? num(it.range_pos_52w, 0) + '%' : '—'}</td>
            <td class="text-right mono">${it.adx != null ? num(it.adx, 0) : '—'}</td>
            <td style="color:${color}; font-weight:600;">${it.setup}</td>
            <td class="text-right" style="white-space:nowrap;">
                <button class="btn-secondary" style="background:transparent; padding:2px 8px;" onclick="toggleWatchPins('${it.ticker}', ${it.price != null ? it.price : 'null'})" title="Chinchetas de seguimiento (fecha y precio)">📌</button>
                <button class="btn-secondary" style="background:transparent; color:var(--negative); padding:2px 8px;" onclick="deleteWatch(${it.id})" title="Quitar">✕</button>
            </td>
        </tr>
        <tr class="pins-expand-row" id="wpins-row-${it.ticker}" hidden><td colspan="9"><div id="wpins-${it.ticker}"></div></td></tr>`;
    }).join('');
    return `<div class="card"><div class="table-container"><table class="manager-table">
        <thead><tr><th>Activo</th><th>Tendencia (1m)</th><th class="text-right">Precio</th><th class="text-right">3m</th><th class="text-right">RSI</th><th class="text-right">Rango 52s</th><th class="text-right">ADX</th><th>Setup</th><th></th></tr></thead>
        <tbody>${rows}</tbody></table></div>
        <p class="text-muted" style="font-size:10.5px; margin:8px 0 0;">Setup: 🟢 posible entrada · 🔵 fuerza/ruptura · 🟡 cerca de mínimos · gris sin setup claro. Son señales técnicas objetivas, no una recomendación. · 📌 abre las chinchetas de seguimiento (fecha y precio de cada día que lo marcaste).</p>
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
