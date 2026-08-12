# -*- coding: utf-8 -*-
"""
apps/abpe_crm/management/commands/content_reindex.py
================================================================================
Baut/fuellt den Personen-Index `content` (abpe_content).

Erst-Befuellung und Reparatur. Loescht optional den Index und legt ihn mit
Mapping neu an, dann werden alle CrmContact-Datensaetze indexiert.

    python manage.py content_reindex --rebuild     # Index neu + alle Personen
    python manage.py content_reindex               # nur fehlende/aktualisieren
    python manage.py content_reindex --limit 100   # Test mit 100
================================================================================
"""
import time

from django.core.management.base import BaseCommand
from apps.abpe_crm.models import CrmContact
from apps.abpe_crm.documents_content import ContentPersonIndex


class Command(BaseCommand):
    help = "Baut/fuellt den Personen-Index `content`."

    def add_arguments(self, parser):
        parser.add_argument("--rebuild", action="store_true",
                            help="Index loeschen und neu anlegen.")
        parser.add_argument("--limit", type=int, default=0,
                            help="Nur die ersten N (Test).")
        parser.add_argument("--batch", type=int, default=500,
                            help="Bulk-Batchgroesse.")

    def handle(self, *args, **opts):
        rebuild = opts["rebuild"]
        limit = opts["limit"]
        batch = opts["batch"]

        idx = ContentPersonIndex._index

        if rebuild:
            self.stdout.write("Loesche und erstelle Index neu ...")
            try:
                idx.delete(ignore=404)
            except Exception as e:
                self.stdout.write(f"  (delete: {e})")
            idx.create()
            self.stdout.write("  Index + Mapping angelegt.")

        qs = CrmContact.objects.all().order_by("id")
        total = qs.count()
        if limit:
            qs = qs[:limit]
        anzahl = min(limit, total) if limit else total

        self.stdout.write(f"Indexiere {anzahl:,} Person(en) ...")
        doc = ContentPersonIndex()

        ok = 0
        t0 = time.perf_counter()
        buffer = []

        def flush(objs):
            if not objs:
                return
            doc.update(objs, action="index")

        for c in qs.iterator(chunk_size=batch):
            buffer.append(c)
            if len(buffer) >= batch:
                flush(buffer)
                ok += len(buffer)
                buffer = []
                el = time.perf_counter() - t0
                rate = ok / el if el else 0
                rest = (anzahl - ok) / rate / 60 if rate else 0
                self.stdout.write(
                    f"  [{ok}/{anzahl}] {rate:.0f} Pers/s | Rest ~{rest:.1f} min")

        flush(buffer)
        ok += len(buffer)

        el = time.perf_counter() - t0
        self.stdout.write(self.style.SUCCESS(
            f"Fertig. {ok:,} Personen indexiert in {el:.0f}s "
            f"({ok/el:.0f} Pers/s)."))

