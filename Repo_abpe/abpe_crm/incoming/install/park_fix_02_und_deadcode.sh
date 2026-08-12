#!/bin/bash
set -e
cd /opt/abpe/backend
AMICTL="apps/abpe_crm/services/ami_control.py"
VIEWSAMI="apps/abpe_crm/views_ami.py"
VIEWS="apps/abpe_crm/views.py"

echo "=== [1/6] Backups ==="
python3 Archiv/backup_restore.py -save "$AMICTL"  -m "park_fix_02: echte park-action + bridge-partner"
python3 Archiv/backup_restore.py -save "$VIEWSAMI" -m "park_fix_02: view auf park_partner umgestellt"
python3 Archiv/backup_restore.py -save "$VIEWS"    -m "park_fix_02: tote park-duplikat-funktion entfernt"

echo "=== [2/6] Patch: echte Park-Action + Bridge-Partner-Ermittlung (ami_control.py) ==="
python3 /tmp/parkfix/patch_ami_control.py

echo "=== [3/6] Patch: views_ami.api_telefon_park auf park_partner umstellen ==="
python3 /tmp/parkfix/patch_views.py

echo "=== [4/6] Patch: tote Duplikat-Funktion in views.py entfernen (mit Sicherheits-Check) ==="
python3 /tmp/parkfix/patch_dead_code.py

echo "=== [5/6] Syntax-Checks ==="
python3 -c "import ast; ast.parse(open('$AMICTL').read()); print('  ami_control.py OK')"
python3 -c "import ast; ast.parse(open('$VIEWSAMI').read()); print('  views_ami.py OK')"
python3 -c "import ast; ast.parse(open('$VIEWS').read()); print('  views.py OK')"

echo "=== [6/6] Restart + Check ==="
supervisorctl restart abpe-django
sleep 2
python manage.py check 2>&1 | tail -3

echo ""
echo "============================================================"
echo "✅ park_fix_02 fertig (Fix + tote Duplikat-Funktion entfernt)."
echo ""
echo "Hinweis: get_and_park() in services/ami_client.py wird nach"
echo "diesem Patch von KEINER Stelle mehr aufgerufen (verwaist)."
echo "Bewusst NICHT geloescht in diesem Schritt - sag Bescheid falls"
echo "du die Funktion selbst auch noch entfernt haben willst."
echo ""
echo "Test: aktives 12<->124 Gespraech, auf Parken klicken, dabei"
echo "asterisk -rvvv live mitschneiden, komplettes Log schicken."
echo "============================================================"
