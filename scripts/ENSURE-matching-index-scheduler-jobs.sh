#!/usr/bin/env bash
# Stellt sicher, dass die 5 Periodik-Jobs existieren
# (ruft register_scheduler_jobs auf).
#
#   bash scripts/ENSURE-matching-index-scheduler-jobs.sh
#   DRY_RUN=1 bash scripts/ENSURE-matching-index-scheduler-jobs.sh
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
DRY_RUN="${DRY_RUN:-0}"

cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"

CMD=""
for cand in \
  apps/abpe_shaduler/management/commands/register_scheduler_jobs.py \
  apps/abpe_scheduler/management/commands/register_scheduler_jobs.py
do
  if [[ -f "$cand" ]]; then
    CMD="$cand"
    break
  fi
done

if [[ -n "$CMD" ]]; then
  echo "→ register_scheduler_jobs ($CMD)"
  if [[ "$DRY_RUN" == "1" ]]; then
    python3 manage.py register_scheduler_jobs --dry-run
  else
    python3 manage.py register_scheduler_jobs
  fi
else
  echo "WARN: register_scheduler_jobs fehlt live — Periodik manuell prüfen."
  echo "Erwartet: radar_poll, inbox_poll, prozess_tick, email_index, radar_berater_index"
fi

echo
echo "Aktuelle Jobs:"
python3 manage.py shell <<'PY'
from django.apps import apps

Job = None
for label, model in (("abpe_scheduler", "SchedulerJob"), ("abpe_scheduler", "ScheduledTask")):
    try:
        Job = apps.get_model(label, model)
        print("model:", f"{label}.{model}")
        break
    except LookupError:
        continue
if Job is None:
    for m in apps.get_models():
        if m.__name__ in ("SchedulerJob", "ScheduledTask") and "schedul" in m._meta.app_label:
            Job = m
            print("model:", f"{m._meta.app_label}.{m.__name__}")
            break
if Job is None:
    print("FAIL: kein Scheduler-Model")
else:
    for j in Job.objects.all().order_by("id"):
        key = None
        for attr in ("job_key", "name", "key"):
            key = getattr(j, attr, None)
            if key:
                break
        p = getattr(j, "payload", None) or {}
        if not key and isinstance(p, dict):
            key = p.get("job")
        print(
            j.id,
            key,
            getattr(j, "status", None),
            getattr(j, "schedule_type", None),
            getattr(j, "rrule_string", None) or getattr(j, "rrule", None),
            p if isinstance(p, dict) else None,
        )
PY
