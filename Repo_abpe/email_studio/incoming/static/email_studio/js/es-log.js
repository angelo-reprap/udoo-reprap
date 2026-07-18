/**
 * es-log.js — ABpE Email Studio
 * Reiter 3: Versand-Log Filter + Refresh
 */
'use strict';

window.ESLog = (() => {

    function init() {
        _bindFilter();
        _bindRefresh();
        console.log('✓ ES Log initialisiert');
    }

    function _bindFilter() {
        ['es-log-search', 'es-log-status', 'es-log-days',
         'es-log-template', 'es-log-mode'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.addEventListener('change', _applyFilter);
        });
        const search = document.getElementById('es-log-search');
        if (search) search.addEventListener('input', _applyFilter);
    }

    function _applyFilter() {
        const q      = (document.getElementById('es-log-search')?.value || '').toLowerCase();
        const status = document.getElementById('es-log-status')?.value  || '';
        const mode   = document.getElementById('es-log-mode')?.value    || '';
        const tpl    = document.getElementById('es-log-template')?.value || '';

        document.querySelectorAll('[data-log-row]').forEach(row => {
            const subj  = (row.dataset.subject  || '').toLowerCase();
            const from  = (row.dataset.from     || '').toLowerCase();
            const ref   = (row.dataset.ref      || '').toLowerCase();
            const st    = row.dataset.status    || '';
            const md    = row.dataset.mode      || '';
            const tp    = row.dataset.template  || '';

            const matchQ  = !q      || subj.includes(q) || from.includes(q) || ref.includes(q);
            const matchSt = !status || st === status;
            const matchMd = !mode   || md === mode;
            const matchTp = !tpl    || tp === tpl;

            row.style.display = (matchQ && matchSt && matchMd && matchTp) ? '' : 'none';
        });
    }

    function _bindRefresh() {
        const btn = document.getElementById('es-log-refresh');
        if (btn) btn.addEventListener('click', () => location.reload());
    }

    return { init };

})();

document.addEventListener('DOMContentLoaded', ESLog.init);
