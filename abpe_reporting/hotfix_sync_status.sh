#!/bin/bash
# Sofort-Reparatur für TypeError __rep_doc_count() auf ucs5
# Usage: cd /opt/abpe/backend && bash hotfix_sync_status.sh

set -e
cd /opt/abpe/backend

echo "========== Hotfix sync/status =========="
grep -n "documents_total\|__rep_doc_count\|_crm_edms_document_count\|_sync_documents_total" apps/abpe_crm/views.py | head -25

SCRIPT=/tmp/patch_sync_status_documents.py
curl -fsSL 'https://raw.githubusercontent.com/angelo-reprap/udoo-reprap/cursor/reporting-overhaul-c24e/abpe_reporting/patch_sync_status_documents.py' \
  -o "$SCRIPT"

python3 "$SCRIPT"
python3 -m py_compile apps/abpe_crm/views.py
supervisorctl restart abpe-django

echo ""
echo "========== Test =========="
python manage.py shell << 'PY'
from django.test import Client
from django.contrib.auth import get_user_model
c = Client()
u = get_user_model().objects.filter(is_superuser=True).first()
if u:
    c.force_login(u)
r = c.get('/crm/api/sync/status/')
print('GET /crm/api/sync/status/ ->', r.status_code)
print(r.content.decode('utf-8', errors='replace')[:500])
PY

echo "========== Fertig =========="
