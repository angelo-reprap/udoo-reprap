# CV Extractor – Modul-Dokumentation
**Version:** 8.0 | **Stand:** 2026-04-29 | **Server:** ucs5 | **Pfad:** /opt/abpe/backend

---

## 1. Überblick & Architektur

### 1.1 Zweck
Das Modul `cv_extractor` ist eine vollautomatische CV-Verarbeitungs-Pipeline.
Es nimmt PDF-, DOC- oder DOCX-Dateien entgegen sowie URLs von freelancermap.de
und GULP Talentfinder, extrahiert strukturierte Daten mit LLM (DeepSeek),
und erzeugt HTML- sowie Word-Ausgaben.

### 1.2 Pipeline-Überblick (3 Wege)
WEG A: PDF/DOCX Upload
Upload → tasks.py → process_pdf_task → pipeline.py → DB → HTML
WEG B: GULP URL Import
GULP-ID/URL → url_gu_importer.py → profil_pre_json.json + PDF
→ url_gu_db_importer.py → DB → HTML
WEG C: freelancermap URL Import
FL-URL → url_fl_importer.py → profil_pre_json.json + PDFs
→ url_fl_db_importer.py → DB → HTML

### 1.3 Pipeline Weg A (PDF/DOCX Upload, 2 Stufen)
Upload (PDF / DOC / DOCX)
│
▼ tasks.py
┌─────────────────────────────────────────────────────────────────┐
│ Datei-Routing:                                                  │
│  .doc  → data/doc/ + LibreOffice → data/pdf/                   │
│  .docx → data/doc/                                              │
│  .pdf  → data/pdf/                                              │
└─────────────────────────────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────────┐
│ STUFE 1 – Celery Task: process_pdf_task (~90-115s)              │
│                                                                 │
│  Schritt 0:   PDF/DOCX → Spans (fitz / python-docx)            │
│               BlockDetector → Gruppen                           │
│                                                                 │
│  Schritt 1:   BlockLabeler → Labels (3 LLM-Calls, ~25s)        │
│               Stufe 1: extract_block_label (alle Gruppen)       │
│               Stufe 2: extract_skill_label (nur SKILLS)         │
│               Stufe 3: extract_project_label (PROJECT/EXP)      │
│                                                                 │
│  Schritte 2-6: PARALLEL (6 Workers, ~23s gleichzeitig)         │
│               Schritt 2: extract_personal                       │
│               Schritt 3: extract_focus_areas                    │
│               Schritt 4a: extract_certifications                │
│               Schritt 4b: extract_schulungen                    │
│               Schritt 5: extract_industries                     │
│               Schritt 6: extract_kopf                           │
│                                                                 │
│  Schritt 7:   Skills direkt aus Blöcken (kein LLM, ~0s)        │
│                                                                 │
│  Schritt 8:   extract_experience PARALLEL (10 Workers, ~30s)   │
│               Alle Projekte gleichzeitig                        │
│               Branchen aus Projekten nachfüllen wenn kein       │
│               BRANCHEN-Block vorhanden                          │
│                                                                 │
│  Schritt 9:   PostProcessor (Token-Coverage, ~12s)              │
│  Schritt 10:  Skill-Gewichtung aus Projekten (~20s)             │
│                                                                 │
│  → DB speichern (extracted_to_db)                               │
│  → HTML generieren (HTMLGenerator)                              │
│  → SearchEnricher (searchable_text + ES-Index)                  │
│  → SelfLearning (TrainingTerm Frequenzen)                       │
│  → Status: profile_ready                                        │
└─────────────────────────────────────────────────────────────────┘
│
▼ (parallel gestartet)
┌─────────────────────────────────────────────────────────────────┐
│ STUFE 2 – Celery Task: enrich_consultant_task (~45-76s)         │
│                                                                 │
│  DBEnricher:        summary + matching + statistics (LLM)       │
│  SkillGraphBuilder: nodes + globale Edges (LLM)                 │
│                                                                 │
│  → Status: completed / enriched                                 │
└─────────────────────────────────────────────────────────────────┘

### 1.4 Pipeline Weg B: GULP URL Import
Eingabe: GULP-ID (z.B. 379269) oder vollständige URL
│
▼ views.py → import_url_api()
│
▼ url_importer.py (Router) → GULPImporter().run(**kwargs)
│
▼ url_gu_importer.py
│  1. Hash-ID aus GULP-ID ermitteln (API Search)
│  2. Session-Cookies laden (data/url/gu/.session_cookies.json)
│  3. API-Call → profile_data
│  4. Name ermitteln (4-stufig):
│     Stufe 1/2: GULP API personalData
│     Stufe 3:   Namazu-Index (/var/www/namazu/index/)
│     Stufe 4a:  provisorisch (hash_gulpId)
│     Stufe 4b:  not_found → Popup im Frontend
│  5. force_dir/first_name/last_name aus kwargs (Popup-Bestätigung)
│  6. Verzeichnis anlegen (data/url/gu/<nachname_vorname>/)
│  7. profil.json speichern
│  8. PDF herunterladen → download/01_profil.pdf
│  9. PDF extrahieren → extract/01_profil_yx.txt
│  10. profil_pre_json.json bauen
│
▼ views.py → import_url_to_db_api()
│
▼ url_gu_db_importer.py → GULPDbImporter().import_one()
│  1. profil_pre_json.json laden
│  2. PDF parsen (GULPPdfParser) → Projekte/Skills/Bildung
│  3. Merge: API-Daten + PDF-Daten
│  4. AID generieren
│  5. Consultant + DB speichern (extracted_to_db)
│  6. SkillNormalizer → ConsultantSkill
│  7. HTML generieren
│  8. SearchEnricher + SelfLearning
│  9. Celery Stufe 2 starten

### 1.5 Pipeline Weg C: freelancermap URL Import
Eingabe: FL-URL (z.B. https://www.freelancermap.de/profil/...)
│
▼ views.py → import_url_api()
│
▼ url_importer.py (Router) → FLImporter().run(**kwargs)
│
▼ url_fl_importer.py (URLImporter._run_freelancermap())
│  1. Session-Cookies laden (data/url/fl/.session_cookies.json)
│  2. Profil-Seite fetchen (BeautifulSoup)
│  3. ProfileShow JSON extrahieren
│  4. ld+json auswerten → first_name, last_name
│  5. Name-Logik:
│     - force_first/force_last aus kwargs → direkt verwenden
│     - givenName/familyName aus ld+json → verwenden
│     - Anonym → fl_id aus ProfileShow → Popup im Frontend
│  6. Verzeichnis anlegen (data/url/fl/<nachname_vorname>/)
│  7. profil.json speichern
│  8. Attachments herunterladen → download/.pdf|docx
│  9. PDFs/DOCXs extrahieren → extract/_yx.txt
│  10. Keywords extrahieren → analysis/keywords.json
│  11. Keywords gegen yx.txt matchen → analysis/matches.json
│  12. Checksum → analysis/checksum.json
│  13. profil_pre_json.json bauen
│
▼ views.py → import_url_to_db_api()
│
▼ url_fl_db_importer.py → FLDbImporter().import_one()
│  (analog GULPDbImporter, ohne PDF-Parser)
│  1. profil_pre_json.json laden
│  2. AID generieren
│  3. Consultant + DB speichern
│  4. SkillNormalizer
│  5. HTML generieren
│  6. SearchEnricher + SelfLearning
│  7. Celery Stufe 2 starten

### 1.6 Popup-Flow (Kein Name gefunden)
Frontend erkennt name_missing: true
│
▼ Popup erscheint mit:
│  - GULP: "GULP ID: 379269 · Session: 69bd3e54"
│  - FL:   "freelancermap ID: 326084"
│
▼ User wählt:
│  A) "Mit Namen" → first_name + last_name eingeben
│     → zweiter import-url/ Aufruf mit force_dir + first_name + last_name
│     → Verzeichnis: nachname_vorname
│  B) "Ohne Namen" → provisional_dir verwenden
│     → GULP: hash_gulpId (z.B. 69bd3e54_gulpId-379269)
│     → FL:   fl-{id} (z.B. fl-326084)

### 1.7 Performance

| Phase | Zeit |
|-------|------|
| Block-Labeler (3 LLM-Calls) | ~25s |
| Parallel-Extraktion (Schritte 2-6) | ~23s |
| Projekte parallel (10 workers) | ~30s |
| Post-Processor + Skill-Gewichtung | ~20s |
| DB + HTML + Search | ~15s |
| **Pipeline gesamt (Schritt 0-10)** | **~77s (1.3 min)** |
| **GULP URL Import** | **~52s** |
| **FL URL Import** | **~30-60s** |
| **Stufe 2** | **~45s** |

**Parallelisierung konfigurierbar in settings.json:**
```json
"pipeline": {
    "parallel_workers_projects": 10,
    "parallel_workers_sections": 6
}
```

---

## 2. Dateistruktur
apps/cv_extractor/
├── pipeline.py              # Haupt-Pipeline (Schritt 0-10)
├── models.py                # Alle Django-Modelle
├── views.py                 # REST API Endpoints
├── urls.py                  # URL-Routing
├── tasks.py                 # Celery Tasks (Stufe 1+2)
├── signals.py               # Post-Save Signal → Task-Start
├── post_processor.py        # Token-Coverage Analyse
├── Modul_Doku_CV_Extractor.md  # Diese Dokumentation
│
├── fixtures/
│   ├── pre_json_struct_reference.json   # Zielstruktur CV-Extraktion
│   ├── pre_json_reference.json          # Beispiel pre_json
│   ├── master_json_struct_reference.json
│   ├── master_json_reference.json
│   └── url_platforms.json               # Plattform-Konfiguration
│
├── services/
│   ├── url_importer.py          # Router: fl→FLImporter, gu→GULPImporter
│   ├── url_fl_importer.py       # freelancermap Fetch+Download+Extract
│   ├── url_fl_importer.py.bak   # Backup
│   ├── url_fl_db_importer.py    # FL → DB (FLDbImporter)
│   ├── url_gu_importer.py       # GULP API Fetch+PDF Download
│   ├── url_gu_importer.py.bak   # Backup
│   ├── url_gu_db_importer.py    # GULP PDF-Parser + DB (GULPDbImporter)
│   ├── pdf_extractor.py         # PDF → Spans (PyMuPDF/fitz)
│   ├── word_extractor.py        # DOCX → Spans (python-docx)
│   ├── block_detector.py        # Spans → Gruppen/Projekte
│   ├── block_detector_ocr.py    # OCR-Variante BlockDetector
│   ├── block_labeler.py         # Gruppen → Labels (3 LLM-Stufen)
│   ├── skill_normalizer.py      # Tech-Counter → ConsultantSkill
│   ├── aid_generator.py         # AID-Generierung mit LLM
│   ├── versioning.py            # Versionierung (DB-basiert)
│   ├── deepseek_api.py          # DeepSeek API (Dict-Parser)
│   ├── deepseek_api_label.py    # DeepSeek API (Array+Dict-Parser)
│   ├── deepseek_api_enricher.py # DeepSeek API für Enricher
│   ├── deepseek_service.py      # DeepSeek Service Wrapper
│   ├── url_extractor.py         # URL-basierte Extraktion
│   ├── structure_analyzer.py    # Dokument-Struktur-Analyse
│   ├── document_analyzer.py     # Dokument-Analyzer
│   ├── pre_skill.py             # Pre-Skill Verarbeitung
│   ├── project_grouper.py       # Projekt-Gruppierung
│   └── ollama_service.py        # Ollama (lokal, Fallback)
│
├── extractors/
│   └── base_extractor.py    # UniversalExtractor (Prompt aus DB)
│
├── enricher/
│   ├── extracted_to_db.py       # Extrahierte Daten → DB-Tabellen
│   ├── db_enricher.py           # Stufe 2: LLM summary+matching
│   ├── search_enricher.py       # searchable_text + ES-Index
│   ├── self_learning_pipeline.py # TrainingTerm Frequenzen
│   ├── skill_graph_builder.py   # Skill-Nodes + globale Edges
│   └── master_json_builder.py   # DB → Master-JSON
│
└── generator/
├── html/
│   └── html_generator.py    # HTML-Ausgabe (Django Templates)
└── word/
├── word_generator.py    # Word-Ausgabe (CVBuilder)
└── word_builder.py      # Word XML-Helpers

### Dateisystem (data/)
/opt/abpe/backend/data/
├── doc/          ← Word-Originale (.doc + .docx)
├── pdf/          ← alle PDFs (original + konvertiert)
├── extracted/    ← Debug TXT (nur debug.pdf_extractor=true)
├── html_out/     ← HTML-Profile pro Consultant
├── doc_out/      ← generierte Word-Dokumente
├── uploads/      ← Django MEDIA_ROOT (Upload-Eingang)
├── exports/      ← Master-JSON Exporte
├── email/        ← E-Mail Verarbeitung
│   ├── attachments/
│   ├── errors/
│   └── processed/
└── url/
├── fl/       ← freelancermap Profile
│   ├── .session_cookies.json
│   └── <nachname_vorname>/
│       ├── profil.json          ← FL API Rohdaten
│       ├── profil_pre_json.json ← Zielstruktur
│       ├── import.log
│       ├── download/            ← heruntergeladene PDFs/DOCXs
│       ├── extract/             ← *_yx.txt Span-Extrakte
│       └── analysis/
│           ├── keywords.json
│           ├── matches.json
│           └── checksum.json
└── gu/       ← GULP Profile
├── .session_cookies.json
└── <nachname_vorname>/
├── profil.json          ← GULP API Rohdaten
├── profil_pre_json.json ← Zielstruktur
├── download/01_profil.pdf
└── extract/01_profil_yx.txt

---

## 3. URL Import — Aktueller Stand (2026-04-29)

### 3.1 GULP Profile in DB (17 gesamt)

| Verzeichnis | AID | Status |
|-------------|-----|--------|
| amri_manochehr | AID-ma_1.2.2.9 | ✅ DB |
| danda_philipp | AID-pd_1.2.3.9 | ✅ DB |
| deuschle_jens | AID-jd_1.2.3.9 | ✅ DB |
| eisenacher_patrick | AID-pe_1.2.3.1 | ✅ DB |
| glas_oliver | AID-og_3.3.3.11 | ✅ DB |
| khaiti_issam | AID-ik_5.2.4.9 | ✅ DB |
| koenig_marcel | AID-mk_1.4.3.9 | ✅ DB |
| kossev_boris | AID-bk_5.4.4.9 | ✅ DB |
| leonov_alexey | AID-al_5.1.4.11 | ✅ DB |
| menke_niels | AID-nm_5.4.4.13 | ✅ DB |
| mueller_ralf-peter | AID-rm_3.2.3.9 | ✅ DB |
| stoertzer_kurt | AID-ks_1.2.3.9 | ✅ DB |
| troschke_thomas | AID-tt_1.2.3.20 | ✅ DB |
| walter_oliver | AID-ow_1.2.3.9 | ✅ DB |
| 542bcc35e4b000c519d02e60_GULP-51404 | – | ❌ nicht in DB |
| 6960f569f0ff5d2b135f7c5e_GULP-377124 | – | ❌ nicht in DB |
| mu_ma | – | ❌ Testprofil |

### 3.2 FL Profile in DB (4 gesamt, 9 ausstehend)

| Verzeichnis | AID | PDFs | Status |
|-------------|-----|------|--------|
| akbulut_akin | AID-aa_2.4.2.0 | 2 | ✅ DB |
| ghebreamlak_asmerom | AID-ag_5.3.4.1 | 1 DOCX | ✅ DB |
| polat_samet | AID-sp_4.3.4.1 | 4 | ✅ DB |
| szewczyk_angelika | AID-as_2.3.2.1 | 2 | ✅ DB |
| claypole_natalie | – | 1 | ❌ nicht in DB |
| fakhari_pouya | – | 7 | ❌ nicht in DB |
| fl-51792 | – | 1 DOCX | ❌ nicht in DB |
| oberlerchner_sarah | – | 1 | ❌ nicht in DB |
| przybylski_matthias | – | 2 | ❌ nicht in DB |
| rehsack_jens | – | 1 | ❌ nicht in DB |
| schumacher_ulrich | – | 0 | ❌ nicht in DB |
| tonev_ivaylo | – | 1 | ❌ nicht in DB |
| ahmad_mashhood | – | 0 | ❌ nicht in DB |

---

## 4. API Endpoints

### 4.1 Upload-Flow
POST /cv-extractor/api/check-duplicate/
Body: {"first_name": "Thomas", "last_name": "Troschke"}
POST /cv-extractor/api/upload/async/
Body (multipart):
pdf_file:         <Datei>
first_name:       Thomas
last_name:        Troschke
target_directory: troschke_thomas
action_type:      new_version
GET /cv-extractor/api/upload/<id>/status/
GET /cv-extractor/api/uploads/

### 4.2 URL Import
POST /cv-extractor/api/import-url/
Body: {
"url": "379269",              # GULP-ID oder vollständige URL
"platform": "gu",             # "gu" oder "fl"
"cookies": {},
"force_dir": "muster_max",    # optional: nach Popup-Bestätigung
"first_name": "Max",          # optional: nach Popup-Bestätigung
"last_name": "Muster"         # optional: nach Popup-Bestätigung
}
Response (Erfolg):    {"success": true, "name": "...", "dir": "...", ...}
Response (Kein Name): {"name_missing": true, "provisional_dir": "...", ...}
POST /cv-extractor/api/import-url-to-db/
Body: {
"dir_name": "troschke_thomas",
"platform": "gu",             # "gu" oder "fl"
"first_name": "Thomas",       # optional: Override
"last_name": "Troschke"       # optional: Override
}
POST /cv-extractor/api/import-url/pdf/

### 4.3 Session-Management
GET/POST /cv-extractor/api/gu-session/    # GULP Session prüfen/setzen
GET/POST /cv-extractor/api/flm-session/  # freelancermap Session

### 4.4 Editor
GET  /cv-extractor/editor/<aid>/
POST /cv-extractor/api/cv-editor/<aid>/update/
POST /cv-extractor/api/cv-editor/<aid>/generate-word/
DELETE /cv-extractor/api/cv-editor/<aid>/delete/
POST /cv-extractor/api/cv-editor/<aid>/validate/

### 4.5 Hilfsfunktionen
GET  /cv-extractor/api/url-platforms/
POST /cv-extractor/api/rename-url-dir/
GET  /cv-extractor/health/
GET  /cv-extractor/api/word-templates/

---

## 5. Detaillierter Extraktionsvorgang (Weg A)

### 5.1 Schritt 0: Dokument → Spans

**PDF:**
```python
from apps.cv_extractor.services.pdf_extractor import PDFExtractor
res = PDFExtractor().extract('data/pdf/AID-tt_1.2.3.3.pdf')
# res.spans = [ExtractedSpan(page, y, x, size, bold, italic, font, text)]
```

**DOCX:**
```python
from apps.cv_extractor.services.word_extractor import WordExtractor
res = WordExtractor().extract('data/doc/datei.docx')
# res.spans = [SimpleSpan(page, y, x, size, bold, italic, font, text)]
```

Jeder Span enthält: `page`, `y`, `x`, `size`, `bold`, `italic`, `font`, `text`

**yx.txt Format (URL-Imports):**
p01|y=  45|x= 100|sz= 18.0|B|BERUFSERFAHRUNG
p01|y=  80|x= 100|sz= 11.0|.|2022 – heute

### 5.2 Schritt 0b: BlockDetector → Gruppen

Regelbasiert (kein LLM):
- Y-Abstand zwischen Spans → neue Gruppe wenn Gap > Schwellenwert
- Score-Berechnung für Projekte: Datum=3, Firma/Rolle/Tech/Branche je 1 Punkt
- Score ≥ 4 → Projekt-Gruppe

### 5.3 Schritt 1: BlockLabeler → Labels (3 LLM-Stufen)

**Mögliche Labels:**
HEADER, PERSONAL, FACHBEREICHE, ZERTIFIKATE, SCHULUNGEN,
BRANCHEN, SKILLS, FOCUS_EXP, EXPERIENCE, PROJECT, OTHER

### 5.4 GULP PDF-Parser (GULPPdfParser)

Speziell für GULP-generierte PDFs (einheitliches Format):
- `sz=15.0` → Sektions-Überschrift
- `sz=19.5` → Headline
- `sz=9.0` → Projekt-Metadaten (zusammengeklebt!)
- `sz=7.5` → Bullet-Liste (sauber)

**Bekannte GULP-PDF Probleme:**
- `sz=9.0` Tokens werden zusammengeklebt: `"ProdukteF5AnsibleOpswat"`
- Lösung: `_split_glued()` + `_expand_brackets()` in `_fin_proj()`
- `sz=9.0` Skills werden ignoriert (unzuverlässig) → API-Daten bevorzugt

---

## 6. Prompt-Übersicht

### 6.1 Block-Labeling Prompts

| Stage | Zweck | Output |
|-------|-------|--------|
| `extract_block_label` | Klassifiziert alle CV-Blöcke | JSON-Array [{group, label}] |
| `extract_skill_label` | Ordnet SKILLS den 27 Kategorien zu | JSON-Array [{group, category}] |
| `extract_project_label` | Gruppiert Projekt-Blöcke | JSON-Array [{group, project_nr}] |

### 6.2 Daten-Extraktions-Prompts

| Stage | Zweck | Output |
|-------|-------|--------|
| `extract_personal` | Persönliche Daten | {first_name, last_name, ...} |
| `extract_focus_areas` | Fachbereiche | {focus_areas: []} |
| `extract_certifications` | Zertifikate | {certifications: [...]} |
| `extract_schulungen` | Schulungen/Kurse | [{name, provider, date}] |
| `extract_industries` | Branchen | {industries: []} |
| `extract_kopf` | Kopfbereich | {aid, headline, company} |
| `extract_experience` | Projekte | {period, company, role, ...} |

### 6.3 Weitere Prompts

| Stage | Zweck |
|-------|-------|
| `classify_aid` | LLM klassifiziert role/landscape/level |
| `classify_missing_tokens` | PostProcessor: fehlende Tokens |

---

## 7. Zielstruktur: pre_json_struct_reference.json

Alle Extraktionen (Weg A, B, C) erzeugen dasselbe Format:

```json
{
  "metadata": {
    "aid": "",
    "version": "",
    "consultant_dir": "",
    "first_name": "",
    "last_name": "",
    "headline": "",
    "source": {"type": "", "platform": "gulp|fl|upload", ...},
    "pipeline": {"version": "5.0", "extractor": "...", ...}
  },
  "extracted_data": {
    "personal": {
      "first_name": "", "last_name": "", "birth_year": null,
      "languages": [], "email": "", "phone": "", "location": "",
      "availability": "", "degree": "", "headline": "", "summary": ""
    },
    "skills": {
      "architecture_pattern": [], "business_software": [],
      "ci_cd_tool": [], "cloud_platform": [], ...
    },
    "certifications": [{"name": "", "issuer": "", "date_obtained": ""}],
    "experience": [{
      "period": "", "title": "", "company": "", "industry": "",
      "role": "", "location": "", "activities": [], "technologies": []
    }],
    "industries": [], "focus_areas": [], "focus_experience": [],
    "education": [{"degree": "", "institution": "", "period": ""}]
  },
  "audit": {"created_by": "", "created_at": "", "steps_completed": []}
}
```

---

## 8. 27 Skill-Kategorien

| JSON-Key | Anzeigename | Beispiele |
|----------|-------------|-----------|
| `architecture_pattern` | Architekturmuster | Microservices, REST, SOA |
| `business_software` | Business Software | SAP, MS Office |
| `ci_cd_tool` | CI/CD Tools | Jenkins, GitLab CI |
| `cloud_platform` | Cloud-Plattformen | Azure, AWS, GCP |
| `communication_tool` | Kommunikationstools | Teams, Slack |
| `database` | Datenbanken | MySQL, Oracle |
| `data_format` | Datenformate | JSON, XML, YAML |
| `data_management` | Datenmanagement | ETL, Data Warehouse |
| `development_environment` | Entwicklungsumgebungen | VS Code, IntelliJ |
| `devops_tool` | DevOps Tools | Ansible, Docker, K8s |
| `documentation_tool` | Dokumentationstools | Confluence, Wiki |
| `framework` | Frameworks | Django, React, Spring |
| `hardware` | Hardware | Cisco Nexus 9K, FortiGate |
| `identity_management` | Identity Management | FortiAuthenticator, AD |
| `it_infrastructure` | IT-Infrastruktur | WAN/LAN, DMZ, TCP/IP |
| `methodology` | Methoden | ITIL, Scrum, Agile |
| `monitoring_tool` | Monitoring Tools | Zabbix, Skybox |
| `network_protocol` | Netzwerkprotokolle | BGP, OSPF, VPN |
| `operating_system` | Betriebssysteme | Linux, FortiOS |
| `programming_languages` | Programmiersprachen | Python, Java, C# |
| `project_management` | Projektmanagement | MS Project, Jira |
| `security_tool` | Security Tools | FortiGate, Checkpoint |
| `soft_skill` | Soft Skills | Teamführung, Coaching |
| `special_concept` | Spezielle Konzepte | GMP-Compliance, Six Sigma |
| `testing_tool` | Testing Tools | JUnit, Selenium |
| `version_control` | Versionsverwaltung | Git, SVN |
| `virtualization` | Virtualisierung | VMware, Proxmox |

---

## 9. Datenmodelle (Übersicht)

| Modell | Zweck |
|--------|-------|
| `Consultant` | Zentrale Entität: aid, version, name, degree, headline, source_type |
| `UploadedPDF` | Upload-Queue: file, status, task_id, aid, consultant_id |
| `Skill` | Skill-Stammdaten: name, category, frequency |
| `ConsultantSkill` | Skill ↔ Consultant mit weight |
| `Experience` | Projekterfahrung: period, company, role |
| `ExperienceActivity` | Projekttätigkeiten |
| `ExperienceTechnology` | Projekt-Technologien |
| `Education` | Ausbildung/Kurse (education_type: degree/course) |
| `Certification` | Zertifikate |
| `SkillCategory` | 27 Skill-Kategorien |
| `PromptTemplate` | LLM-Prompts in DB |
| `TrainingTerm` | Self-Learning Frequenzen |
| `ConsultantVersion` | Versions-Verwaltung |
| `SkillRelation` | Globaler Skill-Graph |

### AID-Format
AID-{initials}_{role}.{landscape}.{level}.{version}
Beispiel: AID-tt_1.2.4.2
role:      1=Admin, 2=Entwickler, 3=Architekt, 4=PL, 5=Berater
landscape: 1=Client/Server, 2=Netz/Security, 3=Web/SW, 4=Cloud, 5=Embedded
level:     1=Junior, 2=Senior, 3=Experte, 4=Sr.Experte, 5=Master

---

## 10. Bekannte Bugs (Stand 2026-04-29)

| Bug | Datei | Problem | Auswirkung |
|-----|-------|---------|------------|
| BUG-01 | self_learning_pipeline.py | `models_F` NameError | SelfLearning crasht still |
| BUG-02 | skill_graph_builder.py | `datetime` Import nach Verwendung | Keine Skill-Gewichtungen |
| BUG-03 | extracted_to_db.py | Schulungen doppelt verarbeitet | Doppelte Education-Einträge |
| BUG-04 | html_generator.py | Zertifikate erscheinen doppelt | Duplikate im HTML |
| BUG-05 | post_processor.py | PDF wird 3x extrahiert | ~5s unnötige Rechenzeit |

---

## 11. Offene Aufgaben (Stand 2026-04-29)

| # | Aufgabe | Priorität |
|---|---------|-----------|
| 1 | FL PDFs → LLM-basierte Extraktion (universeller CV-Extractor) | 🔴 HOCH |
| 2 | Restliche FL-Profile importieren (9 ausstehend) | 🟡 MITTEL |
| 3 | Alte Test-Einträge aufräumen (mu_ma, hash-Verzeichnisse) | 🟢 NIEDRIG |
| 4 | oberlerchner_sarah in DB importieren | 🟡 MITTEL |
| 5 | Bugs BUG-01 bis BUG-05 beheben | 🟡 MITTEL |

### Nächster Chat: Universeller LLM CV-Extractor

**Ziel:** FL PDFs (und beliebige CV-Formate) via LLM extrahieren

**Architektur:**
PDF/DOCX
↓
PDFExtractor → yx.txt
↓
Block-Segmenter → logische Blöcke
[PERSONAL] [EXPERIENCE] [SKILLS] [EDUCATION] [CERTS]
↓
LLM pro Block (~5 Calls) → strukturiert
↓
pre_json_struct_reference.json befüllt
↓
FLDbImporter.import_one() → DB → HTML → Editor

**Zu lesende Dateien im neuen Chat:**
```bash
cat apps/cv_extractor/fixtures/pre_json_struct_reference.json
cat data/url/fl/szewczyk_angelika/extract/01_CV-Angelika-Szewczyk_yx.txt | head -80
cat data/url/fl/rehsack_jens/extract/01_2025-05-Rehsack-Profil_yx.txt | head -80
cat data/url/fl/oberlerchner_sarah/extract/01_CV-Oberlerchner-DE_yx.txt | head -80
cat apps/cv_extractor/services/pdf_extractor.py
cat apps/cv_extractor/services/url_fl_db_importer.py
```

---

## 12. Wichtige Befehle

```bash
# Kontext laden
cd /opt/abpe/backend && source /opt/abpe/venv311/bin/activate

# GULP alle importieren
python3 manage.py shell -c "
from apps.cv_extractor.services.url_gu_db_importer import GULPDbImporter
results = GULPDbImporter().import_all(dry_run=False)
print(f'OK: {len(results[\"ok\"])} | Fehler: {len(results[\"error\"])}')
"

# FL alle importieren
python3 manage.py shell -c "
from apps.cv_extractor.services.url_fl_db_importer import FLDbImporter
results = FLDbImporter().import_all(dry_run=False)
print(f'OK: {len(results[\"ok\"])} | Fehler: {len(results[\"error\"])}')
"

# HTML neu generieren
python3 manage.py shell -c "
from apps.cv_extractor.models import Consultant
from apps.cv_extractor.generator.html.html_generator import HTMLGenerator
c = Consultant.objects.get(aid='AID-tt_1.2.3.20')
gen = HTMLGenerator()
gen.generate('aid-profile', c)
gen.generate('aid-short', c)
"

# Profil löschen
python3 manage.py shell -c "
from apps.cv_extractor.models import Consultant, UploadedPDF
c = Consultant.objects.filter(aid='AID-mm_2.3.2.1').first()
if c:
    UploadedPDF.objects.filter(aid=c.aid).delete()
    c.delete()
    print('Gelöscht')
"

# Pipeline manuell testen
python3 manage.py shell -c "
from apps.cv_extractor.pipeline import CvExtractionPipeline
pipeline = CvExtractionPipeline()
result = pipeline.run(
    pdf_path='data/pdf/AID-tt_1.2.3.3.pdf',
    save_to_db=False,
    first_name='Thomas', last_name='Troschke',
    target_directory='troschke_thomas',
    action_type='new_version'
)
"

# Logs beobachten
tail -f /opt/abpe/logs/celery.log | grep -E "SCHRITT|✅|ERROR|Dauer|Gesamt"

# Server neu starten
supervisorctl restart abpe-django abpe-celery

# Workers anpassen
nano /opt/abpe/backend/settings.json
# → "pipeline": {"parallel_workers_projects": 10}
supervisorctl restart abpe-celery
```

---

## 13. Konfiguration (settings.json)

```json
{
  "ai_models": {
    "deepseek": {
      "api_key": "sk-98572f9172bb4dd7a370f7340420dc2a",
      "model":   "deepseek-chat",
      "timeout": 30,
      "temperature": 0.1
    }
  },
  "pipeline": {
    "parallel_workers_projects": 10,
    "parallel_workers_sections": 6
  },
  "namazu": {
    "html_source": "/var/www/namazu/index/",
    "name_pattern": "([^_]+)__([^_]+)__([a-f0-9-]+)\\.html"
  },
  "elasticsearch": {
    "enabled": true,
    "hosts": ["http://localhost:9200"],
    "index_name": "abpe_skills_index"
  },
  "debug": {
    "global":         false,
    "pdf_extractor":  true,
    "block_detector": false,
    "pipeline":       true
  }
}
```

---

## 14. Getestete CVs (Stand 2026-04-29)

| AID | Person | Quelle | Projekte | Status |
|-----|--------|--------|----------|--------|
| AID-tt_1.2.3.20 | Thomas Troschke | GULP | 16 | ✅ |
| AID-ma_1.2.2.9 | Manochehr Amri | GULP | – | ✅ |
| AID-og_3.3.3.11 | Oliver Glas | GULP | – | ✅ |
| AID-nm_5.4.4.13 | Niels Menke | GULP | – | ✅ |
| AID-sp_4.3.4.1 | Samet Polat | FL | 13 | ✅ |
| AID-as_2.3.2.1 | Angelika Szewczyk | FL | – | ✅ |
| AID-ag_5.3.4.1 | Asmerom Ghebreamlak | FL | – | ✅ |
| AID-aa_2.4.2.0 | Akin Akbulut | FL | – | ✅ |

---
*Dokumentation Stand 2026-04-29 — Version 8.0*
