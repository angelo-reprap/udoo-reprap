# main_pipeline — Architektur & Ablauf

**Stand:** 2026-05-09
**Version:** 6.0
**Autor:** main_pipeline Entwicklung

---

## Übersicht

Die main_pipeline verarbeitet ein einzelnes CV (PDF oder DOCX) vollständig im RAM.
Einzige Disk-Outputs am Ende der Pipeline:
- `data/extracted/<dir>/<AID>.txt` — lesbares Profil
- `data/html_out/<dir>/<AID>.html` — HTML Qualifikationsprofil

---

## Aufruf

```python
from apps.cv_extractor.services.main_pipeline_controller import main_pipeline_controller

result = main_pipeline_controller.run(
    pdf_path   = 'data/url/fl/akbulut_akin/download/01_CV.pdf',
    first_name = 'Akin',
    last_name  = 'Akbulut',
    dir_name   = 'akbulut_akin',
)
# → {'success': True, 'aid': 'AID-aa_5.3.3.18', 'editor_url': '/cv-extractor/editor/...'}
```

---

## Pipeline-Schritte

### SCHRITT 1 — PDF/DOCX → Spans
**Datei:** `services/main_pdf_extractor.py` oder `services/main_word_extractor.py`

- PDF: PyMuPDF extrahiert alle Text-Spans mit X/Y-Koordinaten, Schriftgröße, Bold/Italic
- DOCX: python-docx extrahiert Paragraphen und Tabellen
- DOC: LibreOffice konvertiert zu PDF → dann wie PDF
- Erkennt 2-spaltige Layouts automatisch (split_x berechnet aus X-Clustern)
- Spalte 0 (links) wird komplett vor Spalte 1 (rechts) verarbeitet
- Jeder Span bekommt `column_id` gesetzt (0=links, 1=rechts, -1=unbekannt)
- OCR-Fallback für PDFs ohne Text-Layer (pytesseract)

**Output:** Liste von `ExtractedSpan` Objekten (im RAM)

---

### SCHRITT 2 — Spans → Blöcke → Gruppen
**Datei:** `services/main_pipeline_detector.py`

**2a. Blöcke:**
- Spans werden zu Blöcken zusammengefasst (gleiche Y-Koordinate = eine Zeile)
- Fingerprint-basierte Erkennung von Wiederholungsmustern (Seiten-Header/-Footer)
- `cv_info` Analyse: erkennt WIEDERKEHRENDE MUSTER, BULLET-BLOECKE, EINZEL-HEADER

**2b. Gruppen (LLM):**
- Prompt: `main_detector_group` (name-basiert, mit master_ Fallback)
- Blöcke werden in logische Gruppen zusammengefasst
- Jede Gruppe = ein inhaltlicher Bereich (Projekt, Ausbildung, Skills, etc.)
- Bei >50 Blöcken: Chunk-Verarbeitung mit `main_detector_group_boundary`
- Spaltenregel: col=0 und col=1 normalerweise getrennte Gruppen

**2c. Format-Split:**
- Regelbasierter Split wenn Formatwechsel innerhalb einer Gruppe erkannt wird

**2d. Quality-Check (LLM):**
- Prompt: `main_detector_quality`
- Labels der Gruppen werden überprüft und korrigiert
- Gruppen werden NICHT gesplittet oder gemergt — nur Labels korrigiert

**Output:** Liste von Gruppen `[{'blocks': [1,2,3], 'label': 'Projekt: ...'}]` (im RAM)

---

### SCHRITT 3 — Gruppen → Labels
**Datei:** `services/main_labeler.py`

**Stufe 1 — Hauptlabels (LLM):**
- Prompt: `main_block_label`
- Jeder Gruppe wird EINES dieser Labels zugewiesen:
  `HEADER | PERSONAL | FACHBEREICHE | ZERTIFIKATE | SCHULUNGEN |`
  `BRANCHEN | SKILLS | FOCUS_EXP | PROJECT | OTHER`

**Stufe 2 — Skills kategorisieren (LLM):**
- Prompt: `main_extract_skill_label`
- SKILLS-Blöcke werden einer der 27 Skill-Kategorien zugeordnet
- Gemischte Listen → `special_skill` → landen in skill_ablage

**Stufe 3 — Projekte zusammenführen (LLM):**
- Prompt: `main_extract_project_label`
- PROJECT-Blöcke werden zusammenhängenden Projekten zugeordnet
- Erkennt: Vermittler / Auftragnehmer / Endkunde = selbes Projekt

**Output:** `labeled` Liste mit `{'index', 'label', 'skill_cat', 'project_nr'}` (im RAM)

---

### SCHRITT 4 — Labels → pre_json
**Datei:** `extractors/main_base_extractor.py`

Alle LLM-Extraktionen nutzen `MasterBaseExtractor` — lädt Prompt aus DB per `stage=`.

**4a. Parallele Extraktionen (7 gleichzeitig):**

| Label | Prompt | Ergebnis in pre_json |
|-------|--------|----------------------|
| PERSONAL | `main_extract_personal` | personal{} |
| FACHBEREICHE | `main_extract_fachbereiche` | focus_areas[] |
| ZERTIFIKATE | `main_extract_zertifikate` | certifications[] |
| SCHULUNGEN | `main_extract_schulungen` | education[] (degree+course) |
| BRANCHEN | `main_extract_branchen` | industries[] |
| FOCUS_EXP | `main_extract_focus_exp` | focus_experience[] |
| OTHER | `main_extract_sonstiges` | other |

**4b. Projekte (einzeln parallel, max 10 gleichzeitig):**
- Prompt: `main_extract_experience`
- Jedes PROJECT-Label wird einzeln extrahiert
- Felder: period, title, company, industry, role, location, activities[], technologies[]

**4c. HEADER → Name + Headline:**
- Prompt: `main_extract_header`
- Extrahiert: first_name, last_name, headline
- Setzt metadata.headline wenn leer

**4d. SKILLS → skill_ablage:**
- Prompt: `main_extract_skill_list`
- Gemischte Skill-Listen werden als flache Liste extrahiert
- Landen in `pre_json.extracted_data.skill_ablage[]`
- Werden später vom skill_normalizer verarbeitet

**Output:** `pre_json` Dict mit vollständig strukturierten Daten (im RAM)

---

### SCHRITT 5 — pre_json → DB
**Datei:** `services/main_db_importer.py` → Methode `import_from_prejson()`

**5a. Versionierung:**
- `versioning.py`: ermittelt consultant_dir und nächste Version
- Namensvetter-Logik: akbulut_akin, akbulut_akin-2, etc.

**5b. AID generieren:**
- `aid_generator.py`: LLM klassifiziert role_code, landscape_code, level_code
- Format: `AID-{initials}_{role}.{landscape}.{level}.{version}`
- Beispiel: `AID-aa_5.3.3.18`

**5c. Consultant-Objekt anlegen:**
- `Consultant.objects.get_or_create(aid=aid)`
- Felder direkt aus pre_json setzen

**5d. DB speichern via main_extracted_to_db:**
- `enricher/main_extracted_to_db.py`
- Schreibt: Sprachen, Skills (aus skills{}), Zertifikate, Education,
  Projekte, Branchen, Fachbereiche, Focus Experience, Other Content
- Degree-Fallback: wenn personal.degree leer → aus education[type=degree]
- Skills{} ist bei main_pipeline leer → 0 Einträge (korrekt)

**5e. Skill-Normalisierung:**
- `services/main_skill_normalizer.py`
- Input: tech_counter aus experience[].technologies[] + skill_ablage
- Sequenziell durch 27 Kategorien (spezifisch → generisch)
- Gewichtung: Monate (50%) + Projektbreite (40%) + Count (10%)
- Schreibt: ConsultantSkill + ExperienceTechnology

**5f. Name + Headline sichern:**
- first_name/last_name aus Override immer setzen
- Headline-Fallback aus focus_areas wenn leer

**5g. HTML generieren (Disk-Output 1):**
- `generator/html/html_generator.py`
- Generiert: aid-profile (vollständig) + aid-short (Kurzprofil)
- Liest Skill-Kategorien aus `ConsultantSkill.category_name` (nicht skill.category!)
- Speichert nach: `data/html_out/<dir>/<AID>.html`

**5h. TXT generieren (Disk-Output 2):**
- Lesbares Profil mit allen Feldern
- Speichert nach: `data/extracted/<dir>/<AID>.txt`

**5i. SearchEnricher:**
- `enricher/search_enricher.py`
- Baut searchable_text (Volltext für ES)
- Baut facets (Filter-Werte)
- Schreibt in ElasticSearch Index `abpe_consultants_index`

**5j. SelfLearning:**
- `enricher/self_learning_pipeline.py`
- Liest Skills aus ConsultantSkill (DB) — nicht aus pre_json
- Erhöht TrainingTerm.frequency + confidence
- Erhöht Industry.frequency + FocusArea.frequency
- Ab frequency≥3 + confidence≥0.7: Skill-Prompts automatisch ergänzen

**5k. Stufe 2 (Celery, asynchron):**
- `tasks.enrich_consultant_task.delay(consultant.id)`
- Läuft parallel im Hintergrund
- db_enricher: summary + matching + statistics (LLM)
- skill_graph_builder: Skill-Relationen
- Danach: EN-HTML generieren

---

## Prompt-Übersicht

### Detector (main_pipeline_detector.py)
| name | Zweck |
|------|-------|
| main_detector_group | Blöcke → Gruppen |
| main_detector_group_boundary | Chunk-Übergänge |
| main_detector_quality | Label-Korrektur |

### Labeler (main_labeler.py)
| stage | Zweck |
|-------|-------|
| main_block_label | Gruppen → Labels |
| main_extract_skill_label | SKILLS → Kategorien |
| main_extract_project_label | Projekte zusammenführen |

### Extractor (main_base_extractor.py)
| stage | Zweck |
|-------|-------|
| main_extract_header | Name + Headline |
| main_extract_personal | Persönliche Daten |
| main_extract_fachbereiche | Fachbereiche |
| main_extract_zertifikate | Zertifikate |
| main_extract_schulungen | Ausbildung + Schulungen |
| main_extract_branchen | Branchen |
| main_extract_focus_exp | Produkte/Standards |
| main_extract_experience | Projekte (einzeln) |
| main_extract_sonstiges | Sonstiges |
| main_extract_skill_list | Skills → skill_ablage |

---

## Dateien
CONTROLLER:
services/main_pipeline_controller.py
SCHRITT 1:
services/main_pdf_extractor.py
services/main_word_extractor.py
SCHRITT 2:
services/main_pipeline_detector.py
SCHRITT 3:
services/main_labeler.py
SCHRITT 4:
extractors/main_base_extractor.py
services/deepseek_api_label.py
services/deepseek_service.py
SCHRITT 5:
services/main_db_importer.py
enricher/main_extracted_to_db.py
services/main_skill_normalizer.py
services/deepseek_api.py
services/aid_generator.py
services/versioning.py
generator/html/html_generator.py
services/master_translator_to_en.py  (EN-HTML via Stufe 2)
enricher/search_enricher.py
enricher/self_learning_pipeline.py
tasks.py

---

## Abgrenzung zu anderen Pipelines

| Pipeline | Datei | Zweck |
|----------|-------|-------|
| main_pipeline | main_pipeline_controller.py | Einzelnes PDF/DOCX direkt |
| FL-Pipeline | url_fl_importer.py | freelancermap API + PDFs |
| GU-Pipeline | url_gu_importer.py | Gulp API |
| Upload-Pipeline | tasks.process_pdf_task | Django Upload via Browser |

Die FL-Pipeline verwendet `main_db_importer.import_one()` — eine komplett separate
Methode die master_merger, master_post_clean und master_translator_to_de aufruft.
Diese Methode wird von der main_pipeline NICHT verwendet.

---

## Disk-Outputs (nur diese!)
data/extracted/<consultant_dir>/<AID>.txt
data/html_out/<consultant_dir>/<AID>.html
data/html_out/<consultant_dir>/<AID>-short.html
data/html_out/<consultant_dir>/<AID>-en.html      (Stufe 2, async)
data/html_out/<consultant_dir>/<AID>-en-short.html (Stufe 2, async)

Alles andere bleibt im RAM.

---

## DB-Tabellen (Schreibzugriffe)
Consultant              ← Hauptobjekt
ConsultantVersion       ← Versionierung
ConsultantDirectory     ← Verzeichnis-Verwaltung
Language                ← Sprachen (global)
ConsultantLanguage      ← Sprachen pro Consultant
Skill                   ← Skills (global, frequency++)
SkillCategory           ← Kategorien (nur lesen)
ConsultantSkill         ← Skills pro Consultant (mit weight)
Certification           ← Zertifikate (global)
ConsultantCertification ← Zertifikate pro Consultant
Education               ← Ausbildung/Schulungen pro Consultant
Experience              ← Projekte pro Consultant
ExperienceActivity      ← Tätigkeiten pro Projekt
ExperienceTechnology    ← Technologien pro Projekt (via skill_normalizer)
Industry                ← Branchen (global, frequency++)
ConsultantIndustry      ← Branchen pro Consultant
FocusArea               ← Fachbereiche (global, frequency++)
ConsultantFocusArea     ← Fachbereiche pro Consultant
FocusExperience         ← Produkte/Standards pro Consultant
OtherContent            ← Sonstiges pro Consultant
TrainingTerm            ← Self-Learning (frequency++, confidence++)

---

## AID-Profil Batch-Import (NEU 2026-05-09)

### Management Command
```bash
python3 manage.py import_aid_profiles --limit 10 --sync    # Test synchron
python3 manage.py import_aid_profiles --letter kkk          # Einen Buchstaben
python3 manage.py import_aid_profiles                       # Alle via Celery
```

### get_best_pdf Logik
- AID-*.pdf bevorzugen
- Englische Profile ausschließen (_engl, _en., -en.)
- Neuestes nach mtime (Änderungsdatum) wählen

### Test-Ergebnisse (9 Profile)
Profile:      9  (1 leer wegen LLM-Gruppierer-Problem bei 263 Blöcken)
Skills:       2132
Projekte:     392
TrainingTerms:932
Ø Skills/Profil:  237
Ø Projekte/Profil: 44

### PENDING
⚠️  get_best_pdf → nach mtime sortieren einbauen (aktuell nach Versionsnr)
⚠️  Management Command → echter Upload-Modus via Celery (process_pdf_task)
⚠️  tasks.process_pdf_task → auf main_pipeline_controller umstellen
⚠️  Panzer-Problem: LLM gibt 0 Gruppen bei >250 Blöcken → Chunk-Modus nötig
