// 3_sp-i18n.js — Internationalisierung
// SP_i18n.t('key') → übersetzter String oder Fallback
// SP_i18n.load('de') → lädt Sprachdatei + setzt RTL falls nötig
// SP_i18n.apply()   → wendet data-i18n Attribute auf DOM an

window.SP_i18n = (function() {
    var _lang   = window.SP_LANG || 'de';
    var _data   = {};
    var _loaded = false;
    var _RTL_LANGS = ['ar', 'he', 'fa', 'ur'];

    async function load(lang) {
        try {
            var url = '/static/abpe_crm/softphone/i18n/' + lang + '_phone.json';
            var r = await fetch(url);
            if (r.ok) {
                _data   = await r.json();
                _lang   = lang;
                _loaded = true;
                _applyDir(lang);
                apply();
            } else {
                console.warn('SP_i18n: Sprachdatei nicht gefunden:', url);
            }
        } catch(e) {
            console.warn('SP_i18n: Laden fehlgeschlagen:', lang, e);
        }
    }

    // RTL/LTR auf <html> setzen
    function _applyDir(lang) {
        var html = document.documentElement;
        if (_RTL_LANGS.indexOf(lang) !== -1) {
            html.setAttribute('dir', 'rtl');
            html.setAttribute('lang', lang);
        } else {
            html.setAttribute('dir', 'ltr');
            html.setAttribute('lang', lang);
        }
    }

    function t(key, fallback) {
        return _data[key] || fallback || key;
    }

    // Wendet data-i18n Attribute auf DOM an
    function apply() {
        document.querySelectorAll('[data-i18n]').forEach(function(el) {
            var key = el.getAttribute('data-i18n');
            var val = _data[key];
            if (val) el.textContent = val;
        });
        document.querySelectorAll('[data-i18n-placeholder]').forEach(function(el) {
            var key = el.getAttribute('data-i18n-placeholder');
            var val = _data[key];
            if (val) el.placeholder = val;
        });
        document.querySelectorAll('[data-i18n-title]').forEach(function(el) {
            var key = el.getAttribute('data-i18n-title');
            var val = _data[key];
            if (val) el.title = val;
        });
        // Callback für dynamische Labels (Status-Text etc.)
        if (window.SP_onLangChange) SP_onLangChange(_lang);
    }

    function getLang()  { return _lang; }
    function isLoaded() { return _loaded; }
    function isRTL()    { return _RTL_LANGS.indexOf(_lang) !== -1; }

    return { load, t, apply, getLang, isLoaded, isRTL };
})();
