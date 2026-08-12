# -*- coding: utf-8 -*-
"""
apps/abpe_crm/management/commands/content_firma_reindex.py
================================================================================
Baut/fuellt den Firmen-Index `content_firma`.

    python manage.py content_firma_reindex --rebuild     # Index neu + alle Firmen
    python manage.py content_firma_reindex --limit 50    # Test
================================================================================
"""
import time

from django.core.management.base import BaseCommand
from apps.abpe_crm.models import CrmAccount
from apps.abpe_crm.documents_content_firma import ContentAccountIndex


class Command(BaseCommand):
    help = "Baut/fuellt den Firmen-Index `content_firma`."

    def add_arguments(self, parser):
        parser.add_argument("--rebuild", action="store_true")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--batch", type=int, default=500)

    def handle(self, *args, **opts):
        rebuild = opts["rebuild"]
        limit = opts["limit"]
        batch = opts["batch"]

        idx = ContentAccountIndex._index
        if rebuild:
            self.stdout.write("Loesche und erstelle Index neu ...")
            try:
                idx.delete(ignore=404)
            except Exception as e:
                self.stdout.write(f"  (delete: {e})")
            idx.create()
            self.stdout.write("  Index + Mapping angelegt.")

        qs = CrmAccount.objects.all().order_by("id")
        total = qs.count()
        if limit:
            qs = qs[:limit]
        anzahl = min(limit, total) if limit else total

        self.stdout.write(f"Indexiere {anzahl:,} Firma(en) ...")
        doc = ContentAccountIndex()
        ok = 0
        t0 = time.perf_counter()
        buffer = []

        def flush(objs):
            if objs:
                doc.update(objs, action="index")

        for c in qs.iterator(chunk_size=batch):
            buffer.append(c)
            if len(buffer) >= batch:
                flush(buffer)
                ok += len(buffer)
                buffer = []
                el = time.perf_counter() - t0
                rate = ok / el if el else 0
                self.stdout.write(f"  [{ok}/{anzahl}] {rate:.0f} Firmen/s")

        flush(buffer)
        ok += len(buffer)
        el = time.perf_counter() - t0
        self.stdout.write(self.style.SUCCESS(
            f"Fertig. {ok:,} Firmen indexiert in {el:.0f}s."))

