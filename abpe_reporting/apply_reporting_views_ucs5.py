#!/usr/bin/env python3
"""Reporting-API auf ucs5 installieren (reporting_api.py + urls + views-Import).

Usage:
  cd /opt/abpe/backend
  python3 apply_reporting_views_ucs5.py --snippet /tmp/reporting_api.py
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

VIEWS_FILE = Path('apps/abpe_crm/views.py')
URLS_FILE = Path('apps/abpe_crm/urls.py')
API_FILE = Path('apps/abpe_crm/reporting_api.py')
MARKER = '# --- reporting dashboard (auto) ---'
IMPORT_LINE = (
    'from apps.abpe_crm.reporting_api import api_reporting_dashboard, api_reporting_sync_start'
)
ROUTES = """    path('api/reporting/dashboard/', views.api_reporting_dashboard, name='api_reporting_dashboard'),
    path('api/reporting/sync/start/', views.api_reporting_sync_start, name='api_reporting_sync_start'),
"""


def _read(path: Path) -> str:
    if not path.is_file():
        print(f'FEHLER: {path} nicht gefunden', file=sys.stderr)
        sys.exit(1)
    return path.read_text(encoding='utf-8')


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding='utf-8')


def _remove_old_appended_block(text: str) -> str:
    if MARKER not in text:
        return text
    idx = text.index(MARKER)
    cleaned = text[:idx].rstrip() + '\n'
    print('views.py: alter reporting-Anhang entfernt')
    return cleaned


def patch_views(views_path: Path) -> None:
    text = _read(views_path)
    text = _remove_old_appended_block(text)
    if IMPORT_LINE not in text:
        if 'def api_sync_status' in text:
            text = text.replace(
                'def api_sync_status',
                IMPORT_LINE + '\n\n\ndef api_sync_status',
                1,
            )
        else:
            text = IMPORT_LINE + '\n\n' + text
        print(f'OK: {views_path} — Import ergänzt')
    else:
        print('views.py: Import bereits vorhanden')

    _write(views_path, text)


def _fix_double_commas(text: str) -> str:
    fixed = re.sub(r'\),\s*,', '),', text)
    if fixed != text:
        print('urls.py: doppelte Kommata bereinigt')
    return fixed


def patch_urls(urls_path: Path) -> None:
    text = _read(urls_path)
    text = _fix_double_commas(text)
    if 'api_reporting_dashboard' in text:
        _write(urls_path, text)
        print('urls.py: Reporting-Routen bereits vorhanden')
        return

    pattern = r"(path\('api/sync/status/'[^\n]*\n)"
    if re.search(pattern, text):
        text = re.sub(pattern, r'\1' + ROUTES, text, count=1)
    else:
        text = text.rstrip() + '\n' + ROUTES + '\n'
    text = _fix_double_commas(text)
    _write(urls_path, text)
    print(f'OK: {urls_path} — Reporting-Routen ergänzt')


def install_api(backend: Path, snippet: Path) -> None:
    dest = backend / API_FILE
    shutil.copy2(snippet, dest)
    print(f'OK: {dest} installiert')


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
    patch_views(backend / VIEWS_FILE)
    patch_urls(backend / URLS_FILE)

    print('\nPrüfen:')
    print('  python -m py_compile apps/abpe_crm/reporting_api.py apps/abpe_crm/urls.py')
    print('  supervisorctl restart abpe-django')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
