#!/usr/bin/env python3
"""Prüft PBX.t()-Key-Abdeckung in de/en crm_telefon.json."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PBX_JS = Path('apps/abpe_crm/static/abpe_crm/js/mod-crm-pbx.js')
DE_JSON = Path('apps/abpe_crm/static/abpe_crm/i18n/de/modules/crm_telefon/crm_telefon.json')
EN_JSON = Path('apps/abpe_crm/static/abpe_crm/i18n/en/modules/crm_telefon/crm_telefon.json')
I18N_ROOT = Path('apps/abpe_crm/static/abpe_crm/i18n')


def pbx_keys(js: str) -> set[str]:
    keys = set(re.findall(r"\.t\(\s*['\"](pbx_[^'\"]+)['\"]", js))
    keys |= set(re.findall(r"PBX\.t\(\s*['\"](pbx_[^'\"]+)['\"]", js))
    keys.discard('pbx_*')
    return keys


def load_flat(path: Path) -> dict:
    data = json.loads(path.read_text(encoding='utf-8'))
    if isinstance(data.get('crm_telefon'), dict):
        return data['crm_telefon']
    return data


def check_lang(label: str, path: Path, needed: set[str]) -> tuple[set[str], set[str]]:
    if not path.is_file():
        return needed, set()
    flat = load_flat(path)
    have = set(flat)
    return needed - have, have - needed - {'pbx_*'}


def main() -> int:
    if not PBX_JS.is_file():
        print(f'FEHLER: {PBX_JS} nicht gefunden', file=sys.stderr)
        return 1

    js = PBX_JS.read_text(encoding='utf-8')
    needed = pbx_keys(js)
    print(f'PBX.t() Keys in mod-crm-pbx.js: {len(needed)}')

    for label, path in [('DE', DE_JSON), ('EN', EN_JSON)]:
        missing, extra = check_lang(label, path, needed)
        flat = load_flat(path) if path.is_file() else {}
        print(f'\n{label}: {len(flat)} Keys, fehlend: {len(missing)}, extra: {len(extra)}')
        if missing:
            for k in sorted(missing)[:20]:
                print(f'  FEHLT  {k}')
            if len(missing) > 20:
                print(f'  ... +{len(missing)-20}')

    langs = sorted(p.name for p in I18N_ROOT.iterdir() if p.is_dir()) if I18N_ROOT.is_dir() else []
    print(f'\nSprachverzeichnisse: {", ".join(langs)}')
    for lang in langs:
        if lang in ('de', 'en'):
            continue
        p = I18N_ROOT / lang / 'modules' / 'crm_telefon' / 'crm_telefon.json'
        miss, _ = check_lang(lang.upper(), p, needed)
        if p.is_file():
            print(f'  {lang}: crm_telefon.json — fehlend {len(miss)}')
        else:
            print(f'  {lang}: crm_telefon.json FEHLT')

    de_miss, _ = check_lang('DE', DE_JSON, needed)
    en_miss, _ = check_lang('EN', EN_JSON, needed)
    ok = not de_miss and not en_miss
    print('\n' + ('OK: DE+EN vollständig für PBX' if ok else 'WARN: Lücken in DE oder EN'))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
