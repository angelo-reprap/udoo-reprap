#!/usr/bin/env bash
# Keyword-/Sektions-Inventur über exportierte gulp_profil_c TXT.
# Kein PDF, kein DB-Write — nur Detection-Coverage.
#
# Auf ucs5:
#   SAMPLE_DIR=/tmp/gulp-samples-20260820-151445 \
#     bash <(git -C /mnt/public/udoo-reprap show origin/cursor/aid-sch-sss-dupes-1532:scripts/ANALYZE-gulp-keywords.sh)
#
set -euo pipefail

SAMPLE_DIR="${SAMPLE_DIR:-/tmp/gulp-samples-20260820-151445}"
OUT="${OUT:-$SAMPLE_DIR/keyword-analysis-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$OUT"

if [[ ! -d "$SAMPLE_DIR/txt" ]]; then
  echo "FAIL: $SAMPLE_DIR/txt fehlt" >&2
  exit 1
fi

python3 - <<'PY' "$SAMPLE_DIR" "$OUT"
import re, sys, json
from pathlib import Path
from collections import Counter, defaultdict

sample_dir = Path(sys.argv[1])
out = Path(sys.argv[2])
files = sorted((sample_dir / "txt").glob("*.txt"))
if not files:
    print("FAIL: keine txt", file=sys.stderr)
    sys.exit(2)

# Zeilen die wie Labels aussehen: "Foo:" oder "Foo Bar:" am Zeilenanfang
LABEL_LINE = re.compile(
    r"(?m)^\s*([A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß0-9 /|&\-]{0,60}?)\s*:\s*(.*)$"
)
# Reine Sektionsköpfe ohne Doppelpunkt (selten)
SECTION_BARE = re.compile(
    r"(?m)^\s*(Stammdaten|Personendaten|Projekte|Projektübersicht|"
    r"Fachlicher\s+Schwerpunkt|Ausbildung|Zertifizierungen?|"
    r"Hardware|Betriebssysteme|Programmiersprachen|Datenbanken|"
    r"Fremdsprachen|Branchen|Einsatzort|Regionen|Position|"
    r"Kommentar|Verfügbar)\s*$",
    re.IGNORECASE,
)
SEP = re.compile(r"(?m)^\s*={5,}\s*$")
GULP_HEADER = re.compile(r"Recherche\s*\||Anfragen_an_ID_|GULP\s*-|Profil ID\s*\d+", re.I)
FOOTER = re.compile(r"GULP Information Services|Seite generiert am|© Copyright", re.I)

# bekannte Ziel-Keywords (v0 — Coverage messen)
KNOWN = [
    "Stammdaten", "Personendaten", "Personen-ID", "Wohnort", "Jahrgang",
    "Staatsbürgerschaft", "Stundensatz", "Verfügbar ab", "Fachlicher Schwerpunkt",
    "Schwerpunkt", "Position", "Ausbildung", "Abschluss", "Institution",
    "Einsatzort", "Regionen", "Fremdsprachen", "Hardware", "Betriebssysteme",
    "Programmiersprachen", "Datenbanken", "Branchen", "Projekte", "Rolle",
    "Kunde", "Aufgaben", "Kenntnisse", "Eingesetzte Produkte", "Kommentar",
    "Profil erstellt am", "Profil zuletzt geändert am",
]

def norm_label(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip())
    return s

label_docs = Counter()          # label -> #docs containing
label_hits = Counter()          # label -> total occurrences
known_doc_hits = Counter()      # known keyword -> #docs
per_file = []
unmatched_labels = Counter()    # labels not in KNOWN (fuzzy)

known_l = {k.lower(): k for k in KNOWN}

def is_known(lab: str) -> str | None:
    low = lab.lower()
    if low in known_l:
        return known_l[low]
    for k, orig in known_l.items():
        if k in low or low in k:
            return orig
    return None

for fp in files:
    text = fp.read_text(encoding="utf-8", errors="replace")
    labs_in_doc = set()
    known_in_doc = set()
    n_sep = len(SEP.findall(text))
    has_header = bool(GULP_HEADER.search(text[:800]))
    has_footer = bool(FOOTER.search(text[-1500:]))

    for m in LABEL_LINE.finditer(text):
        lab = norm_label(m.group(1))
        if len(lab) < 2 or len(lab) > 60:
            continue
        # skip URL-ish / nav crumbs
        if lab.lower() in {"http", "https", "www"}:
            continue
        label_hits[lab] += 1
        labs_in_doc.add(lab)
        k = is_known(lab)
        if k:
            known_in_doc.add(k)
        else:
            unmatched_labels[lab] += 1

    for m in SECTION_BARE.finditer(text):
        lab = norm_label(m.group(1))
        label_hits[lab] += 1
        labs_in_doc.add(lab)
        k = is_known(lab)
        if k:
            known_in_doc.add(k)
        else:
            unmatched_labels[lab] += 1

    for lab in labs_in_doc:
        label_docs[lab] += 1
    for k in known_in_doc:
        known_doc_hits[k] += 1

    # grobe Block-Flags
    flags = {
        "file": fp.name,
        "chars": len(text),
        "n_labels": len(labs_in_doc),
        "n_sep_blocks": n_sep,
        "has_nav_header": has_header,
        "has_footer": has_footer,
        "has_projekte": any("projekt" in x.lower() for x in labs_in_doc) or bool(re.search(r"(?im)^\s*Projekte\s*:", text)),
        "has_schwerpunkt": any("schwerpunkt" in x.lower() for x in labs_in_doc),
        "has_ausbildung": any("ausbildung" in x.lower() for x in labs_in_doc),
        "has_skills_table": any(
            x.lower() in {"hardware", "betriebssysteme", "programmiersprachen", "datenbanken"}
            or "programmiersprache" in x.lower()
            for x in labs_in_doc
        ),
        "known_hit_n": len(known_in_doc),
        "known_hit_pct": round(100.0 * len(known_in_doc) / max(len(KNOWN), 1), 1),
    }
    per_file.append(flags)

n = len(files)

# outputs
lines = ["label\tdocs\toccs\tpct_docs\tknown"]
for lab, docs in label_docs.most_common():
    k = "1" if is_known(lab) else "0"
    lines.append(f"{lab}\t{docs}\t{label_hits[lab]}\t{100*docs/n:.0f}\t{k}")
(out / "labels_by_freq.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")

lines = ["known_keyword\tdocs\tpct"]
for k in KNOWN:
    d = known_doc_hits.get(k, 0)
    lines.append(f"{k}\t{d}\t{100*d/n:.0f}")
(out / "known_coverage.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")

lines = ["label\toccs\tdocs_est"]
for lab, occ in unmatched_labels.most_common(80):
    lines.append(f"{lab}\t{occ}\t{label_docs.get(lab,0)}")
(out / "unmatched_labels_top.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")

# per-file tsv
cols = list(per_file[0].keys())
plines = ["\t".join(cols)]
for r in per_file:
    plines.append("\t".join(str(r[c]) for c in cols))
(out / "per_file.tsv").write_text("\n".join(plines) + "\n", encoding="utf-8")

# summary
avg_known = sum(r["known_hit_n"] for r in per_file) / n
summary = {
    "n_files": n,
    "avg_known_keywords_hit": round(avg_known, 1),
    "known_keyword_universe": len(KNOWN),
    "unique_labels_total": len(label_docs),
    "docs_with_projekte": sum(1 for r in per_file if r["has_projekte"]),
    "docs_with_schwerpunkt": sum(1 for r in per_file if r["has_schwerpunkt"]),
    "docs_with_ausbildung": sum(1 for r in per_file if r["has_ausbildung"]),
    "docs_with_skills_table": sum(1 for r in per_file if r["has_skills_table"]),
    "docs_with_sep_blocks": sum(1 for r in per_file if r["n_sep_blocks"] > 0),
    "top_labels": label_docs.most_common(25),
    "top_unmatched": unmatched_labels.most_common(25),
    "known_coverage": {k: known_doc_hits.get(k, 0) for k in KNOWN},
}
(out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print("======== Gulp Keyword Inventur ========")
print(f"files={n}  OUT={out}")
print(f"unique labels: {len(label_docs)}")
print(f"avg known-keyword hits / doc: {avg_known:.1f} / {len(KNOWN)}")
print(f"docs Projekte: {summary['docs_with_projekte']}/{n}")
print(f"docs Schwerpunkt: {summary['docs_with_schwerpunkt']}/{n}")
print(f"docs Ausbildung: {summary['docs_with_ausbildung']}/{n}")
print(f"docs Skill-Tabellen: {summary['docs_with_skills_table']}/{n}")
print(f"docs mit ==== Blöcken: {summary['docs_with_sep_blocks']}/{n}")
print()
print("=== Top Labels (docs) ===")
for lab, d in label_docs.most_common(20):
    print(f"  {100*d/n:3.0f}%  {lab}")
print()
print("=== Known coverage ===")
for k in KNOWN:
    d = known_doc_hits.get(k, 0)
    if d == 0:
        mark = "MISS"
    elif d < n * 0.5:
        mark = "low"
    else:
        mark = "ok"
    print(f"  [{mark:4}] {100*d/n:3.0f}%  {k}")
print()
print("=== Top unmatched (erweitern?) ===")
for lab, occ in unmatched_labels.most_common(20):
    print(f"  {occ:3}×  {lab}")
print()
print(f"labels_by_freq.tsv     {out/'labels_by_freq.tsv'}")
print(f"known_coverage.tsv     {out/'known_coverage.tsv'}")
print(f"unmatched_labels_top.tsv {out/'unmatched_labels_top.tsv'}")
print(f"summary.json           {out/'summary.json'}")
PY
