#!/usr/bin/env bash
# Read-only Gesundheitscheck: DB / ES / Scheduler / Namazu.
#
# ucs5:
#   cd /mnt/public/udoo-reprap && git pull origin cursor/matching-index-hygiene-1532
#   bash scripts/CHECK-matching-index-health.sh
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
OUT="${OUT:-/tmp/matching-health-$(date +%Y%m%d-%H%M%S)}"
NAMAZU_DIR="${NAMAZU_DIR:-/var/www/namazu/index}"
CLASSIC_NAMAZU="${CLASSIC_NAMAZU:-/var/namazu/index}"
KEEP_KEYS="${KEEP_KEYS:-radar_poll,inbox_poll,prozess_tick,email_index,radar_berater_index,namazu_profiles_index,namazu_profiles_index_22,namazu_profiles_index_03,radar_berater_gulp_available,radar_berater_fl_available}"

mkdir -p "$OUT"
cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"
export OUT NAMAZU_DIR CLASSIC_NAMAZU KEEP_KEYS

python3 manage.py shell <<'PY'
import json, os
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(os.environ["OUT"])
NAMAZU_DIR = Path(os.environ.get("NAMAZU_DIR") or "/var/www/namazu/index")
CLASSIC = Path(os.environ.get("CLASSIC_NAMAZU") or "/var/namazu/index")
KEEP = {k.strip() for k in (os.environ.get("KEEP_KEYS") or "").split(",") if k.strip()}

report = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "notes": [
        "Shortlist (MatchingEngine) nutzt aktuell nur die DB — nicht ES/Namazu.",
        "Klassisches Namazu-Binary ist Legacy; Suche läuft über ES abpe_namazu_profiles.",
        "AID-ES sollte ≈ deduplizierte DB-Consultants sein; Gap → REPAIR-aid-consultants-es-index.sh",
        "Scheduler sollte die 5 Periodics haben; Junk → CLEANUP-scheduler-junk-jobs.sh",
    ],
}

# ── DB ────────────────────────────────────────────────────────────
from django.apps import apps
from django.db.models import Count

Consultant = apps.get_model("cv_extractor", "Consultant")
qs = Consultant.objects.all()
by_status = dict(qs.values("status").annotate(c=Count("id")).values_list("status", "c"))
pool = qs.filter(status__in=["completed", "validated", "profile_ready"])
pool_de = pool.exclude(aid__endswith="-en")
pool_en = pool.filter(aid__endswith="-en")
# Dedup wie Repair: neueste AID pro consultant_dir
from collections import defaultdict

def _aid_ver(aid):
    try:
        parts = (aid or "").split("_")[-1].replace("-en", "").split(".")
        return tuple(int(x) for x in parts if x.isdigit())
    except Exception:
        return (0,)

groups = defaultdict(list)
for c in pool_de.only("id", "aid", "consultant_dir", "created_at"):
    key = (c.consultant_dir or c.aid or str(c.id)).lower().strip()
    groups[key].append(c)
dedup_de = len(groups)

db = {
    "consultants_total": qs.count(),
    "by_status": by_status,
    "with_skills": qs.filter(skills__isnull=False).distinct().count(),
    "match_pool_completed_validated": qs.filter(status__in=["completed", "validated"]).count(),
    "profile_ready": qs.filter(status="profile_ready").count(),
    "pool_completed_validated_ready": pool.count(),
    "pool_de_skip_en": pool_de.count(),
    "pool_en_only": pool_en.count(),
    "pool_de_dedup_by_dir": dedup_de,
}
print("DB:", json.dumps(db, ensure_ascii=False, indent=2))
report["db"] = db

# ── Scheduler ─────────────────────────────────────────────────────
sched = {"model": None, "jobs": [], "junk_count": 0, "keep_count": 0}
Job = None
for label, model in (("abpe_scheduler", "SchedulerJob"), ("abpe_scheduler", "ScheduledTask")):
    try:
        Job = apps.get_model(label, model)
        sched["model"] = f"{label}.{model}"
        break
    except LookupError:
        continue
if Job is None:
    for m in apps.get_models():
        if m.__name__ in ("SchedulerJob", "ScheduledTask") and "schedul" in m._meta.app_label:
            Job = m
            sched["model"] = f"{m._meta.app_label}.{m.__name__}"
            break

def job_key(j):
    for attr in ("job_key", "name", "key", "slug", "title"):
        v = getattr(j, attr, None)
        if v:
            return str(v)
    p = getattr(j, "payload", None) or {}
    if isinstance(p, dict) and p.get("job"):
        return str(p["job"])
    return ""

if Job is not None:
    import re
    for j in Job.objects.all().order_by("id"):
        key = job_key(j)
        row = {
            "id": j.id,
            "key": key,
            "status": getattr(j, "status", None),
            "schedule_type": getattr(j, "schedule_type", None),
            "rrule": getattr(j, "rrule_string", None) or getattr(j, "rrule", None),
            "payload": getattr(j, "payload", None),
        }
        sched["jobs"].append(row)
        is_keep = key in KEEP or (
            isinstance(row["payload"], dict) and row["payload"].get("job") in KEEP
        )
        junk = False
        if not is_keep:
            if not key or re.match(r"^meetme-delivery-\d+$", key) or key.startswith(("e2e-test", "e2e_test")):
                junk = True
            elif key in ("test", "hello") or "ohne job_key" in key:
                junk = True
        if junk:
            sched["junk_count"] += 1
        elif is_keep:
            sched["keep_count"] += 1
else:
    sched["error"] = "SchedulerJob/ScheduledTask model not found"

print("Scheduler:", json.dumps({
    "model": sched["model"],
    "total": len(sched["jobs"]),
    "keep": sched["keep_count"],
    "junk": sched["junk_count"],
    "keys": [j["key"] for j in sched["jobs"][:40]],
}, ensure_ascii=False, indent=2))
report["scheduler"] = sched

# ── ES ────────────────────────────────────────────────────────────
es_info = {}
try:
    from elasticsearch import Elasticsearch
    cfg = {}
    try:
        cfg = json.load(open("/opt/abpe/backend/settings.json"))
    except Exception:
        pass
    hosts = (cfg.get("elasticsearch") or {}).get("hosts") or ["http://localhost:9200"]
    es = Elasticsearch(hosts, verify_certs=False, request_timeout=30)

    def es_count(index):
        try:
            return es.count(index=index)["count"]
        except Exception as e:
            return f"ERR:{e}"

    def es_max(index, field="indexed_at"):
        try:
            r = es.search(index=index, size=0, aggs={"m": {"max": {"field": field}}})
            v = (r.get("aggregations") or {}).get("m", {}).get("value")
            if v is None:
                return None
            return datetime.fromtimestamp(v / 1000, tz=timezone.utc).isoformat()
        except Exception as e:
            return f"ERR:{e}"

    for idx, field in (
        ("abpe_consultants_index", "indexed_at"),
        ("abpe_namazu_profiles", "indexed_at"),
        ("content", None),
        ("abpe_radar_berater", "indexed_at"),
    ):
        entry = {"count": es_count(idx)}
        if field:
            entry["max_" + field] = es_max(idx, field)
        es_info[idx] = entry
except Exception as e:
    es_info = {"error": str(e)}

print("ES:", json.dumps(es_info, ensure_ascii=False, indent=2))
report["elasticsearch"] = es_info

# ── Namazu FS ─────────────────────────────────────────────────────
namazu = {"dir": str(NAMAZU_DIR), "exists": NAMAZU_DIR.is_dir()}
if NAMAZU_DIR.is_dir():
    namazu["html_count"] = sum(1 for _ in NAMAZU_DIR.glob("*.html"))
classic = {"dir": str(CLASSIC), "exists": CLASSIC.is_dir()}
if CLASSIC.is_dir():
    nmz = CLASSIC / "NMZ.status"
    classic["nmz_status_exists"] = nmz.exists()
    if nmz.exists():
        classic["nmz_status_mtime"] = datetime.fromtimestamp(
            nmz.stat().st_mtime, tz=timezone.utc
        ).isoformat()
    classic["files"] = sorted(x.name for x in CLASSIC.iterdir())[:20]

report["namazu_html"] = namazu
report["classic_namazu"] = classic
print("Namazu HTML:", json.dumps(namazu, ensure_ascii=False))
print("Classic Namazu:", json.dumps(classic, ensure_ascii=False))

# Gap hint — vergleichbar mit REPAIR (DE, ohne -en, dedup)
try:
    es_n = es_info.get("abpe_consultants_index", {}).get("count")
    if isinstance(es_n, int):
        report["aid_es_gap_hint"] = {
            "db_pool_all_incl_en": db.get("pool_completed_validated_ready"),
            "db_pool_de_skip_en": db.get("pool_de_skip_en"),
            "db_pool_de_dedup": db.get("pool_de_dedup_by_dir"),
            "es_consultants": es_n,
            "gap_vs_dedup_de": max(0, (db.get("pool_de_dedup_by_dir") or 0) - es_n),
            "note": (
                "Repair indexiert DE/skip_en + dedup(dir). "
                "Wenn gap_vs_dedup_de==0 und to_index=0 → AID-ES für diesen Pool fertig. "
                "EN (-en) und Rohtexte außerhalb der Consultant-DB gehören nicht in diesen Gap."
            ),
        }
        print("AID-ES gap hint:", json.dumps(report["aid_es_gap_hint"], ensure_ascii=False, indent=2))
except Exception:
    pass

(OUT / "health.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
    encoding="utf-8",
)
print(f"\n→ {OUT}/health.json")
PY
