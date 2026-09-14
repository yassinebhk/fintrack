/**
 * 🎯 Eficacia de las recomendaciones — the out-of-sample scorecard made visible.
 * Every asset the engine recommends is tracked forward (1m/3m/6m) and its real
 * return + alpha vs its benchmark is measured here. This is the honest track
 * record: did following the recommendations actually work? Needs weeks/months of
 * history to be meaningful (small samples are flagged, not trusted).
 */
const SCORECARD_API = window.API_BASE_URL || '/api';

async function loadScorecard() {
    const el = document.getElementById('scorecardContent');
    if (!el) return;
    el.innerHTML = '<p class="text-muted">Cargando el histórico de aciertos…</p>';
    let data = null;
    try {
        const r = await fetch(`${SCORECARD_API}/scorecard`);
        if (r.ok) data = await r.json();
    } catch (e) { /* handled below */ }
    if (!data) { el.innerHTML = '<p class="text-muted">No pude cargar el scorecard ahora mismo.</p>'; return; }
    el.innerHTML = scorecardHtml(data);
    const ex = document.getElementById('scorecardExport');
    if (ex && window.exportToolbarHTML) ex.innerHTML = exportToolbarHTML('scorecardContent', 'eficacia-recomendaciones');
}

function scorecardHtml(d) {
    const total = d.total_recommendations_tracked || 0;
    const evaluated = d.evaluated_any || 0;
    const pct = (v) => (v == null ? '—' : (v >= 0 ? '+' : '') + v + '%');
    const cls = (v) => (v == null ? '' : v >= 0 ? 'value-positive' : 'value-negative');

    const header = `<div class="card" style="margin-bottom:16px;">
        <h3>🎯 Eficacia de las recomendaciones</h3>
        <p class="text-muted" style="font-size:13px; margin:6px 0 0;">
            Rendimiento de cada idea <strong>después</strong> de recomendarla (out-of-sample), frente a su índice.
            Se registran automáticamente todas las recomendaciones; esto es su acierto REAL.</p>
        <p style="font-size:14px; margin:10px 0 0;">
            <strong>${total}</strong> recomendaciones en seguimiento · <strong>${evaluated}</strong> ya con retorno medido.</p>
        ${evaluated < 5 ? `<div style="margin-top:10px; background:var(--warning)18; border:1px solid var(--warning)55; border-radius:8px; padding:8px 12px; font-size:13px;">⏳ Aún hay poco historial evaluado. El track record necesita semanas/meses para ser fiable — de momento tómalo como provisional.</div>` : ''}
    </div>`;

    // Horizons table
    const H = d.horizons || {};
    const hrow = (key) => {
        const h = H[key]; if (!h) return '';
        const ret = h.return, al = h.alpha_vs_benchmark;
        return `<tr>
            <td><strong>${h.label}</strong></td>
            <td class="text-right mono">${ret ? ret.n : '—'}</td>
            <td class="text-right mono">${ret ? ret.hit_rate_pct + '%' : '—'}</td>
            <td class="text-right mono ${ret ? cls(ret.avg) : ''}">${ret ? pct(ret.avg) : '—'}</td>
            <td class="text-right mono ${al ? cls(al.avg) : ''}">${al ? pct(al.avg) : '—'}</td>
        </tr>`;
    };
    const horizonCard = `<div class="card" style="margin-bottom:16px;">
        <h3>📅 Por horizonte</h3>
        <div class="table-container"><table class="manager-table">
            <thead><tr><th>Horizonte</th><th class="text-right">N</th><th class="text-right">% aciertos</th><th class="text-right">Retorno medio</th><th class="text-right">Alpha vs índice</th></tr></thead>
            <tbody>${['ret_1m','ret_3m','ret_6m'].map(hrow).join('')}</tbody>
        </table></div>
        <p class="text-muted" style="font-size:11px; margin:8px 0 0;">Alpha = exceso sobre su índice de referencia. Un alpha positivo significa que la idea batió a su mercado, no solo que subió.</p>
    </div>`;

    // Breakdown by approach / conviction (3m)
    const bd = (obj, title, subtitle) => {
        const entries = Object.entries(obj || {}).filter(([, v]) => v);
        if (!entries.length) return '';
        const rows = entries.map(([k, v]) => `<tr>
            <td>${k}</td>
            <td class="text-right mono">${v.n}</td>
            <td class="text-right mono">${v.hit_rate_pct}%</td>
            <td class="text-right mono ${cls(v.expectancy)}">${pct(v.expectancy)}</td>
        </tr>`).join('');
        return `<div class="card" style="margin-bottom:16px; flex:1; min-width:280px;">
            <h3>${title}</h3>
            <p class="text-muted" style="font-size:12px; margin:-4px 0 8px;">${subtitle}</p>
            <div class="table-container"><table class="manager-table">
                <thead><tr><th></th><th class="text-right">N</th><th class="text-right">% aciertos</th><th class="text-right">Retorno medio</th></tr></thead>
                <tbody>${rows}</tbody></table></div>
        </div>`;
    };
    const breakdowns = `<div style="display:flex; gap:16px; flex-wrap:wrap;">
        ${bd(d.by_approach_1m, '🎛️ Por enfoque (1m)', 'Madura ~3x más rápido que el de 3m — primera señal de alerta')}
        ${bd(d.by_conviction_1m, '💪 Por convicción (1m)', '¿Aciertan más las de convicción alta?')}
        ${bd(d.by_approach_3m, '🎛️ Por enfoque (3m)', 'Momentum vs valor/contrarian')}
        ${bd(d.by_conviction_3m, '💪 Por convicción (3m)', '¿Aciertan más las de convicción alta?')}
    </div>`;

    const note = d.note ? `<p class="text-muted" style="font-size:12px; margin-top:8px;">${d.note}</p>` : '';
    return header + horizonCard + breakdowns + note;
}

document.addEventListener('DOMContentLoaded', () => {
    const link = document.querySelector('[data-page="scorecard"]');
    if (link) link.addEventListener('click', () => setTimeout(loadScorecard, 150));
    setTimeout(() => {
        const p = document.getElementById('page-scorecard');
        if (p && p.classList.contains('active')) loadScorecard();
    }, 500);
});
