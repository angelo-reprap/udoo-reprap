#!/usr/bin/env bash
# fix_sp_standalone.sh — SP_STANDALONE direkt ins HTML Template
set -euo pipefail
GREEN='\033[0;32m'; NC='\033[0m'
ok() { echo -e "${GREEN}✓${NC} $*"; }

BASE="/opt/abpe/backend"
TMPL="apps/abpe_crm/templates/abpe_crm/softphone/softphone.html"
[[ "$(pwd)" == "$BASE" ]] || { echo "Falsches Verzeichnis"; exit 1; }

python3 Archiv/backup_restore.py -save "$TMPL" -m "vor SP_STANDALONE fix" || exit 1

python3 << 'PYEOF'
with open("apps/abpe_crm/templates/abpe_crm/softphone/softphone.html", "r") as f:
    c = f.read()

old = "    window.SP_LANG = '{{ request.LANGUAGE_CODE|default:\"de\" }}';"

assert old in c, "FEHLER: SP_LANG Zeile nicht gefunden"

new = """    window.SP_LANG = '{{ request.LANGUAGE_CODE|default:"de" }}';
    window.SP_STANDALONE = true;  // Softphone läuft als eigenständige Seite"""

c = c.replace(old, new, 1)
assert "window.SP_STANDALONE = true" in c

with open("apps/abpe_crm/templates/abpe_crm/softphone/softphone.html", "w") as f:
    f.write(c)
print("✓  SP_STANDALONE = true ins HTML Template eingefügt")
PYEOF

python3 manage.py collectstatic --noinput 2>&1 | tail -2
supervisorctl restart abpe-django
sleep 2
supervisorctl status abpe-django
ok "Fertig — Hard-Reload im Browser (Ctrl+Shift+R)"

