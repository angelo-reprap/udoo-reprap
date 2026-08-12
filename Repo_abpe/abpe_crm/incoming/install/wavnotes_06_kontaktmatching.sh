#!/bin/bash
# ============================================================
# wavnotes_06_kontaktmatching.sh
# WAV-Notizen — Etappe 6: Neuer-Kontakt-Modal (Wiederverwendung
# _mmNewContactHtml, optionaler wavnoteMode-Parameter) +
# Kontakt-Suche auf Elasticsearch (api_search_all?scope=personen)
# umgestellt statt langsamem contacts-Dump.
# ============================================================
set -e
cd /opt/abpe/backend
JS="apps/abpe_crm/static/abpe_crm/js/mod-crm-pbx.js"
CSS="apps/abpe_crm/static/abpe_crm/css/mod-crm-pbx.css"

echo "=== [1/5] Backups ==="
python3 Archiv/backup_restore.py -save "$JS" -m "wavnotes_06: kontaktmatching"
python3 Archiv/backup_restore.py -save "$CSS" -m "wavnotes_06: kontaktmatching css"

echo "=== [2/5] JS-Patches (idempotent) ==="
python3 /tmp/wn06/patch.py

echo "=== [3/5] CSS-Patch (idempotent) ==="
python3 /tmp/wn06/css_patch.py

echo "=== [4/5] node --check ==="
node --check "$JS" && echo "  Syntax OK"

echo "=== [5/5] collectstatic + restart ==="
python manage.py collectstatic --noinput 2>&1 | tail -3
supervisorctl restart abpe-django
python manage.py check 2>&1 | tail -3

echo ""
echo "============================================================"
echo "✅ wavnotes_06 fertig."
echo "Test: WAV-Notizen -> Notiz erstellen -> Kontakt-Suche (jetzt ES,"
echo "sollte bei 'angelo mala' Treffer bringen) + Neuer Kontakt (Telefon"
echo "vorausgefuellt, Speichern ordnet Kontakt der Notiz zu)."
echo "============================================================"
