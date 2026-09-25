/**
 * Nav groups + sub-tabs — compacts the sidebar into a few top-level entries
 * (Dashboard · Cartera · Análisis · Watchlist · Alertas · Inteligencia · Labs ·
 * Aprender). A grouped section's member pages show as a secondary sub-tab bar
 * under the header.
 *
 * This is purely a PRESENTATION layer: it never changes the pages themselves.
 * Every action ends by clicking the existing (now hidden) .nav-item[data-page=X],
 * so initNavigation, the hash router and every inline [data-page].click() keep
 * working exactly as before. The hidden .nav-subitems in index.html exist only to
 * keep those .nav-item elements in the DOM.
 */
const NAV_GROUPS = {
    cartera:      { label: 'Cartera',      icon: '💼', pages: [['portfolio-manager', 'Posiciones'], ['transactions', 'Transacciones'], ['journal', 'Diario'], ['goals', 'Objetivos']] },
    analisis:     { label: 'Análisis',     icon: '📈', pages: [['analysis', 'Mercado'], ['position-review', '¿Vender o mantener?'], ['daily-summary', 'Resumen diario'], ['calculators', 'Calculadoras']] },
    inteligencia: { label: 'Recomendaciones', icon: '💡', pages: [['opportunities', 'Oportunidades'], ['superinvestors', 'Superinversores'], ['ai-advisor', 'Asesor IA'], ['news', 'Noticias']] },
    labs:         { label: 'Labs',         icon: '🧪', pages: [['scorecard', 'Eficacia'], ['daytrading', 'Trading Diario'], ['backtest', 'Backtest Lab'], ['polymarket', 'Polymarket Lab']] },
    aprender:     { label: 'Aprender',     icon: '📚', pages: [['learn', 'Guía'], ['docs', 'Documentación']] },
};

// page -> group id
const _PAGE_GROUP = {};
Object.entries(NAV_GROUPS).forEach(([gid, g]) => g.pages.forEach(([p]) => { _PAGE_GROUP[p] = gid; }));

// Navigate by reusing ALL existing logic: click the (hidden) real nav item.
function _navGoToPage(pageName) {
    const el = document.querySelector(`.nav-item[data-page="${pageName}"]`);
    if (el) el.click();
}

// Reflect the active page in the sub-tab bar + group-header highlight. Called on
// every navigation (manual, hash router, inline click, asset-detail) so the two
// stay in sync no matter how the page was reached.
function syncSubtabs(activePage) {
    const bar = document.getElementById('subtabBar');
    if (!bar) return;
    const gid = _PAGE_GROUP[activePage];

    document.querySelectorAll('.nav-group').forEach(g =>
        g.classList.toggle('active', g.dataset.group === gid));

    if (!gid) { bar.hidden = true; bar.innerHTML = ''; return; }
    const g = NAV_GROUPS[gid];
    bar.innerHTML = `<span class="subtab-group-label">${g.icon} ${g.label}</span>` + g.pages.map(([p, label]) =>
        `<button type="button" class="subtab-btn${p === activePage ? ' active' : ''}" data-page="${p}">${label}</button>`).join('');
    bar.hidden = false;
    bar.querySelectorAll('.subtab-btn').forEach(b =>
        b.addEventListener('click', () => _navGoToPage(b.dataset.page)));
}
window.syncSubtabs = syncSubtabs;

function initNavGroups() {
    // Group header → open its first child page (which reveals the sub-tab bar).
    document.querySelectorAll('.nav-group').forEach(group => {
        group.addEventListener('click', (e) => {
            if (e.target.closest('.nav-item')) return;  // a real sub-item handles itself
            const g = NAV_GROUPS[group.dataset.group];
            if (g && g.pages.length) _navGoToPage(g.pages[0][0]);
        });
    });

    // Any page opened (manual, hash, inline .click()) resyncs the sub-tabs.
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => syncSubtabs(item.dataset.page));
    });

    // Initial state: reflect whatever page is active on load.
    const active = document.querySelector('.page.active');
    syncSubtabs(active ? active.id.replace(/^page-/, '') : 'dashboard');
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNavGroups);
} else {
    initNavGroups();
}
