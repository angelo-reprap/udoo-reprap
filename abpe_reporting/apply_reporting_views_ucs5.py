#!/usr/bin/env python3
"""Reporting-API auf ucs5 installieren.

Kopiert reporting_api.py und ergänzt apps/abpe_crm/urls.py.
Kein Regex — kein Anhängen an views.py nötig.

Usage:
  cd /opt/abpe/backend
  curl -sL '.../reporting_api.py' -o /tmp/reporting_api.py
  curl -sL '.../apply_reporting_views_ucs5.py' -o /tmp/apply_reporting_views_ucs5.py
  python3 /tmp/apply_reporting_views_ucs5.py --snippet /tmp/reporting_api.py
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

URLS_FILE = Path('apps/abpe_crm/urls.py')
VIEWS_FILE = Path('apps/abpe_crm/views.py')
API_FILE = Path('apps/abpe_crm/reporting_api.py')
MARKER = '# --- reporting dashboard (auto) ---'

ROUTES = (
    "    path('api/reporting/dashboard/', reporting_api.api_reporting_dashboard, "
    "name='api_reporting_dashboard'),\n"
    "    path('api/reporting/sync/start/', reporting_api.api_reporting_sync_start, "
    "name='api_reporting_sync_start'),\n"
)


def _read(path: Path) -> str:
    if not path.is_file():
        print(f'FEHLER: {path} nicht gefunden', file=sys.stderr)
        sys.exit(1)
    return path.read_text(encoding='utf-8')


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding='utf-8')


def install_api(backend: Path, snippet: Path) -> None:
    dest = backend / API_FILE
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(snippet, dest)
    print(f'OK: {dest} installiert')


def cleanup_views(views_path: Path) -> None:
    if not views_path.is_file():
        print('views.py: nicht vorhanden — übersprungen')
        return
    text = _read(views_path)
    changed = False

    if MARKER in text:
        text = text[:text.index(MARKER)].rstrip() + '\n'
        changed = True
        print('views.py: alter reporting-Anhang entfernt')

    orphan_import = 'from apps.abpe_crm.reporting_api import api_reporting_dashboard, api_reporting_sync_start'
    if orphan_import in text:
        text = text.replace(orphan_import + '\n\n\n', '')
        text = text.replace(orphan_import + '\n\n', '')
        text = text.replace(orphan_import + '\n', '')
        changed = True
        print('views.py: überflüssigen Import entfernt')

    if changed:
        _write(views_path, text)
    else:
        print('views.py: keine Bereinigung nötig')


def _fix_double_commas(text: str) -> str:
    while '),,' in text:
        text = text.replace('),,', '),')
    return text


def _ensure_import(text: str) -> str:
    if 'reporting_api' in text:
        return text
    pairs = [
        ('from . import views', 'from . import views\nfrom apps.abpe_crm import reporting_api'),
        ('from apps.abpe_crm import views', 'from apps.abpe_crm import reporting_api, views'),
    ]
    for old, new in pairs:
        if old in text:
            print('urls.py: import reporting_api ergänzt')
            return text.replace(old, new, 1)
    lines = text.split('\n')
    insert_at = 0
    for i, line in enumerate(lines):
        if line.startswith('from ') or line.startswith('import '):
            insert_at = i + 1
    lines.insert(insert_at, 'from apps.abpe_crm import reporting_api')
    print('urls.py: import reporting_api eingefügt')
    return '\n'.join(lines)


def patch_urls(urls_path: Path) -> None:
    text = _fix_double_commas(_read(urls_path))

    if 'api/reporting/dashboard/' in text:
        _write(urls_path, text)
        print('urls.py: Reporting-Routen bereits vorhanden')
        return

    text = _ensure_import(text)

    needle = "path('api/sync/status/'"
    pos = text.find(needle)
    if pos >= 0:
        line_end = text.find('\n', pos)
        if line_end < 0:
            line_end = len(text)
        else:
            line_end += 1
        text = text[:line_end] + ROUTES + text[line_end:]
        print('urls.py: Routen nach api/sync/status/ eingefügt')
    else:
        close = text.rfind(']')
        if close >= 0:
            text = text[:close] + ROUTES + text[close:]
            print('urls.py: Routen vor urlpatterns-Ende eingefügt')
        else:
            text = text.rstrip() + '\n' + ROUTES
            print('urls.py: Routen ans Dateiende angefügt')

    text = _fix_double_commas(text)
    _write(urls_path, text)


def verify(backend: Path) -> int:
    rc = 0
    api = backend / API_FILE
    urls = backend / URLS_FILE
    if not api.is_file():
        print(f'FEHLER: fehlt {api}', file=sys.stderr)
        rc = 1
    else:
        print(f'OK: {api} vorhanden')
    text = _read(urls)
    if 'api/reporting/dashboard/' not in text:
        print('FEHLER: api/reporting/dashboard/ fehlt in urls.py', file=sys.stderr)
        rc = 1
    else:
        print('OK: urls.py enthält reporting-Routen')
    if 'reporting_api' not in text:
        print('FEHLER: reporting_api-Import fehlt in urls.py', file=sys.stderr)
        rc = 1
    return rc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--backend', default='/opt/abpe/backend')
    parser.add_argument('--snippet', required=True, help='Pfad zu reporting_api.py')
    args = parser.parse_args()

    backend = Path(args.backend)
    snippet = Path(args.snippet)
    if not snippet.is_file():
        print(f'FEHLER: Snippet nicht gefunden: {snippet}', file=sys.stderr)
        return 1

    install_api(backend, snippet)
    cleanup_views(backend / VIEWS_FILE)
    patch_urls(backend / URLS_FILE)

    print()
    rc = verify(backend)
    if rc:
        return rc

    print('\nNächste Schritte:')
    print('  python3 -m py_compile apps/abpe_crm/reporting_api.py apps/abpe_crm/urls.py')
    print('  supervisorctl restart abpe-django')
    print('  curl -sI https://abpe.win.abcona.info/crm/api/reporting/dashboard/ | head -1')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
