#!/bin/bash
# HOTFIX: Email Studio 500 nach Nav-Deploy
# Ursache: views.py wurde komplett überschrieben — Live-Code ≠ Repo.
# Lösung: Restore vom Backup, dann nur Nav-Zeilen patchen.
#
# Ausführen auf ucs5:
#   cd /opt/abpe/backend && bash /mnt/public/udoo-reprap/Repo_abpe/abpe_ui/incoming/modules/email/HOTFIX-rollback.sh

set -e
cd /opt/abpe/backend
BR="python3 Archiv/backup_restore.py"

echo "=== 1. views.py auf Stand VOR Nav-Deploy zurücksetzen ==="
$BR -restore apps/abpe_email_studio/views.py --version 20260715_152726

echo "=== 2. Nur Nav-Zeilen in _base_context patchen ==="
python3 << 'PY'
from pathlib import Path

views = Path('apps/abpe_email_studio/views.py')
text = views.read_text()
old = "'active_module': 'email_studio',"
new = """'active_module': 'email',
        'active':        'email',
        'active_subpage': 'studio',"""
if old in text:
    views.write_text(text.replace(old, new, 1))
    print('✓ email_studio _base_context gepatcht')
elif "'active_module': 'email'," in text:
    print('✓ email_studio bereits gepatcht')
else:
    print('⚠ active_module nicht gefunden — manuell prüfen')
PY

echo "=== 3. CRM compose — active_subpage ==="
$BR -restore apps/abpe_crm/views.py --version 20260715_152726
python3 << 'PY'
from pathlib import Path

crm = Path('apps/abpe_crm/views.py')
text = crm.read_text()
needle = "'signatures_list': list(signatures),"
insert = """'signatures_list': list(signatures),
        'active':         'email',
        'active_subpage': 'compose',"""
if "'active_subpage': 'compose'" in text:
    print('✓ crm bereits gepatcht')
elif needle in text:
    crm.write_text(text.replace(needle, insert, 1))
    print('✓ crm_email_compose gepatcht')
else:
    print('⚠ signatures_list nicht gefunden — manuell prüfen')
PY

echo "=== 4. Django neu starten ==="
supervisorctl restart abpe-django

echo ""
echo "Fertig. Prüfen: https://abpe.win.abcona.info/email-studio/"
echo "Nav-Gruppe (module.json, scanner, sidebar) bleibt aktiv."
