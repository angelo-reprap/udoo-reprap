#!/bin/bash
# ============================================================
# wavnotes_07_archivieren.sh
# WAV-Notizen — Etappe 7: manuelles Archivieren nicht-relevanter
# Voicemails (CrmWavnoteStatus), Offen/Archiv-Trennung im Frontend.
# ============================================================
set -e
cd /opt/abpe/backend

MODELS="apps/abpe_crm/models.py"
VIEWS="apps/abpe_crm/views_ami.py"
URLS="apps/abpe_crm/urls.py"
TPL="apps/abpe_crm/templates/abpe_crm/tabs/telefon_tab.html"
JS="apps/abpe_crm/static/abpe_crm/js/mod-crm-pbx.js"
CSS="apps/abpe_crm/static/abpe_crm/css/mod-crm-pbx.css"

echo "=== [1/6] Backups ==="
python3 Archiv/backup_restore.py -save "$MODELS" -m "wavnotes_07: CrmWavnoteStatus"
python3 Archiv/backup_restore.py -save "$VIEWS"  -m "wavnotes_07: archive-view"
python3 Archiv/backup_restore.py -save "$URLS"   -m "wavnotes_07: archive-route"
python3 Archiv/backup_restore.py -save "$TPL"    -m "wavnotes_07: archiv-toggle"
python3 Archiv/backup_restore.py -save "$JS"     -m "wavnotes_07: frontend"
python3 Archiv/backup_restore.py -save "$CSS"    -m "wavnotes_07: css"

echo "=== [2/6] Patches ==="
python3 /tmp/wn07/patch.py

echo "=== [3/6] Syntax-Checks ==="
python3 -c "import ast; ast.parse(open('$MODELS').read()); print('  models.py OK')"
python3 -c "import ast; ast.parse(open('$VIEWS').read()); print('  views_ami.py OK')"
python3 -c "import ast; ast.parse(open('$URLS').read()); print('  urls.py OK')"
node --check "$JS" && echo "  mod-crm-pbx.js OK"

echo "=== [4/6] Div-Balance Template pruefen ==="
python3 - << 'PYEOF'
s = open('apps/abpe_crm/templates/abpe_crm/tabs/telefon_tab.html', encoding='utf-8').read()
o, c = s.count('<div'), s.count('</div>')
print(f'  <div> = {o}   </div> = {c}   Differenz = {o - c}')
assert o == c, 'Div-Balance kaputt!'
PYEOF

echo "=== [5/6] Migration generieren (NUR makemigrations, KEIN migrate!) ==="
python manage.py makemigrations abpe_crm 2>&1 | tail -8

echo "=== [6/6] collectstatic + restart ==="
python manage.py collectstatic --noinput 2>&1 | tail -3
supervisorctl restart abpe-django
python manage.py check 2>&1 | tail -3

echo ""
echo "============================================================"
echo "✅ wavnotes_07 fertig."
echo "NAECHSTER SCHRITT (manuell): python manage.py migrate abpe_crm"
echo "Danach testen: Offen/Archiv-Trennung + Archivieren-Button"
echo "============================================================"
