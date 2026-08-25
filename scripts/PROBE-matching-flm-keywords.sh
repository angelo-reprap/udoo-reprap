#!/usr/bin/env bash
# Probe: Freelancermap Keyword-Suche für eine Matching-Anfrage.
# Schreibt NICHTS in Shortlist/Radar — nur Console-Report.
#
# ucs5:
#   cd /mnt/public/udoo-reprap
#   MATCH_PROJECT=ANF-2026-0002 bash scripts/PROBE-matching-flm-keywords.sh
#   KEYWORDS="Python Django" bash scripts/PROBE-matching-flm-keywords.sh
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
REF="${MATCH_PROJECT:-${PROJECT_ID:-ANF-2026-0002}}"
KEYWORDS="${KEYWORDS:-}"
PAGES="${PAGES:-2}"
AVAILABLE="${AVAILABLE:-1}"

cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"

export MATCH_PROJECT="$REF"
export MATCH_KEYWORDS="$KEYWORDS"
export MATCH_PAGES="$PAGES"
export MATCH_AVAILABLE="$AVAILABLE"

python3 <<'PY'
import os, json
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
import django
django.setup()

from apps.abpe_shaduler.services import radar_berater_fl as fl
from apps.abpe_matching_workflow.models import ProjectRequest

ref = (os.environ.get('MATCH_PROJECT') or '').strip()
kw_env = (os.environ.get('MATCH_KEYWORDS') or '').strip()
pages = max(1, min(5, int(os.environ.get('MATCH_PAGES') or 2)))
available_only = (os.environ.get('MATCH_AVAILABLE') or '1') == '1'

p = None
skills = []
if ref:
    p = (
        ProjectRequest.objects.filter(project_number=ref).first()
        or ProjectRequest.objects.filter(id=ref).first()
        or ProjectRequest.objects.filter(title__icontains=ref).first()
    )
    if p:
        for s in (p.required_skills or []):
            if isinstance(s, dict) and s.get('name'):
                skills.append(str(s['name']).strip())
            elif isinstance(s, str) and s.strip():
                skills.append(s.strip())
        for t in (p.extracted_technologies or []):
            t = str(t).strip()
            if t and t not in skills:
                skills.append(t)

term = kw_env or ' '.join(skills[:6]) or 'Python Django'

sess = fl.fl_session_info()
print('=' * 64)
if p:
    print(f'Projekt: {getattr(p, "project_number", p.id)}  {p.title}')
    print(f'Skills: {skills}')
else:
    print(f'Projekt: (nicht geladen, ref={ref!r})')
print(
    f'FLM-Session: {"OK" if sess.get("ok") else "NEIN (öffentliche Suche oft trotzdem ok)"}  '
    f'source={sess.get("source")}'
)
print(f'query: {term!r}  pages={pages} available_only={available_only}')
print('=' * 64)

skill_lc = [s.lower() for s in skills]


def _search(page):
    try:
        return fl.fetch_freelancers_list(
            page=page, available_only=available_only, query=term,
        )
    except TypeError:
        # Live ohne query-Kwarg → _search_ajax + normalize
        raw = fl._search_ajax(query=term, page=page, available_only=available_only)
        if not raw.get('ok'):
            return {
                'ok': False,
                'error': raw.get('error') or f'HTTP {raw.get("http")}',
                'results': [],
                'http': raw.get('http'),
            }
        out = []
        for hit in raw.get('freelancers') or []:
            if not isinstance(hit, dict):
                continue
            n = fl.normalize_freelancer(hit)
            if n.get('fm_id'):
                out.append(n)
        return {
            'ok': True,
            'results': out,
            'raw_count': len(raw.get('freelancers') or []),
            'http': raw.get('http'),
            'total': None,
            'rates_with_value': sum(1 for r in out if r.get('satz') is not None),
        }


all_hits = []
seen = set()
for page in range(1, pages + 1):
    res = _search(page)
    if not res.get('ok'):
        print('FAIL page', page, res.get('error') or res)
        break
    print(
        f'page {page}: raw={res.get("raw_count")} total={res.get("total")} '
        f'http={res.get("http")} rates={res.get("rates_with_value")}'
    )
    if res.get('hint'):
        print('  hint:', res['hint'])
    for h in res.get('results') or []:
        key = h.get('fm_id') or h.get('fm_slug') or h.get('name')
        if key in seen:
            continue
        seen.add(key)
        hs = [str(x).lower() for x in (h.get('skills') or [])]
        overlap = [s for s in skill_lc if any(s in x or x in s for x in hs)]
        blob = ' '.join([
            str(h.get('name') or ''),
            str(h.get('beschreibung') or h.get('description') or '')[:500],
            ' '.join(str(x) for x in (h.get('skills') or [])[:40]),
            str(h.get('fm_slug') or ''),
        ]).lower()
        soft = [s for s in skill_lc if s in blob]
        score = len(set(overlap) | set(soft))
        all_hits.append((score, h, sorted(set(overlap) | set(soft))))

all_hits.sort(key=lambda x: (-x[0], (x[1].get('name') or '')))
print(f'\nUnique hits: {len(all_hits)}  (sortiert nach Skill-Overlap vs. Anfrage)\n')
for i, (score, h, ov) in enumerate(all_hits[:20], 1):
    name = h.get('name') or '?'
    fid = h.get('fm_id') or ''
    skills_s = ', '.join(str(s) for s in (h.get('skills') or [])[:8])
    avail = h.get('verfuegbar_ab') or h.get('availability') or ''
    rate = h.get('satz')
    rate_s = f'{rate} €/h' if rate is not None else '-'
    print(f'#{i:02d}  overlap={score}/{len(skill_lc) or "?"}  {name}  fm_id={fid}  satz={rate_s}')
    print(f'     matched: {ov or "-"}')
    print(f'     skills: {skills_s or "-"}')
    if avail:
        print(f'     verfügbar: {avail}')
    url = h.get('profil_url') or fl.profil_url_for(slug=h.get('fm_slug') or '', fm_id=fid)
    if url:
        print(f'     {url}')

out = Path(os.environ.get('OUT') or '/tmp/matching-flm-keywords-probe.json')
payload = {
    'project': getattr(p, 'project_number', None) if p else ref,
    'title': getattr(p, 'title', None) if p else None,
    'skills': skills,
    'query': term,
    'fl_session': bool(sess.get('ok')),
    'count': len(all_hits),
    'results': [
        {
            'overlap': sc,
            'overlap_skills': ov,
            'name': h.get('name'),
            'fm_id': h.get('fm_id'),
            'fm_slug': h.get('fm_slug'),
            'satz': h.get('satz'),
            'skills': (h.get('skills') or [])[:20],
            'profil_url': h.get('profil_url') or fl.profil_url_for(
                slug=h.get('fm_slug') or '', fm_id=h.get('fm_id') or '',
            ),
        }
        for sc, h, ov in all_hits[:40]
    ],
}
out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'\nJSON → {out}')
PY
