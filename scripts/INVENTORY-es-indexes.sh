#!/usr/bin/env bash
# Inventur aller ES-Indizes: KEEP / STALE / CANDIDATE_DELETE / UNKNOWN
# Read-only. Kein Löschen.
#
#   bash scripts/INVENTORY-es-indexes.sh
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
OUT="${OUT:-/tmp/es-index-inventory-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$OUT"

cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"
export OUT

python3 manage.py shell <<'PY'
import json, os
from datetime import datetime, timezone, timedelta
from pathlib import Path

OUT = Path(os.environ["OUT"])

# Produktive Indizes — NICHT löschen
KEEP = {
    "abpe_consultants_index": "AID/CV Shortlist-Pool (DB-Sync)",
    "abpe_namazu_profiles": "Gulp/Namazu HTML-Korpus (~23k)",
    "abpe_radar_berater": "Radar Berater — Periodik radar_berater_index",
    "abpe_emails": "Posteingang — Periodik email_index",
    "content": "CRM Personen",
    "content_firma": "CRM Firmen",
    "dms": "Dokumentenablage",
    "abpe_skills_index": "Skill-Stammdaten / Embeddings (Enricher)",
}

# Optional Radar-Anfragen-Index (falls vorhanden)
KEEP_PREFIXES = ("abpe_radar",)  # abpe_radar / abpe_radar_* außer bewusst junk

# Verdächtig / Test / leer / Experiment — nur Kandidaten, nicht auto-löschen
CANDIDATE_DELETE_EXACT = {
    "abpe_profiles_v2": "historisch leer / Experiment",
    "abpe_profile_versions": "Experiment Profile-Versionen (klein)",
    "abpe_profile_versions_v2": "Experiment Profile-Versionen v2 (klein)",
}
JUNK_NAME_RE = ("test", "e2e", "tmp", "scratch", "sandbox", "demo-index")

from elasticsearch import Elasticsearch
cfg = {}
try:
    cfg = json.load(open("/opt/abpe/backend/settings.json"))
except Exception:
    pass
hosts = (cfg.get("elasticsearch") or {}).get("hosts") or ["http://localhost:9200"]
es = Elasticsearch(hosts, verify_certs=False, request_timeout=60)

stats = es.indices.stats(metric="docs,store")
indices = sorted(stats.get("indices", {}).keys())
now = datetime.now(timezone.utc)
rows = []

for name in indices:
    st = stats["indices"][name]
    docs = st.get("primaries", {}).get("docs", {}).get("count", 0)
    size = st.get("primaries", {}).get("store", {}).get("size_in_bytes", 0)
    max_idx = None
    try:
        r = es.search(index=name, size=0, aggs={"m": {"max": {"field": "indexed_at"}}})
        v = (r.get("aggregations") or {}).get("m", {}).get("value")
        if v is not None:
            max_idx = datetime.fromtimestamp(v / 1000, tz=timezone.utc)
    except Exception:
        pass

    cls = "UNKNOWN"
    note = ""
    low = name.lower()
    if name in KEEP:
        cls = "KEEP"
        note = KEEP[name]
    elif name in CANDIDATE_DELETE_EXACT:
        cls = "CANDIDATE_DELETE"
        note = CANDIDATE_DELETE_EXACT[name]
    elif any(j in low for j in JUNK_NAME_RE):
        cls = "CANDIDATE_DELETE"
        note = "Name sieht nach Test/Tmp aus"
    elif any(low.startswith(p) for p in KEEP_PREFIXES):
        cls = "KEEP"
        note = "Radar-Familie"
    elif docs == 0:
        cls = "CANDIDATE_DELETE"
        note = "leer (0 docs)"

    stale = False
    if cls == "KEEP" and max_idx is not None:
        age_days = (now - max_idx).days
        if name in ("abpe_namazu_profiles",) and age_days > 14:
            stale = True
            note = f"{note} | STALE indexed_at vor {age_days}d"
        elif name == "abpe_consultants_index" and age_days > 7:
            stale = True
            note = f"{note} | indexed_at vor {age_days}d (Import/Repair prüfen)"

    rows.append({
        "index": name,
        "docs": docs,
        "size_mb": round(size / 1024 / 1024, 2),
        "max_indexed_at": max_idx.isoformat() if max_idx else None,
        "class": cls,
        "stale": stale,
        "note": note,
    })

by = {"KEEP": [], "CANDIDATE_DELETE": [], "UNKNOWN": [], "STALE_KEEP": []}
for r in rows:
    by[r["class"]].append(r)
    if r["stale"]:
        by["STALE_KEEP"].append(r)

print("=== ES Index Inventur ===")
for cls in ("KEEP", "STALE_KEEP", "CANDIDATE_DELETE", "UNKNOWN"):
    print(f"\n-- {cls} ({len(by[cls])}) --")
    for r in by[cls]:
        print(f"  {r['index']:40} docs={r['docs']:<8} {r['size_mb']:>8}MB  indexed={r['max_indexed_at']}  {r['note']}")

report = {"generated_at": now.isoformat(), "hosts": hosts, "rows": rows, "by_class": {k: len(v) for k, v in by.items()}}
(OUT / "es-indexes.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"\n→ {OUT}/es-indexes.json")
print("\nLöschen nur gezielt:")
print("  EXECUTE=1 INDEXES=abpe_profiles_v2,abpe_profile_versions bash scripts/CLEANUP-es-candidate-indexes.sh")
PY
