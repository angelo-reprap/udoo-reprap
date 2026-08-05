# Umsetzungshinweis — Taktgeber (Stand 04.08.2026)

Die aktualisierte `Architektur_zielvorlage.md` sagt in **Kap. 0** klar:

> Die vier Shaduler-Beat-Tasks werden **NICHT** über Celery Beat konfiguriert,
> sondern als wiederkehrende `SchedulerJob`-Einträge über denselben
> `scheduler_client`-Weg wie MeetMe registriert — **ein Taktgeber**.

**Kap. 1 / Kap. 4** im Frozen-Dok nennen `tasks.py` noch „Celery Beat“ —
das ist veraltet gegenüber Kap. 0. Umsetzung im Repo:

| Artefakt | Rolle |
|----------|--------|
| `scheduler_client.py` | HTTP-Client → `/scheduler/api/jobs/create/` (`owner_app=abpe_shaduler`) |
| `tasks.py` | Handler-Funktionen (kein Celery-Beat) |
| `api/webhook/<job_key>/` | PUSH-Callback vom Scheduler |
| `manage.py register_scheduler_jobs` | RECURRING-Jobs (RRULE 5 / 2 / 15 Min) |

Settings (bereits für MeetMe üblich):

- `SCHEDULER_SERVICE_TOKEN`
- `SCHEDULER_API_BASE_URL` (Default `http://localhost:8000/scheduler/api`)
- optional `SHADULER_CALLBACK_BASE_URL` (Default `http://localhost:8000/shaduler/api`)

Jobs (RRULE):

| job_key | Intervall | Webhook |
|---------|-----------|---------|
| `radar_poll` | 5 Min | `/shaduler/api/webhook/radar-poll/` |
| `inbox_poll` | 2 Min | `/shaduler/api/webhook/inbox-poll/` |
| `prozess_tick` | 15 Min | `/shaduler/api/webhook/prozess-tick/` |
| `email_index` | **1 Min** | `/shaduler/api/webhook/email-index/?token=…` |

**Timeout:** `abpe_scheduler` POSTet mit `timeout=15` und **ohne** `Authorization`-Header.
Deshalb enthält die Callback-URL `?token=` (siehe `scheduler_client.build_callback_url`).
Indexer läuft async via Celery. Nach Token-Fix: `register_scheduler_jobs` erneut.

**Härte (email_index):**
- Celery-Retry bei Fehler: 60s → 120s → 180s (`max_retries=3`)
- Celery/Broker down → Daemon-Thread-Fallback (Webhook bleibt schnell)
- Soft-Poll UI: Pause bei Dialog/Hidden-Tab; Fehler-Backoff 60→120→180; Refresh-Button

Supervisor restartet Celery bei Crash — kein Auto-Restart aus dem Webhook nötig.

## Webhook-Auth prüfen (401 vs. OK)

PUSH vom Scheduler braucht denselben `SCHEDULER_SERVICE_TOKEN` wie Django.
`register_scheduler_jobs` kann OK sein (Outbound), während Inbound 401 liefert,
wenn der Scheduler beim PUSH einen anderen/keinen Token mitschickt.

```bash
# Token aus Django-Settings laden und Webhook manuell treffen:
cd /opt/abpe/backend && /opt/abpe/venv311/bin/python - <<'PY'
import django, os, json, urllib.request
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
from django.conf import settings
tok = settings.SCHEDULER_SERVICE_TOKEN
req = urllib.request.Request(
    'http://127.0.0.1:8000/shaduler/api/webhook/inbox-poll/',
    data=b'{"job":"inbox_poll"}',
    headers={
        'Authorization': f'Token {tok}',
        'Content-Type': 'application/json',
    },
    method='POST',
)
with urllib.request.urlopen(req, timeout=60) as r:
    print(r.status, r.read()[:500])
PY
```

Erwartung: HTTP 200 + `{"ok": true, "job": "inbox_poll", ...}`.
Bei 401: Token in Scheduler-Service und Django angleichen (wie MeetMe).
Bei `SyntaxError`: `tasks.py` muss `def` (nicht `function`) haben — SYNC + restart.
