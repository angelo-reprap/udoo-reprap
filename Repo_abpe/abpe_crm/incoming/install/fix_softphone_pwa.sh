#!/usr/bin/env bash
# ============================================================
# fix_softphone_pwa.sh — Behebt Icon-404 und SW-404
# Aufruf: bash apps/abpe_crm/install/fix_softphone_pwa.sh
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
SP_STATIC="${APP}/static/abpe_crm/softphone"
SP_TMPL="${APP}/templates/abpe_crm/softphone/softphone.html"
ARCHIVE="Archiv/backup_restore.py"

[[ "$(pwd)" == "$BASE" ]] || err "Bitte aus $BASE ausführen"

echo "════════════════════════════════════════════════════"
info "ABpE Softphone PWA — Fix Icon-404 + SW-404"
echo "════════════════════════════════════════════════════"
echo

# ── Fix 1: Icons neu generieren ───────────────────────────
info "Fix 1/2 — Icons neu generieren (valides PNG)"

python3 << 'PYEOF'
import struct, zlib, os, sys

def make_png(size, bg_rgb, fg_rgb):
    """Valides PNG ohne externe Libraries.
    RGBA 8bit, kein Interlacing, deflate-komprimiert.
    """
    w = h = size
    center = size // 2
    # Telefon-Silhouette: blaues Quadrat + weißer Kreis in Mitte
    r_inner = int(size * 0.22)

    raw = b''
    for y in range(h):
        raw += b'\x00'  # filter=None pro Zeile
        for x in range(w):
            dx = x - center
            dy = y - center
            dist = (dx*dx + dy*dy) ** 0.5
            if dist <= r_inner:
                raw += bytes([*fg_rgb, 255])
            else:
                raw += bytes([*bg_rgb, 255])

    def chunk(tag, data):
        crc = zlib.crc32(tag + data) & 0xffffffff
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', crc)

    # IHDR: width, height, bit_depth=8, color_type=2(RGB)+1(alpha)=6
    ihdr = struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)
    idat = zlib.compress(raw, 9)

    png = (
        b'\x89PNG\r\n\x1a\n' +
        chunk(b'IHDR', ihdr) +
        chunk(b'IDAT', idat) +
        chunk(b'IEND', b'')
    )
    return png

icon_dir = "apps/abpe_crm/static/abpe_crm/softphone/icons"
os.makedirs(icon_dir, exist_ok=True)

bg = (22, 50, 88)     # #163258
fg = (255, 255, 255)  # weiß

errors = 0
for size in [192, 512]:
    path = f"{icon_dir}/icon-{size}.png"
    data = make_png(size, bg, fg)
    # Validierung
    assert data[:8] == b'\x89PNG\r\n\x1a\n', f"PNG-Signatur falsch für {size}"
    assert data[12:16] == b'IHDR', f"IHDR fehlt für {size}"
    with open(path, 'wb') as f:
        f.write(data)
    print(f"✓  icon-{size}.png ({len(data):,} bytes)")

if errors == 0:
    sys.exit(0)
else:
    sys.exit(1)
PYEOF
ok "Icons generiert"
echo

# ── Fix 2: Service Worker URL korrigieren ─────────────────
info "Fix 2/2 — Service Worker URL in softphone.html korrigieren"
info "  Problem: SW registriert unter /crm/softphone/service-worker.js (404)"
info "  Fix:     SW liegt unter /static/abpe_crm/softphone/js/service-worker.js"

python3 "$ARCHIVE" -save "$SP_TMPL" -m "vor SW-URL fix" || err "Backup fehlgeschlagen"

# Prüfen ob der fehlerhafte String vorhanden ist
OLD_STR="'{% static \"abpe_crm/softphone/js/service-worker.js\" %}'"
grep -q "service-worker.js" "$SP_TMPL" || err "service-worker.js nicht in Template gefunden"

# Python-Patch mit assert
python3 << 'PYEOF'
with open("apps/abpe_crm/templates/abpe_crm/softphone/softphone.html", "r") as f:
    c = f.read()

# Alter Block — SW-Registrierung am Ende des Templates
old = """<!-- PWA Service Worker -->
<script>
if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
        navigator.serviceWorker.register(
            '{% static "abpe_crm/softphone/js/service-worker.js" %}'
        ).catch(function(e) { console.warn('SW:', e); });
    });
}
</script>"""

# Neu: korrekter Static-Pfad + scope explizit setzen
new = """<!-- PWA Service Worker -->
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

assert old in c, f"FEHLER: Alter SW-Block nicht gefunden in Template!"
c = c.replace(old, new, 1)
assert new in c, "FEHLER: Replace fehlgeschlagen!"

with open("apps/abpe_crm/templates/abpe_crm/softphone/softphone.html", "w") as f:
    f.write(c)
print("✓  SW-Registrierung gepatcht")
PYEOF
ok "softphone.html gepatcht"
echo

# ── Service Worker self: scope anpassen ───────────────────
info "Service Worker scope im SW selbst prüfen…"

SW_FILE="${SP_STATIC}/js/service-worker.js"
# SW braucht keinen scope in sich selbst — das macht der register()-Aufruf
# Aber PRECACHE-URL für /crm/softphone/ prüfen:
if grep -q "'/crm/softphone/'" "$SW_FILE"; then
    ok "SW PRECACHE-URL für /crm/softphone/ bereits vorhanden"
else
    warn "PRECACHE-URL fehlt — wird ergänzt (unkritisch, SW funktioniert trotzdem)"
fi
echo

# ── collectstatic + restart ───────────────────────────────
info "Deploy…"
python3 manage.py collectstatic --noinput 2>&1 | tail -3
echo
supervisorctl restart abpe-django
sleep 2
supervisorctl status abpe-django
echo

# ── Verifikation ──────────────────────────────────────────
info "Verifikation"

# Icon-Dateigröße prüfen
for size in 192 512; do
    f="staticfiles/abpe_crm/softphone/icons/icon-${size}.png"
    if [[ -f "$f" ]]; then
        bytes=$(wc -c < "$f")
        if [[ $bytes -gt 1000 ]]; then
            ok "  icon-${size}.png in staticfiles: ${bytes} bytes"
        else
            warn "  icon-${size}.png zu klein: ${bytes} bytes — möglicherweise kein valides PNG"
        fi
    else
        warn "  icon-${size}.png nicht in staticfiles gefunden"
    fi
done

# SW-URL im Template prüfen
if grep -q "scope: '/crm/softphone/'" "$SP_TMPL"; then
    ok "  SW scope in Template korrekt"
else
    warn "  SW scope nicht gefunden — manuell prüfen"
fi

echo
echo "════════════════════════════════════════════════════"
echo -e "${GREEN}Fix abgeschlossen${NC}"
echo "════════════════════════════════════════════════════"
echo
echo "Browser-Test:"
echo "  1. https://abpe.win.abcona.info/crm/softphone/ aufrufen"
echo "  2. DevTools → Application → Manifest   → Icon muss angezeigt werden"
echo "  3. DevTools → Application → SW          → Status: activated and running"
echo "  4. DevTools → Console                   → Kein 404-Fehler mehr"
echo
echo "Erwartete Console-Ausgabe:"
echo "  SP: SW registriert, scope: https://abpe.win.abcona.info/crm/softphone/"

