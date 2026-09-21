/**
 * 🔔 Alertas — real system alerts (AlertsEngine: portfolio/asset moves,
 * drawdown, bearish news, watchlist setups — evaluated every ~5 min, also
 * pushed to Telegram) + real trailing-stop management. Previously this page
 * was a static mockup: 3 hardcoded rows and a "+ Nueva Alerta" form with NO
 * submit handler anywhere — filling it out and clicking "Crear Alerta" did
 * nothing (worse: a plain <form> with no JS interception silently reloads
 * the SPA on submit). The real backend (AlertsEngine + trailing_stops) has
 * always existed; it just had no UI until now.
 */
const ALERTS_API = window.API_BASE_URL || '/api';
let _trailingStops = [];

async function loadAlertsPage() {
    loadRecentAlerts();
    loadTrailingStops();
}

async function loadRecentAlerts() {
    const el = document.getElementById('alertsList');
    if (!el) return;
    try {
        const r = await fetch(`${ALERTS_API}/alerts?limit=30`, { cache: 'no-store' });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const alerts = await r.json();
        if (!alerts.length) {
            el.innerHTML = '<p class="text-muted">Sin alertas todavía. El motor revisa tu cartera cada ~5 minutos y avisará aquí (y por Telegram) si algo relevante pasa.</p>';
            return;
        }
        const sevMeta = {
            critical: { color: 'var(--negative)', icon: '🚨' },
            warning: { color: 'var(--warning)', icon: '⚠️' },
            info: { color: 'var(--info)', icon: 'ℹ️' },
        };
        el.innerHTML = alerts.map(a => {
            const m = sevMeta[a.severity] || sevMeta.info;
            const when = new Date(a.triggered_at).toLocaleString('es-ES', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
            const isOpen = a.status === 'open';
            return `<div class="card" style="margin-bottom:10px; border-left:3px solid ${m.color}; ${isOpen ? '' : 'opacity:0.65;'}">
                <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:10px; flex-wrap:wrap;">
                    <div>
                        <strong>${m.icon} ${a.title}</strong>
                        <div class="text-muted" style="font-size:11px; margin-top:2px;">${when}${a.delivered_telegram ? ' · enviada a Telegram' : ''}</div>
                    </div>
                    ${isOpen ? `<button class="btn-secondary" style="padding:3px 10px; font-size:12px;" onclick="ackAlert(${a.id})">Marcar vista</button>` : `<span class="text-muted" style="font-size:11px;">✓ vista</span>`}
                </div>
                <p style="margin:8px 0 0; font-size:13px; white-space:pre-line;">${a.body}</p>
                ${a.link ? `<a href="${a.link}" style="font-size:12px; color:var(--info);">${a.link_text || 'Ver más'} →</a>` : ''}
            </div>`;
        }).join('');
    } catch (err) {
        el.innerHTML = `<p class="text-muted" style="color:var(--negative);">No se pudieron cargar las alertas: ${err.message}</p>`;
    }
}

async function ackAlert(id) {
    try {
        await fetch(`${ALERTS_API}/alerts/${id}/ack`, { method: 'POST' });
        loadRecentAlerts();
    } catch (err) { /* noop */ }
}

async function loadTrailingStops() {
    const el = document.getElementById('trailingStopsList');
    if (!el) return;
    try {
        const r = await fetch(`${ALERTS_API}/alerts/trailing-stops`, { cache: 'no-store' });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = await r.json();
        _trailingStops = data.stops || [];
        if (!_trailingStops.length) {
            el.innerHTML = '<p class="text-muted">No tienes trailing stops armados. Pulsa "+ Nuevo trailing stop" arriba.</p>';
            return;
        }
        const fmt = (v, cur) => (v == null ? '—' : (+v).toLocaleString('es-ES', { maximumFractionDigits: 4 }) + (cur ? ' ' + cur : ''));
        el.innerHTML = `<div class="table-container"><table class="manager-table">
            <thead><tr><th>Activo</th><th class="text-right">Máximo registrado</th><th class="text-right">Cae y avisa a</th><th class="text-right">Objetivo</th><th>Estado</th><th></th></tr></thead>
            <tbody>${_trailingStops.map(s => {
                const stopPrice = s.peak ? s.peak * (1 - (s.trailing_pct || 0) / 100) : null;
                return `<tr>
                    <td>${s.label || s.ticker} <span class="text-muted mono" style="font-size:11px;">${s.ticker}</span></td>
                    <td class="text-right mono">${fmt(s.peak, s.currency)}</td>
                    <td class="text-right mono">${s.trailing_pct}% (${fmt(stopPrice, s.currency)})</td>
                    <td class="text-right mono">${s.target_price ? fmt(s.target_price, s.currency) + (s.target_hit ? ' ✓' : '') : '—'}</td>
                    <td>${s.active ? '<span class="value-positive">Activo</span>' : '<span class="text-muted">Disparado</span>'}</td>
                    <td class="text-right"><button class="btn-secondary" style="background:transparent; color:var(--negative); padding:2px 8px;" onclick="deleteTrailingStop('${s.ticker}')" title="Eliminar">✕</button></td>
                </tr>`;
            }).join('')}</tbody>
        </table></div>`;
    } catch (err) {
        el.innerHTML = `<p class="text-muted" style="color:var(--negative);">No se pudieron cargar los trailing stops: ${err.message}</p>`;
    }
}

async function deleteTrailingStop(ticker) {
    if (!confirm(`¿Eliminar el trailing stop de ${ticker}?`)) return;
    try {
        const r = await fetch(`${ALERTS_API}/alerts/trailing-stop/${encodeURIComponent(ticker)}`, { method: 'DELETE' });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        loadTrailingStops();
    } catch (err) {
        alert('No se pudo eliminar: ' + err.message);
    }
}

async function submitAlertForm(e) {
    e.preventDefault();
    const btn = document.getElementById('tsSubmitBtn');
    const msg = document.getElementById('tsMsg');
    const ticker = document.getElementById('tsTicker').value.trim().toUpperCase();
    const trailingPct = parseFloat(document.getElementById('tsPct').value);
    const targetPrice = parseFloat(document.getElementById('tsTarget').value) || null;
    if (!ticker || !trailingPct) {
        msg.textContent = 'Activo y % de caída son obligatorios.';
        msg.style.color = 'var(--negative)';
        return;
    }
    btn.disabled = true;
    msg.textContent = 'Buscando precio actual y armando…';
    msg.style.color = 'var(--text-secondary)';
    try {
        // Seed the peak with the live price so the stop is accurate immediately,
        // instead of waiting for the next ~5min evaluation cycle to pick it up.
        let peak = null, currency = '';
        try {
            const pr = await fetch(`${ALERTS_API}/price/${encodeURIComponent(ticker)}`);
            if (pr.ok) {
                const pd = await pr.json();
                peak = pd.price || null;
                currency = pd.currency || '';
            }
        } catch (e) { /* best-effort — the evaluator will pick up a peak on its next run anyway */ }

        const r = await fetch(`${ALERTS_API}/alerts/trailing-stop`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ticker, trailing_pct: trailingPct, peak, currency, target_price: targetPrice }),
        });
        if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `HTTP ${r.status}`);
        document.getElementById('alertModal').classList.remove('active');
        document.getElementById('alertForm').reset();
        document.getElementById('tsPct').value = 12;
        loadTrailingStops();
    } catch (err) {
        msg.textContent = 'No se pudo armar: ' + err.message;
        msg.style.color = 'var(--negative)';
    } finally {
        btn.disabled = false;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const nav = document.querySelector('[data-page="alerts"]');
    if (nav) nav.addEventListener('click', () => setTimeout(loadAlertsPage, 100));

    const form = document.getElementById('alertForm');
    if (form) form.addEventListener('submit', submitAlertForm);
});
