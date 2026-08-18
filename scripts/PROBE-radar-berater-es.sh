#!/usr/bin/env bash
# Live: Radar-Berater ES diagnose + optional Reindex.
# Default = CHECK only (kein Write). APPLY=1 → ensure_index + reindex_all.
# Kein Datei-Overwrite; Archiv nur wenn APPLY Code ändert (hier nicht).
#
#   bash <(git show origin/cursor/posteingang-radar-fix-1532:scripts/PROBE-radar-berater-es.sh)
#   APPLY=1 bash <(git show origin/cursor/posteingang-radar-fix-1532:scripts/PROBE-radar-berater-es.sh)
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
PYBIN="${PYBIN:-/opt/abpe/venv311/bin/python}"
APPLY="${APPLY:-0}"
RECREATE="${RECREATE:-1}"

cd "$BACKEND"
echo "======== PROBE radar berater ES APPLY=$APPLY RECREATE=$RECREATE ========"

"$PYBIN" - <<PY
import os, json, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()

from apps.abpe_shaduler.models import RadarConsultantItem
from apps.abpe_shaduler.services import radar_berater_index as idx
from apps.abpe_shaduler.services import radar_berater_service as rbs

print('=== DB ===')
qs = RadarConsultantItem.objects.filter(deleted_at__isnull=True).exclude(status='geloescht')
print('  active=', qs.count())
from django.db.models import Count
for row in qs.values('quelle__name').annotate(n=Count('id')).order_by('-n')[:10]:
    print(f"  quelle={row['quelle__name']!r} n={row['n']}")

print()
print('=== ES index_stats ===')
st = idx.index_stats(sample=True)
print(json.dumps(st, ensure_ascii=False, indent=2, default=str)[:4000])

print()
print('=== ES search (q="", days=None, limit=5) ===')
pack = idx.search(q='', days=None, limit=5, include_deleted=False)
if pack is None:
    print('  pack=None (client fail)')
else:
    print('  error=', pack.get('error'))
    print('  index_missing=', pack.get('index_missing'))
    print('  total=', pack.get('total'))
    print('  hits=', len(pack.get('hits') or []))
    print('  by_source=', pack.get('by_source'))

print()
print('=== list_berater (wie UI) ===')
try:
    data = rbs.list_berater(q='', days=0, source='', status='all', match_status='', sort='date_desc', limit=5)
except TypeError:
    # Signatur kann abweichen — Fallback
    data = rbs.list_berater()
if isinstance(data, dict):
    print('  list_source=', data.get('list_source'))
    print('  es_total=', data.get('es_total'))
    print('  es_info=', json.dumps(data.get('es_info') or {}, ensure_ascii=False, default=str)[:800])
    print('  results=', len(data.get('results') or data.get('items') or []))
else:
    print('  unexpected', type(data), str(data)[:200])
PY

if [[ "$APPLY" != "1" ]]; then
  echo
  echo "DRY-RUN. Wenn Index fehlt / search_error / count=0 bei DB>0:"
  echo "  APPLY=1 bash <(git show origin/cursor/posteingang-radar-fix-1532:scripts/PROBE-radar-berater-es.sh)"
  echo "  # optional ohne Temp-Swap: RECREATE=0 APPLY=1 …"
  exit 0
fi

echo
echo "=== APPLY: ensure_index + reindex_all(recreate=$RECREATE) ==="
"$PYBIN" - <<PY
import os, json, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
from apps.abpe_shaduler.services import radar_berater_index as idx

print('ensure_index=', idx.ensure_index())
rec = os.environ.get('RECREATE', '1') == '1'
print('reindex_all recreate=', rec, '…')
out = idx.reindex_all(limit=50000, active_only=True, recreate=rec)
print(json.dumps(out, ensure_ascii=False, indent=2, default=str)[:6000])

print()
print('=== nachher search ===')
pack = idx.search(q='', days=None, limit=3)
print('error=', (pack or {}).get('error'), 'total=', (pack or {}).get('total'), 'hits=', len((pack or {}).get('hits') or []))
st = idx.index_stats(sample=False)
print('stats count=', st.get('count'), 'exists=', st.get('exists'), 'ok=', st.get('ok'))
PY

echo
echo "Browser: Ctrl+F5 auf Radar · Berater — erwartet Liste ES (ohne ES-Fehler)"
