#!/bin/bash
# ============================================================
# atxfer_complete.sh
# Nach erfolgreicher Ruecksprache (Atxfer gestartet) zeigt die Box
# jetzt "Uebergeben"/"Zurueck" statt sich zu schliessen.
# Uebergeben = normaler Hangup des eigenen Kanals - Asterisks
# native Atxfer-Logik fuehrt daraufhin automatisch Anrufer + Ziel
# zusammen (kein Extra-AMI-Kommando noetig, exakt wie im
# verifizierten Electron-Softphone: SESSION.terminate()).
# Zurueck = bereits vorhandenes cancel_atxfer, unveraendert.
# ============================================================
set -e
cd /opt/abpe/backend
JS="apps/abpe_crm/static/abpe_crm/js/mod-crm-pbx.js"

echo "=== [1/4] Backup ==="
python3 Archiv/backup_restore.py -save "$JS" -m "atxfer_complete: uebergeben/zurueck nach ruecksprache"

echo "=== [2/4] Patch ==="
python3 /tmp/atxfer_complete/patch.py

echo "=== [3/4] node --check ==="
node --check "$JS" && echo "  Syntax OK"

echo "=== [4/4] collectstatic + restart ==="
python manage.py collectstatic --noinput 2>&1 | tail -3
supervisorctl restart abpe-django
python manage.py check 2>&1 | tail -3

echo ""
echo "============================================================"
echo "✅ atxfer_complete fertig."
echo "Test: Rueckspreche starten (Ziel eingeben, 'Ruecksprache' klicken),"
echo "warten bis Ziel abnimmt, dann 'Uebergeben' klicken - Anrufer und"
echo "Ziel sollten automatisch zusammengefuehrt werden, dein eigener"
echo "Kanal legt auf. Alternativ 'Zurueck' testen (sollte wieder zum"
echo "Anrufer zurueckspringen, wie bisher schon)."
echo "============================================================"
