#!/usr/bin/env bash
# Exportiert gulp_profil_c TXT-Samples für Keyword/Regex-Entwicklung.
#
# Default LIMIT=1000, stratifiziert:
#   1) alle aus NEED (fs_dir_no_neu), sofern vorhanden
#   2) Auffüllen aus CRM (gulp_profil_c len >= MIN_LEN), zufällig
#
# Auf ucs5:
#   cd /opt/abpe/backend && source /opt/abpe/venv311/bin/activate
#   NEED=/tmp/gulp-vs-neu-*/need_neu_cv_with_fs_dir.tsv \
#   LIMIT=1000 OUT=/tmp/gulp-samples-1000-$(date +%Y%m%d-%H%M%S) \
#     bash /mnt/public/udoo-reprap/scripts/EXPORT-gulp-samples.sh
#
# Danach temporär ins Repo (Branch aid-sch-sss-dupes):
#   mkdir -p artifacts/gulp-samples-1000
#   rm -rf artifacts/gulp-samples-1000/txt
#   cp -a "$OUT"/txt "$OUT"/index.tsv artifacts/gulp-samples-1000/
#   git add artifacts/gulp-samples-1000 && git commit -m 'chore: temp 1000 gulp txt for keyword harden' && git push
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
NEED="${NEED:-}"
OUT="${OUT:-/tmp/gulp-samples-$(date +%Y%m%d-%H%M%S)}"
LIMIT="${LIMIT:-1000}"
MIN_LEN="${MIN_LEN:-200}"
REPO="${REPO:-/mnt/public/udoo-reprap}"
SEED="${SEED:-42}"

mkdir -p "$OUT/txt"
cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"
export NEED OUT LIMIT MIN_LEN SEED

python3 manage.py shell <<'PY'
import os, re, random
from pathlib import Path
from django.apps import apps
from django.db.models import Q

NEED = (os.environ.get("NEED") or "").strip()
OUT = Path(os.environ["OUT"])
LIMIT = int(os.environ.get("LIMIT", "1000"))
MIN_LEN = int(os.environ.get("MIN_LEN", "200"))
SEED = int(os.environ.get("SEED", "42"))
(OUT / "txt").mkdir(parents=True, exist_ok=True)
rng = random.Random(SEED)

CrmContactCstm = apps.get_model("abpe_crm", "CrmContactCstm")
CrmContact = apps.get_model("abpe_crm", "CrmContact")

need_rows = []
if NEED and Path(NEED).is_file():
    for i, line in enumerate(Path(NEED).read_text(encoding="utf-8").splitlines()):
        if i == 0 or not line.strip():
            continue
        p = [c.strip() for c in line.split("\t")]
        if len(p) < 7:
            continue
        need_rows.append(
            {
                "contact_id": p[1],
                "gulp_id": p[2],
                "last": p[3],
                "first": p[4],
                "fs_letter": p[5],
                "fs_dir": p[6],
                "tier": "need_fs_no_neu",
            }
        )
    print(f"NEED rows={len(need_rows)} from {NEED}")
else:
    print("NEED fehlt/leer — nur CRM-Zufallsstichprobe")

picked = []
seen_cid = set()

def add_row(r):
    cid = str(r["contact_id"])
    if cid in seen_cid:
        return False
    seen_cid.add(cid)
    picked.append(r)
    return True

# Tier 1: NEED (prefer with gulp_id)
need_sorted = sorted(need_rows, key=lambda r: (0 if r.get("gulp_id") else 1, r.get("fs_dir") or ""))
for r in need_sorted:
    if len(picked) >= LIMIT:
        break
    add_row(r)

# Tier 2: fill from CRM
if len(picked) < LIMIT:
    need_more = LIMIT - len(picked)
    print(f"CRM fill need={need_more} (have={len(picked)})")
    qs = (
        CrmContactCstm.objects.exclude(gulp_profil_c__isnull=True)
        .exclude(gulp_profil_c="")
        .values_list("contact_id", "gulp_id_c", "gulp_profil_c")
    )
    candidates = []
    for contact_id, gulp_id, profil in qs.iterator(chunk_size=500):
        text = (profil or "").strip()
        if len(text) < MIN_LEN:
            continue
        cid = str(contact_id)
        if cid in seen_cid:
            continue
        candidates.append((cid, str(gulp_id or ""), len(text)))
    rng.shuffle(candidates)
    print(f"CRM candidates len>={MIN_LEN}: {len(candidates)}")
    for cid, gid, _ln in candidates[:need_more]:
        # resolve name for filename
        try:
            cid_int = int(cid)
        except ValueError:
            cid_int = cid
        c = CrmContact.objects.filter(id=cid_int).first()
        last = (getattr(c, "last_name", None) or "").strip() if c else ""
        first = (getattr(c, "first_name", None) or "").strip() if c else ""
        slug = re.sub(
            r"[^\w\-]+",
            "_",
            f"{last}_{first}".strip("_").lower() or f"contact_{cid}",
            flags=re.UNICODE,
        )
        add_row(
            {
                "contact_id": cid,
                "gulp_id": gid,
                "last": last,
                "first": first,
                "fs_letter": "",
                "fs_dir": slug,
                "tier": "crm_random",
            }
        )

meta = []
ok = 0
fail = 0
for r in picked:
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
    if len(text) < MIN_LEN:
        fail += 1
        print(f"SKIP short/empty contact_id={cid} dir={r['fs_dir']}")
        continue
    safe = re.sub(r"[^\w\-]+", "_", r["fs_dir"] or f"c_{cid}", flags=re.UNICODE)
    # avoid collisions
    fn = f"{safe}.txt"
    target = OUT / "txt" / fn
    n = 2
    while target.exists():
        fn = f"{safe}_{n}.txt"
        target = OUT / "txt" / fn
        n += 1
    target.write_text(text, encoding="utf-8")
    meta.append(
        f"{r.get('tier','')}\t{r.get('fs_letter','')}\t{r['fs_dir']}\t{r.get('gulp_id','')}\t{cid}\t{fn}\t{len(text)}"
    )
    ok += 1
    if ok <= 5 or ok % 100 == 0:
        print(f"OK #{ok} {r.get('tier')} {r['fs_dir']} len={len(text)}")

(OUT / "index.tsv").write_text(
    "tier\tletter\tdir\tgulp_id\tcontact_id\tfile\tlen\n"
    + "\n".join(meta)
    + ("\n" if meta else ""),
    encoding="utf-8",
)
print(f"OUT={OUT}")
print(f"files={ok} fail={fail} limit={LIMIT}")
if ok == 0:
    raise SystemExit(2)
PY

echo
echo "Zum Cloud-Agent syncen (temporär, später wieder löschen):"
echo "  cd $REPO"
echo "  git fetch origin cursor/aid-sch-sss-dupes-1532 && git checkout cursor/aid-sch-sss-dupes-1532"
echo "  mkdir -p artifacts/gulp-samples-1000 && rm -rf artifacts/gulp-samples-1000/txt"
echo "  cp -a $OUT/txt $OUT/index.tsv artifacts/gulp-samples-1000/"
echo "  git add artifacts/gulp-samples-1000"
echo "  git commit -m 'chore: temp 1000 gulp txt for keyword harden'"
echo "  git push -u origin cursor/aid-sch-sss-dupes-1532"
