#!/bin/bash
# Reporting-API auf ucs5 testen — Ergebnis kopieren und posten.
# Usage: cd /opt/abpe/backend && bash /tmp/test_reporting_api.sh

set -e
cd /opt/abpe/backend

echo "========== 1) Dateien =========="
ls -la apps/abpe_crm/reporting_api.py
grep -n "reporting" apps/abpe_crm/urls.py | head -10

echo ""
echo "========== 2) Django Test-Client (ohne Browser-Cookie) =========="
python manage.py shell << 'PY'
from django.test import Client
from django.contrib.auth import get_user_model

User = get_user_model()
u = User.objects.filter(is_superuser=True).first() or User.objects.first()
print("User:", u.username if u else "KEIN USER")

c = Client()
if u:
    c.force_login(u)

r = c.get("/crm/api/reporting/dashboard/")
print("GET /crm/api/reporting/dashboard/ ->", r.status_code)
body = r.content.decode("utf-8", errors="replace")
print(body[:1200] if len(body) > 1200 else body)

r2 = c.post(
    "/crm/api/reporting/sync/start/",
    data="{}",
    content_type="application/json",
)
print("\nPOST /crm/api/reporting/sync/start/ ->", r2.status_code)
print(r2.content.decode("utf-8", errors="replace"))

r3 = c.get("/crm/api/sync/status/")
print("\nGET /crm/api/sync/status/ ->", r3.status_code)
print(r3.content.decode("utf-8", errors="replace")[:400])
PY

echo ""
echo "========== 3) Legacy sync/status (cat) =========="
grep -A12 "def api_sync_status" apps/abpe_crm/views.py | head -14

echo ""
echo "========== Fertig =========="
