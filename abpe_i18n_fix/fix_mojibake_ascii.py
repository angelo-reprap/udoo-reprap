#!/usr/bin/env python3
"""DE-i18n Mojibake reparieren — nur ASCII/\\u Escapes (shell-sicher)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path('apps/abpe_crm/static/abpe_crm/i18n/de')

# Ã Â â€ â… â†' Â· ï¿½ �
SUSPECT = re.compile(
    r'[\u00c2\u00c3][\u0080-\u00bf]|'
    r'\u00e2[\u0080-\u00bf\u20ac\u0080-\u00ff]|'
    r'\ufffd|'
    r'\u00e2.'
)

MANUAL = [
    ('\u00e2\u20ac\u00a6', '\u2026'),  # â€¦ -> …
    ('\u00e2\u20ac\u201d', '\u2014'),  # â€" -> —
    ('\u00e2\u20ac\u201c', '\u2013'),  # â€" -> –
    ('\u00e2\u0080\u0094', '\u2014'),
    ('\u00e2\u0080\u0093', '\u2013'),
    ('\u00e2\u0080\u00a6', '\u2026'),
    ('\u00e2\u0086\u0092', '\u2192'),  # â†' -> →
    ('\u00e2\u0080\u00a2', '\u2192'),
    ('\u00c2\u00b7', '\u00b7'),        # Â· -> ·
    ('\u00c3\u00a4', '\u00e4'),
    ('\u00c3\u00b6', '\u00f6'),
    ('\u00c3\u00bc', '\u00fc'),
    ('\u00c3\u009f', '\u00df'),
    ('\u00c3\u009c', '\u00dc'),
    ('\u00c3\u0096', '\u00d6'),
    ('\u00c3\u0084', '\u00c4'),
    ('\u00c3\u0178', '\u00df'),        # ÃŸ -> ß (selten)
]


def try_fix(value: str) -> str:
    if not SUSPECT.search(value):
        return value
    for enc in ('cp1252', 'latin-1'):
        try:
            fixed = value.encode(enc).decode('utf-8')
            if fixed != value and not SUSPECT.search(fixed):
                return fixed
        except (UnicodeDecodeError, UnicodeEncodeError):
            pass
    out = value
    for bad, good in MANUAL:
        out = out.replace(bad, good)
    return out


def fix_obj(obj, bad: list):
    if isinstance(obj, dict):
        return {k: fix_obj(v, bad) for k, v in obj.items()}
    if isinstance(obj, list):
        return [fix_obj(v, bad) for v in obj]
    if isinstance(obj, str):
        fixed = try_fix(obj)
        if fixed != obj:
            return fixed
        if SUSPECT.search(obj):
            bad.append(obj)
        return obj
    return obj


def scan(root: Path) -> int:
    n = 0
    for path in sorted(root.rglob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))

        def walk(o, key=''):
            nonlocal n
            if isinstance(o, dict):
                for k, v in o.items():
                    walk(v, f'{key}.{k}' if key else k)
            elif isinstance(o, list):
                for i, v in enumerate(o):
                    walk(v, f'{key}[{i}]')
            elif isinstance(o, str) and SUSPECT.search(o):
                n += 1
                print(f'{path} [{key}] {o!r}')

        walk(data)
    if n == 0:
        print('OK: kein Mojibake in', root)
    else:
        print(f'\n{n} verdächtige String(s)')
    return n


def fix(root: Path) -> int:
    changed = still = 0
    still_bad = []
    for path in sorted(root.rglob('*.json')):
        bad = []
        data = json.loads(path.read_text(encoding='utf-8'))
        new = fix_obj(data, bad)
        if new != data:
            path.write_text(
                json.dumps(new, ensure_ascii=False, indent=4) + '\n',
                encoding='utf-8',
            )
            changed += 1
            print(f'\u2713 {path}')
        still_bad.extend(bad)
    still = len(still_bad)
    print(f'\n{changed} Datei(en) ge\u00e4ndert')
    if still:
        print(f'WARN: {still} nicht reparierbar:')
        for s in still_bad[:15]:
            print(f'  {s!r}')
    else:
        print('OK: alles sauber')
    return 0


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'fix'
    root = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT
    raise SystemExit(scan(root) if cmd == 'scan' else fix(root))
