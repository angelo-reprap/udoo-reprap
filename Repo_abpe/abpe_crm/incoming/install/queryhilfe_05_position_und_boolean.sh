#!/bin/bash
# ============================================================
# queryhilfe_05_position_und_boolean.sh
# Query-Hilfe-Panel physisch in den search-container verschoben
# (position:absolute relativ zum Suchfeld statt fixed/vollbreite
# unter dem ganzen Header). Boolean/Wildcards jetzt im gleichen
# Zeile-plus-Beispiel-Format wie Felder/Beispiele.
# ============================================================
set -e
cd /opt/abpe/backend
HTML="apps/abpe_crm/templates/abpe_crm/components/header.html"
CSS="apps/abpe_crm/static/abpe_crm/css/mod-crm.css"

echo "=== [1/5] Backups ==="
python3 Archiv/backup_restore.py -save "$HTML" -m "queryhilfe_05: panel verschoben + boolean vertikal"
python3 Archiv/backup_restore.py -save "$CSS"  -m "queryhilfe_05: absolute positionierung"

echo "=== [2/5] HTML-Patch ==="
python3 /tmp/qhilfe5/patch.py

echo "=== [3/5] CSS-Patch ==="
python3 /tmp/qhilfe5/css_patch.py

echo "=== [4/5] Div-Balance ==="
python3 - << 'PYEOF'
s = open('apps/abpe_crm/templates/abpe_crm/components/header.html', encoding='utf-8').read()
o, c = s.count('<div'), s.count('</div>')
print(f'  <div> = {o}   </div> = {c}   Differenz = {o - c}')
assert o == c, 'Div-Balance kaputt!'
PYEOF

echo "=== [5/5] collectstatic ==="
python manage.py collectstatic --noinput 2>&1 | tail -3

echo ""
echo "============================================================"
echo "✅ queryhilfe_05 fertig."
echo "Hard-Refresh + Query-Hilfe pruefen: Panel jetzt direkt unter dem"
echo "Suchfeld, Boolean/Wildcards/Felder/Beispiele alle im gleichen"
echo "Zeile-mit-Beispiel-Format."
echo "============================================================"
