/**
 * Opportunities page - AI market analyst suggestions.
 */
const OPP_API = (window.API_BASE_URL || 'http://localhost:8000/api');
let oppLoaded = false;
let oppLastData = null;
let oppSort = { key: 'momentum_score', dir: 'desc' };

function oppSetSort(key) {
    if (oppSort.key === key) {
        oppSort.dir = oppSort.dir === 'desc' ? 'asc' : 'desc';
    } else {
        oppSort = { key, dir: 'desc' };
    }
    if (oppLastData) renderOpportunities(oppLastData);
}

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

let oppPollTimer = null;
let oppPollStart = 0;
let oppLastGeneratedAt = null;   // timestamp currently shown
let oppWaitSince = null;         // when forcing, ignore the (stale) cache with this timestamp
const OPP_POLL_MS = 6000;
const OPP_POLL_MAX_MS = 6 * 60 * 1000; // give up after ~6 min

async function fetchOpp(force) {
    // no-store so the browser never serves a stale cached API response
    const resp = await fetch(`${OPP_API}/opportunities${force ? '?force=true' : ''}`, { cache: 'no-store' });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);
    return data;
}

function endOppLoading() {
    stopOppThinking();
    if (oppPollTimer) { clearTimeout(oppPollTimer); oppPollTimer = null; }
    const btn = document.getElementById('oppRefreshBtn');
    const loading = document.getElementById('oppLoading');
    if (btn) btn.disabled = false;
    if (loading) loading.style.display = 'none';
}

function finishOpp(data) {
    renderOpportunities(data);
    oppLastGeneratedAt = data.generated_at || null;
    oppLoaded = true;
    endOppLoading();
}

// While forcing a refresh, the backend may keep serving the previous (still-fresh)
// cache until the new scan finishes. Treat that stale payload as "still generating".
function isStaleWhileForcing(data) {
    return oppWaitSince && data.status === 'ready' && data.generated_at === oppWaitSince;
}

function scheduleOppPoll() {
    // Still generating in the background — keep the spinner and check again soon.
    oppPollTimer = setTimeout(async () => {
        if (Date.now() - oppPollStart > OPP_POLL_MAX_MS) {
            document.getElementById('oppContent').innerHTML =
                '<div class="alert alert-error">El análisis está tardando más de lo normal. Vuelve a intentarlo en un momento.</div>';
            endOppLoading();
            return;
        }
        try {
            const data = await fetchOpp(false);
            if (data.status === 'generating' || data.status === 'stale' || isStaleWhileForcing(data)) { scheduleOppPoll(); return; }
            finishOpp(data);
        } catch (err) {
            // transient (e.g., instance busy) — keep trying until the max window
            scheduleOppPoll();
        }
    }, OPP_POLL_MS);
}

async function loadOpportunities(force = false) {
    const btn = document.getElementById('oppRefreshBtn');
    const loading = document.getElementById('oppLoading');
    const content = document.getElementById('oppContent');
    btn.disabled = true;
    loading.style.display = 'block';
    startOppThinking();
    oppPollStart = Date.now();
    oppWaitSince = force ? oppLastGeneratedAt : null;  // wait for a NEW result when forcing
    if (force) content.innerHTML = '';

    try {
        const data = await fetchOpp(force);
        if (data.status === 'generating' || isStaleWhileForcing(data)) {
            scheduleOppPoll();   // keep spinner, poll until ready — never hangs
            return;
        }
        if (data.status === 'stale') {
            // Show the last analysis now, but keep polling for the fresh one.
            renderOpportunities(data);
            oppLoaded = true;
            scheduleOppPoll();
            const c = document.getElementById('oppContent');
            if (c) c.insertAdjacentHTML('afterbegin',
                '<div class="alert" style="background:rgba(201, 154, 62, 0.13); border:1px solid rgba(201, 154, 62, 0.33); border-radius:8px; padding:8px 12px; margin-bottom:10px; font-size:13px;">⏳ Mostrando el último análisis mientras se genera uno nuevo…</div>');
            endOppLoading();
            return;
        }
        finishOpp(data);
    } catch (err) {
        content.innerHTML = `<div class="alert alert-error">No se pudieron cargar las oportunidades: ${err.message}</div>`;
        endOppLoading();
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
    // Fundamentales (solo acciones)
    calidad_fund: 'Calidad (ROE/márgenes)',
    crecimiento: 'Crecimiento (ventas/BPA)',
    valoracion_fund: 'Valoración (PER/PB, sector)',
    solidez: 'Solidez (deuda)',
    // Renta fija
    carry_bono: 'Carry real (yield−inflación, ajust. tipos)',
};

function assetLinks(op) {
    const tk = (op.ticker_or_isin || '').trim();
    if (!tk) return '';
    const q = encodeURIComponent(tk);
    const yahoo = `https://finance.yahoo.com/quote/${q}`;
    const justetf = `https://www.justetf.com/en/search.html?query=${q}`;
    const isFund = op.kind === 'etf' || op.kind === 'fondo';
    return `<div style="margin:8px 0 2px; font-size:13px;">🔗 <strong>Ver ficha del activo:</strong>
        <a href="${yahoo}" target="_blank" rel="noopener" style="color:var(--info);">precio actual e info (Yahoo Finance)</a>${isFund ? `
        · <a href="${justetf}" target="_blank" rel="noopener" style="color:var(--info);">ISIN y dónde comprar (justETF)</a>` : ''}
    </div>`;
}

function renderBreakdown(op) {
    const bd = op.score_breakdown;
    if (!bd || !Object.keys(bd).length) return '';
    const maxAbs = Math.max(...Object.values(bd).map(v => Math.abs(v)), 0.01);
    const rows = Object.entries(bd).map(([k, v]) => {
        const pct = Math.round(Math.abs(v) / maxAbs * 100);
        const pos = v >= 0;
        const barColor = pos ? 'var(--positive)' : 'var(--negative)';
        return `<div style="display:flex; align-items:center; gap:8px; margin:3px 0; font-size:12px;">
            <span style="flex:0 0 150px; color:var(--text-secondary);">${CRITERION_LABEL[k] || k}</span>
            <span style="flex:1; background:rgba(43, 40, 34, 0.05); border-radius:4px; height:10px; position:relative;">
                <span style="position:absolute; left:0; top:0; height:10px; width:${pct}%; background:${barColor}; border-radius:4px;"></span>
            </span>
            <span class="mono" style="flex:0 0 46px; text-align:right; color:${barColor};">${pos ? '+' : ''}${v.toFixed(2)}</span>
        </div>`;
    }).join('');
    return `<details style="margin-top:8px; padding-top:8px; border-top:1px solid rgba(43, 40, 34, 0.08);">
        <summary style="cursor:pointer; font-size:13px; color:var(--text-secondary);">🧮 Por qué lo puntúa así (criterios que convergen)</summary>
        <div style="margin-top:8px;">${rows}</div>
    </details>`;
}

// The per-idea decision frame: the 4 things a serious trader checks before
// investing — edge, quantified risk + position size, out-of-sample expectancy,
// and horizon. Every value comes from real data; expectancy is gated and shows
// "en validación" until the engine's own track record clears the anti-noise gate.
function renderDecision(op) {
    const r = op.risk || {};
    const ex = op.expectancy || {};
    const bd = op.score_breakdown || {};

    // Edge = the measurable drivers that most support the thesis (names only; the
    // full numeric contribution lives in the "Por qué lo puntúa así" breakdown).
    const drivers = Object.entries(bd).filter(([, v]) => v > 0).slice(0, 2).map(([k]) => CRITERION_LABEL[k] || k);
    const edgeLine = drivers.length
        ? `<div style="font-size:12.5px; margin-bottom:8px;"><strong>🎯 Edge medible${infoIcon('edge')}:</strong> ${drivers.join(' · ')} <span class="text-muted">(ver desglose abajo)</span></div>`
        : '';

    // Fundamentales (solo acciones): los ratios reales que justifican la tesis.
    const fu = op.fundamentals;
    let fundBlock = '';
    if (fu) {
        const pct = v => (v == null ? null : (v * 100).toFixed(0) + '%');
        const num = v => (v == null ? null : (+v).toFixed(1));
        const rows = [
            ['PER', num(fu.per), 'per'], ['P/B', num(fu.pb), 'pb'], ['ROE', pct(fu.roe), 'roe'],
            ['Margen', pct(fu.margin), 'margen'], ['Crec. ventas', pct(fu.rev_growth), 'crec_ventas'],
            ['Deuda/eq.', num(fu.debt_to_equity), 'debt_ratio'],
            ['Div.', fu.div_yield == null ? null : (+fu.div_yield).toFixed(1) + '%', 'dividend_yield'],
        ].filter(([, v]) => v != null);
        const chips = rows.map(([k, v, gk]) => `<span style="background:rgba(43,40,34,0.05); border-radius:6px; padding:2px 7px; font-size:11.5px; white-space:nowrap;">${k}${infoIcon(gk)} <strong>${v}</strong></span>`).join(' ');
        fundBlock = `<div style="margin:6px 0 8px;">
            <div style="font-size:11px; color:var(--text-secondary); margin-bottom:4px;">🏢 Fundamentales${fu.sector ? ` · <span class="text-muted">${fu.sector}</span>` : ''}</div>
            <div style="display:flex; gap:4px; flex-wrap:wrap;">${chips}</div>
        </div>`;
    }

    // Renta fija (bonos): yield, yield real, tramo de duración, sensibilidad a tipos.
    const bo = op.bond;
    let bondBlock = '';
    if (bo) {
        const brows = [
            ['Yield', bo.yield_pct == null ? null : bo.yield_pct + '%', 'yield_bono'],
            ['Yield real', bo.real_yield_pct == null ? null : bo.real_yield_pct + '%', 'yield_real'],
            ['Duración', bo.duration_bucket, 'duracion_bono'],
            ['Sensib. tipos', bo.rate_sensitivity == null ? null : 'β ' + (+bo.rate_sensitivity).toFixed(2), 'sensib_tipos'],
        ].filter(([, v]) => v != null);
        const bchips = brows.map(([k, v, gk]) => `<span style="background:rgba(43,40,34,0.05); border-radius:6px; padding:2px 7px; font-size:11.5px; white-space:nowrap;">${k}${infoIcon(gk)} <strong>${v}</strong></span>`).join(' ');
        bondBlock = `<div style="margin:6px 0 8px;">
            <div style="font-size:11px; color:var(--text-secondary); margin-bottom:4px;">🏦 Renta fija</div>
            <div style="display:flex; gap:4px; flex-wrap:wrap;">${bchips}</div>
        </div>`;
    }

    const tile = (label, value, sub, gk) => `<div style="flex:1; min-width:118px; background:rgba(43,40,34,0.03); border-radius:8px; padding:8px 10px;">
        <div style="font-size:11px; color:var(--text-secondary);">${label}${gk ? infoIcon(gk) : ''}</div>
        <div style="font-size:14px; font-weight:600; margin-top:2px;">${value}</div>
        ${sub ? `<div style="font-size:10.5px; color:var(--text-tertiary); margin-top:1px; line-height:1.3;">${sub}</div>` : ''}
    </div>`;

    const riskTile = (r.volatility_pct != null)
        ? tile('⚖️ Riesgo', `${r.volatility_pct}% vol.`, r.max_drawdown_pct != null ? `peor caída histórica ${r.max_drawdown_pct}%` : '', 'riesgo_score')
        : '';
    const sizeTile = (r.suggested_weight_pct != null)
        ? tile('📏 Tamaño sugerido', `${r.suggested_weight_pct}%`,
            op.correlation_to_portfolio != null
                ? `inverse-vol · ajustado por correlación con tu cartera (r=${op.correlation_to_portfolio})`
                : 'inverse-vol · ≤2% de vol. a la cartera',
            'tamano_sugerido')
        : '';

    let expTile = '';
    if (ex.status === 'listo') {
        const sg = ex.expectancy_pct >= 0 ? '+' : '';
        expTile = tile('📊 Expectancy (OOS)', `${sg}${ex.expectancy_pct}% a ${ex.horizon}`,
            `acierta ${ex.hit_rate_pct}% · gana ${ex.avg_win_pct}% / al fallar ${ex.avg_loss_pct}% · n=${ex.n}`, 'expectancy');
    } else if (ex.status === 'validando') {
        expTile = tile('📊 Expectancy (OOS)', 'en validación', `n=${ex.n}/${ex.n_required} — muestra insuficiente, aún no fiable`, 'expectancy');
    }

    const horizonTile = op.horizon ? tile('⏳ Horizonte', op.horizon, 'típico de esta estrategia', 'horizonte') : '';

    // Próximos catalizadores (resultados / ex-dividendo) — no operar a ciegas.
    const cat = op.catalysts;
    let catBlock = '';
    if (cat && (cat.earnings || cat.ex_dividend)) {
        const daysTo = (iso) => Math.round((new Date(iso) - new Date()) / 86400000);
        const parts = [];
        if (cat.earnings) {
            const dd = daysTo(cat.earnings);
            const soon = dd >= 0 && dd <= 14;
            parts.push(`<span${soon ? ' style="color:var(--negative); font-weight:600;"' : ''}>📊 Resultados ${cat.earnings}${dd >= 0 ? ` (en ${dd}d)` : ''}${soon ? ' ⚠️' : ''}</span>`);
        }
        if (cat.ex_dividend) {
            const dd = daysTo(cat.ex_dividend);
            if (dd >= 0) parts.push(`💰 Ex-dividendo ${cat.ex_dividend} (en ${dd}d)`);
        }
        if (parts.length) catBlock = `<div style="font-size:11.5px; margin:6px 0 2px; color:var(--text-secondary);">📅 Próximos catalizadores: ${parts.join(' · ')}</div>`;
    }

    // Técnico: fuerza de tendencia (ADX), volatilidad (ATR) + stop sugerido, volumen.
    const tc = op.technical;
    let techBlock = '';
    if (tc) {
        const bits = [];
        if (tc.adx != null) bits.push(`ADX ${tc.adx}${tc.adx_signal ? ` (${tc.adx_signal})` : ''}`);
        if (tc.atr_pct != null) bits.push(`ATR ${tc.atr_pct}%`);
        if (tc.stop_pct != null) bits.push(`<span title="2×ATR bajo el precio">🛑 stop sugerido ${tc.stop_pct}%</span>`);
        if (tc.volume_signal) bits.push(`volumen ${tc.volume_signal}${tc.rvol != null ? ` (${tc.rvol}×)` : ''}`);
        if (bits.length) techBlock = `<div style="font-size:11.5px; margin:6px 0 2px; color:var(--text-secondary);">📐 Técnico: ${bits.join(' · ')}</div>`;
    }

    const tiles = [riskTile, sizeTile, expTile, horizonTile].filter(Boolean).join('');
    if (!edgeLine && !tiles && !fundBlock && !bondBlock && !catBlock && !techBlock) return '';
    return `<div style="margin:10px 0; padding:10px 12px; border:1px solid rgba(43,40,34,0.10); border-radius:10px; background:rgba(43,40,34,0.015);">
        <div style="font-size:12px; color:var(--text-secondary); font-weight:600; margin-bottom:6px;">🧭 Marco de decisión</div>
        ${edgeLine}
        ${fundBlock}
        ${bondBlock}
        ${catBlock}
        ${techBlock}
        <div style="display:flex; gap:8px; flex-wrap:wrap;">${tiles}</div>
        <div style="font-size:10.5px; color:var(--text-tertiary); margin-top:8px; line-height:1.4;">Riesgo = estadística sobre precios; el tamaño se ajusta por correlación con tu cartera. Expectancy = resultado real de esta estrategia <em>después</em> de recomendar (out-of-sample), no una promesa. No es asesoramiento financiero.</div>
    </div>`;
}

function renderOpportunities(data) {
    oppLastData = data;
    const content = document.getElementById('oppContent');
    const convColor = { alta: 'var(--positive)', media: 'var(--warning)', baja: 'var(--text-tertiary)' };
    const kindIcon = { tema: '🌐', etf: '📊', fondo: '💼', sector: '🏭' };
    const regimeColor = { alcista: 'var(--positive)', bajista: 'var(--negative)', neutral: 'var(--warning)' };

    const opps = (data.opportunities || []).map(op => {
        const color = convColor[op.conviction] || 'var(--warning)';
        const icon = kindIcon[op.kind] || '💡';
        const apprStyle = op.approach === 'momentum' ? 'background:rgba(198, 71, 60, 0.13); color:var(--negative);' : 'background:rgba(59, 130, 246, 0.13); color:#3b82f6;';
        const apprLabel = op.approach === 'momentum' ? '🔥 momentum' : (op.approach ? '🧊 ' + op.approach : '');
        return `
        <div class="card" style="margin-bottom:14px; border-left:3px solid ${color};">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:8px;">
                <h3 style="margin:0;">${icon} ${op.ticker_or_isin ? `<a href="https://finance.yahoo.com/quote/${encodeURIComponent(op.ticker_or_isin)}" target="_blank" rel="noopener" title="Ver ficha (precio e info)" style="color:inherit; text-decoration:underline dotted;">${op.name}</a>` : op.name}${op.ticker_or_isin ? ` <span class="text-muted" style="font-size:13px;">${op.ticker_or_isin}</span>` : ''}</h3>
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
            ${renderDecision(op)}
            ${op.extended ? `<div style="margin:8px 0; background:#a855f718; border:1px solid #a855f755; border-radius:8px; padding:8px 12px; font-size:13px;">${op.extended_note || '🫧 Extendido: alto riesgo de reversión.'}</div>` : ''}
            ${assetLinks(op)}
            ${op.ticker_or_isin ? `<button onclick="openDeepAnalysis('${(op.ticker_or_isin+'').replace(/'/g,"&#39;")}','${(op.name+'').replace(/'/g,"&#39;")}')" style="margin:8px 0 4px; background:var(--accent-secondary); color:#fff; border:none; border-radius:8px; padding:7px 14px; font-size:13px; cursor:pointer;">🔬 Análisis profesional del activo</button>` : ''}
            ${renderBreakdown(op)}
            ${(op.news && op.news.length) ? `<div style="margin-top:8px; padding-top:8px; border-top:1px solid rgba(43, 40, 34, 0.08);"><strong style="font-size:13px;">📰 Noticias que lo respaldan:</strong><ul style="margin:6px 0 0; padding-left:18px; font-size:13px;">${op.news.map(n => `<li><a href="${n.url}" target="_blank" rel="noopener" style="color:var(--info);">${n.title}</a> <span class="text-muted">(${n.source})</span></li>`).join('')}</ul></div>` : ''}
        </div>`;
    }).join('');

    const fmtScore = (s) => {
        if (s == null) return '<span class="text-muted">—</span>';
        const cls = s >= 0 ? 'value-positive' : 'value-negative';
        return `<span class="mono ${cls}">${s >= 0 ? '+' : ''}${s.toFixed(2)}</span>`;
    };
    // Group by asset type so the user can see "de todo" at a glance, and every
    // row opens the SAME full deep-analysis modal the curated cards use above
    // (stats breakdown + multi-source news + narrative) — not just the ~7 curated ideas.
    const oppGroupOf = (cat) => {
        cat = cat || '';
        if (cat === 'acción' || cat.startsWith('screener ·')) return '📈 Acciones';
        if (cat === 'renta fija') return '🏦 Renta fija (bonos)';
        if (cat === 'materia prima') return '🪙 Materias primas';
        if (cat === 'fondo gestionado' || cat.startsWith('screener-fondo ·')) return '📁 Fondos';
        return '📊 ETFs';
    };
    const GROUP_ORDER = ['📈 Acciones', '📊 ETFs', '📁 Fondos', '🏦 Renta fija (bonos)', '🪙 Materias primas'];
    const themeRow = (t) => {
        const r3 = t.ret_3m, cls = (r3 || 0) >= 0 ? 'value-positive' : 'value-negative';
        const safeTicker = (t.ticker + '').replace(/'/g, "&#39;");
        const safeName = (t.theme + '').replace(/'/g, "&#39;");
        return `<tr onclick="openDeepAnalysis('${safeTicker}','${safeName}')" style="cursor:pointer;" title="Ver análisis completo">
            <td>${t.theme} <span class="text-muted mono" style="font-size:11px;">${t.ticker}</span></td>
            <td class="text-right">${fmtScore(t.momentum_score)}</td>
            <td class="text-right">${fmtScore(t.value_score)}</td>
            <td class="text-right mono ${cls}">${r3 != null ? (r3>=0?'+':'')+r3+'%' : '—'}</td>
            <td class="text-right mono">${t.range_pos_52w != null ? t.range_pos_52w.toFixed(0)+'%' : '—'}</td>
        </tr>`;
    };
    const themesByGroup = {};
    for (const t of (data.themes || [])) {
        const g = oppGroupOf(t.category);
        (themesByGroup[g] = themesByGroup[g] || []).push(t);
    }
    const sortKeyFn = { momentum_score: t => t.momentum_score, value_score: t => t.value_score, ret_3m: t => t.ret_3m, range_pos_52w: t => t.range_pos_52w }[oppSort.key];
    const sortMul = oppSort.dir === 'asc' ? 1 : -1;
    const sortThemes = (arr) => arr.slice().sort((a, b) => {
        const av = sortKeyFn(a), bv = sortKeyFn(b);
        if (av == null && bv == null) return 0;
        if (av == null) return 1;   // missing values always sink to the bottom
        if (bv == null) return -1;
        return (av - bv) * sortMul;
    });
    const sortArrow = (key) => oppSort.key === key ? (oppSort.dir === 'desc' ? ' ▼' : ' ▲') : '';
    const sortableTh = (key, label) => `<th class="text-right" onclick="oppSetSort('${key}')" style="cursor:pointer; user-select:none;" title="Ordenar">${label}${sortArrow(key)}</th>`;
    const themeGroups = GROUP_ORDER.filter(g => themesByGroup[g] && themesByGroup[g].length).map(g => {
        const rows = sortThemes(themesByGroup[g]).map(themeRow).join('');
        return `<div style="margin-bottom:14px;">
            <strong style="font-size:13px;">${g} <span class="text-muted" style="font-weight:400;">(${themesByGroup[g].length})</span></strong>
            <div class="table-container" style="margin-top:6px;">
                <table class="manager-table">
                    <thead><tr><th>Tema</th>${sortableTh('momentum_score', 'Score Mom.')}${sortableTh('value_score', 'Score Valor')}${sortableTh('ret_3m', '3 meses')}${sortableTh('range_pos_52w', 'Rango 52s')}</tr></thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
        </div>`;
    }).join('');

    const rc = regimeColor[data.market_regime] || 'var(--warning)';
    const regimeBanner = data.market_regime ? `<div style="margin-bottom:12px; padding:8px 14px; border-radius:8px; background:${rc}18; border:1px solid ${rc}44; font-size:13px;">📡 <strong>Régimen de mercado:</strong> <span style="color:${rc}; text-transform:uppercase; font-weight:600;">${data.market_regime}</span>${data.market_breadth != null ? ` · ${Math.round(data.market_breadth*100)}% de activos sobre su tendencia de 200 sesiones` : ''}<br><span class="text-muted" style="font-size:11px;">En régimen alcista pesa más el momentum; en bajista, el valor/defensivo.</span></div>` : '';

    const rcx = data.rates_context || {};
    const fmtP = (v) => (v == null ? '—' : v + '%');
    const inverted = rcx.curve_10y_2y != null && rcx.curve_10y_2y < 0;
    const ratesBanner = (rcx.nominal_10y != null || rcx.real_10y != null) ? `<div style="margin-bottom:12px; padding:8px 14px; border-radius:8px; background:rgba(43,40,34,0.04); border:1px solid rgba(43,40,34,0.12); font-size:13px;">🏦 <strong>Contexto de tipos (EE.UU.):</strong> 10Y <strong>${fmtP(rcx.nominal_10y)}</strong> · 10Y real ${fmtP(rcx.real_10y)} · inflación implícita ${fmtP(rcx.breakeven_inflation)} · 2Y ${fmtP(rcx.two_y)} · curva 10Y-2Y <strong style="color:${inverted ? 'var(--negative)' : 'var(--positive)'};">${rcx.curve_10y_2y == null ? '—' : (rcx.curve_10y_2y > 0 ? '+' : '') + rcx.curve_10y_2y}</strong>${inverted ? ' (invertida ⚠️)' : ''}<br><span class="text-muted" style="font-size:11px;">Marco para renta fija: el <strong>yield real</strong> (yield − inflación) es lo que de verdad ganas; una curva invertida suele avisar de recesión.</span></div>` : '';

    const t = data.trends || {};
    const growRow = (g) => {
        const safeTicker = (g.ticker + '').replace(/'/g, "&#39;");
        const safeName = (g.name + '').replace(/'/g, "&#39;");
        return `<tr onclick="openDeepAnalysis('${safeTicker}','${safeName}')" style="cursor:pointer;" title="Ver análisis completo"><td>${g.name} <span class="text-muted" style="font-size:12px;">${g.ticker}</span></td><td class="text-right mono ${(g.ret_3m||0)>=0?'value-positive':'value-negative'}">${g.ret_3m!=null?(g.ret_3m>=0?'+':'')+Math.round(g.ret_3m)+'%':'—'}</td><td class="text-right">${g.above_sma200?'📈':'📉'}</td></tr>`;
    };
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

    const fr = data.froth || {};
    const eu = fr.euphoria_level;
    const euColor = eu === 'alta' ? '#a855f7' : eu === 'media' ? 'var(--warning)' : 'var(--positive)';
    const frothBanner = (eu && (eu !== 'baja' || fr.concentration_warning)) ? `
        <div style="margin-bottom:12px; padding:10px 14px; border-radius:8px; background:${euColor}14; border:1px solid ${euColor}44; font-size:13px;">
            🫧 <strong>Termómetro de euforia:</strong> <span style="color:${euColor}; text-transform:uppercase; font-weight:600;">${eu}</span>
            · ${fr.market_overbought_pct}% del mercado sobrecomprado (RSI&gt;70)
            ${fr.concentration_warning ? `<br>${fr.concentration_warning}` : ''}
            ${(fr.extended_ideas && fr.extended_ideas.length) ? `<br>🫧 Ideas extendidas (parabólicas): <strong>${fr.extended_ideas.join(', ')}</strong> — cuidado con perseguir el pico.` : ''}
        </div>` : '';

    content.innerHTML = `
        ${frothBanner}
        ${regimeBanner}
        ${ratesBanner}
        ${data.market_summary ? `<div class="integrations-banner-inner" style="margin-bottom:16px;"><div class="integrations-banner-icon">🧠</div><div class="integrations-banner-body"><strong>Resumen de mercado</strong><p style="margin:6px 0 0;">${data.market_summary}</p></div></div>` : ''}
        ${trendsCard}
        ${opps}
        <div class="card" style="margin-top:16px;">
            <h3>📊 Ranking cuantitativo (motor empyrical + ta, datos reales)</h3>
            <p class="text-muted" style="font-size:12px; margin:-4px 0 10px;">${data.universe_size ? `Escaneados <strong>${data.universe_size}</strong> instrumentos (acciones, ETFs, fondos, bonos + screeners de Yahoo), excluyendo lo que ya tienes. ` : ''}Puntuación objetiva por estadística sobre precios, no opinión de la IA. Score Mom. = tendencia + retorno ajustado a riesgo · Score Valor = castigado pero de calidad. <strong>Pincha cualquier fila</strong> para el análisis completo (estadísticas, noticias y narrativa).</p>
            ${themeGroups}
        </div>
        ${data.disclaimer ? `<p class="text-muted" style="font-size:11px; margin-top:12px;">${data.disclaimer}</p>` : ''}
        <p class="text-muted" style="font-size:11px;">Generado ${data.generated_at ? new Date(data.generated_at).toLocaleString('es-ES') : ''} · modelo ${data.model || ''}</p>
    `;
}

document.addEventListener('DOMContentLoaded', () => {
    const nav = document.querySelector('[data-page="opportunities"]');
    if (nav) nav.addEventListener('click', () => { if (!oppLoaded) loadOpportunities(false); });
});
