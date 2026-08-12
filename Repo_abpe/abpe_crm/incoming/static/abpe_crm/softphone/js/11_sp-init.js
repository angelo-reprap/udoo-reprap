/**
 * 11_sp-init.js — Initialisierung aller Module in korrekter Reihenfolge
 */
(async function() {
    // 1. Theme
    if (window.SP_Theme) SP_Theme.init();
    // 2. Sprach-Dropdown + i18n laden (await — blockiert bis Sprache geladen)
    if (window.SP_Lang) await SP_Lang.init();
    // 3. PWA Service Worker
    if ('serviceWorker' in navigator) {
        try {
            var reg = await navigator.serviceWorker.register('/crm/softphone/sw.js', {
                scope: '/crm/softphone/'
            });
            console.log('SP: Service Worker registriert, scope:', reg.scope);
        } catch(e) { console.warn('SP: Service Worker Fehler', e); }
    }
    // 4. Softphone initialisieren
    if (window.SP_STANDALONE && typeof Softphone !== 'undefined') {
        function _initSoftphone() {
            if (Softphone.init) Softphone.init();
            if (Softphone._restorePosition) Softphone._restorePosition();
            if (Softphone._initDrag) Softphone._initDrag();
            if (Softphone._loadExtSettings) {
                setTimeout(function() { Softphone._loadExtSettings(); }, 500);
            }
            var loading = document.getElementById('sp-loading');
            if (loading) loading.style.display = 'none';
            // Suchfeld und Ergebnisse beim Start leeren
            var s = document.getElementById('sp-search');
            var r = document.getElementById('sp-search-results');
            if (s) s.value = '';
            if (r) { r.innerHTML = ''; r.style.display = 'none'; }
        }
        // DOM bereits bereit (Scripts am Ende von <body>)
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', _initSoftphone);
        } else {
            _initSoftphone();
        }
    }
    console.log('ABpE Softphone bereit.');
})();
