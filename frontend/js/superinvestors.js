/**
 * 🏆 Superinversores — carteras públicas (informes 13F de la SEC) de los mejores
 * gestores de valor, como pozo de ideas a LARGO PLAZO. Datos de /api/superinvestors.
 * No son señales de corto plazo (para eso están los screeners de momentum/setups).
 */
const SUPERINV_API = window.API_BASE_URL || '/api';

async function loadSuperinvestors() {
    const el = document.getElementById('superinvestorsContent');
    if (!el) return;
    el.innerHTML = '<p class="text-muted">Cargando carteras de superinversores…</p>';
    try {
        const r = await fetch(`${SUPERINV_API}/superinvestors`, { cache: 'no-store' });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        el.innerHTML = renderSuperinvestors(await r.json());
    } catch (e) {
        el.innerHTML = `<p class="text-muted" style="color:var(--negative);">No se pudieron cargar ahora mismo (${e.message}). Reintenta en un momento.</p>`;
    }
}

function renderSuperinvestors(data) {
    const managers = (data && data.managers) || [];
    if (!managers.length) return '<p class="text-muted">Sin datos de superinversores todavía.</p>';
    const wHtml = (w) => w == null ? '' : `<span class="si-weight" title="Peso en la cartera del gestor">${w}%</span>`;
    const cards = managers.map(m => {
        const rows = m.holdings.map(h => `
            <li class="si-holding">
                <span class="ticker-link" onclick="showAssetDetail('${h.ticker}')" style="cursor:pointer;" title="Ver detalle de ${(h.name || h.ticker).replace(/"/g, '&quot;')}">
                    <strong>${h.name}</strong> <span class="text-muted mono" style="font-size:11px;">${h.ticker}</span>
                </span>
                ${wHtml(h.weight)}
            </li>`).join('');
        return `<div class="card si-card">
            <div class="si-card-head">
                <h3 style="margin:0; font-size:16px;">🏆 ${m.name}</h3>
                <span class="text-muted" style="font-size:12px; white-space:nowrap;">${m.count} posiciones</span>
            </div>
            ${m.about ? `<p class="text-muted" style="font-size:12.5px; margin:4px 0 10px;">${m.about}</p>` : ''}
            <ul class="si-holdings">${rows}</ul>
        </div>`;
    }).join('');
    return `<div class="si-intro card" style="margin:0 0 16px;">
        <p style="margin:0 0 6px; font-size:13px;"><strong>¿De dónde salen?</strong> De los informes <strong>13F</strong> que la SEC obliga a publicar cada trimestre a los grandes gestores de EE.UU. (vía Dataroma, agregador público). Magallanes es un <em>snapshot</em> manual (España no tiene 13F). Son ideas de <strong>largo plazo</strong>, no señales de corto — pincha cualquier activo para su análisis profesional.</p>
        <p class="text-muted" style="margin:0; font-size:11.5px;"><strong>Seleccionados por rentabilidad real, no por fama.</strong> Descartados con motivo: Klarman (~4%/año 2014-24), Ackman (2026 −9,1% YTD), Pabrai y Akre (bajo rendimiento reciente), Horos AM (continuidad de histórico), True Value (5 años en negativo).</p>
    </div>
    <div class="si-grid">${cards}</div>`;
}

document.addEventListener('DOMContentLoaded', () => {
    const link = document.querySelector('[data-page="superinvestors"]');
    if (link) link.addEventListener('click', () => setTimeout(loadSuperinvestors, 120));
    setTimeout(() => {
        const p = document.getElementById('page-superinvestors');
        if (p && p.classList.contains('active')) loadSuperinvestors();
    }, 500);
});
