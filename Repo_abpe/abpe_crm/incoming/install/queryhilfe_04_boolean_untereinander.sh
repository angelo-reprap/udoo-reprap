#!/bin/bash
# ============================================================
# queryhilfe_04_boolean_untereinander.sh
# .qh-section wird Standard-Spalte (fuer die Berater-Felder/
# Beispiele-Abschnitte, die bisher per Inline-Style umgestellt
# waren). Boolean/Wildcards (bleiben inline pro Zeile, wie
# gewuenscht) bekommen eigene Klasse .qh-section-inline, damit
# beide Layouts sauber getrennt sind statt Inline-Style-Hacks.
# ============================================================
set -e
cd /opt/abpe/backend
CSS="apps/abpe_crm/static/abpe_crm/css/mod-crm.css"
HTML="apps/abpe_crm/templates/abpe_crm/components/header.html"

echo "=== [1/4] Backups ==="
python3 Archiv/backup_restore.py -save "$CSS"  -m "queryhilfe_04: boolean/wildcards untereinander"
python3 Archiv/backup_restore.py -save "$HTML" -m "queryhilfe_04: qh-section-inline"

echo "=== [2/4] Patches ==="
python3 /tmp/qhilfe3/patch.py

echo "=== [3/4] Div-Balance ==="
python3 - << 'PYEOF'
s = open('apps/abpe_crm/templates/abpe_crm/components/header.html', encoding='utf-8').read()
o, c = s.count('<div'), s.count('</div>')
print(f'  <div> = {o}   </div> = {c}   Differenz = {o - c}')
assert o == c, 'Div-Balance kaputt!'
PYEOF

echo "=== [4/4] collectstatic ==="
python manage.py collectstatic --noinput 2>&1 | tail -3

echo ""
echo "============================================================"
echo "✅ queryhilfe_04 fertig."
echo "Hard-Refresh + Query-Hilfe pruefen: Boolean/Wildcards jetzt auch"
echo "jeweils eigene Zeile (Label + Tags einer Kategorie bleiben inline"
echo "nebeneinander, aber jede Kategorie steht untereinander)."
echo "============================================================"
