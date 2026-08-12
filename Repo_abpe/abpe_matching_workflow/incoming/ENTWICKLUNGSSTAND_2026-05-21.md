# ABpE Matching Workflow — Entwicklungs-Zusammenfassung 2026-05-21

## Ausgangslage
Django 5.x Portal (abpe_backend) auf ucs5.win.abcona.info
Bestehende Apps: cv_extractor (23.000+ Berater), abpe_email_studio, crm_bridge
Ziel: Vollständiges Matching-Workflow-Modul für Personalvermittlung

---

## 1. Infrastruktur & Bereinigung
- Alte Dummy-Apps (abe_matching, abpe_portal) deregistriert
- Neue App-Struktur: `apps/abpe_matching_workflow/`
- Static-Dateien konsolidiert nach `apps/abpe_ui/static/abpe_ui/`
- settings.json um Block "matching" erweitert (Scoring, LLM, CRM, Kanban)

---

## 2. Datenbank-Modelle (7 Tabellen)
| Model | Beschreibung |
|-------|-------------|
| ProjectRequest | Projektanfrage mit allen Feldern (Kunde, Skills, Budget, Standort, Laufzeit, open_positions) |
| ProjectConsultant | Berater im Workflow (Status, Score, Kontakthistorie, Vermittlungsdetails, Vertragseingang) |
| MatchResult | Matching-Ergebnisse mit Scores pro Dimension |
| EmailTemplate | 12 Email-Vorlagen für alle Workflow-Phasen |
| EmailHistory | Versandhistorie |
| ProjectContact | Kontakte pro Projekt |
| FollowupRule | Wiedervorlage-Regeln |

**WICHTIG:** Kein eigenes Consultant-Model — FK auf `apps.cv_extractor.Consultant`

---

## 3. Matching Engine (3-stufige Deduplizierung)

### Stage 1: ORM-Filter
- Alle Berater mit matching Skills aus cv_extractor
- Deduplizierung über `consultant_dir` (gleicher Dir = gleiche Person)
- Namensvettern: `kaiser_frank` vs `kaiser_frank_1` → verschiedene Personen
- Keine `-en` Versionen (DE bevorzugt)
- Tiebreaker 1: höchste AID-Versionsnummer (Major.Minor.Patch.Build)
- Tiebreaker 2: neuestes `created_at` Datum

### Stage 2: Python-Scoring (5 Dimensionen)
| Dimension | Gewicht |
|-----------|---------|
| Skills Required | 0.5 |
| Skills Nice-to-Have | 0.2 |
| Industrie | 0.15 |
| Erfahrung | 0.1 |
| Standort | 0.05 |

### Stage 3: AI Reranker (optional)
- Ollama qwen2.5:7b → Deepseek Fallback → regelbasiert

---

## 4. Services
| Service | Beschreibung |
|---------|-------------|
| matching_engine.py | Kernlogik, 3-stufige Dedup |
| matching_service.py | Orchestrierung Engine + Reranker |
| ai_reranker.py | LLM-Begründungen für Matches |
| crm_sync_service.py | SuiteCRM API (Opportunity create/update) |
| phone_service.py | Click-to-Call via Issabel/Asterisk webdial.cgi, User-spezifische Extension |
| followup_scheduler.py | Wiedervorlage-Tasks |
| availability_alert.py | Benachrichtigung wenn Berater wieder verfügbar |
| tasks.py | Celery Tasks (async Matching, CRM Sync, Alerts) |

---

## 5. Frontend — 8 Tabs

### Tab 1: Anfragen
- Liste aller Projekte mit Filter (Status, Suche)
- Pro Karte: Shortlist + Board + Abschluss Button
- Stats-Leiste: Offen / Angeschrieben / Im Gespräch / Vermittelt

### Tab 2: Neue Anfrage
- Formular: Kunde (CRM-Suche), Ansprechpartner, Anfrage-Text
- Ollama erkennt Skills automatisch aus dem Text
- Titel, Startdatum, Dauer, Standort, Stundensatz

### Tab 3: Shortlist
- Alle Match-Ergebnisse sortiert nach Score
- Schwellwert-Schieberegler (0.0 - 1.0)
- Checkboxen: manuell auswählen wer ins Board kommt
- Berater unter Schwellwert → ausgegraut als "Reserve"
- Anrufen / E-Mail / CV Buttons pro Eintrag

### Tab 4: Workflow-Board (Kanban)
- 7 Spalten: Shortlist → Angeschrieben → Interesse → Beim Kunden → Interview → Vermittelt → Absage
- HTML5 Drag & Drop zwischen Spalten
- Status-Update via API bei jedem Drag
- Zähler pro Spalte

### Tab 5: Projektabschluss
- Übersicht: X/Y Stellen besetzt (Fortschrittsbalken)
- Vermittelte Berater mit Toggle-Sektion:
  - Vereinbarter Stundensatz, Startdatum, Laufzeit
  - Vertragseingang vom Kunden: Checkbox, Datum, Kanal, Von wem, Notiz
- Projektabschluss: Grund + Notiz

### Tab 6: Archiv
- Abgeschlossene Projekte

### Tab 7: CRM & Kontakte
- Placeholder (Phase 2)

### Tab 8: Reporting
- Vermittlungsquote, Vermittlungen gesamt, Abgeschlossene Projekte

---

## 6. Email Templates (12 Stück)
| Nr | Typ | Beschreibung |
|----|-----|-------------|
| 10 | consultant_contact | Berater kontaktieren |
| 20 | consultant_followup | Berater Nachfrage |
| 25 | consultant_no_feedback | Nicht erreicht — Rückrufbitte |
| 30 | client_offer | Beratervorschlag an Kunde |
| 35 | client_followup | Kunde Nachfrage |
| 40 | consultant_rejection | Absage an Berater |
| 42 | consultant_rejection | Bulk-Absage nicht vermittelte Berater |
| 45 | consultant_unavailable | Berater nicht mehr verfügbar |
| 50 | placement_start | Projektstart Info an Berater |
| 55 | availability_alert | Berater wieder verfügbar |
| 60 | interview_request | Interview-Anfrage an Kunde |
| 65 | client_rejection | Absage an Kunde |

---

## 7. Telefon / Click-to-Call (Issabel/Asterisk)
- Browser-seitiger Aufruf via `window.open()` (wie Bookmarklet)
- Webdial URL: `http://172.20.3.120/cgi-bin/webdial.cgi`
- User-spezifische Settings in UserSettings DB:
  - Durchwahl, PIN, Anzeigename
  - Webdial URL, Context, Timeout, Intl. Prefix, Amtsvorwahl Prefix
- Einstellungen im Header-Modal → Telefon-Sektion
- Testanruf direkt aus den Einstellungen
- 8 neue Felder in UserSettings (Migration 0006 + 0007)

---

## 8. i18n (5 Sprachen)
- DE: vollständig (Basis)
- EN: vollständig
- ES/FR/IT: via Deepseek API übersetzt
- Alle Labels über `_t()` — kein hardcodierter Text
- languageChanged Handler in `{% block content %}` (Anhang A.17)

---

## 9. Wichtige Pfade
apps/abpe_matching_workflow/
├── models.py                    # 7 Modelle
├── views.py                     # 20+ API-Endpoints
├── urls.py
├── apps.py
├── signals.py
├── tasks.py
├── migrations/
│   ├── 0001_initial.py
│   ├── 0002_add_open_positions.py
│   └── 0003_add_client_contract_fields.py
├── fixtures/
│   └── email_templates.json     # 12 Templates gesichert
└── services/
├── matching_engine.py
├── matching_service.py
├── ai_reranker.py
├── crm_sync_service.py
├── phone_service.py
├── availability_alert.py
└── followup_scheduler.py
apps/abpe_ui/
├── models.py                    # UserSettings + Phone-Felder
├── templates/abpe_ui/
│   ├── components/header.html   # Phone Settings Modal
│   └── modules/matching/
│       └── module.json
└── static/abpe_ui/
├── css/mod/mod-matching.css
├── js/mod/mod-matching.js
└── i18n/{de,en,es,fr,it}/modules/matching/matching.json

---

## 10. Offene Punkte (Phase 2)
- [ ] Email Studio Integration (Berater anschreiben)
- [ ] Vertragsgenerator (PDF)
- [ ] CRM Sync (SuiteCRM8 API URL `candy` korrigieren)
- [ ] AI Reranker aktivieren (Ollama)
- [ ] Berater-Historie im CV-Editor
- [ ] Verfügbarkeits-Alert (Celery Beat)
- [ ] Reporting ausbauen
- [ ] Phone Multi-User (weitere User konfigurieren)

---

*Erstellt: 2026-05-21 | Entwicklung: Claude Sonnet + Angelo Malaguarnera*


###########################################################################################

╔══════════════════════════════════════════════════════════════════════════════╗
║   ABpE Matching Workflow — Entwicklungs-Zusammenfassung 2026-05-20/21       ║
╠══════════════════════════════════════════════════════════════════════════════╣

AUSGANGSLAGE
────────────
Django 5.x Portal (abpe_backend) auf ucs5.win.abcona.info
Bestehende Apps: cv_extractor (23.000+ Berater), abpe_email_studio, crm_bridge
Ziel: Vollständiges Matching-Workflow-Modul für Personalvermittlung

══════════════════════════════════════════════════════════════════════════════

1. INFRASTRUKTUR & BEREINIGUNG
────────────────────────────────
- Alte Dummy-Apps (abe_matching, abpe_portal) deregistriert
- Neue App-Struktur: apps/abpe_matching_workflow/
- Static-Dateien konsolidiert nach apps/abpe_ui/static/abpe_ui/
- settings.json um Block "matching" erweitert (Scoring, LLM, CRM, Kanban)

══════════════════════════════════════════════════════════════════════════════

2. DATENBANK-MODELLE (7 Tabellen)
───────────────────────────────────
- ProjectRequest    — Projektanfrage mit allen Feldern (Kunde, Skills, Budget,
                      Standort, Laufzeit, Abschlussfelder, open_positions)
- ProjectConsultant — Berater im Workflow (Status, Score, Kontakthistorie,
                      Vermittlungsdetails, Vertragseingang vom Kunden)
- MatchResult       — Matching-Ergebnisse mit Scores pro Dimension
- EmailTemplate     — 12 Email-Vorlagen für alle Workflow-Phasen
- EmailHistory      — Versandhistorie
- ProjectContact    — Kontakte pro Projekt
- FollowupRule      — Wiedervorlage-Regeln

WICHTIG: Kein eigenes Consultant-Model — FK auf apps.cv_extractor.Consultant

══════════════════════════════════════════════════════════════════════════════

3. MATCHING ENGINE (3-stufige Deduplizierung)
──────────────────────────────────────────────
- Stage 1: ORM-Filter — alle Berater mit matching Skills aus cv_extractor
  → Deduplizierung über consultant_dir (gleicher Dir = gleiche Person)
  → Namensvettern: kaiser_frank vs kaiser_frank_1 → verschiedene Personen
  → Keine -en Versionen (DE bevorzugt)
  → Tiebreaker 1: höchste AID-Versionsnummer (Major.Minor.Patch.Build)
  → Tiebreaker 2: neuestes created_at Datum
- Stage 2: Python-Scoring — 5 Dimensionen:
  - Skills Required (Gewicht 0.5)
  - Skills Nice-to-Have (0.2)
  - Industrie (0.15)
  - Erfahrung (0.1)
  - Standort (0.05)
- Stage 3: AI Reranker (optional) — Ollama qwen2.5:7b → Deepseek Fallback

══════════════════════════════════════════════════════════════════════════════

4. SERVICES
────────────
- matching_engine.py    — Kernlogik, 3-stufige Dedup
- matching_service.py   — Orchestrierung Engine + Reranker
- ai_reranker.py        — LLM-Begründungen für Matches
- crm_sync_service.py   — SuiteCRM API (Opportunity create/update)
- phone_service.py      — Click-to-Call via Issabel/Asterisk webdial.cgi
                          User-spezifische Extension aus UserSettings
- followup_scheduler.py — Wiedervorlage-Tasks
- availability_alert.py — Benachrichtigung wenn Berater wieder verfügbar
- tasks.py              — Celery Tasks (async Matching, CRM Sync, Alerts)

══════════════════════════════════════════════════════════════════════════════

5. PORTAL-INTEGRATION
──────────────────────
- module.json → Sidebar-Icon (diagram-3), Order 25
- base.html: extends abpe_ui/base.html, MATCHING_CONFIG Bridge,
             languageChanged Handler in {% block content %} (A.17 Fix)
- i18n: DE/EN/ES/FR/IT vollständig (via Deepseek API übersetzt)

══════════════════════════════════════════════════════════════════════════════

6. FRONTEND — 8 TABS
─────────────────────
TAB 1: ANFRAGEN
  • Liste aller Projekte mit Filter (Status, Suche)
  • Pro Karte: Shortlist + Board + Abschluss Button
  • Stats-Leiste: Offen / Angeschrieben / Im Gespräch / Vermittelt

TAB 2: NEUE ANFRAGE
  • Formular: Kunde (CRM-Suche), Ansprechpartner, Anfrage-Text
  • Ollama erkennt Skills automatisch aus dem Text
  • Titel, Startdatum, Dauer, Standort, Stundensatz

TAB 3: SHORTLIST
  • Alle Match-Ergebnisse sortiert nach Score
  • Schwellwert-Schieberegler (0.0 - 1.0)
  • Checkboxen: manuell auswählen wer ins Board kommt
  • Score-Balken, Begründungen (AI Reranker)
  • Berater unter Schwellwert → ausgegraut als "Reserve"
  • Anrufen / E-Mail / CV Buttons pro Eintrag

TAB 4: WORKFLOW-BOARD (Kanban)
  • 7 Spalten: Shortlist → Angeschrieben → Interesse →
               Beim Kunden → Interview → Vermittelt → Absage
  • HTML5 Drag & Drop zwischen Spalten
  • Status-Update via API bei jedem Drag
  • Berater-Karten mit Score, Tage seit Kontakt, Nachfassen-Alert
  • Zähler pro Spalte, leere Spalten werden angezeigt

TAB 5: PROJEKTABSCHLUSS
  • Übersicht: X/Y Stellen besetzt (Fortschrittsbalken)
  • Vermittelte Berater mit Toggle-Sektion:
    - Vereinbarter Stundensatz, Startdatum, Laufzeit
    - Vermittelt am, Bemerkungen
    - Vertragseingang vom Kunden: Checkbox, Datum (optional),
      Kanal (Email/Post/Fax/Portal), Von wem (optional), Notiz
  • Offene Stellen mit Link zurück zur Shortlist
  • Projektabschluss: Grund (Vollständig/Teilweise/Storniert/Nicht vermittelt)
  • Vertrag senden + Projektstart Mail (Phase 2)

TAB 6: ARCHIV
  • Abgeschlossene Projekte mit Toggle-Details

TAB 7: CRM & KONTAKTE
  • Placeholder (Phase 2)

TAB 8: REPORTING
  • Vermittlungsquote, Vermittlungen gesamt, Abgeschlossene Projekte

══════════════════════════════════════════════════════════════════════════════

7. EMAIL TEMPLATES (12 Stück in DB + Fixture)
───────────────────────────────────────────────
10  consultant_contact        — Berater kontaktieren
20  consultant_followup       — Berater Nachfrage (mit {projekt_gesendet_zeit})
25  consultant_no_feedback    — Nicht erreicht — Rückrufbitte
30  client_offer              — Beratervorschlag an Kunde
35  client_followup           — Kunde Nachfrage
40  consultant_rejection      — Absage an Berater
42  consultant_rejection      — Bulk-Absage nicht vermittelte Berater
45  consultant_unavailable    — Berater nicht mehr verfügbar
50  placement_start           — Projektstart Info an Berater
55  availability_alert        — Berater wieder verfügbar
60  interview_request         — Interview-Anfrage an Kunde
65  client_rejection          — Absage an Kunde

══════════════════════════════════════════════════════════════════════════════

8. TELEFON / CLICK-TO-CALL
────────────────────────────
- Issabel/Asterisk webdial.cgi Integration
- Browser-seitiger Aufruf via window.open() (wie Bookmarklet)
- User-spezifische Settings in UserSettings DB:
  - Durchwahl, PIN, Anzeigename
  - Webdial URL (default: http://172.20.3.120/cgi-bin/webdial.cgi)
  - Context (from-internal), Timeout (10s)
  - Intl. Prefix (00 statt +), Amtsvorwahl Prefix
- Einstellungen im Header-Modal (Zahnrad) → Telefon-Sektion
- Testanruf direkt aus den Einstellungen
- Anrufen-Button in Shortlist und Kanban-Board
- Migration: 8 neue Felder in UserSettings

══════════════════════════════════════════════════════════════════════════════

9. i18n (5 Sprachen)
─────────────────────
- Alle Labels über _t() — kein einziger hardcodierter Text
- DE: vollständig (Basis)
- EN: vollständig
- ES/FR/IT: via Deepseek API übersetzt
- Sprachwechsel: alle Tab-Inhalte werden neu gerendert
- languageChanged Handler in {% block content %} (A.17 aus Doku)

══════════════════════════════════════════════════════════════════════════════

10. TECHNISCHE HIGHLIGHTS
──────────────────────────
- 3-stufige Berater-Deduplizierung via consultant_dir + AID-Version + Timestamp
- Lazy Tab-Loading (erst beim Klick, nicht beim Init)
- i18n-Ready Guard (wartet auf loadLanguage() bevor Tabs gerendert werden)
- Auto-Projekt-Load (letztes Projekt wird automatisch geladen)
- Kanban Drag & Drop mit sofortigem DB-Update
- Projektabschluss mit mehreren vermittelten Beratern (open_positions)

══════════════════════════════════════════════════════════════════════════════

OFFENE PUNKTE (Phase 2)
────────────────────────
- Email Studio Integration (Berater anschreiben)
- Vertragsgenerator (PDF)
- CRM Sync (SuiteCRM8 API URL korrigieren)
- AI Reranker aktivieren (Ollama)
- Berater-Historie im CV-Editor
- Verfügbarkeits-Alert (Celery Beat)
- Reporting ausbauen

══════════════════════════════════════════════════════════════════════════════
DATEIEN GESICHERT:
  apps/abpe_ui/archive/2026-05-20/
  apps/abpe_matching_workflow/fixtures/email_templates.json
  Migration 0001_initial, 0002_add_open_positions,
  0003_add_client_contract_fields, 0006_add_phone_settings,
  0007_add_phone_webdial_fields
╚══════════════════════════════════════════════════════════════════════════════╝
