/**
 * 📔 Diario de decisiones — reasoned trade journal with a review loop.
 * Log WHY you decide (thesis) BEFORE the outcome; later record WHAT happened and
 * the LESSON. That thesis→outcome→lesson loop is the habit that most improves
 * decision quality over time. No money moves here — it's a record of reasoning.
 */
const JOURNAL_API = window.API_BASE_URL || '/api';

const JOURNAL_ACTIONS = { compra: '🟢 Compra', venta: '🔴 Venta', mantener: '⏸️ Mantener', vigilar: '👀 Vigilar' };
const JOURNAL_OUTCOME = { acierto: '✅ Acierto', fallo: '❌ Fallo', neutral: '➖ Neutral' };

function _jEsc(s) {
    return (s || '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

async function loadJournal() {
    const el = document.getElementById('journalContent');
    if (!el) return;
    let entries = [];
    try {
        const r = await fetch(`${JOURNAL_API}/journal`);
        if (r.ok) entries = (await r.json()).entries || [];
    } catch (e) { /* still render the form */ }
    el.innerHTML = journalFormHtml() + journalStatsHtml(entries) + journalListHtml(entries);
    wireJournalForm();
}

function journalFormHtml() {
    const sel = (o, cur) => Object.entries(o).map(([k, v]) => `<option value="${k}"${k === cur ? ' selected' : ''}>${v}</option>`).join('');
    return `<div class="card" style="margin-bottom:16px;">
        <h3>➕ Registrar una decisión</h3>
        <p class="text-muted" style="font-size:12px; margin:-4px 0 12px;">Escribe <strong>por qué</strong> decides esto <em>antes</em> de saber el resultado. Más tarde lo revisas y anotas la <strong>lección</strong>.</p>
        <div style="display:flex; gap:10px; flex-wrap:wrap;">
            <div class="form-group"><label>Activo (ticker)</label><input id="jTicker" placeholder="AAPL" style="text-transform:uppercase;"></div>
            <div class="form-group"><label>Nombre (opcional)</label><input id="jName" placeholder="Apple"></div>
            <div class="form-group"><label>Acción</label><select id="jAction">${sel(JOURNAL_ACTIONS, 'compra')}</select></div>
            <div class="form-group"><label>Convicción</label><select id="jConv">${sel({ alta: 'Alta', media: 'Media', baja: 'Baja' }, 'media')}</select></div>
            <div class="form-group"><label>Horizonte</label><input id="jHorizon" placeholder="6-12 meses"></div>
            <div class="form-group"><label>Precio objetivo (opc)</label><input id="jTarget" type="number" step="any"></div>
            <div class="form-group"><label>Stop (opc)</label><input id="jStop" type="number" step="any"></div>
        </div>
        <div class="form-group" style="margin-top:8px;">
            <label>Tesis — ¿por qué? (mín. 10 caracteres)</label>
            <textarea id="jThesis" rows="3" placeholder="Ej: entro en X porque sus fundamentales han mejorado (ROE 25%, crecimiento 18%), está barata vs su sector, y el catalizador es el lanzamiento de..."></textarea>
        </div>
        <button class="btn-primary" id="jSubmit">Registrar decisión</button>
        <span id="jMsg" style="margin-left:10px; font-size:13px;"></span>
    </div>`;
}

function journalStatsHtml(entries) {
    const reviewed = entries.filter(e => e.status === 'revisada');
    if (reviewed.length < 3) return '';
    const wins = reviewed.filter(e => e.outcome === 'acierto').length;
    const rate = Math.round(wins / reviewed.length * 100);
    const pending = entries.length - reviewed.length;
    return `<div class="card" style="margin-bottom:16px;">
        <h4>📊 Tu historial de decisiones</h4>
        <p style="font-size:14px; margin:6px 0 0;">De <strong>${reviewed.length}</strong> decisiones revisadas acertaste el <strong>${rate}%</strong> (${wins} aciertos)${pending ? ` · <span class="text-muted">${pending} pendientes de revisar</span>` : ''}.</p>
    </div>`;
}

function journalListHtml(entries) {
    if (!entries.length) return '<p class="text-muted">Aún no has registrado ninguna decisión. Empieza con el formulario de arriba ☝️</p>';
    const convColor = { alta: 'var(--positive)', media: 'var(--warning)', baja: 'var(--text-tertiary)' };
    return entries.map(e => {
        const date = e.created_at ? new Date(e.created_at).toLocaleDateString('es-ES') : '';
        const reviewed = e.status === 'revisada';
        const border = reviewed ? 'var(--text-tertiary)' : (convColor[e.conviction] || 'var(--warning)');
        const meta = [
            e.target_price != null ? `🎯 objetivo ${e.target_price}` : '',
            e.stop_price != null ? `🛑 stop ${e.stop_price}` : '',
            e.entry_price != null ? `entrada ${e.entry_price}` : '',
        ].filter(Boolean).join(' · ');
        return `<div class="card" style="margin-bottom:12px; border-left:3px solid ${border};">
            <div style="display:flex; justify-content:space-between; gap:8px; flex-wrap:wrap;">
                <div><strong>${JOURNAL_ACTIONS[e.action] || e.action}</strong> ${_jEsc(e.name || e.ticker)}${(e.ticker && e.name) ? ` <span class="text-muted mono" style="font-size:12px;">${_jEsc(e.ticker)}</span>` : ''}</div>
                <div class="text-muted" style="font-size:12px;">${date} · convicción ${e.conviction}${e.horizon ? ` · ${_jEsc(e.horizon)}` : ''}</div>
            </div>
            <p style="margin:6px 0 4px;"><strong>Tesis:</strong> ${_jEsc(e.thesis)}</p>
            ${meta ? `<p class="text-muted" style="font-size:12px; margin:2px 0;">${meta}</p>` : ''}
            ${reviewed
                ? `<div style="margin-top:8px; padding-top:8px; border-top:1px solid rgba(43,40,34,0.08);">
                       <p style="margin:0;"><strong>Resultado:</strong> ${JOURNAL_OUTCOME[e.outcome] || e.outcome}${e.review_price != null ? ` · precio al revisar ${e.review_price}` : ''}</p>
                       <p style="margin:4px 0 0;"><strong>Lección:</strong> ${_jEsc(e.lesson || '')}</p>
                   </div>`
                : `<div id="jrev-${e.id}" style="margin-top:8px; display:flex; gap:8px; flex-wrap:wrap;">
                       <button class="btn-secondary" onclick="showJournalReview(${e.id})">Revisar (resultado + lección)</button>
                       <button class="btn-secondary" style="background:transparent; color:var(--negative);" onclick="deleteJournal(${e.id})">Eliminar</button>
                   </div>`}
        </div>`;
    }).join('');
}

function wireJournalForm() {
    const btn = document.getElementById('jSubmit');
    if (!btn) return;
    btn.onclick = async () => {
        const thesis = (document.getElementById('jThesis').value || '').trim();
        const msg = document.getElementById('jMsg');
        if (thesis.length < 10) { msg.textContent = 'La tesis debe tener al menos 10 caracteres.'; msg.style.color = 'var(--negative)'; return; }
        const body = {
            ticker: document.getElementById('jTicker').value.trim(),
            name: document.getElementById('jName').value.trim(),
            action: document.getElementById('jAction').value,
            conviction: document.getElementById('jConv').value,
            horizon: document.getElementById('jHorizon').value.trim(),
            thesis,
        };
        const t = parseFloat(document.getElementById('jTarget').value); if (!isNaN(t)) body.target_price = t;
        const s = parseFloat(document.getElementById('jStop').value); if (!isNaN(s)) body.stop_price = s;
        btn.disabled = true; msg.textContent = 'Guardando…'; msg.style.color = 'var(--text-secondary)';
        try {
            const r = await fetch(`${JOURNAL_API}/journal`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
            if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.detail || 'error'); }
            await loadJournal();
        } catch (e) { msg.textContent = 'No se pudo guardar: ' + e.message; msg.style.color = 'var(--negative)'; btn.disabled = false; }
    };
}

function showJournalReview(id) {
    const box = document.getElementById(`jrev-${id}`);
    if (!box) return;
    box.innerHTML = `<div style="border:1px solid rgba(43,40,34,0.12); border-radius:8px; padding:10px; width:100%;">
        <div class="form-group"><label>Resultado</label>
            <select id="jro-${id}"><option value="acierto">✅ Acierto</option><option value="neutral">➖ Neutral</option><option value="fallo">❌ Fallo</option></select></div>
        <div class="form-group" style="margin-top:6px;"><label>Lección — ¿qué aprendiste?</label>
            <textarea id="jrl-${id}" rows="2" placeholder="Ej: la tesis era correcta pero entré caro; la próxima vez espero un mejor punto de entrada."></textarea></div>
        <button class="btn-primary" onclick="submitJournalReview(${id})">Guardar revisión</button>
        <span id="jrm-${id}" style="margin-left:8px; font-size:13px;"></span>
    </div>`;
}

async function submitJournalReview(id) {
    const outcome = document.getElementById(`jro-${id}`).value;
    const lesson = (document.getElementById(`jrl-${id}`).value || '').trim();
    const msg = document.getElementById(`jrm-${id}`);
    if (lesson.length < 3) { msg.textContent = 'Escribe la lección.'; msg.style.color = 'var(--negative)'; return; }
    try {
        const r = await fetch(`${JOURNAL_API}/journal/${id}/review`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ outcome, lesson }) });
        if (!r.ok) throw new Error('error');
        await loadJournal();
    } catch (e) { msg.textContent = 'No se pudo guardar.'; msg.style.color = 'var(--negative)'; }
}

async function deleteJournal(id) {
    if (!confirm('¿Eliminar esta entrada del diario? No se puede deshacer.')) return;
    try { await fetch(`${JOURNAL_API}/journal/${id}`, { method: 'DELETE' }); await loadJournal(); } catch (e) { /* noop */ }
}

document.addEventListener('DOMContentLoaded', () => {
    const link = document.querySelector('[data-page="journal"]');
    if (link) link.addEventListener('click', () => setTimeout(loadJournal, 150));
    setTimeout(() => {
        const p = document.getElementById('page-journal');
        if (p && p.classList.contains('active')) loadJournal();
    }, 500);
});
