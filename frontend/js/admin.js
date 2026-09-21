/**
 * Admin panel — owner-only. Manage the access allowlist (which Google emails may
 * log in), the "open signup" switch, and view registered users. The backend
 * gates every /api/admin/* route to the owner (403 otherwise); the nav item is
 * only shown when /auth/me reports is_admin.
 */
const ADMIN_API = window.API_BASE_URL || '/api';

async function _adminFetch(path, opts) {
    const resp = await fetch(`${ADMIN_API}${path}`, { credentials: 'same-origin', ...(opts || {}) });
    let data = null;
    try { data = await resp.json(); } catch (e) { /* no body */ }
    if (!resp.ok) {
        const msg = (data && data.detail) || (resp.status === 403
            ? 'Solo el administrador puede hacer esto.' : `Error (HTTP ${resp.status})`);
        const err = new Error(msg); err.status = resp.status; throw err;
    }
    return data;
}

function _adminMsg(id, text, ok) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = text || '';
    el.className = 'admin-msg' + (text ? (ok ? ' ok' : ' err') : '');
    if (text) setTimeout(() => { if (el.textContent === text) { el.textContent = ''; el.className = 'admin-msg'; } }, 6000);
}

async function loadAdmin() {
    await Promise.all([loadAllowlist(), loadAdminUsers()]);
}

async function loadAllowlist() {
    try {
        const data = await _adminFetch('/admin/allowlist');
        renderAllowlist(data);
    } catch (err) {
        const ul = document.getElementById('adminAllowlist');
        if (ul) ul.innerHTML = `<li style="color:var(--negative);">No se pudo cargar: ${err.message}</li>`;
    }
}

function renderAllowlist(data) {
    const emails = data.emails || [];
    const me = ((window.currentUser && window.currentUser.email) || '').toLowerCase();
    const ul = document.getElementById('adminAllowlist');
    if (ul) {
        ul.innerHTML = emails.length ? emails.map(e => {
            const isMe = e.toLowerCase() === me;
            const esc = e.replace(/"/g, '&quot;');
            return `<li>
                <span>📧 ${e}${isMe ? '<span class="you">tú</span>' : ''}</span>
                <button class="admin-del" title="${isMe ? 'No puedes quitarte a ti mismo' : 'Quitar acceso'}"
                    ${isMe ? 'disabled' : `onclick="adminRemoveEmail('${esc}')"`}>🗑️</button>
            </li>`;
        }).join('') : '<li class="text-muted">La lista está vacía.</li>';
    }
    const toggle = document.getElementById('adminSignupToggle');
    const state = document.getElementById('adminSignupState');
    if (toggle) toggle.checked = !!data.public_signup;
    if (state) state.innerHTML = data.public_signup
        ? '<strong style="color:var(--negative);">Registro abierto ACTIVADO</strong> — cualquier cuenta de Google puede entrar.'
        : 'Registro abierto desactivado — solo la lista de arriba puede entrar (recomendado).';
}

async function adminAddEmail() {
    const input = document.getElementById('adminNewEmail');
    const email = (input.value || '').trim();
    if (!email) { _adminMsg('adminAllowlistMsg', 'Escribe un email.', false); return; }
    try {
        const data = await _adminFetch('/admin/allowlist', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email }),
        });
        input.value = '';
        renderAllowlist({ ...data, public_signup: document.getElementById('adminSignupToggle').checked });
        _adminMsg('adminAllowlistMsg', `✅ Acceso concedido a ${email}`, true);
    } catch (err) {
        _adminMsg('adminAllowlistMsg', err.message, false);
    }
}

async function adminRemoveEmail(email) {
    if (!confirm(`¿Quitar el acceso a ${email}? No podrá volver a iniciar sesión (su sesión actual, si la tiene abierta, sigue hasta que cierre).`)) return;
    try {
        const data = await _adminFetch(`/admin/allowlist/${encodeURIComponent(email)}`, { method: 'DELETE' });
        renderAllowlist({ ...data, public_signup: document.getElementById('adminSignupToggle').checked });
        _adminMsg('adminAllowlistMsg', `Acceso retirado a ${email}.`, true);
    } catch (err) {
        _adminMsg('adminAllowlistMsg', err.message, false);
    }
}

async function adminToggleSignup(el) {
    const enabling = el.checked;
    if (enabling && !confirm('⚠️ ATENCIÓN: vas a permitir que CUALQUIER cuenta de Google entre en FinTrack, ignorando la lista de acceso.\n\n¿Seguro que quieres abrir el registro a todo el mundo?')) {
        el.checked = false; return;
    }
    try {
        const data = await _adminFetch('/admin/signup', {
            method: 'PUT', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: enabling }),
        });
        el.checked = !!data.public_signup;
        // Re-fetch so the whole card (state text + list) stays authoritative.
        await loadAllowlist();
        _adminMsg('adminSignupMsg', data.public_signup ? 'Registro abierto ACTIVADO.' : 'Registro abierto desactivado.', !data.public_signup);
    } catch (err) {
        el.checked = !enabling;
        _adminMsg('adminSignupMsg', err.message, false);
    }
}

async function loadAdminUsers() {
    const tbody = document.getElementById('adminUsersBody');
    if (!tbody) return;
    try {
        const data = await _adminFetch('/admin/users');
        const users = data.users || [];
        const d = (s) => (s || '').slice(0, 10);
        tbody.innerHTML = users.length ? users.map(u => `
            <tr>
                <td>${u.email}</td>
                <td>${u.name || '—'}</td>
                <td>${d(u.created_at)}</td>
                <td>${d(u.last_login_at)}</td>
                <td>${u.is_admin ? '⭐ Sí' : '—'}</td>
            </tr>`).join('') : '<tr><td colspan="5" class="text-center text-muted" style="padding:16px;">Aún no hay usuarios registrados.</td></tr>';
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="5" class="text-center" style="padding:16px; color:var(--negative);">No se pudo cargar: ${err.message}</td></tr>`;
    }
}

// Reveal the admin nav only for the admin, and load data when the tab opens.
function initAdminNav() {
    if (window.currentUser && window.currentUser.is_admin) {
        const nav = document.getElementById('navAdmin');
        if (nav) nav.style.display = '';
    }
    const link = document.querySelector('[data-page="admin"]');
    if (link) link.addEventListener('click', () => setTimeout(loadAdmin, 100));
}
window.initAdminNav = initAdminNav;

document.addEventListener('DOMContentLoaded', () => {
    // currentUser may not be set yet (auth is async); retry briefly.
    let tries = 0;
    const t = setInterval(() => {
        tries += 1;
        if (window.currentUser || tries > 20) { clearInterval(t); initAdminNav(); }
    }, 200);
});
