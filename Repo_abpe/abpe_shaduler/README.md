# ABpE Shaduler — Repo-Scaffold (V0)

**App-Name (Architektur):** `apps.abpe_shaduler`  
**Nicht verwechseln mit:** `apps.abpe_scheduler` (Cron/Job-Runner — bleibt unangetastet)

> Schreibweise: Architektur-Dok = **shaduler** (mit *e*).  
> Falls du `abpe_shadular` meintest: bitte einmal festlegen — Repo folgt dem Frozen LLD.

## Inhalt dieses Branches

| Pfad | Zweck |
|------|--------|
| `Repo_abpe/abpe_shaduler/incoming/` | Django-App (Live-Ziel: `/opt/abpe/backend/apps/abpe_shaduler/`) |
| `…/Architektur_zielvorlage.md` | Frozen LLD |
| `…/docs/mockup_final.html` | Final-Mockup |
| `Repo_abpe/abpe_ui/incoming/modules/shaduler/module.json` | Sidebar-Modul (order 24, `!berater`) |
| `…/mod-shaduler.css` / `.js` / `-kalender.js` | Static |
| `…/i18n/{de,en}/modules/shaduler/` | i18n DE/EN |

## Status

- Modelle (10) + Admin + URL-Gerüst + Stub-APIs + Portal-Index: **vorhanden**
- **Taktgeber:** `scheduler_client.py` + Webhooks → `abpe_scheduler` (Kap. 0), **kein** Celery Beat
- Services / Signals: **Stubs**
- Migrationen: **noch nicht erzeugt** (`makemigrations` erst nach Register + Review)
- Live-Register (`apps.py` / `urls.py`): **manuell per nano** — siehe `SETUP_NANO.md`

## Scan-Kurzfazit

Siehe `SCAN.md`.
