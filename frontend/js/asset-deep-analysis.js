/**
 * Deep per-asset analysis modal — opens from an opportunity card and shows
 * extended metrics, ensemble breakdown, multiple charts, multi-source news with
 * sentiment, and an LLM broker-style narrative. Talks to /api/assets/{t}/deep-analysis.
 */
const DEEP_API = (window.API_BASE_URL || 'http://localhost:8000/api');

// Search ANY asset by ticker/ISIN/name → resolve it → run the same deep analysis.
// No curated library needed: resolution + analysis both use live Yahoo/CoinGecko data.
async function analyzeAnyAsset() {
    const input = document.getElementById('assetSearchInput');
    const msg = document.getElementById('assetSearchMsg');
    if (!input || !msg) return;
    const q = (input.value || '').trim();
    if (!q) { msg.textContent = 'Escribe un ticker, ISIN o nombre.'; msg.style.color = 'var(--negative)'; return; }
    msg.textContent = 'Buscando…'; msg.style.color = 'var(--text-secondary)';
    try {
        const r = await fetch(`${DEEP_API}/positions/resolve?query=${encodeURIComponent(q)}`);
        const d = await r.json();
        if (!r.ok || !d.ok) {
            msg.innerHTML = `⚠️ ${d.detail || 'No encontré ese activo. Prueba con el ticker o ISIN.'}`;
            msg.style.color = 'var(--negative)';
            return;
        }
        msg.innerHTML = `✓ <strong>${d.name}</strong> (${d.symbol})${d.type_label ? ' · ' + d.type_label : ''} — abriendo análisis…`;
        msg.style.color = 'var(--positive)';
        openDeepAnalysis(d.symbol, d.name);
    } catch (e) {
        msg.textContent = 'No pude buscar ahora mismo; inténtalo de nuevo.';
        msg.style.color = 'var(--negative)';
    }
}

function _ensureDeepModal() {
    let m = document.getElementById('deepAnalysisModal');
    if (m) return m;
    m = document.createElement('div');
    m.id = 'deepAnalysisModal';
    m.style.cssText = 'position:fixed; inset:0; background:rgba(5,10,20,0.85); z-index:1000; display:none; overflow-y:auto; padding:24px;';
    m.innerHTML = `
        <div style="max-width:980px; margin:0 auto; background:var(--bg-card,var(--bg-card)); border:1px solid var(--border-primary,var(--border-primary)); border-radius:14px; padding:22px; position:relative;">
            <button id="deepCloseBtn" style="position:absolute; top:12px; right:14px; background:none; border:none; color:var(--text-secondary); font-size:24px; cursor:pointer;" title="Cerrar">×</button>
            <div id="deepExport" style="margin:0 0 12px; padding-right:36px;"></div>
            <div id="deepBody"><div style="text-align:center; padding:40px;"><div class="spinner"></div><p class="text-muted" style="margin-top:14px;">Analizando el activo…</p></div></div>
        </div>`;
    document.body.appendChild(m);
    m.addEventListener('click', (e) => { if (e.target === m) closeDeepAnalysis(); });
    m.querySelector('#deepCloseBtn').addEventListener('click', closeDeepAnalysis);
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeDeepAnalysis(); });
    return m;
}

function closeDeepAnalysis() {
    const m = document.getElementById('deepAnalysisModal');
    if (m) m.style.display = 'none';
}

async function openDeepAnalysis(ticker, name) {
    const m = _ensureDeepModal();
    m.style.display = 'block';
    const body = m.querySelector('#deepBody');
    body.innerHTML = `<div style="text-align:center; padding:40px;"><div class="spinner"></div><p class="text-muted" style="margin-top:14px;">Analizando ${name || ticker}…<br><span style="font-size:12px;">Esto tarda ~10-30s la primera vez (escaneo profundo y noticias).</span></p></div>`;
    try {
        const nameParam = name ? `?name=${encodeURIComponent(name)}` : '';
        const resp = await fetch(`${DEEP_API}/assets/${encodeURIComponent(ticker)}/deep-analysis${nameParam}`, { cache: 'no-store' });
        // A 502/empty body (e.g. the backend mid-restart during a deploy) has no
        // JSON to parse — read as text first so that shows a clear "try again in a
        // few seconds" instead of a cryptic "Unexpected end of JSON input".
        const raw = await resp.text();
        let data;
        try { data = raw ? JSON.parse(raw) : {}; } catch (e) {
            throw new Error(resp.status === 502
                ? 'El servidor se está reiniciando — prueba de nuevo en unos segundos.'
                : `Respuesta inesperada del servidor (HTTP ${resp.status}).`);
        }
        if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);
        body.innerHTML = renderDeepAnalysis(data);
        // Interactive price chart with range toggles (replaces the old static image)
        // + ⭐ favorite quick-add, both mounted after the HTML is in the DOM.
        const pc = body.querySelector('#deepPriceChart');
        if (pc && window.mountPriceChart) window.mountPriceChart(pc, data.ticker, { height: 360, defaultPeriod: '1y' });
        // Analytics charts (drawdown, distribución, vol/Sharpe rodante, vs benchmark)
        // recomputed client-side per range — no longer static images.
        const ac = body.querySelector('#deepAnalyticsCharts');
        if (ac && window.mountAnalyticsCharts) window.mountAnalyticsCharts(ac, data.ticker, {
            benchTicker: (data.benchmark || {}).ticker,
            benchName: (data.benchmark || {}).name || 'benchmark',
            rfAnnualPct: (data.metrics || {}).rf_annual_pct,
            defaultPeriod: '1y',
        });
        if (window.renderFavButton) window.renderFavButton(body.querySelector('#deepFav'), data.ticker, data.name);
        const ex = m.querySelector('#deepExport');
        if (ex && window.exportToolbarHTML) {
            const safe = String(ticker).replace(/[^A-Za-z0-9._-]/g, '');
            ex.innerHTML = exportToolbarHTML('deepBody', 'analisis-' + safe);
        }
    } catch (err) {
        body.innerHTML = `<div class="alert alert-error" style="margin-top:10px;">No pude analizar el activo: ${err.message}</div>`;
    }
}

const _CRITERION_LABEL = {
    momentum: 'Momentum (tendencia)', regimen: 'Régimen (sobre 200d)', riesgo: 'Riesgo (Sharpe)',
    tecnico: 'Técnico (RSI/MACD)', volatilidad: 'Volatilidad (EWMA)',
    infravaloracion: 'Infravaloración', reversion: 'Reversión a la media',
    sobreventa: 'Sobreventa (RSI)', calidad: 'Calidad (Sharpe)',
    consistencia: 'Consistencia (% meses positivos)',
    // Fundamentales (solo acciones)
    calidad_fund: 'Calidad (ROE/márgenes)', crecimiento: 'Crecimiento (ventas/BPA)',
    valoracion_fund: 'Valoración (PER/PB, sector)', solidez: 'Solidez (deuda)',
    insider: 'Insiders (compras directivos)',
    // Renta fija
    carry_bono: 'Carry real (yield−inflación, ajust. tipos)',
};
const _CRITERION_GLOSSARY_KEY = {
    momentum: 'momentum_criterio', regimen: 'regimen_200d', riesgo: 'riesgo_score',
    tecnico: 'tecnico_rsi_macd', volatilidad: 'volatilidad',
    infravaloracion: 'infravaloracion_criterio', reversion: 'reversion_media',
    sobreventa: 'tecnico_rsi_macd', calidad: 'riesgo_score',
    consistencia: 'momentum_consistencia',
    calidad_fund: 'roe', crecimiento: 'crec_ventas', valoracion_fund: 'per', solidez: 'debt_ratio',
    insider: 'insider_sentiment',
    carry_bono: 'yield_bono',
};
const _SENT_EMOJI = { bullish: '🟢', bearish: '🔴', neutral: '⚪' };

function _fmt(n, d = 2) { return n == null || isNaN(n) ? '—' : (Number(n)).toFixed(d); }
function _signedCls(n) { return n == null ? '' : (n >= 0 ? 'value-positive' : 'value-negative'); }
function _signedFmt(n, d = 2) { return n == null ? '—' : (n >= 0 ? '+' : '') + Number(n).toFixed(d); }

function _gi(key) { return (typeof infoIcon === 'function' ? infoIcon(key) : ''); }

function _metricsBlock(m) {
    const groups = [
        {title: 'Rentabilidad y riesgo', cells: [
            ['Precio', _fmt(m.last_price, 4)],
            ['CAGR', _signedFmt(m.cagr_pct) + '%', _signedCls(m.cagr_pct), 'cagr'],
            ['Volatilidad anual', _fmt(m.volatility_pct) + '%', '', 'volatilidad'],
            [`Sharpe (Rf ${_fmt(m.rf_annual_pct)}%)`, _signedFmt(m.sharpe), _signedCls(m.sharpe), 'sharpe'],
            ['Sortino', _signedFmt(m.sortino), _signedCls(m.sortino), 'sortino'],
            ['Calmar', _fmt(m.calmar), '', 'calmar'],
            ['Años cubiertos', _fmt(m.years_covered), '', 'anos_cubiertos'],
        ]},
        {title: 'Drawdown', cells: [
            ['Máx. drawdown', _signedFmt(m.max_drawdown_pct) + '%' + (m.max_drawdown_date ? ` <span class="text-muted" style="font-size:11px;">(${m.max_drawdown_date})</span>` : ''), 'value-negative', 'max_drawdown'],
            ['Duración máx. (días)', m.max_drawdown_days == null ? '—' : m.max_drawdown_days, '', 'drawdown_duracion_max'],
            ['Duración media (días)', m.avg_drawdown_days == null ? '—' : m.avg_drawdown_days, '', 'drawdown_duracion_media'],
        ]},
        {title: 'Riesgo de cola (histórico)', cells: [
            ['VaR 95% diario', _fmt(m.var_95_pct) + '%', '', 'var95'],
            ['VaR 99% diario', _fmt(m.var_99_pct) + '%', '', 'var99'],
            ['CVaR 95% (ES)', m.cvar_95_pct == null ? '—' : _fmt(m.cvar_95_pct) + '%', '', 'cvar95'],
            ['CVaR 99% (ES)', m.cvar_99_pct == null ? '—' : _fmt(m.cvar_99_pct) + '%', '', 'cvar99'],
        ]},
        {title: 'Distribución de retornos', cells: [
            ['Asimetría (skew)', _signedFmt(m.skewness), '', 'skewness'],
            ['Curtosis exceso', _signedFmt(m.excess_kurtosis), '', 'excess_kurtosis'],
            ['Jarque-Bera (p)', m.jarque_bera_p == null ? '—' : _fmt(m.jarque_bera_p, 4) + (m.jarque_bera_p < 0.05 ? ' · no-normal' : ' · ≈normal'), '', 'jarque_bera'],
            ['PSR (prob. Sharpe > 0)', m.psr_pct == null ? '—' : _fmt(m.psr_pct, 1) + '%', '', 'psr'],
        ]},
        {title: `Frente al benchmark`, cells: [
            ['Beta', m.beta == null ? '—' : _fmt(m.beta), '', 'beta'],
            ['Alfa anual', m.alpha_annual_pct == null ? '—' : _signedFmt(m.alpha_annual_pct) + '%', _signedCls(m.alpha_annual_pct), 'alfa_anual'],
            ['t-stat alfa', m.alpha_t_stat == null ? '—' : _signedFmt(m.alpha_t_stat) + (m.alpha_p_value != null ? ` <span class="text-muted" style="font-size:11px;">(p=${_fmt(m.alpha_p_value, 4)})</span>` : ''), '', 'alpha_t_stat'],
            ['Correlación', m.correlation == null ? '—' : _fmt(m.correlation), '', 'correlacion'],
            ['R²', m.r_squared_pct == null ? '—' : _fmt(m.r_squared_pct, 1) + '%', '', 'r_squared'],
            ['Information Ratio', m.information_ratio == null ? '—' : _signedFmt(m.information_ratio), _signedCls(m.information_ratio), 'information_ratio'],
            ['Tracking error', m.tracking_error_pct == null ? '—' : _fmt(m.tracking_error_pct) + '%', '', 'tracking_error'],
            ['Treynor', m.treynor_pct == null ? '— <span class="text-muted" style="font-size:11px;">(β muy bajo)</span>' : _signedFmt(m.treynor_pct) + '%', '', 'treynor'],
            ['Up-capture', m.up_capture_pct == null ? '—' : _fmt(m.up_capture_pct, 1) + '%', '', 'up_capture'],
            ['Down-capture', m.down_capture_pct == null ? '—' : _fmt(m.down_capture_pct, 1) + '%', '', 'down_capture'],
        ]},
    ];
    return groups.map(g => `
        <div style="margin:14px 0;">
            <h4 style="margin:0 0 8px; font-size:14px; color:var(--text-secondary);">${g.title}</h4>
            <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:10px;">
                ${g.cells.map(([k, v, cls, gk]) => `<div style="background:rgba(43, 40, 34, 0.03); border-radius:8px; padding:10px 12px;">
                    <div style="color:var(--text-secondary); font-size:12px;">${k}${gk ? _gi(gk) : ''}</div>
                    <div class="mono ${cls || ''}" style="font-size:15px; margin-top:2px;">${v}</div>
                </div>`).join('')}
            </div>
        </div>`).join('');
}

function _breakdownBars(bd) {
    if (!bd || !Object.keys(bd).length) return '<p class="text-muted" style="font-size:13px;">Sin desglose disponible (genera Oportunidades para que el activo entre al ranking).</p>';
    const maxAbs = Math.max(...Object.values(bd).map(v => Math.abs(v)), 0.01);
    return Object.entries(bd).map(([k, v]) => {
        const pct = Math.round(Math.abs(v) / maxAbs * 100);
        const c = v >= 0 ? 'var(--positive)' : 'var(--negative)';
        return `<div style="display:flex; align-items:center; gap:8px; margin:4px 0; font-size:13px;">
            <span style="flex:0 0 170px; color:var(--text-secondary);">${_CRITERION_LABEL[k] || k}${_gi(_CRITERION_GLOSSARY_KEY[k])}</span>
            <span style="flex:1; background:rgba(43, 40, 34, 0.05); border-radius:4px; height:10px; position:relative;">
                <span style="position:absolute; left:0; top:0; height:10px; width:${pct}%; background:${c}; border-radius:4px;"></span>
            </span>
            <span class="mono" style="flex:0 0 56px; text-align:right; color:${c};">${v >= 0 ? '+' : ''}${v.toFixed(2)}</span>
        </div>`;
    }).join('');
}

function _newsBlock(news, sentiment, sources) {
    if (!news || !news.length) return '<p class="text-muted" style="font-size:13px;">Sin titulares específicos de este activo en el feed actual.</p>';
    const sentBar = `<div style="font-size:12px; color:var(--text-secondary); margin-bottom:8px;">
        Sentimiento: 🟢 ${sentiment.bullish || 0} · 🔴 ${sentiment.bearish || 0} · ⚪ ${sentiment.neutral || 0}
        ${sources && sources.length ? ` · Fuentes: ${sources.join(', ')}` : ''}
    </div>`;
    const items = news.slice(0, 10).map(n => {
        const e = _SENT_EMOJI[n.impact] || '⚪';
        const t = (n.title || '').replace(/</g, '&lt;');
        const macroTag = n.category === 'economy' ? ' <span class="text-muted" style="font-size:10px; border:1px solid rgba(43,40,34,0.2); border-radius:4px; padding:0 4px;" title="Contexto de mercado general, no una noticia específica de este activo">🌐 macro</span>' : '';
        return `<li style="margin:4px 0;">${e} <a href="${n.url}" target="_blank" rel="noopener" style="color:var(--info);">${t}</a>${macroTag} <span class="text-muted" style="font-size:11px;">(${n.source})</span></li>`;
    }).join('');
    return sentBar + `<ul style="margin:0; padding-left:20px; font-size:13px;">${items}</ul>`;
}

// Which of the engine's two theses this asset's CURRENT profile fits better
// (momentum ~1-3 meses vs valor/reversión ~6-18 meses) — not a prediction, and
// flags when it's extended enough above its 200d average that a pullback is
// statistically more likely, regardless of which thesis fits.
function _horizonBlock(h) {
    if (!h) return '';
    const color = h.thesis === 'momentum' ? 'var(--info)' : h.thesis === 'valor' ? 'var(--positive)' : 'var(--text-secondary)';
    const warn = h.extended
        ? `<div style="margin-top:6px; background:rgba(201,154,62,0.12); border:1px solid rgba(201,154,62,0.4); border-radius:6px; padding:6px 10px; font-size:12px;">⚠️ Está un ${h.dist_sma200_pct}% por encima de su media de 200 sesiones — cuanto más lejos, estadísticamente más probable una pausa/consolidación (no es una predicción para este caso concreto).</div>`
        : '';
    return `<div style="margin:10px 0; padding:10px 14px; background:rgba(43,40,34,0.03); border-radius:8px; border-left:3px solid ${color};">
        <strong>⏱️ Horizonte que mejor encaja:</strong> ${h.label}
        ${warn}
    </div>`;
}

// Real "qué es esto" — Yahoo's own business/fund/coin summary (never
// generated by us), with sector/category context when available.
function _descriptionBlock(descr) {
    if (!descr || !descr.summary) return '';
    const meta = [descr.long_name, descr.sector || descr.category, descr.industry || descr.fund_family].filter(Boolean).join(' · ');
    return `<div style="margin:10px 0 14px; padding:10px 14px; background:rgba(43,40,34,0.03); border-radius:8px;">
        <strong>📖 ¿Qué es esto?</strong>
        ${meta ? `<div class="text-muted" style="font-size:12px; margin:4px 0 6px;">${meta}</div>` : ''}
        <p style="margin:6px 0 0; font-size:13px; line-height:1.6;">${descr.summary}</p>
    </div>`;
}

function renderDeepAnalysis(d) {
    const m = d.metrics || {};
    const charts = d.charts || {};
    const benchName = (d.benchmark || {}).name || 'benchmark';
    const yh = `https://finance.yahoo.com/quote/${encodeURIComponent(d.ticker)}`;
    const isFund = (d.category || '').includes('fondo') || (d.category || '').includes('etf') || (d.category || '').includes('temático') || (d.category || '').includes('amplio');
    const je = `https://www.justetf.com/en/search.html?query=${encodeURIComponent(d.ticker)}`;

    const chartImg = (url, title, gk) => url ? `<div style="margin:14px 0;">
        <div style="font-size:12px; color:var(--text-secondary); margin-bottom:4px;">${title}${gk ? _gi(gk) : ''}</div>
        <img src="${url}" alt="${title}" loading="lazy" style="width:100%; max-width:920px; border-radius:8px; display:block;">
    </div>` : '';

    return `
    <h2 style="margin:0 0 4px;">🔬 ${d.name} <span class="text-muted" style="font-size:14px; font-weight:normal;">${d.ticker}</span></h2>
    <p class="text-muted" style="margin:0 0 12px; font-size:13px;">
        ${[d.category, d.region].filter(Boolean).join(' · ')}
        · Benchmark de comparación: <strong>${benchName}</strong>
        · <a href="${yh}" target="_blank" rel="noopener" style="color:var(--info);">Ficha en Yahoo</a>
        ${isFund ? ` · <a href="${je}" target="_blank" rel="noopener" style="color:var(--info);">justETF (ISIN / dónde comprar)</a>` : ''}
    </p>

    <div id="deepFav" style="margin:6px 0 12px;"></div>

    ${_descriptionBlock(d.description)}

    ${_horizonBlock(d.horizon)}

    <h3 style="margin-top:18px;">📊 Métricas extendidas</h3>
    ${_metricsBlock(m)}

    <h3 style="margin-top:18px;">🧮 Cómo lo puntúa el motor cuantitativo</h3>
    <p class="text-muted" style="font-size:12px; margin:0 0 6px;">
        Score momentum${_gi('momentum_score')}: <strong class="mono ${_signedCls((d.scores||{}).momentum_score)}">${_signedFmt((d.scores||{}).momentum_score)}</strong>
        · Score valor${_gi('value_score')}: <strong class="mono ${_signedCls((d.scores||{}).value_score)}">${_signedFmt((d.scores||{}).value_score)}</strong>
        · Afinidad con el "perfil ganador"${_gi('winner_affinity')}: ${(d.scores||{}).winner_affinity == null ? '—' : Math.round((d.scores.winner_affinity)*100)+'%'}
        · Tesis dominante: <strong>${d.ensemble_thesis}</strong>
    </p>
    ${_breakdownBars(d.score_breakdown || {})}

    <h3 style="margin-top:22px;">📈 Gráficas</h3>
    <div style="margin:14px 0;">
        <div style="font-size:12px; color:var(--text-secondary); margin-bottom:6px;">Precio con SMA50/200 · elige el rango (Hoy → Máx)${_gi('chart_precio_sma')}</div>
        <div id="deepPriceChart"></div>
    </div>
    <div id="deepAnalyticsCharts" style="margin-top:14px;"></div>

    <h3 style="margin-top:18px;">📰 Noticias del activo (varias fuentes)</h3>
    ${_newsBlock(d.news, d.news_sentiment || {}, d.news_sources || [])}
    ${_catalystBriefHtml(d.catalyst_brief)}

    ${d.narrative ? `
    <h3 style="margin-top:18px;">🖋️ Nota del analista</h3>
    <div style="background:rgba(99,102,241,0.08); border-left:3px solid var(--accent-secondary); padding:12px 14px; border-radius:6px; font-size:14px; white-space:pre-wrap;">${d.narrative.replace(/</g,'&lt;')}</div>
    ` : ''}

    <p class="text-muted" style="font-size:11px; margin-top:14px;">Generado ${new Date(d.generated_at).toLocaleString('es-ES')} · Esto es análisis educativo, no recomendación de compra/venta.</p>
    `;
}

// ===== Range-aware analytics charts (client-side, replace the static images) =====
// Recomputed from the asset's own price history (and the benchmark's) for the
// selected range, using Chart.js — so drawdown, return distribution, rolling
// vol/Sharpe and relative-vs-benchmark all respond to the range you pick.
const ANALYTICS_PERIODS = [['3mo', '3M'], ['6mo', '6M'], ['1y', '1A'], ['2y', '2A'], ['5y', '5A'], ['max', 'Máx']];
const _deepCharts = [];
function _destroyDeepCharts() { while (_deepCharts.length) { try { _deepCharts.pop().destroy(); } catch (e) { /* noop */ } } }

function _mean(a) { return a.length ? a.reduce((s, x) => s + x, 0) / a.length : 0; }
function _std(a) { if (a.length < 2) return 0; const m = _mean(a); return Math.sqrt(a.reduce((s, x) => s + (x - m) * (x - m), 0) / (a.length - 1)); }
function _clClose(history) { return (history || []).map(h => ({ date: h.date, c: (h.close ?? h.price) })).filter(x => x.c > 0); }
function _dailyReturns(cl) { const r = []; for (let i = 1; i < cl.length; i++) r.push(cl[i].c / cl[i - 1].c - 1); return r; }

function _adScales(yPct) {
    return {
        x: { ticks: { maxTicksLimit: 7, color: '#9C9689' }, grid: { display: false } },
        y: { ticks: { color: '#9C9689', callback: v => yPct ? v + '%' : v }, grid: { color: '#EFEBE3' } },
    };
}
function _adLine(labels, data, color, yPct, fill) {
    return {
        type: 'line',
        data: { labels, datasets: [{ data, borderColor: color, backgroundColor: fill || 'transparent', fill: !!fill, tension: 0.15, pointRadius: 0, borderWidth: 2 }] },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => `${(+c.parsed.y).toFixed(2)}${yPct ? '%' : ''}` } } },
            scales: _adScales(yPct),
        },
    };
}
function _adBar(labels, data, color) {
    return {
        type: 'bar',
        data: { labels, datasets: [{ data, backgroundColor: color }] },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false }, tooltip: { callbacks: { title: it => `retorno ${it[0].label}`, label: c => `${c.parsed.y} días` } } },
            scales: { x: { ticks: { maxTicksLimit: 8, color: '#9C9689' }, grid: { display: false } }, y: { ticks: { color: '#9C9689' }, grid: { color: '#EFEBE3' } } },
        },
    };
}
function _histogram(vals, nbins) {
    const min = Math.min(...vals), max = Math.max(...vals);
    if (!isFinite(min) || !isFinite(max) || min === max) return { bins: ['0%'], counts: [vals.length] };
    const w = (max - min) / nbins;
    const counts = new Array(nbins).fill(0);
    vals.forEach(v => { let i = Math.floor((v - min) / w); if (i >= nbins) i = nbins - 1; if (i < 0) i = 0; counts[i]++; });
    const bins = [];
    for (let i = 0; i < nbins; i++) bins.push((min + w * i + w / 2).toFixed(1) + '%');
    return { bins, counts };
}

async function mountAnalyticsCharts(container, ticker, opts = {}) {
    if (!container || typeof Chart === 'undefined') return;
    const benchTicker = opts.benchTicker || null;
    const benchName = opts.benchName || 'benchmark';
    const rfPct = (opts.rfAnnualPct != null) ? opts.rfAnnualPct : 0;
    let period = opts.defaultPeriod || '1y';

    const cards = [
        ['dd', 'Drawdown (caída desde máximos)'],
        ['hist', 'Distribución de retornos diarios'],
        ['vol', 'Volatilidad rodante (anualizada)'],
        ['sharpe', 'Sharpe rodante'],
        ['rel', `Rendimiento relativo vs ${benchName}`],
    ];
    container.innerHTML = `
        <div class="pchart-ranges" style="margin-bottom:10px;">
            ${ANALYTICS_PERIODS.map(([p, l]) => `<button type="button" class="pchart-range-btn" data-period="${p}">${l}</button>`).join('')}
        </div>
        <div class="deep-analytics-grid">
            ${cards.map(([k, title]) => `<div class="card metric-card" style="margin:0;">
                <div style="font-size:12px; color:var(--text-secondary); margin-bottom:6px;">${title}</div>
                <div class="ad-canvas-wrap" style="position:relative; height:200px;"><canvas data-chart="${k}"></canvas></div>
            </div>`).join('')}
        </div>`;
    const rangesEl = container.querySelector('.pchart-ranges');
    const wrapOf = (k) => container.querySelector(`canvas[data-chart="${k}"]`);
    const noteInto = (k, txt) => { const c = wrapOf(k); if (c) c.parentElement.innerHTML = `<p class="text-muted" style="font-size:12px; padding:20px 0; text-align:center;">${txt}</p>`; };

    async function draw(p) {
        period = p;
        rangesEl.querySelectorAll('.pchart-range-btn').forEach(b => b.classList.toggle('active', b.dataset.period === p));
        _destroyDeepCharts();
        const base = window.API_BASE_URL || '/api';
        const url = (t) => `${base}/asset/${encodeURIComponent(t)}/history?period=${p}&asset_type=auto`;
        const [aR, bR] = await Promise.all([
            fetch(url(ticker), { cache: 'no-store' }).then(r => r.ok ? r.json() : null).catch(() => null),
            benchTicker ? fetch(url(benchTicker), { cache: 'no-store' }).then(r => r.ok ? r.json() : null).catch(() => null) : Promise.resolve(null),
        ]);
        const cl = _clClose(aR && aR.history);
        if (cl.length < 5) {
            ['dd', 'hist', 'vol', 'sharpe', 'rel'].forEach(k => noteInto(k, 'Pocos datos para este rango.'));
            return;
        }
        const labels = cl.map(x => x.date);
        const rets = _dailyReturns(cl);

        // 1) Drawdown
        let peak = -Infinity;
        const dd = cl.map(x => { peak = Math.max(peak, x.c); return (x.c / peak - 1) * 100; });
        _deepCharts.push(new Chart(wrapOf('dd'), _adLine(labels, dd, '#C6473C', true, 'rgba(198,71,60,0.12)')));

        // 2) Histogram of daily returns (%)
        const { bins, counts } = _histogram(rets.map(r => r * 100), 21);
        _deepCharts.push(new Chart(wrapOf('hist'), _adBar(bins, counts, '#2C4A6E')));

        // 3/4) Rolling vol + Sharpe (annualized), window sized to the range
        const W = Math.max(10, Math.min(60, Math.floor(cl.length / 4)));
        if (rets.length > W + 2) {
            const rollLabels = [], volS = [], shS = [];
            for (let i = W; i < rets.length; i++) {
                const w = rets.slice(i - W, i);
                const sd = _std(w), annVol = sd * Math.sqrt(252), annMean = _mean(w) * 252;
                volS.push(annVol * 100);
                shS.push(annVol > 0 ? (annMean - rfPct / 100) / annVol : 0);
                rollLabels.push(cl[i + 1] ? cl[i + 1].date : labels[i]);
            }
            _deepCharts.push(new Chart(wrapOf('vol'), _adLine(rollLabels, volS, '#C99A3E', true, 'rgba(201,154,62,0.10)')));
            _deepCharts.push(new Chart(wrapOf('sharpe'), _adLine(rollLabels, shS, '#4A9B8E', false, 'rgba(74,155,142,0.10)')));
        } else {
            noteInto('vol', `Rango corto: se necesitan más sesiones para la ventana rodante.`);
            noteInto('sharpe', `Rango corto: se necesitan más sesiones para la ventana rodante.`);
        }

        // 5) Relative performance vs benchmark (aligned by date)
        const bcl = _clClose(bR && bR.history);
        if (bcl.length > 2) {
            const bmap = {}; bcl.forEach(x => { bmap[x.date] = x.c; });
            const common = cl.filter(x => bmap[x.date] != null);
            if (common.length > 2) {
                const a0 = common[0].c, b0 = bmap[common[0].date];
                const rel = common.map(x => ((x.c / a0) / (bmap[x.date] / b0) - 1) * 100);
                _deepCharts.push(new Chart(wrapOf('rel'), _adLine(common.map(x => x.date), rel, '#2C4A6E', true, 'rgba(44,74,110,0.10)')));
            } else { noteInto('rel', 'Sin fechas comunes con el benchmark en este rango.'); }
        } else {
            noteInto('rel', `Sin datos del benchmark (${benchName}).`);
        }
    }

    rangesEl.querySelectorAll('.pchart-range-btn').forEach(b => b.addEventListener('click', () => draw(b.dataset.period)));
    draw(period);
}
window.mountAnalyticsCharts = mountAnalyticsCharts;
