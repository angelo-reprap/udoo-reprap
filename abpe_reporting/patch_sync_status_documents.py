#!/usr/bin/env python3
"""api_sync_status: documents_total aus EDMS korrigieren (falls 0 obwohl EDMS voll).

Usage:
  cd /opt/abpe/backend
  python3 patch_sync_status_documents.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

VIEWS = Path('apps/abpe_crm/views.py')
OLD = "'documents_total': CrmDocument.objects.count(),"
NEW = "'documents_total': __rep_doc_count(),"


def __rep_doc_count():
    try:
        from apps.abpe_edms.models import CrmDocument
        return CrmDocument.objects.count()
    except Exception:
        return 0


def patch() -> int:
    path = VIEWS
    if not path.is_file():
        print(f'FEHLER: {path} nicht gefunden', file=sys.stderr)
        return 1
    text = path.read_text(encoding='utf-8')
    helper = '''

def __rep_doc_count():
    try:
        from apps.abpe_edms.models import CrmDocument
        return CrmDocument.objects.count()
    except Exception:
        return 0
'''
    if OLD not in text:
        if NEW in text or '__rep_doc_count' in text:
            print('OK: bereits gepatcht')
            return 0
        print('WARNUNG: documents_total-Zeile nicht gefunden — manuell prüfen', file=sys.stderr)
        return 1
    if '__rep_doc_count' not in text:
        m = re.search(r'\ndef api_sync_status\(', text)
        if m:
            text = text[:m.start()] + helper + text[m.start():]
        else:
            text = helper + text
    text = text.replace(OLD, NEW, 1)
    path.write_text(text, encoding='utf-8')
    print(f'OK: {path} — documents_total nutzt EDMS CrmDocument')
    return 0


if __name__ == '__main__':
    raise SystemExit(patch())
