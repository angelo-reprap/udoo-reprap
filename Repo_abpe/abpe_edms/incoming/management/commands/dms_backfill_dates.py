"""
dms_backfill_dates — trägt document_date aus dem Datei-mtime nach.

Hintergrund: Beim Scannen gescannter Altdokumente blieb document_date oft null.
Das Datei-Änderungsdatum (st_mtime) über den CIFS-Mount ist aber immer vorhanden
und ein brauchbarer Datums-Fallback (z. B. für die zeitbasierte Suche/Sortierung).

Verwendung:
    python manage.py dms_backfill_dates            # nur wo document_date NULL ist
    python manage.py dms_backfill_dates --force    # auch vorhandene überschreiben
    python manage.py dms_backfill_dates --dry-run   # nur zählen, nichts schreiben
    python manage.py dms_backfill_dates --limit 500 # nur erste 500 (zum Testen)

Liest IMMER nur st_mtime (keine Datei-Inhalte, kein Parser) → schnell.
Setzt document_date NICHT, wenn die Datei nicht erreichbar ist (Mount weg o.ä.).
"""
import os
import time
import datetime as dt

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.abpe_edms.models import CrmDocument, CrmDocumentVersion
from apps.abpe_edms.services import storage


class Command(BaseCommand):
    help = "Trägt document_date aus dem Datei-mtime (st_mtime) nach."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force", action="store_true",
            help="Auch Dokumente mit bereits gesetztem document_date überschreiben.",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Nur zählen/anzeigen, nichts in die DB schreiben.",
        )
        parser.add_argument(
            "--limit", type=int, default=0,
            help="Nur die ersten N Dokumente verarbeiten (0 = alle).",
        )

    def handle(self, *args, **opts):
        force = opts["force"]
        dry_run = opts["dry_run"]
        limit = opts["limit"]

        t0 = time.time()

        # Welche Dokumente? Ohne --force nur die mit document_date IS NULL.
        qs = CrmDocument.objects.all()
        if not force:
            qs = qs.filter(document_date__isnull=True)
        qs = qs.order_by("created_at")
        if limit:
            qs = qs[:limit]

        total = qs.count()
        self.stdout.write(
            f"Backfill document_date · {total} Dokument(e) "
            f"({'FORCE' if force else 'nur NULL'}{', DRY-RUN' if dry_run else ''})"
        )

        updated = 0
        no_file = 0
        no_version = 0
        errors = 0
        i = 0

        for doc in qs.iterator(chunk_size=500):
            i += 1
            # aktive Version (für den Pfad)
            version = (
                doc.versions.filter(is_active=True).order_by("-version_no").first()
                or doc.versions.order_by("-version_no").first()
            )
            if version is None:
                no_version += 1
                continue

            try:
                abs_path = storage.absolute_path(version)
            except Exception:
                abs_path = None

            if not abs_path or not os.path.exists(abs_path):
                no_file += 1
                continue

            try:
                mtime = os.stat(abs_path).st_mtime
                doc_date = dt.date.fromtimestamp(mtime)
            except OSError:
                errors += 1
                continue

            if not dry_run:
                # Nur das eine Feld speichern (schnell, keine Signals/ES-Reindex hier)
                CrmDocument.objects.filter(pk=doc.pk).update(document_date=doc_date)
            updated += 1

            if i % 1000 == 0:
                dur = round(time.time() - t0, 1)
                self.stdout.write(
                    f"  {i}/{total} · gesetzt={updated} · ohne_datei={no_file} · {dur}s"
                )

        dur = round(time.time() - t0, 1)
        self.stdout.write(self.style.SUCCESS(
            f"\nFertig in {dur}s · gesetzt={updated} · "
            f"ohne_datei={no_file} · ohne_version={no_version} · fehler={errors}"
        ))
        if not dry_run and updated:
            self.stdout.write(
                "Hinweis: Für die Suche/Sortierung im ES-Index ggf. "
                "'python manage.py dms_reindex --rebuild' laufen lassen."
            )

