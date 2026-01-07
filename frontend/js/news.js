/**
 * News Module
 * Fetches and displays real financial news from API
 */

// API URL - uses global CONFIG from app.js
const NEWS_API = window.API_BASE_URL || CONFIG?.API_BASE_URL || 'http://localhost:8000/api';

// State
let currentNewsCategory = 'all';
let newsLastUpdate = null;
let isLoadingNews = false;

/**
 * Fetch news from API
 */
async function fetchNews(category = 'all', limit = 30) {
    try {
        const response = await fetch(`${NEWS_API}/news?category=${category}&limit=${limit}`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        newsLastUpdate = new Date(data.last_updated);
        return data.news || [];
        
    } catch (error) {
        console.error('Error fetching news:', error);
        // Return fallback news if API fails
        return getFallbackNews();
    }
}

/**
 * Fallback news data in case API fails
 */
function getFallbackNews() {
    return [
        {
            title: "Cargando noticias...",
            excerpt: "Estamos obteniendo las últimas noticias financieras. Por favor, espera un momento.",
            source: "FinTrack",
            date: new Date().toISOString().split('T')[0],
            category: "economy",
            impact: "neutral",
            impactedAssets: [],
            url: "#"
        }
    ];
}

/**
 * Render news cards
 */
async function renderNews(filter = 'all') {
    const grid = document.getElementById('newsGrid');
    if (!grid) return;
    
    // Show loading state
    if (!isLoadingNews) {
        isLoadingNews = true;
        grid.innerHTML = `
            <div class="news-loading">
                <span class="loading-icon">📰</span>
                <p>Cargando noticias reales...</p>
            </div>
        `;
    }
    
    // Update current category
    currentNewsCategory = filter;
    
    // Fetch news from API
    const newsData = await fetchNews(filter);
    isLoadingNews = false;
    
    if (!newsData || newsData.length === 0) {
        grid.innerHTML = `
            <div class="news-empty">
                <span class="empty-icon">📭</span>
                <p>No hay noticias disponibles en esta categoría</p>
            </div>
        `;
        return;
    }
    
    // Render news cards
    grid.innerHTML = newsData.map((news, index) => `
        <article class="news-card" data-category="${news.category}" style="animation-delay: ${index * 0.05}s">
            ${news.image ? `<img src="${news.image}" alt="${news.title}" class="news-image" onerror="this.style.display='none'">` : ''}
            <div class="news-content">
                <div class="news-header">
                    <span class="news-source">${news.source}</span>
                    <span class="news-category-badge ${news.category}">${getCategoryLabel(news.category)}</span>
                </div>
                <h3 class="news-title">${news.title}</h3>
                <p class="news-excerpt">${news.excerpt || ''}</p>
                ${news.impactedAssets && news.impactedAssets.length > 0 ? `
                    <div class="news-assets">
                        ${news.impactedAssets.map(asset => `<span class="asset-tag">${asset}</span>`).join('')}
                    </div>
                ` : ''}
                <div class="news-meta">
                    <span class="news-date">${formatNewsDate(news.date)}</span>
                    <span class="market-impact ${news.impact}">
                        ${getImpactLabel(news.impact)}
                    </span>
                </div>
                ${news.url && news.url !== '#' ? `
                    <a href="${news.url}" target="_blank" rel="noopener noreferrer" class="news-link">
                        Leer más →
                    </a>
                ` : ''}
            </div>
        </article>
    `).join('');
    
    // Update last update indicator
    updateNewsTimestamp();
}

/**
 * Get category label in Spanish
 */
function getCategoryLabel(category) {
    const labels = {
        'stocks': '📈 Acciones',
        'crypto': '🪙 Cripto',
        'economy': '💼 Economía',
        'politics': '🏛️ Política'
    };
    return labels[category] || category;
}

/**
 * Get impact label
 */
function getImpactLabel(impact) {
    const labels = {
        'bullish': '📈 Alcista',
        'bearish': '📉 Bajista',
        'neutral': '➡️ Neutral'
    };
    return labels[impact] || '➡️ Neutral';
}

/**
 * Format news date
 */
function formatNewsDate(dateStr) {
    if (!dateStr) return '';
    
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    
    if (diffHours < 1) return 'Hace menos de 1 hora';
    if (diffHours < 24) return `Hace ${diffHours} hora${diffHours > 1 ? 's' : ''}`;
    if (diffDays === 1) return 'Ayer';
    if (diffDays < 7) return `Hace ${diffDays} días`;
    
    return date.toLocaleDateString('es-ES', { day: 'numeric', month: 'short' });
}

/**
 * Update news timestamp display
 */
function updateNewsTimestamp() {
    const timestampEl = document.getElementById('newsLastUpdate');
    if (timestampEl && newsLastUpdate) {
        timestampEl.textContent = `Última actualización: ${newsLastUpdate.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })}`;
    }
}

/**
 * Initialize news filters
 */
function initNewsFilters() {
    const filterBtns = document.querySelectorAll('.news-filters .chart-btn, .news-filters .filter-btn');
    
    filterBtns.forEach(btn => {
        btn.addEventListener('click', async () => {
            // Update active state
            filterBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            // Render filtered news
            const filter = btn.dataset.filter || 'all';
            await renderNews(filter);
        });
    });
}

/**
 * Refresh news manually
 */
async function refreshNews() {
    const refreshBtn = document.getElementById('refreshNewsBtn');
    if (refreshBtn) {
        refreshBtn.classList.add('spinning');
        refreshBtn.disabled = true;
    }
    
    // Clear cache by fetching fresh
    await renderNews(currentNewsCategory);
    
    if (refreshBtn) {
        refreshBtn.classList.remove('spinning');
        refreshBtn.disabled = false;
    }
}

/**
 * Initialize news page
 */
function initNews() {
    renderNews('all');
    initNewsFilters();
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Initial render with small delay to ensure page is loaded
    setTimeout(() => {
        const newsGrid = document.getElementById('newsGrid');
        if (newsGrid) {
            initNews();
        }
    }, 100);
});

// Export for use in pages.js
window.renderNews = renderNews;
window.refreshNews = refreshNews;
window.initNews = initNews;
