# abpe_meetme — Backend (Konferenz / MeetMe)

Django-App für Konferenzplanung, Einladungen, Erinnerungsregeln und Scheduler-Anbindung.

## Im Git-Repo

| Pfad | Inhalt |
|---|---|
| `incoming/` | Spiegel von `/opt/abpe/backend/apps/abpe_meetme/` |
| `../abpe_scheduler/incoming/` | Scheduler-App (Webhook, Jobs) |

**Baseline** (Jul 2025): `views.py`, `urls.py`, `email_helpers.py`, `reminder_engine.py` — unvollständig ohne `models.py`, `serializers.py`, `scheduler_client.py`.

## Aktuellen Stand von ucs5 exportieren

```bash
cd /mnt/public/udoo-reprap && git pull
bash scripts/export-meetme-backend.sh
git add Repo_abpe/abpe_meetme Repo_abpe/abpe_scheduler
git commit -m "Export: MeetMe + Scheduler Backend von ucs5"
git push
```

## Deploy Fix nach ucs5

```bash
cd /mnt/public/udoo-reprap && git pull
bash Repo_abpe/abpe_meetme/incoming/RUN-deploy-meetme-backend-ucs5.sh
cd /opt/abpe/backend && python manage.py migrate abpe_meetme --noinput
supervisorctl restart abpe-django abpe-scheduler-loop abpe-celery
```

## AUTO-Versand (implementiert)

`api_webhook_reminder_due`: bei `rule.mode == 'AUTO'` → `_mm_send_reminder_delivery()` (HTML, Anhänge, Vorlage).  
Bei `MANUAL` → `status=DUE` für Sende-Assistent.
