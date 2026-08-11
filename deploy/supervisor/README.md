# abpe-scheduler-loop — stabiler Taktgeber

Ohne diesen Supervisor-Prozess: **kein** periodisches `email_index`, keine MeetMe-Reminder.

## Symptom

```
abpe-scheduler-loop              STOPPED   Not started
```

= Programm existiert, wurde aber seit Supervisord-Start **nie** gestartet
(typisch: `autostart=false` in der Conf).

`supervisorctl restart all` startet ihn — aber nach Reboot / nur-Django-Restart
bleibt er wieder STOPPED.

## Fix (ucs5, einmalig + dauerhaft)

```bash
cd /mnt/public/udoo-reprap && git fetch origin cursor/shaduler-all-in-one-7f07
bash <(git show origin/cursor/shaduler-all-in-one-7f07:scripts/ENSURE-abpe-scheduler-loop.sh)
supervisorctl status abpe-django abpe-celery abpe-scheduler-loop
```

ENSURE macht:

1. `scheduler_loop.py` nach `/opt/abpe/backend/apps/abpe_scheduler/...` syncen
2. Supervisor-Conf: `autostart=true`, `autorestart=true`, `startretries=999`
3. `supervisorctl reread && update && start abpe-scheduler-loop`
4. Exit 1 wenn nicht RUNNING

## Regel

Nach Sync/Restart immer alle drei prüfen:

| Prozess | Rolle |
|---------|--------|
| `abpe-django` | API / Webhooks empfangen |
| `abpe-celery` | IMAP→ES (`email_index_run`) |
| `abpe-scheduler-loop` | Takt: faellige Jobs → Celery → Webhook |

Optional Gruppe: `deploy/supervisor/abpe-group.conf` → `supervisorctl restart abpe:*`
