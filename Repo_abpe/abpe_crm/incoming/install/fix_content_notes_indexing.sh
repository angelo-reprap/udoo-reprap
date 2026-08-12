#!/bin/bash
# ============================================================
# fix_content_notes_indexing.sh
# Fix: CrmContactNote-Aenderungen wurden nie in Elasticsearch
# reindiziert, weil documents_content.py/documents_content_firma.py
# von django_elasticsearch_dsl's Auto-Discovery nie gefunden wurden
# (erwartet exakt den Dateinamen "documents.py", nicht
# "documents_content*.py"). ready() in apps.py war ein reines "pass".
# Fix: Explizit importieren in ready(), damit @registry.register_document
# tatsaechlich laeuft und der RealTimeSignalProcessor greift.
# Danach einmaliger voller Reindex, um historisch verpasste Notizen
# (inkl. der beiden aus dem Screenshot) nachzuholen.
# ============================================================
set -e
cd /opt/abpe/backend

APPS="apps/abpe_crm/apps.py"

echo "=== [1/6] Backup apps.py ==="
python3 Archiv/backup_restore.py -save "$APPS" -m "fix: documents_content Registry-Import in ready()"

echo "=== [2/6] ready() patchen ==="
python3 - << 'PYEOF'
p = 'apps/abpe_crm/apps.py'
s = open(p, encoding='utf-8').read()

OLD = '''    def ready(self):
        pass'''

NEW = '''    def ready(self):
        # documents_content.py / documents_content_firma.py heissen nicht
        # "documents.py" -> django_elasticsearch_dsl's Auto-Discovery findet
        # sie nie von allein. Explizit importieren, damit
        # @registry.register_document tatsaechlich laeuft und der
        # RealTimeSignalProcessor bei CrmContactNote/CrmContact/CrmAccount
        # etc. greift.
        from . import documents_content        # noqa: F401
        from . import documents_content_firma   # noqa: F401'''

assert s.count(OLD) == 1, f"Anker {s.count(OLD)}x gefunden statt 1"
s = s.replace(OLD, NEW)
open(p, 'w', encoding='utf-8').write(s)
print("  ready() gepatcht.")
PYEOF

echo "=== [3/6] Syntax-Check ==="
python3 -c "import ast; ast.parse(open('$APPS').read()); print('  apps.py OK')"

echo "=== [4/6] Restart, damit ready() erneut laeuft ==="
supervisorctl restart abpe-django
sleep 2

echo "=== [5/6] Registry-Check: stehen die Document-Klassen jetzt drin? ==="
python3 -c "
import sys; sys.path.insert(0, '/opt/abpe/backend')
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
from django_elasticsearch_dsl.registries import registry
docs = list(registry.get_documents())
print('Registrierte Documents:', [d.__name__ for d in docs])
assert len(docs) > 1, 'Immer noch nur ein Document registriert - Fix hat nicht gegriffen!'
"

echo "=== [6/6] Vollstaendiger Reindex (holt historische Notizen nach, inkl. der beiden aus dem Screenshot) ==="
python manage.py content_reindex
python manage.py content_firma_reindex

echo ""
echo "============================================================"
echo "✅ Fix + Reindex fertig."
echo "Bitte jetzt in der UI nach 'die4isthier' suchen - sollte jetzt"
echo "gefunden werden. Neue Notizen sollten ab sofort live erscheinen,"
echo "ohne manuellen Reindex."
echo "============================================================"
