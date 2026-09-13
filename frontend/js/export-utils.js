/**
 * Export helpers — save any section/table as PDF, PNG image, or standalone HTML.
 * Libraries (html2canvas, jsPDF) are loaded lazily from CDN only when first used.
 * Note: externally-hosted chart images (QuickChart) may not render in PNG/PDF if
 * they don't allow CORS; the HTML export keeps them (referenced by URL).
 */
const _EXPORT_CDN = {
    html2canvas: 'https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js',
    jspdf: 'https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js',
};

function _loadScript(src) {
    return new Promise((resolve, reject) => {
        if ([...document.scripts].some((s) => s.src === src)) return resolve();
        const s = document.createElement('script');
        s.src = src; s.onload = resolve; s.onerror = () => reject(new Error('No se pudo cargar ' + src));
        document.head.appendChild(s);
    });
}

async function _ensureLibs(need) {
    if (need.canvas && !window.html2canvas) await _loadScript(_EXPORT_CDN.html2canvas);
    if (need.pdf && !window.jspdf) await _loadScript(_EXPORT_CDN.jspdf);
}

function _bgColor() {
    try { return getComputedStyle(document.body).backgroundColor || '#ffffff'; } catch (e) { return '#ffffff'; }
}

async function _snapshot(el) {
    await _ensureLibs({ canvas: true });
    return window.html2canvas(el, { scale: 2, backgroundColor: _bgColor(), useCORS: true, logging: false });
}

async function exportAsPNG(el, filename) {
    const canvas = await _snapshot(el);
    const a = document.createElement('a');
    a.href = canvas.toDataURL('image/png');
    a.download = filename + '.png';
    a.click();
}

async function exportAsPDF(el, filename) {
    await _ensureLibs({ canvas: true, pdf: true });
    const canvas = await _snapshot(el);
    const img = canvas.toDataURL('image/png');
    const { jsPDF } = window.jspdf;
    const pdf = new jsPDF('p', 'mm', 'a4');
    const pw = pdf.internal.pageSize.getWidth();
    const ph = pdf.internal.pageSize.getHeight();
    const iw = pw;
    const ih = (canvas.height * iw) / canvas.width;
    let remaining = ih;
    let pos = 0;
    pdf.addImage(img, 'PNG', 0, pos, iw, ih);
    remaining -= ph;
    while (remaining > 0) {          // paginate tall content across A4 pages
        pos -= ph;
        pdf.addPage();
        pdf.addImage(img, 'PNG', 0, pos, iw, ih);
        remaining -= ph;
    }
    pdf.save(filename + '.pdf');
}

async function exportAsHTML(el, filename) {
    let css = '';
    try { css = await (await fetch('/css/styles.css')).text(); } catch (e) { /* standalone will just be unstyled */ }
    const doc = `<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${filename}</title><style>${css}\nbody{padding:16px;}</style></head>
<body>${el.outerHTML}</body></html>`;
    const blob = new Blob([doc], { type: 'text/html' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename + '.html';
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

/**
 * Single entry point used by the export buttons.
 * @param {string} elementId  id of the element to capture
 * @param {string} baseName   file base name (a date is appended)
 * @param {string} format     'pdf' | 'png' | 'html'
 * @param {HTMLElement} [btn] the button (for a small loading state)
 */
async function exportSection(elementId, baseName, format, btn) {
    const el = document.getElementById(elementId);
    if (!el) return;
    const name = `${baseName}_${new Date().toISOString().slice(0, 10)}`;
    const prev = btn ? btn.textContent : null;
    if (btn) { btn.disabled = true; btn.textContent = '…'; }
    try {
        if (format === 'png') await exportAsPNG(el, name);
        else if (format === 'pdf') await exportAsPDF(el, name);
        else await exportAsHTML(el, name);
    } catch (e) {
        if (window.showToast) window.showToast('No se pudo exportar: ' + (e.message || e), 'error');
        else alert('No se pudo exportar: ' + (e.message || e));
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = prev; }
    }
}

// Reusable toolbar HTML to drop into a section header.
function exportToolbarHTML(elementId, baseName) {
    const call = (fmt) => `onclick="exportSection('${elementId}','${baseName}','${fmt}',this)"`;
    return `<div class="export-toolbar" style="display:inline-flex; gap:6px; flex-wrap:wrap;">
        <button class="btn-secondary" style="padding:4px 10px; font-size:12px;" title="Descargar PDF" ${call('pdf')}>⬇️ PDF</button>
        <button class="btn-secondary" style="padding:4px 10px; font-size:12px;" title="Descargar imagen PNG" ${call('png')}>🖼️ PNG</button>
        <button class="btn-secondary" style="padding:4px 10px; font-size:12px;" title="Descargar HTML" ${call('html')}>&lt;/&gt; HTML</button>
    </div>`;
}
