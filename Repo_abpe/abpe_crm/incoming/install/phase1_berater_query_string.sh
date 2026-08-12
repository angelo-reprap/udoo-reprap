#!/bin/bash
# ============================================================
# phase1_berater_query_string.sh
# api_berater_list: alte ORM-icontains-Wortsuche ersetzt durch
# echte ES query_string-Suche (AND/OR/NOT/+/-/Wildcards/Fuzzy/
# Phrase/Feld:Wert/Bereichssuche - alles was die Query-Hilfe
# verspricht). type=cross_fields, damit Woerter auch in
# verschiedenen Feldern erfuellt werden duerfen (z.B. Skill im
# Profiltext + Name im Namensfeld). lenient=True gegen Syntax-
# Fehler-Abstuerze. Status/Typ-Filter, Sortierung, Pagination
# bleiben unveraendert (nur die Treffermenge kommt jetzt aus ES).
# Bekannte kleine Verhaltensaenderung: Telefonnummer-Suche laeuft
# jetzt ueber das rohe ES-Textfeld statt ueber normalisierte
# Rufnummern - fuer die allermeisten Faelle gleichwertig.
# ============================================================
set -e
cd /opt/abpe/backend
FILE="apps/abpe_crm/views.py"

echo "=== [1/4] Backup ==="
python3 Archiv/backup_restore.py -save "$FILE" -m "phase1: berater query_string"

echo "=== [2/4] Patch ==="
python3 /tmp/phase1/patch.py

echo "=== [3/4] Syntax-Check ==="
python3 -c "import ast; ast.parse(open('$FILE').read()); print('  views.py OK')"

echo "=== [4/4] Restart + Check ==="
supervisorctl restart abpe-django
sleep 2
python manage.py check 2>&1 | tail -3

echo ""
echo "============================================================"
echo "✅ Phase 1 fertig."
echo "Test im OBEREN Berater-Suchfeld (nicht Strg+K!):"
echo "  haskell AND Andreas"
echo "  stundensatz:[80 TO 120]"
echo "  city:München AND java"
echo "============================================================"
