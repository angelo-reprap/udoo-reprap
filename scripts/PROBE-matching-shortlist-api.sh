#!/usr/bin/env bash
# Diagnose Shortlist-API 500 für eine Anfrage.
#   MATCH_PROJECT=ANF-2026-0002 bash scripts/PROBE-matching-shortlist-api.sh
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
import os, traceback, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
import django
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from apps.abpe_matching_workflow.models import ProjectRequest, MatchResult
from apps.abpe_matching_workflow import views as mw_views

ref = os.environ.get('MATCH_PROJECT', '').strip()
p = (
    ProjectRequest.objects.filter(project_number=ref).first()
    or ProjectRequest.objects.filter(id=ref).first()
)
if not p:
    raise SystemExit(f'Projekt nicht gefunden: {ref}')

print('project', p.project_number, p.id)
print('MatchResults', MatchResult.objects.filter(project_request=p).count())
print('has _matching_shortlist_limit', hasattr(mw_views, '_matching_shortlist_limit'))

User = get_user_model()
user = User.objects.filter(is_superuser=True).first() or User.objects.first()
rf = RequestFactory()
req = rf.get(f'/matching/api/requests/{p.id}/shortlist/')
req.user = user
try:
    resp = mw_views.api_shortlist(req, str(p.id))
    print('status', getattr(resp, 'status_code', '?'))
    data = getattr(resp, 'data', None)
    if data is None and hasattr(resp, 'content'):
        print('content', resp.content[:500])
    else:
        print('success', data.get('success') if isinstance(data, dict) else type(data))
        if isinstance(data, dict):
            print('count', data.get('count'), 'error', data.get('error'))
            print('keys', sorted(data.keys()))
except Exception:
    traceback.print_exc()
    raise SystemExit(2)
PY
