"""Firmennamen für toleranten Sperrlisten-/Radar-Abgleich normalisieren."""
from __future__ import annotations

import re
import unicodedata

# Rechtsformen (DE + häufige EN) — nach Lowercasing; (?!\w) statt \b,
# damit Formen mit Punkt am Ende (A.G.) matchen.
_LEGAL_FORMS = re.compile(
    r'(?<!\w)('
    r'gmbh|gmb|mbh|'
    r'a\.?\s*g\.?|'  # AG / A.G.
    r'kg|ohg|ug|'
    r'e\.?\s*k\.?|'
    r'inc\.?|ltd\.?|llc|corp\.?|co\.?'
    r')(?!\w)',
    re.IGNORECASE,
)
_NON_ALNUM = re.compile(r'[^\w\s]', re.UNICODE)
_MULTI_SPACE = re.compile(r'\s+')


def normalize_firma_name(name: str) -> str:
    """
    Lowercase, Rechtsformen/Interpunktion strippen, Whitespace kollabieren.

    Gemeinsam für Sperrliste.save() und Radar-Matcher — gleiche Logik Pflicht.
    """
    s = (name or '').strip()
    if not s:
        return ''
    s = unicodedata.normalize('NFKC', s).lower()
    s = _LEGAL_FORMS.sub(' ', s)
    s = _NON_ALNUM.sub(' ', s)
    s = _MULTI_SPACE.sub(' ', s).strip()
    return s
