# ABpE Matching Workflow — Vollständige Verzeichnisstruktur
# Angelehnt an: abpe_email_studio + abpe_ui Modul-Muster
# Stand: 2026-05-20

## PRINZIP
# Eigene Django App:  apps/abpe_matching_workflow/   (Business-Logik, Models, APIs)
# Portal-Modul:       apps/abpe_ui/templates/abpe_ui/modules/matching/   (nur module.json)
# Static Files:       apps/abpe_ui/static/abpe_ui/   (CSS + JS im Portal-Static-Tree)
# i18n:               apps/abpe_ui/static/abpe_ui/i18n/{lang}/modules/matching/

═══════════════════════════════════════════════════════════════════════
 DJANGO APP — apps/abpe_matching_workflow/
═══════════════════════════════════════════════════════════════════════

apps/abpe_matching_workflow/
├── __init__.py
├── apps.py                          # AppConfig: name = 'apps.abpe_matching_workflow'
├── admin.py                         # Django Admin Registrierungen
│
├── models/                          # Aufgeteilt nach Domäne (statt 1 riesige models.py)
│   ├── __init__.py                  # importiert alle Models
│   ├── project_request.py           # ProjectRequest (erweitert bestehend + CRM-Felder)
│   ├── project_contact.py           # ProjectContact (NEU: mehrere AP pro Projekt)
│   ├── project_consultant.py        # ProjectConsultant (erweitert + consultant_cv FK)
│   ├── followup_rule.py             # FollowupRule (NEU: Wiedervorlage-Regeln)
│   ├── match_result.py              # MatchResult (Score, LLM-Begründung)
│   ├── email_template.py            # EmailTemplate (bestehend)
│   └── email_history.py             # EmailHistory (bestehend + erweitert)
│
├── migrations/
│   ├── __init__.py
│   ├── 0001_initial.py              # bestehende Migration (ProjectRequest etc.)
│   └── 0002_matching_workflow_v2.py # NEU: consultant_cv FK, CRM-Felder, ProjectContact,
│                                    #      FollowupRule, match_reason, crm_ids
│
├── services/
│   ├── __init__.py
│   ├── matching_engine.py           # UMBAU: direkt gegen cv_extractor DB
│   │                                #   Stufe 1: ORM-Filter (status, skills, location)
│   │                                #   Stufe 2: Python-Scoring (gewichtet)
│   │                                #   Stufe 3: Synonym-Erweiterung via SkillRelation
│   ├── ai_reranker.py               # NEU: Ollama/Deepseek LLM-Begründung pro Berater
│   ├── ollama_matcher.py            # bestehend: Projektanalyse, E-Mail-Generierung
│   ├── matching_service.py          # UMBAU: orchestriert Engine + Reranker
│   ├── email_service.py             # bestehend: E-Mail-Versand via IMAP/IONOS
│   ├── crm_sync_service.py          # NEU: SuiteCRM bidirektionaler Sync
│   │                                #   ProjectRequest → opportunities
│   │                                #   ProjectContact → contacts (via accounts_contacts)
│   │                                #   E-Mails → emails + emails_beans
│   │                                #   Status-Updates → calls/meetings/notes
│   ├── followup_scheduler.py        # NEU: Wiedervorlage-Tasks via abpe_scheduler/Celery
│   ├── phone_service.py             # NEU: Click-to-Call → webdial.cgi HTTP-GET
│   │                                #   + SuiteCRM calls-Aktivität schreiben
│   └── availability_alert.py       # NEU: Scheduler prüft Berater-Verfügbarkeit
│                                    #   gegen archivierte Projekte → Alert generieren
│
├── tasks.py                         # Celery Tasks:
│                                    #   run_matching_async(project_id)
│                                    #   send_followup_reminders()
│                                    #   check_availability_alerts()
│                                    #   sync_crm_batch()
│
├── signals.py                       # Django Signals:
│                                    #   post_save ProjectRequest → Celery Task
│                                    #   post_save ProjectConsultant → CRM Sync
│
├── views.py                         # Django Views (alle Tabs als JSON-APIs)
│                                    #   + Template-Render für Portal-Frame
│
├── urls.py                          # URL-Patterns
│
├── serializers.py                   # DRF Serializers (für API-Responses)
│
├── templates/
│   └── matching/                    # Eigene Templates (wie email_studio)
│       ├── base.html                # {% extends 'abpe_ui/base.html' %}
│       ├── index.html               # Haupt-View (lädt alle Tabs via JS)
│       ├── anfragen.html            # Tab 1: Anfragenliste
│       ├── shortlist.html           # Tab 3: Shortlist & Matching
│       ├── kanban.html              # Tab 4: Workflow-Board
│       ├── abschluss.html           # Tab 5: Projektabschluss
│       ├── archiv.html              # Tab 6: Archiv
│       ├── crm.html                 # Tab 7: CRM & Kontakte
│       └── reporting.html           # Tab 8: Reporting
│
├── static/
│   └── matching/                    # App-eigene Static Files (NICHT in abpe_ui)
│       ├── css/
│       │   └── matching-components.css   # Kanban-Board, Shortlist-spezifische Styles
│       └── js/
│           └── matching-core.js          # Tab-Logik, Slider, Kanban Drag&Drop
│
├── management/
│   ├── __init__.py
│   └── commands/
│       ├── __init__.py
│       ├── run_matching.py          # python manage.py run_matching --project ANF-2026-0042
│       ├── sync_crm.py              # python manage.py sync_crm --full
│       └── check_availability.py   # python manage.py check_availability
│
└── fixtures/
    └── email_templates.json         # Initiale E-Mail-Vorlagen (Berater, Absage, Angebot)


═══════════════════════════════════════════════════════════════════════
 PORTAL-MODUL — apps/abpe_ui/templates/abpe_ui/modules/matching/
═══════════════════════════════════════════════════════════════════════
# NUR module.json — kein HTML hier (wie email_studio)
# ModuleScanner erkennt es → Sidebar-Eintrag

apps/abpe_ui/templates/abpe_ui/modules/matching/
└── module.json
    # {
    #   "id": "matching",
    #   "title": "Matching",
    #   "titles": {"de": "Matching", "en": "Matching", ...},
    #   "icon": "diagram-3",
    #   "route": "/matching/",
    #   "order": 25,
    #   "enabled": true,
    #   "roles": ["!berater"],
    #   "static": {
    #     "css": ["mod/mod-matching.css"],
    #     "js":  ["mod/mod-matching.js"]
    #   }
    # }


═══════════════════════════════════════════════════════════════════════
 PORTAL STATIC — apps/abpe_ui/static/abpe_ui/
═══════════════════════════════════════════════════════════════════════
# Im Portal-Static-Tree (wie alle anderen Module)
# collectstatic holt es von hier

apps/abpe_ui/static/abpe_ui/
├── css/
│   └── mod/
│       └── mod-matching.css         # NEU: Portal-Styles für Matching
│                                    #   Shortlist-Karten, Score-Bars,
│                                    #   Schwellwert-Trenner, Kanban-Spalten
└── js/
    └── mod/
        └── mod-matching.js          # NEU: Tab-Switching, Slider-Logik,
                                     #   Kanban-Drag&Drop, API-Calls,
                                     #   languageChanged Handler (in {% block content %})


═══════════════════════════════════════════════════════════════════════
 i18n — apps/abpe_ui/static/abpe_ui/i18n/
═══════════════════════════════════════════════════════════════════════
# Pro Sprache ein Unterverzeichnis mit manifest.json (neue Struktur)

apps/abpe_ui/static/abpe_ui/i18n/
├── de/modules/matching/
│   ├── manifest.json                # {"files": ["matching.json", "matching_help.json"]}
│   ├── matching.json                # {"matching": {"tab_anfragen": "Anfragen", ...}}
│   └── matching_help.json           # Hilfe-Texte für Help-Modal
├── en/modules/matching/
│   ├── manifest.json
│   ├── matching.json
│   └── matching_help.json
├── es/modules/matching/
│   ├── manifest.json
│   ├── matching.json
│   └── matching_help.json
├── fr/modules/matching/
│   ├── manifest.json
│   ├── matching.json
│   └── matching_help.json
└── it/modules/matching/
    ├── manifest.json
    ├── matching.json
    └── matching_help.json


═══════════════════════════════════════════════════════════════════════
 URL-EINBINDUNG — abpe_backend/urls.py
═══════════════════════════════════════════════════════════════════════

# In abpe_backend/urls.py:
# path('matching/', include('apps.abpe_matching_workflow.urls')),

# In apps/abpe_matching_workflow/urls.py:
# app_name = 'abpe_matching_workflow'
# path('')                                → index (Portal-Frame)
# path('api/requests/')                   → Anfragen-Liste JSON
# path('api/requests/<uuid>/')            → Anfrage-Detail
# path('api/requests/<uuid>/match/')      → Matching starten (async)
# path('api/requests/<uuid>/shortlist/')  → Shortlist abrufen
# path('api/requests/<uuid>/close/')      → Projektabschluss
# path('api/requests/<uuid>/archive/')    → Archivieren
# path('api/match/<uuid>/status/')        → ProjectConsultant Status-Update
# path('api/match/<uuid>/email/')         → E-Mail senden
# path('api/match/<uuid>/call/')          → Click-to-Call
# path('api/contacts/search/')            → SuiteCRM Kontakt-Suche
# path('api/crm/sync/')                   → CRM Sync manuell
# path('api/reporting/')                  → Reporting-Daten


═══════════════════════════════════════════════════════════════════════
 DATENBANK-MODELLE — Übersicht neue Felder
═══════════════════════════════════════════════════════════════════════

ProjectRequest (ERWEITERT):
  + crm_account_id       CharField(36)   → SuiteCRM accounts.id
  + crm_contact_id       CharField(36)   → SuiteCRM contacts.id (Haupt-AP)
  + crm_opportunity_id   CharField(36)   → SuiteCRM opportunities.id
  + crm_synced_at        DateTimeField   → letzter Sync
  + source_document      FileField       → PDF/TXT Upload
  + is_archived          BooleanField    → Archiv-Flag
  + close_reason         CharField       → Abschlussgrund
  + close_note           TextField       → Interne Notiz
  + placed_consultant    FK(cv_extractor.Consultant) → wer wurde platziert
  + placed_at            DateTimeField
  + placed_rate          IntegerField    → vereinbarter Stundensatz
  + placed_start         DateField       → erster Arbeitstag
  + placed_end           DateField       → Vertragsende
  + placed_notes         TextField       → Infos zum ersten Tag

ProjectContact (NEU):
  + project              FK(ProjectRequest)
  + crm_contact_id       CharField(36)   → SuiteCRM contacts.id
  + first_name           CharField
  + last_name            CharField
  + email                EmailField
  + phone                CharField
  + role                 CharField       → entscheider/fachverantw/sachbearbeiter/cc
  + personal_note        TextField       → "Nur vormittags, bevorzugt Telefon"
  + followup_rule        FK(FollowupRule) null=True

ProjectConsultant (ERWEITERT):
  + consultant_cv        FK(cv_extractor.Consultant)  → direkte Verknüpfung
  + match_reason         TextField       → LLM-Begründung
  + crm_email_id         CharField(36)   → SuiteCRM emails.id
  + email_studio_id      IntegerField    → Email Studio Nachricht
  + unavailable_at       DateTimeField   → wann wurde Nicht-Verfügbarkeit gemeldet
  + unavailable_note     TextField

FollowupRule (NEU):
  + name                 CharField       → "Standard", "Nur VM", "Teams-bevorzugt"
  + available_from       TimeField       → 08:00
  + available_until      TimeField       → 12:00
  + preferred_channel    CharField       → phone/email/teams/personal
  + followup_delay_hours IntegerField    → 2 (nach 2 Stunden nachfassen)
  + auto_email_on_no_reach BooleanField  → automatische E-Mail wenn nicht erreicht
  + reminder_days        JSONField       → [1, 3, 7] (nach 1, 3, 7 Tagen erneut)
  + is_default           BooleanField

MatchResult (NEU — trennt Scoring von ProjectConsultant):
  + project_request      FK(ProjectRequest)
  + consultant_cv        FK(cv_extractor.Consultant)
  + overall_score        FloatField      → 0.0–1.0
  + skill_score          FloatField
  + industry_score       FloatField
  + experience_score     FloatField
  + location_score       FloatField
  + matched_skills       JSONField       → ["SAP S/4HANA", "ABAP"]
  + missing_skills       JSONField       → ["Fiori"]
  + match_reason         TextField       → LLM-generierte Begründung
  + match_reason_lang    CharField       → 'de'
  + calculated_at        DateTimeField
  + calculated_by        CharField       → 'ollama:qwen2.5:7b' / 'deepseek'


═══════════════════════════════════════════════════════════════════════
 SETTINGS — abpe_backend/settings/apps.py
═══════════════════════════════════════════════════════════════════════

# abpe_matching_workflow ist bereits eingetragen — keine Änderung nötig
# 'apps.abpe_matching_workflow'  ← schon vorhanden


═══════════════════════════════════════════════════════════════════════
 REPORTING — Reiter 8 (Datenquellen)
═══════════════════════════════════════════════════════════════════════

Queries gegen abpe_matching_workflow DB:
  - Vermittlungsquote:  placed / total × 100  (pro Monat/Quartal/Jahr)
  - Ø Zeit Anfrage→Platzierung: placed_at - created_at
  - Top-Berater:  ProjectConsultant.objects.annotate(placed=Count).order_by
  - Top-Kunden:   ProjectRequest.objects.values('customer_name').annotate(count=Count)
  - Absagegründe: ProjectRequest.objects.values('close_reason').annotate(count=Count)
  - Reaktionszeit Berater: consultant_response_at - contacted_at  (Ø)

Queries gegen cv_extractor DB (read-only):
  - Meistgesuchte Skills: gegen MatchResult.matched_skills JSONField
  - Skill-Lücken: MatchResult.missing_skills aggregiert
  - Berater-Auslastung: placed_consultant Häufigkeit


═══════════════════════════════════════════════════════════════════════
 CHECKLISTE VOR IMPLEMENTIERUNG
═══════════════════════════════════════════════════════════════════════

[ ] Migration 0002 schreiben (neue Felder)
[ ] python manage.py makemigrations abpe_matching_workflow
[ ] python manage.py migrate
[ ] module.json anlegen → ModuleScanner erkennt es
[ ] mod-matching.css anlegen (minimal, kein margin-left:0 !important !)
[ ] mod-matching.js anlegen (languageChanged in {% block content %} !)
[ ] i18n/de/modules/matching/manifest.json + matching.json
[ ] i18n für en/es/fr/it (i18n_translator.py nutzen)
[ ] abpe_backend/urls.py: path('matching/', include(...))
[ ] python manage.py collectstatic --noinput
[ ] supervisorctl restart abpe-django
[ ] python manage.py check  → 0 issues

