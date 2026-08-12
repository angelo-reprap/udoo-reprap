#!/bin/bash
set -e
cd /opt/abpe/backend
LINE="============================================================"
sec() { echo ""; echo "$LINE"; echo "$1"; echo "$LINE"; }

# ------------------------------------------------------------------
sec "1) Was macht der bestehende 'Zuletzt 20' Umschalter aktuell? (JS)"
grep -n "Zuletzt\|zuletzt" apps/abpe_crm/static/abpe_crm/js/mod-crm-berater.js apps/abpe_crm/templates/abpe_crm/tabs/berater_tab.html 2>/dev/null

# ------------------------------------------------------------------
sec "2) api_berater_detail komplett"
sed -n '/def api_berater_detail/,/^def /p' apps/abpe_crm/views.py | head -60

# ------------------------------------------------------------------
sec "3) api_kunden_detail komplett"
sed -n '/def api_kunden_detail/,/^def /p' apps/abpe_crm/views.py | head -60

# ------------------------------------------------------------------
sec "4) CrmUserSettings Modell - Muster fuer pro-Benutzer-Tabelle"
python3 -c "
import sys; sys.path.insert(0, '/opt/abpe/backend')
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
from apps.abpe_crm.models import CrmUserSettings
import inspect
print(inspect.getsource(CrmUserSettings))
"

# ------------------------------------------------------------------
sec "5) Letzte Migrationen (fuer naechste Nummer)"
ls apps/abpe_crm/migrations/ | grep -E '^[0-9]{4}_' | sort | tail -5

echo ""
echo "$LINE"
echo "FERTIG"
echo "$LINE"
