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
| `manage.py register_scheduler_jobs` | RRULE-Jobs anlegen (5 / 2 / 15 Min) |

Settings (bereits für MeetMe üblich):

- `SCHEDULER_SERVICE_TOKEN`
- `SCHEDULER_API_BASE_URL` (Default `http://localhost:8000/scheduler/api`)
- optional `SHADULER_CALLBACK_BASE_URL` (Default `http://localhost:8000/shaduler/api`)
