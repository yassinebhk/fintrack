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
        const ex = document.getElementById('transactionsExport');
        if (ex && window.exportToolbarHTML) ex.innerHTML = exportToolbarHTML('transactionsCard', 'transacciones');
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center" style="padding:24px; color:var(--negative);">No se pudieron cargar las transacciones: ${err.message}</td></tr>`;
    }
}

function renderTransactions() {
    const tbody = document.getElementById('transactionsBody');
    if (!tbody) return;

    const type = (document.getElementById('txType') || {}).value || 'all';
    const from = (document.getElementById('txDateFrom') || {}).value || '';
    const to = (document.getElementById('txDateTo') || {}).value || '';
    const q = ((document.getElementById('txSearch') || {}).value || '').trim().toLowerCase();

    let list = _txAll.slice();
    if (type !== 'all') list = list.filter(t => t.type === type);
    if (from) list = list.filter(t => (t.executed_at || '').slice(0, 10) >= from);
    if (to) list = list.filter(t => (t.executed_at || '').slice(0, 10) <= to);
    if (q) {
        list = list.filter(t => {
            const name = (typeof getAssetName === 'function' ? getAssetName(t.ticker) : '') || '';
            return (t.ticker || '').toLowerCase().includes(q)
                || name.toLowerCase().includes(q)
                || (t.broker || '').toLowerCase().includes(q)
                || (t.notes || '').toLowerCase().includes(q);
        });
    }

    if (!list.length) {
        const msg = _txAll.length
            ? 'No hay transacciones que coincidan con el filtro.'
            : 'Aún no hay transacciones registradas. Pulsa "+ Nueva Transacción", o registra aportaciones desde <strong>Gestionar Cartera</strong> o por <strong>Telegram</strong> (ej.: "mete 50€ al oro desde Kraken").';
        tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted" style="padding:30px;">${msg}</td></tr>`;
        renderTransactionsFooter([]);
        return;
    }

    const typeLabel = {
        buy: '🟢 Compra', sell: '🔴 Venta', dividend: '💰 Dividendo',
        deposit: '⬆️ Ingreso', withdrawal: '⬇️ Retirada', fee: '💸 Comisión',
    };
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
            <td><span class="ticker-link" onclick="showAssetDetail('${t.ticker}')" style="cursor:pointer;" title="Ver detalle de ${(assetName || t.ticker).replace(/"/g, '&quot;')}">${assetName ? `${assetName}<br><span class="text-muted" style="font-family: var(--font-mono); font-size:12px;">${t.ticker}</span>` : `<span style="font-family: var(--font-mono); font-weight: 600;">${t.ticker}</span>`}</span></td>
            <td class="text-right mono">${fmt(t.quantity, 6)}</td>
            <td class="text-right mono">${fmt(t.price)} ${cur}</td>
            <td class="text-right mono">${fmt(total)} ${cur}</td>
            <td>${t.broker || '—'}</td>
            <td><button onclick="deleteTransaction(${t.id})" title="Eliminar" style="background:none; border:none; cursor:pointer; font-size:15px;">🗑️</button></td>
        </tr>`;
    }).join('');

    renderTransactionsFooter(list);
}

// Totals footer for the (filtered) transaction list: gross money moved plus a
// buy / sell+dividend breakdown, each grouped by currency. Responds to the
// active filters, so filtering by "Compras" shows exactly what you've invested.
function renderTransactionsFooter(list) {
    const foot = document.getElementById('transactionsFoot');
    if (!foot) return;
    if (!list.length) { foot.innerHTML = ''; return; }

    const money = t => (t.quantity || 0) * (t.price || 0);
    const gross = sumByCurrency(list, t => Math.abs(money(t)), t => t.currency);
    const buys = sumByCurrency(list.filter(t => t.type === 'buy'), money, t => t.currency);
    const ins = sumByCurrency(list.filter(t => t.type === 'sell' || t.type === 'dividend'), money, t => t.currency);

    const lines = [`<span class="text-muted">Movido</span>${formatByCurrency(gross)}`];
    if (Object.keys(buys).length) lines.push(`<span class="text-muted">Compras</span>${formatByCurrency(buys)}`);
    if (Object.keys(ins).length) lines.push(`<span class="text-muted">Ventas+div.</span>${formatByCurrency(ins)}`);

    const n = list.length;
    foot.innerHTML = `<tr class="totals-row">
        <td colspan="5" style="font-weight:600;">Σ Totales · ${n} transacci${n === 1 ? 'ón' : 'ones'}</td>
        <td class="text-right mono" style="line-height:1.75;">${lines.join('<br>')}</td>
        <td colspan="2"></td>
    </tr>`;
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
    const search = document.getElementById('txSearch');
    if (search) search.addEventListener('input', renderTransactions);
});
