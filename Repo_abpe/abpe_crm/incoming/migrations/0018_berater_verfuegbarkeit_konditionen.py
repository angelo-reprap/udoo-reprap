"""CRM-Stammdaten: eingeschränkte Verfügbarkeit + Remote/vor-Ort-Sätze.

Echte DB-Spalten (kein JSON). Läuft nach Live-Leaf 0017_crmusersettings_timezone.
Spalten per ADD COLUMN IF NOT EXISTS (idempotent).
"""
from django.db import migrations, connection


COLUMNS = [
    ('verfuegbar_tage_pro_woche_c', 'smallint NULL'),
    ('verfuegbar_hinweis_c', 'varchar(255) NULL'),
    ('satz_remote_c', 'numeric(8,2) NULL'),
    ('satz_vor_ort_c', 'numeric(8,2) NULL'),
]

CANDIDATE_TABLES = (
    'abpe_crm_crmcontactcstm',
    'contacts_cstm',
)


def _add_columns(apps, schema_editor):
    with connection.cursor() as cur:
        existing = set(connection.introspection.table_names())
        for table in CANDIDATE_TABLES:
            if table not in existing:
                continue
            for col, ddl in COLUMNS:
                cur.execute(
                    f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {ddl}'
                )


def _noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        # Live-Leaf auf ucs5 (siehe migrate-Konflikt-Meldung)
        ('abpe_crm', '0017_crmusersettings_timezone'),
    ]

    operations = [
        migrations.RunPython(_add_columns, _noop),
    ]
