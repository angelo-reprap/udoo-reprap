#!/usr/bin/env python3
"""
Offline-Audit gegen email_studio_snapshot_*.json (kein Django nötig).

  python3 Repo_abpe/email_studio/incoming/audit_email_studio_snapshot.py
  python3 …/audit_email_studio_snapshot.py --snapshot path/to.json --json report.json

Prüft CI-Regeln (Schrift, Farbe, Align, Header/Footer) und Variablen-/Block-Lücken.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

CI = {
    'font': 'Arial',
    'font_size_body': '14px',
    'text_color': '#333333',
    'text_align': 'left',
    'width_px': '600',
    'header_modules': ('abcona_header_blau', 'abcona_header_gruen', 'abcona_header_rot'),
    'footer_modules': ('footer_standard', 'footer_auto_reply', 'signature'),
}

FONT = re.compile(r'font-family\s*:\s*([^;"\']+)', re.I)
SIZE = re.compile(r'font-size\s*:\s*([^;"\']+)', re.I)
COLOR = re.compile(r'(?<![-\w])color\s*:\s*([^;"\']+)', re.I)
BG = re.compile(r'background(?:-color)?\s*:\s*([^;"\']+)', re.I)
ALIGN = re.compile(r'text-align\s*:\s*([^;"\']+)', re.I)
VARS = re.compile(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}')
BLOCKS = re.compile(r'\{\{block:([a-zA-Z0-9_\-]+)\}\}')


def _find_snapshot(repo_root: Path) -> Path:
    data = repo_root / 'Repo_abpe' / 'email_studio' / 'data'
    latest = data / 'email_studio_snapshot_latest.json'
    if latest.is_file():
        return latest
    snaps = sorted(data.glob('email_studio_snapshot_*.json'))
    if not snaps:
        raise SystemExit(f'Kein Snapshot unter {data}')
    return snaps[-1]


def _style_summary(html: str) -> dict[str, list[str]]:
    return {
        'font': sorted({x.strip() for x in FONT.findall(html)}),
        'size': sorted({x.strip() for x in SIZE.findall(html)}),
        'color': sorted({x.strip() for x in COLOR.findall(html)}),
        'bg': sorted({x.strip() for x in BG.findall(html)}),
        'align': sorted({x.strip() for x in ALIGN.findall(html)}),
    }


def analyze(snapshot: list[dict[str, Any]]) -> dict[str, Any]:
    by_model: dict[str, list] = defaultdict(list)
    for row in snapshot:
        by_model[row['model']].append(row)

    modules = by_model.get('abpe_email_studio.emailmodule', [])
    templates = by_model.get('abpe_email_studio.emailtemplate', [])
    signatures = by_model.get('abpe_email_studio.emailsignature', [])
    senders = by_model.get('abpe_email_studio.emailsenderaccount', [])

    module_ids = {r['fields']['identifier'] for r in modules}
    module_ids.add('signature')

    module_rows = []
    for row in sorted(modules, key=lambda r: r['fields']['identifier']):
        f = row['fields']
        html = f.get('html_body') or ''
        styles = _style_summary(html)
        issues = []
        if styles['font'] and not any(CI['font'] in x for x in styles['font']):
            issues.append('font_not_arial')
        if f['identifier'].startswith('abcona_header_'):
            if 'left' not in styles['align'] and styles['align']:
                issues.append('header_not_left_aligned')
            if not styles['align']:
                issues.append('header_align_missing')
        if f['identifier'] in ('footer_standard', 'footer_auto_reply'):
            if styles['align'] and 'left' not in styles['align']:
                issues.append('footer_not_left_aligned')
            if CI['text_color'].lower() not in {c.lower() for c in styles['color']}:
                issues.append('footer_color_not_ci_333')
            if '14px' not in styles['size']:
                issues.append('footer_size_not_14px')
        module_rows.append({
            'identifier': f['identifier'],
            'module_type': f.get('module_type'),
            'is_active': f.get('is_active'),
            'vars': sorted(set(VARS.findall(html))),
            'styles': styles,
            'issues': issues,
        })

    template_rows = []
    unknown_blocks: Counter[str] = Counter()
    all_vars: Counter[str] = Counter()
    for row in sorted(templates, key=lambda r: r['fields']['identifier']):
        f = row['fields']
        html = f.get('html_body') or ''
        text = f.get('text_body') or ''
        subj = f.get('subject') or ''
        blocks = BLOCKS.findall(html)
        vars_ = sorted(set(VARS.findall(html + ' ' + text + ' ' + subj)))
        for v in vars_:
            all_vars[v] += 1
        unknown = [b for b in blocks if b not in module_ids]
        for b in unknown:
            unknown_blocks[b] += 1
        has_header = any(b in CI['header_modules'] for b in blocks)
        has_footer = any(b in CI['footer_modules'] for b in blocks)
        inline_header = bool(re.search(r'background\s*:\s*#163258', html, re.I)) and not has_header
        issues = []
        if f.get('status') == 'ACTIVE' and not has_header:
            issues.append('active_missing_header_module')
        if f.get('status') == 'ACTIVE' and not has_footer and f.get('signature_mode') in (None, 'NONE'):
            # many meetme mails rely on USER signature mode without {{block:signature}}
            if f.get('signature_mode') != 'USER':
                issues.append('active_missing_footer_or_signature')
        if inline_header:
            issues.append('inline_header_instead_of_module')
        template_rows.append({
            'identifier': f['identifier'],
            'app_scope': f.get('app_scope'),
            'status': f.get('status'),
            'signature_mode': f.get('signature_mode'),
            'blocks': blocks,
            'vars': vars_,
            'styles': _style_summary(html),
            'has_header_module': has_header,
            'has_footer_module': has_footer,
            'unknown_blocks': unknown,
            'issues': issues,
        })

    return {
        'ci_target': CI,
        'counts': {
            'modules': len(modules),
            'templates': len(templates),
            'signatures': len(signatures),
            'senders': len(senders),
        },
        'modules': module_rows,
        'templates': template_rows,
        'unknown_blocks': dict(unknown_blocks),
        'template_vars': sorted(all_vars.keys()),
        'module_issues': sum(1 for m in module_rows if m['issues']),
        'template_issues': sum(1 for t in template_rows if t['issues']),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, default=None)
    parser.add_argument('--json', type=Path, default=None, help='JSON-Report schreiben')
    parser.add_argument('--repo', type=Path, default=None)
    args = parser.parse_args()

    repo = args.repo or Path(__file__).resolve().parents[3]
    snap_path = args.snapshot or _find_snapshot(repo)
    data = json.loads(snap_path.read_text(encoding='utf-8'))
    report = analyze(data)
    report['snapshot'] = str(snap_path)

    print(f"Snapshot: {snap_path}")
    print(f"Counts:   {report['counts']}")
    print(f"Module mit Issues:   {report['module_issues']}")
    print(f"Vorlagen mit Issues: {report['template_issues']}")
    print(f"Unknown blocks: {report['unknown_blocks'] or '{}'}")
    print()
    print('--- Module Issues ---')
    for m in report['modules']:
        if m['issues']:
            print(f"  {m['identifier']}: {', '.join(m['issues'])} | align={m['styles']['align']} size={m['styles']['size']} color={m['styles']['color']}")
    print('--- Template Issues ---')
    for t in report['templates']:
        if t['issues']:
            print(f"  {t['identifier']}: {', '.join(t['issues'])} blocks={t['blocks']}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        print(f"\nJSON: {args.json}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
