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

    # Merge: Parallel-Projekte gleiches Datum (zwei Fortinet) + keine MM/YYYY-Duplikate
    llm_variant = []
    for p in bpf_projs:
        if re.search(r'\b(04/1990|01/1990|07/1989)\b', p.get('period') or ''):
            continue
        q = dict(p)
        if q.get('company'):
            q['company'] = (q['company'].split(',')[0]).strip()
        llm_variant.append(q)
    merged = base._merge_experience(bpf_projs, llm_variant)
    (ok if len(merged) == len(bpf_projs) else fail).append(
        f'merge seed={len(bpf_projs)} llm={len(llm_variant)} → {len(merged)}'
    )
    y2005 = [
        p for p in merged
        if '2005' in (p.get('period') or '') and re.search(r'(?i)dato|parallel|^2005', p.get('period') or '')
    ]
    (ok if len(y2005) >= 2 else fail).append(f'merge keeps two 2005-parallel={len(y2005)}')

    # TT: zwei Fortinet 03/2024 mit unterschiedlichen Kursen bleiben
    tt = aid._strip_page_headers(full('AID-tt_1.2.4.2.pdf'))
    tt_projs = aid._extract_projekte(tt)
    tt_merged = base._merge_experience(tt_projs, tt_projs[:10])  # LLM-Subset
    fort = [
        p for p in tt_merged
        if '03/2024' in (p.get('period') or '') and 'fortinet' in (p.get('company') or '').lower()
    ]
    (ok if len(tt_projs) >= 18 and len(fort) >= 2 else fail).append(
        f'tt projects={len(tt_projs)} merge={len(tt_merged)} fortinet_03_2024={len(fort)}'
    )

    # OV Degree ohne Institution-Kleber
    ov_txt = aid._strip_page_headers(full('AID-ov_3.4.5.1.pdf'))
    ov_edu = aid._extract_ausbildung(ov_txt)
    deg = (ov_edu[0].get('degree') if ov_edu else '') or ''
    inst = (ov_edu[0].get('institution') if ov_edu else '') or ''
    (ok if 'Bankkaufmann' in deg and 'SGZ' not in deg and 'SGZ' in inst else fail).append(
        f'ov edu degree={deg!r} institution={inst!r}'
    )

    # Footer: Krone gewinnt gegen falsch gelabeltes Cap Gemini 1980–1984
    llm_bad_footer = [
        p for p in bpf_projs
        if not re.search(r'(?i)krone', p.get('company') or '')
    ] + [{
        'period': '1980 – 1984',
        'company': 'Cap Gemini Berlin GmbH',
        'title': 'wrong',
        'activities': ['x'],
    }]
    merged_f = base._merge_experience(bpf_projs, llm_bad_footer)
    firms = ' '.join((p.get('company') or '') for p in merged_f).lower()
    (ok if 'krone' in firms and len(merged_f) >= 30 else fail).append(
        f'footer krone kept firms_has_krone={"krone" in firms} n={len(merged_f)}'
    )

    # Soft-Wrap: erste Activity zusammengezogen
    a0 = (bpf_projs[0].get('activities') or [''])[0]
    (ok if 'Weiterentwicklung' in a0 and a0.count('Unterstützung') <= 1 else fail).append(
        f'bpf softwrap act0={a0[:80]}'
    )
    # Footer mit Rolle/Acts
    footer = [
        p for p in bpf_projs
        if re.search(r'(?i)krone|cap gemini|umweltbundesamt', p.get('company') or '')
    ]
    footer_ok = (
        len(footer) >= 3
        and any('krone' in (p.get('company') or '').lower() for p in footer)
        and any((p.get('activities') or []) for p in footer)
        and any((p.get('role') or '') for p in footer)
    )
    (ok if footer_ok else fail).append(
        f'bpf footer={[(p.get("company"), p.get("role"), (p.get("activities") or [""])[:1]) for p in footer]}'
    )

    # 1b-Pfad: Allgemeine Kenntnisse → branchen+skills (wie Controller)
    ctrl_src = (INCOMING / 'services' / 'main_pipeline_controller.py').read_text(encoding='utf-8')
    (ok if '_extract_allgemeine_kenntnisse' in ctrl_src else fail).append(
        'controller wires allgemeine kenntnisse'
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

    # Fill: leere LLM-Hülle darf Seed-Inhalt nicht verwerfen (Merge-Enrich)
    seed_full = {
        'period': '03/2024 – 03/2024',
        'company': 'Fortinet GmbH',
        'role': 'Engineer',
        'activities': ['NSE4 Training und Lab'],
        'technologies': ['FortiGate'],
    }
    llm_shell = {
        'period': '03/2024 – 03/2024',
        'company': 'Fortinet GmbH',
        'role': '',
        'activities': [],
        'technologies': [],
    }
    enriched = base._merge_experience([seed_full], [llm_shell])
    enr_acts = (enriched[0].get('activities') if enriched else []) or []
    (ok if len(enriched) == 1 and 'NSE4' in (enr_acts[0] if enr_acts else '') else fail).append(
        f'fill enrich shell→seed acts={enr_acts} n={len(enriched)}'
    )

    # Fill: normalize leeres LLM + Format-A Text → Regex-Fallback
    sample_a = (
        "Zeitraum:\n03/2024 – 03/2024\n"
        "Kunde / Branche:\nFortinet GmbH\n"
        "Rolle / Position:\nSecurity Engineer\n"
        "Aufgaben:\n• NSE4 Kurs\n"
    )
    filled, used_fb = base._normalize_project_fill(sample_a, {})
    (ok if used_fb and filled and '03/2024' in (filled[0].get('period') or '') else fail).append(
        f'fill normalize empty-llm fb={used_fb} filled={filled[:1]}'
    )
    # Junk-LLM ohne Experience-Felder → Fallback
    filled2, used2 = base._normalize_project_fill(sample_a, {'note': 'not a project', 'ok': True})
    (ok if filled2 and base._usable_experience(filled2[0]) else fail).append(
        f'fill normalize junk-llm n={len(filled2)} used_fb={used2}'
    )

    # Seed-Match aus Gruppentext
    hit = base._match_seed_for_group_text(
        "Projekt 03/2024 bei Fortinet GmbH\nAufgaben ...",
        [seed_full, {'period': '01/2020 – 02/2020', 'company': 'Other', 'activities': ['x']}],
    )
    (ok if hit and 'Fortinet' in (hit.get('company') or '') else fail).append(
        f'fill seed-match={hit.get("company") if hit else None}'
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
