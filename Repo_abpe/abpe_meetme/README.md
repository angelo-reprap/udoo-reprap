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

## Deploy zurück nach ucs5 (nach Agent-Fix)

```bash
rsync -a Repo_abpe/abpe_meetme/incoming/ /opt/abpe/backend/apps/abpe_meetme/
rsync -a Repo_abpe/abpe_scheduler/incoming/ /opt/abpe/backend/apps/abpe_scheduler/
cd /opt/abpe/backend && supervisorctl restart abpe-django abpe-scheduler-loop
```

## Bekannte Lücke (AUTO-Versand)

`api_webhook_reminder_due` setzt bei Fälligkeit nur `status=DUE`.  
Bei `mode=AUTO` wird **noch nicht automatisch** versendet — das ist der nächste Fix nach vollständigem Export.
