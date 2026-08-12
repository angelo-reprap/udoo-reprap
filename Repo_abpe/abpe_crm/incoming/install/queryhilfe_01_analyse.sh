#!/bin/bash
set -e
cd /opt/abpe/backend
LINE="============================================================"
sec() { echo ""; echo "$LINE"; echo "$1"; echo "$LINE"; }

# ------------------------------------------------------------------
sec "1) api_berater_list KOMPLETT (Rest ab 'if status:', den wir noch nicht gesehen haben)"
sed -n '/def api_berater_list/,/^def api_berater_detail/p' apps/abpe_crm/views.py

# ------------------------------------------------------------------
sec "2) CrmContact Modell - stundensatz/verfuegbar_ab - welcher DB-Typ wirklich?"
python3 -c "
import sys; sys.path.insert(0, '/opt/abpe/backend')
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
from apps.abpe_crm.models import CrmContact, CrmContactCstm
for f in CrmContact._meta.get_fields():
    if 'stunden' in f.name.lower() or 'verfueg' in f.name.lower() or 'rate' in f.name.lower():
        print('CrmContact:', f.name, type(f).__name__)
for f in CrmContactCstm._meta.get_fields():
    if 'stunden' in f.name.lower() or 'verfueg' in f.name.lower() or 'rate' in f.name.lower():
        print('CrmContactCstm:', f.name, type(f).__name__)
"

# ------------------------------------------------------------------
sec "3) documents_content.py - ContentPersonIndex - wie ist verfuegbar_ab/stundensatz dort gemappt (prepare-Methoden)?"
sed -n '/class ContentPersonIndex/,/^class /p' apps/abpe_crm/documents_content.py | head -100

# ------------------------------------------------------------------
sec "4) Existiert schon ein wiederverwendbarer ES-Client-Helper in abpe_crm?"
grep -rn "Elasticsearch(\[" apps/abpe_crm/*.py apps/abpe_crm/services/*.py 2>/dev/null

echo ""
echo "$LINE"
echo "FERTIG"
echo "$LINE"
