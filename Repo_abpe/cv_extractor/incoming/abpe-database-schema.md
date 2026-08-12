# ABPE Database Schema — cv_extractor
**Stand:** 2026-05-03 | **DB:** abpe_db | **Server:** ucs5 | **User:** abpe

---

## Übersicht: Alle 31 Tabellen

| Tabelle | Zeilen | Typ |
|---------|--------|-----|
| cv_extractor_consultant | 105 | Zentrale Entität |
| cv_extractor_consultantskill | 19.844 | Verknüpfung |
| cv_extractor_skill | 6.781 | Global |
| cv_extractor_skillcategory | 28 | Stammdaten |
| cv_extractor_experience | 1.508 | Pro Consultant |
| cv_extractor_experienceactivity | 3.500 | Pro Experience |
| cv_extractor_experiencetechnology | 8.269 | Verknüpfung |
| cv_extractor_education | 433 | Pro Consultant |
| cv_extractor_consultantcertification | 816 | Verknüpfung |
| cv_extractor_certification | 197 | Global |
| cv_extractor_issuer | 32 | Global |
| cv_extractor_consultantindustry | 805 | Verknüpfung |
| cv_extractor_industry | 185 | Global |
| cv_extractor_consultantfocusarea | 174 | Verknüpfung |
| cv_extractor_focusarea | 167 | Global |
| cv_extractor_focusexperience | 811 | Pro Consultant |
| cv_extractor_consultantlanguage | 228 | Verknüpfung |
| cv_extractor_language | 42 | Global |
| cv_extractor_consultantmatching | 90 | Pro Consultant |
| cv_extractor_consultantstatistics | 90 | Pro Consultant |
| cv_extractor_consultantdirectory | 41 | Versionierung |
| cv_extractor_consultantversion | 224 | Versionierung |
| cv_extractor_uploadedpdf | 109 | Upload-Queue |
| cv_extractor_prompttemplate | 105 | LLM-Prompts |
| cv_extractor_trainingterm | 2.749 | Self-Learning |
| cv_extractor_skillrelation | 798 | Skill-Graph |
| cv_extractor_extractionjob | 17 | Legacy |
| cv_extractor_extractionlog | 17 | Legacy |
| cv_extractor_extractionrule | 0 | Leer |
| cv_extractor_extractedcv | 0 | Leer |
| cv_extractor_jsonexport | 0 | Leer |

---

## ⚠️ Bekanntes Design-Problem

**cv_extractor_consultantskill hat KEIN eigenes category_name Feld.**

Die Kategorie liegt ausschließlich in cv_extractor_skill.category_name (global).
Ändert man die Kategorie eines Skills, betrifft das ALLE Consultants mit diesem Skill.

Beispiel ARM: frequency=16, category_name="Programmiersprachen"
Betrifft: AID-jr (Rehsack 4x) + AID-tn (Nagy DE+EN)

Lösung: category_name direkt in cv_extractor_consultantskill (Migration siehe unten).

---

## Detaillierte Tabellen

### 1. cv_extractor_consultant (105 Zeilen)
Zentrale Entität — DE + optional EN pro Berater

| Spalte | Typ | Nullable | Beschreibung |
|--------|-----|----------|--------------|
| id | bigint | NO | PK |
| aid | varchar(50) | NO | UNIQUE z.B. AID-tn_2.3.2.15 |
| version | varchar(20) | NO | z.B. 2.3.2.15 |
| consultant_dir | varchar(200) | NO | z.B. nagy_tamas |
| first_name | varchar(100) | NO | |
| last_name | varchar(100) | NO | |
| birth_year | integer | YES | |
| nationality | varchar(100) | NO | |
| degree | varchar(200) | NO | Höchster Abschluss |
| email | varchar(500) | NO | Mehrere mit ; getrennt |
| phone | varchar(300) | NO | Mehrere mit ; getrennt |
| website | varchar(500) | NO | Mehrere mit ; getrennt |
| location | varchar(200) | NO | |
| headline | text | NO | |
| summary | text | NO | |
| availability | varchar(100) | NO | |
| edv_experience_since | integer | YES | Jahr seit EDV-Erfahrung |
| company | varchar(200) | NO | |
| address | varchar(300) | NO | |
| stand | varchar(50) | NO | Datum des Profils |
| status | varchar(30) | NO | pending/completed/enriched |
| error_message | text | NO | |
| hourly_rate | integer | YES | EUR |
| placement_text | varchar(100) | NO | |
| language | varchar(5) | NO | de oder en |
| aid_base | varchar(50) | NO | AID des DE-Profils (nur EN) |
| source_type | varchar(50) | NO | upload/fl/gu |
| source_filename | varchar(500) | NO | |
| source_filesize | integer | NO | |
| source_import_id | varchar(100) | NO | |
| pipeline_version | varchar(20) | NO | |
| pipeline_step | varchar(50) | NO | extracted/enriched/validated |
| pipeline_extractor | varchar(50) | NO | |
| pipeline_model | varchar(50) | NO | |
| pipeline_self_learning | boolean | NO | |
| duplicate_exists | boolean | NO | |
| duplicate_message | text | NO | |
| processing_time_ms | integer | NO | |
| created_at | timestamptz | NO | |
| updated_at | timestamptz | NO | |
| created_by | varchar(200) | NO | |
| master_json_export | jsonb | NO | Export-Cache |
| extracted_json_export | jsonb | NO | Export-Cache |
| raw_text | text | NO | |

---

### 2. cv_extractor_skill (6.781 Zeilen)
Globale Skill-Stammdaten — NICHT pro Consultant

| Spalte | Typ | Nullable | Beschreibung |
|--------|-----|----------|--------------|
| id | bigint | NO | PK |
| name | varchar(200) | NO | UNIQUE z.B. ARM |
| category_name | varchar(100) | NO | z.B. Programmiersprachen — GLOBAL! |
| frequency | integer | NO | Häufigkeit über alle Consultants |
| confidence | double | NO | |
| created_at | timestamptz | NO | |
| updated_at | timestamptz | NO | |
| category_id | bigint | YES | FK → cv_extractor_skillcategory |

---

### 3. cv_extractor_consultantskill (19.844 Zeilen)
Verknüpfung Consultant-Skill mit Gewichtung
FEHLT: eigenes category_name — kommt derzeit von skill.category_name

| Spalte | Typ | Nullable | Beschreibung |
|--------|-----|----------|--------------|
| id | bigint | NO | PK |
| consultant_id | bigint | NO | FK → cv_extractor_consultant |
| skill_id | bigint | NO | FK → cv_extractor_skill |
| weight | double | NO | 0.0-1.0 pro Consultant individuell |
| last_used_year | integer | YES | |
| created_at | timestamptz | NO | |

UNIQUE: (consultant_id, skill_id)

---

### 4. cv_extractor_skillcategory (28 Zeilen)
Die 27+1 Skill-Kategorien

| Spalte | Typ | Nullable | Beschreibung |
|--------|-----|----------|--------------|
| id | bigint | NO | PK |
| name | varchar(100) | NO | UNIQUE z.B. Programmiersprachen |
| description | text | NO | |
| example_terms | jsonb | NO | |
| is_active | boolean | NO | |
| sort_order | integer | NO | |
| created_at | timestamptz | NO | |
| updated_at | timestamptz | NO | |

---

### 5. cv_extractor_experience (1.508 Zeilen)
Projekterfahrungen pro Consultant

| Spalte | Typ | Nullable | Beschreibung |
|--------|-----|----------|--------------|
| id | bigint | NO | PK |
| consultant_id | bigint | NO | FK → cv_extractor_consultant |
| period | varchar(50) | NO | z.B. 01/2023-12/2024 |
| title | varchar(200) | NO | |
| company | varchar(200) | NO | |
| industry | varchar(100) | NO | |
| role | varchar(200) | NO | |
| location | varchar(200) | NO | |
| sort_order | integer | NO | |
| created_at | timestamptz | NO | |

---

### 6. cv_extractor_experienceactivity (3.500 Zeilen)
Tätigkeiten pro Projekt

| Spalte | Typ | Nullable | Beschreibung |
|--------|-----|----------|--------------|
| id | bigint | NO | PK |
| experience_id | bigint | NO | FK → cv_extractor_experience |
| activity_text | text | NO | |
| sort_order | integer | NO | |
| created_at | timestamptz | NO | |

---

### 7. cv_extractor_experiencetechnology (8.269 Zeilen)
Technologien pro Projekt — Experience-Skill Verknüpfung

| Spalte | Typ | Nullable | Beschreibung |
|--------|-----|----------|--------------|
| id | bigint | NO | PK |
| experience_id | bigint | NO | FK → cv_extractor_experience |
| skill_id | bigint | NO | FK → cv_extractor_skill |
| created_at | timestamptz | NO | |

UNIQUE: (experience_id, skill_id)

---

### 8. cv_extractor_education (433 Zeilen)
Ausbildung + Schulungen pro Consultant

| Spalte | Typ | Nullable | Beschreibung |
|--------|-----|----------|--------------|
| id | bigint | NO | PK |
| consultant_id | bigint | NO | FK → cv_extractor_consultant |
| degree | varchar(200) | NO | Abschluss oder Kursname |
| institution | varchar(200) | NO | |
| period | varchar(50) | NO | |
| description | text | NO | |
| education_type | varchar(20) | NO | degree/course/certification |
| issuer | varchar(200) | NO | |
| sort_order | integer | NO | |
| created_at | timestamptz | NO | |

---

### 9. cv_extractor_certification (197 Zeilen)
Globale Zertifikat-Stammdaten

| Spalte | Typ | Nullable | Beschreibung |
|--------|-----|----------|--------------|
| id | bigint | NO | PK |
| name | varchar(200) | NO | UNIQUE |
| issuer_id | bigint | YES | FK → cv_extractor_issuer |
| issuer_name | varchar(100) | NO | |
| created_at | timestamptz | NO | |

---

### 10. cv_extractor_consultantcertification (816 Zeilen)
Verknüpfung Consultant-Certification

| Spalte | Typ | Nullable | Beschreibung |
|--------|-----|----------|--------------|
| id | bigint | NO | PK |
| consultant_id | bigint | NO | FK → cv_extractor_consultant |
| certification_id | bigint | NO | FK → cv_extractor_certification |
| date_obtained | varchar(20) | NO | |
| expiry_date | varchar(20) | NO | |
| created_at | timestamptz | NO | |

UNIQUE: (consultant_id, certification_id)

---

### 11. cv_extractor_issuer (32 Zeilen)
Zertifikat-Aussteller

| Spalte | Typ | Nullable | Beschreibung |
|--------|-----|----------|--------------|
| id | bigint | NO | PK |
| name | varchar(200) | NO | UNIQUE |
| confidence | double | NO | |
| frequency | integer | NO | |
| source | varchar(100) | NO | |
| created_at | timestamptz | NO | |
| updated_at | timestamptz | NO | |

---

### 12. cv_extractor_industry (185 Zeilen)
Globale Branchen-Stammdaten

| Spalte | Typ | Nullable | Beschreibung |
|--------|-----|----------|--------------|
| id | bigint | NO | PK |
| name | varchar(200) | NO | UNIQUE |
| frequency | integer | NO | |
| created_at | timestamptz | NO | |

---

### 13. cv_extractor_consultantindustry (805 Zeilen)
Verknüpfung Consultant-Industry

| Spalte | Typ | Nullable | Beschreibung |
|--------|-----|----------|--------------|
| id | bigint | NO | PK |
| consultant_id | bigint | NO | FK → cv_extractor_consultant |
| industry_id | bigint | NO | FK → cv_extractor_industry |
| weight | double | NO | 0.0-1.0 |

UNIQUE: (consultant_id, industry_id)

---

### 14. cv_extractor_focusarea (167 Zeilen)
Globale Fachbereiche

| Spalte | Typ | Nullable | Beschreibung |
|--------|-----|----------|--------------|
| id | bigint | NO | PK |
| name | varchar(200) | NO | UNIQUE |
| frequency | integer | NO | |
| created_at | timestamptz | NO | |

---

### 15. cv_extractor_consultantfocusarea (174 Zeilen)
Verknüpfung Consultant-FocusArea

| Spalte | Typ | Nullable | Beschreibung |
|--------|-----|----------|--------------|
| id | bigint | NO | PK |
| consultant_id | bigint | NO | FK → cv_extractor_consultant |
| focus_area_id | bigint | NO | FK → cv_extractor_focusarea |
| weight | double | NO | |

UNIQUE: (consultant_id, focus_area_id)

---

### 16. cv_extractor_focusexperience (811 Zeilen)
Produkte/Standards/Erfahrungen pro Consultant

| Spalte | Typ | Nullable | Beschreibung |
|--------|-----|----------|--------------|
| id | bigint | NO | PK |
| consultant_id | bigint | NO | FK → cv_extractor_consultant |
| name | varchar(500) | NO | |
| category | varchar(100) | NO | |
| sort_order | integer | NO | |
| created_at | timestamptz | NO | |

---

### 17. cv_extractor_language (42 Zeilen)
Globale Sprachen-Stammdaten

| Spalte | Typ | Nullable | Beschreibung |
|--------|-----|----------|--------------|
| id | bigint | NO | PK |
| name | varchar(100) | NO | UNIQUE |

---

### 18. cv_extractor_consultantlanguage (228 Zeilen)
Verknüpfung Consultant-Language

| Spalte | Typ | Nullable | Beschreibung |
|--------|-----|----------|--------------|
| id | bigint | NO | PK |
| consultant_id | bigint | NO | FK → cv_extractor_consultant |
| language_id | bigint | NO | FK → cv_extractor_language |
| level | varchar(2) | NO | A1/A2/B1/B2/C1/C2 |

UNIQUE: (consultant_id, language_id)

---

### 19. cv_extractor_consultantmatching (90 Zeilen)
LLM-Matching Scores pro Consultant

| Spalte | Typ | Nullable |
|--------|-----|----------|
| id | bigint | NO |
| consultant_id | bigint | NO |
| overall_score | double | NO |
| skill_match_score | double | NO |
| role_match_score | double | NO |
| industry_match_score | double | NO |
| skill_weights | jsonb | NO |
| role_weights | jsonb | NO |
| industry_weights | jsonb | NO |
| preferred_roles | jsonb | NO |
| preferred_industries | jsonb | NO |
| preferred_locations | jsonb | NO |
| min_experience_years | integer | NO |
| must_have_skills | jsonb | NO |
| nice_to_have_skills | jsonb | NO |
| calculated_at | timestamptz | NO |
| calculated_by | varchar(100) | NO |

---

### 20. cv_extractor_consultantstatistics (90 Zeilen)
Berechnete Statistiken pro Consultant

| Spalte | Typ | Nullable |
|--------|-----|----------|
| id | bigint | NO |
| consultant_id | bigint | NO |
| total_experience_years | integer | NO |
| total_months | integer | NO |
| project_count | integer | NO |
| skill_count | integer | NO |
| unique_categories | integer | NO |
| top_skills | jsonb | NO |
| certification_count | integer | NO |
| top_certifications | jsonb | NO |
| placement_probability | double | NO |
| market_value_estimate | integer | NO |
| demand_index | double | NO |
| calculated_at | timestamptz | NO |

---

### 21. cv_extractor_consultantdirectory (41 Zeilen)
Verzeichnis-Verwaltung mit Namensvetter-Suffix

| Spalte | Typ | Nullable | Beschreibung |
|--------|-----|----------|--------------|
| id | bigint | NO | PK |
| directory_name | varchar(200) | NO | UNIQUE z.B. nagy_tamas |
| normalized_name | varchar(200) | NO | |
| suffix | integer | NO | 0=kein Suffix, 2,3 für Namensvetter |
| version | varchar(20) | NO | |
| last_used | timestamptz | NO | |
| created_at | timestamptz | NO | |

---

### 22. cv_extractor_consultantversion (224 Zeilen)
Versionsverwaltung

| Spalte | Typ | Nullable |
|--------|-----|----------|
| id | bigint | NO |
| aid | varchar(50) | NO |
| consultant_dir | varchar(200) | NO |
| version | varchar(20) | NO |
| file_path | varchar(500) | NO |
| checksum | varchar(64) | NO |
| created_at | timestamptz | NO |

UNIQUE: (consultant_dir, version)

---

### 23. cv_extractor_uploadedpdf (109 Zeilen)
Upload-Queue für async Celery-Verarbeitung

| Spalte | Typ | Nullable | Beschreibung |
|--------|-----|----------|--------------|
| id | bigint | NO | PK |
| file | varchar(100) | NO | Dateipfad |
| filename | varchar(500) | NO | Originaldateiname |
| first_name | varchar(100) | NO | |
| last_name | varchar(100) | NO | |
| target_directory | varchar(200) | NO | |
| target_version | varchar(20) | NO | |
| action_type | varchar(20) | NO | new/new_version/update |
| status | varchar(20) | NO | uploaded/processing/completed/failed |
| error_message | text | NO | |
| aid | varchar(50) | NO | gesetzt nach Verarbeitung |
| version | varchar(20) | NO | |
| consultant_dir | varchar(200) | NO | |
| task_id | varchar(100) | NO | Celery Task ID |
| created_at | timestamptz | NO | |
| updated_at | timestamptz | NO | |
| consultant_id | integer | YES | FK-lose Referenz |

---

### 24. cv_extractor_prompttemplate (105 Zeilen)
LLM-Prompts in der DB

| Spalte | Typ | Nullable | Beschreibung |
|--------|-----|----------|--------------|
| id | bigint | NO | PK |
| stage | varchar(100) | NO | UNIQUE z.B. extract_personal |
| name | varchar(200) | NO | |
| prompt_text | text | NO | |
| schema | jsonb | NO | |
| target_path | varchar(200) | NO | |
| description | text | NO | |
| version | varchar(20) | NO | |
| is_active | boolean | NO | |
| updated_by | varchar(50) | NO | |
| trained_on_count | integer | NO | |
| created_at | timestamptz | NO | |
| updated_at | timestamptz | NO | |

---

### 25. cv_extractor_trainingterm (2.749 Zeilen)
Self-Learning: erkannte Terme mit Frequenzen

| Spalte | Typ | Nullable |
|--------|-----|----------|
| id | bigint | NO |
| term | varchar(200) | NO |
| category | varchar(100) | NO |
| confidence | double | NO |
| frequency | integer | NO |
| source | varchar(100) | NO |
| is_technology_category | boolean | NO |
| in_prompt | boolean | NO |
| created_at | timestamptz | NO |
| updated_at | timestamptz | NO |

---

### 26. cv_extractor_skillrelation (798 Zeilen)
Globaler Skill-Graph

| Spalte | Typ | Nullable | Beschreibung |
|--------|-----|----------|--------------|
| id | bigint | NO | PK |
| term_from | varchar(200) | NO | |
| term_to | varchar(200) | NO | |
| relation_type | varchar(20) | NO | synonym/related/specialization |
| weight | double | NO | |
| frequency | integer | NO | |
| confidence | double | NO | |
| source | varchar(100) | NO | |
| created_at | timestamptz | NO | |
| updated_at | timestamptz | NO | |

UNIQUE: (term_from, term_to, relation_type)

---

### 27-31. Legacy / Leer

| Tabelle | Zeilen | Status |
|---------|--------|--------|
| cv_extractor_extractionjob | 17 | Legacy |
| cv_extractor_extractionlog | 17 | Legacy |
| cv_extractor_extractionrule | 0 | Leer |
| cv_extractor_extractedcv | 0 | Leer |
| cv_extractor_jsonexport | 0 | Leer |

---

## Foreign Keys (alle 23)

| Von Tabelle | Spalte | Ziel | Zielspalte |
|-------------|--------|------|------------|
| cv_extractor_certification | issuer_id | cv_extractor_issuer | id |
| cv_extractor_consultantcertification | certification_id | cv_extractor_certification | id |
| cv_extractor_consultantcertification | consultant_id | cv_extractor_consultant | id |
| cv_extractor_consultantfocusarea | consultant_id | cv_extractor_consultant | id |
| cv_extractor_consultantfocusarea | focus_area_id | cv_extractor_focusarea | id |
| cv_extractor_consultantindustry | consultant_id | cv_extractor_consultant | id |
| cv_extractor_consultantindustry | industry_id | cv_extractor_industry | id |
| cv_extractor_consultantlanguage | consultant_id | cv_extractor_consultant | id |
| cv_extractor_consultantlanguage | language_id | cv_extractor_language | id |
| cv_extractor_consultantmatching | consultant_id | cv_extractor_consultant | id |
| cv_extractor_consultantskill | consultant_id | cv_extractor_consultant | id |
| cv_extractor_consultantskill | skill_id | cv_extractor_skill | id |
| cv_extractor_consultantstatistics | consultant_id | cv_extractor_consultant | id |
| cv_extractor_education | consultant_id | cv_extractor_consultant | id |
| cv_extractor_experience | consultant_id | cv_extractor_consultant | id |
| cv_extractor_experienceactivity | experience_id | cv_extractor_experience | id |
| cv_extractor_experiencetechnology | experience_id | cv_extractor_experience | id |
| cv_extractor_experiencetechnology | skill_id | cv_extractor_skill | id |
| cv_extractor_extractedcv | job_id | cv_extractor_extractionjob | id |
| cv_extractor_extractionlog | job_id | cv_extractor_extractionjob | id |
| cv_extractor_focusexperience | consultant_id | cv_extractor_consultant | id |
| cv_extractor_jsonexport | consultant_id | cv_extractor_consultant | id |
| cv_extractor_skill | category_id | cv_extractor_skillcategory | id |

---

## Geplante Migration: category_name in ConsultantSkill

```sql
-- Schritt 1: Spalte hinzufügen
ALTER TABLE cv_extractor_consultantskill
ADD COLUMN category_name VARCHAR(100) NOT NULL DEFAULT '';

-- Schritt 2: Vorbelegen aus skill.category_name
UPDATE cv_extractor_consultantskill cs
SET category_name = s.category_name
FROM cv_extractor_skill s
WHERE cs.skill_id = s.id;

-- Schritt 3: Prüfen
SELECT category_name, COUNT(*)
FROM cv_extractor_consultantskill
GROUP BY category_name ORDER BY COUNT(*) DESC LIMIT 10;
```

Django models.py Ergänzung in ConsultantSkill:
    category_name = models.CharField(max_length=100, blank=True)  # NEU

Nach Migration: Editor kann Skills per Kategorie-Wechsel verschieben,
ohne andere Consultants zu beeinflussen.

---

Stand: 2026-05-03
Basis: PostgreSQL Information Schema + pg_stat_user_tables
