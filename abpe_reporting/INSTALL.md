# Reporting-Modul — Deploy (ucs5)

Branch: `cursor/reporting-overhaul-c24e`

## Fehler beheben (wenn nach erstem Deploy Meldungen / 500)

Meist **SyntaxError in urls.py** (doppeltes Komma) oder **fehlendes reporting_api.py**.
Install-Script erneut ausführen (repariert urls + entfernt alten views-Anhang):

```bash
cd /opt/abpe/backend
curl -sL 'https://raw.githubusercontent.com/angelo-reprap/udoo-reprap/cursor/reporting-overhaul-c24e/abpe_reporting/apply_reporting_views_ucs5.py' -o /tmp/apply_reporting_views_ucs5.py
curl -sL 'https://raw.githubusercontent.com/angelo-reprap/udoo-reprap/cursor/reporting-overhaul-c24e/abpe_reporting/incoming/reporting_api.py' -o /tmp/reporting_api.py
python3 /tmp/apply_reporting_views_ucs5.py --snippet /tmp/reporting_api.py
python3 -m py_compile apps/abpe_crm/reporting_api.py apps/abpe_crm/urls.py apps/abpe_crm/views.py
supervisorctl restart abpe-django
```

## 1. Backup

```bash
cd /opt/abpe/backend
python3 Archiv/backup_restore.py -save apps/abpe_crm/static/abpe_crm/js/mod-crm-reporting.js -m "vor reporting overhaul"
python3 Archiv/backup_restore.py -save apps/abpe_crm/templates/abpe_crm/tabs/reporting_tab.html -m "vor reporting overhaul"
python3 Archiv/backup_restore.py -save apps/abpe_crm/urls.py -m "vor reporting urls"
```

## 2. Frontend (curl)

```bash
BASE='https://raw.githubusercontent.com/angelo-reprap/udoo-reprap/cursor/reporting-overhaul-c24e/abpe_reporting/incoming'

curl -sL "$BASE/mod-crm-reporting.js" \
  -o apps/abpe_crm/static/abpe_crm/js/mod-crm-reporting.js

curl -sL "$BASE/reporting_tab.html" \
  -o apps/abpe_crm/templates/abpe_crm/tabs/reporting_tab.html
```

## 3. Backend-API

```bash
curl -sL 'https://raw.githubusercontent.com/angelo-reprap/udoo-reprap/cursor/reporting-overhaul-c24e/abpe_reporting/apply_reporting_views_ucs5.py' \
  -o /tmp/apply_reporting_views_ucs5.py

curl -sL 'https://raw.githubusercontent.com/angelo-reprap/udoo-reprap/cursor/reporting-overhaul-c24e/abpe_reporting/incoming/reporting_api.py' \
  -o /tmp/reporting_api.py

python3 /tmp/apply_reporting_views_ucs5.py --snippet /tmp/reporting_api.py
python3 -m py_compile apps/abpe_crm/reporting_api.py apps/abpe_crm/urls.py
supervisorctl restart abpe-django
```

## 4. i18n

```bash
curl -sL 'https://raw.githubusercontent.com/angelo-reprap/udoo-reprap/cursor/reporting-overhaul-c24e/abpe_i18n_fix/patch_reporting_i18n.py' \
  -o /tmp/patch_reporting_i18n.py
python3 /tmp/patch_reporting_i18n.py
python apps/abpe_crm/bin/i18n_translator.py
python apps/abpe_crm/bin/i18n_validate.py
```

## 5. Static

```bash
python manage.py collectstatic --noinput
```

Strg+F5 → `/crm/reporting/`

## Fallback

Ohne Backend zeigt das JS Basis-Zähler aus `/crm/api/sync/status/` mit Hinweis-Banner.

## Prüfen

```bash
grep -n "api/reporting" apps/abpe_crm/urls.py
grep -n "reporting_api" apps/abpe_crm/views.py
curl -s -b /tmp/cookies.txt http://127.0.0.1:8000/crm/api/reporting/dashboard/ | head
```
