#!/bin/bash
# ============================================================
# gsearch_03_size_fix.sh
# Globale Suche — Etappe 3: size=30 war bei JEDEM Filter hart
# verdrahtet, auch bei Einzel-Scope (max. 100 waere erlaubt).
# Jetzt: 'Alles'=30, Einzel-Scope=100. Zusaetzlich Hinweistext
# wenn selbst 100 nicht alle Treffer zeigt (z.B. 135 Treffer).
# ============================================================
set -e
cd /opt/abpe/backend
JS="apps/abpe_crm/static/abpe_crm/js/core-gsearch.js"
CSS="apps/abpe_crm/static/abpe_crm/css/core-gsearch.css"

echo "=== [1/4] Backups ==="
python3 Archiv/backup_restore.py -save "$JS"  -m "gsearch_03: size fix + hint"
python3 Archiv/backup_restore.py -save "$CSS" -m "gsearch_03: hint css"

echo "=== [2/4] Patches ==="
python3 /tmp/gsearch2/patch.py

echo "=== [3/4] node --check ==="
node --check "$JS" && echo "  Syntax OK"

echo "=== [4/4] collectstatic + restart ==="
python manage.py collectstatic --noinput 2>&1 | tail -3
supervisorctl restart abpe-django
python manage.py check 2>&1 | tail -3

echo ""
echo "============================================================"
echo "✅ gsearch_03 fertig."
echo "Test: 'haskell' suchen, auf 'Personen'-Filter klicken (jetzt bis"
echo "zu 100 statt 30), Andreas Wollschlaeger sollte jetzt sichtbar sein."
echo "============================================================"
