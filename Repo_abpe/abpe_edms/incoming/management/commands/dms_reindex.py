# -*- coding: utf-8 -*-
"""
apps/abpe_edms/management/commands/dms_reindex.py
================================================================================
Befüllt / repariert den Elasticsearch-Index `abpe_dms`.

Der RealTimeSignalProcessor hält den Index im Normalbetrieb automatisch aktuell.
Dieser Command ist für:
  - die Erst-Befüllung
  - Reparatur nach Schema-/Mapping-Änderungen
  - Auffrischen denormalisierter Owner-Daten nach CRM-Stammdaten-Änderungen

Verwendung:
  python manage.py dms_reindex            # nur neu befüllen (populate)
  python manage.py dms_reindex --rebuild  # Index löschen + Mapping neu + befüllen
================================================================================
"""

from django.core.management.base import BaseCommand
from django_elasticsearch_dsl.registries import registry

from apps.abpe_edms.documents import DmsDocumentIndex
from apps.abpe_edms.models import CrmDocument


class Command(BaseCommand):
    help = "Befüllt oder repariert den Elasticsearch-Index abpe_dms."

    def add_arguments(self, parser):
        parser.add_argument(
            "--rebuild",
            action="store_true",
            help="Index löschen und Mapping neu anlegen, dann befüllen.",
        )

    def handle(self, *args, **options):
        doc = DmsDocumentIndex()
        index = doc._index

        if options["rebuild"]:
            self.stdout.write("Lösche und erstelle Index neu …")
            try:
                index.delete(ignore=404)
            except Exception as exc:  # pragma: no cover
                self.stdout.write(self.style.WARNING(f"  delete: {exc}"))
            index.create()
            self.stdout.write(self.style.SUCCESS("  Index + Mapping angelegt."))
        else:
            # Sicherstellen, dass der Index überhaupt existiert
            if not index.exists():
                index.create()
                self.stdout.write(self.style.SUCCESS("Index neu angelegt."))

        total = CrmDocument.objects.count()
        self.stdout.write(f"Indexiere {total} Dokument(e) …")

        if total:
            qs = doc.get_queryset()
            doc.update(qs)

        # Verifikation
        self.stdout.write(self.style.SUCCESS(
            f"Fertig. Index '{index._name}' enthält jetzt "
            f"{doc.search().count()} Dokument(e)."
        ))

