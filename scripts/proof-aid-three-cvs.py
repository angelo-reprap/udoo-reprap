#!/usr/bin/env python3
"""Golden-Set: Troschke + Pfirrmann + Vogelgesang (Spans → AID-Regex 1b)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INCOMING = ROOT / 'Repo_abpe' / 'cv_extractor' / 'incoming'
SAMPLES = ROOT / 'Repo_abpe' / 'cv_extractor' / 'samples'
OUT = Path('/opt/cursor/artifacts/aid-three-cvs-proof.json')

CVS = [
    {
        'id': 'troschke_thomas',
        'letter': 'ttt',
        'pdf': SAMPLES / 'AID-tt_1.2.4.2.pdf',
        'first': 'Thomas',
        'last': 'Troschke',
        'expect': {
            'is_aid': True,
            'min_projects': 17,
            'min_skills': 30,
            'min_focus': 10,
            'birth_year': 1965,
        },
    },
    {
        'id': 'pfirrmann_peter',
        'letter': 'ppp',
        'pdf': SAMPLES / 'AID-bpf_1.6.4.7.pdf',
        'first': 'Peter',
        'last': 'Pfirrmann',
        'expect': {
            'is_aid': True,
            'min_projects': 1,
            'min_skills': 5,
            'min_focus': 0,
            'birth_year': None,  # optional
        },
    },
    {
        'id': 'vogelgesang_oliver',
        'letter': 'vvv',
        'pdf': SAMPLES / 'AID-ov_3.4.5.1.pdf',
        'first': 'Oliver',
        'last': 'Vogelgesang',
        'expect': {
            'is_aid': True,
            'min_projects': 1,
            'min_skills': 5,
            'min_focus': 0,
            'birth_year': None,
        },
    },
]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def analyze(ctrl, aid, pdf_mod, cv: dict) -> dict:
    r = pdf_mod.PDFExtractor().extract(str(cv['pdf']))
    spans = ctrl._normalize_spans(r.spans)
    lines = ctrl._spans_to_aid_lines(spans)
    full = '\n'.join(lines)
    clean = aid._strip_page_headers(full)
    personal = aid._extract_personal(clean, cv['first'], cv['last'])
    skills = aid._extract_skill_tables(clean)
    focus = aid._extract_focus_experience(clean)
    projects = aid._extract_projekte(clean)
    headline = aid._extract_headline(clean)
    fach = aid._extract_fachbereiche(clean)
    branchen = aid._extract_branchen(clean)
    certs = aid._extract_zertifikate(clean)
    edu = list(aid._extract_ausbildung(clean) or []) + list(aid._extract_schulungen(clean) or [])
    opswat_skill = any('opswat' in (s.get('name') or '').lower() for s in skills)

    exp = cv['expect']
    checks = {
        'pdf_exists': cv['pdf'].is_file(),
        'spans': len(spans) > 50,
        'is_aid': aid.is_aid_profile(full) == exp['is_aid'],
        'projects': len(projects) >= exp['min_projects'],
        'skills': len(skills) >= exp['min_skills'],
        'focus': len(focus) >= exp['min_focus'],
        'opswat_not_skill': not opswat_skill,
    }
    if exp.get('birth_year') is not None:
        checks['birth_year'] = personal.get('birth_year') == exp['birth_year']

    return {
        'id': cv['id'],
        'letter': cv['letter'],
        'pdf': cv['pdf'].name,
        'spans': len(spans),
        'lines': len(lines),
        'chars': len(clean),
        'is_aid': aid.is_aid_profile(full),
        'personal': personal,
        'headline': (headline or '')[:120],
        'counts': {
            'projects': len(projects),
            'skills': len(skills),
            'focus_experience': len(focus),
            'fachbereiche': len(fach),
            'branchen': len(branchen),
            'certs': len(certs),
            'education': len(edu),
        },
        'project_periods': [p.get('period') for p in projects[:8]],
        'focus_sample': [f.get('name') for f in focus[:6]],
        'skill_cats': sorted({s.get('category') for s in skills if s.get('category')})[:12],
        'checks': checks,
        'ok': all(checks.values()),
        'fail': [k for k, v in checks.items() if not v],
    }


def main() -> int:
    ctrl = load('ctrl', INCOMING / 'services' / 'main_pipeline_controller.py')
    aidm = load('aid', INCOMING / 'extractors' / 'aid_regex_extractor.py')
    pdf_mod = load('pdf', INCOMING / 'services' / 'main_pdf_extractor.py')
    aid = aidm.aid_regex_extractor

    rows = []
    for cv in CVS:
        if not cv['pdf'].is_file():
            rows.append({'id': cv['id'], 'ok': False, 'fail': ['pdf_missing'], 'pdf': str(cv['pdf'])})
            continue
        rows.append(analyze(ctrl, aid, pdf_mod, cv))

    report = {
        'ok': [r['id'] for r in rows if r.get('ok')],
        'fail': {r['id']: r.get('fail') for r in rows if not r.get('ok')},
        'rows': rows,
        'ucs5_mkdir': [
            f"mkdir -p /mnt/public/Berater/AID_profile/{r['letter']}/{r['id']}/neu/cv"
            for r in CVS
        ],
        'ucs5_import': [
            f"python3 manage.py import_aid_profiles --letter {r['letter']} --dir {r['id']} --sync --no-skip-existing"
            for r in CVS
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f'\n→ {OUT}')
    return 0 if all(r.get('ok') for r in rows) else 1


if __name__ == '__main__':
    raise SystemExit(main())
