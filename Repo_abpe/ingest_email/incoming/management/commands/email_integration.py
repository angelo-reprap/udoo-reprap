"""
Management Command für E-Mail Integration mit ABpE Intake
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Verwaltet die Integration zwischen ingest_email und abpe_intake'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            type=str,
            choices=['status', 'import', 'test', 'setup'],
            help='Aktion: status, import, test, setup'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help='Anzahl Emails für Batch Import'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Importiere alle Emails (auch schon verarbeitete)'
        )
        parser.add_argument(
            '--email-id',
            type=int,
            help='Spezifische Email ID für Test'
        )
    
    def handle(self, *args, **options):
        action = options['action']
        batch_size = options['batch_size']
        
        self.stdout.write(f"🔗 E-Mail Integration Management")
        self.stdout.write(f"   • Aktion: {action}")
        
        if action == 'status':
            self.show_status()
        elif action == 'import':
            self.import_emails(batch_size, options['all'])
        elif action == 'test':
            self.run_test(options['email_id'])
        elif action == 'setup':
            self.setup_integration()
    
    def show_status(self):
        """Zeigt Status der Integration"""
        try:
            from apps.ingest_email.integration import get_integration_status
            
            status = get_integration_status()
            
            self.stdout.write("\n📊 INTEGRATION STATUS:")
            self.stdout.write("=" * 50)
            
            self.stdout.write(f"1. SYSTEM:")
            self.stdout.write(f"   • abpe_intake verfügbar: {'✅ Ja' if status['abpe_intake_available'] else '❌ Nein'}")
            
            self.stdout.write(f"\n2. EMAIL DATENBANK:")
            self.stdout.write(f"   • Total Emails: {status['total_emails']}")
            self.stdout.write(f"   • Bereits integriert: {status['processed_emails']}")
            self.stdout.write(f"   • Ausstehend: {status['pending_emails']}")
            self.stdout.write(f"   • Mit Anhängen: {status.get('with_attachments', 0)}")
            
            if status['total_emails'] > 0:
                percentage = (status['processed_emails'] / status['total_emails']) * 100
                self.stdout.write(f"   • Fortschritt: {percentage:.1f}%")
            
            self.stdout.write(f"\n3. AKTIONEN:")
            self.stdout.write(f"   • Batch Import: python manage.py ingest_email.email_integration import --batch-size=100")
            self.stdout.write(f"   • Test Email: python manage.py ingest_email.email_integration test")
            self.stdout.write(f"   • Setup Check: python manage.py ingest_email.email_integration setup")
            
        except Exception as e:
            self.stderr.write(f"❌ Status Abfrage fehlgeschlagen: {e}")
    
    def import_emails(self, batch_size, import_all):
        """Importiert Emails in abpe_intake"""
        try:
            from apps.ingest_email.integration import import_existing_emails
            
            self.stdout.write(f"\n📧 EMAIL IMPORT GESTARTET:")
            self.stdout.write(f"   • Batch Size: {batch_size}")
            self.stdout.write(f"   • Alle importieren: {'Ja' if import_all else 'Nein (nur unverarbeitete)'}")
            
            imported = import_existing_emails(
                batch_size=batch_size,
                skip_processed=not import_all
            )
            
            self.stdout.write(f"\n✅ IMPORT ABGESCHLOSSEN:")
            self.stdout.write(f"   • Importierte Emails: {imported}")
            
        except Exception as e:
            self.stderr.write(f"❌ Import fehlgeschlagen: {e}")
    
    def run_test(self, email_id=None):
        """Führt Integrationstest durch"""
        try:
            from apps.ingest_email.integration import create_test_email, IntakeIntegration
            from apps.ingest_email.models import EmailMessage
            
            self.stdout.write(f"\n🧪 INTEGRATION TEST:")
            
            if email_id:
                # Test mit spezifischer Email
                email = EmailMessage.objects.get(id=email_id)
                self.stdout.write(f"   • Verwende existierende Email: {email.id}")
            else:
                # Neue Test-Email erstellen
                self.stdout.write(f"   • Erstelle neue Test-Email...")
                email = create_test_email()
                if not email:
                    self.stderr.write("❌ Test-Email konnte nicht erstellt werden")
                    return
            
            self.stdout.write(f"   • Email ID: {email.id}")
            self.stdout.write(f"   • Betreff: {email.subject}")
            self.stdout.write(f"   • Von: {email.from_email}")
            
            # Integration testen
            self.stdout.write(f"   • Führe Integration aus...")
            raw_input = IntakeIntegration.create_rawinput_from_email(email)
            
            if raw_input:
                self.stdout.write(f"✅ TEST ERFOLGREICH:")
                self.stdout.write(f"   • RawInput erstellt: {raw_input.id}")
                self.stdout.write(f"   • Content Type: {raw_input.get_content_type_display()}")
                self.stdout.write(f"   • Tags: {', '.join(raw_input.tags[:5])}")
                self.stdout.write(f"   • Status: {raw_input.get_status_display()}")
            else:
                self.stdout.write(f"❌ TEST FEHLGESCHLAGEN")
                self.stdout.write(f"   • Email Status: {email.status}")
                self.stdout.write(f"   • Fehler: {email.error_message}")
            
        except Exception as e:
            self.stderr.write(f"❌ Test fehlgeschlagen: {e}")
            import traceback
            traceback.print_exc()
    
    def setup_integration(self):
        """Prüft und richtet Integration ein"""
        try:
            from apps.ingest_email.integration import IntakeIntegration
            
            self.stdout.write(f"\n🔧 INTEGRATION SETUP CHECK:")
            
            # Verfügbarkeit prüfen
            available = IntakeIntegration.is_available()
            self.stdout.write(f"   • abpe_intake verfügbar: {'✅ Ja' if available else '❌ Nein'}")
            
            if not available:
                self.stdout.write(f"   ⚠️  Integration kann nicht eingerichtet werden")
                self.stdout.write(f"   ℹ️  Stellen Sie sicher dass 'apps.abpe_intake' in INSTALLED_APPS ist")
                return
            
            # Signal-Handler setupen
            self.stdout.write(f"   • Richte Signal-Handler ein...")
            success = IntakeIntegration.setup_signals()
            
            if success:
                self.stdout.write(f"✅ SETUP ERFOLGREICH:")
                self.stdout.write(f"   • Neue Emails werden automatisch integriert")
                self.stdout.write(f"   • Signal-Handler aktiv")
            else:
                self.stdout.write(f"❌ SETUP FEHLGESCHLAGEN")
                self.stdout.write(f"   • Signal-Handler konnten nicht eingerichtet werden")
            
        except Exception as e:
            self.stderr.write(f"❌ Setup fehlgeschlagen: {e}")

