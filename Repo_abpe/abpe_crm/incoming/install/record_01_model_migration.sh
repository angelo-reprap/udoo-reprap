#!/bin/bash
# ============================================================
# record_01_model_migration.sh
# ABpE Call Recording — Etappe 1a: CrmCallRecording Model + Migration
# Idempotent: prüft ob Model schon da ist, macht Backup, fügt an, makemigrations.
# Führt KEIN migrate aus — das macht Angelo kontrolliert nach Prüfung.
# ============================================================
set -e
cd /opt/abpe/backend

MODELS="apps/abpe_crm/models.py"

echo "=== [1/4] Backup models.py ==="
python3 Archiv/backup_restore.py -save "$MODELS" -m "record_01: vor CrmCallRecording model"

echo "=== [2/4] Model anhängen (falls noch nicht vorhanden) ==="
python3 - << 'PYEOF'
p = 'apps/abpe_crm/models.py'
s = open(p, encoding='utf-8').read()

if 'class CrmCallRecording' in s:
    print("  CrmCallRecording existiert schon — übersprungen.")
else:
    model = '''

# ============================================================
# CrmCallRecording  (NEU — Anruf-Aufnahmen, Zuordnung lebt in DB)
# ============================================================

class CrmCallRecording(models.Model):
    """Anruf-Aufnahme. Die WAV behält ihren Original-Namen (PBX = lokal),
    die Zuordnung zu Contact/Account ist eine DB-Spalte (jederzeit korrigierbar,
    ohne die Datei anzufassen). Siehe Archiv/Call_record_future_architecture_v1.md"""
    filename        = models.CharField(max_length=255, unique=True, db_index=True)
    pbx_path        = models.CharField(max_length=500)
    local_path      = models.CharField(max_length=500, blank=True, null=True)
    extension       = models.CharField(max_length=10, db_index=True)
    caller_number   = models.CharField(max_length=50, blank=True, null=True, db_index=True)

    # Zuordnung (Kern — in der DB, nie im Dateinamen)
    contact_crm_id  = models.CharField(max_length=36, blank=True, null=True, db_index=True)
    account_crm_id  = models.CharField(max_length=36, blank=True, null=True, db_index=True)
    subject         = models.CharField(max_length=255, blank=True, null=True)
    is_assigned     = models.BooleanField(default=False, db_index=True)
    is_private      = models.BooleanField(default=False)

    # Metadaten
    recorded_at     = models.DateTimeField(db_index=True)
    duration_sec    = models.IntegerField(null=True, blank=True)
    file_size       = models.BigIntegerField(null=True, blank=True)
    synced_at       = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Anruf-Aufnahme'
        verbose_name_plural = 'Anruf-Aufnahmen'
        ordering            = ['-recorded_at']
        indexes = [
            models.Index(fields=['contact_crm_id']),
            models.Index(fields=['account_crm_id']),
            models.Index(fields=['is_assigned', 'recorded_at']),
        ]

    def __str__(self):
        return f"{self.filename} ({self.recorded_at})"


class CrmExtensionOwner(models.Model):
    """Mapping Extension -> Person (CRM-Contact). Konfigurierbar, für Default-
    Zuordnung nicht-aufgelöster Aufnahmen. Kein Hardcoding."""
    extension      = models.CharField(max_length=10, unique=True, db_index=True)
    contact_crm_id = models.CharField(max_length=36, blank=True, null=True)
    label          = models.CharField(max_length=100, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Extension-Besitzer'
        verbose_name_plural = 'Extension-Besitzer'

    def __str__(self):
        return f"{self.extension} -> {self.label or self.contact_crm_id or '?'}"
'''
    # Vor dem CDR-Import-Block anhängen (falls vorhanden), sonst ans Ende
    marker = '# ── CDR-Spiegel'
    if marker in s:
        idx = s.find(marker)
        s = s[:idx] + model + '\n\n' + s[idx:]
    else:
        s = s.rstrip() + '\n' + model + '\n'
    open(p, 'w', encoding='utf-8').write(s)
    print("  CrmCallRecording + CrmExtensionOwner angehängt.")
PYEOF

echo "=== [3/4] Syntax-Check ==="
python3 -c "import ast; ast.parse(open('$MODELS').read()); print('  models.py syntaktisch OK')"

echo "=== [4/4] Migration generieren (NUR makemigrations, KEIN migrate!) ==="
python manage.py makemigrations abpe_crm 2>&1 | tail -8

echo ""
echo "============================================================"
echo "✅ record_01 fertig."
echo ""
echo "NÄCHSTER SCHRITT (manuell, kontrolliert):"
echo "  1. Migration prüfen: python manage.py sqlmigrate abpe_crm <nummer>"
echo "  2. Wenn ok:          python manage.py migrate abpe_crm"
echo ""
echo "Danach: record_02_sync_endpoint.sh"
echo "============================================================"

