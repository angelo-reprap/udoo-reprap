# -*- coding: utf-8 -*-
"""
apps/abpe_edms/management/commands/dms_extract_content.py
================================================================================
Massenlauf: füllt CrmDocument.content mit Tika-Volltext — PARALLEL.

Der DÜNNE Auslöser — die eigentliche Extraktion steckt im Service
(apps/abpe_edms/services/tika_extractor.py). Dieses Command iteriert nur,
verteilt die Tika-Aufrufe auf mehrere Threads und speichert nach Postgres.

Warum Threads (und nicht Prozesse): Der Flaschenhals ist WARTEN auf Tikas
HTTP-Antwort (I/O), nicht CPU im Django-Prozess. Während ein Scan bei Tika
OCR rechnet, können weitere Anfragen schon unterwegs sein. Die Tika-LXC
(2 Kerne) rechnet real ~2 gleichzeitig — der Rest wartet dort in der Queue,
aber unsere schnellen Text-PDFs (0,15s) flutschen dazwischen durch.

Wichtig: Tika-Aufrufe laufen PARALLEL in Worker-Threads, aber das SPEICHERN
in Postgres passiert SERIELL im Hauptthread (Djangos DB-Connection wird nicht
zwischen Threads geteilt). So bleibt es sicher.

Schreibt NUR nach Postgres (CrmDocument.content). Elasticsearch wird
SEPARAT danach reindexiert (nicht hier).

Beispiele:
    python manage.py dms_extract_content --limit 50 --dry-run   # Try-Run trocken
    python manage.py dms_extract_content --limit 50             # Try-Run echt
    python manage.py dms_extract_content                        # alle offenen
    python manage.py dms_extract_content --workers 6            # weniger Last
    python manage.py dms_extract_content --force                # auch gefüllte neu
================================================================================
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.abpe_edms.models import CrmDocument
from apps.abpe_edms.services import tika_extractor as tika


class Command(BaseCommand):
    help = "Extrahiert Volltext per Tika (parallel) und füllt CrmDocument.content."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0,
                            help="Nur die ersten N Dokumente (Try-Run). 0 = alle.")
        parser.add_argument("--workers", type=int, default=10,
                            help="Parallele Tika-Anfragen (Default 10).")
        parser.add_argument("--force", action="store_true",
                            help="Auch Dokumente neu extrahieren, die schon content haben.")
        parser.add_argument("--dry-run", action="store_true",
                            help="Extrahieren, aber NICHT speichern (nur zählen).")
        parser.add_argument("--batch", type=int, default=200,
                            help="Wie viele Dokumente pro DB-Transaktion gespeichert werden.")
        parser.add_argument("--no-ocr", action="store_true",
                            help="OCR abschalten (Welle 1: schnell). Scans bleiben leer "
                                 "und werden im 2. Lauf ohne --no-ocr nachgeholt.")

    def handle(self, *args, **opts):
        limit = opts["limit"]
        workers = opts["workers"]
        force = opts["force"]
        dry = opts["dry_run"]
        batch = opts["batch"]
        no_ocr = opts["no_ocr"]

        # 1. Tika erreichbar?
        alive, info = tika.tika_alive()
        if not alive:
            self.stderr.write(self.style.ERROR(
                f"Tika NICHT erreichbar unter {tika.TIKA_URL}: {info}"))
            return
        self.stdout.write(self.style.SUCCESS(f"Tika: {info}  ({tika.TIKA_URL})"))
        self.stdout.write(f"Parallelität: {workers} Worker")
        self.stdout.write("OCR: " + ("AUS (Welle 1 — schnell)" if no_ocr else "AN (Scans werden ge-OCRt)"))
        if dry:
            self.stdout.write(self.style.WARNING("DRY-RUN — es wird NICHTS gespeichert."))

        # 2. Auswahl (wiederaufsetzbar: nur leere content)
        qs = CrmDocument.objects.all().order_by("id")
        if not force:
            qs = qs.filter(content="")
        total_offen = qs.count()
        if limit:
            qs = qs[:limit]
        anzahl = min(limit, total_offen) if limit else total_offen

        self.stdout.write(
            f"Offen (ohne content): {total_offen:,}  |  dieser Lauf: {anzahl:,}"
            + ("  [FORCE]" if force else ""))
        self.stdout.write("=" * 64)

        # 3. Arbeitspakete vorbereiten: (doc_id, volume, relative_path, filename)
        #    Wir ziehen die nötigen Felder VORHER raus, damit die Worker-Threads
        #    NICHT auf die DB zugreifen müssen — sie machen nur HTTP zu Tika.
        jobs = []
        docmap = {}
        for doc in qs.iterator(chunk_size=500):
            version = doc.versions.filter(is_active=True).first()
            if not version:
                docmap[doc.id] = (doc, None)
                jobs.append((doc.id, None, None, None))
                continue
            docmap[doc.id] = (doc, version)
            jobs.append((doc.id, version.volume, version.relative_path, version.filename))

        # 4. Worker-Funktion: nur Tika, keine DB
        def work(job):
            doc_id, volume, rel, fn = job
            if volume is None:
                return doc_id, None, "keine aktive version"
            res = tika.extract(volume=volume, relative_path=rel, filename=fn,
                               skip_ocr=no_ocr)
            return doc_id, res, None

        # 5. Zähler + Speicher-Puffer (Speichern seriell im Hauptthread)
        ok = fail = skip = leer = 0
        total_chars = 0
        errors = []
        buffer = []
        t_start = time.perf_counter()
        done = 0

        def flush():
            if dry or not buffer:
                buffer.clear()
                return
            with transaction.atomic():
                for doc, text in buffer:
                    doc.content = text
                    doc.save(update_fields=["content", "modified_at"])
            buffer.clear()

        # 6. Parallel ausführen, Ergebnisse im Hauptthread einsammeln
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(work, j): j for j in jobs}
            for fut in as_completed(futures):
                done += 1
                doc_id, res, hard_err = fut.result()
                doc, _version = docmap[doc_id]

                if hard_err:
                    skip += 1
                    errors.append((doc.title, hard_err))
                elif res.skipped:
                    skip += 1
                elif not res.ok:
                    fail += 1
                    errors.append((res.abs_path or doc.title, res.reason))
                else:
                    ok += 1
                    total_chars += res.chars
                    if res.chars == 0:
                        leer += 1
                    buffer.append((doc, res.text))
                    if len(buffer) >= batch:
                        flush()

                if done % 25 == 0 or done == anzahl:
                    elapsed = time.perf_counter() - t_start
                    rate = done / elapsed if elapsed else 0
                    self.stdout.write(
                        f"[{done}/{anzahl}]  ok={ok} skip={skip} fail={fail}  "
                        f"| {rate:.1f} Dok/s")

        flush()

        # 7. Zusammenfassung
        elapsed = time.perf_counter() - t_start
        rate = done / elapsed if elapsed else 0
        self.stdout.write("=" * 64)
        self.stdout.write(self.style.SUCCESS(
            f"Fertig. OK={ok}  übersprungen={skip}  Fehler={fail}  davon leer={leer}"))
        self.stdout.write(
            f"Zeichen gesamt: {total_chars:,}  |  Zeit: {elapsed:.0f}s  |  ⌀ {rate:.1f} Dok/s")
        if not force and rate and total_offen > anzahl:
            rest_min = (total_offen - anzahl) / rate / 60
            self.stdout.write(
                f"Hochrechnung Rest ({total_offen - anzahl:,} Dok): ≈ {rest_min:.0f} min")
        if dry:
            self.stdout.write(self.style.WARNING("DRY-RUN — nichts gespeichert."))

        if errors:
            self.stdout.write("-" * 64)
            self.stdout.write(f"Fehler/Skips mit Grund (erste 15 von {len(errors)}):")
            for what, grund in errors[:15]:
                self.stdout.write(f"  · {what}: {grund}")

