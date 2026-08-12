#!/bin/bash
# ============================================================
# queryhilfe_06_finales_redesign.sh
# Query-Hilfe-Button wandert neben das Lupensymbol (Logo-Bereich),
# weg vom Ende der Suchleiste. Panel haengt jetzt an diesem Button
# (crm-qh-anchor), Karten-Design statt Tag-Wurst, flex-wrap:nowrap
# behebt den Scrollbalken-Bug endgueltig.
# ============================================================
set -e
cd /opt/abpe/backend
HTML="apps/abpe_crm/templates/abpe_crm/components/header.html"
CSS="apps/abpe_crm/static/abpe_crm/css/mod-crm.css"

echo "=== [1/5] Backups ==="
python3 Archiv/backup_restore.py -save "$HTML" -m "queryhilfe_06: finales redesign"
python3 Archiv/backup_restore.py -save "$CSS"  -m "queryhilfe_06: karten-design"

echo "=== [2/5] HTML-Patch ==="
python3 /tmp/qhilfe6/patch.py

echo "=== [3/5] CSS-Patch ==="
python3 /tmp/qhilfe6/css_patch.py

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
echo "✅ queryhilfe_06 fertig."
echo "Hard-Refresh: Query-Hilfe-Button jetzt neben der Lupe, Panel"
echo "klappt direkt darunter auf, Karten-Design, kein Scrollbalken."
echo "============================================================"
