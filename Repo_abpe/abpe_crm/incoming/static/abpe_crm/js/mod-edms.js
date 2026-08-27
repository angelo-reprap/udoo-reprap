/* ============================================================
   ABpE EDMS — mod-edms.js  (v2: Drei-Modi-Layout)
   Modi: 'personen' | 'dokumente' | 'posteingang'
   ============================================================ */

const EDMS = {
    mode:          'personen',
    currentPage:    1,
    currentDocUuid: null,
    currentOwner:   null,
    akteFilter:    '',
    vorschauTab:   'dokument',
    _personenFilter: 'alle',
    _viewMode:     'liste',   // 'liste' | 'favoriten'
    _favTab:       'alle',    // 'alle' | 'berater' | 'kunden'
    favBeraterIds: new Set(),
    favKundenIds:  new Set(),
    _favBerater:   [],
    _favKunden:    [],

    api: {
        search:   '/edms/api/search/',
        personen: '/edms/api/personen/',
        searchAll: '/edms/api/search_all/',
        akte:     '/edms/api/akte/',
        document: '/edms/api/document/',
        preview:  '/edms/api/preview/',
        file:     '/edms/api/file/',
        edmsFile: '/crm/api/edms/file/',
        inbox:    '/edms/api/inbox/',
        doctypes: '/edms/api/doctypes/',
        personMails: '/edms/api/person/',
        mailView:    '/edms/api/mail/view/',
        mailAttach:  '/edms/api/mail/attachment/',
        mailAttachPreview: '/edms/api/mail/attachment/preview/',
    },

    ABCONA_CRM_ID: '51691c10-97fd-2e65-75ef-4b1eb782b729',

    t(key, fallback) { return (window.i18nData && window.i18nData[key]) || fallback || key; },
    csrf() { return (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || ''; },

    init() {
        this.fillScopeDropdown();
        this.bindSearch();
        this.bindModeButtons();
        this.bindResizers();
        this._initStatLabels();
        this.loadStats();
        this.loadFavIds();
        this.setMode('personen');
        this._handleDeepLink();
    },

    // ── Favoriten (gleiche Listen wie Berater / Kunde) ──
    _favHeaders() {
        return { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } };
    },
    loadFavIds() {
        return Promise.all([
            fetch('/crm/api/favoriten/?type=berater', this._favHeaders()).then(r => r.json()),
            fetch('/crm/api/favoriten/?type=kunden', this._favHeaders()).then(r => r.json()),
        ]).then(([b, k]) => {
            this.favBeraterIds = new Set((b.ids || []).map(String));
            this.favKundenIds = new Set((k.ids || []).map(String));
            this._favBerater = (b.results || []).map(r => ({
                crm_id: r.crm_id,
                name: r.full_name || [r.first_name, r.last_name].filter(Boolean).join(' '),
                owner_type: 'contact',
            }));
            this._favKunden = (k.results || []).map(r => ({
                crm_id: r.crm_id,
                name: r.name || '',
                owner_type: 'account',
            }));
        }).catch(() => {});
    },
    isFav(crmId, ownerType) {
        const id = String(crmId || '');
        return ownerType === 'account' ? this.favKundenIds.has(id) : this.favBeraterIds.has(id);
    },
    setViewMode(mode) {
        this._viewMode = (mode === 'favoriten') ? 'favoriten' : 'liste';
        const btnL = document.getElementById('edms-btn-liste');
        const btnF = document.getElementById('edms-btn-favoriten');
        if (btnL) btnL.classList.toggle('active', this._viewMode === 'liste');
        if (btnF) btnF.classList.toggle('active', this._viewMode === 'favoriten');
        const laschen = document.getElementById('edms-fav-laschen');
        if (laschen) laschen.style.display = (this.mode === 'personen' && this._viewMode === 'favoriten') ? 'flex' : 'none';
        const pf = document.getElementById('edms-personen-filter');
        if (pf && this.mode === 'personen') pf.style.display = this._viewMode === 'liste' ? 'flex' : 'none';
        this.loadCol1(1);
    },
    setFavTab(tab) {
        this._favTab = (tab === 'berater' || tab === 'kunden') ? tab : 'alle';
        document.querySelectorAll('#edms-fav-laschen [data-fav-tab]').forEach(p => {
            p.classList.toggle('active', p.dataset.favTab === this._favTab);
        });
        this._renderFavoriten();
    },
    _renderFavoriten() {
        const list = document.getElementById('edms-col1-list');
        if (!list) return;
        let people = [];
        if (this._favTab === 'berater') people = this._favBerater.slice();
        else if (this._favTab === 'kunden') people = this._favKunden.slice();
        else people = this._favBerater.concat(this._favKunden);
        const q = ((document.getElementById('crm-global-search') || {}).value || '').trim().toLowerCase();
        if (q) people = people.filter(p => (p.name || '').toLowerCase().includes(q));
        if (!people.length) {
            list.innerHTML = '<div class="crm-list-loading"><i class="bi bi-star"></i> ' +
                this.t('edms_keine_favoriten', 'Keine Favoriten markiert') + '</div>';
            this._setCount('edms-col1-count', 0);
            this._clearPagination();
            return;
        }
        this.renderPersonen(people, true);
        this._setCount('edms-col1-count', people.length);
        this._clearPagination();
    },
    toggleFav(crmId, ownerType, iconEl) {
        const typ = ownerType === 'account' ? 'kunden' : 'berater';
        fetch('/crm/api/favoriten/toggle/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrf(),
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: JSON.stringify({ type: typ, crm_id: crmId }),
        })
            .then(r => r.json())
            .then(data => {
                const id = String(crmId);
                const set = typ === 'kunden' ? this.favKundenIds : this.favBeraterIds;
                if (data.favorited) set.add(id);
                else set.delete(id);
                if (iconEl) {
                    iconEl.classList.toggle('bi-star', !data.favorited);
                    iconEl.classList.toggle('bi-star-fill', !!data.favorited);
                    iconEl.classList.toggle('crm-fav-active', !!data.favorited);
                }
                return this.loadFavIds();
            })
            .then(() => {
                if (this._viewMode === 'favoriten') this._renderFavoriten();
            })
            .catch(() => {});
    },

    _initStatLabels() {
        const map = {
            'stat-total':  'edms_stat_dokumente',
            'stat-extra1': 'edms_stat_posteingang',
            'stat-extra2': 'edms_stat_doctypes',
        };
        Object.entries(map).forEach(([id, key]) => {
            const lbl = document.querySelector('#' + id + ' .crm-stat-lbl');
            if (lbl) lbl.textContent = this.t(key, key);
        });
    },

    _doctypeLabel(k, fallback) {
        const map = {
            cv: 'edms_doctype_cv', vertrag: 'edms_doctype_vertrag', rechnung: 'edms_doctype_rechnung',
            angebot: 'edms_doctype_angebot', sonstiges: 'edms_doctype_sonstiges',
            leistungsnachweis: 'edms_doctype_nachweis', zeitnachweis: 'edms_doctype_zeitnachweis',
            korrespondenz: 'edms_doctype_korrespondenz',
        };
        return this.t(map[k] || k, fallback || k);
    },

    refreshI18n() {
        this._initStatLabels();
        this.fillScopeDropdown();
        if (this.currentOwner) {
            this.loadAkte(this.currentOwner.type, this.currentOwner.crm_id, this.currentOwner.name, this.currentDocUuid);
        }
    },
    _handleDeepLink() {
        const params = new URLSearchParams(window.location.search);
        const docId = params.get('doc');
        const mailAccount = params.get('mail_account');
        if (docId) {
            this._openDocFallback(docId);
        } else if (mailAccount) {
            this._showMailDetail({
                account: mailAccount,
                folder: params.get('mail_folder') || '',
                message_id: params.get('mail_message_id') || '',
                uid: params.get('mail_uid') || '',
                subject: params.get('mail_subject') || '',
                from_addr: '',
            });
        }
    },
    // Das crm-sort-Dropdown zum Such-Bereich-Umschalter machen
    fillScopeDropdown() {
        const sel = document.getElementById('crm-sort');
        if (!sel) return;
        const opts = [
            ['all',       this.t('edms_scope_alles','Alles')],
            ['personen',  this.t('edms_scope_personen','Personen')],
            ['firmen',    this.t('edms_scope_firmen','Firmen')],
            ['dokumente', this.t('edms_scope_dokumente','Dokumente')],
            ['mails',     this.t('edms_scope_mails','Mails')],
        ];
        sel.innerHTML = opts.map(o =>
            '<option value="' + o[0] + '">' + o[1] + '</option>').join('');
        this._scope = 'all';
    },

    bindSearch() {
        const btn = document.getElementById('crm-search-btn');
        const inp = document.getElementById('crm-global-search');
        if (btn) btn.addEventListener('click', () => this.loadCol1(1));
        if (inp) inp.addEventListener('keydown', e => { if (e.key === 'Enter') this.loadCol1(1); });
        // Live-Suche: tippen -> nach kurzer Pause automatisch suchen (Debounce)
        if (inp) inp.addEventListener('input', () => {
            clearTimeout(this._liveTimer);
            const val = inp.value.trim();
            if (val.length < 2) return;   // erst ab 2 Zeichen
            this._liveTimer = setTimeout(() => this.loadCol1(1), 300);
        });
        const sort = document.getElementById('crm-sort');
        if (sort) sort.addEventListener('change', () => { this._scope = sort.value; this.loadCol1(1); });
        // Query-Hilfe-Button an die bestehende CRM-Funktion binden
        const helpBtn = document.getElementById('crm-help-btn');
        if (helpBtn && window.toggleCrmQueryHelp) {
            helpBtn.addEventListener('click', () => window.toggleCrmQueryHelp());
        }
    },

    bindModeButtons() {
        document.querySelectorAll('.edms-mode-btn').forEach(b => {
            b.addEventListener('click', () => this.setMode(b.dataset.mode));
        });
    },

    setMode(mode) {
        this.mode = mode;
        this.currentOwner = null;
        this.currentDocUuid = null;
        this.akteFilter = '';

        document.querySelectorAll('.edms-mode-btn').forEach(b => {
            b.classList.toggle('active', b.dataset.mode === mode);
        });

        const titles = {
            personen:    [this.t('edms_personen','Personen & Firmen'), 'bi-people'],
            dokumente:   [this.t('dokumente','Dokumente'), 'bi-files'],
            posteingang: [this.t('edms_stat_posteingang','Posteingang'), 'bi-inbox'],
            archiv:      [this.t('edms_mode_archiv','Archiv'), 'bi-archive'],
        };
        const conf = titles[mode] || titles.personen;
        const tEl = document.getElementById('edms-col1-title');
        const iEl = document.getElementById('edms-col1-icon');
        if (tEl) tEl.textContent = conf[0];
        if (iEl) iEl.className = 'bi ' + conf[1];

        const pf = document.getElementById('edms-personen-filter');
        if (pf) pf.style.display = (mode === 'personen' && this._viewMode === 'liste') ? 'flex' : 'none';
        const df = document.getElementById('edms-doctype-filter');
        if (df) df.style.display = (mode === 'dokumente') ? 'flex' : 'none';
        const wrap = document.getElementById('edms-view-toggle-wrap');
        if (wrap) wrap.style.display = (mode === 'personen') ? 'flex' : 'none';
        const laschen = document.getElementById('edms-fav-laschen');
        if (mode !== 'personen') {
            this._viewMode = 'liste';
            const btnL = document.getElementById('edms-btn-liste');
            const btnF = document.getElementById('edms-btn-favoriten');
            if (btnL) btnL.classList.add('active');
            if (btnF) btnF.classList.remove('active');
            if (laschen) laschen.style.display = 'none';
        } else if (laschen) {
            laschen.style.display = this._viewMode === 'favoriten' ? 'flex' : 'none';
        }

        this._resetCol2();
        this._resetCol3();
        this.loadCol1(1);
    },

    loadCol1(page) {
        page = page || 1;
        this.currentPage = page;
        const q = (document.getElementById('crm-global-search') || {}).value || '';
        this._col1Loading();

        if (this.mode === 'personen' && this._viewMode === 'favoriten') {
            this.loadFavIds().then(() => this._renderFavoriten());
            return;
        }

        const scope = (document.getElementById('crm-sort') || {}).value || 'all';
        if (q.trim()) {
            const size = (document.getElementById('crm-per-page') || {}).value || 20;
            const p = new URLSearchParams({ q: q, scope: scope, size: size });
            fetch(this.api.searchAll + '?' + p, { headers: {'X-Requested-With':'XMLHttpRequest'} })
                .then(r => r.json())
                .then(d => {
                    this.renderMixed(d.results || []);
                    this._setCount('edms-col1-count', (d.counts && d.counts[scope]) || 0);
                    this._clearPagination();
                })
                .catch(() => this._col1Error());
            return;
        }

        if (this.mode === 'personen') {
            const params = new URLSearchParams({ q: q, size: 200 });
            fetch(this.api.personen + '?' + params, { headers: {'X-Requested-With':'XMLHttpRequest'} })
                .then(r => r.json())
                .then(d => { this.renderPersonen(d.results || []); this._setCount('edms-col1-count', d.total); this._clearPagination(); })
                .catch(() => this._col1Error());
            return;
        }

        const sort = (document.getElementById('crm-sort') || {}).value || '';
        const perPage = (document.getElementById('crm-per-page') || {}).value || 20;
        const doctype = (document.getElementById('edms-filter-doctype') || {}).value || '';
        const params = new URLSearchParams({ q: q, page: page, per_page: perPage });
        if (sort) params.set('sort', sort);
        if (doctype) params.set('doctype', doctype);
        if (this.mode === 'archiv') params.set('status', 'archiviert');

        const url = (this.mode === 'posteingang') ? this.api.inbox + '?' + params : this.api.search + '?' + params;
        fetch(url, { headers: {'X-Requested-With':'XMLHttpRequest'} })
            .then(r => r.json())
            .then(d => { this.renderDokumente(d.results || []); this.renderPagination(d.total, d.pages, d.page); this._setCount('edms-col1-count', d.total); })
            .catch(() => this._col1Error());
    },

    _kindIcon(k) {
        return {person:'bi-person', firma:'bi-buildings-fill', dokument:'bi-file-earmark-text', mail:'bi-envelope-fill'}[k] || 'bi-dot';
    },
    _kindLabel(k) {
        return {person:this.t('edms_kind_person','Person'), firma:this.t('edms_kind_firma','Firma'),
                dokument:this.t('edms_kind_dokument','Dokument'), mail:this.t('edms_kind_mail','Mail')}[k] || k;
    },
    _kindColor(k) {
        return { person:'#6b62c9', firma:'#1d9e75', dokument:'#378add', mail:'#ba7517' }[k] || '#888';
    },
    _typeIconHtml(kind, biIcon, onclick) {
        const click = onclick ? ' onclick="' + onclick + '"' : '';
        return '<div class="edms-type-icon edms-kind-' + kind + '"' + click + '><i class="bi ' + biIcon + '"></i></div>';
    },
    _doctypeKind(doctype) {
        return ['email', 'korrespondenz'].includes(doctype) ? 'mail' : 'dokument';
    },
    renderMixed(results) {
        const list = document.getElementById('edms-col1-list')
                  || document.getElementById('edms-col-treffer-body')
                  || document.querySelector('.edms-col-treffer .edms-col-body');
        if (!list) return;
        if (!results.length) {
            list.innerHTML = '<div class="crm-list-loading">' + this.t('keine_treffer','Keine Treffer') + '</div>';
            return;
        }
        list.innerHTML = results.map(r => this._mixItem(r)).join('');
    },
    _mixItem(r) {
        const badgeCol = this._kindColor(r.kind);
        let icon;
        if (r.kind === 'person') {
            icon = '<div class="crm-avatar edms-kind-person" style="font-size:10px;background:' + badgeCol + '">' + this._initials(r.title) + '</div>';
        } else {
            icon = this._typeIconHtml(r.kind, this._kindIcon(r.kind));
        }
        const sub = r.meta ? this._esc(r.meta) : this._kindLabel(r.kind);
        const dokCounter = (r.kind === 'person')
            ? '<div class="crm-dok-counter' + ((r.doc_count > 0) ? '' : ' crm-dok-zero') + '">' +
              '<span class="crm-dok-num">' + (r.doc_count || 0) + '</span>' +
              '<span class="crm-dok-lbl">Dok.</span></div>'
            : '';
        const snip = r.snippet
            ? '<div class="crm-item-snip">' + this._esc(r.snippet) + '</div>' : '';
        const mailData = (r.kind === 'mail')
            ? ' data-account="' + this._esc(r.account||'') + '" data-folder="' + this._esc(r.folder||'') +
              '" data-message-id="' + this._esc(r.message_id||'') + '" data-uid="' + this._esc(r.uid||'') +
              '" data-subject="' + this._esc(r.title||'') + '" data-from="' + this._esc(r.snippet||'') + '"'
            : '';
        return '<div class="crm-list-item"' + mailData + ' onclick="EDMS.openMixed(\'' + r.kind + '\',\'' + this._esc(r.id) + '\',this)">' +
            icon + '<div class="crm-item-info">' +
            '<div class="crm-item-name" style="font-size:12px">' + this._esc(r.title || '—') +
            ' <span class="crm-item-kind" style="color:' + badgeCol + '">' + this._kindLabel(r.kind) + '</span></div>' +
            '<div class="crm-item-sub">' + sub + '</div>' + snip +
            '</div>' + dokCounter + '</div>';
    },
        openMixed(kind, id, el) {
        document.querySelectorAll('.crm-list-item').forEach(x => x.classList.remove('active'));
        if (el) el.classList.add('active');
        if (kind === 'person') this.loadAkte('contact', id, '');
        else if (kind === 'firma') this.loadAkte('account', id, '');
        else if (kind === 'dokument') this._openDocFallback(id);
        else if (kind === 'mail') this._openMailHit(el);
    },
    _openMailHit(el) {
        // Mail-Daten aus dem Treffer-Element holen (in data-* gespeichert)
        const m = {
            account: el.dataset.account || '',
            folder: el.dataset.folder || '',
            message_id: el.dataset.messageId || '',
            uid: el.dataset.uid || '',
            subject: el.dataset.subject || '',
            from_addr: el.dataset.from || '',
        };
        this._showMailDetail(m);
    },
    _showMailDetail(m) {
        // Spalte 3 auf Mails schalten
        this.vorschauTab = 'mails';
        document.querySelectorAll('.edms-vorschau-tab').forEach(t => t.classList.remove('active'));
        const tabEl = document.getElementById('edms-vtab-mails');
        if (tabEl) tabEl.classList.add('active');
        const head = document.getElementById('edms-vorschau-head');
        if (head) head.innerHTML = '<span class="edms-vorschau-fname"><i class="bi bi-envelope"></i> ' + this._esc(m.subject) + '</span>';
        const body = document.getElementById('edms-vorschau-body');
        if (body) body.innerHTML = '<div class="edms-mail-detail" id="edms-mail-detail"></div>';
        const det = document.getElementById('edms-mail-detail');
        if (det) det.innerHTML = '<div class="crm-list-loading">' + this.t('laden','Lade…') + '</div>';
        const p = new URLSearchParams({ account: m.account, folder: m.folder });
        if (m.uid) p.set('uid', m.uid); else p.set('message_id', m.message_id);
        fetch(this.api.mailView + '?' + p, { headers: {'X-Requested-With':'XMLHttpRequest'} })
            .then(r => r.json())
            .then(md => this._renderMailDetail(md, m))
            .catch(() => { if (det) det.innerHTML = '<div class="edms-vorschau-msg"><i class="bi bi-exclamation-triangle"></i>' + this.t('fehler_beim_laden','Fehler') + '</div>'; });
    },
    _openDocFallback(id) {
        this._showPdf(id);
    },
    renderPersonen(people, skipTypeFilter) {
        const list = document.getElementById('edms-col1-list');
        if (!list) return;
        const filt = this._personenFilter || 'alle';
        let arr = people;
        if (!skipTypeFilter) {
            if (filt === 'berater' || filt === 'personen') arr = people.filter(p => p.owner_type === 'contact');
            else if (filt === 'firmen') arr = people.filter(p => p.owner_type === 'account');
        }
        if (!arr.length) { list.innerHTML = '<div class="crm-list-loading">' + this.t('keine_treffer','Keine Treffer') + '</div>'; return; }
        list.innerHTML = arr.map(p => this._personItem(p)).join('');
        list.querySelectorAll('.crm-list-item').forEach(el => {
            el.addEventListener('click', () => {
                list.querySelectorAll('.crm-list-item').forEach(i => i.classList.remove('active'));
                el.classList.add('active');
                this.selectPerson(el.dataset.ownerType, el.dataset.crmId, el.dataset.name);
            });
        });
    },

    _personItem(p) {
        const isAccount = p.owner_type === 'account';
        const icon = isAccount
            ? this._typeIconHtml('firma', this._kindIcon('firma'))
            : '<div class="crm-avatar edms-kind-person" style="font-size:10px;background:#6b62c9">' + this._initials(p.name) + '</div>';
        const typeLabel = isAccount ? this.t('kunden_label','Firma') : this.t('berater_label','Berater');
        const fav = this.isFav(p.crm_id, p.owner_type);
        const sub = (p.doc_count == null)
            ? typeLabel
            : (typeLabel + ' · ' + (p.doc_count || 0) + ' ' + this.t('dokumente','Dok.'));
        const cid = this._esc(p.crm_id || '');
        const otype = isAccount ? 'account' : 'contact';
        return '<div class="crm-list-item" data-crm-id="' + cid + '"' +
            ' data-owner-type="' + otype + '" data-name="' + this._esc(p.name || '') + '">' +
            icon + '<div class="crm-item-info">' +
            '<div class="crm-item-name" style="font-size:12px">' + this._esc(p.name || '—') + '</div>' +
            '<div class="crm-item-sub">' + sub + '</div>' +
            '</div>' +
            '<i class="bi ' + (fav ? 'bi-star-fill' : 'bi-star') + ' crm-fav-star' + (fav ? ' crm-fav-active' : '') + '"' +
            ' title="' + this.t('favoriten','Favorit') + '"' +
            ' onclick="event.stopPropagation(); EDMS.toggleFav(\'' + cid + '\',\'' + otype + '\', this);"></i>' +
            '</div>';
    },

    renderDokumente(results) {
        const list = document.getElementById('edms-col1-list');
        if (!list) return;
        if (!results.length) { list.innerHTML = '<div class="crm-list-loading">' + this.t('keine_treffer','Keine Treffer') + '</div>'; return; }
        list.innerHTML = results.map(r => this._dokItem(r)).join('');
        list.querySelectorAll('.crm-list-item').forEach(el => {
            el.addEventListener('click', () => {
                list.querySelectorAll('.crm-list-item').forEach(i => i.classList.remove('active'));
                el.classList.add('active');
                this.selectDokument(el.dataset.uuid);
            });
        });
    },

    _dokItem(r) {
        const owner = (r.owner_names && r.owner_names.length) ? r.owner_names[0] : this.t('edms_kein_owner','kein Owner');
        const kind = this._doctypeKind(r.doctype);
        const icon = this._typeIconHtml(kind, this._docIcon(r.doctype));
        const sub = [owner, r.doctype_label || r.doctype].filter(Boolean).join(' · ');
        return '<div class="crm-list-item" data-uuid="' + r.uuid + '">' +
            icon + '<div class="crm-item-info">' +
            '<div class="crm-item-name" style="font-size:12px">' + (r.title || r.filename || '—') + '</div>' +
            '<div class="crm-item-sub">' + sub + '</div>' +
            '</div></div>';
    },

    _docIcon(doctype) {
        const m = {cv:'bi-file-person', vertrag:'bi-file-earmark-text', contract:'bi-file-earmark-text',
                   rechnung:'bi-receipt', invoice:'bi-receipt', nachweis:'bi-file-earmark-check',
                   leistungsnachweis:'bi-file-earmark-check', zeitnachweis:'bi-clock-history',
                   angebot:'bi-file-earmark-richtext', korrespondenz:'bi-envelope-fill',
                   email:'bi-envelope-fill', sonstiges:'bi-file-earmark'};
        return m[doctype] || 'bi-file-earmark';
    },

    setPersonenFilter(filt) {
        this._personenFilter = filt;
        this._scope = filt;   // Pill = Scope (all/personen/firmen/mails/dokumente)
        // Dropdown synchron halten
        const sort = document.getElementById('crm-sort');
        if (sort) sort.value = filt;
        document.querySelectorAll('.edms-pf-pill').forEach(p => p.classList.toggle('active', p.dataset.filter === filt));
        this.loadCol1(1);
    },

    selectPerson(ownerType, crmId, name) {
        this.currentOwner = {type: ownerType, crm_id: crmId, name: name};
        this.akteFilter = '';
        this.loadAkte(ownerType, crmId, name, null);
    },

    selectDokument(uuid) {
        this.currentDocUuid = uuid;
        this._currentAttachment = null;
        if (this.mode === 'posteingang') {
            this.showInboxActions(uuid);   // 2d: Aufräum-Box
        } else {
            this.showDetail(uuid);          // Dokumente-Modus: Detail direkt
        }
        this.loadVorschau(uuid);
    },

    // ── 2d: Posteingang-Aufräum-Aktionen ──────────────────
    showInboxActions(uuid) {
        const panel = document.getElementById('edms-akte-panel');
        if (!panel) return;
        this.currentDocUuid = uuid;
        panel.innerHTML = '<div class="crm-list-loading"><i class="bi bi-arrow-repeat"></i> ' + this.t('laden','Lade...') + '</div>';
        fetch(this.api.document + uuid + '/', { headers: {'X-Requested-With':'XMLHttpRequest'} })
            .then(r => r.json())
            .then(resp => this._renderInboxActions(resp.document || resp))
            .catch(() => { panel.innerHTML = '<div class="crm-list-loading">' + this.t('fehler_beim_laden','Fehler beim Laden') + '</div>'; });
    },

    _renderInboxActions(d) {
        const panel = document.getElementById('edms-akte-panel');
        if (!panel) return;
        panel.innerHTML =
            '<div class="edms-detail-head"><i class="bi bi-inbox edms-detail-back" style="cursor:default"></i>' +
            '<span class="edms-detail-title">' + this.t('edms_inbox_zuordnen','Posteingang — zuordnen') + '</span></div>' +
            '<div class="edms-col-body">' +
            '<div class="edms-inbox-fname"><i class="bi ' + this._docIcon(d.doctype) + '"></i> ' + (d.filename || d.title || '—') + '</div>' +
            '<div class="edms-inbox-hint">' + this.t('edms_inbox_hint','Dieses Dokument hat noch keinen Owner. Wohin gehört es?') + '</div>' +

            // Aktion 1: Person/Firma suchen
            '<div class="edms-inbox-section">' +
            '<div class="edms-inbox-label">' + this.t('edms_inbox_person','Zu Person / Firma zuordnen') + '</div>' +
            '<input type="text" id="edms-inbox-search" class="edms-inbox-input" placeholder="' + this.t('search','Suchen...') + '" autocomplete="off">' +
            '<div id="edms-inbox-results" class="edms-inbox-results"></div>' +
            '</div>' +

            // Aktion 2: abcona
            '<button class="crm-action-btn edms-inbox-abcona" onclick="EDMS.assignToAbcona(\'' + d.uuid + '\')">' +
            '<i class="bi bi-building"></i> ' + this.t('edms_inbox_abcona','Als abcona-Dokument') + '</button>' +

            // Aktion 3: erledigt
            '<button class="crm-action-btn edms-inbox-done" onclick="EDMS.markReviewDone(\'' + d.uuid + '\')">' +
            '<i class="bi bi-check2-circle"></i> ' + this.t('edms_inbox_done','Als erledigt (kein Owner)') + '</button>' +
            '</div>';

        // Suchfeld verdrahten
        const inp = document.getElementById('edms-inbox-search');
        if (inp) {
            inp.focus();
            let timer = null;
            inp.addEventListener('input', () => {
                clearTimeout(timer);
                timer = setTimeout(() => this._inboxSearchOwner(inp.value, d.uuid), 300);
            });
        }
    },

    _inboxSearchOwner(q, docUuid) {
        const res = document.getElementById('edms-inbox-results');
        if (!res) return;
        if (!q.trim()) { res.innerHTML = ''; return; }
        fetch('/crm/api/berater/?q=' + encodeURIComponent(q) + '&per_page=8', { headers: {'X-Requested-With':'XMLHttpRequest'} })
            .then(r => r.json())
            .then(d => {
                const items = d.results || [];
                if (!items.length) { res.innerHTML = '<div class="edms-inbox-noresult">' + this.t('keine_treffer','Keine Treffer') + '</div>'; return; }
                res.innerHTML = items.map(c =>
                    '<div class="edms-inbox-result" onclick="EDMS.assignInboxOwner(\'' + docUuid + '\',\'contact\',\'' + c.crm_id + '\',\'' + (c.full_name||'').replace(/'/g,"\\'") + '\')">' +
                    '<i class="bi bi-person" style="color:var(--abcona-blue)"></i>' +
                    '<span style="flex:1">' + (c.full_name||'') + '</span>' +
                    '<span class="edms-inbox-city">' + (c.city||'') + '</span></div>'
                ).join('');
            }).catch(()=>{ res.innerHTML = '<div class="edms-inbox-noresult">' + this.t('fehler_beim_laden','Fehler') + '</div>'; });
    },

    assignInboxOwner(docUuid, ownerType, crmId, name) {
        this._postOwner(docUuid, ownerType, crmId, () => this._inboxAfterAction(docUuid));
    },

    assignToAbcona(docUuid) {
        this._postOwner(docUuid, 'account', this.ABCONA_CRM_ID, () => this._inboxAfterAction(docUuid));
    },

    _postOwner(docUuid, ownerType, crmId, cb) {
        fetch(this.api.document + docUuid + '/owner/', {
            method: 'POST',
            headers: {'Content-Type':'application/json','X-CSRFToken':this.csrf(),'X-Requested-With':'XMLHttpRequest'},
            body: JSON.stringify({owner_crm_id: crmId, owner_type: ownerType, role: 'primaer', is_primary: true}),
        }).then(r => r.json()).then(d => { if (d.ok && cb) cb(); }).catch(()=>{});
    },

    markReviewDone(docUuid) {
        fetch(this.api.document + docUuid + '/review-done/', {
            method: 'POST',
            headers: {'Content-Type':'application/json','X-CSRFToken':this.csrf(),'X-Requested-With':'XMLHttpRequest'},
            body: JSON.stringify({}),
        }).then(r => r.json()).then(d => { if (d.ok) this._inboxAfterAction(docUuid); }).catch(()=>{});
    },

    _inboxAfterAction(docUuid) {
        // Dokument aus Liste entfernen + Mitte/Vorschau zurücksetzen + Zähler aktualisieren
        const item = document.querySelector('.crm-list-item[data-uuid="' + docUuid + '"]');
        if (item) item.remove();
        this._resetCol2();
        this._resetCol3();
        this.loadStats();
    },

    loadStats() {
        fetch(this.api.search + '?per_page=1', { headers: {'X-Requested-With':'XMLHttpRequest'} })
            .then(r => r.json()).then(d => this._setStat('stat-total', d.total || 0)).catch(function(){});
        fetch(this.api.inbox + '?per_page=1', { headers: {'X-Requested-With':'XMLHttpRequest'} })
            .then(r => r.json()).then(d => this._setStat('stat-extra1', d.total || 0, true)).catch(function(){});
        fetch(this.api.doctypes, { headers: {'X-Requested-With':'XMLHttpRequest'} })
            .then(r => r.json()).then(d => this._setStat('stat-extra2', (d.results || d.doctypes || []).length)).catch(function(){});
    },

    _setStat(id, val, warn) {
        const el = document.querySelector('#' + id + ' .crm-stat-val');
        if (el) { el.textContent = (val || 0).toLocaleString(); if (warn) el.classList.add('edms-warn'); }
    },

    loadAkte(ownerType, crmId, ownerName, activeUuid) {
        const panel = document.getElementById('edms-akte-panel');
        if (!panel) return;
        panel.innerHTML = '<div class="crm-list-loading"><i class="bi bi-arrow-repeat"></i> ' + this.t('laden','Lade...') + '</div>';
        // Dokumente, Mails UND Aufnahmen parallel laden
        const pDocs = fetch(this.api.akte + ownerType + '/' + crmId + '/', { headers: {'X-Requested-With':'XMLHttpRequest'} }).then(r => r.json()).catch(() => null);
        const pMails = fetch(this.api.personMails + encodeURIComponent(crmId) + '/mails/?size=200', { headers: {'X-Requested-With':'XMLHttpRequest'} }).then(r => r.json()).catch(() => null);
        const pRecs = fetch('/crm/api/recording/contact/' + encodeURIComponent(crmId) + '/', { headers: {'X-Requested-With':'XMLHttpRequest'} }).then(r => r.ok ? r.json() : null).catch(() => null);
        const pNotes = fetch('/crm/api/notes/contact/' + encodeURIComponent(crmId) + '/', { headers: {'X-Requested-With':'XMLHttpRequest'} }).then(r => r.ok ? r.json() : null).catch(() => null);
        Promise.all([pDocs, pMails, pRecs, pNotes]).then(([d, mailResp, recResp, noteResp]) => {
            if (!d) { panel.innerHTML = '<div class="crm-list-loading">' + this.t('fehler_beim_laden','Fehler beim Laden') + '</div>'; return; }
            this._akteMails = (mailResp && mailResp.results) || [];
            this._ownerAddrs = (mailResp && mailResp.addresses) || [];
            this._akteRecs = (recResp && recResp.recordings) || [];
            this._akteNotes = (noteResp && noteResp.notes) || [];
            this._currentMail = null;          // neue Person -> Mail-Kontext zurücksetzen
            this._currentAttachment = null;
            this.renderAkte(d, ownerType, crmId, ownerName, activeUuid);
        });
    },

    renderAkte(data, ownerType, crmId, ownerName, activeUuid) {
        const panel = document.getElementById('edms-akte-panel');
        if (!panel) return;
        const groups = data.tabs || data.groups || data.doctypes || {};
        const name = (data.owner && data.owner.name) || ownerName || crmId;
        const docsOf = g => Array.isArray(g) ? g : (g.documents || g.docs || []);
        const total = data.total || Object.keys(groups).reduce((a, k) => a + docsOf(groups[k]).length, 0);

        let html = '<div class="edms-akte-person">' +
            '<div class="crm-avatar" style="width:26px;height:26px;font-size:10px">' + this._initials(name) + '</div>' +
            '<div style="min-width:0"><div class="edms-akte-pname">' + name + '</div>' +
            '<div class="edms-akte-psub">' + total + ' ' + this.t('dokumente','Dokumente') + '</div></div>' +
            '<button class="edms-akte-open-crm" title="' + this.t('edms_in_crm_oeffnen','Im CRM öffnen') + '"' +
            ' onclick="EDMS.openInCrm(\'' + ownerType + '\',\'' + crmId + '\')"><i class="bi bi-box-arrow-up-right"></i></button></div>';

        const keys = Object.keys(groups);
        html += '<div class="edms-akte-tabs">';
        html += '<span class="edms-akte-pill' + (this.akteFilter===''?' active':'') + '" onclick="EDMS.setAkteFilter(\'\')">' + this.t('edms_alle','Alle') + ' ' + total + '</span>';
        keys.forEach(k => {
            const cnt = docsOf(groups[k]).length;
            const raw = (groups[k] && groups[k].label) ? groups[k].label : k;
            const label = this._doctypeLabel(k, raw);
            html += '<span class="edms-akte-pill' + (this.akteFilter===k?' active':'') + '" onclick="EDMS.setAkteFilter(\'' + k + '\')">' + label + ' ' + cnt + '</span>';
        });
        html += '</div>';

        // Filterleiste (Format + Sortierung) — clientseitig
        html += '<div class="edms-akte-filter">' +
            '<select id="edms-akte-format" onchange="EDMS._renderAkteList()">' +
            '<option value="">' + this.t('edms_format_alle','Format: alle') + '</option>' +
            '<option value="pdf">PDF</option>' +
            '<option value="word">Word</option>' +
            '<option value="excel">Excel</option>' +
            '<option value="email">E-Mail</option>' +
            '<option value="bild">' + this.t('edms_format_bild','Bild') + '</option>' +
            '<option value="sonst">' + this.t('sonstiges','Sonstige') + '</option>' +
            '</select>' +
            '<select id="edms-akte-sort" onchange="EDMS._renderAkteList()">' +
            '<option value="neu">' + this.t('edms_sort_neu','Datum: neueste') + '</option>' +
            '<option value="alt">' + this.t('edms_sort_alt','Datum: älteste') + '</option>' +
            '<option value="gross">' + this.t('edms_sort_gross','Größe ↓') + '</option>' +
            '<option value="name">' + this.t('edms_sort_name','Name A-Z') + '</option>' +
            '</select>' +
            '<select id="edms-akte-status" onchange="EDMS._renderAkteList()">' +
            '<option value="aktiv">' + this.t('edms_status_aktiv','Status: gültige') + '</option>' +
            '<option value="archiviert">' + this.t('edms_status_archiv','Archivierte') + '</option>' +
            '<option value="alle">' + this.t('edms_status_alle','Alle (inkl. Archiv)') + '</option>' +
            '</select>' +
            '</div>';

        // Dritte Zeile: eigene Mail-Zeile (getrennt von Dokumenten)
        const mailCnt = (this._akteMails || []).length;
        const attCnt = (this._akteMails || []).filter(m => m.has_attachments).length;
        html += '<div class="edms-akte-mailbar">' +
            '<i class="bi bi-envelope edms-akte-mailbar-ic"></i>' +
            '<select id="edms-akte-mailfilter" onchange="EDMS._renderAkteList()">' +
            '<option value="alle">' + this.t('edms_mailf_alle','Mails: alle') + '</option>' +
            '<option value="anhang">' + this.t('edms_mailf_anhang','nur mit Anhang') + '</option>' +
            '<option value="ohne">' + this.t('edms_mailf_ohne','nur ohne Anhang') + '</option>' +
            '<option value="aus">' + this.t('edms_mailf_aus','Mails ausblenden') + '</option>' +
            '</select>' +
            '<span class="edms-akte-mailcount">' + mailCnt +
            (attCnt ? ' <i class="bi bi-paperclip"></i>' + attCnt : '') + '</span>' +
            '</div>';

        // Aufnahmen-Sektion (nur wenn vorhanden) — ausklappbar
        const recs = this._akteRecs || [];
        if (recs.length) {
            html += '<div class="edms-akte-recbar" onclick="EDMS.toggleAkteRecs()">' +
                '<i class="bi bi-mic edms-akte-recbar-ic"></i>' +
                '<span class="edms-akte-recbar-txt">' + this.t('edms_aufnahmen','Aufnahmen') + '</span>' +
                '<span class="edms-akte-mailcount">' + recs.length + '</span>' +
                '<i class="bi bi-chevron-down edms-akte-recchev" id="edms-recchev"></i>' +
                '</div>' +
                '<div class="edms-akte-reclist" id="edms-akte-reclist" style="display:none"></div>';
        }

        // Notizen-Sektion (nur wenn vorhanden) — ausklappbar
        const notes = this._akteNotes || [];
        if (notes.length) {
            html += '<div class="edms-akte-notebar" onclick="EDMS.toggleAkteNotes()">' +
                '<i class="bi bi-journal-text edms-akte-notebar-ic"></i>' +
                '<span class="edms-akte-recbar-txt">' + this.t('edms_notizen','Notizen') + '</span>' +
                '<span class="edms-akte-mailcount">' + notes.length + '</span>' +
                '<i class="bi bi-chevron-down edms-akte-recchev" id="edms-notechev"></i>' +
                '</div>' +
                '<div class="edms-akte-notelist" id="edms-akte-notelist" style="display:none"></div>';
        }

        html += '<div class="edms-col-body" id="edms-akte-doclist"></div>';
        panel.innerHTML = html;

        // Daten merken + Liste rendern
        this._akteGroups = groups;
        this._akteActiveUuid = activeUuid;
        this._renderAkteList();
    },

    // Format aus Dateiname ableiten (Gruppen wie im Filter)
    _fmtGroup(filename) {
        const ext = ((filename || '').split('.').pop() || '').toLowerCase();
        if (ext === 'pdf') return 'pdf';
        if (['doc','docx','rtf','odt'].includes(ext)) return 'word';
        if (['xls','xlsx','sxc','csv'].includes(ext)) return 'excel';
        if (['msg','eml'].includes(ext)) return 'email';
        if (['jpg','jpeg','gif','tif','tiff','png','bmp'].includes(ext)) return 'bild';
        return 'sonst';
    },

    _renderAkteList() {
        const list = document.getElementById('edms-akte-doclist');
        if (!list || !this._akteGroups) return;
        const groups = this._akteGroups;
        const docsOf = g => Array.isArray(g) ? g : (g.documents || g.docs || []);

        // Nach DocType-Pill (Art) vorfiltern
        let docs = [];
        if (this.akteFilter && groups[this.akteFilter]) docs = docsOf(groups[this.akteFilter]);
        else Object.keys(groups).forEach(k => { docs = docs.concat(docsOf(groups[k])); });

        // Format-Filter (Dokumente)
        const fmt = (document.getElementById('edms-akte-format') || {}).value || '';
        if (fmt && fmt !== 'email') docs = docs.filter(d => this._fmtGroup(d.filename) === fmt);
        if (fmt === 'email') docs = [];  // nur Mails zeigen

        // Status-Filter (gültige / archivierte / alle)
        const stat = (document.getElementById('edms-akte-status') || {}).value || 'aktiv';
        if (stat === 'aktiv')      docs = docs.filter(d => d.status !== 'archiviert');
        else if (stat === 'archiviert') docs = docs.filter(d => d.status === 'archiviert');

        // Dokumente auf gemeinsames Format normalisieren
        let items = docs.map(d => ({
            _type: 'doc',
            uuid: d.uuid,
            title: d.title || d.filename || '—',
            sub: (d.doctype_label || d.doctype || ''),
            date: d.document_date || '',
            size_bytes: d.size_bytes || 0,
            status: d.status,
            doctype: d.doctype,
            filename: d.filename,
        }));

        // Mails dazu (Mail-Filter: alle / anhang / ohne / aus)
        const mailMode = (document.getElementById('edms-akte-mailfilter') || {}).value || 'alle';
        const showMails = (mailMode !== 'aus') && (!fmt || fmt === 'email') && (stat !== 'archiviert');
        if (showMails && this._akteMails && this._akteMails.length) {
            let mails = this._akteMails;
            if (mailMode === 'anhang') mails = mails.filter(m => m.has_attachments);
            else if (mailMode === 'ohne') mails = mails.filter(m => !m.has_attachments);
            const mailItems = mails.map((m) => ({
                _type: 'mail',
                _mailIdx: this._akteMails.indexOf(m),
                title: m.subject || '(kein Betreff)',
                sub: this.t('edms_mail','Mail') + ' · ' + (this._addrOf(this._mailPeer(m, this._mailDir(m))) || this._mailPeer(m, this._mailDir(m))),
                date: m.date || '',
                has_attachments: m.has_attachments,
                _mail: m,
            }));
            items = items.concat(mailItems);
        }

        // Gemeinsame Sortierung
        const sort = (document.getElementById('edms-akte-sort') || {}).value || 'neu';
        const dt = x => (x.date || '').substring(0,10);
        if (sort === 'neu')   items.sort((a,b) => dt(b).localeCompare(dt(a)));
        else if (sort === 'alt') items.sort((a,b) => dt(a).localeCompare(dt(b)));
        else if (sort === 'gross') items.sort((a,b) => (b.size_bytes||0) - (a.size_bytes||0));
        else if (sort === 'name')  items.sort((a,b) => (a.title||'').localeCompare(b.title||''));

        if (!items.length) {
            list.innerHTML = '<div class="crm-list-loading">' + this.t('keine_treffer','Keine Treffer') + '</div>';
            return;
        }
        const activeUuid = this._akteActiveUuid;
        list.innerHTML = items.map(it => {
            if (it._type === 'mail') {
                const clip = it.has_attachments ? '<i class="bi bi-paperclip edms-akte-archicon"></i>' : '';
                const datum = it.date ? ' · ' + this._mailDate(it.date) : '';
                return '<div class="edms-akte-doc edms-akte-mailrow" onclick="EDMS.openAkteMail(' + it._mailIdx + ')">' +
                    this._typeIconHtml('mail', this._kindIcon('mail')) +
                    '<div style="flex:1;min-width:0">' +
                    '<div class="edms-akte-dtitle">' + clip + this._esc(it.title) + '</div>' +
                    '<div class="edms-akte-dsub">' + this._esc(it.sub) + datum + '</div></div>' +
                    '</div>';
            }
            const act = (it.uuid === activeUuid) ? ' active' : '';
            const arch = (it.status === 'archiviert') ? ' edms-doc-archiviert' : '';
            const archBadge = (it.status === 'archiviert')
                ? '<i class="bi bi-archive-fill edms-akte-archicon" title="' + this.t('edms_status_archiviert','archiviert') + '"></i>'
                : '';
            const sizeKb = it.size_bytes ? ' · ' + Math.round(it.size_bytes/1024) + ' KB' : '';
            const datum = it.date ? ' · ' + it.date.substring(0,10) : '';
            const docKind = this._doctypeKind(it.doctype);
            return '<div class="edms-akte-doc' + act + arch + '" data-uuid="' + it.uuid + '">' +
                this._typeIconHtml(docKind, this._docIcon(it.doctype), 'EDMS.selectAkteDoc(this.parentNode,\'' + it.uuid + '\')') +
                '<div style="flex:1;min-width:0" onclick="EDMS.selectAkteDoc(this.parentNode,\'' + it.uuid + '\')">' +
                '<div class="edms-akte-dtitle">' + archBadge + this._esc(it.title) + '</div>' +
                '<div class="edms-akte-dsub">' + this._esc(it.sub) + datum + sizeKb + '</div></div>' +
                '<i class="bi bi-info-square edms-akte-detailbtn" title="' + this.t('edms_dok_details','Dokument-Details') + '" onclick="EDMS.showDetail(\'' + it.uuid + '\')"></i>' +
                '</div>';
        }).join('');
    },

    // Klick auf eine Mail in der Akte-Liste -> Spalte 3 Mails-Reiter + Mail öffnen
    openAkteMail(idx) {
        document.querySelectorAll('.edms-akte-doc').forEach(r => r.classList.remove('active'));
        // Spalte 3 auf Mails-Reiter schalten und diese Mail anzeigen
        this.vorschauTab = 'mails';
        document.querySelectorAll('.edms-vorschau-tab').forEach(t => t.classList.remove('active'));
        const tabEl = document.getElementById('edms-vtab-mails');
        if (tabEl) tabEl.classList.add('active');
        // Mail-Daten für openMail bereitstellen (aus Akte-Mails)
        this._mailData = this._akteMails;
        const head = document.getElementById('edms-vorschau-head');
        if (head) head.innerHTML = '<span class="edms-vorschau-fname"><i class="bi bi-envelope"></i> ' + this.t('edms_mails','Mails') + '</span>';
        // Body-Container vorbereiten (ohne Liste, nur Detail)
        const body = document.getElementById('edms-vorschau-body');
        if (body) body.innerHTML = '<div class="edms-mail-detail" id="edms-mail-detail"></div>';
        this.openMail(idx);
    },

    // Aufnahmen-Sektion auf-/zuklappen (lazy: Audio erst beim Öffnen laden)
    toggleAkteRecs() {
        const list = document.getElementById('edms-akte-reclist');
        const chev = document.getElementById('edms-recchev');
        if (!list) return;
        const open = list.style.display !== 'none';
        if (open) {
            list.style.display = 'none';
            if (chev) chev.className = 'bi bi-chevron-down edms-akte-recchev';
            return;
        }
        list.style.display = 'block';
        if (chev) chev.className = 'bi bi-chevron-up edms-akte-recchev';
        if (!list.dataset.loaded) {
            this._renderAkteRecs();
            list.dataset.loaded = '1';
        }
    },

    _renderAkteRecs() {
        const list = document.getElementById('edms-akte-reclist');
        if (!list) return;
        const recs = this._akteRecs || [];
        if (!recs.length) { list.innerHTML = '<div class="crm-list-loading">' + this.t('edms_keine_aufnahmen','Keine Aufnahmen') + '</div>'; return; }
        list.innerHTML = recs.map(r => {
            const dt = (r.recorded_at || '').replace('T',' ').substring(0,16);
            const dur = r.duration_sec ? Math.floor(r.duration_sec/60) + ':' + String(r.duration_sec%60).padStart(2,'0') : '';
            const ext = r.extension ? ' · ' + this.t('edms_durchwahl','Durchwahl') + ' ' + this._esc(r.extension) : '';
            const subj = r.subject ? '<div class="edms-rec-subj">' + this._esc(r.subject) + '</div>' : '';
            return '<div class="edms-rec-item">' +
                '<div class="edms-rec-head"><i class="bi bi-record-circle edms-rec-ico"></i>' +
                '<div style="flex:1;min-width:0"><div class="edms-rec-meta">' + dt + (dur ? ' · ' + dur : '') + ext + '</div>' + subj + '</div></div>' +
                '<audio controls preload="none" data-rec-id="' + r.id + '" class="edms-rec-audio"></audio>' +
                '</div>';
        }).join('');
        // Audio per Blob nachladen (Session-Auth, robust)
        list.querySelectorAll('audio[data-rec-id]').forEach(el => this._loadRecAudio(el));
    },
    toggleAkteNotes() {
        const list = document.getElementById('edms-akte-notelist');
        const chev = document.getElementById('edms-notechev');
        if (!list) return;
        const open = list.style.display !== 'none';
        if (open) {
            list.style.display = 'none';
            if (chev) chev.className = 'bi bi-chevron-down edms-akte-recchev';
            return;
        }
        list.style.display = 'block';
        if (chev) chev.className = 'bi bi-chevron-up edms-akte-recchev';
        if (!list.dataset.loaded) { this._renderAkteNotes(); list.dataset.loaded = '1'; }
    },
    _renderAkteNotes() {
        const list = document.getElementById('edms-akte-notelist');
        if (!list) return;
        const notes = this._akteNotes || [];
        if (!notes.length) { list.innerHTML = '<div class="crm-list-loading">' + this.t('edms_keine_notizen','Keine Notizen') + '</div>'; return; }
        const typLabel = { phone:'telefonnotiz', email:'email_notiz', meeting:'besprechung', general:'allgemein' };
        list.innerHTML = notes.map(n => {
            const dt = (n.created_at || '').replace('T',' ').substring(0,16);
            const typ = this.t(typLabel[n.note_type] || n.note_type || '', n.note_type || '');
            const by = n.created_by ? ' · ' + this._esc(n.created_by) : '';
            return '<div class="edms-note-item">' +
                '<div class="edms-rec-head"><i class="bi bi-journal-text edms-note-ico"></i>' +
                '<div style="flex:1;min-width:0"><div class="edms-rec-meta">' + dt + ' · ' + this._esc(typ) + by + '</div>' +
                '<div class="edms-note-text">' + this._esc(n.note_text || '') + '</div></div></div>' +
                '</div>';
        }).join('');
    },

    _loadRecAudio(el) {
        const id = el.getAttribute('data-rec-id');
        if (!id) return;
        fetch('/crm/api/recording/' + id + '/audio/', { headers: {'X-Requested-With':'XMLHttpRequest'} })
            .then(r => r.ok ? r.blob() : null)
            .then(blob => { if (blob) el.src = URL.createObjectURL(blob); })
            .catch(() => {});
    },

    setAkteFilter(key) {
        this.akteFilter = key;
        // Pills neu markieren ohne Neuladen
        document.querySelectorAll('.edms-akte-pill').forEach(p => {
            const isAll = (key === '' && p.getAttribute('onclick').indexOf("setAkteFilter('')") >= 0);
            const isThis = p.getAttribute('onclick').indexOf("setAkteFilter('" + key + "')") >= 0;
            p.classList.toggle('active', key === '' ? isAll : isThis);
        });
        this._renderAkteList();
    },

    selectAkteDoc(el, uuid) {
        document.querySelectorAll('.edms-akte-doc').forEach(d => d.classList.remove('active'));
        if (el) el.classList.add('active');
        this.currentDocUuid = uuid;
        this._currentAttachment = null;
        this._currentMail = null;
        this.loadVorschau(uuid);
    },

    openInCrm(ownerType, crmId) {
        const base = (ownerType === 'account') ? '/crm/kunden/?detail=' : '/crm/berater/?detail=';
        window.open(base + crmId, '_blank');
    },

    showDetail(uuid) {
        const panel = document.getElementById('edms-akte-panel');
        if (!panel) return;
        this.currentDocUuid = uuid;
        panel.innerHTML = '<div class="crm-list-loading"><i class="bi bi-arrow-repeat"></i> ' + this.t('laden','Lade...') + '</div>';
        fetch(this.api.document + uuid + '/', { headers: {'X-Requested-With':'XMLHttpRequest'} })
            .then(r => r.json())
            .then(resp => this._renderDetail(resp.document || resp))
            .catch(() => { panel.innerHTML = '<div class="crm-list-loading">' + this.t('fehler_beim_laden','Fehler beim Laden') + '</div>'; });
        // Vorschau rechts gleich mitladen
        this.loadVorschau(uuid);
    },

    _renderDetail(d) {
        const panel = document.getElementById('edms-akte-panel');
        if (!panel) return;
        const owners = d.owners || [];
        const owner = owners.length ? owners[0] : null;
        const ext = ((d.filename || '').split('.').pop() || '').toLowerCase();
        const sizeKb = d.size_bytes ? Math.round(d.size_bytes/1024) + ' KB' : '—';
        const archived = (d.status === 'archiviert');
        const statusHtml = archived
            ? '<span style="color:var(--badge-warning-text,#c2841d)">' + this.t('edms_status_archiviert','archiviert') + '</span>'
            : '<span style="color:var(--status-green,#16a34a)">' + (d.status || 'gültig') + '</span>';

        // Zurück-Pfeil (führt zur Akte zurück, nur wenn Owner-Kontext da)
        const backArrow = this.currentOwner
            ? '<i class="bi bi-arrow-left edms-detail-back" title="' + this.t('zurueck','Zurück') + '" onclick="EDMS.backToAkte()"></i>'
            : '';

        // Owner-Kopf
        const ownerHead = owner
            ? '<div class="edms-detail-owner">' +
                '<div class="crm-avatar" style="width:30px;height:30px;font-size:10px;background:' + (owner.type==='account'?'#1d9e75':'#6b62c9') + (owner.type==='account'?';border-radius:6px':'') + '">' +
                (owner.type==='account' ? '<i class="bi bi-buildings-fill"></i>' : this._initials(owner.name)) + '</div>' +
                '<div style="min-width:0"><div class="edms-detail-oname">' + (owner.name||'') + '</div>' +
                '<div class="edms-detail-osub">' + (owner.type==='account'?this.t('kunden_label','Firma'):this.t('berater_label','Berater')) + ' · ' + this.t('edms_owner','Owner') + '</div></div>' +
                '<i class="bi bi-box-arrow-up-right edms-detail-crm" title="' + this.t('edms_in_crm_oeffnen','Im CRM öffnen') + '" onclick="EDMS.openInCrm(\'' + owner.type + '\',\'' + owner.crm_id + '\')"></i>' +
                '</div>'
            : '<div class="edms-detail-owner edms-detail-noowner">' +
                '<i class="bi bi-person-exclamation"></i>' +
                '<div><div class="edms-detail-oname">' + this.t('edms_kein_owner','kein Owner') + '</div>' +
                '<div class="edms-detail-osub">' + this.t('edms_im_posteingang','im Posteingang zuordnen') + '</div></div></div>';

        const row = (label, val) => '<tr><td class="edms-detail-lbl">' + label + '</td><td class="edms-detail-val">' + (val || '—') + '</td></tr>';

        // Pfad-Zeile
        const winPath = d.win_path || '';
        const pfadHtml = winPath
            ? '<div class="edms-detail-pfad-wrap"><div class="edms-detail-pfad-lbl">' + this.t('edms_win_pfad','Windows-Pfad') + ':</div>' +
                '<div class="edms-pfad-zeile" style="display:flex;border-radius:6px">' +
                '<span class="edms-pfad-text">' + winPath + '</span>' +
                '<button class="edms-pfad-copy" title="' + this.t('edms_pfad_kopieren','Pfad kopieren') + '" onclick="EDMS.copyPath(this,\'' + winPath.replace(/\\/g,'\\\\').replace(/'/g,"\\'") + '\')"><i class="bi bi-clipboard"></i></button></div></div>'
            : '';

        // Archivieren-Button
        const archBtn = archived
            ? '<button class="crm-action-btn edms-detail-restore" onclick="EDMS.restoreDoc(\'' + d.uuid + '\')"><i class="bi bi-arrow-counterclockwise"></i> ' + this.t('edms_wiederherstellen','Wiederherstellen') + '</button>'
            : '<button class="crm-action-btn edms-detail-archive" onclick="EDMS.archiveDoc(\'' + d.uuid + '\')"><i class="bi bi-archive"></i> ' + this.t('edms_archivieren','Archivieren') + '</button>';

        panel.innerHTML =
            '<div class="edms-detail-head">' + backArrow +
            '<span class="edms-detail-title">' + this.t('edms_dok_details','Dokument-Details') + '</span></div>' +
            '<div class="edms-col-body">' +
            ownerHead +
            '<div class="edms-detail-body">' +
            '<div class="edms-detail-fname">' + (d.filename || d.title || '—') + '</div>' +
            '<table class="edms-detail-table">' +
            row(this.t('edms_art','Art'), d.doctype_label || d.doctype) +
            row(this.t('edms_format','Format'), ext.toUpperCase()) +
            row(this.t('edms_dokumentdatum','Dokumentdatum'), d.document_date ? d.document_date.substring(0,10) : '—') +
            row(this.t('edms_groesse','Größe'), sizeKb) +
            row(this.t('status','Status'), statusHtml) +
            row(this.t('edms_aufbewahrung','Aufbew.-frist'), d.retention_until ? d.retention_until.substring(0,10) : '—') +
            row(this.t('edms_gewerk','Gewerk'), d.gewerk || '—') +
            '</table>' +
            pfadHtml +
            '<div class="edms-detail-actions">' +
            '<button class="crm-action-btn" onclick="EDMS.download(\'' + d.uuid + '\')"><i class="bi bi-download"></i> ' + this.t('edms_herunterladen','Herunterladen') + '</button>' +
            archBtn +
            '</div>' +
            '</div></div>';
    },

    archiveDoc(uuid) {
        fetch(this.api.document + uuid + '/archive/', {
            method: 'POST',
            headers: {'Content-Type':'application/json','X-CSRFToken':this.csrf(),'X-Requested-With':'XMLHttpRequest'},
            body: JSON.stringify({}),
        }).then(r => r.json()).then(d => {
            if (d.ok) this.showDetail(uuid);  // Detail neu laden (Status aktualisiert)
        }).catch(()=>{});
    },

    restoreDoc(uuid) {
        fetch(this.api.document + uuid + '/restore/', {
            method: 'POST',
            headers: {'Content-Type':'application/json','X-CSRFToken':this.csrf(),'X-Requested-With':'XMLHttpRequest'},
            body: JSON.stringify({}),
        }).then(r => r.json()).then(d => {
            if (d.ok) this.showDetail(uuid);
        }).catch(()=>{});
    },

    backToAkte() {
        if (this.currentOwner) this.loadAkte(this.currentOwner.type, this.currentOwner.crm_id, this.currentOwner.name, this.currentDocUuid);
        else this._resetCol2();
    },

    loadVorschau(uuid) {
        const head = document.getElementById('edms-vorschau-head');
        const body = document.getElementById('edms-vorschau-body');
        const pfad = document.getElementById('edms-pfad-zeile');
        if (!body) return;
        fetch(this.api.document + uuid + '/', { headers: {'X-Requested-With':'XMLHttpRequest'} })
            .then(r => r.json())
            .then(resp => {
                const d = resp.document || resp;
                const fname = d.filename || (d.versions && d.versions[0] ? d.versions[0].filename : '—');
                const ext = (fname.split('.').pop() || '').toLowerCase();
                if (head) {
                    head.innerHTML =
                        '<span class="edms-vorschau-fname">' + fname + '</span>' +
                        '<span class="edms-vorschau-format">' + ext.toUpperCase() + '</span>' +
                        '<span class="edms-vorschau-hint">' +
                        '<span class="edms-kbd-grp"><kbd class="edms-kbd">Strg</kbd>+<kbd class="edms-kbd">F</kbd> ' + this.t('edms_kbd_suchen','suchen') + '</span>' +
                        '<span class="edms-kbd-grp"><kbd class="edms-kbd">Strg</kbd>+<kbd class="edms-kbd">Scroll</kbd> ' + this.t('edms_kbd_zoomen','zoomen') + '</span>' +
                        '<span class="edms-kbd-grp"><kbd class="edms-kbd">F11</kbd> ' + this.t('edms_kbd_vollbild','Vollbild') + '</span>' +
                        '</span>' +
                        '<div class="edms-vorschau-actions">' +
                        '<button class="edms-vorschau-actbtn" title="' + this.t('edms_herunterladen','Herunterladen') + '" onclick="EDMS.download(\'' + uuid + '\')"><i class="bi bi-download"></i></button>' +
                        '<button class="edms-vorschau-actbtn" title="' + this.t('edms_neuer_tab','In neuem Tab öffnen') + '" onclick="EDMS.openTab(\'' + uuid + '\')"><i class="bi bi-box-arrow-up-right"></i></button>' +
                        '</div>';
                }
                if (pfad) pfad.style.display = 'none';  // Pfad nur in Detail-Ansicht (Spalte 2)
                const verIds = [];
                (d.versions || []).forEach(v => {
                    const id = v && (v.uuid || v.id);
                    if (id && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(String(id))) {
                        verIds.push(String(id));
                    }
                });
                this._previewDocMeta = d;
                this.renderVorschauTab(uuid, ext, verIds);
            })
            .catch(() => { if (body) body.innerHTML = '<div class="edms-vorschau-msg"><i class="bi bi-exclamation-triangle"></i>' + this.t('fehler_beim_laden','Fehler beim Laden') + '</div>'; });
    },

    renderVorschauTab(uuid, ext, extraIds) {
        const body = document.getElementById('edms-vorschau-body');
        if (!body) return;
        if (this.vorschauTab === 'mails') {
            this.loadPersonMails();
            return;
        }
        // Dokument-Reiter zeigt aktuell einen Mail-Anhang (kein EDMS-Dokument)
        if (this.vorschauTab === 'dokument' && this._currentAttachment) {
            const a = this._currentAttachment;
            body.innerHTML =
                '<iframe class="edms-vorschau-frame" src="' + a.preview + '" ' +
                'onload="EDMS._attachFrameCheck(this)"></iframe>';
            return;
        }
        const office = ['doc', 'docx', 'rtf', 'odt'].includes(ext);
        if (ext === 'pdf') {
            this._showPdf(uuid, extraIds);
            return;
        }
        if (!office) {
            body.innerHTML = '<div class="edms-vorschau-msg"><i class="bi bi-file-earmark"></i>' +
                this.t('edms_kein_preview','Keine Vorschau für dieses Format — herunterladen') +
                '<button class="crm-action-btn crm-action-btn-secondary" style="max-width:200px" onclick="EDMS.download(\'' + uuid + '\')"><i class="bi bi-download"></i> ' + this.t('edms_herunterladen','Herunterladen') + '</button></div>';
            return;
        }
        this._showPdf(uuid, extraIds, true);
    },

    _pdfCandidateUrls(uuid, extraIds) {
        const ids = [];
        const add = id => {
            if (!id) return;
            const s = String(id);
            if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(s)) return;
            if (ids.indexOf(s) < 0) ids.push(s);
        };
        add(uuid);
        (extraIds || []).forEach(add);
        const urls = [];
        ids.forEach(id => {
            // Preview zuerst: AID-CVs liegen oft nur als gecachte Vorschau-PDF vor.
            urls.push(this.api.preview + id + '/');
            // CRM-Streamer: Originalbytes, SAMEORIGIN, Mount-Fallbacks (office/public).
            urls.push(this.api.edmsFile + id + '/');
            urls.push(this.api.file + id + '/');
            urls.push(this.api.file + id + '/?download=1');
        });
        return urls;
    },

    _revokePdfBlob() {
        if (this._pdfBlobUrl) {
            try { URL.revokeObjectURL(this._pdfBlobUrl); } catch (e) {}
            this._pdfBlobUrl = '';
        }
    },

    _looksLikePdf(buf, contentType) {
        const ct = (contentType || '').toLowerCase();
        if (ct.indexOf('application/pdf') >= 0) return true;
        if (ct.indexOf('json') >= 0 || ct.indexOf('text/html') >= 0) return false;
        if (!buf || buf.byteLength < 5) return false;
        const head = String.fromCharCode.apply(null, new Uint8Array(buf.slice(0, 5)));
        return head === '%PDF-';
    },

    _showPdf(uuid, extraIds, officePreview) {
        const body = document.getElementById('edms-vorschau-body');
        if (!body) return;
        this._revokePdfBlob();
        this._lastFileErr = null;
        body.innerHTML = '<div class="crm-list-loading"><i class="bi bi-arrow-repeat"></i> ' + this.t('edms_vorschau_laedt','Vorschau wird erzeugt…') + '</div>';
        const urls = officePreview
            ? [this.api.preview + uuid + '/'].concat(this._pdfCandidateUrls(uuid, extraIds))
            : this._pdfCandidateUrls(uuid, extraIds);
        const tryNext = (i) => {
            if (i >= urls.length) {
                const meta = this._previewDocMeta || {};
                const err = this._lastFileErr || {};
                const win = meta.win_path || meta.unc_path || '';
                const linux = err.linux_path || err.linux_guess || '';
                const isPerm = (err._status === 403) || (err.error || '').toLowerCase().indexOf('recht') >= 0;
                const msg = isPerm
                    ? this.t('edms_datei_keine_rechte', 'PDF gefunden, aber der Server darf sie nicht lesen (chmod/chown auf /mnt/office)')
                    : this.t('edms_datei_nicht_im_viewer', 'PDF konnte nicht geladen werden (Datei auf dem Share nicht erreichbar)');
                const hint = err.hint ? '<div class="edms-vorschau-pathhint" style="font-size:11px;color:var(--text-muted);max-width:90%">' + this._esc(err.hint) + '</div>' : '';
                const pathHint = [win, linux].filter(Boolean).map(p =>
                    '<div class="edms-vorschau-pathhint" style="font-size:11px;color:var(--text-muted);max-width:90%;word-break:break-all">' +
                    this._esc(p) + '</div>'
                ).join('');
                const sib = (err.walk_siblings || []).slice(0, 8).map(s => this._esc(s)).join(', ');
                const walkHint = err.walk_missing
                    ? '<div class="edms-vorschau-pathhint" style="font-size:11px;color:var(--text-muted);max-width:90%">bricht ab bei: <b>' +
                      this._esc(err.walk_missing) + '</b>' +
                      (err.walk_last_ok ? ' (letzter Ordner: ' + this._esc(err.walk_last_ok) + ')' : '') +
                      (sib ? '<br>daneben: ' + sib : '') + '</div>'
                    : '';
                body.innerHTML = '<div class="edms-vorschau-msg"><i class="bi bi-exclamation-triangle"></i>' +
                    msg + hint + pathHint + walkHint +
                    '<button class="crm-action-btn crm-action-btn-secondary" style="max-width:200px" onclick="EDMS.download(\'' + this._esc(uuid) + '\')">' +
                    '<i class="bi bi-download"></i> ' + this.t('edms_herunterladen','Herunterladen') + '</button></div>';
                return;
            }
            fetch(urls[i], { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
                .then(r => r.arrayBuffer().then(buf => ({ r: r, buf: buf })))
                .then(pack => {
                    if (!pack.r.ok) {
                        if (urls[i].indexOf(this.api.edmsFile) === 0) {
                            try {
                                this._lastFileErr = JSON.parse(new TextDecoder().decode(new Uint8Array(pack.buf)));
                                this._lastFileErr._status = pack.r.status;
                            } catch (e) {}
                        }
                        tryNext(i + 1);
                        return;
                    }
                    const ct = pack.r.headers.get('content-type') || '';
                    if (!this._looksLikePdf(pack.buf, ct)) { tryNext(i + 1); return; }
                    const blob = new Blob([pack.buf], { type: 'application/pdf' });
                    this._pdfBlobUrl = URL.createObjectURL(blob);
                    body.innerHTML = '<iframe class="edms-vorschau-frame" src="' + this._pdfBlobUrl + '"></iframe>';
                })
                .catch(() => tryNext(i + 1));
        };
        tryNext(0);
    },

    // Mail-Anhang im Dokument-Reiter öffnen (wechselt automatisch dorthin)
    openAttachmentInDoc(aid) {
        const a = (this._attachStore || {})[aid];
        if (!a) return;
        this._currentAttachment = a;
        // Reiter-Kopf zeigt den Anhang-Namen + Download
        const head = document.getElementById('edms-vorschau-head');
        if (head) {
            const ext = (a.filename.split('.').pop() || '').toUpperCase();
            head.innerHTML = '<span class="edms-vorschau-fname"><i class="bi bi-paperclip"></i> ' + this._esc(a.filename) + '</span>' +
                '<span class="edms-vorschau-format">' + ext + '</span>' +
                '<div class="edms-vorschau-actions"><a class="edms-vorschau-actbtn" title="' + this.t('edms_herunterladen','Herunterladen') + '" href="' + a.url + '" target="_blank"><i class="bi bi-download"></i></a></div>';
        }
        // Auf Dokument-Reiter wechseln
        this.vorschauTab = 'dokument';
        document.querySelectorAll('.edms-vorschau-tab').forEach(t => t.classList.remove('active'));
        const el = document.getElementById('edms-vtab-dokument');
        if (el) el.classList.add('active');
        this.renderVorschauTab(null, '');
    },

    // Prüft, ob die Anhang-Preview ein PDF lieferte; bei 415 -> Download-Hinweis
    _attachFrameCheck(frame) {
        const a = this._currentAttachment;
        if (!a) return;
        // Wir können den iframe-Inhalt bei same-origin lesen; bei 415 ist es JSON
        try {
            const doc = frame.contentDocument;
            if (doc && doc.body && doc.body.innerText && doc.body.innerText.indexOf('"kind": "download"') >= 0) {
                const body = document.getElementById('edms-vorschau-body');
                if (body) body.innerHTML = '<div class="edms-vorschau-msg"><i class="bi ' + this._attachIcon(a.filename) + '"></i>' +
                    this._esc(a.filename) + '<br><span style="font-size:11px;color:var(--text-muted)">' + this.t('edms_att_kein_preview','Dieses Format kann nicht angezeigt werden') + '</span>' +
                    '<a class="crm-action-btn crm-action-btn-secondary" style="max-width:220px" href="' + a.url + '" target="_blank"><i class="bi bi-download"></i> ' + this.t('edms_herunterladen','Herunterladen') + '</a></div>';
            }
        } catch (e) { /* cross-origin o. ä. — iframe zeigt was es kann */ }
    },

    switchVorschauTab(tab) {
        this.vorschauTab = tab;
        document.querySelectorAll('.edms-vorschau-tab').forEach(t => t.classList.remove('active'));
        const el = document.getElementById('edms-vtab-' + tab);
        if (el) el.classList.add('active');
        // Mails/Aufnahmen hängen an der Person, nicht am Dokument -> auch ohne Datei laden
        if (tab === 'mails') {
            // War eine Mail offen (z. B. vor dem Anhang-Klick)? -> direkt deren Body zeigen
            if (this._currentMail) {
                const body = document.getElementById('edms-vorschau-body');
                const head = document.getElementById('edms-vorschau-head');
                if (head) head.innerHTML = '<span class="edms-vorschau-fname"><i class="bi bi-envelope"></i> ' + this.t('edms_mails','Mails') + '</span>';
                if (body) body.innerHTML = '<div class="edms-mail-detail" id="edms-mail-detail"></div>';
                this._mailData = this._akteMails || this._mailData;
                this.openMail(this._currentMailIdx);
                return;
            }
            this.renderVorschauTab(this.currentDocUuid, '');
            return;
        }
        if (this.currentDocUuid) this.loadVorschau(this.currentDocUuid);
        else this.renderVorschauTab(null, '');
    },

    // ── Mails-Reiter: Mailbox-Mails der gewählten Person ──────────────
    loadPersonMails() {
        const body = document.getElementById('edms-vorschau-body');
        const head = document.getElementById('edms-vorschau-head');
        if (!body) return;
        if (head) head.innerHTML = '<span class="edms-vorschau-fname"><i class="bi bi-envelope"></i> ' + this.t('edms_mails','Mails') + '</span>';
        if (!this.currentOwner) {
            body.innerHTML = '<div class="edms-vorschau-msg"><i class="bi bi-person"></i>' + this.t('edms_mails_keine_person','Bitte links eine Person wählen') + '</div>';
            return;
        }
        body.innerHTML = '<div class="edms-mail-wrap"><div class="edms-mail-list" id="edms-mail-list"><div class="crm-list-loading">' + this.t('laden','Lade…') + '</div></div><div class="edms-mail-detail" id="edms-mail-detail"></div></div>';
        const url = this.api.personMails + encodeURIComponent(this.currentOwner.crm_id) + '/mails/?size=100';
        fetch(url, { headers: {'X-Requested-With':'XMLHttpRequest'} })
            .then(r => r.json())
            .then(d => this._renderMailList(d))
            .catch(() => { const l = document.getElementById('edms-mail-list'); if (l) l.innerHTML = '<div class="edms-vorschau-msg"><i class="bi bi-exclamation-triangle"></i>' + this.t('fehler_beim_laden','Fehler beim Laden') + '</div>'; });
    },

    _renderMailList(d) {
        const list = document.getElementById('edms-mail-list');
        if (!list) return;
        const mails = (d && d.results) || [];
        if (!mails.length) {
            list.innerHTML = '<div class="edms-vorschau-msg"><i class="bi bi-inbox"></i>' + this.t('edms_mails_keine','Keine Mails zu dieser Person gefunden') + '</div>';
            return;
        }
        this._mailData = mails;
        this._ownerAddrs = d.addresses || [];
        const cnt = (d.total || mails.length) + ' ' + this.t('edms_mails','Mails');
        const addr = (d.addresses || []).length + ' ' + this.t('edms_mails_adressen','Adressen');
        let html = '<div class="edms-mail-listhead"><i class="bi bi-envelope"></i> ' + cnt + ' · ' + addr + '</div>';
        html += mails.map((m, i) => {
            const dir = this._mailDir(m);
            const dt = m.date ? this._mailDate(m.date) : '';
            const clip = m.has_attachments ? '<i class="bi bi-paperclip edms-mail-clip"></i>' : '';
            const peer = this._mailPeer(m, dir);
            return '<div class="edms-mail-row" data-i="' + i + '" onclick="EDMS.openMail(' + i + ')">' +
                this._typeIconHtml('mail', this._kindIcon('mail')) +
                '<div class="edms-mail-rowmain">' +
                '<div class="edms-mail-subject">' + this._esc(m.subject) + '</div>' +
                '<div class="edms-mail-peer">' + this._esc(peer) + '</div></div>' +
                '<div class="edms-mail-meta">' + dt + clip + '</div></div>';
        }).join('');
        list.innerHTML = html;
    },

    openMail(i) {
        const m = (this._mailData || [])[i];
        if (!m) return;
        this._currentMail = m;           // für Rücksprung vom Dokument-Reiter
        this._currentMailIdx = i;
        document.querySelectorAll('.edms-mail-row').forEach(r => r.classList.toggle('active', r.dataset.i == i));
        const det = document.getElementById('edms-mail-detail');
        if (!det) return;
        det.innerHTML = '<div class="crm-list-loading">' + this.t('laden','Lade…') + '</div>';
        const p = new URLSearchParams({ account: m.account, folder: m.folder });
        if (m.uid) p.set('uid', m.uid); else p.set('message_id', m.message_id);
        fetch(this.api.mailView + '?' + p, { headers: {'X-Requested-With':'XMLHttpRequest'} })
            .then(r => r.json())
            .then(md => this._renderMailDetail(md, m))
            .catch(() => { det.innerHTML = '<div class="edms-vorschau-msg"><i class="bi bi-exclamation-triangle"></i>' + this.t('fehler_beim_laden','Fehler') + '</div>'; });
    },

    _renderMailDetail(md, m) {
        const det = document.getElementById('edms-mail-detail');
        if (!det || !md || !md.ok) { if (det) det.innerHTML = '<div class="edms-vorschau-msg"><i class="bi bi-exclamation-triangle"></i>' + this.t('fehler_beim_laden','Fehler') + '</div>'; return; }
        const initials = this._initials(md.from_addr);
        const dt = md.date ? this._mailDate(md.date, true) : '';
        // Anhang-Leiste
        let att = '';
        if (md.attachments && md.attachments.length) {
            att = '<div class="edms-mail-attachbar">' + md.attachments.map(a => {
                const p = new URLSearchParams({ account: m.account, folder: m.folder, index: a.index });
                if (m.uid) p.set('uid', m.uid); else p.set('message_id', m.message_id);
                const url = this.api.mailAttach + '?' + p;
                const pv = this.api.mailAttachPreview + '?' + p;
                const kb = a.size_bytes ? Math.round(a.size_bytes/1024) + ' KB' : '';
                const icon = this._attachIcon(a.filename);
                this._attachStore = this._attachStore || {};
                const aid = 'att_' + a.index + '_' + (m.uid || '');
                this._attachStore[aid] = { url: url, preview: pv, filename: a.filename };
                return '<div class="edms-mail-attach" title="' + this._esc(a.filename) + '" onclick="EDMS.openAttachmentInDoc(\'' + aid + '\')">' +
                    '<i class="bi ' + icon + '"></i><div class="edms-mail-attmeta"><div class="edms-mail-attname">' + this._esc(a.filename) + '</div><div class="edms-mail-attsize">' + kb + ' · ' + this.t('edms_att_oeffnen','öffnen') + '</div></div></div>';
            }).join('') + '</div>';
        }
        // Body als iframe via srcdoc (isoliert, Outlook-Look bleibt)
        const bodyHtml = md.body_html || ('<pre style="white-space:pre-wrap;font-family:sans-serif;font-size:13px">' + this._esc(md.body_plain || '') + '</pre>');
        const srcdoc = this._esc(bodyHtml);
        det.innerHTML =
            '<div class="edms-mail-dhead">' +
            '<div class="edms-mail-avatar">' + initials + '</div>' +
            '<div class="edms-mail-dfrom"><div class="edms-mail-dname">' + this._esc(this._nameOf(md.from_addr)) + '</div><div class="edms-mail-daddr">' + this._esc(this._addrOf(md.from_addr)) + '</div></div>' +
            '<div class="edms-mail-ddate">' + dt + '<div class="edms-mail-dfolder">' + this._esc(md.folder) + '</div></div></div>' +
            '<div class="edms-mail-dto"><span>' + this.t('edms_mail_an','An') + ':</span> ' + this._esc(md.to_addr) + (md.cc_addr ? '<br><span>Cc:</span> ' + this._esc(md.cc_addr) : '') + '</div>' +
            '<div class="edms-mail-dsubject">' + this._esc(md.subject) + '</div>' +
            att +
            '<iframe class="edms-mail-bodyframe" srcdoc="' + srcdoc + '"></iframe>';
    },

    // Mail-Helfer
    _mailDir(m) {
        const addrs = (this.currentOwner && this._ownerAddrs) || [];
        // grobe Heuristik: steht eine Owner-Adresse im from -> empfangen, sonst gesendet
        const from = (m.from_addr || '').toLowerCase();
        for (const a of addrs) { if (from.indexOf(a.toLowerCase()) >= 0) return 'in'; }
        return 'out';
    },
    _mailPeer(m, dir) {
        return dir === 'out' ? (this._addrOf(m.to_addr) || m.to_addr) : (this._addrOf(m.from_addr) || m.from_addr);
    },
    _mailDate(s, withTime) {
        try { const d = new Date(s); const dd = String(d.getDate()).padStart(2,'0'); const mm = String(d.getMonth()+1).padStart(2,'0'); const base = dd+'.'+mm+'.'+d.getFullYear(); if (!withTime) return base; const hh = String(d.getHours()).padStart(2,'0'); const mi = String(d.getMinutes()).padStart(2,'0'); return base+' '+hh+':'+mi; } catch(e) { return (s||'').substring(0,10); }
    },
    _nameOf(h) { const m = (h||'').match(/^\s*"?([^"<]+?)"?\s*</); return m ? m[1].trim() : this._addrOf(h); },
    _addrOf(h) { const m = (h||'').match(/<([^>]+)>/); return m ? m[1].trim() : (h||'').trim(); },
    _initials(h) { const n = this._nameOf(h); const p = n.split(/[\s.@]+/).filter(Boolean); return ((p[0]||'?')[0] + (p[1]||'')[0]||'').toUpperCase(); },
    _attachIcon(fn) { const e = (fn.split('.').pop()||'').toLowerCase(); if (e==='pdf') return 'bi-file-earmark-pdf'; if (['doc','docx'].includes(e)) return 'bi-file-earmark-word'; if (['xls','xlsx'].includes(e)) return 'bi-file-earmark-excel'; if (['jpg','jpeg','png','gif'].includes(e)) return 'bi-file-earmark-image'; return 'bi-file-earmark'; },
    _esc(s) { return (s==null?'':String(s)).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); },


    download(uuid) {
        window.open(this.api.edmsFile + uuid + '/?download=1', '_blank');
    },
    openTab(uuid) {
        if (this._pdfBlobUrl) {
            window.open(this._pdfBlobUrl, '_blank');
            return;
        }
        window.open(this.api.edmsFile + uuid + '/', '_blank');
    },

    copyPath(btn, path) {
        const clean = path.replace(/\\\\/g,'\\');
        navigator.clipboard.writeText(clean).then(() => {
            btn.classList.add('copied');
            const ico = btn.querySelector('i');
            if (ico) ico.className = 'bi bi-check-lg';
            setTimeout(() => { btn.classList.remove('copied'); if (ico) ico.className = 'bi bi-clipboard'; }, 1500);
        });
    },

    renderPagination(total, pages, current) {
        const el = document.getElementById('edms-pagination');
        if (!el || !pages || pages <= 1) { if (el) el.innerHTML = ''; return; }
        let html = '';
        if (current > 1) html += '<button class="crm-page-btn" onclick="EDMS.loadCol1(' + (current-1) + ')">‹</button>';
        const start = Math.max(1, current - 2), end = Math.min(pages, current + 2);
        for (let i = start; i <= end; i++)
            html += '<button class="crm-page-btn ' + (i===current?'active':'') + '" onclick="EDMS.loadCol1(' + i + ')">' + i + '</button>';
        if (current < pages) html += '<button class="crm-page-btn" onclick="EDMS.loadCol1(' + (current+1) + ')">›</button>';
        el.innerHTML = html;
    },
    _clearPagination() { const el = document.getElementById('edms-pagination'); if (el) el.innerHTML = ''; },

    bindResizers() {
        document.querySelectorAll('.edms-resizer').forEach(rz => {
            rz.addEventListener('mousedown', e => {
                e.preventDefault();
                const target = document.getElementById(rz.dataset.target);
                if (!target) return;
                rz.classList.add('dragging');
                const startX = e.clientX, startW = target.offsetWidth;
                const move = ev => { target.style.flex = '0 0 ' + Math.max(140, startW + (ev.clientX - startX)) + 'px'; };
                const up = () => { rz.classList.remove('dragging'); document.removeEventListener('mousemove', move); document.removeEventListener('mouseup', up); };
                document.addEventListener('mousemove', move);
                document.addEventListener('mouseup', up);
            });
        });
    },

    _resetCol2() {
        const panel = document.getElementById('edms-akte-panel');
        if (panel) panel.innerHTML = '<div class="crm-detail-empty" style="flex:1;justify-content:center">' +
            '<i class="bi bi-folder2-open"></i><p>' +
            (this.mode === 'personen' ? this.t('edms_person_waehlen','Person links wählen') : this.t('edms_dokument_waehlen','Dokument links wählen')) +
            '</p></div>';
    },
    _resetCol3() {
        const body = document.getElementById('edms-vorschau-body');
        const pfad = document.getElementById('edms-pfad-zeile');
        const head = document.getElementById('edms-vorschau-head');
        if (head) head.innerHTML = '';
        if (pfad) pfad.style.display = 'none';
        if (body) body.innerHTML = '<div class="edms-vorschau-empty"><i class="bi bi-file-earmark-text"></i><p>' + this.t('edms_dokument_waehlen','Dokument wählen') + '</p></div>';
    },

    _initials(name) { return (name || '').split(' ').map(w => w[0] || '').slice(0,2).join('').toUpperCase(); },
    _setCount(id, n) { const el = document.getElementById(id); if (el) el.textContent = '(' + (n||0).toLocaleString() + ')'; },
    _col1Loading() { const l = document.getElementById('edms-col1-list'); if (l) l.innerHTML = '<div class="crm-list-loading"><i class="bi bi-arrow-repeat"></i> ' + this.t('laden','Lade...') + '</div>'; },
    _col1Error()   { const l = document.getElementById('edms-col1-list'); if (l) l.innerHTML = '<div class="crm-list-loading"><i class="bi bi-exclamation-triangle"></i> ' + this.t('fehler_beim_laden','Fehler beim Laden') + '</div>'; },
};

window.EDMS = EDMS;
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('edms-three-col')) EDMS.init();
});
document.addEventListener('languageChanged', () => {
    if (window.EDMS && document.getElementById('edms-three-col')) EDMS.refreshI18n();
});

