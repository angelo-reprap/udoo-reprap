#!/usr/bin/env python3
"""JS-Patch fuer mod-crm-pbx.js — auf ucs5 nach Backup ausfuehren."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

BACKEND = Path('/opt/abpe/backend')
PKG = Path(__file__).resolve().parent
PATCHED = PKG / 'incoming' / 'mod-crm-pbx.js'
TARGET = BACKEND / 'apps/abpe_crm/static/abpe_crm/js/mod-crm-pbx.js'


def main():
    root = BACKEND if BACKEND.exists() else Path.cwd()
    src = PATCHED if PATCHED.exists() else root / 'abpe_deepseek_raupe/incoming/mod-crm-pbx.js'
    dst = root / 'apps/abpe_crm/static/abpe_crm/js/mod-crm-pbx.js'
    if not src.exists():
        print('FEHLER: gepatchte mod-crm-pbx.js nicht gefunden:', src)
        sys.exit(1)
    if not dst.parent.exists():
        print('FEHLER: Ziel nicht gefunden:', dst)
        sys.exit(1)
    if '_mmRaupeRequest' not in src.read_text(encoding='utf-8'):
        print('FEHLER: Quelldatei enthaelt keinen Raupe-Patch')
        sys.exit(1)
    shutil.copy2(src, dst)
    print('OK', dst)
    print('Danach: python manage.py collectstatic --noinput')


if __name__ == '__main__':
    main()
