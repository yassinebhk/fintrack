/**
 * Personal Finance Dashboard v2.0 - Frontend Application
 * Handles data fetching, chart rendering, and UI updates
 */

// Configuration - Auto-detects production vs development
// In production the backend serves both the API and this HTML from the same origin.
// In local dev we typically run the frontend on :3000 and the backend on :8000.
const isProduction = window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1';
const API_BASE_URL = isProduction
    ? `${window.location.origin}/api`
    : 'http://localhost:8000/api';

const CONFIG = {
    API_BASE_URL: API_BASE_URL,
    REFRESH_INTERVAL: 60000, // 1 minute
    CHART_COLORS: ['#00d4aa', '#6366f1', '#f59e0b', '#ec4899', '#8b5cf6', '#14b8a6'],
};

console.log('FinTrack API URL:', CONFIG.API_BASE_URL);

// Export for other scripts
window.API_BASE_URL = CONFIG.API_BASE_URL;

// State
let portfolioData = null;
let charts = {
    portfolio: null,
    type: null,
    broker: null,
    currency: null,
    benchmark: null
};
let currentPeriod = 30;
let sortColumn = 'market_value';
let sortDirection = 'desc';

// Single source of truth for asset display names/icons/colors — verified 2026-08
// against the real Trade Republic / MyInvestor / Kraken records. Every other
// script (asset-analysis.js, portfolio-manager.js, transactions.js, backtest.js)
// reads this same object; do not declare a second copy anywhere, and do not
// "correct" an entry without re-checking a real CSV/broker export first
// (LYX0F.DE and IE00BYX5NX33 were swapped here for months, and this dict used
// to also mislabel the Gold ETC, IE00B4ND3602, as "iShares MSCI World").
// `short` is for tight spaces (correlation matrix headers, chart legends)
// where "Fidelity MSCI World P-Acc" would overflow — keep it recognizable
// at a glance, matching how the user talks about these positions.
// `about` is static, hand-written educational content (what it is, what it
// tracks/how it works, brief history) — deliberately NOT LLM-generated, since
// facts like inception dates or index methodology are exactly the kind of
// thing a model can quietly get wrong. Verify before editing, same rule as
// the rest of this object.
const ASSET_DISPLAY_NAMES = {
    'BTC': { name: 'Bitcoin', short: 'Bitcoin', icon: '₿', color: '#f7931a', about:
        `Bitcoin es la primera criptomoneda descentralizada, descrita en un whitepaper publicado en octubre de 2008 bajo el seudónimo Satoshi Nakamoto (su identidad real nunca se ha confirmado), poco después de la crisis financiera de ese año. La red arrancó el 3 de enero de 2009.

Funciona sobre una blockchain: un libro de cuentas público replicado por miles de nodos independientes. Las transacciones se validan mediante "prueba de trabajo" (proof-of-work) — los mineros compiten resolviendo cálculos costosos en energía, y quien lo logra primero añade el siguiente bloque y recibe una recompensa en bitcoins nuevos.

Su rasgo distintivo es la oferta fija: nunca habrá más de 21 millones de bitcoins, a diferencia del dinero tradicional, que los bancos centrales pueden emitir sin límite. Cada ~4 años ocurre el "halving", que reduce a la mitad la recompensa de los mineros y ralentiza la creación de nuevas unidades. No hay empresa, gobierno ni activo físico detrás — su valor depende por completo de la demanda de quienes lo usan como reserva de valor o medio de pago.` },
    'ETH': { name: 'Ethereum', short: 'Ethereum', icon: 'Ξ', color: '#627eea', about:
        `Ethereum es una plataforma descentralizada para ejecutar "contratos inteligentes" — programas que se ejecutan automáticamente si se cumplen ciertas condiciones —, lanzada en julio de 2015 por Vitalik Buterin junto a varios cofundadores. A diferencia de Bitcoin, pensado sobre todo como dinero digital, Ethereum es infraestructura sobre la que se construyen aplicaciones: finanzas descentralizadas (DeFi), NFTs, DAOs y muchas otras.

En septiembre de 2022 completó "The Merge", el cambio de su mecanismo de validación de "prueba de trabajo" (minería con GPUs) a "prueba de participación" (proof-of-stake), reduciendo su consumo energético en más de un 99%.

El token ETH sirve para pagar el "gas" (la comisión) de cada operación en la red y para hacer staking (bloquear ETH para ayudar a validar la red a cambio de recompensas). No tiene un límite de oferta fijo como Bitcoin, pero desde 2021 una parte de cada comisión se "quema" (se destruye), lo que puede hacerlo deflacionario en periodos de mucho uso de la red.` },
    'SOL': { name: 'Solana', short: 'Solana', icon: '◎', color: '#00ffa3', about:
        `Solana es una blockchain lanzada en 2020 por Anatoly Yakovenko (ex-Qualcomm), diseñada para procesar muchas más transacciones por segundo que Bitcoin o Ethereum, a cambio de mayor centralización técnica y algún historial de caídas de red.

Combina "prueba de participación" con una innovación propia, "prueba de historia" (proof-of-history), que ordena las transacciones con marcas de tiempo criptográficas antes de que los validadores lleguen a un consenso, acelerando el proceso frente a otras blockchains.

Se usa sobre todo para aplicaciones que necesitan velocidad y comisiones muy bajas: exchanges descentralizados, NFTs y pagos. El token SOL sirve para pagar comisiones de red y para hacer staking.` },
    'DOGE': { name: 'Dogecoin', short: 'Dogecoin', icon: '🐕', color: '#c3a634', about:
        `Dogecoin nació en diciembre de 2013 como una broma entre dos ingenieros de software (Billy Markus y Jackson Palmer), basada en el meme del perro Shiba Inu "Doge". Técnicamente es una copia (fork) de Litecoin, que a su vez es una copia de Bitcoin, y usa el mismo sistema de "prueba de trabajo".

A diferencia de Bitcoin, no tiene límite máximo de unidades: se crean unos 5.000 millones de DOGE nuevos cada año de forma indefinida, lo que lo hace estructuralmente inflacionario.

No aporta ninguna propuesta tecnológica diferencial ni caso de uso más allá de pagos simples y propinas online; su cotización depende casi por completo del sentimiento de la comunidad y de menciones virales (incluidas las históricas de Elon Musk). Es, por diseño, un activo altamente especulativo.` },
    'PEPE': { name: 'Pepe', short: 'Pepe', icon: '🐸', color: '#4caf50', about:
        `PEPE es una criptomoneda "meme" lanzada en abril de 2023 sobre la red de Ethereum, inspirada en el personaje de internet "Pepe the Frog". No tiene equipo fundador público conocido, whitepaper técnico, ni ningún caso de uso más allá de la especulación y la cultura de internet cripto.

Su valor se basa exclusivamente en la demanda especulativa y la actividad de comunidades en redes sociales — junto con Dogecoin, es de los activos con más volatilidad de toda la cartera. Es un token estándar (ERC-20) sin ningún mecanismo económico especial detrás.` },
    'IE00BYX5NX33': { name: 'Fidelity MSCI World P-Acc', short: 'MSCI World', icon: '🌍', color: '#2196f3', about:
        `Fondo indexado (no cotiza como un ETF; se compra/vende directamente a través del gestor, en este caso vía MyInvestor) gestionado por Fidelity, que replica el índice MSCI World: en torno a 1.400-1.500 empresas grandes y medianas de 23 países desarrollados, donde EE. UU. suele pesar en torno al 65-70%, seguido de lejos por Japón, Reino Unido y otros mercados desarrollados.

"P-Acc" significa clase "P" (sin mínimo alto de inversión) y "Acc" (acumulación): los dividendos que reparten las empresas no se pagan al inversor, se reinvierten automáticamente dentro del fondo.

Es un fondo domiciliado en Irlanda (UCITS), lo que en España permite traspasos entre fondos sin tributar hasta el reembolso final. Es de gestión pasiva: no intenta batir al mercado, solo replicarlo al menor coste posible.` },
    'IE00B4ND3602': { name: 'iShares Physical Gold ETC', short: 'Oro', icon: '🥇', color: '#ffd700', about:
        `No es un fondo de acciones de mineras de oro, sino un ETC (Exchange Traded Commodity) respaldado por oro físico real almacenado en bóvedas seguras auditadas. Cada participación representa una fracción de una onza de oro, y su precio sigue casi uno a uno la cotización del oro al contado, menos una pequeña comisión de gestión.

El oro se ha usado como reserva de valor durante milenios; a diferencia de las divisas, no depende de ningún banco central ni gobierno, y suele comportarse como refugio en momentos de inflación alta, crisis geopolíticas o caídas fuertes de bolsa — aunque no genera ni dividendos ni intereses, solo (o no) revalorización del propio metal.` },
    'LYX0F.DE': { name: 'Amundi Nasdaq-100', short: 'Nasdaq-100', icon: '📈', color: '#1976d2', about:
        `ETF gestionado por Amundi (que absorbió en 2021 la gama de fondos Lyxor de Société Générale) que replica el índice Nasdaq-100: las 100 mayores empresas no financieras cotizadas en el Nasdaq de EE. UU., ponderadas por capitalización bursátil.

Está muy concentrado en tecnología — Apple, Microsoft, Nvidia, Amazon, Meta, Alphabet y Broadcom suelen representar más de la mitad del índice —, por lo que aporta más potencial de crecimiento pero también más volatilidad que un índice amplio como el S&P 500 o el MSCI World.

El Nasdaq-100 se creó en 1985; su composición se revisa periódicamente para mantener solo las empresas más grandes que cumplen los requisitos de liquidez del índice.` },
    'VVSM.DE': { name: 'VanEck Semiconductor', short: 'Semiconductores', icon: '💾', color: '#9c27b0', about:
        `Replica el índice MVIS US Listed Semiconductor 25, formado por unas 25 empresas relacionadas con el diseño, fabricación y equipamiento de semiconductores (chips) — desde diseñadoras como Nvidia o AMD hasta fabricantes de la maquinaria necesaria para producirlos, como ASML.

Los semiconductores son el componente físico que hace posible toda la computación moderna (ordenadores, móviles, coches, centros de datos de IA), por lo que el sector suele moverse en ciclos marcados: fuertes subidas en fases de expansión de la demanda (como el auge de la IA generativa) y correcciones bruscas cuando esa demanda se satura o cae la inversión en capacidad.` },
    'QDVF.DE': { name: 'iShares S&P500 Energy', short: 'S&P Energía', icon: '⚡', color: '#ff9800', about:
        `Replica el subíndice de energía dentro del S&P 500: empresas estadounidenses grandes dedicadas a la extracción, refino y distribución de petróleo y gas (ExxonMobil y Chevron suelen ser sus mayores posiciones).

Su cotización está fuertemente correlacionada con el precio del petróleo y el gas natural, y por tanto con decisiones de la OPEP+, tensiones geopolíticas en zonas productoras y el ciclo económico global (más actividad industrial implica más demanda energética). Es un sector que históricamente reparte dividendos altos, pero que compite a largo plazo con la transición hacia energías renovables.` },
    'NUKL.DE': { name: 'VanEck Uranium & Nuclear', short: 'Uranio/Nuclear', icon: '☢️', color: '#8bc34a', about:
        `Invierte en empresas de toda la cadena de la energía nuclear: minería de uranio (el combustible), diseño de reactores y generación de electricidad nuclear.

Es un sector nicho y volátil, muy sensible a decisiones políticas (cierres o reaperturas de centrales, nuevas licencias) y al resurgir del interés por la energía nuclear desde 2022, al buscarse alternativas al gas ruso y fuentes de electricidad estables y sin emisiones de CO2 — entre otras cosas, para alimentar los centros de datos de inteligencia artificial.` },
    'BTEC.L': { name: 'iShares Nasdaq Biotech', short: 'Biotech', icon: '🧬', color: '#00bcd4', about:
        `Replica el índice Nasdaq Biotechnology, compuesto por empresas biotecnológicas y farmacéuticas cotizadas en el Nasdaq — desde grandes farmacéuticas consolidadas hasta compañías pequeñas en fase de investigación clínica sin ingresos todavía.

Es un sector de alto riesgo/alta recompensa: el valor de una empresa biotecnológica puede duplicarse o desplomarse de la noche a la mañana según el resultado de un ensayo clínico o una decisión de aprobación de la FDA (la agencia reguladora de medicamentos de EE. UU.). Al diversificar entre muchas compañías, el ETF reduce —pero no elimina— ese riesgo binario de apostar por una sola empresa.` },
    'COPX.L': { name: 'Global X Copper Miners', short: 'Cobre', icon: '🔶', color: '#b87333', about:
        `Replica un índice de empresas dedicadas a la extracción y producción de cobre en todo el mundo. El cobre es un metal industrial clave — se usa en cableado eléctrico, construcción, electrodomésticos y, cada vez más, en la transición energética (coches eléctricos, paneles solares, redes eléctricas) —, por lo que su demanda está ligada al crecimiento industrial global y a la electrificación.

A diferencia del oro, el cobre no se considera un refugio, sino un termómetro del ciclo económico: sube cuando se espera más actividad industrial y baja cuando se teme una desaceleración.` },
    'JEDI.DE': { name: 'VanEck Space Innovators', short: 'Espacio', icon: '🚀', color: '#673ab7', about:
        `Invierte en empresas de la cadena de valor espacial: fabricantes de satélites, lanzadores, comunicaciones satelitales y compañías que dependen de infraestructura espacial (imágenes satelitales, navegación).

Es un sector todavía emergente, impulsado por la caída de costes de lanzamiento (en gran parte gracias a los cohetes reutilizables de SpaceX) y la multiplicación de aplicaciones comerciales del espacio: internet por satélite, observación de la Tierra, defensa. Al ser un sector joven con muchas empresas pequeñas, su volatilidad es alta y depende mucho del sentimiento sobre "temas de futuro" más que de beneficios actuales.` },
    'PLTR': { name: 'Palantir Technologies', short: 'Palantir', icon: '🔮', color: '#000000', about:
        `Empresa estadounidense de software de análisis de datos fundada en 2003 por Peter Thiel, Alex Karp y otros, con fuertes vínculos iniciales con agencias de inteligencia y defensa de EE. UU. (su primer gran cliente fue la CIA, a través de su brazo inversor In-Q-Tel).

Sus dos productos principales son Gotham (para gobiernos, defensa e inteligencia) y Foundry (su versión para empresas privadas): plataformas que integran datos dispersos de una organización para tomar decisiones. Salió a bolsa en septiembre de 2020 mediante una cotización directa, sin la ronda tradicional de banca de inversión.

En los últimos años ha crecido mucho su negocio de IA aplicada (Palantir AIP), lo que ha disparado su valoración y también genera debate sobre si cotiza muy por encima de sus beneficios actuales.` },
    'SPCX': { name: 'SpaceX', short: 'SpaceX', icon: '🛰️', color: '#005288', about:
        `SpaceX (Space Exploration Technologies Corp.) fue fundada por Elon Musk en 2002 con el objetivo declarado de reducir el coste del acceso al espacio y, a largo plazo, hacer posible la colonización de Marte.

Desarrolló los cohetes Falcon 1, Falcon 9 y Falcon Heavy, pionera en la reutilización de la primera etapa de los cohetes (aterrizan verticalmente y vuelven a volar), lo que abarató drásticamente el coste por lanzamiento frente a la industria tradicional. Opera la cápsula Dragon, que transporta carga y astronautas a la Estación Espacial Internacional para la NASA, y Starlink, su red de miles de satélites de internet en órbita baja, que ya supone una parte muy relevante de sus ingresos. Está desarrollando Starship, el cohete más grande jamás construido, pensado para misiones a la Luna y Marte.

Tras años como empresa privada valorada en cientos de miles de millones de dólares en el mercado secundario, SpaceX salió a bolsa en el Nasdaq bajo el ticker SPCX en junio de 2026.` },
    'USPY.DE': { name: 'L&G Cyber Security', short: 'Ciberseguridad', icon: '🔐', color: '#607d8b', about:
        `Gestionado por Legal & General (L&G), replica un índice de empresas dedicadas a la ciberseguridad: protección de redes, detección de intrusiones, gestión de identidad digital, seguridad en la nube, etc.

La demanda del sector crece de forma bastante estructural —no solo cíclica— a medida que aumentan los ataques informáticos, el trabajo en remoto y la digitalización de empresas y gobiernos, aunque eso no evita que sus valoraciones suban y bajen con el sentimiento general del sector tecnológico.` },
    'IEAA.L': { name: 'iShares Core € Corp Bond', short: 'Bonos Corp.', icon: '🏦', color: '#795548', about:
        `Replica un índice amplio de bonos corporativos denominados en euros con calificación "grado de inversión" (empresas consideradas solventes por las agencias de rating, no bonos basura).

Es el activo más conservador y de renta fija de la cartera: en vez de comprar acciones (una parte de la empresa), presta dinero a esas empresas a cambio de un interés periódico. Su precio se mueve sobre todo por las expectativas de tipos de interés del BCE: si los tipos suben, el precio de los bonos ya emitidos baja (porque los nuevos bonos pagan más), y viceversa. Sirve como colchón de estabilidad frente a la volatilidad de las acciones y las criptomonedas del resto de la cartera.` },
};

function getAssetName(ticker) {
    return ASSET_DISPLAY_NAMES[ticker?.toUpperCase()]?.name || null;
}

function getTickerIcon(ticker, type) {
    const info = ASSET_DISPLAY_NAMES[ticker?.toUpperCase()];
    if (info) return info.icon;
    if (type === 'crypto') return '🪙';
    if (type === 'etf') return '📊';
    if (type === 'fund') return '📈';
    return ticker?.substring(0, 2).toUpperCase() || '??';
}

// Utility Functions
function formatCurrency(value, currency = 'EUR') {
    return new Intl.NumberFormat('es-ES', {
        style: 'currency',
        currency: currency,
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(value);
}

function formatNumber(value, decimals = 2) {
    return new Intl.NumberFormat('es-ES', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    }).format(value);
}

function formatPercent(value) {
    const sign = value >= 0 ? '+' : '';
    return `${sign}${formatNumber(value)}%`;
}

function formatDate(dateStr) {
    return new Date(dateStr).toLocaleDateString('es-ES', {
        day: '2-digit',
        month: 'short',
        year: 'numeric'
    });
}

function formatTime(dateStr) {
    return new Date(dateStr).toLocaleTimeString('es-ES', {
        hour: '2-digit',
        minute: '2-digit'
    });
}

// API Functions
async function fetchAPI(endpoint) {
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}${endpoint}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error(`API Error (${endpoint}):`, error);
        throw error;
    }
}

async function fetchPortfolio() {
    return fetchAPI('/portfolio');
}

async function fetchHistory(days = 365) {
    return fetchAPI(`/portfolio/history?days=${days}`);
}

async function refreshData() {
    return fetchAPI('/refresh');
}

// UI Update Functions
function updateStatus(online) {
    const dot = document.getElementById('statusDot');
    const text = document.getElementById('statusText');
    
    if (dot && text) {
        if (online) {
            dot.className = 'status-dot online';
            text.textContent = 'Conectado';
        } else {
            dot.className = 'status-dot offline';
            text.textContent = 'Sin conexión';
        }
    }
}

function updateLastUpdate(timestamp) {
    const el = document.getElementById('lastUpdate');
    if (el) {
        el.textContent = formatTime(timestamp);
    }
}

function updateSummary(data) {
    // Total Value
    const totalValueEl = document.getElementById('totalValue');
    if (totalValueEl) {
        totalValueEl.innerHTML = formatCurrency(data.total_value, data.base_currency);
    }
    
    // Base Currency
    const baseCurrencyEl = document.getElementById('baseCurrency');
    if (baseCurrencyEl) {
        baseCurrencyEl.textContent = data.base_currency;
    }
    
    // Daily Change
    const dailyEl = document.getElementById('dailyChange');
    if (dailyEl) {
        const dailyClass = data.daily_change >= 0 ? 'positive' : 'negative';
        dailyEl.className = `change-daily ${dailyClass}`;
        dailyEl.innerHTML = `Hoy: ${formatPercent(data.daily_change_pct)} (${formatCurrency(data.daily_change, data.base_currency)})`;
    }
    
    // Total Gain/Loss
    const totalEl = document.getElementById('totalGainLoss');
    if (totalEl) {
        const totalClass = data.total_gain_loss >= 0 ? 'positive' : 'negative';
        totalEl.className = `change-total ${totalClass}`;
        totalEl.innerHTML = `Total: ${formatPercent(data.total_gain_loss_pct)} (${formatCurrency(data.total_gain_loss, data.base_currency)})`;
    }
    
    // Positions count
    const positionsCountEl = document.getElementById('positionsCount');
    if (positionsCountEl) {
        positionsCountEl.textContent = data.positions?.length || 0;
    }
}

function updateKPIs(kpis) {
    // CAGR
    const cagrEl = document.getElementById('cagr');
    if (cagrEl) {
        cagrEl.textContent = kpis.cagr ? `${formatNumber(kpis.cagr)}%` : 'N/A';
        cagrEl.className = `kpi-value ${kpis.cagr >= 0 ? 'positive' : 'negative'}`;
    }
    
    // Max Drawdown
    const ddEl = document.getElementById('maxDrawdown');
    if (ddEl) {
        ddEl.textContent = kpis.max_drawdown ? `-${formatNumber(kpis.max_drawdown)}%` : 'N/A';
        ddEl.className = 'kpi-value negative';
    }
    
    // Volatility
    const volEl = document.getElementById('volatility');
    if (volEl) {
        volEl.textContent = kpis.volatility ? `${formatNumber(kpis.volatility)}%` : 'N/A';
    }
    
    // Sharpe Ratio
    const sharpeEl = document.getElementById('sharpeRatio');
    if (sharpeEl) {
        sharpeEl.textContent = kpis.sharpe_ratio ? formatNumber(kpis.sharpe_ratio) : 'N/A';
        sharpeEl.className = `kpi-value ${kpis.sharpe_ratio >= 1 ? 'positive' : ''}`;
    }
    
    // Best/Worst day for analysis page
    const bestDayEl = document.getElementById('bestDay');
    if (bestDayEl) {
        bestDayEl.textContent = kpis.best_day ? formatPercent(kpis.best_day) : '+0.00%';
    }
    
    const worstDayEl = document.getElementById('worstDay');
    if (worstDayEl) {
        worstDayEl.textContent = kpis.worst_day ? formatPercent(kpis.worst_day) : '-0.00%';
    }

    const positiveDaysEl = document.getElementById('positiveDays');
    if (positiveDaysEl) {
        positiveDaysEl.textContent = kpis.positive_days_pct != null ? `${formatNumber(kpis.positive_days_pct, 1)}%` : '0%';
    }

    const ytdEl = document.getElementById('ytdReturn');
    if (ytdEl) {
        ytdEl.textContent = kpis.ytd_return != null ? formatPercent(kpis.ytd_return) : '0.00%';
        ytdEl.className = `stat-value ${kpis.ytd_return >= 0 ? 'positive' : 'negative'}`;
    }
}

function updateQuickStats(data) {
    if (!data.positions || data.positions.length === 0) return;
    
    // Best performer
    const bestPerformer = data.positions.reduce((best, pos) => 
        pos.gain_loss_pct > (best?.gain_loss_pct || -Infinity) ? pos : best
    , null);
    
    const bestEl = document.getElementById('bestPerformer');
    if (bestEl && bestPerformer) {
        const bestName = getAssetName(bestPerformer.ticker) || bestPerformer.name || bestPerformer.ticker;
        bestEl.innerHTML = `<span style="color: var(--positive)">${bestName}</span> ${formatPercent(bestPerformer.gain_loss_pct)}`;
    }
    
    // Worst performer
    const worstPerformer = data.positions.reduce((worst, pos) => 
        pos.gain_loss_pct < (worst?.gain_loss_pct || Infinity) ? pos : worst
    , null);
    
    const worstEl = document.getElementById('worstPerformer');
    if (worstEl && worstPerformer) {
        const worstName = getAssetName(worstPerformer.ticker) || worstPerformer.name || worstPerformer.ticker;
        worstEl.innerHTML = `<span style="color: var(--negative)">${worstName}</span> ${formatPercent(worstPerformer.gain_loss_pct)}`;
    }
}

function updatePositionsTable(positions) {
    const tbody = document.getElementById('positionsBody');
    if (!tbody) return;
    
    if (!positions || positions.length === 0) {
        tbody.innerHTML = '<tr><td colspan="11" class="loading-row">No hay posiciones</td></tr>';
        return;
    }
    
    // Apply filters
    const typeFilter = document.getElementById('filterType')?.value || 'all';
    const brokerFilter = document.getElementById('filterBroker')?.value || 'all';
    const searchTerm = document.getElementById('searchPositions')?.value?.toLowerCase() || '';
    
    let filtered = positions;
    if (typeFilter !== 'all') {
        filtered = filtered.filter(p => p.type === typeFilter);
    }
    if (brokerFilter !== 'all') {
        filtered = filtered.filter(p => p.broker === brokerFilter);
    }
    if (searchTerm) {
        filtered = filtered.filter(p => 
            p.ticker.toLowerCase().includes(searchTerm) ||
            (p.name && p.name.toLowerCase().includes(searchTerm))
        );
    }
    
    // Sort
    filtered.sort((a, b) => {
        let aVal = a[sortColumn];
        let bVal = b[sortColumn];
        
        if (typeof aVal === 'string') {
            aVal = aVal.toLowerCase();
            bVal = bVal.toLowerCase();
        }
        
        if (sortDirection === 'asc') {
            return aVal > bVal ? 1 : -1;
        }
        return aVal < bVal ? 1 : -1;
    });
    
    tbody.innerHTML = filtered.map(pos => {
        const assetName = getAssetName(pos.ticker) || pos.name || pos.ticker;
        const icon = getTickerIcon(pos.ticker, pos.type);
        const typeName = {'crypto': 'Crypto', 'etf': 'ETF', 'fund': 'Fondo', 'stock': 'Acción'}[pos.type] || pos.type;
        
        return `
        <tr onclick="showAssetDetail('${pos.ticker}')" style="cursor:pointer" title="Ver detalle de ${assetName}">
            <td>
                <div class="ticker-cell">
                    <div class="ticker-icon">${icon}</div>
                    <div class="ticker-info">
                        <span class="ticker-symbol">${assetName}</span>
                        <span class="ticker-name">${pos.ticker}</span>
                    </div>
                </div>
            </td>
            <td><span class="type-badge ${pos.type}">${typeName}</span></td>
            <td><span class="broker-name">${pos.broker}</span></td>
            <td class="text-right mono">${formatNumber(pos.quantity, pos.type === 'crypto' ? 6 : 2)}</td>
            <td class="text-right mono">${formatNumber(pos.avg_price)}</td>
            <td class="text-right mono">${formatNumber(pos.current_price)}</td>
            <td class="text-right mono">${formatCurrency(pos.market_value, pos.currency)}</td>
            <td class="text-right mono ${pos.gain_loss >= 0 ? 'value-positive' : 'value-negative'}">
                ${formatCurrency(pos.gain_loss, pos.currency)}
            </td>
            <td class="text-right mono ${pos.gain_loss_pct >= 0 ? 'value-positive' : 'value-negative'}">
                ${formatPercent(pos.gain_loss_pct)}
            </td>
            <td class="text-right mono ${pos.day_change_pct >= 0 ? 'value-positive' : 'value-negative'}">
                ${formatPercent(pos.day_change_pct)}
            </td>
            <td class="text-right mono">${formatNumber(pos.weight)}%</td>
        </tr>
    `}).join('');
}

function updateBrokerFilter(brokers) {
    const select = document.getElementById('filterBroker');
    if (!select) return;
    
    const currentValue = select.value;
    
    select.innerHTML = '<option value="all">Todos los brokers</option>' +
        Object.keys(brokers).map(broker => 
            `<option value="${broker}">${broker}</option>`
        ).join('');
    
    select.value = currentValue;
}

function updateTopMovers(positions) {
    const container = document.getElementById('topMovers');
    if (!container || !positions) return;
    
    const sorted = [...positions].sort((a, b) => Math.abs(b.day_change_pct) - Math.abs(a.day_change_pct));
    const topMovers = sorted.slice(0, 5);
    
    container.innerHTML = topMovers.map(pos => `
        <div class="mover-item" style="display: flex; justify-content: space-between; padding: 10px; background: var(--bg-tertiary); border-radius: 8px; margin-bottom: 8px;">
            <span style="font-family: var(--font-mono); font-weight: 600;">${pos.ticker}</span>
            <span class="${pos.day_change_pct >= 0 ? 'value-positive' : 'value-negative'}" style="font-family: var(--font-mono);">
                ${formatPercent(pos.day_change_pct)}
            </span>
        </div>
    `).join('');
}

// Chart Functions
function createPortfolioChart(history) {
    const ctx = document.getElementById('portfolioChart');
    if (!ctx) return;
    
    if (charts.portfolio && typeof charts.portfolio.destroy === 'function') {
        charts.portfolio.destroy();
    }
    
    // Filter by period
    let filteredHistory = history;
    if (currentPeriod !== 'all') {
        const cutoff = new Date();
        cutoff.setDate(cutoff.getDate() - currentPeriod);
        filteredHistory = history.filter(h => new Date(h.date) >= cutoff);
    }
    
    const labels = filteredHistory.map(h => h.date);
    const values = filteredHistory.map(h => h.value);
    
    // Calculate gradient
    const gradient = ctx.getContext('2d').createLinearGradient(0, 0, 0, 350);
    gradient.addColorStop(0, 'rgba(0, 212, 170, 0.3)');
    gradient.addColorStop(1, 'rgba(0, 212, 170, 0)');
    
    charts.portfolio = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Valor de Cartera',
                data: values,
                borderColor: '#00d4aa',
                backgroundColor: gradient,
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 6,
                pointHoverBackgroundColor: '#00d4aa',
                pointHoverBorderColor: '#fff',
                pointHoverBorderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: '#1a2332',
                    titleColor: '#94a3b8',
                    bodyColor: '#f8fafc',
                    borderColor: '#334155',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: false,
                    callbacks: {
                        title: function(context) {
                            return formatDate(context[0].label);
                        },
                        label: function(context) {
                            return formatCurrency(context.raw, 'EUR');
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        color: '#64748b',
                        maxTicksLimit: 8,
                        callback: function(value, index) {
                            const date = new Date(this.getLabelForValue(value));
                            return date.toLocaleDateString('es-ES', { month: 'short', day: 'numeric' });
                        }
                    }
                },
                y: {
                    grid: {
                        color: '#1e293b'
                    },
                    ticks: {
                        color: '#64748b',
                        callback: function(value) {
                            return formatCurrency(value, 'EUR');
                        }
                    }
                }
            }
        }
    });
}

function createDoughnutChart(canvasId, data, legendId) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    
    const chartKey = canvasId.replace('Chart', '');
    if (charts[chartKey] && typeof charts[chartKey].destroy === 'function') {
        charts[chartKey].destroy();
    }
    
    const labels = Object.keys(data);
    const values = labels.map(k => data[k].value || data[k].weight);
    const weights = labels.map(k => data[k].weight);
    
    const chart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: CONFIG.CHART_COLORS.slice(0, labels.length),
                borderColor: '#151d2c',
                borderWidth: 3,
                hoverBorderColor: '#1a253a',
                hoverBorderWidth: 3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '70%',
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: '#1a2332',
                    titleColor: '#94a3b8',
                    bodyColor: '#f8fafc',
                    borderColor: '#334155',
                    borderWidth: 1,
                    padding: 12,
                    callbacks: {
                        label: function(context) {
                            const weight = weights[context.dataIndex];
                            return `${weight}%`;
                        }
                    }
                }
            }
        }
    });
    
    charts[chartKey] = chart;
    
    // Update legend
    const legendEl = document.getElementById(legendId);
    if (legendEl) {
        legendEl.innerHTML = labels.map((label, i) => `
            <div class="legend-item">
                <span class="legend-color" style="background: ${CONFIG.CHART_COLORS[i]}"></span>
                <span class="legend-label">${label}</span>
                <span class="legend-value">${formatNumber(weights[i])}%</span>
            </div>
        `).join('');
    }
}

// Export to CSV
function exportToCSV() {
    if (!portfolioData || !portfolioData.positions) return;
    
    const headers = ['Ticker', 'Nombre', 'Tipo', 'Broker', 'Cantidad', 'Precio Medio', 'Precio Actual', 'Valor', 'P/L', 'P/L %', 'Peso %'];
    const rows = portfolioData.positions.map(p => [
        p.ticker,
        p.name,
        p.type,
        p.broker,
        p.quantity,
        p.avg_price,
        p.current_price,
        p.market_value,
        p.gain_loss,
        p.gain_loss_pct,
        p.weight
    ]);
    
    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    
    const link = document.createElement('a');
    link.href = url;
    link.download = `portfolio_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
    
    URL.revokeObjectURL(url);
    
    if (window.showToast) {
        window.showToast('CSV exportado correctamente', 'success');
    }
}

// Check which backend integrations are configured and surface a banner if any are missing.
async function loadIntegrationsStatus() {
    const banner = document.getElementById('integrationsBanner');
    if (!banner) return;
    try {
        const status = await fetchAPI('').catch(() => null) || await (await fetch(`${CONFIG.API_BASE_URL}`)).json();
        const checks = [
            { key: 'has_gemini', label: 'Gemini (briefing diario + FinBot)', env: 'GEMINI_API_KEY' },
            { key: 'has_kraken', label: 'Kraken (sync cripto cada 15 min)', env: 'KRAKEN_API_KEY + KRAKEN_API_SECRET' },
            { key: 'has_telegram', label: 'Telegram (alertas push)', env: 'TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID' },
        ];
        const missing = checks.filter(c => !status[c.key]);
        if (missing.length === 0) {
            banner.style.display = 'none';
            return;
        }
        const items = missing.map(m =>
            `<li><strong>${m.label}</strong> — define <code>${m.env}</code> en Render → Environment</li>`
        ).join('');
        banner.innerHTML = `
            <div class="integrations-banner-inner">
                <div class="integrations-banner-icon">⚙️</div>
                <div class="integrations-banner-body">
                    <strong>Quedan ${missing.length} integraci${missing.length === 1 ? 'ón' : 'ones'} por activar</strong>
                    <ul>${items}</ul>
                    <small>Lo que ya funciona: portfolio, posiciones, news, charts y FinBot con Groq.</small>
                </div>
            </div>
        `;
        banner.style.display = 'block';
    } catch (err) {
        console.warn('Could not load integrations status:', err);
    }
}

// Main Functions
async function loadDashboard() {
    try {
        updateStatus(false);

        loadIntegrationsStatus();

        // Fetch portfolio data
        portfolioData = await fetchPortfolio();
        
        // Update UI
        updateSummary(portfolioData);
        updateKPIs(portfolioData.kpis);
        updateQuickStats(portfolioData);
        updatePositionsTable(portfolioData.positions);
        updateBrokerFilter(portfolioData.by_broker);
        updateLastUpdate(portfolioData.last_updated);
        updateTopMovers(portfolioData.positions);
        
        // Create distribution charts
        if (portfolioData.by_type && Object.keys(portfolioData.by_type).length > 0) {
            createDoughnutChart('typeChart', portfolioData.by_type, 'typeLegend');
        }
        if (portfolioData.by_broker && Object.keys(portfolioData.by_broker).length > 0) {
            createDoughnutChart('brokerChart', portfolioData.by_broker, 'brokerLegend');
        }
        if (portfolioData.by_currency && Object.keys(portfolioData.by_currency).length > 0) {
            createDoughnutChart('currencyChart', portfolioData.by_currency, 'currencyLegend');
        }
        
        // Fetch and create history chart
        const historyData = await fetchHistory(365);
        if (historyData.history && historyData.history.length > 0) {
            createPortfolioChart(historyData.history);
        }
        
        updateStatus(true);
        
    } catch (error) {
        console.error('Error loading dashboard:', error);
        updateStatus(false);
        
        // Show error state
        const totalValueEl = document.getElementById('totalValue');
        if (totalValueEl) {
            totalValueEl.innerHTML = '<span class="value-loading">Error al cargar datos</span>';
        }
    }
}

async function handleRefresh() {
    const btn = document.getElementById('btnRefresh');
    const overlay = document.getElementById('loadingOverlay');
    
    if (btn) btn.classList.add('loading');
    if (overlay) overlay.classList.add('active');
    
    try {
        await refreshData();
        await loadDashboard();
        if (window.showToast) {
            window.showToast('Datos actualizados correctamente', 'success');
        }
    } catch (error) {
        console.error('Error refreshing:', error);
        if (window.showToast) {
            window.showToast('Error al actualizar datos', 'error');
        }
    } finally {
        if (btn) btn.classList.remove('loading');
        if (overlay) overlay.classList.remove('active');
    }
}

function handlePeriodChange(period) {
    currentPeriod = period === 'all' ? 'all' : parseInt(period);
    
    // Update active button
    document.querySelectorAll('.chart-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.period === String(period));
    });
    
    // Reload history chart
    if (portfolioData) {
        fetchHistory(period === 'all' ? 3650 : 365).then(data => {
            if (data.history) {
                createPortfolioChart(data.history);
            }
        });
    }
}

function handleFilterChange() {
    if (portfolioData) {
        updatePositionsTable(portfolioData.positions);
    }
}

function handleSort(column) {
    if (sortColumn === column) {
        sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
        sortColumn = column;
        sortDirection = 'desc';
    }
    
    if (portfolioData) {
        updatePositionsTable(portfolioData.positions);
    }
}

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    // Initial load
    loadDashboard();
    
    // Refresh button
    const btnRefresh = document.getElementById('btnRefresh');
    if (btnRefresh) {
        btnRefresh.addEventListener('click', handleRefresh);
    }
    
    // Period buttons
    document.querySelectorAll('.chart-btn').forEach(btn => {
        btn.addEventListener('click', () => handlePeriodChange(btn.dataset.period));
    });
    
    // Filters
    const filterType = document.getElementById('filterType');
    const filterBroker = document.getElementById('filterBroker');
    const searchPositions = document.getElementById('searchPositions');
    
    if (filterType) filterType.addEventListener('change', handleFilterChange);
    if (filterBroker) filterBroker.addEventListener('change', handleFilterChange);
    if (searchPositions) searchPositions.addEventListener('input', handleFilterChange);
    
    // Table sorting
    document.querySelectorAll('.positions-table th[data-sort]').forEach(th => {
        th.addEventListener('click', () => handleSort(th.dataset.sort));
    });
    
    // Export CSV
    const btnExport = document.getElementById('btnExportCSV');
    if (btnExport) {
        btnExport.addEventListener('click', exportToCSV);
    }
    
    // Auto-refresh every minute
    setInterval(loadDashboard, CONFIG.REFRESH_INTERVAL);
});

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Press 'R' to refresh
    if ((e.key === 'r' || e.key === 'R') && !e.ctrlKey && !e.metaKey) {
        const activeElement = document.activeElement;
        if (activeElement.tagName !== 'INPUT' && activeElement.tagName !== 'TEXTAREA') {
            handleRefresh();
        }
    }
});
