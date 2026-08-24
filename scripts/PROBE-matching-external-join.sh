#!/usr/bin/env bash
# Diagnose: wie viele Gulp/FLM-Hits treffen auf CRM gulp_id_c / freelancermap_profil_c?
#
#   MATCH_PROJECT=ANF-2026-0002 bash scripts/PROBE-matching-external-join.sh
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
from apps.abpe_matching_workflow.services import matching_external_recall as mer
from apps.abpe_matching_workflow.services import matching_source_join as msj
from apps.abpe_crm.models import CrmContactCstm

ref = os.environ.get('MATCH_PROJECT', '').strip()
p = (
    ProjectRequest.objects.filter(project_number=ref).first()
    or ProjectRequest.objects.filter(id=ref).first()
)
if not p:
    raise SystemExit(f'Projekt nicht gefunden: {ref}')

skills = mer._skill_names(p)
print('=' * 64)
print(p.project_number, p.title)
print('skills:', skills)
print('CRM gulp_id_c belegt:', CrmContactCstm.objects.exclude(gulp_id_c__isnull=True).exclude(gulp_id_c='').count())
print('CRM freelancermap_profil_c belegt:', CrmContactCstm.objects.exclude(freelancermap_profil_c__isnull=True).exclude(freelancermap_profil_c='').count())
print('=' * 64)

gulp = mer.fetch_gulp_hits(skills, pages=2)
flm = mer.fetch_flm_hits(skills, pages=2)
print(f'gulp_raw={len(gulp)} flm_raw={len(flm)}')

def _scan(source, hits):
    known = crm_only = unknown = placeholders = 0
    samples = []
    for h in hits:
        join = msj.resolve_gulp_hit(h) if source == 'gulp' else msj.resolve_flm_hit(h)
        jd = join.as_dict()
        raw_name = str(h.get('name') or '')
        if msj.is_placeholder_name(raw_name):
            placeholders += 1
        if join.known and join.consultant is not None and jd.get('can_contact'):
            known += 1
            tag = 'KNOWN+CV'
        elif join.known:
            crm_only += 1
            tag = 'CRM'
        else:
            unknown += 1
            tag = 'UNK'
        if len(samples) < 8 and (tag != 'UNK' or len(samples) < 3):
            samples.append(
                f"  [{tag}] {mer._hit_display_name(h, jd.get('display_name') or '')} "
                f"via={jd.get('join_via') or '-'} "
                f"email={jd.get('email') or '-'} "
                f"id={h.get('gulp_id') or h.get('fm_id')}"
            )
    print(f'\n{source}: known+cv={known} crm_only={crm_only} unknown={unknown} placeholder_names={placeholders}')
    for s in samples:
        print(s)

_scan('gulp', gulp)
_scan('flm', flm)
PY
