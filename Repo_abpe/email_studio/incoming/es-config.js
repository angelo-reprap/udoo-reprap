/**
 * es-config.js — ABpE Email Studio
 * Reiter 4: SMTP Test, Absender-Konten, Signaturen
 */
'use strict';

window.ESConfig = (() => {

    function init() {
        _bindSmtpTest();
        _bindSenderDelete();
        _bindSignatureDelete();
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
            if (!ES.confirm('es.confirm_delete_sig', 'Signatur löschen?')) return;
            const id = btn.dataset.id;
            try {
                await ES.api.delete(ES.apiUrl(`signatures/${id}/`));
                btn.closest('[data-sig-row]')?.remove();
                ES.notify.success('es.deleted', 'Gelöscht');
            } catch(err) {
                console.error('Löschen fehlgeschlagen:', err);
                ES.notify.error('es.error_delete', 'Fehler beim Löschen');
            }
        });
    }

    return { init };

})();

document.addEventListener('DOMContentLoaded', ESConfig.init);
