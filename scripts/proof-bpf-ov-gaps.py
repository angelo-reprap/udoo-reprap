#!/usr/bin/env python3
"""Regression: bpf Alt-Projekte + ov Branchen/Focus-Noise + Experience-Merge."""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INCOMING = ROOT / 'Repo_abpe' / 'cv_extractor' / 'incoming'
SAMPLES = ROOT / 'Repo_abpe' / 'cv_extractor' / 'samples'
OUT = Path('/opt/cursor/artifacts/bpf-ov-gaps-after-fix.json')


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ctrl = load('ctrl', INCOMING / 'services' / 'main_pipeline_controller.py')
    aidm = load('aid', INCOMING / 'extractors' / 'aid_regex_extractor.py')
    base = load('base', INCOMING / 'extractors' / 'main_base_extractor.py')
    pdf_mod = load('pdf', INCOMING / 'services' / 'main_pdf_extractor.py')
    aid = aidm.aid_regex_extractor
    ctrl_src = (INCOMING / 'services' / 'main_pipeline_controller.py').read_text(encoding='utf-8')
    base_src = (INCOMING / 'extractors' / 'main_base_extractor.py').read_text(encoding='utf-8')

    ok, fail = [], []

    def full(pdf_name: str) -> str:
        r = pdf_mod.PDFExtractor().extract(str(SAMPLES / pdf_name))
        spans = ctrl._normalize_spans(r.spans)
        return '\n'.join(ctrl._spans_to_aid_lines(spans))

    # ── bpf: DE-Monate + numerisch inkl. älteste drei + 12/2004 ──
    bpf = aid._strip_page_headers(full('AID-bpf_1.6.4.7.pdf'))
    bpf_projs = aid._extract_projekte(bpf)
    starts = []
    for p in bpf_projs:
        m = re.search(r'(\d{1,2}/\d{4})', p.get('period') or '')
        if m:
            starts.append(m.group(1))
    need = [
        '03/2021', '09/2018', '02/2014', '01/2013', '05/2012',
        '04/1990', '01/1990', '07/1989', '12/2004', '09/2006',
    ]
    missing = [n for n in need if n not in starts]
    companies = ' '.join((p.get('company') or '') for p in bpf_projs).lower()
    company_need = ['st. gallen', 'deutsche bahn', 'ekom21', 'ge money', 'krone']
    company_miss = [c for c in company_need if c not in companies]
    (ok if len(bpf_projs) >= 28 and not missing and not company_miss else fail).append(
        f'bpf projects={len(bpf_projs)} missing={missing} company_miss={company_miss}'
    )

    skills, allg_br = aid._extract_allgemeine_kenntnisse(bpf)
    skill_names = ' '.join(s.get('name') or '' for s in skills).lower()
    skill_need = ['cobol', 'natural', 'adabas', 'z/os']
    skill_miss = [s for s in skill_need if s not in skill_names]
    (ok if len(skills) >= 20 and not skill_miss else fail).append(
        f'bpf allg skills={len(skills)} miss={skill_miss}'
    )
    (ok if len(allg_br) >= 5 and any('bank' in b.lower() for b in allg_br) else fail).append(
        f'bpf allg branchen={allg_br}'
    )

    edu = aid._extract_ausbildung(bpf)
    edu_ok = (
        len(edu) >= 1
        and 'Informatik' in (edu[0].get('degree') or '')
        and 'Allgemeine' not in (edu[0].get('degree') or '')
    )
    (ok if edu_ok else fail).append(f'bpf edu={edu}')

    # Merge stellt fehlende LLM-Perioden wieder her
    llm_fake = [
        p for p in bpf_projs
        if not re.search(r'\b(04/1990|01/1990|07/1989)\b', p.get('period') or '')
    ]
    merged = base._merge_experience(bpf_projs, llm_fake)
    (ok if len(merged) == len(bpf_projs) else fail).append(
        f'merge seed={len(bpf_projs)} llm={len(llm_fake)} → {len(merged)}'
    )
    (ok if "aid_extracted['experience']" in ctrl_src or 'experience' in ctrl_src and '_extract_projekte' in ctrl_src else fail).append(
        'controller seeds experience'
    )
    (ok if '_merge_experience' in base_src else fail).append('base has _merge_experience')

    # ── ov: 7 Projekte, Focus ohne Niveau-Header, Branchen clean ──
    ov = aid._strip_page_headers(full('AID-ov_3.4.5.1.pdf'))
    ov_projs = aid._extract_projekte(ov)
    focus = aid._extract_focus_experience(ov)
    branchen = aid._extract_branchen(ov)
    niveau_in_focus = [
        f['name'] for f in focus
        if re.search(r'(?i)^(sehr\s+gute|fortgeschrittene|gute|grund)\s*kenntnisse$', f['name'])
    ]
    branchen_noise = [
        b for b in branchen
        if base._is_section_noise_name(b) or ('produkte' in b.lower() and 'standard' in b.lower())
    ]
    (ok if len(ov_projs) >= 7 else fail).append(f'ov projects={len(ov_projs)}')
    (ok if not niveau_in_focus and len(focus) >= 10 else fail).append(
        f'ov focus={len(focus)} niveau={niveau_in_focus}'
    )
    (ok if not branchen_noise and len(branchen) >= 3 else fail).append(
        f'ov branchen={branchen} noise={branchen_noise}'
    )
    (ok if base._is_section_noise_name('Sehr gute Kenntnisse') else fail).append(
        'noise filter niveau'
    )
    (ok if base._is_section_noise_name('betriebssysteme') else fail).append(
        'noise filter skill-header'
    )

    # Troschke unverändert
    tt = aid._strip_page_headers(full('AID-tt_1.2.4.2.pdf'))
    (ok if len(aid._extract_projekte(tt)) >= 17 else fail).append(
        f'tt projects={len(aid._extract_projekte(tt))}'
    )

    report = {'ok': ok, 'fail': fail}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f'→ {OUT}')
    return 1 if fail else 0


if __name__ == '__main__':
    raise SystemExit(main())
