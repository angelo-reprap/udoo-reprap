#!/bin/bash
set -e
cd /opt/abpe/backend
HTML="apps/abpe_crm/templates/abpe_crm/components/header.html"
CSS="apps/abpe_crm/static/abpe_crm/css/mod-crm.css"

echo "=== [1/5] Backups ==="
python3 Archiv/backup_restore.py -save "$HTML" -m "queryhilfe_07: final button+panel verschoben"
python3 Archiv/backup_restore.py -save "$CSS"  -m "queryhilfe_07: karten-css final"

echo "=== [2/5] HTML-Patches (schrittweise, sofort gespeichert) ==="
python3 /tmp/qhilfe7/patch.py

echo "=== [3/5] CSS-Patch ==="
python3 /tmp/qhilfe7/css_patch.py

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
echo "✅ queryhilfe_07 fertig."
echo "Hard-Refresh: Query-Hilfe neben der Lupe, Karten-Design, kein"
echo "Scrollbalken. Falls das Panel gar nicht mehr aufklappt (statt nur"
echo "falsch positioniert): dann steckt's im JS (toggleCrmQueryHelp),"
echo "das noch auf die alte Struktur reagieren koennte - dann Bescheid geben."
echo "============================================================"
