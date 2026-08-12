#!/bin/bash
# ============================================================
# wavnotes_01_model_migration.sh
# WAV-Notizen — Etappe 1: CrmContactNote um 3 Felder erweitern
# (kein neues Modell — CrmContactNote wird bereits automatisch in ES
# indexiert ueber documents_content.py/documents_content_firma.py/
# abpe_edms/documents.py). Idempotent, macht Backup, nur makemigrations.
# ============================================================
set -e
cd /opt/abpe/backend

MODELS="apps/abpe_crm/models.py"

echo "=== [1/4] Backup models.py ==="
python3 Archiv/backup_restore.py -save "$MODELS" -m "wavnotes_01: vor CrmContactNote Erweiterung"

echo "=== [2/4] Felder anhaengen (idempotent) ==="
python3 - << 'PYEOF'
p = 'apps/abpe_crm/models.py'
s = open(p, encoding='utf-8').read()

if 'wavnote_mailbox' in s:
    print("  wavnote_mailbox existiert schon — uebersprungen.")
else:
    OLD = '''    created_by      = models.CharField(max_length=100, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'CRM Notiz'
'''
    NEW = '''    created_by      = models.CharField(max_length=100, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    # WAV-Notizen (NEU) — Referenz auf Quell-Voicemail, verhindert Doppel-
    # Dokumentation und behaelt den Whisper-Rohtext als Beleg.
    wavnote_mailbox   = models.CharField(max_length=10, blank=True, null=True, db_index=True)
    wavnote_msg_id    = models.CharField(max_length=20, blank=True, null=True)
    wavnote_raw_text  = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name        = 'CRM Notiz'
'''
    assert s.count(OLD) == 1, f"Anker {s.count(OLD)}x gefunden statt 1"
    s = s.replace(OLD, NEW)
    open(p, 'w', encoding='utf-8').write(s)
    print("  3 Felder an CrmContactNote angehaengt.")
PYEOF

echo "=== [3/4] Syntax-Check ==="
python3 -c "import ast; ast.parse(open('$MODELS').read()); print('  models.py syntaktisch OK')"

echo "=== [4/4] Migration generieren (NUR makemigrations, KEIN migrate!) ==="
python manage.py makemigrations abpe_crm 2>&1 | tail -8

echo ""
echo "============================================================"
echo "✅ wavnotes_01 fertig."
echo "NAECHSTER SCHRITT (manuell): python manage.py migrate abpe_crm"
echo "Danach: wavnotes_02_services.sh"
echo "============================================================"
