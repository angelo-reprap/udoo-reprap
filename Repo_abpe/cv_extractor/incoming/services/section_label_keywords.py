"""
section_label_keywords.py
=========================
Gemeinsame Section-/Field-Keywords für CV-Labeling (AID + Gulp).

Herkunft: Gulp keyword detection v1.3 (5652/5666 = 99.75% Dry-Run).
Zweck: regelbasiert MAIN_LABELS setzen (ergänzt LLM in main_labeler /
       master_labeler), ohne Skill-Taxonomie (Java/SAP/…).

Labels (Pipeline):
  HEADER, PERSONAL, FACHBEREICHE, ZERTIFIKATE, SCHULUNGEN,
  BRANCHEN, SKILLS, FOCUS_EXP, EXPERIENCE, PROJECT, OTHER
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

# ── Pipeline-Hauptlabels (identisch zu main_labeler.MAIN_LABELS) ────────────
MAIN_LABELS = [
    "HEADER",
    "PERSONAL",
    "FACHBEREICHE",
    "ZERTIFIKATE",
    "SCHULUNGEN",
    "BRANCHEN",
    "SKILLS",
    "FOCUS_EXP",
    "EXPERIENCE",
    "PROJECT",
    "OTHER",
]

# ── Erstes Wort / Phrasen-Anfang → Label (lowercased keys) ─────────────────
# Erweitert main_labeler.FIRST_WORD_TO_LABEL um Gulp-v1.3-Treffer.
FIRST_WORD_TO_LABEL: Dict[str, str] = {
    # PERSONAL / Stamm
    "stammdaten": "PERSONAL",
    "personendaten": "PERSONAL",
    "personen-id": "PERSONAL",
    "personen": "PERSONAL",
    "wohnort": "PERSONAL",
    "jahrgang": "PERSONAL",
    "staatsbürgerschaft": "PERSONAL",
    "staatsbuergerschaft": "PERSONAL",
    "stundensatz": "PERSONAL",
    "verfügbar": "PERSONAL",
    "verfuegbar": "PERSONAL",
    "persönliche": "PERSONAL",
    "personal": "PERSONAL",
    "name": "PERSONAL",
    "geburtsjahr": "PERSONAL",
    "bemerkungen": "PERSONAL",
    "kommentar": "OTHER",
    "kontaktwunsch": "PERSONAL",
    # FACHBEREICHE / Schwerpunkt / Position
    "fachlicher": "FACHBEREICHE",
    "schwerpunkt": "FACHBEREICHE",
    "schwerpunkte": "FACHBEREICHE",
    "fachbereiche": "FACHBEREICHE",
    "fachbereich": "FACHBEREICHE",
    "position": "FACHBEREICHE",
    "top-skills": "FACHBEREICHE",
    "top": "FACHBEREICHE",  # "Top-Skills:" — first token often "Top-Skills"
    # BRANCHEN
    "branchen": "BRANCHEN",
    "branche": "BRANCHEN",
    # ZERTIFIKATE
    "zertifizierungen": "ZERTIFIKATE",
    "zertifizierung": "ZERTIFIKATE",
    "zertifikate": "ZERTIFIKATE",
    "zertifikat": "ZERTIFIKATE",
    "qualifikationen": "ZERTIFIKATE",
    # SCHULUNGEN / Ausbildung
    "ausbildung": "SCHULUNGEN",
    "schulungen": "SCHULUNGEN",
    "schulung": "SCHULUNGEN",
    "weiterbildung": "SCHULUNGEN",
    "training": "SCHULUNGEN",
    "studium": "SCHULUNGEN",
    "beruflicher": "SCHULUNGEN",  # Beruflicher Werdegang
    "werdegang": "SCHULUNGEN",
    "abschluss": "SCHULUNGEN",
    "abschluß": "SCHULUNGEN",
    "institution": "SCHULUNGEN",
    # SKILLS
    "programmiersprachen": "SKILLS",
    "programmiersprache": "SKILLS",
    "betriebssysteme": "SKILLS",
    "betriebssystem": "SKILLS",
    "datenbanken": "SKILLS",
    "datenbank": "SKILLS",
    "hardware": "SKILLS",
    "hardwareplattform": "SKILLS",
    "datenkommunikation": "SKILLS",
    "netzwerk": "SKILLS",
    "netzwerkprotokolle": "SKILLS",
    "webserver": "SKILLS",
    "middleware": "SKILLS",
    "methoden": "SKILLS",
    "methodisches": "SKILLS",
    "tools": "SKILLS",
    "tool": "SKILLS",
    "office": "SKILLS",
    "software": "SKILLS",
    "kenntnisse": "SKILLS",
    "edv": "SKILLS",
    "repositories": "SKILLS",
    "j2ee": "SKILLS",
    "j2se": "SKILLS",
    "entwicklungstools": "SKILLS",
    "softwaretechnologien": "SKILLS",
    "modellierungstools": "SKILLS",
    "spezialkenntnisse": "SKILLS",
    "application": "SKILLS",
    "technologien": "SKILLS",
    "frameworks": "SKILLS",
    "framework": "SKILLS",
    "cloud": "SKILLS",
    "virtualisierung": "SKILLS",
    "sicherheit": "SKILLS",
    "security": "SKILLS",
    "monitoring": "SKILLS",
    "versionsverwaltung": "SKILLS",
    "testing": "SKILLS",
    "datenformate": "SKILLS",
    "datenmanagement": "SKILLS",
    "fremdsprachen": "SKILLS",
    # FOCUS_EXP
    "produkte": "FOCUS_EXP",
    "erfahrungen": "FOCUS_EXP",
    "einsatzort": "FOCUS_EXP",
    "regionen": "FOCUS_EXP",
    # PROJECT
    "projekte": "PROJECT",
    "projektübersicht": "PROJECT",
    "projektuebersicht": "PROJECT",
    "projekt": "PROJECT",
    "zeitraum": "PROJECT",
    "laufzeit": "PROJECT",
    "dauer": "PROJECT",
    "rolle": "PROJECT",
    "kunde": "PROJECT",
    "firma": "PROJECT",
    "auftrag": "PROJECT",
    "aufgaben": "PROJECT",
    "aufgabenstellung": "PROJECT",
    "projektinhalte": "PROJECT",
    "meine": "PROJECT",  # Meine Aufgaben
    "tätigkeiten": "PROJECT",
    "tatigkeiten": "PROJECT",
    "tätigkeit": "PROJECT",
    "systemumgebung": "PROJECT",
    "projektumgebung": "PROJECT",
    "eingesetzte": "PROJECT",
    "period": "PROJECT",
    "referenzen": "EXPERIENCE",
}

# Mehrwort-Phrasen (lower) → Label — wenn first_word allein zu grob ist
PHRASE_TO_LABEL: Dict[str, str] = {
    "fachlicher schwerpunkt": "FACHBEREICHE",
    "top-skills": "FACHBEREICHE",
    "top skills": "FACHBEREICHE",
    "beruflicher Werdegang".lower(): "SCHULUNGEN",
    "stammdaten (auszug)": "PERSONAL",
    "produkte/standards/erfahrungen": "FOCUS_EXP",
    "produkte / standards / erfahrungen": "FOCUS_EXP",
    "software / tools / methoden": "SKILLS",
    "durchgeführte projekte": "PROJECT",
    "durchgefuehrte projekte": "PROJECT",
    "meine aufgaben": "PROJECT",
    "rolle im projekt": "PROJECT",
    "aufgaben im projekt": "PROJECT",
    "eingesetzte produkte": "PROJECT",
    "verfügbar ab": "PERSONAL",
    "verfuegbar ab": "PERSONAL",
}

# Regex-Gruppen (Detection / Convert) — gleiche Ontology wie Dry-Run v1.3
CORE_SECTION_PATTERNS: List[str] = [
    r"Fachlicher\s+Schwerpunkt",
    r"Schwerpunkt",
    r"Position",
    r"Ausbildung",
    r"Beruflicher\s+Werdegang",
    r"(?:Durchgef[uü]hrte\s+)?Projekte",
    r"Projekt[uü]bersicht",
    r"Branchen?",
    r"Fremdsprachen",
    r"Einsatzort",
    r"Regionen(?:\s*&\s*L[aä]nder)?",
    r"Kommentar",
    r"Sonstige\s+Anmerkungen",
    r"Bemerkungen",
    r"Stammdaten(?:\s*\(Auszug\))?",
    r"Personendaten",
    r"Zertifizierungen?",
    r"Top[- ]Skills",
]

SKILL_SECTION_PATTERNS: List[str] = [
    r"Hardware(?:plattform)?",
    r"Betriebssysteme",
    r"Programmiersprachen?",
    r"Datenbank(?:en)?",
    r"Datenkommunikation",
    r"Software(?:\s*/\s*Tools(?:\s*/\s*Methoden)?)?",
    r"Tools?",
    r"Office\s+Tools?",
    r"Web\s*/\s*Portal-Server",
    r"Repositories",
    r"J2EE\s+Technologien",
    r"J2SE\s+Technologien",
    r"Methodisches\s+Vorgehen",
    r"Methoden",
    r"Produkte\s*/\s*Standards\s*/\s*Erfahrungen",
    r"Produkte\s*\|\s*Standards(?:\s*\|\s*Erfahrungen)?",
    r"Kenntnisse",
    r"EDV[- ]Kenntnisse",
    r"Design/Entwicklung/Konstruktion",
    r"Berechnung/Simulation/Versuch/Validierung",
    r"Middleware",
    r"Top[- ]Skills",
    r"Fremdsprachen",
]

PROJECT_FIELD_PATTERNS: List[str] = [
    r"Zeitraum",
    r"Dauer",
    r"Laufzeit",
    r"Rolle(?:\s+im\s+Projekt)?",
    r"Kunde",
    r"Firma(?:/Institut)?",
    r"Firma(?:\s*/\s*Branche)?",
    r"Branche/Firma",
    r"Firma",
    r"Auftrag",
    r"Aufgaben(?:\s+im\s+Projekt)?",
    r"Aufgabenstellung",
    r"Meine\s+Aufgaben",
    r"Projektinhalte",
    r"Beschreibung",
    r"Kenntnisse",
    r"Eingesetzte\s+Produkte",
    r"Technologie",
    r"Tech",
    r"Projektumgebung",
    r"Systemumgebung",
    r"Verantwortung",
    r"Referenzen",
    r"T[aä]tigkeiten?",
    r"Titel",
]

STAMM_FIELD_PATTERNS: List[str] = [
    r"Personen[- ]?ID",
    r"Wohnort",
    r"Jahrgang",
    r"Staatsb[uü]rgerschaft",
    r"Stundensatz",
    r"Verf[uü]gbar\s+ab",
    r"verf[uü]gbar\s+zu",
    r"davon\s+vor\s+Ort",
    r"Remote[- ]Einsatz",
    r"Kontaktwunsch",
    r"Unternehmensgr[oö]ße",
    r"Profil\s+erstellt\s+am",
    r"Profil\s+zuletzt\s+ge[aä]ndert\s+am",
    r"EDV[- ]Erfahrung\s+seit",
]


def norm_heading(text: str) -> str:
    t = (text or "").strip().lower()
    t = t.replace("\u00a0", " ").replace("\u200b", "")
    t = re.sub(r"\s+", " ", t)
    t = t.rstrip(":").strip()
    return t


def label_from_heading(text: str) -> Optional[str]:
    """Mappt eine Überschrift/erste Zeile auf MAIN_LABEL — Phrase, dann first word."""
    h = norm_heading(text)
    if not h:
        return None
    if h in PHRASE_TO_LABEL:
        return PHRASE_TO_LABEL[h]
    # längste Phrase, die als Prefix matcht
    for phrase, lab in sorted(PHRASE_TO_LABEL.items(), key=lambda x: -len(x[0])):
        if h.startswith(phrase):
            return lab
    first = re.split(r"[\s/|,;:]+", h, maxsplit=1)[0]
    # "Top-Skills" als ein Token
    if first.startswith("top-skill") or first == "top-skills":
        return "FACHBEREICHE"
    return FIRST_WORD_TO_LABEL.get(first)


def merged_first_word_map(base: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """base (z.B. bestehendes FIRST_WORD_TO_LABEL) ∪ Gulp-Erweiterungen."""
    out = dict(base or {})
    out.update(FIRST_WORD_TO_LABEL)
    return out


# Detection-Version (für Scripts / Dry-Run Sync)
KEYWORDS_VERSION = "v1.3"
