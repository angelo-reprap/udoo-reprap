#!/usr/bin/env python3
"""
Perioden-Lücken Orig vs neu/cv: Kontext + Format-Check.

Auf ucs5 (mit venv, pypdf):
  python3 scripts/dig-period-gaps.py \\
    --orig /mnt/public/Berater/AID_profile/aaa/al-kenani_muhanned/AID-mak_2.1.9.1.pdf \\
    --neu  /mnt/public/Berater/AID_profile/aaa/al-kenani_muhanned/neu/cv/AID-ma_1.2.3.1.pdf

  # oder via Letter/Dir:
  python3 scripts/dig-period-gaps.py --letter aaa --dir al-kenani_muhanned
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPARE = (
    ROOT
    / 'Repo_abpe/cv_extractor/incoming/management/commands/compare_aid_neu_cv.py'
)
AID_ROOT = Path('/mnt/public/Berater/AID_profile')


def _load_compare_helpers():
    src = COMPARE.read_text(encoding='utf-8')
    cut = src.find('\nclass Command')
    stub = types.ModuleType('django.core.management.base')
    stub.BaseCommand = object  # type: ignore
    sys.modules.setdefault('django', types.ModuleType('django'))
    sys.modules.setdefault('django.core', types.ModuleType('django.core'))
    sys.modules.setdefault(
        'django.core.management', types.ModuleType('django.core.management')
    )
    sys.modules['django.core.management.base'] = stub
    ns: dict = {'__name__': 'compare_helpers', 're': re}
    exec(compile(src[:cut], str(COMPARE), 'exec'), ns)
    return ns


def _pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        return '\n'.join((p.extract_text() or '') for p in reader.pages)
    except Exception as e:
        return f'[PDF_READ_ERROR: {e}]'


def _ctx(text: str, token: str, width: int = 90) -> list[str]:
    out = []
    for m in re.finditer(re.escape(token), text):
        a = max(0, m.start() - width)
        b = min(len(text), m.end() + width)
        snippet = text[a:b].replace('\n', '⏎')
        out.append(snippet)
        if len(out) >= 3:
            break
    return out


def _alt_forms(mm_yyyy: str) -> list[str]:
    """Alternative Schreibweisen desselben Monats."""
    m = re.match(r'^(\d{1,2})/(\d{4})$', mm_yyyy)
    if not m:
        return []
    mm, yyyy = int(m.group(1)), m.group(2)
    mm2 = f'{mm:02d}'
    mm1 = str(mm)
    de = {
        1: 'Januar', 2: 'Februar', 3: 'März', 4: 'April',
        5: 'Mai', 6: 'Juni', 7: 'Juli', 8: 'August',
        9: 'September', 10: 'Oktober', 11: 'November', 12: 'Dezember',
    }.get(mm, '')
    alts = [
        f'{mm2}/{yyyy}',
        f'{mm1}/{yyyy}',
        f'{mm2}.{yyyy}',
        f'{mm1}.{yyyy}',
        f'{yyyy}-{mm2}',
        f'{yyyy}/{mm2}',
        f'{mm2}-{yyyy}',
    ]
    if de:
        alts += [f'{de} {yyyy}', f'{de[:3]} {yyyy}', f'{de[:3]}. {yyyy}']
    # dedupe preserve order
    seen = set()
    out = []
    for a in alts:
        if a not in seen:
            seen.add(a)
            out.append(a)
    return out


def _classify(token: str, neu_text: str) -> str:
    if not re.match(r'^\d{1,2}/\d{4}$', token):
        # bare year / heute — nur mit Digit-Boundaries (nicht Nexus 7000)
        if re.search(rf'(?<!\d){re.escape(token)}(?!\d)', neu_text, flags=re.I):
            return 'present_raw'
        return 'missing_other'
    for alt in _alt_forms(token):
        # '(?<!\d)1/2015(?!\d)' — nicht Treffer in 11/2015
        if re.search(rf'(?<!\d){re.escape(alt)}(?!\d)', neu_text):
            return f'format_alt:{alt}'
    # Jahr allein irgendwo — schwach
    y = token.split('/')[-1]
    if re.search(rf'(?<!\d){re.escape(y)}(?!\d)', neu_text):
        return 'year_only'
    return 'likely_gap'


def resolve_paths(letter: str, dir_name: str) -> tuple[Path, Path]:
    person = AID_ROOT / letter / dir_name
    origs = sorted(
        person.glob('AID-*.pdf'),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    origs = [p for p in origs if p.parent == person]
    neu_dir = person / 'neu' / 'cv'
    neus = sorted(
        neu_dir.glob('AID-*.pdf'),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ) if neu_dir.is_dir() else []
    if not origs:
        raise SystemExit(f'kein Orig-PDF unter {person}')
    if not neus:
        raise SystemExit(f'kein neu/cv PDF unter {neu_dir}')
    return origs[0], neus[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--orig', type=Path)
    ap.add_argument('--neu', type=Path)
    ap.add_argument('--letter', default='')
    ap.add_argument('--dir', dest='consultant_dir', default='')
    ap.add_argument('--out', type=Path, default=None)
    args = ap.parse_args()

    if args.letter and args.consultant_dir:
        orig, neu = resolve_paths(args.letter, args.consultant_dir)
    elif args.orig and args.neu:
        orig, neu = args.orig, args.neu
    else:
        ap.error('brauch --orig/--neu oder --letter/--dir')
        return 2

    helpers = _load_compare_helpers()
    ot = helpers['_norm'](_pdf_text(orig))
    nt = helpers['_norm'](_pdf_text(neu))
    op = helpers['_period_anchors'](ot)
    np_ = helpers['_period_anchors'](nt)
    missing = sorted(op - np_)
    extra = sorted(np_ - op)

    lines = [
        f'# Period-Gaps',
        f'- orig: `{orig}` ({len(ot)} chars, {len(op)} anchors)',
        f'- neu:  `{neu}` ({len(nt)} chars, {len(np_)} anchors)',
        f'- missing: **{len(missing)}**  extra: **{len(extra)}**',
        '',
        '## Klassifikation Missing',
    ]

    buckets = {
        'likely_gap': [],
        'format_alt': [],
        'year_only': [],
        'present_raw': [],
        'missing_other': [],
    }
    for tok in missing:
        kind = _classify(tok, nt)
        bucket = kind.split(':', 1)[0]
        buckets.setdefault(bucket, []).append((tok, kind))
        ctxs = _ctx(ot, tok)
        lines.append(f'### `{tok}` → **{kind}**')
        if ctxs:
            for c in ctxs:
                lines.append(f'- orig: …{c}…')
        else:
            lines.append('- orig: (kein Kontext — Token nur via Range-Expand?)')
        lines.append('')

    lines += [
        '## Summary',
        f"- likely_gap: {len(buckets.get('likely_gap', []))}",
        f"- format_alt: {len(buckets.get('format_alt', []))}",
        f"- year_only: {len(buckets.get('year_only', []))}",
        f"- other: {len(buckets.get('missing_other', [])) + len(buckets.get('present_raw', []))}",
        '',
        '## Extra in neu (Auszug)',
        f'- {extra[:25]}',
    ]

    report = '\n'.join(lines) + '\n'
    print(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding='utf-8')
        print(f'→ {args.out}', file=sys.stderr)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
