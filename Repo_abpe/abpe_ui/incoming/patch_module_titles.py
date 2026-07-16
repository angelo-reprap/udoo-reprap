#!/usr/bin/env python3
"""module.json titles — fehlende Sprachen ergänzen (Fallback: en → de).

ucs5:
  python3 Repo_abpe/abpe_ui/incoming/patch_module_titles.py
  python3 .../patch_module_titles.py --write
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

LANGS = ['ar', 'de', 'en', 'es', 'fr', 'it', 'ja', 'ko', 'nl', 'pl', 'pt', 'ru', 'tr', 'zh']
MODULES_DIR = Path(__file__).parent / 'modules'


def _fill_titles(titles: dict) -> tuple[dict, int]:
    if not isinstance(titles, dict):
        return titles, 0
    n = 0
    fallback = titles.get('en') or titles.get('de') or next(iter(titles.values()), '')
    for lang in LANGS:
        if lang not in titles and fallback:
            titles[lang] = fallback
            n += 1
    return titles, n


def _patch_node(node: dict) -> int:
    total = 0
    if 'titles' in node:
        node['titles'], n = _fill_titles(node['titles'])
        total += n
    for sub in node.get('subpages') or []:
        total += _patch_node(sub)
    return total


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true', help='Dateien schreiben (sonst dry-run)')
    args = parser.parse_args()

    grand = 0
    for path in sorted(MODULES_DIR.glob('*/module.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        n = _patch_node(data)
        if n:
            print(f'  {path.parent.name}: +{n} title(s)')
            grand += n
            if args.write:
                path.write_text(json.dumps(data, ensure_ascii=False, indent=4) + '\n', encoding='utf-8')
    print(f'{"Geschrieben" if args.write else "Dry-run"}: {grand} fehlende titles ergänzt')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
