#!/bin/bash
# ============================================================
# queryhilfe_03_layout_klartext.sh
# Query-Hilfe: Abschnitte (Boolean/Wildcards/Felder/Beispiele)
# jeweils eigene Zeile statt alles nebeneinander (flex-direction:
# column). Berater-Felder+Beispiele mit Klartext-Erklaerung pro
# Zeile statt nackter Tags, fuer Sachbearbeiter verstaendlich.
# ============================================================
set -e
cd /opt/abpe/backend
CSS="apps/abpe_crm/static/abpe_crm/css/mod-crm.css"
HTML="apps/abpe_crm/templates/abpe_crm/components/header.html"
I18N="apps/abpe_crm/static/abpe_crm/i18n/de/core-common.json"

echo "=== [1/5] Backups ==="
python3 Archiv/backup_restore.py -save "$CSS"  -m "queryhilfe_03: layout spalten"
python3 Archiv/backup_restore.py -save "$HTML" -m "queryhilfe_03: klartext berater"
python3 Archiv/backup_restore.py -save "$I18N" -m "queryhilfe_03: klartext i18n"

echo "=== [2/5] Patches ==="
python3 /tmp/qhilfe2/patch.py
python3 /tmp/qhilfe2/i18n_patch.py

echo "=== [3/5] Div-Balance ==="
python3 - << 'PYEOF'
s = open('apps/abpe_crm/templates/abpe_crm/components/header.html', encoding='utf-8').read()
o, c = s.count('<div'), s.count('</div>')
print(f'  <div> = {o}   </div> = {c}   Differenz = {o - c}')
assert o == c, 'Div-Balance kaputt!'
PYEOF

echo "=== [4/5] JSON-Check ==="
python3 -c "import json; json.load(open('$I18N', encoding='utf-8')); print('  core-common.json OK')"

echo "=== [5/5] collectstatic ==="
python manage.py collectstatic --noinput 2>&1 | tail -3

echo ""
echo "============================================================"
echo "✅ queryhilfe_03 fertig."
echo "Hard-Refresh + Query-Hilfe auf Berater-Tab oeffnen zum Pruefen."
echo "============================================================"
