#!/usr/bin/env python3
"""Reporting-API in apps/abpe_crm/views.py + urls.py einspielen (ucs5).

Usage:
  cd /opt/abpe/backend
  python3 /tmp/apply_reporting_views_ucs5.py --repo /mnt/public/Repo_abpe
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

VIEWS_FILE = Path('apps/abpe_crm/views.py')
URLS_FILE = Path('apps/abpe_crm/urls.py')
MARKER = '# --- reporting dashboard (auto) ---'


def _read(path: Path) -> str:
    if not path.is_file():
        print(f'FEHLER: {path} nicht gefunden', file=sys.stderr)
        sys.exit(1)
    return path.read_text(encoding='utf-8')


def patch_views(views_path: Path, snippet_path: Path) -> None:
    text = _read(views_path)
    if 'def api_reporting_dashboard' in text:
        print('views.py: api_reporting_dashboard bereits vorhanden — übersprungen')
        return
    snippet = snippet_path.read_text(encoding='utf-8')
    # Nur Funktionen ab _iso (ohne Modul-Docstring)
    idx = snippet.find('def _iso(')
    body = snippet[idx:] if idx >= 0 else snippet
    text = text.rstrip() + '\n\n' + MARKER + '\n' + body + '\n'
    views_path.write_text(text, encoding='utf-8')
    print(f'OK: {views_path} — Reporting-Funktionen angehängt')


def patch_urls(urls_path: Path) -> None:
    text = _read(urls_path)
    if 'api_reporting_dashboard' in text:
        print('urls.py: Reporting-Routen bereits vorhanden — übersprungen')
        return
    routes = """
    path('api/reporting/dashboard/', views.api_reporting_dashboard, name='api_reporting_dashboard'),
    path('api/reporting/sync/start/', views.api_reporting_sync_start, name='api_reporting_sync_start'),
"""
    m = re.search(r'(path\(\'api/sync/status/\'', text)
    if m:
        insert_at = text.find('\n', m.start())
        text = text[:insert_at] + ',' + routes + text[insert_at:]
    else:
        text = text.rstrip() + '\n' + routes + '\n'
    urls_path.write_text(text, encoding='utf-8')
    print(f'OK: {urls_path} — Reporting-Routen ergänzt')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--backend', default='/opt/abpe/backend')
    parser.add_argument('--snippet', default='abpe_reporting/incoming/reporting_views.py')
    args = parser.parse_args()
    backend = Path(args.backend)
    snippet = Path(args.snippet)
    if not snippet.is_file():
        snippet = backend / args.snippet
    patch_views(backend / VIEWS_FILE, snippet)
    patch_urls(backend / URLS_FILE)
    print('\nNächster Schritt: supervisorctl restart abpe-django  # oder gunicorn reload')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
