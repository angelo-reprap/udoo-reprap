"""
gulp_profile_clean.py
=====================
Gulp-TXT → schlankes AID-Profil (Stammdaten + Sektionen + experience[]).

- Nur neuester Snapshot (erster „Gulp-Profil Stand …“)
- Noise weg: Kommentar, Navigation, Footer, Links, Alt-Snapshots
- Personen-ID → Name: AID-{initials}_{version}
- Projekte → experience[{period,title,company,industry,role,location,activities,technologies}]
  activities max 8
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

UMLAUT = str.maketrans(
    {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue"}
)

SNAPSHOT_RE = re.compile(
    r"-{5,}\s*Gulp-Profil\s+Stand\s+(\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)

NOISE_LINE_RE = re.compile(
    r"""(?ix)^(?:
        \*?$
        |recherche\b.*
        |suchergebnis\b.*
        |kontaktieren\b.*
        |anfragen\s+an\s+id\b.*
        |seite\s+drucken\b.*
        |zum\s+seitenanfang\b.*
        |direktkontakt\b.*
        |wordprofil\b.*
        |xml\s*profil\b.*
        |gulp\s+information\s+services\b.*
        |\(c\)\s*copyright\b.*
        |seite\s+generiert\s+am\b.*
        |links:\s*$
        |-{3,}$
        |\[\d+\].*
        |suche\s*\|.*agb.*
        |kommentar\s*:?\s*$
        |kommentar\s+schreiben.*
        |profil\s+angezeigt\s+am\b.*
        |festanstellung\s+kommt\s+derzeit\s+nicht\b.*
    )$"""
)

# Stammdaten-Felder (Reihenfolge für Ausgabe)
PERSONAL_KEYS = [
    ("wohnort", re.compile(r"Wohnort\s+(.+?)(?=\s+(?:Jahrgang|Stundensatz|EDV-Erfahrung|Verfügbar|Verfuegbar|Profil\s+erstellt)\b|$)", re.I | re.S)),
    ("jahrgang", re.compile(r"Jahrgang\s+(\d{4})", re.I)),
    # Stundensatz bewusst nicht extrahiert (kein Matching / kein hourly_rate)
    ("edv_seit", re.compile(r"EDV-Erfahrung\s+seit\s+(\d{4})", re.I)),
    ("verfuegbar", re.compile(
        r"Verf(?:ü|ue)gbar\s+ab\s+(.+?)(?=\s+Profil\s+erstellt\b|\s+Lesen\s+von\b|$)",
        re.I | re.S,
    )),
]

# Top-level Gulp section heads (NOT project-internal labels like Einsatzort inside Projekte)
SECTION_HEAD_NAMES = (
    r"Fachlicher\s+Schwerpunkt|Position|Einsatzort|Regionen|"
    r"Fremdsprachen|Projekte|Branchen|Zertifizierungen|Ausbildung|"
    r"Kenntnisse|Hardware|Software|Tools|Methoden|"
    r"Betriebssysteme|Programmiersprachen|Datenbanken|"
    r"Datenkommunikation|Aufgabenbereiche|Schwerpunkte|"
    r"Produkte/Standards/Erfahrungen|Managementerfahrung|"
    r"Persönliche\s+Stärken|Sonstige\s+Anmerkungen|Referenzen"
)

SECTION_HEAD_RE = re.compile(
    rf"(?im)^\s*({SECTION_HEAD_NAMES})\s*:?\s*$"
)

# Inline heads before Projekte (Stammdaten dump). Einsatzort/Position only here —
# inside Projekte they are project fields, not section boundaries.
INLINE_SECTION_RE = re.compile(
    r"(?i)\b(Fachlicher\s+Schwerpunkt|Position|Einsatzort|Regionen|"
    r"Fremdsprachen|Projekte)\s*:\s*"
)

# After Projekte starts, only these heads may close the Projekte block
# Alone on the line only — NOT "Kenntnisse: AD Server …" inside a project
PROJEKTE_END_HEAD_RE = re.compile(
    r"(?im)^\s*(?:Branchen|Zertifizierungen|Ausbildung|Referenzen|"
    r"Seite\s+drucken|Zum\s+Seitenanfang|"
    r"GULP Information Services|Links:"
    r"|Persönliche\s+Stärken|Sonstige\s+Anmerkungen|"
    r"Ältere\s+Projekte\s+auf\s+Anfrage)\s*:?\s*$"
)

KUNDE_RE = re.compile(r"(?im)^\s*Kunde\s*:\s*(.+?)\s*$")
# Gulp "Kunde····Name" (multi-space / nbsp) OR "Kunde CapName" after ws-normalize
KUNDE_PLAIN_RE = re.compile(
    r"(?im)^\s*Kunde(?:(?:\s{2,}|\t|\xa0)+|\s+)(?!in\b|und\b|als\b|oder\b|für\b|fuer\b|/)"
    r"([A-ZÄÖÜ][^\n]{0,80})\s*$"
)
PROJEKT_RE = re.compile(r"(?im)^\s*Projekt\s*:\s*(.+?)\s*$")
ZEITRAUM_RE = re.compile(r"(?im)^\s*Zeitraum\s*:\s*(.+?)\s*$")
FIRMA_RE = re.compile(r"(?im)^\s*Firma(?:/Institut)?\s*:\s*(.+?)\s*$")
AUFTRAG_RE = re.compile(r"(?im)^\s*Auftrag\s*:\s*(.+?)\s*$")
ROLLE_RE = re.compile(r"(?im)^\s*Rolle(?:\s*/\s*Position)?\s*:\s*(.+?)\s*$")
EINSATZORT_FIELD_RE = re.compile(r"(?im)^\s*Einsatzort\s*:\s*(.+?)\s*$")
PROJEKTINHALTE_RE = re.compile(r"(?im)^\s*Projektinhalte\s*:\s*(.*)$")
TECH_UMGEBUNG_RE = re.compile(
    r"(?im)^\s*(?:Technische\s+Umgebung|Systemumgebung|Kenntnisse)\s*:\s*(.*)$"
)
DURATION_ONLY_RE = re.compile(
    r"(?i)^\s*(?:\d+\s*(?:Monate?|Jahre?|Jahr)|"
    r"\d+\s*Jahr\s+\d+\s*Monate?)\b"
)

# Period at start of line (Pauser / Hoellig / mixed)
PERIOD_LINE_RE = re.compile(
    r"""(?ix)^\s*
    (?P<period>
        \d{4}-\d{2}\s*[-–]\s*\d{4}-\d{2}
        |\d{2}/\d{4}\s*[-–]\s*(?:\d{2}/\d{4}|heute|aktuell)
        |\d{2}/\d{4}\s+heute
        |\d{4}\s*[-–]\s*(?:\d{4}|heute|aktuell)
    )
    (?:\s*:\s*|\s+)
    (?P<title>.*)?
    $"""
)

# Stotz: "Projekt 7 / Jul/Aug 2007" or "Projekt 5 / 2006"
PROJEKT_NUM_RE = re.compile(
    r"(?im)^\s*Projekt\s+(?P<num>\d+)\s*/\s*(?P<period>.+?)\s*$"
)

# Arnold-style freeform
PROJEKT_BEI_RE = re.compile(r"(?im)^\s*Projekt\s+bei\s+(.+?)\s*:?\s*$")
TAETIGKEITEN_BEI_RE = re.compile(
    r"(?im)^\s*Tätigkeiten\s+bei\s+(?:der\s+|dem\s+|den\s+)?(.+?)\s*$"
)

TECH_HINT_RE = re.compile(
    r"(?i)(?:^|\b)(?:cisco|juniper|nortel|brocade|f5|hp-|aperture|nexus|"
    r"dwdm|lan/san|switch|firewall|ansible|linux|windows|excel|exel)\b"
)
DOC_TECH_RE = re.compile(r"(?i)^\s*Dokumentation\s*:\s*(.+)$")
MONTAGE_TECH_RE = re.compile(
    r"(?i)^\s*(?:Montage\s+der\s+passiven\s+und\s+aktiven\s+Komponenten\s*:?\s*)?$"
)

# Knowledge dumps that must not land in Sprachen
SKILL_SECTION_KEYS = (
    "kenntnisse", "hardware", "software", "tools", "methoden",
    "betriebssysteme", "programmiersprachen", "datenbanken",
    "datenkommunikation", "aufgabenbereiche", "schwerpunkte",
    "produkte/standards/erfahrungen", "managementerfahrung",
)

# Gulp-Skill-Head → AID-Label (aid_regex erkennt diese)
SKILL_AID_LABEL = {
    "betriebssysteme": "Betriebssysteme",
    "programmiersprachen": "Programmiersprachen",
    "datenbanken": "Datenbanken",
    "hardware": "Hardware",
    # → Label muss aid_regex SKILL_SECTIONS treffen
    "software": "Softwaretechnologien",
    "tools": "Tools",
    "methoden": "Methoden",
    "datenkommunikation": "Datenkommunikation",
    "kenntnisse": "Sonstige Kenntnisse",
    "produkte/standards/erfahrungen": "Produkte|Standards|Erfahrungen",
    "aufgabenbereiche": "Aufgabenbereiche",
    "schwerpunkte": "Schwerpunkte",
    "managementerfahrung": "Managementerfahrung",
}

# Max. Zeichen pro Skill-Sektion im AID-Plain (PDF-Größe)
SKILL_BODY_MAX_CHARS = 3500



def initials(first: str, last: str) -> str:
    a = (first[:1] if first else "").lower()
    b = (last[:1] if last else "").lower()
    a = {"ä": "a", "ö": "o", "ü": "u"}.get(a, a)
    b = {"ä": "a", "ö": "o", "ü": "u"}.get(b, b)
    return (a + b) if (a or b) else "xx"


def aid_name(first: str, last: str, version: str = "1.0.0.0") -> str:
    return f"AID-{initials(first, last)}_{version}"


def norm_ws(t: str) -> str:
    for ch in ("\u00a0", "\u2009", "\u202f", "\t"):
        t = t.replace(ch, " ")
    for ch in ("\u200b", "\u00ad"):
        t = t.replace(ch, "")
    t = t.replace("&amp;", "&")
    t = re.sub(r"[ \t]+", " ", t)
    return t


def latest_snapshot(raw: str) -> str:
    """Neuester Snapshot = erster Block (CRM-Export hängt Historie chronologisch absteigend an)."""
    text = norm_ws(raw)
    matches = list(SNAPSHOT_RE.finditer(text))
    if not matches:
        return text.strip()
    # Prefer highest date if multiple; CRM usually newest-first — still sort by date
    best_i = 0
    best_date = matches[0].group(1)
    for i, m in enumerate(matches):
        if m.group(1) > best_date:
            best_date = m.group(1)
            best_i = i
    start = matches[best_i].start()
    end = matches[best_i + 1].start() if best_i + 1 < len(matches) else len(text)
    return text[start:end].strip()


def strip_noise_lines(text: str) -> str:
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            out.append("")
            continue
        if NOISE_LINE_RE.match(s):
            continue
        if re.match(r"^\[\d+\]\s*/", s):
            continue
        # leftover from wrapped Festanstellung-line
        if re.fullmatch(r"(?i)mitarbeit", s):
            continue
        # footer crumbs
        if re.search(r"(?i)\bID\s+\d+\s*\[\d+\]", s):
            continue
        if re.search(r"(?i)Richtigkeit der hier gemachten", s):
            continue
        # drop bare link rows
        if s.startswith("http") or s.startswith("mailto:"):
            continue
        out.append(s)
    # collapse 3+ blank lines
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(out))
    return cleaned.strip()


def cut_after_projects_footer(text: str) -> str:
    """Footer/Navigation nach dem Profilinhalt abschneiden (nicht Kopf-Recherche)."""
    # Page-break markers mid-profile are noise, not hard cuts
    text = re.sub(
        r"(?im)^\s*\d{1,2}\.\d{2}\.\d{4}\s+\d+\s+von\s+\d+\s*$",
        "",
        text,
    )
    text = re.sub(r"(?im)^\s*Seite\s+drucken\b.*$", "", text)
    text = re.sub(r"(?im)^\s*Zum\s+Seitenanfang\b.*$", "", text)
    cut = re.split(
        r"(?im)^\s*(?:GULP Information Services|Links:\s*$)",
        text,
        maxsplit=1,
    )[0]
    return cut.strip()


def soft_join_lines(lines: List[str]) -> List[str]:
    """Umgebrochene Gulp-Zeilen wieder zusammenziehen (nur echte Fortsetzungen)."""
    if not lines:
        return []
    out: List[str] = [lines[0]]
    open_end = re.compile(
        r"(?i)\b(vom|von|zu|zur|zum|im|in|und|oder|sowie|der|die|das|den|dem|"
        r"ein|eine|einen|für|fuer|auf|bei|mit|des|am|an)$"
    )
    for ln in lines[1:]:
        prev = out[-1]
        starts_lower = bool(ln[:1].islower()) if ln else False
        starts_glue = ln.startswith(
            ("und ", "oder ", "sowie ", "auf ", "für ", "fuer ", "zum ", "zur ", "im ", "in ", "von ", "vom ")
        )
        prev_open = (
            prev.endswith("-")
            or bool(open_end.search(prev.rstrip()))
            or bool(re.search(r"(?i)\b(des|der|die|dem|den|ein|eine|einen)\s+\S+$", prev))
        )
        if (starts_lower or starts_glue or prev_open) and not re.match(
            r"(?i)^(kunde|projekt|zeitraum|firma|auftrag|rolle|einsatzort|"
            r"projektinhalte|technische\s+umgebung|systemumgebung)\s*:",
            ln,
        ):
            out[-1] = _squash(prev + " " + ln)
        else:
            out.append(ln)
    return out

def _squash(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def extract_personal(blob: str) -> Dict[str, str]:
    personal: Dict[str, str] = {}
    m = re.search(r"Personen-ID\s+(\d+)", blob, re.I)
    if m:
        personal["gulp_id"] = m.group(1)
    for key, rx in PERSONAL_KEYS:
        m = rx.search(blob)
        if m:
            personal[key] = _squash(m.group(1))
    return personal


def _carve_projekte(text: str) -> Tuple[str, str]:
    """
    Projekte-Block herausschneiden BEVOR andere Section-Heads greifen.
    Verhindert, dass 'Einsatzort:' / 'Position:' innerhalb von Projekten
    die Section zerschneiden (Pauser-Format u.a.).
    """
    m = re.search(r"(?im)^\s*Projekte\s*:?\s*$", text)
    if not m:
        m = re.search(r"(?i)\bProjekte\s*:\s*", text)
    if not m:
        return text, ""
    start = m.end()
    end_m = PROJEKTE_END_HEAD_RE.search(text, start)
    if end_m:
        body = text[start : end_m.start()].strip()
        rest = (text[: m.start()] + "\n" + text[end_m.start() :]).strip()
    else:
        body = text[start:].strip()
        rest = text[: m.start()].strip()
    return rest, body


def _split_section_bodies(text: str) -> List[Tuple[str, str]]:
    """Find section headings (line-start or inline after Stammdaten) and bodies."""
    rest, projekte_body = _carve_projekte(text)

    # Normalize inline headings onto own lines (pre-Projekte only)
    t = INLINE_SECTION_RE.sub(
        lambda m: "\n" + m.group(1) + ":\n", rest
    )
    t = re.sub(r"(?i)\bfachlicher\s+schwerpunkt\s*:", "Fachlicher Schwerpunkt:", t)
    t = re.sub(r"(?i)\bposition\s*:", "Position:", t)
    t = re.sub(r"(?i)\beinsatzort\s*:", "Einsatzort:", t)
    t = re.sub(r"(?i)\bregionen\s*:", "Regionen:", t)
    t = re.sub(r"(?i)\bfremdsprachen\s*:", "Fremdsprachen:", t)
    # Skill dumps often appear inline after Sprachen — force line breaks
    for lab in (
        "Hardware", "Software", "Tools", "Methoden", "Betriebssysteme",
        "Programmiersprachen", "Datenbanken", "Datenkommunikation",
        "Aufgabenbereiche", "Kenntnisse", "Schwerpunkte",
        "Produkte/Standards/Erfahrungen", "Branchen", "Ausbildung",
        "Zertifizierungen",
    ):
        t = re.sub(rf"(?i)\b{re.escape(lab)}\s*:", f"\n{lab}:\n", t)

    heads = list(SECTION_HEAD_RE.finditer(t))
    parts: List[Tuple[str, str]] = []
    for i, h in enumerate(heads):
        name = re.sub(r"\s+", " ", h.group(1)).strip()
        if name.lower() == "projekte":
            continue  # already carved
        start = h.end()
        end = heads[i + 1].start() if i + 1 < len(heads) else len(t)
        body = t[start:end].strip()
        parts.append((name, body))

    if projekte_body:
        # Drop trailing "Projekterfahrung" / noise-only intro line
        projekte_body = re.sub(
            r"(?im)^\s*Projekterfahrung\s*$", "", projekte_body
        ).strip()
        parts.append(("Projekte", projekte_body))
    return parts


def _merge_einsatz_regionen(sections: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    i = 0
    while i < len(sections):
        name, body = sections[i]
        if name.lower() == "einsatzort" and i + 1 < len(sections) and sections[i + 1][0].lower() == "regionen":
            # combine: prefer regionen body; drop empty einsatzort
            reg_body = sections[i + 1][1].strip()
            combined = body.strip()
            if reg_body:
                combined = (combined + "\n" + reg_body).strip() if combined else reg_body
            # strip "Regionen:" leftover
            combined = re.sub(r"(?i)^\s*Regionen\s*:?\s*", "", combined).strip()
            out.append(("Einsatzort / Regionen", combined))
            i += 2
            continue
        if name.lower() == "regionen" and out and out[-1][0].startswith("Einsatzort"):
            prev = out[-1][1]
            out[-1] = ("Einsatzort / Regionen", (prev + "\n" + body).strip())
            i += 1
            continue
        if name.lower() == "regionen":
            out.append(("Einsatzort / Regionen", body))
            i += 1
            continue
        out.append((name, body))
        i += 1
    return out


def _is_tech_line(line: str) -> bool:
    s = line.strip()
    if DOC_TECH_RE.match(s):
        return True
    # short comma-separated tech dump
    if "," in s and TECH_HINT_RE.search(s) and len(s) < 180:
        return True
    if re.match(r"(?i)^\s*cisco[- ]", s) and "," in s:
        return True
    return False


def _techs_from_line(line: str) -> List[str]:
    s = line.strip()
    m = DOC_TECH_RE.match(s)
    if m:
        s = m.group(1)
    s = re.sub(r"(?i)^\s*Montage\s+der\s+passiven\s+und\s+aktiven\s+Komponenten\s*:\s*", "", s)
    parts = re.split(r"\s*,\s*", s)
    out = []
    for p in parts:
        p = p.strip(" .;")
        if p and len(p) < 60:
            out.append(p)
    return out


def _looks_like_location(line: str) -> bool:
    s = line.strip().rstrip(",")
    if len(s) > 100:
        return False
    if _is_tech_line(s):
        return False
    if re.match(r"(?i)^(unterst|planung|aufnahme|bearbeitung|analyse|austausch|neuaufbau|montage|dokumentation|troubleshooting|patcharbeiten)\b", s):
        return False
    return bool(
        re.search(
            r"(?i)\b(datacenter|standort|münchen|muenchen|krefeld|bielefeld|"
            r"münster|muenster|nrw|berlin|hamburg|frankfurt|köln|koeln)\b",
            s,
        )
    )


def _empty_exp() -> Dict[str, Any]:
    return {
        "period": "",
        "title": "",
        "company": "",
        "industry": "",
        "role": "",
        "location": "",
        "activities": [],
        "technologies": [],
    }


def _finalize_exp(cur: Dict[str, Any], max_activities: int) -> Dict[str, Any]:
    acts = soft_join_lines([a for a in cur["activities"] if a.strip()])
    cur["activities"] = acts[:max_activities]
    seen = set()
    techs = []
    for t in cur["technologies"]:
        k = t.lower()
        if k not in seen:
            seen.add(k)
            techs.append(t)
    cur["technologies"] = techs
    return cur


def _exp_is_useful(cur: Dict[str, Any]) -> bool:
    if (cur.get("period") or "").strip():
        return True
    if (cur.get("company") or "").strip() and (
        (cur.get("title") or "").strip() or cur.get("activities")
    ):
        return True
    title = (cur.get("title") or "").strip()
    if title and len(title) > 8 and not title.lower().startswith("referenz"):
        return True
    return False


def _apply_field_line(cur: Dict[str, Any], ln: str) -> bool:
    """Map known project field labels onto cur. Returns True if consumed."""
    mk = KUNDE_RE.match(ln)
    if mk:
        cur["company"] = mk.group(1).strip()
        return True
    mf = FIRMA_RE.match(ln)
    if mf:
        cur["company"] = mf.group(1).strip()
        return True
    ma = AUFTRAG_RE.match(ln)
    if ma:
        val = ma.group(1).strip()
        if not cur.get("title"):
            cur["title"] = val
        else:
            cur["activities"].append(val)
        return True
    mr = ROLLE_RE.match(ln)
    if mr:
        cur["role"] = mr.group(1).strip()
        if not cur.get("title"):
            cur["title"] = cur["role"]
        return True
    me = EINSATZORT_FIELD_RE.match(ln)
    if me:
        cur["location"] = me.group(1).strip()
        return True
    mz = ZEITRAUM_RE.match(ln)
    if mz:
        cur["period"] = _squash(mz.group(1))
        return True
    mpi = PROJEKTINHALTE_RE.match(ln)
    if mpi:
        rest = (mpi.group(1) or "").strip()
        if rest:
            rest = re.sub(r"^[•\-\*]\s*", "", rest).strip()
            if rest:
                cur["activities"].append(_squash(rest))
        return True
    mt = TECH_UMGEBUNG_RE.match(ln)
    if mt:
        rest = (mt.group(1) or "").strip()
        if rest:
            cur["technologies"].extend(_techs_from_line(rest))
        return True
    return False


def _parse_kunde_projekt_zeitraum(
    lines: List[str], max_activities: int
) -> List[Dict[str, Any]]:
    """Format A (Broeckling): Kunde: / Projekt: / Zeitraum:"""
    experiences: List[Dict[str, Any]] = []
    cur: Optional[Dict[str, Any]] = None

    def flush():
        nonlocal cur
        if not cur:
            return
        cur = _finalize_exp(cur, max_activities)
        if _exp_is_useful(cur):
            experiences.append(cur)
        cur = None

    i = 0
    while i < len(lines):
        ln = lines[i]
        mk = KUNDE_RE.match(ln)
        mp = PROJEKT_RE.match(ln)
        mz = ZEITRAUM_RE.match(ln)
        mf = FIRMA_RE.match(ln)

        if mk:
            flush()
            cur = _empty_exp()
            cur["company"] = mk.group(1).strip()
            i += 1
            continue

        if mf and cur is None:
            flush()
            cur = _empty_exp()
            cur["company"] = mf.group(1).strip()
            i += 1
            continue

        if mp:
            if cur is None:
                cur = _empty_exp()
            title = mp.group(1).strip().rstrip(",")
            loc_bits: List[str] = []
            j = i + 1
            while j < len(lines):
                nxt = lines[j]
                if (
                    KUNDE_RE.match(nxt)
                    or PROJEKT_RE.match(nxt)
                    or ZEITRAUM_RE.match(nxt)
                    or FIRMA_RE.match(nxt)
                ):
                    break
                if _is_tech_line(nxt) or re.match(
                    r"(?i)^\s*Montage\s+der\s+passiven", nxt
                ):
                    break
                if _looks_like_location(nxt) and not title.endswith(","):
                    loc_bits.append(nxt.strip().rstrip(","))
                    j += 1
                    continue
                if _looks_like_location(nxt) and title.endswith(","):
                    if re.match(r"(?i)^\s*Datacenter\b", nxt):
                        loc_bits.append(nxt.strip().rstrip(","))
                        j += 1
                        continue
                if not re.match(
                    r"(?i)^(unterst|planung|aufnahme|bearbeitung|analyse|"
                    r"austausch|neuaufbau|troubleshooting|patcharbeiten)\b",
                    nxt,
                ):
                    title = (title + " " + nxt).strip().rstrip(",")
                    j += 1
                    continue
                break
            cur["title"] = _squash(title)
            if loc_bits:
                cur["location"] = _squash(", ".join(loc_bits))
            i = j
            continue

        if mz:
            if cur is None:
                cur = _empty_exp()
            cur["period"] = _squash(mz.group(1))
            i += 1
            continue

        if cur is None:
            i += 1
            continue

        if _apply_field_line(cur, ln):
            i += 1
            continue

        if re.match(
            r"(?i)^\s*Montage\s+der\s+passiven\s+und\s+aktiven\s+Komponenten\s*:?\s*$",
            ln,
        ):
            i += 1
            if i < len(lines) and _is_tech_line(lines[i]):
                cur["technologies"].extend(_techs_from_line(lines[i]))
                i += 1
            continue

        if _is_tech_line(ln):
            cur["technologies"].extend(_techs_from_line(ln))
            i += 1
            continue

        cur["activities"].append(_squash(ln))
        i += 1

    flush()
    return experiences


def _parse_period_first(
    lines: List[str], max_activities: int
) -> List[Dict[str, Any]]:
    """
    Format B/C: Period at line start
      2021-10 - 2022-02 Migration Exchange …
      2017 - 2019 Fintech
      06/2012 - heute: …
    """
    experiences: List[Dict[str, Any]] = []
    cur: Optional[Dict[str, Any]] = None
    # track subsections for hoellig
    mode = ""  # '', 'tech', 'tasks', 'topics'

    def flush():
        nonlocal cur, mode
        if not cur:
            return
        cur = _finalize_exp(cur, max_activities)
        if _exp_is_useful(cur):
            experiences.append(cur)
        cur = None
        mode = ""

    i = 0
    while i < len(lines):
        ln = lines[i]
        pm = PERIOD_LINE_RE.match(ln)
        # also bare Zeitraum: as period-first start
        mz = ZEITRAUM_RE.match(ln)
        if pm or mz:
            flush()
            cur = _empty_exp()
            if pm:
                cur["period"] = _squash(pm.group("period"))
                title = (pm.group("title") or "").strip().rstrip(":")
                if title:
                    cur["title"] = _squash(title)
            else:
                cur["period"] = _squash(mz.group(1))
            mode = ""
            i += 1
            continue

        if cur is None:
            i += 1
            continue

        # skip duration-only lines ("5 Monate", "1 Jahr 7 Monate …")
        if DURATION_ONLY_RE.match(ln) and len(ln) < 80:
            # trailing words after duration may be title fragment
            rest = DURATION_ONLY_RE.sub("", ln).strip(" ,;")
            if rest and not cur.get("title"):
                cur["title"] = _squash(rest)
            elif rest and cur.get("title") and rest.lower() not in cur["title"].lower():
                cur["title"] = _squash(cur["title"] + " " + rest)
            i += 1
            continue

        if _apply_field_line(cur, ln):
            mode = ""
            i += 1
            continue

        if re.match(r"(?i)^\s*Fachliche\s+Themen\s*:?\s*$", ln):
            mode = "topics"
            i += 1
            continue
        if re.match(r"(?i)^\s*Aufgabenbereich\s*:?\s*$", ln):
            mode = "tasks"
            i += 1
            continue
        if re.match(r"(?i)^\s*Technische\s+Umgebung\s*:?\s*$", ln):
            mode = "tech"
            i += 1
            continue

        if mode == "tech":
            cur["technologies"].extend(_techs_from_line(ln) or [ln.strip()])
            i += 1
            continue

        # bullet
        cleaned = re.sub(r"^[•\-\*\?]\s*", "", ln).strip()
        if not cleaned:
            i += 1
            continue

        # first non-field line after period often = role/industry if no title
        if (
            not cur.get("title")
            and not cur.get("role")
            and len(cleaned) < 80
            and not cleaned.endswith(".")
        ):
            cur["title"] = cleaned
            cur["role"] = cleaned
            i += 1
            continue

        if _is_tech_line(cleaned):
            cur["technologies"].extend(_techs_from_line(cleaned))
        else:
            cur["activities"].append(_squash(cleaned))
        i += 1

    flush()
    return experiences


def _parse_projekt_nummer(
    lines: List[str], max_activities: int
) -> List[Dict[str, Any]]:
    """Format D (Stotz): 'Projekt 7 / Jul/Aug 2007' … Kunde Name"""
    experiences: List[Dict[str, Any]] = []
    cur: Optional[Dict[str, Any]] = None

    def flush():
        nonlocal cur
        if not cur:
            return
        cur = _finalize_exp(cur, max_activities)
        if _exp_is_useful(cur):
            experiences.append(cur)
        cur = None

    i = 0
    while i < len(lines):
        ln = lines[i]
        mn = PROJEKT_NUM_RE.match(ln)
        if mn:
            flush()
            cur = _empty_exp()
            # period may include trailing title after nbsp/spaces
            raw_period = _squash(mn.group("period"))
            # split "2004 Bearbeitung …" / "2001-02 Ablösung …"
            pm = re.match(
                r"(?ix)^(?P<p>seit\s+\S+(?:\s+\d{4})?|\d{4}(?:\s*[-–]\s*\d{2,4})?|"
                r"(?:Jan|Feb|Mär|Maerz|Apr|Mai|Jun|Jul|Aug|Sep|Okt|Nov|Dez)"
                r"[a-zäöü]*(?:\s*/\s*(?:Jan|Feb|Mär|Maerz|Apr|Mai|Jun|Jul|Aug|Sep|Okt|Nov|Dez)[a-zäöü]*)?"
                r"\s*\d{4})"
                r"(?:\s+(?P<t>.+))?$",
                raw_period,
            )
            if pm:
                cur["period"] = _squash(pm.group("p"))
                if pm.group("t"):
                    cur["title"] = _squash(pm.group("t"))
            else:
                cur["period"] = raw_period
            i += 1
            continue
        # "Projekte / 2000 - 2006 …" summary line — skip as project start
        if re.match(r"(?im)^\s*Projekte\s*/\s*", ln):
            flush()
            i += 1
            continue
        if cur is None:
            i += 1
            continue
        if _apply_field_line(cur, ln):
            i += 1
            continue
        # normalize nbsp so Kunde····Name matches
        ln_norm = ln.replace("\xa0", " ")
        mk2 = KUNDE_PLAIN_RE.match(ln_norm) or KUNDE_PLAIN_RE.match(ln)
        if mk2:
            cur["company"] = mk2.group(1).replace("\xa0", " ").strip()
            i += 1
            continue
        if re.match(r"(?i)^\s*Branche\s*$", ln):
            i += 1
            if i < len(lines) and not PROJEKT_NUM_RE.match(lines[i]):
                # next line may be industry or "Kunde …"
                nxt = lines[i]
                if re.match(r"(?i)^\s*Kunde\b", nxt):
                    continue
                cur["industry"] = nxt.strip()
                i += 1
            continue
        if re.match(r"(?i)^\s*Eckdaten\b", ln):
            rest = re.sub(r"(?i)^\s*Eckdaten\s*-?\s*", "", ln).strip()
            if rest:
                cur["activities"].append(_squash(rest))
            i += 1
            continue
        cleaned = re.sub(r"^[•\-\*]\s*", "", ln).strip()
        if not cleaned:
            i += 1
            continue
        if not cur.get("title") and len(cleaned) < 160:
            cur["title"] = cleaned
        else:
            cur["activities"].append(_squash(cleaned))
        i += 1

    flush()
    return experiences


def _count_format_a_signals(lines: List[str]) -> int:
    n = 0
    for ln in lines:
        if KUNDE_RE.match(ln) or PROJEKT_RE.match(ln) or ZEITRAUM_RE.match(ln):
            n += 1
    return n


def _count_period_starts(lines: List[str]) -> int:
    return sum(1 for ln in lines if PERIOD_LINE_RE.match(ln) or ZEITRAUM_RE.match(ln))


def _count_projekt_num(lines: List[str]) -> int:
    return sum(1 for ln in lines if PROJEKT_NUM_RE.match(ln))


def _score_experiences(exps: List[Dict[str, Any]]) -> Tuple[int, int, int]:
    """Prefer dated projects, then with company, then count."""
    n = len(exps)
    with_period = sum(1 for e in exps if (e.get("period") or "").strip())
    with_co = sum(1 for e in exps if (e.get("company") or "").strip())
    return (with_period, with_co, n)


def _looks_like_freeform_title(ln: str) -> bool:
    s = ln.strip().rstrip(":")
    if len(s) < 18 or len(s) > 160:
        return False
    if not s[:1].isupper():
        return False
    if re.match(r"^[·.•\-\*\d]", s):
        return False
    if "·" in s or "•" in s:
        return False
    if re.match(
        r"(?i)^(und|oder|sowie|wie|desweiteren|des\s+weiteren|hierzu|"
        r"gleichzeitig|hierbei|mittels|nachdem|weiterhin|meine|die\s+aufgabe|"
        r"problemen|pack\s+\d|werden|karten|spielen|installiert|migriert)\b",
        s,
    ):
        return False
    if re.search(r"(?i)\b(aufzu-|einbau von|im laufe des)\b", s):
        return False
    if re.search(
        r"(?i)\b(migration|projekt|support|help-?desk|rollout|tätigkeit|"
        r"installation|administration|entwicklung|lösung|troubleshooting|"
        r"user-help|client/server|datenbank|client-migration)\b",
        s,
    ):
        # reject sentence fragments that merely contain those words
        if re.search(r"(?i)\b(bestand darin|im laufe|musste ich|gehörten)\b", s):
            return False
        if s.count(" ") > 18:
            return False
        return True
    if ln.strip().endswith(":") and len(s) > 25:
        return True
    return False


def _parse_freeform_titles(
    lines: List[str], max_activities: int
) -> List[Dict[str, Any]]:
    """
    Format F (Arnold u.a.): Titelzeilen ohne Datum/Kunde-Labels,
    Aktivitäten als · / - Bullets.
    """
    experiences: List[Dict[str, Any]] = []
    cur: Optional[Dict[str, Any]] = None

    def flush():
        nonlocal cur
        if not cur:
            return
        cur = _finalize_exp(cur, max_activities)
        if _exp_is_useful(cur):
            experiences.append(cur)
        cur = None

    for ln in lines:
        mb = PROJEKT_BEI_RE.match(ln)
        if mb:
            flush()
            cur = _empty_exp()
            company = mb.group(1).strip().rstrip(":")
            cur["company"] = company
            cur["title"] = f"Projekt bei {company}"
            continue
        mt = TAETIGKEITEN_BEI_RE.match(ln)
        if mt:
            flush()
            cur = _empty_exp()
            company = mt.group(1).strip().rstrip(":")
            # drop trailing parenthetical noise lightly
            company = re.sub(r"\s*\(.*$", "", company).strip() or company
            cur["company"] = company
            cur["title"] = f"Tätigkeiten bei {company}"
            continue
        if _looks_like_freeform_title(ln) and not PERIOD_LINE_RE.match(ln):
            flush()
            cur = _empty_exp()
            cur["title"] = ln.strip().rstrip(":")
            continue
        if cur is None:
            continue
        if _apply_field_line(cur, ln):
            continue
        cleaned = re.sub(r"^[·.•\-\*]+\s*", "", ln).strip()
        if not cleaned:
            continue
        # hyphen line-wrap leftovers
        if cur["activities"] and cleaned[:1].islower():
            cur["activities"][-1] = _squash(cur["activities"][-1] + " " + cleaned)
        else:
            cur["activities"].append(_squash(cleaned))
    flush()
    return experiences


def _parse_projects_summary_line(
    lines: List[str], max_activities: int
) -> List[Dict[str, Any]]:
    """Ungureanu-style: 'Projects: Germany -> Vodafone, …' single block."""
    blob = " ".join(lines)
    m = re.search(r"(?i)\bProjects?\s*:\s*(.+)", blob)
    if not m:
        return []
    rest = m.group(1).strip()
    # split on ';' into client mentions
    parts = [p.strip() for p in re.split(r"\s*;\s*", rest) if p.strip()]
    if len(parts) < 2:
        # one blob
        cur = _empty_exp()
        cur["title"] = "Projects"
        cur["activities"] = [_squash(rest)[:400]]
        return [_finalize_exp(cur, max_activities)]
    exps = []
    for p in parts[:max_activities]:
        cur = _empty_exp()
        # "Germany -> Vodafone, O2"
        if "->" in p:
            loc, clients = p.split("->", 1)
            cur["location"] = loc.strip()
            cur["company"] = clients.strip()[:80]
            cur["title"] = f"Project {loc.strip()}"
        else:
            cur["title"] = p[:100]
        exps.append(_finalize_exp(cur, max_activities))
    return exps


def _count_freeform_titles(lines: List[str]) -> int:
    n = 0
    for ln in lines:
        if PROJEKT_BEI_RE.match(ln) or TAETIGKEITEN_BEI_RE.match(ln):
            n += 2
        elif _looks_like_freeform_title(ln):
            n += 1
    return n


def _split_referenzen_from_projects(body: str) -> Tuple[str, str]:
    """
    Referenz-Blöcke (Gulp: „Projekt …“ + „Referenz durch …“ + Zitat) aus dem
    Projekte-Body herauslösen → other, nicht experience.
    """
    body = body or ""
    m = re.search(
        r"(?im)^\s*Projekt\s+[^\n]{5,160}\n\s*Referenz\s+durch\b",
        body,
    )
    if not m:
        m = re.search(r"(?im)^\s*(?:Referenz\s+durch|Alle\s+Referenzen)\b", body)
    if not m:
        return body, ""
    start = m.start()
    # „Referenz durch“ ohne Projekt-Zeile davor → vorherige Projekt-Zeile mitnehmen
    if not re.match(r"(?im)^\s*Projekt\s+", body[start : start + 30]):
        prev_lines = body[:start].rstrip().splitlines()
        if prev_lines and re.match(r"(?i)^Projekt\s+", prev_lines[-1].strip()):
            start = body.rfind(prev_lines[-1], 0, start)
    return body[:start].rstrip(), body[start:].strip()


def parse_projects(body: str, max_activities: int = 8) -> List[Dict[str, Any]]:
    body = cut_after_projects_footer(body)
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    lines = [ln for ln in lines if not NOISE_LINE_RE.match(ln)]
    if not lines:
        return []

    sig_a = _count_format_a_signals(lines)
    sig_p = _count_period_starts(lines)
    sig_n = _count_projekt_num(lines)
    sig_f = _count_freeform_titles(lines)

    candidates: List[List[Dict[str, Any]]] = []
    if sig_a >= 2:
        candidates.append(_parse_kunde_projekt_zeitraum(lines, max_activities))
    if sig_p >= 1:
        candidates.append(_parse_period_first(lines, max_activities))
    if sig_n >= 1:
        candidates.append(_parse_projekt_nummer(lines, max_activities))
    # Freeform only when structured signals are weak (else over-splits)
    if sig_f >= 2 and sig_p < 2 and sig_a < 2 and sig_n < 2:
        candidates.append(_parse_freeform_titles(lines, max_activities))
    if not candidates:
        candidates.append(_parse_kunde_projekt_zeitraum(lines, max_activities))
        candidates.append(_parse_period_first(lines, max_activities))
        candidates.append(_parse_projekt_nummer(lines, max_activities))
        if sig_p < 2 and sig_a < 2:
            candidates.append(_parse_freeform_titles(lines, max_activities))
        candidates.append(_parse_projects_summary_line(lines, max_activities))

    best: List[Dict[str, Any]] = []
    best_score = (-1, -1, -1)
    for exps in candidates:
        sc = _score_experiences(exps)
        if sc > best_score:
            best_score = sc
            best = exps

    # Last resort: summary line or freeform if still empty but body is large
    if not best and len(body) > 200:
        for exps in (
            _parse_freeform_titles(lines, max_activities),
            _parse_projects_summary_line(lines, max_activities),
        ):
            if len(exps) > len(best):
                best = exps
    return best


def clean_gulp_profile(
    raw: str,
    *,
    first: str = "",
    last: str = "",
    version: str = "1.0.0.0",
    max_activities: int = 8,
) -> Dict[str, Any]:
    snap = latest_snapshot(raw)
    snap = cut_after_projects_footer(snap)
    snap = strip_noise_lines(snap)
    snap = re.split(r"(?i)GULP Information Services übernimmt", snap)[0].strip()

    personal = extract_personal(snap)
    name = aid_name(first, last, version) if (first or last) else ""
    if name:
        personal["name"] = name
    # drop raw gulp_id from display mapping — kept separately
    gulp_id = personal.pop("gulp_id", "") or ""

    sections = _merge_einsatz_regionen(_split_section_bodies(snap))

    # Clean section bodies
    cleaned_sections: List[Tuple[str, str]] = []
    experiences: List[Dict[str, Any]] = []
    skills: Dict[str, str] = {}
    other_chunks: List[str] = []
    for name_s, body in sections:
        body = strip_noise_lines(body)
        key = name_s.lower().strip()
        if key == "projekte":
            body_proj, ref_text = _split_referenzen_from_projects(body)
            experiences = parse_projects(body_proj, max_activities=max_activities)
            if ref_text:
                other_chunks.append(f"Referenzen:\n{ref_text}")
            continue
        # Skill dumps → skills{} für AID-Plain (nicht verwerfen)
        if any(key == sk or key.startswith(sk) for sk in SKILL_SECTION_KEYS):
            label = SKILL_AID_LABEL.get(key)
            if not label:
                for sk, lab in SKILL_AID_LABEL.items():
                    if key.startswith(sk):
                        label = lab
                        break
            label = label or name_s.strip()
            cleaned = _squash_skill_body(body)
            if cleaned:
                # merge if duplicate heads
                if label in skills:
                    skills[label] = (skills[label] + "\n" + cleaned).strip()
                else:
                    skills[label] = cleaned
            continue
        # Persönliche Stärken / Sonstige Anmerkungen / Referenzen → other
        if key in (
            "persönliche stärken",
            "sonstige anmerkungen",
            "referenzen",
        ) or key.startswith("referenzen"):
            cleaned = _squash_skill_body(body)
            if cleaned:
                other_chunks.append(f"{name_s.strip()}:\n{cleaned}")
            continue
        # Fremdsprachen: one per line, drop empties / skill crumbs
        if key == "fremdsprachen":
            langs = []
            for ln in body.splitlines():
                s = ln.strip()
                if not s or NOISE_LINE_RE.match(s):
                    continue
                # stop if skill-category leaked in
                if re.match(
                    r"(?i)^(hardware|software|betriebssysteme|programmiersprachen|"
                    r"datenbanken|datenkommunikation|aufgabenbereiche|schwerpunkte|"
                    r"produkte|kenntnisse|tools|methoden)\b",
                    s,
                ):
                    break
                langs.append(s)
            body = "\n".join(langs)
        # Position: drop freiberuflich note already via noise; keep role lines
        if key == "position":
            lines = [
                ln.strip()
                for ln in body.splitlines()
                if ln.strip() and not re.search(r"(?i)festanstellung", ln)
            ]
            body = "\n".join(lines)
        # Fachlicher Schwerpunkt: one line squash; Festanstellung-Fließtext abschneiden
        if "schwerpunkt" in key:
            body = _squash(body)
            body = re.split(r"(?i)\bFestanstellung\b", body)[0].strip()
            body = re.split(r"(?i)\bVoraussetzung\s+f[uü]r\b", body)[0].strip()
            body = body.rstrip(" ;,.")
        if "einsatzort" in key:
            body = _clean_einsatzort_body(body)
        if body.strip():
            cleaned_sections.append((name_s, body))

    # Display personal rows (ordered) — Stundensatz bewusst weggelassen (kein Matching)
    personal_rows: List[Tuple[str, str]] = []
    if personal.get("name"):
        personal_rows.append(("Name", personal["name"]))
    if personal.get("wohnort"):
        personal_rows.append(("Wohnort", personal["wohnort"]))
    if personal.get("jahrgang"):
        personal_rows.append(("Jahrgang", personal["jahrgang"]))
    if personal.get("edv_seit"):
        personal_rows.append(("EDV-Erfahrung seit", personal["edv_seit"]))
    if personal.get("verfuegbar"):
        personal_rows.append(("Verfügbar ab", personal["verfuegbar"]))
    # Stundensatz nicht in personal_rows / AID-Plain
    personal.pop("stundensatz", None)

    return {
        "gulp_id": gulp_id,
        "aid_name": personal.get("name", ""),
        "personal": personal,
        "personal_rows": personal_rows,
        "sections": cleaned_sections,
        "skills": skills,
        "experience": experiences,
        "other": "\n\n".join(other_chunks).strip(),
        "snapshot_chars": len(snap),
    }


def _squash_skill_body(body: str) -> str:
    """Skill-Sektion bereinigen, Länge begrenzen."""
    lines = []
    for ln in (body or "").splitlines():
        s = ln.strip()
        if not s or NOISE_LINE_RE.match(s):
            continue
        if re.match(r"(?i)^(seite\s+drucken|zum\s+seitenanfang|links:)", s):
            continue
        lines.append(s)
    text = "\n".join(lines).strip()
    if len(text) > SKILL_BODY_MAX_CHARS:
        text = text[: SKILL_BODY_MAX_CHARS].rsplit("\n", 1)[0] + "\n…"
    return text


def _clean_einsatzort_body(body: str) -> str:
    """
    Gulp-Einsatzort oft:
      D8
      im Umkreis von:
      Augsburg (100 km)
      …
      Ich möchte BEVORZUGT …
    Oder geklebt: 'DeutschlandKommentar: Bevorzugt Berlin…'
    """
    body = body or ""
    # geklebte Varianten ohne Leerzeichen
    body = re.split(r"(?i)Kommentar\s*:\s*", body)[0]
    body = re.split(r"(?i)Kommentar\s+zum\s+Einsatzort", body)[0]
    body = re.split(r"(?i)zur\s+Arbeitserlaubnis", body)[0]
    body = re.split(r"(?i)Ich möchte BEVORZUGT", body)[0]
    body = re.split(r"(?i)Bevorzugt\b", body)[0]
    body = re.split(r"(?i)Kontaktwunsch\s*:", body)[0]
    body = re.split(r"(?i)Projekte mit hohem Remote", body)[0]
    body = re.split(r"(?i)Anstellung\s+ausschlie", body)[0]
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    if not lines:
        return ""
    kept: List[str] = []
    for ln in lines:
        if len(ln) > 120:
            break
        if re.match(r"(?i)^(fremdsprachen|projekte|hardware|kenntnisse)\b", ln):
            break
        kept.append(ln)
    if not kept:
        return ""
    primary = " ".join(kept)
    primary = re.sub(r"\s+", " ", primary).strip(" ;,.")
    if len(primary) > 200:
        primary = primary[:200].rsplit(" ", 1)[0]
    return primary


def _dedupe_lang_list(langs: str) -> str:
    """'Deutsch, Deutsch (Muttersprache), Englisch' → eindeutig."""
    if not langs:
        return ""
    seen = set()
    out = []
    for part in re.split(r"\s*,\s*", langs):
        p = part.strip()
        if not p:
            continue
        # Basis-Sprache: erstes Wort vor Klammer/Niveau
        base = re.split(r"[\(:]", p, 1)[0].strip().lower()
        base = re.split(r"\s+", base)[0] if base else ""
        if not base or base in seen:
            continue
        seen.add(base)
        out.append(p)
    return ", ".join(out)


def _section_map(profile: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for heading, body in profile.get("sections") or []:
        key = (heading or "").strip().lower()
        out[key] = body
    return out


def _schwerpunkt(profile: Dict[str, Any]) -> str:
    sm = _section_map(profile)
    for k, v in sm.items():
        if "schwerpunkt" in k:
            return _squash(v)
    return ""


def _sprachen(profile: Dict[str, Any]) -> str:
    sm = _section_map(profile)
    for k, v in sm.items():
        if "fremdsprachen" in k or k == "sprachen":
            langs = [ln.strip() for ln in v.splitlines() if ln.strip()]
            raw = ", ".join(langs) if langs else _squash(v)
            return _dedupe_lang_list(raw)
    return ""


def _einsatzort(profile: Dict[str, Any]) -> str:
    sm = _section_map(profile)
    for k, v in sm.items():
        if "einsatzort" in k or "regionen" in k:
            return _clean_einsatzort_body(v)
    return (profile.get("personal") or {}).get("wohnort", "")


def _fachbereich_lines(profile: Dict[str, Any]) -> List[str]:
    """Fachbereiche + Position → Bullet-Zeilen für AID-Block."""
    sm = _section_map(profile)
    lines: List[str] = []
    schw = _schwerpunkt(profile)
    if schw:
        # Schwerpunkt-CSV → einzelne Fachbereichs-Zeilen
        for part in re.split(r"\s*,\s*", schw):
            part = part.strip()
            if part and len(part) > 1:
                lines.append(part)
    for k, v in sm.items():
        if k == "position" or k.startswith("position"):
            for ln in v.splitlines():
                ln = ln.strip()
                if ln and ln not in lines:
                    lines.append(ln)
    # dedupe preserve order
    seen = set()
    out = []
    for ln in lines:
        low = ln.lower()
        if low not in seen:
            seen.add(low)
            out.append(ln)
    return out


def _section_body_by_keys(profile: Dict[str, Any], *keys: str) -> str:
    """Erste Section deren Kopf (lower) einem der Keys entspricht/startet."""
    sm = _section_map(profile)
    for key in keys:
        key_l = key.lower()
        for k, v in sm.items():
            if k == key_l or k.startswith(key_l):
                return (v or "").strip()
    return ""


def _emit_plain_block(lines: List[str], heading: str, body: str, *, colon: bool = False) -> None:
    """AID-Plain Block: Überschrift + Body-Zeilen (Noise/leer überspringen)."""
    body = (body or "").strip()
    if not body:
        return
    if colon:
        lines.append(f"{heading}:")
    else:
        lines.append(heading)
    lines.append("")
    for ln in body.splitlines():
        s = ln.strip()
        if not s or NOISE_LINE_RE.match(s):
            continue
        if re.match(r"(?i)^(seite\s+drucken|zum\s+seitenanfang|links:)", s):
            continue
        lines.append(s)
    lines.append("")


def profile_to_aid_plain(profile: Dict[str, Any], *, display_name: str = "") -> str:
    """
    Plaintext im abcona/AID-Layout — für aid_regex_extractor Fast-Path
    (mind. 3/5 ABCONA_SIGNALS + Format-A Projekte).
    """
    aid = profile.get("aid_name") or "AID-xx_1.0.0.0"
    pers = profile.get("personal") or {}
    person_label = display_name.strip() if display_name else ""
    lines: List[str] = []

    # Seite-1-Signale (abcona / Bornhohl / office / AID)
    lines.append(f"Qualifikationsprofil: {aid} www.abcona.de")
    lines.append("")
    lines.append(aid)
    lines.append("")
    schw = _schwerpunkt(profile)
    if schw:
        lines.append(f"Schwerpunkt: {schw}")
        lines.append("")
    lines.append("abcona e. K.")
    lines.append("active business consulting agency")
    lines.append("")
    lines.append("Bornhohl 26")
    lines.append("61449 Steinbach")
    lines.append("")
    lines.append("Telefon  +49 (0) 61 71 - 8867 - 00")
    lines.append("Fax   +49 (0) 61 71 - 8867 - 09")
    lines.append("")
    lines.append("E-Mail office@abcona.de")
    lines.append("Internet http://www.abcona.de")
    lines.append("")
    lines.append("Persönliche Daten")
    lines.append("")
    lines.append(f"Name: {aid}")
    if person_label:
        lines.append(f"Berater: {person_label}")
    if pers.get("jahrgang"):
        lines.append(f"Geburtsjahr: {pers['jahrgang']}")
    if pers.get("wohnort"):
        lines.append(f"Wohnort: {pers['wohnort']}")
    langs = _sprachen(profile)
    if langs:
        lines.append(f"Sprachen: {langs}")
    if pers.get("edv_seit"):
        lines.append(f"EDV Erfahrung seit: {pers['edv_seit']}")
    if pers.get("verfuegbar"):
        lines.append(f"verfügbar: {pers['verfuegbar']}")
    einsatz = _einsatzort(profile)
    if einsatz:
        lines.append(f"Einsatzort: {einsatz}")
    lines.append("")

    fach = _fachbereich_lines(profile)
    if fach:
        lines.append("Fachbereiche")
        lines.append("")
        for f in fach:
            lines.append(f)
        lines.append("")

    # Ausbildung / Zertifizierungen / Branchen — eigene AID-Blöcke für aid_regex
    # (aid_regex erwartet u.a. „Ausbildung:“ mit Doppelpunkt)
    _emit_plain_block(
        lines,
        "Ausbildung",
        _section_body_by_keys(profile, "ausbildung"),
        colon=True,
    )
    _emit_plain_block(
        lines,
        "Zertifizierungen",
        _section_body_by_keys(profile, "zertifizierungen", "zertifikate"),
        colon=False,
    )
    _emit_plain_block(
        lines,
        "Branchen",
        _section_body_by_keys(profile, "branchen", "branche"),
        colon=False,
    )

    # Skill-Kataloge aus Gulp (aid_regex: Betriebssysteme/Programmiersprachen/…)
    skills = profile.get("skills") or {}
    # stabile Reihenfolge
    skill_order = [
        "Betriebssysteme",
        "Programmiersprachen",
        "Datenbanken",
        "Hardware",
        "Softwaretechnologien",
        "Tools",
        "Methoden",
        "Datenkommunikation",
        "Sonstige Kenntnisse",
        "Produkte|Standards|Erfahrungen",
        "Aufgabenbereiche",
        "Schwerpunkte",
        "Managementerfahrung",
    ]
    emitted = set()
    for lab in skill_order:
        body = (skills.get(lab) or "").strip()
        if not body:
            continue
        lines.append(lab)
        lines.append("")
        for ln in body.splitlines():
            ln = ln.strip()
            if ln:
                lines.append(ln)
        lines.append("")
        emitted.add(lab)
    for lab, body in skills.items():
        if lab in emitted:
            continue
        body = (body or "").strip()
        if not body:
            continue
        lines.append(lab)
        lines.append("")
        for ln in body.splitlines():
            ln = ln.strip()
            if ln:
                lines.append(ln)
        lines.append("")

    exps = profile.get("experience") or []
    if exps:
        lines.append("Berufliche Erfahrungen")
        lines.append("")
        for exp in exps:
            period = (exp.get("period") or "").strip()
            company = (exp.get("company") or "").strip()
            title = (exp.get("title") or "").strip()
            location = (exp.get("location") or "").strip()
            role = (exp.get("role") or "").strip()
            industry = (exp.get("industry") or "").strip()
            # Format-A Trenner braucht Zeitraum: — sonst aid_regex sieht 0 Projekte
            lines.append(f"Zeitraum: {period if period else 'k.A.'}")
            if company:
                lines.append(f"Firma/Institut: {company}")
                # auch Kunde / Branche (neueres AID-Format)
                br = industry or company
                lines.append(f"Kunde / Branche: {br}")
            if role:
                lines.append(f"Rolle / Position: {role}")
            if title:
                if location:
                    lines.append(f"Projektbeschreibung: {title}, {location}")
                else:
                    lines.append(f"Projektbeschreibung: {title}")
            for a in exp.get("activities") or []:
                a = (a or "").strip()
                if a:
                    lines.append(f"• {a}")
            techs = [t for t in (exp.get("technologies") or []) if t]
            if techs:
                lines.append("Systemumgebung: " + ", ".join(techs))
            lines.append("")
            lines.append("")

    # Sonstiges → pre_json.other / OtherContent (Stärken, Anmerkungen, Referenzen)
    other = (profile.get("other") or "").strip()
    if other:
        lines.append("Sonstiges")
        lines.append("")
        for ln in other.splitlines():
            s = ln.rstrip()
            if s.strip():
                lines.append(s)
            else:
                lines.append("")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def profile_to_html(profile: Dict[str, Any], *, display_title: str = "") -> str:
    """AID-kompatibles HTML (LibreOffice → PDF) für aid_regex_extractor."""
    import html as html_mod

    aid = profile.get("aid_name") or "AID-xx_1.0.0.0"
    plain = profile_to_aid_plain(profile, display_name=display_title)
    # Zeilen → einfaches HTML, Labels fett
    body_parts = []
    for raw in plain.splitlines():
        line = raw.rstrip()
        if not line:
            body_parts.append("<br>")
            continue
        if line in (
            "Persönliche Daten",
            "Fachbereiche",
            "Ausbildung",
            "Ausbildung:",
            "Zertifizierungen",
            "Branchen",
            "Berufliche Erfahrungen",
            "Sonstiges",
        ) or re.match(r"(?i)^Ausbildung\s*:?\s*$", line):
            body_parts.append(f"<h2>{html_mod.escape(line.rstrip(':'))}</h2>")
            continue
        if line.startswith("Qualifikationsprofil:"):
            body_parts.append(
                f"<p class='hdr'>{html_mod.escape(line)}</p>"
            )
            continue
        if line == aid or re.match(r"^AID-[a-z]{2,4}_", line, re.I):
            body_parts.append(f"<h1>{html_mod.escape(line)}</h1>")
            continue
        if line.startswith("• ") or line.startswith("- "):
            body_parts.append(f"<p class='bullet'>{html_mod.escape(line)}</p>")
            continue
        m = re.match(r"^([^:]{2,40}):\s*(.*)$", line)
        if m and not line.lower().startswith("http"):
            lab, val = m.group(1), m.group(2)
            body_parts.append(
                f"<p><span class='lab'>{html_mod.escape(lab)}:</span> "
                f"{html_mod.escape(val)}</p>"
            )
            continue
        body_parts.append(f"<p>{html_mod.escape(line)}</p>")

    return "\n".join(
        [
            "<!DOCTYPE html><html><head><meta charset='utf-8'>",
            f"<title>{html_mod.escape(aid)}</title>",
            "<style>",
            "body{font-family:DejaVu Sans,Arial,sans-serif;font-size:10.5pt;"
            "line-height:1.35;margin:16mm;color:#111;}",
            "h1{font-size:16pt;margin:8pt 0 12pt 0;}",
            "h2{font-size:12pt;margin:16pt 0 8pt 0;border-bottom:1px solid #333;"
            "padding-bottom:2pt;}",
            "p{margin:0 0 3pt 0;}",
            "p.hdr{font-size:9pt;color:#444;}",
            "p.bullet{margin:0 0 2pt 12pt;}",
            "span.lab{font-weight:bold;}",
            "</style></head><body>",
            *body_parts,
            "</body></html>",
        ]
    )


def profile_to_plain(profile: Dict[str, Any]) -> str:
    """Alias: AID-Plain (Pipeline-tauglich)."""
    return profile_to_aid_plain(profile)
