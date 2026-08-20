#!/usr/bin/env bash
# Inventur: CRM gulp_profil_c vs AID_profile/{letter}/{nachname_vorname}/neu/cv
#
# Frage: Wie viele Kontakte haben Gulp-Text, aber noch kein neu/cv auf dem Share?
# → entscheidet, ob Gulp→Pipeline sich lohnt.
#
# Auf ucs5:
#   cd /opt/abpe/backend && source /opt/abpe/venv311/bin/activate
#   OUT=/tmp/gulp-vs-neu-$(date +%Y%m%d-%H%M%S) \
#     bash /mnt/public/udoo-reprap/scripts/INVENTORY-gulp-vs-neu-cv.sh
#   # oder ohne Checkout:
#   bash <(git -C /mnt/public/udoo-reprap show origin/cursor/aid-sch-sss-dupes-1532:scripts/INVENTORY-gulp-vs-neu-cv.sh)
#
set -euo pipefail

ROOT="${AID_PROFILE_ROOT:-/mnt/public/Berater/AID_profile}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
OUT="${OUT:-/tmp/gulp-vs-neu-$(date +%Y%m%d-%H%M%S)}"
MIN_PROFIL_LEN="${MIN_PROFIL_LEN:-200}"   # zu kurze Snippets ignorieren

mkdir -p "$OUT"
cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate

export AID_PROFILE_ROOT="$ROOT"
export INVENTORY_OUT="$OUT"
export MIN_PROFIL_LEN
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"

python3 manage.py shell <<'PY'
import os, re, json, sys
from pathlib import Path
from collections import defaultdict

from django.apps import apps

ROOT = Path(os.environ.get("AID_PROFILE_ROOT", "/mnt/public/Berater/AID_profile"))
OUT = Path(os.environ["INVENTORY_OUT"])
MIN_LEN = int(os.environ.get("MIN_PROFIL_LEN", "200"))

CrmContactCstm = apps.get_model("abpe_crm", "CrmContactCstm")
CrmContact = apps.get_model("abpe_crm", "CrmContact")


def norm_name(s: str) -> str:
    s = (s or "").strip().lower()
    s = s.replace("ß", "ss")
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue")):
        s = s.replace(a, b)
    s = re.sub(r"[\s,]+", "_", s)
    s = re.sub(r"[^\w\-]+", "_", s, flags=re.UNICODE)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def letter_bucket(last: str) -> str:
    """wie Publish: erster a-z Buchstabe ×3; Sch… oft unter sch/."""
    src = (last or "").strip().lower()
    # umlaut
    for a, b in (("ä", "a"), ("ö", "o"), ("ü", "u"), ("ß", "s")):
        src = src.replace(a, b)
    ch = ""
    for c in src:
        if "a" <= c <= "z":
            ch = c
            break
    if not ch:
        return "zzzSONSTIGES"
    # Speziell: Nachnamen mit sch → auch sch-Bucket prüfen
    return ch * 3


def candidate_dirs(first: str, last: str) -> list[str]:
    """mögliche nachname_vorname Varianten."""
    f, l = norm_name(first), norm_name(last)
    if not l:
        return []
    out = []
    if f:
        out.append(f"{l}_{f}")
        # Vorname nur erstes Token
        f0 = f.split("_")[0]
        if f0 != f:
            out.append(f"{l}_{f0}")
    else:
        out.append(l)
    # dedupe preserve order
    seen = set()
    uniq = []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


def letter_dirs_for(last: str) -> list[str]:
    b = letter_bucket(last)
    letters = [b]
    ln = norm_name(last)
    if ln.startswith("sch") and "sch" not in letters:
        letters.insert(0, "sch")
    if b == "sss" and "sch" not in letters:
        letters.append("sch")
    return letters


def find_person(first: str, last: str):
    """(letter, dir_name, path) oder (None,None,None). Prefer dir mit neu/cv."""
    names = candidate_dirs(first, last)
    if not names:
        return None, None, None
    hits = []
    for letter in letter_dirs_for(last):
        base = ROOT / letter
        if not base.is_dir():
            continue
        for name in names:
            p = base / name
            if p.is_dir():
                hits.append((letter, name, p))
    if not hits:
        # Fallback: irgendwo unter ROOT nach exaktem dir-Namen suchen (teurer, nur names)
        for name in names:
            for letter_dir in ROOT.iterdir() if ROOT.is_dir() else []:
                if not letter_dir.is_dir():
                    continue
                if len(letter_dir.name) != 3 and letter_dir.name not in ("sch", "zzzSONSTIGES"):
                    continue
                p = letter_dir / name
                if p.is_dir():
                    hits.append((letter_dir.name, name, p))
    if not hits:
        return None, None, None
    # Prefer one with neu/cv pdf
    def score(h):
        _, _, p = h
        neu = p / "neu" / "cv"
        if neu.is_dir() and any(neu.glob("AID-*.pdf")):
            return 2
        if neu.is_dir():
            return 1
        return 0

    hits.sort(key=score, reverse=True)
    return hits[0]


def has_neu_pdf(person: Path) -> bool:
    neu = person / "neu" / "cv"
    if not neu.is_dir():
        return False
    try:
        return any(neu.glob("AID-*.pdf"))
    except OSError:
        return False


# --- scan CRM ---
rows_all = []
rows_need = []  # gulp ja, neu/cv nein (oder kein Ordner)
summary = defaultdict(int)

qs = (
    CrmContactCstm.objects.exclude(gulp_profil_c__isnull=True)
    .exclude(gulp_profil_c="")
    .only("id_c", "gulp_id_c", "gulp_profil_c")
)

# Contact map
contact_ids = list(qs.values_list("id_c", flat=True))
contacts = {
    c.id: c
    for c in CrmContact.objects.filter(id__in=contact_ids).only(
        "id", "first_name", "last_name", "deleted"
    )
}

for st in qs.iterator(chunk_size=500):
    profil = st.gulp_profil_c or ""
    plen = len(profil.strip())
    if plen < MIN_LEN:
        summary["gulp_too_short"] += 1
        continue
    summary["gulp_ok_len"] += 1

    c = contacts.get(st.id_c)
    if c is None:
        summary["no_contact"] += 1
        continue
    if getattr(c, "deleted", 0) in (1, True, "1"):
        summary["contact_deleted"] += 1
        continue

    first = (c.first_name or "").strip()
    last = (c.last_name or "").strip()
    if not last:
        summary["no_lastname"] += 1
        continue

    letter, dname, path = find_person(first, last)
    if path is None:
        cat = "no_fs_dir"
        summary[cat] += 1
        row = {
            "contact_id": c.id,
            "gulp_id": st.gulp_id_c or "",
            "first": first,
            "last": last,
            "profil_len": plen,
            "fs_letter": "",
            "fs_dir": "",
            "has_neu_pdf": 0,
            "cat": cat,
        }
        rows_all.append(row)
        rows_need.append(row)
        continue

    neu = has_neu_pdf(path)
    if neu:
        cat = "has_neu_cv"
        summary[cat] += 1
    else:
        cat = "fs_dir_no_neu"
        summary[cat] += 1
    row = {
        "contact_id": c.id,
        "gulp_id": st.gulp_id_c or "",
        "first": first,
        "last": last,
        "profil_len": plen,
        "fs_letter": letter,
        "fs_dir": dname,
        "has_neu_pdf": int(neu),
        "cat": cat,
    }
    rows_all.append(row)
    if not neu:
        rows_need.append(row)

# write outputs
def write_tsv(path: Path, rows: list):
    cols = [
        "cat",
        "contact_id",
        "gulp_id",
        "last",
        "first",
        "fs_letter",
        "fs_dir",
        "has_neu_pdf",
        "profil_len",
    ]
    lines = ["\t".join(cols)]
    for r in rows:
        lines.append("\t".join(str(r.get(c, "")) for c in cols))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


write_tsv(OUT / "all.tsv", rows_all)
write_tsv(OUT / "need_neu_cv.tsv", rows_need)  # Generier-Kandidaten
write_tsv(
    OUT / "need_neu_cv_with_fs_dir.tsv",
    [r for r in rows_need if r["cat"] == "fs_dir_no_neu"],
)
write_tsv(
    OUT / "need_neu_cv_no_fs_dir.tsv",
    [r for r in rows_need if r["cat"] == "no_fs_dir"],
)

# candidates for generation: has gulp, no neu (both with and without fs dir)
cand_with_dir = sum(1 for r in rows_need if r["cat"] == "fs_dir_no_neu")
cand_no_dir = sum(1 for r in rows_need if r["cat"] == "no_fs_dir")

report = {
    "root": str(ROOT),
    "min_profil_len": MIN_LEN,
    "summary": dict(summary),
    "gulp_contacts_scanned_ok_len": summary["gulp_ok_len"],
    "already_has_neu_cv": summary.get("has_neu_cv", 0),
    "candidates_total_no_neu": len(rows_need),
    "candidates_fs_dir_no_neu": cand_with_dir,
    "candidates_no_fs_dir": cand_no_dir,
    "worth_it_hint": (
        "high"
        if cand_with_dir >= 100
        else ("medium" if cand_with_dir >= 30 else "low")
    ),
}
(OUT / "summary.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)

print("======== Gulp vs neu/cv Inventur ========")
print(f"OUT={OUT}")
print(f"gulp_profil ok (len>={MIN_LEN}): {summary['gulp_ok_len']}")
print(f"  bereits neu/cv:              {summary.get('has_neu_cv', 0)}")
print(f"  FS-Ordner, aber KEIN neu/cv: {cand_with_dir}  ← Haupt-Kandidaten")
print(f"  kein FS-Ordner:              {cand_no_dir}  ← Ordner anlegen nötig")
print(f"  Kandidaten gesamt:           {len(rows_need)}")
print(f"  worth_it_hint:               {report['worth_it_hint']}")
print()
print(f"need_neu_cv.tsv:              {OUT / 'need_neu_cv.tsv'}")
print(f"need_neu_cv_with_fs_dir.tsv:  {OUT / 'need_neu_cv_with_fs_dir.tsv'}")
print(f"summary.json:                 {OUT / 'summary.json'}")
print()
print("=== Stichprobe fs_dir_no_neu ===")
for r in [x for x in rows_need if x["cat"] == "fs_dir_no_neu"][:15]:
    print(
        f"  {r['fs_letter']}/{r['fs_dir']}  gulp_id={r['gulp_id']}  "
        f"profil_len={r['profil_len']}  {r['last']}, {r['first']}"
    )
PY
