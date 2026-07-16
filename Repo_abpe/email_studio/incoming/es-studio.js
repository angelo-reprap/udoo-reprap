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
    let _previewSeq   = 0;
    let _currentEntity = 'template'; // template | module | signature
    let _currentMode  = 'visual';  // visual | html-editor | code | txt-editor
    let _txtRawMode   = false;
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
        _initTxtEditor();
        _initVarChips();
        _initModuleChips();
        _initSave();
        _initTestSend();
        _initVersionsBar();
        _initUndoRedo();
        _initMilestone();
        _initSignaturePanel();
        _initRestorePopup();
        _initPreviewRefresh();

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
            _applyI18nToCanvas();
        });

        console.log('ES Studio initialisiert, Template:', _templateId);
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
        const snap = _getEditorSnapshot();
        const html = snap.html;
        const txt  = snap.txt;
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

        let deferPreview = false;

        if (entity === 'template') {
            const c = _entityCache.template;
            if (c) {
                const htmlEl = document.getElementById('es-html-editor');
                const txtEl  = document.getElementById('es-txt-editor');
                if (htmlEl) htmlEl.value = c.html;
                if (txtEl)  txtEl.value  = c.text;
                _syncEditorsFromCode();
            }
        } else if (entity === 'module') {
            const c = _entityCache.module;
            const modSel = document.getElementById('es-entity-module-select');
            const selId = modSel?.value ? parseInt(modSel.value, 10) : null;
            if (c.id) {
                _applyEntityToEditors(c);
                _fillModuleMeta(c);
                if (modSel && c.id) modSel.value = String(c.id);
            } else if (selId) {
                deferPreview = true;
                void _loadModuleEntity(selId);
            } else {
                _clearEditors();
                _clearModuleMeta();
            }
        } else if (entity === 'signature') {
            const c = _entityCache.signature;
            const sigSel = document.getElementById('es-entity-signature-select');
            const selId = sigSel?.value ? parseInt(sigSel.value, 10) : null;
            if (c.id) {
                _applyEntityToEditors(c);
                _fillSignatureMeta(c);
                if (sigSel && c.id) sigSel.value = String(c.id);
            } else if (selId) {
                deferPreview = true;
                void _loadSignatureEntity(selId);
            } else {
                _clearEditors();
                _clearSignatureMeta();
            }
        }

        _updateModePanels();
        _updateSaveButtonLabel();
        _updateEntityMetaVisibility();
        if (!deferPreview) {
            setTimeout(_loadPreview, 100);
        }
    }

    /** Aktiven Entity-Tab aus DOM lesen (Fallback falls State desync) */
    function _getActiveEntity() {
        const tab = document.querySelector('.es-entity-tab.active');
        const dom = tab?.dataset?.entity;
        if (dom && dom !== _currentEntity) {
            _currentEntity = dom;
        }
        return _currentEntity;
    }

    /** Inhalt aus dem gerade sichtbaren Editor — nicht aus veralteter Textarea */
    function _getEditorSnapshot() {
        if (_currentMode === 'html-editor') {
            const rich = document.getElementById('es-rich-editor');
            if (rich) {
                const html = _sanitizeEmailHtml(_restorePlaceholdersFromRich(rich.innerHTML));
                const txt  = document.getElementById('es-txt-editor')?.value || '';
                return { html, txt };
            }
        }
        if (_currentMode === 'visual' && _currentEntity === 'template') {
            _syncCanvasToCode();
        } else if (_currentMode === 'html-editor') {
            _syncRichToCode();
        }
        return {
            html: document.getElementById('es-html-editor')?.value || '',
            txt:  document.getElementById('es-txt-editor')?.value  || '',
        };
    }

    function _updateSaveButtonLabel() {
        const lbl = document.querySelector('#es-save-btn span');
        if (!lbl) return;
        if (_currentEntity === 'module') {
            const key = _entityCache.module.id ? 'btn_save_module' : 'btn_create_module';
            lbl.textContent = t(key, _entityCache.module.id ? 'Modul speichern' : 'Modul anlegen');
            return;
        }
        if (_currentEntity === 'signature') {
            const key = _entityCache.signature.id ? 'btn_save_signature' : 'btn_create_signature';
            lbl.textContent = t(key, _entityCache.signature.id ? 'Signatur speichern' : 'Signatur anlegen');
            return;
        }
        lbl.textContent = t('btn_save', 'Speichern');
    }

    function _slugify(text) {
        return (text || '')
            .toLowerCase()
            .replace(/ä/g, 'ae').replace(/ö/g, 'oe').replace(/ü/g, 'ue').replace(/ß/g, 'ss')
            .replace(/[^a-z0-9]+/g, '_')
            .replace(/^_+|_+$/g, '')
            .slice(0, 80);
    }

    function _fillModuleMeta(data) {
        const nameEl = document.getElementById('es-entity-module-name');
        const idEl   = document.getElementById('es-entity-module-identifier');
        const typeEl = document.getElementById('es-entity-module-type');
        if (nameEl) nameEl.value = data?.name || '';
        if (idEl)   idEl.value   = data?.identifier || '';
        if (typeEl && data?.module_type) typeEl.value = data.module_type;
    }

    function _readModuleMeta() {
        if (_entityCache.module.id) {
            return {
                name: _entityCache.module.name,
                identifier: _entityCache.module.identifier,
                module_type: _entityCache.module.module_type || 'SECTION',
            };
        }
        const name = document.getElementById('es-entity-module-name')?.value?.trim() || '';
        let identifier = document.getElementById('es-entity-module-identifier')?.value?.trim() || '';
        if (!identifier && name) identifier = _slugify(name);
        return {
            name,
            identifier,
            module_type: document.getElementById('es-entity-module-type')?.value || 'SECTION',
        };
    }

    function _fillSignatureMeta(data) {
        const nameEl = document.getElementById('es-entity-signature-name');
        const idEl   = document.getElementById('es-entity-signature-identifier');
        const defEl  = document.getElementById('es-entity-signature-default');
        const pubEl  = document.getElementById('es-entity-signature-public');
        const defNew = document.getElementById('es-entity-signature-default-new');
        const pubNew = document.getElementById('es-entity-signature-public-new');
        if (nameEl) nameEl.value = data?.name || '';
        if (idEl)   idEl.value   = data?.identifier || '';
        if (defEl)  defEl.checked = !!data?.is_default;
        if (pubEl)  pubEl.checked = !!data?.is_public;
        if (defNew) defNew.checked = !!data?.is_default;
        if (pubNew) pubNew.checked = !!data?.is_public;
    }

    function _readSignatureMeta() {
        if (_entityCache.signature.id) {
            return {
                name: _entityCache.signature.name,
                identifier: _entityCache.signature.identifier,
                is_default: !!document.getElementById('es-entity-signature-default')?.checked,
                is_public:  !!document.getElementById('es-entity-signature-public')?.checked,
            };
        }
        const name = document.getElementById('es-entity-signature-name')?.value?.trim() || '';
        let identifier = document.getElementById('es-entity-signature-identifier')?.value?.trim() || '';
        if (!identifier && name) identifier = _slugify(name);
        return {
            name,
            identifier,
            is_default: !!document.getElementById('es-entity-signature-default-new')?.checked,
            is_public:  !!document.getElementById('es-entity-signature-public-new')?.checked,
        };
    }

    function _clearModuleMeta() {
        _fillModuleMeta({});
        const typeEl = document.getElementById('es-entity-module-type');
        if (typeEl) typeEl.value = 'SECTION';
    }

    function _clearSignatureMeta() {
        _fillSignatureMeta({});
    }

    /** Metafelder nur bei „Neu“ (ohne ID) — Name/Identifier sonst im Dropdown */
    function _updateEntityMetaVisibility() {
        const moduleNew = _currentEntity === 'module' && !_entityCache.module.id;
        const sigNew    = _currentEntity === 'signature' && !_entityCache.signature.id;
        const sigEdit   = _currentEntity === 'signature' && !!_entityCache.signature.id;

        const modMeta = document.getElementById('es-entity-module-meta');
        const sigNewMeta  = document.getElementById('es-entity-signature-meta-new');
        const sigEditMeta = document.getElementById('es-entity-signature-meta-edit');

        if (modMeta) modMeta.style.display = moduleNew ? '' : 'none';
        if (sigNewMeta)  sigNewMeta.style.display  = sigNew ? '' : 'none';
        if (sigEditMeta) sigEditMeta.style.display = sigEdit ? '' : 'none';
    }

    function _applyEntityToEditors(data) {
        const htmlEl = document.getElementById('es-html-editor');
        const txtEl  = document.getElementById('es-txt-editor');
        if (htmlEl) htmlEl.value = data.html || data.html_body || '';
        if (txtEl)  txtEl.value  = data.text || data.text_body || '';
        _syncEditorsFromCode();
    }

    function _clearEditors() {
        const htmlEl = document.getElementById('es-html-editor');
        const txtEl  = document.getElementById('es-txt-editor');
        const rich   = document.getElementById('es-rich-editor');
        if (htmlEl) htmlEl.value = '';
        if (txtEl)  txtEl.value  = '';
        if (rich)   rich.innerHTML = '';
        if (_currentMode === 'visual' && _currentEntity !== 'template') {
            _updateEntityVisual();
        }
    }

    /** Textarea → Rich-Editor / Entity-Visual nach Laden oder Wechsel */
    function _syncEditorsFromCode() {
        if (_currentMode === 'html-editor') {
            _syncCodeToRich();
        }
        if (_currentMode === 'visual' && _currentEntity !== 'template') {
            _updateEntityVisual();
        }
    }

    async function _initEntitySelectors() {
        const modSel = document.getElementById('es-entity-module-select');
        const sigSel = document.getElementById('es-entity-signature-select');

        modSel?.addEventListener('change', async function() {
            const id = parseInt(this.value, 10);
            if (!id) {
                _entityCache.module = { id: null, html: '', text: '', identifier: '', name: '' };
                _clearEditors();
                _clearModuleMeta();
                _updateSaveButtonLabel();
                _updateEntityMetaVisibility();
                _loadPreview(false);
                return;
            }
            await _loadModuleEntity(id);
        });

        sigSel?.addEventListener('change', async function() {
            const id = parseInt(this.value, 10);
            if (!id) {
                _entityCache.signature = { id: null, html: '', text: '', identifier: '', name: '' };
                _clearEditors();
                _clearSignatureMeta();
                _updateSaveButtonLabel();
                _updateEntityMetaVisibility();
                _loadPreview(false);
                return;
            }
            await _loadSignatureEntity(id);
        });

        await _refreshModuleSelect();
        await _refreshSignatureSelect();
        await _loadModuleTypes();
    }

    async function _loadModuleTypes() {
        const typeEl = document.getElementById('es-entity-module-type');
        if (!typeEl) return;
        try {
            const data = await ES.api.get(ES.apiUrl('modules/'));
            const types = data.types || [];
            if (!types.length) return;
            typeEl.innerHTML = types.map(([val, label]) =>
                `<option value="${val}">${label || val}</option>`
            ).join('');
        } catch (e) {
            console.warn('Modul-Typen laden:', e);
        }
    }

    async function _loadModuleEntity(id) {
        try {
            const data = await ES.api.get(ES.apiUrl(`modules/${id}/`));
            _entityCache.module = {
                id, html: data.html_body, text: data.text_body,
                identifier: data.identifier, name: data.name,
                module_type: data.module_type,
            };
            _applyEntityToEditors(_entityCache.module);
            _fillModuleMeta(data);
            const modSel = document.getElementById('es-entity-module-select');
            if (modSel) modSel.value = String(id);
            _updateSaveButtonLabel();
            _updateEntityMetaVisibility();
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

    async function _refreshSignatureSelect(selectedId) {
        const sigSel = document.getElementById('es-entity-signature-select');
        if (!sigSel) return;
        try {
            const data = await ES.api.get(ES.apiUrl('signatures/'));
            const sigs = data.signatures || [];
            let opts = `<option value="">${t('entity_select_placeholder', '— Bitte wählen —')}</option>`;
            for (const s of sigs) {
                const sel = selectedId && String(s.id) === String(selectedId) ? ' selected' : '';
                opts += `<option value="${s.id}"${sel}>${s.name} (${s.identifier})</option>`;
            }
            sigSel.innerHTML = opts;
        } catch (e) {
            console.error('Signatur-Liste aktualisieren fehlgeschlagen:', e);
        }
    }

    function _initEntityActions() {
        document.getElementById('es-entity-module-new')?.addEventListener('click', _resetNewModule);
        document.getElementById('es-entity-module-dup')?.addEventListener('click', () => _duplicateModule());
        document.getElementById('es-entity-module-del')?.addEventListener('click', () => _deleteModule());
        document.getElementById('es-entity-signature-new')?.addEventListener('click', _resetNewSignature);
        document.getElementById('es-entity-signature-dup')?.addEventListener('click', () => _duplicateSignature());
        document.getElementById('es-entity-signature-del')?.addEventListener('click', () => _deleteSignature());

        document.getElementById('es-entity-module-name')?.addEventListener('input', function() {
            const idEl = document.getElementById('es-entity-module-identifier');
            if (idEl && !idEl.value.trim()) {
                idEl.placeholder = _slugify(this.value) || t('label_identifier', 'identifier');
            }
        });
        document.getElementById('es-entity-signature-name')?.addEventListener('input', function() {
            const idEl = document.getElementById('es-entity-signature-identifier');
            if (idEl && !idEl.value.trim()) {
                idEl.placeholder = _slugify(this.value) || t('label_identifier', 'identifier');
            }
        });
    }

    function _resetNewModule() {
        _entityCache.module = { id: null, html: '', text: '', identifier: '', name: '' };
        const modSel = document.getElementById('es-entity-module-select');
        if (modSel) modSel.value = '';
        _clearModuleMeta();
        _clearEditors();
        _updateSaveButtonLabel();
        _updateEntityMetaVisibility();
        document.getElementById('es-entity-module-name')?.focus();
        _loadPreview(false);
    }

    function _resetNewSignature() {
        _entityCache.signature = { id: null, html: '', text: '', identifier: '', name: '' };
        const sigSel = document.getElementById('es-entity-signature-select');
        if (sigSel) sigSel.value = '';
        _clearSignatureMeta();
        _clearEditors();
        _updateSaveButtonLabel();
        _updateEntityMetaVisibility();
        document.getElementById('es-entity-signature-name')?.focus();
        _loadPreview(false);
    }

    async function _duplicateModule() {
        const snap = _getEditorSnapshot();
        const meta = _readModuleMeta();
        if (!meta.name) {
            ES.notify.error('es.error_save', t('entity_name_required', 'Anzeigename ist Pflicht'));
            return;
        }
        const payload = {
            name: `${meta.name} (Kopie)`,
            identifier: `${meta.identifier || _slugify(meta.name)}_copy`,
            module_type: meta.module_type,
            html_body: snap.html,
            text_body: snap.txt,
        };
        try {
            const r = await fetch(ES.apiUrl('modules/'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': ES.csrf() },
                body: JSON.stringify(payload),
            });
            const data = await r.json().catch(() => ({}));
            if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
            await _refreshModuleSelect(data.id);
            await _loadModuleEntity(data.id);
            ES.notify.success('es.module_saved', t('entity_saveas_ok', 'Als Kopie gespeichert'));
            _loadModules(true);
        } catch (e) {
            ES.notify.error('es.error_save', e.message || t('error_save', 'Fehler'));
        }
    }

    async function _duplicateSignature() {
        const snap = _getEditorSnapshot();
        const meta = _readSignatureMeta();
        if (!meta.name) {
            ES.notify.error('es.error_save', t('entity_name_required', 'Anzeigename ist Pflicht'));
            return;
        }
        const payload = {
            name: `${meta.name} (Kopie)`,
            identifier: `${meta.identifier || _slugify(meta.name)}_copy`,
            html_body: snap.html,
            text_body: snap.txt,
            is_default: false,
            is_public: meta.is_public,
        };
        try {
            const r = await fetch(ES.apiUrl('signatures/'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': ES.csrf() },
                body: JSON.stringify(payload),
            });
            const data = await r.json().catch(() => ({}));
            if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
            await _refreshSignatureSelect(data.id);
            await _loadSignatureEntity(data.id);
            ES.notify.success('es.sig_saved', t('entity_saveas_ok', 'Als Kopie gespeichert'));
        } catch (e) {
            ES.notify.error('es.error_save', e.message || t('error_save', 'Fehler'));
        }
    }

    async function _deleteModule() {
        const id = _entityCache.module.id;
        if (!id) {
            ES.notify.error('es.entity_select_module', t('entity_select_module', 'Bitte zuerst ein Modul wählen'));
            return;
        }
        if (!ES.confirm('es.entity_delete_confirm', t('entity_delete_confirm', 'Wirklich löschen?'))) return;
        try {
            const r = await fetch(ES.apiUrl(`modules/${id}/`), {
                method: 'DELETE',
                headers: { 'X-CSRFToken': ES.csrf() },
            });
            const data = await r.json().catch(() => ({}));
            if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
            _resetNewModule();
            await _refreshModuleSelect();
            ES.notify.success('es.entity_deleted', t('entity_deleted', 'Gelöscht'));
            _loadModules(true);
        } catch (e) {
            ES.notify.error('es.error_save', e.message || t('error_save', 'Fehler'));
        }
    }

    async function _deleteSignature() {
        const id = _entityCache.signature.id;
        if (!id) {
            ES.notify.error('es.entity_select_signature', t('entity_select_signature', 'Bitte zuerst eine Signatur wählen'));
            return;
        }
        if (!ES.confirm('es.entity_delete_confirm', t('entity_delete_confirm', 'Wirklich löschen?'))) return;
        try {
            const r = await fetch(ES.apiUrl(`signatures/${id}/`), {
                method: 'DELETE',
                headers: { 'X-CSRFToken': ES.csrf() },
            });
            const data = await r.json().catch(() => ({}));
            if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
            _resetNewSignature();
            await _refreshSignatureSelect();
            ES.notify.success('es.entity_deleted', t('entity_deleted', 'Gelöscht'));
        } catch (e) {
            ES.notify.error('es.error_save', e.message || t('error_save', 'Fehler'));
        }
    }

    async function _saveModuleEntity() {
        const snap = _getEditorSnapshot();
        const meta = _readModuleMeta();
        if (!meta.name || !meta.identifier) {
            ES.notify.error('es.error_save', t('entity_meta_required', 'Name und Identifier sind Pflichtfelder'));
            return;
        }

        const payload = {
            name: meta.name,
            identifier: meta.identifier,
            module_type: meta.module_type,
            html_body: snap.html,
            text_body: snap.txt,
        };

        const id = _entityCache.module.id;
        const url    = id ? ES.apiUrl(`modules/${id}/`) : ES.apiUrl('modules/');
        const method = id ? 'PUT' : 'POST';

        try {
            const r = await fetch(url, {
                method,
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': ES.csrf(),
                },
                body: JSON.stringify(payload),
            });
            const data = await r.json().catch(() => ({}));
            if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);

            const newId = data.id || id;
            _entityCache.module = {
                id: newId,
                html: payload.html_body,
                text: payload.text_body,
                identifier: data.identifier || meta.identifier,
                name: data.name || meta.name,
                module_type: meta.module_type,
            };
            await _refreshModuleSelect(newId);
            _fillModuleMeta(_entityCache.module);
            _updateSaveButtonLabel();
            ES.notify.success('es.module_saved', t('module_saved', id ? 'Modul gespeichert' : 'Modul angelegt'));
            _loadModules(true);
        } catch (e) {
            console.error('Modul speichern fehlgeschlagen:', e);
            ES.notify.error('es.error_save', e.message || t('error_save', 'Fehler'));
        }
    }

    async function _loadSignatureEntity(id) {
        try {
            const data = await ES.api.get(ES.apiUrl(`signatures/${id}/`));
            _entityCache.signature = {
                id, html: data.html_body, text: data.text_body,
                identifier: data.identifier, name: data.name,
                is_default: data.is_default, is_public: data.is_public,
            };
            _applyEntityToEditors(_entityCache.signature);
            _fillSignatureMeta(data);
            const sigSel = document.getElementById('es-entity-signature-select');
            if (sigSel) sigSel.value = String(id);
            _updateSaveButtonLabel();
            _updateEntityMetaVisibility();
            if (_currentEntity === 'signature') {
                _updateModePanels();
                _loadPreview(false);
            }
        } catch (e) {
            console.error('Signatur laden fehlgeschlagen:', e);
            ES.notify.error('es.error_load_sig', 'Signatur konnte nicht geladen werden');
        }
    }

    async function _saveSignatureEntity() {
        const snap = _getEditorSnapshot();
        const meta = _readSignatureMeta();
        if (!meta.name || !meta.identifier) {
            ES.notify.error('es.error_save', t('entity_meta_required', 'Name und Identifier sind Pflichtfelder'));
            return;
        }

        const payload = {
            name: meta.name,
            identifier: meta.identifier,
            html_body: snap.html,
            text_body: snap.txt,
            is_default: meta.is_default,
            is_public: meta.is_public,
        };

        const id = _entityCache.signature.id;
        const url    = id ? ES.apiUrl(`signatures/${id}/`) : ES.apiUrl('signatures/');
        const method = id ? 'PUT' : 'POST';

        try {
            const r = await fetch(url, {
                method,
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': ES.csrf(),
                },
                body: JSON.stringify(payload),
            });
            const data = await r.json().catch(() => ({}));
            if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);

            const newId = data.id || id;
            _entityCache.signature = {
                id: newId,
                html: payload.html_body,
                text: payload.text_body,
                identifier: meta.identifier,
                name: meta.name,
                is_default: meta.is_default,
                is_public: meta.is_public,
            };
            await _refreshSignatureSelect(newId);
            _fillSignatureMeta(_entityCache.signature);
            _updateSaveButtonLabel();
            ES.notify.success('es.sig_saved', t('sig_saved', id ? 'Signatur gespeichert' : 'Signatur angelegt'));
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

        setTimeout(_loadPreview, 100);
    }

    function _initTxtEditor() {
        document.getElementById('es-txt-raw-toggle')?.addEventListener('click', _toggleTxtRaw);
    }

    function _toggleTxtRaw() {
        _txtRawMode = !_txtRawMode;
        const ta  = document.getElementById('es-txt-editor');
        const btn = document.getElementById('es-txt-raw-toggle');
        if (!ta) return;
        ta.classList.toggle('es-txt-friendly', !_txtRawMode);
        ta.classList.toggle('es-code-textarea', _txtRawMode);
        btn?.classList.toggle('active', _txtRawMode);
    }

    function _updateModePanels() {
        const mode   = _currentMode;
        const entity = _currentEntity;

        const visualWrap     = document.getElementById('es-wysiwyg-wrap');
        const entityVisual   = document.getElementById('es-entity-visual-wrap');
        const htmlEditorWrap = document.getElementById('es-html-editor-wrap');
        const codeWrap       = document.getElementById('es-code-wrap');
        const txtWrap        = document.getElementById('es-txt-editor-wrap');

        if (visualWrap)     visualWrap.style.display     = (mode === 'visual' && entity === 'template') ? '' : 'none';
        if (entityVisual)   entityVisual.style.display   = (mode === 'visual' && entity !== 'template') ? '' : 'none';
        if (htmlEditorWrap) htmlEditorWrap.style.display   = mode === 'html-editor' ? '' : 'none';
        if (codeWrap)       codeWrap.style.display         = mode === 'code' ? '' : 'none';
        if (txtWrap)        txtWrap.style.display          = mode === 'txt-editor' ? '' : 'none';

        if (mode === 'visual' && entity !== 'template') {
            _updateEntityVisual();
        }
    }

    function _updateEntityVisual() {
        const body = document.getElementById('es-entity-visual-body');
        if (!body) return;
        const html = _getEditorSnapshot().html;
        body.innerHTML = html ? _applyDummyVarsLocal(html) : `<p style="color:#999;padding:20px;">${t('entity_visual_empty', 'Kein Inhalt — HTML-Code oder HTML-Editor verwenden')}</p>`;
    }

    function _syncCodeToRich() {
        const code = document.getElementById('es-html-editor')?.value || '';
        const rich = document.getElementById('es-rich-editor');
        if (rich) rich.innerHTML = _protectPlaceholdersForRich(code);
    }

    function _syncRichToCode() {
        const rich = document.getElementById('es-rich-editor');
        const htmlEl = document.getElementById('es-html-editor');
        if (!rich || !htmlEl) return;
        let html = _restorePlaceholdersFromRich(rich.innerHTML);
        html = _sanitizeEmailHtml(html);
        htmlEl.value = html;
    }

    /** {{block:x}} als geschützte Chips — {variablen} in Attributen bleiben unberührt */
    function _protectPlaceholdersForRich(html) {
        if (!html) return '';
        return html.replace(
            /\{\{block:([a-zA-Z0-9_]+)\}\}/g,
            '<span class="es-rich-block-token" contenteditable="false" data-syntax="{{block:$1}}">{{block:$1}}</span>'
        );
    }

    function _restorePlaceholdersFromRich(html) {
        if (!html) return '';
        const tmp = document.createElement('div');
        tmp.innerHTML = html;
        tmp.querySelectorAll('.es-rich-block-token').forEach(el => {
            el.replaceWith(document.createTextNode(el.dataset.syntax || el.textContent));
        });
        return tmp.innerHTML;
    }

    const _EMAIL_ALLOWED_TAGS = new Set([
        'P', 'BR', 'STRONG', 'B', 'EM', 'I', 'A', 'UL', 'OL', 'LI',
        'TABLE', 'TBODY', 'THEAD', 'TR', 'TD', 'TH', 'DIV', 'SPAN',
        'H1', 'H2', 'H3', 'H4', 'IMG', 'FONT',
    ]);
    const _EMAIL_ALLOWED_ATTRS = {
        A:    ['href', 'style', 'target'],
        IMG:  ['src', 'alt', 'width', 'height', 'style'],
        FONT: ['color', 'face', 'size', 'style'],
        '*':  ['style', 'class', 'colspan', 'rowspan', 'width', 'cellpadding', 'cellspacing', 'border', 'align'],
    };

    function _sanitizeEmailHtml(html) {
        if (!html) return '';
        const doc = new DOMParser().parseFromString(`<div id="es-sanitize-root">${html}</div>`, 'text/html');
        const root = doc.getElementById('es-sanitize-root');
        if (!root) return html;

        function clean(node) {
            Array.from(node.childNodes).forEach(child => {
                if (child.nodeType === Node.COMMENT_NODE) {
                    child.remove();
                    return;
                }
                if (child.nodeType === Node.TEXT_NODE) return;
                if (child.nodeType !== Node.ELEMENT_NODE) {
                    child.remove();
                    return;
                }
                const tag = child.tagName;
                if (!_EMAIL_ALLOWED_TAGS.has(tag)) {
                    while (child.firstChild) child.parentNode.insertBefore(child.firstChild, child);
                    child.remove();
                    return;
                }
                Array.from(child.attributes).forEach(attr => {
                    const n = attr.name.toLowerCase();
                    if (n.startsWith('on')) {
                        child.removeAttribute(attr.name);
                        return;
                    }
                    const allowed = _EMAIL_ALLOWED_ATTRS[tag] || _EMAIL_ALLOWED_ATTRS['*'];
                    if (!allowed.includes(attr.name) && !allowed.includes(n)) {
                        child.removeAttribute(attr.name);
                    }
                });
                if (tag === 'A' && child.getAttribute('href')) {
                    const href = child.getAttribute('href');
                    if (!/^https?:\/\/|^mailto:/i.test(href)) {
                        child.removeAttribute('href');
                    }
                }
                clean(child);
            });
        }
        clean(root);
        return root.innerHTML.trim();
    }

    /** Theme-Farben aus core-theme.css (:root Light) */
    const THEME_COLORS = [
        { hex: '#163258', label: 'Abcona Blau' },
        { hex: '#0f2442', label: 'Blau dunkel' },
        { hex: '#1e4a7a', label: 'Blau hell' },
        { hex: '#1e1e1e', label: 'Text primär' },
        { hex: '#6c757d', label: 'Text sekundär' },
        { hex: '#10b981', label: 'Grün' },
        { hex: '#f59e0b', label: 'Gelb' },
        { hex: '#ef4444', label: 'Rot' },
        { hex: '#ffffff', label: 'Weiß' },
        { hex: '#333333', label: 'Dunkelgrau' },
    ];

    function _richGetBlockParent(node, root) {
        let el = node;
        if (el && el.nodeType === Node.TEXT_NODE) el = el.parentElement;
        const blocks = new Set(['P', 'DIV', 'LI', 'TD', 'TH', 'H1', 'H2', 'H3', 'H4']);
        while (el && el !== root) {
            if (blocks.has(el.tagName)) return el;
            el = el.parentElement;
        }
        return null;
    }

    /** Ausrichtung per Block-style — verhindert „verschwindende" Zeilen bei rechts */
    function _richSetBlockAlign(align) {
        const rich = document.getElementById('es-rich-editor');
        if (!rich) return;
        rich.focus();
        const sel = window.getSelection();
        if (!sel || !sel.rangeCount) return;

        let block = _richGetBlockParent(sel.anchorNode, rich);
        if (!block) {
            document.execCommand('formatBlock', false, 'p');
            block = _richGetBlockParent(sel.anchorNode, rich);
        }
        if (!block) {
            block = rich;
        }
        if (block === rich) {
            const p = document.createElement('p');
            p.style.textAlign = align;
            p.style.width = '100%';
            p.style.display = 'block';
            p.style.boxSizing = 'border-box';
            p.innerHTML = rich.innerHTML;
            rich.innerHTML = '';
            rich.appendChild(p);
        } else {
            block.style.textAlign = align;
            block.style.width = '100%';
            block.style.display = 'block';
            block.style.boxSizing = 'border-box';
            block.style.minHeight = '1em';
        }
        _syncRichToCode();
        _schedulePreview();
    }

    function _richApplyColor(hex) {
        const rich = document.getElementById('es-rich-editor');
        if (!rich) return;
        rich.focus();
        document.execCommand('foreColor', false, hex);
        _syncRichToCode();
        _schedulePreview();
    }

    function _richExecCmd(cmd, value) {
        const rich = document.getElementById('es-rich-editor');
        if (!rich) return;
        rich.focus();
        if (cmd === 'justifyLeft' || cmd === 'justifyCenter' || cmd === 'justifyRight') {
            const map = { justifyLeft: 'left', justifyCenter: 'center', justifyRight: 'right' };
            _richSetBlockAlign(map[cmd]);
            return;
        }
        if (cmd === 'link') {
            const url = prompt(t('html_link_prompt', 'Link-URL:'), 'https://');
            if (url) document.execCommand('createLink', false, url);
        } else if (cmd === 'color') {
            document.execCommand('foreColor', false, value || '#163258');
        } else if (cmd === 'insertBr') {
            document.execCommand('insertHTML', false, '<br>');
        } else if (cmd === 'fontSize') {
            const sel = window.getSelection()?.toString();
            if (!sel) return;
            document.execCommand('insertHTML', false,
                `<span style="font-size:${value}">${sel}</span>`);
        } else {
            document.execCommand(cmd, false, value || null);
        }
        _syncRichToCode();
        _schedulePreview();
    }

    function _initThemeColorPopover() {
        const pop = document.getElementById('es-rich-theme-popover');
        if (!pop) return;
        pop.innerHTML = THEME_COLORS.map(c =>
            `<button type="button" class="es-rich-swatch" data-hex="${c.hex}" title="${c.label}"
                     style="background:${c.hex};${c.hex === '#ffffff' ? 'border:1px solid #ccc' : ''}"></button>`
        ).join('');
        pop.querySelectorAll('.es-rich-swatch').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                _richApplyColor(btn.dataset.hex);
                pop.style.display = 'none';
            });
        });
    }

    function _initRichEditor() {
        _initThemeColorPopover();

        document.querySelectorAll('.es-rich-btn[data-cmd]').forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                _richExecCmd(this.dataset.cmd, this.dataset.value);
            });
        });

        const themeBtn = document.getElementById('es-rich-theme-btn');
        const themePop = document.getElementById('es-rich-theme-popover');
        themeBtn?.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (!themePop) return;
            themePop.style.display = themePop.style.display === 'none' ? 'flex' : 'none';
        });

        const colorInput = document.getElementById('es-rich-color-input');
        document.getElementById('es-rich-custom-color-btn')?.addEventListener('click', (e) => {
            e.preventDefault();
            colorInput?.click();
        });
        colorInput?.addEventListener('input', () => {
            if (colorInput.value) _richApplyColor(colorInput.value);
        });

        document.addEventListener('click', (e) => {
            if (!e.target.closest('.es-rich-color-wrap')) {
                if (themePop) themePop.style.display = 'none';
            }
        });

        document.getElementById('es-rich-fontsize')?.addEventListener('change', function() {
            const sel = window.getSelection()?.toString();
            if (sel) {
                _richExecCmd('fontSize', this.value);
            } else {
                ES.notify.info('es.html_select_text', t('html_select_text', 'Text markieren, dann Schriftgröße wählen'));
            }
        });

        const rich = document.getElementById('es-rich-editor');
        if (rich) {
            rich.addEventListener('input', () => {
                _syncRichToCode();
                if (_currentEntity === 'module' || _currentEntity === 'signature') {
                    _persistEntityEditors();
                }
                _schedulePreview();
            });
            rich.addEventListener('paste', (e) => {
                e.preventDefault();
                const html  = e.clipboardData?.getData('text/html');
                const plain = e.clipboardData?.getData('text/plain') || '';
                if (html) {
                    document.execCommand('insertHTML', false, _sanitizeEmailHtml(html));
                } else {
                    document.execCommand('insertText', false, plain);
                }
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
        if (_currentEntity !== 'template') return;
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
     * VARIABLEN-CHIPS
     * ══════════════════════════════════════════════════════ */
    function _initVarChips() {
        document.querySelectorAll('.es-var-chip').forEach(chip => {
            chip.addEventListener('click', function() {
                const varName = this.dataset.var;
                const token   = `{${varName}}`;

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
                    const ta = document.getElementById('es-html-editor');
                    if (ta) {
                        const pos = ta.selectionStart;
                        ta.value  = ta.value.slice(0, pos) + token + ta.value.slice(pos);
                        ta.selectionStart = ta.selectionEnd = pos + token.length;
                        ta.focus();
                        _schedulePreview();
                    }
                }
                ES.copyToClipboard(token, this);
            });
        });
    }

    /* ══════════════════════════════════════════════════════
     * MODULE-CHIPS
     * ══════════════════════════════════════════════════════ */
    function _initModuleChips() {
        document.querySelectorAll('.es-module-chip').forEach(chip => {
            chip.addEventListener('click', function() {
                const syntax = this.dataset.syntax;
                if (!syntax) return;
                _insertAtCursor(syntax);
                ES.copyToClipboard(syntax, this);
            });
        });

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
            let html      = '';
            const typeIcons = {
                HEADER: 'bi-layout-text-window-reverse',
                FOOTER: 'bi-layout-text-window',
                BUTTON: 'bi-cursor',
                SECTION:'bi-layout-text-sidebar',
                DISCLAIMER: 'bi-info-circle',
                SIGNATURE: 'bi-pen',
            };
            for (const [type, modules] of Object.entries(grouped)) {
                if (!modules.length) continue;
                html += `<div class="es-var-group-lbl">${type}</div>`;
                for (const m of modules) {
                    html += `
                    <div class="es-module-chip" data-syntax="${m.syntax}" title="${m.description || m.name}">
                        <i class="bi ${typeIcons[type] || 'bi-puzzle'}" style="font-size:11px;color:var(--abcona-blue)"></i>
                        <span>${m.name}</span>
                    </div>`;
                }
            }
            container.innerHTML = html || `<div style="font-size:10px;color:var(--text-secondary)">Keine Module gefunden</div>`;
            container.dataset.loaded = '1';
            container.querySelectorAll('.es-module-chip').forEach(chip => {
                chip.addEventListener('click', function() {
                    const syntax = this.dataset.syntax;
                    if (syntax === '{{block:signature}}') {
                        _insertSignatureBlock();
                    } else {
                        _insertAtCursor(syntax);
                    }
                    ES.copyToClipboard(syntax, this);
                });
            });
        } catch(e) {
            console.error('Module laden fehlgeschlagen:', e);
        }
    }

    function _insertAtCursor(text) {
        if (_currentMode === 'visual') {
            const ta = document.getElementById('es-html-editor');
            if (ta) {
                const pos = ta.selectionStart;
                ta.value  = ta.value.slice(0, pos) + text + ta.value.slice(pos);
                ta.selectionStart = ta.selectionEnd = pos + text.length;
            }
        } else {
            const ta = document.getElementById('es-html-editor');
            if (!ta) return;
            const pos = ta.selectionStart;
            ta.value  = ta.value.slice(0, pos) + text + ta.value.slice(pos);
            ta.selectionStart = ta.selectionEnd = pos + text.length;
            ta.focus();
        }
        _syncCanvasToCode();
        _schedulePreview();
        if (text && text.includes('{{block:signature}}')) {
            _updateSignatureBlockState();
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
        return _currentMode === 'txt-editor' || _getActivePreviewClient() === 'txt';
    }

    async function _loadPreview(manual = false) {
        const seq = ++_previewSeq;
        const entity = _getActiveEntity();
        const snap = _getEditorSnapshot();
        const htmlBody = snap.html;
        const txtBody  = snap.txt;

        const editLang = window.ES_CONFIG?.editLang || '';
        const subject  = document.getElementById('es-subject-input')?.value || '';

        const subjEl = document.getElementById('es-preview-subject');
        const bodyEl = document.getElementById('es-preview-body');
        const refreshBtn = document.getElementById('es-preview-refresh-btn');

        if (manual && refreshBtn) refreshBtn.classList.add('es-preview-refreshing');
        if (manual && bodyEl) bodyEl.classList.add('es-preview-loading');

        /* Modul / Signatur: Client-Vorschau (immer aus Live-Editor) */
        if (entity === 'module' || entity === 'signature') {
            if (subjEl) {
                const label = entity === 'module'
                    ? (_entityCache.module.name || t('entity_module', 'Modul'))
                    : (_entityCache.signature.name || t('entity_signature', 'Signatur'));
                subjEl.textContent = label;
            }
            if (_wantsTxtPreview() && txtBody) {
                if (bodyEl) {
                    bodyEl.innerHTML = '';
                    bodyEl.className = 'es-email-sim-body es-preview-txt-mode';
                    bodyEl.textContent = _applyDummyVarsLocal(txtBody);
                }
            } else if (htmlBody) {
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

        if (_currentMode === 'txt-editor' && txtBody) {
            if (bodyEl) {
                bodyEl.innerHTML = '';
                bodyEl.className = 'es-email-sim-body es-preview-txt-mode';
                bodyEl.textContent = _applyDummyVarsLocal(txtBody);
            }
            if (manual && refreshBtn) refreshBtn.classList.remove('es-preview-refreshing');
            if (manual && bodyEl) bodyEl.classList.remove('es-preview-loading');
            return;
        }

        if (!_templateId || editLang) {
            if (htmlBody) _renderInIframe(_applyDummyVarsLocal(htmlBody));
            if (manual && refreshBtn) refreshBtn.classList.remove('es-preview-refreshing');
            if (manual && bodyEl) bodyEl.classList.remove('es-preview-loading');
            return;
        }

        try {
            const data = await ES.api.post(
                ES.apiUrl(`templates/${_templateId}/preview/`),
                _collectPreviewPayload()
            );
            if (seq !== _previewSeq) return;
            if (data.html) _renderInIframe(data.html);
            if (subjEl && data.subject) subjEl.textContent = data.subject;
            const fromEl = document.getElementById('es-preview-from');
            if (fromEl && data.from_email) fromEl.textContent = data.from_email;
        } catch(err) {
            if (seq !== _previewSeq) return;
            console.error('Vorschau fehlgeschlagen:', err);
            if (htmlBody) _renderInIframe(_applyDummyVarsLocal(htmlBody));
        } finally {
            if (seq !== _previewSeq) return;
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
        bodyEl.className = 'es-email-sim-body';
        bodyEl.style.padding = '10px';
        bodyEl.innerHTML = `<div class="es-preview-html">${safeHtml}</div>`;
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
        const badge = document.getElementById('es-sig-block-badge');
        if (badge) badge.style.display = has ? '' : 'none';
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
            if (span) span.textContent = t('add_block', 'Block hinzufügen');
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
