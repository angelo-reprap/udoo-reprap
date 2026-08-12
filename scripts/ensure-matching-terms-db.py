#!/usr/bin/env python3
"""Ensure CRM Terms-columns + MatchingBeraterTerms table exist (idempotent).

Bypasses Django migration graph conflicts by:
1) raw SQL ADD COLUMN / CREATE TABLE IF NOT EXISTS
2) recording migration rows in django_migrations when safe
3) optional migrate when graph is clean

Run:
  cd /opt/abpe/backend && BACKEND=/opt/abpe/backend \\
    /opt/abpe/venv311/bin/python /path/to/ensure-matching-terms-db.py
"""
from __future__ import annotations

import os
import sys


def main() -> int:
    backend = os.environ.get('BACKEND', '/opt/abpe/backend')
    if backend not in sys.path:
        sys.path.insert(0, backend)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')

    import django
    django.setup()

    from django.db import connection
    from django.utils import timezone

    cols = [
        ('verfuegbar_tage_pro_woche_c', 'smallint NULL'),
        ('verfuegbar_hinweis_c', 'varchar(255) NULL'),
        ('satz_remote_c', 'numeric(8,2) NULL'),
        ('satz_vor_ort_c', 'numeric(8,2) NULL'),
    ]
    tables = ('abpe_crm_crmcontactcstm', 'contacts_cstm')

    existing = set(connection.introspection.table_names())
    with connection.cursor() as cur:
        touched = False
        for table in tables:
            if table not in existing:
                print(f'skip table (fehlt): {table}')
                continue
            for col, ddl in cols:
                cur.execute(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {ddl}')
                print(f'OK column {table}.{col}')
                touched = True
        if not touched:
            print('WARN: keine CRM-cstm-Tabelle gefunden — Spalten nicht angelegt')

        # MatchingBeraterTerms — raw CREATE (unabhängig vom Migrations-Graph)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS abpe_shaduler_matchingberaterterms (
                id uuid PRIMARY KEY,
                created_at timestamptz NOT NULL DEFAULT NOW(),
                updated_at timestamptz NOT NULL DEFAULT NOW(),
                match_id uuid NOT NULL UNIQUE,
                project_id varchar(64) NOT NULL DEFAULT '',
                crm_contact_id varchar(36) NOT NULL DEFAULT '',
                avail_from date NULL,
                avail_days_per_week smallint NULL,
                avail_note varchar(255) NOT NULL DEFAULT '',
                rate_remote numeric(8,2) NULL,
                rate_onsite numeric(8,2) NULL,
                rate_note varchar(255) NOT NULL DEFAULT '',
                updated_by varchar(80) NOT NULL DEFAULT ''
            )
            """
        )
        print('OK CREATE TABLE IF NOT EXISTS abpe_shaduler_matchingberaterterms')
        # Indexes (IF NOT EXISTS)
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS abpe_shadul_crm_con_7f07a1_idx
            ON abpe_shaduler_matchingberaterterms (crm_contact_id, updated_at)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS abpe_shadul_project_7f07a2_idx
            ON abpe_shaduler_matchingberaterterms (project_id)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS abpe_shadul_match_id_7f07a3_idx
            ON abpe_shaduler_matchingberaterterms (match_id)
            """
        )
        print('OK indexes MatchingBeraterTerms')

        # django_migrations bookkeeping — damit spätere migrate nicht erneut CreateModel fährt
        def _record(app: str, name: str) -> None:
            cur.execute(
                'SELECT 1 FROM django_migrations WHERE app=%s AND name=%s LIMIT 1',
                [app, name],
            )
            if cur.fetchone():
                print(f'OK django_migrations schon: {app}.{name}')
                return
            cur.execute(
                'INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, %s)',
                [app, name, timezone.now()],
            )
            print(f'OK django_migrations insert: {app}.{name}')

        # Alte kollidierende Leafs ggf. als angewendet markieren / neue Names
        # 0001_berater… war falsch nummeriert — wenn vorhanden: als applied belassen,
        # neue 0018 zusätzlich recorden (Spalten sind schon da).
        _record('abpe_crm', '0018_berater_verfuegbarkeit_konditionen')
        _record('abpe_shaduler', '0006_matchingberaterterms')

    # Optional: migrate versuchen (nicht fatal)
    from django.core.management import call_command
    for app in ('abpe_shaduler', 'abpe_crm'):
        try:
            call_command('migrate', app, verbosity=1, interactive=False)
            print(f'OK migrate {app}')
        except Exception as exc:
            print(f'WARN migrate {app}: {exc}')

    # Verify
    from django.db.utils import ProgrammingError
    try:
        from apps.abpe_shaduler.models import MatchingBeraterTerms
        n = MatchingBeraterTerms.objects.count()
        print(f'OK MatchingBeraterTerms count={n}')
    except ProgrammingError as exc:
        print(f'FEHLER MatchingBeraterTerms Tabelle fehlt noch: {exc}')
        return 2
    except Exception as exc:
        print(f'WARN MatchingBeraterTerms check: {exc}')
        return 1

    try:
        from apps.abpe_crm.models import CrmContactCstm
        list(CrmContactCstm.objects.values_list(
            'satz_remote_c', 'satz_vor_ort_c',
            'verfuegbar_tage_pro_woche_c', 'verfuegbar_hinweis_c',
        )[:1])
        print('OK CrmContactCstm Terms-Felder query ok')
    except ProgrammingError as exc:
        print(f'FEHLER CRM Terms-Spalten: {exc}')
        return 2
    except Exception as exc:
        print(f'WARN CRM Terms check: {exc}')
        return 1

    print('OK ensure-matching-terms-db fertig')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
