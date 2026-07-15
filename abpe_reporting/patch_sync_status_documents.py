#!/usr/bin/env python3
"""api_sync_status: documents_total aus EDMS (inline, ohne Helper — keine Namenskollision).

Repariert fehlerhafte Patches mit __rep_doc_count() / _crm_edms_document_count(),
die mit bestehenden View-Funktionen(request) in views.py kollidieren.

Usage:
  cd /opt/abpe/backend
  curl -fsSL 'https://raw.githubusercontent.com/angelo-reprap/udoo-reprap/cursor/reporting-overhaul-c24e/abpe_reporting/patch_sync_status_documents.py' -o /tmp/patch_sync_status_documents.py
  python3 /tmp/patch_sync_status_documents.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

VIEWS = Path('apps/abpe_crm/views.py')
MARKER = '_sync_documents_total'

INJECT = '''    try:
        from apps.abpe_edms.models import CrmDocument as _EdmsCrmDocument
        _sync_documents_total = _EdmsCrmDocument.objects.count()
    except Exception:
        _sync_documents_total = 0
'''

DOC_TOTAL_RE = re.compile(
    r"(['\"]documents_total['\"]\s*:\s*)"
    r"(?:CrmDocument\.objects\.count\(\)|__rep_doc_count\s*\(\s*\)|_crm_edms_document_count\s*\(\s*\))\s*,",
)

# Fehlerhafte no-arg Helper aus früheren Patch-Versuchen entfernen
BAD_HELPERS = (
    re.compile(
        r'\n\ndef __rep_doc_count\(\):\n'
        r'    try:\n'
        r'        from apps\.abpe_edms\.models import CrmDocument\n'
        r'        return CrmDocument\.objects\.count\(\)\n'
        r'    except Exception:\n'
        r'        return 0\n',
        re.MULTILINE,
    ),
    re.compile(
        r'\n\ndef _crm_edms_document_count\(\):\n'
        r'    """EDMS-Dokumente zählen \(api_sync_status, ohne Request\)\."""\n'
        r'    try:\n'
        r'        from apps\.abpe_edms\.models import CrmDocument\n'
        r'        return CrmDocument\.objects\.count\(\)\n'
        r'    except Exception:\n'
        r'        return 0\n',
        re.MULTILINE,
    ),
    re.compile(
        r'\n\ndef _crm_edms_document_count\(\):\n'
        r'    try:\n'
        r'        from apps\.abpe_edms\.models import CrmDocument\n'
        r'        return CrmDocument\.objects\.count\(\)\n'
        r'    except Exception:\n'
        r'        return 0\n',
        re.MULTILINE,
    ),
)

API_SYNC_HEAD = re.compile(
    r'(def api_sync_status\(request\):\n(?:    """.*?"""\n|    \'\'\'.*?\'\'\'\n)?)',
    re.DOTALL,
)


def _already_patched(text: str) -> bool:
    return bool(
        re.search(
            rf"documents_total['\"]\s*:\s*{re.escape(MARKER)}\s*,",
            text,
        )
        and MARKER in text
        and 'def api_sync_status' in text
    )


def _inject_block(text: str) -> str:
    m = API_SYNC_HEAD.search(text)
    if not m:
        return text
    body_start = m.end()
    before_return = text[body_start : body_start + 400].split('return', 1)[0]
    if MARKER in before_return:
        return text
    return text[:body_start] + INJECT + text[body_start:]


def patch() -> int:
    path = VIEWS
    if not path.is_file():
        print(f'FEHLER: {path} nicht gefunden', file=sys.stderr)
        return 1

    text = path.read_text(encoding='utf-8')
    changed = False

    for bad in BAD_HELPERS:
        if bad.search(text):
            text = bad.sub('\n', text, count=1)
            changed = True
            print('OK: fehlerhaften no-arg Helper entfernt')

    if _already_patched(text):
        if changed:
            path.write_text(text, encoding='utf-8')
        else:
            print('OK: bereits gepatcht (inline _sync_documents_total)')
        return 0

    if not DOC_TOTAL_RE.search(text):
        print(
            'WARNUNG: documents_total-Zeile nicht erkannt — grep api_sync_status prüfen',
            file=sys.stderr,
        )
        return 1

    text = _inject_block(text)
    text = DOC_TOTAL_RE.sub(rf"\1{MARKER},", text, count=1)
    path.write_text(text, encoding='utf-8')
    print(f'OK: {path} — documents_total inline via EDMS ({MARKER})')
    return 0


if __name__ == '__main__':
    raise SystemExit(patch())
