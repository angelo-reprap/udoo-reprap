#!/bin/bash
# ============================================================
# queryhilfe_02_text_berater.sh
# Korrigiert die Query-Hilfe-Felder/Beispiele fuer den Berater-Tab
# auf die echten, nach dem Reindex verfuegbaren ES-Feldnamen.
# WICHTIG: nur der Hilfetext - die Beispiele funktionieren erst,
# sobald Phase 1 (query_string-Umbau von api_berater_list) fertig ist.
# ============================================================
set -e
cd /opt/abpe/backend
FILE="apps/abpe_crm/templates/abpe_crm/components/header.html"

echo "=== [1/4] Backup ==="
python3 Archiv/backup_restore.py -save "$FILE" -m "queryhilfe_02: berater feldnamen korrigiert"

echo "=== [2/4] Patch ==="
python3 /tmp/qhilfe/patch.py

echo "=== [3/4] Div-Balance pruefen ==="
python3 - << 'PYEOF'
s = open('apps/abpe_crm/templates/abpe_crm/components/header.html', encoding='utf-8').read()
o, c = s.count('<div'), s.count('</div>')
print(f'  <div> = {o}   </div> = {c}   Differenz = {o - c}')
assert o == c, 'Div-Balance kaputt!'
PYEOF

echo "=== [4/4] collectstatic (Template braucht keinen Django-Restart, aber sauberkeitshalber) ==="
python manage.py collectstatic --noinput 2>&1 | tail -3

echo ""
echo "============================================================"
echo "✅ queryhilfe_02 fertig."
echo "Hard-Refresh + 'Query-Hilfe' auf dem Berater-Tab oeffnen zum Pruefen."
echo "Hinweis: Beispiele wirken erst nach Phase 1 (query_string-Umbau)."
echo "============================================================"
