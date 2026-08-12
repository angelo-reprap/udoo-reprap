#!/bin/bash
set -e
cd /opt/abpe/backend
LINE="============================================================"
sec() { echo ""; echo "$LINE"; echo "$1"; echo "$LINE"; }

# ------------------------------------------------------------------
sec "1) _normalize_hit komplett, exakter aktueller Stand (alle vier kind-Zweige)"
sed -n '/def _normalize_hit/,/^def /p' apps/abpe_edms/views.py

# ------------------------------------------------------------------
sec "2) _FIELDS_MAIL - welche Felder hat der Mail-Index ueberhaupt?"
sed -n '/_FIELDS_MAIL\s*=/,/\]/p' apps/abpe_edms/views.py

# ------------------------------------------------------------------
sec "3) ES-Mapping von abpe_emails - welche Feldnamen gibt es wirklich? (account/folder/uid/message_id)"
python3 -c "
import sys; sys.path.insert(0, '/opt/abpe/backend')
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
from elasticsearch import Elasticsearch
es = Elasticsearch(['http://localhost:9200'])
m = es.indices.get_mapping(index='abpe_emails')
props = list(m['abpe_emails']['mappings']['properties'].keys())
print('Felder:', props)
"

# ------------------------------------------------------------------
sec "4) mod-edms.js - api.akte / api.personMails / api.mailView Pfade (fuer Deep-Link-Ziel-Konstruktion)"
grep -n "akte:\|personMails:\|mailView:\|preview:" apps/abpe_crm/static/abpe_crm/js/mod-edms.js

echo ""
echo "$LINE"
echo "FERTIG"
echo "$LINE"
