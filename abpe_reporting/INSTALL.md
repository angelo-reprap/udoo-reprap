# Reporting — Reparatur (404 auf /crm/api/reporting/dashboard/)

Der 404 bedeutet: **Route fehlt in urls.py** (und/oder reporting_api.py fehlt).
Das alte Install-Script ist abgebrochen — deshalb nichts registriert.

## Ein Befehlsblock (copy & paste)

```bash
cd /opt/abpe/backend

curl -sL 'https://raw.githubusercontent.com/angelo-reprap/udoo-reprap/cursor/reporting-overhaul-c24e/abpe_reporting/incoming/reporting_api.py' \
  -o /tmp/reporting_api.py

curl -sL 'https://raw.githubusercontent.com/angelo-reprap/udoo-reprap/cursor/reporting-overhaul-c24e/abpe_reporting/apply_reporting_views_ucs5.py' \
  -o /tmp/apply_reporting_views_ucs5.py

python3 /tmp/apply_reporting_views_ucs5.py --snippet /tmp/reporting_api.py
python3 -m py_compile apps/abpe_crm/reporting_api.py apps/abpe_crm/urls.py
supervisorctl restart abpe-django
```

Erwartete Ausgabe u.a.:
```
OK: .../apps/abpe_crm/reporting_api.py installiert
urls.py: Routen nach api/sync/status/ eingefügt
OK: urls.py enthält reporting-Routen
```

## Prüfen

```bash
grep -n "reporting" apps/abpe_crm/urls.py
ls -la apps/abpe_crm/reporting_api.py
python3 -m py_compile apps/abpe_crm/urls.py && echo "urls.py OK"
```

Dann Strg+F5 auf `/crm/reporting/` — kein 404 mehr in der Konsole.

## Sync-Status reparieren (TypeError __rep_doc_count)

Falls `/crm/api/sync/status/` mit `__rep_doc_count() missing 1 required positional argument: 'request'` fehlschlägt:

```bash
cd /opt/abpe/backend
curl -sL 'https://raw.githubusercontent.com/angelo-reprap/udoo-reprap/cursor/reporting-overhaul-c24e/abpe_reporting/patch_sync_status_documents.py' \
  -o /tmp/patch_sync_status_documents.py
python3 /tmp/patch_sync_status_documents.py
python3 -m py_compile apps/abpe_crm/views.py
supervisorctl restart abpe-django
python manage.py shell -c "from django.test import Client; c=Client(); print(c.get('/crm/api/sync/status/').status_code, c.get('/crm/api/sync/status/').content[:200])"
```

Erwartung: Status **200**, `documents_total` > 0 (EDMS).

## Frontend (falls noch nicht)

```bash
BASE='https://raw.githubusercontent.com/angelo-reprap/udoo-reprap/cursor/reporting-overhaul-c24e/abpe_reporting/incoming'
curl -sL "$BASE/mod-crm-reporting.js" -o apps/abpe_crm/static/abpe_crm/js/mod-crm-reporting.js
python manage.py collectstatic --noinput
```
