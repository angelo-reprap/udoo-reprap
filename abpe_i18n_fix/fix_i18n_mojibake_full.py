#!/usr/bin/env python3
"""Scannt DE-i18n-JSON auf verbleibendes Mojibake und repariert es."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path('apps/abpe_crm/static/abpe_crm/i18n/de')

# Typische Mojibake-Muster (UTF-8 als cp1252/latin-1 gelesen)
SUSPECT = re.compile(
    r'Ã[\x80-\xbf\u0080-\u00ff]?|'   # äöüÄÖÜß etc.
    r'â€[\x80-\xbf]|'                  # – — ' " …
    r'ï¿½|'                           
    r'\ufffd|'                        # replacement char
    r'â\x80'                          
)


def try_fix(value: str) -> str | None:
    if not SUSPECT.search(value):
        return None
    for enc in ('cp1252', 'latin-1'):
        try:
            fixed = value.encode(enc).decode('utf-8')
            if fixed != value and not SUSPECT.search(fixed):
                return fixed
        except (UnicodeDecodeError, UnicodeEncodeError):
            continue
    return None


def fix_obj(obj, hits: list):
    if isinstance(obj, dict):
        return {k: fix_obj(v, hits) for k, v in obj.items()}
    if isinstance(obj, list):
        return [fix_obj(v, hits) for v in obj]
    if isinstance(obj, str):
        fixed = try_fix(obj)
        if fixed is not None:
            hits.append((obj, fixed))
            return fixed
        if SUSPECT.search(obj):
            hits.append((obj, None))  # unfixable
        return obj
    return obj


def scan_only(root: Path) -> list[tuple[str, str, str]]:
    found = []
    for path in sorted(root.rglob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))

        def walk(o, prefix=''):
            if isinstance(o, dict):
                for k, v in o.items():
                    walk(v, f'{prefix}.{k}' if prefix else k)
            elif isinstance(o, list):
                for i, v in enumerate(o):
                    walk(v, f'{prefix}[{i}]')
            elif isinstance(o, str) and SUSPECT.search(o):
                found.append((str(path), prefix, o))

        walk(data)
    return found


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else 'scan'
    root = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT

    if mode == 'scan':
        found = scan_only(root)
        if not found:
            print('OK: Kein Mojibake gefunden in', root)
            return 0
        print(f'WARN: {len(found)} verdächtige String(s):')
        for path, key, val in found[:40]:
            print(f'  {path}\n    [{key}] {val!r}')
        if len(found) > 40:
            print(f'  ... und {len(found) - 40} weitere')
        return 1

    if mode == 'fix':
        changed_files = 0
        total_fixed = 0
        still_broken = []
        for path in sorted(root.rglob('*.json')):
            hits: list = []
            data = json.loads(path.read_text(encoding='utf-8'))
            new = fix_obj(data, hits)
            fixed = [h for h in hits if h[1] is not None]
            broken = [h for h in hits if h[1] is None]
            if fixed:
                path.write_text(
                    json.dumps(new, ensure_ascii=False, indent=4) + '\n',
                    encoding='utf-8',
                )
                changed_files += 1
                print(f'✓ {path} ({len(fixed)} repariert)')
                total_fixed += len(fixed)
            still_broken.extend(broken)
        print(f'\n{changed_files} Datei(en), {total_fixed} String(s) repariert')
        if still_broken:
            print(f'\nWARN: {len(still_broken)} nicht automatisch reparierbar:')
            for orig, _ in still_broken[:10]:
                print(f'  {orig!r}')
        return 0

    print('Usage: fix_i18n_mojibake_full.py [scan|fix] [root]', file=sys.stderr)
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
