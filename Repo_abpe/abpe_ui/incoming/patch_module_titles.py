#!/usr/bin/env python3
"""module.json titles — fehlende Sprachen ergänzen (Fallback: immer de).

ucs5:
  python3 /mnt/public/udoo-reprap/Repo_abpe/abpe_ui/incoming/patch_module_titles.py
  python3 .../patch_module_titles.py --write
  python3 .../patch_module_titles.py --write --from-de   # ar/ja/ko/… auf de zurücksetzen
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

LANGS = ['ar', 'de', 'en', 'es', 'fr', 'it', 'ja', 'ko', 'nl', 'pl', 'pt', 'ru', 'tr', 'zh']
# Fremdsprachen ohne eigene Übersetzung → deutscher Titel aus titles.de
DE_FALLBACK_LANGS = {'ar', 'ja', 'ko', 'nl', 'pl', 'pt', 'ru', 'tr', 'zh'}
MODULES_DIR = Path(__file__).parent / 'modules'


def _fill_titles(titles: dict, from_de: bool = False) -> tuple[dict, int]:
    if not isinstance(titles, dict):
        return titles, 0
    n = 0
    de = titles.get('de') or next(iter(titles.values()), '')
    for lang in LANGS:
        if lang == 'de':
            continue
        if lang in DE_FALLBACK_LANGS:
            if (from_de or lang not in titles) and de and titles.get(lang) != de:
                titles[lang] = de
                n += 1
        elif lang not in titles and de:
            titles[lang] = de
            n += 1
    return titles, n


def _patch_node(node: dict, from_de: bool) -> int:
    total = 0
    if 'titles' in node:
        node['titles'], n = _fill_titles(node['titles'], from_de=from_de)
        total += n
    for sub in node.get('subpages') or []:
        total += _patch_node(sub, from_de)
    return total


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true', help='Dateien schreiben (sonst dry-run)')
    parser.add_argument('--from-de', action='store_true',
                        help='ar/ja/ko/nl/pl/pt/ru/tr/zh auf titles.de zurücksetzen')
    args = parser.parse_args()

    grand = 0
    for path in sorted(MODULES_DIR.glob('*/module.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        n = _patch_node(data, from_de=args.from_de)
        if n:
            print(f'  {path.parent.name}: +{n} title(s)')
            grand += n
            if args.write:
                path.write_text(json.dumps(data, ensure_ascii=False, indent=4) + '\n', encoding='utf-8')
    print(f'{"Geschrieben" if args.write else "Dry-run"}: {grand} fehlende titles ergänzt')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
