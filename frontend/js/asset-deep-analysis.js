/**
 * Deep per-asset analysis modal — opens from an opportunity card and shows
 * extended metrics, ensemble breakdown, multiple charts, multi-source news with
 * sentiment, and an LLM broker-style narrative. Talks to /api/assets/{t}/deep-analysis.
 */
const ASSET_API = (window.API_BASE_URL || 'http://localhost:8000/api');

function _ensureDeepModal() {
    let m = document.getElementById('deepAnalysisModal');
    if (m) return m;
    m = document.createElement('div');
    m.id = 'deepAnalysisModal';
    m.style.cssText = 'position:fixed; inset:0; background:rgba(5,10,20,0.85); z-index:1000; display:none; overflow-y:auto; padding:24px;';
    m.innerHTML = `
        <div style="max-width:980px; margin:0 auto; background:var(--bg-card,#1e2a3d); border:1px solid var(--border-primary,#2b3a52); border-radius:14px; padding:22px; position:relative;">
            <button id="deepCloseBtn" style="position:absolute; top:12px; right:14px; background:none; border:none; color:#94a3b8; font-size:24px; cursor:pointer;" title="Cerrar">×</button>
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
        const resp = await fetch(`${ASSET_API}/assets/${encodeURIComponent(ticker)}/deep-analysis`, { cache: 'no-store' });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);
        body.innerHTML = renderDeepAnalysis(data);
    } catch (err) {
        body.innerHTML = `<div class="alert alert-error" style="margin-top:10px;">No pude analizar el activo: ${err.message}</div>`;
    }
}

const _CRITERION_LABEL = {
    momentum: 'Momentum (tendencia)', regimen: 'Régimen (sobre 200d)', riesgo: 'Riesgo (Sharpe)',
    tecnico: 'Técnico (RSI/MACD)', volatilidad: 'Volatilidad (EWMA)',
    infravaloracion: 'Infravaloración', reversion: 'Reversión a la media',
    sobreventa: 'Sobreventa (RSI)', calidad: 'Calidad (Sharpe)',
};
const _SENT_EMOJI = { bullish: '🟢', bearish: '🔴', neutral: '⚪' };

function _fmt(n, d = 2) { return n == null || isNaN(n) ? '—' : (Number(n)).toFixed(d); }
function _signedCls(n) { return n == null ? '' : (n >= 0 ? 'value-positive' : 'value-negative'); }
function _signedFmt(n, d = 2) { return n == null ? '—' : (n >= 0 ? '+' : '') + Number(n).toFixed(d); }

function _metricsBlock(m) {
    const cells = [
        ['Precio', _fmt(m.last_price, 4)],
        ['CAGR', _signedFmt(m.cagr_pct) + '%', _signedCls(m.cagr_pct)],
        ['Volatilidad anual', _fmt(m.volatility_pct) + '%'],
        ['Sharpe', _signedFmt(m.sharpe), _signedCls(m.sharpe)],
        ['Sortino', _signedFmt(m.sortino), _signedCls(m.sortino)],
        ['Máx. drawdown', _signedFmt(m.max_drawdown_pct) + '%' + (m.max_drawdown_date ? ` <span class="text-muted" style="font-size:11px;">(${m.max_drawdown_date})</span>` : ''), 'value-negative'],
        ['Calmar', _fmt(m.calmar)],
        ['Beta', m.beta == null ? '—' : _fmt(m.beta)],
        ['Alfa anual', m.alpha_annual_pct == null ? '—' : _signedFmt(m.alpha_annual_pct) + '%', _signedCls(m.alpha_annual_pct)],
        ['Correlación', m.correlation == null ? '—' : _fmt(m.correlation)],
        ['Años cubiertos', _fmt(m.years_covered)],
    ];
    return `<div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:10px; margin:14px 0;">
        ${cells.map(([k, v, cls]) => `<div style="background:rgba(255,255,255,0.03); border-radius:8px; padding:10px 12px;">
            <div style="color:#94a3b8; font-size:12px;">${k}</div>
            <div class="mono ${cls || ''}" style="font-size:16px; margin-top:2px;">${v}</div>
        </div>`).join('')}
    </div>`;
}

function _breakdownBars(bd) {
    if (!bd || !Object.keys(bd).length) return '<p class="text-muted" style="font-size:13px;">Sin desglose disponible (genera Oportunidades para que el activo entre al ranking).</p>';
    const maxAbs = Math.max(...Object.values(bd).map(v => Math.abs(v)), 0.01);
    return Object.entries(bd).map(([k, v]) => {
        const pct = Math.round(Math.abs(v) / maxAbs * 100);
        const c = v >= 0 ? '#10b981' : '#ef4444';
        return `<div style="display:flex; align-items:center; gap:8px; margin:4px 0; font-size:13px;">
            <span style="flex:0 0 170px; color:#cbd5e1;">${_CRITERION_LABEL[k] || k}</span>
            <span style="flex:1; background:rgba(255,255,255,0.05); border-radius:4px; height:10px; position:relative;">
                <span style="position:absolute; left:0; top:0; height:10px; width:${pct}%; background:${c}; border-radius:4px;"></span>
            </span>
            <span class="mono" style="flex:0 0 56px; text-align:right; color:${c};">${v >= 0 ? '+' : ''}${v.toFixed(2)}</span>
        </div>`;
    }).join('');
}

function _newsBlock(news, sentiment, sources) {
    if (!news || !news.length) return '<p class="text-muted" style="font-size:13px;">Sin titulares específicos de este activo en el feed actual.</p>';
    const sentBar = `<div style="font-size:12px; color:#94a3b8; margin-bottom:8px;">
        Sentimiento: 🟢 ${sentiment.bullish || 0} · 🔴 ${sentiment.bearish || 0} · ⚪ ${sentiment.neutral || 0}
        ${sources && sources.length ? ` · Fuentes: ${sources.join(', ')}` : ''}
    </div>`;
    const items = news.slice(0, 10).map(n => {
        const e = _SENT_EMOJI[n.impact] || '⚪';
        const t = (n.title || '').replace(/</g, '&lt;');
        return `<li style="margin:4px 0;">${e} <a href="${n.url}" target="_blank" rel="noopener" style="color:#60a5fa;">${t}</a> <span class="text-muted" style="font-size:11px;">(${n.source})</span></li>`;
    }).join('');
    return sentBar + `<ul style="margin:0; padding-left:20px; font-size:13px;">${items}</ul>`;
}

function renderDeepAnalysis(d) {
    const m = d.metrics || {};
    const charts = d.charts || {};
    const benchName = (d.benchmark || {}).name || 'benchmark';
    const yh = `https://finance.yahoo.com/quote/${encodeURIComponent(d.ticker)}`;
    const isFund = (d.category || '').includes('fondo') || (d.category || '').includes('etf') || (d.category || '').includes('temático') || (d.category || '').includes('amplio');
    const je = `https://www.justetf.com/en/search.html?query=${encodeURIComponent(d.ticker)}`;

    const chartImg = (url, title) => url ? `<div style="margin:14px 0;"><img src="${url}" alt="${title}" loading="lazy" style="width:100%; max-width:920px; border-radius:8px; display:block;"></div>` : '';

    return `
    <h2 style="margin:0 0 4px;">🔬 ${d.name} <span class="text-muted" style="font-size:14px; font-weight:normal;">${d.ticker}</span></h2>
    <p class="text-muted" style="margin:0 0 12px; font-size:13px;">
        ${[d.category, d.region].filter(Boolean).join(' · ')}
        · Benchmark de comparación: <strong>${benchName}</strong>
        · <a href="${yh}" target="_blank" rel="noopener" style="color:#60a5fa;">Ficha en Yahoo</a>
        ${isFund ? ` · <a href="${je}" target="_blank" rel="noopener" style="color:#60a5fa;">justETF (ISIN / dónde comprar)</a>` : ''}
    </p>

    <h3 style="margin-top:18px;">📊 Métricas extendidas</h3>
    ${_metricsBlock(m)}

    <h3 style="margin-top:18px;">🧮 Cómo lo puntúa el motor cuantitativo</h3>
    <p class="text-muted" style="font-size:12px; margin:0 0 6px;">
        Score momentum: <strong class="mono ${_signedCls((d.scores||{}).momentum_score)}">${_signedFmt((d.scores||{}).momentum_score)}</strong>
        · Score valor: <strong class="mono ${_signedCls((d.scores||{}).value_score)}">${_signedFmt((d.scores||{}).value_score)}</strong>
        · Afinidad con el "perfil ganador": ${(d.scores||{}).winner_affinity == null ? '—' : Math.round((d.scores.winner_affinity)*100)+'%'}
        · Tesis dominante: <strong>${d.ensemble_thesis}</strong>
    </p>
    ${_breakdownBars(d.score_breakdown || {})}

    <h3 style="margin-top:22px;">📈 Gráficas</h3>
    ${chartImg(charts.price_with_smas, 'Precio con SMA50 y SMA200')}
    ${chartImg(charts.drawdown, 'Drawdown histórico')}
    ${chartImg(charts.returns_histogram, 'Distribución de retornos diarios')}
    ${chartImg(charts.rolling_volatility, 'Volatilidad rodante 60d')}
    ${chartImg(charts.relative_vs_benchmark, 'Rendimiento vs benchmark')}

    <h3 style="margin-top:18px;">📰 Noticias del activo (varias fuentes)</h3>
    ${_newsBlock(d.news, d.news_sentiment || {}, d.news_sources || [])}

    ${d.narrative ? `
    <h3 style="margin-top:18px;">🖋️ Nota del analista</h3>
    <div style="background:rgba(99,102,241,0.08); border-left:3px solid #6366f1; padding:12px 14px; border-radius:6px; font-size:14px; white-space:pre-wrap;">${d.narrative.replace(/</g,'&lt;')}</div>
    ` : ''}

    <p class="text-muted" style="font-size:11px; margin-top:14px;">Generado ${new Date(d.generated_at).toLocaleString('es-ES')} · Esto es análisis educativo, no recomendación de compra/venta.</p>
    `;
}
