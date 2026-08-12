#!/bin/bash
set -e
cd /opt/abpe/backend
JS="apps/abpe_crm/static/abpe_crm/js/mod-crm.js"
CSS="apps/abpe_crm/static/abpe_crm/css/mod-crm.css"
BTAB="apps/abpe_crm/templates/abpe_crm/tabs/berater_tab.html"
KTAB="apps/abpe_crm/templates/abpe_crm/tabs/kunden_tab.html"

echo "=== [1/6] Backups ==="
python3 Archiv/backup_restore.py -save "$JS"   -m "favoriten_02: stern+umschalter"
python3 Archiv/backup_restore.py -save "$CSS"  -m "favoriten_02: stern-css"
python3 Archiv/backup_restore.py -save "$BTAB" -m "favoriten_02: favoriten-button berater"
python3 Archiv/backup_restore.py -save "$KTAB" -m "favoriten_02: toggle-leiste kunden neu"

echo "=== [2/6] JS-Patches ==="
python3 /tmp/fav02/patch.py

echo "=== [3/6] HTML-Patches ==="
python3 /tmp/fav02/patch_html.py

echo "=== [4/6] CSS-Patch ==="
python3 /tmp/fav02/css_patch.py

echo "=== [5/6] Checks ==="
node --check "$JS" && echo "  mod-crm.js OK"
for f in "$BTAB" "$KTAB"; do
  o=$(grep -o '<div' "$f" | wc -l); c=$(grep -o '</div>' "$f" | wc -l)
  echo "  $f: <div>=$o </div>=$c"
done

echo "=== [6/6] collectstatic ==="
python manage.py collectstatic --noinput 2>&1 | tail -3

echo ""
echo "============================================================"
echo "✅ favoriten_02 (Frontend) fertig."
echo "Hard-Refresh: Stern in jeder Berater-/Kunden-Zeile, dritter"
echo "Button 'Favoriten' neben Liste/Zuletzt in BEIDEN Modulen."
echo "============================================================"
