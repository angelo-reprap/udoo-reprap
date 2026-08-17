#!/usr/bin/env bash
# Inventar: Matching Anfrage ↔ Berater Schnittstellen (Outreach-/Match-Wizard)
#
# Liest Repo-URLs/Views + Frontend-Fetches aus und mappt sie auf den
# gewünschten Wizard-Flow. Optional Live-Probe gegen ucs5.
#
# Aufruf (Repo oder ucs5):
#   cd /mnt/public/udoo-reprap   # oder Cloud-Workspace
#   bash scripts/inventory-matching-wizard-apis.sh
#
# Optionen:
#   OUT=/tmp/matching-wizard-api-inventory.md   # Markdown speichern
#   JSON_OUT=/tmp/matching-wizard-api-inventory.json
#   LIVE=1 BASE=https://portal.example            # HTTP-Probe (nur Auth-Cookie/Session)
#   COOKIE='sessionid=…'                          # optional für LIVE
#   REPO=/mnt/public/udoo-reprap
#
set -euo pipefail

REPO="${REPO:-}"
if [[ -z "$REPO" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
fi

OUT="${OUT:-}"
JSON_OUT="${JSON_OUT:-}"
LIVE="${LIVE:-0}"
BASE="${BASE:-}"
COOKIE="${COOKIE:-}"

# Erlaubt: OUT=/tmp/x.md bash script   ODER   bash script OUT=/tmp/x.md
for arg in "$@"; do
  case "$arg" in
    OUT=*) OUT="${arg#OUT=}" ;;
    JSON_OUT=*) JSON_OUT="${arg#JSON_OUT=}" ;;
    LIVE=*) LIVE="${arg#LIVE=}" ;;
    BASE=*) BASE="${arg#BASE=}" ;;
    COOKIE=*) COOKIE="${arg#COOKIE=}" ;;
    REPO=*) REPO="${arg#REPO=}" ;;
  esac
done

export REPO OUT JSON_OUT LIVE BASE COOKIE

echo "======== Matching Wizard API-Inventar $(date -Iseconds) ========"
echo "REPO=$REPO"
echo

python3 - <<'PY'
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

REPO = Path(os.environ["REPO"])
LIVE = os.environ.get("LIVE", "0") == "1"
BASE = (os.environ.get("BASE") or "").rstrip("/")
COOKIE = os.environ.get("COOKIE") or ""
OUT = os.environ.get("OUT") or ""
JSON_OUT = os.environ.get("JSON_OUT") or ""

# Mount-Präfixe wie auf Live (abpe urls include)
MOUNTS = {
    "abpe_matching_workflow": "/matching/",
    "abpe_ki_wiz": "/ki-wizard/",
    "abpe_shaduler": "/shaduler/",
    "abpe_crm": "/crm/",
}

SOURCES = [
    {
        "app": "abpe_matching_workflow",
        "urls": REPO / "Repo_abpe/abpe_matching_workflow/incoming/urls.py",
        "views": REPO / "Repo_abpe/abpe_matching_workflow/incoming/views.py",
        "role": "Anfrage, Match, Shortlist, Kanban, Status",
    },
    {
        "app": "abpe_ki_wiz",
        "urls": REPO / "Repo_abpe/abpe_ki_wiz/incoming/urls.py",
        "views": REPO / "Repo_abpe/abpe_ki_wiz/incoming/api.py",
        "role": "KI Anfrage-Extrakt, Wizard-Sessions, Firma-Web",
    },
    {
        "app": "abpe_shaduler",
        "urls": REPO / "Repo_abpe/abpe_shaduler/incoming/urls.py",
        "views": REPO / "Repo_abpe/abpe_shaduler/incoming/views.py",
        "role": "Aufgaben/Wiedervorlage, Matching-Terms, Shortlist-Reset, Request-Patch",
    },
]

FRONTEND_JS = [
    REPO / "Repo_abpe/abpe_ui/incoming/static_abpe_ui/js/mod/mod-matching.js",
    REPO / "Repo_abpe/abpe_ui/incoming/mod-matching.js",
]

# Wizard-Flow (Soll) → Keywords / bekannte Pfade
WIZARD_STEPS = [
    {
        "id": "1_match",
        "title": "Anfrage matchen → Shortlist (Score ≥ Threshold)",
        "need": ["run matching", "shortlist"],
        "have_paths": [
            "/matching/api/requests/<uuid>/match/",
            "/matching/api/requests/<uuid>/shortlist/",
        ],
        "status_hint": "exists",
    },
    {
        "id": "2_deep_reason",
        "title": "Pro Kandidat: DeepSeek CV↔Anfrage Begründung (warum anschreiben / Chance)",
        "need": ["deep-reason", "rationale", "match explain"],
        "have_paths": [],
        "missing_paths": [
            "/matching/api/match/<uuid>/deep-reason/",
            # alternative
            "/ki-wizard/api/matching-outreach/reason/",
        ],
        "status_hint": "missing",
    },
    {
        "id": "3_letter_draft",
        "title": "Persönliches Anschreiben entwerfen (editierbar)",
        "need": ["letter draft", "anschreiben"],
        "have_paths": [
            # UI-only templates in STAGE_MAIL (mod-matching.js) + CRM send
            "/crm/api/email/send/",
        ],
        "missing_paths": [
            "/matching/api/match/<uuid>/letter/draft/",
        ],
        "status_hint": "partial",
        "note": "Frontend hat STAGE_MAIL-Templates; kein DeepSeek-Draft-Endpoint.",
    },
    {
        "id": "4_letter_polish",
        "title": "Optional: DeepSeek Anschreiben polieren (Stil behalten)",
        "need": ["letter polish", "polish"],
        "have_paths": [],
        "missing_paths": [
            "/matching/api/match/<uuid>/letter/polish/",
        ],
        "status_hint": "missing",
        "note": "CRM PBX hat polished_text für Call-Notes — nicht für Matching-Mail.",
    },
    {
        "id": "5_send",
        "title": "Mail senden + Match-Status (angeschrieben)",
        "need": ["email send", "kanban move", "match status"],
        "have_paths": [
            "/crm/api/email/send/",
            "/matching/api/match/<uuid>/move/",
            "/matching/api/match/<uuid>/status/",
        ],
        "status_hint": "exists",
    },
    {
        "id": "6_wiedervorlage",
        "title": "Wiedervorlage-Aufgabe anlegen (default, editierbar)",
        "need": ["aufgabe create", "wiedervorlage"],
        "have_paths": [
            "/shaduler/api/aufgaben/create/",
        ],
        "status_hint": "partial",
        "note": "API existiert; Wizard-Flow nach Send noch nicht verdrahtet als outreach/complete.",
    },
    {
        "id": "7_next",
        "title": "Nächster Kandidat (sequentieller Outreach-Wizard)",
        "need": ["outreach wizard ui"],
        "have_paths": [],
        "missing_paths": [
            "UI: Shortlist → Outreach-Wizard Modal-Sequenz",
            "/matching/api/match/<uuid>/outreach/complete/",
        ],
        "status_hint": "missing",
    },
    {
        "id": "support_ki_anfrage",
        "title": "Support: Anfrage aus E-Mail (KI-Anfragen-Wizard)",
        "need": ["matching-anfrage extract"],
        "have_paths": [
            "/ki-wizard/api/matching-anfrage/extract/",
        ],
        "status_hint": "exists",
    },
    {
        "id": "support_terms",
        "title": "Support: Berater-Terms / Shortlist-Reset / Request-Edit",
        "need": ["matching terms", "shortlist reset"],
        "have_paths": [
            "/shaduler/api/matching/terms/<uuid>/",
            "/shaduler/api/matching/shortlist/reset/<uuid>/",
            "/shaduler/api/matching/request/<uuid>/",
        ],
        "status_hint": "exists",
    },
]


def parse_urlpatterns(urls_path: Path) -> list[dict]:
    if not urls_path.is_file():
        return []
    text = urls_path.read_text(encoding="utf-8", errors="replace")
    # path('…', views.foo, name='…')  or  api.Class.as_view()
    pat = re.compile(
        r"""path\(\s*['\"]([^'\"]+)['\"]\s*,\s*([^,]+?)(?:,\s*name=['\"]([^'\"]+)['\"])?\s*\)""",
        re.MULTILINE,
    )
    rows = []
    for m in pat.finditer(text):
        route, view_ref, name = m.group(1), m.group(2).strip(), m.group(3) or ""
        view_ref = re.sub(r"\s+", " ", view_ref)
        rows.append({"route": route, "view": view_ref, "name": name})
    return rows


def parse_view_docs(views_path: Path) -> dict[str, dict]:
    """Map function/class name → {methods, summary, lineno}."""
    if not views_path.is_file():
        return {}
    text = views_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    out: dict[str, dict] = {}

    # api_view decorators + def
    for i, line in enumerate(lines):
        m = re.match(r"^def\s+(\w+)\s*\(", line)
        if m:
            name = m.group(1)
            methods = []
            summary = ""
            # look back up to 12 lines for @api_view / @extend_schema / docstring
            window = lines[max(0, i - 12) : i]
            for w in window:
                am = re.search(r"@api_view\(\[([^\]]+)\]\)", w)
                if am:
                    methods = [x.strip().strip("'\"") for x in am.group(1).split(",")]
                sm = re.search(r'summary\s*=\s*["\']([^"\']+)["\']', w)
                if sm:
                    summary = sm.group(1)
            # class-based: skip
            doc = ""
            if i + 1 < len(lines) and lines[i + 1].strip().startswith('"""'):
                doc = lines[i + 1].strip().strip('"')
            out[name] = {
                "kind": "function",
                "methods": methods,
                "summary": summary or doc,
                "lineno": i + 1,
            }

    # DRF APIView classes
    for i, line in enumerate(lines):
        m = re.match(r"^class\s+(\w+)\s*\(", line)
        if not m:
            continue
        name = m.group(1)
        methods = []
        for j in range(i + 1, min(i + 40, len(lines))):
            if re.match(r"^class\s+", lines[j]):
                break
            hm = re.match(r"\s+def\s+(get|post|put|patch|delete)\s*\(", lines[j], re.I)
            if hm:
                methods.append(hm.group(1).upper())
        summary = ""
        if i + 1 < len(lines) and '"""' in lines[i + 1]:
            summary = lines[i + 1].strip().strip('"')
        out[name] = {
            "kind": "class",
            "methods": methods,
            "summary": summary,
            "lineno": i + 1,
        }
    return out


def view_basename(view_ref: str) -> str:
    # views.api_shortlist  |  api.KiWizard…API.as_view()
    ref = view_ref.split("(")[0].strip()
    if "." in ref:
        ref = ref.split(".")[-1]
    return ref


def scan_frontend_fetches(paths: list[Path]) -> list[str]:
    found: set[str] = set()
    # Absolute API strings and concatenations with known prefixes
    abs_re = re.compile(
        r"""['\"](/(?:matching|ki-wizard|shaduler|crm)/api/[^'\"]+)['\"]"""
    )
    # API + 'requests/…'
    concat_re = re.compile(
        r"""(?:API|KI_API)\s*\+\s*['\"]([^'\"]+)['\"]"""
    )
    for p in paths:
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in abs_re.finditer(text):
            found.add(m.group(1))
        for m in concat_re.finditer(text):
            frag = m.group(1)
            if "KI_API" in text[max(0, m.start() - 80) : m.start()] or "ki-wizard" in frag:
                # crude: look at which const is left — check nearby
                nearby = text[max(0, m.start() - 120) : m.start()]
                if "KI_API" in nearby:
                    found.add("/ki-wizard/api/" + frag.lstrip("/"))
                else:
                    found.add("/matching/api/" + frag.lstrip("/"))
            else:
                nearby = text[max(0, m.start() - 120) : m.start()]
                if "KI_API" in nearby:
                    found.add("/ki-wizard/api/" + frag.lstrip("/"))
                else:
                    found.add("/matching/api/" + frag.lstrip("/"))
    return sorted(found)


def normalize_template(path: str) -> str:
    """Collapse Django converters / placeholders for comparison."""
    path = path.strip()
    path = re.sub(r"<[^>]+>", "<id>", path)
    path = re.sub(r"\{[^}]+\}", "<id>", path)
    path = re.sub(
        r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "/<id>",
        path,
        flags=re.I,
    )
    path = re.sub(r"/+", "/", path)
    return path.rstrip("/") or "/"


def static_tail(path: str, n: int = 3) -> str:
    """Last n static path segments (converters removed)."""
    parts = [x for x in re.sub(r"<[^>]+>|\{[^}]+\}", "", path).split("/") if x]
    return "/".join(parts[-n:])


def path_present(wanted: str, known_paths: list[str]) -> bool:
    if wanted.startswith("UI:"):
        return False
    wn = normalize_template(wanted)
    for p in known_paths:
        if normalize_template(p) == wn:
            return True
    wt = static_tail(wanted, 3)
    if not wt:
        return False
    for p in known_paths:
        if static_tail(p, 3) == wt:
            return True
        if static_tail(wanted, 2) and static_tail(p, 2) == static_tail(wanted, 2):
            # e.g. shortlist / match / status / move
            return True
    return False


def probe(url: str) -> dict:
    req = urllib.request.Request(url, method="GET")
    req.add_header("User-Agent", "matching-wizard-inventory/1.0")
    if COOKIE:
        req.add_header("Cookie", COOKIE)
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return {"ok": True, "status": resp.status, "url": url}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "url": url, "error": str(e.reason)}
    except Exception as e:
        return {"ok": False, "status": None, "url": url, "error": str(e)}


# ── collect ──────────────────────────────────────────────────────────────
inventory = {"apps": [], "frontend_fetches": [], "wizard_gap": [], "live": []}

all_full_paths: list[str] = []

for src in SOURCES:
    mount = MOUNTS[src["app"]]
    routes = parse_urlpatterns(src["urls"])
    docs = parse_view_docs(src["views"])
    entries = []
    for r in routes:
        full = mount + r["route"].lstrip("/")
        # skip empty portal root duplication noise handled below
        vb = view_basename(r["view"])
        meta = docs.get(vb, {})
        methods = meta.get("methods") or []
        # infer GET for Spectacular / template index
        if not methods:
            if "Spectacular" in r["view"] or vb in ("index", "KiWizardIndexView"):
                methods = ["GET"]
            elif "create" in r["route"] or r["route"].endswith("save/") or "/move/" in full:
                methods = ["POST?"]
            else:
                methods = ["?"]
        entry = {
            "full_path": full,
            "route": r["route"],
            "name": r["name"],
            "view": r["view"],
            "view_base": vb,
            "methods": methods,
            "summary": meta.get("summary") or "",
            "view_file": str(src["views"].relative_to(REPO)) if src["views"].is_file() else "",
            "lineno": meta.get("lineno"),
        }
        entries.append(entry)
        all_full_paths.append(full)
    inventory["apps"].append(
        {
            "app": src["app"],
            "mount": mount,
            "role": src["role"],
            "urls_file": str(src["urls"].relative_to(REPO)) if src["urls"].is_file() else "MISSING",
            "views_file": str(src["views"].relative_to(REPO)) if src["views"].is_file() else "MISSING",
            "routes": entries,
        }
    )

# CRM email send (used by matching UI) — light scan
crm_urls = list((REPO / "Repo_abpe/abpe_crm").rglob("urls*.py"))
crm_hits = []
for up in crm_urls:
    t = up.read_text(encoding="utf-8", errors="replace")
    if "email" in t.lower() or "berater" in t.lower():
        for m in re.finditer(
            r"""path\(\s*['\"]([^'\"]*email[^'\"]*)['\"]""", t, re.I
        ):
            crm_hits.append("/crm/" + m.group(1).lstrip("/"))
        for m in re.finditer(
            r"""path\(\s*['\"](api/email/[^'\"]+)['\"]""", t
        ):
            crm_hits.append("/crm/" + m.group(1).lstrip("/"))
inventory["crm_email_paths"] = sorted(set(crm_hits))

fe = scan_frontend_fetches(FRONTEND_JS)
inventory["frontend_fetches"] = fe

# Gap analysis
known = all_full_paths + inventory["crm_email_paths"] + fe
raw_blob = "\n".join(known)

for step in WIZARD_STEPS:
    have = []
    for hp in step.get("have_paths") or []:
        present = path_present(hp, known)
        if "email/send" in hp and any("email/send" in x for x in fe):
            present = True
        have.append({"path": hp, "present": bool(present)})

    miss = step.get("missing_paths") or []
    missing_still = []
    for mp in miss:
        if mp.startswith("UI:") or not path_present(mp, known):
            # still missing if distinctive token absent
            if mp.startswith("UI:"):
                missing_still.append(mp)
            else:
                token = None
                for needle in (
                    "deep-reason",
                    "letter/draft",
                    "letter/polish",
                    "outreach/complete",
                    "matching-outreach",
                ):
                    if needle in mp:
                        token = needle
                        break
                if token and token not in raw_blob:
                    missing_still.append(mp)
                elif not token and not path_present(mp, known):
                    missing_still.append(mp)

    status = step["status_hint"]
    if all(h["present"] for h in have) and have:
        if not missing_still:
            if status in ("partial", "exists"):
                # keep partial when note says UI not wired
                if step["id"] in ("6_wiedervorlage", "3_letter_draft"):
                    status = "partial"
                else:
                    status = "exists"
        elif status == "exists":
            status = "partial"
    elif status == "exists":
        status = "partial"

    inventory["wizard_gap"].append(
        {
            "id": step["id"],
            "title": step["title"],
            "status": status,
            "have": have,
            "missing": missing_still,
            "note": step.get("note", ""),
        }
    )

# Live probes (safe GETs only on list/health endpoints)
if LIVE and BASE:
    probe_paths = [
        "/matching/api/stats/",
        "/matching/api/requests/?page=1&per_page=5",
        "/ki-wizard/api/health/",
        "/shaduler/api/stats/",
        "/matching/api/schema/",
    ]
    for pp in probe_paths:
        inventory["live"].append(probe(BASE + pp))


# ── render markdown ──────────────────────────────────────────────────────
def md_escape(s: str) -> str:
    return s.replace("|", "\\|")


lines: list[str] = []
lines.append("# Matching Outreach Wizard — API-Inventar")
lines.append("")
lines.append(f"Repo: `{REPO}`")
lines.append("")
lines.append("## Wizard-Flow Gap (Soll vs. Ist)")
lines.append("")
lines.append("| Step | Status | Titel |")
lines.append("|------|--------|-------|")
for g in inventory["wizard_gap"]:
    badge = {"exists": "✅", "partial": "🟡", "missing": "❌"}.get(g["status"], g["status"])
    lines.append(f"| `{g['id']}` | {badge} `{g['status']}` | {md_escape(g['title'])} |")
lines.append("")
for g in inventory["wizard_gap"]:
    lines.append(f"### {g['id']} — {g['title']}")
    lines.append(f"- **Status:** `{g['status']}`")
    if g.get("note"):
        lines.append(f"- **Hinweis:** {g['note']}")
    if g.get("have"):
        lines.append("- Vorhanden / geprüft:")
        for h in g["have"]:
            mark = "✅" if h["present"] else "❌"
            lines.append(f"  - {mark} `{h['path']}`")
    if g.get("missing"):
        lines.append("- Fehlt / UI-only:")
        for m in g["missing"]:
            lines.append(f"  - `{m}`")
    lines.append("")

lines.append("## Apps / URL-Module")
lines.append("")
for app in inventory["apps"]:
    lines.append(f"### {app['app']} → `{app['mount']}`")
    lines.append(f"- Rolle: {app['role']}")
    lines.append(f"- urls: `{app['urls_file']}`")
    lines.append(f"- views/api: `{app['views_file']}`")
    lines.append("")
    lines.append("| Methods | Path | View | Name | Summary |")
    lines.append("|--------|------|------|------|---------|")
    for e in app["routes"]:
        meth = ",".join(e["methods"]) if e["methods"] else "?"
        summ = (e["summary"] or "")[:60]
        loc = f":{e['lineno']}" if e.get("lineno") else ""
        lines.append(
            f"| {meth} | `{e['full_path']}` | `{e['view_base']}{loc}` | `{e['name']}` | {md_escape(summ)} |"
        )
    lines.append("")

if inventory.get("crm_email_paths"):
    lines.append("## CRM E-Mail Pfade (Scan)")
    lines.append("")
    for p in inventory["crm_email_paths"]:
        lines.append(f"- `{p}`")
    lines.append("")

lines.append("## Frontend-Fetches (`mod-matching.js`)")
lines.append("")
for p in inventory["frontend_fetches"]:
    lines.append(f"- `{p}`")
lines.append("")

lines.append("## Empfohlene neue Endpoints (für Wizard)")
lines.append("")
lines.append("| Method | Path | Zweck |")
lines.append("|--------|------|-------|")
lines.append("| POST | `/matching/api/match/<uuid>/deep-reason/` | DeepSeek: Warum match / Anschreiben / Reply-Chance |")
lines.append("| POST | `/matching/api/match/<uuid>/letter/draft/` | Persönliches Anschreiben (CV + Anfrage) |")
lines.append("| POST | `/matching/api/match/<uuid>/letter/polish/` | Text polieren, Stil behalten |")
lines.append("| POST | `/matching/api/match/<uuid>/outreach/complete/` | Send-Status + optionale Wiedervorlage in einem Rutsch |")
lines.append("")

if inventory["live"]:
    lines.append("## Live-Probe")
    lines.append("")
    for r in inventory["live"]:
        st = r.get("status")
        mark = "✅" if r.get("ok") else "❌"
        err = f" — {r.get('error')}" if r.get("error") else ""
        lines.append(f"- {mark} `{st}` `{r['url']}`{err}")
    lines.append("")

md = "\n".join(lines)
print(md)

if OUT:
    outp = Path(OUT)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(md, encoding="utf-8")
    print(f"\n--- wrote {OUT}", file=sys.stderr)

if JSON_OUT:
    jp = Path(JSON_OUT)
    jp.parent.mkdir(parents=True, exist_ok=True)
    jp.write_text(
        json.dumps(inventory, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"--- wrote {JSON_OUT}", file=sys.stderr)

# Exit non-zero if critical wizard steps missing? No — inventory always OK.
sys.exit(0)
PY
