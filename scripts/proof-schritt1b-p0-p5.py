#!/usr/bin/env python3
"""Regression P0–P5 für Schritt 1b (ohne Django)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INCOMING = ROOT / 'Repo_abpe' / 'cv_extractor' / 'incoming'
OUT = Path('/opt/cursor/artifacts/schritt1b-p0-p5-after-fix.json')


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ctrl = load('main_pipeline_controller', INCOMING / 'services' / 'main_pipeline_controller.py')
    aid = load('aid_regex_extractor', INCOMING / 'extractors' / 'aid_regex_extractor.py')
    base = load('main_base_extractor', INCOMING / 'extractors' / 'main_base_extractor.py')
    pdf_mod = load('main_pdf_extractor', INCOMING / 'services' / 'main_pdf_extractor.py')
    ctrl_src = (INCOMING / 'services' / 'main_pipeline_controller.py').read_text(encoding='utf-8')
    base_src = (INCOMING / 'extractors' / 'main_base_extractor.py').read_text(encoding='utf-8')

    ok, fail = [], []

    lines = ctrl._spans_to_aid_lines([
        {'page': 1, 'y': 100, 'x': 50, 'text': 'Zeitraum:', 'column_id': -1},
        {'page': 1, 'y': 103, 'x': 50, 'text': '01/2020 – 12/2021', 'column_id': -1},
    ])
    (ok if lines[:2] == ['Zeitraum:', '01/2020 – 12/2021'] else fail).append(f'P0 {lines[:2]}')

    lines = ctrl._spans_to_aid_lines([
        {'page': 1, 'y': 200, 'x': 40, 'text': 'Programmiersprachen', 'column_id': 0},
        {'page': 1, 'y': 220, 'x': 40, 'text': 'Java', 'column_id': 0},
        {'page': 1, 'y': 200, 'x': 320, 'text': 'Datenbanken', 'column_id': 1},
        {'page': 1, 'y': 220, 'x': 320, 'text': 'PostgreSQL', 'column_id': 1},
    ])
    mixed = any('Programmiersprachen' in ln and 'Datenbanken' in ln for ln in lines)
    (ok if not mixed else fail).append(f'P1 {lines}')

    start = ctrl_src.find('# ── Schritt 1b')
    end = ctrl_src.find('# ── Schritt 2:', start)
    block = ctrl_src[start:end]
    strip_pos = block.find('_strip_page_headers')
    skill_pos = block.find('_extract_skill_tables')
    (ok if 0 <= strip_pos < skill_pos else fail).append(f'P2 strip={strip_pos}<skill={skill_pos}')

    merged = base._merge_str_lists(['Netzwerk'], ['Firewall', 'Netzwerk'])
    gate_gone = "and not pre_json['extracted_data']['focus_areas']" not in base_src
    (ok if merged == ['Netzwerk', 'Firewall'] and gate_gone else fail).append(
        f'P3 merge={merged} gate_gone={gate_gone}'
    )

    except_body = block[block.find('except Exception'):]
    (ok if 'aid_skill_categories = {}' in except_body and 'aid_extracted = {}' in except_body else fail).append(
        'P4 clear'
    )

    pat = next(p for p in aid.ABCONA_SIGNALS if 'AID-' in p.pattern)
    p5 = (
        bool(pat.search('AID-tt_1.2.4.2'))
        and bool(pat.search('AID-kea_2.8.4.1'))
        and 'Skill-Duplikat' in ctrl_src
    )
    (ok if p5 else fail).append(f'P5 {pat.pattern}')

    sample = ROOT / 'Repo_abpe' / 'cv_extractor' / 'samples' / 'AID-tt_1.2.4.2.pdf'
    r = pdf_mod.PDFExtractor().extract(str(sample))
    spans = ctrl._normalize_spans(r.spans)
    full = '\n'.join(ctrl._spans_to_aid_lines(spans))
    clean = aid.aid_regex_extractor._strip_page_headers(full)
    skills = aid.aid_regex_extractor._extract_skill_tables(clean)
    focus = aid.aid_regex_extractor._extract_focus_experience(clean)
    # Produkte|Standards zählen als focus_experience, nicht mehr als Skills (≥50 war inkl. Produkte)
    opswat_as_skill = any('opswat' in (s.get('name') or '').lower() for s in skills)
    sanity = (
        aid.aid_regex_extractor.is_aid_profile(full)
        and len(skills) >= 30
        and len(focus) >= 10
        and not opswat_as_skill
    )
    (ok if sanity else fail).append(
        f'SANITY skills={len(skills)} focus={len(focus)} opswat_skill={opswat_as_skill}'
    )

    report = {'ok': ok, 'fail': fail}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f'\nWrote {OUT}')
    return 1 if fail else 0


if __name__ == '__main__':
    raise SystemExit(main())
