#!/usr/bin/env bash
# Gulp-Profil Keyword-Detection v1.1 — Coverage über TXT-Samples.
# Fixes vs v1: NBSP-Normalisierung, Mid-Line-Sektionen (Projekte/Ausbildung),
# Zeitraum mit Spaces um ":", date-led Projektzeilen, Stamm-Inline-Felder.
# Kein PDF, kein DB-Write.
#
#   SAMPLE_DIR=artifacts/gulp-samples-1000 \
#     bash scripts/ANALYZE-gulp-keywords-v1.sh
#
set -euo pipefail

SAMPLE_DIR="${SAMPLE_DIR:?SAMPLE_DIR=/pfad/zu/gulp-samples}"
OUT="${OUT:-$SAMPLE_DIR/keyword-v1.1-$(date +%Y%m%d-%H%M%S)}"
LIMIT="${LIMIT:-0}"
mkdir -p "$OUT"

python3 - <<'PY' "$SAMPLE_DIR" "$OUT" "$LIMIT"
import re, sys, json
from pathlib import Path
from collections import Counter, defaultdict

sample_dir = Path(sys.argv[1])
out = Path(sys.argv[2])
limit = int(sys.argv[3] or "0")

files = sorted((sample_dir / "txt").glob("*.txt"))
if limit > 0:
    files = files[:limit]
if not files:
    raise SystemExit("keine txt in SAMPLE_DIR/txt")

def norm_text(t: str) -> str:
    # NBSP / thin space → space (Zeitraum\xa0\xa0:)
    t = t.replace("\u00a0", " ").replace("\u2009", " ").replace("\u202f", " ")
    return t

CORE_SECTIONS = [
    r"Fachlicher\s+Schwerpunkt",
    r"Schwerpunkt",
    r"Position",
    r"Ausbildung",
    r"(?:Durchgef[uü]hrte\s+)?Projekte",
    r"Projekt[uü]bersicht",
    r"Branchen?",
    r"Fremdsprachen",
    r"Einsatzort",
    r"Regionen",
    r"Kommentar",
    r"Sonstige\s+Anmerkungen",
    r"Stammdaten(?:\s*\(Auszug\))?",
    r"Personendaten",
    r"Zertifizierungen?",
]

SKILL_SECTIONS = [
    r"Hardware",
    r"Betriebssysteme",
    r"Programmiersprachen?",
    r"Datenbanken?",
    r"Datenkommunikation",
    r"Software",
    r"Tools?",
    r"Office\s+Tools?",
    r"Web\s*/\s*Portal-Server",
    r"Repositories",
    r"J2EE\s+Technologien",
    r"J2SE\s+Technologien",
    r"Methodisches\s+Vorgehen",
    r"Produkte\s*/\s*Standards\s*/\s*Erfahrungen",
    r"Produkte\s*\|\s*Standards(?:\s*\|\s*Erfahrungen)?",
    r"Kenntnisse",
    r"EDV[- ]Kenntnisse",
    r"Design/Entwicklung/Konstruktion",
    r"Berechnung/Simulation/Versuch/Validierung",
]

PROJECT_FIELDS = [
    r"Zeitraum",
    r"Dauer",
    r"Rolle",
    r"Kunde",
    r"Firma(?:/Institut)?",
    r"Firma",
    r"Auftrag",
    r"Aufgaben",
    r"Beschreibung",
    r"Kenntnisse",
    r"Eingesetzte\s+Produkte",
    r"Technologie",
    r"Projektumgebung",
    r"Verantwortung",
    r"Referenzen",
]

STAMM_FIELDS = [
    r"Personen[- ]?ID",
    r"Wohnort",
    r"Jahrgang",
    r"Staatsb[uü]rgerschaft",
    r"Stundensatz",
    r"Verf[uü]gbar\s+ab",
    r"Profil\s+erstellt\s+am",
    r"Profil\s+zuletzt\s+ge[aä]ndert\s+am",
    r"EDV[- ]Erfahrung\s+seit",
]

AUSBILDUNG_FIELDS = [
    r"Abschluss",
    r"Institution",
]

ALL_GROUPS = {
    "core_sections": CORE_SECTIONS,
    "skill_sections": SKILL_SECTIONS,
    "project_fields": PROJECT_FIELDS,
    "stamm_fields": STAMM_FIELDS,
    "ausbildung_fields": AUSBILDUNG_FIELDS,
}

# Mid-line OK for core (Gulp wraps "… Unternehmen      Projekte:")
# Prefer label + optional colon; allow leading whitespace OR 2+ spaces after other text.
def compile_label(pat: str, mid_line: bool):
    if mid_line:
        return re.compile(rf"(?im)(?:^|(?<=\s{{2}})|(?<=\t))(?:{pat})\s*:?\s*")
    return re.compile(rf"(?im)^\s*(?:{pat})\s*:?\s*")

compiled = []
for group, pats in ALL_GROUPS.items():
    mid = group in {"core_sections", "project_fields", "stamm_fields"}
    for p in pats:
        compiled.append((group, p, compile_label(p, mid)))

# Zeitraum often: "Zeitraum   : 07/13" after NBSP→space
ZEITRAUM_LOOSE = re.compile(r"(?im)(?:^|(?<=\s))Zeitraum\s*:")

# Date-led project blocks (many profiles omit "Zeitraum:" label)
DATE_LED = re.compile(
    r"(?m)^\s*(?:"
    r"\d{1,2}[./]\d{1,2}[./]\d{2,4}\s*[-–]\s*\d{1,2}[./]\d{1,2}[./]\d{2,4}"
    r"|"
    r"(?:0?[1-9]|1[0-2])[/.-](?:19|20)\d{2}\s*[-–]\s*(?:0?[1-9]|1[0-2]|heute|aktuell|laufend)"
    r"|"
    r"(?:Jan|Feb|Mär|Apr|Mai|Jun|Jul|Aug|Sep|Okt|Nov|Dez)[a-zä.]*\s+(?:19|20)\d{2}\s*[-–]"
    r")",
    re.IGNORECASE,
)

LABEL_ANY = re.compile(
    r"(?m)^\s*([A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß0-9 /|&\-]{1,60}?)\s*:\s*"
)
SEP = re.compile(r"(?m)^\s*={5,}\s*$")
NAV = re.compile(r"Recherche\s*\||Anfragen_an_ID_|---------- Gulp-Profil", re.I)

per_file = []
group_doc = defaultdict(Counter)
unmatched = Counter()
all_labels = Counter()

for fp in files:
    raw = fp.read_text(encoding="utf-8", errors="replace")
    text = norm_text(raw)
    hit = defaultdict(set)
    for group, name, rx in compiled:
        if rx.search(text):
            hit[group].add(name)
            group_doc[group][name] += 1

    has_zeitraum_loose = bool(ZEITRAUM_LOOSE.search(text))
    if has_zeitraum_loose:
        hit["project_fields"].add("Zeitraum")
        group_doc["project_fields"]["Zeitraum"] = group_doc["project_fields"].get("Zeitraum", 0)
        # recount only once per doc — fix below via set already

    n_date_led = len(DATE_LED.findall(text))
    has_date_led = n_date_led >= 1

    labs = set()
    for m in LABEL_ANY.finditer(text):
        lab = re.sub(r"\s+", " ", m.group(1).strip())
        labs.add(lab)
        all_labels[lab] += 1
    for lab in labs:
        covered = False
        for group, name, rx in compiled:
            if re.match(rf"(?i)^{name}$", lab) or re.search(rf"(?i){name}", lab):
                covered = True
                break
        if not covered:
            unmatched[lab] += 1

    has_projekte = any(
        "Projekte" in x or "Projekt" in x for x in hit["core_sections"]
    )
    has_schwerpunkt = any("Schwerpunkt" in x for x in hit["core_sections"])
    has_ausbildung = "Ausbildung" in hit["core_sections"]
    has_skills = len(hit["skill_sections"]) >= 2
    has_zeitraum = "Zeitraum" in hit["project_fields"] or has_zeitraum_loose

    # Projekt-Signal: Sektion ODER genug date-led Zeilen ODER Zeitraum-Feld
    project_signal = has_projekte or has_zeitraum or has_date_led

    row = {
        "file": fp.name,
        "chars": len(text),
        "has_nav": int(bool(NAV.search(text[:1000]))),
        "n_sep": len(SEP.findall(text)),
        "core_n": len(hit["core_sections"]),
        "skill_n": len(hit["skill_sections"]),
        "proj_field_n": len(hit["project_fields"]),
        "stamm_n": len(hit["stamm_fields"]),
        "has_projekte": int(has_projekte),
        "has_schwerpunkt": int(has_schwerpunkt),
        "has_ausbildung": int(has_ausbildung),
        "has_skills": int(has_skills),
        "has_zeitraum": int(has_zeitraum),
        "has_date_led": int(has_date_led),
        "n_date_led": n_date_led,
        "project_signal": int(project_signal),
        "ok_min_structure": 0,
    }
    # Mindeststruktur: Projekte-Signal + (Schwerpunkt|Skills) + Ausbildung
    if project_signal and (has_schwerpunkt or has_skills) and has_ausbildung:
        row["ok_min_structure"] = 1
    per_file.append(row)

# Fix Zeitraum doc count (set-based already in hit; recount from per_file)
# Rebuild group_doc Zeitraum from unique docs
zt = sum(1 for r in per_file if r["has_zeitraum"])
group_doc["project_fields"]["Zeitraum"] = zt

n = len(files)
ok = sum(r["ok_min_structure"] for r in per_file)

def dump_group(group):
    lines = ["pattern\tdocs\tpct"]
    for pat in ALL_GROUPS[group]:
        d = group_doc[group].get(pat, 0)
        lines.append(f"{pat}\t{d}\t{100 * d / n:.0f}")
    (out / f"coverage_{group}.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")

for g in ALL_GROUPS:
    dump_group(g)

cols = list(per_file[0].keys())
lines = ["\t".join(cols)]
for r in per_file:
    lines.append("\t".join(str(r[c]) for c in cols))
(out / "per_file.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")

um = ["label\thits"]
for lab, c in unmatched.most_common(80):
    um.append(f"{lab}\t{c}")
(out / "unmatched_still.tsv").write_text("\n".join(um) + "\n", encoding="utf-8")

fails = [r["file"] for r in per_file if not r["ok_min_structure"]]
(out / "fails.txt").write_text("\n".join(fails) + ("\n" if fails else ""), encoding="utf-8")

summary = {
    "version": "v1.1",
    "n_files": n,
    "ok_min_structure": ok,
    "ok_pct": round(100 * ok / n, 1),
    "docs_projekte": sum(r["has_projekte"] for r in per_file),
    "docs_project_signal": sum(r["project_signal"] for r in per_file),
    "docs_schwerpunkt": sum(r["has_schwerpunkt"] for r in per_file),
    "docs_ausbildung": sum(r["has_ausbildung"] for r in per_file),
    "docs_skills": sum(r["has_skills"] for r in per_file),
    "docs_zeitraum": sum(r["has_zeitraum"] for r in per_file),
    "docs_date_led": sum(r["has_date_led"] for r in per_file),
    "fails_n": len(fails),
    "fails_sample": fails[:30],
}
(out / "summary.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)

print("======== Gulp Keyword Detection v1.1 ========")
print(f"files={n}  OUT={out}")
print(f"ok_min_structure: {ok}/{n} ({summary['ok_pct']}%)")
print(f"  Projekte(label): {summary['docs_projekte']}/{n}")
print(f"  project_signal:  {summary['docs_project_signal']}/{n}")
print(f"  Schwerpunkt:     {summary['docs_schwerpunkt']}/{n}")
print(f"  Ausbildung:      {summary['docs_ausbildung']}/{n}")
print(f"  Skills≥2:        {summary['docs_skills']}/{n}")
print(f"  Zeitraum:        {summary['docs_zeitraum']}/{n}")
print(f"  date_led:        {summary['docs_date_led']}/{n}")
if fails:
    print("fails:", ", ".join(fails[:15]))
print()
print("Top still-unmatched:")
for lab, c in unmatched.most_common(15):
    print(f"  {c:3}×  {lab}")
print(f"\nsummary: {out / 'summary.json'}")
PY
