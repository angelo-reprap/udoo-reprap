# CV Extraktion Master Pipeline — Vollständige Dokumentation
**Stand: 02. Mai 2026**  
**System: UCS5 — `/opt/abpe/backend/`**

---

## 1. Übersicht

Die CV Extractor Pipeline importiert Freelancer-Profile von Freelancermap.de (und anderen Plattformen), extrahiert strukturierte Daten aus PDFs und der API, normalisiert Skills, und speichert alles in der Datenbank. Das Ergebnis ist ein vollständiges Qualifikationsprofil als HTML, TXT und DB-Eintrag.

### Gesamtfluss

```
URL (freelancermap.de/profil/xxx)
  ↓
[1] URL Import (profil.json + PDFs herunterladen)
  ↓
[2] PDF Extraktion → Spans im RAM
  ↓
[3] Keyword-Filter (nur relevante PDFs)
  ↓
[4] Master Pipeline (Detector → Labeler → Extractor)
  ↓  pdf_pre_json.json
[5] Merge + Normalize (PDF + API)
  ↓  profil_pre_json.json
[6] DB Import (AID generieren → Skills → Projekte → HTML → TXT)
  ↓
[7] Elasticsearch Index + Self-Learning
```

**Gesamtdauer:** ~3–5 Minuten pro Profil  
**Beispiel Rehsack:** 131s Pipeline + 84s DB = 215s = 3.6 Minuten

---

## 2. Verzeichnisstruktur

### Quelldaten pro Profil
```
/opt/abpe/backend/data/url/fl/<name>/
├── analysis/
│   ├── checksum.json       ← MD5 Checksummen der PDFs
│   ├── keywords.json       ← extrahierte Keywords aus API
│   └── matches.json        ← Keyword-Coverage pro PDF (%)
├── download/
│   ├── 01_<name>.pdf       ← heruntergeladene PDFs (nummeriert)
│   ├── 02_<name>.pdf
│   └── ...
├── extract/                ← leer (yx.txt nicht mehr nötig)
├── import.log              ← Protokoll des Imports
├── profil.json             ← rohe API-Daten von Freelancermap
├── pdf_pre_json.json       ← aus PDFs extrahierte Daten (NEU)
└── profil_pre_json.json    ← merged + normalized (finale Eingabe für DB)
```

### Ausgabedaten
```
/opt/abpe/backend/data/extracted/<name>/
└── AID-xx_x.x.x.x.txt     ← TXT-Export des Profils

/opt/abpe/backend/data/cv/aid/<AID>/
└── profile.html            ← HTML-Profil (generiert)
```

### Beispiele
```
/opt/abpe/backend/data/url/fl/rehsack_jens/
/opt/abpe/backend/data/url/fl/nagy_tamas/
/opt/abpe/backend/data/extracted/rehsack_jens/AID-jr_3.5.4.9.txt
/opt/abpe/backend/data/extracted/nagy_tamas/AID-tn_2.5.2.5.txt
```

---

## 3. Programme und Dateien

### 3.1 Upload & Web-Interface

| Datei | Pfad | Funktion |
|-------|------|----------|
| Upload-View | `/opt/abpe/backend/apps/cv_extractor/views/upload.py` | Django View für Upload-Seite |
| Upload-Template | `/opt/abpe/backend/apps/cv_extractor/templates/cv_extractor/upload.html` | HTML Upload-Formular |
| URL-Konfiguration | `/opt/abpe/backend/apps/cv_extractor/urls.py` | Django URL-Routing |

**URL:** `https://abpe.win.abcona.info/cv-extractor/upload/`

### 3.2 Celery Tasks

| Datei | Pfad | Funktion |
|-------|------|----------|
| Tasks | `/opt/abpe/backend/apps/cv_extractor/tasks.py` | Celery Tasks (process_pdf, batch_process, enrich_consultant) |
| Celery Config | `/opt/abpe/backend/abpe_backend/celery_app.py` | Celery Konfiguration |

**Log:** `/opt/abpe/logs/celery.log`  
**Neustart:** `supervisorctl restart abpe-celery`

### 3.3 URL Import (Stufe 1)

| Datei | Pfad | Funktion |
|-------|------|----------|
| **url_fl_importer.py** | `/opt/abpe/backend/apps/cv_extractor/services/url_fl_importer.py` | Haupt-Pipeline: Download + Extraktion + Master Pipeline |

**Kernfunktionen:**
- `url_importer.run(url, vorname, nachname)` — kompletter Import von URL
- `url_importer._run_freelancermap(...)` — interne Pipeline
- `run_master_pipeline_from_spans(spans, first, last)` — Master Pipeline RAM-basiert

**Was es macht:**
1. Session-Cookies laden (Freelancermap Login)
2. `profil.json` von API holen
3. Alle Anhänge (PDFs) herunterladen → `download/`
4. Spans aus PDFs extrahieren (inkl. OCR-Fallback)
5. `analysis/keywords.json` + `analysis/matches.json` erstellen
6. **PDF-Filter:** nur PDFs mit >20% Keyword-Coverage
7. Master Pipeline für gefilterte PDFs starten
8. `pdf_pre_json.json` speichern
9. Mit API-Daten mergen → `profil_pre_json.json`

### 3.4 PDF Extraktion

| Datei | Pfad | Funktion |
|-------|------|----------|
| **pdf_extractor.py** | `/opt/abpe/backend/apps/cv_extractor/services/pdf_extractor.py` | PDF → Spans (mit OCR-Fallback) |

**Was es macht:**
- Normales PDF: Text-Layer direkt lesen → Spans mit `x0, x1, y, size, bold, font`
- OCR-PDF (kein Text-Layer): Tesseract OCR → Spans mit `x, y, size`
- Gibt `PDFResult` zurück mit `result.spans`

**Span-Felder:**
```python
{
  'page': int,     # Seitennummer
  'y': int,        # Y-Position
  'x': int,        # X-Position  
  'size': float,   # Schriftgröße
  'bold': bool,    # Fett
  'italic': bool,  # Kursiv
  'font': str,     # Fontname
  'text': str,     # Textinhalt
  'width': float,  # Breite (float! wegen OCR-Kompatibilität)
}
```

**Wichtiger Fix (OCR):**
```python
# OCR Spans haben x0=None → float() Schutz
'width': float(getattr(s, 'x1', 0) or 0) - float(getattr(s, 'x0', 0) or 0)
```

### 3.5 Master Detector

| Datei | Pfad | Funktion |
|-------|------|----------|
| **master_detector.py** | `/opt/abpe/backend/apps/cv_extractor/services/master_detector.py` | Spans → Gruppen (CV-Struktur erkennen) |

**Kernfunktion:** `master_detector.detect_from_spans(spans, debug_dir=None)`

**Pipeline intern:**
```
Spans → Zeilen → Blöcke → CV-Struktur-Analyse
  → LLM Gruppierung → Format-Split → Quality-Check
  → Gruppen (Liste von Projektgruppen)
```

**Wichtiger Fix (quality_check):**
```python
# LLM gibt manchmal "G001" statt 1 zurück
raw = str(k.get('gruppe', '0')).lstrip('G').lstrip('0') or '0'
idx = int(raw) - 1
```

### 3.6 Master Labeler

| Datei | Pfad | Funktion |
|-------|------|----------|
| **master_labeler.py** | `/opt/abpe/backend/apps/cv_extractor/services/master_labeler.py` | Gruppen → Labels (PROJECT, SKILLS, PERSONAL, ...) |

**Kernfunktion:** `BlockLabeler().label(gruppen)`

**Labels:**
`HEADER, PERSONAL, PROJECT, SKILLS, BRANCHEN, FACHBEREICHE, ZERTIFIKATE, SCHULUNGEN, FOCUS_EXP, OTHER`

### 3.7 Master Extractor (parallel LLM)

Eingebaut in `url_fl_importer.py` → `run_master_pipeline_from_spans()`

**Was es macht:**
- Für jede gelabelte Gruppe → LLM Extraktion parallel
- Projekte: Datum, Firma, Rolle, Skills, Beschreibung
- Skills: nach Kategorien sortiert
- Gibt `pdf_pre_json` zurück

### 3.8 DB Import (Stufe 2)

| Datei | Pfad | Funktion |
|-------|------|----------|
| **url_fl_db_importer.py** | `/opt/abpe/backend/apps/cv_extractor/services/url_fl_db_importer.py` | profil_pre_json → Datenbank |

**Kernfunktion:** `fl_db_importer.import_one(dir_name)`

**Was es macht:**
1. `profil_pre_json.json` lesen
2. Wenn fehlt → Auto-Pipeline starten (ruft `_run_freelancermap` auf)
3. AID generieren (LLM-basiert: Rolle + Landschaft + Level)
4. Daten in DB speichern (Projekte, Skills, Zertifikate, Ausbildung)
5. SkillNormalizer: Skills kategorisieren + Gewichte berechnen
6. HTML generieren → `data/cv/aid/<AID>/profile.html`
7. TXT generieren → `data/extracted/<name>/AID-xx.txt`
8. Elasticsearch indexieren
9. Self-Learning Pipeline

### 3.9 AID Generator

| Datei | Pfad | Funktion |
|-------|------|----------|
| **aid_generator.py** | `/opt/abpe/backend/apps/cv_extractor/services/aid_generator.py` | AID-Code generieren |

**AID-Format:** `AID-<kürzel>_<rolle>.<landschaft>.<level>.<version>`

**Beispiel:** `AID-jr_3.5.4.9`
- `jr` = Jens Rehsack
- `3` = Architekt
- `5` = Embedded/IoT
- `4` = Senior Experte
- `9` = Version 9

### 3.10 Skill Normalizer

| Datei | Pfad | Funktion |
|-------|------|----------|
| **skill_normalizer.py** | `/opt/abpe/backend/apps/cv_extractor/services/skill_normalizer.py` | Skills kategorisieren + Gewichte |

**Kategorien (28):** CI/CD, Testing, Versionsverwaltung, Dokumentation, Cloud, Datenbanken, Betriebssysteme, Hardware, Frameworks, Programmiersprachen, ...

**Gewichtungsformel:**
```python
weight = min(0.95, 0.3 + (count/10) + (monate/200))
```

---

## 4. Datenfluss Detail

### 4.1 profil.json (API-Rohdaten)
```json
{
  "url": "https://www.freelancermap.de/profil/...",
  "person": {"familyName": "...", "givenName": "..."},
  "address": {"addressLocality": "...", "postalCode": "..."},
  "profile": {
    "references": [...],     ← Projekte
    "certificates": [...],   ← Zertifikate
    "attachments": [...],    ← PDF-Links
    "skills": "...",         ← HTML-Text
    "graduation": "..."      ← Abschluss
  }
}
```

### 4.2 pdf_pre_json.json (aus PDFs)
```json
{
  "extracted_data": {
    "experience": [
      {
        "zeitraum": "05/2024 – 03/2025",
        "firma": "...",
        "rolle": "...",
        "skills": ["C++", "Linux", ...],
        "beschreibung": "..."
      }
    ],
    "skills": {"Programmiersprachen": ["C++", "Python"], ...},
    "personal": {"name": "...", "ort": "..."}
  }
}
```

### 4.3 profil_pre_json.json (merged + normalized)
Kombination aus `pdf_pre_json.json` + `profil.json`:
- Projekte: PDF-Daten bevorzugt, API als Fallback
- Skills: aus beiden Quellen zusammengeführt
- Persönliche Daten: API + PDF
- Zertifikate: aus API
- Ausbildung: aus API + PDF

---

## 5. PDF-Keyword-Filter

**Ziel:** Nur relevante PDFs (Lebenslauf, nicht Zeugnisse) in die Master Pipeline.

**Logik in `url_fl_importer.py`:**
```python
# matches.json enthält Coverage pro PDF
high_score = [f for f in all_pdfs
              if matches.get(f.name, {}).get('coverage_percent', 0) >= 20]

if not high_score:
    # Fallback: bestes PDF nehmen
    best = max(all_pdfs, key=lambda f: matches.get(f.name, {}).get('coverage_percent', 0))
    pdf_files = [best]
else:
    pdf_files = high_score
```

**Beispiel Nagy:**
```
13_Lebenslauf-TN-upd2.pdf:    71.1% ← ✅ nehmen
12_Europass:                  34.2% ← ✅ nehmen
11_Anschreiben-rev5.pdf:      23.7% ← ✅ nehmen
08_Coverletter-rev2.pdf:      23.7% ← ✅ nehmen
07_Lebenslauf-unterschrift:   15.8% ← ❌ raus
01-06, 09, 10:                <10%  ← ❌ raus (Zeugnisse, Referenzen)
```

---

## 6. Getestete Profile

### Rehsack Jens — AID-jr_3.5.4.9 ✅
```
PDFs:        1 PDF (Hauptlebenslauf)
Spans:       1355 Spans
Gruppen:     54
Projekte:    30
Skills:      408
Branchen:    13
Dauer:       3.6 Minuten (131s + 84s DB)

Dateien:
  /opt/abpe/backend/data/url/fl/rehsack_jens/pdf_pre_json.json     (58KB)
  /opt/abpe/backend/data/url/fl/rehsack_jens/profil_pre_json.json  (63KB)
  /opt/abpe/backend/data/extracted/rehsack_jens/AID-jr_3.5.4.9.txt (14KB)
```

### Nagy Tamas — AID-tn_2.5.2.x ⚠️
```
PDFs:        13 PDFs (Zeugnisse + Lebenslauf gemischt)
Filter:      4 PDFs >20% Keywords
Problem:     Pipeline crasht bei 08_Coverletter (G001 Bug im quality_check)
Status:      Nur API-Daten (10 Projekte, 0 Skills aus PDF)
Letzter Fix: G001 → int() Fix in master_detector.py

Dateien:
  /opt/abpe/backend/data/url/fl/nagy_tamas/profil.json              (30KB)
  /opt/abpe/backend/data/url/fl/nagy_tamas/profil_pre_json.json     (9KB)
  /opt/abpe/backend/data/extracted/nagy_tamas/AID-tn_2.5.2.5.txt
```

---

## 7. Alle Fixes (chronologisch)

### Fix 1: OCR Span width (url_fl_importer.py)
```python
# Problem: OCR Spans haben x0=None oder x0=''
# Alt:
'width': getattr(s, 'x1', 0) - getattr(s, 'x0', 0)
# Fix:
'width': float(getattr(s, 'x1', 0) or 0) - float(getattr(s, 'x0', 0) or 0)
```

### Fix 2: quality_check G001 (master_detector.py)
```python
# Problem: LLM gibt "G001" statt 1 zurück bei kleinen CVs
# Alt:
idx = int(k.get('gruppe', 0)) - 1
# Fix:
raw = str(k.get('gruppe', '0')).lstrip('G').lstrip('0') or '0'
idx = int(raw) - 1
```

### Fix 3: PDF-Keyword-Filter (url_fl_importer.py)
```python
# Problem: Alle 13 PDFs → 2038 Spans → master_detector findet 0 Gruppen
# Fix: nur PDFs mit >20% Keyword-Coverage nehmen
```

### Fix 4: Auto-Pipeline in import_one (url_fl_db_importer.py)
```python
# Problem: import_one() crashed wenn profil_pre_json.json fehlt
# Fix: wenn profil.json vorhanden → _run_freelancermap() automatisch aufrufen
```

### Fix 5: detect_from_spans() (master_detector.py)
```python
# Neue RAM-basierte Methode statt Datei-basiert
master_detector.detect_from_spans(spans, debug_dir=None)
```

### Fix 6: analyze_from_spans() (master_structure_analyzer.py)
```python
# Neue RAM-basierte Methode
analyzer.analyze_from_spans(spans)
```

---

## 8. Architektur: RAM vs. Disk

### Alt (vor dieser Session):
```
PDF → yx.txt (Disk) → BlockDetector (liest Datei) → Gruppen
```

### Neu (nach dieser Session):
```
PDF → Spans (RAM) → detect_from_spans() → Gruppen
                                        → pdf_pre_json.json (Disk, nur einmal)
```

**Vorteile:**
- Kein temporäres yx.txt mehr nötig
- `extract/` Verzeichnis bleibt leer
- Schneller (kein Disk I/O)
- Sauberer Code

---

## 9. Pending / Noch zu tun

### 🔴 Kritisch
1. **Nagy PDF-Pipeline testen** — G001 Fix testen, ob jetzt Skills aus PDF extrahiert werden
2. **Coverletter-Filter** — Coverletter sollte auch gefiltert werden (hat keine Projektdaten)

### 🟡 Wichtig
3. **Nagy Skills** — nach erfolgreicher Pipeline: 0 Skills → sollte >50 Skills haben
4. **Andere Profile testen:**
   - `AID-vm` (Mikhaylov) — noch nicht importiert
   - `AID-tt` (Troschke) — noch nicht importiert
5. **Keyword-Filter Schwellwert** — 20% ist gut für Nagy, aber allgemein prüfen

### 🟢 Nice to have
6. **10_Delphi-XE10-VCL-compr.pdf** — Screenshot-PDF, 0 Spans, nicht extrahierbar
   → Besserer OCR oder einfach ignorieren
7. **Europass-Format** — spezifischer Parser für Europass-CVs
8. **Version-Cleanup** — alte Versionen (2.5.2.1 bis 2.5.2.4) löschen
9. **Batch-Import** — mehrere Profile auf einmal importieren

### 🔵 Langfristig
10. **Self-Learning verbessern** — bei Nagy: 0 terms_created (weil keine PDF-Skills)
11. **Skill-Duplikate** — "GitHub Actions" + "Github-Pipelines" = gleich → zusammenführen
12. **Branchen-Erkennung verbessern** — Nagy hat nur 1 Branche (sollte mehr haben)

---

## 10. Wichtige Befehle

### Import starten (Shell)
```bash
cd /opt/abpe/backend
source /opt/abpe/venv311/bin/activate

python3 manage.py shell << 'EOF'
from apps.cv_extractor.services.url_fl_db_importer import fl_db_importer
result = fl_db_importer.import_one('nagy_tamas')
print(result)
EOF
```

### Pipeline neu starten (alte Daten löschen)
```bash
python3 manage.py shell << 'EOF'
from pathlib import Path
for f in ['profil_pre_json.json', 'pdf_pre_json.json']:
    p = Path('data/url/fl/nagy_tamas/' + f)
    if p.exists(): p.unlink(); print(f"Gelöscht: {f}")

from apps.cv_extractor.services.url_fl_db_importer import fl_db_importer
result = fl_db_importer.import_one('nagy_tamas')
print(result)
EOF
```

### Logs live verfolgen
```bash
tail -f /opt/abpe/logs/celery.log
tail -f /opt/abpe/logs/django.log
```

### Services neu starten
```bash
supervisorctl restart all
supervisorctl restart abpe-celery
supervisorctl restart abpe-django
```

### Keyword-Coverage anschauen
```bash
cat /opt/abpe/backend/data/url/fl/nagy_tamas/analysis/matches.json | python3 -c "
import json,sys
d=json.load(sys.stdin)
for k,v in sorted(d.items(), key=lambda x: -x[1]['coverage_percent']):
    print(f'{v[\"coverage_percent\"]:5.1f}%  {k}')
"
```

---

## 11. Modell / Datenbank

**LLM:** DeepSeek API (Remote)  
**Lokales LLM:** Ollama `qwen2.5:7b` (für einfache Tasks)  
**Datenbank:** PostgreSQL (Django ORM)  
**Suche:** Elasticsearch 8.11.0  

### Wichtige Django Models
```
apps/cv_extractor/models/
├── Consultant          ← Hauptprofil
├── Project             ← Projekte
├── Skill               ← Skills mit Gewicht
├── Certificate         ← Zertifikate
├── Education           ← Ausbildung
└── CVVersion           ← Versionierung (AID)
```

---

*Dokumentation erstellt am 02.05.2026*  
*Pipeline-Version: RAM-basiert (ohne yx.txt)*



