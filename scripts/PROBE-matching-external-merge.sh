#!/usr/bin/env bash
# Diagnose: Gulp/FLM External-Recall für eine Anfrage (ohne Shortlist-Write der Matches).
# Speichert Backoffice-Meta am Projekt (wie MatchingEngine).
#
#   MATCH_PROJECT=ANF-2026-0002 bash scripts/PROBE-matching-external-merge.sh
#
set -euo pipefail
BACKEND="${BACKEND:-/opt/abpe/backend}"
REF="${MATCH_PROJECT:-ANF-2026-0002}"
cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"
export MATCH_PROJECT="$REF"

python3 <<'PY'
import os, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
import django
django.setup()

from apps.abpe_matching_workflow.models import ProjectRequest
from apps.abpe_matching_workflow.services.matching_external_recall import (
    classify_external_hits, store_backoffice_on_project,
)

ref = os.environ.get('MATCH_PROJECT', '').strip()
p = (
    ProjectRequest.objects.filter(project_number=ref).first()
    or ProjectRequest.objects.filter(id=ref).first()
)
if not p:
    raise SystemExit(f'Projekt nicht gefunden: {ref}')

print('=' * 64)
print(p.project_number, p.title)
print('=' * 64)
meta = classify_external_hits(p, existing_consultant_ids=set(), min_overlap=1)
store_backoffice_on_project(p, meta.get('backoffice') or [], meta.get('stats') or {})
stats = meta.get('stats') or {}
print('stats:', json.dumps(stats, ensure_ascii=False, indent=2))
print(f"known={len(meta.get('known_results') or [])}  backoffice={len(meta.get('backoffice') or [])}")
print('\nKnown (max 10):')
for kr in (meta.get('known_results') or [])[:10]:
    c = kr.get('consultant_cv')
    name = getattr(c, 'full_name', None) or kr.get('crm_link', {}).get('display_name')
    print(
        f"  [{kr.get('match_source')}] {name}  "
        f"aid={getattr(c,'aid', '')}  "
        f"status={kr.get('crm_link_status')}  "
        f"email={kr.get('email') or '-'}  "
        f"already_db={kr.get('already_in_db')}"
    )
print('\nBackoffice (max 10):')
for b in (meta.get('backoffice') or [])[:10]:
    eh = b.get('external_hit') or {}
    sk = ', '.join((eh.get('skills') or [])[:3])
    print(
        f"  [{b.get('match_source')}] {b.get('display_name') or eh.get('name')}  "
        f"reason={b.get('reason')}  ov={b.get('external_overlap')}  "
        f"email={b.get('email') or '-'}  "
        f"gulp={eh.get('gulp_id') or '-'} fm={eh.get('fm_id') or '-'}  "
        f"skills={sk or '-'}"
    )
# verify persisted
p.refresh_from_db()
er = p.extracted_requirements if isinstance(p.extracted_requirements, dict) else {}
print('\nPersisted backoffice_count:', len(er.get('_matching_backoffice') or []))
print('Persisted stats:', er.get('_matching_external_stats'))
PY
