/**
 * Opportunities page - AI market analyst suggestions.
 */
const OPP_API = (window.API_BASE_URL || 'http://localhost:8000/api');
let oppLoaded = false;

const OPP_THINKING_STEPS = [
    '🧠 La herramienta está pensando…',
    '🔎 Escaneando ~130 ETFs/fondos y screeners del mercado…',
    '📊 Calculando momentum, Sharpe y RSI (motor cuantitativo)…',
    '📰 Cruzando con las noticias recientes…',
    '🧩 Redactando las oportunidades y sus gráficas…',
];
let oppThinkingTimer = null;

function startOppThinking() {
    const msg = document.getElementById('oppLoadingMsg');
    let i = 0;
    if (msg) msg.textContent = OPP_THINKING_STEPS[0];
    oppThinkingTimer = setInterval(() => {
        i = (i + 1) % OPP_THINKING_STEPS.length;
        if (msg) msg.textContent = OPP_THINKING_STEPS[i];
    }, 3500);
}

function stopOppThinking() {
    if (oppThinkingTimer) { clearInterval(oppThinkingTimer); oppThinkingTimer = null; }
}

async function loadOpportunities(force = false) {
    const btn = document.getElementById('oppRefreshBtn');
    const loading = document.getElementById('oppLoading');
    const content = document.getElementById('oppContent');
    btn.disabled = true;
    loading.style.display = 'block';
    startOppThinking();
    if (force) content.innerHTML = '';

    try {
        const resp = await fetch(`${OPP_API}/opportunities${force ? '?force=true' : ''}`);
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);
        renderOpportunities(data);
        oppLoaded = true;
    } catch (err) {
        content.innerHTML = `<div class="alert alert-error">No se pudieron cargar las oportunidades: ${err.message}</div>`;
    } finally {
        stopOppThinking();
        btn.disabled = false;
        loading.style.display = 'none';
    }
}

function renderOpportunities(data) {
    const content = document.getElementById('oppContent');
    const convColor = { alta: '#10b981', media: '#f59e0b', baja: '#64748b' };
    const kindIcon = { tema: '🌐', etf: '📊', fondo: '💼', sector: '🏭' };

    const opps = (data.opportunities || []).map(op => {
        const color = convColor[op.conviction] || '#f59e0b';
        const icon = kindIcon[op.kind] || '💡';
        const apprStyle = op.approach === 'momentum' ? 'background:#ef444422; color:#ef4444;' : 'background:#3b82f622; color:#3b82f6;';
        const apprLabel = op.approach === 'momentum' ? '🔥 momentum' : (op.approach ? '🧊 ' + op.approach : '');
        return `
        <div class="card" style="margin-bottom:14px; border-left:3px solid ${color};">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:8px;">
                <h3 style="margin:0;">${icon} ${op.name}${op.ticker_or_isin ? ` <span class="text-muted" style="font-size:13px;">${op.ticker_or_isin}</span>` : ''}</h3>
                <div style="display:flex; gap:6px; flex-wrap:wrap; justify-content:flex-end;">
                    ${apprLabel ? `<span style="${apprStyle} padding:2px 10px; border-radius:12px; font-size:12px; white-space:nowrap;">${apprLabel}</span>` : ''}
                    <span style="background:${color}22; color:${color}; padding:2px 10px; border-radius:12px; font-size:12px; white-space:nowrap;">convicción ${op.conviction}</span>
                </div>
            </div>
            ${op.chart_url ? `<img src="${op.chart_url}" alt="Tendencia 6 meses de ${op.name}" loading="lazy" style="width:100%; max-width:560px; border-radius:8px; margin:10px 0; display:block;">` : ''}
            <p style="margin:8px 0 4px;"><strong>Qué es:</strong> ${op.what_it_is}</p>
            <p style="margin:4px 0;"><strong>📈 Por qué ahora:</strong> ${op.why_now}</p>
            <p style="margin:4px 0;"><strong>⚠️ Riesgos:</strong> ${op.risks}</p>
            <p style="margin:4px 0;"><strong>🎯 Encaje en tu cartera:</strong> ${op.fit}</p>
            ${(op.news && op.news.length) ? `<div style="margin-top:8px; padding-top:8px; border-top:1px solid rgba(255,255,255,0.08);"><strong style="font-size:13px;">📰 Noticias que lo respaldan:</strong><ul style="margin:6px 0 0; padding-left:18px; font-size:13px;">${op.news.map(n => `<li><a href="${n.url}" target="_blank" rel="noopener" style="color:#60a5fa;">${n.title}</a> <span class="text-muted">(${n.source})</span></li>`).join('')}</ul></div>` : ''}
        </div>`;
    }).join('');

    const fmtScore = (s) => {
        if (s == null) return '<span class="text-muted">—</span>';
        const cls = s >= 0 ? 'value-positive' : 'value-negative';
        return `<span class="mono ${cls}">${s >= 0 ? '+' : ''}${s.toFixed(2)}</span>`;
    };
    const themes = (data.themes || []).slice(0, 10).map(t => {
        const r3 = t.ret_3m, cls = (r3 || 0) >= 0 ? 'value-positive' : 'value-negative';
        return `<tr><td>${t.theme}</td><td class="text-right">${fmtScore(t.momentum_score)}</td><td class="text-right">${fmtScore(t.value_score)}</td><td class="text-right mono ${cls}">${r3 != null ? (r3>=0?'+':'')+r3+'%' : '—'}</td><td class="text-right mono">${t.range_pos_52w != null ? t.range_pos_52w.toFixed(0)+'%' : '—'}</td></tr>`;
    }).join('');

    content.innerHTML = `
        ${data.market_summary ? `<div class="integrations-banner-inner" style="margin-bottom:16px;"><div class="integrations-banner-icon">🧠</div><div class="integrations-banner-body"><strong>Resumen de mercado</strong><p style="margin:6px 0 0;">${data.market_summary}</p></div></div>` : ''}
        ${opps}
        <div class="card" style="margin-top:16px;">
            <h3>📊 Ranking cuantitativo (motor empyrical + ta, datos reales)</h3>
            <p class="text-muted" style="font-size:12px; margin:-4px 0 10px;">${data.universe_size ? `Escaneados <strong>${data.universe_size}</strong> instrumentos (ETFs/fondos + screeners de Yahoo), excluyendo lo que ya tienes. ` : ''}Puntuación objetiva por estadística sobre precios, no opinión de la IA. Score Mom. = tendencia + retorno ajustado a riesgo · Score Valor = castigado pero de calidad.</p>
            <div class="table-container">
                <table class="manager-table">
                    <thead><tr><th>Tema</th><th class="text-right">Score Mom.</th><th class="text-right">Score Valor</th><th class="text-right">3 meses</th><th class="text-right">Rango 52s</th></tr></thead>
                    <tbody>${themes}</tbody>
                </table>
            </div>
        </div>
        ${data.disclaimer ? `<p class="text-muted" style="font-size:11px; margin-top:12px;">${data.disclaimer}</p>` : ''}
        <p class="text-muted" style="font-size:11px;">Generado ${data.generated_at ? new Date(data.generated_at).toLocaleString('es-ES') : ''} · modelo ${data.model || ''}</p>
    `;
}

document.addEventListener('DOMContentLoaded', () => {
    const nav = document.querySelector('[data-page="opportunities"]');
    if (nav) nav.addEventListener('click', () => { if (!oppLoaded) loadOpportunities(false); });
});
