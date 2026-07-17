/* ============================================================
   ABpE CRM — mod-crm-pbx.js
   Telefon-Cockpit (HUD, Parken, Konferenz, Queues, Anrufliste,
   Statistik, Voicemail) — spricht die /crm/api/telefon/* Endpoints.
   Muster wie mod-edms.js: Namespace-Objekt + t()/csrf().
   Alle sichtbaren Texte via PBX.t('pbx_*') -> window.i18nData.
   ============================================================ */

const PBX = {
    cfg:  {},
    tab:  'hud',
    ext:  '',
    data: { extensions: [], channels: [], parked: [], confbridge: [], queues: [], voicemail: [] },
    _extFilter: 'free',
    _extGroups: null,
    _pollTimer: null,
    _tickTimer: null,
    _call: null,          // aktiver 1:1-Ruf (Kunde-Koenig): {name, nr}
    _atxfer: null,        // Ruecksprache-State: {origChannel, exten} -- persistiert ueber Polls
    _confRoomsLoaded: false,
    _confRoomsList: null,  // Cache: alle konfigurierten Konferenzraeume
    _confNotes: {},        // Konferenz-Notizen: {[room]: {open, contacts:[{crm_id,name,kind}], noteType}}

    api: {
        hud:        '/crm/api/telefon/hud/',
        dial:       '/crm/api/telefon/dial/',
        call:       '/crm/api/telefon/call/',
        hangup:     '/crm/api/telefon/hangup/',
        redirect:   '/crm/api/telefon/redirect/',
        transferTargets: '/crm/api/telefon/transfer-targets/',
        park:       '/crm/api/telefon/park/',
        presence:   '/crm/api/telefon/presence/',
        steal:      '/crm/api/telefon/steal/',
        barge:      '/crm/api/telefon/barge/',
        record:     '/crm/api/telefon/record/',
        dnd:        '/crm/api/telefon/dnd/',
        fwd:        '/crm/api/telefon/fwd/',
        fwdSet:     '/crm/api/telefon/fwd/set/',
        confDetail: '/crm/api/conf/detail/',
        confMember: '/crm/api/conf/member/',
        confLock:   '/crm/api/conf/lock/',
        confInvite: '/crm/api/conf/invite/',
        conference: '/crm/api/telefon/conference/',
        pullPartner:'/crm/api/conf/pull-partner/',
        joinSelf:   '/crm/api/conf/join-self/',
        conferenceRooms: '/crm/api/telefon/conference-rooms/',
        queues:     '/crm/api/telefon/queues/',
        queueMember:'/crm/api/telefon/queue-member/',
        voicemail:  '/crm/api/telefon/voicemail/',
        vmboxes:    '/crm/api/telefon/vmboxes/',
        stats:      '/crm/api/telefon/stats/',
        cdr:        '/crm/api/telefon/cdr/',
        contacts:   '/crm/api/softphone/contacts/',
        protokoll:  '/crm/api/telefon/protokoll/',
        notiz:      '/crm/api/telefon/notiz/',
        wavnotes:          '/crm/api/telefon/wavnotes/',
        wavnoteAudio:      '/crm/api/telefon/wavnotes/audio/',
        wavnoteTranscribe: '/crm/api/telefon/wavnotes/transcribe/',
        wavnoteSave:       '/crm/api/telefon/wavnotes/save/',
        cdrResolve:        '/crm/api/cdr/resolve/',
        wavnoteArchive:    '/crm/api/telefon/wavnotes/archive/',
        blindTransfer: '/crm/api/telefon/blind-transfer/',
        atxfer:        '/crm/api/telefon/atxfer/',
        cancelAtxfer:  '/crm/api/telefon/cancel-atxfer/',
        noteSave:      '/crm/api/note/save/',
        berater:       '/crm/api/berater/',
        kunden:        '/crm/api/kunden/',
        searchAll:     '/edms/api/search_all/',
    },

    /* ---- Helfer ---- */
    t(key, fb) { return (window.i18nData && window.i18nData[key]) || fb || key; },
    csrf() { return (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || ''; },
    esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); },
    fmtDur(sec) { sec = parseInt(sec || 0, 10); const m = Math.floor(sec / 60), s = sec % 60; return m + ':' + String(s).padStart(2, '0'); },
    $(id) { return document.getElementById(id); },

    async get(url) {
        const r = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
        return r.json();
    },
    async post(url, body) {
        const r = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrf(), 'X-Requested-With': 'XMLHttpRequest' },
            body: JSON.stringify(body || {}),
        });
        return r.json();
    },

    toast(msg) {
        let t = this.$('pbx-toast');
        if (!t) { t = document.createElement('div'); t.id = 'pbx-toast'; t.className = 'pbx-toast'; document.body.appendChild(t); }
        t.innerHTML = msg;
        t.classList.add('show');
        clearTimeout(this._toastT);
        this._toastT = setTimeout(() => t.classList.remove('show'), 2200);
    },

    /* ---- Init ---- */
    init() {
        this.cfg = window.PBX_CONFIG || {};
        this.ext = this.cfg.extension || '12';
        this.bindTabs();
        this.bindDial();
        const de = this.$('pbx-dial-ext'); if (de) de.value = this.ext;
        this.poll();                          // sofort
        this._pollTimer = setInterval(() => this.poll(), 4000);
        this._tickTimer = setInterval(() => this.tick(), 1000);
        if (window.applyTranslations) window.applyTranslations();
    },

    bindTabs() {
        document.querySelectorAll('#pbx-root .pbx-tabbtn').forEach(btn => {
            btn.addEventListener('click', () => this.showTab(btn.getAttribute('data-tab'), btn));
        });
    },

    showTab(tab, btn) {
        this.tab = tab;
        document.querySelectorAll('#pbx-root .pbx-tabbtn').forEach(b => b.classList.remove('pbx-tab-active'));
        if (btn) btn.classList.add('pbx-tab-active');
        document.querySelectorAll('#pbx-root .pbx-panel').forEach(p => p.style.display = 'none');
        const panel = this.$('pbx-panel-' + tab);
        if (panel) panel.style.display = '';
        if (tab === 'cdr') this.loadCdr();
        if (tab === 'stats') this.loadStats();
        if (tab === 'vm') this.loadVm();
        if (tab === 'wavnotes') this.loadWavNotes();
        if (tab === 'konf' && this.meetmeSwitchSubtab) this.meetmeSwitchSubtab('planung');
    },

    /* ---- Polling ---- */
    async poll() {
        try {
            const res = await this.get(this.api.hud);
            if (res && res.success) {
                this.data = res.data;
                this.renderHud();
                this.renderPark();
                this.renderKonf();
                this.renderQueues();
                this.updateCount();
            }
        } catch (e) { /* still */ }
    },

    updateCount() {
        const busy = (this.data.channels || []).length;
        const el = this.$('pbx-call-count');
        if (el) el.textContent = busy + ' ' + this.t('pbx_active_calls', 'aktiv');
    },

    tick() {
        // laufende Dauer-Anzeigen hochzaehlen (Kacheln, Park-Countdown)
        document.querySelectorAll('#pbx-root [data-tick]').forEach(el => {
            let v = parseInt(el.getAttribute('data-tick') || '0', 10) + 1;
            el.setAttribute('data-tick', v);
            el.textContent = this.fmtDur(v);
        });
        document.querySelectorAll('#pbx-root [data-countdown]').forEach(el => {
            let v = parseInt(el.getAttribute('data-countdown') || '0', 10) - 1;
            if (v < 0) v = 0;
            el.setAttribute('data-countdown', v);
            el.textContent = this.fmtDur(v);
            if (v <= 10) el.classList.add('pbx-urgent');
        });
    },

    /* ======================= HUD ======================= */
    renderHud() {
        this._renderCallStrip();
        this._fillDialExt();
        // Nebenstellen-Grid
        this._renderExtFilter();
        const grid = this.$('pbx-extgrid');
        if (grid) {
            let exts = this.data.extensions || [];
            exts = this._applyExtFilter(exts);
            const chBy = {};
            (this.data.channels || []).forEach(c => { if (c.extension) chBy[c.extension] = c; });
            grid.innerHTML = exts.map(e => this._extCard(e, chBy[e.ext])).join('') ||
                '<div class="pbx-empty" data-i18n="pbx_no_ext">' + this.t('pbx_no_ext', 'Keine Nebenstellen') + '</div>';
        }
    },

    _callKey(ch) { return String(ch == null ? '' : ch).replace(/[^a-zA-Z0-9]/g, '_'); },

    /* ---- Kontakt-Cache (1x beim ersten aktiven Call, wie Softphone) ---- */
    async loadContactsCache() {
        if (this._contactsLoaded || this._contactsLoading) return;
        this._contactsLoading = true;
        this._setContactsHint(true);
        try {
            const res = await this.get(this.api.contacts);
            this._contacts = res.contacts || [];
            this._extmap   = res.pbx_extensions || {};
            this._contactsLoaded = true;
        } catch (e) { /* Matching greift, sobald Cache da ist */ }
        this._contactsLoading = false;
        this._setContactsHint(false);
        this._resolveAllCards();
        this._fillDialExt();
    },
    _setContactsHint(on) {
        document.querySelectorAll('.pbx-ac-contact').forEach(box => {
            if (box.dataset.state === 'set') return;
            const cn = box.querySelector('.pbx-ac-cn');
            if (cn) cn.textContent = on
                ? this.t('pbx_load_contacts', 'Kontakte werden geladen…')
                : this.t('pbx_no_contact', 'Kein Kontakt – über „ändern" suchen');
        });
    },
    _resolveAllCards() {
        (this.data.channels || []).forEach(c => this.ccResolveAuto(c.channel, c.callerid || c.connectednum || ''));
    },
    /* Normierung wie normalize_phone_nr.py / phone-normalize.js (00-Format) */
    _normNr(x) {
        let d = String(x == null ? '' : x).replace(/\D/g, '');
        if (!d) return '';
        if (d.startsWith('00')) return d;
        if (d.startsWith('0'))  return '0049' + d.slice(1);
        if (d.startsWith('49') && d.length > 10) return '00' + d;
        return d;
    },
    /* Gegenstellen-Nummer je Richtung; interne Nst (<=4 Ziffern) -> '' */
    _peerNr(c) {
        const ch = String(c.channel || '');
        const bridge = String(c.bridge_channel || '');
        // ausgehend: gebridgter Kanal ist ein Trunk (…-out-…) / app Dial -> Gegenstelle = connectednum
        const outgoing = /-out-/i.test(bridge) || /trunk|easysip/i.test(bridge);
        let nr = outgoing ? (c.connectednum || c.callerid) : (c.callerid || c.connectednum);
        nr = String(nr || '');
        const d = nr.replace(/\D/g, '');
        if (d.length <= 4) return '';   // interne Nst -> kein Auto-Match
        return nr;
    },
    _findContact(number) {
        if (!number || !this._contacts || !this._contacts.length) return null;
        const t = this._normNr(number);
        if (!t || t.length <= 4) return null;
        return this._contacts.find(c => (c.phones || []).some(p =>
            this._normNr(p.number || p.raw) === t
        )) || null;
    },

    /* ---- Aktive-Gespraeche-Strip (Signatur-Guard: Eingaben bleiben) ---- */
    _renderCallStrip() {
        const strip = this.$('pbx-callstrip');
        if (!strip) return;
        this.loadContactsCache();
        const chans = this.data.channels || [];
        if (this._atxfer && !chans.some(c => c.channel === this._atxfer.origChannel)) {
            this._atxfer = null; // Original-Kanal weg -- Transfer/Hangup ausserhalb der GUI abgeschlossen
        }
        const sig = chans.map(c => c.channel).join('|');
        if (sig === this._callSig) return;
        this._callSig = sig;
        if (!chans.length) {
            strip.innerHTML = '<div class="pbx-empty" data-i18n="pbx_no_calls">' + this.t('pbx_no_calls', 'Keine aktiven Gespräche') + '</div>';
            return;
        }
        strip.innerHTML = chans.map(c => this._callCard(c)).join('');
        this._resolveAllCards();
    },

    _callCard(c) {
        const who     = this.esc(c.calleridname || c.callerid || c.connectednum || c.extension || '—');
        const nr      = this.esc(c.callerid || c.connectednum || '');
        const partner = c.bridge_channel ? this.esc(c.connectedname || c.connectednum || '') : '';
        const dur     = (String(c.duration || '0:0:0')).split(':').reduce((a, b) => a * 60 + (+b), 0) || 0;
        const key     = this._callKey(c.channel);
        const ch      = this.esc(c.channel);
        const ext     = this.esc(c.extension);
        const rec     = this._recOn && this._recOn.has(c.channel);
        const ib = (icon, cls, title, onclick) =>
            `<button class="pbx-ac-btn ${cls}" title="${title}" aria-label="${title}" onclick="${onclick}"><i class="bi ${icon}"></i></button>`;
        return `<div class="pbx-ac pbx-st-busy" data-cc="${key}" data-ch="${ch}" data-ext="${ext}" data-nr="${nr}" data-scope="all">
            <div class="pbx-ac-head">
                <span class="pbx-ac-dot"></span>
                <div class="pbx-ac-id">
                    <div class="pbx-ac-nm">${who}${partner ? ' <i class="bi bi-arrow-right pbx-ac-arr"></i> ' + partner : ''}</div>
                    <div class="pbx-ac-sub">${nr ? nr + ' · ' : ''}${ch}</div>
                </div>
                <div class="pbx-ac-r">
                    <div class="pbx-ac-dur" data-tick="${dur}">${this.fmtDur(dur)}</div>
                    <div class="pbx-ac-owner"></div>
                </div>
            </div>
            <div class="pbx-ac-bar">
                ${ib('bi-telephone-x', 'danger', this.t('pbx_hangup', 'Auflegen'), "PBX.doHangup('" + ch + "')")}
                ${ib('bi-pause-fill', '', this.t('pbx_park', 'Parken'), "PBX.doPark('" + ext + "')")}
                ${ib('bi-arrow-right-circle', '', this.t('pbx_blind', 'Blind-Transfer'), "PBX.ccXfer(this,'blind')")}
                ${ib('bi-people', '', this.t('pbx_atxfer', 'Rücksprache'), "PBX.ccXfer(this,'att')")}
                ${ib('bi-collection', '', this.t('pbx_to_conf', 'In Konferenz legen'), "PBX.ccXfer(this,'conf')")}
                ${ib(rec ? 'bi-record-circle-fill' : 'bi-record-circle', rec ? 'danger pbx-ac-rec' : 'pbx-ac-rec', this.t('pbx_record', 'Aufnahme'), "PBX.ccRecord(this,'" + ch + "')")}
                ${ib('bi-telephone-plus', '', this.t('pbx_second_call', 'Zweitanruf'), "PBX.ccXfer(this,'second')")}
                <span class="pbx-ac-sp"></span>
                <button class="pbx-ac-note-tgl" onclick="PBX.toggleNote(this)"><i class="bi bi-journal-text"></i> ${this.t('pbx_note', 'Notiz')} <i class="bi bi-chevron-down"></i></button>
            </div>
            <div class="pbx-ac-xfer${(this._atxfer && this._atxfer.origChannel === c.channel) ? ' show' : ''}"${(this._atxfer && this._atxfer.origChannel === c.channel) ? ' data-ch="' + ch + '"' : ''}>${(this._atxfer && this._atxfer.origChannel === c.channel) ? this._atxferBoxHtml() : ''}</div>
            <div class="pbx-ac-note" style="display:none">
                <div class="pbx-ac-contact" data-state="" data-crm="" data-kind="">
                    <i class="bi bi-person-dash pbx-ac-cicon"></i>
                    <div class="pbx-ac-ci">
                        <div class="pbx-ac-cn">${this.t('pbx_resolving', 'suche Kontakt…')}</div>
                        <div class="pbx-ac-ct">${nr}</div>
                    </div>
                    <button class="pbx-ac-link" onclick="PBX.ccNoteSearch(this)"><i class="bi bi-pencil"></i> ${this.t('pbx_change', 'ändern')}</button>
                </div>
                <div class="pbx-ac-search">
                    <div class="pbx-ac-scope">
                        <button class="on" data-sc="all" onclick="PBX.ccSetScope(this,'all')">${this.t('pbx_scope_all', 'Alle')}</button>
                        <button data-sc="person" onclick="PBX.ccSetScope(this,'person')">${this.t('pbx_scope_person', 'Personen')}</button>
                        <button data-sc="firma" onclick="PBX.ccSetScope(this,'firma')">${this.t('pbx_scope_firma', 'Firmen')}</button>
                        <button data-sc="ext" onclick="PBX.ccSetScope(this,'ext')">${this.t('pbx_scope_ext', 'Nst/Owner')}</button>
                    </div>
                    <div class="pbx-ac-searchin"><i class="bi bi-search"></i><input placeholder="${this.t('pbx_search_contact', 'Name, Firma oder Nummer…')}" oninput="PBX.ccSearch(this)"></div>
                    <div class="pbx-ac-results"></div>
                </div>
                <label class="pbx-ac-lbl">${this.t('pbx_note_in', 'Stichpunkte (Eingabe)')}</label>
                <textarea class="pbx-ac-in" rows="3" placeholder="${this.t('pbx_note_ph', '- interesse projekt ab august\n- tagessatz 95 ok')}"></textarea>
                <div class="pbx-ac-dsrow">
                    <button class="pbx-ac-ds" onclick="PBX.ccDeepseek(this)"><i class="bi bi-stars"></i> ${this.t('pbx_deepseek', 'DeepSeek formulieren')} <i class="bi bi-arrow-down"></i></button>
                </div>
                <div class="pbx-ac-outhd">
                    <label class="pbx-ac-lbl">${this.t('pbx_note_out', 'DeepSeek-Ausgabe (editierbar)')}</label>
                    <span>
                        <button class="pbx-ac-mini" title="${this.t('pbx_copy_up', 'nach oben kopieren')}" onclick="PBX.ccCopyUp(this)"><i class="bi bi-arrow-up"></i> ${this.t('pbx_up', 'nach oben')}</button>
                        <button class="pbx-ac-mini" title="${this.t('pbx_regen', 'neu generieren')}" onclick="PBX.ccDeepseek(this)"><i class="bi bi-arrow-repeat"></i> ${this.t('pbx_new', 'neu')}</button>
                    </span>
                </div>
                <textarea class="pbx-ac-out" rows="4" placeholder="${this.t('pbx_out_ph', 'Formulierte Notiz erscheint hier – editierbar, bis sie passt …')}"></textarea>
                <div class="pbx-ac-targets">
                    <span class="pbx-ac-tlbl">${this.t('pbx_save_to', 'Speichern an')}:</span>
                    <button class="pbx-ac-chip" data-target="contact" data-on="0" onclick="PBX.ccToggleTarget(this)"><i class="bi bi-person"></i> ${this.t('pbx_person', 'Kontakt')}</button>
                    <button class="pbx-ac-chip" data-target="company" data-on="0" onclick="PBX.ccToggleTarget(this)"><i class="bi bi-building"></i> ${this.t('pbx_firma', 'Firma')}</button>
                    <span class="pbx-ac-type">
                        <select class="pbx-ac-nt">
                            <option value="phone">${this.t('pbx_note_phone', 'Telefonnotiz')}</option>
                            <option value="general">${this.t('pbx_note_generic', 'Notiz')}</option>
                            <option value="meeting">${this.t('pbx_note_meeting', 'Besprechung')}</option>
                        </select>
                    </span>
                    <button class="pbx-ac-save" onclick="PBX.ccSaveNote(this)"><i class="bi bi-check-lg"></i> ${this.t('pbx_save', 'Speichern')}</button>
                </div>
            </div>
        </div>`;
    },

    toggleNote(btn) {
        const card = btn.closest('.pbx-ac');
        const box = card.querySelector('.pbx-ac-note');
        const open = box.style.display === 'none';
        box.style.display = open ? 'block' : 'none';
        btn.classList.toggle('on', open);
        const ch = btn.querySelector('.bi-chevron-down, .bi-chevron-up');
        if (ch) ch.className = open ? 'bi bi-chevron-up' : 'bi bi-chevron-down';
    },

    /* ---- Auto-Match Anrufer-Nr -> Kontakt (aus Cache) ---- */
    ccResolveAuto(channel, nr) {
        const card = document.querySelector('.pbx-ac[data-cc="' + this._callKey(channel) + '"]');
        if (!card) return;
        const ownerEl = card.querySelector('.pbx-ac-owner');
        const owner = this._extmap && this._extmap[card.dataset.ext];
        if (ownerEl) ownerEl.textContent = owner ? (this.t('pbx_owner', 'Owner') + ': ' + owner) : '';
        const box = card.querySelector('.pbx-ac-contact');
        if (!box || box.dataset.state === 'set') return;
        const chan = (this.data.channels || []).find(c => c.channel === channel);
        const peer = chan ? this._peerNr(chan) : nr;
        const ctEl = box.querySelector('.pbx-ac-ct');
        if (ctEl && peer) ctEl.textContent = peer;   // "erkannt aus <Gegenstelle>"
        const hit = this._findContact(peer);
        if (hit) {
            this._ccAssign(card, { crm_id: hit.id || hit.crm_id, name: hit.full_name || hit.name, kind: 'person' }, 'auto');
        } else if (this._contactsLoaded) {
            const cn = box.querySelector('.pbx-ac-cn');
            if (cn) cn.textContent = this.t('pbx_no_contact', 'Kein Kontakt – über „ändern" suchen');
        }
    },
    _ccAssign(card, obj, mode) {
        const box = card.querySelector('.pbx-ac-contact');
        const isAcc = obj.kind === 'firma';
        box.dataset.state = 'set';
        box.dataset.crm = obj.crm_id || '';
        box.dataset.kind = obj.kind || 'person';
        if (isAcc) card.dataset.accountCrm = obj.crm_id || '';
        else       card.dataset.contactCrm = obj.crm_id || '';
        box.querySelector('.pbx-ac-cn').innerHTML = this.esc(obj.name || '—') +
            ' <span class="pbx-ac-badge' + (isAcc ? ' acc' : '') + '">' +
            (isAcc ? this.t('pbx_firma', 'Firma') : this.t('pbx_person', 'Kontakt')) + '</span>';
        box.querySelector('.pbx-ac-ct').textContent = (mode === 'auto')
            ? this.t('pbx_auto', 'automatisch erkannt') : this.t('pbx_manual', 'manuell gewählt');
        const ic = box.querySelector('.pbx-ac-cicon'); if (ic) ic.className = 'bi bi-person-check-fill pbx-ac-cicon';
        const chip = card.querySelector('.pbx-ac-chip[data-target="' + (isAcc ? 'company' : 'contact') + '"]');
        if (chip) { chip.dataset.on = '1'; chip.classList.add('on'); }
        if (mode !== 'auto') this.toast(this.t('pbx_assigned', 'Zugeordnet') + ': ' + (obj.name || ''));
    },

    /* ---- "ändern"-Suche: Cache-first + Fallback (wie Softphone) ---- */
    ccNoteSearch(btn) {
        const card = btn.closest('.pbx-ac');
        const s = card.querySelector('.pbx-ac-search');
        const on = !s.classList.contains('show');
        s.classList.toggle('show', on);
        if (on) { const i = s.querySelector('input'); if (i) setTimeout(() => i.focus(), 40); }
    },
    ccSetScope(btn, scope) {
        const card = btn.closest('.pbx-ac');
        card.dataset.scope = scope;
        card.querySelectorAll('.pbx-ac-scope button').forEach(b => b.classList.toggle('on', b.dataset.sc === scope));
        const inp = card.querySelector('.pbx-ac-searchin input');
        if (inp && inp.value.trim().length >= 2) this.ccSearch(inp);
    },
    ccSearch(inp) {
        const card = inp.closest('.pbx-ac');
        const box = card.querySelector('.pbx-ac-results');
        const q = (inp.value || '').trim();
        const scope = card.dataset.scope || 'all';
        clearTimeout(this._ccTimer);
        if (q.length < 2) { box.innerHTML = ''; box.style.display = 'none'; return; }
        box.innerHTML = '<div class="pbx-ac-hit muted">' + this.t('pbx_searching', 'suche…') + '</div>';
        box.style.display = 'block';
        this._ccTimer = setTimeout(async () => {
            let out = [];
            const esScopes = [];
            if (scope === 'all' || scope === 'person') esScopes.push(['personen', 'person']);
            if (scope === 'all' || scope === 'firma') esScopes.push(['firmen', 'firma']);
            for (const sk of esScopes) {
                try {
                    const r = await this.get(this.api.searchAll + '?q=' + encodeURIComponent(q) + '&scope=' + sk[0] + '&size=10');
                    (r.results || []).forEach(h => out.push({ crm_id: h.id, name: h.title, sub: h.meta || h.company || '', kind: sk[1] }));
                } catch (e) { /* ignore */ }
            }
            if (scope === 'all' || scope === 'ext') {
                const ql = q.toLowerCase();
                Object.keys(this._extmap || {}).forEach(ext => {
                    const nm = this._extmap[ext];
                    if (ext.indexOf(q) !== -1 || String(nm || '').toLowerCase().indexOf(ql) !== -1)
                        out.push({ crm_id: '', name: 'Nst ' + ext + ' · ' + nm, sub: this.t('pbx_owner', 'Owner'), kind: 'ext' });
                });
            }
            this._ccResults = this._ccResults || {};
            const key = card.dataset.cc;
            this._ccResults[key] = out.slice(0, 20);
            this._ccRenderResults(card, this._ccResults[key]);
        }, 150);
    },
    _ccRenderResults(card, list) {
        const box = card.querySelector('.pbx-ac-results');
        if (!list.length) { box.innerHTML = '<div class="pbx-ac-hit muted">' + this.t('pbx_no_hits', 'keine Treffer') + '</div>'; box.style.display = 'block'; return; }
        const icon = k => k === 'firma' ? 'bi-building' : (k === 'ext' ? 'bi-telephone-inbound' : 'bi-person');
        const badge = k => k === 'firma' ? this.t('pbx_firma', 'Firma') : (k === 'ext' ? this.t('pbx_owner', 'Owner') : this.t('pbx_person', 'Kontakt'));
        box.innerHTML = list.map((h, i) =>
            `<div class="pbx-ac-hit" onclick="PBX.ccPick(this,${i})">
                <i class="bi ${icon(h.kind)}"></i>
                <div class="pbx-ac-hi"><div class="pbx-ac-hn">${this.esc(h.name)}</div><div class="pbx-ac-hs">${this.esc(h.sub || '')}</div></div>
                <span class="pbx-ac-badge${h.kind === 'firma' ? ' acc' : ''}">${badge(h.kind)}</span>
            </div>`).join('');
        box.style.display = 'block';
    },
    ccPick(hit, idx) {
        const card = hit.closest('.pbx-ac');
        const list = (this._ccResults || {})[card.dataset.cc] || [];
        const obj = list[idx];
        if (!obj) return;
        if (obj.kind === 'ext' || !obj.crm_id) { this.toast(this.t('pbx_ext_nocrm', 'Nst/Owner hat keinen CRM-Kontakt zum Speichern')); return; }
        this._ccAssign(card, obj, 'manual');
        card.querySelector('.pbx-ac-search').classList.remove('show');
        card.querySelector('.pbx-ac-results').style.display = 'none';
    },
    ccToggleTarget(chip) {
        const on = chip.dataset.on !== '1';
        chip.dataset.on = on ? '1' : '0';
        chip.classList.toggle('on', on);
    },

    /* ---- DeepSeek: Eingabe -> Ausgabe (2 Textareas) ---- */
    async ccDeepseek(btn) {
        const card = btn.closest('.pbx-ac');
        const src = card.querySelector('.pbx-ac-in');
        const dst = card.querySelector('.pbx-ac-out');
        const note = (src.value || '').trim();
        if (!note) { this.toast(this.t('pbx_note_empty', 'Erst Stichpunkte eingeben')); return; }
        const old = btn.innerHTML; btn.innerHTML = '<i class="bi bi-hourglass-split"></i> …';
        try {
            const res = await this.post(this.api.notiz, { note });
            if (res.success && res.text) dst.value = res.text;
            else this.toast(res.error || this.t('pbx_ds_fail', 'DeepSeek fehlgeschlagen'));
        } catch (e) { this.toast(this.t('pbx_ds_fail', 'DeepSeek fehlgeschlagen')); }
        btn.innerHTML = old;
    },
    ccCopyUp(btn) {
        const card = btn.closest('.pbx-ac');
        const src = card.querySelector('.pbx-ac-in');
        const dst = card.querySelector('.pbx-ac-out');
        if (dst.value.trim()) { src.value = dst.value; this.toast(this.t('pbx_copied_up', 'in Eingabe übernommen')); }
    },
    async ccSaveNote(btn) {
        const card = btn.closest('.pbx-ac');
        const out = card.querySelector('.pbx-ac-out').value.trim();
        const inp = card.querySelector('.pbx-ac-in').value.trim();
        const text = out || inp;
        if (!text) { this.toast(this.t('pbx_note_empty', 'Notiz ist leer')); return; }
        const type = card.querySelector('.pbx-ac-nt').value || 'phone';
        const jobs = [];
        card.querySelectorAll('.pbx-ac-chip[data-on="1"]').forEach(chip => {
            const t = chip.dataset.target;
            if (t === 'contact' && card.dataset.contactCrm) jobs.push({ note_text: text, note_type: type, contact_crm_id: card.dataset.contactCrm });
            else if (t === 'company' && card.dataset.accountCrm) jobs.push({ note_text: text, note_type: type, account_crm_id: card.dataset.accountCrm });
        });
        if (!jobs.length) { this.toast(this.t('pbx_no_target', 'Kein Ziel gewählt – Kontakt/Firma zuordnen')); return; }
        let ok = 0;
        for (const body of jobs) {
            try { const r = await this.post(this.api.noteSave, body); if (r && (r.ok || r.success)) ok++; } catch (e) { /* ignore */ }
        }
        if (ok) this.toast(this.t('pbx_note_saved', 'Notiz gespeichert') + ' (' + ok + '×)');
        else this.toast(this.t('pbx_note_fail', 'Speichern fehlgeschlagen'));
    },

    /* ---- Transfer / Zweitanruf (inline) ---- */
    async ccXfer(btn, mode) {
        const card = btn.closest('.pbx-ac');
        const box = card.querySelector('.pbx-ac-xfer');
        const ch = card.dataset.ch;
        const ext = card.dataset.ext;
        box.dataset.ch = ch;
        box.dataset.ext = ext;
        if (mode === 'conf') {
            await this._loadConfRooms();
            const rooms = this._confRoomsList || [];
            const roomBtns = rooms.length
                ? rooms.map(r => '<button class="pbx-ac-xbtn go" onclick="PBX.pullToConf(\'' + this.esc(ext) + '\',\'' + this.esc(r.room_extension) + '\');PBX.ccXferClose(this)"><i class="bi bi-collection"></i> ' + this.esc(r.room_extension) + (r.parties ? ' (' + r.parties + ')' : '') + (r.locked ? ' <i class="bi bi-lock-fill"></i>' : '') + '</button>').join('')
                : '<span class="pbx-ac-noroom">' + this.t('pbx_no_rooms', 'Keine Räume konfiguriert') + '</span>';
            box.innerHTML = '<label>' + this.t('pbx_conf_hint', 'In Konferenz legen — Raum wählen') + '</label><div class="pbx-ac-xrow pbx-ac-roomrow">' + roomBtns + '<button class="pbx-ac-xbtn" onclick="PBX.ccXferClose(this)">' + this.t('pbx_close', 'Zu') + '</button></div>';
            box.classList.add('show');
            return;
        }
        const labels = {
            blind:  this.t('pbx_blind_hint', 'Blind-Transfer — Ziel sofort verbinden'),
            att:    this.t('pbx_att_hint', 'Rücksprache — erst anklingeln, dann verbinden'),
            second: this.t('pbx_second_hint', 'Zweitanruf — Nummer oder Nebenstelle wählen')
        };
        let row = '';
        if (mode === 'blind') row = '<button class="pbx-ac-xbtn go" onclick="PBX.doBlind(this)"><i class="bi bi-arrow-right-circle"></i> ' + this.t('pbx_connect', 'Verbinden') + '</button>';
        else if (mode === 'att') row = '<button class="pbx-ac-xbtn go" onclick="PBX.doAtxfer(this)"><i class="bi bi-telephone"></i> ' + this.t('pbx_consult', 'Rücksprache') + '</button><button class="pbx-ac-xbtn danger" onclick="PBX.cancelAtxfer(this)"><i class="bi bi-x-lg"></i> ' + this.t('pbx_cancel', 'Abbrechen') + '</button>';
        else row = '<button class="pbx-ac-xbtn go" onclick="PBX.secondCall(this)"><i class="bi bi-telephone-plus"></i> ' + this.t('pbx_call', 'Anrufen') + '</button>';
        box.innerHTML = '<label>' + labels[mode] + '</label><input class="pbx-ac-xin" placeholder="' + this.t('pbx_target_ph', 'Nst oder Nummer, z.B. 22') + '"><div class="pbx-ac-xrow">' + row + '<button class="pbx-ac-xbtn" onclick="PBX.ccXferClose(this)">' + this.t('pbx_close', 'Zu') + '</button></div>';
        box.classList.add('show');
        const i = box.querySelector('.pbx-ac-xin'); if (i) i.focus();
    },
    ccXferClose(btn) { const b = btn.closest('.pbx-ac-xfer'); b.classList.remove('show'); b.innerHTML = ''; },
    async doBlind(btn) {
        const box = btn.closest('.pbx-ac-xfer'), exten = (box.querySelector('.pbx-ac-xin').value || '').trim();
        if (!exten) { this.toast(this.t('pbx_target_req', 'Ziel eingeben')); return; }
        const res = await this.post(this.api.blindTransfer, { channel: box.dataset.ch, exten });
        this.toast(res.success ? this.t('pbx_transferred', 'Verbunden — du bist raus') : (res.error || 'Fehler'));
        this.ccXferClose(btn); this.poll();
    },
    async doAtxfer(btn) {
        const box = btn.closest('.pbx-ac-xfer'), exten = (box.querySelector('.pbx-ac-xin').value || '').trim();
        if (!exten) { this.toast(this.t('pbx_target_req', 'Ziel eingeben')); return; }
        const res = await this.post(this.api.atxfer, { channel: box.dataset.ch, exten });
        this.toast(res.success ? this.t('pbx_consulting', 'Rücksprache läuft…') : (res.error || 'Fehler'));
        if (res.success) {
            this._atxfer = { origChannel: box.dataset.ch, exten };
            this._showAtxferComplete(box);
        }
    },

    _atxferBoxHtml() {
        return '<label>' + this.t('pbx_atxfer_active', 'Rücksprache aktiv') + '</label>' +
            '<div class="pbx-ac-xrow">' +
            '<button class="pbx-ac-xbtn go" onclick="PBX.completeAtxfer(this)"><i class="bi bi-check-lg"></i> ' + this.t('pbx_xfer_complete', 'Übergeben') + '</button>' +
            '<button class="pbx-ac-xbtn danger" onclick="PBX.cancelAtxfer(this)"><i class="bi bi-arrow-return-left"></i> ' + this.t('pbx_xfer_back', 'Zurück') + '</button>' +
            '</div>';
    },
    _showAtxferComplete(box) {
        box.innerHTML = this._atxferBoxHtml();
    },

    async completeAtxfer(btn) {
        const box = btn.closest('.pbx-ac-xfer');
        const res = await this.post(this.api.hangup, { channel: box.dataset.ch });
        this.toast(res.success ? this.t('pbx_xfer_done', 'Übergeben') : (res.error || 'Fehler'));
        if (res.success) this._atxfer = null;
        this.ccXferClose(btn); this.poll();
    },
    async cancelAtxfer(btn) {
        const box = btn.closest('.pbx-ac-xfer');
        const res = await this.post(this.api.cancelAtxfer, { channel: box.dataset.ch });
        this.toast(res.success ? this.t('pbx_atxfer_cancelled', 'Rücksprache abgebrochen') : (res.error || 'Fehler'));
        if (res.success) this._atxfer = null;
        this.ccXferClose(btn); this.poll();
    },
    async secondCall(btn) {
        const box = btn.closest('.pbx-ac-xfer'), target = (box.querySelector('.pbx-ac-xin').value || '').trim();
        if (!target) { this.toast(this.t('pbx_target_req', 'Ziel eingeben')); return; }
        const res = await this.post(this.api.dial, { desk: this.ext, target });
        this.toast(res.success ? this.t('pbx_ringing', 'Tischtelefon klingelt') + ' → ' + this.esc(target) : (res.error || 'Fehler'));
        this.ccXferClose(btn);
    },
    async ccRecord(btn, channel) {
        if (!this._recOn) this._recOn = new Set();
        const on = this._recOn.has(channel);
        const res = await this.post(this.api.record, { channel, action: on ? 'stop' : 'start' });
        if (res.success) {
            const ic = btn.querySelector('.bi');
            if (on) { this._recOn.delete(channel); btn.classList.remove('danger'); if (ic) ic.className = 'bi bi-record-circle'; }
            else    { this._recOn.add(channel);    btn.classList.add('danger');    if (ic) ic.className = 'bi bi-record-circle-fill'; }
        }
        this.toast(res.success ? (on ? this.t('pbx_rec_stop', 'Aufnahme gestoppt') : this.t('pbx_rec_start', 'Aufnahme läuft')) : (res.error || 'Fehler'));
    },

    async _loadExtGroups() {
        // Personen-Gruppen laden (aus transfer-targets Endpunkt) und cachen
        if (this._extGroupsLoaded) return;
        this._extGroupsLoaded = true;
        try {
            const res = await this.get(this.api.transferTargets);
            this._extGroups = (res && res.success) ? (res.groups || []) : [];
        } catch (err) {
            this._extGroups = [];
        }
    },
    async _loadConfRooms() {
        // Konferenzraeume (Hints+Live-Config) laden und cachen
        if (this._confRoomsLoaded) return;
        this._confRoomsLoaded = true;
        try {
            const res = await this.get(this.api.conferenceRooms);
            this._confRoomsList = (res && res.success) ? (res.rooms || []) : [];
        } catch (err) {
            this._confRoomsList = [];
        }
    },
    _renderExtFilter() {
        const wrap = this.$('pbx-extfilter');
        if (!wrap) return;
        // Personen-Gruppen lazy nachladen (einmal), dann Filterzeile neu zeichnen
        if (!this._extGroupsLoaded) {
            this._loadExtGroups().then(() => this._renderExtFilter());
        }
        // Basis-Buttons: Freie (default) + Alle, dazwischen die Personen-Gruppen
        const groups = this._extGroups || [];
        const personButtons = groups
            .filter(g => g.name !== 'Nebenstellen')
            .map(g => {
                // Kurzname: erster Vorname, sonst voller Name
                const short = g.name === 'Zentrale' ? 'Zentrale' : (g.name.split(' ')[0] || g.name);
                return { key: 'grp:' + g.name, label: short };
            });
        const buttons = [
            { key: 'free', label: this.t('pbx_filter_free', 'Freie') },
            ...personButtons,
            { key: 'all', label: this.t('pbx_filter_all', 'Alle') },
        ];
        wrap.innerHTML = buttons.map(b => {
            const active = this._extFilter === b.key;
            return `<button class="pbx-extfilter-btn ${active ? 'is-active' : ''}"
                onclick="PBX._extFilter='${b.key.replace(/'/g, "\\'")}';PBX.renderHud()">${this.esc(b.label)}</button>`;
        }).join('');
    },
    _applyExtFilter(exts) {
        const f = this._extFilter || 'free';
        if (f === 'all') return exts;
        if (f === 'free') return exts.filter(e => e.status === 'free');
        if (f.startsWith('grp:')) {
            const groupName = f.slice(4);
            const group = (this._extGroups || []).find(g => g.name === groupName);
            if (!group) return exts;
            const extSet = new Set(group.extensions.map(x => x.ext));
            return exts.filter(e => extSet.has(e.ext));
        }
        return exts;
    },
    _extCard(e, ch) {
        let busy = false, ringing = false;
        if (ch) {
            const cs = (ch.state || '').toLowerCase();
            if (cs.indexOf('ring') !== -1) ringing = true;
            else if (cs === 'up')          busy = true;
        }
        const isMine = (String(e.ext) === String(this.ext));

        // Zustand -> Rand (border) + Punkt (dot) + Statustext
        let border, dot, stTxt, stCls = '';
        if (busy)                     { border = 'busy';    dot = 'busy';    stTxt = this.t('pbx_in_call', 'im Gespräch'); stCls = 'pbx-s-busy'; }
        else if (ringing)             { border = 'ringing'; dot = 'ringing'; stTxt = this.t('pbx_ringing_now', 'klingelt'); stCls = 'pbx-s-ring'; }
        else if (e.offline)           { border = 'away';    dot = 'away';    stTxt = this.t('pbx_offline_vm', 'offline · → Voicemail'); stCls = 'pbx-s-off'; }
        else if (e.status === 'away') { border = 'away';    dot = 'away';    stTxt = this.t('pbx_unregistered', 'nicht registriert (Gerät aus)'); stCls = 'pbx-s-off'; }
        else if (e.dnd)               { border = 'busy';    dot = 'busy';    stTxt = this.t('pbx_dnd_on', 'DND ein') + ' · → VM'; stCls = 'pbx-s-dnd'; }
        else if (e.fwd)               { border = 'ringing'; dot = 'ringing'; stTxt = this.t('pbx_fwd_to', 'umgeleitet') + ' → ' + this.esc(e.fwd); stCls = 'pbx-s-fwd'; }
        else                          { border = 'free';    dot = 'free';    stTxt = this.t('pbx_ready', 'frei · registriert'); }

        // Aktionen
        let acts = `<button class="pbx-act pbx-act-green" title="${this.t('pbx_dial', 'Anrufen')}" onclick="PBX.dialExt('${this.esc(e.ext)}')"><i class="bi bi-telephone"></i></button>`;
        if (ringing) {
            acts += `<button class="pbx-act pbx-act-warn" title="${this.t('pbx_pickup', 'Gespräch holen')}" onclick="PBX.pickup('${this.esc(e.ext)}')"><i class="bi bi-telephone-inbound"></i></button>`;
        }
        if (busy && !isMine) {
            acts += `<button class="pbx-act pbx-act-warn" title="${this.t('pbx_steal', 'Zu mir ziehen')}" onclick="PBX.steal('${this.esc(e.ext)}')"><i class="bi bi-box-arrow-in-down-right"></i></button>`;
            acts += `<button class="pbx-act pbx-act-accent" title="${this.t('pbx_barge', 'Dazuschalten')}" onclick="PBX.barge('${this.esc(e.ext)}')"><i class="bi bi-headset"></i></button>`;
        }
        acts += `<button class="pbx-act ${(e.dnd && !e.offline) ? 'pbx-act-red' : 'pbx-act-gray'}" title="DND" onclick="PBX.toggleDnd('${this.esc(e.ext)}',${!!(e.dnd && !e.offline)})"><i class="bi bi-bell-slash"></i></button>`;
        acts += `<button class="pbx-act ${e.fwd ? 'pbx-act-warn' : 'pbx-act-gray'}" title="${this.t('pbx_fwd', 'Umleitung')}" onclick="PBX.promptFwd('${this.esc(e.ext)}')"><i class="bi bi-arrow-return-right"></i></button>`;
        acts += `<button class="pbx-act ${e.offline ? 'pbx-act-dark' : 'pbx-act-gray'}" title="${this.t('pbx_offline', 'Offline')}" onclick="PBX.toggleOffline('${this.esc(e.ext)}',${!!e.offline})"><i class="bi bi-power"></i></button>`;

        return `<div class="pbx-extcard pbx-st-${border}">
            <div class="pbx-ext-top">
                <span class="pbx-dot pbx-dot-${dot}"></span>
                <span class="pbx-ext-nr">${this.esc(e.ext)}</span>
                <span class="pbx-ext-proto">${this.esc(e.proto)}</span>
            </div>
            <div class="pbx-ext-name">${this.esc(e.name)}</div>
            <div class="pbx-ext-status ${stCls}">${stTxt}</div>
            <div class="pbx-ext-actions">${acts}</div>
        </div>`;
    },

    async toggleOffline(ext, currentlyOff) {
        const res = await this.post(this.api.presence, { extension: ext, offline: !currentlyOff });
        this.toast(res.success ? (ext + ' ' + (!currentlyOff ? this.t('pbx_set_offline', 'offline') : this.t('pbx_set_online', 'online'))) : (res.error || 'Fehler'));
        this.poll();
    },
    async steal(ext) {
        const res = await this.post(this.api.steal, { extension: ext, to: this.ext });
        this.toast(res.success ? this.t('pbx_stolen', 'Gespräch zu dir gezogen') : (res.error || 'Fehler'));
        this.poll();
    },
    async barge(ext) {
        const res = await this.post(this.api.barge, { extension: ext, desk: this.ext, mode: 'B' });
        this.toast(res.success ? this.t('pbx_barged', 'Dazugeschaltet — alle hören dich') : (res.error || 'Fehler'));
    },

    async pickup(ext) {
        const res = await this.post(this.api.dial, { desk: this.ext, target: '**' + ext });
        this.toast(res.success ? this.t('pbx_pickup', 'Gespräch holen') + ' ' + ext : (res.error || 'Fehler'));
        this.poll();
    },

    /* ---- Click-to-Dial (HUD-Kopf) ---- */
    bindDial() {
        const inp = this.$('pbx-dial-input');
        if (inp) {
            inp.addEventListener('input', () => this.dialSearch(inp.value));
            inp.addEventListener('keydown', e => { if (e.key === 'Enter') this.dialGo(); });
        }
        document.addEventListener('click', e => {
            if (!e.target.closest('#pbx-dial-input') && !e.target.closest('#pbx-dial-results')) {
                const r = this.$('pbx-dial-results'); if (r) r.style.display = 'none';
            }
        });
        this.loadContactsCache();
    },
    _fillDialExt() {
        const sel = this.$('pbx-dial-ext');
        if (!sel) return;
        const list = (this.data.extensions || []).filter(e => e.status !== 'away');
        const sig = list.map(e => e.ext).join('|');
        if (sig === this._dialExtSig) return;   // nichts geaendert -> Auswahl unangetastet
        this._dialExtSig = sig;
        const cur = sel.value || this.ext || '';
        list.sort((a, b) => String(a.ext).localeCompare(String(b.ext), undefined, { numeric: true }));
        const nm = e => (this._extmap && this._extmap[e.ext]) || e.name || e.ext;
        sel.innerHTML = list.map(e => `<option value="${this.esc(e.ext)}">${this.esc(e.ext)} · ${this.esc(nm(e))}</option>`).join('')
            || `<option value="${this.esc(this.ext || '')}">${this.esc(this.ext || '—')}</option>`;
        if (list.some(e => String(e.ext) === String(cur))) sel.value = String(cur);
        else if (this.ext && list.some(e => String(e.ext) === String(this.ext))) sel.value = String(this.ext);
    },
    async dialSearch(q) {
        const box = this.$('pbx-dial-results');
        if (!box) return;
        q = (q || '').trim();
        this._dialNr = '';
        clearTimeout(this._dialTimer);
        if (q.length < 2) { box.style.display = 'none'; return; }
        this._dialTimer = setTimeout(async () => {
            let hits = [];
            try {
                const r = await this.get(this.api.searchAll + '?q=' + encodeURIComponent(q) + '&scope=personen&size=8');
                hits = (r && r.results) || [];
            } catch (e) { box.style.display = 'none'; return; }
            box.innerHTML = hits.length ? hits.map(h => {
                const ph = h.phones || [];
                const nr = this.esc(ph[0] || ph[1] || '');
                const disp = this.esc((ph[1] && /\D/.test(ph[1])) ? ph[1] : (ph[0] || ''));
                const nm = this.esc(h.title || nr);
                const co = h.company ? ' <span class="pbx-dial-co">' + this.esc(h.company) + '</span>' : (h.meta ? ' <span class="pbx-dial-co">' + this.esc(h.meta) + '</span>' : '');
                return `<div class="pbx-dial-hit" onclick="PBX.dialPick('${nr}','${nm.replace(/'/g, '')}')"><b>${nm}</b>${co} <span>${disp}</span></div>`;
            }).join('') : `<div class="pbx-dial-hit pbx-empty">${this.t('pbx_no_hits', 'keine Treffer')}</div>`;
            box.style.display = 'block';
        }, 150);
    },
    dialPick(nr, name) {
        const inp = this.$('pbx-dial-input');
        inp.value = name + ' · ' + nr;
        this._dialNr = nr;
        this.$('pbx-dial-results').style.display = 'none';
    },

    async dialGo() {
        const inp = this.$('pbx-dial-input');
        const nr = this._dialNr || (inp ? inp.value.trim() : '');
        const desk = (this.$('pbx-dial-ext') || {}).value || this.ext;
        if (!nr) { this.toast(this.t('pbx_enter_number', 'Nummer oder Kontakt eingeben')); return; }
        const r = this.$('pbx-dial-results'); if (r) r.style.display = 'none';
        const res = await this.post(this.api.dial, { desk, target: nr });
        this.toast(res.success
            ? '<i class="bi bi-telephone-outbound"></i> ' + this.t('pbx_ringing', 'Tischtelefon klingelt') + ' → ' + this.esc(nr)
            : (res.error || this.t('pbx_dial_failed', 'Anruf fehlgeschlagen')));
    },

    async dialExt(target) {
        const desk = (this.$('pbx-dial-ext') || {}).value || this.ext;
        const res = await this.post(this.api.dial, { desk, target });
        this.toast(res.success ? this.t('pbx_ringing', 'Tischtelefon klingelt') + ' → ' + target : (res.error || 'Fehler'));
    },

    /* ---- Anruf-Aktionen ---- */
    async doHangup(channel) {
        const res = await this.post(this.api.hangup, { channel });
        this.toast(res.success ? this.t('pbx_hung_up', 'Aufgelegt') : (res.error || 'Fehler'));
        this.poll();
    },
    async doPark(extension) {
        const res = await this.post(this.api.park, { extension });
        this.toast(res.success ? this.t('pbx_parked', 'Geparkt') : (res.error || 'Fehler'));
        this.poll();
    },
    async pullToConf(extension, room) {
        room = room || '5555';
        const res = await this.post(this.api.pullPartner, { extension, room });
        this.toast(res.success
            ? '<i class="bi bi-box-arrow-in-right"></i> ' + this.t('pbx_in_conf', 'In Konferenz') + ' ' + room + ' ' + this.t('pbx_gelegt', 'gelegt')
            : (res.error || this.t('pbx_no_partner', 'Kein Gesprächspartner')));
        this.poll();
    },
    async toggleDnd(extension, currentlyOn) {
        const res = await this.post(this.api.dnd, { extension, active: !currentlyOn });
        this.toast(res.success ? ('DND ' + extension + ' ' + (!currentlyOn ? this.t('pbx_on', 'ein') : this.t('pbx_off', 'aus'))) : (res.error || 'Fehler'));
        this.poll();
    },
    async promptFwd(extension) {
        const cur = await this.get(this.api.fwd + '?extension=' + encodeURIComponent(extension));
        const target = window.prompt(this.t('pbx_fwd_prompt', 'Umleitungsziel (leer = aus):'), cur.target || '');
        if (target === null) return;
        const res = await this.post(this.api.fwdSet, { extension, target: target.trim() });
        this.toast(res.success ? (target.trim() ? this.t('pbx_fwd_set', 'Umleitung aktiv') : this.t('pbx_fwd_off', 'Umleitung aus')) : (res.error || 'Fehler'));
    },

    /* ======================= PARKEN ======================= */
    renderPark() {
        const p = this.data.parked || [];
        const grid = this.$('pbx-parkgrid');
        if (grid) {
            grid.innerHTML = p.length ? p.map(x => this._parkCard(x)).join('')
                : '<div class="pbx-empty">' + this.t('pbx_no_parked', 'Keine Parkplaetze') + '</div>';
        }
        const occupied = p.filter(x => x.occupied);
        const hudSection = this.$('pbx-hud-park-section');
        const hudGrid = this.$('pbx-hud-parkgrid');
        if (hudSection && hudGrid) {
            if (occupied.length) {
                hudGrid.innerHTML = occupied.map(x => this._parkCard(x)).join('');
                hudSection.style.display = '';
            } else {
                hudGrid.innerHTML = '';
                hudSection.style.display = 'none';
            }
        }
    },
    _parkCard(x) {
        if (!x.occupied) {
            return `<div class="pbx-parkcard pbx-st-free">
                <div class="pbx-park-slot">${this.esc(x.slot)}</div>
                <div class="pbx-park-who">${this.t('pbx_park_free', 'Frei')}</div>
            </div>`;
        }
        const rem = parseInt(x.timeout || 0, 10);
        return `<div class="pbx-parkcard pbx-st-busy">
            <div class="pbx-park-slot">${this.esc(x.slot)}</div>
            <div class="pbx-park-who">${this.esc(x.caller_name || x.caller_id)}</div>
            <div class="pbx-park-meta">${this.t('pbx_timeout', 'Timeout')}: <span data-countdown="${rem}">${this.fmtDur(rem)}</span></div>
            <div style="display:flex;gap:6px;margin-top:6px">
                <button class="pbx-act pbx-act-green" style="flex:1" title="${this.t('pbx_pickup', 'Abholen')}" onclick="PBX.pickupPark('${this.esc(x.slot)}')"><i class="bi bi-telephone-inbound"></i> ${this.t('pbx_pickup', 'Abholen')}</button>
                <button class="pbx-act pbx-act-gray" style="flex:1" title="${this.t('pbx_transfer', 'Uebergeben')}" onclick="PBX.showTransferModal('park','${this.esc(x.slot)}','${this.esc(x.caller_name || x.caller_id)}')"><i class="bi bi-arrow-right-circle"></i> ${this.t('pbx_transfer', 'Uebergeben')}</button>
            </div>
        </div>`;
    },
    async showTransferModal(sourceType, sourceId, callerLabel) {
        const res = await this.get(this.api.transferTargets);
        if (!res || !res.success) { this.toast(res && res.error || 'Fehler beim Laden'); return; }
        const groups = res.groups || [];
        if (!groups.length) { this.toast(this.t('pbx_no_targets', 'Keine Ziele verfuegbar')); return; }

        this._transferCtx = { sourceType, sourceId };
        this._transferGroups = groups;
        this._transferActiveTab = 0;
        this._transferSelected = null;

        const old = document.getElementById('pbx-transfer-modal');
        if (old) old.remove();

        const modal = document.createElement('div');
        modal.id = 'pbx-transfer-modal';
        modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.45);display:flex;align-items:center;justify-content:center;z-index:2000';
        modal.innerHTML = `
            <div style="background:var(--surface-2,#fff);border-radius:12px;border:1px solid var(--border-color,#ddd);width:380px;max-width:95%;padding:1.25rem">
                <div style="font-size:16px;font-weight:600;margin-bottom:4px">${this.t('pbx_transfer_title','An Nebenstelle uebergeben')}</div>
                <div style="font-size:13px;color:var(--text-secondary,#888);margin-bottom:14px">${this.esc(callerLabel || '')}</div>
                <div id="pbx-transfer-tabs" style="display:flex;gap:4px;flex-wrap:wrap;border-bottom:1px solid var(--border-color,#ddd);padding-bottom:10px;margin-bottom:12px"></div>
                <div id="pbx-transfer-list" style="display:flex;flex-direction:column;gap:6px;max-height:260px;overflow-y:auto"></div>
                <div style="display:flex;gap:8px;margin-top:16px;justify-content:flex-end">
                    <button class="pbx-act pbx-act-gray" onclick="document.getElementById('pbx-transfer-modal').remove()">${this.t('pbx_cancel','Abbrechen')}</button>
                    <button class="pbx-act pbx-act-green" id="pbx-transfer-confirm" disabled onclick="PBX.confirmTransfer()">${this.t('pbx_transfer','Uebergeben')}</button>
                </div>
            </div>`;
        document.body.appendChild(modal);
        this._renderTransferTabs();
        this._renderTransferList();
    },
    _renderTransferTabs() {
        const wrap = document.getElementById('pbx-transfer-tabs');
        if (!wrap) return;
        wrap.innerHTML = this._transferGroups.map((g, i) => {
            const active = i === this._transferActiveTab;
            return `<button class="pbx-act ${active ? 'pbx-act-blue' : 'pbx-act-gray'}" style="font-size:12.5px;padding:5px 10px"
                onclick="PBX._transferActiveTab=${i};PBX._renderTransferTabs();PBX._renderTransferList()">${this.esc(g.name)}</button>`;
        }).join('');
    },
    _renderTransferList() {
        const listEl = document.getElementById('pbx-transfer-list');
        if (!listEl) return;
        const group = this._transferGroups[this._transferActiveTab];
        const exts = (group && group.extensions) || [];
        const statusMap = {
            busy: this.t('pbx_busy','besetzt'),
            dnd:  this.t('pbx_dnd','nicht stoeren'),
            free: this.t('pbx_free','frei'),
        };
        const statusColor = { free: 'var(--status-green)', busy: 'var(--status-red)', dnd: 'var(--status-yellow)', away: 'var(--text-muted)', offline: 'var(--text-muted)', unbekannt: 'var(--text-muted)' };
        listEl.innerHTML = exts.length ? exts.map(e => {
            const selected = this._transferSelected === e.ext;
            const statusLabel = statusMap[e.status] || e.status;
            const phone = e.phone ? this.esc(e.phone) : '';
            const bg = selected ? 'var(--abcona-blue-tint)' : 'var(--bg-white)';
            const bd = selected ? 'var(--abcona-blue-tint-border)' : 'var(--border-color)';
            return `<div style="display:flex;align-items:center;justify-content:space-between;cursor:pointer;padding:8px 12px;gap:10px;border:1px solid ${bd};border-radius:8px;background:${bg}"
                onclick="PBX._transferSelected='${this.esc(e.ext)}';PBX._renderTransferList();document.getElementById('pbx-transfer-confirm').disabled=false">
                <span style="display:flex;flex-direction:column;line-height:1.35">
                    <span style="color:var(--text-primary)"><b>Ext ${this.esc(e.ext)}</b>${phone ? ' &middot; ' + phone : ''}</span>
                    <span style="font-size:11px;color:var(--text-secondary)">${this.esc(e.name)}</span>
                </span>
                <span style="display:flex;align-items:center;gap:6px;white-space:nowrap">
                    <span style="font-size:11px;color:${statusColor[e.status] || 'var(--text-muted)'}">${statusLabel}</span>
                    ${selected ? '<i class="bi bi-check-circle-fill" style="color:var(--status-green)"></i>' : ''}
                </span>
            </div>`;
        }).join('') : `<div class="pbx-empty">${this.t('pbx_no_targets','Keine Ziele')}</div>`;
    },
    async confirmTransfer() {
        const ctx = this._transferCtx;
        const targetExt = this._transferSelected;
        if (!ctx || !targetExt) return;

        if (ctx.sourceType === 'park') {
            const channel = (this.data.parked || []).find(p => p.slot === ctx.sourceId && p.occupied);
            if (!channel) { this.toast('Kanal nicht mehr vorhanden'); return; }
            const res = await this.post(this.api.redirect, { channel: channel.channel, exten: targetExt });
            this.toast(res.success ? this.t('pbx_transfer','Uebergeben') : (res.error || 'Fehler'));
        }

        const m = document.getElementById('pbx-transfer-modal');
        if (m) m.remove();
        this.poll();
    },
    async pickupPark(slot) {
        // Abholen = Originate vom eigenen Tischtelefon auf den Slot
        const res = await this.post(this.api.dial, { desk: this.ext, target: slot });
        this.toast(res.success ? this.t('pbx_pickup', 'Abholen') + ' ' + slot : (res.error || 'Fehler'));
        this.poll();
    },

    /* ======================= KONFERENZ ======================= */
    renderKonf() {
        const wrap = this.$('pbx-confwrap');
        if (!wrap) return;
        const rooms = this.data.confbridge || [];
        if (!rooms.length) {
            wrap.innerHTML = '<div class="pbx-empty">' + this.t('pbx_no_conf', 'Keine laufende Konferenz') + '</div>';
            return;
        }
        // Invite- + Label-Feldwerte + Fokus/Cursor ueber den Poll retten
        const saved = {}; let focId = null, selS = 0, selE = 0;
        wrap.querySelectorAll('[id^="pbx-conf-invite-"],[id^="pbx-conf-label-"],[id^="pbx-conf-note-in-"],[id^="pbx-conf-note-out-"],[id^="pbx-conf-note-search-"]').forEach(inp => {
            saved[inp.id] = inp.value;
            if (document.activeElement === inp) { focId = inp.id; selS = inp.selectionStart; selE = inp.selectionEnd; }
        });
        wrap.innerHTML = rooms.map(r => this._confRoom(r)).join('');
        Object.keys(saved).forEach(id => { const inp = document.getElementById(id); if (inp && saved[id]) inp.value = saved[id]; });
        if (focId) { const inp = document.getElementById(focId); if (inp) { inp.focus(); try { inp.setSelectionRange(selS, selE); } catch (e) {} } }
    },
    _confRoom(r) {
        const room = this.esc(r.conference);
        const members = (r.members || []).map(m => {
            const nm   = this.esc(m.name || m.callerid || '?');
            const num  = (m.callerid && m.callerid !== m.name) ? '<span class="pbx-cnum">' + this.esc(m.callerid) + '</span>' : '';
            const dur  = m.duration ? '<span class="pbx-cdur">' + this.esc(m.duration) + '</span>' : '';
            const admin= m.admin ? '<span class="pbx-badge">' + this.t('pbx_admin', 'Admin') + '</span>' : '';
            const wait = m.waitmarked ? '<span class="pbx-badge pbx-badge-warn">' + this.t('pbx_waiting', 'Wartet') + '</span>' : '';
            return `<div class="pbx-cmember ${m.talking ? 'pbx-talking' : ''}">
                <span class="pbx-talkdot ${m.talking ? 'on' : ''}"></span>
                <i class="bi bi-mic-fill pbx-talkmic ${m.talking ? 'on' : ''}" title="${this.t('pbx_talking', 'spricht')}"></i>
                <span class="pbx-cnm">${nm}</span>${num}${dur}${admin}${wait}
                <button class="pbx-act ${m.muted ? 'pbx-act-warn' : 'pbx-act-gray'}" title="${this.t('pbx_mute', 'Stumm')}" onclick="PBX.confMute('${room}','${this.esc(m.channel)}',${m.muted})"><i class="bi ${m.muted ? 'bi-mic-mute' : 'bi-mic'}"></i></button>
                <button class="pbx-act pbx-act-red" title="${this.t('pbx_kick', 'Entfernen')}" onclick="PBX.confKick('${room}','${this.esc(m.channel)}')"><i class="bi bi-person-x"></i></button>
            </div>`;
        }).join('') || ('<div class="pbx-empty" style="padding:6px 0">' + this.t('pbx_conf_empty', 'Niemand im Raum') + '</div>');
        return `<div class="pbx-confroom">
            <div class="pbx-conf-head">
                <span class="pbx-conf-title"><i class="bi bi-collection"></i> ${this.t('pbx_conf', 'Konferenz')} ${room}</span>
                <span class="pbx-badge pbx-badge-blue">${(r.members || []).length} ${this.t('pbx_participants', 'Teilnehmer')}</span>
                <span class="pbx-conf-sp"></span>
                <button class="pbx-act pbx-act-green" title="${this.t('pbx_join_room', 'Diesem Raum mit Nst beitreten')}" onclick="PBX.joinSelf('${room}')"><i class="bi bi-door-open"></i> ${this.t('pbx_join', 'Beitreten')} (${this.esc(this.ext)})</button>
                <button class="pbx-tgl ${r.locked ? 'on' : ''}" onclick="PBX.confLock('${room}',${r.locked})"><i class="bi ${r.locked ? 'bi-lock-fill' : 'bi-lock'}"></i> ${r.locked ? this.t('pbx_locked', 'Gesperrt') : this.t('pbx_lock', 'Sperren')}</button>
            </div>
            <div class="pbx-cmembers">${members}</div>
            <div class="pbx-conf-invite">
                <div class="pbx-conf-searchwrap">
                    <input id="pbx-conf-invite-${room}" class="pbx-conf-invin" autocomplete="off" placeholder="${this.t('pbx_conf_invite_ph', 'Name, Firma oder Nummer…')}" oninput="PBX.confSearch(this,'${room}')" onkeydown="if(event.key==='Enter')PBX.confInvite('${room}')">
                </div>
                <input id="pbx-conf-label-${room}" class="pbx-conf-label" autocomplete="off" placeholder="${this.t('pbx_conf_label_ph', 'Label (opt.)')}" title="${this.t('pbx_conf_label_t', 'Anzeigename in der Konferenz, z.B. Feuerwehr')}">
                <button class="pbx-act pbx-act-blue" title="${this.t('pbx_conf_invite', 'In diesen Raum holen')}" onclick="PBX.confInvite('${room}')"><i class="bi bi-person-plus"></i> ${this.t('pbx_conf_here', '→ Hier rein')}</button>
            </div>
            ${this._confNoteRoom(room)}
        </div>`;
    },
    _confNoteInit(room) {
        if (!this._confNotes[room]) this._confNotes[room] = { open: false, contacts: [], noteType: 'meeting' };
        return this._confNotes[room];
    },
    _confNoteChipsHtml(room) {
        const st = this._confNoteInit(room);
        return st.contacts.map(c =>
            `<span class="pbx-ac-chip on" style="cursor:default">
                <i class="bi ${c.kind === 'firma' ? 'bi-building' : 'bi-person'}"></i> ${this.esc(c.name)}
                <i class="bi bi-x-lg" style="margin-left:6px;cursor:pointer" onclick="PBX.confNoteRemoveChip('${room}','${this.esc(c.crm_id)}')"></i>
            </span>`).join('') || '<span class="pbx-ac-noroom">' + this.t('pbx_no_contacts_selected', 'Noch keine Kontakte gewählt') + '</span>';
    },
    _confNoteRoom(room) {
        const st = this._confNoteInit(room);
        return `<div class="pbx-conf-notewrap">
            <button class="pbx-ac-note-tgl" onclick="PBX.confNoteToggle(this,'${room}')"><i class="bi bi-journal-text"></i> ${this.t('pbx_conf_note', 'Notiz')} <i class="bi bi-chevron-${st.open ? 'up' : 'down'}"></i></button>
            <div class="pbx-ac-note" style="display:${st.open ? 'block' : 'none'}">
                <label class="pbx-ac-lbl">${this.t('pbx_note_in', 'Stichpunkte (Eingabe)')}</label>
                <textarea id="pbx-conf-note-in-${room}" class="pbx-ac-in" rows="3" placeholder="${this.t('pbx_conf_note_ph', '- Teilnehmer, Themen, Ergebnisse…')}"></textarea>
                <div class="pbx-ac-dsrow">
                    <button class="pbx-ac-ds" onclick="PBX.confNoteDeepseek(this,'${room}')"><i class="bi bi-stars"></i> ${this.t('pbx_deepseek', 'DeepSeek formulieren')} <i class="bi bi-arrow-down"></i></button>
                </div>
                <label class="pbx-ac-lbl">${this.t('pbx_note_out', 'DeepSeek-Ausgabe (editierbar)')}</label>
                <textarea id="pbx-conf-note-out-${room}" class="pbx-ac-out" rows="4" placeholder="${this.t('pbx_out_ph', 'Formulierte Notiz erscheint hier – editierbar, bis sie passt …')}"></textarea>
                <label class="pbx-ac-lbl">${this.t('pbx_conf_note_contacts', 'Teilnehmer/Kontakte zuordnen (mehrere möglich)')}</label>
                <div style="display:flex;flex-wrap:wrap;gap:6px;margin:4px 0 8px">${this._confNoteChipsHtml(room)}</div>
                <div class="pbx-ac-searchin"><i class="bi bi-search"></i><input id="pbx-conf-note-search-${room}" placeholder="${this.t('pbx_search_contact', 'Name, Firma oder Nummer…')}" oninput="PBX.confNoteSearch(this,'${room}')"></div>
                <div class="pbx-ac-results" id="pbx-conf-note-results-${room}"></div>
                <div class="pbx-ac-targets">
                    <span class="pbx-ac-tlbl">${this.t('pbx_note_type', 'Notizart')}:</span>
                    <select id="pbx-conf-note-type-${room}" class="pbx-ac-nt" onchange="PBX._confNoteInit('${room}').noteType=this.value">
                        <option value="meeting" ${st.noteType === 'meeting' ? 'selected' : ''}>${this.t('pbx_note_meeting', 'Besprechung')}</option>
                        <option value="phone" ${st.noteType === 'phone' ? 'selected' : ''}>${this.t('pbx_note_phone', 'Telefonnotiz')}</option>
                        <option value="general" ${st.noteType === 'general' ? 'selected' : ''}>${this.t('pbx_note_generic', 'Notiz')}</option>
                    </select>
                    <button class="pbx-ac-save" onclick="PBX.confNoteSave(this,'${room}')"><i class="bi bi-check-lg"></i> ${this.t('pbx_save_note', 'Telefonnotiz speichern')}</button>
                </div>
            </div>
        </div>`;
    },
    confNoteToggle(btn, room) {
        const st = this._confNoteInit(room);
        st.open = !st.open;
        const box = btn.nextElementSibling;
        if (box) box.style.display = st.open ? 'block' : 'none';
        const ch = btn.querySelector('.bi-chevron-down, .bi-chevron-up');
        if (ch) ch.className = st.open ? 'bi bi-chevron-up' : 'bi bi-chevron-down';
    },
    async confNoteDeepseek(btn, room) {
        const inEl = document.getElementById('pbx-conf-note-in-' + room);
        const outEl = document.getElementById('pbx-conf-note-out-' + room);
        const note = (inEl.value || '').trim();
        if (!note) { this.toast(this.t('pbx_note_empty', 'Erst Stichpunkte eingeben')); return; }
        const old = btn.innerHTML; btn.innerHTML = '<i class="bi bi-hourglass-split"></i> …';
        try {
            const res = await this.post(this.api.notiz, { note });
            if (res.success && res.text) outEl.value = res.text;
            else this.toast(res.error || this.t('pbx_ds_fail', 'DeepSeek fehlgeschlagen'));
        } catch (e) { this.toast(this.t('pbx_ds_fail', 'DeepSeek fehlgeschlagen')); }
        btn.innerHTML = old;
    },
    confNoteSearch(inp, room) {
        const box = document.getElementById('pbx-conf-note-results-' + room);
        const q = (inp.value || '').trim();
        clearTimeout(this._confNoteTimer);
        if (q.length < 2) { box.innerHTML = ''; box.style.display = 'none'; return; }
        box.innerHTML = '<div class="pbx-ac-hit muted">' + this.t('pbx_searching', 'suche…') + '</div>';
        box.style.display = 'block';
        this._confNoteTimer = setTimeout(async () => {
            let out = [];
            for (const sk of [['personen', 'person'], ['firmen', 'firma']]) {
                try {
                    const r = await this.get(this.api.searchAll + '?q=' + encodeURIComponent(q) + '&scope=' + sk[0] + '&size=10');
                    (r.results || []).forEach(h => out.push({ crm_id: h.id, name: h.title, sub: h.meta || h.company || '', kind: sk[1] }));
                } catch (e) { /* ignore */ }
            }
            this._confNoteResults = this._confNoteResults || {};
            this._confNoteResults[room] = out.slice(0, 20);
            this._confNoteRenderResults(room);
        }, 150);
    },
    _confNoteRenderResults(room) {
        const box = document.getElementById('pbx-conf-note-results-' + room);
        if (!box) return;
        const list = (this._confNoteResults || {})[room] || [];
        if (!list.length) { box.innerHTML = '<div class="pbx-ac-hit muted">' + this.t('pbx_no_hits', 'keine Treffer') + '</div>'; box.style.display = 'block'; return; }
        const icon = k => k === 'firma' ? 'bi-building' : 'bi-person';
        const badge = k => k === 'firma' ? this.t('pbx_firma', 'Firma') : this.t('pbx_person', 'Kontakt');
        box.innerHTML = list.map((h, i) =>
            `<div class="pbx-ac-hit" onclick="PBX.confNotePick('${room}',${i})">
                <i class="bi ${icon(h.kind)}"></i>
                <div class="pbx-ac-hi"><div class="pbx-ac-hn">${this.esc(h.name)}</div><div class="pbx-ac-hs">${this.esc(h.sub || '')}</div></div>
                <span class="pbx-ac-badge${h.kind === 'firma' ? ' acc' : ''}">${badge(h.kind)}</span>
            </div>`).join('');
        box.style.display = 'block';
    },
    confNotePick(room, idx) {
        const list = (this._confNoteResults || {})[room] || [];
        const obj = list[idx];
        if (!obj) return;
        const st = this._confNoteInit(room);
        if (!st.contacts.some(c => c.crm_id === obj.crm_id)) st.contacts.push(obj);
        const inp = document.getElementById('pbx-conf-note-search-' + room);
        if (inp) inp.value = '';
        const box = document.getElementById('pbx-conf-note-results-' + room);
        if (box) { box.innerHTML = ''; box.style.display = 'none'; }
        this._confNoteRerenderChips(room);
    },
    confNoteRemoveChip(room, crmId) {
        const st = this._confNoteInit(room);
        st.contacts = st.contacts.filter(c => c.crm_id !== crmId);
        this._confNoteRerenderChips(room);
    },
    _confNoteRerenderChips(room) {
        const searchEl = document.getElementById('pbx-conf-note-search-' + room);
        const notebox = searchEl ? searchEl.closest('.pbx-ac-note') : null;
        if (!notebox) return;
        const wraps = notebox.querySelectorAll('div');
        for (const w of wraps) {
            if (w.style && w.style.display === 'flex') { w.innerHTML = this._confNoteChipsHtml(room); break; }
        }
    },
    async confNoteSave(btn, room) {
        const st = this._confNoteInit(room);
        const outEl = document.getElementById('pbx-conf-note-out-' + room);
        const inEl = document.getElementById('pbx-conf-note-in-' + room);
        const text = (outEl.value || '').trim() || (inEl.value || '').trim();
        if (!text) { this.toast(this.t('pbx_note_empty', 'Notiz ist leer')); return; }
        if (!st.contacts.length) { this.toast(this.t('pbx_no_target', 'Kein Ziel gewählt – Kontakt/Firma zuordnen')); return; }
        const type = st.noteType || 'meeting';
        let ok = 0;
        for (const c of st.contacts) {
            const body = { note_text: text, note_type: type };
            if (c.kind === 'firma') body.account_crm_id = c.crm_id; else body.contact_crm_id = c.crm_id;
            try { const r = await this.post(this.api.noteSave, body); if (r && (r.ok || r.success)) ok++; } catch (e) { /* ignore */ }
        }
        if (ok) {
            this.toast(this.t('pbx_note_saved', 'Notiz gespeichert') + ' (' + ok + '×)');
            st.contacts = [];
            inEl.value = '';
            outEl.value = '';
            this._confNoteRerenderChips(room);
        } else {
            this.toast(this.t('pbx_note_fail', 'Speichern fehlgeschlagen'));
        }
    },
    async confMute(room, channel, isMuted) {
        const res = await this.post(this.api.confMember, { room, channel, action: isMuted ? 'unmute' : 'mute' });
        this.toast(res.success ? (isMuted ? this.t('pbx_unmuted', 'Laut') : this.t('pbx_muted', 'Stumm')) : (res.error || 'Fehler'));
        this.poll();
    },
    async confKick(room, channel) {
        const res = await this.post(this.api.confMember, { room, channel, action: 'kick' });
        this.toast(res.success ? this.t('pbx_kicked', 'Entfernt') : (res.error || 'Fehler'));
        this.poll();
    },
    async confLock(room, isLocked) {
        const res = await this.post(this.api.confLock, { room, action: isLocked ? 'unlock' : 'lock' });
        this.toast(res.success ? (isLocked ? this.t('pbx_unlocked', 'Entsperrt') : this.t('pbx_locked', 'Gesperrt')) : (res.error || 'Fehler'));
        this.poll();
    },
    async joinSelf(room) {
        const res = await this.post(this.api.joinSelf, { desk: this.ext, room });
        this.toast(res.success ? this.t('pbx_joining', 'Trete Konferenz bei') + ' ' + room : (res.error || 'Fehler'));
    },

    /* ======================= QUEUES ======================= */
    /* Overlay am body (umgeht overflow:hidden), robust: nur Aussenklick/Escape schliesst */
    _confPop() {
        let p = document.getElementById('pbx-conf-pop');
        if (!p) {
            p = document.createElement('div');
            p.id = 'pbx-conf-pop';
            p.className = 'pbx-conf-pop';
            document.body.appendChild(p);
            document.addEventListener('mousedown', e => {
                if (!e.target.closest('#pbx-conf-pop') && !e.target.closest('.pbx-conf-invin')) this._confPopHide();
            });
            document.addEventListener('keydown', e => { if (e.key === 'Escape') this._confPopHide(); });
        }
        return p;
    },
    _confPopHide() { const p = document.getElementById('pbx-conf-pop'); if (p) { p.style.display = 'none'; p.innerHTML = ''; } },
    _confPopAt(inp) {
        const p = this._confPop();
        const r = inp.getBoundingClientRect();
        p.style.left = r.left + 'px';
        p.style.top = (r.bottom + 4) + 'px';
        p.style.width = Math.max(r.width, 260) + 'px';
        p.style.display = 'block';
        return p;
    },
    /* Kontaktsuche aus dem Cache (wie dialSearch): ab 2 Zeichen, Namens-Treffer zuerst, max 10 */
    confSearch(inp, room) {
        const q = (inp.value || '').trim();
        inp.dataset.nr = '';
        clearTimeout(this._confTimer);
        if (q.length < 2) { this._confPopHide(); return; }
        this._confTimer = setTimeout(async () => {
            const pw = this._confPopAt(inp);
            pw.innerHTML = '<div class="pbx-conf-info"><i class="bi bi-search"></i> ' + this.t('pbx_searching_contacts', 'suche…') + '</div>';
            let data = null;
            try { data = await this.get(this.api.searchAll + '?q=' + encodeURIComponent(q) + '&scope=personen&size=10'); }
            catch (e) { this._confPopHide(); return; }
            if ((inp.value || '').trim() !== q) return;          // Eingabe hat sich geaendert
            const results = (data && data.results) || [];
            if (!results.length) { this._confPopHide(); return; }
            const total = (data.counts && data.counts.personen) || results.length;
            const p = this._confPopAt(inp);
            const head = '<div class="pbx-conf-count">' + total + ' ' + this.t('pbx_hits', 'Treffer') + (total > results.length ? ' · ' + this.t('pbx_refine', 'verfeinern…') : '') + '</div>';
            p.innerHTML = head + results.map(hit => {
                const nm = this.esc(hit.title || '');
                const co = hit.company ? ' · ' + this.esc(hit.company) : (hit.meta ? ' · ' + this.esc(hit.meta) : '');
                const raw = hit.phones || [];
                let nums = '';
                for (let i = 0; i < raw.length; i += 2) {
                    const dial = this.esc(raw[i] || raw[i + 1] || '');
                    const disp = this.esc((raw[i + 1] && /\D/.test(raw[i + 1])) ? raw[i + 1] : raw[i]);
                    if (dial) nums += `<button class="pbx-conf-nr" onclick="PBX.confPickNr('${room}','${dial}','${nm.replace(/'/g, '')}')"><i class="bi bi-telephone"></i> ${disp}</button>`;
                }
                return `<div class="pbx-conf-hit"><div class="pbx-conf-hn">${nm}<span class="pbx-conf-hc">${co}</span></div><div class="pbx-conf-nrs">${nums || '<span class="pbx-conf-nonum">' + this.t('pbx_no_number', 'keine Nummer') + '</span>'}</div></div>`;
            }).join('');
        }, 150);
    },
    confPickNr(room, nr, name) {
        const inp = this.$('pbx-conf-invite-' + room);
        if (inp) { inp.value = (name ? name + ' · ' : '') + nr; inp.dataset.nr = nr; }
        const lbl = this.$('pbx-conf-label-' + room);
        if (lbl && name && !lbl.value.trim()) lbl.value = name;
        this._confPopHide();
    },
    async confInvite(room) {
        const inp = this.$('pbx-conf-invite-' + room);
        const number = inp ? ((inp.dataset.nr || '').trim() || (inp.value || '').trim()) : '';
        if (!number) { this.toast(this.t('pbx_conf_invite_req', 'Kontakt suchen oder Nummer eingeben')); return; }
        const lbl = this.$('pbx-conf-label-' + room);
        const caller_id = (lbl && lbl.value.trim()) || '';
        this._confPopHide();
        const body = { room, number };
        if (caller_id) body.caller_id = caller_id;
        const res = await this.post(this.api.confInvite, body);
        this.toast(res.success ? (this.t('pbx_conf_invited', 'wird geholt') + ' → ' + room) : (res.error || 'Fehler'));
        if (inp && res.success) { inp.value = ''; inp.dataset.nr = ''; if (lbl) lbl.value = ''; }
        this.poll();
    },
    renderQueues() {
        const grid = this.$('pbx-queuegrid');
        if (!grid) return;
        const q = this.data.queues || [];
        grid.innerHTML = q.length ? q.map(x => this._queueCard(x)).join('')
            : '<div class="pbx-empty">' + this.t('pbx_no_queues', 'Keine Warteschlangen') + '</div>';
    },
    _queueCard(x) {
        const callers = x.callers || [];
        const waiting = callers.length;
        const mem = (x.members || []).length;
        const callerRows = callers.map(c => `
            <div class="pbx-queue-caller">
                <span class="pbx-queue-caller-id">${this.esc(c.callername || c.callerid)}</span>
                <span class="pbx-queue-caller-wait">${this.fmtDur(parseInt(c.wait || 0, 10))}</span>
                <button class="pbx-act pbx-act-green" title="${this.t('pbx_queue_pickup', 'Zu mir holen')}"
                        onclick="PBX.queuePickup('${this.esc(c.channel)}')"
                        ${c.channel ? '' : 'disabled'}>
                    <i class="bi bi-telephone-inbound"></i> ${this.t('pbx_queue_pickup', 'Zu mir holen')}
                </button>
            </div>`).join('');
        return `<div class="pbx-queuecard ${waiting ? 'pbx-st-busy' : 'pbx-st-free'}">
            <div class="pbx-queue-top"><b>${this.esc(x.name)}</b><span class="pbx-badge">${mem} ${this.t('pbx_agents', 'Agenten')}</span></div>
            <div class="pbx-queue-wait">${waiting} ${this.t('pbx_waiting', 'wartend')}</div>
            ${callerRows}
        </div>`;
    },
    async queuePickup(channel) {
        if (!channel) return;
        const desk = (this.$('pbx-dial-ext') || {}).value || this.ext;
        const res = await this.post(this.api.redirect, { channel: channel, exten: desk });
        this.toast(res.success ? this.t('pbx_queue_pickup', 'Zu mir holen') : (res.error || 'Fehler'));
        this.poll();
    },

    /* ======================= VOICEMAIL ======================= */
    async loadVm() {
        const grid = this.$('pbx-vmgrid');
        if (!grid) return;
        grid.innerHTML = '<div class="pbx-empty">' + this.t('pbx_loading', 'Lade…') + '</div>';
        try {
            const res = await this.get(this.api.vmboxes);
            const v = res.boxes || [];
            grid.innerHTML = v.length ? v.map(b => this._vmCard(b)).join('')
                : '<div class="pbx-empty">' + this.t('pbx_no_vm', 'Keine Mailboxen') + '</div>';
        } catch (e) {
            grid.innerHTML = '<div class="pbx-empty">' + this.t('pbx_load_error', 'Fehler beim Laden') + '</div>';
        }
    },
    _vmCard(b) {
        const pct = b.max ? Math.min(100, Math.round((b.new + b.old) / b.max * 100)) : 0;
        return `<div class="pbx-vmcard ${b.new ? 'pbx-st-warn' : 'pbx-st-free'}">
            <div class="pbx-vm-top"><b>${this.esc(b.box)}</b> <span>${this.esc(b.user)}</span></div>
            <div class="pbx-vm-count"><span class="pbx-vm-new">${b.new}</span> ${this.t('pbx_new', 'neu')} · ${b.old} ${this.t('pbx_old', 'alt')}</div>
            <div class="pbx-vm-bar"><div style="width:${pct}%"></div></div>
            <div class="pbx-vm-meta">${b.new + b.old}/${b.max} · ${this.esc(b.email || '')}</div>
            <div class="pbx-vm-actions">
                <button class="pbx-act pbx-act-blue" style="flex:1" onclick="PBX.vmListen('${b.box}')">
                    <i class="bi bi-headphones"></i> ${this.t('pbx_vm_listen', 'Abhören')}
                </button>
                <button class="pbx-act pbx-act-green" style="padding:6px 10px" onclick="PBX.dialGuestNumber('${b.box}')" title="${this.t('pbx_dial', 'Anrufen')}">
                    <i class="bi bi-telephone-outbound"></i>
                </button>
            </div>
        </div>`;
    },
    async loadWavNotes() {
        const grid = this.$('pbx-wavnotesgrid');
        if (!grid) return;
        grid.innerHTML = '<div class="pbx-empty">' + this.t('pbx_loading', 'Lade\u2026') + '</div>';
        try {
            const res = await this.get(this.api.wavnotes);
            const list = res.data || [];
            const byDateDesc = (a, b) => new Date(b.origtime) - new Date(a.origtime);
            const offen = list.filter(n => !n.is_done).sort(byDateDesc);
            const done = list.filter(n => n.is_done).sort(byDateDesc);
            grid.innerHTML = offen.length ? offen.map(n => this._wavnoteCard(n)).join('')
                : '<div class="pbx-empty">' + this.t('pbx_no_wavnotes', 'Keine offenen Voicemail-Nachrichten') + '</div>';
            const countEl = document.querySelector('#pbx-wavnotes-archive-toggle .pbx-wav-archive-count');
            if (countEl) countEl.textContent = done.length;
            this._wavArchiveData = done;
            this._wavnoteRenderArchive();
        } catch (e) {
            grid.innerHTML = '<div class="pbx-empty">' + this.t('pbx_load_error', 'Fehler beim Laden') + '</div>';
        }
    },

    _wavnoteSetArchiveFilter(f) {
        this._wavArchiveFilter = f;
        this._wavnoteRenderArchive();
    },

    _wavnoteRenderArchive() {
        const archBox = this.$('pbx-wavnotes-archive-box');
        if (!archBox) return;
        const filter = this._wavArchiveFilter || 'all';
        const all = this._wavArchiveData || [];
        const filtered = filter === 'doc' ? all.filter(n => n.has_note)
            : filter === 'arch' ? all.filter(n => n.archived_manual && !n.has_note)
            : all;
        const bar = `<div class="pbx-wav-archive-filterbar">
            <span class="pbx-wav-archive-filt ${filter === 'all' ? 'pbx-wav-archive-filt-active' : ''}" onclick="PBX._wavnoteSetArchiveFilter('all')">${this.t('pbx_wavnote_filt_all', 'Alle')}</span>
            <span class="pbx-wav-archive-filt ${filter === 'doc' ? 'pbx-wav-archive-filt-active' : ''}" onclick="PBX._wavnoteSetArchiveFilter('doc')">${this.t('pbx_documented', 'Dokumentiert')}</span>
            <span class="pbx-wav-archive-filt ${filter === 'arch' ? 'pbx-wav-archive-filt-active' : ''}" onclick="PBX._wavnoteSetArchiveFilter('arch')">${this.t('pbx_archived', 'Archiviert')}</span>
        </div>`;
        archBox.innerHTML = bar + (filtered.length
            ? filtered.map(n => this._wavnoteArchiveRow(n)).join('')
            : '<div class="pbx-empty">' + this.t('pbx_wavnote_no_archive_hits', 'Keine Eintr\u00e4ge') + '</div>');
    },

    wavnoteToggleArchive() {
        const box = this.$('pbx-wavnotes-archive-box');
        const icon = this.$('pbx-wavnotes-archive-icon');
        if (!box) return;
        const open = box.style.display !== 'none';
        box.style.display = open ? 'none' : '';
        if (icon) icon.className = open ? 'bi bi-chevron-right' : 'bi bi-chevron-down';
    },

    _wavnoteArchiveRow(n) {
        const dt = n.origtime ? new Date(n.origtime).toLocaleDateString() : '';
        const dur = n.duration ? this._fmtDur(n.duration) : '--:--';
        const badge = n.has_note
            ? `<span class="pbx-badge pbx-badge-doc"><i class="bi bi-check-lg"></i> ${this.t('pbx_documented', 'Dokumentiert')}</span>`
            : `<span class="pbx-badge pbx-badge-archived">${this.t('pbx_archived', 'Archiviert')}</span>`;
        const audioSrc = `${this.api.wavnoteAudio}?mailbox=${encodeURIComponent(n.mailbox)}&folder=${encodeURIComponent(n.folder)}&msg_id=${encodeURIComponent(n.msg_id)}`;
        return `<div class="pbx-wav-archive-row">
            <audio controls preload="none" src="${audioSrc}" class="pbx-wav-archive-audio"></audio>
            <span class="pbx-wav-archive-label">${this.esc(n.callerid || this.t('pbx_unknown_number', 'Unbekannte Nummer'))} \u00b7 ${this.t('pbx_box', 'Box')} ${this.esc(n.mailbox)} \u00b7 ${this.esc(dt)} \u00b7 ${dur}</span>
            ${badge}
        </div>`;
    },

    _fmtDur(sec) {
        const m = Math.floor(sec / 60), s = sec % 60;
        return `${m}:${String(s).padStart(2, '0')}`;
    },

    _wavnoteCard(n) {
        const newBadge = n.folder === 'INBOX'
            ? `<span class="pbx-badge pbx-badge-new">${this.t('pbx_new', 'Neu')}</span>`
            : '';
        const dur = n.duration ? this._fmtDur(n.duration) : '--:--';
        const dt = n.origtime ? new Date(n.origtime).toLocaleString() : '';
        const audioSrc = `${this.api.wavnoteAudio}?mailbox=${encodeURIComponent(n.mailbox)}&folder=${encodeURIComponent(n.folder)}&msg_id=${encodeURIComponent(n.msg_id)}`;
        const dataAttr = this.esc(JSON.stringify(n)).replace(/"/g, '&quot;');
        return `<div class="pbx-wavcard">
            <div class="pbx-wav-top">
                <b>${this.esc(n.callerid || this.t('pbx_unknown_number', 'Unbekannte Nummer'))}</b>
                ${newBadge}
            </div>
            <div class="pbx-wav-meta">${this.t('pbx_box', 'Box')} ${this.esc(n.mailbox)} \u00b7 ${this.esc(dt)} \u00b7 ${dur}</div>
            <audio class="pbx-wav-audio" controls preload="none" src="${audioSrc}"></audio>
            <div class="pbx-wav-actions">
                <button class="pbx-act pbx-act-blue" data-wavnote="${dataAttr}" onclick="PBX.wavnoteOpenModal(JSON.parse(this.dataset.wavnote))">
                    <i class="bi bi-journal-text"></i> ${this.t('pbx_wavnote_create', 'Notiz erstellen')}
                </button>
                <button class="pbx-act pbx-act-gray" data-wavnote="${dataAttr}" onclick="PBX.wavnoteArchive(JSON.parse(this.dataset.wavnote))">
                    <i class="bi bi-archive"></i> ${this.t('pbx_wavnote_archive', 'Archivieren')}
                </button>
            </div>
        </div>`;
    },

    async wavnoteArchive(n) {
        if (!confirm(this.t('pbx_wavnote_archive_confirm', 'Diese Voicemail als erledigt markieren (ohne Notiz)?'))) return;
        try {
            await this.post(this.api.wavnoteArchive, { mailbox: n.mailbox, msg_id: n.msg_id });
            this.loadWavNotes();
        } catch (e) {
            alert(this.t('pbx_wavnote_archive_err', 'Archivieren fehlgeschlagen'));
        }
    },

    wavnoteOpenModal(n) {
        this._wavCurrent = n;
        this._wavContact = null;
        const overlay = document.createElement('div');
        overlay.className = 'pbx-modal-overlay';
        overlay.id = 'pbx-wav-modal-overlay';
        const audioSrc = `${this.api.wavnoteAudio}?mailbox=${encodeURIComponent(n.mailbox)}&folder=${encodeURIComponent(n.folder)}&msg_id=${encodeURIComponent(n.msg_id)}`;
        overlay.innerHTML = `<div class="pbx-modal">
            <div class="pbx-modal-hdr">
                <i class="bi bi-telephone-inbound"></i>
                <span>${this.t('pbx_wavnote_title', 'Telefonnotiz')}</span>
                <button class="pbx-modal-close" onclick="PBX.wavnoteCloseModal()"><i class="bi bi-x-lg"></i></button>
            </div>
            <audio controls preload="none" src="${audioSrc}" style="width:100%;margin-bottom:12px"></audio>
            <div class="pbx-modal-lbl">${this.t('pbx_wavnote_raw', 'Rohtext (automatische Transkription)')}</div>
            <textarea id="pbx-wav-raw" readonly class="pbx-modal-raw"></textarea>
            <div class="pbx-modal-lbl">${this.t('pbx_wavnote_polished', 'Gegl\u00e4ttetes Protokoll (editierbar)')}</div>
            <textarea id="pbx-wav-polished" class="pbx-modal-polished"></textarea>
            <div id="pbx-wav-contact-box" class="pbx-wav-contact"></div>
            <div class="pbx-modal-ftr">
                <button class="pbx-act" style="background:var(--text-secondary)" onclick="PBX.wavnoteCloseModal()">${this.t('pbx_cancel', 'Abbrechen')}</button>
                <button class="pbx-act pbx-act-green" onclick="PBX.wavnoteSaveNote()"><i class="bi bi-save"></i> ${this.t('pbx_wavnote_save', 'Telefonnotiz speichern')}</button>
            </div>
        </div>`;
        this._meetmeMountModal(overlay);
        this.wavnoteTranscribe();
        this.wavnoteResolveContact();
    },

    wavnoteCloseModal() {
        const el = this.$('pbx-wav-modal-overlay');
        if (el) el.remove();
        this._wavCurrent = null;
        this._wavContact = null;
    },

    async wavnoteTranscribe() {
        const n = this._wavCurrent;
        if (!n) return;
        const rawEl = this.$('pbx-wav-raw');
        const polEl = this.$('pbx-wav-polished');
        rawEl.value = this.t('pbx_loading', 'Lade\u2026');
        try {
            const res = await this.post(this.api.wavnoteTranscribe, {
                mailbox: n.mailbox, folder: n.folder, msg_id: n.msg_id,
            });
            rawEl.value = res.raw_text || '';
            polEl.value = res.polished_text || res.raw_text || '';
        } catch (e) {
            rawEl.value = this.t('pbx_load_error', 'Fehler beim Laden');
        }
    },

    async wavnoteResolveContact() {
        const n = this._wavCurrent;
        if (!n || !n.callerid) { this._wavnoteRenderContactBox(); return; }
        try {
            const res = await this.get(`${this.api.cdrResolve}?number=${encodeURIComponent(n.callerid)}`);
            if (res.matched && res.crm_id && res.confidence !== 'multi') {
                this._wavContact = { crm_id: res.crm_id, module: res.module, name: res.name };
            }
        } catch (e) { /* still - fallback auf manuelle Suche */ }
        this._wavnoteRenderContactBox();
    },

    _wavnoteRenderContactBox() {
        const box = this.$('pbx-wav-contact-box');
        if (!box) return;
        if (this._wavContact) {
            box.innerHTML = `<div class="pbx-wav-contact-match">
                <i class="bi bi-person-check-fill"></i> ${this.esc(this._wavContact.name)}
                <a href="#" onclick="PBX._wavContact=null; PBX._wavnoteRenderContactBox(); return false;">${this.t('pbx_wavnote_other_contact', 'Anderer Kontakt?')}</a>
            </div>`;
            return;
        }
        box.innerHTML = `<div class="pbx-wav-contact-unknown">
            <input type="text" id="pbx-wav-contact-search" placeholder="${this.t('pbx_wavnote_search_contact', 'Kontakt suchen\u2026')}" oninput="PBX._wavnoteSearchContact(this.value)">
            <div id="pbx-wav-contact-results"></div>
            <button class="pbx-act pbx-act-blue" onclick="PBX.wavnoteNewContact()">
                <i class="bi bi-person-plus-fill"></i> ${this.t('pbx_wavnote_new_contact', 'Neuer Kontakt')}
            </button>
        </div>`;
    },

    async _wavnoteSearchContact(q) {
        const results = this.$('pbx-wav-contact-results');
        if (!results) return;
        q = (q || '').trim();
        if (q.length < 2) { results.innerHTML = ''; return; }
        try {
            const res = await this.get(`${this.api.searchAll}?q=${encodeURIComponent(q)}&scope=personen&size=8`);
            const list = (res.results || []).filter(r => r.kind === 'person');
            results.innerHTML = list.length
                ? list.map(c => `<div class="pbx-wav-contact-hit" onclick='PBX._wavnotePickContact(${JSON.stringify(c)})'>${this.esc(c.title || '')}${c.meta ? ' <span class="pbx-wav-contact-hit-meta">' + this.esc(c.meta) + '</span>' : ''}</div>`).join('')
                : '<div class="pbx-wav-contact-nohit">' + this.t('pbx_wavnote_no_hits', 'Keine Treffer') + '</div>';
        } catch (e) { /* still */ }
    },

    _wavnotePickContact(c) {
        this._wavContact = { crm_id: c.id, module: 'Contacts', name: c.title || '' };
        this._wavnoteRenderContactBox();
    },

    wavnoteNewContact() {
        const n = this._wavCurrent;
        if (!n) return;
        this._mmNewContactState = {
            phones: [{ field_name: 'phone_mobile', raw: n.callerid || '' }],
            emails: [{ address: '', primary: true }],
            companyMode: 'search',
            selectedAccount: null,
        };
        const overlay = document.createElement('div');
        overlay.className = 'pbx-meetme-modal-overlay';
        overlay.id = 'pbx-meetme-modal-overlay';
        overlay.innerHTML = this._mmNewContactHtml(0, true);
        this._meetmeMountModal(overlay);
    },

    async wavnoteSaveNewContact() {
        const st = this._mmNewContactState;
        const lastName = this.$('pbx-mm-new-lastname').value.trim();
        if (!lastName) { this.toast(this.t('pbx_mm_lastname_req', 'Nachname erforderlich')); return; }

        const body = {
            salutation: this.$('pbx-mm-new-salutation').value,
            first_name: this.$('pbx-mm-new-firstname').value.trim(),
            last_name: lastName,
            category: this.$('pbx-mm-new-category').value,
            phones: st.phones.filter(p => p.raw.trim()),
            emails: st.emails.filter(e => e.address.trim()),
            company: {},
        };
        if (st.companyMode === 'new') {
            const name = (this.$('pbx-mm-new-company-name') || {}).value || '';
            if (name.trim()) {
                body.company.new_name = name.trim();
                body.company.city = (this.$('pbx-mm-new-company-city') || {}).value || '';
            }
        } else if (st.selectedAccount) {
            body.company.existing_crm_id = st.selectedAccount.crm_id;
        }

        try {
            const res = await this.post('/crm/api/contact/quick-create/', body);
            if (res && res.error) { this.toast(res.error); return; }
            this._wavContact = { crm_id: res.contact_crm_id, module: 'Contacts', name: res.name || lastName };
            this.meetmeCloseModal();
            this._wavnoteRenderContactBox();
            this.toast(this.t('pbx_mm_contact_created', 'Kontakt angelegt'));
        } catch (e) {
            this.toast(this.t('pbx_mm_contact_create_err', 'Anlegen fehlgeschlagen'));
        }
    },

    async wavnoteSaveNote() {
        const n = this._wavCurrent;
        if (!n) return;
        const noteText = this.$('pbx-wav-polished').value.trim();
        if (!noteText) { alert(this.t('pbx_wavnote_empty', 'Notiztext fehlt')); return; }
        const body = {
            mailbox: n.mailbox, folder: n.folder, msg_id: n.msg_id,
            note_text: noteText, raw_text: this.$('pbx-wav-raw').value,
        };
        if (this._wavContact) {
            if (this._wavContact.module === 'Contacts') body.contact_crm_id = this._wavContact.crm_id;
            if (this._wavContact.module === 'Accounts') body.account_crm_id = this._wavContact.crm_id;
        }
        try {
            await this.post(this.api.wavnoteSave, body);
            this.wavnoteCloseModal();
            this.loadWavNotes();
        } catch (e) {
            alert(this.t('pbx_wavnote_save_error', 'Speichern fehlgeschlagen'));
        }
    },


    /* ======================= ANRUFLISTE (CDR) ======================= */
    _cdrState: { sortBy: 'calldate', sortDir: 'DESC' },

    initCdrFilters() {
        const extSel = this.$('pbx-cdr-ext-filter');
        if (extSel && extSel.options.length <= 1) {
            (this.data.extensions || []).forEach(e => {
                const opt = document.createElement('option');
                opt.value = e.ext;
                opt.textContent = e.ext + (e.name ? ' · ' + e.name : '');
                extSel.appendChild(opt);
            });
        }
        ['pbx-cdr-ext-filter', 'pbx-cdr-mode-filter', 'pbx-cdr-hide-system'].forEach(id => {
            const el = this.$(id);
            if (el && !el.dataset.bound) {
                el.dataset.bound = '1';
                el.addEventListener('change', () => this.loadCdr());
            }
        });
        const rangeSel = this.$('pbx-cdr-range-filter');
        if (rangeSel && !rangeSel.dataset.bound) {
            rangeSel.dataset.bound = '1';
            rangeSel.addEventListener('change', () => this.loadCdr());
        }
        ['pbx-cdr-date-from', 'pbx-cdr-date-to'].forEach(id => {
            const el = this.$(id);
            if (el && !el.dataset.bound) {
                el.dataset.bound = '1';
                el.addEventListener('change', () => this.loadCdr());
            }
        });
    },

    toggleCdrDateRange() {
        const wrap = this.$('pbx-cdr-daterange');
        wrap.style.display = (wrap.style.display === 'none' || !wrap.style.display) ? 'flex' : 'none';
    },

    clearCdrDateRange() {
        this.$('pbx-cdr-date-from').value = '';
        this.$('pbx-cdr-date-to').value = '';
        this.$('pbx-cdr-daterange').style.display = 'none';
        this.loadCdr();
    },

    resetCdrFilters() {
        this.$('pbx-cdr-ext-filter').value = '';
        this.$('pbx-cdr-mode-filter').value = 'all';
        this.$('pbx-cdr-range-filter').value = '30';
        this.$('pbx-cdr-daterange').style.display = 'none';
        this.$('pbx-cdr-date-from').value = '';
        this.$('pbx-cdr-date-to').value = '';
        this.$('pbx-cdr-hide-system').checked = false;
        this._cdrState = { sortBy: 'calldate', sortDir: 'DESC' };
        this.loadCdr();
    },

    sortCdr(field) {
        if (this._cdrState.sortBy === field) {
            this._cdrState.sortDir = this._cdrState.sortDir === 'DESC' ? 'ASC' : 'DESC';
        } else {
            this._cdrState.sortBy = field;
            this._cdrState.sortDir = 'DESC';
        }
        ['calldate', 'billsec'].forEach(f => {
            const icon = this.$('pbx-cdr-sort-' + f);
            if (!icon) return;
            if (f !== this._cdrState.sortBy) { icon.className = 'bi bi-arrow-down-up'; return; }
            icon.className = this._cdrState.sortDir === 'DESC' ? 'bi bi-chevron-down' : 'bi bi-chevron-up';
        });
        this.loadCdr();
    },

    async loadCdr() {
        const body = this.$('pbx-cdr-tbody');
        if (!body) return;
        this.initCdrFilters();
        body.innerHTML = `<tr><td colspan="6" class="pbx-empty">${this.t('pbx_loading', 'Lade…')}</td></tr>`;

        const extFilter = (this.$('pbx-cdr-ext-filter') || {}).value || '';
        const extension = extFilter || this.ext;
        const mode = (this.$('pbx-cdr-mode-filter') || {}).value || 'all';
        const hideSystem = (this.$('pbx-cdr-hide-system') || {}).checked ? '1' : '0';
        const range = (this.$('pbx-cdr-range-filter') || {}).value || '30';
        const dateFrom = (this.$('pbx-cdr-date-from') || {}).value || '';
        const dateTo = (this.$('pbx-cdr-date-to') || {}).value || '';

        let timeParams;
        if (dateFrom || dateTo) {
            // Von-Bis hat Vorrang vor dem Preset-Dropdown, sobald mind. ein Datum gesetzt ist
            timeParams = (dateFrom ? '&date_from=' + encodeURIComponent(dateFrom) : '') +
                         (dateTo ? '&date_to=' + encodeURIComponent(dateTo) : '');
        } else {
            timeParams = 'days=' + encodeURIComponent(range);
        }

        const url = this.api.cdr + '?extension=' + encodeURIComponent(extension) +
                    '&mode=' + encodeURIComponent(mode) +
                    '&' + timeParams +
                    '&hide_system=' + hideSystem +
                    '&sort_by=' + encodeURIComponent(this._cdrState.sortBy) +
                    '&sort_dir=' + encodeURIComponent(this._cdrState.sortDir) +
                    '&limit=100';

        try {
            const res = await this.get(url);
            const rows = res.rows || [];
            body.innerHTML = rows.length ? rows.map(r => this._cdrRow(r)).join('')
                : `<tr><td colspan="6" class="pbx-empty">${this.t('pbx_no_cdr', 'Keine Anrufe')}</td></tr>`;
        } catch (e) {
            body.innerHTML = `<tr><td colspan="6" class="pbx-empty">${this.t('pbx_load_error', 'Fehler beim Laden')}</td></tr>`;
        }
    },
    _cdrRow(r) {
        const dir = r.direction === 'outgoing'
            ? '<i class="bi bi-telephone-outbound" style="color:var(--abcona-blue)"></i>'
            : '<i class="bi bi-telephone-inbound" style="color:var(--status-green)"></i>';
        const nr = r.direction === 'incoming' ? r.src : r.dst;
        const contact = r.contact ? this.esc(r.contact.name) : '—';
        const ok = r.disposition === 'ANSWERED';
        return `<tr>
            <td>${this.esc((r.calldate || '').slice(0, 16))}</td>
            <td>${dir}</td>
            <td>${this.esc(nr)}</td>
            <td>${contact}</td>
            <td><span class="pbx-badge ${ok ? 'pbx-ok' : 'pbx-miss'}">${this.esc(r.disposition || '')}</span></td>
            <td>${this.esc(r.billsec_fmt || '')}</td>
        </tr>`;
    },

    /* ======================= STATISTIK ======================= */
    _statLabel(k) {
        const fb = {
            total: 'Gesamt', answered: 'Angenommen', missed: 'Verpasst',
            incoming: 'Eingehend', outgoing: 'Ausgehend', talk_sec: 'Gesprächszeit',
        };
        return this.t('pbx_stat_' + k, fb[k] || k);
    },
    _statValue(k, v) {
        return k === 'talk_sec' ? this.fmtDur(v) : v;
    },
    async loadStats() {
        const wrap = this.$('pbx-stats');
        if (!wrap) return;
        wrap.innerHTML = `<div class="pbx-empty">${this.t('pbx_loading', 'Lade…')}</div>`;
        try {
            const res = await this.get(this.api.stats + '?extension=' + encodeURIComponent(this.ext));
            const s = res.stats || {};
            const box = (title, o) => `<div class="pbx-statcard"><h4>${title}</h4>` +
                Object.entries(o || {}).map(([k, v]) =>
                    `<div class="pbx-statrow"><span>${this.esc(this._statLabel(k))}</span><span>${this.esc(this._statValue(k, v))}</span></div>`
                ).join('') + '</div>';
            wrap.innerHTML = box(this.t('pbx_today', 'Heute'), s.heute) + box(this.t('pbx_week', 'Woche'), s.woche) + box(this.t('pbx_month', 'Monat'), s.monat);
        } catch (e) {
            wrap.innerHTML = `<div class="pbx-empty">${this.t('pbx_load_error', 'Fehler beim Laden')}</div>`;
        }
    },
};

document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('pbx-root')) PBX.init();
});

// ============================================================
// Meetme-Planung (Reiter 1) - via Object.assign ergaenzt, um
// das bestehende PBX-Objektliteral nicht anfassen zu muessen.
// ============================================================
Object.assign(PBX.api, {
    meetmeMeetings:      '/meetme/api/meetings/',
    meetmeMeetingCreate: '/meetme/api/meetings/create/',
    meetmeRooms:         '/meetme/api/rooms/',
});

Object.assign(PBX, {
    _meetmeState: {
        meetings: [],
        selectedId: null,
        rooms: [],
        detailCache: {},
    },
    _meetmeGuestTimer: null,

    async meetmeSwitchSubtab(tab) {
        document.querySelectorAll('.pbx-subtabbtn').forEach(b => b.classList.remove('pbx-subtab-active'));
        const btn = document.querySelector(`.pbx-subtabbtn[data-subtab="${tab}"]`);
        if (btn) btn.classList.add('pbx-subtab-active');
        this.$('pbx-meetme-planung').style.display = (tab === 'planung') ? '' : 'none';
        this.$('pbx-meetme-cockpit').style.display = (tab === 'cockpit') ? '' : 'none';
        if (tab === 'planung' && !this._meetmeState.meetings.length) {
            await this.meetmeLoadMeetings();
        }
    },

    async meetmeLoadMeetings() {
        let data = null;
        try { data = await this.get(this.api.meetmeMeetings + '?archived=false'); }
        catch (e) { this.toast(this.t('pbx_meetme_load_err', 'Termine konnten nicht geladen werden')); return; }
        this._meetmeState.meetings = (data && data.length) ? data : (data.results || data || []);
        this.meetmeRenderStrip();
        if (this._meetmeState.meetings.length && !this._meetmeState.selectedId) {
            this.meetmeSelectMeeting(this._meetmeState.meetings[0].id);
        }
        if (this._mmArchiveState.open) this._mmLoadArchive();
    },

    _mmArchiveState: { open: false, filter: 'week', customFrom: '', customTo: '', items: [], loaded: false },

    _mmTileHtml(m, compact) {
        const cancelled = m.status === 'CANCELLED';
        const past = !cancelled && new Date(m.start_at).getTime() < Date.now();
        const statusCls = cancelled ? 'pbx-mm-tile-cancelled' : (past ? 'pbx-mm-tile-done' : 'pbx-mm-tile-ok');
        const activeCls = m.id === this._meetmeState.selectedId ? 'pbx-mm-tile-active' : '';
        const deleteBtn = compact ? `
            <div style="display:flex;justify-content:flex-end;margin-top:4px">
                <button type="button" title="${this.t('pbx_meetme_delete', 'Löschen')}"
                        style="border:none;background:transparent;color:#adb5bd;cursor:pointer;padding:2px 6px;border-radius:4px;font-size:14px;line-height:1"
                        onclick="event.stopPropagation(); PBX.meetmeDeleteArchived(${m.id})">
                    <i class="bi bi-trash"></i>
                </button>
            </div>` : '';
        return `
            <div class="pbx-meetme-card pbx-mm-tile ${statusCls} ${activeCls} ${compact ? 'pbx-mm-tile-compact' : ''}"
                 onclick="PBX.meetmeSelectMeeting(${m.id})">
                <div class="pbx-mm-tile-top">
                    <span class="pbx-mm-tile-dot"></span>
                    <span class="pm-title" style="margin:0">${this._meetmeEsc(m.title)}</span>
                    ${cancelled ? `<span class="pbx-meetme-badge declined" style="font-size:8.5px;margin-left:auto;flex-shrink:0">${this.t('pbx_meetme_status_cancelled', 'ABGESAGT')}</span>` : ''}
                </div>
                <p class="pm-date">${this._meetmeFmtDate(m.start_at)}</p>
                <p class="pm-guests"><i class="bi bi-people"></i> ${(m.guests || []).length} ${this.t('pbx_meetme_guests_short', 'Gäste')}</p>
                ${deleteBtn}
            </div>
        `;
    },

    meetmeRenderStrip() {
        const wrap = this.$('pbx-meetme-strip');
        if (!wrap) return;
        const active = this._meetmeState.meetings;
        wrap.innerHTML = active.map(m => this._mmTileHtml(m, false)).join('')
            || `<div class="pbx-hint">${this.t('pbx_meetme_none', 'Keine aktiven Termine')}</div>`;
        this._mmRenderArchiveBox();
        const inArchive = (this._mmArchiveState.items || []).some(m => m.id === this._meetmeState.selectedId);
        const stillActive = active.some(m => m.id === this._meetmeState.selectedId) || inArchive;
        if (!stillActive) {
            this._meetmeState.selectedId = null;
            const detail = this.$('pbx-meetme-detail');
            if (detail) {
                detail.innerHTML = `<div class="pbx-hint">${this.t('pbx_meetme_select_hint', 'Termin auswählen oder neuen Termin anlegen')}</div>`;
            }
        }
    },

    _mmRenderArchiveBox() {
        const box = this.$('pbx-meetme-archive');
        if (!box) return;
        box.style.display = '';
        const st = this._mmArchiveState;
        const filters = [
            ['week', this.t('pbx_mm_arch_week', 'Letzte Woche')],
            ['month', this.t('pbx_mm_arch_month', 'Letzter Monat')],
            ['year', this.t('pbx_mm_arch_year', 'Letztes Jahr')],
            ['all', this.t('pbx_mm_arch_all', 'Alle')],
        ];
        box.innerHTML = `
            <button class="pbx-act pbx-act-gray pbx-mm-archive-toggle" onclick="PBX._mmToggleArchive()">
                <i class="bi bi-chevron-${st.open ? 'down' : 'right'}"></i>
                ${this.t('pbx_meetme_archive', 'Archiv')}
            </button>
            <div style="display:${st.open ? '' : 'none'}">
                <div class="pbx-mm-archive-filterbar">
                    ${filters.map(([key, label]) => `
                        <span class="pbx-mm-archive-filt ${st.filter === key ? 'pbx-mm-archive-filt-active' : ''}"
                              onclick="PBX._mmSetArchiveFilter('${key}')">${label}</span>
                    `).join('')}
                    <span class="pbx-mm-archive-filt ${st.filter === 'custom' ? 'pbx-mm-archive-filt-active' : ''}"
                          onclick="PBX._mmSetArchiveFilter('custom')"><i class="bi bi-calendar-range"></i> ${this.t('pbx_mm_arch_custom', 'Zeitraum…')}</span>
                </div>
                ${st.filter === 'custom' ? `
                    <div style="display:flex;gap:6px;align-items:center;margin:0 0 10px">
                        <input type="date" id="pbx-mm-archive-from" value="${st.customFrom}" class="pbx-input" style="flex:1">
                        <span style="font-size:12px;color:var(--text-secondary)">${this.t('pbx_mm_arch_to', 'bis')}</span>
                        <input type="date" id="pbx-mm-archive-to" value="${st.customTo}" class="pbx-input" style="flex:1">
                        <button class="pbx-act pbx-act-gray" onclick="PBX._mmApplyCustomRange()">${this.t('pbx_mm_arch_apply', 'Anwenden')}</button>
                    </div>
                ` : ''}
                <div class="pbx-mm-archive-grid">
                    ${st.items.length
                        ? st.items.map(m => this._mmTileHtml(m, true)).join('')
                        : `<div class="pbx-hint">${this.t('pbx_mm_arch_empty', 'Keine Termine in diesem Zeitraum')}</div>`}
                </div>
            </div>
        `;
    },

    _mmSetArchiveFilter(key) {
        this._mmArchiveState.filter = key;
        if (key !== 'custom') this._mmLoadArchive();
        else this._mmRenderArchiveBox();
    },

    _mmApplyCustomRange() {
        const from = this.$('pbx-mm-archive-from');
        const to = this.$('pbx-mm-archive-to');
        this._mmArchiveState.customFrom = from ? from.value : '';
        this._mmArchiveState.customTo = to ? to.value : '';
        this._mmLoadArchive();
    },

    async _mmLoadArchive() {
        const st = this._mmArchiveState;
        const now = new Date();
        let dateFrom = null, dateTo = null;
        if (st.filter === 'week') { dateFrom = new Date(now.getTime() - 7 * 86400000); }
        else if (st.filter === 'month') { dateFrom = new Date(now.getTime() - 30 * 86400000); }
        else if (st.filter === 'year') { dateFrom = new Date(now.getTime() - 365 * 86400000); }
        else if (st.filter === 'custom') {
            if (st.customFrom) dateFrom = new Date(st.customFrom + 'T00:00:00');
            if (st.customTo) dateTo = new Date(st.customTo + 'T23:59:59');
        }
        let url = this.api.meetmeMeetings + '?archived=true';
        if (dateFrom) url += '&date_from=' + encodeURIComponent(dateFrom.toISOString());
        if (dateTo) url += '&date_to=' + encodeURIComponent(dateTo.toISOString());

        let data = null;
        try { data = await this.get(url); }
        catch (e) { this.toast(this.t('pbx_meetme_load_err', 'Termine konnten nicht geladen werden')); return; }
        st.items = (data && data.length) ? data : (data.results || data || []);
        st.loaded = true;
        this._mmRenderArchiveBox();
    },

    async _mmToggleArchive() {
        const st = this._mmArchiveState;
        st.open = !st.open;
        if (st.open && !st.loaded) { await this._mmLoadArchive(); return; }
        this._mmRenderArchiveBox();
    },

    async meetmeDeleteArchived(meetingId) {
        const st = this._mmArchiveState;
        const m = (st.items || []).find(x => x.id === meetingId);
        const title = m ? m.title : String(meetingId);
        if (!confirm(this.t('pbx_meetme_delete_confirm', 'Termin „{title}“ wirklich endgültig löschen?\n\nDer Termin wird dauerhaft aus der Datenbank entfernt. Dies kann nicht rückgängig gemacht werden.').replace('{title}', title))) return;
        try {
            const res = await this.del(`/meetme/api/meetings/${meetingId}/delete/`);
            if (res && res.error) throw new Error(res.error);
            st.items = (st.items || []).filter(x => x.id !== meetingId);
            if (this._meetmeState.selectedId === meetingId) {
                this._meetmeState.selectedId = null;
                const detail = this.$('pbx-meetme-detail');
                if (detail) {
                    detail.innerHTML = `<div class="pbx-hint">${this.t('pbx_meetme_select_hint', 'Termin auswählen oder neuen Termin anlegen')}</div>`;
                }
            }
            this.meetmeRenderStrip();
            this.toast(this.t('pbx_meetme_deleted', 'Termin gelöscht'));
        } catch (e) {
            this.toast(this.t('pbx_meetme_delete_err', 'Löschen fehlgeschlagen'));
        }
    },

    async meetmeSelectMeeting(id) {
        this._meetmeState.selectedId = id;
        this.meetmeRenderStrip();
        let m = null;
        try { m = await this.get(this.api.meetmeMeetings + id + '/'); }
        catch (e) { this.toast(this.t('pbx_meetme_load_err', 'Termin konnte nicht geladen werden')); return; }
        this._meetmeState.detailCache[id] = m;
        this.meetmeRenderDetail(m);
    },

    _mmFindMeeting(id) {
        return this._meetmeState.detailCache[id]
            || this._meetmeState.meetings.find(x => x.id === id)
            || (this._mmArchiveState.items || []).find(x => x.id === id)
            || null;
    },

    _mmComputeStatus(m) {
        const guests = (m.guests || []).filter(g => g.is_active !== false);
        const rules = m.reminder_rules || [];
        const invitedCount = guests.filter(g => !!g.invited_at).length;
        const total = guests.length;
        let inviteStatus, inviteClass, inviteTip;
        if (total === 0) {
            inviteStatus = this.t('pbx_mm_status_no_guests', 'Keine Gäste');
            inviteClass = 'neutral';
            inviteTip = this.t('pbx_mm_status_no_guests_tip', 'Es sind noch keine Gäste für diesen Termin hinterlegt.');
        } else if (invitedCount === 0) {
            inviteStatus = this.t('pbx_mm_status_none_invited', PBX.t('pbx_meetme_no_invites'));
            inviteClass = 'warning';
            inviteTip = this.t('pbx_mm_status_none_invited_tip', 'Noch keine Einladungs-E-Mail versendet. Einladungen über „Einladung senden“ oder den Assistenten starten.');
        } else if (invitedCount === total) {
            inviteStatus = this.t('pbx_mm_status_all_invited', 'Einladungen versendet');
            inviteClass = 'success';
            inviteTip = this.t('pbx_mm_status_all_invited_tip', 'Alle Gäste wurden per E-Mail über den Termin informiert.');
        } else {
            inviteStatus = this.t('pbx_mm_status_some_invited', 'Einladungen teilweise versendet');
            inviteClass = 'warning';
            inviteTip = this.t('pbx_mm_status_some_invited_tip', 'Nicht alle Gäste wurden per E-Mail informiert. Fehlende Einladungen über den Assistenten nachsenden.');
        }

        const coversAll = rules.some(r => !r.guest);
        let remindersSetCount;
        if (coversAll) remindersSetCount = total;
        else {
            const guestIdsWithRule = new Set(rules.map(r => r.guest).filter(Boolean));
            remindersSetCount = guests.filter(g => guestIdsWithRule.has(g.id)).length;
        }

        const agreedTip = this.t('pbx_mm_status_agreed_tip', 'Der Termin ist in der Planung angelegt und aktiv — noch nicht abgesagt.');
        const remindersTip = this.t('pbx_mm_status_reminders_tip', 'Zeigt, für wie viele Gäste automatische Erinnerungen eingerichtet sind. Unter „Erinnerungen verwalten“ konfigurieren.');

        return `
            <span class="pbx-mm-status-pill success" title="${this._meetmeEsc(agreedTip)}"><i class="bi bi-check-circle-fill"></i> ${this.t('pbx_mm_status_agreed', PBX.t('pbx_meetme_termin_ok'))}</span>
            <span class="pbx-mm-status-pill ${inviteClass}" title="${this._meetmeEsc(inviteTip)}">${inviteStatus}</span>
            <span class="pbx-mm-status-pill neutral" title="${this._meetmeEsc(remindersTip)}">${this.t('pbx_mm_status_reminders', 'Erinnerungen')}: ${remindersSetCount} ${this.t('pbx_mm_status_of', 'von')} ${total} ${this.t('pbx_mm_status_guests', 'Gästen')} ${this.t('pbx_mm_status_set', 'eingerichtet')}</span>
        `;
    },

    meetmeToggleGuestAdd() {
        const wrap = this.$('pbx-meetme-guest-search-wrap');
        if (!wrap) return;
        const show = wrap.style.display === 'none';
        wrap.style.display = show ? 'flex' : 'none';
        if (show) { const i = this.$('pbx-meetme-guest-search'); if (i) i.focus(); }
    },

    async meetmeSaveDescription(meetingId, value) {
        try {
            await this.patchReq(`/meetme/api/meetings/${meetingId}/update/`, { description: value });
        } catch (e) {
            this.toast(this.t('pbx_mm_note_save_err', 'Bemerkung konnte nicht gespeichert werden'));
        }
    },

    _mmNoteCancel() {
        const ta = this.$('pbx-mm-note');
        if (ta) ta.value = ta.dataset.original || '';
    },

    async _mmNoteSave(meetingId) {
        const ta = this.$('pbx-mm-note');
        if (!ta) return;
        const value = ta.value;
        await this.meetmeSaveDescription(meetingId, value);
        ta.dataset.original = value;
        this.toast(this.t('pbx_mm_note_saved', 'Bemerkung gespeichert'));
    },

    meetmeRenderDetail(m) {
        this._meetmeEnsureDragStyles();
        const wrap = this.$('pbx-meetme-detail');
        if (!wrap) return;
        const guests = m.guests || [];
        const rules = m.reminder_rules || [];
        wrap.innerHTML = `
            <div class="pbx-mm-card">
                <div class="pbx-mm-hdrgrid">
                    <div><label>${this.t('pbx_meetme_field_title', 'Titel')}</label><span class="val">${this._meetmeEsc(m.title)}${m.status === 'CANCELLED' ? ` <span class="pbx-meetme-badge declined">${this.t('pbx_meetme_status_cancelled', 'ABGESAGT')}</span>` : ''}</span></div>
                    <div><label>${this.t('pbx_meetme_field_start', 'Datum')}</label><span class="val">${this._meetmeFmtDateTime(m.start_at)}</span></div>
                    <div><label>${this.t('pbx_meetme_field_duration', 'Dauer')}</label><span class="val">${m.duration_minutes} min</span></div>
                    <div><label>${this.t('pbx_meetme_field_room', 'Konferenzraum')}</label><span class="val">${m.room_extension || '—'}</span></div>
                </div>
                <div style="display:flex;gap:6px">
                    <button class="pbx-act pbx-act-gray" onclick="PBX.meetmeShowEditModal(${m.id})">
                        <i class="bi bi-pencil"></i> ${this.t('pbx_meetme_edit', 'Bearbeiten')}
                    </button>
                    <button class="pbx-act pbx-act-blue" onclick="PBX.meetmeShowRescheduleModal(${m.id})">
                        <i class="bi bi-calendar-week"></i> ${this.t('pbx_meetme_reschedule', 'Termin verschieben')}
                    </button>
                    <button class="pbx-act pbx-act-red" onclick="PBX.meetmeShowCancelConfirm(${m.id})">
                        <i class="bi bi-x-circle"></i> ${this.t('pbx_meetme_cancel_meeting', 'Absagen')}
                    </button>${m.description ? `<span class="pbx-hint pbx-mm-desc-preview" style="margin:0 0 0 auto;align-self:center;max-width:260px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${this._meetmeEsc(m.description)}"><i class="bi bi-card-text"></i> ${this._meetmeEsc(m.description)}</span>` : ''}
                </div>
            </div>

            <div class="pbx-mm-status-row">${this._mmComputeStatus(m)}</div>

            <div class="pbx-mm-card">
                <p style="font-size:12.5px;font-weight:600;margin:0 0 8px">${this.t('pbx_meetme_guests_head', 'Gäste')}</p>
                <div id="pbx-meetme-guestlist">
                    ${guests.map(g => {
                        const invited = !!g.invited_at;
                        const declined = g.status === 'DECLINED' || g.is_active === false;
                        let badge;
                        if (declined) {
                            badge = `<span class="pbx-meetme-badge declined">${this.t('pbx_mm_status_declined', 'Nimmt nicht teil')}</span>`;
                        } else if (invited) {
                            badge = `<span class="pbx-meetme-badge confirmed">${this.t('pbx_mm_status_invited', 'Eingeladen')}</span>`;
                        } else {
                            badge = `<button class="pbx-meetme-badge pending" style="border:none;cursor:pointer" onclick="PBX.meetmeOpenInviteAssistant(${m.id})" title="${this.t('pbx_mm_status_pending_hint', 'Klicken zum Einladen')}">${this.t('pbx_mm_status_pending', PBX.t('pbx_meetme_invite_pending'))}</button>`;
                        }
                        const trashOnclick = (invited && !declined) ? `PBX.meetmeRequestDecline(${g.id}, ${m.id})` : `PBX.meetmeDeleteGuest(${g.id}, ${m.id})`;
                        const trashTitle = (invited && !declined) ? this.t('pbx_mm_mark_declined', 'Nimmt nicht teil markieren') : this.t('pbx_delete', 'Löschen');
                        return `
                        <div class="pbx-meetme-guestrow">
                            <span>
                                <span class="pbx-mm-clickable" onclick="PBX.meetmeShowGuestPhone(${g.id})">${this._meetmeEsc(g.name)}</span>
                                <span class="pbx-mm-clickable" style="color:#999" onclick="PBX.meetmeShowGuestCompose(${g.id})">${this._meetmeEsc(g.email || '')}</span>
                            </span>
                            <span style="display:flex;align-items:center;gap:6px">
                                ${badge}
                                <button class="pbx-act pbx-act-gray" style="padding:3px 7px" onclick="${trashOnclick}" title="${trashTitle}"><i class="bi bi-trash"></i></button>
                            </span>
                        </div>
                    `;
                    }).join('') || `<div class="pbx-hint">${this.t('pbx_meetme_no_guests', 'Noch keine Gäste')}</div>`}
                </div>
                <button class="pbx-act pbx-mm-add-guest-btn" style="width:100%;justify-content:center;margin-top:8px" onclick="PBX.meetmeToggleGuestAdd()">
                    <i class="bi bi-plus-lg"></i> ${this.t('pbx_mm_add_guest', 'Weiterer Gast')}
                </button>
                <div id="pbx-meetme-guest-search-wrap" style="position:relative;display:none;gap:6px;margin-top:8px">
                    <input id="pbx-meetme-guest-search" class="pbx-input" style="flex:1" autocomplete="off"
                           placeholder="${this.t('pbx_meetme_guest_search_ph', 'Kontakt suchen…')}"
                           oninput="PBX.meetmeGuestSearch(this, ${m.id})">
                    <button class="pbx-act pbx-act-gray" style="white-space:nowrap" onclick="PBX.meetmeShowNewContactModal(${m.id})">
                        <i class="bi bi-person-plus"></i> ${this.t('pbx_mm_new_contact', 'Neuer Kontakt')}
                    </button>
                </div>
            </div>

            <div class="pbx-mm-card">
                <button class="pbx-act pbx-act-green" style="margin-bottom:14px" onclick="PBX.meetmeOpenInviteAssistant(${m.id})">
                    <i class="bi bi-envelope-plus"></i> ${this.t('pbx_meetme_invite', PBX.t('pbx_meetme_to_invites'))}
                </button>
                <button class="pbx-act pbx-act-warn" style="margin-bottom:14px" onclick="PBX.meetmeOpenReminderPanel(${m.id})">
                    <i class="bi bi-bell"></i> ${this.t('pbx_meetme_reminders_manage', PBX.t('pbx_meetme_manage_reminders'))}
                </button>
                <label style="font-size:11px;color:var(--text-secondary);display:block;margin:0 0 4px">${this.t('pbx_mm_note', 'Bemerkung')}</label>
                <textarea id="pbx-mm-note" class="pbx-input" style="width:100%;box-sizing:border-box" rows="2"
                          data-original="${this._meetmeEsc(m.description || '')}"
                          placeholder="${this.t('pbx_mm_note_ph', 'Interne Notiz zum Termin…')}">${this._meetmeEsc(m.description || '')}</textarea>
                <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:8px">
                    <button class="pbx-act pbx-act-gray" onclick="PBX._mmNoteCancel()">
                        <i class="bi bi-x-lg"></i> ${this.t('pbx_cancel', 'Abbrechen')}
                    </button>
                    <button class="pbx-act pbx-act-green" onclick="PBX._mmNoteSave(${m.id})">
                        <i class="bi bi-check-lg"></i> ${this.t('pbx_meetme_save', 'Speichern')}
                    </button>
                </div>
            </div>

        `;
    },

    meetmeGuestSearch(inp, meetingId) {
        const q = (inp.value || '').trim();
        clearTimeout(this._meetmeGuestTimer);
        if (q.length < 2) return;
        this._meetmeGuestTimer = setTimeout(async () => {
            let data = null;
            try { data = await this.get(this.api.searchAll + '?q=' + encodeURIComponent(q) + '&scope=personen&size=8'); }
            catch (e) { return; }
            const results = (data && data.results) || [];
            this._meetmeRenderGuestResults(inp, results, meetingId);
        }, 300);
    },

    _meetmeRenderGuestResults(inp, results, meetingId) {
        let pop = document.getElementById('pbx-meetme-guest-pop');
        if (pop) pop.remove();
        const wrap = document.getElementById('pbx-meetme-guest-search-wrap');
        if (!wrap) return;
        pop = document.createElement('div');
        pop.id = 'pbx-meetme-guest-pop';
        pop.className = 'pbx-meetme-guest-pop';
        pop.innerHTML = results.map((r, i) => `
            <div class="pbx-meetme-guest-pop-item" onclick="PBX.meetmeGuestAdd(${meetingId}, ${i})">
                <span>${this._meetmeEsc(r.title || '')}</span>
                <span class="pbx-meetme-guest-pop-meta">${this._meetmeEsc(r.meta || '')}</span>
            </div>
        `).join('') + `
            <div class="pbx-meetme-guest-pop-item pbx-mm-newcontact-item" onclick="PBX.meetmeShowNewContactModal(${meetingId})">
                <span><i class="bi bi-person-plus"></i> ${this.t('pbx_mm_new_contact', 'Neuer Kontakt anlegen')}</span>
            </div>
        `;
        wrap.appendChild(pop);
        this._meetmeSearchResults = results;
    },

    async meetmeGuestAdd(meetingId, idx) {
        const r = (this._meetmeSearchResults || [])[idx];
        const pop = document.getElementById('pbx-meetme-guest-pop');
        if (pop) pop.remove();
        if (!r) return;

        let detail = null;
        try { detail = await this.get(`/crm/api/berater/${r.id}/`); }
        catch (e) { /* Detail nicht verfuegbar */ }

        const emails = (detail && Array.isArray(detail.emails)) ? detail.emails.filter(e => !e.invalid_email) : [];
        const phones = (detail && Array.isArray(detail.phones)) ? detail.phones : [];
        const phone = (phones.find(p => p.is_primary) || phones[0] || {}).raw || '';

        if (emails.length <= 1) {
            const email = (emails[0] && emails[0].email) || '';
            if (!email) this.toast(this.t('pbx_meetme_guest_no_email', 'Keine E-Mail gefunden - bitte manuell ergänzen'));
            await this._meetmeGuestSave(meetingId, r, email, phone);
            return;
        }

        // Mehrere E-Mails - Auswahl-Dialog zeigen
        this._meetmeShowEmailChoice(meetingId, r, emails, phone);
    },

    _meetmeShowEmailChoice(meetingId, r, emails, phone) {
        document.querySelectorAll('#pbx-meetme-modal-overlay').forEach(el => el.remove());
        const overlay = document.createElement('div');
        overlay.className = 'pbx-meetme-modal-overlay';
        overlay.id = 'pbx-meetme-modal-overlay';
        overlay.innerHTML = `
            <div class="pbx-meetme-modal">
                <h4>${this.t('pbx_meetme_choose_email', 'E-Mail-Adresse wählen')} — ${this._meetmeEsc(r.title || '')}</h4>
                <p style="font-size:12px;color:#888;margin:0 0 10px">${this.t('pbx_meetme_choose_email_hint', 'Dieser Kontakt hat mehrere E-Mail-Adressen. Eine oder mehrere auswählen (mehrere = mehrere Gast-Einträge).')}</p>
                <div id="pbx-mm-email-list">
                    ${emails.map((e, i) => `
                        <label style="display:flex;align-items:center;gap:8px;padding:6px 0;font-size:12.5px">
                            <input type="checkbox" class="pbx-mm-email-cb" value="${i}" ${e.primary ? 'checked' : ''} style="width:auto">
                            ${this._meetmeEsc(e.email)} ${e.primary ? '<span style="color:#999;font-size:11px">(primär)</span>' : ''}
                        </label>
                    `).join('')}
                </div>
                <div class="pbx-meetme-modal-actions">
                    <button class="pbx-act pbx-act-gray" onclick="PBX.meetmeCloseModal()">${this.t('pbx_cancel', 'Abbrechen')}</button>
                    <button class="pbx-act pbx-act-green" onclick="PBX.meetmeConfirmEmailChoice(${meetingId})">${this.t('pbx_meetme_add', 'Hinzufügen')}</button>
                </div>
            </div>
        `;
        this._meetmeMountModal(overlay);
        this._meetmeChoiceCtx = { r, emails, phone };
    },

    async meetmeConfirmEmailChoice(meetingId) {
        const ctx = this._meetmeChoiceCtx;
        const checked = Array.from(document.querySelectorAll('.pbx-mm-email-cb:checked')).map(cb => parseInt(cb.value, 10));
        this.meetmeCloseModal();
        if (!ctx || !checked.length) {
            this.toast(this.t('pbx_meetme_choose_email_none', 'Keine E-Mail ausgewählt'));
            return;
        }
        for (const idx of checked) {
            const email = ctx.emails[idx].email;
            await this._meetmeGuestSave(meetingId, ctx.r, email, ctx.phone);
        }
    },

    async _meetmeGuestSave(meetingId, r, email, phone) {
        try {
            await this.post(`/meetme/api/meetings/${meetingId}/guests/create/`, {
                contact_crm_id: r.id || null,
                name: r.title || '',
                email: email || `noemail-${r.id}@platzhalter.invalid`,
                phone: phone || '',
            });
            this.toast(this.t('pbx_meetme_guest_added', 'Gast hinzugefügt'));
            const searchInp = this.$('pbx-meetme-guest-search');
            if (searchInp) searchInp.value = '';
            this.meetmeSelectMeeting(meetingId);
        } catch (e) {
            this.toast(this.t('pbx_meetme_guest_err', 'Gast konnte nicht hinzugefügt werden'));
        }
    },

    async meetmeShowNewModal() {
        let rooms = [];
        try { const d = await this.get(this.api.meetmeRooms); rooms = d.rooms || []; } catch (e) {}
        document.querySelectorAll('#pbx-meetme-modal-overlay').forEach(el => el.remove());
        const overlay = document.createElement('div');
        overlay.className = 'pbx-meetme-modal-overlay';
        overlay.id = 'pbx-meetme-modal-overlay';
        overlay.innerHTML = `
            <div class="pbx-meetme-modal">
                <h4>${this.t('pbx_meetme_new', 'Neuer Termin')}</h4>
                <label>${this.t('pbx_meetme_field_title', 'Titel')}</label>
                <input id="pbx-mm-title" type="text">
                <label>${this.t('pbx_meetme_field_start', 'Datum/Zeit')}</label>
                <input id="pbx-mm-start" type="datetime-local">
                <label>${this.t('pbx_meetme_field_duration', 'Dauer (Minuten)')}</label>
                <input id="pbx-mm-duration" type="number" value="60">
                <label>${this.t('pbx_meetme_field_room', 'Konferenzraum')}</label>
                <select id="pbx-mm-room">
                    <option value="">${this.t('pbx_meetme_room_none', '– kein fester Raum –')}</option>
                    ${rooms.map(r => `<option value="${r.room_extension}">${r.room_extension}${r.hint_state ? ' (' + r.hint_state + ')' : ''}</option>`).join('')}
                </select>
                <div class="pbx-meetme-modal-actions">
                    <button class="pbx-act pbx-act-gray" onclick="PBX.meetmeCloseModal()">${this.t('pbx_cancel', 'Abbrechen')}</button>
                    <button class="pbx-act pbx-act-green" onclick="PBX.meetmeCreateMeeting()">${this.t('pbx_meetme_create', 'Termin anlegen')}</button>
                </div>
            </div>
        `;
        this._meetmeMountModal(overlay);
    },

    _meetmeModalDragPos: null,

    meetmeCloseModal() {
        // Alle Overlays entfernen, nicht nur eins - falls durch einen Bug
        // mehrere gleichzeitig im DOM haengen, sonst liest getElementById()
        // andernorts weiterhin aus einer verwaisten Kopie.
        document.querySelectorAll('#pbx-meetme-modal-overlay').forEach(el => el.remove());
        this._meetmeModalDragPos = null;
        this._mmCollapsibleState = {};
    },

    _meetmeEnsureDragStyles() {
        if (document.getElementById('pbx-mm-drag-styles')) return;
        const s = document.createElement('style');
        s.id = 'pbx-mm-drag-styles';
        s.textContent = [
            '.pbx-meetme-modal-overlay.pbx-mm-drag-active{align-items:flex-start!important;justify-content:flex-start!important;}',
            '.pbx-meetme-modal.pbx-mm-drag-positioned{position:absolute;margin:0;max-height:calc(100vh - 16px);overflow:auto;}',
            '.pbx-mm-modal-drag-handle{cursor:grab;user-select:none;-webkit-user-select:none;}',
            '.pbx-mm-modal-drag-handle:active{cursor:grabbing;}',
            '.pbx-mm-collapsible{border:1px solid var(--border-color);border-radius:8px;margin-bottom:10px;background:var(--bg-white);overflow:hidden;color:var(--text-primary);}',
            '.pbx-mm-collapsible-hdr{width:100%;display:flex;justify-content:space-between;align-items:center;gap:8px;padding:10px 12px;background:var(--abcona-gray-bg);border:none;cursor:pointer;font-size:12px;font-weight:600;color:var(--text-secondary);text-align:left;}',
            '.pbx-mm-collapsible-hdr span{font-size:12.5px;font-weight:600;color:var(--text-primary);}',
            '.pbx-mm-collapsible-hdr .pbx-mm-collapsible-chevron{color:var(--text-muted);font-size:14px;flex-shrink:0;}',
            '.pbx-mm-collapsible:not(.pbx-mm-collapsed) .pbx-mm-collapsible-hdr{border-radius:8px 8px 0 0;}',
            '.pbx-mm-collapsible.pbx-mm-collapsed .pbx-mm-collapsible-hdr{border-radius:8px;}',
            '.pbx-mm-collapsible-body{padding:10px 12px 12px;}',
            '.pbx-mm-collapsible.pbx-sa-ds .pbx-mm-collapsible-hdr span{color:var(--text-primary);}',
            '.pbx-mm-add-guest-btn{background:var(--badge-success-bg)!important;color:var(--badge-success-text)!important;border:1px solid var(--status-green)!important;}',
            '.pbx-mm-add-guest-btn:hover{background:var(--status-green-bg)!important;}',
            '.pbx-mm-status-pill[title]{cursor:help;}',
        ].join('');
        document.head.appendChild(s);
    },

    _mmCollapsibleState: {},

    _mmCollapsibleIsOpen(id, defaultOpen) {
        if (Object.prototype.hasOwnProperty.call(this._mmCollapsibleState, id)) {
            return this._mmCollapsibleState[id];
        }
        return !!defaultOpen;
    },

    _mmToggleCollapsible(id) {
        const body = this.$(id);
        if (!body) return;
        const wrap = body.closest('.pbx-mm-collapsible');
        const open = body.style.display === 'none';
        body.style.display = open ? 'block' : 'none';
        this._mmCollapsibleState[id] = open;
        if (wrap) {
            wrap.classList.toggle('pbx-mm-collapsed', !open);
            const chev = wrap.querySelector('.pbx-mm-collapsible-chevron');
            if (chev) chev.className = 'bi ' + (open ? 'bi-chevron-up' : 'bi-chevron-down') + ' pbx-mm-collapsible-chevron';
            const btn = wrap.querySelector('.pbx-mm-collapsible-hdr');
            if (btn) btn.setAttribute('aria-expanded', open ? 'true' : 'false');
        }
    },

    _mmRenderCollapsible(bodyId, title, bodyHtml, opts) {
        opts = opts || {};
        const open = this._mmCollapsibleIsOpen(bodyId, opts.defaultOpen);
        const icon = opts.icon ? `<i class="bi ${opts.icon}"></i> ` : '';
        const cls = opts.className ? ' ' + opts.className : '';
        return `
<div class="pbx-mm-collapsible${cls}${open ? '' : ' pbx-mm-collapsed'}">
  <button type="button" class="pbx-mm-collapsible-hdr" onclick="PBX._mmToggleCollapsible('${bodyId}')" aria-expanded="${open}">
    <span>${icon}${title}</span>
    <i class="bi ${open ? 'bi-chevron-up' : 'bi-chevron-down'} pbx-mm-collapsible-chevron"></i>
  </button>
  <div class="pbx-mm-collapsible-body" id="${bodyId}" style="display:${open ? 'block' : 'none'}">${bodyHtml}</div>
</div>`;
    },

    _mmRenderDeepseekPanel(bodyId, topId, bottomId, suggestOnclick, applyOnclick) {
        const inner = `
            <div style="display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap">
                <button class="pbx-act pbx-act-gray" onclick="${suggestOnclick}"><i class="bi bi-arrow-clockwise"></i> ${this.t('pbx_sa_suggest', 'Vorschlag generieren')}</button>
                <button class="pbx-act pbx-act-blue" onclick="${applyOnclick}"><i class="bi bi-check2-circle"></i> ${this.t('pbx_sa_apply', 'Vorschlag übernehmen')}</button>
            </div>
            <label>${this.t('pbx_sa_your_text', 'Ihr Text (oben, wird gesendet)')}</label>
            <textarea id="${topId}" rows="3"></textarea>
            <label>${this.t('pbx_sa_suggestion', 'DeepSeek-Vorschlag (zum Rueckkopieren)')}</label>
            <textarea id="${bottomId}" rows="3" readonly></textarea>
        `;
        return this._mmRenderCollapsible(bodyId, this.t('pbx_sa_deepseek', 'DeepSeek-Raupe'), inner, { icon: 'bi-stars', className: 'pbx-sa-ds' });
    },

    _meetmeMountModal(overlay) {
        this._meetmeEnsureDragStyles();
        document.body.appendChild(overlay);
        if (overlay.id === 'pbx-meetme-modal-overlay' && overlay.querySelector('.pbx-meetme-modal')) {
            this._meetmeInitModalDrag(overlay);
        }
    },

    _meetmeInitModalDrag(overlay) {
        const modal = overlay.querySelector('.pbx-meetme-modal');
        if (!modal || overlay.dataset.mmDragInit === '1') return;
        overlay.dataset.mmDragInit = '1';

        const pos = this._meetmeModalDragPos;
        if (pos && pos.x != null && pos.y != null) {
            overlay.classList.add('pbx-mm-drag-active');
            modal.classList.add('pbx-mm-drag-positioned');
            modal.style.left = pos.x + 'px';
            modal.style.top = pos.y + 'px';
        }

        let handle = modal.querySelector('.pbx-mm-modal-drag-handle');
        if (!handle && modal.firstElementChild) {
            handle = modal.firstElementChild;
            handle.classList.add('pbx-mm-modal-drag-handle');
        }
        if (!handle) return;

        handle.addEventListener('mousedown', (e) => {
            if (e.button !== 0) return;
            if (e.target.closest('button, input, select, textarea, a, label, .pbx-wizard-tab')) return;

            const rect = modal.getBoundingClientRect();
            overlay.classList.add('pbx-mm-drag-active');
            modal.classList.add('pbx-mm-drag-positioned');
            const startX = e.clientX;
            const startY = e.clientY;
            const origX = this._meetmeModalDragPos ? this._meetmeModalDragPos.x : rect.left;
            const origY = this._meetmeModalDragPos ? this._meetmeModalDragPos.y : rect.top;
            modal.style.left = origX + 'px';
            modal.style.top = origY + 'px';

            const onMove = (ev) => {
                let nx = origX + (ev.clientX - startX);
                let ny = origY + (ev.clientY - startY);
                const pad = 8;
                const mw = modal.offsetWidth;
                const mh = modal.offsetHeight;
                nx = Math.max(pad, Math.min(nx, window.innerWidth - mw - pad));
                ny = Math.max(pad, Math.min(ny, window.innerHeight - Math.min(mh, window.innerHeight - pad * 2) - pad));
                modal.style.left = nx + 'px';
                modal.style.top = ny + 'px';
                this._meetmeModalDragPos = { x: nx, y: ny };
            };
            const onUp = () => {
                document.removeEventListener('mousemove', onMove);
                document.removeEventListener('mouseup', onUp);
            };
            e.preventDefault();
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        });
    },

    async meetmeCreateMeeting() {
        const title = this.$('pbx-mm-title').value.trim();
        const start = this.$('pbx-mm-start').value;
        const duration = parseInt(this.$('pbx-mm-duration').value, 10) || 60;
        const room = this.$('pbx-mm-room').value;
        if (!title || !start) { this.toast(this.t('pbx_meetme_fields_req', 'Titel und Datum erforderlich')); return; }
        try {
            const created = await this.post(this.api.meetmeMeetingCreate, {
                title, start_at: new Date(start).toISOString(),
                duration_minutes: duration, room_extension: room,
            });
            this.meetmeCloseModal();
            this.toast(this.t('pbx_meetme_created', 'Termin angelegt'));
            this._meetmeState.meetings.unshift(created);
            this._meetmeState.selectedId = created.id;
            this.meetmeRenderStrip();
            this.meetmeRenderDetail(created);
        } catch (e) {
            this.toast(this.t('pbx_meetme_create_err', 'Termin konnte nicht angelegt werden'));
        }
    },

    _meetmeFmtDate(iso) {
        const d = new Date(iso);
        return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' }) + ' ' + d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
    },
    _meetmeFmtDateTime(iso) {
        const d = new Date(iso);
        return d.toLocaleDateString('de-DE') + ', ' + d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
    },
    _meetmeEsc(s) {
        const div = document.createElement('div');
        div.textContent = s || '';
        return div.innerHTML;
    },

    _mmSanitizePreviewHtml(html) {
        return String(html || '')
            .replace(/<script[\s\S]*?<\/script>/gi, '')
            .replace(/\son\w+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi, '')
            .replace(/javascript:/gi, '')
            .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
            .replace(/<object[\s\S]*?<\/object>/gi, '')
            .replace(/<embed[\s\S]*?\/?>/gi, '');
    },

    _mmMountPreviewHtml(bodyEl, html, className, height) {
        if (!bodyEl) return;
        const safeHtml = this._mmSanitizePreviewHtml(html);
        let iframe = bodyEl.querySelector('iframe.' + className);
        if (!iframe) {
            bodyEl.innerHTML = '';
            iframe = document.createElement('iframe');
            iframe.className = className;
            iframe.style.cssText = `width:100%;height:${height}px;border:1px solid var(--border-color);border-radius:8px;display:block;background:var(--bg-white)`;
            iframe.setAttribute('sandbox', '');
            iframe.setAttribute('referrerpolicy', 'no-referrer');
            iframe.title = this.t('pbx_mm_notify_tab_html', 'HTML');
            bodyEl.appendChild(iframe);
        }
        iframe.srcdoc = safeHtml;
    },
});

Object.assign(PBX, {
    async del(url) {
        const r = await fetch(url, {
            method: 'DELETE',
            headers: { 'X-CSRFToken': this.csrf(), 'X-Requested-With': 'XMLHttpRequest' },
        });
        if (r.status === 204) return { success: true };
        try { return await r.json(); }
        catch (e) { return { success: r.ok }; }
    },
});

// ============================================================
// Sende-Assistent (Meetme Erinnerungs-Queue)
// ============================================================

// ============================================================
// Einladungs-Assistent (Meetme Gast-Einladungen)
// ============================================================
Object.assign(PBX, {
    meetmeOpenInviteAssistant(meetingId) {
        this.meetmeOpenWizard(meetingId, 'invite');
    },
});

Object.assign(PBX.api, {
    meetmeDeliveryQueue: '/meetme/api/deliveries/queue/',
    emailTemplates: '/email-studio/api/templates/',
});

Object.assign(PBX, {
    _meetmeInitials(name) {
        return (name || '').split(' ').map(p => p[0] || '').join('').slice(0, 2).toUpperCase();
    },

});


Object.assign(PBX, {
    async meetmeDeleteGuest(guestId, meetingId) {
        try {
            await this.del(`/meetme/api/guests/${guestId}/delete/`);
            this.toast(this.t('pbx_meetme_guest_deleted', 'Gast entfernt'));
            this.meetmeSelectMeeting(meetingId);
        } catch (e) {
            this.toast(this.t('pbx_meetme_guest_del_err', 'Konnte nicht entfernt werden'));
        }
    },

    async meetmeRequestDecline(guestId, meetingId) {
        if (!confirm(this.t('pbx_mm_decline_confirm', 'Gast als "nimmt nicht teil" markieren?'))) return;
        const inform = confirm(this.t('pbx_mm_decline_inform', 'Andere Gäste über die Absage informieren?'));
        try {
            await this.patchReq(`/meetme/api/guests/${guestId}/update/`, { status: 'DECLINED', is_active: false });
            this.toast(inform
                ? this.t('pbx_mm_decline_saved_inform', 'Vermerkt — bitte andere Gäste informieren (manuell)')
                : this.t('pbx_mm_decline_saved', 'Vermerkt: nimmt nicht teil'));
            this.meetmeSelectMeeting(meetingId);
        } catch (e) {
            this.toast(this.t('pbx_mm_decline_err', 'Konnte nicht gespeichert werden'));
        }
    },
});


// ============================================================
// Gast-Popovers: Telefon (Click-to-Dial) + Ad-hoc Mail-Compose
// ============================================================
Object.assign(PBX, {
    _mmGuestCache: {},

    async meetmeShowGuestPhone(guestId) {
        const g = this._mmFindGuestObj(guestId);
        let phones = [];

        if (g && g.contact_crm_id) {
            try {
                const detail = await this.get(`/crm/api/berater/${g.contact_crm_id}/`);
                if (detail && Array.isArray(detail.phones)) {
                    phones = detail.phones.map(p => ({ raw: p.raw, label: p.label || p.field_name || '', primary: p.is_primary }));
                }
            } catch (e) { /* Fallback unten */ }
        }
        if (!phones.length && g && g.phone) {
            phones = [{ raw: g.phone, label: '', primary: true }];
        }
        phones.sort((a, b) => (b.primary ? 1 : 0) - (a.primary ? 1 : 0));

        document.querySelectorAll('#pbx-meetme-modal-overlay').forEach(el => el.remove());
        const overlay = document.createElement('div');
        overlay.className = 'pbx-meetme-modal-overlay';
        overlay.id = 'pbx-meetme-modal-overlay';
        overlay.innerHTML = `
            <div class="pbx-meetme-modal" style="width:340px">
                <h4>${this.t('pbx_mm_call', 'Anrufen')} — ${this._meetmeEsc(g ? g.name : '')}</h4>
                ${phones.length ? `
                    <div style="display:flex;flex-direction:column;gap:6px;margin-bottom:12px">
                        ${phones.map(p => `
                            <div style="display:flex;justify-content:space-between;align-items:center;padding:6px 8px;background:var(--abcona-surface-1,#f7f7f7);border-radius:6px">
                                <span style="font-size:13px;font-weight:600">${this._meetmeEsc(p.raw)}${p.label ? ` <span style="font-weight:400;color:#999;font-size:11px">(${this._meetmeEsc(p.label)})</span>` : ''}${p.primary ? ' <span style="color:#999;font-size:11px">★</span>' : ''}</span>
                                <button class="pbx-act pbx-act-green" style="padding:4px 10px" onclick="PBX.meetmeDialGuest('${p.raw}')"><i class="bi bi-telephone-outbound"></i></button>
                            </div>
                        `).join('')}
                    </div>
                    <div class="pbx-meetme-modal-actions">
                        <button class="pbx-act pbx-act-gray" onclick="PBX.meetmeCloseModal()">${this.t('pbx_cancel', 'Schließen')}</button>
                    </div>
                ` : `
                    <p class="pbx-hint">${this.t('pbx_mm_no_phone', 'Keine Telefonnummer hinterlegt')}</p>
                    <div class="pbx-meetme-modal-actions">
                        <button class="pbx-act pbx-act-gray" onclick="PBX.meetmeCloseModal()">${this.t('pbx_cancel', 'Schließen')}</button>
                    </div>
                `}
            </div>
        `;
        this._meetmeMountModal(overlay);
    },

    _mmFindGuestObj(guestId) {
        const m = this._mmFindMeeting(this._meetmeState.selectedId);
        if (!m || !m.guests) return null;
        return m.guests.find(x => x.id === guestId) || null;
    },

    async meetmeDialGuest(phone) {
        this.meetmeCloseModal();
        const desk = (this.$('pbx-dial-ext') || {}).value || this.ext;
        try {
            const res = await this.post(this.api.dial, { desk, target: phone });
            this.toast(res.success ? this.t('pbx_dialing', 'Wird angerufen') : (res.error || this.t('pbx_dial_err', 'Anruf fehlgeschlagen')));
        } catch (e) {
            this.toast(this.t('pbx_dial_err', 'Anruf fehlgeschlagen'));
        }
    },

    _mmComposeState: {
        guestId: null, meetingId: null,
        allTemplates: false, templates: [],
        sigOverride: false, sigId: null, signatures: [],
        attachment_refs: [],
        attachPanelOpen: false, attachTab: 'search', attachSource: 'office',
        attachSearchResults: [], attachBrowsePath: '', attachBrowseFolders: [], attachBrowseFiles: [],
        previewTab: 'text',
    },

    async meetmeShowGuestCompose(guestId) {
        const m = this._mmFindMeeting(this._meetmeState.selectedId);
        const g = m && m.guests ? m.guests.find(x => x.id === guestId) : null;
        if (!g) return;

        const st = this._mmComposeState;
        st.guestId = guestId;
        st.meetingId = m.id;
        st.allTemplates = false;
        st.sigOverride = false;
        st.sigId = null;
        st.attachment_refs = [];
        st.attachPanelOpen = false;
        st.attachTab = 'search';
        st.attachSource = 'office';
        st.attachSearchResults = [];
        st.attachBrowsePath = '';
        st.attachBrowseFolders = [];
        st.attachBrowseFiles = [];

        await this._mmComposeLoadTemplateList();
        if (!st.signatures.length) {
            try {
                const sigData = await this.get('/email-studio/api/signatures/');
                st.signatures = (sigData && sigData.signatures) || [];
            } catch (e) { /* optional */ }
        }

        document.querySelectorAll('#pbx-meetme-modal-overlay').forEach(el => el.remove());
        const overlay = document.createElement('div');
        overlay.className = 'pbx-meetme-modal-overlay';
        overlay.id = 'pbx-meetme-modal-overlay';
        overlay.dataset.guestId = guestId;
        overlay.innerHTML = `
            <div class="pbx-meetme-modal pbx-sa-modal">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <h4 style="margin:0">${this.t('pbx_mm_compose', 'E-Mail an')} ${this._meetmeEsc(g.name)}</h4>
                    <button class="pbx-act pbx-act-gray" onclick="PBX.meetmeCloseModal()"><i class="bi bi-x-lg"></i></button>
                </div>
                <p class="pbx-sa-meta">${this._meetmeEsc(g.email || '')}</p>

                <div id="pbx-mm-compose-controls">${this._mmComposeRenderControlsHtml(st)}</div>

                <div id="pbx-mm-compose-attach-section">${this._mmAttachRenderSection('compose')}</div>

                <div class="pbx-sa-mailbox">
                    <div class="pbx-sa-subject">
                        <input id="pbx-mm-compose-subject" type="text" placeholder="${this.t('pbx_sa_subject_ph', 'Betreff')}">
                    </div>
                    <div class="pbx-sa-body">
                        <textarea id="pbx-mm-compose-body" rows="7"></textarea>
                    </div>
                </div>

                <div style="display:flex;gap:6px;margin-bottom:6px">
                    <button id="pbx-mm-compose-tab-text-btn" class="pbx-act ${st.previewTab !== 'html' ? 'pbx-act-blue' : 'pbx-act-gray'}" style="flex:1" onclick="PBX._mmComposeSetPreviewTab('text')">${this.t('pbx_mm_notify_tab_text', 'Text')}</button>
                    <button id="pbx-mm-compose-tab-html-btn" class="pbx-act ${st.previewTab === 'html' ? 'pbx-act-blue' : 'pbx-act-gray'}" style="flex:1" onclick="PBX._mmComposeSetPreviewTab('html')">${this.t('pbx_mm_notify_tab_html', 'HTML')}</button>
                    <button class="pbx-act pbx-act-gray" onclick="PBX._mmComposeRefreshPreview()"><i class="bi bi-arrow-clockwise"></i> ${this.t('pbx_mm_notify_refresh_preview', 'Vorschau aktualisieren')}</button>
                </div>
                <div id="pbx-mm-compose-preview-text" style="display:${st.previewTab === 'html' ? 'none' : 'block'};white-space:pre-wrap;font-size:12px;border:1px solid var(--border-color, #dee2e6);border-radius:8px;padding:10px;max-height:220px;overflow:auto;margin-bottom:12px"></div>
                <div id="pbx-mm-compose-preview-html" style="display:${st.previewTab === 'html' ? 'block' : 'none'};margin-bottom:12px"></div>

                ${this._mmRenderDeepseekPanel(
                    'pbx-mm-compose-ds-panel',
                    'pbx-mm-compose-ds-top',
                    'pbx-mm-compose-ds-bottom',
                    'PBX._mmComposeDeepseekSuggest()',
                    "PBX._mmRaupeApply('pbx-mm-compose-ds-bottom','pbx-mm-compose-body')"
                )}

                <div class="pbx-meetme-modal-actions">
                    <button class="pbx-act pbx-act-gray" onclick="PBX.meetmeCloseModal()">${this.t('pbx_cancel', 'Abbrechen')}</button>
                    <button class="pbx-act pbx-act-green" onclick="PBX._mmComposeSend(${guestId})">${this.t('pbx_sa_send', 'Senden')}</button>
                </div>
            </div>
        `;
        this._meetmeMountModal(overlay);
    },

    _mmComposeRenderOptionsInnerHtml(st) {
        return `
                <div style="display:flex;gap:6px">
                    <button type="button" style="flex:1;font-size:11px;line-height:1.25;padding:8px 4px;border-radius:8px;border:none;cursor:pointer;background:${st.allTemplates ? 'var(--abcona-blue-light)' : 'var(--abcona-gray-bg)'};color:${st.allTemplates ? '#fff' : 'var(--text-secondary)'}" onclick="PBX._mmComposeToggleTemplateFilter(${st.allTemplates ? 'false' : 'true'})">${this.t('pbx_mm_notify_all_templates_short', 'Alle Vorlagen')}</button>
                    <button type="button" style="flex:1;font-size:11px;line-height:1.25;padding:8px 4px;border-radius:8px;border:none;cursor:pointer;background:${st.sigOverride ? 'var(--abcona-blue-light)' : 'var(--abcona-gray-bg)'};color:${st.sigOverride ? '#fff' : 'var(--text-secondary)'}" onclick="PBX._mmComposeToggleSigOverride(${st.sigOverride ? 'false' : 'true'})">${this.t('pbx_mm_notify_sig_override_short', 'Andere Signatur')}</button>
                </div>
                ${st.sigOverride ? `
                    <select id="pbx-mm-compose-sig-select" onchange="PBX._mmComposeState.sigId = this.value" style="width:100%;margin-top:8px">
                        ${st.signatures.map(s => `<option value="${s.id}" ${s.id === st.sigId ? 'selected' : ''}>${this._meetmeEsc(s.name)}</option>`).join('')}
                    </select>
                ` : ''}
        `;
    },

    _mmComposeRenderControlsHtml(st) {
        return `
            ${this._mmRenderCollapsible(
                'pbx-mm-compose-options',
                this.t('pbx_mm_notify_options_label', 'Weitere Optionen'),
                this._mmComposeRenderOptionsInnerHtml(st),
                { icon: 'bi-sliders' },
            )}

            <label>${this.t('pbx_sa_template', 'Vorlage')}</label>
            <div style="display:flex;gap:6px">
                <select id="pbx-mm-compose-tpl" style="flex:1">
                    <option value="">${this.t('pbx_sa_template_none', 'keine Vorlage')}</option>
                    ${st.templates.map(t => `<option value="${this._meetmeEsc(t.identifier)}">${this._meetmeEsc(t.name)}</option>`).join('')}
                </select>
                <button class="pbx-act pbx-act-gray" onclick="PBX._mmComposeLoadTemplate()">${this.t('pbx_sa_load', 'Laden')}</button>
            </div>
        `;
    },

    _mmComposeRefreshControls() {
        const el = this.$('pbx-mm-compose-controls');
        if (el) el.innerHTML = this._mmComposeRenderControlsHtml(this._mmComposeState);
    },

    async _mmComposeToggleTemplateFilter(checked) {
        const st = this._mmComposeState;
        st.allTemplates = checked;
        await this._mmComposeLoadTemplateList();
        this._mmComposeRefreshControls();
    },

    _mmComposeToggleSigOverride(checked) {
        const st = this._mmComposeState;
        st.sigOverride = checked;
        if (checked && !st.sigId && st.signatures.length) st.sigId = st.signatures[0].id;
        this._mmComposeRefreshControls();
    },

    async _mmComposeLoadTemplateList() {
        const st = this._mmComposeState;
        let tplData = null;
        try {
            const url = this.api.emailTemplates + (st.allTemplates ? '' : '?event_type=meetme_invite');
            tplData = await this.get(url);
        } catch (e) { /* optional */ }
        st.templates = (tplData && tplData.templates) || [];
    },

    async _mmComposeLoadTemplate() {
        const st = this._mmComposeState;
        const identifier = this.$('pbx-mm-compose-tpl').value;
        if (!identifier) return;
        try {
            const data = await this.get(`/meetme/api/guests/${st.guestId}/invite-preview/?template_identifier=${encodeURIComponent(identifier)}`);
            this.$('pbx-mm-compose-subject').value = data.subject || '';
            this.$('pbx-mm-compose-body').value = data.body || '';
        } catch (e) {
            this.toast(this.t('pbx_sa_template_err', 'Vorlage konnte nicht geladen werden'));
        }
    },

    _mmComposeSetPreviewTab(tab) {
        const st = this._mmComposeState;
        st.previewTab = tab;
        const textEl = this.$('pbx-mm-compose-preview-text');
        const htmlEl = this.$('pbx-mm-compose-preview-html');
        if (textEl) textEl.style.display = tab === 'html' ? 'none' : 'block';
        if (htmlEl) htmlEl.style.display = tab === 'html' ? 'block' : 'none';
        const textBtn = this.$('pbx-mm-compose-tab-text-btn');
        const htmlBtn = this.$('pbx-mm-compose-tab-html-btn');
        if (textBtn) textBtn.className = 'pbx-act ' + (tab !== 'html' ? 'pbx-act-blue' : 'pbx-act-gray');
        if (htmlBtn) htmlBtn.className = 'pbx-act ' + (tab === 'html' ? 'pbx-act-blue' : 'pbx-act-gray');
        if (tab === 'html') this._mmComposeRefreshPreview();
    },

    async _mmComposeRefreshPreview() {
        const st = this._mmComposeState;
        const bodyEl = this.$('pbx-mm-compose-body');
        const body = bodyEl ? bodyEl.value : '';
        if (!body.trim()) { return; }
        try {
            const data = await this.post('/meetme/api/notify-preview/', {
                body, signature_id: st.sigOverride ? st.sigId : null, action: 'invite',
            });
            const textEl = this.$('pbx-mm-compose-preview-text');
            if (textEl) textEl.textContent = data.text || '';
            this._mmComposeRenderPreviewHtml(data.html || '');
        } catch (e) {
            this.toast(this.t('pbx_mm_notify_preview_err', 'Vorschau konnte nicht geladen werden'));
        }
    },

    _mmComposeRenderPreviewHtml(html) {
        this._mmMountPreviewHtml(this.$('pbx-mm-compose-preview-html'), html, 'pbx-mm-compose-preview-iframe', 220);
    },

    _mmRaupeContext() {
        const cst = this._mmComposeState;
        if (cst && cst.guestId && cst.meetingId) {
            const m = this._mmFindMeeting(cst.meetingId);
            const guest = m && m.guests ? m.guests.find(x => x.id === cst.guestId) : null;
            return { meeting: m, guest, startAt: m ? m.start_at : null };
        }
        const nst = this._mmNotifyState;
        if (nst && nst.meetingId) {
            const m = this._mmFindMeeting(nst.meetingId);
            const guest = nst.mode === 'individual' && nst.queue[nst.idx]
                ? nst.queue[nst.idx]
                : (nst.queue[0] || null);
            return { meeting: m, guest, startAt: nst.newStartAt || (m ? m.start_at : null) };
        }
        const rst = this._mmReminderState;
        if (rst && rst.meetingId) {
            const m = this._mmFindMeeting(rst.meetingId);
            const guest = rst.mode === 'individual' && rst.queue[rst.idx]
                ? rst.queue[rst.idx]
                : (rst.queue[0] || null);
            return { meeting: m, guest, startAt: m ? m.start_at : null };
        }
        return { meeting: null, guest: null, startAt: null };
    },

    _mmRaupeSplitDateTime(iso) {
        if (!iso) return { datum: '', uhrzeit: '' };
        const d = new Date(iso);
        return {
            datum: d.toLocaleDateString('de-DE'),
            uhrzeit: d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' }),
        };
    },

    _mmRaupeVariables() {
        const { meeting, guest, startAt } = this._mmRaupeContext();
        const dt = this._mmRaupeSplitDateTime(startAt);
        const nst = this._mmNotifyState;
        const rst = this._mmReminderState;
        const guests = (nst && nst.queue && nst.queue.length)
            ? nst.queue
            : (rst && rst.queue && rst.queue.length)
                ? rst.queue
                : (meeting && meeting.guests ? meeting.guests.filter(g => g.is_active !== false) : []);
        const teilnehmer_liste = guests.map(g => g.name || '').filter(Boolean).join(', ');
        return {
            name: (guest && guest.name) || '',
            title: (meeting && meeting.title) || '',
            termin_datum: dt.datum,
            termin_uhrzeit: dt.uhrzeit,
            raum: (meeting && meeting.room_extension) || '',
            einwahl_info: (guest && guest.einwahl_info) || '',
            teilnehmer_liste,
            teilnehmer_liste_html: teilnehmer_liste.replace(/, /g, '<br>'),
        };
    },

    _mmRaupeSubjectEl() {
        return this.$('pbx-mm-compose-subject')
            || this.$('pbx-mm-notify-subject-all')
            || this.$('pbx-mm-notify-subject-ind')
            || this.$('pbx-mm-reminder-subject');
    },

    _mmRaupeRequest(text, extra = {}) {
        const subjEl = this._mmRaupeSubjectEl();
        return Object.assign({
            text: text || '',
            prompt_key: 'meetme_email',
            format: 'text',
            subject: subjEl ? (subjEl.value || '').trim() : '',
            variables: this._mmRaupeVariables(),
        }, extra);
    },

    _mmRaupeApply(bottomId, editorId) {
        const src = this.$(bottomId);
        const dst = this.$(editorId);
        const val = src ? (src.value || '').trim() : '';
        if (!val) {
            this.toast(this.t('pbx_sa_ds_err', 'DeepSeek konnte keinen Vorschlag liefern'));
            return;
        }
        if (dst) dst.value = val;
        this.toast(this.t('pbx_sa_applied', 'Vorschlag übernommen'));
    },

    _mmRaupeApplyNotify() {
        const st = this._mmNotifyState || {};
        const editorId = st.mode === 'all' ? 'pbx-mm-notify-body-all' : 'pbx-mm-notify-body-ind';
        this._mmRaupeApply('pbx-mm-notify-ds-bottom', editorId);
    },

    async _mmComposeDeepseekSuggest() {
        const current = this.$('pbx-mm-compose-body').value.trim();
        if (!current) {
            this.toast(this.t('pbx_sa_ds_empty', 'Erst Text eingeben oder Vorlage laden'));
            return;
        }
        this.$('pbx-mm-compose-ds-top').value = current;
        const btn = event.currentTarget;
        const origHtml = btn ? btn.innerHTML : '';
        if (btn) { btn.innerHTML = '<i class="bi bi-hourglass-split"></i> ...'; btn.disabled = true; }
        try {
            const res = await this.post('/meetme/api/deepseek-suggest/', this._mmRaupeRequest(current));
            if (res && res.suggestion) {
                this.$('pbx-mm-compose-ds-bottom').value = res.suggestion;
            } else {
                this.toast(this.t('pbx_sa_ds_err', 'DeepSeek konnte keinen Vorschlag liefern'));
            }
        } catch (e) {
            this.toast(this.t('pbx_sa_ds_err', 'DeepSeek konnte keinen Vorschlag liefern'));
        } finally {
            if (btn) { btn.innerHTML = origHtml; btn.disabled = false; }
        }
    },

    async _mmComposeSend(guestId) {
        const st = this._mmComposeState;
        const subject = this.$('pbx-mm-compose-subject').value.trim();
        const body = this.$('pbx-mm-compose-body').value.trim();
        if (!subject || !body) {
            this.toast(this.t('pbx_mm_compose_req', 'Betreff und Text erforderlich'));
            return;
        }
        try {
            await this.post(`/meetme/api/guests/${guestId}/send-adhoc/`, {
                subject, body,
                signature_id: st.sigOverride ? st.sigId : null,
                attachment_refs: st.attachment_refs,
            });
            this.toast(this.t('pbx_mm_compose_sent', 'E-Mail gesendet'));
            this.meetmeCloseModal();
        } catch (e) {
            this.toast(this.t('pbx_mm_compose_err', 'Senden fehlgeschlagen'));
        }
    },
});

// ============================================================
// Erinnerungsregeln (Versand An alle/Individuell, wie Compose-Panel)
// ============================================================
Object.assign(PBX, {
    _mmReminderState: {
        meetingId: null, mode: 'all', queue: [], idx: 0, templates: [], allTemplates: false,
        sigOverride: false, sigId: null, signatures: [],
        draft: null, draftExpanded: false, draftEditingId: null,
        previewTab: 'text', wizardMode: false,
        attachPanelOpen: false, attachTab: 'search', attachSource: 'office',
        attachSearchResults: [], attachBrowsePath: '', attachBrowseFolders: [], attachBrowseFiles: [],
    },

    _mmReminderFreshDraft(guestId) {
        return {
            offset_value: 1, offset_unit: 'HOURS', time_of_day: null, mode: 'MANUAL',
            guest: guestId || null, template_id: null, subject: '', body: '', attachment_refs: [],
        };
    },

    _mmReminderHasExistingRule(st, m) {
        if (!m) return false;
        const currentGuestId = st.mode === 'individual' ? ((st.queue[st.idx] || {}).id) : null;
        return (m.reminder_rules || []).some(r => st.mode === 'all' ? !r.guest : r.guest === currentGuestId);
    },

    async meetmeOpenReminderPanel(meetingId) {
        const st = this._mmReminderState;
        const m = this._mmFindMeeting(meetingId);
        st.meetingId = meetingId;
        st.wizardMode = false;
        st.mode = 'all';
        st.queue = ((m && m.guests) || []).filter(g => g.is_active !== false);
        st.idx = 0;
        st.allTemplates = false;
        st.sigOverride = false;
        st.sigId = null;
        st.draft = this._mmReminderFreshDraft(null);
        st.draftExpanded = !this._mmReminderHasExistingRule(st, m);
        st.draftEditingId = null;
        st.previewTab = 'text';
        st.attachPanelOpen = false;
        st.attachTab = 'search';
        st.attachSource = 'office';
        st.attachSearchResults = [];
        st.attachBrowsePath = '';
        st.attachBrowseFolders = [];
        st.attachBrowseFiles = [];

        let tplData = null;
        try { tplData = await this.get(this.api.emailTemplates + '?event_type=meetme_reminder'); }
        catch (e) { /* optional */ }
        st.templates = (tplData && tplData.templates) || [];

        if (!st.signatures.length) {
            try {
                const sigData = await this.get('/email-studio/api/signatures/');
                st.signatures = (sigData && sigData.signatures) || [];
            } catch (e) { /* optional */ }
        }

        await this._mmReminderAutoPrepareDraft();
        await this._mmReminderRenderWithPreview();
    },

    async _mmReminderAutoPrepareDraft() {
        const st = this._mmReminderState;
        if (!st.templates.length || !st.draft) return;
        const guestForPreview = st.mode === 'individual' ? st.queue[st.idx] : st.queue[0];
        st.draft.template_id = st.templates[0].id;
        try {
            const url = `/meetme/api/meetings/${st.meetingId}/render-preview/?template_id=${st.templates[0].id}` + (guestForPreview ? `&guest_id=${guestForPreview.id}` : '');
            const data = await this.get(url);
            st.draft.subject = data.subject || '';
            st.draft.body = data.text || '';
        } catch (e) { /* optional */ }
    },

    async _mmReminderRenderWithPreview() {
        this._mmReminderRender();
        const st = this._mmReminderState;
        if (st.draftExpanded && st.draft.body) {
            await this._mmReminderRefreshPreview();
        }
    },

    async _mmReminderFinish() {
        const st = this._mmReminderState;
        if (st.draftExpanded) {
            await this._mmReminderSaveDraft();
        }
        this.meetmeCloseModal();
    },

    async _mmReminderSendNow() {
        const st = this._mmReminderState;
        const subject = this.$('pbx-mm-reminder-subject').value.trim();
        const body = this.$('pbx-mm-reminder-body').value.trim();
        if (!subject || !body) { this.toast(this.t('pbx_meetme_fields_req', 'Betreff und Text erforderlich')); return; }
        const attachmentRefs = (st.draft.attachment_refs || []).slice();
        const guestId = st.mode === 'individual' ? st.queue[st.idx].id : null;
        const sigId = st.sigOverride ? st.sigId : null;

        if (st.draftExpanded) {
            await this._mmReminderSaveDraft();
        }

        try {
            await this.post(`/meetme/api/meetings/${st.meetingId}/reminder-send-now/`, {
                subject, body, signature_id: sigId, guest_id: guestId, attachment_refs: attachmentRefs,
            });
            this.toast(this.t('pbx_mm_reminder_sent', 'Erinnerung versendet'));
        } catch (e) {
            this.toast(this.t('pbx_mm_reminder_send_err', 'Versand fehlgeschlagen'));
            return;
        }
        this.meetmeCloseModal();
    },

    async _mmReminderSetMode(mode) {
        const st = this._mmReminderState;
        const m = this._mmFindMeeting(st.meetingId);
        st.mode = mode;
        st.idx = 0;
        st.draft = this._mmReminderFreshDraft(mode === 'individual' ? (st.queue[0] && st.queue[0].id) : null);
        st.draftExpanded = !this._mmReminderHasExistingRule(st, m);
        st.draftEditingId = null;
        await this._mmReminderAutoPrepareDraft();
        await this._mmReminderRenderWithPreview();
    },

    async _mmReminderToggleTemplateFilter(checked) {
        const st = this._mmReminderState;
        st.allTemplates = checked;
        let tplData = null;
        try {
            const url = this.api.emailTemplates + (checked ? '' : '?event_type=meetme_reminder');
            tplData = await this.get(url);
        } catch (e) { /* optional */ }
        st.templates = (tplData && tplData.templates) || [];
        this._mmReminderRender();
    },

    _mmReminderToggleSigOverride(checked) {
        const st = this._mmReminderState;
        st.sigOverride = checked;
        if (checked && !st.sigId && st.signatures.length) st.sigId = st.signatures[0].id;
        this._mmReminderRender();
    },

    async _mmReminderSkip() {
        const st = this._mmReminderState;
        const m = this._mmFindMeeting(st.meetingId);
        if (st.idx < st.queue.length - 1) {
            st.idx++;
            st.draft = this._mmReminderFreshDraft(st.queue[st.idx].id);
            st.draftExpanded = !this._mmReminderHasExistingRule(st, m);
            st.draftEditingId = null;
            await this._mmReminderAutoPrepareDraft();
            await this._mmReminderRenderWithPreview();
        } else {
            this.meetmeCloseModal();
        }
    },

    async _mmReminderNextGuest() {
        const st = this._mmReminderState;
        const m = this._mmFindMeeting(st.meetingId);
        if (st.idx < st.queue.length - 1) {
            st.idx++;
            st.draft = this._mmReminderFreshDraft(st.queue[st.idx].id);
            st.draftExpanded = !this._mmReminderHasExistingRule(st, m);
            st.draftEditingId = null;
            await this._mmReminderAutoPrepareDraft();
            await this._mmReminderRenderWithPreview();
        } else {
            this.meetmeCloseModal();
        }
    },

    async _mmReminderGoToGuest(idx) {
        const st = this._mmReminderState;
        const m = this._mmFindMeeting(st.meetingId);
        st.idx = idx;
        st.draft = this._mmReminderFreshDraft(st.queue[idx].id);
        st.draftExpanded = !this._mmReminderHasExistingRule(st, m);
        st.draftEditingId = null;
        await this._mmReminderAutoPrepareDraft();
        await this._mmReminderRenderWithPreview();
    },

    async _mmReminderOpenNewDraft() {
        const st = this._mmReminderState;
        st.draft = this._mmReminderFreshDraft(st.mode === 'individual' ? st.queue[st.idx].id : null);
        st.draftEditingId = null;
        st.draftExpanded = true;
        await this._mmReminderAutoPrepareDraft();
        await this._mmReminderRenderWithPreview();
    },

    _mmReminderEditDraft(ruleId) {
        const st = this._mmReminderState;
        const m = this._mmFindMeeting(st.meetingId);
        const rule = ((m && m.reminder_rules) || []).find(r => r.id === ruleId);
        if (!rule) return;
        st.draft = Object.assign({}, rule, { attachment_refs: (rule.attachment_refs || []).slice() });
        st.draftEditingId = ruleId;
        st.draftExpanded = true;
        this._mmReminderRender();
    },

    _mmReminderCancelDraft() {
        const st = this._mmReminderState;
        st.draft = this._mmReminderFreshDraft(st.mode === 'individual' ? st.queue[st.idx].id : null);
        st.draftEditingId = null;
        st.draftExpanded = false;
        this._mmReminderRender();
    },

    async _mmReminderDeleteRule(ruleId) {
        if (!confirm(this.t('pbx_mm_reminder_delete_confirm', 'Erinnerung wirklich löschen?'))) return;
        try {
            await this.del(`/meetme/api/reminder-rules/${ruleId}/delete/`);
        } catch (e) {
            this.toast(this.t('pbx_mm_reminder_delete_err', 'Konnte nicht gelöscht werden'));
            return;
        }
        const st = this._mmReminderState;
        const m = this._mmFindMeeting(st.meetingId);
        if (m) m.reminder_rules = (m.reminder_rules || []).filter(r => r.id !== ruleId);
        this._mmReminderRefreshScopeBody();
    },

    async _mmReminderLoadTemplate() {
        const st = this._mmReminderState;
        const sel = this.$('pbx-mm-reminder-tpl');
        const tplId = sel && sel.value;
        if (!tplId) return;
        const guestId = st.mode === 'individual' ? st.queue[st.idx].id : '';
        try {
            const url = `/meetme/api/meetings/${st.meetingId}/render-preview/?template_id=${tplId}` + (guestId ? `&guest_id=${guestId}` : '');
            const data = await this.get(url);
            st.draft.template_id = parseInt(tplId, 10);
            this.$('pbx-mm-reminder-subject').value = data.subject || '';
            this.$('pbx-mm-reminder-body').value = data.text || '';
        } catch (e) {
            this.toast(this.t('pbx_sa_template_err', 'Vorlage konnte nicht geladen werden'));
        }
    },

    _mmReminderGetCurrentBody() {
        const el = this.$('pbx-mm-reminder-body');
        return el ? el.value : '';
    },

    _mmReminderSetPreviewTab(tab) {
        const st = this._mmReminderState;
        st.previewTab = tab;
        const textEl = this.$('pbx-mm-reminder-preview-text');
        const htmlEl = this.$('pbx-mm-reminder-preview-html');
        if (textEl) textEl.style.display = tab === 'html' ? 'none' : 'block';
        if (htmlEl) htmlEl.style.display = tab === 'html' ? 'block' : 'none';
        const textBtn = this.$('pbx-mm-reminder-tab-text-btn');
        const htmlBtn = this.$('pbx-mm-reminder-tab-html-btn');
        if (textBtn) textBtn.className = 'pbx-act ' + (tab !== 'html' ? 'pbx-act-blue' : 'pbx-act-gray');
        if (htmlBtn) htmlBtn.className = 'pbx-act ' + (tab === 'html' ? 'pbx-act-blue' : 'pbx-act-gray');
        if (tab === 'html') this._mmReminderRefreshPreview();
    },

    async _mmReminderRefreshPreview() {
        const st = this._mmReminderState;
        const body = this._mmReminderGetCurrentBody();
        if (!body.trim()) { return; }
        try {
            const data = await this.post('/meetme/api/notify-preview/', {
                body, signature_id: st.sigOverride ? st.sigId : null, action: 'reminder',
            });
            const textEl = this.$('pbx-mm-reminder-preview-text');
            if (textEl) textEl.textContent = data.text || '';
            this._mmReminderRenderPreviewHtml(data.html || '');
        } catch (e) {
            this.toast(this.t('pbx_mm_notify_preview_err', 'Vorschau konnte nicht geladen werden'));
        }
    },

    _mmReminderRenderPreviewHtml(html) {
        this._mmMountPreviewHtml(this.$('pbx-mm-reminder-preview-html'), html, 'pbx-mm-reminder-preview-iframe', 220);
    },

    async _mmReminderDeepseekSuggest() {
        const current = (this._mmReminderGetCurrentBody() || '').trim();
        if (!current) { this.toast(this.t('pbx_sa_ds_empty', 'Erst Text eingeben oder Vorlage laden')); return; }
        this.$('pbx-mm-reminder-ds-top').value = current;
        const btn = event.currentTarget;
        const origHtml = btn.innerHTML;
        btn.innerHTML = '<i class="bi bi-hourglass-split"></i> ...'; btn.disabled = true;
        try {
            const res = await this.post('/meetme/api/deepseek-suggest/', this._mmRaupeRequest(current));
            if (res && res.suggestion) this.$('pbx-mm-reminder-ds-bottom').value = res.suggestion;
            else this.toast(this.t('pbx_sa_ds_err', 'DeepSeek konnte keinen Vorschlag liefern'));
        } catch (e) {
            this.toast(this.t('pbx_sa_ds_err', 'DeepSeek konnte keinen Vorschlag liefern'));
        } finally {
            btn.innerHTML = origHtml; btn.disabled = false;
        }
    },

    async _mmReminderSaveDraft() {
        const st = this._mmReminderState;
        const offsetValue = parseInt(this.$('pbx-mm-reminder-offset-value').value, 10) || 1;
        const offsetUnit = this.$('pbx-mm-reminder-offset-unit').value;
        const timeInput = this.$('pbx-mm-reminder-time');
        const timeOfDay = timeInput ? (timeInput.value || null) : null;
        const mode = this.$('pbx-mm-reminder-mode').value;
        const subject = this.$('pbx-mm-reminder-subject').value.trim();
        const body = this.$('pbx-mm-reminder-body').value.trim();

        const payload = {
            offset_value: offsetValue,
            offset_unit: offsetUnit,
            time_of_day: offsetUnit === 'DAYS' ? timeOfDay : null,
            mode: mode,
            guest: st.mode === 'individual' ? st.queue[st.idx].id : null,
            template_id: st.draft.template_id || null,
            subject: subject,
            body: body,
            attachment_refs: st.draft.attachment_refs || [],
        };

        try {
            let saved;
            if (st.draftEditingId) {
                saved = await this.patchReq(`/meetme/api/reminder-rules/${st.draftEditingId}/update/`, payload);
            } else {
                saved = await this.post(`/meetme/api/meetings/${st.meetingId}/reminder-rules/create/`, payload);
            }
            const m = this._mmFindMeeting(st.meetingId);
            if (m) {
                m.reminder_rules = m.reminder_rules || [];
                const idx = m.reminder_rules.findIndex(rr => rr.id === saved.id);
                if (idx >= 0) m.reminder_rules[idx] = saved; else m.reminder_rules.push(saved);
            }
            this.toast(this.t('pbx_mm_reminder_saved', 'Erinnerung gespeichert'));
            st.draft = this._mmReminderFreshDraft(st.mode === 'individual' ? st.queue[st.idx].id : null);
            st.draftEditingId = null;
            st.draftExpanded = false;
            this._mmReminderRefreshScopeBody();
        } catch (e) {
            this.toast(this.t('pbx_mm_reminder_save_err', 'Konnte nicht gespeichert werden'));
        }
    },

    _mmReminderToggleTimeField(unit) {
        const wrap = this.$('pbx-mm-reminder-time-wrap');
        if (wrap) wrap.style.display = unit === 'DAYS' ? 'block' : 'none';
    },

    _mmReminderRender() {
        const st = this._mmReminderState;
        if (st.wizardMode) {
            this._mmWizardRender();
            return;
        }
        this._mmReminderRenderStandalone();
    },

    _mmReminderRenderStandalone() {
        const st = this._mmReminderState;
        const m = this._mmFindMeeting(st.meetingId);
        if (!m) { this.meetmeCloseModal(); return; }

        document.querySelectorAll('#pbx-meetme-modal-overlay').forEach(el => el.remove());
        const overlay = document.createElement('div');
        overlay.className = 'pbx-meetme-modal-overlay';
        overlay.id = 'pbx-meetme-modal-overlay';

        overlay.innerHTML = `
            <div class="pbx-meetme-modal pbx-sa-modal">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <h4 style="margin:0;background:var(--status-yellow, #f59e0b);color:#fff;padding:5px 12px;border-radius:6px;display:inline-block;font-size:15px">${this.t('pbx_mm_reminder_title', 'Erinnerungen')}</h4>
                    <button class="pbx-act pbx-act-gray" onclick="PBX.meetmeCloseModal()"><i class="bi bi-x-lg"></i> ${this.t('pbx_cancel', 'Abbrechen')}</button>
                </div>
                <p style="font-size:12px;color:#888;margin:4px 0 10px">${this._meetmeEsc(m.title)}</p>

                <label>${this.t('pbx_mm_notify_mode', 'Versand')}</label>
                <div style="display:flex;gap:6px;margin-bottom:10px">
                    <button class="pbx-act ${st.mode === 'all' ? 'pbx-act-blue' : 'pbx-act-gray'}" style="flex:1" onclick="PBX._mmReminderSetMode('all')">${this.t('pbx_mm_notify_all', 'An alle')}</button>
                    <button class="pbx-act ${st.mode === 'individual' ? 'pbx-act-blue' : 'pbx-act-gray'}" style="flex:1" onclick="PBX._mmReminderSetMode('individual')">${this.t('pbx_mm_notify_individual', 'Individuell')}</button>
                </div>

                ${this._mmRenderCollapsible(
                    'pbx-mm-reminder-options',
                    this.t('pbx_mm_notify_options_label', 'Weitere Optionen'),
                    `
                    <div style="display:flex;gap:6px">
                        <div class="pbx-mm-opt-wrap" style="position:relative;flex:1">
                            <button type="button" style="width:100%;font-size:11px;line-height:1.25;padding:8px 4px;border-radius:8px;border:none;cursor:pointer;background:${st.allTemplates ? 'var(--abcona-blue-light)' : 'var(--abcona-gray-bg)'};color:${st.allTemplates ? '#fff' : 'var(--text-secondary)'}" onclick="PBX._mmReminderToggleTemplateFilter(${st.allTemplates ? 'false' : 'true'})">${this.t('pbx_mm_notify_all_templates_short', 'Alle Vorlagen')}</button>
                        </div>
                        <div class="pbx-mm-opt-wrap" style="position:relative;flex:1">
                            <button type="button" style="width:100%;font-size:11px;line-height:1.25;padding:8px 4px;border-radius:8px;border:none;cursor:pointer;background:${st.sigOverride ? 'var(--abcona-blue-light)' : 'var(--abcona-gray-bg)'};color:${st.sigOverride ? '#fff' : 'var(--text-secondary)'}" onclick="PBX._mmReminderToggleSigOverride(${st.sigOverride ? 'false' : 'true'})">${this.t('pbx_mm_notify_sig_override_short', 'Andere Signatur')}</button>
                        </div>
                    </div>
                    ${st.sigOverride ? `
                        <select id="pbx-mm-reminder-sig-select" onchange="PBX._mmReminderState.sigId = this.value" style="width:100%;margin-top:8px">
                            ${st.signatures.map(s => `<option value="${s.id}" ${s.id === st.sigId ? 'selected' : ''}>${this._meetmeEsc(s.name)}</option>`).join('')}
                        </select>
                    ` : ''}
                    `,
                    { icon: 'bi-sliders' },
                )}

                <div id="pbx-mm-reminder-scope-body">${this._mmReminderRenderScopeBody(st, m)}</div>

                <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:10px">
                    ${st.mode === 'individual' ? `
                        <button class="pbx-act pbx-act-gray" onclick="PBX._mmReminderSkip()">${this.t('pbx_sa_skip', 'Überspringen')}</button>
                        <button class="pbx-act pbx-act-green" onclick="PBX._mmReminderNextGuest()">${this.t('pbx_mm_reminder_next', 'Weiter')}</button>
                    ` : `
                        <button class="pbx-act pbx-act-green" onclick="PBX._mmReminderFinish()">${this.t('pbx_mm_reminder_done', 'Fertig')}</button>
                        <button class="pbx-act pbx-act-green" onclick="PBX._mmReminderSendNow()">${this.t('pbx_mm_reminder_send_now', 'Versenden')}</button>
                    `}
                </div>
            </div>
        `;
        this._meetmeMountModal(overlay);
    },

    _mmReminderRenderScopeBody(st, m) {
        const guestChips = st.mode === 'individual' ? `
            <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:4px">
                ${st.queue.map((g, i) => `<span class="pbx-sa-chip ${i === st.idx ? 'current' : ''}" style="cursor:pointer" onclick="PBX._mmReminderGoToGuest(${i})">${this._meetmeEsc(g.name || '')}</span>`).join('')}
            </div>
            <p class="pbx-sa-meta" style="margin-bottom:10px">${this.t('pbx_sa_of', 'Gast')} ${st.idx + 1} ${this.t('pbx_sa_of2', 'von')} ${st.queue.length}</p>
        ` : '';

        const currentGuestId = st.mode === 'individual' ? ((st.queue[st.idx] || {}).id) : null;
        const rules = (m.reminder_rules || []).filter(r => st.mode === 'all' ? !r.guest : r.guest === currentGuestId);
        const unitLabel = (u) => u === 'DAYS' ? this.t('pbx_mm_unit_days', 'Tage') : u === 'HOURS' ? this.t('pbx_mm_unit_hours', 'Stunden') : this.t('pbx_mm_unit_minutes', 'Minuten');

        const rows = rules.map(r => `
            <div style="display:flex;align-items:center;gap:8px;padding:7px 4px;border-bottom:1px solid var(--border-color, #dee2e6)">
                <i class="bi bi-clock" style="color:#888"></i>
                <span style="flex:1;font-size:12.5px">${r.offset_value} ${unitLabel(r.offset_unit)} ${this.t('pbx_mm_reminder_before', 'vorher')}${r.offset_unit === 'DAYS' && r.time_of_day ? ', ' + r.time_of_day.slice(0, 5) + ' Uhr' : ''}</span>
                <span style="font-size:11px;padding:3px 9px;border-radius:999px;background:${r.mode === 'AUTO' ? 'var(--status-green-bg, #d1e7dd)' : 'var(--abcona-gray-bg)'};color:${r.mode === 'AUTO' ? '#0f5132' : 'var(--text-secondary)'}">${r.mode === 'AUTO' ? this.t('pbx_mm_reminder_auto', 'Automatisch') : this.t('pbx_mm_reminder_manual', 'Manuell')}</span>
                <i class="bi bi-pencil" style="cursor:pointer;color:var(--text-secondary)" onclick="PBX._mmReminderEditDraft(${r.id})" title="${this.t('pbx_edit', 'Bearbeiten')}"></i>
                <i class="bi bi-trash" style="cursor:pointer;color:var(--status-red, #dc3545)" onclick="PBX._mmReminderDeleteRule(${r.id})" title="${this.t('pbx_delete', 'Löschen')}"></i>
            </div>
        `).join('');

        const label = st.mode === 'all' ? this.t('pbx_mm_reminder_for_all', 'Erinnerungen für alle Gäste') : this.t('pbx_mm_reminder_for_guest', 'Erinnerungen für diesen Gast');
        const recipientsLine = st.mode === 'all'
            ? `<div style="font-size:11px;color:#999;margin-bottom:8px">${(m.guests || []).filter(g => g.is_active !== false).map(g => `${this._meetmeEsc(g.name || '')} &lt;${this._meetmeEsc(g.email || '')}&gt;`).join(', ')}</div>`
            : '';

        return `
            ${guestChips}
            <div style="font-size:12px;color:var(--text-secondary);font-weight:600;margin-bottom:6px">${label}</div>
            ${recipientsLine}
            ${rows || `<p class="pbx-hint" style="margin-bottom:6px">${this.t('pbx_mm_reminder_none', 'Noch keine Erinnerungen angelegt')}</p>`}
            ${!st.draftExpanded ? `
                <div style="text-align:center;font-size:12px;color:var(--text-secondary);padding:8px;border:1px dashed var(--border-strong, #adb5bd);border-radius:8px;cursor:pointer;margin-bottom:14px" onclick="PBX._mmReminderOpenNewDraft()">
                    <i class="bi bi-plus-lg"></i> ${this.t('pbx_mm_reminder_new_for_scope', 'Weitere Erinnerung hinzufügen')}
                </div>
            ` : this._mmReminderRenderDraftEditor(st)}
        `;
    },

    _mmReminderRenderDraftEditor(st) {
        const r = st.draft;
        const tplOptions = (st.templates || []).map(t => `<option value="${t.id}" ${r.template_id === t.id ? 'selected' : ''}>${this._meetmeEsc(t.name)}</option>`).join('');

        return `
            <div style="border:1px solid var(--border-color, #dee2e6);border-radius:10px;padding:14px;margin-bottom:10px">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
                    <span style="font-size:12.5px;font-weight:600"><i class="bi bi-clock"></i> ${st.draftEditingId ? this.t('pbx_mm_reminder_editing', 'Erinnerung bearbeiten') : this.t('pbx_mm_reminder_new_one', 'Neue Erinnerung')}</span>
                </div>

                <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px">
                    <div>
                        <label style="font-size:11px;color:#888">${this.t('pbx_mm_reminder_offset', 'Zeitpunkt')}</label>
                        <div style="display:flex;gap:6px;align-items:center">
                            <input id="pbx-mm-reminder-offset-value" type="number" min="1" value="${r.offset_value}" style="width:60px">
                            <select id="pbx-mm-reminder-offset-unit" onchange="PBX._mmReminderToggleTimeField(this.value)">
                                <option value="MINUTES" ${r.offset_unit === 'MINUTES' ? 'selected' : ''}>${this.t('pbx_mm_unit_minutes', 'Minuten')}</option>
                                <option value="HOURS" ${r.offset_unit === 'HOURS' ? 'selected' : ''}>${this.t('pbx_mm_unit_hours', 'Stunden')}</option>
                                <option value="DAYS" ${r.offset_unit === 'DAYS' ? 'selected' : ''}>${this.t('pbx_mm_unit_days', 'Tage')}</option>
                            </select>
                            <span style="font-size:12px;color:var(--text-secondary)">${this.t('pbx_mm_reminder_before', 'vorher')}</span>
                        </div>
                    </div>
                    <div id="pbx-mm-reminder-time-wrap" style="display:${r.offset_unit === 'DAYS' ? 'block' : 'none'}">
                        <label style="font-size:11px;color:#888">${this.t('pbx_mm_reminder_time_of_day', 'Uhrzeit')}</label>
                        <input id="pbx-mm-reminder-time" type="time" value="${r.time_of_day || '09:00'}">
                    </div>
                    <div>
                        <label style="font-size:11px;color:#888">${this.t('pbx_mm_reminder_mode', 'Modus')}</label>
                        <select id="pbx-mm-reminder-mode">
                            <option value="MANUAL" ${r.mode === 'MANUAL' ? 'selected' : ''}>${this.t('pbx_mm_reminder_manual', 'Manuell pruefen')}</option>
                            <option value="AUTO" ${r.mode === 'AUTO' ? 'selected' : ''}>${this.t('pbx_mm_reminder_auto', 'Automatisch senden')}</option>
                        </select>
                    </div>
                </div>

                <label>${this.t('pbx_sa_template', 'Vorlage')}</label>
                <div style="display:flex;gap:6px;margin-bottom:12px">
                    <select id="pbx-mm-reminder-tpl" style="flex:1">
                        <option value="">${this.t('pbx_sa_template_none', '– keine –')}</option>
                        ${tplOptions}
                    </select>
                    <button class="pbx-act pbx-act-gray" onclick="PBX._mmReminderLoadTemplate()">${this.t('pbx_sa_load', 'Laden')}</button>
                </div>

                <div id="pbx-mm-reminder-attach-section">${this._mmAttachRenderSection('reminder')}</div>

                <div class="pbx-sa-mailbox" style="margin:12px 0">
                    <div class="pbx-sa-subject"><input id="pbx-mm-reminder-subject" type="text" value="${this._meetmeEsc(r.subject || '')}" placeholder="${this.t('pbx_sa_subject_ph', 'Betreff')}"></div>
                    <div class="pbx-sa-body"><textarea id="pbx-mm-reminder-body" rows="4">${this._meetmeEsc(r.body || '')}</textarea></div>
                </div>

                <div style="display:flex;gap:6px;margin-bottom:6px">
                    <button id="pbx-mm-reminder-tab-text-btn" class="pbx-act ${st.previewTab !== 'html' ? 'pbx-act-blue' : 'pbx-act-gray'}" style="flex:1" onclick="PBX._mmReminderSetPreviewTab('text')">${this.t('pbx_mm_notify_tab_text', 'Text')}</button>
                    <button id="pbx-mm-reminder-tab-html-btn" class="pbx-act ${st.previewTab === 'html' ? 'pbx-act-blue' : 'pbx-act-gray'}" style="flex:1" onclick="PBX._mmReminderSetPreviewTab('html')">${this.t('pbx_mm_notify_tab_html', 'HTML')}</button>
                    <button class="pbx-act pbx-act-gray" onclick="PBX._mmReminderRefreshPreview()"><i class="bi bi-arrow-clockwise"></i> ${this.t('pbx_mm_notify_refresh_preview', 'Vorschau aktualisieren')}</button>
                </div>
                <div id="pbx-mm-reminder-preview-text" style="display:${st.previewTab === 'html' ? 'none' : 'block'};white-space:pre-wrap;font-size:12px;border:1px solid var(--border-color, #dee2e6);border-radius:8px;padding:10px;max-height:180px;overflow:auto;margin-bottom:12px"></div>
                <div id="pbx-mm-reminder-preview-html" style="display:${st.previewTab === 'html' ? 'block' : 'none'};margin-bottom:12px"></div>

                ${this._mmRenderDeepseekPanel(
                    'pbx-mm-reminder-ds-panel',
                    'pbx-mm-reminder-ds-top',
                    'pbx-mm-reminder-ds-bottom',
                    'PBX._mmReminderDeepseekSuggest()',
                    "PBX._mmRaupeApply('pbx-mm-reminder-ds-bottom','pbx-mm-reminder-body')"
                )}

                <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:10px">
                    <button class="pbx-act pbx-act-gray" onclick="PBX._mmReminderCancelDraft()">${this.t('pbx_mm_reminder_discard', 'Verwerfen')}</button>
                    <button class="pbx-act pbx-act-green" onclick="PBX._mmReminderSaveDraft()">${this.t('pbx_mm_reminder_save_one', 'Diese Erinnerung speichern')}</button>
                </div>
            </div>
        `;
    },

    _mmReminderRefreshScopeBody() {
        const st = this._mmReminderState;
        const m = this._mmFindMeeting(st.meetingId);
        const el = this.$('pbx-mm-reminder-scope-body');
        if (el && m) el.innerHTML = this._mmReminderRenderScopeBody(st, m);
    },

});

// ============================================================
// Generischer Anhang-Helper (gemeinsam fuer Reminder/Notify/Compose)
// ============================================================
Object.assign(PBX, {
    _mmAttachConfigs: {
        reminder: {
            state: () => PBX._mmReminderState,
            getList: (st) => { st.draft.attachment_refs = st.draft.attachment_refs || []; return st.draft.attachment_refs; },
            containerId: 'pbx-mm-reminder-attach-section',
            resultsId: 'pbx-mm-reminder-attach-results',
            browseListId: 'pbx-mm-reminder-attach-browse-list',
        },
        notify: {
            state: () => PBX._mmNotifyState,
            getList: (st) => {
                if (st.mode === 'all') { return st.attachmentsShared; }
                const guest = st.queue[st.idx];
                if (!guest) return [];
                st.attachmentsByGuest[guest.id] = st.attachmentsByGuest[guest.id] || [];
                return st.attachmentsByGuest[guest.id];
            },
            containerId: 'pbx-mm-notify-attach',
            resultsId: 'pbx-mm-attach-results',
            browseListId: 'pbx-mm-attach-browse-list',
        },
        compose: {
            state: () => PBX._mmComposeState,
            getList: (st) => { st.attachment_refs = st.attachment_refs || []; return st.attachment_refs; },
            containerId: 'pbx-mm-compose-attach-section',
            resultsId: 'pbx-mm-compose-attach-results',
            browseListId: 'pbx-mm-compose-attach-browse-list',
        },
    },

    _mmAttachRenderSection(key) {
        const cfg = this._mmAttachConfigs[key];
        const st = cfg.state();
        const list = cfg.getList(st);
        const chips = list.map((f, i) => `
            <span class="pbx-mm-attach-chip">
                <i class="bi bi-paperclip"></i>${this._meetmeEsc(f.filename || '')}
                <i class="bi bi-x" onclick="PBX._mmAttachRemove('${key}', ${i})" title="${this.t('pbx_mm_attach_remove', 'Entfernen')}"></i>
            </span>
        `).join('');

        let panel = '';
        if (st.attachPanelOpen) {
            panel = `
                <div class="pbx-mm-attach-panel">
                    <div style="display:flex;gap:6px;margin-bottom:8px">
                        <button class="pbx-act ${st.attachTab === 'search' ? 'pbx-act-blue' : 'pbx-act-gray'}" style="flex:1" onclick="PBX._mmAttachSetTab('${key}', 'search')"><i class="bi bi-search"></i> ${this.t('pbx_mm_attach_search', 'Suchen')}</button>
                        <button class="pbx-act ${st.attachTab === 'browse' ? 'pbx-act-blue' : 'pbx-act-gray'}" style="flex:1" onclick="PBX._mmAttachSetTab('${key}', 'browse')"><i class="bi bi-folder"></i> ${this.t('pbx_mm_attach_browse', 'Durchsuchen')}</button>
                    </div>
                    <div style="display:flex;gap:6px;margin-bottom:8px">
                        <button class="pbx-act ${st.attachSource === 'office' ? 'pbx-act-blue' : 'pbx-act-gray'}" style="font-size:11px" onclick="PBX._mmAttachSetSource('${key}', 'office')">${this.t('pbx_mm_attach_source_office', 'Office (O:\)')}</button>
                        <button class="pbx-act ${st.attachSource === 'public' ? 'pbx-act-blue' : 'pbx-act-gray'}" style="font-size:11px" onclick="PBX._mmAttachSetSource('${key}', 'public')">${this.t('pbx_mm_attach_source_public', 'Public (X:\)')}</button>
                    </div>
                    ${st.attachTab === 'search' ? `
                        <input id="${cfg.resultsId}-input" type="text" placeholder="${this.t('pbx_mm_attach_search_ph', 'Dateiname suchen...')}" oninput="PBX._mmAttachSearch('${key}', this.value)" style="width:100%;margin-bottom:8px">
                        <div id="${cfg.resultsId}" style="display:flex;flex-direction:column;gap:2px;max-height:220px;overflow-y:auto">
                            ${this._mmAttachRenderSearchResults(key)}
                        </div>
                    ` : `
                        <div style="font-size:12px;color:#888;margin-bottom:6px">${this._mmAttachBreadcrumb(key)}</div>
                        <div id="${cfg.browseListId}" style="display:flex;flex-direction:column;gap:2px;max-height:220px;overflow-y:auto">
                            ${this._mmAttachRenderBrowseList(key)}
                        </div>
                    `}
                </div>
            `;
        }

        return `
            <div class="pbx-mm-attach-section">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:${list.length ? '6px' : '0'}">
                    <span style="font-size:12.5px;font-weight:600"><i class="bi bi-paperclip"></i> ${this.t('pbx_mm_attach_title', 'Anhänge')}</span>
                    <button class="pbx-act pbx-act-gray" onclick="PBX._mmAttachTogglePanel('${key}')">${st.attachPanelOpen ? this.t('pbx_mm_attach_close', 'Schließen') : this.t('pbx_mm_attach_add', '+ Hinzufügen')}</button>
                </div>
                ${chips ? `<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px">${chips}</div>` : ''}
                ${panel}
            </div>
        `;
    },

    _mmAttachRenderSearchResults(key) {
        const cfg = this._mmAttachConfigs[key];
        const st = cfg.state();
        if (!st.attachSearchResults.length) {
            return `<div style="font-size:12px;color:#888;padding:6px 2px">${this.t('pbx_mm_attach_no_results', 'Suchbegriff eingeben...')}</div>`;
        }
        return st.attachSearchResults.map(r => `
            <div class="pbx-mm-attach-row" onclick="PBX._mmAttachAddEdms('${key}', '${r.uuid}', '${this._meetmeEsc(r.filename || r.title || '').replace(/'/g, "&#39;")}')">
                <i class="bi bi-file-earmark"></i>
                <div style="flex:1;min-width:0">
                    <div style="font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${this._meetmeEsc(r.filename || r.title || '')}</div>
                    <div style="font-size:11px;color:#999">${this._meetmeEsc(r.doctype_label || '')}</div>
                </div>
                <i class="bi bi-plus-lg"></i>
            </div>
        `).join('');
    },

    _mmAttachBreadcrumb(key) {
        const cfg = this._mmAttachConfigs[key];
        const st = cfg.state();
        const root = st.attachSource === 'office' ? 'Office' : 'Public';
        const parts = st.attachBrowsePath ? st.attachBrowsePath.split('/').filter(Boolean) : [];
        let acc = '';
        let html = `<span class="pbx-mm-clickable" onclick="PBX._mmAttachBrowse('${key}', '')">${root}</span>`;
        parts.forEach(part => {
            acc = acc ? acc + '/' + part : part;
            const target = acc;
            html += ` <i class="bi bi-chevron-right" style="font-size:10px"></i> <span class="pbx-mm-clickable" onclick="PBX._mmAttachBrowse('${key}', '${target.replace(/'/g, "&#39;")}')">${this._meetmeEsc(part)}</span>`;
        });
        return html;
    },

    _mmAttachRenderBrowseList(key) {
        const cfg = this._mmAttachConfigs[key];
        const st = cfg.state();
        const folders = (st.attachBrowseFolders || []).map(name => `
            <div class="pbx-mm-attach-row" onclick="PBX._mmAttachBrowse('${key}', '${((st.attachBrowsePath ? st.attachBrowsePath + '/' : '') + name).replace(/'/g, "&#39;")}')">
                <i class="bi bi-folder-fill" style="color:var(--abcona-blue, #1a5fb4)"></i>
                <div style="flex:1;font-size:13px">${this._meetmeEsc(name)}</div>
                <i class="bi bi-chevron-right"></i>
            </div>
        `).join('');
        const files = (st.attachBrowseFiles || []).map(f => `
            <div class="pbx-mm-attach-row" onclick="PBX._mmAttachAddFs('${key}', '${st.attachSource}', '${((st.attachBrowsePath ? st.attachBrowsePath + '/' : '') + f.name).replace(/'/g, "&#39;")}', '${this._meetmeEsc(f.name).replace(/'/g, "&#39;")}')">
                <i class="bi bi-file-earmark"></i>
                <div style="flex:1;font-size:13px">${this._meetmeEsc(f.name)}</div>
                <i class="bi bi-plus-lg"></i>
            </div>
        `).join('');
        if (!folders && !files) {
            return `<div style="font-size:12px;color:#888;padding:6px 2px">${this.t('pbx_mm_attach_empty_folder', 'Ordner ist leer')}</div>`;
        }
        return folders + files;
    },

    _mmAttachTogglePanel(key) {
        const cfg = this._mmAttachConfigs[key];
        const st = cfg.state();
        st.attachPanelOpen = !st.attachPanelOpen;
        if (st.attachPanelOpen && st.attachTab === 'browse' && !st.attachBrowseFolders.length && !st.attachBrowseFiles.length) {
            this._mmAttachBrowse(key, '');
            return;
        }
        this._mmAttachRefresh(key);
    },

    _mmAttachSetTab(key, tab) {
        const cfg = this._mmAttachConfigs[key];
        const st = cfg.state();
        st.attachTab = tab;
        if (tab === 'browse' && !st.attachBrowseFolders.length && !st.attachBrowseFiles.length) {
            this._mmAttachBrowse(key, '');
            return;
        }
        this._mmAttachRefresh(key);
    },

    _mmAttachSetSource(key, source) {
        const cfg = this._mmAttachConfigs[key];
        const st = cfg.state();
        st.attachSource = source;
        st.attachBrowsePath = '';
        st.attachBrowseFolders = [];
        st.attachBrowseFiles = [];
        st.attachSearchResults = [];
        if (st.attachTab === 'browse') { this._mmAttachBrowse(key, ''); return; }
        this._mmAttachRefresh(key);
    },

    async _mmAttachSearch(key, q) {
        const cfg = this._mmAttachConfigs[key];
        const st = cfg.state();
        clearTimeout(this._mmAttachSearchTimer);
        this._mmAttachSearchTimer = setTimeout(async () => {
            if (!q || q.trim().length < 2) { st.attachSearchResults = []; this._mmAttachRefreshResultsDom(key); return; }
            try {
                const data = await this.get('/meetme/api/attachments/search/?q=' + encodeURIComponent(q.trim()) + '&size=8&volume=' + st.attachSource);
                st.attachSearchResults = (data && data.results) || [];
            } catch (e) {
                st.attachSearchResults = [];
            }
            this._mmAttachRefreshResultsDom(key);
        }, 300);
    },

    _mmAttachRefreshResultsDom(key) {
        const cfg = this._mmAttachConfigs[key];
        const el = this.$(cfg.resultsId);
        if (el) el.innerHTML = this._mmAttachRenderSearchResults(key);
    },

    async _mmAttachBrowse(key, path) {
        const cfg = this._mmAttachConfigs[key];
        const st = cfg.state();
        try {
            const data = await this.get('/meetme/api/attachments/browse/?volume=' + st.attachSource + '&path=' + encodeURIComponent(path || ''));
            st.attachBrowsePath = (data && data.path) || '';
            st.attachBrowseFolders = (data && data.folders) || [];
            st.attachBrowseFiles = (data && data.files) || [];
        } catch (e) {
            this.toast(this.t('pbx_mm_attach_browse_err', 'Ordner konnte nicht geladen werden'));
            return;
        }
        this._mmAttachRefresh(key);
    },

    _mmAttachAddEdms(key, uuid, filename) {
        this._mmAttachPush(key, { type: 'edms', uuid: uuid, filename: filename });
    },

    _mmAttachAddFs(key, volume, relativePath, filename) {
        this._mmAttachPush(key, { type: 'fs', volume: volume, relative_path: relativePath, filename: filename });
    },

    _mmAttachPush(key, ref) {
        const cfg = this._mmAttachConfigs[key];
        const st = cfg.state();
        const list = cfg.getList(st);
        if (!list) return;
        const sameRef = a => a.type === ref.type && a.uuid === ref.uuid && a.relative_path === ref.relative_path;
        if (!list.some(sameRef)) list.push(ref);
        this._mmAttachRefresh(key);
    },

    _mmAttachRemove(key, index) {
        const cfg = this._mmAttachConfigs[key];
        const st = cfg.state();
        const list = cfg.getList(st);
        if (!list) return;
        list.splice(index, 1);
        this._mmAttachRefresh(key);
    },

    _mmAttachRefresh(key) {
        const cfg = this._mmAttachConfigs[key];
        const el = this.$(cfg.containerId);
        if (el) el.innerHTML = this._mmAttachRenderSection(key);
    },
});

// ============================================================
// Termin-Wizard (Geruest: Reiter-Leiste + Navigation, Inhalt folgt)
// ============================================================
Object.assign(PBX, {
    _mmWizardState: {
        meetingId: null, action: null, tabs: [], tabIndex: 0,
    },

    _mmWizardTabsFor(action) {
        if (action === 'cancel') return [this.t('pbx_wiz_tab_cancel', 'Absagen'), this.t('pbx_wiz_tab_send', 'Senden'), this.t('pbx_wiz_tab_summary', 'Zusammenfassung')];
        if (action === 'invite') return [this.t('pbx_wiz_tab_create', 'Erstellen'), this.t('pbx_wiz_tab_invite', 'Einladung'), this.t('pbx_wiz_tab_reminder', 'Erinnerung'), this.t('pbx_wiz_tab_summary', 'Zusammenfassung')];
        return [this.t('pbx_wiz_tab_resched', 'Termin verschieben'), this.t('pbx_wiz_tab_invite2', 'Einladen'), this.t('pbx_wiz_tab_reminder2', 'Erinnern'), this.t('pbx_wiz_tab_summary', 'Zusammenfassung')];
    },

    async meetmeOpenWizard(meetingId, action) {
        const st = this._mmWizardState;
        const m = await this._mmNotifyPrepareState(meetingId, action);
        if (!m) return;
        st.meetingId = meetingId;
        st.action = action;
        st.tabs = this._mmWizardTabsFor(action);
        st.tabIndex = 0;
        st.autoLoadedTemplate = false;
        this._mmWizardRender();
    },

    _mmNotifyDefaultTemplateName(action) {
        const map = {
            invite: 'Einladung — Abstimmung',
            cancel: 'Terminabsage — Standard',
            reschedule: 'Terminänderung — Standard',
        };
        return map[action] || null;
    },

    async _mmNotifyAutoLoadDefaultTemplate() {
        const st = this._mmNotifyState;
        const templateName = this._mmNotifyDefaultTemplateName(st.action);
        if (!templateName) return;
        const tpl = (st.templates || []).find(t => t.name === templateName);
        if (!tpl) return;
        const selId = st.mode === 'all' ? 'pbx-mm-notify-tpl-all' : 'pbx-mm-notify-tpl-ind';
        const sel = this.$(selId);
        if (sel) sel.value = tpl.id;
        await this._mmNotifyLoadTemplate(st.mode);
    },

    async _mmWizardMaybeAutoLoadDefaultTemplate() {
        const st = this._mmWizardState;
        if (st.tabIndex !== 1 || st.autoLoadedTemplate) return;
        if (!this._mmNotifyDefaultTemplateName(st.action)) return;
        st.autoLoadedTemplate = true;
        await this._mmNotifyAutoLoadDefaultTemplate();
    },

    async _mmWizardEnsureTabReady(idx) {
        const st = this._mmWizardState;
        if (idx === 2 && st.tabs.length === 4) {
            const rst = this._mmReminderState;
            rst.wizardMode = true;
            if (rst.meetingId !== st.meetingId) {
                const m = this._mmFindMeeting(st.meetingId);
                rst.meetingId = st.meetingId;
                rst.mode = 'all';
                rst.queue = ((m && m.guests) || []).filter(g => g.is_active !== false);
                rst.idx = 0;
                rst.allTemplates = false;
                rst.sigOverride = false;
                rst.sigId = null;
                rst.draft = this._mmReminderFreshDraft(null);
                rst.draftExpanded = !this._mmReminderHasExistingRule(rst, m);
                rst.draftEditingId = null;
                rst.previewTab = 'text';
                rst.attachPanelOpen = false;
                rst.attachTab = 'search';
                rst.attachSource = 'office';
                rst.attachSearchResults = [];
                rst.attachBrowsePath = '';
                rst.attachBrowseFolders = [];
                rst.attachBrowseFiles = [];
                let tplData = null;
                try { tplData = await this.get(this.api.emailTemplates + '?event_type=meetme_reminder'); }
                catch (e) { /* optional */ }
                rst.templates = (tplData && tplData.templates) || [];
                if (!rst.signatures.length) {
                    try {
                        const sigData = await this.get('/email-studio/api/signatures/');
                        rst.signatures = (sigData && sigData.signatures) || [];
                    } catch (e) { /* optional */ }
                }
                await this._mmReminderAutoPrepareDraft();
            }
        }
    },

    _mmNotifyInWizard() {
        return !!this.$('pbx-mm-wizard-body');
    },

    _mmNotifySaveCurrentGuestText() {
        const st = this._mmNotifyState;
        if (st.mode === 'all') {
            const subjectEl = this.$('pbx-mm-notify-subject-all');
            const bodyEl = this.$('pbx-mm-notify-body-all');
            if (subjectEl) st.cachedSubject = subjectEl.value;
            if (bodyEl) st.cachedBody = bodyEl.value;
            return;
        }
        const g = st.queue[st.idx];
        if (!g) return;
        st.subjectByGuest = st.subjectByGuest || {};
        st.bodyByGuest = st.bodyByGuest || {};
        const subjectEl = this.$('pbx-mm-notify-subject-ind');
        const bodyEl = this.$('pbx-mm-notify-body-ind');
        if (subjectEl) st.subjectByGuest[g.id] = subjectEl.value;
        if (bodyEl) st.bodyByGuest[g.id] = bodyEl.value;
    },

    _mmNotifyGetGuestDraft(m, g) {
        const st = this._mmNotifyState;
        const hasCached = st.subjectByGuest && Object.prototype.hasOwnProperty.call(st.subjectByGuest, g.id);
        if (hasCached || (st.bodyByGuest && Object.prototype.hasOwnProperty.call(st.bodyByGuest, g.id))) {
            return {
                subject: (st.subjectByGuest && st.subjectByGuest[g.id]) || '',
                body: (st.bodyByGuest && st.bodyByGuest[g.id]) || '',
            };
        }
        return this._mmNotifyDefaultText(m, g);
    },

    _mmNotifyGetBulkDraft(m) {
        const st = this._mmNotifyState;
        if (st.cachedSubject !== null || st.cachedBody !== null) {
            return { subject: st.cachedSubject || '', body: st.cachedBody || '' };
        }
        const g = st.queue[0];
        return g ? this._mmNotifyDefaultText(m, g) : { subject: '', body: '' };
    },

    _mmNotifyGoToGuest(idx) {
        const st = this._mmNotifyState;
        if (idx < 0 || idx >= st.queue.length || idx === st.idx) return;
        this._mmNotifySaveCurrentGuestText();
        st.idx = idx;
        if (this._mmNotifyInWizard()) {
            const m = this._mmFindMeeting(st.meetingId);
            const el = this.$('pbx-mm-notify-content');
            if (el && m) el.innerHTML = this._mmNotifyRenderContentHtml(st, m);
        } else {
            this._mmNotifyRefreshContent();
            this._mmNotifyRefreshActions();
        }
    },

    _mmWizardCacheComposeText() {
        this._mmNotifySaveCurrentGuestText();
        this._mmNotifyState.composeVisited = true;
    },

    async _mmWizardGoToTab(idx) {
        const st = this._mmWizardState;
        if (st.tabIndex === 1) this._mmWizardCacheComposeText();
        st.tabIndex = idx;
        await this._mmWizardEnsureTabReady(idx);
        this._mmWizardRender();
        await this._mmWizardMaybeAutoLoadDefaultTemplate();
    },

    async _mmWizardNext() {
        const st = this._mmWizardState;
        if (st.tabIndex < st.tabs.length - 1) {
            if (st.tabIndex === 1) this._mmWizardCacheComposeText();
            st.tabIndex++;
            await this._mmWizardEnsureTabReady(st.tabIndex);
            this._mmWizardRender();
            await this._mmWizardMaybeAutoLoadDefaultTemplate();
        }
    },

    async _mmWizardBack() {
        const st = this._mmWizardState;
        if (st.tabIndex > 0) {
            if (st.tabIndex === 1) this._mmWizardCacheComposeText();
            st.tabIndex--;
            await this._mmWizardEnsureTabReady(st.tabIndex);
            this._mmWizardRender();
        }
    },

    async _mmWizardSend() {
        const wst = this._mmWizardState;
        const st = this._mmNotifyState;
        const m = this._mmFindMeeting(st.meetingId);
        if (!m) return;

        if (wst.tabIndex === 1 || st.composeVisited) {
            this._mmWizardCacheComposeText();
        } else if (this._mmNotifyInWizard()) {
            this._mmNotifySaveCurrentGuestText();
            st.composeVisited = true;
        }

        if (st.mode === 'all') {
            const draft = this._mmNotifyGetBulkDraft(m);
            if (!draft.subject.trim() || !draft.body.trim()) {
                this.toast(this.t('pbx_meetme_fields_req', 'Betreff und Text erforderlich'));
                return;
            }
        } else if (!st.queue.length) {
            this.toast(this.t('pbx_mm_notify_none_open', 'Alle Gäste sind bereits informiert.'));
            return;
        } else {
            for (const g of st.queue) {
                const draft = this._mmNotifyGetGuestDraft(m, g);
                if (!draft.subject.trim() || !draft.body.trim()) {
                    this.toast(`${this.t('pbx_meetme_fields_req', 'Betreff und Text erforderlich')}: ${g.name || ''}`);
                    return;
                }
            }
        }

        const committed = await this._mmNotifyCommit();
        if (!committed) return;

        try {
            if (st.mode === 'all') {
                const draft = this._mmNotifyGetBulkDraft(m);
                await this.post(`/meetme/api/meetings/${st.meetingId}/notify-bulk/`, {
                    notification_kind: st.action,
                    subject: draft.subject.trim(),
                    body: draft.body.trim(),
                    target_start_at: st.newStartAt,
                    force: st.force,
                    signature_id: st.sigOverride ? st.sigId : null,
                    attachment_refs: st.attachmentsShared,
                });
            } else {
                for (const g of st.queue) {
                    const draft = this._mmNotifyGetGuestDraft(m, g);
                    await this.post(`/meetme/api/guests/${g.id}/send-adhoc/`, {
                        subject: draft.subject.trim(),
                        body: draft.body.trim(),
                        notification_kind: st.action,
                        target_start_at: st.newStartAt,
                        signature_id: st.sigOverride ? st.sigId : null,
                        attachment_refs: st.attachmentsByGuest[g.id] || [],
                    });
                }
            }
        } catch (e) {
            this.toast(st.mode === 'all'
                ? this.t('pbx_mm_notify_bulk_err', 'Versand an alle fehlgeschlagen')
                : this.t('pbx_mm_compose_err', 'Senden fehlgeschlagen'));
            return;
        }

        this.meetmeCloseModal();
        this.toast(st.action === 'cancel' ? this.t('pbx_meetme_cancelled', 'Termin abgesagt') : this.t('pbx_meetme_saved', 'Gespeichert'));
        await this.meetmeLoadMeetings();
    },

    _mmWizardRenderBody() {
        const st = this._mmWizardState;
        const m = this._mmFindMeeting(st.meetingId);
        if (!m) return '';

        if (st.tabIndex === 0) {
            return `<div id="pbx-mm-notify-basics">${this._mmNotifyRenderBasicsHtml(this._mmNotifyState, m)}</div>`;
        }

        const isReminderTab = st.tabIndex === 2 && st.tabs.length === 4;
        const isSummaryTab = st.tabIndex === st.tabs.length - 1;

        if (isSummaryTab) {
            const nst = this._mmNotifyState;
            const guestNames = (nst.queue || []).map(g => g.name).join(', ') || this.t('pbx_wiz_summary_none', 'Keine Empfaenger in der Warteschlange');
            const notVisited = !nst.composeVisited;
            if (nst.mode === 'individual') {
                const guestRows = (nst.queue || []).map(g => {
                    const draft = this._mmNotifyGetGuestDraft(m, g);
                    const customized = nst.subjectByGuest && Object.prototype.hasOwnProperty.call(nst.subjectByGuest, g.id);
                    return `
                        <div style="padding:8px 0;border-bottom:1px solid var(--border-color, #dee2e6)">
                            <div style="font-size:12.5px;font-weight:600">${this._meetmeEsc(g.name || '')}${customized ? '' : ` <span style="font-weight:400;color:#999;font-size:11px">(${this.t('pbx_wiz_summary_default', 'Standard')})</span>`}</div>
                            <div style="font-size:12px;color:var(--text-secondary);margin-top:2px">${this._meetmeEsc(draft.subject || '—')}</div>
                        </div>
                    `;
                }).join('');
                return `
                    <div style="font-size:13px;font-weight:600;margin-bottom:10px">${this.t('pbx_wiz_summary_title', 'Zusammenfassung')}</div>
                    <div style="display:flex;justify-content:space-between;font-size:12.5px;padding:6px 0;border-bottom:1px solid var(--border-color, #dee2e6)"><span style="color:var(--text-secondary)">${this.t('pbx_wiz_summary_recipients', 'Empfaenger')}</span><span>${this._meetmeEsc(guestNames)}</span></div>
                    <div style="display:flex;justify-content:space-between;font-size:12.5px;padding:6px 0;border-bottom:1px solid var(--border-color, #dee2e6)"><span style="color:var(--text-secondary)">${this.t('pbx_wiz_summary_mode', 'Versand')}</span><span>${this.t('pbx_mm_notify_individual', 'Individuell')}</span></div>
                    ${notVisited ? `
                        <p class="pbx-hint" style="margin-top:10px">${this.t('pbx_wiz_summary_not_visited', 'Betreff/Text noch nicht sichtbar - bitte zuerst den Reiter mit dem Text besuchen.')}</p>
                    ` : guestRows || `<p class="pbx-hint">${this.t('pbx_wiz_summary_none', 'Keine Empfaenger in der Warteschlange')}</p>`}
                `;
            }
            const summaryDraft = this._mmNotifyGetBulkDraft(m);
            return `
                <div style="font-size:13px;font-weight:600;margin-bottom:10px">${this.t('pbx_wiz_summary_title', 'Zusammenfassung')}</div>
                <div style="display:flex;justify-content:space-between;font-size:12.5px;padding:6px 0;border-bottom:1px solid var(--border-color, #dee2e6)"><span style="color:var(--text-secondary)">${this.t('pbx_wiz_summary_recipients', 'Empfaenger')}</span><span>${this._meetmeEsc(guestNames)}</span></div>
                <div style="display:flex;justify-content:space-between;font-size:12.5px;padding:6px 0;border-bottom:1px solid var(--border-color, #dee2e6)"><span style="color:var(--text-secondary)">${this.t('pbx_wiz_summary_mode', 'Versand')}</span><span>${this.t('pbx_mm_notify_all', 'An alle')}</span></div>
                ${notVisited ? `
                    <p class="pbx-hint" style="margin-top:10px">${this.t('pbx_wiz_summary_not_visited', 'Betreff/Text noch nicht sichtbar - bitte zuerst den Reiter mit dem Text besuchen.')}</p>
                ` : `
                    <div style="font-size:12.5px;padding:6px 0;border-bottom:1px solid var(--border-color, #dee2e6)"><span style="color:var(--text-secondary);display:block;margin-bottom:2px">${this.t('pbx_wiz_summary_subject', 'Betreff')}</span><span>${this._meetmeEsc(summaryDraft.subject)}</span></div>
                    <div style="font-size:12.5px;padding:6px 0"><span style="color:var(--text-secondary);display:block;margin-bottom:2px">${this.t('pbx_wiz_summary_body', 'Text')}</span><div style="white-space:pre-wrap;max-height:220px;overflow:auto">${this._meetmeEsc(summaryDraft.body)}</div></div>
                `}
            `;
        }

        if (isReminderTab) {
            const rst = this._mmReminderState;
            return `
                <label>${this.t('pbx_mm_notify_mode', 'Versand')}</label>
                <div style="display:flex;gap:6px;margin-bottom:10px">
                    <button class="pbx-act ${rst.mode === 'all' ? 'pbx-act-blue' : 'pbx-act-gray'}" style="flex:1" onclick="PBX._mmReminderSetMode('all')">${this.t('pbx_mm_notify_all', 'An alle')}</button>
                    <button class="pbx-act ${rst.mode === 'individual' ? 'pbx-act-blue' : 'pbx-act-gray'}" style="flex:1" onclick="PBX._mmReminderSetMode('individual')">${this.t('pbx_mm_notify_individual', 'Individuell')}</button>
                </div>
                <div id="pbx-mm-reminder-scope-body">${this._mmReminderRenderScopeBody(rst, m)}</div>
            `;
        }

        const nst = this._mmNotifyState;
        return `
            <label>${this.t('pbx_mm_notify_mode', 'Versand')}</label>
            <div id="pbx-mm-notify-modetoggle" style="display:flex;gap:6px;margin-bottom:10px">${this._mmNotifyRenderModeToggleHtml(nst)}</div>
            ${this._mmRenderCollapsible(
                'pbx-mm-notify-options',
                this.t('pbx_mm_notify_options_label', 'Weitere Optionen'),
                this._mmNotifyRenderOptionsHtml(nst),
                { icon: 'bi-sliders' },
            )}
            <div id="pbx-mm-notify-content">${this._mmNotifyRenderContentHtml(nst, m)}</div>
            <div style="margin:10px 0">
                <div style="display:flex;gap:6px;margin-bottom:6px">
                    <button id="pbx-mm-notify-tab-text-btn" class="pbx-act ${nst.previewTab !== 'html' ? 'pbx-act-blue' : 'pbx-act-gray'}" style="flex:1" onclick="PBX._mmNotifySetPreviewTab('text')">${this.t('pbx_mm_notify_tab_text', 'Text')}</button>
                    <button id="pbx-mm-notify-tab-html-btn" class="pbx-act ${nst.previewTab === 'html' ? 'pbx-act-blue' : 'pbx-act-gray'}" style="flex:1" onclick="PBX._mmNotifySetPreviewTab('html')">${this.t('pbx_mm_notify_tab_html', 'HTML')}</button>
                    <button class="pbx-act pbx-act-gray" onclick="PBX._mmNotifyRefreshPreview()"><i class="bi bi-arrow-clockwise"></i> ${this.t('pbx_mm_notify_refresh_preview', 'Vorschau aktualisieren')}</button>
                </div>
                <div id="pbx-mm-notify-preview-text" style="display:${nst.previewTab === 'html' ? 'none' : 'block'};white-space:pre-wrap;font-size:12px;border:1px solid var(--border-color, #dee2e6);border-radius:8px;padding:10px;max-height:280px;overflow:auto"></div>
                <div id="pbx-mm-notify-preview-html" style="display:${nst.previewTab === 'html' ? 'block' : 'none'}"></div>
            </div>
            ${this._mmRenderDeepseekPanel(
                'pbx-mm-notify-ds-panel',
                'pbx-mm-notify-ds-top',
                'pbx-mm-notify-ds-bottom',
                'PBX._mmNotifyDeepseekSuggest()',
                'PBX._mmRaupeApplyNotify()'
            )}
        `;
    },

    _mmWizardRender() {
        const st = this._mmWizardState;
        document.querySelectorAll('#pbx-meetme-modal-overlay').forEach(el => el.remove());
        const overlay = document.createElement('div');
        overlay.className = 'pbx-meetme-modal-overlay';
        overlay.id = 'pbx-meetme-modal-overlay';

        const tabBar = st.tabs.map((t, i) => `<div class="pbx-wizard-tab ${i === st.tabIndex ? 'active' : ''}" onclick="PBX._mmWizardGoToTab(${i})">${this._meetmeEsc(t)}</div>`).join('');
        const isLastTab = st.tabIndex >= st.tabs.length - 1;
        const nst = this._mmNotifyState;
        const isCancel = nst.action === 'cancel';
        const isInvite = nst.action === 'invite';
        const sendLabel = isCancel ? this.t('pbx_meetme_cancel_confirm_btn', 'Ja, absagen') : (isInvite ? this.t('pbx_meetme_invite_confirm', 'Einladung senden') : this.t('pbx_meetme_reschedule_confirm', 'Verschieben'));
        const sendCls = isCancel ? 'pbx-act-red' : 'pbx-act-green';

        overlay.innerHTML = `
            <div class="pbx-meetme-modal pbx-sa-modal">
                <div id="pbx-mm-wizard-tabbar" style="display:flex;gap:4px;margin-bottom:10px;border-bottom:1px solid var(--border-color, #dee2e6);padding-bottom:10px;flex-wrap:wrap">${tabBar}</div>
                <div id="pbx-mm-wizard-body" style="min-height:100px;padding:10px 0">${this._mmWizardRenderBody()}</div>
                <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:12px">
                    <button class="pbx-act pbx-act-gray" onclick="PBX._mmWizardBack()" style="visibility:${st.tabIndex === 0 ? 'hidden' : 'visible'}">${this.t('pbx_wiz_back', 'Zurueck')}</button>
                    ${isLastTab
                        ? `<button class="pbx-act ${sendCls}" onclick="PBX._mmWizardSend()">${sendLabel}</button>`
                        : `<button class="pbx-act pbx-act-blue" onclick="PBX._mmWizardNext()">${this.t('pbx_wiz_next', 'Weiter')}</button>`}
                    <button class="pbx-act pbx-act-gray" onclick="PBX.meetmeCloseModal()">${this.t('pbx_cancel', 'Abbrechen')}</button>
                </div>
            </div>
        `;
        this._meetmeMountModal(overlay);
    },
});

// ============================================================
// Termin verschieben / absagen (vereinheitlicht)
// ============================================================
Object.assign(PBX, {
    _mmNotifyState: { meetingId: null, action: null, mode: 'individual', queue: [], idx: 0, templates: [], newStartAt: null, force: false, allTemplates: false, sigOverride: false, sigId: null, signatures: [], previewTab: 'text', subjectByGuest: {}, bodyByGuest: {}, composeVisited: false },

    meetmeShowRescheduleModal(meetingId) {
        this.meetmeOpenWizard(meetingId, 'reschedule');
    },

    meetmeShowCancelConfirm(meetingId) {
        this.meetmeOpenWizard(meetingId, 'cancel');
    },

    async _mmNotifyPrepareState(meetingId, action) {
        const m = this._mmFindMeeting(meetingId);
        if (!m) return null;

        let tplData = null;
        try { tplData = await this.get(this.api.emailTemplates + '?event_type=meetme_' + action); }
        catch (e) { /* optional */ }

        const st = this._mmNotifyState;
        st.meetingId = meetingId;
        st.action = action;
        st.mode = 'individual';
        st.templates = (tplData && tplData.templates) || [];
        st.newStartAt = m.start_at;
        st.force = false;
        st.allTemplates = false;
        st.sigOverride = false;
        st.sigId = null;
        st.attachmentsShared = [];
        st.attachmentsByGuest = {};
        st.attachPanelOpen = false;
        st.attachTab = 'search';
        st.attachSource = 'office';
        st.attachSearchResults = [];
        st.attachBrowsePath = '';
        st.attachBrowseFolders = [];
        st.attachBrowseFiles = [];
        st.cachedSubject = null;
        st.cachedBody = null;
        st.subjectByGuest = {};
        st.bodyByGuest = {};
        st.composeVisited = false;
        if (!st.signatures.length) {
            try {
                const sigData = await this.get('/email-studio/api/signatures/');
                st.signatures = (sigData && sigData.signatures) || [];
            } catch (e) { /* optional */ }
        }
        this._mmNotifyRebuildQueue(m);
        st.idx = 0;
        return m;
    },

    async _mmNotifyOpen(meetingId, action) {
        const m = await this._mmNotifyPrepareState(meetingId, action);
        if (!m) return;
        this._mmNotifyRender();
    },

    _mmNotifyRebuildQueue(m) {
        const st = this._mmNotifyState;
        const guests = (m.guests || []).filter(g => g.is_active !== false);
        st.queue = st.force ? guests.slice() : guests.filter(g => {
            if (st.action === 'cancel') return !g.notified_cancelled;
            if (st.action === 'invite') return !g.invited_at;
            return g.last_notified_start_at !== st.newStartAt;
        });
    },

    _mmNotifyDefaultText(m, g) {
        const st = this._mmNotifyState;
        const greeting = this.t('pbx_mm_notify_default_greeting', 'Hallo');
        const signoff = this.t('pbx_mm_notify_default_signoff', 'Viele Gruesse');
        if (st.action === 'cancel') {
            const termin = this.t('pbx_mm_notify_default_termin_label', 'der Termin');
            const outro = this.t('pbx_mm_notify_default_cancel_outro', 'musste leider abgesagt werden.');
            return {
                subject: `${this.t('pbx_mm_notify_default_cancel_subject', 'Terminabsage')}: ${m.title}`,
                body: `${greeting} ${g.name},\n\n${termin} "${m.title}" ${outro}\n\n${signoff}`,
            };
        }
        if (st.action === 'invite') {
            const fmtInv = this._meetmeFmtDateTime(st.newStartAt);
            const intro = this.t('pbx_mm_notify_default_invite_intro', 'ich lade Sie herzlich zu folgendem Termin ein:');
            return {
                subject: `${this.t('pbx_mm_notify_default_invite_subject', 'Einladung')}: ${m.title}`,
                body: `${greeting} ${g.name},\n\n${intro}\n\n${m.title}\n${fmtInv} Uhr\n\n${signoff}`,
            };
        }
        const fmt = this._meetmeFmtDateTime(st.newStartAt);
        const termin2 = this.t('pbx_mm_notify_default_termin_label', 'der Termin');
        const outro2 = this.t('pbx_mm_notify_default_reschedule_outro', 'wurde verschoben.');
        const newLabel = this.t('pbx_mm_notify_default_new_label', 'Neu');
        return {
            subject: `${this.t('pbx_mm_notify_default_reschedule_subject', 'Terminaenderung')}: ${m.title}`,
            body: `${greeting} ${g.name},\n\n${termin2} "${m.title}" ${outro2}\n${newLabel}: ${fmt} Uhr\n\n${signoff}`,
        };
    },

    _mmNotifyRender() {
        const st = this._mmNotifyState;
        const m = this._mmFindMeeting(st.meetingId);
        if (!m) { this.meetmeCloseModal(); return; }

        document.querySelectorAll('#pbx-meetme-modal-overlay').forEach(el => el.remove());
        const overlay = document.createElement('div');
        overlay.className = 'pbx-meetme-modal-overlay';
        overlay.id = 'pbx-meetme-modal-overlay';

        const isCancel = st.action === 'cancel';
        const isInvite = st.action === 'invite';
        const title = isCancel ? this.t('pbx_meetme_cancel_meeting', 'Absagen') : (isInvite ? this.t('pbx_meetme_invite_title', 'Einladen') : this.t('pbx_meetme_reschedule', 'Termin verschieben'));
        const titleBg = isCancel ? 'var(--status-red, #dc3545)' : (isInvite ? 'var(--status-green, #28a745)' : 'var(--abcona-blue, #1a5fb4)');

        overlay.innerHTML = `
            <div class="pbx-meetme-modal pbx-sa-modal">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <h4 style="margin:0;background:${titleBg};color:#fff;padding:5px 12px;border-radius:6px;display:inline-block;font-size:15px">${title}</h4>
                    <button class="pbx-act pbx-act-gray" onclick="PBX.meetmeCloseModal()"><i class="bi bi-x-lg"></i> ${this.t('pbx_cancel', 'Abbrechen')}</button>
                </div>
                <p style="font-size:12px;color:#888;margin:4px 0 10px">${this._meetmeEsc(m.title)}</p>

                <div id="pbx-mm-notify-basics">${this._mmNotifyRenderBasicsHtml(st, m)}</div>

                <label>${this.t('pbx_mm_notify_mode', 'Versand')}</label>
                <div id="pbx-mm-notify-modetoggle" style="display:flex;gap:6px;margin-bottom:10px">${this._mmNotifyRenderModeToggleHtml(st)}</div>

                ${this._mmRenderCollapsible(
                    'pbx-mm-notify-options',
                    this.t('pbx_mm_notify_options_label', 'Weitere Optionen'),
                    this._mmNotifyRenderOptionsHtml(st),
                    { icon: 'bi-sliders' },
                )}

                <div id="pbx-mm-notify-content">${this._mmNotifyRenderContentHtml(st, m)}</div>

                <div style="margin:10px 0">
                    <div style="display:flex;gap:6px;margin-bottom:6px">
                        <button id="pbx-mm-notify-tab-text-btn" class="pbx-act ${st.previewTab !== 'html' ? 'pbx-act-blue' : 'pbx-act-gray'}" style="flex:1" onclick="PBX._mmNotifySetPreviewTab('text')">${this.t('pbx_mm_notify_tab_text', 'Text')}</button>
                        <button id="pbx-mm-notify-tab-html-btn" class="pbx-act ${st.previewTab === 'html' ? 'pbx-act-blue' : 'pbx-act-gray'}" style="flex:1" onclick="PBX._mmNotifySetPreviewTab('html')">${this.t('pbx_mm_notify_tab_html', 'HTML')}</button>
                        <button class="pbx-act pbx-act-gray" onclick="PBX._mmNotifyRefreshPreview()"><i class="bi bi-arrow-clockwise"></i> ${this.t('pbx_mm_notify_refresh_preview', 'Vorschau aktualisieren')}</button>
                    </div>
                    <div id="pbx-mm-notify-preview-text" style="display:${st.previewTab === 'html' ? 'none' : 'block'};white-space:pre-wrap;font-size:12px;border:1px solid var(--border-color, #dee2e6);border-radius:8px;padding:10px;max-height:280px;overflow:auto"></div>
                    <div id="pbx-mm-notify-preview-html" style="display:${st.previewTab === 'html' ? 'block' : 'none'}"></div>
                </div>

                ${this._mmRenderDeepseekPanel(
                    'pbx-mm-notify-ds-panel',
                    'pbx-mm-notify-ds-top',
                    'pbx-mm-notify-ds-bottom',
                    'PBX._mmNotifyDeepseekSuggest()',
                    'PBX._mmRaupeApplyNotify()'
                )}

                <div id="pbx-mm-notify-actions" class="pbx-meetme-modal-actions">${this._mmNotifyRenderActionsHtml(st)}</div>
            </div>
        `;
        this._meetmeMountModal(overlay);
    },

    _mmNotifyRenderModeToggleHtml(st) {
        return `
            <button class="pbx-act ${st.mode === 'all' ? 'pbx-act-blue' : 'pbx-act-gray'}" style="flex:1" onclick="PBX._mmNotifySetMode('all')">${this.t('pbx_mm_notify_all', 'An alle')}</button>
            <button class="pbx-act ${st.mode === 'individual' ? 'pbx-act-blue' : 'pbx-act-gray'}" style="flex:1" onclick="PBX._mmNotifySetMode('individual')">${this.t('pbx_mm_notify_individual', 'Individuell')}</button>
        `;
    },

    _mmNotifyRenderOptionsHtml(st) {
        return `
            <div style="display:flex;gap:6px">
                <div class="pbx-mm-opt-wrap" style="position:relative;flex:1">
                    <button type="button" style="width:100%;font-size:11px;line-height:1.25;padding:8px 4px;border-radius:8px;border:none;cursor:pointer;background:${st.force ? 'var(--abcona-blue, #1a5fb4)' : 'var(--abcona-gray-bg)'};color:${st.force ? '#fff' : 'var(--text-secondary)'}" onclick="PBX._mmNotifyToggleForce(${st.force ? 'false' : 'true'})">${this.t('pbx_mm_notify_force_short', 'Erneut informieren')}</button>
                    <div class="pbx-mm-opt-tip">${this.t('pbx_mm_notify_force_tip', 'Auch Gäste, die für diesen Termin-Stand bereits informiert wurden, erneut per E-Mail anschreiben.')}</div>
                </div>
                <div class="pbx-mm-opt-wrap" style="position:relative;flex:1">
                    <button type="button" style="width:100%;font-size:11px;line-height:1.25;padding:8px 4px;border-radius:8px;border:none;cursor:pointer;background:${st.allTemplates ? 'var(--abcona-blue, #1a5fb4)' : 'var(--abcona-gray-bg)'};color:${st.allTemplates ? '#fff' : 'var(--text-secondary)'}" onclick="PBX._mmNotifyToggleTemplateFilter(${st.allTemplates ? 'false' : 'true'})">${this.t('pbx_mm_notify_all_templates_short', 'Alle Vorlagen')}</button>
                    <div class="pbx-mm-opt-tip">${this.t('pbx_mm_notify_all_templates_tip', 'Zeigt alle E-Mail-Vorlagen im System an, nicht nur die für Verschieben/Absagen vorgesehenen.')}</div>
                </div>
                <div class="pbx-mm-opt-wrap" style="position:relative;flex:1">
                    <button type="button" style="width:100%;font-size:11px;line-height:1.25;padding:8px 4px;border-radius:8px;border:none;cursor:pointer;background:${st.sigOverride ? 'var(--abcona-blue, #1a5fb4)' : 'var(--abcona-gray-bg)'};color:${st.sigOverride ? '#fff' : 'var(--text-secondary)'}" onclick="PBX._mmNotifyToggleSigOverride(${st.sigOverride ? 'false' : 'true'})">${this.t('pbx_mm_notify_sig_override_short', 'Andere Signatur')}</button>
                    <div class="pbx-mm-opt-tip">${this.t('pbx_mm_notify_sig_override_tip', 'Standardmäßig wird die Team-Signatur angehängt. Hier kann stattdessen eine persönliche Signatur gewählt werden.')}</div>
                </div>
            </div>
            ${st.sigOverride ? `
                <select id="pbx-mm-notify-sig-select" onchange="PBX._mmNotifyState.sigId = this.value" style="width:100%;margin-top:8px">
                    ${st.signatures.map(s => `<option value="${s.id}" ${s.id === st.sigId ? 'selected' : ''}>${this._meetmeEsc(s.name)}</option>`).join('')}
                </select>
            ` : ''}
        `;
    },

    _mmNotifyRenderContentHtml(st, m) {
        const tplOptions = st.templates.map(t => `<option value="${t.id}">${this._meetmeEsc(t.name)}</option>`).join('');
        const bulkText = st.queue.length ? this._mmNotifyDefaultText(m, st.queue[0]) : { subject: '', body: '' };
        return st.mode === 'all' ? `
            <label>${this.t('pbx_sa_template', 'Vorlage')}</label>
            <div style="display:flex;gap:6px">
                <select id="pbx-mm-notify-tpl-all" style="flex:1">
                    <option value="">${this.t('pbx_sa_template_none', '– keine –')}</option>
                    ${tplOptions}
                </select>
                <button class="pbx-act pbx-act-gray" onclick="PBX._mmNotifyLoadTemplate('all')">${this.t('pbx_sa_load', 'Laden')}</button>
            </div>
            <div id="pbx-mm-notify-attach">${this._mmAttachRenderSection('notify')}</div>
            <div class="pbx-sa-mailbox" style="margin-top:8px">
                <div class="pbx-sa-subject"><input id="pbx-mm-notify-subject-all" type="text" value="${this._meetmeEsc(bulkText.subject)}"></div>
                <div class="pbx-sa-body"><textarea id="pbx-mm-notify-body-all" rows="5">${this._meetmeEsc(bulkText.body)}</textarea></div>
            </div>
            <p class="pbx-hint" style="margin-top:6px">${st.queue.length} ${this.t('pbx_mm_notify_recipients', 'Empfänger (nach Duplikat-Filter)')}</p>
        ` : (st.queue.length ? this._mmNotifyRenderIndividual(st, m) : `<p class="pbx-hint">${this.t('pbx_mm_notify_none_open', 'Alle Gäste sind bereits informiert.')}</p>`);
    },

    _mmNotifyRenderActionsHtml(st) {
        const isCancel = st.action === 'cancel';
        const isInvite = st.action === 'invite';
        const confirmLabel = isCancel ? this.t('pbx_meetme_cancel_confirm_btn', 'Ja, absagen') : (isInvite ? this.t('pbx_meetme_invite_confirm', 'Einladung senden') : this.t('pbx_meetme_reschedule_confirm', 'Verschieben'));
        const confirmCls = isCancel ? 'pbx-act-red' : 'pbx-act-green';
        return `
            <button class="pbx-act pbx-act-gray" onclick="PBX.meetmeCloseModal()">${this.t('pbx_cancel', 'Abbrechen')}</button>
            ${st.mode === 'all'
                ? `<button class="pbx-act ${confirmCls}" onclick="PBX._mmNotifySendBulk()">${confirmLabel}</button>`
                : (st.queue.length
                    ? `<button class="pbx-act pbx-act-gray" onclick="PBX._mmNotifySkip()">${this.t('pbx_sa_skip', 'Überspringen')}</button><button class="pbx-act pbx-act-green" onclick="PBX._mmNotifySendAndNext()">${this.t('pbx_sa_send_next', 'Senden & weiter')}</button>`
                    : `<button class="pbx-act ${confirmCls}" onclick="PBX._mmNotifyFinish()">${confirmLabel}</button>`)}
        `;
    },

    _mmNotifyRefreshModeToggle() {
        const el = this.$('pbx-mm-notify-modetoggle');
        if (el) el.innerHTML = this._mmNotifyRenderModeToggleHtml(this._mmNotifyState);
    },

    _mmNotifyRefreshOptions() {
        const el = this.$('pbx-mm-notify-options');
        if (el) el.innerHTML = this._mmNotifyRenderOptionsHtml(this._mmNotifyState);
    },

    _mmNotifyRefreshContent() {
        const st = this._mmNotifyState;
        const m = this._mmFindMeeting(st.meetingId);
        const el = this.$('pbx-mm-notify-content');
        if (el && m) el.innerHTML = this._mmNotifyRenderContentHtml(st, m);
    },

    _mmNotifyRefreshAttach() {
        this._mmAttachRefresh('notify');
    },

    _mmNotifyRefreshActions() {
        const el = this.$('pbx-mm-notify-actions');
        if (el) el.innerHTML = this._mmNotifyRenderActionsHtml(this._mmNotifyState);
    },

    _mmNotifyRenderBasicsHtml(st, m) {
        const isCancel = st.action === 'cancel';
        const isInvite = st.action === 'invite';
        const dateBlock = (isCancel || isInvite) ? '' : `
            <label>${this.t('pbx_meetme_new_start', 'Neues Datum/Zeit')}</label>
            <input id="pbx-mm-notify-start" type="datetime-local" value="${this._mmNotifyLocalInput(st.newStartAt)}" onchange="PBX._mmNotifyDateChanged(this.value)">
        `;
        const warnBlock = !isCancel ? '' : `
            <p class="pbx-hint" style="background:#f8d7da;color:#842029;border-radius:6px;padding:8px 10px">
                ${this.t('pbx_meetme_cancel_confirm_text2', "wird auf 'Abgesagt' gesetzt. Alle offenen, noch nicht gesendeten Erinnerungen werden storniert.")}
            </p>
        `;
        return `
            ${dateBlock}
            ${warnBlock}
            <div id="pbx-mm-notify-guests">${this._mmNotifyRenderGuestList(st, m)}</div>
        `;
    },

    _mmNotifyRenderGuestList(st, m) {
        const guests = (m.guests || []).filter(g => g.is_active !== false);
        const rows = guests.map(g => {
            const done = st.action === 'cancel' ? g.notified_cancelled
                : st.action === 'invite' ? !!g.invited_at
                : g.last_notified_start_at === st.newStartAt;
            const label = st.action === 'invite' ? this.t('pbx_mm_guest_status_invited', 'Eingeladen') : this.t('pbx_mm_guest_status_notified', 'Informiert');
            return `
                <div style="display:flex;align-items:center;gap:8px;padding:8px 4px;border-bottom:1px solid var(--border-color, #dee2e6)">
                    <div style="flex:1;min-width:0">
                        <span style="font-size:13px">${this._meetmeEsc(g.name || '')}</span>
                        <span style="font-size:12px;color:#999;margin-left:6px">${this._meetmeEsc(g.email || '')}</span>
                    </div>
                    <span style="font-size:11px;padding:3px 9px;border-radius:999px;background:${done ? 'var(--status-green-bg, #d1e7dd)' : 'var(--abcona-gray-bg)'};color:${done ? '#0f5132' : 'var(--text-secondary)'}">${done ? label : this.t('pbx_mm_guest_status_pending', 'Ausstehend')}</span>
                    <i class="bi bi-trash" style="cursor:pointer;color:var(--status-red, #dc3545)" onclick="PBX._mmNotifyDeleteGuest(${g.id})" title="${this.t('pbx_mm_guest_remove', 'Gast entfernen')}"></i>
                </div>
            `;
        }).join('');
        const addBlock = st.action === 'cancel' ? '' : `
            <button class="pbx-act pbx-mm-add-guest-btn" style="width:100%;justify-content:center;margin-top:6px" onclick="PBX._mmNotifyToggleGuestAdd()">
                <i class="bi bi-plus-lg"></i> ${this.t('pbx_mm_add_guest', 'Weiterer Gast')}
            </button>
            <div id="pbx-mm-notify-guest-search-wrap" style="position:relative;display:none;flex-wrap:wrap;gap:6px;margin-top:8px">
                <input id="pbx-mm-notify-guest-search" class="pbx-input" style="flex:1" autocomplete="off"
                       placeholder="${this.t('pbx_meetme_guest_search_ph', 'Kontakt suchen…')}"
                       oninput="PBX._mmNotifyGuestSearch(this)">
            </div>
        `;
        return `
            <div style="font-size:12px;color:#888;font-weight:600;margin:4px 0">${this.t('pbx_mm_guests_label', 'Gäste')}</div>
            ${rows}
            ${addBlock}
        `;
    },

    async _mmNotifyDeleteGuest(guestId) {
        if (!confirm(this.t('pbx_mm_guest_remove_confirm', 'Gast wirklich entfernen?'))) return;
        try {
            await this.del(`/meetme/api/guests/${guestId}/delete/`);
        } catch (e) {
            this.toast(this.t('pbx_mm_guest_remove_err', 'Konnte nicht entfernt werden'));
            return;
        }
        const st = this._mmNotifyState;
        const m = this._mmFindMeeting(st.meetingId);
        if (m) {
            m.guests = (m.guests || []).filter(g => g.id !== guestId);
            this._mmNotifyRebuildQueue(m);
            st.idx = 0;
        }
        this._mmNotifyRefreshGuestList();
        this._mmNotifyRefreshContent();
        this._mmNotifyRefreshActions();
    },

    _mmNotifyRefreshGuestList() {
        const st = this._mmNotifyState;
        const m = this._mmFindMeeting(st.meetingId);
        const el = this.$('pbx-mm-notify-guests');
        if (el && m) el.innerHTML = this._mmNotifyRenderGuestList(st, m);
    },

    _mmNotifyToggleGuestAdd() {
        const wrap = this.$('pbx-mm-notify-guest-search-wrap');
        if (!wrap) return;
        const show = wrap.style.display === 'none';
        wrap.style.display = show ? 'flex' : 'none';
        if (show) { const i = this.$('pbx-mm-notify-guest-search'); if (i) i.focus(); }
    },

    _mmNotifyGuestSearch(inp) {
        const q = (inp.value || '').trim();
        clearTimeout(this._mmNotifyGuestTimer);
        if (q.length < 2) return;
        this._mmNotifyGuestTimer = setTimeout(async () => {
            let data = null;
            try { data = await this.get(this.api.searchAll + '?q=' + encodeURIComponent(q) + '&scope=personen&size=8'); }
            catch (e) { return; }
            const results = (data && data.results) || [];
            this._mmNotifyRenderGuestSearchResults(results);
        }, 300);
    },

    _mmNotifyRenderGuestSearchResults(results) {
        let pop = document.getElementById('pbx-mm-notify-guest-pop');
        if (pop) pop.remove();
        const wrap = document.getElementById('pbx-mm-notify-guest-search-wrap');
        if (!wrap) return;
        pop = document.createElement('div');
        pop.id = 'pbx-mm-notify-guest-pop';
        pop.className = 'pbx-meetme-guest-pop';
        pop.innerHTML = results.map((r, i) => `
            <div class="pbx-meetme-guest-pop-item" onclick="PBX._mmNotifyGuestAdd(${i})">
                <span>${this._meetmeEsc(r.title || '')}</span>
                <span class="pbx-meetme-guest-pop-meta">${this._meetmeEsc(r.meta || '')}</span>
            </div>
        `).join('');
        wrap.appendChild(pop);
        this._mmNotifyGuestSearchResults = results;
    },

    async _mmNotifyGuestAdd(idx) {
        const r = (this._mmNotifyGuestSearchResults || [])[idx];
        const pop = document.getElementById('pbx-mm-notify-guest-pop');
        if (pop) pop.remove();
        if (!r) return;

        let detail = null;
        try { detail = await this.get(`/crm/api/berater/${r.id}/`); }
        catch (e) { /* Detail nicht verfuegbar */ }

        const emails = (detail && Array.isArray(detail.emails)) ? detail.emails.filter(e => !e.invalid_email) : [];
        const phones = (detail && Array.isArray(detail.phones)) ? detail.phones : [];
        const phone = (phones.find(p => p.is_primary) || phones[0] || {}).raw || '';

        if (emails.length <= 1) {
            const email = (emails[0] && emails[0].email) || '';
            if (!email) this.toast(this.t('pbx_meetme_guest_no_email', 'Keine E-Mail gefunden - bitte manuell ergaenzen'));
            await this._mmNotifyGuestSave(r, email, phone);
            return;
        }
        this._mmNotifyShowEmailChoiceInline(r, emails, phone);
    },

    _mmNotifyShowEmailChoiceInline(r, emails, phone) {
        const wrap = this.$('pbx-mm-notify-guest-search-wrap');
        if (!wrap) return;
        this._mmNotifyEmailChoiceCtx = { r, emails, phone };
        let box = document.getElementById('pbx-mm-notify-email-choice');
        if (box) box.remove();
        box = document.createElement('div');
        box.id = 'pbx-mm-notify-email-choice';
        box.style.cssText = 'width:100%;border:1px solid var(--border-color);border-radius:8px;padding:10px;margin-top:6px;background:var(--bg-white);color:var(--text-primary)';
        box.innerHTML = `
            <p style="font-size:12px;color:var(--text-muted);margin:0 0 8px">${this.t('pbx_meetme_choose_email_hint', 'Mehrere E-Mail-Adressen gefunden, eine oder mehrere waehlen:')}</p>
            ${emails.map((e, i) => `
                <label style="display:flex;align-items:center;gap:8px;padding:4px 0;font-size:12.5px">
                    <input type="checkbox" class="pbx-mm-notify-email-cb" value="${i}" ${e.primary ? 'checked' : ''} style="width:auto">
                    ${this._meetmeEsc(e.email)} ${e.primary ? '<span style="color:#999;font-size:11px">(primaer)</span>' : ''}
                </label>
            `).join('')}
            <div style="display:flex;justify-content:flex-end;gap:6px;margin-top:8px">
                <button class="pbx-act pbx-act-gray" onclick="document.getElementById('pbx-mm-notify-email-choice').remove()">${this.t('pbx_cancel', 'Abbrechen')}</button>
                <button class="pbx-act pbx-act-green" onclick="PBX._mmNotifyConfirmEmailChoice()">${this.t('pbx_meetme_add', 'Hinzufuegen')}</button>
            </div>
        `;
        wrap.appendChild(box);
    },

    async _mmNotifyConfirmEmailChoice() {
        const ctx = this._mmNotifyEmailChoiceCtx;
        const checked = Array.from(document.querySelectorAll('.pbx-mm-notify-email-cb:checked')).map(cb => parseInt(cb.value, 10));
        const box = document.getElementById('pbx-mm-notify-email-choice');
        if (box) box.remove();
        if (!ctx || !checked.length) {
            this.toast(this.t('pbx_meetme_choose_email_none', 'Keine E-Mail ausgewaehlt'));
            return;
        }
        for (const idx of checked) {
            const email = ctx.emails[idx].email;
            await this._mmNotifyGuestSave(ctx.r, email, ctx.phone);
        }
    },

    async _mmNotifyGuestSave(r, email, phone) {
        const st = this._mmNotifyState;
        let created = null;
        try {
            created = await this.post(`/meetme/api/meetings/${st.meetingId}/guests/create/`, {
                contact_crm_id: r.id || null,
                name: r.title || '',
                email: email || `noemail-${r.id}@platzhalter.invalid`,
                phone: phone || '',
            });
        } catch (e) {
            this.toast(this.t('pbx_meetme_guest_err', 'Gast konnte nicht hinzugefuegt werden'));
            return;
        }
        this.toast(this.t('pbx_meetme_guest_added', 'Gast hinzugefuegt'));
        const searchInp = this.$('pbx-mm-notify-guest-search');
        if (searchInp) searchInp.value = '';
        const m = this._mmFindMeeting(st.meetingId);
        if (m && created) {
            m.guests = m.guests || [];
            m.guests.push(created);
            this._mmNotifyRebuildQueue(m);
        }
        this._mmNotifyRefreshGuestList();
        this._mmNotifyRefreshContent();
        this._mmNotifyRefreshActions();
    },

    _mmNotifyRenderIndividual(st, m) {
        const g = st.queue[st.idx];
        if (!g) return '';
        const chips = st.queue.map((item, i) => {
            let cls = 'pbx-sa-chip';
            if (i < st.idx) cls += ' done';
            if (i === st.idx) cls += ' current';
            const customized = st.subjectByGuest && Object.prototype.hasOwnProperty.call(st.subjectByGuest, item.id);
            return `<span class="${cls}" style="cursor:pointer" onclick="PBX._mmNotifyGoToGuest(${i})" title="${this._meetmeEsc(item.name || '')}">${this._meetmeEsc(item.name || '')}${customized ? ' *' : ''}</span>`;
        }).join('');
        const text = this._mmNotifyGetGuestDraft(m, g);
        const tplOptions = st.templates.map(t => `<option value="${t.id}">${this._meetmeEsc(t.name)}</option>`).join('');
        return `
            <div class="pbx-sa-guestchips">${chips}</div>
            <p class="pbx-sa-meta">${this.t('pbx_sa_of', 'Gast')} ${st.idx + 1} ${this.t('pbx_sa_of2', 'von')} ${st.queue.length} · ${this._meetmeEsc(g.email || '')}</p>

            <label>${this.t('pbx_sa_template', 'Vorlage')}</label>
            <div style="display:flex;gap:6px">
                <select id="pbx-mm-notify-tpl-ind" style="flex:1">
                    <option value="">${this.t('pbx_sa_template_none', '– keine –')}</option>
                    ${tplOptions}
                </select>
                <button class="pbx-act pbx-act-gray" onclick="PBX._mmNotifyLoadTemplate('individual')">${this.t('pbx_sa_load', 'Laden')}</button>
            </div>

            <div id="pbx-mm-notify-attach">${this._mmAttachRenderSection('notify')}</div>

            <div class="pbx-sa-mailbox" style="margin-top:8px">
                <div class="pbx-sa-mailhead">
                    <div class="pbx-sa-avatar">${this._meetmeInitials(g.name)}</div>
                    <p style="font-size:12.5px;font-weight:600;margin:0">${this._meetmeEsc(g.name)} <span style="font-weight:400;color:#999">&lt;${this._meetmeEsc(g.email || '')}&gt;</span></p>
                </div>
                <div class="pbx-sa-subject"><input id="pbx-mm-notify-subject-ind" type="text" value="${this._meetmeEsc(text.subject)}"></div>
                <div class="pbx-sa-body"><textarea id="pbx-mm-notify-body-ind" rows="5">${this._meetmeEsc(text.body)}</textarea></div>
            </div>
        `;
    },

    _mmNotifyLocalInput(iso) {
        const d = new Date(iso);
        const pad = n => String(n).padStart(2, '0');
        return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
    },

    _mmNotifyDateChanged(value) {
        this._mmNotifyState.newStartAt = new Date(value).toISOString();
        const m = this._mmFindMeeting(this._mmNotifyState.meetingId);
        this._mmNotifyRebuildQueue(m);
        this._mmNotifyState.idx = 0;
        this._mmNotifyRefreshContent();
        this._mmNotifyRefreshActions();
    },

    _mmNotifySetMode(mode) {
        this._mmNotifySaveCurrentGuestText();
        this._mmNotifyState.mode = mode;
        this._mmNotifyRefreshModeToggle();
        this._mmNotifyRefreshContent();
        this._mmNotifyRefreshActions();
    },

    _mmNotifyToggleForce(checked) {
        this._mmNotifyState.force = checked;
        const m = this._mmFindMeeting(this._mmNotifyState.meetingId);
        this._mmNotifyRebuildQueue(m);
        this._mmNotifyState.idx = 0;
        this._mmNotifyRefreshOptions();
        this._mmNotifyRefreshContent();
        this._mmNotifyRefreshActions();
    },

    _mmNotifyToggleSigOverride(checked) {
        const st = this._mmNotifyState;
        st.sigOverride = checked;
        if (checked && !st.sigId && st.signatures.length) {
            st.sigId = st.signatures[0].id;
        }
        this._mmNotifyRefreshOptions();
    },

    _mmNotifyGetCurrentBody() {
        const st = this._mmNotifyState;
        const el = this.$(st.mode === 'all' ? 'pbx-mm-notify-body-all' : 'pbx-mm-notify-body-ind');
        return el ? el.value : '';
    },

    _mmNotifySetPreviewTab(tab) {
        this._mmNotifyState.previewTab = tab;
        const textEl = this.$('pbx-mm-notify-preview-text');
        const htmlEl = this.$('pbx-mm-notify-preview-html');
        if (textEl) textEl.style.display = tab === 'html' ? 'none' : 'block';
        if (htmlEl) htmlEl.style.display = tab === 'html' ? 'block' : 'none';
        const textBtn = this.$('pbx-mm-notify-tab-text-btn');
        const htmlBtn = this.$('pbx-mm-notify-tab-html-btn');
        if (textBtn) textBtn.className = 'pbx-act ' + (tab !== 'html' ? 'pbx-act-blue' : 'pbx-act-gray');
        if (htmlBtn) htmlBtn.className = 'pbx-act ' + (tab === 'html' ? 'pbx-act-blue' : 'pbx-act-gray');
        if (tab === 'html') this._mmNotifyRefreshPreview();
    },

    async _mmNotifyRefreshPreview() {
        const st = this._mmNotifyState;
        const body = this._mmNotifyGetCurrentBody();
        if (!body.trim()) { this.toast(this.t('pbx_mm_notify_preview_empty', 'Erst Text eingeben')); return; }
        try {
            const data = await this.post('/meetme/api/notify-preview/', {
                body, signature_id: st.sigOverride ? st.sigId : null, action: st.action,
            });
            const textEl = this.$('pbx-mm-notify-preview-text');
            if (textEl) textEl.textContent = data.text || '';
            this._mmNotifyRenderPreviewHtml(data.html || '');
        } catch (e) {
            this.toast(this.t('pbx_mm_notify_preview_err', 'Vorschau konnte nicht geladen werden'));
        }
    },

    _mmNotifyRenderPreviewHtml(html) {
        this._mmMountPreviewHtml(this.$('pbx-mm-notify-preview-html'), html, 'pbx-mm-notify-preview-iframe', 280);
    },

    async _mmNotifyToggleTemplateFilter(checked) {
        const st = this._mmNotifyState;
        st.allTemplates = checked;
        let tplData = null;
        try {
            const url = this.api.emailTemplates + (checked ? '' : ('?event_type=meetme_' + st.action));
            tplData = await this.get(url);
        } catch (e) { /* optional */ }
        st.templates = (tplData && tplData.templates) || [];
        this._mmNotifyRefreshOptions();
        this._mmNotifyRefreshContent();
    },

    async _mmNotifyLoadTemplate(which) {
        const st = this._mmNotifyState;
        const sel = this.$(which === 'all' ? 'pbx-mm-notify-tpl-all' : 'pbx-mm-notify-tpl-ind');
        const tplId = sel && sel.value;
        if (!tplId) return;
        const guestId = which === 'individual' && st.queue[st.idx] ? st.queue[st.idx].id : '';
        try {
            const url = `/meetme/api/meetings/${st.meetingId}/render-preview/?template_id=${tplId}` + (guestId ? `&guest_id=${guestId}` : '');
            const data = await this.get(url);
            this.$(which === 'all' ? 'pbx-mm-notify-subject-all' : 'pbx-mm-notify-subject-ind').value = data.subject || '';
            this.$(which === 'all' ? 'pbx-mm-notify-body-all' : 'pbx-mm-notify-body-ind').value = data.text || '';
            this._mmNotifySaveCurrentGuestText();
            st.composeVisited = true;
            await this._mmNotifyRefreshPreview();
        } catch (e) {
            this.toast(this.t('pbx_sa_template_err', 'Vorlage konnte nicht geladen werden'));
        }
    },

    async _mmNotifyDeepseekSuggest() {
        const current = (this._mmNotifyGetCurrentBody() || '').trim();
        if (!current) { this.toast(this.t('pbx_sa_ds_empty', 'Erst Text eingeben oder Vorlage laden')); return; }
        this.$('pbx-mm-notify-ds-top').value = current;
        const btn = event.currentTarget;
        const origHtml = btn.innerHTML;
        btn.innerHTML = '<i class="bi bi-hourglass-split"></i> ...'; btn.disabled = true;
        try {
            const res = await this.post('/meetme/api/deepseek-suggest/', this._mmRaupeRequest(current));
            if (res && res.suggestion) this.$('pbx-mm-notify-ds-bottom').value = res.suggestion;
            else this.toast(this.t('pbx_sa_ds_err', 'DeepSeek konnte keinen Vorschlag liefern'));
        } catch (e) {
            this.toast(this.t('pbx_sa_ds_err', 'DeepSeek konnte keinen Vorschlag liefern'));
        } finally {
            btn.innerHTML = origHtml; btn.disabled = false;
        }
    },

    async _mmNotifySkip() {
        const st = this._mmNotifyState;
        st.idx++;
        if (st.idx >= st.queue.length) { await this._mmNotifyFinish(); return; }
        this._mmNotifyRefreshContent();
        this._mmNotifyRefreshActions();
    },

    async _mmNotifySendAndNext() {
        const st = this._mmNotifyState;
        const g = st.queue[st.idx];
        this._mmNotifySaveCurrentGuestText();
        const draft = this._mmNotifyGetGuestDraft(this._mmFindMeeting(st.meetingId), g);
        if (!draft.subject.trim() || !draft.body.trim()) { this.toast(this.t('pbx_meetme_fields_req', 'Betreff und Text erforderlich')); return; }
        try {
            await this.post(`/meetme/api/guests/${g.id}/send-adhoc/`, {
                subject: draft.subject.trim(), body: draft.body.trim(),
                notification_kind: st.action,
                target_start_at: st.newStartAt,
                signature_id: st.sigOverride ? st.sigId : null,
                attachment_refs: st.attachmentsByGuest[g.id] || [],
            });
        } catch (e) {
            this.toast(this.t('pbx_mm_compose_err', 'Senden fehlgeschlagen')); return;
        }
        st.idx++;
        if (st.idx >= st.queue.length) { await this._mmNotifyFinish(); return; }
        this._mmNotifyRefreshContent();
        this._mmNotifyRefreshActions();
    },

    async _mmNotifySendBulk() {
        const st = this._mmNotifyState;
        const m = this._mmFindMeeting(st.meetingId);
        this._mmNotifySaveCurrentGuestText();
        const draft = this._mmNotifyGetBulkDraft(m);
        if (!draft.subject.trim() || !draft.body.trim()) { this.toast(this.t('pbx_meetme_fields_req', 'Betreff und Text erforderlich')); return; }
        const committed = await this._mmNotifyCommit();
        if (!committed) return;
        try {
            await this.post(`/meetme/api/meetings/${st.meetingId}/notify-bulk/`, {
                notification_kind: st.action, subject: draft.subject.trim(), body: draft.body.trim(),
                target_start_at: st.newStartAt, force: st.force,
                signature_id: st.sigOverride ? st.sigId : null,
                attachment_refs: st.attachmentsShared,
            });
        } catch (e) {
            this.toast(this.t('pbx_mm_notify_bulk_err', 'Versand an alle fehlgeschlagen'));
        }
        this.meetmeCloseModal();
        this.toast(st.action === 'cancel' ? this.t('pbx_meetme_cancelled', 'Termin abgesagt') : this.t('pbx_meetme_saved', 'Gespeichert'));
        await this.meetmeLoadMeetings();
    },

    async _mmNotifyFinish() {
        const st = this._mmNotifyState;
        const committed = await this._mmNotifyCommit();
        this.meetmeCloseModal();
        if (committed) {
            this.toast(st.action === 'cancel' ? this.t('pbx_meetme_cancelled', 'Termin abgesagt') : this.t('pbx_meetme_saved', 'Gespeichert'));
        }
        await this.meetmeLoadMeetings();
    },

    async _mmNotifyCommit() {
        const st = this._mmNotifyState;
        try {
            if (st.action === 'cancel') {
                await this.del(`/meetme/api/meetings/${st.meetingId}/cancel/`);
            } else {
                await this.post(`/meetme/api/meetings/${st.meetingId}/reschedule/`, { new_start_at: st.newStartAt });
            }
            return true;
        } catch (e) {
            this.toast(st.action === 'cancel' ? this.t('pbx_meetme_cancel_err', 'Absagen fehlgeschlagen') : this.t('pbx_meetme_reschedule_err', 'Verschieben fehlgeschlagen'));
            return false;
        }
    },

});

// ============================================================
// Meeting bearbeiten / absagen
// ============================================================
Object.assign(PBX, {
    async meetmeShowEditModal(meetingId) {
        const m = this._mmFindMeeting(meetingId);
        if (!m) return;

        let rooms = [];
        try { const d = await this.get(this.api.meetmeRooms); rooms = d.rooms || []; } catch (e) {}

        document.querySelectorAll('#pbx-meetme-modal-overlay').forEach(el => el.remove());
        const overlay = document.createElement('div');
        overlay.className = 'pbx-meetme-modal-overlay';
        overlay.id = 'pbx-meetme-modal-overlay';
        overlay.innerHTML = `
            <div class="pbx-meetme-modal">
                <h4>${this.t('pbx_meetme_edit', 'Termin bearbeiten')}</h4>
                <label>${this.t('pbx_meetme_field_title', 'Titel')}</label>
                <input id="pbx-mm-edit-title" type="text" value="${this._meetmeEsc(m.title)}">
                <label>${this.t('pbx_meetme_field_duration', 'Dauer (Minuten)')}</label>
                <input id="pbx-mm-edit-duration" type="number" value="${m.duration_minutes}">
                <label>${this.t('pbx_meetme_field_room', 'Konferenzraum')}</label>
                <select id="pbx-mm-edit-room">
                    <option value="">${this.t('pbx_meetme_room_none', '– kein fester Raum –')}</option>
                    ${rooms.map(r => `<option value="${r.room_extension}" ${r.room_extension === m.room_extension ? 'selected' : ''}>${r.room_extension}${r.hint_state ? ' (' + r.hint_state + ')' : ''}</option>`).join('')}
                </select>
                <label>${this.t('pbx_meetme_field_desc', 'Beschreibung')}</label>
                <textarea id="pbx-mm-edit-desc" rows="3">${this._meetmeEsc(m.description || '')}</textarea>
                <div class="pbx-meetme-modal-actions">
                    <button class="pbx-act pbx-act-gray" onclick="PBX.meetmeCloseModal()">${this.t('pbx_cancel', 'Abbrechen')}</button>
                    <button class="pbx-act pbx-act-green" onclick="PBX.meetmeSaveEdit(${meetingId})">${this.t('pbx_meetme_save', 'Speichern')}</button>
                </div>
            </div>
        `;
        this._meetmeMountModal(overlay);
    },

    async meetmeSaveEdit(meetingId) {
        const title = this.$('pbx-mm-edit-title').value.trim();
        const duration = parseInt(this.$('pbx-mm-edit-duration').value, 10) || 60;
        const room = this.$('pbx-mm-edit-room').value;
        const desc = this.$('pbx-mm-edit-desc').value;
        if (!title) { this.toast(this.t('pbx_meetme_fields_req', 'Titel erforderlich')); return; }

        try {
            await this.patchReq(`/meetme/api/meetings/${meetingId}/update/`, {
                title, duration_minutes: duration, room_extension: room, description: desc,
            });
            this.meetmeCloseModal();
            this.toast(this.t('pbx_meetme_saved', 'Gespeichert'));
            await this.meetmeLoadMeetings();
            this.meetmeSelectMeeting(meetingId);
        } catch (e) {
            this.toast(this.t('pbx_meetme_save_err', 'Speichern fehlgeschlagen'));
        }
    },

    async patchReq(url, body) {
        const r = await fetch(url, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrf(), 'X-Requested-With': 'XMLHttpRequest' },
            body: JSON.stringify(body || {}),
        });
        return r.json();
    },
});

// ============================================================
// Neuer Kontakt (optional mit neuer Firma) - Schnellanlage
// ============================================================
Object.assign(PBX, {
    _mmNewContactState: { phones: [{ field_name: 'phone_mobile', raw: '' }], emails: [{ address: '', primary: true }], companyMode: 'search', selectedAccount: null },

    _mmNewContactHtml(meetingId, wavnoteMode) {
        const st = this._mmNewContactState;
        return `
            <div class="pbx-meetme-modal pbx-mm-newcontact-modal">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <h4 style="margin:0"><i class="bi bi-person-plus"></i> ${this.t('pbx_mm_new_contact', 'Neuer Kontakt')}</h4>
                    <button class="pbx-act pbx-act-gray" onclick="PBX.meetmeCloseModal()"><i class="bi bi-x-lg"></i></button>
                </div>

                <div class="pbx-mm-section">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                        <label style="margin:0">${this.t('pbx_mm_company', 'Firma (optional)')}</label>
                        ${st.companyMode === 'search'
                            ? `<button class="pbx-act pbx-act-gray" style="padding:3px 8px;font-size:11px" onclick="PBX._mmToggleCompanyMode('new')"><i class="bi bi-building-add"></i> ${this.t('pbx_mm_new_company', 'neu')}</button>`
                            : `<button class="pbx-act pbx-act-gray" style="padding:3px 8px;font-size:11px" onclick="PBX._mmToggleCompanyMode('search')"><i class="bi bi-arrow-90deg-left"></i> ${this.t('pbx_mm_search_instead', 'stattdessen suchen')}</button>`
                        }
                    </div>
                    ${st.companyMode === 'search' ? `
                        <div style="position:relative" id="pbx-mm-company-search-wrap">
                            <input id="pbx-mm-company-search" type="text" autocomplete="off" placeholder="${this.t('pbx_mm_company_search_ph', 'Firma suchen…')}" oninput="PBX._mmCompanySearch(this)" ${st.selectedAccount ? 'style="display:none"' : ''}>
                        </div>
                        ${st.selectedAccount ? `
                            <div class="pbx-mm-company-chip">
                                <span>${this._meetmeEsc(st.selectedAccount.name)}</span>
                                <i class="bi bi-x" onclick="PBX._mmClearCompany()"></i>
                            </div>
                        ` : ''}
                    ` : `
                        <div class="pbx-mm-newcompany-box">
                            <label>${this.t('pbx_meetme_field_company_name', 'Firmenname')} <span style="color:#c0392b">*</span></label>
                            <input id="pbx-mm-new-company-name" type="text" placeholder="${this.t('pbx_mm_company_name_ph', 'Firmenname (Pflicht)')}">
                            <label>${this.t('pbx_meetme_field_city', 'Stadt (optional)')}</label>
                            <input id="pbx-mm-new-company-city" type="text" placeholder="${this.t('pbx_mm_city_ph', 'Stadt')}">
                        </div>
                        <p class="pbx-hint" style="margin-top:6px">${this.t('pbx_mm_company_hint', 'Wird beim Anlegen automatisch als neuer Kunde in der CRM-DB erstellt und mit diesem Kontakt verknüpft.')}</p>
                    `}
                </div>

                <div class="pbx-mm-section">
                    <div style="display:flex;gap:8px">
                        <div style="width:80px">
                            <label>${this.t('pbx_mm_salutation', 'Anrede')}</label>
                            <select id="pbx-mm-new-salutation">
                                <option>Hr.</option><option>Fr.</option><option>-</option>
                            </select>
                        </div>
                        <div style="flex:1">
                            <label>${this.t('pbx_meetme_field_firstname', 'Vorname')}</label>
                            <input id="pbx-mm-new-firstname" type="text" placeholder="${this.t('pbx_meetme_field_firstname', 'Vorname')}">
                        </div>
                    </div>
                    <label>${this.t('pbx_meetme_field_lastname', 'Nachname')} <span style="color:#c0392b">*</span></label>
                    <input id="pbx-mm-new-lastname" type="text" placeholder="${this.t('pbx_mm_lastname_ph', 'Nachname (Pflicht)')}">
                    <label>${this.t('pbx_mm_category', 'Kategorie')}</label>
                    <select id="pbx-mm-new-category">
                        <option value="berater">${this.t('pbx_mm_cat_berater', 'Berater')}</option>
                        <option value="kunde" selected>${this.t('pbx_mm_cat_kunde', 'Kunde')}</option>
                        <option value="interessent">${this.t('pbx_mm_cat_interessent', 'Interessent')}</option>
                        <option value="andere">${this.t('pbx_mm_cat_andere', 'Andere')}</option>
                    </select>
                </div>

                <div class="pbx-mm-section">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                        <label style="margin:0">${this.t('pbx_mm_phones', 'Telefonnummern')}</label>
                        <button class="pbx-act pbx-act-gray" style="padding:3px 8px;font-size:11px" onclick="PBX._mmAddPhoneRow()"><i class="bi bi-plus"></i></button>
                    </div>
                    <div id="pbx-mm-phones-list">${this._mmRenderPhoneRows()}</div>
                </div>

                <div class="pbx-mm-section">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                        <label style="margin:0">${this.t('pbx_mm_emails', 'E-Mail-Adressen')}</label>
                        <button class="pbx-act pbx-act-gray" style="padding:3px 8px;font-size:11px" onclick="PBX._mmAddEmailRow()"><i class="bi bi-plus"></i></button>
                    </div>
                    <div id="pbx-mm-emails-list">${this._mmRenderEmailRows()}</div>
                </div>

                <div class="pbx-meetme-modal-actions">
                    <button class="pbx-act pbx-act-gray" onclick="PBX.meetmeCloseModal()">${this.t('pbx_cancel', 'Abbrechen')}</button>
                    <button class="pbx-act pbx-act-green" onclick="${wavnoteMode ? 'PBX.wavnoteSaveNewContact()' : `PBX._mmSaveNewContact(${meetingId})`}"><i class="bi bi-check-lg"></i> ${wavnoteMode ? this.t('pbx_wavnote_create_contact', 'Anlegen und Telefonnotiz zuordnen') : this.t('pbx_mm_create_and_add', 'Anlegen und als Gast hinzufügen')}</button>
                </div>
            </div>
        `;
    },
});

Object.assign(PBX, {
    _mmRenderPhoneRows() {
        const st = this._mmNewContactState;
        return st.phones.map((p, i) => `
            <div class="pbx-mm-row">
                <select onchange="PBX._mmNewContactState.phones[${i}].field_name=this.value">
                    <option value="phone_mobile" ${p.field_name === 'phone_mobile' ? 'selected' : ''}>${this.t('pbx_mm_mobile', 'mobil')}</option>
                    <option value="phone_work" ${p.field_name === 'phone_work' ? 'selected' : ''}>${this.t('pbx_mm_work', 'geschäftl.')}</option>
                    <option value="phone_home" ${p.field_name === 'phone_home' ? 'selected' : ''}>${this.t('pbx_mm_home', 'privat')}</option>
                </select>
                <input type="text" value="${this._meetmeEsc(p.raw)}" placeholder="+49 …" oninput="PBX._mmNewContactState.phones[${i}].raw=this.value">
                <button class="pbx-act pbx-act-gray" style="padding:5px 8px" onclick="PBX._mmRemovePhoneRow(${i})"><i class="bi bi-trash"></i></button>
            </div>
        `).join('');
    },

    _mmAddPhoneRow() {
        this._mmNewContactState.phones.push({ field_name: 'phone_mobile', raw: '' });
        this.$('pbx-mm-phones-list').innerHTML = this._mmRenderPhoneRows();
    },

    _mmRemovePhoneRow(idx) {
        this._mmNewContactState.phones.splice(idx, 1);
        if (!this._mmNewContactState.phones.length) this._mmNewContactState.phones.push({ field_name: 'phone_mobile', raw: '' });
        this.$('pbx-mm-phones-list').innerHTML = this._mmRenderPhoneRows();
    },

    _mmRenderEmailRows() {
        const st = this._mmNewContactState;
        return st.emails.map((e, i) => `
            <div class="pbx-mm-row">
                <input type="text" value="${this._meetmeEsc(e.address)}" placeholder="name@firma.de" oninput="PBX._mmNewContactState.emails[${i}].address=this.value" style="flex:1">
                <label style="display:flex;align-items:center;gap:4px;font-size:11px;color:var(--abcona-text-secondary,#888);white-space:nowrap">
                    <input type="checkbox" ${e.primary ? 'checked' : ''} onchange="PBX._mmSetPrimaryEmail(${i}, this.checked)" style="width:auto">${this.t('pbx_mm_primary', 'primär')}
                </label>
                <button class="pbx-act pbx-act-gray" style="padding:5px 8px" onclick="PBX._mmRemoveEmailRow(${i})"><i class="bi bi-trash"></i></button>
            </div>
        `).join('');
    },

    _mmAddEmailRow() {
        this._mmNewContactState.emails.push({ address: '', primary: false });
        this.$('pbx-mm-emails-list').innerHTML = this._mmRenderEmailRows();
    },

    _mmRemoveEmailRow(idx) {
        this._mmNewContactState.emails.splice(idx, 1);
        if (!this._mmNewContactState.emails.length) this._mmNewContactState.emails.push({ address: '', primary: true });
        this.$('pbx-mm-emails-list').innerHTML = this._mmRenderEmailRows();
    },

    _mmSetPrimaryEmail(idx, checked) {
        this._mmNewContactState.emails.forEach((e, i) => { e.primary = (i === idx) && checked; });
        this.$('pbx-mm-emails-list').innerHTML = this._mmRenderEmailRows();
    },

    _mmToggleCompanyMode(mode) {
        this._mmNewContactState.companyMode = mode;
        this._mmNewContactState.selectedAccount = null;
        const modalWrap = document.querySelector('#pbx-meetme-modal-overlay .pbx-meetme-modal');
        if (modalWrap) modalWrap.parentElement.innerHTML = '';
        this.meetmeShowNewContactModal.call(this, this._mmCurrentMeetingIdForNewContact);
    },

    meetmeShowNewContactModal(meetingId) {
        this._mmCurrentMeetingIdForNewContact = meetingId;
        const pop = document.getElementById('pbx-meetme-guest-pop');
        if (pop) pop.remove();
        document.querySelectorAll('#pbx-meetme-modal-overlay').forEach(el => el.remove());

        const overlay = document.createElement('div');
        overlay.className = 'pbx-meetme-modal-overlay';
        overlay.id = 'pbx-meetme-modal-overlay';
        overlay.innerHTML = this._mmNewContactHtml(meetingId);
        this._meetmeMountModal(overlay);
    },

    _mmCompanySearch(inp) {
        const q = (inp.value || '').trim();
        clearTimeout(this._mmCompanySearchTimer);
        if (q.length < 2) return;
        this._mmCompanySearchTimer = setTimeout(async () => {
            let data = null;
            try { data = await this.get(this.api.searchAll + '?q=' + encodeURIComponent(q) + '&scope=firmen&size=8'); }
            catch (e) { return; }
            const results = (data && data.results) || [];
            this._mmRenderCompanyResults(inp, results);
        }, 300);
    },

    _mmRenderCompanyResults(inp, results) {
        let pop = document.getElementById('pbx-mm-company-pop');
        if (pop) pop.remove();
        if (!results.length) return;
        const wrap = document.getElementById('pbx-mm-company-search-wrap');
        if (!wrap) return;
        pop = document.createElement('div');
        pop.id = 'pbx-mm-company-pop';
        pop.className = 'pbx-meetme-guest-pop';
        pop.innerHTML = results.map((r, i) => `
            <div class="pbx-meetme-guest-pop-item" onclick="PBX._mmSelectCompany(${i})">
                <span>${this._meetmeEsc(r.title || '')}</span>
                <span class="pbx-meetme-guest-pop-meta">${this._meetmeEsc(r.meta || '')}</span>
            </div>
        `).join('');
        wrap.appendChild(pop);
        this._mmCompanySearchResults = results;
    },

    _mmSelectCompany(idx) {
        const r = (this._mmCompanySearchResults || [])[idx];
        const pop = document.getElementById('pbx-mm-company-pop');
        if (pop) pop.remove();
        if (!r) return;
        this._mmNewContactState.selectedAccount = { crm_id: r.id, name: r.title };
        const meetingId = this._mmCurrentMeetingIdForNewContact;
        document.querySelectorAll('#pbx-meetme-modal-overlay').forEach(el => el.remove());
        const overlay = document.createElement('div');
        overlay.className = 'pbx-meetme-modal-overlay';
        overlay.id = 'pbx-meetme-modal-overlay';
        overlay.innerHTML = this._mmNewContactHtml(meetingId);
        this._meetmeMountModal(overlay);
    },

    _mmClearCompany() {
        this._mmNewContactState.selectedAccount = null;
        const meetingId = this._mmCurrentMeetingIdForNewContact;
        document.querySelectorAll('#pbx-meetme-modal-overlay').forEach(el => el.remove());
        const overlay = document.createElement('div');
        overlay.className = 'pbx-meetme-modal-overlay';
        overlay.id = 'pbx-meetme-modal-overlay';
        overlay.innerHTML = this._mmNewContactHtml(meetingId);
        this._meetmeMountModal(overlay);
    },

    async _mmSaveNewContact(meetingId) {
        const st = this._mmNewContactState;
        const lastName = this.$('pbx-mm-new-lastname').value.trim();
        if (!lastName) { this.toast(this.t('pbx_mm_lastname_req', 'Nachname erforderlich')); return; }

        const body = {
            salutation: this.$('pbx-mm-new-salutation').value,
            first_name: this.$('pbx-mm-new-firstname').value.trim(),
            last_name: lastName,
            category: this.$('pbx-mm-new-category').value,
            phones: st.phones.filter(p => p.raw.trim()),
            emails: st.emails.filter(e => e.address.trim()),
            company: {},
        };

        if (st.companyMode === 'new') {
            const name = (this.$('pbx-mm-new-company-name') || {}).value || '';
            if (name.trim()) {
                body.company.new_name = name.trim();
                body.company.city = (this.$('pbx-mm-new-company-city') || {}).value || '';
            }
        } else if (st.selectedAccount) {
            body.company.existing_crm_id = st.selectedAccount.crm_id;
        }

        try {
            const res = await this.post('/crm/api/contact/quick-create/', body);
            if (res && res.error) { this.toast(res.error); return; }

            await this.post(`/meetme/api/meetings/${meetingId}/guests/create/`, {
                contact_crm_id: res.contact_crm_id,
                name: res.name,
                email: res.email || `noemail-${res.contact_crm_id}@platzhalter.invalid`,
                phone: res.phone || '',
            });

            this.meetmeCloseModal();
            this.toast(this.t('pbx_mm_contact_created', 'Kontakt angelegt und als Gast hinzugefügt'));
            this.meetmeSelectMeeting(meetingId);
        } catch (e) {
            this.toast(this.t('pbx_mm_contact_create_err', 'Anlegen fehlgeschlagen'));
        }
    },
});

// ============================================================
// Voicemail-Bridge (feste WebRTC-Nebenstelle 104) - Abhoeren fremder
// Mailboxen ueber Feature-Code *98<box>, unabhaengig von der eigenen
// Softphone-Registrierung des Users. Eigene, isolierte JsSIP-Instanz,
// getrennt von mod-softphone.js (das nirgends eingebunden ist).
// ============================================================
Object.assign(PBX, {
    _vmBridge: {
        ua: null, session: null, audioEl: null,
        user: '104', pass: 'abcona104', ws: 'wss://pbx.win.abcona.info:8089/ws',
        registered: false,
    },

    async dialGuestNumber(box) {
        const desk = (this.$('pbx-dial-ext') || {}).value || this.ext;
        const target = '*98' + box;
        try {
            const res = await this.post(this.api.dial, { desk, target });
            this.toast(res.success ? this.t('pbx_dialing', 'Wird angerufen') : (res.error || this.t('pbx_dial_err', 'Anruf fehlgeschlagen')));
        } catch (e) {
            this.toast(this.t('pbx_dial_err', 'Anruf fehlgeschlagen'));
        }
    },

    async vmListen(box) {
        this._vmShowModal(box);
        await this._vmEnsureRegistered();
        this._vmCall(box);
    },

    _vmEnsureRegistered() {
        return new Promise((resolve) => {
            const br = this._vmBridge;
            if (br.registered && br.ua) { resolve(); return; }

            const socket = new JsSIP.WebSocketInterface(br.ws);
            const config = {
                sockets: [socket],
                uri: `sip:${br.user}@${new URL(br.ws).hostname}`,
                password: br.pass,
                authorization_user: br.user,
                realm: 'asterisk',
                display_name: 'VM-Bridge',
                register: true,
                register_expires: 300,
                session_timers: false,
            };
            br.ua = new JsSIP.UA(config);
            br.ua.on('registered', () => { br.registered = true; this._vmSetStatus('Verbunden', true); resolve(); });
            br.ua.on('registrationFailed', (e) => {
                this._vmSetStatus('Registrierung fehlgeschlagen: ' + (e.cause || ''), false);
                resolve();
            });
            br.ua.on('newRTCSession', (e) => {
                e.session.on('sdp', (data) => {
                    data.sdp = data.sdp.replace(/a=setup:actpass/g, 'a=setup:passive');
                });
                e.session.on('confirmed', () => this._vmSetupAudio(e.session.connection));
            });
            br.ua.start();
        });
    },

    _vmCall(box) {
        const br = this._vmBridge;
        if (!br.ua || !br.ua.isRegistered()) {
            this._vmSetStatus(this.t('pbx_vm_not_registered', 'Bridge nicht registriert'), false);
            return;
        }
        const feature = '*98' + box;
        const target = `sip:${feature}@${new URL(br.ws).hostname}`;
        br.session = br.ua.call(target, {
            mediaConstraints: { audio: true, video: false },
            pcConfig: { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] },
        });
        this.$('pbx-vm-modal-route').textContent = `über ${br.user} · ${feature}`;
        this._vmStartTimer();
        br.session.on('ended', () => this._vmOnCallEnd());
        br.session.on('failed', () => this._vmOnCallEnd());
    },

    _vmSetupAudio(pc) {
        const br = this._vmBridge;
        if (br.audioEl) { try { br.audioEl.remove(); } catch (e) {} }
        br.audioEl = document.createElement('audio');
        br.audioEl.autoplay = true;
        br.audioEl.style.display = 'none';
        const volEl = this.$('pbx-vm-volume');
        br.audioEl.volume = volEl ? (parseInt(volEl.value, 10) / 100) : 1.0;
        document.body.appendChild(br.audioEl);
        pc.ontrack = (e) => {
            if (e.streams && e.streams[0]) {
                br.audioEl.srcObject = e.streams[0];
                br.audioEl.play().catch(() => {});
            }
        };
        setTimeout(() => {
            const receivers = pc.getReceivers();
            if (receivers.length && br.audioEl && !br.audioEl.srcObject) {
                br.audioEl.srcObject = new MediaStream(receivers.map(r => r.track));
                br.audioEl.play().catch(() => {});
            }
        }, 2000);
    },

    _vmShowModal(box) {
        document.querySelectorAll('#pbx-vm-modal-overlay').forEach(el => el.remove());
        const overlay = document.createElement('div');
        overlay.className = 'pbx-meetme-modal-overlay';
        overlay.id = 'pbx-vm-modal-overlay';
        overlay.innerHTML = `
            <div class="pbx-meetme-modal" style="width:300px">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
                    <h4 style="margin:0">${this.t('pbx_vm_listen_title', 'Voicemail')} ${this._meetmeEsc(box)}</h4>
                    <button class="pbx-act pbx-act-gray" onclick="PBX.vmHangup()"><i class="bi bi-x-lg"></i></button>
                </div>
                <p id="pbx-vm-modal-route" style="font-size:11.5px;color:var(--text-secondary);margin:0 0 10px">${this.t('pbx_vm_connecting', 'Verbinde…')}</p>

                <div id="pbx-vm-status-row" style="display:flex;align-items:center;gap:8px;padding:8px 10px;background:var(--abcona-gray-bg);border-radius:7px;margin-bottom:14px">
                    <span id="pbx-vm-status-dot" style="width:8px;height:8px;border-radius:50%;background:var(--status-yellow);flex-shrink:0"></span>
                    <span id="pbx-vm-status-text" style="font-size:12.5px">${this.t('pbx_vm_connecting', 'Verbinde…')}</span>
                    <span id="pbx-vm-timer" style="margin-left:auto;font-size:12px;color:var(--text-secondary)"></span>
                </div>

                <div style="display:flex;align-items:center;gap:6px;margin-bottom:10px">
                    <input id="pbx-vm-dtmf-display" type="text" readonly style="flex:1;text-align:center;font-size:15px;letter-spacing:2px;background:var(--abcona-gray-bg)">
                    <button class="pbx-act pbx-act-gray" style="padding:6px 10px" onclick="PBX.vmDtmfBackspace()" title="${this.t('pbx_vm_backspace', 'Letzte Ziffer löschen')}"><i class="bi bi-backspace"></i></button>
                    <button class="pbx-act pbx-act-gray" style="padding:6px 10px" onclick="PBX.vmDtmfClear()" title="${this.t('pbx_vm_clear', 'Anzeige löschen')}">C</button>
                </div>

                <div class="pbx-vm-dtmf-grid">
                    ${['1','2','3','4','5','6','7','8','9','*','0','#'].map(k =>
                        `<button class="pbx-act pbx-act-gray" onclick="PBX.vmDtmf('${k}')">${k}</button>`
                    ).join('')}
                </div>

                <div style="display:flex;align-items:center;gap:8px;margin-top:12px">
                    <i class="bi bi-volume-down" style="font-size:14px;color:var(--text-secondary)"></i>
                    <input id="pbx-vm-volume" type="range" min="0" max="100" value="100" style="flex:1" oninput="PBX.vmSetVolume(this.value)">
                    <i class="bi bi-volume-up" style="font-size:14px;color:var(--text-secondary)"></i>
                </div>

                <div style="display:flex;gap:8px;margin-top:10px">
                    <button class="pbx-act pbx-act-gray" style="flex:1" onclick="PBX.vmToggleMute()"><i class="bi bi-mic-mute"></i> ${this.t('pbx_vm_mute', 'Stumm')}</button>
                    <button class="pbx-act pbx-act-red" style="flex:1" onclick="PBX.vmHangup()"><i class="bi bi-telephone-x"></i> ${this.t('pbx_vm_hangup', 'Auflegen')}</button>
                </div>

                <p style="font-size:10px;color:var(--text-muted);margin:10px 0 0;text-align:center">1 Wiedergabe · 3 Löschen · 7 Zurück · 9 Weiter</p>
            </div>
        `;
        this._meetmeMountModal(overlay);
    },

    _vmSetStatus(text, ok) {
        const dot = this.$('pbx-vm-status-dot');
        const txt = this.$('pbx-vm-status-text');
        if (dot) dot.style.background = ok ? 'var(--status-green)' : 'var(--status-red)';
        if (txt) txt.textContent = text;
    },

    _vmStartTimer() {
        this._vmSetStatus(this.t('pbx_vm_connected', 'Verbunden'), true);
        let sec = 0;
        this._vmTimerInt = setInterval(() => {
            sec += 1;
            const el = this.$('pbx-vm-timer');
            if (el) el.textContent = String(Math.floor(sec / 60)).padStart(2, '0') + ':' + String(sec % 60).padStart(2, '0');
        }, 1000);
    },

    _vmOnCallEnd() {
        clearInterval(this._vmTimerInt);
        this._vmSetStatus(this.t('pbx_vm_ended', 'Beendet'), false);
    },

    vmDtmf(key) {
        const br = this._vmBridge;
        if (br.session && br.session.isEstablished && br.session.isEstablished()) {
            try { br.session.sendDTMF(key); } catch (e) {}
        }
        const disp = this.$('pbx-vm-dtmf-display');
        if (disp) disp.value += key;
    },

    vmDtmfBackspace() {
        const disp = this.$('pbx-vm-dtmf-display');
        if (disp) disp.value = disp.value.slice(0, -1);
    },

    vmDtmfClear() {
        const disp = this.$('pbx-vm-dtmf-display');
        if (disp) disp.value = '';
    },

    vmSetVolume(val) {
        const br = this._vmBridge;
        if (br.audioEl) br.audioEl.volume = Math.max(0, Math.min(100, parseInt(val, 10))) / 100;
    },

    vmToggleMute() {
        // Stummt die WIEDERGABE (was du hoerst), nicht das eigene Mikrofon -
        // beim Voicemail-Abhoeren spricht man ja nicht rein, session.mute()
        // haette daher keinen hoerbaren Effekt fuer den Nutzer selbst.
        const br = this._vmBridge;
        if (!br.audioEl) return;
        br.audioEl.muted = !br.audioEl.muted;
        const btn = document.querySelector('#pbx-vm-modal-overlay [onclick="PBX.vmToggleMute()"]');
        if (btn) {
            btn.innerHTML = br.audioEl.muted
                ? '<i class="bi bi-volume-mute-fill"></i> ' + this.t('pbx_vm_unmute', 'Ton an')
                : '<i class="bi bi-mic-mute"></i> ' + this.t('pbx_vm_mute', 'Stumm');
        }
    },

    vmHangup() {
        const br = this._vmBridge;
        if (br.session) { try { br.session.terminate(); } catch (e) {} }
        clearInterval(this._vmTimerInt);
        document.querySelectorAll('#pbx-vm-modal-overlay').forEach(el => el.remove());
    },
});
Object.assign(PBX, {
    refreshI18n() {
        if (!document.getElementById('pbx-root')) return;
        if (typeof window.applyTranslations === 'function') window.applyTranslations();
        if (typeof this.renderHud === 'function') this.renderHud();
        if (typeof this.renderPark === 'function') this.renderPark();
        if (typeof this.renderKonf === 'function') this.renderKonf();
        if (typeof this.renderQueues === 'function') this.renderQueues();
        if (typeof this.updateCount === 'function') this.updateCount();
        if (this.$('pbx-meetme-strip') && typeof this.meetmeRenderStrip === 'function') {
            this.meetmeRenderStrip();
            const id = this._meetmeState && this._meetmeState.selectedId;
            const cached = id && this._meetmeState.detailCache && this._meetmeState.detailCache[id];
            if (cached && typeof this.meetmeRenderDetail === 'function') {
                this.meetmeRenderDetail(cached);
            } else {
                const detail = this.$('pbx-meetme-detail');
                if (detail && !id) {
                    detail.innerHTML = '<div class="pbx-hint">' + this.t('pbx_meetme_select_hint', 'Termin auswählen oder neuen Termin anlegen') + '</div>';
                }
            }
        }
        const tab = this.tab;
        if (tab === 'cdr' && typeof this.loadCdr === 'function') this.loadCdr();
        else if (tab === 'stats' && typeof this.loadStats === 'function') this.loadStats();
        else if (tab === 'vm' && typeof this.loadVm === 'function') this.loadVm();
        else if (tab === 'wavnotes' && typeof this.loadWavNotes === 'function') this.loadWavNotes();
    },
});

function _pbxOnLanguageUpdate() {
    if (document.getElementById('pbx-root') && typeof PBX !== 'undefined' && typeof PBX.refreshI18n === 'function') {
        PBX.refreshI18n();
    }
}

document.addEventListener('languageChanged', _pbxOnLanguageUpdate);
document.addEventListener('languageSelectorReady', _pbxOnLanguageUpdate);

window.PBX = PBX;
