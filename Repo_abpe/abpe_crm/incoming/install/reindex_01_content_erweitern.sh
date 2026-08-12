#!/bin/bash
# ============================================================
# reindex_01_content_erweitern.sh
# Personen-Index `content` erweitern:
#   - verfuegbar_ab: Text -> DateField (echte Bereichssuche)
#   - stundensatz: NEU, aus konditionen_c extrahiert (Plausibilitaet 10-500)
#   - company/account_crm_ids/is_ansprechpartner: NEU, Firma-Join
#     (Ansprechpartner-Kennzeichen fuer Kunden-Kontakte)
# --rebuild legt den Index komplett neu an (Mapping-Aenderung sicher).
# ============================================================
set -e
cd /opt/abpe/backend
FILE="apps/abpe_crm/documents_content.py"

echo "=== [1/5] Backup ==="
python3 Archiv/backup_restore.py -save "$FILE" -m "reindex_01: verfuegbar_ab+stundensatz+company"

echo "=== [2/5] Patches ==="
python3 /tmp/reindex01/patch.py

echo "=== [3/5] Syntax-Check ==="
python3 -c "import ast; ast.parse(open('$FILE').read()); print('  documents_content.py OK')"

echo "=== [4/5] Reindex (--rebuild, Mapping neu) ==="
python manage.py content_reindex --rebuild

echo "=== [5/5] Verifikation ==="
python3 -c "
import sys; sys.path.insert(0, '/opt/abpe/backend')
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
from elasticsearch import Elasticsearch
es = Elasticsearch(['http://localhost:9200'])
m = es.indices.get_mapping(index='content')['content']['mappings']['properties']
print('verfuegbar_ab Typ:', m.get('verfuegbar_ab', {}).get('type'))
print('stundensatz Typ:', m.get('stundensatz', {}).get('type'))
print('company Typ:', m.get('company', {}).get('type'))
print('is_ansprechpartner Typ:', m.get('is_ansprechpartner', {}).get('type'))

r1 = es.count(index='content', query={'range': {'stundensatz': {'gte': 10}}})
print('Personen mit erkanntem Stundensatz:', r1['count'])

r2 = es.count(index='content', query={'term': {'is_ansprechpartner': True}})
print('Personen als Ansprechpartner (Firma verknuepft):', r2['count'])

r3 = es.search(index='content', size=1, query={'term': {'crm_id': '28539747-c732-dbfb-6f04-4b7a7702ae6a'}})
if r3['hits']['hits']:
    src = r3['hits']['hits'][0]['_source']
    print('Beispiel Angelo Malaguarnera - stundensatz:', src.get('stundensatz'), '| company:', src.get('company'))
"

echo ""
echo "============================================================"
echo "✅ reindex_01 fertig."
echo "Danach: query_string-Umbau von api_berater_list (Phase 1 der"
echo "Query-Hilfe-Reparatur), damit stundensatz/verfuegbar_ab/company"
echo "auch wirklich durchsuchbar sind."
echo "============================================================"
