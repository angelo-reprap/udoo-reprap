# -*- coding: utf-8 -*-
"""
apps/abpe_edms/management/commands/dms_scan.py
================================================================================
Startet den Dateisystem-Scanner (services/scanner.py).

Sicherer Standard: DRY-RUN. Erst --execute schreibt wirklich.

Baum-Auswahl (Default: alle):
  --berater          nur Berater-Baum (Contact-Match)
  --kunde            nur Kunde-Baum (Account-Match, zweistufig)
  --administration   nur Rechnungen/ -> abcona-Self
  --alle             alle drei (Default, wenn keiner gewählt)

Modus:
  --update           bekannte Dateien mitnehmen und Owner NACHTRAGEN/korrigieren
                     (Grundmodus ohne --update: nur NEUE Dateien anlegen)
  --execute          ECHT schreiben (sonst nur dry-run)
  --limit N          nur N Dateien (Test)

Beispiele:
  python manage.py dms_scan --kunde                    # Trockenlauf Kunde
  python manage.py dms_scan --kunde --update           # Trockenlauf: Kunde-Owner nachtragen
  python manage.py dms_scan --kunde --update --execute # ECHT: Kunde-Owner setzen
  python manage.py dms_scan --administration --update --execute  # abcona-Rechnungen
  python manage.py dms_scan --alle --update --execute  # alles abgleichen
================================================================================
"""
from django.core.management.base import BaseCommand
from apps.abpe_edms.services import scanner


class Command(BaseCommand):
    help = "Scannt die konfigurierten Ordner und gleicht sie mit der DB ab."

    def add_arguments(self, parser):
        parser.add_argument("--execute", action="store_true",
                            help="ECHT schreiben. Ohne dieses Flag: Trockenlauf.")
        parser.add_argument("--limit", type=int, default=None,
                            help="Maximal so viele Dateien betrachten (Test).")
        parser.add_argument("--update", action="store_true",
                            help="Bekannte Dateien mitnehmen, Owner nachtragen/korrigieren.")
        # Baum-Auswahl
        parser.add_argument("--berater", action="store_true",
                            help="Nur Berater-Baum (Contact).")
        parser.add_argument("--kunde", action="store_true",
                            help="Nur Kunde-Baum (Account, zweistufig).")
        parser.add_argument("--administration", action="store_true",
                            help="Nur Rechnungen/ -> abcona-Self.")
        parser.add_argument("--alle", action="store_true",
                            help="Alle drei Bäume (Default wenn keiner gewählt).")

    def handle(self, *args, **options):
        dry = not options["execute"]
        limit = options["limit"]
        update = options["update"]

        # Baum-Auswahl: wenn keiner explizit -> alle
        b = options["berater"]
        k = options["kunde"]
        a = options["administration"]
        if options["alle"] or not (b or k or a):
            b = k = a = True

        mode = "TROCKENLAUF (nichts wird geschrieben)" if dry else "ECHTER LAUF"
        self.stdout.write(self.style.WARNING(f"=== dms_scan — {mode} ==="))
        self.stdout.write(f"  Bäume: berater={b} kunde={k} administration={a}")
        self.stdout.write(f"  Modus: {'UPDATE (Owner nachtragen)' if update else 'nur NEUE Dateien'}")
        if limit:
            self.stdout.write(f"  Limit: {limit} Dateien")

        stats = scanner.scan_all(
            dry_run=dry,
            limit=limit,
            logger=lambda msg: self.stdout.write(msg),
            do_berater=b, do_kunde=k, do_admin=a, update=update,
        )

        if dry:
            self.stdout.write(self.style.SUCCESS(
                "\n  Trockenlauf beendet. Wenn die Zahlen passen: "
                "mit --execute echt laufen lassen."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"\n  Fertig. neu={stats.new} owner_gesetzt={stats.owner_resolved} "
                f"owner_nachgetragen={stats.owner_added} "
                f"vorschläge={stats.owner_suggested} konflikte={stats.owner_conflict} "
                f"posteingang={stats.to_inbox}"
            ))

