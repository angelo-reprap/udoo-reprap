/**
 * es-studio.js — ABpE Email Studio WYSIWYG Editor
 * Nutzt: ES.api, ES.notify, ES.confirm, ES.csrf aus es-core.js
 *        loadLanguage, window.i18nData aus core-language.js
 * Kein hardcoded Text — alle Labels aus window.i18nData?.es.*
 */
'use strict';

window.ESStudio = (() => {

    let _templateId   = null;
    let _previewTimer = null;
    let _currentEntity = 'template'; // template | module | signature
    let _currentMode  = 'visual';  // visual | html-editor | code | txt
    let _entityCache  = {
        template:  null,
        module:    { id: null, html: '', text: '', identifier: '', name: '' },
        signature: { id: null, html: '', text: '', identifier: '', name: '' },
    };
    let _undoStack    = [];
    let _redoStack    = [];
    let _undoTimer    = null;
    const UNDO_MAX    = 20;
    const MILESTONE_MAX = 10;

    const DUMMY_VARS = {
        name:           'Max Mustermann',
        first_name:     'Max',
        last_name:      'Mustermann',
        vorname:        'Max',
        nachname:       'Mustermann',
        email:          'max@example.de',
        firma:          'Muster GmbH',
        unternehmen:    'Muster GmbH',
        termin_datum:   '15.07.2026',
        termin_zeit:    '14:00 Uhr',
        termin_uhrzeit: '14:00 Uhr',
        raum:           'Meetingraum 3',
        einwahl_info:   'Einwahl: +49 30 123456, PIN 4711',
        teilnehmer_liste_html: '<ul><li>Max Mustermann</li><li>Erika Musterfrau</li></ul>',
        teilnehmer_liste: 'Max Mustermann, Erika Musterfrau',
        vertretung_name: 'Erika Musterfrau',
        vertretung_email: 'erika.musterfrau@abcona.de',
        vertretung_telefon: '+49 171 1234567',
        mobil_nummer: '+49 171 9876543',
        abwesenheit_von: '15.07.2026',
        abwesenheit_bis: '20.07.2026',
        sender_name: 'Max Mustermann',
        sender_email: 'max@example.de',
        strasse:        'Musterstraße 1',
        plz:            '12345',
        ort:            'Musterstadt',
        telefon:        '+49 123 456789',
        link:           'https://abpe.win.abcona.info',
        button_url:     'https://abpe.win.abcona.info',
        button_text:    'Zum Portal',
        cv_link:        'https://abpe.win.abcona.info/cv/beispiel',
        cv_version:     'v3',
        created_date:   '15.07.2026',
        task_ref:       'TASK-4711',
        signature:      'Mit freundlichen Grüßen\nMax Mustermann\nmax@example.de',
        signature_name: 'Max Mustermann',
        berater_name:   'Tanja Groß',
        kandidat_name:  'Max Mustermann',
    };

    /* ── t() Hilfsfunktion ── */
    function t(key, fallback) {
        return window.i18nData?.es?.[key] || fallback || key;
    }

    /* ══════════════════════════════════════════════════════
     * INIT
     * ══════════════════════════════════════════════════════ */
    function init() {
        _templateId = window.ES_CONFIG?.templateId || null;

        _initEditorTabs();
        _initEntityTabs();
        _initEntitySelectors();
        _initEntityActions();
        _initRichEditor();
        _initSectionHints();
        _initVarChips();
        _initModuleChips();
        _initScopeVariableReload();
        _initSave();
        _initTestSend();
        _initVersionsBar();
        _initUndoRedo();
        _initMilestone();
        _initSignaturePanel();
        _initRestorePopup();
        _initPreviewRefresh();
        _initMcidValidate();

        if (_currentMode === 'visual') {
            _initWysiwyg();
        }

        _updateModePanels();
        _updateSaveButtonLabel();

        ['es-html-editor', 'es-txt-editor'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.addEventListener('input', () => {
                    _schedulePreview();
                    if (_currentMode === 'visual' && _currentEntity !== 'template') {
                        _updateEntityVisual();
                    }
                });
            }
        });

        if (_templateId) {
            setTimeout(() => _loadPreview(false), 200);
            _loadVersionsBar();
        }

        const subjectInput = document.getElementById('es-subject-input');
        if (subjectInput) subjectInput.addEventListener('input', _schedulePreview);

        const editLang = window.ES_CONFIG?.editLang;
        if (editLang) {
            _markTranslationMode(editLang);
        }

        document.addEventListener('languageChanged', () => {
            _onLanguageChanged();
        });

        _applyPendingWizardResult();

        /* Nach erstem loadLanguage Module-Labels neu setzen (Race mit DOMContentLoaded) */
        _waitForI18nThenRefresh();

        console.log('ES Studio initialisiert, Template:', _templateId);
    }

    let _langRefreshTimer = null;
    function _onLanguageChanged() {
        clearTimeout(_langRefreshTimer);
        _langRefreshTimer = setTimeout(() => {
            _applyI18nToCanvas();
            _loadModules(true);
            const mode = document.querySelector('input[name="es-sig-mode"]:checked')?.value || 'USER';
            _updateSigBlock(mode);
            _initSectionHints();
            /* Dynamische Var-Gruppen neu laden (Sektor-Labels via t()) */
            if (document.getElementById('es-vars-panel-body')) {
                _reloadVariablesPanel();
            }
        }, 50);
    }

    function _waitForI18nThenRefresh() {
        let n = 0;
        const tick = () => {
            n += 1;
            if (window.i18nData?.es?.modules_title || window.i18nData?.es?.signature_title) {
                _onLanguageChanged();
                return true;
            }
            return false;
        };
        if (tick()) return;
        const iv = setInterval(() => {
            if (tick() || n > 40) clearInterval(iv);
        }, 100);
    }

    function _setSenderModeBtn(mode) {
        document.querySelectorAll('.es-mode-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.mode === mode);
        });
        const hint = document.getElementById('es-mode-hint');
        if (hint) {
            const hints = {
                USER: t('mode_hint_user', 'From = eingeloggter User'),
                AUTO: t('mode_hint_auto', 'From = noreply'),
                TEMPLATE: t('mode_hint_template', 'From = feste Adresse'),
            };
            hint.textContent = hints[mode] || '';
        }
    }

    function _setSignatureMode(mode) {
        document.querySelectorAll('input[name="es-sig-mode"]').forEach(radio => {
            const active = radio.value === mode;
            radio.checked = active;
            radio.closest('.es-sig-option')?.classList.toggle('active', active);
        });
        const preview = document.getElementById('es-sig-preview');
        if (preview) preview.style.display = mode === 'NONE' ? 'none' : '';
        _updateSigBlock(mode);
        _updateSignatureBlockState();
    }

    function applyWizardResult(fields) {
        if (!fields) return;
        const setVal = (id, v) => {
            const el = document.getElementById(id);
            if (el && v != null && v !== '') el.value = v;
        };
        setVal('es-name-input', fields.name);
        setVal('es-subject-input', fields.subject);
        setVal('es-identifier-input', fields.identifier);
        // HTML/TXT auch bei Leerstring setzen, wenn Key vorhanden
        if (Object.prototype.hasOwnProperty.call(fields, 'html_body')) {
            const htmlEl = document.getElementById('es-html-editor');
            if (htmlEl) htmlEl.value = fields.html_body || '';
        } else {
            setVal('es-html-editor', fields.html_body);
        }
        if (Object.prototype.hasOwnProperty.call(fields, 'text_body')) {
            const txtEl = document.getElementById('es-txt-editor');
            if (txtEl) txtEl.value = fields.text_body || '';
        } else {
            setVal('es-txt-editor', fields.text_body);
        }

        const scopeSel = document.querySelector('select[name="app_scope"]');
        if (scopeSel && fields.app_scope) scopeSel.value = fields.app_scope;

        const statusSel = document.querySelector('select[name="status"]');
        if (statusSel && fields.status) statusSel.value = fields.status;

        if (fields.sender_mode) _setSenderModeBtn(fields.sender_mode);
        if (fields.signature_mode) _setSignatureMode(fields.signature_mode);

        _syncCodeToCanvas();
        // Visuell-Tab: Canvas ist führend — sicherstellen dass Code→Canvas greift
        if (_currentMode === 'visual' || _currentMode === 'html-editor') {
            _syncCodeToCanvas();
        }
        _schedulePreview();
        ES.notify.success('es.ki_applied', t('ki_applied', 'KI-Vorlage übernommen'));
    }

    function _applyPendingWizardResult() {
        const key = window.ESKiWizard?.STORAGE_KEY || 'es_ki_wizard_apply';
        const raw = sessionStorage.getItem(key);
        if (!raw) return;
        sessionStorage.removeItem(key);
        try {
            applyWizardResult(JSON.parse(raw));
        } catch (e) {
            console.error('KI wizard apply failed', e);
        }
    }

    /* ══════════════════════════════════════════════════════
     * ENTITY TABS (Vorlage / Modul / Signatur)
     * ══════════════════════════════════════════════════════ */
    function _initEntityTabs() {
        document.querySelectorAll('.es-entity-tab').forEach(tab => {
            tab.addEventListener('click', function() {
                const entity = this.dataset.entity;
                if (!entity || entity === _currentEntity) return;
                _switchEntity(entity);
            });
        });
    }

    function _persistEntityEditors() {
        _syncAllToCode();
        const html = document.getElementById('es-html-editor')?.value || '';
        const txt  = document.getElementById('es-txt-editor')?.value   || '';
        if (_currentEntity === 'template') {
            _entityCache.template = { html, text: txt };
        } else if (_currentEntity === 'module') {
            Object.assign(_entityCache.module, { html, text: txt });
        } else if (_currentEntity === 'signature') {
            Object.assign(_entityCache.signature, { html, text: txt });
        }
    }

    function _switchEntity(entity) {
        _persistEntityEditors();
        _currentEntity = entity;

        document.querySelectorAll('.es-entity-tab').forEach(t => {
            t.classList.toggle('active', t.dataset.entity === entity);
        });

        const ctx = document.getElementById('es-entity-context');
        const modCtx = document.getElementById('es-entity-module-ctx');
        const sigCtx = document.getElementById('es-entity-signature-ctx');
        if (ctx) ctx.style.display = entity === 'template' ? 'none' : '';
        if (modCtx) modCtx.style.display = entity === 'module' ? '' : 'none';
        if (sigCtx) sigCtx.style.display = entity === 'signature' ? '' : 'none';

        if (entity === 'template') {
            const c = _entityCache.template;
            if (c) {
                const htmlEl = document.getElementById('es-html-editor');
                const txtEl  = document.getElementById('es-txt-editor');
                if (htmlEl) htmlEl.value = c.html;
                if (txtEl)  txtEl.value  = c.text;
            }
        } else if (entity === 'module') {
            const c = _entityCache.module;
            if (c.id) {
                _applyEntityToEditors(c);
                const badge = document.getElementById('es-entity-module-id');
                if (badge) badge.textContent = c.identifier || '';
                const sel = document.getElementById('es-entity-module-select');
                if (sel && c.id) sel.value = String(c.id);
            } else {
                _clearEditors();
            }
        } else if (entity === 'signature') {
            const c = _entityCache.signature;
            if (c.id) {
                _applyEntityToEditors(c);
                const badge = document.getElementById('es-entity-signature-id');
                if (badge) badge.textContent = c.identifier || '';
                const sel = document.getElementById('es-entity-signature-select');
                if (sel && c.id) sel.value = String(c.id);
            } else {
                _clearEditors();
            }
        }

        _updateModePanels();
        _updateSaveButtonLabel();
        setTimeout(_loadPreview, 100);
    }

    function _updateSaveButtonLabel() {
        const lbl = document.querySelector('#es-save-btn span');
        if (!lbl) return;
        const keys = {
            template:  ['btn_save', 'Speichern'],
            module:    ['btn_save_module', 'Modul speichern'],
            signature: ['btn_save_signature', 'Signatur speichern'],
        };
        const [key, fb] = keys[_currentEntity] || keys.template;
        lbl.textContent = t(key, fb);
    }

    function _applyEntityToEditors(data) {
        const htmlEl = document.getElementById('es-html-editor');
        const txtEl  = document.getElementById('es-txt-editor');
        if (htmlEl) htmlEl.value = data.html || data.html_body || '';
        if (txtEl)  txtEl.value  = data.text || data.text_body || '';
    }

    function _clearEditors() {
        const htmlEl = document.getElementById('es-html-editor');
        const txtEl  = document.getElementById('es-txt-editor');
        if (htmlEl) htmlEl.value = '';
        if (txtEl)  txtEl.value  = '';
    }

    async function _initEntitySelectors() {
        const modSel = document.getElementById('es-entity-module-select');
        const sigSel = document.getElementById('es-entity-signature-select');

        modSel?.addEventListener('change', async function() {
            const id = parseInt(this.value, 10);
            if (!id) return;
            await _loadModuleEntity(id);
        });

        sigSel?.addEventListener('change', async function() {
            const id = parseInt(this.value, 10);
            if (!id) return;
            await _loadSignatureEntity(id);
        });

        if (!modSel) return;
        await _refreshModuleSelect();
    }

    async function _loadModuleEntity(id) {
        try {
            const data = await ES.api.get(ES.apiUrl(`modules/${id}/`));
            _entityCache.module = {
                id, html: data.html_body, text: data.text_body,
                identifier: data.identifier, name: data.name,
            };
            _applyEntityToEditors(_entityCache.module);
            const badge = document.getElementById('es-entity-module-id');
            if (badge) badge.textContent = data.identifier;
            if (_currentEntity === 'module') {
                _updateModePanels();
                _loadPreview(false);
            }
        } catch (e) {
            console.error('Modul laden fehlgeschlagen:', e);
            ES.notify.error('es.error_load_module', 'Modul konnte nicht geladen werden');
        }
    }

    async function _refreshModuleSelect(selectedId) {
        const modSel = document.getElementById('es-entity-module-select');
        if (!modSel) return;
        try {
            const data = await ES.api.get(ES.apiUrl('modules/'));
            const grouped = data.modules || {};
            let opts = `<option value="">${t('entity_select_placeholder', '— Bitte wählen —')}</option>`;
            for (const modules of Object.values(grouped)) {
                for (const m of modules) {
                    if (!m.id || m.is_virtual) continue;
                    const sel = selectedId && String(m.id) === String(selectedId) ? ' selected' : '';
                    opts += `<option value="${m.id}"${sel}>${m.name} (${m.identifier})</option>`;
                }
            }
            modSel.innerHTML = opts;
        } catch (e) {
            console.error('Modul-Liste aktualisieren fehlgeschlagen:', e);
        }
    }

    function _initEntityActions() {
        document.getElementById('es-entity-module-new')?.addEventListener('click', _createNewModule);
    }

    async function _createNewModule() {
        const name = prompt(t('module_new_name', 'Anzeigename des neuen Moduls:'), '');
        if (!name) return;
        const identifier = prompt(
            t('module_new_identifier', 'Technischer Name (Identifier):'),
            name.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')
        );
        if (!identifier) return;

        _syncAllToCode();
        const html = document.getElementById('es-html-editor')?.value || '';
        const txt  = document.getElementById('es-txt-editor')?.value  || '';

        try {
            const r = await fetch(ES.apiUrl('modules/'), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': ES.csrf(),
                },
                body: JSON.stringify({
                    name, identifier,
                    html_body: html,
                    text_body: txt,
                    module_type: 'SECTION',
                }),
            });
            const data = await r.json().catch(() => ({}));
            if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);

            _entityCache.module = {
                id: data.id, html, text: txt,
                identifier: data.identifier, name: data.name,
            };
            await _refreshModuleSelect(data.id);
            const badge = document.getElementById('es-entity-module-id');
            if (badge) badge.textContent = data.identifier;
            ES.notify.success('es.module_saved', t('module_saved', 'Modul angelegt'));
            _loadModules(true);
        } catch (e) {
            console.error('Modul anlegen fehlgeschlagen:', e);
            ES.notify.error('es.error_save', e.message || t('error_save', 'Fehler'));
        }
    }

    async function _loadSignatureEntity(id) {
        try {
            const data = await ES.api.get(ES.apiUrl(`signatures/${id}/`));
            _entityCache.signature = {
                id, html: data.html_body, text: data.text_body,
                identifier: data.identifier, name: data.name,
            };
            _applyEntityToEditors(_entityCache.signature);
            const badge = document.getElementById('es-entity-signature-id');
            if (badge) badge.textContent = data.identifier;
            if (_currentEntity === 'signature') {
                _updateModePanels();
                _loadPreview(false);
            }
        } catch (e) {
            console.error('Signatur laden fehlgeschlagen:', e);
            ES.notify.error('es.error_load_sig', 'Signatur konnte nicht geladen werden');
        }
    }

    async function _saveModuleEntity() {
        _syncAllToCode();
        const id = _entityCache.module.id;
        if (!id) {
            ES.notify.error('es.entity_select_module', t('entity_select_module', 'Bitte zuerst ein Modul wählen'));
            return;
        }
        const payload = {
            html_body: document.getElementById('es-html-editor')?.value || '',
            text_body: document.getElementById('es-txt-editor')?.value  || '',
        };
        try {
            const r = await fetch(ES.apiUrl(`modules/${id}/`), {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': ES.csrf(),
                },
                body: JSON.stringify(payload),
            });
            const data = await r.json().catch(() => ({}));
            if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
            Object.assign(_entityCache.module, { html: payload.html_body, text: payload.text_body });
            ES.notify.success('es.module_saved', t('module_saved', 'Modul gespeichert'));
            _loadModules(true);
        } catch (e) {
            console.error('Modul speichern fehlgeschlagen:', e);
            ES.notify.error('es.error_save', e.message || t('error_save', 'Fehler'));
        }
    }

    async function _saveSignatureEntity() {
        _syncAllToCode();
        const id = _entityCache.signature.id;
        if (!id) {
            ES.notify.error('es.entity_select_signature', t('entity_select_signature', 'Bitte zuerst eine Signatur wählen'));
            return;
        }
        const payload = {
            html_body: document.getElementById('es-html-editor')?.value || '',
            text_body: document.getElementById('es-txt-editor')?.value  || '',
        };
        try {
            const r = await fetch(ES.apiUrl(`signatures/${id}/`), {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': ES.csrf(),
                },
                body: JSON.stringify(payload),
            });
            const data = await r.json().catch(() => ({}));
            if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
            Object.assign(_entityCache.signature, { html: payload.html_body, text: payload.text_body });
            ES.notify.success('es.sig_saved', t('sig_saved', 'Signatur gespeichert'));
        } catch (e) {
            console.error('Signatur speichern fehlgeschlagen:', e);
            ES.notify.error('es.error_save', e.message || t('error_save', 'Fehler'));
        }
    }

    /* ══════════════════════════════════════════════════════
     * EDITOR TABS (Visual / HTML-Editor / HTML-Code / TXT)
     * ══════════════════════════════════════════════════════ */
    function _initEditorTabs() {
        document.querySelectorAll('.es-editor-tab').forEach(tab => {
            tab.addEventListener('click', function() {
                const mode = this.dataset.mode;
                if (!mode || mode === _currentMode) return;
                _switchMode(mode);
            });
        });
    }

    function _syncAllToCode() {
        if (_currentMode === 'visual' && _currentEntity === 'template') {
            _syncCanvasToCode();
        }
        if (_currentMode === 'html-editor') {
            _syncRichToCode();
        }
    }

    function _switchMode(mode) {
        const prev = _currentMode;

        if (prev === 'visual' && _currentEntity === 'template') {
            _syncCanvasToCode();
        } else if (prev === 'html-editor') {
            _syncRichToCode();
        }

        _currentMode = mode;

        document.querySelectorAll('.es-editor-tab').forEach(t => {
            t.classList.toggle('active', t.dataset.mode === mode);
        });

        if (mode === 'visual' && _currentEntity === 'template' && prev !== 'visual') {
            _syncCodeToCanvas();
        } else if (mode === 'html-editor') {
            _syncCodeToRich();
        }

        _updateModePanels();

        if (mode !== 'txt') {
            setTimeout(_loadPreview, 100);
        }
    }

    function _updateModePanels() {
        const mode   = _currentMode;
        const entity = _currentEntity;

        const visualWrap     = document.getElementById('es-wysiwyg-wrap');
        const entityVisual   = document.getElementById('es-entity-visual-wrap');
        const htmlEditorWrap = document.getElementById('es-html-editor-wrap');
        const codeWrap       = document.getElementById('es-code-wrap');
        const txtWrap        = document.getElementById('es-txt-wrap');

        if (visualWrap)     visualWrap.style.display     = (mode === 'visual' && entity === 'template') ? '' : 'none';
        if (entityVisual)   entityVisual.style.display   = (mode === 'visual' && entity !== 'template') ? '' : 'none';
        if (htmlEditorWrap) htmlEditorWrap.style.display   = mode === 'html-editor' ? '' : 'none';
        if (codeWrap)       codeWrap.style.display         = mode === 'code' ? '' : 'none';
        if (txtWrap)        txtWrap.style.display          = mode === 'txt' ? '' : 'none';

        if (mode === 'visual' && entity !== 'template') {
            _updateEntityVisual();
        }
    }

    function _updateEntityVisual() {
        const body = document.getElementById('es-entity-visual-body');
        if (!body) return;
        _syncAllToCode();
        const html = document.getElementById('es-html-editor')?.value || '';
        body.innerHTML = html ? _applyDummyVarsLocal(html) : `<p style="color:#999;padding:20px;">${t('entity_visual_empty', 'Kein Inhalt — HTML-Code oder HTML-Editor verwenden')}</p>`;
    }

    function _syncCodeToRich() {
        const code = document.getElementById('es-html-editor')?.value || '';
        const rich = document.getElementById('es-rich-editor');
        if (rich) rich.innerHTML = code;
    }

    function _syncRichToCode() {
        const rich = document.getElementById('es-rich-editor');
        const htmlEl = document.getElementById('es-html-editor');
        if (rich && htmlEl) htmlEl.value = rich.innerHTML;
    }

    function _initRichEditor() {
        document.querySelectorAll('.es-rich-btn').forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                const cmd = this.dataset.cmd;
                const rich = document.getElementById('es-rich-editor');
                if (!rich) return;
                rich.focus();
                if (cmd === 'link') {
                    const url = prompt('URL:', 'https://');
                    if (url) document.execCommand('createLink', false, url);
                } else if (cmd === 'color') {
                    document.execCommand('foreColor', false, '#163258');
                } else {
                    document.execCommand(cmd, false, null);
                }
                _syncRichToCode();
                _schedulePreview();
            });
        });

        const rich = document.getElementById('es-rich-editor');
        if (rich) {
            rich.addEventListener('input', () => {
                _syncRichToCode();
                _schedulePreview();
            });
        }
    }

    /* ══════════════════════════════════════════════════════
     * WYSIWYG CANVAS
     * ══════════════════════════════════════════════════════ */
    function _initWysiwyg() {
        const canvas = document.getElementById('es-canvas');
        if (!canvas) return;

        canvas.querySelectorAll('.es-block').forEach(block => {
            _bindBlock(block);
        });

        const addBtn = document.getElementById('es-add-block-btn');
        if (addBtn) {
            addBtn.addEventListener('click', _showAddBlockMenu);
        }

        // Echter Template-Inhalt aus Textarea in Canvas laden
        if (document.getElementById('es-html-editor')?.value?.trim()) {
            _syncCodeToCanvas();
        }
        _syncCanvasToCode();
    }

    function _bindBlock(block) {
        const bodyEl = block.querySelector('.es-block-body-inner');
        if (bodyEl) {
            bodyEl.addEventListener('input', () => {
                _scheduleUndoSnapshot();
                _schedulePreview();
                _syncCanvasToCode();
            });
            bodyEl.addEventListener('focus', () => {
                document.querySelectorAll('.es-block.selected')
                    .forEach(b => b.classList.remove('selected'));
                block.classList.add('selected');
            });
        }

        block.querySelectorAll('.es-block-action-btn').forEach(btn => {
            btn.addEventListener('click', e => {
                e.stopPropagation();
                const action = btn.dataset.action;
                if (action === 'up')     _moveBlock(block, -1);
                if (action === 'down')   _moveBlock(block, 1);
                if (action === 'delete') _deleteBlock(block);
                if (action === 'sig-settings') _openSignaturePanel();
            });
        });
    }

    function _moveBlock(block, dir) {
        const canvas = document.getElementById('es-canvas');
        if (!canvas) return;
        const blocks = Array.from(canvas.querySelectorAll('.es-block'));
        const idx    = blocks.indexOf(block);
        const target = blocks[idx + dir];
        if (!target) return;
        if (dir === -1) canvas.insertBefore(block, target);
        else            canvas.insertBefore(target, block);
        _scheduleUndoSnapshot();
        _syncCanvasToCode();
        _schedulePreview();
    }

    function _deleteBlock(block) {
        if (!ES.confirm('es.confirm_delete', t('confirm_delete', 'Block löschen?'))) return;
        block.remove();
        _scheduleUndoSnapshot();
        _syncCanvasToCode();
        _schedulePreview();
    }

    function _showAddBlockMenu() {
        const menu = document.getElementById('es-add-block-menu');
        if (menu) menu.classList.toggle('show');
    }

    document.addEventListener('click', e => {
        const menu = document.getElementById('es-add-block-menu');
        if (menu && !e.target.closest('#es-add-block-btn') && !e.target.closest('#es-add-block-menu')) {
            menu.classList.remove('show');
        }
        const msWrap = document.getElementById('es-milestone-input-wrap');
        if (msWrap && !e.target.closest('#es-milestone-btn') && !e.target.closest('#es-milestone-input-wrap')) {
            msWrap.classList.remove('show');
        }
    });

    window.esAddBlock = function(type) {
        const canvas = document.getElementById('es-canvas');
        if (!canvas) return;

        const sigBlock = canvas.querySelector('.es-block[data-block-type="signature"]');
        const newBlock = _createBlock(type);
        if (!newBlock) return;

        _bindBlock(newBlock);

        if (sigBlock) canvas.insertBefore(newBlock, sigBlock);
        else          canvas.appendChild(newBlock);

        const menu = document.getElementById('es-add-block-menu');
        if (menu) menu.classList.remove('show');

        _scheduleUndoSnapshot();
        _syncCanvasToCode();
        _schedulePreview();
    };

    function _createBlock(type) {
        const div = document.createElement('div');
        div.className = 'es-block';
        div.dataset.blockType = type;

        const actions = `
            <div class="es-block-actions">
                <button class="es-block-action-btn" data-action="up"     title="Hoch"><i class="bi bi-arrow-up"></i></button>
                <button class="es-block-action-btn" data-action="down"   title="Runter"><i class="bi bi-arrow-down"></i></button>
                <button class="es-block-action-btn danger" data-action="delete" title="Löschen"><i class="bi bi-trash"></i></button>
            </div>`;

        const placeholderTxt = t('wysiwyg_click_to_edit', 'Klicken zum Bearbeiten');

        if (type === 'text') {
            div.innerHTML = actions + `
                <div class="es-block-body-inner" contenteditable="true" data-placeholder="${placeholderTxt}">
                    <p>${t('block_body', 'Neuer Textabschnitt')}</p>
                </div>`;
        } else if (type === 'button') {
            div.innerHTML = `<span class="es-block-label">{{block:cta_blau}}</span>` + actions + `
                <div class="es-block-button-inner">
                    <a href="{button_url}" class="es-block-button-link" contenteditable="true">{button_text}</a>
                </div>`;
        } else if (type === 'divider') {
            div.innerHTML = actions + `
                <div style="padding:8px 16px;"><hr style="border:none;border-top:1px solid #e0e0e0;margin:0;"></div>`;
        } else if (type === 'signature') {
            div.innerHTML = `<span class="es-block-label">{{block:signature}}</span>` + actions + `
                <div class="es-block-sig-inner">
                    <span class="es-block-sig-label">
                        <i class="bi bi-pen"></i>
                        <span>${t('block_signature', 'Signatur')}</span>
                    </span>
                    <div class="es-sig-content es-sig-preview-placeholder"></div>
                </div>`;
        } else {
            return null;
        }
        return div;
    }

    /* ══════════════════════════════════════════════════════
     * CANVAS ↔ CODE SYNC
     * ══════════════════════════════════════════════════════ */
    function _syncCanvasToCode() {
        const canvas   = document.getElementById('es-canvas');
        const textarea = document.getElementById('es-html-editor');
        if (!canvas || !textarea) return;

        const clone = canvas.cloneNode(true);
        clone.querySelectorAll('.es-block-actions').forEach(el => el.remove());
        clone.querySelectorAll('.es-block-label').forEach(el => el.remove());
        clone.querySelectorAll('.es-block-sig-label').forEach(el => el.remove());

        clone.querySelectorAll('.es-block[data-block-type="signature"]').forEach(block => {
            const ph = document.createTextNode('{{block:signature}}');
            block.replaceWith(ph);
        });

        clone.querySelectorAll('[contenteditable]').forEach(el => {
            el.removeAttribute('contenteditable');
            el.removeAttribute('data-placeholder');
        });

        textarea.value = clone.innerHTML
            .replace(/\s*class="es-block[^"]*"/g, '')
            .replace(/\s*data-block-type="[^"]*"/g, '')
            .replace(/\n\s*\n/g, '\n')
            .trim();
    }

    function _syncCodeToCanvas() {
        const canvas   = document.getElementById('es-canvas');
        const textarea = document.getElementById('es-html-editor');
        if (!canvas || !textarea || !textarea.value.trim()) return;

        // Einfacher Parser: bekannte Block-Typen aus HTML wiederherstellen
        const html = textarea.value;
        const hasSigToken = html.includes('{{block:signature}}');
        const htmlWithoutSig = html.replace(/\{\{block:signature\}\}/g, '').trim();

        const tmpDiv = document.createElement('div');
        tmpDiv.innerHTML = htmlWithoutSig || html;

        // Blöcke aus dem Canvas-HTML rekonstruieren
        canvas.querySelectorAll('.es-block').forEach(b => b.remove());

        // Alle es-block divs aus dem gespeicherten HTML wiederherstellen
        tmpDiv.querySelectorAll('.es-block').forEach(block => {
            canvas.appendChild(block.cloneNode(true));
        });

        // Wenn keine es-block Struktur vorhanden → rohen HTML als Body-Block anzeigen
        if (!canvas.querySelector('.es-block')) {
            const bodyBlock = document.createElement('div');
            bodyBlock.className = 'es-block';
            bodyBlock.dataset.blockType = 'body';
            bodyBlock.innerHTML = `
                <div class="es-block-actions">
                    <button class="es-block-action-btn" data-action="up" title="${t('block_up','Hoch')}"><i class="bi bi-arrow-up"></i></button>
                    <button class="es-block-action-btn" data-action="down" title="${t('block_down','Runter')}"><i class="bi bi-arrow-down"></i></button>
                    <button class="es-block-action-btn danger" data-action="delete" title="${t('block_delete','Löschen')}"><i class="bi bi-trash"></i></button>
                </div>
                <div class="es-block-body-inner" contenteditable="true">${htmlWithoutSig || html}</div>`;
            canvas.appendChild(bodyBlock);
        }

        if (hasSigToken && !canvas.querySelector('.es-block[data-block-type="signature"]')) {
            const sigBlock = _createBlock('signature');
            if (sigBlock) {
                canvas.appendChild(sigBlock);
                _bindBlock(sigBlock);
            }
        }

        canvas.querySelectorAll('.es-block').forEach(_bindBlock);
        _updateSigBlock(document.querySelector('input[name="es-sig-mode"]:checked')?.value || 'USER');
        _updateSignatureBlockState();
    }

    /* ══════════════════════════════════════════════════════
     * SIDEBAR-HINWEISE & VARIABLEN
     * ══════════════════════════════════════════════════════ */
    function _initSectionHints() {
        document.querySelectorAll('.es-section-hint[data-i18n-title]').forEach(el => {
            const raw = el.getAttribute('data-i18n-title') || '';
            const key = raw.startsWith('es.') ? raw.slice(3) : raw;
            const txt = t(key, el.getAttribute('title') || '');
            if (txt) {
                el.setAttribute('title', txt);
                el.setAttribute('data-bs-original-title', txt);
            }
        });
        if (typeof bootstrap === 'undefined' || !bootstrap.Tooltip) return;
        document.querySelectorAll('.es-section-hint[data-bs-toggle="tooltip"]').forEach(el => {
            bootstrap.Tooltip.getInstance(el)?.dispose();
            bootstrap.Tooltip.getOrCreateInstance(el, { trigger: 'hover focus', container: 'body' });
        });
    }

    function _moduleGroupLabel(type) {
        return t('module_grp_' + type, type);
    }

    function _varGroupLabel(key, fallback) {
        const map = {
            context: t('vars_context', 'Aus Kontext'),
            meetme:  t('vars_meetme', 'MeetMe / Telefon'),
            scope:   t('vars_scope', 'App-Bereich'),
            user:    t('vars_user', 'Benutzerprofil'),
            system:  t('vars_system', 'System'),
            status:  t('vars_status', 'System-Status'),
            module:  t('vars_module', 'Module'),
        };
        return map[key] || fallback || key;
    }

    function _subGroupAccordionHtml(label, innerHtml, count, i18nKey) {
        const n = count != null ? count : (innerHtml.match(/es-var-chip|es-module-chip/g) || []).length;
        const i18nAttr = i18nKey
            ? ` data-i18n="${i18nKey.startsWith('es.') ? i18nKey : 'es.' + i18nKey}"`
            : '';
        return `<div class="es-sub-toggle">`
             + `<div class="es-sub-toggle-hdr" onclick="toggleSection(this)">`
             + `<span class="es-sub-toggle-lbl"${i18nAttr}>${label}</span>`
             + `<span class="es-sub-toggle-meta">`
             + `<span class="es-sub-toggle-count">${n}</span>`
             + `<i class="bi bi-chevron-down"></i></span></div>`
             + `<div class="es-sub-toggle-body section-content">${innerHtml}</div></div>`;
    }

    function _renderVariableGroups(groups) {
        const container = document.getElementById('es-vars-panel-body');
        if (!container || !groups) return;
        let html = '';
        groups.forEach(group => {
            const chipClass = group.chip_class || group.key || 'context';
            const label = _varGroupLabel(group.key, group.label);
            let chips = '';
            (group.vars || []).forEach(v => {
                const desc = (v.description || '').replace(/"/g, '&quot;');
                const ex   = (v.example || '').replace(/"/g, '&quot;');
                chips += `<div class="es-var-chip ${chipClass}" data-var="${v.name}"`
                     + ` data-var-desc="${desc}" data-var-example="${ex}">`
                     + `<span class="es-var-chip-label">{${v.name}}</span>`
                     + `<span class="es-var-chip-actions">`
                     + `<button type="button" class="es-var-info-btn" title="Info"`
                     + ` aria-label="Info"><i class="bi bi-info-circle"></i></button>`
                     + `<i class="bi bi-clipboard es-var-chip-icon"></i></span></div>`;
            });
            const i18nKey = group.label_i18n || ('es.vars_' + (group.key || ''));
            html += _subGroupAccordionHtml(label, chips, (group.vars || []).length, i18nKey);
        });
        container.innerHTML = html;
        const badge = document.getElementById('es-var-count-badge');
        if (badge) {
            const n = groups.reduce((sum, g) => sum + (g.vars || []).length, 0);
            badge.textContent = String(n);
        }
    }

    async function _reloadVariablesPanel() {
        const scopeEl = document.querySelector('select[name=app_scope]');
        const identEl = document.getElementById('es-identifier-input');
        const scope = scopeEl?.value || 'general';
        const ident = identEl?.value || '';
        if (typeof ES === 'undefined' || !ES.api) return;
        try {
            const q = `variables/?scope=${encodeURIComponent(scope)}&identifier=${encodeURIComponent(ident)}`;
            const data = await ES.api.get(ES.apiUrl(q));
            if (data.groups) _renderVariableGroups(data.groups);
            _bindVarChips(document.getElementById('es-vars-panel-body'));
        } catch (e) {
            console.warn('Variablen neu laden fehlgeschlagen:', e);
        }
    }

    function _initScopeVariableReload() {
        const scopeEl = document.querySelector('select[name=app_scope]');
        if (scopeEl) {
            scopeEl.addEventListener('change', () => _reloadVariablesPanel());
        }
        const identEl = document.getElementById('es-identifier-input');
        if (identEl && !identEl.readOnly) {
            identEl.addEventListener('change', () => _reloadVariablesPanel());
        }
    }

    function _showVarPopover(btn, chip) {
        if (typeof bootstrap === 'undefined' || !bootstrap.Popover) return;
        const name = chip.dataset.var || '';
        const fallback = chip.dataset.varDesc || '';
        const desc = t('var_desc_' + name, fallback);
        const ex   = chip.dataset.varExample || '';
        let content = `<div class="es-var-popover"><strong>{${name}}</strong>`;
        if (desc) content += `<p class="es-var-popover-desc">${desc}</p>`;
        if (ex) content += `<div class="es-var-popover-example">${t('var_example', 'Beispiel')}: ${ex}</div>`;
        content += `<div class="es-var-popover-hint">${t('var_click_insert', 'Klick auf Chip = einfügen')}</div></div>`;

        bootstrap.Popover.getInstance(btn)?.dispose();
        const pop = new bootstrap.Popover(btn, {
            html: true,
            sanitize: false,
            content,
            trigger: 'focus',
            placement: 'right',
            container: 'body',
        });
        pop.show();
        btn.addEventListener('blur', () => pop.dispose(), { once: true });
    }

    function _showModulePopover(btn, chip) {
        if (typeof bootstrap === 'undefined' || !bootstrap.Popover) return;
        const syntax = chip.dataset.syntax || '';
        const desc   = chip.dataset.modDesc || '';
        const name   = chip.dataset.modName || '';
        let content = `<div class="es-var-popover"><strong>${name}</strong>`;
        if (syntax) {
            content += `<div class="es-var-popover-example">${syntax}</div>`;
        }
        if (desc) content += `<p class="es-var-popover-desc">${desc}</p>`;
        content += `<div class="es-var-popover-hint">${t('module_click_insert', t('var_click_insert', 'Klick auf Chip = einfügen'))}</div></div>`;

        bootstrap.Popover.getInstance(btn)?.dispose();
        const pop = new bootstrap.Popover(btn, {
            html: true,
            sanitize: false,
            content,
            trigger: 'focus',
            placement: 'right',
            container: 'body',
        });
        pop.show();
        btn.addEventListener('blur', () => pop.dispose(), { once: true });
    }

    function _insertModuleSyntax(syntax, chipEl) {
        if (!syntax) return;
        if (syntax === '{{block:signature}}') {
            _insertSignatureBlock();
            ES.copyToClipboard(syntax, chipEl);
            return;
        }
        // Paar-Syntax: Cursor zwischen {{block:id}} und {{/block}}
        if (syntax.includes('{{/block}}')) {
            _insertPairedBlockSyntax(syntax);
        } else {
            _insertAtCursor(syntax);
        }
        ES.copyToClipboard(syntax, chipEl);
    }

    function _insertPairedBlockSyntax(syntax) {
        const openEnd = syntax.indexOf('}}') + 2;
        const closeStart = syntax.indexOf('{{/block}}');
        if (openEnd < 2 || closeStart < 0) {
            _insertAtCursor(syntax);
            return;
        }
        const before = syntax.slice(0, openEnd) + '\n';
        const after = '\n' + syntax.slice(closeStart);
        const mid = syntax.slice(openEnd, closeStart).replace(/^\n/, '').replace(/\n$/, '');
        const ta = document.getElementById('es-html-editor');
        const rich = document.getElementById('es-rich-editor');
        if (_currentMode === 'html-editor' && rich) {
            rich.focus();
            document.execCommand('insertText', false, before + (mid || '') + after);
            _syncRichToCode();
            _schedulePreview();
            return;
        }
        if (ta && (_currentMode === 'code' || _currentMode === 'html-editor')) {
            const pos = ta.selectionStart || 0;
            const insert = before + (mid || '') + after;
            ta.value = ta.value.slice(0, pos) + insert + ta.value.slice(pos);
            const cursor = pos + before.length + (mid || '').length;
            ta.selectionStart = ta.selectionEnd = cursor;
            ta.focus();
            _schedulePreview();
            return;
        }
        _insertAtCursor(syntax);
    }

    function _insertVariableToken(varName) {
        const token = `{${varName}}`;
        if (_currentMode === 'visual') {
            const sel = window.getSelection();
            if (sel && sel.rangeCount) {
                const range = sel.getRangeAt(0);
                const canvas = document.getElementById('es-canvas');
                if (canvas && canvas.contains(range.commonAncestorContainer)) {
                    range.deleteContents();
                    range.insertNode(document.createTextNode(token));
                    range.collapse(false);
                    _scheduleUndoSnapshot();
                    _syncCanvasToCode();
                    _schedulePreview();
                }
            }
        } else {
            const ta = (_currentMode === 'txt')
                ? document.getElementById('es-txt-editor')
                : document.getElementById('es-html-editor');
            if (ta) {
                const pos = ta.selectionStart;
                ta.value  = ta.value.slice(0, pos) + token + ta.value.slice(pos);
                ta.selectionStart = ta.selectionEnd = pos + token.length;
                ta.focus();
                _schedulePreview();
            }
        }
    }

    function _bindVarChips(root) {
        (root || document).querySelectorAll('.es-var-chip').forEach(chip => {
            if (chip.dataset.bound) return;
            chip.dataset.bound = '1';
            chip.addEventListener('click', function(e) {
                if (e.target.closest('.es-var-info-btn')) return;
                const varName = this.dataset.var;
                _insertVariableToken(varName);
                ES.copyToClipboard(`{${varName}}`, this);
            });
            const infoBtn = chip.querySelector('.es-var-info-btn');
            if (infoBtn) {
                infoBtn.addEventListener('click', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    _showVarPopover(this, chip);
                });
            }
        });
    }

    function _initVarChips() {
        _bindVarChips(document.getElementById('es-vars-panel-body'));
    }

    /* ══════════════════════════════════════════════════════
     * MODULE-CHIPS
     * ══════════════════════════════════════════════════════ */
    function _bindModuleChips(root) {
        (root || document).querySelectorAll('.es-module-chip[data-syntax]').forEach(chip => {
            if (chip.dataset.bound) return;
            chip.dataset.bound = '1';
            chip.addEventListener('click', function(e) {
                if (e.target.closest('.es-var-info-btn')) return;
                _insertModuleSyntax(this.dataset.syntax, this);
            });
            const infoBtn = chip.querySelector('.es-var-info-btn');
            if (infoBtn) {
                infoBtn.addEventListener('click', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    _showModulePopover(this, chip);
                });
            }
        });
    }

    function _initModuleChips() {
        _bindModuleChips(document);
        const modulesPanel = document.getElementById('es-modules-panel-body');
        if (modulesPanel && !modulesPanel.dataset.loaded) {
            _loadModules();
        }
    }

    async function _loadModules(forceReload) {
        const container = document.getElementById('es-modules-panel-body');
        if (!container) return;
        if (container.dataset.loaded && !forceReload) return;
        if (forceReload) delete container.dataset.loaded;
        if (typeof ES === 'undefined' || !ES.api) {
            console.warn('ES noch nicht geladen, Module-Load verschoben');
            setTimeout(() => _loadModules(forceReload), 300);
            return;
        }
        try {
            const data    = await ES.api.get(ES.apiUrl('modules/'));
            const grouped = data.modules || {};
            const groupOrder = data.group_order || [
                'HEADER', 'FORMAT', 'BLOCK', 'SECTION', 'BUTTON',
                'SIGNATURE', 'FOOTER', 'DISCLAIMER',
            ];
            let html      = '';
            const typeIcons = {
                FORMAT: 'bi-columns-gap',
                BLOCK: 'bi-collection',
                HEADER: 'bi-layout-text-window-reverse',
                FOOTER: 'bi-layout-text-window',
                BUTTON: 'bi-cursor',
                SECTION:'bi-layout-text-sidebar',
                DISCLAIMER: 'bi-info-circle',
                SIGNATURE: 'bi-pen',
            };
            let totalMods = 0;
            const types = [
                ...groupOrder.filter(t => grouped[t] && grouped[t].length),
                ...Object.keys(grouped).filter(t => !groupOrder.includes(t) && grouped[t]?.length),
            ];
            for (const type of types) {
                const modules = grouped[type] || [];
                if (!modules.length) continue;
                totalMods += modules.length;
                let chips = '';
                for (const m of modules) {
                    const desc   = (m.description || '').replace(/"/g, '&quot;');
                    const name   = (m.name || '').replace(/"/g, '&quot;');
                    const syntax = (m.syntax || '').replace(/"/g, '&quot;');
                    const idHint = (m.identifier || '').replace(/"/g, '&quot;');
                    chips += `
                    <div class="es-module-chip" data-syntax="${syntax}"
                         data-mod-name="${name}" data-mod-desc="${desc}"
                         title="${idHint}">
                        <span class="es-module-chip-label">
                            <i class="bi ${typeIcons[type] || 'bi-puzzle'} es-module-chip-icon"></i>
                            <span>${m.name}</span>
                        </span>
                        <span class="es-var-chip-actions">
                            <button type="button" class="es-var-info-btn" title="Info"
                                    aria-label="Info"><i class="bi bi-info-circle"></i></button>
                            <i class="bi bi-clipboard es-var-chip-icon"></i>
                        </span>
                    </div>`;
                }
                html += _subGroupAccordionHtml(
                    _moduleGroupLabel(type), chips, modules.length, 'es.module_grp_' + type
                );
            }
            container.innerHTML = html || `<div class="es-modules-empty">${t('modules_empty', 'Keine Module gefunden')}</div>`;
            container.dataset.loaded = '1';
            const modBadge = document.getElementById('es-mod-count-badge');
            if (modBadge) modBadge.textContent = String(totalMods);
            _bindModuleChips(container);
        } catch(e) {
            console.error('Module laden fehlgeschlagen:', e);
        }
    }

    function _insertAtCursor(text) {
        const taId = (_currentMode === 'txt') ? 'es-txt-editor' : 'es-html-editor';
        const ta = document.getElementById(taId);
        if (ta) {
            const pos = ta.selectionStart || 0;
            ta.value  = ta.value.slice(0, pos) + text + ta.value.slice(pos);
            ta.selectionStart = ta.selectionEnd = pos + text.length;
            if (_currentMode !== 'visual') ta.focus();
        }
        _syncCanvasToCode();
        _schedulePreview();
        if (text && text.includes('{{block:signature}}')) {
            _updateSignatureBlockState();
        }
    }

    function _initMcidValidate() {
        const btn = document.getElementById('es-mcid-validate-btn');
        if (!btn || btn.dataset.bound) return;
        btn.dataset.bound = '1';
        btn.addEventListener('click', _runMcidValidate);
    }

    async function _runMcidValidate() {
        const out = document.getElementById('es-mcid-validate-result');
        const btn = document.getElementById('es-mcid-validate-btn');
        if (_currentMode === 'visual' && _currentEntity === 'template') {
            _syncCanvasToCode();
        }
        const html = document.getElementById('es-html-editor')?.value || '';
        if (btn) btn.disabled = true;
        try {
            const data = await ES.api.post(ES.apiUrl('mcid-validate/'), {
                html_body: html,
                context: _currentEntity === 'module' ? 'module' : 'template',
            });
            if (!out) return;
            out.hidden = false;
            const errs = data.errors || [];
            const warns = data.warnings || [];
            if (data.ok) {
                out.className = 'es-mcid-validate-result ok';
                out.innerHTML = `<i class="bi bi-check-circle"></i> ${t('mcid_validate_ok', 'MCID Regel 1 OK')}`
                    + (warns.length ? ` <span class="es-mcid-warn-count">(${warns.length} Hinweise)</span>` : '');
            } else {
                out.className = 'es-mcid-validate-result fail';
                const lines = errs.slice(0, 8).map(e =>
                    `<li>${(e.message || e.code || '').replace(/</g, '&lt;')}</li>`
                ).join('');
                out.innerHTML = `<div><i class="bi bi-x-circle"></i> ${t('mcid_validate_fail', 'MCID-Probleme gefunden')}</div>`
                    + `<ul class="es-mcid-error-list">${lines}</ul>`;
            }
            if (warns.length && data.ok) {
                out.title = warns.map(w => w.message).join('\n');
            }
        } catch (err) {
            console.error('MCID-Validate fehlgeschlagen:', err);
            if (out) {
                out.hidden = false;
                out.className = 'es-mcid-validate-result fail';
                out.textContent = String(err.message || err);
            }
        } finally {
            if (btn) btn.disabled = false;
        }
    }

    /* ══════════════════════════════════════════════════════
     * LIVE VORSCHAU
     * ══════════════════════════════════════════════════════ */
    function _schedulePreview() {
        clearTimeout(_previewTimer);
        _previewTimer = setTimeout(() => _loadPreview(false), 600);
    }

    function _collectPreviewPayload() {
        _syncAllToCode();

        const sigModeEl  = document.querySelector('input[name="es-sig-mode"]:checked');
        const sigFixedEl = document.getElementById('es-sig-fixed-select');
        const sigMode    = sigModeEl?.value || 'USER';

        const payload = {
            variables:         _expandPreviewVars(
                document.getElementById('es-html-editor')?.value || '',
                document.getElementById('es-subject-input')?.value || '',
                document.getElementById('es-txt-editor')?.value || ''
            ),
            mode:              'both',
            html_body:         document.getElementById('es-html-editor')?.value || '',
            subject:           document.getElementById('es-subject-input')?.value || '',
            text_body:         document.getElementById('es-txt-editor')?.value || '',
            signature_mode:    sigMode,
            include_signature: sigMode !== 'NONE',
        };

        if (sigMode === 'FIXED' && sigFixedEl?.value) {
            payload.signature_id = parseInt(sigFixedEl.value, 10);
        }

        const senderBtn = document.querySelector('.es-mode-btn.active');
        if (senderBtn?.dataset.mode) {
            payload.sender_mode = senderBtn.dataset.mode;
        }

        return payload;
    }

    function _initPreviewRefresh() {
        const btn = document.getElementById('es-preview-refresh-btn');
        if (btn) {
            btn.addEventListener('click', () => _loadPreview(true));
        }
    }

    function _getActivePreviewClient() {
        return document.querySelector('.es-preview-hdr .es-preview-client-btn.active')?.dataset.client || 'outlook';
    }

    function _wantsTxtPreview() {
        return _currentMode === 'txt' || _getActivePreviewClient() === 'txt';
    }

    function _renderTxtPreview(text) {
        const bodyEl = document.getElementById('es-preview-body');
        if (!bodyEl) return;
        bodyEl.innerHTML = '';
        bodyEl.className = 'es-email-sim-body es-preview-txt-mode';
        bodyEl.textContent = text || '';
    }

    async function _loadPreview(manual = false) {
        _syncAllToCode();

        const editLang = window.ES_CONFIG?.editLang || '';
        const htmlBody = document.getElementById('es-html-editor')?.value || '';
        const txtBody  = document.getElementById('es-txt-editor')?.value || '';
        const subject  = document.getElementById('es-subject-input')?.value || '';
        const wantTxt  = _wantsTxtPreview();

        const subjEl = document.getElementById('es-preview-subject');
        const bodyEl = document.getElementById('es-preview-body');
        const refreshBtn = document.getElementById('es-preview-refresh-btn');

        if (manual && refreshBtn) refreshBtn.classList.add('es-preview-refreshing');
        if (manual && bodyEl) bodyEl.classList.add('es-preview-loading');

        /* Modul / Signatur: Client-Vorschau */
        if (_currentEntity === 'module' || _currentEntity === 'signature') {
            if (subjEl) {
                const label = _currentEntity === 'module'
                    ? (_entityCache.module.name || t('entity_module', 'Modul'))
                    : (_entityCache.signature.name || t('entity_signature', 'Signatur'));
                subjEl.textContent = label;
            }
            if (wantTxt && txtBody) {
                _renderTxtPreview(_applyDummyVarsLocal(txtBody));
            } else if (htmlBody) {
                if (bodyEl) bodyEl.className = 'es-email-sim-body';
                _renderInIframe(_applyDummyVarsLocal(htmlBody));
            } else if (bodyEl) {
                bodyEl.innerHTML = '';
                bodyEl.className = 'es-email-sim-body';
            }
            if (manual && refreshBtn) refreshBtn.classList.remove('es-preview-refreshing');
            if (manual && bodyEl) bodyEl.classList.remove('es-preview-loading');
            return;
        }

        if (subjEl && subject) subjEl.textContent = _applyDummyVarsLocal(subject);

        if (!_templateId || editLang) {
            try {
                const payload = _collectPreviewPayload();
                const data = await ES.api.post(ES.apiUrl('preview/draft/'), payload);
                if (wantTxt) {
                    _renderTxtPreview(data.text || _applyDummyVarsLocal(txtBody));
                } else if (data.html) {
                    if (bodyEl) bodyEl.className = 'es-email-sim-body';
                    _renderInIframe(data.html);
                }
                if (subjEl && data.subject) subjEl.textContent = data.subject;
                const fromEl = document.getElementById('es-preview-from');
                if (fromEl && data.from_email) fromEl.textContent = data.from_email;
            } catch (err) {
                console.warn('Draft-Vorschau fallback:', err);
                if (wantTxt) {
                    _renderTxtPreview(_applyDummyVarsLocal(txtBody));
                } else if (htmlBody) {
                    if (bodyEl) bodyEl.className = 'es-email-sim-body';
                    _renderInIframe(_applyDummyVarsLocal(htmlBody));
                }
                if (subjEl && subject) subjEl.textContent = _applyDummyVarsLocal(subject);
            }
            if (manual && refreshBtn) refreshBtn.classList.remove('es-preview-refreshing');
            if (manual && bodyEl) bodyEl.classList.remove('es-preview-loading');
            return;
        }

        try {
            const data = await ES.api.post(
                ES.apiUrl(`templates/${_templateId}/preview/`),
                _collectPreviewPayload()
            );
            if (wantTxt) {
                _renderTxtPreview(data.text || _applyDummyVarsLocal(txtBody));
            } else if (data.html) {
                if (bodyEl) bodyEl.className = 'es-email-sim-body';
                _renderInIframe(data.html);
            }
            if (subjEl && data.subject) subjEl.textContent = data.subject;
            const fromEl = document.getElementById('es-preview-from');
            if (fromEl && data.from_email) fromEl.textContent = data.from_email;
        } catch(err) {
            console.error('Vorschau fehlgeschlagen:', err);
            if (wantTxt) {
                _renderTxtPreview(_applyDummyVarsLocal(txtBody));
            } else if (htmlBody) {
                if (bodyEl) bodyEl.className = 'es-email-sim-body';
                _renderInIframe(_applyDummyVarsLocal(htmlBody));
            }
        } finally {
            if (manual && refreshBtn) refreshBtn.classList.remove('es-preview-refreshing');
            if (manual && bodyEl) bodyEl.classList.remove('es-preview-loading');
        }
    }

    function _expandPreviewVars(...texts) {
        const vars = { ...DUMMY_VARS, ..._collectTestVars() };
        const re = /\{(\w+)\}/g;
        texts.forEach(text => {
            if (!text) return;
            let m;
            while ((m = re.exec(text)) !== null) {
                if (!(m[1] in vars)) vars[m[1]] = `[${m[1]}]`;
            }
        });
        return vars;
    }

    function _applyDummyVarsLocal(html) {
        const vars = _expandPreviewVars(html);
        let out = html;
        Object.entries(vars).forEach(([key, value]) => {
            out = out.split(`{${key}}`).join(String(value ?? ''));
        });
        return out;
    }

    function _sanitizePreviewHtml(html) {
        if (!html) return '';
        let out = html;
        out = out.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '');
        out = out.replace(/<script\b[^>]*\/>/gi, '');
        out = out.replace(/\s+on\w+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi, '');
        return out;
    }

    function _renderInIframe(html) {
        const bodyEl = document.getElementById('es-preview-body');
        if (!bodyEl) return;

        const safeHtml = _sanitizePreviewHtml(html);
        let wrap = bodyEl.querySelector('.es-preview-html');
        if (!wrap) {
            bodyEl.innerHTML = '';
            bodyEl.style.padding = '10px';
            wrap = document.createElement('div');
            wrap.className = 'es-preview-html';
            bodyEl.appendChild(wrap);
        }
        wrap.innerHTML = safeHtml;
    }

    function _collectTestVars() {
        const vars = {};
        document.querySelectorAll('[data-test-var]').forEach(el => {
            vars[el.dataset.testVar] = el.value || el.textContent;
        });
        return vars;
    }

    /* ══════════════════════════════════════════════════════
     * UNDO / REDO
     * ══════════════════════════════════════════════════════ */
    function _initUndoRedo() {
        const undoBtn = document.getElementById('es-undo-btn');
        const redoBtn = document.getElementById('es-redo-btn');

        if (undoBtn) {
            undoBtn.addEventListener('click', _undo);
            undoBtn.title = t('undo', 'Rückgängig') + ' (Ctrl+Z)';
        }
        if (redoBtn) {
            redoBtn.addEventListener('click', _redo);
            redoBtn.title = t('redo', 'Wiederholen') + ' (Ctrl+Y)';
        }

        document.addEventListener('keydown', e => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
            if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
                e.preventDefault();
                _undo();
            }
            if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) {
                e.preventDefault();
                _redo();
            }
        });

        const ta = document.getElementById('es-html-editor');
        if (ta) {
            ta.addEventListener('input', _scheduleUndoSnapshot);
        }

        _takeUndoSnapshot();
    }

    function _scheduleUndoSnapshot() {
        clearTimeout(_undoTimer);
        _undoTimer = setTimeout(_takeUndoSnapshot, 800);
    }

    function _takeUndoSnapshot() {
        const state = _captureState();
        const last  = _undoStack[_undoStack.length - 1];
        if (last && last.html === state.html && last.subject === state.subject) return;

        _undoStack.push(state);
        if (_undoStack.length > UNDO_MAX) _undoStack.shift();
        _redoStack = [];
        _updateUndoRedoBtns();
    }

    function _captureState() {
        const canvas  = document.getElementById('es-canvas');
        const ta      = document.getElementById('es-html-editor');
        const subject = document.getElementById('es-subject-input');
        return {
            html:    canvas ? canvas.innerHTML : (ta ? ta.value : ''),
            subject: subject ? subject.value : '',
            mode:    _currentMode,
        };
    }

    function _applyState(state) {
        if (!state) return;
        const canvas  = document.getElementById('es-canvas');
        const ta      = document.getElementById('es-html-editor');
        const subject = document.getElementById('es-subject-input');

        if (canvas && state.mode === 'visual') {
            canvas.innerHTML = state.html;
            canvas.querySelectorAll('.es-block').forEach(_bindBlock);
        } else if (ta) {
            ta.value = state.html;
        }
        if (subject && state.subject !== undefined) {
            subject.value = state.subject;
        }
        _updateUndoRedoBtns();
        _schedulePreview();
    }

    function _undo() {
        if (_undoStack.length <= 1) return;
        const current = _undoStack.pop();
        _redoStack.push(current);
        _applyState(_undoStack[_undoStack.length - 1]);
    }

    function _redo() {
        if (!_redoStack.length) return;
        const state = _redoStack.pop();
        _undoStack.push(state);
        _applyState(state);
    }

    function _updateUndoRedoBtns() {
        const undoBtn = document.getElementById('es-undo-btn');
        const redoBtn = document.getElementById('es-redo-btn');
        if (undoBtn) undoBtn.disabled = _undoStack.length <= 1;
        if (redoBtn) redoBtn.disabled = _redoStack.length === 0;
    }

    /* ══════════════════════════════════════════════════════
     * MEILENSTEINE
     * ══════════════════════════════════════════════════════ */
    function _initMilestone() {
        const btn  = document.getElementById('es-milestone-btn');
        const wrap = document.getElementById('es-milestone-input-wrap');
        const save = document.getElementById('es-milestone-save');
        const inp  = document.getElementById('es-milestone-label-inp');

        if (btn && wrap) {
            btn.addEventListener('click', e => {
                e.stopPropagation();
                wrap.classList.toggle('show');
                if (wrap.classList.contains('show') && inp) inp.focus();
            });
        }

        if (save && inp) {
            save.addEventListener('click', async () => {
                const label = inp.value.trim();
                if (!label) { inp.focus(); return; }
                await _saveMilestone(label);
                inp.value = '';
                if (wrap) wrap.classList.remove('show');
            });
            inp.addEventListener('keydown', async e => {
                if (e.key === 'Enter') {
                    const label = inp.value.trim();
                    if (!label) return;
                    await _saveMilestone(label);
                    inp.value = '';
                    if (wrap) wrap.classList.remove('show');
                }
                if (e.key === 'Escape') {
                    inp.value = '';
                    if (wrap) wrap.classList.remove('show');
                }
            });
        }
    }

    async function _saveMilestone(label) {
        if (!_templateId) {
            ES.notify.warning('es.error_save', t('error_save', 'Erst speichern'));
            return;
        }
        try {
            await ES.api.post(
                ES.apiUrl(`templates/${_templateId}/milestones/`),
                { label }
            );
            ES.notify.success('es.milestone_saved', t('milestone_saved', 'Meilenstein gespeichert'));
            _loadVersionsBar();
        } catch(e) {
            ES.notify.error('es.milestone_error', t('milestone_error', 'Fehler'));
        }
    }

    /* ══════════════════════════════════════════════════════
     * VERSIONS-TOGGLE-LEISTE
     * ══════════════════════════════════════════════════════ */
    function _initVersionsBar() {
        const verToggle   = document.getElementById('es-versions-toggle');
        const verPanel    = document.getElementById('es-versions-panel');
        const transToggle = document.getElementById('es-trans-toggle');
        const transPanel  = document.getElementById('es-trans-panel');

        if (verToggle && verPanel) {
            verToggle.addEventListener('click', () => {
                const isOpen = verToggle.classList.contains('open');
                verPanel.style.display = isOpen ? '' : 'none';
            });
        }

        if (transToggle && transPanel) {
            transToggle.addEventListener('click', () => {
                const isOpen = transToggle.classList.contains('open');
                transPanel.style.display = isOpen ? '' : 'none';
            });
        }
    }

    async function _loadVersionsBar() {
        if (!_templateId) return;
        if (typeof ES === 'undefined' || !ES.api) {
            setTimeout(_loadVersionsBar, 300);
            return;
        }
        try {
            const [verData, msData] = await Promise.all([
                ES.api.get(ES.apiUrl(`templates/${_templateId}/versions/`)),
                ES.api.get(ES.apiUrl(`templates/${_templateId}/milestones/`)),
            ]);

            _renderVersionsList(verData.versions || [], msData.milestones || [], verData.active_version);
            _updateVersionsBadges(verData.versions || [], msData.milestones || []);
        } catch(e) {
            console.warn('Versionen laden fehlgeschlagen:', e);
        }
    }

    function _renderVersionsList(versions, milestones, activeVersion) {
        const list = document.getElementById('es-versions-list');
        if (!list) return;

        let html = '';

        milestones.slice(0, MILESTONE_MAX).forEach(ms => {
            html += `
            <div class="es-version-item milestone" data-ms-id="${ms.id}"
                 title="${t('versions_click_hint', 'anklicken zum Wiederherstellen')}">
                <div class="es-version-num ms">📌</div>
                <div class="es-version-info">
                    <div class="vt">${_esc(ms.milestone_label)}</div>
                    <div class="vs">${_formatDate(ms.created_at)}</div>
                </div>
            </div>`;
        });

        versions.forEach(v => {
            const isActive = v.version == activeVersion;
            html += `
            <div class="es-version-item ${isActive ? 'active-ver' : ''}"
                 data-ver="${v.version}"
                 title="${isActive ? t('version_active', 'Aktiv') : t('versions_click_hint', 'anklicken')}">
                <div class="es-version-num ${isActive ? 'ok' : 'old'}">${v.version}</div>
                <div class="es-version-info">
                    <div class="vt">${_esc(v.change_note) || 'Version ' + v.version}${isActive ? ' · ' + t('version_active','Aktiv') : ''}</div>
                    <div class="vs">${_formatDate(v.created_at)}</div>
                </div>
            </div>`;
        });

        if (!html) {
            html = `<span class="es-versions-hint">${t('versions_empty', 'Noch keine Versionen')}</span>`;
        }

        html += `<span class="es-versions-hint">
            <i class="bi bi-arrow-left"></i>
            ${t('versions_click_hint', 'anklicken zum Wiederherstellen')}
        </span>`;

        list.innerHTML = html;

        list.querySelectorAll('.es-version-item.milestone').forEach(el => {
            el.addEventListener('click', () => {
                const msId = parseInt(el.dataset.msId);
                const ms   = milestones.find(m => m.id === msId);
                if (ms) _showRestorePopup(ms, 'milestone');
            });
        });

        list.querySelectorAll('.es-version-item:not(.milestone):not(.active-ver)').forEach(el => {
            el.addEventListener('click', () => {
                const ver = versions.find(v => v.version == el.dataset.ver);
                if (ver) _showRestorePopup(ver, 'version');
            });
        });
    }

    function _updateVersionsBadges(versions, milestones) {
        const offEl = document.getElementById('es-versions-official-badge');
        const msEl  = document.getElementById('es-versions-ms-badge');
        if (offEl) offEl.textContent = versions.length + ' ' + t('versions_official_count', 'offiziell');
        if (msEl)  msEl.textContent  = '📌 ' + milestones.length + ' ' + t('versions_milestone_count', 'Meilensteine');
    }

    /* ══════════════════════════════════════════════════════
     * RESTORE POPUP
     * ══════════════════════════════════════════════════════ */
    function _initRestorePopup() {
        const overlay = document.getElementById('es-restore-overlay');
        if (overlay) {
            overlay.addEventListener('click', e => {
                if (e.target === overlay) _closeRestorePopup();
            });
        }

        const cancelBtn = document.getElementById('es-restore-cancel');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', _closeRestorePopup);
        }

        const okBtn = document.getElementById('es-restore-ok');
        if (okBtn) {
            okBtn.addEventListener('click', _doRestore);
        }
    }

    let _restoreTarget = null;
    let _restoreType   = null;

    async function _showRestorePopup(item, type) {
        _restoreTarget = item;
        _restoreType   = type;

        const overlay = document.getElementById('es-restore-overlay');
        if (!overlay) return;

        const nameEl = document.getElementById('es-restore-ms-name');
        const subEl  = document.getElementById('es-restore-ms-sub');

        const label = type === 'milestone'
            ? item.milestone_label
            : ('Version ' + item.version + (item.change_note ? ' — ' + item.change_note : ''));

        if (nameEl) nameEl.textContent = (type === 'milestone' ? '📌 ' : '') + label;
        if (subEl)  subEl.textContent  = _formatDate(item.created_at);

        const efHdr  = document.getElementById('es-restore-ef-hdr');
        const efBody = document.getElementById('es-restore-ef-body');
        const efSubj = document.getElementById('es-restore-ef-subject');

        if (efSubj) efSubj.textContent = item.subject || '';
        if (efHdr)  efHdr.textContent  = 'abcona e. K.';
        if (efBody) {
            const preview = item.html_body
                ? item.html_body.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 200)
                : t('restore_preview_lbl', 'Vorschau');
            efBody.textContent = preview;
        }

        overlay.classList.add('show');
    }

    function _closeRestorePopup() {
        const overlay = document.getElementById('es-restore-overlay');
        if (overlay) overlay.classList.remove('show');
        _restoreTarget = null;
        _restoreType   = null;
    }

    async function _doRestore() {
        if (!_restoreTarget || !_templateId) return;

        const okBtn = document.getElementById('es-restore-ok');
        if (okBtn) okBtn.disabled = true;

        try {
            if (_restoreType === 'milestone') {
                await ES.api.post(
                    ES.apiUrl(`templates/${_templateId}/milestones/${_restoreTarget.id}/restore/`),
                    {}
                );
            } else {
                await ES.api.post(
                    ES.apiUrl(`templates/${_templateId}/versions/${_restoreTarget.version}/activate/`),
                    {}
                );
            }
            ES.notify.success('es.version_activated', t('version_activated', 'Stand wiederhergestellt'));
            _closeRestorePopup();
            setTimeout(() => location.reload(), 800);
        } catch(e) {
            ES.notify.error('es.error_version', t('error_version', 'Fehler beim Wiederherstellen'));
            if (okBtn) okBtn.disabled = false;
        }
    }

    /* ══════════════════════════════════════════════════════
     * SIGNATUR PANEL
     * ══════════════════════════════════════════════════════ */
    function _initSignaturePanel() {
        document.querySelectorAll('input[name="es-sig-mode"]').forEach(radio => {
            radio.addEventListener('change', function() {
                document.querySelectorAll('.es-sig-option').forEach(el => el.classList.remove('active'));
                this.closest('.es-sig-option')?.classList.add('active');
                _updateSigPanel(this.value);
                _updateSigBlock(this.value);
                _schedulePreview();
            });
        });

        const sigFixedEl = document.getElementById('es-sig-fixed-select');
        if (sigFixedEl) {
            sigFixedEl.addEventListener('change', _schedulePreview);
        }

        const insertBtn = document.getElementById('es-sig-insert-btn');
        if (insertBtn) {
            insertBtn.addEventListener('click', _insertSignatureBlock);
        }

        const current = document.querySelector('input[name="es-sig-mode"]:checked');
        if (current) {
            _updateSigPanel(current.value);
            _updateSigBlock(current.value);
        }
        _updateSignatureBlockState();
    }

    function _hasSignatureBlock() {
        const html = document.getElementById('es-html-editor')?.value || '';
        return html.includes('{{block:signature}}') ||
               !!document.querySelector('.es-block[data-block-type="signature"]');
    }

    function _updateSignatureBlockState() {
        const has = _hasSignatureBlock();
        const hdr = document.getElementById('es-signature-section')?.querySelector('.section-header');
        if (hdr) hdr.classList.toggle('es-sig-active', has);
    }

    function _openSignaturePanel() {
        const section = document.getElementById('es-signature-section');
        const hdr = section?.querySelector('.section-header');
        if (hdr && !hdr.classList.contains('open')) hdr.click();
        section?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    function _insertSignatureBlock() {
        if (_hasSignatureBlock()) {
            _openSignaturePanel();
            return;
        }
        if (_currentMode === 'visual') {
            const canvas = document.getElementById('es-canvas');
            const sigBlock = _createBlock('signature');
            if (sigBlock && canvas) {
                canvas.appendChild(sigBlock);
                _bindBlock(sigBlock);
                _syncCanvasToCode();
            }
        } else {
            _insertAtCursor('{{block:signature}}');
        }
        _updateSigBlock(document.querySelector('input[name="es-sig-mode"]:checked')?.value || 'USER');
        _updateSignatureBlockState();
        _schedulePreview();
        _openSignaturePanel();
    }

    function _updateSigPanel(mode) {
        const fixedSel = document.getElementById('es-sig-fixed-select-wrap');
        const dynHint  = document.getElementById('es-sig-dynamic-hint');
        const preview  = document.getElementById('es-sig-preview');

        if (fixedSel) fixedSel.style.display = mode === 'FIXED'   ? '' : 'none';
        if (dynHint)  dynHint.style.display  = mode === 'DYNAMIC' ? '' : 'none';

        if (preview) {
            const map = {
                NONE:    '',
                TEAM:    'Mit freundlichen Grüßen<br><br><strong>Ihr abcona e. K. Team</strong>'
                         + '<br><span style="color:#888;font-size:10px;">'
                         + 'info@abcona.de · +49 0 6171 8867 10</span>',
                USER:    'Mit freundlichen Grüßen<br><strong>{sender_name}</strong><br>{sender_email}',
                FIXED:   t('sig_fixed', 'Feste Signatur — Auswahl oben'),
                DYNAMIC: t('sig_dynamic', 'Beim Versand wählbar'),
            };
            preview.innerHTML = map[mode] || '';
            preview.style.display = mode !== 'NONE' ? '' : 'none';
        }
    }

    function _updateSigBlock(mode) {
        const sigBlock = document.querySelector('.es-block[data-block-type="signature"]');
        if (!sigBlock) return;
        const inner = sigBlock.querySelector('.es-block-sig-inner');
        if (!inner) return;

        if (mode === 'NONE') {
            sigBlock.style.display = 'none';
            return;
        }
        sigBlock.style.display = '';

        const label = inner.querySelector('.es-block-sig-label');
        const modeLabel = t('sig_' + mode.toLowerCase(), mode);
        if (label) {
            label.innerHTML = `<i class="bi bi-pen"></i> ${t('signature_title', 'Signatur')} — ${modeLabel}`;
        }

        const content = inner.querySelector('.es-sig-content');
        if (content) {
            const map = {
                TEAM:    'Mit freundlichen Grüßen<br><br><strong>Ihr abcona e. K. Team</strong>'
                         + '<br><span style="color:#888">info@abcona.de · +49 0 6171 8867 10</span>',
                USER:    'Mit freundlichen Grüßen<br><strong>{sender_name}</strong><br><span style="color:#888">{sender_email}</span>',
                FIXED:   'Mit freundlichen Grüßen<br><strong>{signature_name}</strong>',
                DYNAMIC: '{signature}',
            };
            content.innerHTML = map[mode] || '';
        }
    }

    /* ══════════════════════════════════════════════════════
     * SPEICHERN
     * ══════════════════════════════════════════════════════ */
    function _initSave() {
        const btn = document.getElementById('es-save-btn');
        if (!btn) return;
        btn.addEventListener('click', async function() {
            if (_currentEntity === 'module') {
                await _saveModuleEntity();
                return;
            }
            if (_currentEntity === 'signature') {
                await _saveSignatureEntity();
                return;
            }

            const isNew    = this.dataset.isNew === 'true';
            const editLang = window.ES_CONFIG?.editLang || '';
            const note     = document.getElementById('es-change-note')?.value || '';

            _syncAllToCode();

            const sigModeEl = document.querySelector('input[name="es-sig-mode"]:checked');
            const sigFixedEl = document.getElementById('es-sig-fixed-select');

            const data = {
                identifier:    document.getElementById('es-identifier-input')?.value || '',
                name:          document.getElementById('es-name-input')?.value       || '',
                subject:       document.getElementById('es-subject-input')?.value    || '',
                html_body:     document.getElementById('es-html-editor')?.value      || '',
                text_body:     document.getElementById('es-txt-editor')?.value       || '',
                sender_mode:   document.querySelector('.es-mode-btn.active')?.dataset.mode || 'TEMPLATE',
                app_scope:     document.querySelector('select[name="app_scope"]')?.value   || 'general',
                status:        document.querySelector('select[name="status"]')?.value      || 'DRAFT',
                change_note:   note,
                signature_mode: sigModeEl ? sigModeEl.value : 'USER',
                include_signature: sigModeEl ? sigModeEl.value !== 'NONE' : true,
            };

            if (sigModeEl?.value === 'FIXED' && sigFixedEl?.value) {
                data.signature_id = sigFixedEl.value;
            }

            if (isNew && !data.identifier) {
                document.getElementById('es-identifier-input')?.focus();
                ES.notify.error('es.error_save', t('error_save', 'Identifier fehlt'));
                return;
            }

            try {
                if (editLang) {
                    await fetch(
                        `/email-studio/api/templates/${_templateId}/translation/${editLang}/`,
                        {
                            method:  'PUT',
                            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': ES.csrf() },
                            body:    JSON.stringify({
                                subject:         data.subject,
                                html_body:       data.html_body,
                                text_body:       data.text_body,
                                reviewed:        true,
                                auto_translated: false,
                            })
                        }
                    );
                    ES.notify.success('es.saved', t('saved', 'Gespeichert'));
                    setTimeout(() => { location.href = `/email-studio/studio/?template=${_templateId}`; }, 800);

                } else if (isNew) {
                    const result = await ES.api.post(ES.apiUrl('templates/'), data);
                    ES.notify.success('es.saved', t('saved', 'Gespeichert'));
                    setTimeout(() => { location.href = `/email-studio/studio/?template=${result.template.id}`; }, 800);

                } else {
                    await ES.api.put(ES.apiUrl(`templates/${_templateId}/`), data);
                    ES.notify.success('es.saved', t('saved', 'Gespeichert'));
                    _takeUndoSnapshot();
                    _loadVersionsBar();
                    setTimeout(() => location.reload(), 800);
                }
            } catch(err) {
                console.error('Speichern fehlgeschlagen:', err);
                ES.notify.error('es.error_save', t('error_save', 'Fehler beim Speichern'));
            }
        });
    }

    /* ══════════════════════════════════════════════════════
     * TEST SENDEN
     * ══════════════════════════════════════════════════════ */
    function _initTestSend() {
        const btns = document.querySelectorAll('.es-test-send-trigger');
        btns.forEach(btn => {
            btn.addEventListener('click', async () => {
                if (!_templateId) return;
                const inp       = document.getElementById('es-test-recipient');
                const recipient = inp?.value?.trim() || prompt(t('test_recipient', 'Empfänger E-Mail:'), '') || '';
                if (!recipient) return;
                if (inp) inp.value = recipient;
                await _doTestSend(recipient);
            });
        });
    }

    async function _doTestSend(recipient) {
        try {
            await ES.api.post(
                ES.apiUrl(`templates/${_templateId}/send-test/`),
                { recipient, variables: _collectTestVars() }
            );
            ES.notify.success('es.test_sent', t('test_sent', 'Test gesendet'));
        } catch(err) {
            ES.notify.error('es.error_test_send', t('error_test_send', 'Fehler beim Test-Versand'));
        }
    }

    /* ══════════════════════════════════════════════════════
     * ÜBERSETZUNGS-MODUS MARKER
     * ══════════════════════════════════════════════════════ */
    function _markTranslationMode(lang) {
        const saveBtn = document.getElementById('es-save-btn');
        if (!saveBtn) return;
        const badge = document.createElement('span');
        badge.className   = 'es-badge es-badge-blue';
        badge.style.marginRight = '6px';
        badge.innerHTML   = `<i class="bi bi-translate"></i> ${lang.toUpperCase()} ${t('translation_suffix', 'Übersetzung')}`;
        saveBtn.parentNode.insertBefore(badge, saveBtn);
    }

    /* ══════════════════════════════════════════════════════
     * i18n auf Canvas anwenden (bei Sprachwechsel)
     * ══════════════════════════════════════════════════════ */
    function _applyI18nToCanvas() {
        const addBtn = document.getElementById('es-add-block-btn');
        if (addBtn) {
            const span = addBtn.querySelector('[data-i18n="es.add_block"]');
            if (span) span.textContent = t('add_block', 'Abschnitt hinzufügen');
        }
    }

    /* ══════════════════════════════════════════════════════
     * HILFSFUNKTIONEN
     * ══════════════════════════════════════════════════════ */
    function _esc(str) {
        if (!str) return '';
        return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    function _formatDate(iso) {
        if (!iso) return '';
        try {
            const d = new Date(iso);
            const today = new Date();
            if (d.toDateString() === today.toDateString()) {
                return t('today', 'heute') + ' ' + d.toLocaleTimeString('de-DE', {hour:'2-digit',minute:'2-digit'});
            }
            return d.toLocaleDateString('de-DE', {day:'2-digit',month:'2-digit'}) + ' ' +
                   d.toLocaleTimeString('de-DE', {hour:'2-digit',minute:'2-digit'});
        } catch(e) { return iso; }
    }

    /* ── Save As ── */
    async function _saveAs() {
        const name = document.getElementById('es-saveas-name')?.value.trim();
        const identifier = document.getElementById('es-saveas-id')?.value.trim();
        if (!name || !identifier) {
            ES.notify.error('es.error_save', t('error_save', 'Name und Identifier erforderlich'));
            return;
        }
        if (_currentMode === 'visual' && _currentEntity === 'template') _syncCanvasToCode();
        if (_currentMode === 'html-editor') _syncRichToCode();
        const data = {
            identifier,
            name,
            subject:       document.getElementById('es-subject-input')?.value || '',
            html_body:     document.getElementById('es-html-editor')?.value   || '',
            text_body:     document.getElementById('es-txt-editor')?.value    || '',
            sender_mode:   document.querySelector('.es-mode-btn.active')?.dataset.mode || 'TEMPLATE',
            app_scope:     document.querySelector('select[name="app_scope"]')?.value   || 'general',
            status:        'DRAFT',
        };
        try {
            const result = await ES.api.post(ES.apiUrl('templates/'), data);
            ES.notify.success('es.saved', t('saved', 'Gespeichert'));
            document.getElementById('es-saveas-wrap')?.classList.remove('show');
            setTimeout(() => { location.href = `/email-studio/studio/?template=${result.template.id}`; }, 800);
        } catch(err) {
            ES.notify.error('es.error_save', t('error_save', 'Fehler'));
        }
    }

    /* ── Public API ── */
    return {
        init,
        applyWizardResult,
        _loadPreview,
        _syncCanvasToCode,
        _syncCodeToCanvas,
        _loadVersionsBar,
        saveAs: function() { _saveAs(); },
        showPanel: function(which) {
            if (which === 'mods') {
                _loadModules();
            }
        },
        autoTranslate:  async function() {
            if (!_templateId) return;
            try {
                const tplLangs = await _getTemplateLangs();
                if (!tplLangs.length) { ES.notify.warning('es.saved', t('milestone_error','Keine Sprachen konfiguriert')); return; }
                const r = await fetch(`/email-studio/api/templates/${_templateId}/translate/`,
                    { method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':ES.csrf()},
                      body: JSON.stringify({langs: tplLangs, force: false}) });
                const d = await r.json();
                if (d.success) { ES.notify.success('es.saved','Übersetzt'); setTimeout(()=>location.reload(),1000); }
                else           { ES.notify.error('es.error_save', d.error||'Fehler'); }
            } catch(e) { ES.notify.error('es.error_save','Fehler'); }
        },
        manageLangs:    async function() {
            const panel = document.getElementById('es-lang-config');
            if (!panel) return;
            panel.style.display = panel.style.display !== 'none' ? 'none' : '';
            if (panel.style.display !== 'none') {
                await _langLoadInstalled();
                await _langLoadAvailable();
            }
        },
        translateLang:  async function(lang) {
            if (!_templateId) return;
            try {
                await fetch(`/email-studio/api/templates/${_templateId}/translate/`,
                    {method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':ES.csrf()},
                     body:JSON.stringify({langs:[lang],force:true})});
                ES.notify.success('es.saved',`${lang.toUpperCase()} übersetzt`);
                setTimeout(()=>location.reload(),800);
            } catch(e) { ES.notify.error('es.error_save','Fehler'); }
        },
        deleteLang:     async function(lang) {
            if (!_templateId) return;
            if (!ES.confirm('es.confirm_delete_sig',`${lang.toUpperCase()} löschen?`)) return;
            try {
                await fetch(`/email-studio/api/templates/${_templateId}/translation/${lang}/`,
                    {method:'DELETE',headers:{'X-CSRFToken':ES.csrf()}});
                ES.notify.success('es.deleted','Gelöscht');
                setTimeout(()=>location.reload(),800);
            } catch(e) { ES.notify.error('es.error_delete','Fehler'); }
        },
        toggleLang:     async function(lang, enabled) {
            if (!_templateId) return;
            try {
                await fetch(`/email-studio/api/templates/${_templateId}/set-langs/`,
                    {method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':ES.csrf()},
                     body:JSON.stringify({lang,enabled})});
                ES.notify.success('es.saved',`${lang.toUpperCase()} ${enabled?'aktiviert':'deaktiviert'}`);
            } catch(e) { ES.notify.error('es.error_save','Fehler'); }
        },
    };

    async function _getTemplateLangs() {
        if (!_templateId) return [];
        try {
            const r = await fetch(`/email-studio/api/templates/${_templateId}/`);
            const d = await r.json();
            return d.template?.translation_languages || [];
        } catch(e) { return []; }
    }

    async function _langLoadInstalled() {
        const container = document.getElementById('es-lang-list');
        if (!container) return;
        try {
            const r     = await fetch('/api/languages/list/');
            const data  = await r.json();
            const langs = (data.languages || []).filter(l => l.code !== 'de');
            const tplLangs = await _getTemplateLangs();
            container.innerHTML = langs.map(l => `
                <label style="display:inline-flex;align-items:center;gap:5px;font-size:11px;cursor:pointer;
                    background:${tplLangs.includes(l.code)?'#e6f1fb':'white'};
                    border:${tplLangs.includes(l.code)?'1px solid var(--abcona-blue)':'1px solid var(--border-color)'};
                    border-radius:5px;padding:4px 9px;">
                    <input type="checkbox" data-lang="${l.code}" ${tplLangs.includes(l.code)?'checked':''}
                           onchange="ESStudio.toggleLang('${l.code}',this.checked)">
                    <strong>${l.code.toUpperCase()}</strong> ${l.native||l.name}
                </label>`).join('');
        } catch(e) { console.error(e); }
    }

    async function _langLoadAvailable() {
        const sel = document.getElementById('es-lang-add-select');
        if (!sel) return;
        try {
            const r    = await fetch('/api/languages/available/');
            const data = await r.json();
            sel.innerHTML = `<option value="">${t('lang_select_placeholder','— Sprache wählen —')}</option>` +
                (data.languages||[]).map(l=>`<option value="${l.code}">${l.flag||''} ${l.name} (${l.code.toUpperCase()})</option>`).join('');
        } catch(e) { console.error(e); }
    }

})();

document.addEventListener('DOMContentLoaded', function() {
    if (typeof ES !== 'undefined' && ES.api) {
        ESStudio.init();
    } else {
        let attempts = 0;
        const wait = setInterval(function() {
            attempts++;
            if (typeof ES !== 'undefined' && ES.api) {
                clearInterval(wait);
                ESStudio.init();
            } else if (attempts > 20) {
                clearInterval(wait);
                console.error('ES core nie geladen');
            }
        }, 50);
    }
});
