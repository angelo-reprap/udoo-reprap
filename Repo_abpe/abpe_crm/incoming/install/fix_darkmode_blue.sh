#!/usr/bin/env bash
# fix_darkmode_blue.sh — Abcona-Blau im Dark Mode durch Dunkelgrau ersetzen
set -euo pipefail
GREEN='\033[0;32m'; NC='\033[0m'
ok() { echo -e "${GREEN}✓${NC} $*"; }

BASE="/opt/abpe/backend"
CSS="apps/abpe_crm/static/abpe_crm/softphone/css/softphone.css"
[[ "$(pwd)" == "$BASE" ]] || { echo "Falsches Verzeichnis"; exit 1; }

python3 Archiv/backup_restore.py -save "$CSS" -m "vor blue dark mode fix" || exit 1

python3 << 'PYEOF'
with open("apps/abpe_crm/static/abpe_crm/softphone/css/softphone.css", "r") as f:
    c = f.read()

old = """[data-theme="dark"] {
    --abcona-blue:       #2a3f5f;
    --abcona-blue-dark:  #1a2f4f;
    --abcona-blue-light: #3a5070;
    --bg-primary:        #1a1a1a;
    --bg-secondary:      #252525;
    --bg-tertiary:       #2e2e2e;
    --text-primary:      #e0e0e0;
    --text-muted:        #a0a0a0;
    --border-color:      #3a3a3a;
    --status-green:      #22c55e;
    --status-red:        #ef4444;
    --status-yellow:     #f59e0b;
    /* Funktions-Buttons */
    --fn-btn-bg:         #2a2a2a;
    --fn-btn-border:     #444444;
    --fn-btn-color:      #c0c0c0;
    /* Inputs */
    --input-bg:          #222222;
    --input-border:      #3a3a3a;
    /* Panels */
    --panel-header-bg:   #1e3a5f;
    --panel-header-text: #e0e0e0;
    /* Scrollbar */
    --scrollbar-thumb:   #444444;
}"""

assert old in c, "FEHLER: Dark-Mode-Block nicht gefunden"

new = """[data-theme="dark"] {
    /* Im Dark Mode: Blau → Dunkelgrau damit es zum Theme passt */
    --abcona-blue:       #2d2d2d;
    --abcona-blue-dark:  #1e1e1e;
    --abcona-blue-light: #3a3a3a;
    --bg-primary:        #1a1a1a;
    --bg-secondary:      #252525;
    --bg-tertiary:       #2e2e2e;
    --text-primary:      #e0e0e0;
    --text-muted:        #a0a0a0;
    --border-color:      #3a3a3a;
    --status-green:      #22c55e;
    --status-red:        #ef4444;
    --status-yellow:     #f59e0b;
    /* Funktions-Buttons */
    --fn-btn-bg:         #2a2a2a;
    --fn-btn-border:     #444444;
    --fn-btn-color:      #c0c0c0;
    /* Inputs */
    --input-bg:          #222222;
    --input-border:      #3a3a3a;
    /* Panels — dunkelgrau statt blau */
    --panel-header-bg:   #2d2d2d;
    --panel-header-text: #e0e0e0;
    /* Scrollbar */
    --scrollbar-thumb:   #444444;
}"""

c = c.replace(old, new, 1)
assert "--abcona-blue:       #2d2d2d;" in c, "FEHLER: Replace fehlgeschlagen"

with open("apps/abpe_crm/static/abpe_crm/softphone/css/softphone.css", "w") as f:
    f.write(c)
print("✓  Dark Mode Blau → Grau gepatcht")
PYEOF

# Zusätzlich: Panel-Header in den JS-Dateien nutzen noch hardcodiertes #163258
# Das können wir per CSS überschreiben:
python3 << 'PYEOF2'
with open("apps/abpe_crm/static/abpe_crm/softphone/css/softphone.css", "r") as f:
    c = f.read()

# Ans Ende anfügen: Override für alle hardcodierten blauen Panel-Header
addition = """
/* ── Dark Mode: Panel-Header Überschreibungen ────────── */
/* JS-Dateien nutzen noch hardcodiertes #163258 — CSS überschreibt */
[data-theme="dark"] #sp-speed-panel > div:first-child,
[data-theme="dark"] #sp-fop-panel > div:first-child,
[data-theme="dark"] #sp-recent-panel > div:first-child,
[data-theme="dark"] #sp-transfer-panel > div:first-child,
[data-theme="dark"] #sp-transfer-expand > div:first-child,
[data-theme="dark"] #sp-incoming > div:first-child {
    background: var(--panel-header-bg) !important;
    color: var(--panel-header-text) !important;
}

/* Widget-Header (immer oben) */
[data-theme="dark"] #sp-drag-handle {
    background: var(--abcona-blue) !important;
}

/* Tab-Nav aktiver Tab */
[data-theme="dark"] .sp-tab-active {
    background: var(--abcona-blue) !important;
}

/* FOP/Recent Section-Header (inline HTML aus JS) */
[data-theme="dark"] #sp-status-panel [style*="background:#163258"],
[data-theme="dark"] #sp-recent-body [style*="background:#163258"],
[data-theme="dark"] #sp-tr-exp-body [style*="background:#163258"],
[data-theme="dark"] #sp-speed-list [style*="background:#163258"] {
    background: var(--panel-header-bg) !important;
}
"""

c = c.rstrip() + "\n" + addition

with open("apps/abpe_crm/static/abpe_crm/softphone/css/softphone.css", "w") as f:
    f.write(c)
print("✓  Dark Mode Panel-Header Overrides eingefügt")
PYEOF2

ok "softphone.css aktualisiert ($(wc -l < "$CSS") Zeilen)"

python3 manage.py collectstatic --noinput 2>&1 | tail -2
supervisorctl restart abpe-django
sleep 2
supervisorctl status abpe-django
ok "Fertig — Hard-Reload (Ctrl+Shift+R)"


