#!/usr/bin/env bash
# Exportiert ~30 gulp_profil_c Samples (fs_dir_no_neu) für txt→AID-gulp.pdf Entwicklung.
#
# Auf ucs5:
#   cd /opt/abpe/backend && source /opt/abpe/venv311/bin/activate
#   NEED=/tmp/gulp-vs-neu-20260820-143848/need_neu_cv_with_fs_dir.tsv \
#   OUT=/tmp/gulp-samples-$(date +%Y%m%d-%H%M%S) \
#     bash /mnt/public/udoo-reprap/scripts/EXPORT-gulp-samples.sh
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
NEED="${NEED:-/tmp/gulp-vs-neu-20260820-143848/need_neu_cv_with_fs_dir.tsv}"
OUT="${OUT:-/tmp/gulp-samples-$(date +%Y%m%d-%H%M%S)}"
LIMIT="${LIMIT:-30}"
REPO="${REPO:-/mnt/public/udoo-reprap}"

if [[ ! -f "$NEED" ]]; then
  echo "FAIL: NEED TSV fehlt: $NEED" >&2
  exit 1
fi

mkdir -p "$OUT/txt"
cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"
export NEED OUT LIMIT

python3 manage.py shell <<'PY'
import os, re
from pathlib import Path
from django.apps import apps

NEED = Path(os.environ["NEED"])
OUT = Path(os.environ["OUT"])
LIMIT = int(os.environ.get("LIMIT", "30"))
(OUT / "txt").mkdir(parents=True, exist_ok=True)

CrmContactCstm = apps.get_model("abpe_crm", "CrmContactCstm")

rows = []
for i, line in enumerate(NEED.read_text(encoding="utf-8").splitlines()):
    if i == 0 or not line.strip():
        continue
    p = [c.strip() for c in line.split("\t")]
    if len(p) < 7:
        continue
    rows.append({
        "contact_id": p[1],
        "gulp_id": p[2],
        "last": p[3],
        "first": p[4],
        "fs_letter": p[5],
        "fs_dir": p[6],
    })

# Prefer rows with gulp_id, then fill up
with_gid = [r for r in rows if r["gulp_id"]]
without = [r for r in rows if not r["gulp_id"]]
pick = (with_gid + without)[:LIMIT]

meta = []
ok = 0
fail = 0
for r in pick:
    cid = r["contact_id"]
    try:
        cid_int = int(cid)
    except ValueError:
        cid_int = cid

    st = (
        CrmContactCstm.objects.filter(contact_id=cid_int).first()
        or CrmContactCstm.objects.filter(contact__id=cid_int).first()
    )
    text = (getattr(st, "gulp_profil_c", None) or "").strip() if st else ""
    if not text:
        fail += 1
        print(f"SKIP empty contact_id={cid} dir={r['fs_dir']}")
        continue

    safe = re.sub(r"[^\w\-]+", "_", r["fs_dir"], flags=re.UNICODE)
    fn = f"{safe}.txt"
    (OUT / "txt" / fn).write_text(text, encoding="utf-8")
    meta.append(
        f"{r['fs_letter']}\t{r['fs_dir']}\t{r['gulp_id']}\t{cid}\t{fn}\t{len(text)}"
    )
    ok += 1
    print(f"OK {r['fs_letter']}/{r['fs_dir']} len={len(text)}")

(OUT / "index.tsv").write_text(
    "letter\tdir\tgulp_id\tcontact_id\tfile\tlen\n" + "\n".join(meta) + ("\n" if meta else ""),
    encoding="utf-8",
)
print(f"OUT={OUT}")
print(f"files={ok} fail={fail}")
if ok == 0:
    raise SystemExit(2)
PY

echo
echo "Sample-Köpfe:"
head -3 "$OUT"/txt/*.txt 2>/dev/null | head -40
echo
echo "Zum Cloud-Agent syncen (Branch aid-sch-sss-dupes, stash lokale Docs-Änderung):"
echo "  cd $REPO"
echo "  git stash push -m ucs5 -- docs/matching-outreach-wizard-api-inventory.md || true"
echo "  git fetch origin cursor/aid-sch-sss-dupes-1532 && git checkout cursor/aid-sch-sss-dupes-1532"
echo "  mkdir -p artifacts/gulp-samples && rm -rf artifacts/gulp-samples/txt"
echo "  cp -a $OUT/txt $OUT/index.tsv artifacts/gulp-samples/"
echo "  git add artifacts/gulp-samples"
echo "  git commit -m 'chore: gulp_profil_c samples for AID-gulp.pdf converter'"
echo "  git push -u origin cursor/aid-sch-sss-dupes-1532"
