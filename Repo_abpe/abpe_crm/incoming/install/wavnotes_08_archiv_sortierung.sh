#!/bin/bash
# ============================================================
# wavnotes_08_archiv_sortierung.sh
# WAV-Notizen — Etappe 8: Archiv explizit neueste-zuerst sortiert,
# Filter-Leiste Alle/Dokumentiert/Archiviert, Dauer in Archiv-Zeile.
# Reines Frontend (keine Backend-/Model-Aenderung noetig).
# ============================================================
set -e
cd /opt/abpe/backend
JS="apps/abpe_crm/static/abpe_crm/js/mod-crm-pbx.js"
CSS="apps/abpe_crm/static/abpe_crm/css/mod-crm-pbx.css"

echo "=== [1/4] Backups ==="
python3 Archiv/backup_restore.py -save "$JS"  -m "wavnotes_08: archiv sortierung+filter"
python3 Archiv/backup_restore.py -save "$CSS" -m "wavnotes_08: archiv filter css"

echo "=== [2/4] Patches ==="
python3 /tmp/wn08/patch.py
python3 /tmp/wn08/css_patch.py

echo "=== [3/4] node --check ==="
node --check "$JS" && echo "  Syntax OK"

echo "=== [4/4] collectstatic + restart ==="
python manage.py collectstatic --noinput 2>&1 | tail -3
supervisorctl restart abpe-django
python manage.py check 2>&1 | tail -3

echo ""
echo "============================================================"
echo "✅ wavnotes_08 fertig."
echo "Test: Archiv -> neueste oben, Filter-Pills Alle/Dokumentiert/Archiviert,"
echo "Dauer in jeder Zeile. Hard-Refresh (Strg+Shift+R) nicht vergessen."
echo "============================================================"
