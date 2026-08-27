# -*- coding: utf-8 -*-
"""
apps/abpe_edms/management/commands/dms_ocr_gpu.py
================================================================================
Welle 2: fuellt CrmDocument.content fuer gescannte Dokumente per GPU-OCR.

Nutzt services/gpu_ocr_extractor.py (EasyOCR auf der lokalen GPU).
Laeuft SERIELL: die GPU ist der Flaschenhals, nicht das Warten -> mehrere
Threads wuerden sich nur um die eine GPU streiten. Der Reader wird EINMAL
geladen und fuer alle Scans wiederverwendet.

Auswahl: standardmaessig alle mit leerem content (die Scans aus Welle 1).

Beispiele:
    python manage.py dms_ocr_gpu --limit 30        # Test
    python manage.py dms_ocr_gpu                   # alle offenen Scans
    python manage.py dms_ocr_gpu --min-chars 50    # auch kurze nachbessern
================================================================================
"""
import time

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models.functions import Length

from apps.abpe_edms.models import CrmDocument
from apps.abpe_edms.services import gpu_ocr_extractor as ocr


class Command(BaseCommand):
    help = "GPU-OCR (EasyOCR) fuellt content fuer gescannte Dokumente."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0,
                            help="Nur die ersten N (Test). 0 = alle.")
        parser.add_argument("--force", action="store_true",
                            help="Auch schon gefuellte neu.")
        parser.add_argument("--min-chars", type=int, default=0,
                            help="Alle mit weniger als N Zeichen (statt nur leere).")
        parser.add_argument("--batch", type=int, default=50,
                            help="DB-Speicher-Batch.")

    def handle(self, *args, **opts):
        limit = opts["limit"]
        force = opts["force"]
        min_chars = opts["min_chars"]
        batch = opts["batch"]

        # Auswahl
        qs = CrmDocument.objects.all().order_by("id")
        if force:
            pass
        elif min_chars > 0:
            qs = qs.annotate(_l=Length("content")).filter(_l__lt=min_chars)
        else:
            qs = qs.filter(content="")
        total = qs.count()
        if limit:
            qs = qs[:limit]
        anzahl = min(limit, total) if limit else total

        self.stdout.write(f"GPU-OCR | offen: {total:,} | dieser Lauf: {anzahl:,}")
        self.stdout.write("Lade EasyOCR-Reader auf die GPU ...")
        t_reader = time.perf_counter()
        ocr.get_reader()  # einmaliges Laden
        self.stdout.write(f"Reader bereit ({time.perf_counter()-t_reader:.1f}s)")
        self.stdout.write("=" * 60)

        ok = fail = skip = leer = 0
        total_chars = 0
        buffer = []
        errors = []
        t0 = time.perf_counter()
        done = 0

        def flush():
            if not buffer:
                return
            with transaction.atomic():
                for doc, text in buffer:
                    doc.content = text
                    doc.save(update_fields=["content", "modified_at"])
            buffer.clear()

        for doc in qs.iterator(chunk_size=200):
            done += 1
            version = doc.versions.filter(is_active=True).first()
            if not version:
                skip += 1
                continue

            res = ocr.extract(version.volume, version.relative_path, version.filename)

            if res.skipped:
                skip += 1
            elif not res.ok:
                fail += 1
                errors.append((version.filename, res.reason))
            else:
                ok += 1
                total_chars += res.chars
                if res.chars == 0:
                    leer += 1
                buffer.append((doc, res.text))
                if len(buffer) >= batch:
                    flush()

            if done % 20 == 0 or done == anzahl:
                el = time.perf_counter() - t0
                rate = done / el if el else 0
                rest = (anzahl - done) / rate / 60 if rate else 0
                self.stdout.write(
                    f"[{done}/{anzahl}] ok={ok} skip={skip} fail={fail} "
                    f"| {rate:.2f} Dok/s | Rest ~{rest:.0f} min")

        flush()

        el = time.perf_counter() - t0
        rate = done / el if el else 0
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS(
            f"Fertig. OK={ok} skip={skip} fail={fail} leer={leer}"))
        self.stdout.write(
            f"Zeichen: {total_chars:,} | Zeit: {el:.0f}s | {rate:.2f} Dok/s")
        if errors:
            self.stdout.write("-" * 60)
            self.stdout.write(f"Fehler (erste 15 von {len(errors)}):")
            for fn, gr in errors[:15]:
                self.stdout.write(f"  · {fn}: {gr}")

