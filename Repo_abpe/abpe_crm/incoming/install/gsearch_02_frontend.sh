#!/bin/bash
# ============================================================
# gsearch_02_frontend.sh
# Globale Suche — Etappe 2: Header-Icon, Strg+K-Modal
# (core-gsearch.js/css, neu + global via base.html geladen),
# i18n-Keys in core-common.json.
# ============================================================
set -e
cd /opt/abpe/backend

HEADER="apps/abpe_crm/templates/abpe_crm/components/header.html"
BASE="apps/abpe_crm/templates/abpe_crm/base.html"
I18N="apps/abpe_crm/static/abpe_crm/i18n/de/core-common.json"

echo "=== [1/6] Backups ==="
python3 Archiv/backup_restore.py -save "$HEADER" -m "gsearch_02: trigger-button"
python3 Archiv/backup_restore.py -save "$BASE"   -m "gsearch_02: css/js include"
python3 Archiv/backup_restore.py -save "$I18N"   -m "gsearch_02: i18n keys"

echo "=== [2/6] Neue Dateien anlegen ==="
cp /tmp/gsearch/core-gsearch.js  apps/abpe_crm/static/abpe_crm/js/core-gsearch.js
cp /tmp/gsearch/core-gsearch.css apps/abpe_crm/static/abpe_crm/css/core-gsearch.css

echo "=== [3/6] header.html + base.html patchen ==="
python3 /tmp/gsearch/patch_02.py

echo "=== [4/6] i18n-Keys ergaenzen ==="
python3 /tmp/gsearch/i18n_patch.py

echo "=== [5/6] Syntax-Checks ==="
node --check apps/abpe_crm/static/abpe_crm/js/core-gsearch.js && echo "  core-gsearch.js OK"
python3 -c "import json; json.load(open('$I18N', encoding='utf-8')); print('  core-common.json OK')"

echo "=== [6/6] Div-Balance header.html pruefen ==="
python3 - << 'PYEOF'
s = open('apps/abpe_crm/templates/abpe_crm/components/header.html', encoding='utf-8').read()
o, c = s.count('<div'), s.count('</div>')
print(f'  <div> = {o}   </div> = {c}   Differenz = {o - c}')
assert o == c, 'Div-Balance kaputt!'
PYEOF

python manage.py collectstatic --noinput 2>&1 | tail -3
supervisorctl restart abpe-django
python manage.py check 2>&1 | tail -3

echo ""
echo "============================================================"
echo "✅ gsearch_02 fertig — Globale Suche ist live."
echo "Test: Strg+K auf JEDER Seite ODER Lupe-Icon neben dem Logo."
echo "Hard-Refresh (Strg+Shift+R) nicht vergessen."
echo "============================================================"
