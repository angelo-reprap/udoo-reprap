# Shaduler — manueller Live-Anschluss (ucs5 / nano)

Du registrierst bewusst selbst. Agent legt nur Dateien unter
`Repo_abpe/abpe_shaduler/incoming/` (+ UI-Anteile) an.

## 1) App-Dateien nach Live kopieren

```bash
cd /mnt/public/udoo-reprap
git fetch origin cursor/abpe-shaduler-scaffold-7f07
# oder Branch checkout / rsync

mkdir -p /opt/abpe/backend/apps/abpe_shaduler
rsync -a --delete \
  Repo_abpe/abpe_shaduler/incoming/ \
  /opt/abpe/backend/apps/abpe_shaduler/

# UI-Modul
mkdir -p /opt/abpe/backend/apps/abpe_ui/templates/abpe_ui/modules/shaduler
cp Repo_abpe/abpe_ui/incoming/modules/shaduler/module.json \
   /opt/abpe/backend/apps/abpe_ui/templates/abpe_ui/modules/shaduler/module.json

mkdir -p /opt/abpe/backend/apps/abpe_ui/static/abpe_ui/css/mod \
         /opt/abpe/backend/apps/abpe_ui/static/abpe_ui/js/mod
cp Repo_abpe/abpe_ui/incoming/mod-shaduler.css \
   /opt/abpe/backend/apps/abpe_ui/static/abpe_ui/css/mod/mod-shaduler.css
cp Repo_abpe/abpe_ui/incoming/mod-shaduler.js \
   /opt/abpe/backend/apps/abpe_ui/static/abpe_ui/js/mod/mod-shaduler.js
cp Repo_abpe/abpe_ui/incoming/mod-shaduler-kalender.js \
   /opt/abpe/backend/apps/abpe_ui/static/abpe_ui/js/mod/mod-shaduler-kalender.js

# i18n DE/EN
for lang in de en; do
  mkdir -p /opt/abpe/backend/apps/abpe_ui/static/abpe_ui/i18n/$lang/modules/shaduler
  cp Repo_abpe/abpe_ui/incoming/i18n/$lang/modules/shaduler/* \
     /opt/abpe/backend/apps/abpe_ui/static/abpe_ui/i18n/$lang/modules/shaduler/
done
```

## 2) nano — INSTALLED / ABPE_APPS

```bash
nano /opt/abpe/backend/abpe_backend/settings/apps.py
```

Zeile ergänzen (z. B. neben Matching / vor `abpe_ui`-Block):

```python
    'apps.abpe_shaduler',
```

**Nicht** `abpe_scheduler` ersetzen oder umbenennen.

## 3) nano — Haupt-urls.py

```bash
nano /opt/abpe/backend/abpe_backend/urls.py
```

Eintrag **VOR** dem Catch-all `path('', include('apps.abpe_ui.urls'))`
(z. B. direkt nach `meetme/` / vor `edms/`):

```python
    path('shaduler/', include('apps.abpe_shaduler.urls', namespace='abpe_shaduler')),
```

**Nicht** ans Dateiende unter `path('', …)` — sonst greift das Portal zuerst und `/shaduler/` kommt nie an.

## 4) Check (noch ohne migrate)

```bash
cd /opt/abpe/backend
djjenv
python -c "import apps.abpe_shaduler; print(apps.abpe_shaduler)"
# urls import:
python manage.py check --deploy 2>/dev/null | head
# oder:
python manage.py shell -c "from django.urls import reverse; print('ok')"
supervisorctl restart abpe-django
```

Migrationen **erst** nach Review der Modelle:

```bash
python manage.py makemigrations abpe_shaduler
# python manage.py migrate abpe_shaduler   # bewusst separat freigeben
```

## 5) Smoke

- Sidebar: Modul „Aufgaben“ (order 24) sichtbar für Nicht-Berater
- `https://…/shaduler/` öffnet Reiter-Gerüst
- `GET /shaduler/api/stats/` → JSON Stub `{ok, stub, badges…}`

## 6) Periodik über abpe_scheduler (kein Celery Beat)

Nach Register + Token (gleicher `SCHEDULER_SERVICE_TOKEN` wie MeetMe):

```bash
python manage.py register_scheduler_jobs --dry-run
python manage.py register_scheduler_jobs
```

Webhooks: `POST /shaduler/api/webhook/radar-poll/` (etc.) — siehe
`incoming/docs/UMSETZUNG_SCHEDULER.md`.
