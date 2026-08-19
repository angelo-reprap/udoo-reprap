#!/usr/bin/env bash
# ANALYZE: Warum hängt Radar · Berater (z.B. Agelis Wassilios oben)?
# Nur lesen (außer SYNC_PROBE=1 → kleiner Live-Sync).
#
# Auf ucs5:
#   cd /mnt/public/udoo-reprap && git fetch origin cursor/posteingang-radar-fix-1532
#   bash <(git show origin/cursor/posteingang-radar-fix-1532:scripts/ANALYZE-radar-berater-stale.sh)
#
# Optional:
#   NAME='Agelis' bash …                 # Fokus-Name
#   SYNC_PROBE=1 LIMIT=5 bash …          # 1 Seite Gulp sync (schreibt!)
#   SYNC_PROBE_FL=1 LIMIT=5 bash …       # 1 Seite FL sync (schreibt!)
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
PYBIN="${PYBIN:-/opt/abpe/venv311/bin/python}"
NAME="${NAME:-Agelis}"
SYNC_PROBE="${SYNC_PROBE:-0}"
SYNC_PROBE_FL="${SYNC_PROBE_FL:-0}"
LIMIT="${LIMIT:-5}"
OUT_DIR="${OUT_DIR:-/tmp/radar-berater-analyze-$(date +%Y%m%d-%H%M%S)}"

mkdir -p "$OUT_DIR"
cd "$BACKEND"

echo "======== ANALYZE Radar Berater Stale ========"
echo "Start: $(date -Iseconds) OUT=$OUT_DIR NAME=$NAME"
echo "SYNC_PROBE=$SYNC_PROBE SYNC_PROBE_FL=$SYNC_PROBE_FL LIMIT=$LIMIT"
echo

"$PYBIN" - <<PY | tee "$OUT_DIR/analyze.log"
import os, json, django
from datetime import timedelta
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()

from django.conf import settings
from django.db.models import Count, Max, Min, Q
from django.utils import timezone

from apps.abpe_shaduler.models import RadarConsultantItem
from apps.abpe_shaduler.services import radar_berater_index as idx
from apps.abpe_shaduler.services import radar_berater_service as rbs
from apps.abpe_shaduler.services import radar_berater_gulp as gulp
from apps.abpe_shaduler.services import radar_berater_fl as fl

NAME = os.environ.get('NAME', 'Agelis')
now = timezone.now()

def _iso(dt):
    return dt.isoformat() if dt else None

def _age_h(dt):
    if not dt:
        return None
    return round((now - dt).total_seconds() / 3600.0, 2)

print('=== 1) Sessions ===')
gs = gulp.gulp_session_info()
print('Gulp:', json.dumps({k: gs.get(k) for k in ('ok','source','path','hint','needs_auth') if k in gs or True}, ensure_ascii=False, default=str)[:800])
print('  has_gulp_session=', gulp.has_gulp_session())
try:
    print('  has_fl_session=', fl.has_fl_session())
    fi = getattr(fl, 'fl_session_info', None)
    if callable(fi):
        print('  FL info:', json.dumps(fi(), ensure_ascii=False, default=str)[:600])
except Exception as e:
    print('  FL session ERR', type(e).__name__, e)

print()
print('=== 2) Scheduler Jobs (radar_berater*) ===')
try:
    import requests
    api = getattr(settings, 'SCHEDULER_API_BASE_URL', '') or 'http://127.0.0.1:8000/scheduler/api'
    api = api.rstrip('/').replace('://localhost:', '://127.0.0.1:')
    tok = getattr(settings, 'SCHEDULER_SERVICE_TOKEN', '') or ''
    h = {'Authorization': f'Token {tok}'} if tok else {}
    r = requests.get(api + '/jobs/', headers=h, timeout=10)
    print('  jobs HTTP', r.status_code, 'api=', api)
    data = r.json() if r.ok else {}
    jobs = data if isinstance(data, list) else (data.get('results') or data.get('jobs') or [])
    keys_hit = 0
    for j in jobs:
        if not isinstance(j, dict):
            continue
        blob = json.dumps(j, ensure_ascii=False, default=str).lower()
        k = j.get('job_key') or j.get('key') or j.get('name') or ''
        cb = str(j.get('callback_url') or j.get('url') or '')
        if 'radar_berater' in blob or 'berater' in str(k).lower() or 'gulp_available' in blob or 'fl_available' in blob:
            keys_hit += 1
            print(f"  · key={k!r} status={j.get('status')} enabled={j.get('enabled')}")
            print(f"    last={j.get('last_run') or j.get('last_run_at') or j.get('last_success')} next={j.get('next_run') or j.get('next_run_at')}")
            print(f"    cb={cb[:120]}")
            err = j.get('last_error') or j.get('error') or j.get('last_message')
            if err:
                print(f"    err={str(err)[:200]}")
    if keys_hit == 0:
        print('  (keine radar_berater_* Jobs gefunden — Sync evtl. nur manuell / anderer Key)')
        # dump a few job keys for orientation
        for j in jobs[:12]:
            if isinstance(j, dict):
                print(f"  sample key={j.get('job_key') or j.get('key') or j.get('name')!r}")
except Exception as e:
    print('  Scheduler ERR', type(e).__name__, e)

print()
print('=== 3) DB Frische ===')
qs = RadarConsultantItem.objects.filter(deleted_at__isnull=True).exclude(status='geloescht')
print('  active=', qs.count())
agg = qs.aggregate(
    max_ein=Max('eingegangen_am'), min_ein=Min('eingegangen_am'),
    max_upd=Max('updated_at'),
)
print('  max eingegangen_am=', _iso(agg['max_ein']), f"({_age_h(agg['max_ein'])} h alt)")
print('  max updated_at=   ', _iso(agg['max_upd']), f"({_age_h(agg['max_upd'])} h alt)")
since_6h = now - timedelta(hours=6)
since_24h = now - timedelta(hours=24)
print('  updated last 6h=', qs.filter(updated_at__gte=since_6h).count())
print('  updated last 24h=', qs.filter(updated_at__gte=since_24h).count())
print('  eingegangen last 6h=', qs.filter(eingegangen_am__gte=since_6h).count())
print('  by quelle:')
for row in qs.values('quelle__name').annotate(n=Count('id')).order_by('-n')[:8]:
    print(f"    {row['quelle__name']!r}: {row['n']}")
print('  by match_status:')
for row in qs.values('match_status').annotate(n=Count('id')).order_by('-n')[:8]:
    print(f"    {row['match_status']!r}: {row['n']}")

print()
print('=== 4) Top 15 DB (wie Sort date_desc) ===')
for i, o in enumerate(qs.order_by('-eingegangen_am', '-updated_at')[:15], 1):
    print(
        f"  {i:02d} {_iso(o.eingegangen_am)} | upd={_iso(o.updated_at)} | "
        f"{(o.name or '')[:40]!r} | gulp={o.gulp_id or '-'} fm={o.fm_id or '-'} | "
        f"src={getattr(o.quelle,'name',None)} match={o.match_status} st={o.status}"
    )

print()
print(f'=== 5) Fokus NAME={NAME!r} ===')
focus = list(
    RadarConsultantItem.objects.filter(name__icontains=NAME)
    .order_by('-eingegangen_am')[:10]
)
if not focus:
    print('  keine Treffer')
else:
    for o in focus:
        print(f"  id={o.id}")
        print(f"    name={o.name!r} gulp_id={o.gulp_id} fm_id={o.fm_id}")
        print(f"    eingegangen_am={_iso(o.eingegangen_am)} ({_age_h(o.eingegangen_am)} h)")
        print(f"    updated_at={_iso(o.updated_at)} ({_age_h(o.updated_at)} h)")
        print(f"    status={o.status} match={o.match_status} deleted={o.deleted_at}")
        print(f"    beschreibung_len={len(o.beschreibung or '')} cv_versions={len(o.cv_versions or [])}")
        print(f"    verfuegbar_ab={o.verfuegbar_ab} satz={o.satz} ort={o.ort}")
        # Rank in current UI list?
        pass

print()
print('=== 6) UI list_berater (available_only, status=neu, date_desc) ===')
data = rbs.list_berater(
    q='', days=0, source='', status='neu', match_status='',
    sort='date_desc', limit=10, available_only=True, auto_seed=False,
)
print('  list_source=', data.get('list_source'))
print('  es_total=', data.get('es_total'))
print('  es_info=', json.dumps(data.get('es_info') or {}, ensure_ascii=False, default=str)[:1500])
print('  results=', len(data.get('results') or []))
for i, it in enumerate(data.get('results') or [], 1):
    print(
        f"  {i:02d} ein={it.get('eingegangen_am')} | {(it.get('name') or '')[:40]!r} | "
        f"gulp={it.get('gulp_id') or '-'} | src={it.get('source')} | match={it.get('match_status')}"
    )

print()
print('=== 7) ES search top 10 ===')
pack = idx.search(q='', days=None, limit=10, include_deleted=False)
if pack is None:
    print('  pack=None')
else:
    print('  error=', pack.get('error'), 'total=', pack.get('total'))
    for i, h in enumerate(pack.get('hits') or [], 1):
        src = h.get('_source') or h
        print(
            f"  {i:02d} ein={src.get('eingegangen_am')} | {(src.get('name') or '')[:40]!r} | "
            f"gulp={src.get('gulp_id') or '-'} | deleted={src.get('deleted')}"
        )

print()
print('=== 8) Diagnose-Hinweise ===')
max_ein = agg['max_ein']
age = _age_h(max_ein)
top_ui = (data.get('results') or [{}])[0] if data.get('results') else {}
top_name = (top_ui.get('name') or '')
if age is not None and age > 6:
    print(f'  ⚠ max eingegangen_am ist {age}h alt → Sync schreibt kaum/nicht')
else:
    print(f'  · max eingegangen_am Alter: {age}h')
if NAME.lower() in top_name.lower():
    print(f'  ⚠ UI-Top ist Fokus "{NAME}" → Sortierung hängt am alten Bump oder Sync liefert dieselbe Reihenfolge')
if (data.get('es_info') or {}).get('search_error') or (data.get('es_info') or {}).get('fallback'):
    print('  ⚠ ES-Fallback/Fehler → UI evtl. alte DB-Order')
if not gulp.has_gulp_session():
    print('  ⚠ Gulp-Session fehlt → sync_available_from_gulp bricht ab')
print('  Nächste Schritte:')
print('    • SYNC_PROBE=1 LIMIT=5 bash scripts/ANALYZE-radar-berater-stale.sh')
print('    • python manage.py radar_berater_gulp_available --limit 10 --pages 1')
print('    • bash scripts/TEST-radar-profile-extract.sh')
PY

if [[ "$SYNC_PROBE" == "1" ]]; then
  echo
  echo "=== SYNC_PROBE Gulp limit=$LIMIT (SCHREIBT) ==="
  "$PYBIN" manage.py radar_berater_gulp_available --limit "$LIMIT" --pages 1 --delay 0.4 \
    | tee "$OUT_DIR/sync_gulp.log" | tail -40
fi

if [[ "$SYNC_PROBE_FL" == "1" ]]; then
  echo
  echo "=== SYNC_PROBE FL limit=$LIMIT (SCHREIBT) ==="
  if "$PYBIN" manage.py help radar_berater_fl_available >/dev/null 2>&1; then
    "$PYBIN" manage.py radar_berater_fl_available --limit "$LIMIT" --pages 1 \
      | tee "$OUT_DIR/sync_fl.log" | tail -40
  else
    echo "(Command radar_berater_fl_available nicht verfügbar)"
  fi
fi

echo
echo "Log: $OUT_DIR/analyze.log"
echo "Fertig. Output hier posten."
