#!/usr/bin/env bash
# Exportiert die Dry-Run-Fail gulp_profil_c als TXT (Sonderbehandlung).
#
# Auf ucs5:
#   FAILS=/mnt/public/udoo-reprap/artifacts/gulp-keyword/dryrun-fails/fails.tsv \
#   OUT=/tmp/gulp-dryrun-fails-$(date +%Y%m%d-%H%M%S) \
#     bash /mnt/public/udoo-reprap/scripts/EXPORT-gulp-dryrun-fails.sh
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
FAILS="${FAILS:-/mnt/public/udoo-reprap/artifacts/gulp-keyword/dryrun-fails/fails.tsv}"
OUT="${OUT:-/tmp/gulp-dryrun-fails-$(date +%Y%m%d-%H%M%S)}"
REPO="${REPO:-/mnt/public/udoo-reprap}"

mkdir -p "$OUT/txt"
cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"
export FAILS OUT

python3 manage.py shell <<'PY'
import os, re
from pathlib import Path
from django.apps import apps

FAILS = Path(os.environ["FAILS"])
OUT = Path(os.environ["OUT"])
(OUT / "txt").mkdir(parents=True, exist_ok=True)

CrmContactCstm = apps.get_model("abpe_crm", "CrmContactCstm")

rows = []
for i, line in enumerate(FAILS.read_text(encoding="utf-8").splitlines()):
    if i == 0 or not line.strip():
        continue
    p = line.split("\t")
    if len(p) < 6:
        continue
    rows.append(
        {
            "contact_id": p[0].strip(),
            "gulp_id": p[1].strip(),
            "last": p[2].strip(),
            "first": p[3].strip(),
            "len": p[4].strip(),
            "reason": p[5].strip(),
        }
    )

meta = []
ok = 0
for r in rows:
    cid = r["contact_id"]
    st = None
    try:
        st = CrmContactCstm.objects.filter(contact_id=cid).first()
    except (ValueError, TypeError):
        st = None
    if st is None and str(cid).isdigit():
        st = CrmContactCstm.objects.filter(contact_id=int(cid)).first()
    text = (getattr(st, "gulp_profil_c", None) or "").strip() if st else ""
    slug = re.sub(
        r"[^\w\-]+",
        "_",
        f"{r['last']}_{r['first']}".strip("_").lower() or f"c_{cid[:12]}",
        flags=re.UNICODE,
    )
    fn = f"{slug}.txt"
    (OUT / "txt" / fn).write_text(text or "(EMPTY)\n", encoding="utf-8")
    reason_fn = f"{slug}.reason.txt"
    (OUT / "txt" / reason_fn).write_text(
        f"contact_id={cid}\ngulp_id={r['gulp_id']}\nreason={r['reason']}\nlen={r['len']}\n",
        encoding="utf-8",
    )
    meta.append(f"{cid}\t{r['gulp_id']}\t{r['last']}\t{r['first']}\t{fn}\t{len(text)}\t{r['reason']}")
    ok += 1
    print(f"OK {fn} chars={len(text)} reason={r['reason']}")

(OUT / "index.tsv").write_text(
    "contact_id\tgulp_id\tlast\tfirst\tfile\tlen\treason\n"
    + "\n".join(meta)
    + ("\n" if meta else ""),
    encoding="utf-8",
)
print(f"OUT={OUT} files={ok}")
PY

echo
echo "Ins Repo:"
echo "  mkdir -p $REPO/artifacts/gulp-keyword/dryrun-fails/txt"
echo "  cp -a $OUT/txt $OUT/index.tsv $REPO/artifacts/gulp-keyword/dryrun-fails/"
echo "  cd $REPO && git add artifacts/gulp-keyword/dryrun-fails && git commit -m 'chore: gulp dryrun fail texts for special-case' && git push"
