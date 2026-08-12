#!/bin/bash
# ============================================================
# gsearch_00_analyse.sh
# Analyse-Script fuer die geplante globale Suche (Strg+K Modal).
# Liest alles, was fuer den Bau gebraucht wird: Basis-Template
# (fuer global geladene Scripte), Header-Komponente, CSS-Dateien,
# i18n-Struktur, mod-edms.js Klick-Router + init(), urls.py.
# ============================================================
set -e
cd /opt/abpe/backend

LINE="============================================================"

sec() { echo ""; echo "$LINE"; echo "$1"; echo "$LINE"; }

# ------------------------------------------------------------------
sec "1) Wo wird core-language.js eingebunden? (= auf ALLEN Seiten geladenes Basis-Template)"
grep -rln "core-language.js" apps/abpe_crm/templates/ 2>/dev/null

echo ""
echo "--- Vollstaendiger Inhalt der ersten Fundstelle (falls Basis-Template) ---"
FIRST_TPL=$(grep -rln "core-language.js" apps/abpe_crm/templates/ 2>/dev/null | head -1)
if [ -n "$FIRST_TPL" ]; then
    echo "Datei: $FIRST_TPL"
    cat "$FIRST_TPL"
fi

# ------------------------------------------------------------------
sec "2) Header-Komponente (der rot markierte Bereich neben dem Logo)"
find apps/abpe_crm/templates -iname "*header*"
echo ""
for f in $(find apps/abpe_crm/templates -iname "*header*" -not -name "*.disabled"); do
    echo "--- $f ---"
    cat "$f"
    echo ""
done

# ------------------------------------------------------------------
sec "3) Alle CSS-Dateien im abpe_crm-Modul (Kandidat fuer Modal-Styles)"
ls -la apps/abpe_crm/static/abpe_crm/css/
echo ""
echo "--- core-theme.css bereits bekannt. Gibt es eine 'core.css' oder 'global.css'? ---"
find apps/abpe_crm/static/abpe_crm/css -iname "core*" -o -iname "global*" -o -iname "header*" -o -iname "modal*"

# ------------------------------------------------------------------
sec "4) i18n - wo liegen die Sprachdateien wirklich? (frueherer Versuch hat nichts gefunden)"
find apps/abpe_crm/static -iname "*.json" | xargs grep -l "pbx_tab_wavnotes\|pbx_new\b" 2>/dev/null
echo ""
echo "--- Falls gefunden: Struktur der ersten 30 Zeilen ---"
FOUND_I18N=$(find apps/abpe_crm/static -iname "*.json" | xargs grep -l "pbx_tab_wavnotes\|pbx_new\b" 2>/dev/null | head -1)
if [ -n "$FOUND_I18N" ]; then
    echo "Datei: $FOUND_I18N"
    head -30 "$FOUND_I18N"
fi
echo ""
echo "--- core-language.js: wie wird geladen/gemappt? (t()-Aequivalent, Ladepfad) ---"
find apps/abpe_crm/static -iname "core-language.js"
CORELANG=$(find apps/abpe_crm/static -iname "core-language.js" | head -1)
if [ -n "$CORELANG" ]; then
    cat "$CORELANG"
fi

# ------------------------------------------------------------------
sec "5) mod-edms.js - init() komplett (fuer Deep-Link ?doc=/?mail= Einbau)"
grep -n "^\s*init(" apps/abpe_crm/static/abpe_crm/js/mod-edms.js
sed -n '/^\s*init(/,/^    },/p' apps/abpe_crm/static/abpe_crm/js/mod-edms.js | head -60

# ------------------------------------------------------------------
sec "6) mod-edms.js - loadAkte() komplett (Person/Firma-Zielfunktion)"
sed -n '/loadAkte(/,/^    },/p' apps/abpe_crm/static/abpe_crm/js/mod-edms.js | head -60

# ------------------------------------------------------------------
sec "7) urls.py - DMS-Seiten-Route (nicht API) + search_all Route, exakte Zeilen"
grep -n "path('dms/'\|path(\"dms/\"\|search_all\|path('crm/dms" apps/abpe_crm/urls.py apps/abpe_ui/*.py 2>/dev/null
grep -rn "urls.py" -e "'dms/'" apps/ 2>/dev/null | grep "path("

# ------------------------------------------------------------------
sec "8) Existiert schon ein globaler Keydown/Escape/Shortcut-Handler? (Stil-Vorlage, Kollisions-Check)"
grep -rln "keydown\|addEventListener('keyup'\|ctrlKey\|metaKey" apps/abpe_crm/static/abpe_crm/js/*.js apps/abpe_crm/templates/ 2>/dev/null

echo ""
echo "$LINE"
echo "FERTIG - komplette Ausgabe zurueckschicken, dann kommt der echte Bau-Patch"
echo "$LINE"
