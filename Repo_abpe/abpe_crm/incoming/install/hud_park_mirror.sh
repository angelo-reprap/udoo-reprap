#!/bin/bash
set -e
cd /opt/abpe/backend
TPL="apps/abpe_crm/templates/abpe_crm/tabs/telefon_tab.html"
JS="apps/abpe_crm/static/abpe_crm/js/mod-crm-pbx.js"

echo "=== [1/5] Backups ==="
python3 Archiv/backup_restore.py -save "$TPL" -m "hud_park_mirror: neue sektion"
python3 Archiv/backup_restore.py -save "$JS"  -m "hud_park_mirror: renderPark erweitert"

echo "=== [2/5] Patches ==="
python3 /tmp/hudpark/patch.py

echo "=== [3/5] Div-Balance ==="
python3 - << 'PYEOF'
s = open('apps/abpe_crm/templates/abpe_crm/tabs/telefon_tab.html', encoding='utf-8').read()
o, c = s.count('<div'), s.count('</div>')
print(f'  <div> = {o}   </div> = {c}   Differenz = {o - c}')
assert o == c, 'Div-Balance kaputt!'
PYEOF

echo "=== [4/5] node --check ==="
node --check "$JS" && echo "  mod-crm-pbx.js OK"

echo "=== [5/5] collectstatic + restart ==="
python manage.py collectstatic --noinput 2>&1 | tail -3
supervisorctl restart abpe-django
python manage.py check 2>&1 | tail -3

echo ""
echo "============================================================"
echo "✅ hud_park_mirror fertig."
echo "Test: Gespraech parken, dann auf HUD-Tab wechseln - Sektion"
echo "'Gehaltene Anrufe' sollte erscheinen (nur wenn wirklich was"
echo "belegt ist, sonst unsichtbar). Abholen/Uebergeben direkt von"
echo "dort aus testen."
echo "============================================================"
