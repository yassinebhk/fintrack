/**
 * Portfolio Manager - Handles position management, CSV import, and editing
 */

// Use the global API_BASE_URL from app.js (loaded first)
const API_BASE = window.API_BASE_URL || 'http://localhost:8000/api';
let currentPositions = [];
let importStep = 1;
let uploadedFile = null;
let previewData = null;

// ============================================
// Modal Functions
// ============================================

function showModal(modalId) {
    document.getElementById(modalId).classList.add('active');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
    // Reset import steps
    if (modalId === 'importModal') {
        importStep = 1;
        updateImportStep();
    }
}

function showAddPositionModal() {
    console.log('Opening add position modal...');
    const form = document.getElementById('addPositionForm');
    if (form) form.reset();
    
    // Reset calculated result
    const resultDiv = document.getElementById('calculatedResult');
    if (resultDiv) resultDiv.style.display = 'none';
    
    // Toggle ISIN field based on default type
    toggleISINField();
    
    showModal('addPositionModal');
    console.log('Modal opened');
}

function showImportModal() {
    importStep = 1;
    uploadedFile = null;
    previewData = null;
    updateImportStep();
    showModal('importModal');
}

function showQuickAddModal() {
    document.getElementById('quickAddText').value = '';
    showModal('quickAddModal');
}

// ============================================
// Load and Display Positions
// ============================================

async function loadManagerPositions() {
    try {
        const response = await fetch(`${API_BASE}/positions`);
        const positions = await response.json();
        currentPositions = positions;
        renderManagerPositions(positions);
    } catch (error) {
        console.error('Error loading positions:', error);
    }
}

function renderManagerPositions(positions) {
    const tbody = document.getElementById('managerPositionsBody');
    if (!tbody) return;

    if (!positions || positions.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center text-muted" style="padding: 3rem;">
                    <div style="font-size: 3rem; margin-bottom: 1rem;">📭</div>
                    <p>No tienes posiciones todavía</p>
                    <p><small>Usa los botones de arriba para añadir tus inversiones</small></p>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = positions.map(pos => {
        const assetName = getAssetName(pos.ticker);
        const showName = assetName !== pos.ticker; // Solo mostrar nombre si es diferente al ticker
        
        return `
        <tr>
            <td>
                <div class="ticker-cell">
                    <div class="ticker-icon">${getTickerIcon(pos.ticker, pos.type)}</div>
                    <div class="ticker-info">
                        <span class="ticker-symbol">${pos.ticker}</span>
                        ${showName ? `<span class="ticker-name">${assetName}</span>` : ''}
                    </div>
                </div>
            </td>
            <td><span class="type-badge ${pos.type}">${getTypeName(pos.type)}</span></td>
            <td>${pos.broker}</td>
            <td class="text-right mono">${formatNumber(pos.quantity, pos.type === 'crypto' ? 6 : 4)}</td>
            <td class="text-right mono">${formatNumber(pos.avg_price)}</td>
            <td class="text-right">${pos.currency}</td>
            <td>
                <div class="action-buttons">
                    <button class="btn-icon" onclick="editPosition('${pos.ticker}')" title="Editar">✏️</button>
                    <button class="btn-icon btn-danger" onclick="deletePosition('${pos.ticker}')" title="Eliminar">🗑️</button>
                </div>
            </td>
        </tr>
    `}).join('');
}

function getTickerIcon(ticker, type) {
    const icons = {
        'BTC': '₿',
        'ETH': 'Ξ',
        'SOL': '◎',
        'DOGE': '🐕',
        'PEPE': '🐸',
        'XRP': '✕',
    };
    
    if (icons[ticker.toUpperCase()]) {
        return icons[ticker.toUpperCase()];
    }
    
    // Iconos por tipo
    if (type === 'crypto') return '🪙';
    if (type === 'etf') return '📊';
    if (type === 'fund') return '📈';
    if (type === 'stock') return '📉';
    
    return ticker.substring(0, 2).toUpperCase();
}

function getTypeName(type) {
    const names = {
        'crypto': 'Crypto',
        'etf': 'ETF',
        'fund': 'Fondo',
        'stock': 'Acción'
    };
    return names[type] || type;
}

function formatNumber(value, decimals = 2) {
    // Para números muy pequeños (como precio de PEPE), mostrar más decimales
    if (value > 0 && value < 0.01) {
        // Encontrar cuántos decimales significativos necesitamos
        const str = value.toString();
        const match = str.match(/0\.0*[1-9]/);
        if (match) {
            decimals = Math.max(decimals, match[0].length - 1 + 2);
        }
    }
    
    return new Intl.NumberFormat('es-ES', {
        minimumFractionDigits: Math.min(decimals, 2),
        maximumFractionDigits: decimals
    }).format(value);
}

// ASSET_NAMES y getAssetName definidos en app.js

// ============================================
// Add Position
// ============================================

/**
 * Calculate quantity from amount and price
 */
function calculateQuantity() {
    const amount = parseFloat(document.getElementById('addAmount').value) || 0;
    const price = parseFloat(document.getElementById('addUnitPrice').value) || 0;
    
    const resultDiv = document.getElementById('calculatedResult');
    const quantitySpan = document.getElementById('calculatedQuantity');
    const unitSpan = document.getElementById('calculatedUnit');
    
    if (amount > 0 && price > 0) {
        const quantity = amount / price;
        quantitySpan.textContent = quantity.toFixed(6);
        
        // Update unit based on type
        const type = document.getElementById('addType').value;
        unitSpan.textContent = type === 'crypto' ? 'monedas' : 'participaciones';
        
        resultDiv.style.display = 'block';
        
        // Set hidden fields
        document.getElementById('addQuantity').value = quantity;
        document.getElementById('addAvgPrice').value = price;
    } else {
        resultDiv.style.display = 'none';
    }
}

/**
 * Toggle ISIN field visibility based on asset type
 */
function toggleISINField() {
    const type = document.getElementById('addType').value;
    const isinGroup = document.getElementById('isinGroup');
    const tickerHelp = document.querySelector('#tickerGroup .form-help');
    
    if (type === 'etf' || type === 'fund') {
        isinGroup.style.display = 'block';
        tickerHelp.textContent = 'El ticker del ETF (ej: VWCE.DE) o déjalo vacío si usas ISIN';
    } else if (type === 'crypto') {
        isinGroup.style.display = 'none';
        tickerHelp.textContent = 'El símbolo de la crypto (BTC, ETH, SOL...)';
    } else {
        isinGroup.style.display = 'none';
        tickerHelp.textContent = 'El símbolo de la acción (AAPL, MSFT, GOOGL...)';
    }
    
    // Recalculate to update unit text
    calculateQuantity();
}

async function handleAddPosition(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    
    // Get ticker - use ISIN if ticker is empty
    let ticker = formData.get('ticker')?.toUpperCase().trim() || '';
    const isin = formData.get('isin')?.toUpperCase().trim() || '';
    
    if (!ticker && isin) {
        ticker = isin;
    }
    
    if (!ticker) {
        showToast('Por favor, introduce un ticker o ISIN', 'error');
        return;
    }
    
    // Get calculated values
    const quantity = parseFloat(document.getElementById('addQuantity').value);
    const avgPrice = parseFloat(document.getElementById('addAvgPrice').value);
    
    if (!quantity || !avgPrice) {
        showToast('Por favor, introduce el importe y precio', 'error');
        return;
    }
    
    const position = {
        ticker: ticker,
        quantity: quantity,
        avg_price: avgPrice,
        type: formData.get('type'),
        currency: 'EUR',
        broker: formData.get('broker')
    };

    try {
        const response = await fetch(`${API_BASE}/positions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(position)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Error al añadir posición');
        }

        const amountInvested = parseFloat(document.getElementById('addAmount').value);
        showToast(`✅ Añadido: ${quantity.toFixed(4)} ${ticker} (${amountInvested}€)`, 'success');
        closeModal('addPositionModal');
        form.reset();
        document.getElementById('calculatedResult').style.display = 'none';
        loadManagerPositions();
        
        // Also refresh main dashboard
        if (typeof loadDashboard === 'function') {
            loadDashboard();
        }
    } catch (error) {
        showToast(error.message, 'error');
    }
}

// ============================================
// Edit Position
// ============================================

function editPosition(ticker) {
    const position = currentPositions.find(p => p.ticker === ticker);
    if (!position) return;

    document.getElementById('editOriginalTicker').value = ticker;
    document.getElementById('editTicker').value = ticker;
    document.getElementById('editQuantity').value = position.quantity;
    document.getElementById('editAvgPrice').value = position.avg_price;

    showModal('editPositionModal');
}

async function handleEditPosition(event) {
    event.preventDefault();
    const ticker = document.getElementById('editOriginalTicker').value;
    const quantity = parseFloat(document.getElementById('editQuantity').value);
    const avg_price = parseFloat(document.getElementById('editAvgPrice').value);

    try {
        const response = await fetch(`${API_BASE}/positions/${ticker}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ quantity, avg_price })
        });

        if (!response.ok) {
            throw new Error('Error al actualizar posición');
        }

        showToast(`Posición ${ticker} actualizada`, 'success');
        closeModal('editPositionModal');
        loadManagerPositions();
        
        if (typeof loadDashboard === 'function') {
            loadDashboard();
        }
    } catch (error) {
        showToast(error.message, 'error');
    }
}

// ============================================
// Delete Position
// ============================================

async function deletePosition(ticker) {
    if (!confirm(`¿Estás seguro de eliminar la posición ${ticker}?`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/positions/${ticker}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            throw new Error('Error al eliminar posición');
        }

        showToast(`Posición ${ticker} eliminada`, 'success');
        loadManagerPositions();
        
        if (typeof loadDashboard === 'function') {
            loadDashboard();
        }
    } catch (error) {
        showToast(error.message, 'error');
    }
}

// ============================================
// CSV Import
// ============================================

function initUploadZone() {
    const zone = document.getElementById('uploadZone');
    const input = document.getElementById('csvFileInput');
    
    if (!zone || !input) return;

    zone.addEventListener('click', () => input.click());
    
    zone.addEventListener('dragover', (e) => {
        e.preventDefault();
        zone.classList.add('dragover');
    });

    zone.addEventListener('dragleave', () => {
        zone.classList.remove('dragover');
    });

    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileSelect(files[0]);
        }
    });

    input.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });
}

function handleFileSelect(file) {
    uploadedFile = file;
    document.getElementById('uploadZone').innerHTML = `
        <span class="upload-icon">✅</span>
        <p><strong>${file.name}</strong></p>
        <small>${(file.size / 1024).toFixed(1)} KB</small>
    `;
}

function updateImportStep() {
    // Update step visibility
    document.querySelectorAll('.import-step').forEach((step, i) => {
        step.classList.toggle('active', i + 1 === importStep);
    });

    // Update buttons
    const backBtn = document.getElementById('importBackBtn');
    const nextBtn = document.getElementById('importNextBtn');

    backBtn.style.display = importStep > 1 ? 'inline-block' : 'none';
    
    if (importStep === 1) {
        nextBtn.textContent = 'Siguiente →';
    } else if (importStep === 2) {
        nextBtn.textContent = 'Importar';
    } else {
        nextBtn.textContent = 'Cerrar';
    }
}

async function importNext() {
    if (importStep === 1) {
        // Validate file selected
        if (!uploadedFile) {
            showToast('Por favor, selecciona un archivo CSV', 'warning');
            return;
        }
        
        // Preview file
        await previewCSV();
        importStep = 2;
        updateImportStep();
    } else if (importStep === 2) {
        // Perform import
        await performImport();
        importStep = 3;
        updateImportStep();
    } else {
        // Close
        closeModal('importModal');
        loadManagerPositions();
        if (typeof loadDashboard === 'function') {
            loadDashboard();
        }
    }
}

function importBack() {
    if (importStep > 1) {
        importStep--;
        updateImportStep();
    }
}

async function previewCSV() {
    const formData = new FormData();
    formData.append('file', uploadedFile);

    try {
        const response = await fetch(`${API_BASE}/import/preview`, {
            method: 'POST',
            body: formData
        });

        previewData = await response.json();

        // Update preview info
        document.getElementById('previewFormat').textContent = 
            `Formato: ${previewData.detected_format.format} (${previewData.detected_format.confidence})`;
        document.getElementById('previewRows').textContent = 
            `Filas: ${previewData.rows}`;

        // Render preview table
        const thead = document.getElementById('previewHead');
        const tbody = document.getElementById('previewBody');

        thead.innerHTML = `<tr>${previewData.columns.map(c => `<th>${c}</th>`).join('')}</tr>`;
        tbody.innerHTML = previewData.preview.map(row => 
            `<tr>${previewData.columns.map(c => `<td>${row[c] || ''}</td>`).join('')}</tr>`
        ).join('');
    } catch (error) {
        showToast('Error al procesar el archivo: ' + error.message, 'error');
    }
}

async function performImport() {
    const formData = new FormData();
    formData.append('file', uploadedFile);
    formData.append('broker', document.getElementById('importBroker').value);
    formData.append('merge_existing', document.getElementById('mergeExisting').checked);

    try {
        const response = await fetch(`${API_BASE}/import/csv`, {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || 'Error en la importación');
        }

        // Show result
        document.getElementById('importResult').innerHTML = `
            <div class="import-success">
                <span style="font-size: 4rem;">✅</span>
                <h4>¡Importación exitosa!</h4>
                <p>Se importaron <strong>${result.positions_imported}</strong> posiciones desde <strong>${result.broker}</strong></p>
                <div class="imported-list">
                    ${result.positions.slice(0, 5).map(p => 
                        `<div class="imported-item">${p.ticker}: ${p.quantity} unidades</div>`
                    ).join('')}
                    ${result.positions.length > 5 ? `<div class="imported-item">... y ${result.positions.length - 5} más</div>` : ''}
                </div>
            </div>
        `;

        showToast(`${result.positions_imported} posiciones importadas correctamente`, 'success');
    } catch (error) {
        document.getElementById('importResult').innerHTML = `
            <div class="import-error">
                <span style="font-size: 4rem;">❌</span>
                <h4>Error en la importación</h4>
                <p>${error.message}</p>
            </div>
        `;
        showToast(error.message, 'error');
    }
}

// ============================================
// Quick Add
// ============================================

async function handleQuickAdd() {
    const text = document.getElementById('quickAddText').value.trim();
    if (!text) {
        showToast('Por favor, introduce al menos una posición', 'warning');
        return;
    }

    const lines = text.split('\n').filter(line => line.trim());
    let added = 0;
    let errors = [];

    for (const line of lines) {
        const parts = line.split(',').map(p => p.trim());
        if (parts.length < 3) {
            errors.push(`Línea inválida: ${line}`);
            continue;
        }

        const position = {
            ticker: parts[0].toUpperCase(),
            quantity: parseFloat(parts[1]),
            avg_price: parseFloat(parts[2]),
            type: parts[3] || 'stock',
            currency: parts[4] || 'EUR',
            broker: parts[5] || 'Manual'
        };

        try {
            const response = await fetch(`${API_BASE}/positions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(position)
            });

            if (response.ok) {
                added++;
            } else {
                const error = await response.json();
                errors.push(`${position.ticker}: ${error.detail}`);
            }
        } catch (e) {
            errors.push(`${position.ticker}: Error de conexión`);
        }
    }

    if (added > 0) {
        showToast(`${added} posiciones añadidas correctamente`, 'success');
    }
    if (errors.length > 0) {
        console.error('Errores:', errors);
        showToast(`${errors.length} errores: ${errors[0]}`, 'warning');
    }

    closeModal('quickAddModal');
    loadManagerPositions();
    
    if (typeof loadDashboard === 'function') {
        loadDashboard();
    }
}

// ============================================
// Export & Clear
// ============================================

function exportPositions() {
    if (!currentPositions || currentPositions.length === 0) {
        showToast('No hay posiciones para exportar', 'warning');
        return;
    }

    const headers = ['ticker', 'quantity', 'avg_price', 'type', 'currency', 'broker'];
    const csv = [
        headers.join(','),
        ...currentPositions.map(p => headers.map(h => p[h]).join(','))
    ].join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `fintrack_positions_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);

    showToast('CSV exportado correctamente', 'success');
}

async function confirmClearAll() {
    if (!confirm('⚠️ ¿Estás seguro de eliminar TODAS las posiciones? Esta acción no se puede deshacer.')) {
        return;
    }
    if (!confirm('⚠️ Esta es tu última oportunidad. ¿Realmente quieres borrar todo?')) {
        return;
    }

    try {
        for (const pos of currentPositions) {
            await fetch(`${API_BASE}/positions/${pos.ticker}`, { method: 'DELETE' });
        }
        showToast('Todas las posiciones han sido eliminadas', 'success');
        loadManagerPositions();
        
        if (typeof loadDashboard === 'function') {
            loadDashboard();
        }
    } catch (error) {
        showToast('Error al eliminar posiciones', 'error');
    }
}

// ============================================
// Toast (if not already defined)
// ============================================

function showToast(message, type = 'info') {
    if (window.showToast && window.showToast !== showToast) {
        window.showToast(message, type);
        return;
    }
    
    const container = document.getElementById('toastContainer') || createToastContainer();
    const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${icons[type]}</span>
        <span class="toast-message">${message}</span>
    `;
    
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'toast-container';
    document.body.appendChild(container);
    return container;
}

// ============================================
// Initialize
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    // Initialize upload zone
    setTimeout(initUploadZone, 100);
    
    // Load positions when page is shown
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
                const page = document.getElementById('page-portfolio-manager');
                if (page && page.classList.contains('active')) {
                    loadManagerPositions();
                }
            }
        });
    });

    const page = document.getElementById('page-portfolio-manager');
    if (page) {
        observer.observe(page, { attributes: true });
    }
});

// Also load when navigating to the page
window.loadManagerPositions = loadManagerPositions;

