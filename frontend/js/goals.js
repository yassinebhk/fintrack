/**
 * 🎯 Objetivos Financieros — real savings goals (target amount/date, manually
 * tracked progress). Previously this page was a static mockup: two hardcoded
 * example cards and an "+ Nuevo Objetivo" button with no event listener at
 * all. Now backed by a real /api/goals CRUD.
 */
const GOALS_API = window.API_BASE_URL || '/api';
let _goalsAll = [];

async function loadGoals() {
    const el = document.getElementById('goalsContainer');
    if (!el) return;
    el.innerHTML = '<p class="text-muted">Cargando objetivos…</p>';
    try {
        const r = await fetch(`${GOALS_API}/goals`, { cache: 'no-store' });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = await r.json();
        _goalsAll = data.goals || [];
        renderGoals();
    } catch (err) {
        el.innerHTML = `<p class="text-muted" style="color:var(--negative);">No se pudieron cargar los objetivos: ${err.message}</p>`;
    }
}

function renderGoals() {
    const el = document.getElementById('goalsContainer');
    if (!el) return;
    const fmt = (v) => (v || 0).toLocaleString('es-ES', { maximumFractionDigits: 0 }) + ' €';
    const cards = _goalsAll.map(g => {
        const pct = g.progress_pct || 0;
        let monthlyNote = '';
        if (g.target_date && g.remaining_eur > 0) {
            const months = Math.max(1, Math.round((new Date(g.target_date) - new Date()) / (1000 * 60 * 60 * 24 * 30.44)));
            if (months > 0) {
                const perMonth = g.remaining_eur / months;
                monthlyNote = `<span>💰 ${fmt(perMonth)}/mes necesarios</span>`;
            }
        }
        const dateLabel = g.target_date
            ? new Date(g.target_date).toLocaleDateString('es-ES', { month: 'short', year: 'numeric' })
            : null;
        return `<div class="goal-card" onclick="openGoalModal(${g.id})" style="cursor:pointer;">
            <div class="goal-icon">${g.icon || '🎯'}</div>
            <h4>${g.name}</h4>
            <div class="goal-progress">
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${pct}%"></div>
                </div>
                <div class="progress-info">
                    <span>${fmt(g.current_amount)} / ${fmt(g.target_amount)}</span>
                    <span>${pct}%</span>
                </div>
            </div>
            <div class="goal-details">
                ${dateLabel ? `<span>📅 Meta: ${dateLabel}</span>` : '<span class="text-muted">Sin fecha objetivo</span>'}
                ${monthlyNote}
            </div>
        </div>`;
    }).join('');
    el.innerHTML = cards + `<div class="goal-card goal-add" onclick="openGoalModal()">
        <span class="add-icon">+</span>
        <span>Añadir objetivo</span>
    </div>`;
}

function openGoalModal(goalId) {
    const modal = document.getElementById('goalModal');
    const title = document.getElementById('goalModalTitle');
    const deleteBtn = document.getElementById('goalDeleteBtn');
    const msg = document.getElementById('goalMsg');
    msg.textContent = '';
    const g = goalId ? _goalsAll.find(x => x.id === goalId) : null;
    document.getElementById('goalId').value = g ? g.id : '';
    document.getElementById('goalName').value = g ? g.name : '';
    document.getElementById('goalIcon').value = g ? g.icon : '';
    document.getElementById('goalTarget').value = g ? g.target_amount : '';
    document.getElementById('goalCurrent').value = g ? g.current_amount : 0;
    document.getElementById('goalDate').value = g ? (g.target_date || '') : '';
    title.textContent = g ? 'Editar objetivo' : 'Nuevo objetivo';
    deleteBtn.style.display = g ? 'inline-block' : 'none';
    modal.classList.add('active');
}

function closeGoalModal() {
    document.getElementById('goalModal').classList.remove('active');
}

async function submitGoalForm(e) {
    e.preventDefault();
    const btn = document.getElementById('goalSubmitBtn');
    const msg = document.getElementById('goalMsg');
    const id = document.getElementById('goalId').value;
    const payload = {
        name: document.getElementById('goalName').value.trim(),
        icon: document.getElementById('goalIcon').value.trim() || '🎯',
        target_amount: parseFloat(document.getElementById('goalTarget').value),
        current_amount: parseFloat(document.getElementById('goalCurrent').value) || 0,
        target_date: document.getElementById('goalDate').value || null,
    };
    if (!payload.name || !payload.target_amount || payload.target_amount <= 0) {
        msg.textContent = 'Nombre e importe objetivo son obligatorios.';
        msg.style.color = 'var(--negative)';
        return;
    }
    btn.disabled = true;
    msg.textContent = 'Guardando…';
    msg.style.color = 'var(--text-secondary)';
    try {
        const url = id ? `${GOALS_API}/goals/${id}` : `${GOALS_API}/goals`;
        const method = id ? 'PUT' : 'POST';
        const r = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `HTTP ${r.status}`);
        closeGoalModal();
        await loadGoals();
    } catch (err) {
        msg.textContent = 'No se pudo guardar: ' + err.message;
        msg.style.color = 'var(--negative)';
    } finally {
        btn.disabled = false;
    }
}

async function deleteGoal() {
    const id = document.getElementById('goalId').value;
    if (!id) return;
    if (!confirm('¿Eliminar este objetivo?')) return;
    try {
        const r = await fetch(`${GOALS_API}/goals/${id}`, { method: 'DELETE' });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        closeGoalModal();
        await loadGoals();
    } catch (err) {
        alert('No se pudo eliminar: ' + err.message);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const nav = document.querySelector('[data-page="goals"]');
    if (nav) nav.addEventListener('click', () => { if (!_goalsAll.length) loadGoals(); });

    const btnAdd = document.getElementById('btnAddGoal');
    if (btnAdd) btnAdd.addEventListener('click', () => openGoalModal());

    const closeBtn = document.getElementById('closeGoalModal');
    if (closeBtn) closeBtn.addEventListener('click', closeGoalModal);

    const modal = document.getElementById('goalModal');
    if (modal) modal.addEventListener('click', (e) => { if (e.target === modal) closeGoalModal(); });

    const form = document.getElementById('goalForm');
    if (form) form.addEventListener('submit', submitGoalForm);

    const delBtn = document.getElementById('goalDeleteBtn');
    if (delBtn) delBtn.addEventListener('click', deleteGoal);
});
