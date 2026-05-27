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

const CRITERION_LABEL = {
    momentum: 'Momentum (tendencia)',
    regimen: 'Régimen (sobre 200d)',
    riesgo: 'Riesgo (Sharpe)',
    tecnico: 'Técnico (RSI/MACD)',
    volatilidad: 'Volatilidad (EWMA)',
    infravaloracion: 'Infravaloración',
    reversion: 'Reversión a la media',
    sobreventa: 'Sobreventa (RSI)',
    calidad: 'Calidad (Sharpe)',
};

function renderBreakdown(op) {
    const bd = op.score_breakdown;
    if (!bd || !Object.keys(bd).length) return '';
    const maxAbs = Math.max(...Object.values(bd).map(v => Math.abs(v)), 0.01);
    const rows = Object.entries(bd).map(([k, v]) => {
        const pct = Math.round(Math.abs(v) / maxAbs * 100);
        const pos = v >= 0;
        const barColor = pos ? '#10b981' : '#ef4444';
        return `<div style="display:flex; align-items:center; gap:8px; margin:3px 0; font-size:12px;">
            <span style="flex:0 0 150px; color:#94a3b8;">${CRITERION_LABEL[k] || k}</span>
            <span style="flex:1; background:rgba(255,255,255,0.05); border-radius:4px; height:10px; position:relative;">
                <span style="position:absolute; left:0; top:0; height:10px; width:${pct}%; background:${barColor}; border-radius:4px;"></span>
            </span>
            <span class="mono" style="flex:0 0 46px; text-align:right; color:${barColor};">${pos ? '+' : ''}${v.toFixed(2)}</span>
        </div>`;
    }).join('');
    return `<details style="margin-top:8px; padding-top:8px; border-top:1px solid rgba(255,255,255,0.08);">
        <summary style="cursor:pointer; font-size:13px; color:#cbd5e1;">🧮 Por qué lo puntúa así (criterios que convergen)</summary>
        <div style="margin-top:8px;">${rows}</div>
    </details>`;
}

function renderOpportunities(data) {
    const content = document.getElementById('oppContent');
    const convColor = { alta: '#10b981', media: '#f59e0b', baja: '#64748b' };
    const kindIcon = { tema: '🌐', etf: '📊', fondo: '💼', sector: '🏭' };
    const regimeColor = { alcista: '#10b981', bajista: '#ef4444', neutral: '#f59e0b' };

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
            ${renderBreakdown(op)}
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

    const rc = regimeColor[data.market_regime] || '#f59e0b';
    const regimeBanner = data.market_regime ? `<div style="margin-bottom:12px; padding:8px 14px; border-radius:8px; background:${rc}18; border:1px solid ${rc}44; font-size:13px;">📡 <strong>Régimen de mercado:</strong> <span style="color:${rc}; text-transform:uppercase; font-weight:600;">${data.market_regime}</span>${data.market_breadth != null ? ` · ${Math.round(data.market_breadth*100)}% de activos sobre su tendencia de 200 sesiones` : ''}<br><span class="text-muted" style="font-size:11px;">En régimen alcista pesa más el momentum; en bajista, el valor/defensivo.</span></div>` : '';

    const t = data.trends || {};
    const growRow = (g) => `<tr><td>${g.name} <span class="text-muted" style="font-size:12px;">${g.ticker}</span></td><td class="text-right mono ${(g.ret_3m||0)>=0?'value-positive':'value-negative'}">${g.ret_3m!=null?(g.ret_3m>=0?'+':'')+Math.round(g.ret_3m)+'%':'—'}</td><td class="text-right">${g.above_sma200?'📈':'📉'}</td></tr>`;
    const trendsCard = (t.top_growers_etf && t.top_growers_etf.length) ? `
        <div class="card" style="margin-bottom:16px;">
            <h3>🚀 Tendencias del momento — qué más ha crecido</h3>
            <p class="text-muted" style="font-size:12px; margin:-4px 0 10px;">Líderes de los últimos meses y los patrones que comparten. Es contexto: el ranking lo deciden los algoritmos; esto explica <em>qué tipo de activo</em> está funcionando (y avisa si está extendido).</p>
            <div style="display:flex; gap:16px; flex-wrap:wrap;">
                <div style="flex:1; min-width:240px;">
                    <strong style="font-size:13px;">📊 ETFs / fondos</strong>
                    <table class="manager-table" style="margin-top:6px;"><thead><tr><th>Activo</th><th class="text-right">3m</th><th class="text-right">Tend.</th></tr></thead><tbody>${(t.top_growers_etf||[]).map(growRow).join('')}</tbody></table>
                </div>
                ${(t.top_growers_crypto && t.top_growers_crypto.length) ? `<div style="flex:1; min-width:240px;"><strong style="font-size:13px;">₿ Cripto</strong><table class="manager-table" style="margin-top:6px;"><thead><tr><th>Activo</th><th class="text-right">3m</th><th class="text-right">Tend.</th></tr></thead><tbody>${t.top_growers_crypto.map(growRow).join('')}</tbody></table></div>` : ''}
            </div>
            ${(t.patterns && t.patterns.length) ? `<div style="margin-top:12px;"><strong style="font-size:13px;">🔁 Patrones comunes:</strong><ul style="margin:6px 0 0; padding-left:18px; font-size:13px;">${t.patterns.map(p => `<li>${p}</li>`).join('')}</ul></div>` : ''}
        </div>` : '';

    content.innerHTML = `
        ${regimeBanner}
        ${data.market_summary ? `<div class="integrations-banner-inner" style="margin-bottom:16px;"><div class="integrations-banner-icon">🧠</div><div class="integrations-banner-body"><strong>Resumen de mercado</strong><p style="margin:6px 0 0;">${data.market_summary}</p></div></div>` : ''}
        ${trendsCard}
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
