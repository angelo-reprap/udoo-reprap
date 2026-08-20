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
# Keywords: Repo section_label_keywords + artifacts/gulp-keyword/section-keywords-v1.3-final.json
# Labeler (main_labeler) wird hier NICHT angefasst.
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
REPO="${REPO:-/mnt/public/udoo-reprap}"
AID_ROOT="${AID_ROOT:-/mnt/public/Berater/AID_profile}"
NEED="${NEED:-}"
FAILS="${FAILS:-}"
OUT_LOG="${OUT_LOG:-/tmp/gulp-to-aid-pdf-$(date +%Y%m%d-%H%M%S)}"
LIMIT="${LIMIT:-0}"
EXECUTE="${EXECUTE:-0}"
MIN_LEN="${MIN_LEN:-200}"
VERSION_TAG="${VERSION_TAG:-1.0.0.0}"

# Auto-Find NEED TSV wenn nicht gesetzt
if [[ -z "$NEED" && -z "$FAILS" ]]; then
  NEED="$(ls -td /tmp/gulp-vs-neu-*/need_neu_cv_with_fs_dir.tsv 2>/dev/null | head -1 || true)"
fi
if [[ -z "$NEED" && -z "$FAILS" ]]; then
  echo "FAIL: weder NEED noch FAILS gesetzt, und kein /tmp/gulp-vs-neu-*/need_neu_cv_with_fs_dir.tsv gefunden." >&2
  echo "  Inventur neu: bash $REPO/scripts/INVENTORY-gulp-vs-neu-cv.sh" >&2
  echo "  oder: NEED=/pfad/zur.tsv LIMIT=5 EXECUTE=0 bash $0" >&2
  exit 1
fi
if [[ -n "$NEED" && ! -f "$NEED" ]]; then
  echo "FAIL: NEED Datei fehlt: $NEED" >&2
  exit 1
fi
echo "NEED=${NEED:-} FAILS=${FAILS:-} LIMIT=$LIMIT EXECUTE=$EXECUTE"

mkdir -p "$OUT_LOG"
cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"
export REPO AID_ROOT NEED FAILS OUT_LOG LIMIT EXECUTE MIN_LEN VERSION_TAG

python3 manage.py shell <<'PY'
import os, re, html, subprocess, tempfile, shutil
from pathlib import Path
from django.apps import apps

REPO = Path(os.environ["REPO"])
AID_ROOT = Path(os.environ["AID_ROOT"])
NEED = (os.environ.get("NEED") or "").strip()
FAILS = (os.environ.get("FAILS") or "").strip()
OUT_LOG = Path(os.environ["OUT_LOG"])
LIMIT = int(os.environ.get("LIMIT") or "0")
EXECUTE = os.environ.get("EXECUTE", "0") in ("1", "true", "TRUE", "yes")
MIN_LEN = int(os.environ.get("MIN_LEN") or "200")
VERSION_TAG = os.environ.get("VERSION_TAG") or "1.0.0.0"

# Keywords aus Repo laden (ohne Django-App-Import-Kette)
import importlib.util
kw_path = REPO / "Repo_abpe/cv_extractor/incoming/services/section_label_keywords.py"
spec = importlib.util.spec_from_file_location("section_label_keywords", kw_path)
kw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kw)

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


def cstm_text(cid: str) -> str:
    st = None
    try:
        st = CrmContactCstm.objects.filter(contact_id=cid).first()
    except (ValueError, TypeError):
        st = None
    if st is None and str(cid).isdigit():
        st = CrmContactCstm.objects.filter(contact_id=int(cid)).first()
    return (getattr(st, "gulp_profil_c", None) or "").strip() if st else ""


# ── Jobs sammeln ────────────────────────────────────────────────────────────
jobs = []
if NEED and Path(NEED).is_file():
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
            }
        )
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
            }
        )
else:
    raise SystemExit("NEED oder FAILS TSV setzen")

if LIMIT > 0:
    jobs = jobs[:LIMIT]

print(f"jobs={len(jobs)} EXECUTE={EXECUTE} AID_ROOT={AID_ROOT}")
print(f"keywords={kw.KEYWORDS_VERSION}")

ok = fail = skip = 0
rows = ["status\tcontact_id\tletter\tdir\tpdf\tchars\tnote"]

for j in jobs:
    cid = j["contact_id"]
    last, first = j["last"], j["first"]
    dname = j["fs_dir"] or slug_name(last, first)
    text = cstm_text(cid)
    if len(text) < MIN_LEN:
        skip += 1
        rows.append(f"SKIP\t{cid}\t\t{dname}\t\t{len(text)}\ttoo_short")
        print(f"SKIP short {dname} len={len(text)}")
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
        rows.append(f"DRY\t{cid}\t{letter}\t{dname}\t{pdf_name}\t{len(text)}\t{note}")
        print(f"DRY {letter}/{dname}/{pdf_name} chars={len(text)} {note}")
        continue

    sections = split_sections(text)
    html_doc = to_html(first, last, j.get("gulp_id") or "", sections)
    person_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gulp2aid_") as td:
        td_path = Path(td)
        html_path = td_path / f"AID-{ini}_{VERSION_TAG}-gulp.html"
        html_path.write_text(html_doc, encoding="utf-8")
        pdf = libreoffice_html_to_pdf(html_path, td_path)
        if not pdf:
            fail += 1
            rows.append(f"FAIL\t{cid}\t{letter}\t{dname}\t{pdf_name}\t{len(text)}\tlibreoffice")
            continue
        shutil.copy2(pdf, target)
    ok += 1
    rows.append(f"OK\t{cid}\t{letter}\t{dname}\t{pdf_name}\t{len(text)}\t{note}")
    print(f"OK {target} chars={len(text)} sections={len(sections)}")

(OUT_LOG / "result.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
summary = {
    "execute": EXECUTE,
    "jobs": len(jobs),
    "ok": ok,
    "fail": fail,
    "skip": skip,
    "version_tag": VERSION_TAG,
    "keywords": kw.KEYWORDS_VERSION,
    "aid_root": str(AID_ROOT),
}
import json
(OUT_LOG / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2))
print(f"LOG={OUT_LOG}")
PY
