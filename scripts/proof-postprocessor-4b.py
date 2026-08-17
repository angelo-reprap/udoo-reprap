#!/usr/bin/env python3
"""4b Post-Processor: darf Seed-Inhalt nicht löschen (Fusion/Analyse mergen)."""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INCOMING = ROOT / 'Repo_abpe' / 'cv_extractor' / 'incoming'
SAMPLES = ROOT / 'Repo_abpe' / 'cv_extractor' / 'samples'
OUT = Path('/opt/cursor/artifacts/postprocessor-4b-proof.json')


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ctrl = load('ctrl', INCOMING / 'services' / 'main_pipeline_controller.py')
    aidm = load('aid', INCOMING / 'extractors' / 'aid_regex_extractor.py')
    pp_mod = load('pp', INCOMING / 'services' / 'main_post_processor.py')
    pdf_mod = load('pdf', INCOMING / 'services' / 'main_pdf_extractor.py')
    aid = aidm.aid_regex_extractor
    pp = pp_mod.MainPostProcessor()
    src = (INCOMING / 'services' / 'main_post_processor.py').read_text(encoding='utf-8')

    ok, fail = [], []

    (ok if '_title_looks_like_role' in src else fail).append('has title_looks_like_role')
    (ok if '_INCOMPLETE_END_RE' in src or 'INCOMPLETE_END' in src else fail).append(
        'has soft-wrap act merge'
    )
    (ok if '_as_text_parts' in src else fail).append('has dict-safe tokenization')
    (ok if "'category': 'Sonstige Skills'" in src or '"category": "Sonstige Skills"' in src else fail).append(
        'AUTO_SKILLS writes dicts'
    )

    # Synthetic: short fragment must merge, not drop
    pre = {
        'metadata': {},
        'extracted_data': {
            'personal': {},
            'experience': [{
                'period': '01/2000 – 12/2000',
                'company': 'Test',
                'role': 'Entwickler',
                'title': '',
                'activities': [
                    'Anbindung von Fremddaten aufgrund einer',
                    'Fusion',
                    'Analyse',
                    'Programmierung',
                ],
                'technologies': ['Natural', 'und', 'Cobol'],
            }],
            'skill_ablage': [{'name': 'Cobol', 'category': 'Programmiersprachen'}],
            'focus_experience': [{'name': 'ADABAS'}],
            'skills': {},
        },
        'audit': {},
    }
    out = pp.clean(copy.deepcopy(pre), pdf_path='')
    acts = out['extracted_data']['experience'][0]['activities']
    blob = ' '.join(acts)
    techs = out['extracted_data']['experience'][0]['technologies']
    (ok if 'Fusion' in blob and 'Analyse' in blob else fail).append(
        f'synthetic merge acts={acts}'
    )
    (ok if any('aufgrund einer Fusion' in a for a in acts) else fail).append(
        f'synthetic softwrap fusion={acts}'
    )
    (ok if any(a.strip() == 'Analyse' or a.startswith('Analyse') for a in acts) else fail).append(
        f'synthetic keeps Analyse keyword acts={acts}'
    )
    (ok if 'und' not in [t.lower() for t in techs] else fail).append(f'tech stopword={techs}')

    # Long Projektbeschreibung must NOT become role
    pre2 = copy.deepcopy(pre)
    pre2['extracted_data']['experience'][0]['role'] = ''
    pre2['extracted_data']['experience'][0]['title'] = (
        'Support, Administration und Erweiterung von Informations- und Wertpapier-Handelssystemen:'
    )
    out2 = pp.clean(pre2, pdf_path='')
    role2 = out2['extracted_data']['experience'][0].get('role') or ''
    (ok if not role2 else fail).append(f'no title→role for beschreibung role={role2!r}')

    # Footer-like short title MAY become role
    pre3 = copy.deepcopy(pre)
    pre3['extracted_data']['experience'][0]['role'] = ''
    pre3['extracted_data']['experience'][0]['title'] = 'Zertifizierter Altersvorsorgeberater'
    out3 = pp.clean(pre3, pdf_path='')
    role3 = out3['extracted_data']['experience'][0].get('role') or ''
    (ok if 'Altersvorsorge' in role3 else fail).append(f'footer title→role={role3!r}')

    # Token parts: dict focus → name only
    parts = pp._as_text_parts({'name': 'Bloomberg TOMS', 'level': 3})
    (ok if parts == ['Bloomberg TOMS'] else fail).append(f'as_text_parts={parts}')

    # Golden bpf: Fusion/Analyse remain after clean
    r = pdf_mod.PDFExtractor().extract(str(SAMPLES / 'AID-bpf_1.6.4.7.pdf'))
    clean_txt = aid._strip_page_headers(
        '\n'.join(ctrl._spans_to_aid_lines(ctrl._normalize_spans(r.spans)))
    )
    projs = aid._extract_projekte(clean_txt)
    pre_bpf = {
        'metadata': {},
        'extracted_data': {
            'personal': {},
            'experience': [dict(p) for p in projs],
            'skill_ablage': [],
            'skills': {},
        },
        'audit': {},
    }
    out_bpf = pp.clean(copy.deepcopy(pre_bpf), pdf_path='')
    blob_bpf = ' '.join(
        ' '.join(e.get('activities') or [])
        for e in out_bpf['extracted_data']['experience']
    )
    (ok if 'Fusion' in blob_bpf and 'Analyse' in blob_bpf else fail).append(
        'bpf keeps Fusion+Analyse after 4b'
    )
    (ok if len(out_bpf['extracted_data']['experience']) == len(projs) else fail).append(
        f'bpf project count {len(projs)}→{len(out_bpf["extracted_data"]["experience"])}'
    )

    report = {'ok': ok, 'fail': fail}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f'→ {OUT}')
    return 1 if fail else 0


if __name__ == '__main__':
    raise SystemExit(main())
