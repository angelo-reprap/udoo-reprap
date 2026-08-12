#!/bin/bash
set -e
cd /opt/abpe/backend
FILE="apps/abpe_edms/views.py"

echo "=== [1/3] Backup ==="
python3 Archiv/backup_restore.py -save "$FILE" -m "schnellsuche: boolean-erkennung in _build_query"

echo "=== [2/3] Patch ==="
python3 /tmp/schnellsuche/patch.py

echo "=== [3/3] Syntax-Check + Restart ==="
python3 -c "import ast; ast.parse(open('$FILE').read()); print('  views.py OK')"
supervisorctl restart abpe-django
sleep 2
python manage.py check 2>&1 | tail -3

echo ""
echo "============================================================"
echo "✅ fertig. Test in der SCHNELLSUCHE (Strg+K):"
echo "  haskell AND Andreas"
echo "Normales Tippen ohne Operatoren bleibt Autocomplete wie bisher."
echo "============================================================"
