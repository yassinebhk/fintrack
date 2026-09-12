/**
 * Polymarket Lab - read-only scanner of crypto prediction markets vs Binance spot.
 * Paper trading / educational only.
 */

const PM_API = (window.API_BASE_URL || 'http://localhost:8000/api');

async function runPolymarketScan() {
    const btn = document.getElementById('pmScanBtn');
    const out = document.getElementById('pmScanResult');
    btn.disabled = true;
    out.innerHTML = '<p class="text-muted">Escaneando mercados de Polymarket y precios de Binance... (~5-10s)</p>';

    try {
        const resp = await fetch(`${PM_API}/polymarket/scan?limit=25`);
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);

        const markets = data.markets || [];
        if (markets.length === 0) {
            out.innerHTML = '<p class="text-muted">No se encontraron mercados cripto activos ahora mismo.</p>';
            return;
        }

        const rows = markets.map(m => {
            const yesPct = m.implied_probability_pct;
            const spot = m.binance_spot;
            const target = m.target_price;
            const noteHtml = m.note ? `<div style="font-size:12px; color:var(--warning); margin-top:4px;">⚡ ${m.note}</div>` : '';
            const linkHtml = m.url ? `<a href="${m.url}" target="_blank" rel="noopener" style="color:var(--accent-primary);">↗</a>` : '';
            return `
                <tr>
                    <td>
                        <div style="font-weight:500;">${(m.question || '').slice(0, 90)} ${linkHtml}</div>
                        ${noteHtml}
                    </td>
                    <td class="text-right mono">${yesPct != null ? yesPct + '%' : '—'}</td>
                    <td class="text-right mono">${m.binance_symbol || '—'}</td>
                    <td class="text-right mono">${spot != null ? '$' + Number(spot).toLocaleString('es-ES', {maximumFractionDigits: 2}) : '—'}</td>
                    <td class="text-right mono">${target != null ? '$' + Number(target).toLocaleString('es-ES') : '—'}</td>
                </tr>
            `;
        }).join('');

        out.innerHTML = `
            <p class="text-muted" style="margin-bottom:8px;">${markets.length} mercados · escaneado ${new Date(data.scanned_at).toLocaleTimeString('es-ES')}</p>
            <div class="table-container">
                <table class="manager-table">
                    <thead>
                        <tr>
                            <th>Mercado</th>
                            <th class="text-right">Prob. YES</th>
                            <th class="text-right">Símbolo</th>
                            <th class="text-right">Spot Binance</th>
                            <th class="text-right">Strike</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
            <p class="text-muted" style="font-size:11px; margin-top:10px;">${data.disclaimer || ''}</p>
        `;
    } catch (err) {
        out.innerHTML = `<div class="alert alert-error">Error: ${err.message}</div>`;
    } finally {
        btn.disabled = false;
    }
}

// ============================================
// Paper-trading ledger (per-user, private)
// ============================================

function pmEsc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function pmFmtPct(v) {
    if (v === undefined || v === null) return '—';
    const s = v > 0 ? '+' : '';
    return `${s}${Number(v).toLocaleString('es-ES', { maximumFractionDigits: 2 })}%`;
}

function pmRenderReport(r) {
    const box = document.getElementById('pmReportBody');
    if (!box) return;
    if (!r || !r.resolved) {
        box.innerHTML = `
            <p><strong>0 apuestas resueltas todavía</strong> ${r && r.open ? `(${r.open} abiertas esperando resolución)` : ''}</p>
            <p class="text-muted">${pmEsc((r && r.criteria && r.criteria.note) || 'Los mercados de predicción tardan semanas en resolverse — que aún no haya datos es normal, no un fallo.')}</p>
        `;
        return;
    }
    const crit = r.criteria || {};
    const verdictColor = crit.passed ? 'var(--positive)' : 'var(--warning)';
    box.innerHTML = `
        <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:12px; margin-bottom:14px;">
            <div><div class="text-muted" style="font-size:12px;">Resueltas / abiertas</div><div style="font-size:20px; font-weight:700;">${r.resolved} / ${r.open}</div></div>
            <div><div class="text-muted" style="font-size:12px;">% de aciertos</div><div style="font-size:20px; font-weight:700;">${r.hit_rate_pct}%</div></div>
            <div><div class="text-muted" style="font-size:12px;">Rentabilidad neta / apuesta</div><div style="font-size:20px; font-weight:700;">${pmFmtPct(r.mean_net_roi_per_bet_pct)}</div></div>
            <div><div class="text-muted" style="font-size:12px;">P&amp;L acumulado (papel)</div><div style="font-size:20px; font-weight:700;">${r.total_pnl}€</div></div>
            <div><div class="text-muted" style="font-size:12px;">Brier modelo vs mercado</div><div style="font-size:20px; font-weight:700;">${r.model_brier ?? '—'} / ${r.market_brier ?? '—'}</div></div>
            <div><div class="text-muted" style="font-size:12px;">IC95 rentabilidad neta</div><div style="font-size:20px; font-weight:700;">${pmFmtPct(r.net_roi_ci95_low_pct)}</div></div>
        </div>
        <div style="background:${verdictColor}22; border:1px solid ${verdictColor}55; border-radius:8px; padding:12px 16px;">
            <strong style="color:${verdictColor};">🚦 ${pmEsc(crit.verdict || (crit.passed ? 'APTO para piloto mínimo real' : 'NO apto todavía — sigue en papel'))}</strong>
        </div>
    `;
}

function pmRenderLedger(bets) {
    const tbody = document.getElementById('pmLedgerBody');
    if (!tbody) return;
    if (!bets || bets.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center text-muted" style="padding:2rem;">Sin apuestas registradas todavía. Pulsa "Actualizar ahora" para buscar señales.</td></tr>`;
        return;
    }
    tbody.innerHTML = bets.map(b => {
        const isOpen = b.status === 'open';
        const statusBadge = isOpen
            ? `<span class="type-badge" style="background:var(--warning);">Abierta</span>`
            : `<span class="type-badge" style="background:${b.won ? 'var(--positive)' : 'var(--negative)'};">${b.won ? 'Ganada' : 'Perdida'}</span>`;
        const link = b.url ? `<a href="${pmEsc(b.url)}" target="_blank" rel="noopener" style="color:var(--accent-primary);">↗</a>` : '';
        const modelP = b.model_prob_yes != null ? `${(b.model_prob_yes * 100).toFixed(0)}%` : '—';
        const marketP = b.implied_prob_yes != null ? `${(b.implied_prob_yes * 100).toFixed(0)}%` : '—';
        const pnl = b.pnl != null ? `${b.pnl > 0 ? '+' : ''}${b.pnl}€` : '—';
        return `
            <tr>
                <td><div style="max-width:280px;">${pmEsc((b.question || '').slice(0, 90))} ${link}</div></td>
                <td class="text-right mono">${pmEsc(b.side)}</td>
                <td class="text-right mono">${modelP}</td>
                <td class="text-right mono">${marketP}</td>
                <td class="text-right mono">${b.stake}€</td>
                <td class="text-right mono ${b.pnl > 0 ? 'positive' : (b.pnl < 0 ? 'negative' : '')}">${pnl}</td>
                <td class="text-right">${statusBadge}</td>
            </tr>
        `;
    }).join('');
}

async function pmLoadLab() {
    const reportBox = document.getElementById('pmReportBody');
    if (reportBox) reportBox.innerHTML = '<p class="text-muted">Cargando tu historial…</p>';
    try {
        const [reportResp, ledgerResp] = await Promise.all([
            fetch(`${PM_API}/polymarket/lab/report`, { credentials: 'same-origin' }),
            fetch(`${PM_API}/polymarket/lab/ledger?limit=100`, { credentials: 'same-origin' }),
        ]);
        if (reportResp.status === 401 || ledgerResp.status === 401) {
            if (reportBox) reportBox.innerHTML = '<p class="text-muted">Inicia sesión para ver tu historial de apuestas en papel.</p>';
            return;
        }
        const report = await reportResp.json();
        const ledger = await ledgerResp.json();
        pmRenderReport(report);
        pmRenderLedger(ledger.bets || []);
    } catch (err) {
        if (reportBox) reportBox.innerHTML = `<div class="alert alert-error">Error al cargar tu historial: ${err.message}</div>`;
    }
}

async function pmRunLab() {
    const btn = document.getElementById('pmRunBtn');
    if (btn) btn.disabled = true;
    try {
        const resp = await fetch(`${PM_API}/polymarket/lab/run?digest=false`, { method: 'POST', credentials: 'same-origin' });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        if (window.showToast) window.showToast('Buscando nuevas señales y resolviendo apuestas maduras… tarda unos segundos', 'info');
        setTimeout(pmLoadLab, 6000);
    } catch (err) {
        if (window.showToast) window.showToast('Error al ejecutar el lab: ' + err.message, 'error');
    } finally {
        if (btn) btn.disabled = false;
    }
}

async function pmResetLab() {
    if (!confirm('¿Seguro que quieres borrar TODO tu historial de apuestas en papel de Polymarket Lab? No se puede deshacer.')) return;
    try {
        const resp = await fetch(`${PM_API}/polymarket/lab/reset`, { method: 'POST', credentials: 'same-origin' });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        if (window.showToast) window.showToast('Historial reiniciado', 'success');
        pmLoadLab();
    } catch (err) {
        if (window.showToast) window.showToast('Error al reiniciar: ' + err.message, 'error');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const nav = document.querySelector('[data-page="polymarket"]');
    if (nav) {
        nav.addEventListener('click', () => {
            pmLoadLab();
        });
    }
});
