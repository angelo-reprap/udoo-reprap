#!/usr/bin/env python3
"""Regression R0–R4 / R7 für aid_regex_extractor + Controller-1b-Wiring."""
from __future__ import annotations

import importlib.util
import inspect
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INCOMING = ROOT / 'Repo_abpe' / 'cv_extractor' / 'incoming'
OUT = Path('/opt/cursor/artifacts/aid-regex-r0-r4-after-fix.json')


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ctrl = load('main_pipeline_controller', INCOMING / 'services' / 'main_pipeline_controller.py')
    aidm = load('aid_regex_extractor', INCOMING / 'extractors' / 'aid_regex_extractor.py')
    base = load('main_base_extractor', INCOMING / 'extractors' / 'main_base_extractor.py')
    pdf_mod = load('main_pdf_extractor', INCOMING / 'services' / 'main_pdf_extractor.py')
    aid = aidm.aid_regex_extractor
    ctrl_src = (INCOMING / 'services' / 'main_pipeline_controller.py').read_text(encoding='utf-8')
    aid_src = (INCOMING / 'extractors' / 'aid_regex_extractor.py').read_text(encoding='utf-8')
    base_src = (INCOMING / 'extractors' / 'main_base_extractor.py').read_text(encoding='utf-8')

    ok, fail = [], []

    # R1: usable project ohne period
    block = (
        "Firma/Institut: Beispiel AG\n"
        "Position: Engineer\n"
        "Projektbeschreibung: Demo\n"
        "• Tätigkeit eins\n"
        "• Tätigkeit zwei\n"
        "Systemumgebung: Java, Spring\n"
    )
    proj = aid._parse_projekt_block_a(block)
    r1 = (
        isinstance(proj, dict)
        and proj.get('company') == 'Beispiel AG'
        and not proj.get('period')
        and proj.get('technologies')
    )
    (ok if r1 else fail).append(f'R1 usable_ohne_period={proj}')

    # R1b: mit period weiter OK
    block2 = "Zeitraum: 01/2020 – 12/2021\n" + block
    proj2 = aid._parse_projekt_block_a(block2)
    (ok if proj2 and proj2.get('period') else fail).append(f'R1b mit_period={proj2 and proj2.get("period")}')

    # R2: Totcode entfernt
    (ok if '_extract_skill_tables_UNUSED' not in aid_src else fail).append('R2 UNUSED removed')

    # R3/R7 + R0 auf Troschke-PDF
    sample = ROOT / 'Repo_abpe' / 'cv_extractor' / 'samples' / 'AID-tt_1.2.4.2.pdf'
    r = pdf_mod.PDFExtractor().extract(str(sample))
    spans = ctrl._normalize_spans(r.spans)
    full = '\n'.join(ctrl._spans_to_aid_lines(spans))
    clean = aid._strip_page_headers(full)

    focus = aid._extract_focus_experience(clean)
    focus_names = [f['name'] for f in focus]
    skills = aid._extract_skill_tables(clean)
    skill_names = {s['name'].lower() for s in skills}
    opswat_in_focus = any('opswat' in n.lower() for n in focus_names)
    opswat_in_skills = any('opswat' in n for n in skill_names)
    (ok if opswat_in_focus and not opswat_in_skills and len(focus) >= 10 else fail).append(
        f'R3/R7 focus={len(focus)} opswat_focus={opswat_in_focus} opswat_skills={opswat_in_skills}'
    )

    # Datenkommunikation darf Produkte-Block nicht mehr schlucken
    dk = aid._extract_skill_section(clean, r'Datenkommunikation')
    (ok if dk and 'OPSWAT' not in dk and 'Berufliche' not in dk else fail).append(
        f'R3 datenkomm_boundary opswat_in_dk={"OPSWAT" in (dk or "")}'
    )

    personal = aid._extract_personal(clean, 'Thomas', 'Troschke')
    (ok if personal.get('birth_year') == 1965 else fail).append(f'R0 personal={personal}')

    # Controller wiring
    (ok if "_extract_personal" in ctrl_src and "focus_experience" in ctrl_src else fail).append(
        'R0 controller wires personal+focus'
    )

    # Seed/merge in labeled_to_prejson
    (ok if '_merge_personal' in base_src and "aid_extracted.get('personal')" in base_src else fail).append(
        'R0 base seeds personal'
    )
    (ok if "aid_extracted.get('focus_experience')" in base_src else fail).append(
        'R7 base seeds focus_experience'
    )
    merged_p = base._merge_personal(
        {'birth_year': 1965, 'languages': ['Deutsch']},
        {'birth_year': 1999, 'location': 'Remote', 'languages': [{'name': 'Englisch'}]},
    )
    r0_merge = (
        merged_p.get('birth_year') == 1965
        and merged_p.get('location') == 'Remote'
        and {x['name'] for x in merged_p['languages']} == {'Deutsch', 'Englisch'}
    )
    (ok if r0_merge else fail).append(f'R0 merge_personal={merged_p}')

    # R4: Y-glue = exact rounded Y (nicht abs>3)
    y_src = inspect.getsource(aid._extract_skill_tables_by_y)
    (ok if 'y != last_y' in y_src and 'abs(y - prev_y) > 3' not in y_src else fail).append(
        'R4 y-glue aligned'
    )

    # Troschke Projekte unverändert ~18
    projekte = aid._extract_projekte(clean)
    (ok if len(projekte) >= 17 else fail).append(f'Troschke projects={len(projekte)}')
    (ok if len(skills) >= 30 else fail).append(f'Troschke skills_after={len(skills)}')

    report = {
        'ok': ok,
        'fail': fail,
        'counts': {
            'focus_experience': len(focus),
            'skills': len(skills),
            'projects': len(projekte),
            'personal_birth_year': personal.get('birth_year'),
        },
        'focus_sample': focus_names[:8],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f'ok={len(ok)} fail={len(fail)} → {OUT}')
    return 1 if fail else 0


if __name__ == '__main__':
    sys.exit(main())
