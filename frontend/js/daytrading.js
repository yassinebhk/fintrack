/**
 * Day Trading Lab — paper-only discretionary trading journal.
 * Fetches/creates/closes trades and renders the anti-noise verdict.
 */

const DT_API = window.API_BASE_URL || CONFIG?.API_BASE_URL || 'http://localhost:8000/api';

function dtEsc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
}

function dtFmtPct(v) {
    if (v === null || v === undefined) return '—';
    const sign = v > 0 ? '+' : '';
    return `${sign}${v.toFixed(2)}%`;
}

function dtFmtDate(iso) {
    if (!iso) return '—';
    try { return new Date(iso).toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit', year: 'numeric' }); }
    catch (e) { return iso; }
}

async function dtLoadNews() {
    const ticker = (document.getElementById('dtTicker').value || '').trim().toUpperCase();
    const out = document.getElementById('dtNewsResult');
    if (!ticker) { out.innerHTML = '<p class="text-muted">Escribe un ticker primero.</p>'; return; }
    out.innerHTML = '<p class="text-muted">Buscando noticias reales...</p>';
    try {
        const resp = await fetch(`${DT_API}/news/asset/${encodeURIComponent(ticker)}?limit=5`);
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);
        const items = data.news || [];
        if (items.length === 0) {
            out.innerHTML = '<p class="text-muted">No hay noticias recientes indexadas para este ticker. Búscalas tú mismo antes de escribir la tesis.</p>';
            return;
        }
        out.innerHTML = items.map(n => `
            <div style="border-left:3px solid var(--accent-primary); padding:6px 10px; margin-bottom:6px; font-size:13px;">
                <a href="${dtEsc(n.url)}" target="_blank" rel="noopener"><strong>${dtEsc(n.title)}</strong></a>
                <div class="text-muted" style="font-size:12px;">${dtEsc(n.source)} · ${dtEsc(n.date)}</div>
            </div>
        `).join('');
    } catch (err) {
        out.innerHTML = `<p class="text-muted">No se pudieron cargar noticias: ${dtEsc(err.message)}</p>`;
    }
}

async function dtOpenTrade() {
    const btn = document.getElementById('dtSubmitBtn');
    const msg = document.getElementById('dtFormMsg');
    const payload = {
        ticker: (document.getElementById('dtTicker').value || '').trim(),
        direction: document.getElementById('dtDirection').value,
        thesis: (document.getElementById('dtThesis').value || '').trim(),
        stake_eur: parseFloat(document.getElementById('dtStake').value),
        stop_loss_pct: parseFloat(document.getElementById('dtStopLoss').value),
        conviction: document.getElementById('dtConviction').value,
        news_url: (document.getElementById('dtNewsUrl').value || '').trim() || null,
    };
    const tpVal = document.getElementById('dtTakeProfit').value;
    if (tpVal) payload.take_profit_pct = parseFloat(tpVal);

    if (!payload.ticker || !payload.thesis || !payload.stake_eur || !payload.stop_loss_pct) {
        msg.innerHTML = '<div style="background:var(--negative-bg); border:1px solid var(--negative); color:var(--negative); border-radius:8px; padding:10px 14px;">Faltan campos obligatorios: ticker, tesis, cantidad y stop-loss.</div>';
        return;
    }

    btn.disabled = true;
    msg.innerHTML = '<p class="text-muted">Abriendo operación con precio real de mercado...</p>';
    try {
        const resp = await fetch(`${DT_API}/daytrading/trades`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const data = await resp.json();
        if (!resp.ok) {
            const detail = Array.isArray(data.detail) ? data.detail.map(d => d.msg).join('; ') : (data.detail || `HTTP ${resp.status}`);
            throw new Error(detail);
        }
        msg.innerHTML = `<div style="background:var(--positive-bg); border:1px solid var(--positive); color:var(--positive); border-radius:8px; padding:10px 14px;">Operación abierta en ${dtEsc(data.ticker)} a ${data.entry_price}.</div>`;
        document.getElementById('dtTicker').value = '';
        document.getElementById('dtThesis').value = '';
        document.getElementById('dtNewsUrl').value = '';
        document.getElementById('dtStake').value = '';
        document.getElementById('dtStopLoss').value = '';
        document.getElementById('dtTakeProfit').value = '';
        document.getElementById('dtNewsResult').innerHTML = '';
        dtRefresh();
    } catch (err) {
        msg.innerHTML = `<div style="background:var(--negative-bg); border:1px solid var(--negative); color:var(--negative); border-radius:8px; padding:10px 14px;">${dtEsc(err.message)}</div>`;
    } finally {
        btn.disabled = false;
    }
}

async function dtCloseTrade(id) {
    if (!confirm('¿Cerrar esta operación en papel ahora, al precio de mercado actual?')) return;
    try {
        const resp = await fetch(`${DT_API}/daytrading/trades/${id}/close`, { method: 'POST' });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);
        dtRefresh();
    } catch (err) {
        alert(`No se pudo cerrar: ${err.message}`);
    }
}

function dtRenderOpen(trades) {
    const body = document.getElementById('dtOpenBody');
    if (trades.length === 0) {
        body.innerHTML = '<tr><td colspan="8" class="text-center text-muted">Sin operaciones abiertas.</td></tr>';
        return;
    }
    body.innerHTML = trades.map(t => {
        const pnlColor = t.unrealized_pnl_pct == null ? '' : (t.unrealized_pnl_pct >= 0 ? 'var(--positive)' : 'var(--negative)');
        return `<tr>
            <td>${dtEsc(t.ticker)}</td>
            <td>${t.direction === 'long' ? '📈 Long' : '📉 Short'}</td>
            <td class="text-right">${t.entry_price.toFixed(4)}</td>
            <td class="text-right">${t.live_price != null ? t.live_price.toFixed(4) : '—'}</td>
            <td class="text-right" style="color:${pnlColor};">${dtFmtPct(t.unrealized_pnl_pct)}</td>
            <td class="text-right">${t.stop_loss.toFixed(4)}</td>
            <td>${dtFmtDate(t.opened_at)}</td>
            <td><button class="btn-secondary" style="font-size:12px; padding:4px 10px;" onclick="dtCloseTrade(${t.id})">Cerrar ahora</button></td>
        </tr>`;
    }).join('');
}

function dtRenderClosed(trades) {
    const body = document.getElementById('dtClosedBody');
    if (trades.length === 0) {
        body.innerHTML = '<tr><td colspan="7" class="text-center text-muted">Sin operaciones cerradas todavía.</td></tr>';
        return;
    }
    const reasonLabel = { stop_loss: '🛑 Stop-loss', take_profit: '🎯 Take-profit', manual: '✋ Manual', time_exit: '⏱️ Límite de tiempo' };
    body.innerHTML = trades.map(t => {
        const pnlColor = t.pnl_pct == null ? '' : (t.pnl_pct >= 0 ? 'var(--positive)' : 'var(--negative)');
        return `<tr>
            <td>${dtEsc(t.ticker)}</td>
            <td>${t.direction === 'long' ? '📈 Long' : '📉 Short'}</td>
            <td class="text-right">${t.entry_price.toFixed(4)}</td>
            <td class="text-right">${t.exit_price != null ? t.exit_price.toFixed(4) : '—'}</td>
            <td class="text-right" style="color:${pnlColor};">${dtFmtPct(t.pnl_pct)}</td>
            <td>${reasonLabel[t.close_reason] || dtEsc(t.close_reason)}</td>
            <td>${dtFmtDate(t.closed_at)}</td>
        </tr>`;
    }).join('');
}

function dtRenderReport(r) {
    const body = document.getElementById('dtReportBody');
    if (!r || r.n_closed === 0) {
        body.innerHTML = `
            <p><strong>0 operaciones cerradas todavía.</strong></p>
            <p class="text-muted">${dtEsc((r && r.readiness && r.readiness.verdict) || 'NO apto — sigue en papel.')}</p>
        `;
        return;
    }
    const rd = r.readiness || {};
    const verdictColor = rd.ready ? 'var(--positive)' : 'var(--warning)';
    body.innerHTML = `
        <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:12px; margin-bottom:14px;">
            <div><div class="text-muted" style="font-size:12px;">Operaciones cerradas</div><div style="font-size:20px; font-weight:700;">${r.n_closed} / 30</div></div>
            <div><div class="text-muted" style="font-size:12px;">Días de histórico</div><div style="font-size:20px; font-weight:700;">${r.span_days} / 60</div></div>
            <div><div class="text-muted" style="font-size:12px;">% de aciertos</div><div style="font-size:20px; font-weight:700;">${r.hit_rate_pct}%</div></div>
            <div><div class="text-muted" style="font-size:12px;">Alpha vs benchmark</div><div style="font-size:20px; font-weight:700;">${dtFmtPct(r.alpha_pct)}</div></div>
            <div><div class="text-muted" style="font-size:12px;">P&amp;L total (papel)</div><div style="font-size:20px; font-weight:700;">${r.total_pnl_eur}€</div></div>
            <div><div class="text-muted" style="font-size:12px;">p-valor</div><div style="font-size:20px; font-weight:700;">${r.p_value ?? '—'}</div></div>
        </div>
        <div style="background:${verdictColor}22; border:1px solid ${verdictColor}55; border-radius:8px; padding:12px 16px;">
            <strong style="color:${verdictColor};">${dtEsc(rd.verdict)}</strong>
        </div>
    `;
}

async function dtRefresh() {
    try {
        const [tradesResp, reportResp] = await Promise.all([
            fetch(`${DT_API}/daytrading/trades?status=all`),
            fetch(`${DT_API}/daytrading/report`),
        ]);
        const tradesData = await tradesResp.json();
        const reportData = await reportResp.json();
        const trades = tradesData.trades || [];
        dtRenderOpen(trades.filter(t => t.status === 'open'));
        dtRenderClosed(trades.filter(t => t.status === 'closed'));
        dtRenderReport(reportData);
    } catch (err) {
        console.error('Error loading day trading data:', err);
    }
}

window.renderDayTrading = dtRefresh;
