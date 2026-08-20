#!/usr/bin/env bash
# Gulp-Profil Keyword-Detection v1 — Coverage über TXT-Samples oder CRM-Export-Ordner.
# Kein PDF, kein DB-Write.
#
#   SAMPLE_DIR=/tmp/gulp-samples-20260820-151445 \
#     bash scripts/ANALYZE-gulp-keywords-v1.sh
#
# Optional LIMIT für Stichprobe in SAMPLE_DIR/txt.
#
set -euo pipefail

SAMPLE_DIR="${SAMPLE_DIR:?SAMPLE_DIR=/pfad/zu/gulp-samples}"
OUT="${OUT:-$SAMPLE_DIR/keyword-v1-$(date +%Y%m%d-%H%M%S)}"
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

# ── Keyword-Sets v1 (aus 29er-Inventur + Gulp-Abbady-Muster) ─────────────
# Detection = Label-Zeile ODER Bare-Section; Coverage = mind. 1 Hit / Doc

CORE_SECTIONS = [
    r"Fachlicher\s+Schwerpunkt",
    r"Schwerpunkt",
    r"Position",
    r"Ausbildung",
    r"Projekte",
    r"Projektübersicht",
    r"Branchen",
    r"Fremdsprachen",
    r"Einsatzort",
    r"Regionen",
    r"Kommentar",
    r"Stammdaten(?:\s*\(Auszug\))?",
    r"Personendaten",
]

SKILL_SECTIONS = [
    r"Hardware",
    r"Betriebssysteme",
    r"Programmiersprachen?",
    r"Datenbanken",
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
    r"Personen-ID",
    r"Wohnort",
    r"Jahrgang",
    r"Staatsb[uü]rgerschaft",
    r"Stundensatz",
    r"Verf[uü]gbar\s+ab",
    r"Profil\s+erstellt\s+am",
    r"Profil\s+zuletzt\s+ge[aä]ndert\s+am",
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

# compiled: (group, name, regex)
compiled = []
for group, pats in ALL_GROUPS.items():
    for p in pats:
        compiled.append(
            (group, p, re.compile(rf"(?im)^\s*(?:{p})\s*:?\s*", re.MULTILINE))
        )

LABEL_ANY = re.compile(
    r"(?m)^\s*([A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß0-9 /|&\-]{1,60}?)\s*:\s*"
)
SEP = re.compile(r"(?m)^\s*={5,}\s*$")
NAV = re.compile(r"Recherche\s*\||Anfragen_an_ID_|---------- Gulp-Profil", re.I)

per_file = []
group_doc = defaultdict(Counter)  # group -> pattern -> docs
unmatched = Counter()
all_labels = Counter()

for fp in files:
    text = fp.read_text(encoding="utf-8", errors="replace")
    hit = defaultdict(set)  # group -> set of pattern names
    for group, name, rx in compiled:
        if rx.search(text):
            hit[group].add(name)
            group_doc[group][name] += 1

    # free labels for unmatched
    labs = set()
    for m in LABEL_ANY.finditer(text):
        lab = re.sub(r"\s+", " ", m.group(1).strip())
        labs.add(lab)
        all_labels[lab] += 1
    # which labels not covered by any compiled pattern?
    for lab in labs:
        covered = False
        for group, name, rx in compiled:
            # match label against pattern as full label approx
            if re.match(rf"(?i)^{name}$", lab) or re.search(rf"(?i){name}", lab):
                covered = True
                break
        if not covered:
            unmatched[lab] += 1

    row = {
        "file": fp.name,
        "chars": len(text),
        "has_nav": int(bool(NAV.search(text[:1000]))),
        "n_sep": len(SEP.findall(text)),
        "core_n": len(hit["core_sections"]),
        "skill_n": len(hit["skill_sections"]),
        "proj_field_n": len(hit["project_fields"]),
        "stamm_n": len(hit["stamm_fields"]),
        "has_projekte": int("Projekte" in hit["core_sections"] or "Projektübersicht" in hit["core_sections"]),
        "has_schwerpunkt": int(
            any("Schwerpunkt" in x for x in hit["core_sections"])
        ),
        "has_ausbildung": int("Ausbildung" in hit["core_sections"]),
        "has_skills": int(len(hit["skill_sections"]) >= 2),
        "has_zeitraum": int("Zeitraum" in hit["project_fields"]),
        "ok_min_structure": 0,
    }
    # Mindeststruktur für „regex kann greifen“
    if row["has_projekte"] and (row["has_schwerpunkt"] or row["has_skills"]) and row["has_ausbildung"]:
        row["ok_min_structure"] = 1
    per_file.append(row)

n = len(files)
ok = sum(r["ok_min_structure"] for r in per_file)

# write TSVs
def dump_group(group):
    lines = ["pattern\tdocs\tpct"]
    for pat in ALL_GROUPS[group]:
        d = group_doc[group].get(pat, 0)
        lines.append(f"{pat}\t{d}\t{100*d/n:.0f}")
    (out / f"coverage_{group}.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")

for g in ALL_GROUPS:
    dump_group(g)

cols = list(per_file[0].keys())
lines = ["\t".join(cols)]
for r in per_file:
    lines.append("\t".join(str(r[c]) for c in cols))
(out / "per_file.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")

um = ["label\thits"]
for lab, c in unmatched.most_common(60):
    um.append(f"{lab}\t{c}")
(out / "unmatched_still.tsv").write_text("\n".join(um) + "\n", encoding="utf-8")

summary = {
    "n_files": n,
    "ok_min_structure": ok,
    "ok_pct": round(100 * ok / n, 1),
    "docs_projekte": sum(r["has_projekte"] for r in per_file),
    "docs_schwerpunkt": sum(r["has_schwerpunkt"] for r in per_file),
    "docs_ausbildung": sum(r["has_ausbildung"] for r in per_file),
    "docs_skills": sum(r["has_skills"] for r in per_file),
    "docs_zeitraum": sum(r["has_zeitraum"] for r in per_file),
    "fails": [r["file"] for r in per_file if not r["ok_min_structure"]],
}
(out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print("======== Gulp Keyword Detection v1 ========")
print(f"files={n}  OUT={out}")
print(f"ok_min_structure: {ok}/{n} ({summary['ok_pct']}%)")
print(f"  Projekte:     {summary['docs_projekte']}/{n}")
print(f"  Schwerpunkt:  {summary['docs_schwerpunkt']}/{n}")
print(f"  Ausbildung:   {summary['docs_ausbildung']}/{n}")
print(f"  Skills≥2:     {summary['docs_skills']}/{n}")
print(f"  Zeitraum:     {summary['docs_zeitraum']}/{n}")
if summary["fails"]:
    print("fails:", ", ".join(summary["fails"][:15]))
print()
print("Top still-unmatched:")
for lab, c in unmatched.most_common(15):
    print(f"  {c:3}×  {lab}")
print(f"\nsummary: {out/'summary.json'}")
PY
