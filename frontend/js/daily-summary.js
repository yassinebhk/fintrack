/**
 * 📅 Resumen diario — historical record of the 08:00 portfolio summary.
 * Table of every day (value, day change, total P/L) from snapshots; days captured
 * from now on can be expanded to the full breakdown exactly as sent to Telegram.
 */
const DAILY_API = window.API_BASE_URL || '/api';

async function loadDailySummary() {
    const el = document.getElementById('dailySummaryContent');
    if (!el) return;
    el.innerHTML = '<p class="text-muted">Cargando histórico…</p>';
    let items = [];
    try {
        const r = await fetch(`${DAILY_API}/portfolio/daily-summaries?days=120`);
        if (r.ok) items = (await r.json()).summaries || [];
    } catch (e) { /* handled below */ }
    if (!items.length) {
        el.innerHTML = '<p class="text-muted">Aún no hay historial. Se irá llenando cada día con el resumen de las 8:00.</p>';
        return;
    }
    el.innerHTML = dailySummaryHtml(items);
}

function dailySummaryHtml(items) {
    const val = (v) => (v == null ? '—' : v.toLocaleString('es-ES', { maximumFractionDigits: 2 }) + ' €');
    const eur = (v) => (v == null ? '—' : (v >= 0 ? '+' : '') + v.toLocaleString('es-ES', { maximumFractionDigits: 2 }) + ' €');
    const pct = (v) => (v == null ? '' : (v >= 0 ? '+' : '') + v.toFixed(2) + '%');
    const cls = (v) => (v == null ? '' : v >= 0 ? 'value-positive' : 'value-negative');

    const rows = items.map((it, i) => {
        const has = !!it.html;
        const id = `ds-detail-${i}`;
        const detailStyle = 'white-space:pre-wrap; font-family:var(--font-mono); font-size:12px; line-height:1.5; overflow-x:auto; background:rgba(43,40,34,0.04); border-radius:8px; padding:12px; margin:4px 0;';
        return `<tr ${has ? `onclick="toggleDailyDetail('${id}')" style="cursor:pointer;" title="Ver desglose"` : ''}>
            <td>${it.date}${has ? ' <span class="text-muted" style="font-size:11px;">▾ ver</span>' : ''}</td>
            <td class="text-right mono">${val(it.total_value)}</td>
            <td class="text-right mono ${cls(it.daily_change)}">${eur(it.daily_change)} <span class="text-muted">(${pct(it.daily_change_pct)})</span></td>
            <td class="text-right mono ${cls(it.total_gain_loss)}">${eur(it.total_gain_loss)} <span class="text-muted">(${pct(it.total_gain_loss_pct)})</span></td>
        </tr>
        ${has ? `<tr id="${id}" hidden><td colspan="4"><div style="${detailStyle}">${it.html}</div></td></tr>` : ''}`;
    }).join('');

    return `<div class="card"><div class="table-container"><table class="manager-table">
        <thead><tr><th>Fecha</th><th class="text-right">Valor</th><th class="text-right">Δ día</th><th class="text-right">P/L total</th></tr></thead>
        <tbody>${rows}</tbody></table></div>
        <p class="text-muted" style="font-size:11px; margin:8px 0 0;">Toca un día con "▾ ver" para el desglose completo (posiciones), igual que en Telegram. Los días previos a hoy muestran solo el titular; el detalle se archiva de ahora en adelante.</p>
    </div>`;
}

function toggleDailyDetail(id) {
    const el = document.getElementById(id);
    if (el) el.hidden = !el.hidden;
}

document.addEventListener('DOMContentLoaded', () => {
    const link = document.querySelector('[data-page="daily-summary"]');
    if (link) link.addEventListener('click', () => setTimeout(loadDailySummary, 150));
    setTimeout(() => {
        const p = document.getElementById('page-daily-summary');
        if (p && p.classList.contains('active')) loadDailySummary();
    }, 500);
});
