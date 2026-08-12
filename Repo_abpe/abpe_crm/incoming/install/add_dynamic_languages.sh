#!/usr/bin/env bash
# add_dynamic_languages.sh — Dynamische Sprachliste + Default-Sprache
# Aufruf: bash apps/abpe_crm/install/add_dynamic_languages.sh
set -euo pipefail
GREEN='\033[0;32m'; BLUE='\033[0;34m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
info() { echo -e "${BLUE}▶${NC}  $*"; }

BASE="/opt/abpe/backend"
APP="apps/abpe_crm"
JS_LANG="${APP}/static/abpe_crm/softphone/js/5_sp-lang.js"
JS8="${APP}/static/abpe_crm/softphone/js/8_sp-status.js"
TMPL="${APP}/templates/abpe_crm/softphone/softphone.html"

[[ "$(pwd)" == "$BASE" ]] || { echo "Falsches Verzeichnis"; exit 1; }

for f in "$JS_LANG" "$JS8" "$TMPL"; do
    python3 Archiv/backup_restore.py -save "$f" -m "vor dynamic languages" || exit 1
done
ok "Backups OK"
echo

# ── Schritt 1: Django-View für Sprachlisten-Scan ─────────
info "Schritt 1/4 — Django-View: /crm/api/softphone/languages/"

python3 << 'PYEOF'
import re

with open("apps/abpe_crm/views.py", "r") as f:
    c = f.read()

# Prüfen ob View schon existiert
if 'api_softphone_languages' in c:
    print("INFO: api_softphone_languages bereits vorhanden")
else:
    # Nach api_crm_user_settings einfügen
    old = "\n@login_required\n@require_POST\ndef api_telefon_dnd(request):"
    new = """

@login_required
def api_softphone_languages(request):
    \"\"\"Gibt Liste der verfügbaren Softphone-Sprachen zurück (scan i18n/*.json)\"\"\"
    import os, glob
    from django.conf import settings as django_settings

    # Flag-Mapping: ISO-Code → Flaggen-Emoji + Bezeichnung
    META = {
        'de': {'flag': '🇩🇪', 'label': 'Deutsch'},
        'en': {'flag': '🇬🇧', 'label': 'English'},
        'fr': {'flag': '🇫🇷', 'label': 'Français'},
        'es': {'flag': '🇪🇸', 'label': 'Español'},
        'it': {'flag': '🇮🇹', 'label': 'Italiano'},
        'pl': {'flag': '🇵🇱', 'label': 'Polski'},
        'ru': {'flag': '🇷🇺', 'label': 'Русский'},
        'ar': {'flag': '🇸🇦', 'label': 'العربية'},
        'zh': {'flag': '🇨🇳', 'label': '中文'},
    }

    # i18n-Verzeichnis scannen
    i18n_dir = os.path.join(
        django_settings.BASE_DIR,
        'apps', 'abpe_crm', 'static', 'abpe_crm', 'softphone', 'i18n'
    )
    langs = []
    for path in sorted(glob.glob(os.path.join(i18n_dir, '*_phone.json'))):
        code = os.path.basename(path).replace('_phone.json', '')
        meta = META.get(code, {'flag': '🌐', 'label': code.upper()})
        # Nur Dateien mit Inhalt (> 5 Bytes)
        if os.path.getsize(path) > 5:
            langs.append({
                'code':  code,
                'iso':   code.upper(),
                'flag':  meta['flag'],
                'label': meta['label'],
                'rtl':   code in ('ar', 'he', 'fa', 'ur'),
            })

    return JsonResponse({'success': True, 'languages': langs})

@login_required
@require_POST
def api_telefon_dnd(request):"""

    assert old in c, "FEHLER: api_telefon_dnd nicht gefunden"
    c = c.replace(old, new, 1)
    with open("apps/abpe_crm/views.py", "w") as f:
        f.write(c)
    print("✓  api_softphone_languages in views.py eingefügt")
PYEOF

# URL eintragen
python3 << 'PYEOF'
with open("apps/abpe_crm/urls.py", "r") as f:
    c = f.read()

if 'softphone/languages' in c:
    print("INFO: URL bereits vorhanden")
else:
    old = "    path('api/softphone/contacts/', views.api_softphone_contacts, name='api_softphone_contacts'),"
    new = """    path('api/softphone/contacts/', views.api_softphone_contacts, name='api_softphone_contacts'),
    path('api/softphone/languages/', views.api_softphone_languages, name='api_softphone_languages'),"""
    assert old in c, "FEHLER: contacts-URL nicht gefunden"
    c = c.replace(old, new, 1)
    with open("apps/abpe_crm/urls.py", "w") as f:
        f.write(c)
    print("✓  URL /crm/api/softphone/languages/ eingetragen")
PYEOF
echo

# ── Schritt 2: 5_sp-lang.js — dynamisch ──────────────────
info "Schritt 2/4 — 5_sp-lang.js: Sprachliste dynamisch laden"

cat > "$JS_LANG" << 'JSEOF'
/**
 * 5_sp-lang.js — Sprach-Dropdown mit Flagge + ISO
 * Lädt Sprachliste dynamisch von /crm/api/softphone/languages/
 * Speichert Sprachwahl in DB (language-Feld) + localStorage
 */
window.SP_Lang = (function() {

    var _langs = [];
    var _open  = false;
    var _current = 'de';

    async function init() {
        // Sprachliste vom Server laden
        try {
            var r = await fetch('/crm/api/softphone/languages/');
            var d = await r.json();
            if (d.success && d.languages && d.languages.length) {
                _langs = d.languages;
            }
        } catch(e) {
            console.warn('SP_Lang: Sprachliste laden fehlgeschlagen', e);
            _langs = [{ code:'de', iso:'DE', flag:'🇩🇪', label:'Deutsch', rtl:false }];
        }

        _buildPanel();
        _buildSettingsDropdown();

        // Sprache aus DB > localStorage > Browser > de
        var saved = _getSavedLang();
        _setLang(saved, false);

        // Klick außerhalb schließt Panel
        document.addEventListener('click', function(e) {
            var wrap = document.getElementById('sp-lang-wrap');
            if (wrap && !wrap.contains(e.target)) _close();
        });
    }

    function _getSavedLang() {
        // Priorität: DB-Wert aus SP_CONFIG > localStorage > Browser-Sprache > 'de'
        if (window.SP_CONFIG && window.SP_CONFIG.language) return window.SP_CONFIG.language;
        try {
            var ls = localStorage.getItem('sp_lang');
            if (ls) return ls;
        } catch(e) {}
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
                + '<span style="font-size:14px">' + l.flag + '</span>'
                + '<span style="font-weight:600;color:var(--text-muted);min-width:22px">' + l.iso + '</span>'
                + '<span style="color:var(--text-primary)">' + l.label + '</span>'
                + '</div>';
        }).join('');
    }

    function _buildSettingsDropdown() {
        // Dropdown im Einstellungen-Tab befüllen
        var sel = document.getElementById('sp-cfg-lang');
        if (!sel) return;
        sel.innerHTML = _langs.map(function(l) {
            return '<option value="' + l.code + '">' + l.flag + ' ' + l.iso + ' — ' + l.label + '</option>';
        }).join('');
    }

    function toggle() {
        _open ? _close() : _openPanel();
    }

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

    function select(code) {
        _setLang(code, true);
        _close();
    }

    function _setLang(code, save) {
        var lang = _langs.find(function(l) { return l.code === code; }) || _langs[0];
        if (!lang) return;
        _current = lang.code;

        // Header-Button aktualisieren
        var flag = document.getElementById('sp-lang-flag');
        var iso  = document.getElementById('sp-lang-iso');
        if (flag) flag.textContent = lang.flag;
        if (iso)  iso.textContent  = lang.iso;

        // Settings-Dropdown synchronisieren
        var sel = document.getElementById('sp-cfg-lang');
        if (sel) sel.value = lang.code;

        // Aktiven Eintrag hervorheben
        _langs.forEach(function(l) {
            var el = document.getElementById('sp-lang-item-' + l.code);
            if (el) el.style.background = (l.code === code)
                ? 'var(--active-highlight,#dbeafe)' : '';
        });

        // i18n laden
        if (window.SP_i18n) SP_i18n.load(lang.code);

        // Speichern
        if (save) {
            try { localStorage.setItem('sp_lang', lang.code); } catch(e) {}
            // In DB speichern
            fetch('/crm/api/user-settings/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': _csrf()
                },
                body: JSON.stringify({ language: lang.code })
            }).catch(function(e) { console.warn('SP_Lang: Sprache speichern fehlgeschlagen', e); });
        }
    }

    function _csrf() {
        var c = document.cookie.split(';').map(function(c) { return c.trim(); })
            .find(function(c) { return c.startsWith('csrftoken='); });
        return c ? c.split('=')[1] : '';
    }

    function getCurrent() { return _current; }
    function getLangs()   { return _langs; }

    return { init, toggle, select, getCurrent, getLangs };
})();
JSEOF

node --check "$JS_LANG" && ok "5_sp-lang.js Syntax OK" || { echo "FEHLER"; exit 1; }
echo

# ── Schritt 3: HTML — Einstellungen-Tab Sprach-Dropdown ──
info "Schritt 3/4 — softphone.html: Sprach-Dropdown in Einstellungen"

python3 << 'PYEOF'
with open("apps/abpe_crm/templates/abpe_crm/softphone/softphone.html", "r") as f:
    c = f.read()

# Nach dem letzten Einstellungs-Feld (status_extensions), vor dem Save-Button
old = """            <button onclick="Softphone.saveAndRegister()"
                style="padding:8px;background:var(--abcona-blue,#163258);color:#fff;border:none;border-radius:7px;font-size:12px;font-weight:500;cursor:pointer;margin-top:4px">"""

new = """            <div>
                <label data-i18n="default_language" style="font-size:11px;color:var(--text-muted);display:block;margin-bottom:3px">Standard-Sprache</label>
                <select id="sp-cfg-lang"
                    style="width:100%;box-sizing:border-box;padding:5px 8px;border:1px solid var(--border-color);border-radius:7px;font-size:12px;background:var(--bg-primary);color:var(--text-primary);cursor:pointer">
                    <option value="de">🇩🇪 DE — Deutsch</option>
                </select>
            </div>
            <button onclick="Softphone.saveAndRegister()"
                style="padding:8px;background:var(--abcona-blue,#163258);color:#fff;border:none;border-radius:7px;font-size:12px;font-weight:500;cursor:pointer;margin-top:4px">"""

assert old in c, "FEHLER: Save-Button nicht gefunden"
c = c.replace(old, new, 1)

with open("apps/abpe_crm/templates/abpe_crm/softphone/softphone.html", "w") as f:
    f.write(c)
print("✓  Sprach-Dropdown in Einstellungen eingefügt")
PYEOF
echo

# ── Schritt 4: 8_sp-status.js — Sprache speichern + laden
info "Schritt 4/4 — 8_sp-status.js: softphone_lang in saveAndRegister"

python3 << 'PYEOF'
with open("apps/abpe_crm/static/abpe_crm/softphone/js/8_sp-status.js", "r") as f:
    c = f.read()

# Beim Laden: Sprache aus Settings setzen
old = "            Softphone._loadExtSettingsIntoForm(s);"
new = """            Softphone._loadExtSettingsIntoForm(s);
            // Sprache aus DB anwenden
            if (s.language && window.SP_Lang) {
                SP_Lang.select(s.language);
            }"""
assert old in c, "FEHLER: _loadExtSettingsIntoForm nicht gefunden"
c = c.replace(old, new, 1)

# saveAndRegister: sp-cfg-lang mitspeichern
old2 = "        await fetch('/crm/api/user-settings/', {\n            method: 'POST',\n            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': Softphone._csrf() },\n            body: JSON.stringify({\n                softphone_vm_ext:      vmExt,\n                softphone_dnd_ext:     dndExt,\n                softphone_status_exts: stsExts,\n            })\n        });"
new2 = """        var langVal = (document.getElementById('sp-cfg-lang') || {value:''}).value.trim();
        await fetch('/crm/api/user-settings/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': Softphone._csrf() },
            body: JSON.stringify({
                softphone_vm_ext:      vmExt,
                softphone_dnd_ext:     dndExt,
                softphone_status_exts: stsExts,
                language:              langVal,
            })
        });
        if (langVal && window.SP_Lang) SP_Lang.select(langVal);"""
assert old2 in c, "FEHLER: saveAndRegister fetch nicht gefunden"
c = c.replace(old2, new2, 1)

with open("apps/abpe_crm/static/abpe_crm/softphone/js/8_sp-status.js", "w") as f:
    f.write(c)
print("✓  8_sp-status.js: Sprache laden + speichern")
PYEOF

node --check "$JS8" && ok "8_sp-status.js Syntax OK" || { echo "FEHLER"; exit 1; }
echo

# de_phone.json: neuer Key
python3 -c "
import json
with open('apps/abpe_crm/static/abpe_crm/softphone/i18n/de_phone.json') as f: d=json.load(f)
d['default_language']='Standard-Sprache'
with open('apps/abpe_crm/static/abpe_crm/softphone/i18n/de_phone.json','w',encoding='utf-8') as f:
    json.dump(d,f,ensure_ascii=False,indent=4)
print('✓  de_phone.json: default_language ergänzt')
"
echo

# SP_CONFIG um language erweitern
info "softphone_view: language in SP_CONFIG"
python3 << 'PYEOF'
with open("apps/abpe_crm/views.py", "r") as f:
    c = f.read()

old = "    sp_settings = {\n        'ws':           s.softphone_ws,"
if old in c:
    # Prüfen ob language schon drin
    if "'language'" in c[c.find(old):c.find(old)+500]:
        print("INFO: language bereits in sp_settings")
    else:
        new = "    sp_settings = {\n        'ws':           s.softphone_ws,\n        'language':     s.language,"
        c = c.replace(old, new, 1)
        with open("apps/abpe_crm/views.py", "w") as f:
            f.write(c)
        print("✓  language in sp_settings Context eingefügt")
else:
    print("INFO: sp_settings nicht gefunden — manuell prüfen")
PYEOF

# HTML: SP_CONFIG um language erweitern
python3 << 'PYEOF'
with open("apps/abpe_crm/templates/abpe_crm/softphone/softphone.html", "r") as f:
    c = f.read()

old = "        status_exts:  '{{ sp_settings.status_exts|default:\"\" }}',"
if "'language'" in c:
    print("INFO: language bereits in SP_CONFIG")
else:
    new = "        status_exts:  '{{ sp_settings.status_exts|default:\"\" }}',\n        language:     '{{ sp_settings.language|default:\"de\" }}',"
    assert old in c, "FEHLER: status_exts nicht in SP_CONFIG"
    c = c.replace(old, new, 1)
    with open("apps/abpe_crm/templates/abpe_crm/softphone/softphone.html", "w") as f:
        f.write(c)
    print("✓  language in SP_CONFIG eingefügt")
PYEOF
echo

info "Deploy"
python3 manage.py collectstatic --noinput 2>&1 | tail -2
supervisorctl restart abpe-django
sleep 2
supervisorctl status abpe-django
echo
ok "Fertig — Hard-Reload (Ctrl+Shift+R)"
echo
echo "Flow:"
echo "  1. Einstellungen → Standard-Sprache auswählen → Speichern"
echo "  2. Beim nächsten Laden: Sprache aus DB automatisch aktiv"
echo "  3. Header-Dropdown zeigt aktive Sprache"
echo "  4. Arabisch → automatisch RTL"

