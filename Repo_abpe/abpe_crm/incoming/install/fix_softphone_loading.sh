#!/usr/bin/env bash
# ============================================================
# fix_softphone_loading.sh
# Fix 1: service-worker.js — contacts.json aus PRECACHE raus
# Fix 2: 6_sp-core.js — sp-loading Element entfernen nach init
# Fix 3: collectstatic + restart
# Aufruf: bash apps/abpe_crm/install/fix_softphone_loading.sh
# CWD:    /opt/abpe/backend/
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
ARCHIVE="Archiv/backup_restore.py"
SW="${APP}/static/abpe_crm/softphone/js/service-worker.js"
CORE="${APP}/static/abpe_crm/softphone/js/6_sp-core.js"

[[ "$(pwd)" == "$BASE" ]] || err "Bitte aus $BASE ausführen"

echo "════════════════════════════════════════════════════"
info "Fix: Ladezeit + sp-loading Indikator"
echo "════════════════════════════════════════════════════"
echo

# ── Backup ────────────────────────────────────────────────
info "Backup"
python3 "$ARCHIVE" -save "$SW"   -m "vor loading fix: service-worker.js" || err "Backup SW fehlgeschlagen"
python3 "$ARCHIVE" -save "$CORE" -m "vor loading fix: 6_sp-core.js"      || err "Backup core fehlgeschlagen"
ok "Backups OK"
echo

# ── Fix 1: service-worker.js neu schreiben ────────────────
info "Fix 1/2 — service-worker.js: contacts-URL aus PRECACHE entfernen"
info "  Ursache: /crm/api/softphone/contacts/ (21k Einträge) wurde beim"
info "  ersten Laden in den SW-Cache geladen → blockiert alles"

cat > "$SW" << 'SWEOF'
// service-worker.js — ABpE Softphone PWA Service Worker
const CACHE_NAME = 'abpe-softphone-v2';

// Nur statische Assets cachen — KEINE API-Calls, KEINE Kontakte
const PRECACHE = [
    '/static/abpe_crm/softphone/css/softphone.css',
    '/static/abpe_crm/softphone/js/vendor/jssip.min.js',
    '/static/abpe_crm/softphone/js/2_sp-config.js',
    '/static/abpe_crm/softphone/js/3_sp-i18n.js',
    '/static/abpe_crm/softphone/js/4_sp-theme.js',
    '/static/abpe_crm/softphone/js/5_sp-contacts.js',
    '/static/abpe_crm/softphone/js/6_sp-core.js',
    '/static/abpe_crm/softphone/js/7_sp-ui.js',
    '/static/abpe_crm/softphone/js/8_sp-status.js',
    '/static/abpe_crm/softphone/js/9_sp-transfer.js',
    '/static/abpe_crm/softphone/js/10_sp-fop.js',
    '/static/abpe_crm/softphone/js/11_sp-init.js',
    '/static/abpe_crm/softphone/i18n/de_phone.json',
    '/static/abpe_crm/softphone/manifest.json',
    // HTML-Seite zuletzt — nach den Assets
    '/crm/softphone/',
];

self.addEventListener('install', function(e) {
    e.waitUntil(
        caches.open(CACHE_NAME).then(function(cache) {
            // allSettled: ein fehlgeschlagener Asset stoppt nicht alles
            return Promise.allSettled(
                PRECACHE.map(function(url) { return cache.add(url); })
            );
        })
    );
    self.skipWaiting();
});

self.addEventListener('activate', function(e) {
    e.waitUntil(
        caches.keys().then(function(keys) {
            return Promise.all(
                keys.filter(function(k) { return k !== CACHE_NAME; })
                    .map(function(k) { return caches.delete(k); })
            );
        })
    );
    self.clients.claim();
});

self.addEventListener('fetch', function(e) {
    var url = e.request.url;

    // API-Calls, WS, Kontakte NIEMALS cachen
    if (url.includes('/crm/api/')
     || url.includes('/api/')
     || url.startsWith('wss://')
     || url.startsWith('ws://')
     || url.includes('contacts')) {
        return; // netzwerk direkt, kein cache
    }

    e.respondWith(
        caches.match(e.request).then(function(cached) {
            if (cached) return cached;
            return fetch(e.request).catch(function() {
                if (e.request.mode === 'navigate') {
                    return caches.match('/crm/softphone/');
                }
            });
        })
    );
});
SWEOF
node --check "$SW" && ok "service-worker.js Syntax OK" || err "service-worker.js Syntax FEHLER"
echo

# ── Fix 2: 6_sp-core.js — sp-loading entfernen nach init ─
info "Fix 2/2 — 6_sp-core.js: sp-loading Element nach init() entfernen"

# Exakt lesen wo init() endet
grep -n "sp-loading\|DOMContentLoaded\|Softphone.init" "$CORE" | head -10
echo

python3 << 'PYEOF'
with open("apps/abpe_crm/static/abpe_crm/softphone/js/6_sp-core.js", "r") as f:
    c = f.read()

old = """document.addEventListener('DOMContentLoaded', function() { Softphone.init(); });"""

assert old in c, "FEHLER: DOMContentLoaded-Zeile nicht gefunden in 6_sp-core.js"

new = """document.addEventListener('DOMContentLoaded', function() {
    Softphone.init();
    // Ladeindikator entfernen
    var loading = document.getElementById('sp-loading');
    if (loading) loading.style.display = 'none';
});"""

c = c.replace(old, new, 1)
assert "sp-loading" in c, "FEHLER: Replace fehlgeschlagen"

with open("apps/abpe_crm/static/abpe_crm/softphone/js/6_sp-core.js", "w") as f:
    f.write(c)
print("✓  sp-loading Entfernung in 6_sp-core.js eingefügt")
PYEOF

node --check "$CORE" && ok "6_sp-core.js Syntax OK" || err "6_sp-core.js Syntax FEHLER"
echo

# ── Alten SW-Cache im Browser löschen ────────────────────
info "Hinweis: Alter SW-Cache muss im Browser gelöscht werden"
warn "DevTools → Application → Storage → 'Clear site data'"
warn "ODER: DevTools → Application → Service Workers → 'Unregister'"
warn "DANN: Hard-Reload (Ctrl+Shift+R)"
echo

# ── Deploy ────────────────────────────────────────────────
info "Deploy…"
python3 manage.py collectstatic --noinput 2>&1 | tail -3
echo
supervisorctl restart abpe-django
sleep 2
supervisorctl status abpe-django
echo

echo "════════════════════════════════════════════════════"
echo -e "${GREEN}Fix abgeschlossen${NC}"
echo "════════════════════════════════════════════════════"
echo
echo "WICHTIG — Browser-Schritte:"
echo "  1. DevTools öffnen (F12)"
echo "  2. Application → Service Workers → 'Unregister'"
echo "  3. Application → Storage → 'Clear site data'"
echo "  4. Tab schließen und neu öffnen"
echo "  5. https://abpe.win.abcona.info/crm/softphone/"
echo
echo "Erwartet: Widget sofort sichtbar, kein langer Ladevorgang"

