# ABpE — Architektur-Zielvorlage `apps/abpe_shaduler`

**Frozen Low-Level-Design · Stand 04.08.2026 · Ablage: `apps/abpe_shaduler/Architektur_zielvorlage.md`**
Basiert auf den vier finalen Zielbildern (Scheduler, Matching-Differenz, Composer/Studios, Radar)
und dem Final-Mockup. Änderungen an diesem Dokument nur bewusst und versioniert.

---

## 0. Einordnung & Naming

- Modulname: **`abpe_shaduler`** — bewusst NICHT `abpe_scheduler` (existiert bereits
  als Cron-Job-Runner mit SchedulerJob/SchedulerJobRun und bleibt unangetastet).
  **Befund 04.08.2026:** `abpe_scheduler` ist aktiv und wird gebraucht — er ist
  der Zeitauslöser der MeetMe-Erinnerungen (Payload `delivery_id` →
  MeetmeReminderDelivery; einziger Nutzer: `abpe_meetme/scheduler_client.py`;
  `scheduler_loop --interval=5` läuft als Prozess, Läufe SUCCESS).
  **Konsequenz:** Die vier Shaduler-Beat-Tasks (Kap. 4) werden NICHT über
  Celery Beat konfiguriert, sondern als wiederkehrende `SchedulerJob`-Einträge
  über denselben `scheduler_client`-Weg registriert (recurrence.py) —
  ein Taktgeber im System statt zwei.
- Sidebar: Icon `check2-square`, Titel "Aufgaben", Order 24 (vor Matching 25).
- Sechs Reiter: **Aufgaben · Kalender · Posteingang · Radar Anfragen · Radar Berater · Regeln**
- Rollen: `!berater` (wie Matching — Berater-Gruppe sieht das Modul nicht).
- Schwestermodul (separate App, eigene Etappe): **`apps/abpe_composer`** — wird hier
  als Schnittstelle referenziert (Kap. 6).

## 1. Verzeichnisstruktur (Soll)

```
apps/abpe_shaduler/
├── __init__.py
├── apps.py                      # AppConfig, ready(): signals registrieren
├── models.py                    # 10 Modelle (Kap. 2)
├── admin.py                     # Alle Modelle im Django-Admin (Kap. 2.11)
├── views.py                     # Portal-View + JSON-APIs (Kap. 3)
├── urls.py                      # Routes + Spectacular Schema (Kap. 4)
├── signals.py                   # Receiver auf ProjectConsultant.post_save u.a.
├── tasks.py                     # Celery: radar_poll, prozess_engine_tick, inbox_poll
├── Architektur_zielvorlage.md   # DIESES Dokument
├── fixtures/
│   ├── ergebnis_typen.json      # Ergebnis-Katalog (aus ergebnis-katalog-entwurf.md)
│   └── prozess_regeln_default.json
├── management/
│   └── commands/
│       ├── seed_shaduler.py     # Fixtures laden + Defaults prüfen
│       └── radar_run_once.py    # Radar manuell anstoßen (Debug)
├── migrations/
│   └── 0001_initial.py          # alle 10 Tabellen
├── services/
│   ├── __init__.py
│   ├── aufgaben_service.py      # Fassade: erstellen(), erledigen(), fuer_ref(), badge()
│   ├── ergebnis_service.py      # Ergebnis anwenden → 3 Wirkungen (Status/Folge/Historie)
│   ├── aktivitaet_service.py    # Aktivitaet.schreiben() — von ALLEN Modulen aufrufbar
│   ├── prozess_engine.py        # ProzessRegel/Schritte ausführen (Trigger + Ketten)
│   ├── kalender_service.py      # Aggregation Tag/Woche/Monat/Jahr
│   ├── inbox_service.py         # IMAP-Leseüberblick (nutzt ingest_email-Konfig)
│   ├── radar_fetcher.py         # RSS- + HTML-Poller, Mail-Alert-Parser
│   ├── radar_grouper.py         # Ähnlichkeits-Clustering (Embedding/Fuzzy)
│   ├── radar_matcher.py         # Quick-Score via MatchingEngine, Berater-Abgleich
│   └── whatsapp_service.py      # build_whatsapp_link() — Übergangslösung bis Composer
└── templates/
    └── shaduler/
        ├── index.html           # extends abpe_ui/base.html, Reiter-Gerüst, Lazy-Load
        └── tabs/
            ├── aufgaben.html
            ├── kalender.html
            ├── posteingang.html
            ├── radar_anfragen.html
            ├── radar_berater.html
            └── regeln.html

apps/abpe_ui/  (Frontend-Anteile — Portal-Konvention)
├── templates/abpe_ui/modules/shaduler/module.json
└── static/abpe_ui/
    ├── css/mod/mod-shaduler.css
    ├── js/mod/mod-shaduler.js
    ├── js/mod/mod-shaduler-kalender.js
    └── i18n/{ar,de,en,es,fr,hu,it,ja,ko,nl,pl,pt,ru,tr,zh}/modules/shaduler/
        ├── shaduler.json
        └── manifest.json
```

## 2. models.py — 10 Modelle

Alle IDs UUID (Muster matching_workflow), `created_at/updated_at`, deutsche
verbose_names, Indizes wie angegeben. JSONField ist Projektstandard.

### 2.1 `Aufgabe`
| Feld | Typ | Bemerkung |
|---|---|---|
| id | UUID PK | |
| art | Char(20) choices | `anruf, termin, email, sms_messenger, dokument, post, wiedervorlage, intern` |
| kanal | Char(20) choices, blank | nur bei termin: `meetme, teams, jitsi, vor_ort, interview`; bei sms_messenger: `sms, whatsapp, xing, linkedin` |
| titel | Char(200) | Headline der Queue |
| beschreibung | Text blank | |
| faellig_am | DateField db_index | |
| faellig_zeit | TimeField null | optional |
| prioritaet | Int default 3 | 1 hoch … 5 niedrig |
| status | Char(15) choices db_index | `offen, erledigt, verworfen, delegiert` |
| zugewiesen_an | FK auth.User **PROTECT** | db_index; bei User-Löschung erst delegieren |
| ref_type | Char(20) blank db_index | `match, anfrage, berater, firma, ansprechpartner, mail, radar_item` |
| ref_id | Char(64) blank db_index | UUID/PK als String (modulübergreifend) |
| quelle | Char(15) choices | `regel, status, manuell, ki, radar, mail` |
| regel | FK ProzessRegel null | welche Regel hat erzeugt |
| ergebnis | FK ErgebnisTyp null | gewähltes Ergebnis |
| ergebnis_daten | JSONField default dict | Eingabefelder (Preis, Datum, Grund …) |
| erledigt_am / erledigt_von | DateTime null / FK User null | |
| parent | FK self null | Aufgabenketten |
| gruppe_id | UUID null db_index | Massenaktionen (n Aufgaben, 1 Gruppe) |
| Meta | | Indexe: (status, faellig_am), (zugewiesen_an, status), (ref_type, ref_id) |

### 2.2 `Aktivitaet` (Historie-Strom, ab Tag 1 geschrieben)
zeitpunkt (DateTime db_index, default=now) · medium (Char: telefon, email, whatsapp, sms,
dokument, post, termin, system, radar) · titel (Char 250) · ref_type/ref_id
(db_index) · deeplink_url (Char 500) · user (FK null) · details (JSON blank).
Schreibzugriff NUR über `aktivitaet_service.schreiben()` (eine Zeile pro Modul-Hook).

### 2.3 `ErgebnisTyp` (Ergebnis-Katalog als DB — Entscheidung)
code (Char 40 unique) · label (Char 100) · label_i18n_key (Char 60) ·
kontext (Char 30: berater_ansprache, berater_nachfassen, kunde_angebot,
vertrag, bestandspflege, berater_initiativ, wiedervorlage, intern, termin,
inbox) · wirkung_status (Char 30 blank → ProjectConsultant/ProjectRequest-Status) ·
wirkung_regel (FK ProzessRegel null → Folgekette) · eingabefelder (JSON:
[{name,label,typ}] ) · zeigt_dialog (Bool) · schliesst_vorgang (Bool) ·
sort_order · aktiv. **Seed aus fixtures/ergebnis_typen.json.**

### 2.4 `ProzessRegel` (wizard-ready)
name · beschreibung · aktiv · ausloeser_typ (Char: status_wechsel, ergebnis,
zeit_ohne_reaktion, radar_score, manuell) · ausloeser_wert (Char 60) ·
bedingung (JSON blank) · followup_rule (FK matching_workflow.FollowupRule
null — Erreichbarkeit/Kanal wiederverwenden) · erstellt_von (Char: user, ki_wizard).

### 2.5 `ProzessSchritt`
regel (FK, related_name='schritte') · reihenfolge (Int) · aktion_art (Char:
aufgabe_erzeugen, email_senden, whatsapp_vorbereiten, status_setzen, warten) ·
parameter (JSON) · frist_offset (Char 10: `+5d`, `-4w`) · abbruch_bei (Char 30 blank).
Unique together (regel, reihenfolge).

### 2.6 `RadarSource`
name · typ (Char: rss, email_alert, html_public, manuell) · url (Char 500 blank) ·
query (Char 200 blank) · ziel (Char: anfragen, berater) · intervall_min (Int 5) ·
aktiv · letzter_lauf (DateTime null) · letzter_status (Char blank).

### 2.7 `RadarItem` (Anfragen)
quelle (FK RadarSource) · external_url (Char 600) · dedup_hash (Char 64
db_index) · gruppe (FK RadarItemGroup null) · headline (Char 250) ·
beschreibung (Text) · skills (JSON list) · eckdaten (JSON: start, ort, satz,
dauer, firma) · quick_score (Float null) · top_berater (JSON list) · status
(Char: neu, interessant, uebernommen, verworfen, gesperrt) db_index ·
project_request (FK matching_workflow.ProjectRequest null) · eingegangen_am.
Sortierung: Manager `order_by_score()` = `F(quick_score).desc(nulls_last=True)`,
dann `-eingegangen_am` (Meta.ordering allein würde in Postgres NULLs zuerst setzen).

### 2.8 `RadarItemGroup`
merkmal_hash (Char 64) · titel_norm (Char 250) · anbieter_anzahl (Int, denorm) ·
erstellt_am. Items zeigen per FK hierauf; Trennen/Mergen = FK umsetzen.

### 2.9 `RadarConsultantItem` (Berater-Radar)
quelle (FK) · profil_url (Char 600) · dedup_hash · name (Char blank — oft anonym) ·
skills (JSON) · verfuegbar_ab (Date null) · satz (Decimal null) · ort (Char) ·
match_status (Char: bekannt, unsicher, unbekannt) db_index · consultant
(FK cv_extractor.Consultant null) · match_confidence (Float) · vorschlag
(JSON: vermuteter Berater + Gründe) · auto_update_log (JSON list:
{feld, alt, neu, quelle, zeit}) · status (neu, bestaetigt, beobachten, verworfen).

### 2.10 `Sperrliste`
firma_name (Char 200) · firma_name_norm (Char 200 db_index — via
`services.firma_normalizer.normalize_firma_name` in `save()`; GmbH/AG/Interpunktion
strippen) · crm_account_id (Char 36 blank db_index — SuiteCRM-UUID, **kein**
Django-FK auf `abpe_crm.CrmAccount`; Matching-Muster wie
`ProjectConsultant.crm_email_id`) · richtung (Char:
die_nicht_mit_uns, wir_nicht_mit_denen, beide) · grund (Text) · seit (Date) ·
angelegt_von (FK User **PROTECT**) · aktiv.

### 2.11 admin.py
Alle 10 Modelle registriert; list_display/list_filter sinnvoll (Aufgabe:
status/art/faellig; RadarItem: status/score; Sperrliste: richtung). ErgebnisTyp
und ProzessRegel+Schritte inline-editierbar (Schritte als TabularInline) —
bis der KI-Wizard kommt, IST der Admin der Regel-Editor.

## 3. views.py — Endpunkte

Muster wie matching_workflow: LoginRequired, JSON, drf-spectacular-Schema.

| Route (unter /shaduler/) | View | Zweck |
|---|---|---|
| `` | index | Portal-Template, Reiter-Gerüst |
| api/stats/ | api_stats | Zähler heute/überfällig/geplant/erledigt + Reiter-Badges |
| api/aufgaben/ | api_aufgaben_list | Filter: von,bis,art,status,user,ref; sortiert überfällig→heute→prio |
| api/aufgaben/create/ | api_aufgabe_create | manuell + für andere Module/KI |
| api/aufgaben/<uuid>/ | api_aufgabe_detail | inkl. Popup-Auszug (letzte 3 Aktivitaeten zum ref) |
| api/aufgaben/<uuid>/ergebnis/ | api_aufgabe_ergebnis | ErgebnisTyp anwenden → ergebnis_service (3 Wirkungen) |
| api/aufgaben/<uuid>/snooze/ | api_aufgabe_snooze | +1d/+1w/Datum |
| api/aufgaben/<uuid>/delegieren/ | api_aufgabe_delegieren | User + Benachrichtigung |
| api/aufgaben/ref/<typ>/<id>/ | api_aufgaben_fuer_ref | Widget in Matching/CRM |
| api/kalender/?von=&bis=&view= | api_kalender | Aggregation für Tag/Woche/Monat/Jahr |
| api/ergebnistypen/?kontext= | api_ergebnistypen | Katalog für Popup |
| api/inbox/ | api_inbox_list | Mails je Postfach, ungelesen, CRM-Zuordnung |
| api/inbox/<id>/aufgabe/ | api_inbox_to_task | Mail → Aufgabe |
| api/radar/anfragen/ | api_radar_items | Gruppen + Items nach Score |
| api/radar/anfragen/<uuid>/uebernehmen/ | api_radar_takeover | → ProjectRequest(source='board') + run_matching_async + Aufgabe "Shortlist prüfen" |
| api/radar/anfragen/<uuid>/verwerfen/ · /sperren/ | … | Dedup-merken · Sperrliste |
| api/radar/gruppe/<uuid>/trennen/ · /mergen/ | … | Clustering korrigieren |
| api/radar/berater/ | api_radar_consultants | 3 Match-Stufen |
| api/radar/berater/<uuid>/bestaetigen/ · /verwerfen/ | … | verknüpfen (Auto-Update) / ablehnen |
| api/radar/berater/einfuegen/ | api_radar_paste | Talentfinder URL/Text → Parsing |
| api/regeln/ (+CRUD) | api_regeln | ProzessRegel + Schritte (bis Wizard: Admin-Link) |
| api/schema/, api/docs/ | Spectacular | wie Matching |

## 4. urls.py / apps.py / signals.py / tasks.py

- **urls.py**: `app_name='abpe_shaduler'`; Routes exakt Tabelle Kap. 3.
- **apps.py**: `ready()` importiert signals.
- **signals.py**:
  - Receiver `post_save ProjectConsultant` → wenn Status geändert:
    `prozess_engine.on_status(instance, alt, neu)` + `aktivitaet_service.schreiben()`.
    (Alt-Status aus `status_history[-1]` — kein Eingriff in set_status nötig.)
  - Receiver auf `automail EmailLog`/`email_studio EmailLog` post_save →
    Aktivitaet "E-Mail gesendet" *(Hook, wird noch implementiert — s. Kap. 6)*
- **tasks.py** (Celery Beat):
  - `shaduler_radar_poll` (alle 5 Min): aktive RadarSources rss/html abarbeiten
  - `shaduler_inbox_poll` (alle 2 Min): IMAP-Konten lesen (nur Header+Preview)
  - `shaduler_prozess_tick` (alle 15 Min): `zeit_ohne_reaktion`-Regeln prüfen,
    fällige ProzessSchritte ausführen, Überfällig-Rollen
  - `shaduler_delegation_notify`: Benachrichtigungs-Mail bei Delegation

## 5. Frontend

### 5.1 module.json (`abpe_ui/templates/abpe_ui/modules/shaduler/module.json`)
id `shaduler`, icon `check2-square`, route `/shaduler/`, order 24, roles `["!berater"]`,
titles in **allen 15 Sprachen** (ar, de, en, es, fr, hu, it, ja, ko, nl, pl, pt,
ru, tr, zh — Übersetzung DE/EN manuell, Rest via DeepSeek wie gehabt),
static: `mod/mod-shaduler.css`, `mod/mod-shaduler.js`, `mod/mod-shaduler-kalender.js`,
subpages: aufgaben (Default), kalender, posteingang, radar, regeln
(`/shaduler/?tab=…`).

### 5.2 Templates
- `index.html`: extends `abpe_ui/base.html`; SHADULER_CONFIG-Bridge (wie
  MATCHING_CONFIG); Reiter-Leiste; **Lazy Tab-Loading** (Inhalt erst beim
  Klick); **i18n-Ready-Guard** + `languageChanged`-Handler im
  `{% block content %}` (Anhang A.17 der Portal-Doku — Pflicht).
- `tabs/*.html`: reine Fragmente, werden per fetch in den Reiter geladen.

### 5.3 static/css — `mod-shaduler.css`
- **Nur Theme-Variablen aus core-theme.css** verwenden (`--abcona-blue`,
  `--abcona-gray-card`, `--status-*`, `--text-*`, `--border-*`,
  `--border-radius-card`) → Dark Mode funktioniert automatisch, keine
  eigenen Farbwerte außer den Aufgabenart-Akzenten:
  `--a-wv --a-anruf --a-email --a-doc --a-post --a-wa --a-allg --a-radar`
  (Light+Dark-Variante, definiert am Anfang von mod-shaduler.css).
- Komponenten aus dem Final-Mockup 1:1: `.acc/.acc-head/.acc-body`, `.task`,
  Kalender (`.grid/.day/.bdg/.hourrow/.week`), Radar (`.ritem/.score/.grp/
  .chips/.mstat`), Popup (`.mh/.phase/.rbtn/.fx`), `.toast`.

### 5.4 static/js
- `mod-shaduler.js`: Reiter-Router, Ziehharmonika, Popup-3-Phasen-Flow
  (Auszug→Ergebnis→Wirkungen), Radar-Listen, Inbox, Toasts; alle Texte über
  `_t()` — **kein hardcodierter String**.
- `mod-shaduler-kalender.js`: Tag/Woche/Monat/Jahr-Renderer (getrennt, weil
  eigenständig testbar und später wiederverwendbar).
- Click-to-dial: bestehenden Weg aus mod-matching.js nutzen
  (webdial window.open + UserSettings) — Funktion in gemeinsames
  `js/lib/` extrahieren *(Refactor, klein)*.

### 5.5 i18n (15 Sprachen)
`i18n/<lang>/modules/shaduler/shaduler.json` + `manifest.json` je Sprache.
Schlüsselräume: `sh.tab_*`, `sh.art_*` (8 Arten), `sh.erg_*`
(ErgebnisTyp.label_i18n_key zeigt hierauf!), `sh.cal_*`, `sh.radar_*`,
`sh.inbox_*`, `sh.regeln_*`, `sh.toast_*`. DE+EN vollständig manuell,
ES/FR/IT/… per DeepSeek-Lauf (bestehender Prozess).

## 6. Schnittstellen-Matrix (vorhanden vs. wird noch implementiert)

| Schnittstelle | Modul | Status |
|---|---|---|
| `set_status()` + status_history | matching_workflow | ✅ vorhanden — Shaduler hängt Signal-Receiver dran |
| Neue Status (recommended_other, meet_later, contract_*, available_from, source) | matching_workflow Migration 0005 | 🔶 **wird noch implementiert** (Matching-Zielbild Kap. 3) |
| FollowupRule (Kaskade/Kanal) | matching_workflow | ✅ vorhanden — per FK referenziert |
| FollowupScheduler.process_due() → erzeugt Aufgabe statt Mail | matching_workflow | 🔶 **Umbau nötig** (ruft künftig aufgaben_service) |
| Click-to-dial (webdial + UserSettings) | matching/phone_service, abpe_ui | ✅ vorhanden — Extraktion nach js/lib *(klein)* |
| MeetMe anlegen + Variablen | abpe_meetme | ✅ vorhanden |
| `EmailStudio.send(template, variables)` | abpe_email_studio | ✅ vorhanden — **ref-basiert (Composer) wird noch implementiert** |
| `DocStudio.generate(template, variables)` + EDMS-Ablage | abpe_doc_studio | ✅ vorhanden — **ref-basiert + einfacher Vorlagen-Modus wird noch implementiert** |
| `build_variables(ref_type, ref_id)` (Kontext-Resolver) | **abpe_composer** | 🔶 **wird noch implementiert — Etappe 1!** Bis dahin: whatsapp_service lokal, E-Mail/Doc mit manuell gebautem Dict |
| `build_whatsapp_link()` | abpe_composer (Ziel) | 🔶 interimsweise in services/whatsapp_service.py, zieht später um |
| variables_registry (+ Matching-Vokabular) | email_studio → composer | 🔶 Umzug/Erweiterung geplant |
| IMAP-Konfiguration + EmailMessage | ingest_email | ✅ vorhanden — inbox_service liest read-only mit |
| Absender→Person/Firma (CrmEmailAddrBeanRel) | abpe_crm | ✅ vorhanden |
| ES-Mail-Index | automail_engine signals | ✅ vorhanden (nur lesen) |
| MatchingEngine Stage 1+2 (Quick-Score) | matching_workflow/services | ✅ vorhanden — radar_matcher ruft sie |
| Ollama Skill-Extraktion aus Text | matching_workflow (Tab „Neu") | ✅ vorhanden — als Service aufrufbar machen *(kleiner Refactor)* |
| Ollama-Embeddings fürs Clustering | ai-Stack | 🔶 **wird noch implementiert** (Fallback: Fuzzy-Score, reicht für V1) |
| LLM-Service mit Backend-Wahl (Ollama/DeepSeek) + Platzhalter-Prinzip | neu (KI-Schicht) | 🔶 später — V1 nutzt Ollama-Aufrufe direkt |
| KI-Wizard fürs Regel-Erstellen | abpe_ki_wiz | 🔶 später — Datenmodell (ProzessRegel/Schritt) ist ab V1 bereit; bis dahin Django-Admin |
| Aktivitaet-Hooks in Email/Doc/CRM/MeetMe (je ~3 Zeilen) | diverse | 🔶 **werden mit den jeweiligen Etappen implementiert** |
| Dashboard-Karte (Badges) | abpe_intranet_portal/dashboard | 🔶 klein, mit V1 |
| WhatsApp Business API | — | ⬜ bewusst NICHT in V1 (eigene App, falls je nötig) |

## 7. Ausbaustufen

- **V1 (Kern):** Migration 0001, Aufgaben+ErgebnisTyp+Aktivitaet+Regel-Tabellen,
  Reiter Aufgaben (Queue/Ziehharmonika + Popup-Flow), Signal-Hook Matching,
  prozess_engine Grundfunktionen, Fixtures, Admin, i18n DE/EN.
- **V1.1:** Kalender-Reiter (4 Ansichten), Posteingang, Dashboard-Karte,
  restliche 13 Sprachen (DeepSeek-Lauf), Aktivitaet-Hooks Email/Doc.
- **V2:** Radar Anfragen (RSS+HTML+Mail-Alerts, Gruppierung, Sperrliste),
  Radar Berater (Abgleich, Auto-Update, Einfügen-Feld), WhatsApp-Regel.
- **V3:** Regeln-UI, Workflow-Generator/KI-Wizard, LLM-Service, ES-Index
  für Aktivitaet.

## 8. Verbindliche Konventionen (aus Portal-Doku)

Kein hardcodierter Text (alles `_t()`) · keine Farbwerte außerhalb der
Variablen · Lazy-Tab-Loading · languageChanged-Handler (A.17) · keine Regel-,
Fristen- oder Firmen-Konstanten im Code (alles DB/SystemConfig) ·
Aktivitaet nur über den Service schreiben · bestehende Module werden nur um
Hooks ergänzt, nie umgebaut (Ausnahmen stehen explizit in den Zielbildern).
