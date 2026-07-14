#!/usr/bin/env python3
"""Repariert Mojibake in DE-i18n-JSON (UTF-8 fälschlich als Latin-1 gespeichert).

Beispiel: AnhÃ¤nge → Anhänge, SchlieÃŸen → Schließen
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path('apps/abpe_crm/static/abpe_crm/i18n/de')
MOJIBAKE = re.compile(r'Ã.|â€|ï¿½')

FIXED: list[str] = []
SKIPPED: list[str] = []


def _try_fix(value: str) -> str:
    if not MOJIBAKE.search(value):
        return value
    for enc in ('cp1252', 'latin-1'):
        try:
            fixed = value.encode(enc).decode('utf-8')
            if fixed != value:
                return fixed
        except (UnicodeDecodeError, UnicodeEncodeError):
            continue
    return value


def _fix_obj(obj):
    if isinstance(obj, dict):
        return {k: _fix_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_fix_obj(v) for v in obj]
    if isinstance(obj, str):
        fixed = _try_fix(obj)
        if fixed != obj:
            FIXED.append(f'{obj!r} -> {fixed!r}')
        return fixed
    return obj


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT
    if not root.is_dir():
        print(f'FEHLER: Verzeichnis nicht gefunden: {root}', file=sys.stderr)
        return 1

    files = sorted(root.rglob('*.json'))
    changed = 0
    for path in files:
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as e:
            print(f'WARN JSON parse {path}: {e}')
            continue
        new_data = _fix_obj(data)
        if new_data != data:
            path.write_text(
                json.dumps(new_data, ensure_ascii=False, indent=4) + '\n',
                encoding='utf-8',
            )
            changed += 1
            print(f'✓ {path}')

    print(f'\nFertig: {changed} Datei(en) geändert, {len(FIXED)} String(s) repariert')
    if FIXED[:10]:
        print('\nBeispiele:')
        for line in FIXED[:10]:
            print(' ', line)
    if len(FIXED) > 10:
        print(f'  ... und {len(FIXED) - 10} weitere')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
