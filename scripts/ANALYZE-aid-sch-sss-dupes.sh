#!/usr/bin/env bash
# ANALYZE: Duplikate zwischen AID_profile/sch und AID_profile/sss
# (Publish schreibt „Sch…“ oft nach sss/, Import-Ordner liegt unter sch/)
#
# Auf ucs5:
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/aid-sch-sss-dupes-1532
#   bash <(git show origin/cursor/aid-sch-sss-dupes-1532:scripts/ANALYZE-aid-sch-sss-dupes.sh)
#
# Optional:
#   ROOT=/mnt/public/Berater/AID_profile OUT=/tmp/sch-sss-dupes bash …
#
set -euo pipefail

ROOT="${AID_PROFILE_ROOT:-/mnt/public/Berater/AID_profile}"
OUT="${OUT:-/tmp/aid-sch-sss-dupes-$(date +%Y%m%d-%H%M%S)}"
SCH="$ROOT/sch"
SSS="$ROOT/sss"

mkdir -p "$OUT"

echo "======== ANALYZE sch ↔ sss Duplikate ========"
echo "Start: $(date -Iseconds)"
echo "SCH=$SCH"
echo "SSS=$SSS"
echo "OUT=$OUT"
echo

if [[ ! -d "$SCH" ]]; then
  echo "FAIL: $SCH fehlt"
  exit 1
fi
if [[ ! -d "$SSS" ]]; then
  echo "FAIL: $SSS fehlt"
  exit 1
fi

python3 - <<'PY' "$SCH" "$SSS" "$OUT"
import os, re, sys, json
from pathlib import Path
from collections import defaultdict

sch_root = Path(sys.argv[1])
sss_root = Path(sys.argv[2])
out = Path(sys.argv[3])


def norm_key(name: str) -> str:
    """nachname_vorname → vergleichbarer Schlüssel (kein Prefix-Raten)."""
    s = (name or "").strip().lower()
    s = s.replace("ß", "ss")
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue")):
        s = s.replace(a, b)
    # Leerzeichen / Komma / Klammern → Underscore
    s = re.sub(r"[\s,]+", "_", s)
    s = re.sub(r"[^\w\-]+", "_", s, flags=re.UNICODE)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def list_person_dirs(root: Path) -> list[Path]:
    skip = {"neu", "audit", "ada"}
    out = []
    try:
        for p in root.iterdir():
            if not p.is_dir():
                continue
            if p.name in skip or p.name.startswith("Neuer"):
                continue
            out.append(p)
    except OSError as e:
        print(f"WARN listdir {root}: {e}")
    return sorted(out, key=lambda p: p.name.lower())


def has_neu_pdf(d: Path) -> bool:
    neu = d / "neu" / "cv"
    if not neu.is_dir():
        return False
    try:
        return any(neu.glob("AID-*.pdf"))
    except OSError:
        return False


def has_orig_pdf(d: Path) -> bool:
    try:
        for f in d.iterdir():
            if not f.is_file():
                continue
            n = f.name.lower()
            if not n.startswith("aid-") or not n.endswith(".pdf"):
                continue
            if "engl" in n or n.endswith("-en.pdf") or "_en." in n:
                continue
            if "_alt" in n or "loesch" in n or "lösch" in n:
                continue
            return True
    except OSError:
        return False
    return False


sch_dirs = list_person_dirs(sch_root)
sss_dirs = list_person_dirs(sss_root)

sch_by_key: dict[str, list[Path]] = defaultdict(list)
sss_by_key: dict[str, list[Path]] = defaultdict(list)
for p in sch_dirs:
    sch_by_key[norm_key(p.name)].append(p)
for p in sss_dirs:
    sss_by_key[norm_key(p.name)].append(p)

sch_keys = set(sch_by_key)
sss_keys = set(sss_by_key)
both = sorted(sch_keys & sss_keys)
only_sch = sorted(sch_keys - sss_keys)
only_sss = sorted(sss_keys - sch_keys)

# interne Duplikate (gleicher Norm-Key, mehrere Ordner)
intra_sch = {k: v for k, v in sch_by_key.items() if len(v) > 1}
intra_sss = {k: v for k, v in sss_by_key.items() if len(v) > 1}

lines = []
lines.append("key\tsch_dirs\tsss_dirs\tsch_neu_pdf\tsss_neu_pdf\tsch_orig\tsss_orig")
for k in both:
    sch_names = "|".join(p.name for p in sch_by_key[k])
    sss_names = "|".join(p.name for p in sss_by_key[k])
    sch_neu = any(has_neu_pdf(p) for p in sch_by_key[k])
    sss_neu = any(has_neu_pdf(p) for p in sss_by_key[k])
    sch_o = any(has_orig_pdf(p) for p in sch_by_key[k])
    sss_o = any(has_orig_pdf(p) for p in sss_by_key[k])
    lines.append(
        f"{k}\t{sch_names}\t{sss_names}\t{int(sch_neu)}\t{int(sss_neu)}\t{int(sch_o)}\t{int(sss_o)}"
    )

dup_tsv = out / "sch_sss_exact_dupes.tsv"
dup_tsv.write_text("\n".join(lines) + "\n", encoding="utf-8")

# both with neu on both sides = echte Doppel-Publish
both_neu = []
sch_only_neu = []
sss_only_neu = []
neither_neu = []
for k in both:
    sch_neu = any(has_neu_pdf(p) for p in sch_by_key[k])
    sss_neu = any(has_neu_pdf(p) for p in sss_by_key[k])
    row = {
        "key": k,
        "sch": [p.name for p in sch_by_key[k]],
        "sss": [p.name for p in sss_by_key[k]],
        "sch_neu": sch_neu,
        "sss_neu": sss_neu,
    }
    if sch_neu and sss_neu:
        both_neu.append(row)
    elif sss_neu and not sch_neu:
        sss_only_neu.append(row)
    elif sch_neu and not sss_neu:
        sch_only_neu.append(row)
    else:
        neither_neu.append(row)

summary = {
    "sch_dirs": len(sch_dirs),
    "sss_dirs": len(sss_dirs),
    "sch_unique_keys": len(sch_keys),
    "sss_unique_keys": len(sss_keys),
    "exact_key_overlap": len(both),
    "only_in_sch": len(only_sch),
    "only_in_sss": len(only_sss),
    "intra_dupes_sch": len(intra_sch),
    "intra_dupes_sss": len(intra_sss),
    "overlap_both_have_neu_pdf": len(both_neu),
    "overlap_neu_only_sss": len(sss_only_neu),
    "overlap_neu_only_sch": len(sch_only_neu),
    "overlap_neither_neu": len(neither_neu),
}

(out / "summary.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
(out / "overlap_both_neu.json").write_text(
    json.dumps(both_neu, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
(out / "overlap_neu_only_sss.json").write_text(
    json.dumps(sss_only_neu[:200], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
(out / "only_sch_keys.txt").write_text("\n".join(only_sch) + ("\n" if only_sch else ""), encoding="utf-8")
(out / "only_sss_keys.txt").write_text("\n".join(only_sss) + ("\n" if only_sss else ""), encoding="utf-8")

intra_lines = ["side\tkey\tdirs"]
for k, ps in sorted(intra_sch.items()):
    intra_lines.append(f"sch\t{k}\t{'|'.join(p.name for p in ps)}")
for k, ps in sorted(intra_sss.items()):
    intra_lines.append(f"sss\t{k}\t{'|'.join(p.name for p in ps)}")
(out / "intra_bucket_dupes.tsv").write_text("\n".join(intra_lines) + "\n", encoding="utf-8")

print("=== Counts ===")
for k, v in summary.items():
    print(f"  {k}: {v}")
print()
print("=== Exact overlap (gleiche Norm-Key) — Stichprobe ===")
for row in (both_neu + sss_only_neu + sch_only_neu)[:15]:
    print(
        f"  {row['key']}: sch={row['sch']} sss={row['sss']} "
        f"neu(sch/sss)={int(row['sch_neu'])}/{int(row['sss_neu'])}"
    )
if intra_sch or intra_sss:
    print()
    print("=== Intra-Duplikate (gleicher Key, mehrere Ordner) ===")
    for k, ps in list(intra_sch.items())[:8]:
        print(f"  sch/{k}: {[p.name for p in ps]}")
    for k, ps in list(intra_sss.items())[:8]:
        print(f"  sss/{k}: {[p.name for p in ps]}")
print()
print(f"TSV Duplikate:     {dup_tsv}")
print(f"Summary JSON:      {out / 'summary.json'}")
print(f"both neu:          {out / 'overlap_both_neu.json'}")
print(f"neu nur sss:       {out / 'overlap_neu_only_sss.json'}")
print(f"intra dupes:       {out / 'intra_bucket_dupes.tsv'}")
PY

echo
echo "Fertig: $OUT"
ls -la "$OUT"
