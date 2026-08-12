/**
 * 5_sp-lang.js — Sprach-Dropdown mit Flagge + ISO
 * Lädt Sprachliste dynamisch von /crm/api/softphone/languages/
 */
window.SP_Lang = (function() {
    var _langs = [];
    var _open  = false;
    var _current = 'de';

    async function init() {
        try {
            var r = await fetch('/crm/api/softphone/languages/');
            var d = await r.json();
            if (d.success && d.languages && d.languages.length) _langs = d.languages;
        } catch(e) {
            console.warn('SP_Lang: Sprachliste laden fehlgeschlagen', e);
            _langs = [{ code:'de', iso:'DE', flag:'🇩🇪', label:'Deutsch', rtl:false }];
        }
        _buildPanel();
        _buildSettingsDropdown();
        // ISO-Span sofort leeren — wird von _setLang befüllt
        var iso = document.getElementById('sp-lang-iso');
        if (iso) iso.textContent = '';
        _setLang(_getSavedLang(), false);
        document.addEventListener('click', function(e) {
            var wrap = document.getElementById('sp-lang-wrap');
            if (wrap && !wrap.contains(e.target)) _close();
        });
    }

    function _getSavedLang() {
        if (window.SP_CONFIG && window.SP_CONFIG.language) return window.SP_CONFIG.language;
        try { var ls = localStorage.getItem('sp_lang'); if (ls) return ls; } catch(e) {}
        var br = (navigator.language || 'de').substring(0,2).toLowerCase();
        if (_langs.find(function(l) { return l.code === br; })) return br;
        return 'de';
    }

    function _buildPanel() {
        var panel = document.getElementById('sp-lang-panel');
        if (!panel) return;
        panel.innerHTML = _langs.map(function(l) {
            return '<div onclick="SP_Lang.select(\'' + l.code + '\')"'
                + ' id="sp-lang-item-' + l.code + '"'
                + ' style="display:flex;align-items:center;gap:8px;padding:6px 10px;'
                + 'font-size:11px;cursor:pointer;border-bottom:0.5px solid var(--border-color)"'
                + ' onmouseover="this.style.background=\'var(--hover-bg)\'"'
                + ' onmouseout="this.style.background=\'\'">'
                + '<span class="fi fi-' + (({en:'gb',ar:'sa',zh:'cn'})[l.code] || l.code) + '" style="font-size:14px;border-radius:2px"></span>'
                + '<span style="font-weight:600;color:var(--text-muted);min-width:22px">' + l.iso + '</span>'
                + '<span style="color:var(--text-primary)">' + l.label + '</span>'
                + '</div>';
        }).join('');
    }

    function _buildSettingsDropdown() {
        var sel = document.getElementById('sp-cfg-lang');
        if (!sel) return;
        sel.innerHTML = _langs.map(function(l) {
            return '<option value="' + l.code + '">' + l.flag + ' ' + l.iso + ' \u2014 ' + l.label + '</option>';
        }).join('');
    }

    function toggle() { _open ? _close() : _openPanel(); }

    function _openPanel() {
        var panel = document.getElementById('sp-lang-panel');
        if (panel) panel.style.display = 'block';
        _open = true;
    }

    function _close() {
        var panel = document.getElementById('sp-lang-panel');
        if (panel) panel.style.display = 'none';
        _open = false;
    }

    function select(code) { _setLang(code, true); _close(); }

    function _setLang(code, save) {
        var lang = _langs.find(function(l) { return l.code === code; }) || _langs[0];
        if (!lang) return;
        _current = lang.code;
        var flag = document.getElementById('sp-lang-flag');
        var iso  = document.getElementById('sp-lang-iso');
        var fiMap = { en:'gb', ar:'sa', zh:'cn' };
        var fiCode = fiMap[lang.code] || lang.code;
        if (flag) {
            flag.className = 'fi fi-' + fiCode;
            flag.style.fontSize = '14px';
            flag.style.borderRadius = '2px';
            flag.textContent = '';
        }
        if (iso) iso.textContent = lang.iso;
        var sel = document.getElementById('sp-cfg-lang');
        if (sel) sel.value = lang.code;
        _langs.forEach(function(l) {
            var el = document.getElementById('sp-lang-item-' + l.code);
            if (el) el.style.background = (l.code === code) ? 'var(--active-highlight,#dbeafe)' : '';
        });
        if (window.SP_i18n) SP_i18n.load(lang.code);
        if (save) {
            try { localStorage.setItem('sp_lang', lang.code); } catch(e) {}
            fetch('/crm/api/user-settings/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': _csrf() },
                body: JSON.stringify({ language: lang.code })
            }).catch(function(e) { console.warn('SP_Lang: Speichern fehlgeschlagen', e); });
        }
    }

    function _csrf() {
        var c = document.cookie.split(';').map(function(c) { return c.trim(); })
            .find(function(c) { return c.startsWith('csrftoken='); });
        return c ? c.split('=')[1] : '';
    }

    function getCurrent() { return _current; }
    function getLangs()   { return _langs; }
    // Öffentlich ohne Speichern (für Laden aus DB)
    function _setLangPublic(code, save) { _setLang(code, save); }
    return { init, toggle, select, getCurrent, getLangs, _setLangPublic };
})();
