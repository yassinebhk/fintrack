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
