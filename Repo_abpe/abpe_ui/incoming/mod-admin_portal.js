// mod-admin_portal.js - Portal Admin Modul JS
// Nur einmal laden — IIFE verhindert doppelte Deklaration
if (typeof window._adminPortalLoaded === 'undefined') {
    window._adminPortalLoaded = true;


let adminLang = 'de';
let adminI18n = {};

async function initAdminPortal(lang) {
    adminLang = lang || document.documentElement.lang || 'de';
    try {
        const r = await fetch(`/static/abpe_ui/i18n/${adminLang}/modules/admin_portal.json`);
        const d = await r.json();
        adminI18n = d.admin_portal || {};
        applyAdminI18n();
    } catch(e) {
        console.warn('Admin i18n nicht geladen:', e);
    }
}

function applyAdminI18n() {
    // Alle data-i18n-admin Elemente übersetzen
    document.querySelectorAll('[data-i18n-admin]').forEach(el => {
        const key = el.getAttribute('data-i18n-admin');
        const val = getNestedKey(adminI18n, key);
        if (val) el.textContent = val;
    });
    // Placeholder
    document.querySelectorAll('[data-i18n-admin-placeholder]').forEach(el => {
        const key = el.getAttribute('data-i18n-admin-placeholder');
        const val = getNestedKey(adminI18n, key);
        if (val) el.placeholder = val;
    });
}

function getNestedKey(obj, path) {
    return path.split('.').reduce((o, k) => (o && o[k] !== undefined ? o[k] : null), obj);
}

function getCsrf() {
    return document.cookie.split(';').map(c => c.trim())
        .find(c => c.startsWith('csrftoken='))?.split('=')[1] || '';
}

// ============================================================
// USERS
// ============================================================
function loadUsers() {
    const group  = document.getElementById('filter-group')?.value  || '';
    const status = document.getElementById('filter-status')?.value || '';
    const search = document.getElementById('search-users')?.value  || '';
    const tbody  = document.getElementById('users-tbody');
    if (!tbody) return;

    tbody.innerHTML = `<tr><td colspan="6" class="text-center py-4">
        <div class="spinner-border spinner-border-sm"></div>
    </td></tr>`;

    fetch(`/api/admin-portal/users/?group=${group}&status=${status}&search=${search}`)
        .then(r => r.json())
        .then(d => renderUsers(d.users || []))
        .catch(() => renderUsers([]));
}

function renderUsers(users) {
    const tbody = document.getElementById('users-tbody');
    if (!users.length) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center py-4 text-muted">
            ${getNestedKey(adminI18n, 'users.no_users') || 'Keine Benutzer'}
        </td></tr>`;
        return;
    }
    tbody.innerHTML = users.map(u => `
        <tr>
            <td><strong>${u.username}</strong><br>
                <small class="text-muted">${u.first_name} ${u.last_name}</small></td>
            <td>${u.email}</td>
            <td>${u.groups.map(g =>
                `<span class="badge bg-secondary">${g}</span>`).join(' ')}</td>
            <td><span class="badge ${u.is_active ? 'bg-success' : 'bg-danger'}">
                ${u.is_active
                    ? (getNestedKey(adminI18n,'users.status_active')||'Aktiv')
                    : (getNestedKey(adminI18n,'users.status_inactive')||'Inaktiv')}
            </span></td>
            <td><small>${u.last_login || '–'}</small></td>
            <td>
                <button class="btn btn-sm btn-outline-primary" onclick="editUser(${u.id})"
                    title="Benutzer bearbeiten">
                    <i class="bi bi-pencil"></i></button>
                <button class="btn btn-sm btn-outline-${u.is_active ? 'warning':'success'}"
                    onclick="toggleUser(${u.id})"
                    title="${u.is_active ? 'Benutzer sperren' : 'Benutzer aktivieren'}">
                    <i class="bi bi-${u.is_active ? 'pause-circle':'play-circle'}"></i>
                    <small>${u.is_active ? 'Sperren' : 'Aktivieren'}</small>
                </button>
            </td>
        </tr>`).join('');
}

function showCreateUser() {
    document.getElementById('userModalTitle').textContent =
        getNestedKey(adminI18n, 'users.modal_create') || 'Neuer Benutzer';
    ['user-id','user-username','user-firstname','user-lastname',
     'user-email','user-password'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    document.getElementById('user-group').value    = '';
    document.getElementById('user-active').checked = true;
    // Modul-Section bei Neuanlage ausblenden
    const section = document.getElementById('module-permissions-section');
    if (section) section.style.display = 'none';
    new bootstrap.Modal(document.getElementById('userModal')).show();
}

function editUser(id) {
    // User-Daten + Modul-Berechtigungen parallel laden
    Promise.all([
        fetch(`/api/admin-portal/users/${id}/`).then(r => r.json()),
        fetch(`/api/admin-portal/users/${id}/module-permissions/`).then(r => r.json())
    ]).then(([u, perms]) => {
        document.getElementById('userModalTitle').textContent =
            getNestedKey(adminI18n, 'users.modal_edit') || 'Benutzer bearbeiten';
        document.getElementById('user-id').value        = u.id;
        document.getElementById('user-username').value  = u.username;
        document.getElementById('user-firstname').value = u.first_name;
        document.getElementById('user-lastname').value  = u.last_name;
        document.getElementById('user-email').value     = u.email;
        document.getElementById('user-group').value     = u.groups[0] || '';
        document.getElementById('user-active').checked  = u.is_active;
        document.getElementById('user-password').value  = '';

        // Modul-Checkboxen rendern
        renderModuleCheckboxes(perms.all_modules || [], perms.denied_modules || []);

        new bootstrap.Modal(document.getElementById('userModal')).show();
    });
}

function renderModuleCheckboxes(allModules, deniedModules) {
    const section = document.getElementById('module-permissions-section');
    const container = document.getElementById('module-checkboxes');
    if (!section || !container) return;

    // Nur anzeigen wenn User bearbeitet wird (nicht bei Neu-Anlage)
    section.style.display = allModules.length ? 'block' : 'none';

    container.innerHTML = allModules.map(m => {
        const isDenied = deniedModules.includes(m.id);
        return `
        <div class="d-flex align-items-center justify-content-between py-1 px-2 rounded"
             style="background:var(--bs-light)">
            <span style="font-size:.85rem">
                <i class="bi bi-${m.icon || 'puzzle'} me-2 text-muted"></i>
                ${m.title}
                <small class="text-muted ms-1">(${m.id})</small>
            </span>
            <div class="form-check form-switch mb-0">
                <input class="form-check-input module-perm-cb"
                    type="checkbox"
                    data-module-id="${m.id}"
                    ${isDenied ? '' : 'checked'}
                    title="${isDenied ? 'Gesperrt' : 'Erlaubt'}">
            </div>
        </div>`;
    }).join('');
}

function saveUser() {
    const id   = document.getElementById('user-id').value;
    const data = {
        username:   document.getElementById('user-username').value,
        first_name: document.getElementById('user-firstname').value,
        last_name:  document.getElementById('user-lastname').value,
        email:      document.getElementById('user-email').value,
        group:      document.getElementById('user-group').value,
        password:   document.getElementById('user-password').value,
        is_active:  document.getElementById('user-active').checked,
    };
    const url    = id ? `/api/admin-portal/users/${id}/` : '/api/admin-portal/users/';
    const method = id ? 'PUT' : 'POST';

    fetch(url, {
        method,
        headers: {'Content-Type':'application/json','X-CSRFToken': getCsrf()},
        body: JSON.stringify(data)
    })
    .then(r => r.json())
    .then(d => {
        if (!d.success) {
            alert('Fehler: ' + (d.error || 'Unbekannt'));
            return;
        }
        // Modul-Berechtigungen speichern (nur bei bestehendem User)
        if (id) {
            const checkboxes = document.querySelectorAll('.module-perm-cb');
            const deniedModules = [];
            checkboxes.forEach(cb => {
                if (!cb.checked) deniedModules.push(cb.getAttribute('data-module-id'));
            });
            fetch(`/api/admin-portal/users/${id}/module-permissions/`, {
                method: 'POST',
                headers: {'Content-Type':'application/json','X-CSRFToken': getCsrf()},
                body: JSON.stringify({ denied_modules: deniedModules })
            }).then(() => {
                bootstrap.Modal.getInstance(document.getElementById('userModal')).hide();
                loadUsers();
            });
        } else {
            bootstrap.Modal.getInstance(document.getElementById('userModal')).hide();
            loadUsers();
        }
    });
}

function toggleUser(id) {
    fetch(`/api/admin-portal/users/${id}/toggle/`, {
        method: 'POST',
        headers: {'X-CSRFToken': getCsrf()}
    }).then(() => loadUsers());
}

// ============================================================
// GROUPS
// ============================================================
function loadGroups() {
    fetch('/api/admin-portal/groups/')
        .then(r => r.json())
        .then(d => renderGroups(d.groups || []));
}

const GROUP_META = {
    berater:   { icon: 'person',       color: 'primary' },
    disponent: { icon: 'envelope',     color: 'info'    },
    betreuer:  { icon: 'person-check', color: 'success' },
    admin:     { icon: 'shield-lock',  color: 'danger'  },
};

function renderGroups(groups) {
    const c = document.getElementById('groups-container');
    if (!c) return;
    c.innerHTML = groups.map(g => {
        const meta = GROUP_META[g.name] || { icon: 'people', color: 'secondary' };
        const desc = getNestedKey(adminI18n, `groups.${g.name}_desc`) || '';
        return `
        <div class="col-md-6" data-group-id="${g.id}">
            <div class="card border-0 shadow-sm h-100">
                <div class="card-header bg-${meta.color} text-white d-flex justify-content-between align-items-center">
                    <span><i class="bi bi-${meta.icon} me-1"></i> ${g.name}</span>
                    <span class="badge bg-white text-${meta.color}">${g.user_count} User</span>
                </div>
                <div class="card-body">
                    <p class="text-muted small mb-3">${desc}</p>
                    <strong class="small">Mitglieder</strong>
                    <div class="mt-2 mb-3">
                        ${g.users.length
                            ? g.users.map(u => `<span class="badge bg-light text-dark me-1 mb-1">${u}</span>`).join('')
                            : `<span class="text-muted small">Keine Mitglieder</span>`}
                    </div>
                </div>
                <div class="card-footer bg-transparent border-0 pt-0">
                    <button class="btn btn-outline-secondary btn-sm btn-perm w-100"
                        onclick="editGroupPermissions(${g.id}, '${g.name}')">
                        <i class="bi bi-shield-check me-1"></i>
                        Modul-Berechtigungen konfigurieren
                    </button>
                </div>
            </div>
        </div>`;
    }).join('');
}

// ============================================================
// MODULES CONFIG
// ============================================================
function loadModules() {
    fetch('/api/admin-portal/modules/')
        .then(r => r.json())
        .then(d => renderModules(d.modules || []));
}

function renderModules(modules) {
    const tbody = document.getElementById('modules-tbody');
    if (!tbody) return;
    tbody.innerHTML = modules.map(m => `
        <tr data-module-id="${m.id}">
            <td><span class="drag-handle" title="Verschieben">
                <i class="bi bi-grip-vertical"></i>
            </span></td>
            <td>
                <i class="bi bi-${m.icon} me-2"></i><strong>${m.title}</strong>
                <br><small class="text-muted">${m.id}
                (#<span class="order-display">${m.order}</span>)</small>
            </td>
            <td><code>${m.route}</code></td>
            <td>${(m.roles||[]).map(r =>
                `<span class="badge bg-secondary">${r}</span>`).join(' ')
                || `<span class="text-muted small">${getNestedKey(adminI18n,'modules.all_roles')||'alle'}</span>`}
            </td>
            <td>
                <div class="form-check form-switch">
                    <input class="form-check-input" type="checkbox" ${m.enabled ? 'checked' : ''}
                        onchange="updateModule('${m.id}', 'enabled', this.checked)">
                </div>
            </td>
        </tr>`).join('');

    if (typeof initDragDrop === 'function') initDragDrop();
}

function updateModule(id, field, value) {
    fetch(`/api/admin-portal/modules/${id}/`, {
        method: 'PATCH',
        headers: {'Content-Type':'application/json','X-CSRFToken': getCsrf()},
        body: JSON.stringify({[field]: value})
    }).then(r => r.json()).then(d => {
        if (!d.success) {
            alert('Fehler beim Speichern');
        } else if (d.reload_nav) {
            // Sidebar neu laden ohne F5
            fetch('/api/admin-portal/modules/')
                .then(r => r.json())
                .then(data => {
                    renderModules(data.modules || []);
                    // Sidebar Icons aktualisieren
                    if (typeof loadNavigation === 'function') loadNavigation();
                });
        }
    });
}

// ============================================================
// SYSTEM
// ============================================================
function loadSystemStatus() {
    fetch('/api/system/')
        .then(r => r.json())
        .then(d => {
            const c = document.getElementById('system-status-container');
            if (!c) return;
            const data = d.data || {};
            const rows = [
                ['Django',     data.django],
                ['Celery',     data.celery],
                ['PostgreSQL', data.postgresql],
                ['CPU',        data.cpu],
                ['RAM',        data.ram],
                ['GPU',        data.gpu],
            ];
            c.innerHTML = rows.map(([label, item]) => {
                const val   = item?.value  || '–';
                const color = item?.status === 'ok' || item?.status === 'online' ? 'success'
                            : item?.status === 'warning' ? 'warning' : 'danger';
                return `<div class="d-flex justify-content-between mb-2">
                    <span>${label}</span>
                    <span class="badge bg-${color}">${val}</span>
                </div>`;
            }).join('');
        })
        .catch(() => {});
}

function loadBackups() {
    fetch('/api/admin-portal/backups/')
        .then(r => r.json())
        .then(d => {
            const lb = document.getElementById('last-backup');
            if (lb) lb.textContent = d.last_backup || '–';
            const list = document.getElementById('backup-list');
            if (!list) return;
            list.innerHTML = (d.recent || []).map(b =>
                `<div class="small border-bottom py-1">
                    <code>${b.timestamp}</code> ${b.message || ''}
                    <span class="text-muted">(${b.files} Dateien)</span>
                </div>`).join('')
                || `<span class="text-muted small">${getNestedKey(adminI18n,'system.no_backups')||'Keine Backups'}</span>`;
        }).catch(() => {});
}

function loadAuditLog() {
    fetch('/api/admin-portal/audit-log/')
        .then(r => r.json())
        .then(d => {
            const el = document.getElementById('audit-log');
            if (!el) return;
            el.innerHTML = (d.entries || []).map(e =>
                `<div>${e.time} [${e.user}] ${e.action}</div>`).join('')
                || getNestedKey(adminI18n,'system.no_entries') || 'Keine Einträge';
        }).catch(() => {
            const el = document.getElementById('audit-log');
            if (el) el.textContent = getNestedKey(adminI18n,'system.not_available') || 'Nicht verfügbar';
        });
}


    // Funktionen global verfügbar machen
    window.initAdminPortal  = initAdminPortal;
    window.loadUsers        = loadUsers;
    window.renderModuleCheckboxes = renderModuleCheckboxes;
    window.showCreateUser   = showCreateUser;
    window.editUser         = editUser;
    window.saveUser         = saveUser;
    window.toggleUser       = toggleUser;
    window.loadGroups       = loadGroups;
    window.loadModules      = loadModules;
    window.updateModule     = updateModule;
    window.loadSystemStatus = loadSystemStatus;
    window.loadBackups      = loadBackups;
    window.loadAuditLog     = loadAuditLog;
    window.getNestedKey     = getNestedKey;
    window.adminI18n        = adminI18n;

    // Sprache wechseln: Admin i18n neu laden
    document.addEventListener('languageChanged', async (e) => {
        adminLang = e.detail.language;
        try {
            const r = await fetch(`/static/abpe_ui/i18n/${adminLang}/modules/admin_portal.json`);
            const d = await r.json();
            window.adminI18n = d.admin_portal || {};
            adminI18n = window.adminI18n;
            applyAdminI18n();
        } catch(err) {}
    });
}
