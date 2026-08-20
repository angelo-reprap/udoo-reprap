#!/usr/bin/env bash
# CONVERT: gulp_profil_c (TXT/CRM) → strukturiertes AID-*-gulp.pdf
# Ablage: {AID_ROOT}/{letter}/{nachname_vorname}/AID-{initials}_1.0.0.0-gulp.pdf
#
# Standard: DRY_RUN=1 (nur planen). Schreiben: EXECUTE=1
#
# Auf ucs5 — Quick-Win NEED (fs_dir_no_neu):
#   cd /opt/abpe/backend && source /opt/abpe/venv311/bin/activate
#   NEED=/tmp/gulp-vs-neu-*/need_neu_cv_with_fs_dir.tsv \
#   EXECUTE=0 LIMIT=5 \
#     bash /mnt/public/udoo-reprap/scripts/CONVERT-gulp-txt-to-aid-pdf.sh
#   EXECUTE=1 LIMIT=0   # alle NEED-Zeilen
#
# Preview nach X:\Berater\AID_profile\aaaMuster (= /mnt/public/.../aaaMuster):
#   TXT_DIR=$REPO/artifacts/gulp-keyword/dryrun-fails/txt \
#   OUT_DIR=/mnt/public/Berater/AID_profile/aaaMuster \
#   SKIP_PERSON_DIR=1 LIMIT=1 EXECUTE=1 \
#     bash /mnt/public/udoo-reprap/scripts/CONVERT-gulp-txt-to-aid-pdf.sh
#
# Fertige Cloud-Preview (ohne LibreOffice auf ucs5):
#   cp -v $REPO/artifacts/gulp-keyword/preview-aaaMuster/AID-*-gulp-*.pdf \
#        /mnt/public/Berater/AID_profile/aaaMuster/
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
REPO="${REPO:-/mnt/public/udoo-reprap}"
AID_ROOT="${AID_ROOT:-/mnt/public/Berater/AID_profile}"
NEED="${NEED:-}"
FAILS="${FAILS:-}"
TXT_DIR="${TXT_DIR:-}"
WEB_COPY="${WEB_COPY:-}"
OUT_DIR="${OUT_DIR:-}"   # z.B. aaaMuster — PDF nur/zusätzlich hierhin
OUT_LOG="${OUT_LOG:-/tmp/gulp-to-aid-pdf-$(date +%Y%m%d-%H%M%S)}"
LIMIT="${LIMIT:-0}"
EXECUTE="${EXECUTE:-0}"
MIN_LEN="${MIN_LEN:-200}"
VERSION_TAG="${VERSION_TAG:-1.0.0.0}"
SKIP_PERSON_DIR="${SKIP_PERSON_DIR:-0}"  # 1 = nur OUT_DIR, kein Person-Ordner

# Auto-Find NEED TSV wenn nicht gesetzt
if [[ -z "$NEED" && -z "$FAILS" && -z "$TXT_DIR" ]]; then
  NEED="$(ls -td /tmp/gulp-vs-neu-*/need_neu_cv_with_fs_dir.tsv 2>/dev/null | head -1 || true)"
fi
if [[ -z "$NEED" && -z "$FAILS" && -z "$TXT_DIR" ]]; then
  echo "FAIL: weder NEED noch FAILS noch TXT_DIR gesetzt, und kein NEED-TSV unter /tmp/gulp-vs-neu-*." >&2
  echo "  Preview: TXT_DIR=$REPO/artifacts/gulp-keyword/dryrun-fails/txt OUT_DIR=$AID_ROOT/aaaMuster LIMIT=1 EXECUTE=1 bash $0" >&2
  exit 1
fi
if [[ -n "$NEED" && ! -f "$NEED" ]]; then
  echo "FAIL: NEED Datei fehlt: $NEED" >&2
  exit 1
fi
echo "NEED=${NEED:-} FAILS=${FAILS:-} TXT_DIR=${TXT_DIR:-} OUT_DIR=${OUT_DIR:-} LIMIT=$LIMIT EXECUTE=$EXECUTE"

mkdir -p "$OUT_LOG"
cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"
export REPO AID_ROOT NEED FAILS TXT_DIR WEB_COPY OUT_DIR SKIP_PERSON_DIR OUT_LOG LIMIT EXECUTE MIN_LEN VERSION_TAG

python3 manage.py shell <<'PY'
import os, re, html, subprocess, tempfile, shutil, json
from pathlib import Path
from django.apps import apps

REPO = Path(os.environ["REPO"])
AID_ROOT = Path(os.environ["AID_ROOT"])
NEED = (os.environ.get("NEED") or "").strip()
FAILS = (os.environ.get("FAILS") or "").strip()
TXT_DIR = (os.environ.get("TXT_DIR") or "").strip()
WEB_COPY = (os.environ.get("WEB_COPY") or "").strip()
OUT_DIR = (os.environ.get("OUT_DIR") or "").strip()
SKIP_PERSON_DIR = os.environ.get("SKIP_PERSON_DIR", "0") in ("1", "true", "TRUE", "yes")
OUT_LOG = Path(os.environ["OUT_LOG"])
LIMIT = int(os.environ.get("LIMIT") or "0")
EXECUTE = os.environ.get("EXECUTE", "0") in ("1", "true", "TRUE", "yes")
MIN_LEN = int(os.environ.get("MIN_LEN") or "200")
VERSION_TAG = os.environ.get("VERSION_TAG") or "1.0.0.0"

# Keywords + Cleaner aus Repo laden (ohne Django-App-Import-Kette)
import importlib.util
kw_path = REPO / "Repo_abpe/cv_extractor/incoming/services/section_label_keywords.py"
spec = importlib.util.spec_from_file_location("section_label_keywords", kw_path)
kw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kw)
clean_path = REPO / "Repo_abpe/cv_extractor/incoming/services/gulp_profile_clean.py"
cspec = importlib.util.spec_from_file_location("gulp_profile_clean", clean_path)
gclean = importlib.util.module_from_spec(cspec)
cspec.loader.exec_module(gclean)

CrmContactCstm = apps.get_model("abpe_crm", "CrmContactCstm")

UMLAUT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue"})


def slug_name(last: str, first: str) -> str:
    raw = f"{last}_{first}".strip("_").lower().translate(UMLAUT)
    return re.sub(r"[^\w\-]+", "_", raw, flags=re.UNICODE).strip("_") or "unknown"


def initials(first: str, last: str) -> str:
    a = (first[:1] if first else "").lower()
    b = (last[:1] if last else "").lower()
    for ch in (a, b):
        if ch in "äöü":
            pass
    a = {"ä": "a", "ö": "o", "ü": "u"}.get(a, a)
    b = {"ä": "a", "ö": "o", "ü": "u"}.get(b, b)
    return (a + b) if (a or b) else "xx"


def letter_bucket(dir_name: str, last_name: str = "") -> str:
    cdir = (dir_name or "").strip()
    if "_" in cdir:
        src = cdir.split("_", 1)[0]
    else:
        src = (last_name or "").strip() or cdir
    ch = ""
    for c in src.lower():
        if "a" <= c <= "z":
            ch = c
            break
        if c in "äöüß":
            ch = {"ä": "a", "ö": "o", "ü": "u", "ß": "s"}[c]
            break
    return (ch * 3) if ch else "zzzSONSTIGES"


def find_existing_person_dir(root: Path, dir_name: str):
    name = (dir_name or "").strip().strip("/")
    if not name or not root.is_dir():
        return None
    # Refuse bogus dirs from shifted TSV (e.g. "0")
    if name.isdigit():
        return None
    hits = []
    try:
        for letter_dir in root.iterdir():
            if not letter_dir.is_dir() or letter_dir.name.startswith((".", "__")):
                continue
            cand = letter_dir / name
            if cand.is_dir():
                hits.append(cand)
    except OSError:
        return None
    if not hits:
        return None
    # Prefer sch before sss
    def rank(p: Path):
        n = p.parent.name.lower()
        if n == "sch":
            return (0, n)
        if n == "sss":
            return (1, n)
        return (2, n)

    hits.sort(key=rank)
    return hits[0]


def norm_text(t: str) -> str:
    for ch in ("\u00a0", "\u2009", "\u202f"):
        t = t.replace(ch, " ")
    for ch in ("\u200b", "\u00ad"):
        t = t.replace(ch, "")
    return t.replace("&amp;", "&")


def split_sections(text: str):
    """Split gulp text into (heading, body) using keyword regex."""
    text = norm_text(text)
    rx = kw.section_splitter_regex()
    matches = list(rx.finditer(text))
    if not matches:
        return [("Profil", text.strip())]
    parts = []
    # preamble
    pre = text[: matches[0].start()].strip()
    if pre:
        parts.append(("Kopf / Schwerpunkt", pre))
    for i, m in enumerate(matches):
        heading = re.sub(r"\s+", " ", m.group(1)).strip().rstrip(":")
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        parts.append((heading, body))
    return parts


def to_html(first: str, last: str, gulp_id: str, sections) -> str:
    title = f"{last}, {first}".strip(", ")
    blocks = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        f"<title>AID Gulp Profile — {html.escape(title)}</title>",
        "<style>",
        "body{font-family:DejaVu Sans,Arial,sans-serif;font-size:10.5pt;line-height:1.35;margin:18mm;}",
        "h1{font-size:16pt;margin:0 0 8pt 0;}",
        "h2{font-size:12pt;margin:14pt 0 6pt 0;border-bottom:1px solid #333;padding-bottom:2pt;}",
        "p,li{margin:0 0 4pt 0;white-space:pre-wrap;}",
        ".meta{color:#444;font-size:9pt;margin-bottom:12pt;}",
        "</style></head><body>",
        f"<h1>{html.escape(title)}</h1>",
        f"<p class='meta'>Quelle: Gulp-Profil"
        + (f" ID {html.escape(str(gulp_id))}" if gulp_id else "")
        + " — strukturiert für AID-Pipeline (Keywords v1.3)</p>",
    ]
    for heading, body in sections:
        if not body and not heading:
            continue
        lab = kw.label_from_heading(heading) or ""
        h = html.escape(heading)
        blocks.append(f"<h2>{h}</h2>")
        # preserve lines as paragraphs
        for para in re.split(r"\n\s*\n", body):
            para = para.strip()
            if not para:
                continue
            blocks.append(f"<p>{html.escape(para)}</p>")
    blocks.append("</body></html>")
    return "\n".join(blocks)


def libreoffice_html_to_pdf(html_path: Path, out_dir: Path, timeout=90) -> Path | None:
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "libreoffice",
        "--headless",
        "--nofirststartwizard",
        "--convert-to",
        "pdf",
        "--outdir",
        str(out_dir),
        str(html_path),
    ]
    try:
        subprocess.run(cmd, check=True, timeout=timeout, capture_output=True)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"  FAIL libreoffice: {e}")
        return None
    pdf = out_dir / (html_path.stem + ".pdf")
    return pdf if pdf.is_file() else None


def cstm_text(cid: str, gulp_id: str = "") -> str:
    """Text holen: gulp_id_c zuerst, dann contact__id (int), dann contact_id (UUID)."""
    st = None
    if gulp_id:
        gid = str(gulp_id).strip()
        st = CrmContactCstm.objects.filter(gulp_id_c=gid).first()
        if st is None and gid.isdigit():
            try:
                st = CrmContactCstm.objects.filter(gulp_id_c=int(gid)).first()
            except (ValueError, TypeError):
                st = None
    if st is None and cid:
        try:
            st = CrmContactCstm.objects.filter(contact_id=cid).first()
        except (ValueError, TypeError):
            st = None
    if st is None and str(cid).isdigit():
        cid_int = int(cid)
        st = (
            CrmContactCstm.objects.filter(contact__id=cid_int).first()
            or CrmContactCstm.objects.filter(contact_id=cid_int).first()
        )
    return (getattr(st, "gulp_profil_c", None) or "").strip() if st else ""


# ── Jobs sammeln ────────────────────────────────────────────────────────────
jobs = []
if TXT_DIR and Path(TXT_DIR).is_dir():
    for fp in sorted(Path(TXT_DIR).glob("*.txt")):
        if fp.name.endswith(".reason.txt"):
            continue
        # name = nachname_vorname.txt
        stem = fp.stem
        parts = stem.rsplit("_", 1)
        if len(parts) == 2:
            last_raw, first_raw = parts[0], parts[1]
        else:
            last_raw, first_raw = stem, ""
        last = last_raw.replace("_", " ").title()
        first = first_raw.replace("_", " ").title()
        jobs.append(
            {
                "contact_id": "",
                "gulp_id": "",
                "last": last,
                "first": first,
                "fs_letter": "",
                "fs_dir": stem,
                "src": "txt",
                "txt_path": str(fp),
            }
        )
elif NEED and Path(NEED).is_file():
    for i, line in enumerate(Path(NEED).read_text(encoding="utf-8").splitlines()):
        if i == 0 or not line.strip():
            continue
        p = [c.strip() for c in line.split("\t")]
        if len(p) < 7:
            continue
        jobs.append(
            {
                "contact_id": p[1],
                "gulp_id": p[2],
                "last": p[3],
                "first": p[4],
                "fs_letter": p[5],
                "fs_dir": p[6],
                "src": "need",
                "txt_path": "",
            }
        )
        # Guard shifted TSV / digit-only dir
        if not p[6] or str(p[6]).isdigit() or (
            "_" not in str(p[6]) and p[3] and p[4]
        ):
            jobs[-1]["fs_dir"] = slug_name(p[3], p[4])
        if not re.fullmatch(r"(?:sch|[a-z]{3}|zzzSONSTIGES)", str(p[5] or "")):
            jobs[-1]["fs_letter"] = letter_bucket(jobs[-1]["fs_dir"], p[3])
elif FAILS and Path(FAILS).is_file():
    for i, line in enumerate(Path(FAILS).read_text(encoding="utf-8").splitlines()):
        if i == 0 or not line.strip():
            continue
        p = line.split("\t")
        if len(p) < 4:
            continue
        last, first = p[2].strip(), p[3].strip()
        jobs.append(
            {
                "contact_id": p[0].strip(),
                "gulp_id": p[1].strip(),
                "last": last,
                "first": first,
                "fs_letter": "",
                "fs_dir": slug_name(last, first),
                "src": "fails",
                "txt_path": "",
            }
        )
else:
    raise SystemExit("NEED oder FAILS oder TXT_DIR setzen")

# LIMIT = max erfolgreiche Outputs (Skips zählen nicht gegen LIMIT beim Schreiben)
print(f"jobs_candidates={len(jobs)} EXECUTE={EXECUTE} AID_ROOT={AID_ROOT}")
print(f"keywords={kw.KEYWORDS_VERSION}")

ok = fail = skip = 0
rows = ["status\tcontact_id\tletter\tdir\tpdf\tchars\tnote\tweb"]
web_urls = []

for j in jobs:
    if LIMIT > 0 and ok >= LIMIT:
        break
    cid = j["contact_id"]
    last, first = j["last"], j["first"]
    dname = j["fs_dir"] or slug_name(last, first)
    if j.get("txt_path"):
        text = Path(j["txt_path"]).read_text(encoding="utf-8", errors="replace").strip()
    else:
        text = cstm_text(cid, j.get("gulp_id") or "")
    if len(text) < MIN_LEN:
        skip += 1
        rows.append(f"SKIP\t{cid}\t\t{dname}\t\t{len(text)}\ttoo_short\t")
        print(f"SKIP short {dname} len={len(text)} cid={cid} gulp_id={j.get('gulp_id')}")
        continue

    ini = initials(first, last)
    pdf_name = f"AID-{ini}_{VERSION_TAG}-gulp.pdf"
    existing = find_existing_person_dir(AID_ROOT, dname)
    if existing:
        person_dir = existing
        letter = existing.parent.name
    else:
        letter = j["fs_letter"] or letter_bucket(dname, last)
        person_dir = AID_ROOT / letter / dname
    target = person_dir / pdf_name

    note = ""
    if (person_dir / "neu" / "cv").is_dir() and any((person_dir / "neu" / "cv").glob("AID-*.pdf")):
        note = "has_neu_cv"
    if target.exists():
        note = (note + "+exists").strip("+")

    if not EXECUTE:
        ok += 1
        rows.append(f"DRY\t{cid}\t{letter}\t{dname}\t{pdf_name}\t{len(text)}\t{note}\t")
        print(f"DRY {letter}/{dname}/{pdf_name} chars={len(text)} {note}")
        continue

    profile = gclean.clean_gulp_profile(
        text, first=first, last=last, version=VERSION_TAG, max_activities=8
    )
    n_exp = len(profile.get("experience") or [])
    print(f"  clean: experience={n_exp} snapshot={profile.get('snapshot_chars')} aid={profile.get('aid_name')}")
    if n_exp == 0:
        # Diagnose: Projekte-Body vorhanden?
        try:
            snap = gclean.strip_noise_lines(
                gclean.cut_after_projects_footer(gclean.latest_snapshot(text))
            )
            _, pbody = gclean._carve_projekte(snap)
            if len(pbody) > 200:
                print(
                    f"  WARN: Projekte-Body={len(pbody)} chars aber experience=0 "
                    f"— Format noch nicht erkannt ({dname})"
                )
        except Exception as e:
            print(f"  WARN: projekte-diagnose failed: {e}")
    if profile.get("gulp_id") and not j.get("gulp_id"):
        j["gulp_id"] = profile["gulp_id"]
    aid = profile.get("aid_name") or f"AID-{ini}_{VERSION_TAG}"
    ini = aid.split("_", 1)[0].replace("AID-", "") if aid.startswith("AID-") else ini
    # Person-Dir: sauberer AID-Name für get_best_pdf / Pipeline
    pdf_name = f"AID-{ini}_{VERSION_TAG}.pdf"
    target = person_dir / pdf_name
    html_doc = gclean.profile_to_html(
        profile, display_title=f"{last}, {first}".strip(", ") or aid
    )
    plain = gclean.profile_to_plain(profile)
    web = ""
    with tempfile.TemporaryDirectory(prefix="gulp2aid_") as td:
        td_path = Path(td)
        html_stem = f"AID-{ini}_{VERSION_TAG}"
        if OUT_DIR:
            html_stem = f"AID-{ini}_{VERSION_TAG}-gulp-{dname}"[:120]
            pdf_name = f"{html_stem}.pdf"
        html_path = td_path / f"{html_stem}.html"
        html_path.write_text(html_doc, encoding="utf-8")
        (td_path / f"{html_stem}.txt").write_text(plain, encoding="utf-8")
        (td_path / f"{html_stem}.experience.json").write_text(
            json.dumps(profile.get("experience") or [], indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        pdf = libreoffice_html_to_pdf(html_path, td_path)
        if not pdf:
            fail += 1
            rows.append(f"FAIL\t{cid}\t{letter}\t{dname}\t{pdf_name}\t{len(text)}\tlibreoffice\t")
            continue
        written = []
        if not SKIP_PERSON_DIR and not OUT_DIR:
            person_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pdf, target)
            written.append(str(target))
        elif not SKIP_PERSON_DIR and OUT_DIR:
            person_dir.mkdir(parents=True, exist_ok=True)
            person_pdf = person_dir / f"AID-{ini}_{VERSION_TAG}.pdf"
            shutil.copy2(pdf, person_pdf)
            written.append(str(person_pdf))
        if OUT_DIR:
            odir = Path(OUT_DIR)
            odir.mkdir(parents=True, exist_ok=True)
            dest = odir / pdf_name
            shutil.copy2(pdf, dest)
            shutil.copy2(html_path, odir / f"{html_stem}.html")
            shutil.copy2(td_path / f"{html_stem}.txt", odir / f"{html_stem}.txt")
            shutil.copy2(
                td_path / f"{html_stem}.experience.json",
                odir / f"{html_stem}.experience.json",
            )
            written.append(str(dest))
            web = str(dest)
        if WEB_COPY:
            wdir = Path(WEB_COPY)
            wdir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pdf, wdir / pdf_name)
            web = f"https://abpe.win.abcona.info/data/html_out/_gulp_preview/{pdf_name}"
            web_urls.append(web)
        if OUT_DIR and not WEB_COPY:
            web_urls.append(web)
    ok += 1
    nsec = len(profile.get("sections") or [])
    nexp = len(profile.get("experience") or [])
    rows.append(f"OK\t{cid}\t{letter}\t{dname}\t{pdf_name}\t{len(text)}\t{note}\t{web}")
    print(f"OK {dname} chars={len(text)} sections={nsec} experience={nexp} aid={aid}")
    for w in written:
        print(f"  → {w}")
    if web and WEB_COPY:
        print(f"  WEB {web}")

(OUT_LOG / "result.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
summary = {
    "execute": EXECUTE,
    "jobs_ok": ok,
    "fail": fail,
    "skip": skip,
    "version_tag": VERSION_TAG,
    "keywords": kw.KEYWORDS_VERSION,
    "aid_root": str(AID_ROOT),
    "web_urls": web_urls,
}
(OUT_LOG / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2))
print(f"LOG={OUT_LOG}")
if web_urls:
    print("DOWNLOAD:")
    for u in web_urls:
        print(f"  {u}")
PY
