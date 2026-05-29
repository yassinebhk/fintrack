/**
 * Position review — objective keep/trim/rotate signals per holding.
 * Forward-looking (not based on entry price); flags the disposition effect.
 */
const PR_API = (window.API_BASE_URL || 'http://localhost:8000/api');

const PR_SIGNAL = {
    ROTAR:    { color: '#ef4444', emoji: '🔴', label: 'Rotar' },
    REDUCIR:  { color: '#f59e0b', emoji: '🟠', label: 'Reducir' },
    VIGILAR:  { color: '#eab308', emoji: '🟡', label: 'Vigilar' },
    MANTENER: { color: '#10b981', emoji: '🟢', label: 'Mantener' },
    SIN_DATOS:{ color: '#64748b', emoji: '⚪', label: 'Sin datos' },
};

async function loadPositionReview() {
    const btn = document.getElementById('btnReviewPositions');
    const box = document.getElementById('positionReviewContent');
    if (btn) btn.disabled = true;
    box.innerHTML = '<div style="padding:18px; text-align:center;"><div class="spinner"></div><p class="text-muted" style="margin-top:10px;">Analizando con señales objetivas…</p></div>';
    try {
        const resp = await fetch(`${PR_API}/positions/review`, { cache: 'no-store' });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);
        renderPositionReview(data);
    } catch (err) {
        box.innerHTML = `<div class="alert alert-error">No se pudo analizar: ${err.message}</div>`;
    } finally {
        if (btn) btn.disabled = false;
    }
}

function renderPositionReview(data) {
    const box = document.getElementById('positionReviewContent');
    const reviews = data.reviews || [];
    if (!reviews.length) { box.innerHTML = '<p class="text-muted">No hay posiciones para revisar.</p>'; return; }
    const s = data.summary || {};

    const att = s.attention_eur || 0;
    const summary = `<div style="display:flex; gap:10px; flex-wrap:wrap; margin:8px 0 8px;">
        ${[['ROTAR',s.rotar],['REDUCIR',s.reducir],['VIGILAR',s.vigilar],['MANTENER',s.mantener]].map(([k,n]) => {
            const c = PR_SIGNAL[k];
            return `<span style="background:${c.color}22; color:${c.color}; padding:3px 10px; border-radius:12px; font-size:13px;">${c.emoji} ${c.label}: ${n||0}</span>`;
        }).join('')}
    </div>
    <div style="font-size:13px; margin:0 0 14px; padding:8px 12px; background:rgba(239,68,68,0.08); border-radius:8px;">
        💰 <strong>Dinero que de verdad pide atención</strong> (posiciones materiales a rotar/reducir): <strong>${att.toLocaleString('es-ES',{maximumFractionDigits:0})}€</strong>.
        ${(s.rotar||0) > (s.rotar_material||0) ? `<span class="text-muted"> (${(s.rotar||0)-(s.rotar_material||0)} señal(es) son de importe insignificante — ignóralas.)</span>` : ''}
    </div>`;

    const cards = reviews.map(r => {
        const c = PR_SIGNAL[r.signal] || PR_SIGNAL.SIN_DATOS;
        const m = r.metrics || {};
        const pnlCls = (r.pnl_pct||0) >= 0 ? 'value-positive' : 'value-negative';
        const metricsRow = m.momentum_pct !== undefined ? `
            <div style="display:flex; gap:14px; flex-wrap:wrap; font-size:12px; color:#94a3b8; margin:6px 0;">
                <span>Tendencia: <strong>${m.above_sma200 ? 'sobre SMA200 📈' : 'bajo SMA200 📉'}</strong></span>
                <span>Momentum: <strong class="${(m.momentum_pct||0)>=0?'value-positive':'value-negative'}">${m.momentum_pct>=0?'+':''}${m.momentum_pct}%</strong></span>
                ${m.rsi!=null?`<span>RSI: <strong>${Math.round(m.rsi)}</strong></span>`:''}
                ${m.drawdown_from_peak_pct!=null?`<span>Desde máximo: <strong class="value-negative">${m.drawdown_from_peak_pct}%</strong></span>`:''}
                ${m.sharpe!=null?`<span>Sharpe: <strong>${m.sharpe}</strong></span>`:''}
            </div>` : '';
        const dim = r.immaterial ? 'opacity:0.6;' : '';
        const matBadge = r.immaterial ? ' <span class="text-muted" style="font-size:11px;">💤 importe insignificante</span>' : '';
        return `
        <div class="card" style="margin-bottom:12px; border-left:4px solid ${c.color}; ${dim}">
            <div style="display:flex; justify-content:space-between; align-items:center; gap:8px; flex-wrap:wrap;">
                <h4 style="margin:0;">${r.name} <span class="text-muted" style="font-size:12px;">${r.ticker}</span>${matBadge}</h4>
                <span style="background:${c.color}22; color:${c.color}; padding:3px 12px; border-radius:12px; font-weight:600;">${c.emoji} ${c.label}</span>
            </div>
            <p class="text-muted" style="font-size:12px; margin:4px 0;">Invertido <strong>${(r.invested_eur||0).toLocaleString('es-ES',{maximumFractionDigits:0})}€</strong> → vale <strong>${(r.value_eur||0).toLocaleString('es-ES',{maximumFractionDigits:0})}€</strong> · P&amp;L <span class="mono ${pnlCls}">${(r.pnl_eur||0)>=0?'+':''}${(r.pnl_eur||0).toLocaleString('es-ES',{maximumFractionDigits:0})}€ (${(r.pnl_pct||0)>=0?'+':''}${r.pnl_pct}%)</span> · peso ${r.weight_pct}%</p>
            ${metricsRow}
            <ul style="margin:6px 0 0; padding-left:18px; font-size:13px;">${(r.reasons||[]).map(x=>`<li>${x}</li>`).join('')}</ul>
            ${r.bias_flag ? `<div style="margin-top:8px; background:#f59e0b18; border:1px solid #f59e0b55; border-radius:8px; padding:8px 12px; font-size:13px;">${r.bias_flag}</div>` : ''}
        </div>`;
    }).join('');

    box.innerHTML = summary + cards +
        `<p class="text-muted" style="font-size:11px; margin-top:10px;">${data.disclaimer || ''}</p>`;
}
