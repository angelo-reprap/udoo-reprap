#!/usr/bin/env bash
# add_language_dropdown.sh — Sprach-Dropdown im Header
# Aufruf: bash apps/abpe_crm/install/add_language_dropdown.sh
set -euo pipefail
GREEN='\033[0;32m'; BLUE='\033[0;34m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
info() { echo -e "${BLUE}▶${NC}  $*"; }

BASE="/opt/abpe/backend"
TMPL="apps/abpe_crm/templates/abpe_crm/softphone/softphone.html"

[[ "$(pwd)" == "$BASE" ]] || { echo "Falsches Verzeichnis"; exit 1; }

python3 Archiv/backup_restore.py -save "$TMPL" -m "vor language dropdown" || exit 1
ok "Backup OK"
echo

info "Dropdown in Header einfügen"

python3 << 'PYEOF'
with open("apps/abpe_crm/templates/abpe_crm/softphone/softphone.html", "r") as f:
    c = f.read()

# Theme-Button ersetzen durch: Theme-Button + Sprach-Dropdown
old = """            <button id="sp-theme-btn" onclick="SP_Theme.toggle()" title="Dark/Light Mode"
                style="background:none;border:none;color:rgba(255,255,255,0.5);cursor:pointer;padding:0;font-size:14px">
                <i class="bi bi-moon"></i>
            </button>"""

new = """            <button id="sp-theme-btn" onclick="SP_Theme.toggle()" title="Dark/Light Mode"
                style="background:none;border:none;color:rgba(255,255,255,0.5);cursor:pointer;padding:0;font-size:14px">
                <i class="bi bi-moon"></i>
            </button>
            <!-- Sprach-Dropdown -->
            <div id="sp-lang-wrap" style="position:relative">
                <button id="sp-lang-btn" onclick="SP_Lang.toggle()"
                    style="background:none;border:none;color:rgba(255,255,255,0.7);cursor:pointer;padding:0 2px;font-size:11px;font-weight:600;display:flex;align-items:center;gap:2px;letter-spacing:.3px">
                    <span id="sp-lang-flag" style="font-size:13px">🇩🇪</span>
                    <span id="sp-lang-iso">DE</span>
                </button>
                <div id="sp-lang-panel" style="display:none;position:absolute;top:22px;right:0;z-index:10010;background:var(--bg-primary);border:1px solid var(--border-color);border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,0.2);min-width:130px;overflow:hidden">
                    <!-- wird per JS befüllt -->
                </div>
            </div>"""

assert old in c, "FEHLER: Theme-Button nicht gefunden"
c = c.replace(old, new, 1)

with open("apps/abpe_crm/templates/abpe_crm/softphone/softphone.html", "w") as f:
    f.write(c)
print("✓  Sprach-Dropdown in Header eingefügt")
PYEOF
echo

info "5_sp-contacts.js oder neue Datei für SP_Lang?"

# Neue Datei 5_sp-lang.js (zwischen config und contacts)
JS_LANG="apps/abpe_crm/static/abpe_crm/softphone/js/5_sp-lang.js"

cat > "$JS_LANG" << 'JSEOF'
/**
 * 5_sp-lang.js — Sprach-Dropdown mit Flagge + ISO
 * Speichert Sprachwahl in localStorage
 */
window.SP_Lang = (function() {

    var LANGS = [
        { code: 'de', iso: 'DE', flag: '🇩🇪', label: 'Deutsch' },
        { code: 'en', iso: 'EN', flag: '🇬🇧', label: 'English' },
        { code: 'fr', iso: 'FR', flag: '🇫🇷', label: 'Français' },
        { code: 'es', iso: 'ES', flag: '🇪🇸', label: 'Español' },
        { code: 'it', iso: 'IT', flag: '🇮🇹', label: 'Italiano' },
        { code: 'pl', iso: 'PL', flag: '🇵🇱', label: 'Polski' },
        { code: 'ru', iso: 'RU', flag: '🇷🇺', label: 'Русский' },
        { code: 'ar', iso: 'AR', flag: '🇸🇦', label: 'العربية' },
        { code: 'zh', iso: 'ZH', flag: '🇨🇳', label: '中文' },
    ];

    var _open = false;

    function init() {
        _buildPanel();
        var saved = localStorage.getItem('sp_lang') || window.SP_LANG || 'de';
        _setLang(saved, false);
        // Klick außerhalb schließt Panel
        document.addEventListener('click', function(e) {
            if (!document.getElementById('sp-lang-wrap')?.contains(e.target)) {
                _close();
            }
        });
    }

    function _buildPanel() {
        var panel = document.getElementById('sp-lang-panel');
        if (!panel) return;
        panel.innerHTML = LANGS.map(function(l) {
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
        var lang = LANGS.find(function(l) { return l.code === code; }) || LANGS[0];

        // Button aktualisieren
        var flag = document.getElementById('sp-lang-flag');
        var iso  = document.getElementById('sp-lang-iso');
        if (flag) flag.textContent = lang.flag;
        if (iso)  iso.textContent  = lang.iso;

        // Aktiven Eintrag hervorheben
        LANGS.forEach(function(l) {
            var el = document.getElementById('sp-lang-item-' + l.code);
            if (el) el.style.background = (l.code === code) ? 'var(--active-highlight,#dbeafe)' : '';
        });

        // i18n laden
        if (window.SP_i18n) SP_i18n.load(code);

        // Speichern
        if (save) {
            try { localStorage.setItem('sp_lang', code); } catch(e) {}
        }
    }

    return { init, toggle, select };
})();
JSEOF

node --check "$JS_LANG" && ok "5_sp-lang.js Syntax OK" || { echo "FEHLER"; exit 1; }
echo

# HTML: 5_sp-lang.js in Script-Liste einfügen
info "5_sp-lang.js in softphone.html einbinden"

python3 << 'PYEOF'
with open("apps/abpe_crm/templates/abpe_crm/softphone/softphone.html", "r") as f:
    c = f.read()

old = '<script src="{% static \'abpe_crm/softphone/js/5_sp-contacts.js\' %}"></script>'
new = '<script src="{% static \'abpe_crm/softphone/js/5_sp-lang.js\' %}"></script>\n<script src="{% static \'abpe_crm/softphone/js/5_sp-contacts.js\' %}"></script>'

assert old in c, "FEHLER: 5_sp-contacts.js nicht gefunden"
c = c.replace(old, new, 1)

with open("apps/abpe_crm/templates/abpe_crm/softphone/softphone.html", "w") as f:
    f.write(c)
print("✓  5_sp-lang.js in Script-Liste eingebunden")
PYEOF
echo

# 11_sp-init.js: SP_Lang.init() aufrufen
info "11_sp-init.js: SP_Lang.init() aufrufen"

python3 << 'PYEOF'
with open("apps/abpe_crm/static/abpe_crm/softphone/js/11_sp-init.js", "r") as f:
    c = f.read()

old = "    // 1. Theme\n    if (window.SP_Theme) SP_Theme.init();"
new = """    // 1. Theme
    if (window.SP_Theme) SP_Theme.init();

    // 2. Sprach-Dropdown initialisieren (vor i18n.load)
    if (window.SP_Lang) SP_Lang.init();"""

# i18n.load entfernen — wird jetzt von SP_Lang.init() übernommen
old2 = """    // 2. i18n laden
    var lang = window.SP_LANG || 'de';
    if (window.SP_i18n) {
        await SP_i18n.load(lang);
    }"""

assert old in c, "FEHLER: Theme-Init nicht gefunden"
c = c.replace(old, new, 1)

if old2 in c:
    c = c.replace(old2, "    // i18n wird von SP_Lang.init() geladen", 1)
    print("✓  altes i18n.load() ersetzt")

with open("apps/abpe_crm/static/abpe_crm/softphone/js/11_sp-init.js", "w") as f:
    f.write(c)
print("✓  11_sp-init.js: SP_Lang.init() eingefügt")
PYEOF

node --check "apps/abpe_crm/static/abpe_crm/softphone/js/11_sp-init.js" && ok "11_sp-init.js Syntax OK"
echo

info "Deploy"
python3 manage.py collectstatic --noinput 2>&1 | tail -2
supervisorctl restart abpe-django
sleep 2
supervisorctl status abpe-django
echo
ok "Fertig — Hard-Reload (Ctrl+Shift+R)"
echo
echo "Dropdown oben rechts neben Moon-Icon:"
echo "  🇩🇪 DE | 🇬🇧 EN | 🇫🇷 FR | 🇪🇸 ES | 🇮🇹 IT"
echo "  🇵🇱 PL | 🇷🇺 RU | 🇸🇦 AR | 🇨🇳 ZH"
echo "Sprachwahl wird in localStorage gespeichert."

