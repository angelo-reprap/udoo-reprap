# ABpE Skill-Pipeline — Design-Dokument
Stand: 2026-05-12

## 1. Datenbank-Tabellen und ihre Rollen

### Stammdaten (werden NICHT vom Normalizer beschrieben)
| Tabelle | Inhalt | Wer schreibt |
|---------|--------|--------------|
| cv_extractor_skill | name + category_name (eindeutig) | Self-Learning Pipeline |
| cv_extractor_skillcategory | Kategorie-Definitionen | manuell |
| cv_extractor_trainingterm | term + category (Lernquelle) | Self-Learning Pipeline |

### Berater-Verknüpfungen (werden vom Normalizer beschrieben)
| Tabelle | Inhalt | Wer schreibt |
|---------|--------|--------------|
| cv_extractor_consultantskill | consultant → skill + weight | Normalizer (save_to_db) |
| cv_extractor_experiencetechnology | experience → skill | Normalizer (save_to_db) |

---

## 2. Pipeline-Ablauf
PDF
↓
pre_json (RAM)
extracted_data.skills{}        ← bereits kategorisiert (aus Skill-Tabelle im PDF)
extracted_data.skill_ablage[]  ← bereits kategorisiert (aus Skill-Tabelle im PDF)
extracted_data.experience[].technologies[] ← NICHT kategorisiert (aus Projektbeschreibungen)
↓
main_extracted_to_db
→ schreibt skills{} direkt in ConsultantSkill
→ schreibt Projekte in Experience + ExperienceActivity
↓
main_skill_normalizer.normalize()   ← SYNCHRON — kein LLM
SCHRITT 1: Ist technologies[]-Eintrag bereits in skills{} oder skill_ablage?
JA  → Kategorie übernehmen (pre_json hat Vorrang)
NEIN → weiter
SCHRITT 2: Ist der Term in TrainingTerm DB?
JA  → Kategorie aus DB übernehmen
NEIN → category='Sonstige Skills' + zu unknown_skills[] hinzufügen
unknown_skills Key-Format:
"OSPF.AID-mm_1.2.3.1.exp_42&45.Mustermann.Max"
└─skill─┘ └────AID────┘ └exp_ids┘ └──name──┘
Projekt-Kontext pro unknown Skill (max 3000 Zeichen):
- Grösstes Projekt zuerst   (max 1500 Zeichen)
- Aktuellstes Projekt       (max verbleibende Zeichen)
- Weiteres Projekt          (nur wenn noch > 100 Zeichen frei)
- Wenn Projekt = grösstes UND aktuellstes → nur einmal
→ Gibt zurück: ({skill_name: {category, count}}, unknown_skills[])
↓
main_skill_normalizer.save_to_db()  ← SYNCHRON
→ ConsultantSkill anlegen (consultant → skill + weight)
→ Gewichtungslogik: Monate (50%) + Projektbreite (40%) + Count (10%)
→ ExperienceTechnology anlegen (experience → skill)
→ Skill anlegen wenn neu (category_name='Sonstige Skills' beim Anlegen)
→ NIEMALS Skill.category_name überschreiben wenn bereits gesetzt
↓
┌─────────────────────────────────┬──────────────────────────────────────────┐
│  HAUPTPFAD (synchron, fertig)   │  FORK: process_unknown_skills_task       │
│                                 │        (Celery async, Stufe 2b)          │
│  HTMLGenerator DE               │                                          │
│  TXT                            │  Startet sofort — wartet intern bis      │
│  SearchEnricher → ES            │  Experience-Objekte in DB verfuegbar     │
│  enrich_consultant_task.delay() │  (max 30s DB-Check-Schleife)             │
│    ↓ Stufe 2 (sequenziell)      │                                          │
│    db_enricher (1 LLM-Call)     │  FÜR JEDEN unbekannten Skill:            │
│    skill_graph_builder          │    → Key parsen                          │
│      (2 LLM-Calls)              │    → Experience aus DB holen             │
│    generate_en_html_task        │    → LLM: skill + Projekt-Kontext        │
│      → DE→EN Übersetzung        │      → Kategorie (1 der 28)              │
│      → EN-HTML                  │    → TrainingTerm anlegen                │
│                                 │      (source='self_learning_llm',        │
│                                 │       confidence=0.80)                   │
│                                 │    → Skill.category_name aktualisieren   │
│                                 │      (nur wenn 'Sonstige Skills')        │
│                                 │    → ConsultantSkill.category_name       │
│                                 │      + weight aktualisieren              │
│                                 │    → Gewichtung NEU berechnen            │
│                                 │  HTML DE + EN neu generieren             │
└─────────────────────────────────┴──────────────────────────────────────────┘
↓ (Berater sofort nach synchronem Lauf verfügbar)

---

## 3. LLM Rate Limiter (llm_rate_limiter.py)
Redis Semaphore — verhindert Überschreitung DeepSeek API Limit (max 10 parallel)
max_slots = settings.json["pipeline"]["parallel_workers_projects"]  # = 10
(kein hardcoded Abzug — alle Calls laufen durch denselben Zähler)
Alle LLM-Calls nutzen llm_slot():
db_enricher              → with llm_slot(label='db_enricher'):
skill_graph_builder nodes → with llm_slot(label='skill_graph_builder:nodes'):
skill_graph_builder edges → with llm_slot(label='skill_graph_builder:edges'):
self_learning            → with llm_slot(label='self_learning:{skill}'):
Verhalten:

Slot frei  → sofort belegen + LLM-Call
Slot voll  → warten (0.5s Intervall, max 120s)
Nach Call  → Slot freigeben (auch bei Exception)
TTL: 300s  → Schutz gegen Leaks bei Prozessabsturz


---

## 4. Gewichtung (läuft ZWEIMAL)
weight = (month_score * 0.50) + (proj_score * 0.40) + (count_score * 0.10)
month_score:  >= 60 Monate → 1.0  |  >= 36 → 0.85  |  >= 12 → 0.70  |  >= 6 → 0.50  |  < 6 → 0.30
proj_score:   >= 5 Projekte → 1.0 |  >= 3  → 0.75  |  >= 2  → 0.50  |  1    → 0.25
count_score:  >= 10 → 1.0         |  >= 5  → 0.75  |  >= 2  → 0.50  |  1    → 0.25
Lauf 1 (synchron):  category='Sonstige Skills' — vorläufiges Gewicht
Lauf 2 (async):     korrekte Kategorie — finales Gewicht wird aktualisiert

---

## 5. LLM-Kontext für Self-Learning
Skill: OSPF
Berater: Mustermann Max (AID-mm_1.2.3.1)
Projekt-Kontext:
Projekt: Maroc Telekom (09/2008 – 02/2009)
Rolle: Network Engineer
Aktivitaeten: Troubleshooting WAN/LAN, Routing-Konfiguration
Technologien: BGP, EIGRP, RIP, Cisco Router 1700, ASA 5505
Projekt: Telekom AG (01/2010 – 06/2011)
...
KATEGORIEN: [dynamisch aus SkillCategory DB geladen]
→ Antworte NUR mit JSON: {"category": "Netzwerkprotokolle"}

---

## 6. Regeln

| Regel | Beschreibung |
|-------|-------------|
| R1 | Normalizer schreibt NICHT in TrainingTerm |
| R2 | Normalizer überschreibt NICHT Skill.category_name wenn bereits gesetzt |
| R3 | Self-Learning ist der EINZIGE der TrainingTerm schreibt |
| R4 | Self-Learning aktualisiert Skill.category_name + ConsultantSkill wenn category='Sonstige Skills' |
| R5 | pre_json.skills{} hat immer Vorrang vor TrainingTerm |
| R6 | Gewichtungslogik läuft synchron (vorläufig) + async (final nach LLM) |
| R7 | Berater ist sofort nach synchronem Lauf verfügbar — kein Warten auf LLM |
| R8 | Alle LLM-Calls laufen durch llm_rate_limiter (max 10 parallel, Redis) |
| R9 | Self-Learning wartet auf Experience-Objekte in DB (max 30s) |

---

## 7. Zeitersparnis

| Variante | Zeit im Hauptpfad |
|----------|-------------------|
| Alt (LLM blockiert) | +30-60s pro unbekanntem Skill |
| Neu (Fire-and-Forget) | 0s — sofort fertig |

Bei 20 unbekannten Skills: **statt ~10-20 Minuten Wartezeit → sofort verfügbar**
Self-Learning läuft unbemerkt im Hintergrund und verfeinert die Daten.

---

## 8. Implementierte Dateien

| Datei | Status | Beschreibung |
|-------|--------|--------------|
| services/main_skill_normalizer.py | ✅ FERTIG | normalize() gibt (result, unknown_skills) zurück |
| services/llm_rate_limiter.py | ✅ NEU | Redis Semaphore, max 10 Slots |
| enricher/self_learning_pipeline.py | ✅ NEU | process() + process_unknown_skills() |
| tasks.py | ✅ ERWEITERT | process_unknown_skills_task (Stufe 2b) |
| services/main_db_importer.py | ✅ ERWEITERT | unknown_skills → Task.delay() |
| enricher/db_enricher.py | ✅ ERWEITERT | with llm_slot() |
| enricher/skill_graph_builder.py | ✅ ERWEITERT | with llm_slot() x2 |

---

## 9. Offene Punkte

- [ ] self_learning_pipeline.py Zeile 85: workers - 2 entfernen (auf workers ändern)
- [ ] llm_rate_limiter.py Kommentar Zeile 8+34: "-2" aus Kommentar entfernen
- [ ] SearchEnricher nach Self-Learning aufrufen (ES-Index aktualisieren)
- [ ] Echter Test mit PDF durchführen
