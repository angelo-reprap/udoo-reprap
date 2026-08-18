# Matching Outreach Wizard — API-Inventar

Repo: `/workspace`

## Wizard-Flow Gap (Soll vs. Ist)

| Step | Status | Titel |
|------|--------|-------|
| `1_match` | ✅ `exists` | Anfrage matchen → Shortlist (Score ≥ Threshold) |
| `2_deep_reason` | ❌ `missing` | Pro Kandidat: DeepSeek CV↔Anfrage Begründung (warum anschreiben / Chance) |
| `3_letter_draft` | 🟡 `partial` | Persönliches Anschreiben entwerfen (editierbar) |
| `4_letter_polish` | ❌ `missing` | Optional: DeepSeek Anschreiben polieren (Stil behalten) |
| `5_send` | ✅ `exists` | Mail senden + Match-Status (angeschrieben) |
| `6_wiedervorlage` | 🟡 `partial` | Wiedervorlage-Aufgabe anlegen (default, editierbar) |
| `7_next` | ❌ `missing` | Nächster Kandidat (sequentieller Outreach-Wizard) |
| `support_ki_anfrage` | ✅ `exists` | Support: Anfrage aus E-Mail (KI-Anfragen-Wizard) |
| `support_terms` | ✅ `exists` | Support: Berater-Terms / Shortlist-Reset / Request-Edit |

### 1_match — Anfrage matchen → Shortlist (Score ≥ Threshold)
- **Status:** `exists`
- Vorhanden / geprüft:
  - ✅ `/matching/api/requests/<uuid>/match/`
  - ✅ `/matching/api/requests/<uuid>/shortlist/`

### 2_deep_reason — Pro Kandidat: DeepSeek CV↔Anfrage Begründung (warum anschreiben / Chance)
- **Status:** `missing`
- Fehlt / UI-only:
  - `/matching/api/match/<uuid>/deep-reason/`
  - `/ki-wizard/api/matching-outreach/reason/`

### 3_letter_draft — Persönliches Anschreiben entwerfen (editierbar)
- **Status:** `partial`
- **Hinweis:** Frontend hat STAGE_MAIL-Templates; kein DeepSeek-Draft-Endpoint.
- Vorhanden / geprüft:
  - ✅ `/crm/api/email/send/`
- Fehlt / UI-only:
  - `/matching/api/match/<uuid>/letter/draft/`

### 4_letter_polish — Optional: DeepSeek Anschreiben polieren (Stil behalten)
- **Status:** `missing`
- **Hinweis:** CRM PBX hat polished_text für Call-Notes — nicht für Matching-Mail.
- Fehlt / UI-only:
  - `/matching/api/match/<uuid>/letter/polish/`

### 5_send — Mail senden + Match-Status (angeschrieben)
- **Status:** `exists`
- Vorhanden / geprüft:
  - ✅ `/crm/api/email/send/`
  - ✅ `/matching/api/match/<uuid>/move/`
  - ✅ `/matching/api/match/<uuid>/status/`

### 6_wiedervorlage — Wiedervorlage-Aufgabe anlegen (default, editierbar)
- **Status:** `partial`
- **Hinweis:** API existiert; Wizard-Flow nach Send noch nicht verdrahtet als outreach/complete.
- Vorhanden / geprüft:
  - ✅ `/shaduler/api/aufgaben/create/`

### 7_next — Nächster Kandidat (sequentieller Outreach-Wizard)
- **Status:** `missing`
- Fehlt / UI-only:
  - `UI: Shortlist → Outreach-Wizard Modal-Sequenz`
  - `/matching/api/match/<uuid>/outreach/complete/`

### support_ki_anfrage — Support: Anfrage aus E-Mail (KI-Anfragen-Wizard)
- **Status:** `exists`
- Vorhanden / geprüft:
  - ✅ `/ki-wizard/api/matching-anfrage/extract/`

### support_terms — Support: Berater-Terms / Shortlist-Reset / Request-Edit
- **Status:** `exists`
- Vorhanden / geprüft:
  - ✅ `/shaduler/api/matching/terms/<uuid>/`
  - ✅ `/shaduler/api/matching/shortlist/reset/<uuid>/`
  - ✅ `/shaduler/api/matching/request/<uuid>/`

## Apps / URL-Module

### abpe_matching_workflow → `/matching/`
- Rolle: Anfrage, Match, Shortlist, Kanban, Status
- urls: `Repo_abpe/abpe_matching_workflow/incoming/urls.py`
- views/api: `Repo_abpe/abpe_matching_workflow/incoming/views.py`

| Methods | Path | View | Name | Summary |
|--------|------|------|------|---------|
| GET | `/matching/api/stats/` | `api_stats:98` | `api_stats` | Matching Dashboard Statistiken |
| GET | `/matching/api/requests/` | `api_project_list:138` | `api_project_list` | Projektanfragen Liste |
| ? | `/matching/api/account/<str:account_crm_id>/requests/` | `api_account_requests:1011` | `api_account_requests` | Projektanfragen einer Firma (crm_account_id) — read-only fue |
| POST | `/matching/api/requests/create/` | `api_project_create:249` | `api_project_create` | Projektanfrage erstellen |
| GET | `/matching/api/requests/<uuid:project_id>/` | `api_project_detail:198` | `api_project_detail` | Projektanfrage Detail |
| PATCH | `/matching/api/requests/<uuid:project_id>/update/` | `api_project_update:290` | `api_project_update` | Projektanfrage aktualisieren |
| POST | `/matching/api/requests/<uuid:project_id>/match/` | `api_run_matching:323` | `api_run_matching` | Matching starten (async) |
| GET | `/matching/api/requests/<uuid:project_id>/shortlist/` | `api_shortlist:356` | `api_shortlist` | Shortlist abrufen |
| GET | `/matching/api/requests/<uuid:project_id>/abschluss/` | `api_abschluss:919` | `api_abschluss` | Projektabschluss Daten |
| GET | `/matching/api/requests/<uuid:project_id>/kanban/` | `api_kanban:771` | `api_kanban` | Kanban Board für ein Projekt |
| POST | `/matching/api/match/<uuid:match_id>/placement/` | `api_placement_details:965` | `api_placement_details` | Vermittlungsdetails speichern |
| POST | `/matching/api/match/<uuid:match_id>/move/` | `api_kanban_move:831` | `api_kanban_move` | Kanban Karte verschieben |
| POST | `/matching/api/requests/<uuid:project_id>/close/` | `api_project_close:491` | `api_project_close` | Projekt abschließen |
| POST | `/matching/api/requests/<uuid:project_id>/archive/` | `api_project_archive:538` | `api_project_archive` | Projekt archivieren |
| GET | `/matching/api/match/<uuid:match_id>/` | `api_match_detail:455` | `api_match_detail` | Match-Details abrufen |
| POST | `/matching/api/match/<uuid:match_id>/status/` | `api_match_status:406` | `api_match_status` | Match-Status aktualisieren |
| POST | `/matching/api/match/<uuid:match_id>/call/` | `api_call:558` | `api_call` | Click-to-Call |
| POST | `/matching/api/crm/sync/<uuid:project_id>/` | `api_crm_sync:587` | `api_crm_sync` | CRM Sync für Projekt |
| GET | `/matching/api/crm/contacts/` | `api_crm_contacts:601` | `api_crm_contacts` | SuiteCRM Kontakte suchen |
| GET | `/matching/api/crm/accounts/` | `api_crm_accounts:647` | `api_crm_accounts` | SuiteCRM Accounts suchen |
| GET | `/matching/api/reporting/` | `api_reporting:680` | `api_reporting` | Reporting-Daten |
| GET | `/matching/api/settings/` | `api_settings_get:737` | `api_settings_get` | Matching-Settings lesen |
| POST | `/matching/api/settings/save/` | `api_settings_save:749` | `api_settings_save` | Matching-Settings speichern |
| GET | `/matching/api/schema/` | `as_view` | `` |  |
| GET | `/matching/api/docs/` | `as_view` | `` |  |
| GET | `/matching/api/redoc/` | `as_view` | `` |  |

### abpe_ki_wiz → `/ki-wizard/`
- Rolle: KI Anfrage-Extrakt, Wizard-Sessions, Firma-Web
- urls: `Repo_abpe/abpe_ki_wiz/incoming/urls.py`
- views/api: `Repo_abpe/abpe_ki_wiz/incoming/api.py`

| Methods | Path | View | Name | Summary |
|--------|------|------|------|---------|
| ? | `/ki-wizard/api/health/` | `as_view` | `` |  |
| ? | `/ki-wizard/api/wizards/` | `as_view` | `` |  |
| ? | `/ki-wizard/api/wizards/<str:wizard_id>/catalog/` | `as_view` | `` |  |
| ? | `/ki-wizard/api/prompts/` | `as_view` | `` |  |
| ? | `/ki-wizard/api/matching-anfrage/extract/` | `as_view` | `` |  |
| ? | `/ki-wizard/api/firma-web/enrich/` | `as_view` | `` |  |
| ? | `/ki-wizard/api/wizards/<str:wizard_id>/session/` | `as_view` | `` |  |
| ? | `/ki-wizard/api/session/<uuid:session_id>/` | `as_view` | `` |  |
| ? | `/ki-wizard/api/session/<uuid:session_id>/analyze/` | `as_view` | `` |  |
| ? | `/ki-wizard/api/session/<uuid:session_id>/clarify/` | `as_view` | `` |  |
| ? | `/ki-wizard/api/session/<uuid:session_id>/suggest-meta/` | `as_view` | `` |  |
| ? | `/ki-wizard/api/session/<uuid:session_id>/generate/` | `as_view` | `` |  |
| ? | `/ki-wizard/api/session/<uuid:session_id>/apply/` | `as_view` | `` |  |

### abpe_shaduler → `/shaduler/`
- Rolle: Aufgaben/Wiedervorlage, Matching-Terms, Shortlist-Reset, Request-Patch
- urls: `Repo_abpe/abpe_shaduler/incoming/urls.py`
- views/api: `Repo_abpe/abpe_shaduler/incoming/views.py`

| Methods | Path | View | Name | Summary |
|--------|------|------|------|---------|
| ? | `/shaduler/shaduler/` | `include` | `` |  |
| ? | `/shaduler/api/stats/` | `api_stats:62` | `api_stats` |  |
| ? | `/shaduler/api/aufgaben/` | `api_aufgaben_list:71` | `api_aufgaben_list` |  |
| POST? | `/shaduler/api/aufgaben/create/` | `api_aufgabe_create:92` | `api_aufgabe_create` |  |
| ? | `/shaduler/api/aufgaben/<uuid:pk>/` | `api_aufgabe_detail:117` | `api_aufgabe_detail` |  |
| ? | `/shaduler/api/aufgaben/<uuid:pk>/ergebnis/` | `api_aufgabe_ergebnis:137` | `api_aufgabe_ergebnis` |  |
| ? | `/shaduler/api/aufgaben/<uuid:pk>/snooze/` | `api_aufgabe_snooze:157` | `api_aufgabe_snooze` |  |
| ? | `/shaduler/api/aufgaben/<uuid:pk>/delegieren/` | `api_aufgabe_delegieren:167` | `api_aufgabe_delegieren` |  |
| ? | `/shaduler/api/aufgaben/ref/<str:typ>/<str:ref_id>/` | `api_aufgaben_fuer_ref:180` | `api_aufgaben_fuer_ref` |  |
| ? | `/shaduler/api/kalender/` | `api_kalender:192` | `api_kalender` |  |
| ? | `/shaduler/api/ergebnistypen/` | `api_ergebnistypen:211` | `api_ergebnistypen` |  |
| ? | `/shaduler/api/ki/vorschlag/` | `api_ki_vorschlag:237` | `api_ki_vorschlag` | Optionaler DeepSeek-Vorschlag zur aktuellen Aufgabe (kein Au |
| ? | `/shaduler/api/inbox/` | `api_inbox_list:256` | `api_inbox_list` |  |
| ? | `/shaduler/api/inbox/crm-lookup/` | `api_inbox_crm_lookup:324` | `api_inbox_crm_lookup` | Absender-E-Mail → CRM Kontakt/Firma (für Aufgabe-Dialog). |
| ? | `/shaduler/api/inbox/<str:mail_id>/view/` | `api_inbox_view:299` | `api_inbox_view` | Mail-Detail aus ES (Fallback wenn EDMS/IMAP 500). |
| ? | `/shaduler/api/inbox/<str:mail_id>/read/` | `api_inbox_mark_read:312` | `api_inbox_mark_read` |  |
| ? | `/shaduler/api/inbox/<str:mail_id>/aufgabe/` | `api_inbox_to_task:339` | `api_inbox_to_task` |  |
| ? | `/shaduler/api/inbox/<str:mail_id>/ack-send/` | `api_inbox_ack_send:366` | `api_inbox_ack_send` |  |
| ? | `/shaduler/api/radar/anfragen/` | `api_radar_items:496` | `api_radar_items` |  |
| ? | `/shaduler/api/radar/anfragen/refresh/` | `api_radar_refresh:591` | `api_radar_refresh` | Manueller Poll Freelancermap + Gulp. |
| ? | `/shaduler/api/radar/anfragen/<str:pk>/` | `api_radar_item_detail:549` | `api_radar_item_detail` |  |
| ? | `/shaduler/api/radar/anfragen/<str:pk>/uebernehmen/` | `api_radar_takeover:559` | `api_radar_takeover` | Interessant markieren (Matching-Vorbereitung). |
| ? | `/shaduler/api/radar/anfragen/<str:pk>/verwerfen/` | `api_radar_dismiss:570` | `api_radar_dismiss` | Archivieren / verwerfen. |
| ? | `/shaduler/api/radar/anfragen/<str:pk>/sperren/` | `api_radar_block:581` | `api_radar_block` |  |
| ? | `/shaduler/api/radar/gruppe/<uuid:pk>/trennen/` | `api_radar_group_split:611` | `api_radar_group_split` |  |
| ? | `/shaduler/api/radar/gruppe/<uuid:pk>/mergen/` | `api_radar_group_merge:621` | `api_radar_group_merge` | Manuell mergen: Body {item_ids: […]} — pk = bestehende Grupp |
| ? | `/shaduler/api/radar/berater/` | `api_radar_consultants:636` | `api_radar_consultants` |  |
| ? | `/shaduler/api/radar/berater/seed/` | `api_radar_berater_seed:700` | `api_radar_berater_seed` | CRM gulp_id_c → Radar + Soft-Delete + Reindex. |
| ? | `/shaduler/api/radar/berater/reindex/` | `api_radar_berater_reindex:820` | `api_radar_berater_reindex` | Manueller Index-Update: CRM-Sync + ES (wie 30-Min-Job). |
| ? | `/shaduler/api/radar/berater/gulp-aktualisieren/` | `api_radar_berater_gulp_refresh:718` | `api_radar_berater_gulp_refresh` |  |
| ? | `/shaduler/api/radar/berater/gulp-verfuegbar/` | `api_radar_berater_gulp_available:746` | `api_radar_berater_gulp_available` |  |
| ? | `/shaduler/api/radar/berater/fl-verfuegbar/` | `api_radar_berater_fl_available:788` | `api_radar_berater_fl_available` |  |
| ? | `/shaduler/api/radar/berater/<uuid:pk>/` | `api_radar_consultant_detail:672` | `api_radar_consultant_detail` |  |
| ? | `/shaduler/api/radar/berater/<uuid:pk>/bestaetigen/` | `api_radar_consultant_confirm:684` | `api_radar_consultant_confirm` |  |
| ? | `/shaduler/api/radar/berater/<uuid:pk>/verwerfen/` | `api_radar_consultant_dismiss:692` | `api_radar_consultant_dismiss` |  |
| ? | `/shaduler/api/radar/berater/einfuegen/` | `api_radar_paste:846` | `api_radar_paste` |  |
| ? | `/shaduler/api/matching/terms/<uuid:match_id>/` | `api_matching_terms:883` | `api_matching_terms` | Anfrage-spezifische Verfügbarkeit/Konditionen (MatchingBerat |
| ? | `/shaduler/api/regeln/` | `api_regeln:861` | `api_regeln` |  |
| ? | `/shaduler/api/webhook/<str:job_key>/` | `api_webhook_job:1319` | `api_webhook_job` |  |

## CRM E-Mail Pfade (Scan)

- `/crm/api/email/send/`
- `/crm/api/email/templates/`
- `/crm/api/emails/`
- `/crm/api/telefon/voicemail/`
- `/crm/email/compose/`
- `/crm/emails/`

## Frontend-Fetches (`mod-matching.js`)

- `/crm/api/account/`
- `/crm/api/berater/`
- `/crm/api/berater/?q=`
- `/crm/api/berater/new/`
- `/crm/api/contact/`
- `/crm/api/email/send/`
- `/crm/api/kunden/?q=`
- `/crm/api/kunden/new/`
- `/matching/api/crm/accounts/?q=`
- `/matching/api/crm/contacts/?q=`
- `/matching/api/firma-web/enrich/`
- `/matching/api/match/`
- `/matching/api/matches/`
- `/matching/api/matching-anfrage/extract/`
- `/matching/api/reporting/`
- `/matching/api/requests/`
- `/matching/api/requests/?archived=1&per_page=20`
- `/matching/api/requests/?page=1&per_page=20`
- `/matching/api/requests/?page=1&per_page=50`
- `/matching/api/requests/create/`
- `/matching/api/stats/`
- `/shaduler/api/aufgaben/create/`
- `/shaduler/api/inbox/`
- `/shaduler/api/matching/request/`
- `/shaduler/api/matching/shortlist/reset/`
- `/shaduler/api/matching/terms/`
- `/shaduler/api/radar/berater/einfuegen/`

## Empfohlene neue Endpoints (für Wizard)

| Method | Path | Zweck |
|--------|------|-------|
| POST | `/matching/api/match/<uuid>/deep-reason/` | DeepSeek: Warum match / Anschreiben / Reply-Chance |
| POST | `/matching/api/match/<uuid>/letter/draft/` | Persönliches Anschreiben (CV + Anfrage) |
| POST | `/matching/api/match/<uuid>/letter/polish/` | Text polieren, Stil behalten |
| POST | `/matching/api/match/<uuid>/outreach/complete/` | Send-Status + optionale Wiedervorlage in einem Rutsch |
