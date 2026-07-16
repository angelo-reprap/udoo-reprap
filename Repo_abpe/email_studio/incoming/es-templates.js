/**
 * es-templates.js — ABpE Email Studio
 * Reiter 1: Vorlagen-Bibliothek
 * Laden, Filtern, Archivieren, Duplizieren
 */
'use strict';

window.ESTemplates = (() => {

    function _applyTitles() {
        document.querySelectorAll('[data-i18n-title]').forEach(el => {
            const key = el.getAttribute('data-i18n-title');
            const parts = key.split('.');
            let v = window.i18nData;
            for (const part of parts) v = v?.[part];
            if (v) el.title = v;
        });
    }

    function init() {
        console.log('✓ ES Templates initialisiert');
        _bindSearch();
        _bindActions();
        // Titles setzen wenn languageChanged fired (sicher nach loadLanguage)
        document.addEventListener('languageChanged', _applyTitles, {once: false});
        // Auch beim ersten Load: auf languageChanged warten oder nach 1s
        const _titleTimer = setInterval(() => {
            if (window.i18nData?.es?.btn_duplicate) {
                _applyTitles();
                clearInterval(_titleTimer);
            }
        }, 100);
        setTimeout(() => clearInterval(_titleTimer), 5000);
    }

    function _bindSearch() {
        const inp = document.getElementById('es-search-input');
        if (inp) inp.addEventListener('input', _filterTable);
        const scpSel = document.getElementById('es-scope-select');
        if (scpSel) scpSel.addEventListener('change', _filterTable);
        const stSel = document.getElementById('es-status-select');
        if (stSel) stSel.addEventListener('change', _filterTable);
    }

    function _filterTable() {
        const q      = (document.getElementById('es-search-input')?.value || '').toLowerCase();
        const scope  = document.getElementById('es-scope-select')?.value  || '';
        const status = document.getElementById('es-status-select')?.value || '';

        document.querySelectorAll('[data-tpl-row]').forEach(row => {
            const name = (row.dataset.name       || '').toLowerCase();
            const id   = (row.dataset.identifier || '').toLowerCase();
            const sc   = row.dataset.scope  || '';
            const st   = row.dataset.status || '';

            const matchQ  = !q      || name.includes(q) || id.includes(q);
            const matchSc = !scope  || sc === scope;
            const matchSt = !status || st === status;

            row.style.display = (matchQ && matchSc && matchSt) ? '' : 'none';
        });

        _updateGroupVisibility();
    }

    function _updateGroupVisibility() {
        document.querySelectorAll('[data-scope-group]').forEach(group => {
            const rows    = group.querySelectorAll('[data-tpl-row]');
            const visible = Array.from(rows).some(r => r.style.display !== 'none');
            group.style.display = visible ? '' : 'none';
        });
    }

    function _bindActions() {
        document.addEventListener('click', async function(e) {

            /* Archivieren */
            const archBtn = e.target.closest('[data-action="archive"]');
            if (archBtn) {
                const id = archBtn.dataset.id;
                if (!ES.confirm('es.confirm_archive', 'Vorlage archivieren?')) return;
                try {
                    await ES.api.delete(ES.apiUrl(`templates/${id}/`));
                    archBtn.closest('[data-tpl-row]')?.remove();
                    ES.notify.success('es.archived', 'Archiviert');
                    _updateGroupVisibility();
                } catch(err) {
                    console.error('Archivieren fehlgeschlagen:', err);
                    ES.notify.error('es.error_archive', 'Fehler beim Archivieren');
                }
            }

            /* Duplizieren */
            const dupBtn = e.target.closest('[data-action="duplicate"]');
            if (dupBtn) {
                const id   = dupBtn.dataset.id;
                const name = dupBtn.dataset.name || '';
                const newId   = prompt('Neuer Identifier:', `${dupBtn.dataset.identifier}_copy`);
                if (!newId) return;
                const newName = prompt('Neuer Name:', `${name} (Kopie)`);
                if (!newName) return;
                try {
                    await ES.api.post(ES.apiUrl(`templates/${id}/duplicate/`), {
                        identifier: newId,
                        name:       newName,
                    });
                    ES.notify.success('es.duplicated', 'Dupliziert');
                    setTimeout(() => location.reload(), 800);
                } catch(err) {
                    console.error('Duplizieren fehlgeschlagen:', err);
                    ES.notify.error('es.error_duplicate', 'Fehler beim Duplizieren');
                }
            }

            /* Test senden */
            const testBtn = e.target.closest('[data-action="test-send"]');
            if (testBtn) {
                const id        = testBtn.dataset.id;
                const recipient = prompt('Test-E-Mail an:', '');
                if (!recipient) return;
                try {
                    await ES.api.post(ES.apiUrl(`templates/${id}/send-test/`), {
                        recipient
                    });
                    ES.notify.success('es.test_sent', 'Test gesendet');
                } catch(err) {
                    console.error('Test-Versand fehlgeschlagen:', err);
                    ES.notify.error('es.error_test_send', 'Fehler beim Test-Versand');
                }
            }
        });
    }

    // Bei Sprachwechsel titles neu setzen
    document.addEventListener('languageChanged', () => setTimeout(_applyTitles, 100));

    return { init };

})();

document.addEventListener('DOMContentLoaded', ESTemplates.init);
