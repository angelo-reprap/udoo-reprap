#!/usr/bin/env bash
# Säubert Scheduler-Müll (meetme-delivery-*, e2e-test*, leere Tests).
# Behält: radar_poll, inbox_poll, prozess_tick, email_index, radar_berater_index.
#
# Default: DRY (nur Liste). Schreiben: EXECUTE=1
# Löschmodus: MODE=delete (ORM, Default — Tests sollen weg)
#             MODE=cancel (nur API cancel, Eintrag bleibt)
#
# ucs5:
#   cd /mnt/public/udoo-reprap && git pull origin cursor/matching-index-hygiene-1532
#   bash scripts/CLEANUP-scheduler-junk-jobs.sh
#   EXECUTE=1 bash scripts/CLEANUP-scheduler-junk-jobs.sh
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
EXECUTE="${EXECUTE:-0}"
MODE="${MODE:-delete}"
KEEP_KEYS="${KEEP_KEYS:-radar_poll,inbox_poll,prozess_tick,email_index,radar_berater_index,namazu_profiles_index,namazu_profiles_index_22,namazu_profiles_index_03,radar_berater_gulp_available,radar_berater_fl_available}"
OUT="${OUT:-/tmp/scheduler-cleanup-$(date +%Y%m%d-%H%M%S)}"

mkdir -p "$OUT"
cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"
export EXECUTE MODE KEEP_KEYS OUT

python3 manage.py shell <<'PY'
import json, os, re
from pathlib import Path
from django.apps import apps

EXECUTE = os.environ.get("EXECUTE", "0") in ("1", "true", "TRUE", "yes")
MODE = (os.environ.get("MODE") or "cancel").strip().lower()
KEEP = {k.strip() for k in (os.environ.get("KEEP_KEYS") or "").split(",") if k.strip()}
OUT = Path(os.environ["OUT"])

Job = None
model_label = None
for label, model in (("abpe_scheduler", "SchedulerJob"), ("abpe_scheduler", "ScheduledTask")):
    try:
        Job = apps.get_model(label, model)
        model_label = f"{label}.{model}"
        break
    except LookupError:
        continue
if Job is None:
    for m in apps.get_models():
        if m.__name__ in ("SchedulerJob", "ScheduledTask") and "schedul" in m._meta.app_label:
            Job = m
            model_label = f"{m._meta.app_label}.{m.__name__}"
            break

if Job is None:
    raise SystemExit("FAIL: kein SchedulerJob/ScheduledTask Model gefunden")

fields = [f.name for f in Job._meta.get_fields() if hasattr(f, "attname")]
print("model:", model_label, "fields:", fields)

def job_key(j):
    for attr in ("job_key", "name", "key", "slug", "title"):
        v = getattr(j, attr, None)
        if v:
            return str(v)
    p = getattr(j, "payload", None) or {}
    if isinstance(p, dict) and p.get("job"):
        return str(p["job"])
    return ""

def is_junk(key, j):
    k = (key or "").strip()
    p = getattr(j, "payload", None) or {}
    if k in KEEP:
        return None
    if isinstance(p, dict) and p.get("job") in KEEP:
        return None
    if not k:
        return "empty_key"
    if re.match(r"^meetme-delivery-\d+$", k):
        return "meetme_delivery"
    if k.startswith("e2e-test") or k.startswith("e2e_test"):
        return "e2e_test"
    if "ohne job_key" in k or k in ("test", "hello"):
        return "test_junk"
    if isinstance(p, dict):
        if set(p.keys()) <= {"hello", "test"} or p.get("test") is True:
            return "test_payload"
    return None

keep_rows, junk_rows = [], []
for j in Job.objects.all().order_by("id"):
    key = job_key(j)
    reason = is_junk(key, j)
    row = {
        "id": j.id,
        "key": key,
        "status": getattr(j, "status", None),
        "schedule_type": getattr(j, "schedule_type", None),
        "rrule": getattr(j, "rrule_string", None) or getattr(j, "rrule", None),
        "payload": getattr(j, "payload", None),
        "reason": reason,
    }
    (junk_rows if reason else keep_rows).append(row)

print(f"\nKEEP {len(keep_rows)}:")
for r in keep_rows:
    print(f"  id={r['id']} key={r['key']!r} type={r['schedule_type']} rrule={r['rrule']}")

print(f"\nJUNK {len(junk_rows)}:")
by = {}
for r in junk_rows:
    by[r["reason"]] = by.get(r["reason"], 0) + 1
    print(f"  id={r['id']} key={r['key']!r} reason={r['reason']} status={r['status']}")
print("junk by reason:", by)

(OUT / "cleanup-plan.json").write_text(
    json.dumps({"keep": keep_rows, "junk": junk_rows, "by_reason": by}, ensure_ascii=False, indent=2, default=str),
    encoding="utf-8",
)
print(f"plan → {OUT}/cleanup-plan.json")

if not EXECUTE:
    print("\nDRY-RUN — nichts geändert. EXECUTE=1 zum Säubern.")
else:
    done = fail = 0
    if MODE == "cancel":
        try:
            from apps.abpe_shaduler.scheduler_client import cancel_job, SchedulerClientError
        except Exception as e:
            print(f"WARN: cancel API nicht nutzbar ({e}) — falle auf ORM delete zurück")
            MODE = "delete"
    if MODE == "cancel":
        for r in junk_rows:
            try:
                cancel_job(r["id"])
                done += 1
                print(f"  CANCELLED id={r['id']} key={r['key']!r}")
            except Exception as e:
                fail += 1
                print(f"  FAIL cancel id={r['id']}: {e}")
        print(f"\nDONE cancel ok={done} fail={fail}")
    else:
        ids = [r["id"] for r in junk_rows]
        n, _ = Job.objects.filter(id__in=ids).delete()
        print(f"\nDELETED rows≈{n} ids={len(ids)}")
    print("Verbleibend:", Job.objects.count())
    print("Keys jetzt:", [job_key(j) for j in Job.objects.all().order_by("id")])
PY
