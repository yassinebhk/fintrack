/**
 * News Module
 * Fetches and displays financial news
 * In production, would use NewsAPI, Alpha Vantage News, or similar
 */

// Last update timestamp
let lastNewsUpdate = new Date().toISOString();

// News data - In production, this would come from an API
// Categories: stocks, crypto, economy, politics
const newsData = [
    {
        id: 1,
        title: "NVIDIA supera expectativas de beneficios por la demanda de IA",
        excerpt: "Las acciones de NVIDIA suben un 8% tras anunciar ingresos récord impulsados por la demanda de chips para inteligencia artificial. Los centros de datos representan ya el 80% de sus ventas.",
        source: "Bloomberg",
        date: "2026-01-06",
        category: "stocks",
        impact: "bullish",
        impactedAssets: ["NVDA", "AMD", "INTC"],
        image: "https://images.unsplash.com/photo-1518770660439-4636190af475?w=400",
        url: "#"
    },
    {
        id: 2,
        title: "Bitcoin supera los $100,000 por primera vez en su historia",
        excerpt: "La criptomoneda más grande del mundo alcanza un nuevo máximo histórico impulsada por la adopción institucional y la aprobación de ETFs de Bitcoin al contado en múltiples países.",
        source: "CoinDesk",
        date: "2026-01-05",
        category: "crypto",
        impact: "bullish",
        impactedAssets: ["BTC", "ETH", "SOL"],
        image: "https://images.unsplash.com/photo-1518546305927-5a555bb7020d?w=400",
        url: "#"
    },
    {
        id: 3,
        title: "La Reserva Federal mantiene tipos de interés estables",
        excerpt: "La Fed decide no modificar los tipos de interés en su última reunión, señalando que la inflación sigue bajo control. Los mercados reaccionan positivamente ante la previsibilidad.",
        source: "Reuters",
        date: "2026-01-04",
        category: "economy",
        impact: "neutral",
        impactedAssets: ["SPY", "QQQ", "VOO"],
        image: "https://images.unsplash.com/photo-1541354329998-f4d9a9f9297f?w=400",
        url: "#"
    },
    {
        id: 4,
        title: "Apple anuncia nuevo iPhone plegable para 2026",
        excerpt: "Las filtraciones confirman que Apple lanzará su primer iPhone con pantalla plegable en el segundo semestre del año. Los analistas esperan que impulse significativamente las ventas.",
        source: "TechCrunch",
        date: "2026-01-04",
        category: "stocks",
        impact: "bullish",
        impactedAssets: ["AAPL"],
        image: "https://images.unsplash.com/photo-1592750475338-74b7b21085ab?w=400",
        url: "#"
    },
    {
        id: 5,
        title: "Crisis en el sector inmobiliario chino se intensifica",
        excerpt: "Evergrande y Country Garden enfrentan nuevas dificultades de liquidez. Los expertos advierten sobre posibles contagios a mercados emergentes y materias primas.",
        source: "Financial Times",
        date: "2026-01-03",
        category: "economy",
        impact: "bearish",
        impactedAssets: ["EEM", "FXI"],
        image: "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=400",
        url: "#"
    },
    {
        id: 6,
        title: "Ethereum completa actualización 'Osaka' con éxito",
        excerpt: "La red Ethereum procesa ahora 100,000 transacciones por segundo tras la última actualización. Las comisiones caen un 90% y el precio de ETH sube un 15%.",
        source: "The Block",
        date: "2026-01-02",
        category: "crypto",
        impact: "bullish",
        impactedAssets: ["ETH"],
        image: "https://images.unsplash.com/photo-1639762681485-074b7f938ba0?w=400",
        url: "#"
    },
    {
        id: 7,
        title: "Europa entra oficialmente en recesión técnica",
        excerpt: "Alemania y Francia registran dos trimestres consecutivos de crecimiento negativo. El BCE considera nuevos estímulos monetarios para reactivar la economía.",
        source: "El Economista",
        date: "2026-01-02",
        category: "economy",
        impact: "bearish",
        impactedAssets: ["EZU", "VGK", "VWCE.DE"],
        image: "https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?w=400",
        url: "#"
    },
    {
        id: 8,
        title: "Microsoft supera a Apple como empresa más valiosa del mundo",
        excerpt: "Con una capitalización de $3.5 billones, Microsoft recupera el primer puesto gracias al éxito de sus servicios de IA integrados en Azure y Office 365.",
        source: "CNBC",
        date: "2026-01-01",
        category: "stocks",
        impact: "bullish",
        impactedAssets: ["MSFT"],
        image: "https://images.unsplash.com/photo-1633419461186-7d40a38105ec?w=400",
        url: "#"
    },
    {
        id: 9,
        title: "Tesla entrega 2 millones de vehículos en 2025",
        excerpt: "La compañía de Elon Musk alcanza un nuevo récord de entregas, superando las expectativas de los analistas. El Cybertruck representa el 20% de las ventas.",
        source: "Electrek",
        date: "2025-12-31",
        category: "stocks",
        impact: "bullish",
        impactedAssets: ["TSLA"],
        image: "https://images.unsplash.com/photo-1560958089-b8a1929cea89?w=400",
        url: "#"
    },
    {
        id: 10,
        title: "Escasez de semiconductores podría extenderse hasta 2027",
        excerpt: "Los principales fabricantes de chips advierten que la demanda sigue superando la capacidad de producción. AMD, Intel y TSMC planean inversiones récord.",
        source: "Semiconductor Weekly",
        date: "2025-12-30",
        category: "stocks",
        impact: "neutral",
        impactedAssets: ["AMD", "INTC", "TSM", "NVDA"],
        image: "https://images.unsplash.com/photo-1518770660439-4636190af475?w=400",
        url: "#"
    },
    {
        id: 11,
        title: "Solana alcanza nuevo máximo histórico tras auge de memecoins",
        excerpt: "SOL supera los $250 por primera vez, impulsada por la actividad especulativa en tokens meme y el crecimiento de su ecosistema DeFi.",
        source: "Decrypt",
        date: "2025-12-29",
        category: "crypto",
        impact: "bullish",
        impactedAssets: ["SOL"],
        image: "https://images.unsplash.com/photo-1642790551116-18e150f248e3?w=400",
        url: "#"
    },
    {
        id: 12,
        title: "El petróleo cae por debajo de $60 ante exceso de oferta",
        excerpt: "Arabia Saudita y Rusia no logran acuerdo para reducir producción. Los analistas esperan que el precio se mantenga bajo durante el primer trimestre.",
        source: "Oil Price",
        date: "2025-12-28",
        category: "economy",
        impact: "bearish",
        impactedAssets: ["XLE", "USO"],
        image: "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=400",
        url: "#"
    },
    // NOTICIAS DE POLÍTICA Y GEOPOLÍTICA
    {
        id: 13,
        title: "Trump anuncia nuevos aranceles del 25% a productos chinos",
        excerpt: "La administración estadounidense intensifica la guerra comercial. Sectores tecnológicos y de semiconductores podrían verse afectados significativamente.",
        source: "Reuters",
        date: "2026-01-05",
        category: "politics",
        impact: "bearish",
        impactedAssets: ["NVDA", "AMD", "AAPL", "BABA"],
        image: "https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=400",
        url: "#"
    },
    {
        id: 14,
        title: "Conflicto en Ucrania: Nuevas sanciones a exportaciones de gas ruso",
        excerpt: "La UE impone sanciones adicionales que podrían afectar al suministro energético europeo. Los precios del gas natural suben un 12%.",
        source: "El País",
        date: "2026-01-04",
        category: "politics",
        impact: "bearish",
        impactedAssets: ["EWG", "VGK", "GAZP"],
        image: "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=400",
        url: "#"
    },
    {
        id: 15,
        title: "Venezuela: EEUU estudia nuevas sanciones petroleras",
        excerpt: "Las tensiones entre Washington y Caracas se intensifican. El petróleo venezolano podría salir del mercado, afectando a los precios globales.",
        source: "Bloomberg",
        date: "2026-01-03",
        category: "politics",
        impact: "neutral",
        impactedAssets: ["USO", "XLE", "CVX"],
        image: "https://images.unsplash.com/photo-1591696205602-2f950c417cb9?w=400",
        url: "#"
    },
    {
        id: 16,
        title: "BCE sube tipos de interés otros 25 puntos básicos",
        excerpt: "Lagarde advierte que la lucha contra la inflación continúa. Los bancos europeos suben mientras el sector inmobiliario sufre.",
        source: "Financial Times",
        date: "2026-01-02",
        category: "politics",
        impact: "neutral",
        impactedAssets: ["SAN.MC", "BBVA.MC", "BNP.PA"],
        image: "https://images.unsplash.com/photo-1551135049-8a33b5883817?w=400",
        url: "#"
    },
    {
        id: 17,
        title: "Tensiones en Taiwán: China realiza ejercicios militares",
        excerpt: "Las maniobras militares cerca de Taiwán generan incertidumbre en los mercados asiáticos. TSMC cae un 3% en pre-market.",
        source: "South China Morning Post",
        date: "2026-01-02",
        category: "politics",
        impact: "bearish",
        impactedAssets: ["TSM", "NVDA", "AMD", "INTC"],
        image: "https://images.unsplash.com/photo-1547036967-23d11aacaee0?w=400",
        url: "#"
    },
    {
        id: 18,
        title: "Arabia Saudí reduce producción de petróleo unilateralmente",
        excerpt: "MBS anuncia recorte de 1 millón de barriles diarios para estabilizar precios. Acciones energéticas suben en pre-market.",
        source: "CNBC",
        date: "2026-01-01",
        category: "politics",
        impact: "bullish",
        impactedAssets: ["XOM", "CVX", "USO"],
        image: "https://images.unsplash.com/photo-1513828583688-c52646db42da?w=400",
        url: "#"
    },
    {
        id: 19,
        title: "Amazon anuncia inversión de $10B en IA generativa",
        excerpt: "El gigante del e-commerce acelera su apuesta por la inteligencia artificial. AWS integrará modelos propios para competir con Azure y Google Cloud.",
        source: "TechCrunch",
        date: "2025-12-31",
        category: "stocks",
        impact: "bullish",
        impactedAssets: ["AMZN", "MSFT", "GOOGL"],
        image: "https://images.unsplash.com/photo-1523961131990-5ea7c61b2107?w=400",
        url: "#"
    },
    {
        id: 20,
        title: "Reguladores de EEUU aprueban fusión Microsoft-Activision",
        excerpt: "Tras meses de incertidumbre, la FTC da luz verde a la adquisición de $69B. Microsoft Gaming se convierte en el tercer mayor editor mundial.",
        source: "The Verge",
        date: "2025-12-30",
        category: "stocks",
        impact: "bullish",
        impactedAssets: ["MSFT", "ATVI"],
        image: "https://images.unsplash.com/photo-1612287230202-1ff1d85d1bdf?w=400",
        url: "#"
    }
];

/**
 * Render news cards
 */
function renderNews(filter = 'all') {
    const grid = document.getElementById('newsGrid');
    if (!grid) return;
    
    let filteredNews = newsData;
    if (filter !== 'all') {
        filteredNews = newsData.filter(news => news.category === filter);
    }
    
    grid.innerHTML = filteredNews.map(news => `
        <article class="news-card" data-category="${news.category}">
            <img src="${news.image}" alt="${news.title}" class="news-image" onerror="this.src='https://via.placeholder.com/400x180/1a2332/00d4aa?text=News'">
            <div class="news-content">
                <div class="news-source">${news.source}</div>
                <h3 class="news-title">${news.title}</h3>
                <p class="news-excerpt">${news.excerpt}</p>
                <div class="news-assets">
                    ${news.impactedAssets.map(asset => `<span class="asset-tag">${asset}</span>`).join('')}
                </div>
                <div class="news-meta">
                    <span class="news-date">${formatNewsDate(news.date)}</span>
                    <span class="market-impact ${news.impact}">
                        ${news.impact === 'bullish' ? '📈 Alcista' : news.impact === 'bearish' ? '📉 Bajista' : '➡️ Neutral'}
                    </span>
                </div>
            </div>
        </article>
    `).join('');
}

/**
 * Format news date
 */
function formatNewsDate(dateStr) {
    const date = new Date(dateStr);
    const now = new Date();
    const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) return 'Hoy';
    if (diffDays === 1) return 'Ayer';
    if (diffDays < 7) return `Hace ${diffDays} días`;
    
    return date.toLocaleDateString('es-ES', { day: 'numeric', month: 'short' });
}

/**
 * Initialize news filters
 */
function initNewsFilters() {
    const filterBtns = document.querySelectorAll('.news-filters .chart-btn');
    
    filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            filterBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            renderNews(btn.dataset.filter);
        });
    });
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Initial render
    setTimeout(() => {
        renderNews();
        initNewsFilters();
    }, 100);
});

// Export for use in pages.js
window.renderNews = renderNews;

