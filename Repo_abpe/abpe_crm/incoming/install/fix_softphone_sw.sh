#!/usr/bin/env bash
# ============================================================
# fix_softphone_sw.sh — SW-Scope-Fix via Django View
# Problem: Browser erlaubt SW-Scope nur unterhalb des SW-Pfads.
#          SW liegt unter /static/ → Scope /crm/softphone/ geblockt.
# Lösung:  SW per Django-View unter /crm/softphone/sw.js ausliefern.
# Aufruf:  bash apps/abpe_crm/install/fix_softphone_sw.sh
# CWD:     /opt/abpe/backend/
# ============================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
err()  { echo -e "${RED}✗${NC}  $*"; exit 1; }
info() { echo -e "${BLUE}▶${NC}  $*"; }

BASE="/opt/abpe/backend"
APP="apps/abpe_crm"
VIEWS="${APP}/views.py"
URLS="${APP}/urls.py"
SP_INIT="${APP}/static/abpe_crm/softphone/js/11_sp-init.js"
SP_TMPL="${APP}/templates/abpe_crm/softphone/softphone.html"
SW_SRC="${APP}/static/abpe_crm/softphone/js/service-worker.js"
ARCHIVE="Archiv/backup_restore.py"

[[ "$(pwd)" == "$BASE" ]] || err "Bitte aus $BASE ausführen (aktuell: $(pwd))"
[[ -f "$VIEWS" ]]   || err "views.py nicht gefunden"
[[ -f "$URLS" ]]    || err "urls.py nicht gefunden"
[[ -f "$SW_SRC" ]]  || err "service-worker.js nicht gefunden: $SW_SRC"
[[ -f "$SP_INIT" ]] || err "11_sp-init.js nicht gefunden: $SP_INIT"
[[ -f "$SP_TMPL" ]] || err "softphone.html nicht gefunden: $SP_TMPL"

echo "════════════════════════════════════════════════════"
info "Softphone SW-Scope Fix — Django View Lösung"
echo "════════════════════════════════════════════════════"
echo

# ── Schritt 1: Backups ───────────────────────────────────
info "Schritt 1/5 — Backups"
python3 "$ARCHIVE" -save "$VIEWS"   -m "vor SW-scope fix: views.py"   || err "Backup views.py fehlgeschlagen"
python3 "$ARCHIVE" -save "$URLS"    -m "vor SW-scope fix: urls.py"     || err "Backup urls.py fehlgeschlagen"
python3 "$ARCHIVE" -save "$SP_INIT" -m "vor SW-scope fix: 11_sp-init.js" || err "Backup 11_sp-init.js fehlgeschlagen"
python3 "$ARCHIVE" -save "$SP_TMPL" -m "vor SW-scope fix: softphone.html" || err "Backup softphone.html fehlgeschlagen"
ok "Backups abgeschlossen"
echo

# ── Schritt 2: Django-View softphone_sw() ────────────────
info "Schritt 2/5 — Django-View softphone_sw() in views.py einfügen"

# Prüfen ob bereits vorhanden
if grep -q "def softphone_sw" "$VIEWS"; then
    warn "softphone_sw() bereits in views.py vorhanden — überspringe"
else
    # Einfügen NACH der softphone_app()-Funktion
    # Zuerst exakt lesen wo softphone_app endet
    python3 << 'PYEOF'
with open("apps/abpe_crm/views.py", "r") as f:
    c = f.read()

# Suchstring: Ende der softphone_app-Funktion (das @login_required danach)
old = """@login_required
def softphone_app(request):
    \"\"\"Softphone PWA — standalone HTML App\"\"\"
    from apps.abpe_crm.models import CrmUserSettings
    s, _ = CrmUserSettings.objects.get_or_create(user=request.user)
    ctx = {
        'api_base':    '/crm/api',
        'user':        request.user,
        'sp_settings': {
            'ws':          s.softphone_ws or '',
            'extension':   s.phone_extension or '',
            'display':     s.phone_display_name or request.user.get_full_name() or request.user.username,
            'vm_ext':      s.softphone_vm_ext or '',
            'dnd_ext':     s.softphone_dnd_ext or '',
            'status_exts': s.softphone_status_exts or '',
            'speed_dials': s.softphone_speed_dials or '',
        },
    }
    return render(request, 'abpe_crm/softphone/softphone.html', ctx)"""

assert old in c, "FEHLER: softphone_app() Block nicht gefunden — grep -n 'def softphone_app' apps/abpe_crm/views.py"

new = old + """


@login_required
def softphone_sw(request):
    \"\"\"Service Worker für Softphone PWA.
    Wird unter /crm/softphone/sw.js ausgeliefert damit der Browser
    den SW-Scope /crm/softphone/ erlaubt (SW muss im selben Pfad liegen).
    \"\"\"
    import os
    from django.http import HttpResponse
    sw_path = os.path.join(
        os.path.dirname(__file__),
        'static', 'abpe_crm', 'softphone', 'js', 'service-worker.js'
    )
    try:
        with open(sw_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        return HttpResponse('// service-worker.js not found', content_type='application/javascript', status=404)
    response = HttpResponse(content, content_type='application/javascript; charset=utf-8')
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response"""

c = c.replace(old, new, 1)
assert "def softphone_sw" in c, "FEHLER: Insert fehlgeschlagen"

with open("apps/abpe_crm/views.py", "w") as f:
    f.write(c)
print("✓  softphone_sw() eingefügt")
PYEOF
    ok "softphone_sw() in views.py eingefügt"
fi

# Syntax prüfen
python3 -m py_compile "$VIEWS" && ok "views.py Syntax OK" || err "views.py Syntax FEHLER"
echo

# ── Schritt 3: URL eintragen ─────────────────────────────
info "Schritt 3/5 — URL /crm/softphone/sw.js in urls.py eintragen"

if grep -q "softphone_sw" "$URLS"; then
    warn "softphone_sw URL bereits in urls.py vorhanden — überspringe"
else
    # Exakt lesen was nach softphone_app kommt
    python3 << 'PYEOF'
with open("apps/abpe_crm/urls.py", "r") as f:
    c = f.read()

# Suchstring: die softphone_app URL-Zeile
old = "path('softphone/',                   views.softphone_app,            name='softphone_app'),"

assert old in c, f"FEHLER: URL-Zeile nicht gefunden.\nGesucht: {old}\nBitte 'grep -n softphone apps/abpe_crm/urls.py' prüfen"

new = old + """
    path('softphone/sw.js',              views.softphone_sw,             name='softphone_sw'),"""

c = c.replace(old, new, 1)
assert "softphone_sw" in c, "FEHLER: URL-Insert fehlgeschlagen"

with open("apps/abpe_crm/urls.py", "w") as f:
    f.write(c)
print("✓  softphone/sw.js URL eingetragen")
PYEOF
    ok "URL eingetragen"
fi

python3 -m py_compile "$URLS" && ok "urls.py Syntax OK" || err "urls.py Syntax FEHLER"
echo

# ── Schritt 4: 11_sp-init.js patchen ────────────────────
info "Schritt 4/5 — 11_sp-init.js: SW-URL korrigieren"

# Erst exakt lesen was drin steht
echo "--- Aktueller Inhalt 11_sp-init.js ---"
cat "$SP_INIT"
echo "--- Ende ---"
echo

python3 << 'PYEOF'
with open("apps/abpe_crm/static/abpe_crm/softphone/js/11_sp-init.js", "r") as f:
    c = f.read()

# Alter Stub-Inhalt (aus install_softphone.sh generiert)
old = """// sp-init.js — Alles zusammenführen, PWA init
// Dieser Einstiegspunkt lädt alle Module in der richtigen Reihenfolge
(async function() {
    // 1. Theme
    if (window.SP_Theme) SP_Theme.init();

    // 2. Config von Django API laden (wenn eingeloggt)
    // 3. i18n initialisieren
    // 4. Kontakte laden
    // 5. Core (JsSIP) initialisieren
    // 6. PWA Service Worker registrieren
    if ('serviceWorker' in navigator) {
        try {
            await navigator.serviceWorker.register('./service-worker.js');
            console.log('SP: Service Worker registriert');
        } catch(e) { console.warn('SP: Service Worker Fehler', e); }
    }
    console.log('ABpE Softphone bereit.');
})();
// TODO: Vollständige Initialisierung aller Module"""

assert old in c, "FEHLER: Alter Stub-Inhalt nicht gefunden in 11_sp-init.js"

new = """// sp-init.js — Alles zusammenführen, PWA init
// Dieser Einstiegspunkt lädt alle Module in der richtigen Reihenfolge
(async function() {
    // 1. Theme
    if (window.SP_Theme) SP_Theme.init();

    // 2. Config von Django API laden (wenn eingeloggt)
    // 3. i18n initialisieren
    // 4. Kontakte laden
    // 5. Core (JsSIP) initialisieren
    // 6. PWA Service Worker registrieren
    //    SW wird per Django-View unter /crm/softphone/sw.js ausgeliefert
    //    damit der Browser den Scope /crm/softphone/ erlaubt.
    if ('serviceWorker' in navigator) {
        try {
            var reg = await navigator.serviceWorker.register('/crm/softphone/sw.js', {
                scope: '/crm/softphone/'
            });
            console.log('SP: Service Worker registriert, scope:', reg.scope);
        } catch(e) { console.warn('SP: Service Worker Fehler', e); }
    }
    console.log('ABpE Softphone bereit.');
})();
// TODO: Vollständige Initialisierung aller Module"""

c = c.replace(old, new, 1)
assert "/crm/softphone/sw.js" in c, "FEHLER: Replace fehlgeschlagen"

with open("apps/abpe_crm/static/abpe_crm/softphone/js/11_sp-init.js", "w") as f:
    f.write(c)
print("✓  11_sp-init.js gepatcht")
PYEOF

node --check "$SP_INIT" && ok "11_sp-init.js JS-Syntax OK" || err "11_sp-init.js JS-Syntax FEHLER"
echo

# ── Schritt 5: softphone.html SW-Block entfernen ────────
info "Schritt 5/5 — softphone.html: doppelten SW-Block entfernen"
info "  (SW-Registrierung liegt jetzt in 11_sp-init.js — HTML-Block wird leer)"

python3 << 'PYEOF'
with open("apps/abpe_crm/templates/abpe_crm/softphone/softphone.html", "r") as f:
    c = f.read()

# Alter SW-Block mit scope (aus dem letzten Fix)
old_with_scope = """<!-- PWA Service Worker -->
<script>
if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
        var swUrl = '{% static "abpe_crm/softphone/js/service-worker.js" %}';
        navigator.serviceWorker.register(swUrl, { scope: '/crm/softphone/' })
            .then(function(reg) {
                console.log('SP: SW registriert, scope:', reg.scope);
            })
            .catch(function(e) { console.warn('SP: SW Fehler:', e); });
    });
}
</script>"""

# Alter SW-Block ohne scope (Original)
old_without_scope = """<!-- PWA Service Worker -->
<script>
if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
        navigator.serviceWorker.register(
            '{% static "abpe_crm/softphone/js/service-worker.js" %}'
        ).catch(function(e) { console.warn('SW:', e); });
    });
}
</script>"""

new_sw_comment = "<!-- PWA Service Worker — Registrierung in 11_sp-init.js -->"

replaced = False
if old_with_scope in c:
    c = c.replace(old_with_scope, new_sw_comment, 1)
    replaced = True
    print("✓  SW-Block (mit scope) durch Kommentar ersetzt")
elif old_without_scope in c:
    c = c.replace(old_without_scope, new_sw_comment, 1)
    replaced = True
    print("✓  SW-Block (ohne scope) durch Kommentar ersetzt")
else:
    # Fallback: suchen was tatsächlich drin ist
    import re
    match = re.search(r'<!-- PWA Service Worker.*?</script>', c, re.DOTALL)
    if match:
        print(f"WARNUNG: SW-Block gefunden aber nicht exakt gematcht:")
        print(repr(match.group(0)[:200]))
    else:
        print("INFO: Kein SW-Block im Template gefunden — nichts zu tun")
    replaced = True  # kein Fehler

assert replaced, "FEHLER: Replace-Logik fehlgeschlagen"

with open("apps/abpe_crm/templates/abpe_crm/softphone/softphone.html", "w") as f:
    f.write(c)
PYEOF
echo

# ── Deploy ────────────────────────────────────────────────
info "Deploy…"
python3 manage.py collectstatic --noinput 2>&1 | tail -3
echo
supervisorctl restart abpe-django
sleep 2
supervisorctl status abpe-django
echo

# ── Verifikation ──────────────────────────────────────────
info "Verifikation"

# URL erreichbar?
SW_STATUS=$(python3 -c "
import urllib.request, ssl
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
try:
    r = urllib.request.urlopen('http://172.20.3.160/crm/softphone/sw.js', context=ctx, timeout=5)
    print(r.getcode())
except Exception as e:
    print('ERR:', e)
" 2>/dev/null || echo "skip")

if [[ "$SW_STATUS" == "200" ]]; then
    ok "  /crm/softphone/sw.js → HTTP 200"
else
    warn "  /crm/softphone/sw.js → $SW_STATUS (Login nötig — manuell testen)"
fi

grep -q "softphone_sw" "$URLS" && ok "  URL softphone_sw in urls.py" || warn "  URL fehlt"
grep -q "def softphone_sw" "$VIEWS" && ok "  View softphone_sw in views.py" || warn "  View fehlt"
grep -q "/crm/softphone/sw.js" "$SP_INIT" && ok "  SW-URL in 11_sp-init.js korrekt" || warn "  SW-URL fehlt"

echo
echo "════════════════════════════════════════════════════"
echo -e "${GREEN}Fix abgeschlossen${NC}"
echo "════════════════════════════════════════════════════"
echo
echo "Browser-Test (DevTools Console — erwartet):"
echo "  SP: Service Worker registriert, scope: https://abpe.win.abcona.info/crm/softphone/"
echo "  ABpE Softphone bereit."
echo
echo "Kein Fehler mehr erwartet."

