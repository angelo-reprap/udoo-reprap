/**
 * es-config.js — ABpE Email Studio
 * Reiter 4: SMTP Test, Absender-Konten, Signaturen (CRUD-Editor)
 */
'use strict';

window.ESConfig = (() => {

    let _sigId = null;
    let _sigPreviewMode = 'html';
    let _sigPreviewTimer = null;

    const DEFAULT_HTML = `<div style="margin-top:20px;font-family:Arial,Helvetica,sans-serif;font-size:13px;line-height:1.5;color:#333;">
  <p style="margin:0 0 4px 0;">Mit freundlichen Grüßen</p>
  <p style="margin:0 0 8px 0;"><strong>Max Mustermann</strong></p>
  <p style="margin:0;font-size:12px;">
    E-Mail: <a href="mailto:max@example.de" style="color:#163258;">max@example.de</a>
  </p>
</div>`;

    const DEFAULT_TXT = `Mit freundlichen Grüßen
Max Mustermann
max@example.de`;

    function t(key, fallback) {
        return window.i18nData?.es?.[key] || fallback;
    }

    function init() {
        _bindSmtpTest();
        _bindSenderDelete();
        _bindSignatureDelete();
        _bindSignatureEditor();
        console.log('✓ ES Config initialisiert');
    }

    /* ── SMTP Verbindungstest ── */
    function _bindSmtpTest() {
        const btn = document.getElementById('es-smtp-test-btn');
        if (!btn) return;
        btn.addEventListener('click', async function() {
            this.disabled = true;
            const statusEl = document.getElementById('es-smtp-status');
            if (statusEl) statusEl.innerHTML = '...';
            try {
                const data = await ES.api.post(ES.apiUrl('senders/test-smtp/'), {});
                if (statusEl) {
                    statusEl.className = 'es-smtp-ok';
                    statusEl.innerHTML =
                        '<i class="bi bi-check-circle"></i> ' +
                        (window.i18nData?.es?.smtp_ok || 'Verbindung OK');
                }
                console.log('SMTP Test OK:', data.message);
            } catch(err) {
                if (statusEl) {
                    statusEl.className = 'es-smtp-fail';
                    statusEl.innerHTML =
                        '<i class="bi bi-x-circle"></i> ' +
                        (window.i18nData?.es?.smtp_fail || 'Verbindung fehlgeschlagen');
                }
                console.error('SMTP Test fehlgeschlagen:', err);
            } finally {
                this.disabled = false;
            }
        });
    }

    /* ── Absender-Konto löschen ── */
    function _bindSenderDelete() {
        document.addEventListener('click', async function(e) {
            const btn = e.target.closest('[data-action="delete-sender"]');
            if (!btn) return;
            if (!ES.confirm('es.confirm_delete_sender', 'Absender-Konto löschen?')) return;
            const id = btn.dataset.id;
            try {
                await ES.api.delete(ES.apiUrl(`senders/${id}/`));
                btn.closest('[data-sender-row]')?.remove();
                ES.notify.success('es.deleted', 'Gelöscht');
            } catch(err) {
                console.error('Löschen fehlgeschlagen:', err);
                ES.notify.error('es.error_delete', 'Fehler beim Löschen');
            }
        });
    }

    /* ── Signatur löschen ── */
    function _bindSignatureDelete() {
        document.addEventListener('click', async function(e) {
            const btn = e.target.closest('[data-action="delete-signature"]');
            if (!btn) return;
            e.stopPropagation();
            if (!ES.confirm('es.confirm_delete_sig', 'Signatur löschen?')) return;
            const id = btn.dataset.id;
            try {
                await ES.api.delete(ES.apiUrl(`signatures/${id}/`));
                btn.closest('[data-sig-row]')?.remove();
                if (_sigId && String(_sigId) === String(id)) _closeEditor();
                _updateSigCount();
                ES.notify.success('es.deleted', 'Gelöscht');
            } catch(err) {
                console.error('Löschen fehlgeschlagen:', err);
                ES.notify.error('es.error_delete', 'Fehler beim Löschen');
            }
        });
    }

    /* ── Signatur-Editor ── */
    function _bindSignatureEditor() {
        document.addEventListener('click', function(e) {
            const newBtn = e.target.closest('[data-action="new-signature"]');
            if (newBtn) {
                e.preventDefault();
                _openEditor(null);
                return;
            }

            const editBtn = e.target.closest('[data-action="edit-signature"]');
            if (editBtn) {
                e.stopPropagation();
                _openEditor(parseInt(editBtn.dataset.id, 10));
                return;
            }

            const row = e.target.closest('[data-sig-row-clickable]');
            if (row && !e.target.closest('button')) {
                _openEditor(parseInt(row.dataset.sigId, 10));
                return;
            }

            const saveBtn = e.target.closest('[data-action="sig-save"]');
            if (saveBtn) {
                e.preventDefault();
                _saveEditor(false);
                return;
            }

            const saveAsBtn = e.target.closest('[data-action="sig-save-as"]');
            if (saveAsBtn) {
                e.preventDefault();
                _saveEditor(true);
                return;
            }

            const cancelBtn = e.target.closest('[data-action="sig-cancel"]');
            if (cancelBtn) {
                e.preventDefault();
                _closeEditor();
                return;
            }

            const tabBtn = e.target.closest('[data-sig-tab]');
            if (tabBtn) {
                _switchCodeTab(tabBtn.dataset.sigTab);
                return;
            }

            const modeBtn = e.target.closest('[data-sig-preview-mode]');
            if (modeBtn) {
                _setPreviewMode(modeBtn.dataset.sigPreviewMode);
                return;
            }

            const refreshBtn = e.target.closest('[data-action="sig-preview-refresh"]');
            if (refreshBtn) {
                _updatePreview();
            }
        });

        const htmlEl = document.getElementById('es-sig-html');
        const txtEl  = document.getElementById('es-sig-txt');
        [htmlEl, txtEl].forEach(el => {
            if (!el) return;
            el.addEventListener('input', () => {
                clearTimeout(_sigPreviewTimer);
                _sigPreviewTimer = setTimeout(_updatePreview, 400);
            });
        });
    }

    function _els() {
        return {
            panel:    document.getElementById('es-sig-editor'),
            title:    document.getElementById('es-sig-editor-title'),
            name:     document.getElementById('es-sig-name'),
            ident:    document.getElementById('es-sig-identifier'),
            sender:   document.getElementById('es-sig-sender'),
            def:      document.getElementById('es-sig-default'),
            pub:      document.getElementById('es-sig-public'),
            html:     document.getElementById('es-sig-html'),
            txt:      document.getElementById('es-sig-txt'),
            preview:  document.getElementById('es-sig-preview-body'),
        };
    }

    async function _openEditor(id) {
        const el = _els();
        if (!el.panel) return;

        _sigId = id;
        el.panel.style.display = '';

        if (!id) {
            if (el.title) el.title.textContent = t('sig_editor_new', 'Neue Signatur');
            if (el.name) el.name.value = '';
            if (el.ident) el.ident.value = '';
            if (el.sender) el.sender.value = '';
            if (el.def) el.def.checked = false;
            if (el.pub) el.pub.checked = false;
            if (el.html) el.html.value = DEFAULT_HTML;
            if (el.txt) el.txt.value = DEFAULT_TXT;
            _switchCodeTab('html');
            _setPreviewMode('html');
            _updatePreview();
            el.panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
            return;
        }

        try {
            const data = await ES.api.get(ES.apiUrl(`signatures/${id}/`));
            if (el.title) {
                el.title.textContent = t('sig_editor_edit', 'Signatur bearbeiten') + ': ' + data.name;
            }
            if (el.name) el.name.value = data.name || '';
            if (el.ident) el.ident.value = data.identifier || '';
            if (el.sender) el.sender.value = data.sender_account_id || '';
            if (el.def) el.def.checked = !!data.is_default;
            if (el.pub) el.pub.checked = !!data.is_public;
            if (el.html) el.html.value = data.html_body || '';
            if (el.txt) el.txt.value = data.text_body || '';
            _switchCodeTab('html');
            _setPreviewMode('html');
            _updatePreview();
            el.panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } catch(err) {
            console.error('Signatur laden fehlgeschlagen:', err);
            ES.notify.error('es.error_load_sig', 'Signatur konnte nicht geladen werden');
            _closeEditor();
        }
    }

    function _closeEditor() {
        const el = _els();
        if (el.panel) el.panel.style.display = 'none';
        _sigId = null;
    }

    function _switchCodeTab(tab) {
        const el = _els();
        document.querySelectorAll('[data-sig-tab]').forEach(btn => {
            const active = btn.dataset.sigTab === tab;
            btn.classList.toggle('inactive', !active);
        });
        if (el.html) el.html.style.display = tab === 'html' ? '' : 'none';
        if (el.txt) el.txt.style.display = tab === 'txt' ? '' : 'none';
    }

    function _setPreviewMode(mode) {
        _sigPreviewMode = mode;
        document.querySelectorAll('[data-sig-preview-mode]').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.sigPreviewMode === mode);
        });
        _updatePreview();
    }

    function _updatePreview() {
        const el = _els();
        if (!el.preview) return;

        if (_sigPreviewMode === 'txt') {
            el.preview.className = 'es-sig-editor-preview-body es-preview-txt';
            el.preview.textContent = el.txt?.value || '';
            return;
        }

        el.preview.className = 'es-sig-editor-preview-body';
        el.preview.innerHTML = el.html?.value || '';
    }

    function _slugify(text) {
        return (text || '')
            .toLowerCase()
            .replace(/ä/g, 'ae').replace(/ö/g, 'oe').replace(/ü/g, 'ue').replace(/ß/g, 'ss')
            .replace(/[^a-z0-9]+/g, '_')
            .replace(/^_+|_+$/g, '')
            .slice(0, 80);
    }

    function _collectPayload(saveAs) {
        const el = _els();
        const name = (el.name?.value || '').trim();
        let identifier = (el.ident?.value || '').trim();
        if (!identifier && name) identifier = _slugify(name);

        const payload = {
            name,
            identifier,
            html_body: el.html?.value || '',
            text_body: el.txt?.value || '',
            sender_account_id: el.sender?.value ? parseInt(el.sender.value, 10) : null,
            is_default: !!el.def?.checked,
            is_public:  !!el.pub?.checked,
        };

        if (saveAs) {
            payload.name = name ? `${name} (Kopie)` : 'Kopie';
            payload.identifier = identifier ? `${identifier}_copy` : `sig_copy_${Date.now()}`;
            return { payload, saveAs: true };
        }
        return { payload, saveAs: false };
    }

    async function _saveEditor(saveAs) {
        const { payload, saveAs: isCopy } = _collectPayload(saveAs);

        if (!payload.name || !payload.identifier) {
            ES.notify.error('es.error_save', 'Name und Identifier sind Pflichtfelder');
            return;
        }

        const url = (_sigId && !isCopy)
            ? ES.apiUrl(`signatures/${_sigId}/`)
            : ES.apiUrl('signatures/');
        const method = (_sigId && !isCopy) ? 'PUT' : 'POST';

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
            if (!r.ok) {
                throw new Error(data.error || `HTTP ${r.status}`);
            }
            const newId = data.id || _sigId;
            ES.notify.success('es.sig_saved', 'Signatur gespeichert');
            window.location.href = '/email-studio/config/?sig=' + newId;
        } catch(err) {
            console.error('Speichern fehlgeschlagen:', err);
            ES.notify.error('es.error_save', err.message || 'Fehler beim Speichern');
        }
    }

    function _updateSigCount() {
        const countEl = document.getElementById('es-sig-count');
        const rows = document.querySelectorAll('#es-sig-table [data-sig-row]');
        if (countEl) countEl.textContent = rows.length;
    }

    function _openFromQuery() {
        const params = new URLSearchParams(window.location.search);
        const sig = params.get('sig');
        if (sig === 'new') {
            _openEditor(null);
        } else if (sig) {
            const id = parseInt(sig, 10);
            if (id) _openEditor(id);
        }
    }

    return { init, _openFromQuery };

})();

document.addEventListener('DOMContentLoaded', () => {
    ESConfig.init();
    ESConfig._openFromQuery();
});
