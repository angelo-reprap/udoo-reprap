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
    ("stundensatz", re.compile(r"Stundensatz\s+([^\n]+?)(?=\s+(?:Verfügbar|Verfuegbar|EDV-Erfahrung|Profil\s+erstellt)\b|$)", re.I)),
    ("edv_seit", re.compile(r"EDV-Erfahrung\s+seit\s+(\d{4})", re.I)),
    ("verfuegbar", re.compile(
        r"Verf(?:ü|ue)gbar\s+ab\s+(.+?)(?=\s+Profil\s+erstellt\b|\s+Lesen\s+von\b|$)",
        re.I | re.S,
    )),
]

SECTION_HEAD_RE = re.compile(
    r"(?im)^\s*(Fachlicher\s+Schwerpunkt|Position|Einsatzort|Regionen|"
    r"Fremdsprachen|Projekte|Branchen|Zertifizierungen|Ausbildung|"
    r"Kenntnisse|Hardware|Software|Tools|Methoden)\s*:?\s*$"
)

# Inline heads that sit mid-line after Stammdaten dump
INLINE_SECTION_RE = re.compile(
    r"(?i)\b(Fachlicher\s+Schwerpunkt|Position|Einsatzort|Regionen|"
    r"Fremdsprachen|Projekte)\s*:\s*"
)

KUNDE_RE = re.compile(r"(?im)^\s*Kunde\s*:\s*(.+?)\s*$")
PROJEKT_RE = re.compile(r"(?im)^\s*Projekt\s*:\s*(.+?)\s*$")
ZEITRAUM_RE = re.compile(r"(?im)^\s*Zeitraum\s*:\s*(.+?)\s*$")
TECH_HINT_RE = re.compile(
    r"(?i)(?:^|\b)(?:cisco|juniper|nortel|brocade|f5|hp-|aperture|nexus|"
    r"dwdm|lan/san|switch|firewall|ansible|linux|windows|excel|exel)\b"
)
DOC_TECH_RE = re.compile(r"(?i)^\s*Dokumentation\s*:\s*(.+)$")
MONTAGE_TECH_RE = re.compile(
    r"(?i)^\s*(?:Montage\s+der\s+passiven\s+und\s+aktiven\s+Komponenten\s*:?\s*)?$"
)


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
    cut = re.split(
        r"(?im)^\s*(?:Seite\s+drucken|Zum\s+Seitenanfang|"
        r"GULP Information Services|Links:\s*$)",
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
            r"(?i)^(kunde|projekt|zeitraum)\s*:", ln
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


def _split_section_bodies(text: str) -> List[Tuple[str, str]]:
    """Find section headings (line-start or inline after Stammdaten) and bodies."""
    # Normalize inline headings onto own lines for easier split
    t = INLINE_SECTION_RE.sub(lambda m: "\n" + m.group(1).title().replace("Fachlicher Schwerpunkt", "Fachlicher Schwerpunkt") + ":\n", text)
    # Fix casing of known heads
    t = re.sub(r"(?i)\bfachlicher\s+schwerpunkt\s*:", "Fachlicher Schwerpunkt:", t)
    t = re.sub(r"(?i)\bposition\s*:", "Position:", t)
    t = re.sub(r"(?i)\beinsatzort\s*:", "Einsatzort:", t)
    t = re.sub(r"(?i)\bregionen\s*:", "Regionen:", t)
    t = re.sub(r"(?i)\bfremdsprachen\s*:", "Fremdsprachen:", t)
    t = re.sub(r"(?i)\bprojekte\s*:", "Projekte:", t)

    heads = list(re.finditer(
        r"(?im)^\s*(Fachlicher\s+Schwerpunkt|Position|Einsatzort|Regionen|"
        r"Fremdsprachen|Projekte|Branchen|Zertifizierungen|Ausbildung|"
        r"Kenntnisse)\s*:?\s*$",
        t,
    ))
    if not heads:
        return []
    parts: List[Tuple[str, str]] = []
    for i, h in enumerate(heads):
        name = re.sub(r"\s+", " ", h.group(1)).strip()
        start = h.end()
        end = heads[i + 1].start() if i + 1 < len(heads) else len(t)
        body = t[start:end].strip()
        parts.append((name, body))
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


def parse_projects(body: str, max_activities: int = 8) -> List[Dict[str, Any]]:
    body = cut_after_projects_footer(body)
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    lines = [ln for ln in lines if not NOISE_LINE_RE.match(ln)]
    experiences: List[Dict[str, Any]] = []
    cur: Optional[Dict[str, Any]] = None

    def empty_exp() -> Dict[str, Any]:
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

    def flush():
        nonlocal cur
        if not cur:
            return
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
        experiences.append(cur)
        cur = None

    i = 0
    while i < len(lines):
        ln = lines[i]
        mk = KUNDE_RE.match(ln)
        mp = PROJEKT_RE.match(ln)
        mz = ZEITRAUM_RE.match(ln)

        if mk:
            flush()
            cur = empty_exp()
            cur["company"] = mk.group(1).strip()
            i += 1
            continue

        if mp:
            if cur is None:
                cur = empty_exp()
            title = mp.group(1).strip().rstrip(",")
            loc_bits: List[str] = []
            j = i + 1
            # Consume continuation until Zeitraum / next Kunde / next Projekt
            while j < len(lines):
                nxt = lines[j]
                if KUNDE_RE.match(nxt) or PROJEKT_RE.match(nxt) or ZEITRAUM_RE.match(nxt):
                    break
                if _is_tech_line(nxt) or re.match(
                    r"(?i)^\s*Montage\s+der\s+passiven", nxt
                ):
                    break
                if _looks_like_location(nxt) and not title.endswith(","):
                    # location after title complete
                    loc_bits.append(nxt.strip().rstrip(","))
                    j += 1
                    continue
                if _looks_like_location(nxt) and title.endswith(","):
                    # still could be title fragment "… Tagesgeschäft, Datacenter…"
                    # Prefer location when line is primarily place names
                    if re.match(r"(?i)^\s*Datacenter\b", nxt):
                        loc_bits.append(nxt.strip().rstrip(","))
                        j += 1
                        continue
                # title continuation (wrapped)
                if not re.match(
                    r"(?i)^(unterst|planung|aufnahme|bearbeitung|analyse|austausch|neuaufbau|troubleshooting|patcharbeiten)\b",
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
                cur = empty_exp()
            cur["period"] = _squash(mz.group(1))
            i += 1
            continue

        if cur is None:
            i += 1
            continue

        if re.match(r"(?i)^\s*Montage\s+der\s+passiven\s+und\s+aktiven\s+Komponenten\s*:?\s*$", ln):
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
    for name_s, body in sections:
        body = strip_noise_lines(body)
        if name_s.lower() == "projekte":
            experiences = parse_projects(body, max_activities=max_activities)
            continue
        # Fremdsprachen: one per line, drop empties
        if name_s.lower() == "fremdsprachen":
            langs = [ln.strip() for ln in body.splitlines() if ln.strip() and not NOISE_LINE_RE.match(ln.strip())]
            body = "\n".join(langs)
        # Position: drop freiberuflich note already via noise; keep role lines
        if name_s.lower() == "position":
            lines = [
                ln.strip()
                for ln in body.splitlines()
                if ln.strip() and not re.search(r"(?i)festanstellung", ln)
            ]
            body = "\n".join(lines)
        # Fachlicher Schwerpunkt: one line squash
        if "schwerpunkt" in name_s.lower():
            body = _squash(body)
        if "einsatzort" in name_s.lower():
            body = _squash(body)
            body = re.sub(r"(?i)\s*Ich möchte BEVORZUGT.*$", "", body).strip()
        cleaned_sections.append((name_s, body))

    # Display personal rows (ordered)
    personal_rows: List[Tuple[str, str]] = []
    if personal.get("name"):
        personal_rows.append(("Name", personal["name"]))
    if personal.get("wohnort"):
        personal_rows.append(("Wohnort", personal["wohnort"]))
    if personal.get("jahrgang"):
        personal_rows.append(("Jahrgang", personal["jahrgang"]))
    if personal.get("stundensatz"):
        personal_rows.append(("Stundensatz", personal["stundensatz"]))
    if personal.get("edv_seit"):
        personal_rows.append(("EDV-Erfahrung seit", personal["edv_seit"]))
    if personal.get("verfuegbar"):
        personal_rows.append(("Verfügbar ab", personal["verfuegbar"]))

    return {
        "gulp_id": gulp_id,
        "aid_name": personal.get("name", ""),
        "personal": personal,
        "personal_rows": personal_rows,
        "sections": cleaned_sections,
        "experience": experiences,
        "snapshot_chars": len(snap),
    }


def profile_to_html(profile: Dict[str, Any], *, display_title: str = "") -> str:
    import html as html_mod

    title = display_title or profile.get("aid_name") or "AID Gulp Profil"
    blocks = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        f"<title>{html_mod.escape(title)}</title>",
        "<style>",
        "body{font-family:DejaVu Sans,Arial,sans-serif;font-size:10.5pt;line-height:1.35;margin:18mm;color:#111;}",
        "h1{font-size:16pt;margin:0 0 10pt 0;}",
        "h2{font-size:12pt;margin:16pt 0 6pt 0;border-bottom:1px solid #333;padding-bottom:2pt;}",
        "h3{font-size:11pt;margin:12pt 0 4pt 0;}",
        "table.meta{border-collapse:collapse;margin:0 0 10pt 0;}",
        "table.meta td{padding:2pt 10pt 2pt 0;vertical-align:top;}",
        "table.meta td.k{font-weight:bold;white-space:nowrap;}",
        "ul{margin:4pt 0 8pt 18pt;padding:0;} li{margin:0 0 3pt 0;}",
        ".exp{margin:0 0 12pt 0;}",
        ".exp .row{margin:0 0 2pt 0;}",
        ".label{font-weight:bold;}",
        ".sep{color:#999;margin:8pt 0;letter-spacing:2pt;}",
        "</style></head><body>",
        f"<h1>{html_mod.escape(title)}</h1>",
    ]

    if profile.get("personal_rows"):
        blocks.append("<h2>Stammdaten</h2><table class='meta'>")
        for k, v in profile["personal_rows"]:
            blocks.append(
                f"<tr><td class='k'>{html_mod.escape(k)}</td>"
                f"<td>{html_mod.escape(v)}</td></tr>"
            )
        blocks.append("</table>")
        blocks.append("<div class='sep'>####</div>")

    for heading, body in profile.get("sections") or []:
        blocks.append(f"<h2>{html_mod.escape(heading)}</h2>")
        for para in body.splitlines():
            para = para.strip()
            if para:
                blocks.append(f"<p>{html_mod.escape(para)}</p>")
        blocks.append("<div class='sep'>####</div>")

    exps = profile.get("experience") or []
    if exps:
        blocks.append("<h2>Projekte / Experience</h2>")
        for idx, exp in enumerate(exps, 1):
            blocks.append(f"<div class='exp'><h3>Projekt {idx}</h3>")
            for key, label in (
                ("company", "Kunde / company"),
                ("title", "Projekt / title"),
                ("period", "Zeitraum / period"),
                ("location", "Ort / location"),
                ("role", "Rolle / role"),
                ("industry", "Branche / industry"),
            ):
                val = (exp.get(key) or "").strip()
                if val:
                    blocks.append(
                        f"<p class='row'><span class='label'>{label}:</span> {html_mod.escape(val)}</p>"
                    )
            acts = [a for a in (exp.get("activities") or []) if a]
            if acts:
                blocks.append("<p class='label'>activities:</p><ul>")
                for a in acts:
                    blocks.append(f"<li>{html_mod.escape(a)}</li>")
                blocks.append("</ul>")
            techs = [t for t in (exp.get("technologies") or []) if t]
            if techs:
                blocks.append(
                    "<p class='row'><span class='label'>technologies:</span> "
                    + html_mod.escape(", ".join(techs))
                    + "</p>"
                )
            blocks.append("</div>")
            if idx < len(exps):
                blocks.append("<div class='sep'>###</div>")

    blocks.append("</body></html>")
    return "\n".join(blocks)


def profile_to_plain(profile: Dict[str, Any]) -> str:
    lines: List[str] = []
    for k, v in profile.get("personal_rows") or []:
        lines.append(f"{k}: {v}")
    if profile.get("personal_rows"):
        lines.append("#####")
    for heading, body in profile.get("sections") or []:
        lines.append("")
        lines.append(heading)
        lines.append(body)
        lines.append("####")
    exps = profile.get("experience") or []
    if exps:
        lines.append("")
        lines.append("Projekte / experience")
        for idx, exp in enumerate(exps, 1):
            lines.append(f"— Projekt {idx}")
            for key in ("company", "title", "period", "location", "role", "industry"):
                if exp.get(key):
                    lines.append(f"  {key}: {exp[key]}")
            if exp.get("activities"):
                lines.append("  activities:")
                for a in exp["activities"]:
                    lines.append(f"    - {a}")
            if exp.get("technologies"):
                lines.append("  technologies: " + ", ".join(exp["technologies"]))
            if idx < len(exps):
                lines.append("###")
    return "\n".join(lines).strip() + "\n"
