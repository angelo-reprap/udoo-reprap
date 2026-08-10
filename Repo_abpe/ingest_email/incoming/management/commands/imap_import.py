"""
Management Command für IMAP E-Mail Import
"""

from django.core.management.base import BaseCommand
import logging
from django.utils import timezone

from apps.ingest_email.imap_client import import_emails_from_imap, test_imap_connection

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Importiert E-Mails vom IMAP Server'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test',
            action='store_true',
            help='Nur Verbindung testen, keine Emails importieren'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=20,
            help='Maximale Anzahl zu importierender Emails'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Testlauf ohne tatsächlichen Import'
        )
        parser.add_argument(
            '--fetch-all',
            action='store_true',
            help='Importiere ALLE Emails (nicht nur ungelesene)'
        )

    def handle(self, *args, **options):
        test_mode = options['test']
        limit = options['limit']
        dry_run = options['dry_run']
        fetch_all = options['fetch_all']

        self.stdout.write("📧 IMAP E-MAIL IMPORT")
        self.stdout.write("=" * 60)

        if test_mode:
            self.stdout.write(f"🧪 IMAP VERBINDUNGSTEST")
            self.stdout.write(f"   • Server: imap.ionos.de:993")
            self.stdout.write(f"   • Benutzer: cv_scan@abcona.de")

            success = test_imap_connection()
            if success:
                self.stdout.write("✅ IMAP VERBINDUNG ERFOLGREICH")
            else:
                self.stdout.write("❌ IMAP VERBINDUNG FEHLGESCHLAGEN")
            return

        # Echter Import
        self.stdout.write(f"🔄 IMPORT START: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if dry_run:
            self.stdout.write("🏃 TROCKENLAUF - Keine Daten werden gespeichert")
        
        if fetch_all:
            self.stdout.write("🔍 MODUS: Importiere ALLE Emails (nicht nur ungelesene)")
        
        try:
            imported = import_emails_from_imap(
                limit=limit, 
                dry_run=dry_run,
                fetch_all=fetch_all
            )
            
            if dry_run:
                self.stdout.write(f"📊 TROCKENLAUF: {imported} E-Mails würden importiert")
            else:
                self.stdout.write(f"✅ IMPORT ERFOLGREICH: {imported} E-Mails importiert")
            
            self.stdout.write(f"🕒 ENDE: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
        except Exception as e:
            self.stderr.write(f"❌ IMPORT FEHLGESCHLAGEN: {e}")
            import traceback
            traceback.print_exc()
