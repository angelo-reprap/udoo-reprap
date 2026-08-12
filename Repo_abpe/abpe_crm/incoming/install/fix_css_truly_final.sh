#!/usr/bin/env bash
# fix_css_truly_final.sh — Wirklich letzter Pass
set -euo pipefail
GREEN='\033[0;32m'; BLUE='\033[0;34m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
info() { echo -e "${BLUE}▶${NC}  $*"; }

BASE="/opt/abpe/backend"
APP="apps/abpe_crm"
JS9="${APP}/static/abpe_crm/softphone/js/9_sp-transfer.js"
JS10="${APP}/static/abpe_crm/softphone/js/10_sp-fop.js"

[[ "$(pwd)" == "$BASE" ]] || { echo "Falsches Verzeichnis"; exit 1; }

python3 Archiv/backup_restore.py -save "$JS9"  -m "truly final css: 9_sp-transfer.js" || exit 1
python3 Archiv/backup_restore.py -save "$JS10" -m "truly final css: 10_sp-fop.js"     || exit 1
ok "Backups OK"
echo

python3 << 'PYEOF'
# ── 9_sp-transfer.js: border-top #1e4080 ─────────────────
with open("apps/abpe_crm/static/abpe_crm/softphone/js/9_sp-transfer.js", "r") as f:
    c = f.read()

# Zeile 94-95: border-top:0.5px solid #1e4080
c = c.replace(
    "            + 'border-top:0.5px solid #1e4080\" '",
    "            + 'border-top:0.5px solid var(--border-color)\" '"
)

with open("apps/abpe_crm/static/abpe_crm/softphone/js/9_sp-transfer.js", "w") as f:
    f.write(c)
print("✓  9_sp-transfer.js: #1e4080 → var(--border-color)")

# ── 10_sp-fop.js ─────────────────────────────────────────
with open("apps/abpe_crm/static/abpe_crm/softphone/js/10_sp-fop.js", "r") as f:
    c = f.read()

# Zeile 78: BLUE_HOV border-top
c = c.replace(
    "';border-top:0.5px solid #1e4080;",
    "';border-top:0.5px solid var(--border-color);"
)

# Zeile 102: DND-Toggle Button (Quote-Stil mit doppelten Anführungszeichen)
c = c.replace(
    'style="font-size:10px;padding:2px 6px;border:0.5px solid #fca5a5;border-radius:3px;cursor:pointer;background:#fee2e2;color:#7f1d1d">',
    'style="font-size:10px;padding:2px 6px;border:0.5px solid var(--status-dnd-border);border-radius:3px;cursor:pointer;background:var(--status-dnd-bg);color:var(--status-dnd-color)">'
)

# Zeile 127: Abholen-Button (Quote-Stil mit doppelten Anführungszeichen)
c = c.replace(
    'style="font-size:10px;padding:1px 5px;border:0.5px solid #86efac;border-radius:3px;cursor:pointer;background:#f0fdf4;color:#14532d">&#9742; Abholen</span>',
    'style="font-size:10px;padding:1px 5px;border:0.5px solid var(--action-ok-border);border-radius:3px;cursor:pointer;background:var(--action-ok-bg);color:var(--action-ok-color)">&#9742; Abholen</span>'
)

# Zeile 157: Konf-Button (Quote-Stil mit doppelten Anführungszeichen)
c = c.replace(
    'style="font-size:10px;padding:1px 5px;border:0.5px solid #86efac;border-radius:3px;cursor:pointer;background:#f0fdf4;color:#14532d">&#8594; Konf</span>',
    'style="font-size:10px;padding:1px 5px;border:0.5px solid var(--action-ok-border);border-radius:3px;cursor:pointer;background:var(--action-ok-bg);color:var(--action-ok-color)">&#8594; Konf</span>'
)

with open("apps/abpe_crm/static/abpe_crm/softphone/js/10_sp-fop.js", "w") as f:
    f.write(c)
print("✓  10_sp-fop.js: alle restlichen Farben ersetzt")
PYEOF

node --check "$JS9"  && ok "9_sp-transfer.js  Syntax OK" || { echo "FEHLER"; exit 1; }
node --check "$JS10" && ok "10_sp-fop.js      Syntax OK" || { echo "FEHLER"; exit 1; }
echo

# ── Finaler Check — nur echte Hardcodes, keine Fallbacks ─
info "Finaler Check (Fallbacks #f8f8f8, #dbeafe, #9ca3af werden ignoriert)"
echo ""

IGNORE="var(--\|22c55e\|ef4444\|163258\|theme-color\|f59e0b\|9ca3af\|0f6e56\|dc2626\|f8f8f8\|dbeafe\|fbbf24"

for f in "$JS9" "$JS10"; do
    remaining=$(grep -n "#[0-9a-fA-F]\{6\}" "$f" | grep -v "$IGNORE" || true)
    if [[ -z "$remaining" ]]; then
        ok "  $(basename $f) — sauber ✓"
    else
        echo "  NOCH OFFEN $(basename $f):"
        echo "$remaining"
    fi
done
echo

info "Deploy"
python3 manage.py collectstatic --noinput 2>&1 | tail -2
supervisorctl restart abpe-django
sleep 2
supervisorctl status abpe-django
echo
ok "Fertig"
echo
echo "Finaler Gesamt-Check:"
echo "  grep -rn '#[0-9a-fA-F]\{6\}' apps/abpe_crm/static/abpe_crm/softphone/js/ apps/abpe_crm/templates/abpe_crm/softphone/ | grep -v 'var(--\|22c55e\|ef4444\|163258\|theme-color\|f59e0b\|9ca3af\|0f6e56\|dc2626\|f8f8f8\|dbeafe\|fbbf24'"

