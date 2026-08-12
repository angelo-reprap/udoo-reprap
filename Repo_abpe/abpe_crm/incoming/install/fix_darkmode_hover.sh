#!/usr/bin/env bash
# fix_darkmode_hover.sh — Hover-States im Dark Mode von Blau auf Grau
set -euo pipefail
GREEN='\033[0;32m'; NC='\033[0m'
ok() { echo -e "${GREEN}✓${NC} $*"; }

BASE="/opt/abpe/backend"
CSS="apps/abpe_crm/static/abpe_crm/softphone/css/softphone.css"
[[ "$(pwd)" == "$BASE" ]] || { echo "Falsches Verzeichnis"; exit 1; }

python3 Archiv/backup_restore.py -save "$CSS" -m "vor hover dark mode fix" || exit 1

python3 << 'PYEOF'
with open("apps/abpe_crm/static/abpe_crm/softphone/css/softphone.css", "r") as f:
    c = f.read()

# 1. sp-key hover: im Light Mode bg-tertiary, im Dark Mode eigene Variable
old = """.sp-key:hover  { background: var(--bg-tertiary); }
.sp-key:active { background: var(--abcona-blue); color: #fff; }"""

assert old in c, "FEHLER: sp-key hover Block nicht gefunden"

new = """.sp-key:hover  { background: var(--hover-bg); }
.sp-key:active { background: var(--active-bg); color: var(--active-color); }"""

c = c.replace(old, new, 1)

# 2. Hover-Variablen in :root und [data-theme="dark"] ergänzen
old_root = "    /* Scrollbar */\n    --scrollbar-thumb:   #dee2e6;\n}"
assert old_root in c, "FEHLER: :root Scrollbar-Zeile nicht gefunden"

new_root = """    /* Scrollbar */
    --scrollbar-thumb:   #dee2e6;
    /* Hover / Active States */
    --hover-bg:          #e9ecef;
    --active-bg:         #163258;
    --active-color:      #ffffff;
}"""
c = c.replace(old_root, new_root, 1)

old_dark = """    /* Scrollbar */
    --scrollbar-thumb:   #444444;
}"""
assert old_dark in c, "FEHLER: Dark-Mode Scrollbar-Zeile nicht gefunden"

new_dark = """    /* Scrollbar */
    --scrollbar-thumb:   #444444;
    /* Hover / Active States — kein Blau im Dark Mode */
    --hover-bg:          #3a3a3a;
    --active-bg:         #444444;
    --active-color:      #e0e0e0;
}"""
c = c.replace(old_dark, new_dark, 1)

# 3. Am Ende: Dark Mode Hover-Overrides für alle Buttons
addition = """
/* ── Dark Mode: Hover-Overrides (kein Blau) ─────────── */
[data-theme="dark"] button:hover:not(#sp-call-btn):not(#sp-hangup-btn):not([style*="background:#163258"]):not([style*="background:#22c55e"]):not([style*="background:#ef4444"]) {
    background: var(--hover-bg) !important;
    color: var(--text-primary) !important;
}

[data-theme="dark"] .sp-tab-btn:not(.sp-tab-active):hover {
    background: var(--hover-bg) !important;
    color: var(--text-primary) !important;
}

[data-theme="dark"] #sp-fn-bar button:hover {
    background: var(--hover-bg) !important;
    border-color: var(--border-color) !important;
    color: var(--text-primary) !important;
}

[data-theme="dark"] #sp-speed-toggle:hover,
[data-theme="dark"] #sp-recent-toggle:hover,
[data-theme="dark"] #sp-fop-toggle:hover {
    background: var(--hover-bg) !important;
    color: var(--text-primary) !important;
}
"""
c = c.rstrip() + "\n" + addition

with open("apps/abpe_crm/static/abpe_crm/softphone/css/softphone.css", "w") as f:
    f.write(c)
print("✓  Hover Dark Mode gepatcht")
PYEOF

ok "softphone.css aktualisiert ($(wc -l < "$CSS") Zeilen)"
python3 manage.py collectstatic --noinput 2>&1 | tail -2
supervisorctl restart abpe-django
sleep 2
supervisorctl status abpe-django
ok "Fertig — Hard-Reload (Ctrl+Shift+R)"

