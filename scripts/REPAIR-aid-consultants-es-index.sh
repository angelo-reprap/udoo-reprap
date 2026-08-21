#!/usr/bin/env bash
# Repariert ES abpe_consultants_index aus der DB (completed|validated|profile_ready).
# Schließt die Lücke DB≫ES ohne Full-Pipeline.
#
# Default: DRY (zählen). Schreiben: EXECUTE=1
# Nur fehlende: default. Alle neu: REBUILD=1
#
# ucs5:
#   cd /mnt/public/udoo-reprap && git pull origin cursor/matching-index-hygiene-1532
#   bash scripts/REPAIR-aid-consultants-es-index.sh
#   EXECUTE=1 LIMIT=100 bash scripts/REPAIR-aid-consultants-es-index.sh   # Test
#   EXECUTE=1 bash scripts/REPAIR-aid-consultants-es-index.sh             # alle fehlenden
#   EXECUTE=1 REBUILD=1 bash scripts/REPAIR-aid-consultants-es-index.sh   # alles neu
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
EXECUTE="${EXECUTE:-0}"
REBUILD="${REBUILD:-0}"
LIMIT="${LIMIT:-0}"
STATUSES="${STATUSES:-completed,validated,profile_ready}"
INDEX="${INDEX:-abpe_consultants_index}"
SKIP_EN="${SKIP_EN:-1}"
OUT="${OUT:-/tmp/aid-es-repair-$(date +%Y%m%d-%H%M%S)}"

mkdir -p "$OUT"
cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"
export EXECUTE REBUILD LIMIT STATUSES INDEX SKIP_EN OUT

python3 manage.py shell <<'PY'
import json, os
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from django.apps import apps

EXECUTE = os.environ.get("EXECUTE", "0") in ("1", "true", "TRUE", "yes")
REBUILD = os.environ.get("REBUILD", "0") in ("1", "true", "TRUE", "yes")
LIMIT = int(os.environ.get("LIMIT") or "0")
STATUSES = [s.strip() for s in (os.environ.get("STATUSES") or "completed").split(",") if s.strip()]
INDEX = os.environ.get("INDEX") or "abpe_consultants_index"
SKIP_EN = os.environ.get("SKIP_EN", "1") in ("1", "true", "TRUE", "yes")
OUT = Path(os.environ["OUT"])

from elasticsearch import Elasticsearch

cfg = {}
try:
    cfg = json.load(open("/opt/abpe/backend/settings.json"))
except Exception:
    pass
hosts = (cfg.get("elasticsearch") or {}).get("hosts") or ["http://localhost:9200"]
es = Elasticsearch(hosts, verify_certs=False, request_timeout=60)
print("ES ping:", es.ping(), "index:", INDEX, "hosts:", hosts)

Consultant = apps.get_model("cv_extractor", "Consultant")
qs = Consultant.objects.filter(status__in=STATUSES)
if SKIP_EN:
    qs = qs.exclude(aid__endswith="-en")


def aid_ver(aid):
    try:
        parts = (aid or "").split("_")[-1].replace("-en", "").split(".")
        return tuple(int(x) for x in parts if x.isdigit())
    except Exception:
        return (0,)


groups = defaultdict(list)
for c in qs.only("id", "aid", "consultant_dir", "created_at", "status"):
    key = (c.consultant_dir or c.aid or str(c.id)).lower().strip()
    groups[key].append(c)

best_ids = []
for _key, entries in groups.items():
    best = max(
        entries,
        key=lambda c: (aid_ver(c.aid), c.created_at.timestamp() if c.created_at else 0),
    )
    best_ids.append(best.id)

print(f"DB pool status={STATUSES} skip_en={SKIP_EN}: raw={qs.count()} dedup={len(best_ids)}")

existing = set()
es_count = 0
if es.indices.exists(index=INDEX):
    try:
        es_count = es.count(index=INDEX)["count"]
        # scroll all ids
        resp = es.search(
            index=INDEX,
            scroll="2m",
            size=1000,
            _source=False,
            query={"match_all": {}},
        )
        sid = resp.get("_scroll_id")
        hits = resp.get("hits", {}).get("hits", [])
        while hits:
            for h in hits:
                if h.get("_id"):
                    existing.add(h["_id"])
            resp = es.scroll(scroll_id=sid, scroll="2m")
            sid = resp.get("_scroll_id")
            hits = resp.get("hits", {}).get("hits", [])
        try:
            es.clear_scroll(scroll_id=sid)
        except Exception:
            pass
        print(f"ES docs={es_count} ids_loaded={len(existing)}")
    except Exception as e:
        print("ES list warn:", e)
        try:
            es_count = es.count(index=INDEX)["count"]
        except Exception:
            es_count = 0
else:
    print("ES index missing — will create on write")

MAPPING = {
    "mappings": {
        "properties": {
            "aid": {"type": "keyword"},
            "version": {"type": "keyword"},
            "first_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "last_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "full_name": {"type": "text"},
            "headline": {"type": "text"},
            "location": {"type": "keyword"},
            "availability": {"type": "keyword"},
            "status": {"type": "keyword"},
            "consultant_dir": {"type": "keyword"},
            "searchable_text": {"type": "text", "analyzer": "standard"},
            "skills": {"type": "keyword"},
            "indexed_at": {"type": "date"},
            "source": {"type": "keyword"},
        }
    },
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
}

if EXECUTE and not es.indices.exists(index=INDEX):
    es.indices.create(index=INDEX, body=MAPPING)
    print("created index", INDEX)

candidates = list(
    Consultant.objects.filter(id__in=best_ids).prefetch_related("skills__skill")
)

missing = []
for c in candidates:
    if REBUILD or (c.aid not in existing):
        missing.append(c)

if LIMIT > 0:
    missing = missing[:LIMIT]

sample_aids = [c.aid for c in missing[:8]]
print(f"to_index={len(missing)} (rebuild={REBUILD}) sample={sample_aids}")

plan = {
    "db_raw": qs.count(),
    "db_dedup": len(best_ids),
    "es_before": es_count,
    "es_ids_loaded": len(existing),
    "to_index": len(missing),
    "rebuild": REBUILD,
    "sample": sample_aids,
}
(OUT / "repair-plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"plan → {OUT}/repair-plan.json")

if not missing:
    print("Nichts zu tun.")
elif not EXECUTE:
    print("\nDRY-RUN — nichts geschrieben. EXECUTE=1 zum Indexieren.")
else:
    ok = fail = 0
    for i, c in enumerate(missing, 1):
        try:
            skills = []
            try:
                skills = sorted({cs.skill.name for cs in c.skills.all() if getattr(cs, "skill", None)})
            except Exception:
                pass
            version = ""
            if c.aid and "_" in c.aid:
                version = c.aid.split("_", 1)[-1]
            parts = [
                c.headline or "",
                c.aid or "",
                c.first_name or "",
                c.last_name or "",
                c.location or "",
                c.availability or "",
                " ".join(skills[:200]),
            ]
            doc = {
                "aid": c.aid,
                "version": version,
                "first_name": c.first_name or "",
                "last_name": c.last_name or "",
                "full_name": f"{c.first_name or ''} {c.last_name or ''}".strip(),
                "headline": c.headline or "",
                "location": c.location or "",
                "availability": c.availability or "",
                "status": c.status,
                "consultant_dir": c.consultant_dir or "",
                "searchable_text": " ".join(p for p in parts if p),
                "skills": skills[:500],
                "indexed_at": datetime.utcnow().isoformat() + "Z",
                "source": "repair_aid_es",
            }
            es.index(index=INDEX, id=c.aid, document=doc)
            ok += 1
            if i % 50 == 0 or i == len(missing):
                print(f"  … {i}/{len(missing)} ok={ok} fail={fail}")
        except Exception as e:
            fail += 1
            print(f"  FAIL {c.aid}: {e}")
    print(f"DONE ok={ok} fail={fail}")
    print("ES count now:", es.count(index=INDEX)["count"])
PY
