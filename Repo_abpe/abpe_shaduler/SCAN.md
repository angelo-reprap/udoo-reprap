# Scan — Ausgangslage für `apps/abpe_shaduler` (04.08.2026)

## Naming

| Name | Rolle |
|------|--------|
| **`abpe_shaduler`** | Neu — Aufgaben / Kalender / Inbox / Radar / Regeln (dieses Modul) |
| **`abpe_scheduler`** | Bestehend — Job-Timer (ONCE/RECURRING + rrule_string), URL `/scheduler/` — **unangetastet** |
| User-Tipp `abpe_shadular` | Vermutlich Tippfehler → Architektur = **shaduler** |

## Live (ucs5) — bereits vorhanden

- `ABPE_APPS` enthält u.a. `apps.abpe_scheduler`, `apps.abpe_matching_workflow`, `apps.abpe_crm`, `apps.abpe_ui`, Studios…
- Root-urls: `path('scheduler/', …)`, `path('matching/', …)`, `path('crm/', …)`, **kein** `shaduler/`
- Matching-UI: Sidebar order **25**, roles `!berater` → Shaduler order **24** (direkt davor)

## Architektur (Frozen LLD)

Quelle: `incoming/Architektur_zielvorlage.md` (Update 04.08.2026 inkl. Kap.-0-Befund
zu `abpe_scheduler` / MeetMe).

- 6 Reiter: Aufgaben · Kalender · Posteingang · Radar Anfragen · Radar Berater · Regeln
- 10 Modelle, Services-Fassaden, Signals auf Matching
- **Periodik über `abpe_scheduler` (SchedulerJob + Webhook), nicht Celery Beat**
  → siehe `incoming/docs/UMSETZUNG_SCHEDULER.md`
- Schwester-App `abpe_composer` = eigene Etappe
- V1 = Aufgaben+Ergebnis+Aktivität+Regeln+Admin+i18n DE/EN

## Bewusst nicht gemacht

- Kein Eintrag in Live-`apps.py` / `urls.py` (dein nano)
- Keine Migration applied
- Keine Umbauten an `abpe_scheduler` / Matching / MeetMe
- Celery-Beat-Einträge: bewusst **nicht** (Kap. 0)
