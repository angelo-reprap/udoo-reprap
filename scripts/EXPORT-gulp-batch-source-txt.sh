#!/usr/bin/env bash
# Exportiert gulp_profil_c (CRM/DB) → eine TXT-Datei pro Berater aus dem Batch.
#
# Nach / vor Batch (ucs5):
#   RESULT_TSV=/tmp/gulp-batch-*/result.tsv \
#     bash /mnt/public/udoo-reprap/scripts/EXPORT-gulp-batch-source-txt.sh
#
# Oder aus NEED (gleiche 10 wie Batch):
#   NEED=/tmp/gulp-vs-neu-*/need_neu_cv_with_fs_dir.tsv LIMIT=10 \
#     bash /mnt/public/udoo-reprap/scripts/EXPORT-gulp-batch-source-txt.sh
#
# Output: $OUT/txt/{letter}__{dir}.txt  + by-person/.../gulp_profil_c.txt + index.tsv
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
REPO="${REPO:-/mnt/public/udoo-reprap}"
RESULT_TSV="${RESULT_TSV:-}"
NEED="${NEED:-}"
LIMIT="${LIMIT:-0}"
OUT="${OUT:-}"
MIN_LEN="${MIN_LEN:-50}"

if [[ -z "$RESULT_TSV" ]]; then
  RESULT_TSV="$(ls -td /tmp/gulp-batch-*/result.tsv 2>/dev/null | head -1 || true)"
fi
if [[ -z "$OUT" ]]; then
  if [[ -n "$RESULT_TSV" && -f "$RESULT_TSV" ]]; then
    OUT="$(dirname "$RESULT_TSV")/source-txt"
  else
    OUT="/tmp/gulp-batch-source-txt-$(date +%Y%m%d-%H%M%S)"
  fi
fi

mkdir -p "$OUT/txt"
cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"
export RESULT_TSV NEED OUT LIMIT MIN_LEN REPO

python3 manage.py shell <<'PY'
import os, re, json
from pathlib import Path
from django.apps import apps

RESULT_TSV = (os.environ.get("RESULT_TSV") or "").strip()
NEED = (os.environ.get("NEED") or "").strip()
OUT = Path(os.environ["OUT"])
LIMIT = int(os.environ.get("LIMIT") or "0")
MIN_LEN = int(os.environ.get("MIN_LEN") or "50")
(OUT / "txt").mkdir(parents=True, exist_ok=True)

CrmContactCstm = apps.get_model("abpe_crm", "CrmContactCstm")
UMLAUT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue"})


def slug(last: str, first: str) -> str:
    raw = f"{last}_{first}".strip("_").lower().translate(UMLAUT)
    return re.sub(r"[^\w\-]+", "_", raw, flags=re.UNICODE).strip("_") or "unknown"


def fetch_text(contact_id: str, gulp_id: str) -> str:
    st = None
    gid = (gulp_id or "").strip()
    if gid and re.fullmatch(r"\d+", gid):
        st = CrmContactCstm.objects.filter(gulp_id_c=gid).first()
        if st is None:
            try:
                st = CrmContactCstm.objects.filter(gulp_id_c=int(gid)).first()
            except (ValueError, TypeError):
                st = None
    if st is None and contact_id:
        try:
            st = CrmContactCstm.objects.filter(contact_id=contact_id).first()
        except (ValueError, TypeError):
            st = None
    if st is None and str(contact_id).isdigit():
        cid = int(contact_id)
        st = (
            CrmContactCstm.objects.filter(contact__id=cid).first()
            or CrmContactCstm.objects.filter(contact_id=cid).first()
        )
    return (getattr(st, "gulp_profil_c", None) or "").strip() if st else ""


jobs = []
src = ""
if RESULT_TSV and Path(RESULT_TSV).is_file():
    src = RESULT_TSV
    # status contact_id gulp_id letter dir pdf note secs
    for i, line in enumerate(Path(RESULT_TSV).read_text(encoding="utf-8").splitlines()):
        if i == 0 or not line.strip():
            continue
        p = line.split("\t")
        if len(p) < 5:
            continue
        status, cid, gid, letter, dname = p[0], p[1], p[2], p[3], p[4]
        if status not in ("OK", "FAIL", "DRY", "SKIP"):
            continue
        if dname.isdigit():
            dname = ""
        if letter and "_" in letter and len(letter) > 3:
            # alter Bug: letter=person_dir
            if not dname:
                dname = letter
            letter = ""
        jobs.append(
            {
                "contact_id": cid,
                "gulp_id": gid if re.fullmatch(r"\d+", str(gid or "")) else "",
                "letter": letter if re.fullmatch(r"(?:sch|[a-z]{3})", letter or "") else "",
                "dir": dname,
                "status": status,
            }
        )
elif NEED and Path(NEED).is_file():
    src = NEED
    for i, line in enumerate(Path(NEED).read_text(encoding="utf-8").splitlines()):
        if i == 0 or not line.strip():
            continue
        p = [c.strip() for c in line.split("\t")]
        if len(p) < 7:
            continue
        if p[0] not in ("fs_dir_no_neu", "need"):
            continue
        jobs.append(
            {
                "contact_id": p[1],
                "gulp_id": p[2],
                "letter": p[5],
                "dir": p[6],
                "last": p[3],
                "first": p[4],
                "status": "need",
            }
        )
        if LIMIT > 0 and len(jobs) >= LIMIT:
            break
else:
    raise SystemExit("RESULT_TSV oder NEED setzen")

print(f"src={src} jobs={len(jobs)} OUT={OUT}")

rows = ["status\tcontact_id\tgulp_id\tletter\tdir\tfile\tchars\tnote"]
ok = fail = 0
for j in jobs:
    cid = j["contact_id"]
    gid = j.get("gulp_id") or ""
    letter = j.get("letter") or ""
    dname = j.get("dir") or ""
    text = fetch_text(cid, gid)
    if len(text) < MIN_LEN:
        fail += 1
        rows.append(f"FAIL\t{cid}\t{gid}\t{letter}\t{dname}\t\t{len(text)}\ttoo_short_or_missing")
        print(f"FAIL {letter}/{dname} cid={cid} len={len(text)}")
        continue
    if not dname:
        last = j.get("last") or ""
        first = j.get("first") or ""
        dname = slug(last, first) if (last or first) else f"cid_{cid}"
    if not letter:
        ch = ""
        for c in dname.lower():
            if "a" <= c <= "z":
                ch = c
                break
        letter = (ch * 3) if ch else "zzz"
    fname = f"{letter}__{dname}.txt"
    payload = text + ("\n" if not text.endswith("\n") else "")
    (OUT / "txt" / fname).write_text(payload, encoding="utf-8")
    person_dir = OUT / "by-person" / letter / dname
    person_dir.mkdir(parents=True, exist_ok=True)
    (person_dir / "gulp_profil_c.txt").write_text(payload, encoding="utf-8")
    ok += 1
    rows.append(f"OK\t{cid}\t{gid}\t{letter}\t{dname}\t{fname}\t{len(text)}\t")
    print(f"OK {letter}/{dname} → {fname} chars={len(text)}")

(OUT / "index.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
(OUT / "summary.json").write_text(
    json.dumps({"ok": ok, "fail": fail, "src": src, "out": str(OUT)}, indent=2, ensure_ascii=False)
    + "\n",
    encoding="utf-8",
)
print(f"Fertig: ok={ok} fail={fail} → {OUT}")
print(f"  flat:      {OUT}/txt/")
print(f"  by-person: {OUT}/by-person/{{letter}}/{{dir}}/gulp_profil_c.txt")
PY

echo
echo "EXPORT fertig: $OUT"
ls -la "$OUT/txt" | head -20
