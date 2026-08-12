#!/bin/bash
set -e
cd /opt/abpe/backend
MODELS="apps/abpe_crm/models.py"
VIEWS="apps/abpe_crm/views.py"
URLS="apps/abpe_crm/urls.py"

echo "=== [1/6] Backups ==="
python3 Archiv/backup_restore.py -save "$MODELS" -m "favoriten_01: modell-felder"
python3 Archiv/backup_restore.py -save "$VIEWS"  -m "favoriten_01: views+row-extraktion"
python3 Archiv/backup_restore.py -save "$URLS"   -m "favoriten_01: routen"

echo "=== [2/6] Patches ==="
python3 /tmp/fav01/patch.py

echo "=== [3/6] Syntax-Checks ==="
python3 -c "import ast; ast.parse(open('$MODELS').read()); print('  models.py OK')"
python3 -c "import ast; ast.parse(open('$VIEWS').read()); print('  views.py OK')"
python3 -c "import ast; ast.parse(open('$URLS').read()); print('  urls.py OK')"

echo "=== [4/6] Migration generieren (NUR makemigrations) ==="
python manage.py makemigrations abpe_crm 2>&1 | tail -8

echo "=== [5/6] Migration anwenden ==="
python manage.py migrate abpe_crm

echo "=== [6/6] Restart + Check ==="
supervisorctl restart abpe-django
sleep 2
python manage.py check 2>&1 | tail -3

echo ""
echo "============================================================"
echo "✅ favoriten_01 (Backend) fertig."
echo "Danach: favoriten_02_frontend.sh"
echo "============================================================"
