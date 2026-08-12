#!/bin/bash
# ============================================================
# queryhilfe_00_analyse.sh
# Analyse fuer den Umbau Berater/Kunden/Emails/Dokumente-Suche
# von ORM-icontains auf echtes ES query_string (AND/OR/NOT/Feld/
# Wildcard/Fuzzy/Phrase - wie in der Query-Hilfe-Box beworben).
# ============================================================
set -e
cd /opt/abpe/backend
LINE="============================================================"
sec() { echo ""; echo "$LINE"; echo "$1"; echo "$LINE"; }

# ------------------------------------------------------------------
sec "1) api_kunden_list komplett"
sed -n '/def api_kunden_list/,/^def /p' apps/abpe_crm/views.py | head -80

# ------------------------------------------------------------------
sec "2) api_dokumente_list komplett"
sed -n '/def api_dokumente_list/,/^def /p' apps/abpe_crm/views.py | head -60

# ------------------------------------------------------------------
sec "3) Welcher Endpunkt bedient den 'emails'-Tab? (urls.py)"
grep -n "emails" apps/abpe_crm/urls.py

# ------------------------------------------------------------------
sec "4) urls.py - alle vier Routen exakt (fuer spaeteren Verify, keine Aenderung)"
grep -n "api/berater/\|api/kunden/\|api/emails\|api/dokumente" apps/abpe_crm/urls.py

# ------------------------------------------------------------------
sec "5) ES-Mapping 'content' (Personen) - ALLE echten Feldnamen"
python3 -c "
import sys; sys.path.insert(0, '/opt/abpe/backend')
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
from elasticsearch import Elasticsearch
es = Elasticsearch(['http://localhost:9200'])
m = es.indices.get_mapping(index='content')
props = m['content']['mappings']['properties']
for k, v in props.items():
    print(f'{k}: {v.get(\"type\")}')"

# ------------------------------------------------------------------
sec "6) ES-Mapping 'content_firma' (Firmen) - ALLE echten Feldnamen"
python3 -c "
import sys; sys.path.insert(0, '/opt/abpe/backend')
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
from elasticsearch import Elasticsearch
es = Elasticsearch(['http://localhost:9200'])
m = es.indices.get_mapping(index='content_firma')
props = m['content_firma']['mappings']['properties']
for k, v in props.items():
    print(f'{k}: {v.get(\"type\")}')"

# ------------------------------------------------------------------
sec "7) Gibt es ueberhaupt einen ES-Index fuer CrmDocument (Doc-Studio, NICHT EDMS-dms)?"
python3 -c "
import sys; sys.path.insert(0, '/opt/abpe/backend')
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
from elasticsearch import Elasticsearch
es = Elasticsearch(['http://localhost:9200'])
print(sorted(es.indices.get_alias(index='*').keys()))"

# ------------------------------------------------------------------
sec "8) Gibt es schon eine documents_content-aehnliche Index-Definition fuer Firma/Person, die wir kennen sollten (Feld-Locations, Boosts)?"
grep -n "class ContentPersonIndex\|class ContentFirmaIndex" apps/abpe_crm/documents_content.py apps/abpe_crm/documents_content_firma.py

echo ""
echo "$LINE"
echo "FERTIG"
echo "$LINE"
