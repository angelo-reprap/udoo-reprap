#!/usr/bin/env bash
# TEST: Was holen wir heute aus Gulp / FreelancerMap (Liste vs Detail vs HTML)?
# Nur lesen — kein DB-Write (außer SAVE_DB=1).
#
# Auf ucs5:
#   cd /mnt/public/udoo-reprap && git fetch origin cursor/posteingang-radar-fix-1532
#   bash <(git show origin/cursor/posteingang-radar-fix-1532:scripts/TEST-radar-profile-extract.sh)
#
# Optional:
#   MONGO=5c11649b9868ee50f8a14eae bash …          # Talentfinder mongoId (24-hex) — bevorzugt
#   GULP_URL='https://www.gulp.de/talentfinder/app/experten/<mongo>' bash …
#   GULP_ID=47094 bash …                          # numerische Gulp-ID (ohne Default)
#   FM_URL='https://www.freelancermap.de/profil/…' bash …
#   FM_SLUG=… FM_ID=… bash …
#   SAVE_DB=1 bash …                              # Corpus an Radar-Eintrag anhängen (cv_versions)
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
PYBIN="${PYBIN:-/opt/abpe/venv311/bin/python}"
GULP_ID="${GULP_ID:-}"
GULP_URL="${GULP_URL:-}"
MONGO="${MONGO:-}"
FM_URL="${FM_URL:-}"
FM_SLUG="${FM_SLUG:-}"
FM_ID="${FM_ID:-}"
SAVE_DB="${SAVE_DB:-0}"
OUT_DIR="${OUT_DIR:-/tmp/radar-profile-extract-$(date +%Y%m%d-%H%M%S)}"

mkdir -p "$OUT_DIR"
cd "$BACKEND"

echo "======== TEST Radar Profile Extract ========"
echo "Start: $(date -Iseconds) OUT=$OUT_DIR"
echo "MONGO=${MONGO:-(none)} GULP_ID=${GULP_ID:-(none)} GULP_URL=${GULP_URL:-(none)} FM_URL=${FM_URL:-(none)} SAVE_DB=$SAVE_DB"
echo

export GULP_ID GULP_URL MONGO FM_URL FM_SLUG FM_ID SAVE_DB OUT_DIR

"$PYBIN" - <<'PY' | tee "$OUT_DIR/extract.log"
import os, json, re, django
from pathlib import Path
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()

from apps.abpe_shaduler.services import radar_berater_gulp as gulp
from apps.abpe_shaduler.services import radar_berater_fl as fl

OUT = Path(os.environ.get('OUT_DIR', '/tmp/radar-extract'))
OUT.mkdir(parents=True, exist_ok=True)

GULP_ID = (os.environ.get('GULP_ID') or '').strip()
GULP_URL = (os.environ.get('GULP_URL') or '').strip()
MONGO = (os.environ.get('MONGO') or '').strip()
FM_URL = (os.environ.get('FM_URL') or '').strip()
FM_SLUG = (os.environ.get('FM_SLUG') or '').strip()
FM_ID = (os.environ.get('FM_ID') or '').strip()
SAVE_DB = os.environ.get('SAVE_DB') == '1'

# mongo from URL if given
if GULP_URL:
    m = re.search(r'/experten/([a-f0-9]{24})', GULP_URL, re.I)
    if m and not MONGO:
        MONGO = m.group(1)
    gid2 = gulp.parse_gulp_id(GULP_URL)
    if gid2 and not GULP_ID:
        GULP_ID = gid2
# 24-hex als mongo behandeln, auch wenn nur in GULP_ID gesetzt
if not MONGO and re.fullmatch(r'[a-f0-9]{24}', GULP_ID or '', re.I):
    MONGO = GULP_ID
if MONGO and not GULP_ID:
    GULP_ID = MONGO  # fetch_expert akzeptiert mongo als id


def _len(x):
    if x is None:
        return 0
    if isinstance(x, (list, dict)):
        return len(x)
    return len(str(x))


def _preview(text, n=400):
    t = re.sub(r'\s+', ' ', str(text or '')).strip()
    return t[:n] + ('…' if len(t) > n else '')


def inventory(label, d: dict):
    print(f'\n--- Inventory: {label} ---')
    if not isinstance(d, dict):
        print('  (not a dict)', type(d))
        return
    keys = sorted(d.keys())
    print('  keys:', ', '.join(keys))
    for k in keys:
        v = d[k]
        if k in ('raw',):
            if isinstance(v, dict):
                print(f'  raw.keys ({len(v)}):', ', '.join(list(v.keys())[:40]))
            else:
                print(f'  raw type={type(v).__name__} len={_len(v)}')
            continue
        if isinstance(v, list):
            print(f'  {k}: list[{len(v)}] sample={v[:3]!r}'[:200])
        elif isinstance(v, dict):
            print(f'  {k}: dict[{len(v)}] keys={list(v.keys())[:12]}')
        elif isinstance(v, str):
            print(f'  {k}: str[{len(v)}] {_preview(v, 120)!r}')
        else:
            print(f'  {k}: {type(v).__name__}={v!r}'[:180])


def corpus_from_gulp_packed(p: dict) -> str:
    """Plaintext-Corpus aus bisherigem Pack + raw (so reich wie möglich)."""
    parts = []
    for k in ('name', 'ort', 'satz', 'verfuegbar_ab', 'gulp_id', 'mongo_id', 'profil_url'):
        if p.get(k) not in (None, '', []):
            parts.append(f'{k}: {p.get(k)}')
    skills = p.get('skills') or []
    if skills:
        parts.append('Top-Skills:\n' + '\n'.join(f'- {s}' for s in skills[:80]))
    if p.get('beschreibung'):
        parts.append('Beschreibung:\n' + p['beschreibung'])
    if p.get('cv_text'):
        parts.append('CV-Text:\n' + p['cv_text'])
    raw = p.get('raw') or {}
    if isinstance(raw, dict):
        # zusätzliche Felder, die normalize ggf. nicht voll nutzt
        profile = raw.get('profile') or raw.get('expertProfile') or {}
        if not isinstance(profile, dict):
            profile = {}
        for label, path in [
            ('Sprachen', ['languages', 'sprachen']),
            ('Ausbildung', ['educations', 'education', 'trainings']),
            ('Projekte(raw)', ['projects']),
            ('Kompetenzen', ['competences', 'skillsCategories']),
            ('Positionen', ['positions', 'roles']),
            ('Branchen', ['industries', 'sectors']),
            ('Werdegang', ['career', 'careerEntries', 'employments']),
        ]:
            val = None
            for key in path:
                val = profile.get(key) if key in profile else raw.get(key)
                if val:
                    break
            if not val:
                continue
            parts.append(f'{label}:\n' + json.dumps(val, ensure_ascii=False, indent=2, default=str)[:12000])
    return '\n\n'.join(parts).strip()


def corpus_from_fl_item(item: dict) -> str:
    parts = []
    for k in ('name', 'ort', 'satz', 'verfuegbar_ab', 'fm_id', 'fm_slug', 'profil_url'):
        if item.get(k) not in (None, '', []):
            parts.append(f'{k}: {item.get(k)}')
    skills = item.get('skills') or []
    if skills:
        parts.append('Skills:\n' + '\n'.join(f'- {s}' for s in skills[:80]))
    if item.get('beschreibung'):
        parts.append('Beschreibung:\n' + item['beschreibung'])
    raw = item.get('raw') or {}
    if isinstance(raw, dict) and raw:
        parts.append('RAW:\n' + json.dumps(raw, ensure_ascii=False, indent=2, default=str)[:20000])
    return '\n\n'.join(parts).strip()


print('=== Sessions ===')
print('Gulp:', json.dumps(gulp.gulp_session_info(), ensure_ascii=False, default=str)[:700])
print('has_gulp_session=', gulp.has_gulp_session())
print('has_fl_session=', fl.has_fl_session())

# ── Gulp ──────────────────────────────────────────────────────────────
if GULP_ID or MONGO:
    print('\n' + '=' * 60)
    print(f'=== GULP detail GULP_ID={GULP_ID!r} MONGO={MONGO!r} ===')
    packed = gulp.fetch_expert_by_gulp_id(GULP_ID or MONGO, mongo_id=MONGO)
    (OUT / 'gulp_packed.json').write_text(
        json.dumps({k: v for k, v in packed.items() if k != 'raw'}, ensure_ascii=False, indent=2, default=str),
        encoding='utf-8',
    )
    if isinstance(packed.get('raw'), dict):
        (OUT / 'gulp_raw_keys.json').write_text(
            json.dumps({
                'top_keys': list(packed['raw'].keys()),
                'sample': {k: packed['raw'][k] for k in list(packed['raw'])[:15]},
            }, ensure_ascii=False, indent=2, default=str)[:200000],
            encoding='utf-8',
        )
    inventory('gulp.fetch_expert_by_gulp_id', packed)
    print('\n  beschreibung_len=', _len(packed.get('beschreibung')))
    print('  cv_text_len=', _len(packed.get('cv_text')))
    print('  skills_n=', _len(packed.get('skills')))
    print('  ok=', packed.get('ok'), 'error=', packed.get('error'), 'needs_auth=', packed.get('needs_auth'))

    # API-Felder für Toggle-Volltext (projects/education/…)
    raw_full = packed.get('raw') if isinstance(packed.get('raw'), dict) else {}
    profile = raw_full.get('profile') if isinstance(raw_full.get('profile'), dict) else {}
    print('\n=== GULP API profile keys ===')
    print('  profile.keys:', sorted(profile.keys())[:80])
    for arr_name in ('projects', 'educations', 'education', 'trainings', 'languages',
                     'competenceCategories', 'competences', 'positions', 'industries'):
        arr = profile.get(arr_name)
        if arr is None:
            arr = raw_full.get(arr_name)
        if isinstance(arr, list) and arr:
            print(f'  {arr_name}: n={len(arr)} item0.keys={sorted(arr[0].keys()) if isinstance(arr[0], dict) else type(arr[0])}')
            if isinstance(arr[0], dict):
                for k, v in sorted(arr[0].items()):
                    if isinstance(v, str) and len(v) > 40:
                        print(f'    {k}: str[{len(v)}] {_preview(v, 100)!r}')
                    elif isinstance(v, list):
                        print(f'    {k}: list[{len(v)}]')
                    else:
                        print(f'    {k}: {type(v).__name__}={v!r}'[:160])
            (OUT / f'gulp_{arr_name}_sample.json').write_text(
                json.dumps(arr[:3], ensure_ascii=False, indent=2, default=str)[:120000],
                encoding='utf-8',
            )
        else:
            print(f'  {arr_name}: (fehlt oder leer)')

    # HTML fallback parse alone (was kommt ohne API?)
    print('\n=== GULP HTML-only parse ===')
    url = packed.get('profil_url') or gulp.profil_url_for_gulp_id(GULP_ID or MONGO)
    if MONGO:
        url = f'https://www.gulp.de/talentfinder/app/experten/{MONGO}'
    code, final_url, raw = gulp._request(
        url,
        headers={
            'Accept': 'text/html,application/xhtml+xml,application/json',
            'Referer': 'https://www.gulp.de/',
            'Origin': 'https://www.gulp.de',
        },
    )
    html = (raw or b'').decode('utf-8', errors='replace')
    (OUT / 'gulp_profile.html').write_text(html[:500000], encoding='utf-8')
    print(f'  HTTP {code} url={final_url or url} html_len={len(html)}')
    # markers for SPA vs embedded JSON
    for needle in (
        '__NEXT_DATA__', 'expert-profiles', 'projects', 'Ausbildung',
        'Top-Skills', 'ProfileShow', 'window.__', 'application/json',
    ):
        print(f'  contains[{needle!r}]=', needle.lower() in html.lower() or needle in html)
    parsed_html = gulp._parse_experten_html(html, prefer_gulp_id=GULP_ID)
    inventory('gulp._parse_experten_html', parsed_html or {})
    print('  html_parse_ok=', bool(parsed_html))

    # List hit comparison (first page search, find this id if present)
    print('\n=== GULP list search (page0) — Treffer-Felder ===')
    listed = gulp.fetch_experts_list(page=0, size=20, available_only=True)
    print('  list ok=', listed.get('ok'), 'n=', len(listed.get('results') or []),
          'error=', listed.get('error'), 'needs_auth=', listed.get('needs_auth'))
    hit = None
    for h in listed.get('results') or []:
        if str(h.get('gulp_id') or '') == str(GULP_ID) or str(h.get('mongo_id') or '') == str(MONGO):
            hit = h
            break
    if hit:
        inventory('list_hit_same_id', hit)
    else:
        print('  (ID nicht in erster Available-Seite — zeige Sample-Hit)')
        sample = (listed.get('results') or [None])[0]
        if sample:
            inventory('list_hit_sample', sample)

    corpus = corpus_from_gulp_packed(packed) if packed.get('ok') else ''
    (OUT / 'gulp_corpus.txt').write_text(corpus, encoding='utf-8')
    print(f'\n  CORPUS chars={len(corpus)} → {OUT / "gulp_corpus.txt"}')
    print('  preview:\n', corpus[:900])

    if SAVE_DB and packed.get('ok') and GULP_ID:
        print('\n=== SAVE_DB: append cv_version ===')
        from apps.abpe_shaduler.services import radar_berater_service as rbs
        item = {
            'gulp_id': packed.get('gulp_id') or GULP_ID,
            'mongo_id': packed.get('mongo_id') or MONGO,
            'name': packed.get('name') or '',
            'skills': packed.get('skills') or [],
            'ort': packed.get('ort') or '',
            'verfuegbar_ab': packed.get('verfuegbar_ab'),
            'satz': packed.get('satz'),
            'beschreibung': packed.get('beschreibung') or '',
            'profil_url': packed.get('profil_url') or '',
            'cv_text': corpus or packed.get('cv_text') or '',
            'source': 'gulp',
        }
        obj = rbs.upsert_berater(item, apply_crm=True)
        print(f'  upserted id={obj.id} name={obj.name!r} beschr={len(obj.beschreibung or "")} cvs={len(obj.cv_versions or [])}')

else:
    print('\n(GULP übersprungen — GULP_ID/GULP_URL leer)')

# ── FreelancerMap ─────────────────────────────────────────────────────
if FM_URL or FM_SLUG or FM_ID:
    print('\n' + '=' * 60)
    print(f'=== FL detail FM_URL={FM_URL!r} SLUG={FM_SLUG!r} ID={FM_ID!r} ===')
    text = FM_URL or FM_SLUG or FM_ID
    if hasattr(fl, 'fetch_profile_by_text'):
        res = fl.fetch_profile_by_text(text)
    else:
        # parse slug/id manually
        slug = FM_SLUG
        fmid = FM_ID
        if FM_URL and not slug:
            m = re.search(r'/profil/([^/?#]+)', FM_URL)
            if m:
                slug = m.group(1)
        res = fl.fetch_profile(slug=slug, fm_id=fmid)
    (OUT / 'fl_result.json').write_text(
        json.dumps(res, ensure_ascii=False, indent=2, default=str)[:300000],
        encoding='utf-8',
    )
    print('  ok=', res.get('ok'), 'error=', res.get('error'), 'url=', res.get('url'))
    item = res.get('item') or {}
    inventory('fl.fetch_profile item', item)

    # list sample
    print('\n=== FL list (aktuellste) ===')
    try:
        listed = fl.fetch_freelancers_list(page=1, available_only=True, most_recent=True)
        print('  list ok=', listed.get('ok'), 'n=', len(listed.get('results') or []),
              'error=', listed.get('error'))
        sample = (listed.get('results') or [None])[0]
        if sample:
            inventory('fl_list_sample', sample)
    except Exception as e:
        print('  list ERR', type(e).__name__, e)

    # HTML dump if URL known
    purl = item.get('profil_url') or FM_URL
    if purl:
        code, raw = fl._request(
            purl,
            accept='text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            timeout=45,
        )
        html = (raw or b'').decode('utf-8', errors='replace') if raw else ''
        (OUT / 'fl_profile.html').write_text(html[:500000], encoding='utf-8')
        print(f'\n  HTML HTTP {code} len={len(html)} → {OUT / "fl_profile.html"}')
        for needle in ('ProfileShow', 'project', 'Ausbildung', 'skills', '__NEXT_DATA__'):
            print(f'  contains[{needle!r}]=', needle.lower() in html.lower() or needle in html)

    corpus = corpus_from_fl_item(item) if item else ''
    (OUT / 'fl_corpus.txt').write_text(corpus, encoding='utf-8')
    print(f'\n  CORPUS chars={len(corpus)} → {OUT / "fl_corpus.txt"}')
    print('  preview:\n', corpus[:900])

    if SAVE_DB and res.get('ok') and item:
        print('\n=== SAVE_DB FL upsert ===')
        from apps.abpe_shaduler.services import radar_berater_service as rbs
        item2 = dict(item)
        item2['cv_text'] = corpus
        item2['source'] = 'freelancermap'
        obj = rbs.upsert_berater(item2, apply_crm=True)
        print(f'  upserted id={obj.id} name={obj.name!r} cvs={len(obj.cv_versions or [])}')
else:
    print('\n(FL übersprungen — setze FM_URL oder FM_SLUG/FM_ID)')
    print('  Tipp: aus Radar einen „neu/unbekannt“ FL-Link kopieren')

print('\n=== Gap vs Wunsch-Volltext (Gulp Beispielseite) ===')
print('  Erwartete Blöcke: Projekte, Ausbildung, Sprachen, Positionen, Kompetenzen,')
print('  Branchen, Werdegang, Remote, Antwortrate, Profiletext …')
print('  → siehe gulp_corpus.txt / gulp_raw_keys.json: was fehlt, muss API/HTML erweitern.')
print(f'\nArtefakte: {OUT}')
PY

echo
echo "Fertig. Log: $OUT_DIR/extract.log"
echo "Corpus: $OUT_DIR/gulp_corpus.txt  (und ggf. fl_corpus.txt)"
