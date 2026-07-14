#!/usr/bin/env python3
"""Telefonliste-Button aus mod-crm-pbx.js entfernen (ucs5)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

TARGET = Path('/opt/abpe/backend/apps/abpe_crm/static/abpe_crm/js/mod-crm-pbx.js')


def main():
    p = TARGET if TARGET.exists() else Path('apps/abpe_crm/static/abpe_crm/js/mod-crm-pbx.js')
    if not p.exists():
        print('FEHLER: mod-crm-pbx.js nicht gefunden')
        sys.exit(1)
    t = p.read_text(encoding='utf-8')
    if 'Telefonliste' not in t and 'show_phones' not in t and 'TogglePhones' not in t:
        print('= Telefonliste bereits entfernt')
        return
    t2 = re.sub(
        r'\s*<div class="pbx-mm-opt-wrap" style="position:relative;flex:1">\s*'
        r'<button type="button"[^>]*TogglePhones[^>]*>.*?</button>\s*'
        r'<div class="pbx-mm-opt-tip">.*?</div>\s*</div>',
        '',
        t,
        count=1,
        flags=re.DOTALL,
    )
    t2 = t2.replace("showPhones: true, phones: {}", '')
    t2 = t2.replace('st.phones = {};\n        ', '')
    t2 = re.sub(r'\s*this\._mmNotifyLoadPhonesIfNeeded\(m\);\s*', '\n', t2)
    t2 = re.sub(r'\s*this\._mmNotifyRenderPhoneList\(m\);\s*', '\n', t2)
    t2 = re.sub(
        r'\s*<div id="pbx-mm-notify-phonelist"[^>]*></div>\s*',
        '\n',
        t2,
    )
    t2 = re.sub(
        r'\n    _mmNotifyTogglePhones\(checked\) \{.*?\n    \},\n\n    async _mmNotifyLoadPhonesIfNeeded\(m\) \{.*?\n    \},\n\n    _mmNotifyRenderPhoneList\(m\) \{.*?\n    \},',
        '',
        t2,
        count=1,
        flags=re.DOTALL,
    )
    if 'Telefonliste' in t2 or 'TogglePhones' in t2:
        print('FEHLER: Patch unvollständig — bitte curl die Datei aus GitHub')
        sys.exit(1)
    p.write_text(t2, encoding='utf-8')
    print('OK Telefonliste entfernt:', p)


if __name__ == '__main__':
    main()
