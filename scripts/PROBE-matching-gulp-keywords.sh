#!/usr/bin/env bash
# Probe: Gulp Talentfinder Keyword-Suche für eine Matching-Anfrage.
# Schreibt NICHTS in Shortlist/Radar — nur Console-Report.
#
# ucs5:
#   cd /mnt/public/udoo-reprap
#   MATCH_PROJECT=ANF-2026-0002 bash scripts/PROBE-matching-gulp-keywords.sh
#   KEYWORDS="Python Django" bash scripts/PROBE-matching-gulp-keywords.sh
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
REPO="${REPO:-/mnt/public/udoo-reprap}"
REF="${MATCH_PROJECT:-${PROJECT_ID:-ANF-2026-0002}}"
KEYWORDS="${KEYWORDS:-}"
PAGES="${PAGES:-2}"
SIZE="${SIZE:-20}"
AVAILABLE="${AVAILABLE:-1}"

cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"

export MATCH_PROJECT="$REF"
export MATCH_KEYWORDS="$KEYWORDS"
export MATCH_PAGES="$PAGES"
export MATCH_SIZE="$SIZE"
export MATCH_AVAILABLE="$AVAILABLE"
export LIVE_GULP_SRC="$REPO/Repo_abpe/abpe_shaduler/incoming/services/radar_berater_gulp.py"

python3 <<'PY'
import os, json, sys
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
import django
django.setup()

# Bevorzugt Repo-Stand (search_term), sonst Live-Modul
repo_gulp = Path(os.environ.get('LIVE_GULP_SRC') or '')
if repo_gulp.is_file():
    import importlib.util
    spec = importlib.util.spec_from_file_location('radar_berater_gulp_probe', repo_gulp)
    gulp = importlib.util.module_from_spec(spec)
    # Package-Deps: Modul erwartet apps… — lieber Live-Import + Monkeypatch searchTerm
    try:
        from apps.abpe_shaduler.services import radar_berater_gulp as gulp
    except Exception as e:
        print('FAIL import gulp:', e)
        raise SystemExit(1)
else:
    from apps.abpe_shaduler.services import radar_berater_gulp as gulp

from apps.abpe_matching_workflow.models import ProjectRequest

ref = (os.environ.get('MATCH_PROJECT') or '').strip()
kw_env = (os.environ.get('MATCH_KEYWORDS') or '').strip()
pages = max(1, min(5, int(os.environ.get('MATCH_PAGES') or 2)))
size = max(5, min(50, int(os.environ.get('MATCH_SIZE') or 20)))
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

term = kw_env or ' '.join(skills[:6])
if not term:
    term = 'Python Django'
    print('WARN: keine Skills/Keywords — Fallback:', term)

info = gulp.gulp_session_info()
print('=' * 64)
if p:
    print(f'Projekt: {getattr(p, "project_number", p.id)}  {p.title}')
    print(f'Skills: {skills}')
else:
    print(f'Projekt: (nicht geladen, ref={ref!r})')
print(f'Gulp-Session: {"OK" if info.get("ok") else "NEIN"}  source={info.get("source")}')
if not info.get('ok'):
    print(info.get('hint') or info)
    raise SystemExit(2)
print(f'searchTerm: {term!r}  pages={pages} size={size} available_only={available_only}')
print('=' * 64)

# Live-Modul hat ggf. noch kein search_term-Kwarg → Wrapper
def _search(page):
    try:
        return gulp.fetch_experts_list(
            page=page, size=size, available_only=available_only, search_term=term,
        )
    except TypeError:
        # Fallback: Body manuell wie fetch_experts_list, mit searchTerm
        import json as _json
        import urllib.parse
        from datetime import date
        if not gulp.has_gulp_session():
            return {'ok': False, 'error': 'Gulp-Session fehlt', 'results': []}
        qs = urllib.parse.urlencode({'pageIndex': page, 'pageSize': size})
        url = f'{gulp.TF_PROFILE_API}/search?{qs}'
        body = {
            'mId': None,
            'sortOrder': 'UPDATED_DATE',
            'availabilityPercent': 20,
            'remote': False,
            'searchOnlyInRecentProjects': False,
            'searchTerm': term,
        }
        if available_only:
            body['availabilityDate'] = date.today().isoformat()
        code, _u, raw = gulp._request(
            url, method='POST', data=_json.dumps(body).encode('utf-8'),
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Origin': 'https://www.gulp.de',
                'Referer': gulp.TF_EXPERTEN,
            },
        )
        if code != 200 or not raw:
            return {'ok': False, 'error': f'HTTP {code}', 'results': [], 'http': code}
        data = _json.loads(raw.decode('utf-8', errors='replace'))
        items = gulp._extract_hit_list(data)
        out = []
        for hit in items:
            n = gulp.normalize_expert_profile(hit if isinstance(hit, dict) else {})
            if n.get('gulp_id') or n.get('mongo_id'):
                out.append(n)
        return {'ok': True, 'results': out, 'raw_count': len(items), 'http': code}

skill_lc = [s.lower() for s in skills]
all_hits = []
seen = set()
for page in range(pages):
    res = _search(page)
    if not res.get('ok'):
        print('FAIL page', page, res.get('error') or res)
        if res.get('needs_auth'):
            raise SystemExit(3)
        break
    print(f'page {page}: raw={res.get("raw_count")} total={res.get("total")} http={res.get("http")}')
    for h in res.get('results') or []:
        key = h.get('gulp_id') or h.get('mongo_id') or h.get('name')
        if key in seen:
            continue
        seen.add(key)
        hs = [str(x).lower() for x in (h.get('skills') or [])]
        overlap = [s for s in skill_lc if any(s in x or x in s for x in hs)]
        # auch Name/Beschreibung grob
        blob = ' '.join([
            str(h.get('name') or ''),
            str(h.get('beschreibung') or h.get('description') or '')[:500],
            ' '.join(str(x) for x in (h.get('skills') or [])[:40]),
        ]).lower()
        soft = [s for s in skill_lc if s in blob]
        score = len(set(overlap) | set(soft))
        all_hits.append((score, h, sorted(set(overlap) | set(soft))))

all_hits.sort(key=lambda x: (-x[0], (x[1].get('name') or '')))
print(f'\nUnique hits: {len(all_hits)}  (sortiert nach Skill-Overlap vs. Anfrage)\n')
for i, (score, h, ov) in enumerate(all_hits[:20], 1):
    name = h.get('name') or '?'
    gid = h.get('gulp_id') or ''
    skills_s = ', '.join(str(s) for s in (h.get('skills') or [])[:8])
    avail = h.get('verfuegbar_ab') or h.get('availability') or ''
    print(f'#{i:02d}  overlap={score}/{len(skill_lc) or "?"}  {name}  gulp_id={gid}')
    print(f'     matched: {ov or "-"}')
    print(f'     skills: {skills_s or "-"}')
    if avail:
        print(f'     verfügbar: {avail}')
    url = h.get('profil_url') or h.get('url') or ''
    if url:
        print(f'     {url}')

out = Path(os.environ.get('OUT') or '/tmp/matching-gulp-keywords-probe.json')
payload = {
    'project': getattr(p, 'project_number', None) if p else ref,
    'title': getattr(p, 'title', None) if p else None,
    'skills': skills,
    'search_term': term,
    'count': len(all_hits),
    'results': [
        {
            'overlap': sc,
            'overlap_skills': ov,
            'name': h.get('name'),
            'gulp_id': h.get('gulp_id'),
            'mongo_id': h.get('mongo_id'),
            'skills': (h.get('skills') or [])[:20],
            'profil_url': h.get('profil_url') or h.get('url'),
        }
        for sc, h, ov in all_hits[:40]
    ],
}
out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'\nJSON → {out}')
PY
