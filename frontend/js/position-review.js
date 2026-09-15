/**
 * 🔄 ¿Vender o mantener? — objective keep/watch/trim/rotate signal per holding,
 * horizon-aware (largo/medio/corto) and forward-looking (NOT based on your entry
 * price), with the reasons why and disposition-effect bias warnings.
 */
const REVIEW_API = window.API_BASE_URL || '/api';

const SIGNAL_META = {
    MANTENER: { emoji: '🟢', label: 'Mantener', color: 'var(--positive)' },
    VIGILAR:  { emoji: '🟡', label: 'Vigilar',  color: 'var(--warning)' },
    REDUCIR:  { emoji: '🟠', label: 'Reducir',  color: '#E08A3C' },
    ROTAR:    { emoji: '🔴', label: 'Rotar / vender', color: 'var(--negative)' },
    SIN_DATOS:{ emoji: '⚪', label: 'Sin datos', color: 'var(--text-secondary)' },
};

async function loadPositionReview(force = false) {
    const el = document.getElementById('positionReviewContent');
    if (!el) return;
    el.innerHTML = '<p class="text-muted">Analizando tus posiciones…</p>';
    let data = null;
    try {
        const r = await fetch(`${REVIEW_API}/positions/review${force ? '?force=true' : ''}`, { cache: 'no-store' });
        if (r.ok) data = await r.json();
    } catch (e) { /* handled below */ }
    if (!data || !(data.reviews || []).length) {
        el.innerHTML = '<p class="text-muted">No pude analizar las posiciones ahora mismo.</p>';
        return;
    }
    el.innerHTML = reviewHtml(data);
    const ex = document.getElementById('positionReviewExport');
    if (ex && window.exportToolbarHTML) ex.innerHTML = exportToolbarHTML('positionReviewContent', 'vender-o-mantener');
}

function reviewHtml(data) {
    const s = data.summary || {};
    const pct = (v) => (v == null ? '—' : (v >= 0 ? '+' : '') + (+v).toFixed(1) + '%');
    const cls = (v) => (v == null ? '' : v >= 0 ? 'value-positive' : 'value-negative');

    const banner = `<div class="card" style="margin-bottom:16px;">
        <h3>🔄 ¿Vender o mantener?</h3>
        <p class="text-muted" style="font-size:13px; margin:6px 0 10px;">
            Señal por posición mirando <strong>hacia delante</strong> (salud del activo + tu concentración), <strong>no</strong> tu precio de entrada.
            Depende del <strong>horizonte</strong> que le pongas a cada activo. No es una orden — decide tú.</p>
        <div style="display:flex; gap:14px; flex-wrap:wrap; font-size:13px;">
            <span>🔴 Rotar <strong>${s.rotar || 0}</strong></span>
            <span>🟠 Reducir <strong>${s.reducir || 0}</strong></span>
            <span>🟡 Vigilar <strong>${s.vigilar || 0}</strong></span>
            <span>🟢 Mantener <strong>${s.mantener || 0}</strong></span>
        </div>
    </div>`;

    const cards = data.reviews.map((r) => {
        const meta = SIGNAL_META[r.signal] || SIGNAL_META.SIN_DATOS;
        const hz = r.horizon || 'medio';
        const opt = (v, lbl) => `<option value="${v}"${hz === v ? ' selected' : ''}>${lbl}</option>`;
        const reasons = (r.reasons || []).map((x) => `<li>${x}</li>`).join('');
        const bias = r.bias_flag ? `<div style="margin-top:8px; background:rgba(198,71,60,0.10); border:1px solid rgba(198,71,60,0.35); border-radius:8px; padding:8px 12px; font-size:12.5px;">${r.bias_flag}</div>` : '';
        const m = r.metrics || {};
        const metricsLine = (r.signal !== 'SIN_DATOS') ? `<div class="text-muted" style="font-size:11.5px; margin-top:8px;">
            ${m.above_sma200 != null ? (m.above_sma200 ? '📈 sobre media 200' : '📉 bajo media 200') : ''}
            ${m.rsi != null ? ` · RSI ${Math.round(m.rsi)}` : ''}
            ${m.momentum_pct != null ? ` · momentum ${pct(m.momentum_pct)}` : ''}
            ${m.drawdown_from_peak_pct != null ? ` · desde máx ${(+m.drawdown_from_peak_pct).toFixed(0)}%` : ''}
        </div>` : '';
        const dim = r.immaterial ? 'opacity:0.6;' : '';
        return `<div class="card" style="margin-bottom:12px; border-left:3px solid ${meta.color}; ${dim}">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:8px; flex-wrap:wrap;">
                <div>
                    <strong>${meta.emoji} ${meta.label}</strong> ·
                    ${r.name} <span class="text-muted mono" style="font-size:11px;">${r.ticker}</span>
                    <div class="text-muted" style="font-size:11.5px; margin-top:2px;">
                        Peso ${r.weight_pct != null ? r.weight_pct + '%' : '—'}
                        ${r.pnl_pct != null ? ` · P/L <span class="${cls(r.pnl_pct)}">${pct(r.pnl_pct)}</span>` : ''}
                        ${r.value_eur != null ? ` · ${(+r.value_eur).toLocaleString('es-ES', { maximumFractionDigits: 0 })} €` : ''}
                    </div>
                </div>
                <label style="font-size:12px; white-space:nowrap;">Horizonte
                    <select onchange="setHorizon('${(r.ticker + '').replace(/'/g, '')}', this.value)" style="margin-left:4px;">
                        ${opt('largo', 'Largo')}${opt('medio', 'Medio')}${opt('corto', 'Corto')}
                    </select>${r.horizon_is_default ? ' <span class="text-muted" style="font-size:10px;">(auto)</span>' : ''}
                </label>
            </div>
            ${reasons ? `<ul style="margin:8px 0 0; padding-left:18px; font-size:13px;">${reasons}</ul>` : ''}
            ${bias}
            ${metricsLine}
        </div>`;
    }).join('');

    return banner + cards;
}

async function setHorizon(ticker, horizon) {
    try {
        await fetch(`${REVIEW_API}/positions/review/horizon`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ticker, horizon }),
        });
        await loadPositionReview(true); // recompute with the new horizon
    } catch (e) { /* noop */ }
}

document.addEventListener('DOMContentLoaded', () => {
    const link = document.querySelector('[data-page="position-review"]');
    if (link) link.addEventListener('click', () => setTimeout(loadPositionReview, 150));
    setTimeout(() => {
        const p = document.getElementById('page-position-review');
        if (p && p.classList.contains('active')) loadPositionReview();
    }, 500);
});
