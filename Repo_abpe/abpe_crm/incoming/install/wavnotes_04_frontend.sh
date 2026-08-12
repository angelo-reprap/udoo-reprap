#!/bin/bash
# ============================================================
# wavnotes_04_frontend.sh
# WAV-Notizen — Etappe 4: Frontend (mod-crm-pbx.js + CSS)
# Template braucht KEINEN Patch — Panel/Grid-Div existiert schon
# (Platzhalter aus vorheriger Session).
# ============================================================
set -e
cd /opt/abpe/backend

JS="apps/abpe_crm/static/abpe_crm/js/mod-crm-pbx.js"
CSS="apps/abpe_crm/static/abpe_crm/css/mod-crm-pbx.css"

echo "=== [1/6] Backups ==="
python3 Archiv/backup_restore.py -save "$JS" -m "wavnotes_04: vor wavnotes JS"
python3 Archiv/backup_restore.py -save "$CSS" -m "wavnotes_04: vor wavnotes CSS"

echo "=== [2/6] api-Objekt erweitern ==="
python3 - << 'PYEOF'
p = 'apps/abpe_crm/static/abpe_crm/js/mod-crm-pbx.js'
s = open(p, encoding='utf-8').read()
if 'wavnotes:' in s:
    print("  api.wavnotes existiert schon — uebersprungen.")
else:
    OLD = "        notiz:      '/crm/api/telefon/notiz/',\n"
    NEW = OLD + \
        "        wavnotes:          '/crm/api/telefon/wavnotes/',\n" \
        "        wavnoteAudio:      '/crm/api/telefon/wavnotes/audio/',\n" \
        "        wavnoteTranscribe: '/crm/api/telefon/wavnotes/transcribe/',\n" \
        "        wavnoteSave:       '/crm/api/telefon/wavnotes/save/',\n"
    assert s.count(OLD) == 1, f"api-Anker {s.count(OLD)}x gefunden statt 1"
    s = s.replace(OLD, NEW)
    open(p, 'w', encoding='utf-8').write(s)
    print("  api.wavnotes* eingetragen.")
PYEOF

echo "=== [3/6] showTab() erweitern ==="
python3 - << 'PYEOF'
p = 'apps/abpe_crm/static/abpe_crm/js/mod-crm-pbx.js'
s = open(p, encoding='utf-8').read()
if "this.loadWavNotes()" in s:
    print("  showTab-Hook existiert schon — uebersprungen.")
else:
    OLD = '''        if (tab === 'vm') this.loadVm();
    },'''
    NEW = '''        if (tab === 'vm') this.loadVm();
        if (tab === 'wavnotes') this.loadWavNotes();
    },'''
    assert s.count(OLD) == 1, f"showTab-Anker {s.count(OLD)}x gefunden statt 1"
    s = s.replace(OLD, NEW)
    open(p, 'w', encoding='utf-8').write(s)
    print("  showTab() Hook eingetragen.")
PYEOF

echo "=== [4/6] loadWavNotes()/_wavnoteCard()/Modal-Funktionen anhaengen (nach _vmCard) ==="
python3 - << 'PYEOF'
p = 'apps/abpe_crm/static/abpe_crm/js/mod-crm-pbx.js'
s = open(p, encoding='utf-8').read()
if 'loadWavNotes(' in s:
    print("  loadWavNotes existiert schon — uebersprungen.")
else:
    OLD = '''                <button class="pbx-act pbx-act-green" style="padding:6px 10px" onclick="PBX.dialGuestNumber('${b.box}')" title="${this.t('pbx_dial', 'Anrufen')}">
                    <i class="bi bi-telephone-outbound"></i>
                </button>
            </div>
        </div>`;
    },'''
    NEW = OLD + '''

    async loadWavNotes() {
        const grid = this.$('pbx-wavnotesgrid');
        if (!grid) return;
        grid.innerHTML = '<div class="pbx-empty">' + this.t('pbx_loading', 'Lade\u2026') + '</div>';
        try {
            const res = await this.get(this.api.wavnotes);
            const list = res.data || [];
            grid.innerHTML = list.length ? list.map(n => this._wavnoteCard(n)).join('')
                : '<div class="pbx-empty">' + this.t('pbx_no_wavnotes', 'Keine Voicemail-Nachrichten') + '</div>';
        } catch (e) {
            grid.innerHTML = '<div class="pbx-empty">' + this.t('pbx_load_error', 'Fehler beim Laden') + '</div>';
        }
    },

    _fmtDur(sec) {
        const m = Math.floor(sec / 60), s = sec % 60;
        return `${m}:${String(s).padStart(2, '0')}`;
    },

    _wavnoteCard(n) {
        const isNew = n.folder === 'INBOX';
        const badge = isNew
            ? `<span class="pbx-badge pbx-badge-new">${this.t('pbx_new', 'Neu')}</span>`
            : `<span class="pbx-badge pbx-badge-archived">${this.t('pbx_archived', 'Archiviert')}</span>`;
        const docBadge = n.has_note
            ? `<span class="pbx-badge pbx-badge-doc"><i class="bi bi-check-lg"></i> ${this.t('pbx_documented', 'Dokumentiert')}</span>`
            : '';
        const dur = n.duration ? this._fmtDur(n.duration) : '--:--';
        const dt = n.origtime ? new Date(n.origtime).toLocaleString() : '';
        const audioSrc = `${this.api.wavnoteAudio}?mailbox=${encodeURIComponent(n.mailbox)}&folder=${encodeURIComponent(n.folder)}&msg_id=${encodeURIComponent(n.msg_id)}`;
        const dataAttr = this.esc(JSON.stringify(n)).replace(/"/g, '&quot;');
        return `<div class="pbx-wavcard">
            <div class="pbx-wav-top">
                <b>${this.esc(n.callerid || this.t('pbx_unknown_number', 'Unbekannte Nummer'))}</b>
                ${badge}${docBadge}
            </div>
            <div class="pbx-wav-meta">${this.t('pbx_box', 'Box')} ${this.esc(n.mailbox)} \u00b7 ${this.esc(dt)} \u00b7 ${dur}</div>
            <audio class="pbx-wav-audio" controls preload="none" src="${audioSrc}"></audio>
            <div class="pbx-wav-actions">
                <button class="pbx-act pbx-act-blue" data-wavnote="${dataAttr}" onclick="PBX.wavnoteOpenModal(JSON.parse(this.dataset.wavnote))">
                    <i class="bi bi-journal-text"></i> ${this.t('pbx_wavnote_create', 'Notiz erstellen')}
                </button>
            </div>
        </div>`;
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
        document.body.appendChild(overlay);
        this.wavnoteTranscribe();
        this._wavnoteRenderContactBox();
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
        // TODO: bestehendes "+Neuer Kontakt"-Modal (Konferenz/Meetme-Modul)
        // hier einhaengen, sobald der genaue Funktionsname bestaetigt ist.
        // Telefonnummer zum Vorausfuellen: this._wavCurrent.callerid
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
            const res = await this.get(`${this.api.contacts}?q=${encodeURIComponent(q)}`);
            const list = (res.results || res.contacts || []).slice(0, 8);
            results.innerHTML = list.map(c => `<div class="pbx-wav-contact-hit" onclick='PBX._wavnotePickContact(${JSON.stringify(c)})'>${this.esc(c.name || c.full_name || '')}</div>`).join('');
        } catch (e) { /* still */ }
    },

    _wavnotePickContact(c) {
        this._wavContact = { crm_id: c.crm_id, module: c.module || 'Contacts', name: c.name || c.full_name };
        this._wavnoteRenderContactBox();
    },

    wavnoteNewContact() {
        alert('TODO: Neuer-Kontakt-Modal verkabeln (Telefonnummer: ' + (this._wavCurrent && this._wavCurrent.callerid || '') + ')');
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
    },'''
    assert s.count(OLD) == 1, f"_vmCard-Anker {s.count(OLD)}x gefunden statt 1"
    s = s.replace(OLD, NEW)
    open(p, 'w', encoding='utf-8').write(s)
    print("  loadWavNotes/_wavnoteCard/Modal-Funktionen angehaengt.")
PYEOF

echo "=== [5/6] node --check ==="
node --check "$JS" && echo "  mod-crm-pbx.js Syntax OK"

echo "=== [6/6] CSS anhaengen (idempotent) + collectstatic + restart ==="
python3 - << 'PYEOF'
p = 'apps/abpe_crm/static/abpe_crm/css/mod-crm-pbx.css'
s = open(p, encoding='utf-8').read()
if 'pbx-wavcard' in s:
    print("  CSS existiert schon — uebersprungen.")
else:
    css = '''

/* ---- WAV-Notizen ---- */
.pbx-grid-wavnotes { grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); }
.pbx-wavcard { border: 1.5px solid var(--border-color); border-radius: var(--border-radius-card, 12px); padding: 12px; background: var(--bg-white); }
.pbx-wav-top { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 4px; }
.pbx-wav-meta { font-size: 11px; color: var(--text-muted); margin-bottom: 8px; }
.pbx-wav-audio { width: 100%; margin-bottom: 8px; }
.pbx-wav-actions { display: flex; gap: 6px; }
.pbx-badge { font-size: 10px; padding: 2px 8px; border-radius: 10px; font-weight: 600; }
.pbx-badge-new { background: var(--status-yellow-bg); color: var(--status-yellow-text); }
.pbx-badge-archived { background: var(--abcona-gray-bg); color: var(--text-secondary); }
.pbx-badge-doc { background: var(--status-green-bg); color: var(--status-green-text); }

.pbx-modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.45); display: flex; align-items: center; justify-content: center; z-index: 2000; }
.pbx-modal { background: var(--bg-white); border-radius: var(--border-radius-card, 12px); padding: 18px; width: 460px; max-width: 92vw; max-height: 88vh; overflow-y: auto; }
.pbx-modal-hdr { display: flex; align-items: center; gap: 8px; font-weight: 600; color: var(--abcona-blue); margin-bottom: 14px; }
.pbx-modal-close { margin-left: auto; border: none; background: transparent; cursor: pointer; color: var(--text-secondary); }
.pbx-modal-lbl { font-size: 11px; color: var(--text-secondary); margin: 10px 0 4px; }
.pbx-modal-raw, .pbx-modal-polished { width: 100%; min-height: 70px; box-sizing: border-box; border: 1px solid var(--border-color); border-radius: 7px; padding: 8px 10px; font-size: 13px; font-family: inherit; }
.pbx-modal-raw { background: var(--abcona-gray-bg); color: var(--text-secondary); }
.pbx-modal-ftr { display: flex; gap: 8px; justify-content: flex-end; margin-top: 14px; }
.pbx-wav-contact { margin-top: 12px; }
.pbx-wav-contact-match, .pbx-wav-contact-unknown { font-size: 12px; padding: 8px 10px; border-radius: 8px; background: var(--abcona-gray-bg); display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.pbx-wav-contact-unknown { flex-direction: column; align-items: stretch; }
#pbx-wav-contact-search { width: 100%; box-sizing: border-box; padding: 6px 8px; border: 1px solid var(--border-color); border-radius: 7px; font-size: 12px; }
.pbx-wav-contact-hit { padding: 4px 6px; cursor: pointer; font-size: 12px; }
.pbx-wav-contact-hit:hover { background: var(--abcona-blue-alpha); }
'''
    s = s.rstrip() + '\n' + css + '\n'
    open(p, 'w', encoding='utf-8').write(s)
    print("  CSS angehaengt.")
PYEOF

python manage.py collectstatic --noinput 2>&1 | tail -3
supervisorctl restart abpe-django
python manage.py check 2>&1 | tail -3

echo ""
echo "============================================================"
echo "✅ wavnotes_04 fertig (Frontend) — WAV-Notizen ist live."
echo "Test: /crm/telefon/ -> Tab WAV-Notizen"
echo "============================================================"
