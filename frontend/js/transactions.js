/**
 * Transactions page — loads and renders the real transaction history from the API.
 * (Previously the table showed a hardcoded "empty" row and was never wired up.)
 */
const TX_API = (window.API_BASE_URL || 'http://localhost:8000/api');
let _txAll = [];

async function loadTransactions() {
    const tbody = document.getElementById('transactionsBody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted" style="padding:24px;">Cargando transacciones…</td></tr>';
    try {
        const resp = await fetch(`${TX_API}/transactions?limit=300`, { cache: 'no-store' });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);
        _txAll = Array.isArray(data) ? data : [];
        renderTransactions();
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center" style="padding:24px; color:#ef4444;">No se pudieron cargar las transacciones: ${err.message}</td></tr>`;
    }
}

function renderTransactions() {
    const tbody = document.getElementById('transactionsBody');
    if (!tbody) return;

    const type = (document.getElementById('txType') || {}).value || 'all';
    const from = (document.getElementById('txDateFrom') || {}).value || '';
    const to = (document.getElementById('txDateTo') || {}).value || '';

    let list = _txAll.slice();
    if (type !== 'all') list = list.filter(t => t.type === type);
    if (from) list = list.filter(t => (t.executed_at || '').slice(0, 10) >= from);
    if (to) list = list.filter(t => (t.executed_at || '').slice(0, 10) <= to);

    if (!list.length) {
        const msg = _txAll.length
            ? 'No hay transacciones que coincidan con el filtro.'
            : 'Aún no hay transacciones registradas. Pulsa "+ Nueva Transacción", o registra aportaciones desde <strong>Gestionar Cartera</strong> o por <strong>Telegram</strong> (ej.: "mete 50€ al oro desde Kraken").';
        tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted" style="padding:30px;">${msg}</td></tr>`;
        return;
    }

    const typeLabel = { buy: '🟢 Compra', sell: '🔴 Venta', dividend: '💰 Dividendo' };
    const fmt = (n, d = 2) => (n || 0).toLocaleString('es-ES', { minimumFractionDigits: d, maximumFractionDigits: d });
    tbody.innerHTML = list.map(t => {
        const date = (t.executed_at || '').slice(0, 10);
        const total = (t.quantity || 0) * (t.price || 0);
        const cur = t.currency || 'EUR';
        const title = t.notes ? ` title="${(t.notes + '').replace(/"/g, '&quot;')}"` : '';
        const assetName = getAssetName(t.ticker);
        return `<tr${title}>
            <td>${date}</td>
            <td>${typeLabel[t.type] || t.type}</td>
            <td>${assetName ? `${assetName}<br><span class="text-muted" style="font-family: var(--font-mono); font-size:12px;">${t.ticker}</span>` : `<span style="font-family: var(--font-mono); font-weight: 600;">${t.ticker}</span>`}</td>
            <td class="text-right mono">${fmt(t.quantity, 6)}</td>
            <td class="text-right mono">${fmt(t.price)} ${cur}</td>
            <td class="text-right mono">${fmt(total)} ${cur}</td>
            <td>${t.broker || '—'}</td>
            <td><button onclick="deleteTransaction(${t.id})" title="Eliminar" style="background:none; border:none; cursor:pointer; font-size:15px;">🗑️</button></td>
        </tr>`;
    }).join('');
}

async function deleteTransaction(id) {
    if (!confirm('¿Eliminar esta transacción del registro?')) return;
    try {
        const resp = await fetch(`${TX_API}/transactions/${id}`, { method: 'DELETE' });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        await loadTransactions();
    } catch (err) {
        alert('No se pudo eliminar: ' + err.message);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const nav = document.querySelector('[data-page="transactions"]');
    if (nav) nav.addEventListener('click', loadTransactions);
    ['txType', 'txDateFrom', 'txDateTo'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('change', renderTransactions);
    });
});
