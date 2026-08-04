# Scan — Ausgangslage für `apps/abpe_shaduler` (04.08.2026)

## Naming

| Name | Rolle |
|------|--------|
| **`abpe_shaduler`** | Neu — Aufgaben / Kalender / Inbox / Radar / Regeln (dieses Modul) |
| **`abpe_scheduler`** | Bestehend — Job-Timer (ONCE/RRULE), URL `/scheduler/` — **unangetastet** |
| User-Tipp `abpe_shadular` | Vermutlich Tippfehler → Architektur = **shaduler** |

## Live (ucs5) — bereits vorhanden

- `ABPE_APPS` enthält u.a. `apps.abpe_scheduler`, `apps.abpe_matching_workflow`, `apps.abpe_crm`, `apps.abpe_ui`, Studios…
- Root-urls: `path('scheduler/', …)`, `path('matching/', …)`, `path('crm/', …)`, **kein** `shaduler/`
- Matching-UI: Sidebar order **25**, roles `!berater` → Shaduler order **24** (direkt davor)

## Architektur (Frozen LLD)

Quelle: `Architektur_zielvorlage.md` im App-Ordner.

- 6 Reiter: Aufgaben · Kalender · Posteingang · Radar Anfragen · Radar Berater · Regeln
- 10 Modelle, Services-Fassaden, Celery-Tasks, Signals auf Matching
- Schwester-App `abpe_composer` = eigene Etappe (hier nur Schnittstelle)
- V1 = Aufgaben+Ergebnis+Aktivität+Regeln+Admin+i18n DE/EN

## Mockup

`docs/mockup_final.html` — 3 Uploads waren byte-identisch (ein Final).  
CSS-Komponenten nach `mod-shaduler.css` übernommen (Akzent-Variablen `--a-*`).

## Repo-Konvention

| Live | Repo-Export |
|------|-------------|
| `/opt/abpe/backend/apps/abpe_shaduler/` | `Repo_abpe/abpe_shaduler/incoming/` |
| `abpe_ui/.../modules/shaduler/` | `Repo_abpe/abpe_ui/incoming/modules/shaduler/` |
| `abpe_ui/static/.../mod-shaduler.*` | `Repo_abpe/abpe_ui/incoming/mod-shaduler.*` (+ `static_abpe_ui/`) |

Matching-Django-App ist im Git kaum als `incoming/` exportiert — Shaduler-Scaffold folgt MeetMe/Email-Studio-Muster + Architektur.

## Bewusst nicht gemacht

- Kein Eintrag in Live-`apps.py` / `urls.py` (dein nano)
- Keine Migration applied
- Keine Celery-Beat-Einträge
- Kein Umbau `abpe_scheduler` / Matching
