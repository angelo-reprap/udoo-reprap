"""
section_label_keywords.py
=========================
Keyword-Sammlung (Gulp v1.3) für Section/Field-Labeling.

Status: FINAL COLLECTION — noch NICHT verdrahtet in main_labeler / block_labeler.
Nutzung jetzt: CONVERT-gulp-txt-to-aid-pdf (Struktur-HTML → AID-*-gulp.pdf).
Später: gemeinsame Ontology für main_labeler + url_gu + block_labeler.

Quelle: artifacts/gulp-keyword/section-keywords-v1.3-final.json
Dry-Run: 5652/5666 (99.75%).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

KEYWORDS_VERSION = "v1.3-final"

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

# Phrase (lower) → MAIN_LABEL — längere Phrasen zuerst matchen
PHRASE_TO_LABEL: Dict[str, str] = {
    "fachlicher schwerpunkt": "FACHBEREICHE",
    "top-skills": "FACHBEREICHE",
    "top skills": "FACHBEREICHE",
    "beruflicher werdegang": "SCHULUNGEN",
    "stammdaten (auszug)": "PERSONAL",
    "stammdaten": "PERSONAL",
    "personendaten": "PERSONAL",
    "personen-id": "PERSONAL",
    "verfügbar ab": "PERSONAL",
    "verfuegbar ab": "PERSONAL",
    "produkte/standards/erfahrungen": "FOCUS_EXP",
    "produkte / standards / erfahrungen": "FOCUS_EXP",
    "software / tools / methoden": "SKILLS",
    "durchgeführte projekte": "PROJECT",
    "durchgefuehrte projekte": "PROJECT",
    "projektübersicht": "PROJECT",
    "projektuebersicht": "PROJECT",
    "meine aufgaben": "PROJECT",
    "rolle im projekt": "PROJECT",
    "aufgaben im projekt": "PROJECT",
    "eingesetzte produkte": "PROJECT",
    "regionen & länder": "FOCUS_EXP",
    "regionen & laender": "FOCUS_EXP",
}

# Sichere First-Word → Label (keine Einwort-Risiken wie top/meine/software)
FIRST_WORD_TO_LABEL: Dict[str, str] = {
    # PERSONAL
    "stammdaten": "PERSONAL",
    "personendaten": "PERSONAL",
    "wohnort": "PERSONAL",
    "jahrgang": "PERSONAL",
    "staatsbürgerschaft": "PERSONAL",
    "staatsbuergerschaft": "PERSONAL",
    "stundensatz": "PERSONAL",
    "bemerkungen": "PERSONAL",
    "kontaktwunsch": "PERSONAL",
    "persönliche": "PERSONAL",
    "personal": "PERSONAL",
    "geburtsjahr": "PERSONAL",
    # FACHBEREICHE
    "schwerpunkt": "FACHBEREICHE",
    "schwerpunkte": "FACHBEREICHE",
    "fachlicher": "FACHBEREICHE",
    "fachbereiche": "FACHBEREICHE",
    "fachbereich": "FACHBEREICHE",
    "position": "FACHBEREICHE",
    # BRANCHEN
    "branchen": "BRANCHEN",
    "branche": "BRANCHEN",
    # ZERTIFIKATE
    "zertifizierungen": "ZERTIFIKATE",
    "zertifizierung": "ZERTIFIKATE",
    "zertifikate": "ZERTIFIKATE",
    "zertifikat": "ZERTIFIKATE",
    "qualifikationen": "ZERTIFIKATE",
    # SCHULUNGEN
    "ausbildung": "SCHULUNGEN",
    "schulungen": "SCHULUNGEN",
    "schulung": "SCHULUNGEN",
    "weiterbildung": "SCHULUNGEN",
    "training": "SCHULUNGEN",
    "studium": "SCHULUNGEN",
    "abschluss": "SCHULUNGEN",
    "abschluß": "SCHULUNGEN",
    "institution": "SCHULUNGEN",
    "werdegang": "SCHULUNGEN",
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
    "kenntnisse": "SKILLS",
    "fremdsprachen": "SKILLS",
    "middleware": "SKILLS",
    "methoden": "SKILLS",
    "methodisches": "SKILLS",
    "tools": "SKILLS",
    "repositories": "SKILLS",
    "technologien": "SKILLS",
    "frameworks": "SKILLS",
    "framework": "SKILLS",
    # FOCUS_EXP
    "produkte": "FOCUS_EXP",
    "erfahrungen": "FOCUS_EXP",
    "einsatzort": "FOCUS_EXP",
    "regionen": "FOCUS_EXP",
    # PROJECT
    "projekte": "PROJECT",
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
    "tätigkeiten": "PROJECT",
    "tatigkeiten": "PROJECT",
    "tätigkeit": "PROJECT",
    "systemumgebung": "PROJECT",
    "projektumgebung": "PROJECT",
    "period": "PROJECT",
    "referenzen": "EXPERIENCE",
}

# Zu riskant als alleiniges First-Word (nur Phrase)
EXCLUDED_FIRST_WORDS = {
    "top",
    "meine",
    "software",
    "personen",
    "kommentar",
    "edv",
    "office",
    "name",
}

# Regex für Section-Detection / Convert-Splitter (Reihenfolge = Priorität)
SECTION_SPLIT_PATTERNS: List[Tuple[str, str]] = [
    # (compiled later) label_hint, pattern
    ("FACHBEREICHE", r"Fachlicher\s+Schwerpunkt"),
    ("FACHBEREICHE", r"Top[- ]Skills"),
    ("FACHBEREICHE", r"Position"),
    ("SCHULUNGEN", r"Ausbildung"),
    ("SCHULUNGEN", r"Beruflicher\s+Werdegang"),
    ("SCHULUNGEN", r"Zertifizierungen?"),
    ("SCHULUNGEN", r"Schulungen?"),
    ("PROJECT", r"(?:Durchgef[uü]hrte\s+)?Projekte"),
    ("PROJECT", r"Projekt[uü]bersicht"),
    ("BRANCHEN", r"Branchen?"),
    ("SKILLS", r"Fremdsprachen"),
    ("SKILLS", r"Hardware(?:plattform)?"),
    ("SKILLS", r"Betriebssysteme"),
    ("SKILLS", r"Programmiersprachen?"),
    ("SKILLS", r"Datenbank(?:en)?"),
    ("SKILLS", r"Datenkommunikation"),
    ("SKILLS", r"Software\s*/\s*Tools(?:\s*/\s*Methoden)?"),
    ("SKILLS", r"Kenntnisse"),
    ("FOCUS_EXP", r"Produkte\s*/\s*Standards\s*/\s*Erfahrungen"),
    ("FOCUS_EXP", r"Einsatzort"),
    ("FOCUS_EXP", r"Regionen(?:\s*&\s*L[aä]nder)?"),
    ("PERSONAL", r"Stammdaten(?:\s*\(Auszug\))?"),
    ("PERSONAL", r"Personendaten"),
    ("PERSONAL", r"Bemerkungen"),
    ("OTHER", r"Kommentar"),
]


def norm_heading(text: str) -> str:
    t = (text or "").strip().lower()
    for ch in ("\u00a0", "\u2009", "\u202f"):
        t = t.replace(ch, " ")
    for ch in ("\u200b", "\u00ad"):
        t = t.replace(ch, "")
    t = t.replace("&amp;", "&")
    t = re.sub(r"\s+", " ", t).rstrip(":").strip()
    return t


def label_from_heading(text: str) -> Optional[str]:
    h = norm_heading(text)
    if not h:
        return None
    if h in PHRASE_TO_LABEL:
        return PHRASE_TO_LABEL[h]
    for phrase, lab in sorted(PHRASE_TO_LABEL.items(), key=lambda x: -len(x[0])):
        if h.startswith(phrase):
            return lab
    # Top-Skills as single token
    first = re.split(r"[\s/|,;:]+", h, maxsplit=1)[0]
    if first in EXCLUDED_FIRST_WORDS:
        if first.startswith("top") and "skill" in h:
            return "FACHBEREICHE"
        return None
    if first in {"top-skills", "top-skill"}:
        return "FACHBEREICHE"
    return FIRST_WORD_TO_LABEL.get(first)


def load_final_json() -> dict:
    """Optional: JSON aus artifacts laden (Repo-Root relativ)."""
    here = Path(__file__).resolve()
    candidates = [
        here.parents[4] / "artifacts/gulp-keyword/section-keywords-v1.3-final.json",
        Path("artifacts/gulp-keyword/section-keywords-v1.3-final.json"),
    ]
    for p in candidates:
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    return {}


def section_splitter_regex() -> re.Pattern:
    """Ein Regex, der alle Section-Köpfe matched (für TXT→HTML Split)."""
    parts = [p for _, p in SECTION_SPLIT_PATTERNS]
    return re.compile(
        r"(?im)(?:^|(?<=\s{2})|(?<=\t))(" + "|".join(f"(?:{p})" for p in parts) + r")\s*:?\s*"
    )
