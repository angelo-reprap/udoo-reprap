/* ============================================================
   ABpE CRM — mod-crm.js
   Gemeinsame Basis: Search, List, Stats, Query-Help, Pagination
   ============================================================ */

const CRM = {
    currentTab:   window.CRM_TAB || 'berater',
    currentPage:  1,
    currentCrmId: null,
    queryHelpOpen: false,

    // ── API Endpoints ─────────────────────────────────────
    endpoints: {
        berater:   '/crm/api/berater/',
        kunden:    '/crm/api/kunden/',
        emails:    '/crm/api/emails/',
        dokumente: '/crm/api/dokumente/',
        sync:      '/crm/api/sync/status/',
    },

    // ── Init ──────────────────────────────────────────────
    favIds: new Set(),

    init() {
        if (window.CRM_SKIP_SEARCH) return;
        this.bindSearch();
        this.bindQueryHelp();
        this.loadStats();
        this.loadFavIds();
        this.search();
    },

    // ── Favoriten ─────────────────────────────────────────
    loadFavIds() {
        const typ = this.currentTab === 'kunden' ? 'kunden' : 'berater';
        fetch('/crm/api/favoriten/?type=' + typ, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(r => r.json())
            .then(data => { this.favIds = new Set((data.ids || []).map(String)); })
            .catch(() => {});
    },

    isFav(crmId) {
        return this.favIds.has(String(crmId));
    },

    toggleFav(crmId, iconEl) {
        const typ = this.currentTab === 'kunden' ? 'kunden' : 'berater';
        const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';
        fetch('/crm/api/favoriten/toggle/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest' },
            body: JSON.stringify({ type: typ, crm_id: crmId }),
        })
            .then(r => r.json())
            .then(data => {
                if (data.favorited) this.favIds.add(String(crmId));
                else this.favIds.delete(String(crmId));
                if (iconEl) {
                    iconEl.classList.toggle('bi-star', !data.favorited);
                    iconEl.classList.toggle('bi-star-fill', !!data.favorited);
                    iconEl.classList.toggle('crm-fav-active', !!data.favorited);
                }
                if (this._viewMode === 'favoriten') this.showFavoriten();
            })
            .catch(() => {});
    },

    // ── Zuletzt / Favoriten (Ansicht-Umschalter, ersetzt renderList) ──
    _viewMode: 'liste',

    setViewMode(mode) {
        this._viewMode = mode;
        const btnL = document.getElementById('btn-liste');
        const btnZ = document.getElementById('btn-zuletzt');
        const btnF = document.getElementById('btn-favoriten');
        const pagination = document.getElementById('crm-pagination');
        [btnL, btnZ, btnF].forEach(b => b && b.classList.remove('active'));
        if (mode === 'liste') {
            if (btnL) btnL.classList.add('active');
            if (pagination) pagination.style.display = '';
            this.search();
        } else if (mode === 'zuletzt') {
            if (btnZ) btnZ.classList.add('active');
            if (pagination) pagination.style.display = 'none';
            this.showZuletzt();
        } else if (mode === 'favoriten') {
            if (btnF) btnF.classList.add('active');
            if (pagination) pagination.style.display = 'none';
            this.showFavoriten();
        }
    },

    _recentKey() {
        return 'crm_' + this.currentTab + '_recent';
    },

    saveRecent(crmId, label) {
        const key = this._recentKey();
        let list = JSON.parse(localStorage.getItem(key) || '[]');
        list = list.filter(x => x.crm_id !== crmId);
        list.unshift({ crm_id: crmId, label: label, ts: Date.now() });
        if (list.length > 50) list = list.slice(0, 50);
        localStorage.setItem(key, JSON.stringify(list));
    },

    _timeAgo(ts) {
        const diff = Math.floor((Date.now() - ts) / 1000);
        if (diff < 60) return 'gerade eben';
        if (diff < 3600) return 'vor ' + Math.floor(diff / 60) + ' Min.';
        if (diff < 86400) return 'vor ' + Math.floor(diff / 3600) + ' Std.';
        return 'vor ' + Math.floor(diff / 86400) + ' Tagen';
    },

    showZuletzt() {
        const list = document.getElementById('crm-list');
        if (!list) return;
        const n = parseInt((document.getElementById('zuletzt-n') || { value: 20 }).value || 20);
        const recent = JSON.parse(localStorage.getItem(this._recentKey()) || '[]').slice(0, n);
        if (!recent.length) {
            list.innerHTML = '<div class="crm-list-loading"><i class="bi bi-clock-history"></i> Noch keine Eintraege</div>';
            return;
        }
        list.innerHTML = recent.map(r => {
            const initials = (r.label || '').split(' ').map(w => w[0] || '').slice(0, 2).join('').toUpperCase();
            return '<div class="crm-list-item" data-crm-id="' + r.crm_id + '">' +
                '<div class="crm-avatar">' + initials + '</div>' +
                '<div class="crm-item-info">' +
                '<div class="crm-item-name">' + r.label + '</div>' +
                '<div class="crm-item-sub"><i class="bi bi-clock"></i> ' + this._timeAgo(r.ts) + '</div>' +
                '</div></div>';
        }).join('');
        this._bindListClicks();
    },

    showFavoriten() {
        const list = document.getElementById('crm-list');
        if (!list) return;
        const typ = this.currentTab === 'kunden' ? 'kunden' : 'berater';
        list.innerHTML = '<div class="crm-list-loading"><i class="bi bi-arrow-repeat"></i> Lade...</div>';
        fetch('/crm/api/favoriten/?type=' + typ, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(r => r.json())
            .then(data => {
                this.favIds = new Set((data.ids || []).map(String));
                const results = data.results || [];
                if (!results.length) {
                    list.innerHTML = '<div class="crm-list-loading"><i class="bi bi-star"></i> Keine Favoriten markiert</div>';
                    return;
                }
                list.innerHTML = results.map(r => this.renderListItem(r)).join('');
                this._bindListClicks();
            })
            .catch(() => { list.innerHTML = '<div class="crm-list-loading">Fehler beim Laden</div>'; });
    },

    // ── Search ────────────────────────────────────────────
    bindSearch() {
        const btn = document.getElementById('crm-search-btn');
        const inp = document.getElementById('crm-global-search');
        if (btn) btn.addEventListener('click', () => this.search());
        if (inp) {
            inp.addEventListener('keydown', e => {
                if (e.key === 'Enter') this.search();
            });
        }
        const sort = document.getElementById('crm-sort');
        if (sort) sort.addEventListener('change', () => this.search());
    },

    search(page = 1) {
        this.currentPage = page;
        const q       = document.getElementById('crm-global-search')?.value || '';
        const sort    = document.getElementById('crm-sort')?.value || '';
        const perPage = document.getElementById('crm-per-page')?.value || 20;
        const status  = document.getElementById('filter-status')?.value || '';
        const typ     = document.getElementById('filter-typ')?.value || '';
        const module  = document.getElementById('filter-module')?.value || '';
        const docType = document.getElementById('filter-doc-type')?.value || '';

        const params = new URLSearchParams({ q, sort, page, per_page: perPage });
        if (status)  params.set('status', status);
        if (typ)     params.set('typ', typ);
        if (module)  params.set('module', module);
        if (docType) params.set('doc_type', docType);

        const url = this.endpoints[this.currentTab] + '?' + params;
        this.showLoading();

        fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(r => r.json())
            .then(data => {
                this.renderList(data.results || []);
                this.renderPagination(data.total, data.pages, data.page);
            })
            .catch(err => {
                console.error('CRM Search Error:', err);
                this.showError();
            });
    },

    // ── Render List ───────────────────────────────────────
    renderList(results) {
        const list = document.getElementById('crm-list');
        if (!list) return;

        if (!results.length) {
            list.innerHTML = '<div class="crm-list-loading">Keine Treffer</div>';
            return;
        }

        list.innerHTML = results.map(r => this.renderListItem(r)).join('');
        this._bindListClicks();
    },

    _bindListClicks() {
        const list = document.getElementById('crm-list');
        if (!list) return;
        list.querySelectorAll('.crm-list-item').forEach(el => {
            el.addEventListener('click', () => {
                list.querySelectorAll('.crm-list-item').forEach(i => i.classList.remove('active'));
                el.classList.add('active');
                this.loadDetail(el.dataset.crmId);
                this.saveRecent(el.dataset.crmId, el.querySelector('.crm-item-name')?.textContent || '');
            });
        });
    },

    renderListItem(r) {
        const tab = this.currentTab;
        if (tab === 'berater') return this.renderBeraterItem(r);
        if (tab === 'kunden')  return this.renderKundenItem(r);
        if (tab === 'emails')  return this.renderEmailItem(r);
        if (tab === 'dokumente') return this.renderDokumentItem(r);
        return '';
    },

    renderBeraterItem(r) {
        const initials = ((r.first_name||'')[0]||'') + ((r.last_name||'')[0]||'');
        const status   = r.status || 'unbekannt';
        const badgeCls = status === 'aktiv' ? 'crm-badge-aktiv' : status === 'passiv' ? 'crm-badge-passiv' : 'crm-badge-warning';
        const fav      = this.isFav(r.crm_id);
        return `
        <div class="crm-list-item" data-crm-id="${r.crm_id}">
            <div class="crm-avatar">${initials.toUpperCase()}</div>
            <div class="crm-item-info">
                <div class="crm-item-name">${r.full_name || ''}</div>
                <div class="crm-item-sub">${r.city || ''} ${r.konditionen ? '· ' + r.konditionen : ''} ${r.gulp_id ? '· Gulp ' + r.gulp_id : ''}</div>
            </div>
            <div class="crm-item-right">
                <span class="crm-badge ${badgeCls}">${status}</span>
                <span style="font-size:10px;color:var(--text-muted)">${r.verfuegbar ? 'ab ' + r.verfuegbar : ''}</span>
            </div>
            <i class="bi ${fav ? 'bi-star-fill' : 'bi-star'} crm-fav-star${fav ? ' crm-fav-active' : ''}" data-crm-id="${r.crm_id}" onclick="event.stopPropagation(); CRM.toggleFav('${r.crm_id}', this);" title="Favorit"></i>
        </div>`;
    },

    renderKundenItem(r) {
        const initials = (r.name||'').substring(0,2).toUpperCase();
        const status   = r.status || 'unbekannt';
        const badgeCls = status === 'aktiv' ? 'crm-badge-aktiv' : 'crm-badge-passiv';
        const fav      = this.isFav(r.crm_id);
        return `
        <div class="crm-list-item" data-crm-id="${r.crm_id}">
            <div class="crm-avatar crm-avatar-sq">${initials}</div>
            <div class="crm-item-info">
                <div class="crm-item-name">${r.name || ''}</div>
                <div class="crm-item-sub">${r.city || ''} ${r.kunden_nr ? '· Kd-Nr. ' + r.kunden_nr : ''}</div>
            </div>
            <div class="crm-item-right">
                <span class="crm-badge ${badgeCls}">${status}</span>
            </div>
            <i class="bi ${fav ? 'bi-star-fill' : 'bi-star'} crm-fav-star${fav ? ' crm-fav-active' : ''}" data-crm-id="${r.crm_id}" onclick="event.stopPropagation(); CRM.toggleFav('${r.crm_id}', this);" title="Favorit"></i>
        </div>`;
    },

    renderEmailItem(r) {
        const invalid = r.invalid_email ? 'crm-badge-error' : 'crm-badge-aktiv';
        const label   = r.invalid_email ? (window.i18nData['ungueltig']||'Ungültig') : (window.i18nData['gueltig']||'Gültig');
        return `
        <div class="crm-list-item" data-crm-id="${r.contact ? r.contact.crm_id : r.crm_id}">
            <div class="crm-avatar" style="font-size:10px">@</div>
            <div class="crm-item-info">
                <div class="crm-item-name">${r.email_address || ''}</div>
                <div class="crm-item-sub">${r.contact ? r.contact.full_name : ''}</div>
            </div>
            <div class="crm-item-right">
                <span class="crm-badge ${invalid}">${label}</span>
            </div>
        </div>`;
    },

    renderDokumentItem(r) {
        const icons = {cv:'bi-file-person', contract:'bi-file-earmark-text',
                       invoice:'bi-file-earmark-invoice', email:'bi-envelope', other:'bi-file'};
        const icon = icons[r.doc_type] || 'bi-file';
        return `
        <div class="crm-list-item" data-crm-id="${r.id}">
            <div class="crm-avatar" style="background:var(--abcona-blue-tint);color:var(--abcona-blue)">
                <i class="bi ${icon}"></i>
            </div>
            <div class="crm-item-info">
                <div class="crm-item-name">${r.title || ''}</div>
                <div class="crm-item-sub">${r.contact || r.account || ''} · ${r.doc_type || ''}</div>
            </div>
            <div class="crm-item-right">
                <span style="font-size:10px;color:var(--text-muted)">${r.created_at ? r.created_at.substring(0,10) : ''}</span>
            </div>
        </div>`;
    },

    // ── Load Detail ───────────────────────────────────────
    loadDetail(crmId) {
        this.currentCrmId = crmId;
        const tab = this.currentTab;
        const url = tab === 'berater'
            ? `/crm/api/berater/${crmId}/`
            : tab === 'emails'
            ? `/crm/api/berater/${crmId}/`
            : `/crm/api/kunden/${crmId}/`;

        fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(r => r.json())
            .then(data => {
                if (tab === 'berater' && typeof CRM_Berater !== 'undefined') {
                    CRM_Berater.renderDetail(data);
                } else if (tab === 'kunden' && typeof CRM_Kunden !== 'undefined') {
                    CRM_Kunden.renderDetail(data);
                }
            })
            .catch(err => console.error('Detail Error:', err));
    },

    // ── Stats ─────────────────────────────────────────────
    loadStats() {
        fetch('/crm/api/sync/status/', { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(r => r.json())
            .then(data => {
                const tab = this.currentTab;
                const map = {
                    berater:   [data.contacts_total,  'Gesamt',   '', ''],
                    kunden:    [data.accounts_total,  'Accounts', '', ''],
                    emails:    [data.emails_total,    'Gesamt',   '', ''],
                    dokumente: [data.documents_total, 'Dokumente','', ''],
                };
                const vals = map[tab] || [];
                const statVal = document.querySelector('#stat-total .crm-stat-val');
                if (statVal && vals[0]) statVal.textContent = vals[0].toLocaleString();
            })
            .catch(() => {});
    },

    // ── Pagination ────────────────────────────────────────
    renderPagination(total, pages, current) {
        const el = document.getElementById('crm-pagination');
        if (!el || pages <= 1) { if (el) el.innerHTML = ''; return; }

        let html = '';
        if (current > 1)
            html += `<button class="crm-page-btn" onclick="CRM.search(${current-1})">‹</button>`;

        const start = Math.max(1, current - 2);
        const end   = Math.min(pages, current + 2);
        for (let i = start; i <= end; i++) {
            html += `<button class="crm-page-btn ${i===current?'active':''}" onclick="CRM.search(${i})">${i}</button>`;
        }

        if (current < pages)
            html += `<button class="crm-page-btn" onclick="CRM.search(${current+1})">›</button>`;

        html += `<span style="font-size:11px;color:var(--text-muted);margin-left:8px">${total} Einträge</span>`;
        el.innerHTML = html;
    },

    // ── Query Help ────────────────────────────────────────
    bindQueryHelp() {
        const btn = document.getElementById('crm-help-btn');
        if (btn) btn.addEventListener('click', () => this.toggleQueryHelp());
    },

    toggleQueryHelp() {
        const el = document.getElementById('crm-query-help');
        if (!el) return;
        this.queryHelpOpen = !this.queryHelpOpen;
        el.style.display = this.queryHelpOpen ? 'flex' : 'none';
        const main = document.querySelector('.main-content');
        if (main) main.style.paddingTop = this.queryHelpOpen ? '120px' : '';
    },

    // ── Loading / Error ───────────────────────────────────
    showLoading() {
        const list = document.getElementById('crm-list');
        if (list) list.innerHTML = `
            <div class="crm-list-loading">
                <i class="bi bi-arrow-repeat matching-spinner"></i> ${(window.i18nData['laden']||'Lade...')}
            </div>`;
    },

    showError() {
        const list = document.getElementById('crm-list');
        if (list) list.innerHTML = `
            <div class="crm-list-loading">
                <i class="bi bi-exclamation-triangle"></i> ${(window.i18nData['fehler_beim_laden']||'Fehler beim Laden')}
            </div>`;
    },

    // ── CSRF ──────────────────────────────────────────────
    getCsrf() {
        return document.cookie.split(';')
            .find(c => c.trim().startsWith('csrftoken='))
            ?.split('=')[1] || '';
    },
};

// Global verfügbar
window.CRM = CRM;
window.crmSearch = () => CRM.search();
window.toggleCrmQueryHelp = () => CRM.toggleQueryHelp();

document.addEventListener('DOMContentLoaded', () => CRM.init());
