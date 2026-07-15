#!/usr/bin/env python3
"""api_sync_status: documents_total aus EDMS korrigieren (falls 0 obwohl EDMS voll).

Repariert auch fehlerhafte Patches, die __rep_doc_count() ohne request aufgerufen haben
(Kollision mit bestehender __rep_doc_count(request)-Funktion in views.py).

Usage:
  cd /opt/abpe/backend
  curl -sL 'https://raw.githubusercontent.com/angelo-reprap/udoo-reprap/cursor/reporting-overhaul-c24e/abpe_reporting/patch_sync_status_documents.py' -o /tmp/patch_sync_status_documents.py
  python3 /tmp/patch_sync_status_documents.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

VIEWS = Path('apps/abpe_crm/views.py')
HELPER = '_crm_edms_document_count'
NEW = f"'documents_total': {HELPER}(),"
OLD_RE = re.compile(
    r"(['\"]documents_total['\"]\s*:\s*)CrmDocument\.objects\.count\(\)\s*,",
)
BROKEN_RE = re.compile(
    r"(['\"]documents_total['\"]\s*:\s*)__rep_doc_count\s*\(\s*\)\s*,",
)

HELPER_BLOCK = f'''

def {HELPER}():
    """EDMS-Dokumente zählen (api_sync_status, ohne Request)."""
    try:
        from apps.abpe_edms.models import CrmDocument
        return CrmDocument.objects.count()
    except Exception:
        return 0
'''

# Fehlerhafter Helper aus erstem Patch-Versuch (Namenskollision mit __rep_doc_count(request))
BROKEN_HELPER = re.compile(
    r'\n\ndef __rep_doc_count\(\):\n'
    r'    try:\n'
    r'        from apps\.abpe_edms\.models import CrmDocument\n'
    r'        return CrmDocument\.objects\.count\(\)\n'
    r'    except Exception:\n'
    r'        return 0\n',
    re.MULTILINE,
)


def _insert_helper(text: str) -> str:
    if f'def {HELPER}(' in text:
        return text
    m = re.search(r'\ndef api_sync_status\(', text)
    if m:
        return text[: m.start()] + HELPER_BLOCK + text[m.start() :]
    return HELPER_BLOCK + text


def patch() -> int:
    path = VIEWS
    if not path.is_file():
        print(f'FEHLER: {path} nicht gefunden', file=sys.stderr)
        return 1

    text = path.read_text(encoding='utf-8')
    changed = False

    if BROKEN_HELPER.search(text):
        text = BROKEN_HELPER.sub('\n', text, count=1)
        changed = True
        print('OK: fehlerhaften __rep_doc_count()-Helper entfernt')

    broken_m = BROKEN_RE.search(text)
    if broken_m:
        text = BROKEN_RE.sub(NEW, text, count=1)
        changed = True
        print('OK: __rep_doc_count()-Aufruf durch _crm_edms_document_count() ersetzt')

    if NEW in text and f'def {HELPER}(' in text:
        if not changed:
            print('OK: bereits gepatcht')
        else:
            text = _insert_helper(text)
        path.write_text(text, encoding='utf-8')
        return 0

    old_m = OLD_RE.search(text)
    if old_m:
        text = _insert_helper(text)
        text = OLD_RE.sub(NEW, text, count=1)
        path.write_text(text, encoding='utf-8')
        print(f'OK: {path} — documents_total nutzt EDMS via {HELPER}()')
        return 0

    if NEW in text and f'def {HELPER}(' not in text:
        text = _insert_helper(text)
        path.write_text(text, encoding='utf-8')
        print(f'OK: {path} — {HELPER}() Helper ergänzt')
        return 0

    print(
        'WARNUNG: documents_total-Zeile nicht gefunden — manuell prüfen '
        f'(erwartet OLD, BROKEN oder NEW)',
        file=sys.stderr,
    )
    return 1


if __name__ == '__main__':
    raise SystemExit(patch())
