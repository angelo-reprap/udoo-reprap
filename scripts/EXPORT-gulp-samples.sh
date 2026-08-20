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
# Expect: files≈1000, Index-Header beginnt mit "tier"
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
from django.db.models.functions import Length

NEED = (os.environ.get("NEED") or "").strip()
OUT = Path(os.environ["OUT"])
LIMIT = int(os.environ.get("LIMIT", "1000"))
MIN_LEN = int(os.environ.get("MIN_LEN", "200"))
SEED = int(os.environ.get("SEED", "42"))
(OUT / "txt").mkdir(parents=True, exist_ok=True)
rng = random.Random(SEED)

CrmContactCstm = apps.get_model("abpe_crm", "CrmContactCstm")
CrmContact = apps.get_model("abpe_crm", "CrmContact")

_DIGITS = re.compile(r"^\d+$")


def is_int_id(cid) -> bool:
    return bool(_DIGITS.fullmatch(str(cid).strip()))


def names_for_cid(cid):
    """Namen via Cstm.contact; nie UUID an integer CrmContact.id."""
    last, first = "", ""
    try:
        st = (
            CrmContactCstm.objects.filter(contact_id=cid)
            .select_related("contact")
            .first()
        )
    except (ValueError, TypeError):
        st = None
    if st is not None:
        c = getattr(st, "contact", None)
        if c is not None:
            last = (getattr(c, "last_name", None) or "").strip()
            first = (getattr(c, "first_name", None) or "").strip()
            return last, first
    if is_int_id(cid):
        c = (
            CrmContact.objects.filter(pk=int(cid))
            .only("id", "first_name", "last_name")
            .first()
        )
        if c is not None:
            last = (getattr(c, "last_name", None) or "").strip()
            first = (getattr(c, "first_name", None) or "").strip()
    return last, first


def cstm_for_cid(cid):
    """Cstm-Zeile holen; UUID/Int tolerant, kein Crash auf int-FK."""
    try:
        st = CrmContactCstm.objects.filter(contact_id=cid).first()
        if st is not None:
            return st
    except (ValueError, TypeError):
        pass
    if is_int_id(cid):
        st = CrmContactCstm.objects.filter(contact_id=int(cid)).first()
        if st is not None:
            return st
        return CrmContactCstm.objects.filter(contact__id=int(cid)).first()
    return None


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
need_sorted = sorted(
    need_rows, key=lambda r: (0 if r.get("gulp_id") else 1, r.get("fs_dir") or "")
)
for r in need_sorted:
    if len(picked) >= LIMIT:
        break
    add_row(r)

# Tier 2: fill from CRM (nur IDs — Length(), kein Full-Text-Scan)
if len(picked) < LIMIT:
    need_more = LIMIT - len(picked)
    print(f"CRM fill need={need_more} (have={len(picked)})")

    qs = (
        CrmContactCstm.objects.exclude(gulp_profil_c__isnull=True)
        .exclude(gulp_profil_c="")
        .annotate(_plen=Length("gulp_profil_c"))
        .filter(_plen__gte=MIN_LEN)
        .values_list("contact_id", "gulp_id_c")
    )
    candidates = []
    for contact_id, gulp_id in qs.iterator(chunk_size=1000):
        if contact_id is None:
            continue
        cid = str(contact_id).strip()
        if not cid or cid in seen_cid:
            continue
        candidates.append((cid, str(gulp_id or "")))

    # Integer-FKs zuerst (CrmContact.id ist int); UUIDs/Sugar-Reste danach
    numeric = [x for x in candidates if is_int_id(x[0])]
    other = [x for x in candidates if not is_int_id(x[0])]
    rng.shuffle(numeric)
    rng.shuffle(other)
    ordered = numeric + other
    print(
        f"CRM candidates len>={MIN_LEN}: {len(candidates)} "
        f"(int_id={len(numeric)} other={len(other)})"
    )

    filled = 0
    skipped_bad = 0
    for cid, gid in ordered:
        if filled >= need_more:
            break
        # Smoke-check: Cstm muss lesbar sein (UUID auf int-FK → skip)
        st = cstm_for_cid(cid)
        if st is None:
            skipped_bad += 1
            continue
        last, first = names_for_cid(cid)
        if not last and not first:
            # Namen optional — Text trotzdem exportieren
            last, first = names_for_cid(cid)
        slug_base = f"{last}_{first}".strip("_").lower()
        if not slug_base:
            slug_base = f"contact_{cid[:12]}"
        slug = re.sub(r"[^\w\-]+", "_", slug_base, flags=re.UNICODE)
        if add_row(
            {
                "contact_id": cid,
                "gulp_id": gid,
                "last": last,
                "first": first,
                "fs_letter": "",
                "fs_dir": slug,
                "tier": "crm_random",
            }
        ):
            filled += 1
    print(f"CRM fill added={filled} skipped_bad={skipped_bad}")

meta = []
ok = 0
fail = 0
for r in picked:
    cid = r["contact_id"]
    st = cstm_for_cid(cid)
    text = (getattr(st, "gulp_profil_c", None) or "").strip() if st else ""
    if len(text) < MIN_LEN:
        fail += 1
        print(f"SKIP short/empty contact_id={cid} dir={r['fs_dir']}")
        continue
    safe = re.sub(r"[^\w\-]+", "_", r["fs_dir"] or f"c_{cid}", flags=re.UNICODE)
    fn = f"{safe}.txt"
    target = OUT / "txt" / fn
    n = 2
    while target.exists():
        fn = f"{safe}_{n}.txt"
        target = OUT / "txt" / fn
        n += 1
    target.write_text(text, encoding="utf-8")
    meta.append(
        f"{r.get('tier','')}\t{r.get('fs_letter','')}\t{r['fs_dir']}\t"
        f"{r.get('gulp_id','')}\t{cid}\t{fn}\t{len(text)}"
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
print(f"files={ok} fail={fail} limit={LIMIT} picked={len(picked)}")
if ok == 0:
    raise SystemExit(2)
if ok < min(LIMIT, 50):
    print(f"WARN: nur {ok} files (erwartet ~{LIMIT})")
PY

echo
echo "Check:"
echo "  ls \"$OUT/txt\" | wc -l"
echo "  head -1 \"$OUT/index.tsv\"   # muss mit tier beginnen"
echo
echo "Zum Cloud-Agent syncen (temporär, später wieder löschen):"
echo "  cd $REPO"
echo "  git fetch origin cursor/aid-sch-sss-dupes-1532 && git checkout cursor/aid-sch-sss-dupes-1532"
echo "  git pull origin cursor/aid-sch-sss-dupes-1532"
echo "  mkdir -p artifacts/gulp-samples-1000 && rm -rf artifacts/gulp-samples-1000/txt"
echo "  cp -a $OUT/txt $OUT/index.tsv artifacts/gulp-samples-1000/"
echo "  git add artifacts/gulp-samples-1000"
echo "  git commit -m 'chore: temp 1000 gulp txt for keyword harden'"
echo "  git push -u origin cursor/aid-sch-sss-dupes-1532"
