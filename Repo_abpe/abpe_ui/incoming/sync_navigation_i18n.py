#!/usr/bin/env python3
"""navigation.json aus module.json (titles.de) erzeugen — Referenz für i18n_translator.py.

Der Translator übersetzt dann automatisch nach hu/ar/…:
  mkdir apps/abpe_ui/static/abpe_ui/i18n/hu/
  python3 apps/abpe_ui/bin/i18n_translator.py

ucs5 (Repo):
  python3 Repo_abpe/abpe_ui/incoming/sync_navigation_i18n.py --write
  cp Repo_abpe/abpe_ui/incoming/i18n/de/navigation.json \\
     /opt/abpe/backend/apps/abpe_ui/static/abpe_ui/i18n/de/navigation.json
  cd /opt/abpe/backend && python3 apps/abpe_ui/bin/i18n_translator.py
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

MODULES_DIR = Path(__file__).parent / 'modules'
OUT = Path(__file__).parent / 'i18n' / 'de' / 'navigation.json'

# Feste Portal-Nav (nicht in module.json)
EXTRA = {
    'dashboard': 'Dashboard',
    'admin': 'Admin Bereich',
}


def _de_title(titles: dict | None, fallback: str) -> str:
    if isinstance(titles, dict) and titles.get('de'):
        return titles['de']
    return fallback


def _collect() -> dict:
    nav: dict[str, str] = dict(EXTRA)
    for path in sorted(MODULES_DIR.glob('*/module.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        mid = data.get('id') or path.parent.name
        nav[mid] = _de_title(data.get('titles'), data.get('title', mid))
        for sp in data.get('subpages') or []:
            sid = sp.get('id')
            if not sid:
                continue
            key = f'{mid}.{sid}'
            nav[key] = _de_title(sp.get('titles'), sp.get('title', sid))
    return {'nav': nav}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true', help='navigation.json schreiben')
    args = parser.parse_args()

    payload = _collect()
    print(json.dumps(payload, ensure_ascii=False, indent=4))
    if args.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=4) + '\n', encoding='utf-8')
        print(f'\n✓ {len(payload["nav"])} Keys → {OUT}')
    else:
        print(f'\nDry-run: {len(payload["nav"])} Keys ( --write zum Speichern )')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
