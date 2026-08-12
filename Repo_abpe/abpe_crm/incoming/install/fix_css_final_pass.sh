#!/usr/bin/env bash
# fix_css_final_pass.sh — Letzter Pass: alle restlichen hardcodierten Farben
set -euo pipefail
GREEN='\033[0;32m'; BLUE='\033[0;34m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
info() { echo -e "${BLUE}▶${NC}  $*"; }

BASE="/opt/abpe/backend"
APP="apps/abpe_crm"
CSS="${APP}/static/abpe_crm/softphone/css/softphone.css"
JS9="${APP}/static/abpe_crm/softphone/js/9_sp-transfer.js"
JS10="${APP}/static/abpe_crm/softphone/js/10_sp-fop.js"
TMPL="${APP}/templates/abpe_crm/softphone/softphone.html"

[[ "$(pwd)" == "$BASE" ]] || { echo "Falsches Verzeichnis"; exit 1; }

python3 Archiv/backup_restore.py -save "$JS9"  -m "css final pass: 9_sp-transfer.js"  || exit 1
python3 Archiv/backup_restore.py -save "$JS10" -m "css final pass: 10_sp-fop.js"       || exit 1
python3 Archiv/backup_restore.py -save "$TMPL" -m "css final pass: softphone.html"     || exit 1
python3 Archiv/backup_restore.py -save "$CSS"  -m "css final pass: softphone.css"      || exit 1
ok "Backups OK"
echo

# ── Neue CSS-Variablen ergänzen ───────────────────────────
info "CSS: neue Variablen für Ankündigen-Button und Zurück-Button"

cat >> "$CSS" << 'CSSEOF'

/* ── Ankündigen / Zurück Buttons ─────────────────────────── */
:root {
    --btn-announce-bg:    #0f6e56;
    --btn-announce-color: #ffffff;
    --btn-cancel-bg:      #dc2626;
    --btn-cancel-color:   #ffffff;
    --header-status-muted: #8ba8c8;
}
[data-theme="dark"] {
    --btn-announce-bg:    #065f46;
    --btn-announce-color: #86efac;
    --btn-cancel-bg:      #7f1d1d;
    --btn-cancel-color:   #fca5a5;
    --header-status-muted: #4a6a8a;
}
CSSEOF
ok "CSS-Variablen ergänzt"
echo

# ── Python-Patch ──────────────────────────────────────────
info "Patche 9_sp-transfer.js, 10_sp-fop.js, softphone.html"

python3 << 'PYEOF'
import sys

# ── 9_sp-transfer.js ─────────────────────────────────────
with open("apps/abpe_crm/static/abpe_crm/softphone/js/9_sp-transfer.js", "r") as f:
    c = f.read()

# Ankündigen-Button #0f6e56
c = c.replace(
    "'style=\"flex:1;padding:5px 4px;background:#0f6e56;color:#fff;border:none;border-radius:5px;font-size:10px;cursor:pointer\">&#9742; Ankündigen</button>'",
    "'style=\"flex:1;padding:5px 4px;background:var(--btn-announce-bg);color:var(--btn-announce-color);border:none;border-radius:5px;font-size:10px;cursor:pointer\">&#9742; Ankündigen</button>'"
)
# Zurück-Button #dc2626
c = c.replace(
    "'style=\"flex:1;padding:5px 4px;background:#dc2626;color:#fff;border:none;border-radius:5px;font-size:10px;cursor:pointer\">&#9746; Zur\\u00fcck</button>'",
    "'style=\"flex:1;padding:5px 4px;background:var(--btn-cancel-bg);color:var(--btn-cancel-color);border:none;border-radius:5px;font-size:10px;cursor:pointer\">&#9746; Zur\\u00fcck</button>'"
)

with open("apps/abpe_crm/static/abpe_crm/softphone/js/9_sp-transfer.js", "w") as f:
    f.write(c)
print("✓  9_sp-transfer.js")

# ── 10_sp-fop.js ─────────────────────────────────────────
with open("apps/abpe_crm/static/abpe_crm/softphone/js/10_sp-fop.js", "r") as f:
    c = f.read()

# DND-Toggle Button (noch nicht ersetzt)
c = c.replace(
    '\'style="font-size:10px;padding:2px 6px;border:0.5px solid #fca5a5;border-radius:3px;cursor:pointer;background:#fee2e2;color:#7f1d1d">\'',
    '\'style="font-size:10px;padding:2px 6px;border:0.5px solid var(--status-dnd-border);border-radius:3px;cursor:pointer;background:var(--status-dnd-bg);color:var(--status-dnd-color)">\''
)
# Abholen-Button (noch nicht ersetzt — zweite Instanz)
c = c.replace(
    '\'style="font-size:10px;padding:1px 5px;border:0.5px solid #86efac;border-radius:3px;cursor:pointer;background:#f0fdf4;color:#14532d">&#9742; Abholen</span>\'',
    '\'style="font-size:10px;padding:1px 5px;border:0.5px solid var(--action-ok-border);border-radius:3px;cursor:pointer;background:var(--action-ok-bg);color:var(--action-ok-color)">&#9742; Abholen</span>\''
)
# Park-Button (noch nicht ersetzt)
c = c.replace(
    '\'style="font-size:10px;padding:1px 5px;border:0.5px solid #7dd3fc;border-radius:3px;cursor:pointer;background:#e0f2fe;color:#0c4a6e">&#8659; Park</span>\'',
    '\'style="font-size:10px;padding:1px 5px;border:0.5px solid var(--action-info-border);border-radius:3px;cursor:pointer;background:var(--action-info-bg);color:var(--action-info-color)">&#8659; Park</span>\''
)
# Konf-Button (noch nicht ersetzt)
c = c.replace(
    '\'style="font-size:10px;padding:1px 5px;border:0.5px solid #86efac;border-radius:3px;cursor:pointer;background:#f0fdf4;color:#14532d">&#8594; Konf</span>\'',
    '\'style="font-size:10px;padding:1px 5px;border:0.5px solid var(--action-ok-border);border-radius:3px;cursor:pointer;background:var(--action-ok-bg);color:var(--action-ok-color)">&#8594; Konf</span>\''
)

with open("apps/abpe_crm/static/abpe_crm/softphone/js/10_sp-fop.js", "w") as f:
    f.write(c)
print("✓  10_sp-fop.js")

# ── softphone.html ────────────────────────────────────────
with open("apps/abpe_crm/templates/abpe_crm/softphone/softphone.html", "r") as f:
    c = f.read()

# Header Status-Text #8ba8c8
c = c.replace(
    '<span id="sp-status-text" style="font-size:10px;color:#8ba8c8">Nicht verbunden</span>',
    '<span id="sp-status-text" style="font-size:10px;color:var(--header-status-muted)">Nicht verbunden</span>'
)

with open("apps/abpe_crm/templates/abpe_crm/softphone/softphone.html", "w") as f:
    f.write(c)
print("✓  softphone.html")
PYEOF

node --check "$JS9"  && ok "9_sp-transfer.js  Syntax OK" || { echo "FEHLER JS9";  exit 1; }
node --check "$JS10" && ok "10_sp-fop.js      Syntax OK" || { echo "FEHLER JS10"; exit 1; }
echo

# ── Abschluss-Check ───────────────────────────────────────
info "Abschluss-Check"
echo ""
for f in "$JS9" "$JS10" "$TMPL"; do
    remaining=$(grep -on "#[0-9a-fA-F]\{6\}" "$f" \
        | grep -v "var(--\|22c55e\|ef4444\|163258\|theme-color" \
        | grep -v "0f6e56\|dc2626\|f59e0b\|9ca3af" \
        || true)
    if [[ -z "$remaining" ]]; then
        ok "  $(basename $f) — sauber"
    else
        echo "  WARNUNG $(basename $f):"
        echo "$remaining" | head -10
    fi
done
echo

info "Deploy"
python3 manage.py collectstatic --noinput 2>&1 | tail -2
supervisorctl restart abpe-django
sleep 2
supervisorctl status abpe-django
echo
ok "Fertig — Hard-Reload (Ctrl+Shift+R)"
echo
echo "Danach: finaler grep zur Bestätigung:"
echo "  grep -rn '#[0-9a-fA-F]\{6\}' apps/abpe_crm/static/abpe_crm/softphone/js/ apps/abpe_crm/templates/abpe_crm/softphone/ | grep -v 'var(--\|22c55e\|ef4444\|163258\|theme-color\|f59e0b\|9ca3af\|0f6e56\|dc2626'"


