#!/usr/bin/env python3
"""api_sync_status: documents_total aus EDMS (inline in api_sync_status only).

Usage:
  cd /opt/abpe/backend
  python3 patch_sync_status_documents.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

VIEWS = Path('apps/abpe_crm/views.py')
MARKER = '_sync_documents_total'
PATCH_VERSION = 'v4'

INJECT = '''    try:
        from apps.abpe_edms.models import CrmDocument as _EdmsCrmDocument
        _sync_documents_total = _EdmsCrmDocument.objects.count()
    except Exception:
        _sync_documents_total = 0
'''

DOC_TOTAL_BROKEN = re.compile(
    r"(['\"]documents_total['\"]\s*:\s*)"
    r"(?:CrmDocument\.objects\.count\(\)|__rep_doc_count\s*\(\s*\)|_crm_edms_document_count\s*\(\s*\))\s*,",
)

DOC_TOTAL_OK = re.compile(
    rf"documents_total['\"]\s*:\s*{re.escape(MARKER)}\s*,",
)

API_SYNC_FN = re.compile(
    r'def api_sync_status\(request\):.*?(?=\n(?:def |@\w|\Z))',
    re.DOTALL,
)

API_SYNC_HEAD = re.compile(
    r'(def api_sync_status\(request\):\n(?:    """.*?"""\n|    \'\'\'.*?\'\'\'\n)?)',
    re.DOTALL,
)

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
        r'(?:    """.*?"""\n)?'
        r'    try:\n'
        r'        from apps\.abpe_edms\.models import CrmDocument\n'
        r'        return CrmDocument\.objects\.count\(\)\n'
        r'    except Exception:\n'
        r'        return 0\n',
        re.MULTILINE,
    ),
)


def _remove_bad_helpers(text: str) -> tuple[str, int]:
    removed = 0
    for bad in BAD_HELPERS:
        while bad.search(text):
            text = bad.sub('\n', text, count=1)
            removed += 1
    return text, removed


def _patch_api_sync_block(block: str) -> str:
    if DOC_TOTAL_OK.search(block):
        return block

    head = API_SYNC_HEAD.match(block)
    if not head:
        return block

    rest = block[head.end() :]
    before_return = rest.split('return', 1)[0]
    if MARKER not in before_return:
        rest = INJECT + rest

    rest = DOC_TOTAL_BROKEN.sub(rf'\1{MARKER},', rest, count=1)
    return head.group(1) + rest


def patch() -> int:
    print(f'patch_sync_status_documents {PATCH_VERSION}')
    path = VIEWS
    if not path.is_file():
        print(f'FEHLER: {path} nicht gefunden', file=sys.stderr)
        return 1

    text = path.read_text(encoding='utf-8')
    text, removed = _remove_bad_helpers(text)
    if removed:
        print(f'OK: {removed} fehlerhafte no-arg Helper entfernt')

    m = API_SYNC_FN.search(text)
    if not m:
        print('FEHLER: def api_sync_status(request) nicht gefunden', file=sys.stderr)
        return 1

    block = m.group(0)
    if DOC_TOTAL_OK.search(block) and MARKER in block.split('return', 1)[0]:
        if removed:
            path.write_text(text, encoding='utf-8')
        print('OK: api_sync_status bereits korrekt')
        return 0

    if not DOC_TOTAL_BROKEN.search(block):
        print(
            'WARNUNG: documents_total in api_sync_status nicht erkannt — bitte manuell prüfen',
            file=sys.stderr,
        )
        print(block[:500], file=sys.stderr)
        return 1

    new_block = _patch_api_sync_block(block)
    if new_block == block:
        print('FEHLER: Patch konnte api_sync_status nicht ändern', file=sys.stderr)
        return 1

    text = text[: m.start()] + new_block + text[m.end() :]
    path.write_text(text, encoding='utf-8')
    print(f'OK: {path} — api_sync_status nutzt inline EDMS ({MARKER})')
    return 0


if __name__ == '__main__':
    raise SystemExit(patch())
