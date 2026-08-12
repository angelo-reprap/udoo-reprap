#!/usr/bin/env python3
"""Ensure CRM Terms-columns + MatchingBeraterTerms table exist (idempotent).

Run from Django backend:
  /opt/abpe/venv311/bin/python /path/to/ensure-matching-terms-db.py
or:
  manage.py shell < ensure-matching-terms-db.py  (not preferred)

Designed to be invoked as:
  cd /opt/abpe/backend && DJANGO_SETTINGS_MODULE=... python scripts/...
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

    # MatchingBeraterTerms via migrate (preferred) + verify
    from django.core.management import call_command
    try:
        call_command('migrate', 'abpe_shaduler', '0005', verbosity=1, interactive=False)
    except Exception as exc:
        print(f'WARN migrate abpe_shaduler 0005: {exc}')
        try:
            call_command('migrate', 'abpe_shaduler', verbosity=1, interactive=False)
        except Exception as exc2:
            print(f'WARN migrate abpe_shaduler: {exc2}')

    try:
        call_command('migrate', 'abpe_crm', verbosity=1, interactive=False)
    except Exception as exc:
        print(f'WARN migrate abpe_crm: {exc}')

    # Verify Terms model / table
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

    # Verify CRM columns via ORM (select one row if any)
    try:
        from apps.abpe_crm.models import CrmContactCstm
        c = CrmContactCstm.objects.first()
        if c is not None:
            _ = getattr(c, 'satz_remote_c', None)
            _ = getattr(c, 'verfuegbar_tage_pro_woche_c', None)
            print('OK CrmContactCstm Terms-Felder lesbar')
        else:
            # force a limited query that touches the columns
            list(CrmContactCstm.objects.values_list(
                'satz_remote_c', 'satz_vor_ort_c',
                'verfuegbar_tage_pro_woche_c', 'verfuegbar_hinweis_c',
            )[:1])
            print('OK CrmContactCstm Terms-Felder query ok (leer)')
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
