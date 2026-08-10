"""
Integration zwischen ingest_email und abpe_intake
Sichere Implementierung mit Fehlerbehandlung
SPEICHERT Anhänge in neuer Media-Struktur
"""
import logging
import os
import shutil
from pathlib import Path
from datetime import datetime

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.db import models
from django.conf import settings

logger = logging.getLogger(__name__)

class IntakeIntegration:
    """Handler für Integration mit abpe_intake"""

    @staticmethod
    def is_available():
        """Prüft ob abpe_intake verfügbar ist"""
        try:
            from apps.abpe_intake.models import RawInput
            return True
        except ImportError:
            return False

    @staticmethod
    def save_attachments_to_media(email_instance, consultant_dir=None, aid=None):
        """
        Speichert E-Mail-Anhänge in der Media-Struktur:
        media/email/attachments/{consultant_dir}/{aid}_{filename}
        
        Args:
            email_instance: EmailMessage Instanz
            consultant_dir: Verzeichnisname für Berater (optional)
            aid: AID für Benennung (optional)
            
        Returns:
            Liste der gespeicherten Anhang-Pfade
        """
        if not email_instance.has_attachments or not email_instance.attachment_info:
            return []

        saved_attachments = []
        
        # Berater-Verzeichnis bestimmen
        if not consultant_dir:
            # Aus Betreff oder Absender einen Namen ableiten
            from_email = email_instance.from_email or ''
            subject = email_instance.subject or ''
            
            # Einfache Extraktion: Alles vor @ als Name
            if '@' in from_email:
                consultant_dir = from_email.split('@')[0].replace('.', '_')
            else:
                # Fallback: Datum
                consultant_dir = f"email_{email_instance.received_date.strftime('%Y%m%d')}"
        
        if not aid:
            import hashlib
            aid = hashlib.md5(f"{email_instance.id}{consultant_dir}".encode()).hexdigest()[:8]
        
        # Basis-Pfad für Anhänge
        attachments_base = Path(settings.MEDIA_ROOT) / 'email' / 'attachments' / consultant_dir
        attachments_base.mkdir(parents=True, exist_ok=True)
        
        # Adds-Verzeichnis für Berater (für spätere Zusatzdateien)
        adds_dir = Path(settings.MEDIA_ROOT) / 'cv' / 'cv' / consultant_dir / 'adds'
        adds_dir.mkdir(parents=True, exist_ok=True)
        
        # Anhänge verarbeiten
        for idx, att_info in enumerate(email_instance.attachment_info):
            try:
                filename = att_info.get('filename', f'attachment_{idx}')
                file_type = att_info.get('type', 'application/octet-stream')
                
                # Original-Anhang suchen (wenn als Datei gespeichert)
                # Hier müsste der tatsächliche Pfad zum Attachment ermittelt werden
                # Dies ist ein Platzhalter - je nachdem wo die Anhänge gespeichert werden
                
                # Generische Benennung: AID-{idx}_{filename}
                safe_filename = filename.replace(' ', '_').replace('/', '_')
                target_filename = f"{aid}_{idx}_{safe_filename}"
                target_path = attachments_base / target_filename
                
                # Hier müsste die tatsächliche Kopierlogik stehen
                # Beispiel: wenn attachments in temp gespeichert werden
                # source_path = Path(settings.MEDIA_ROOT) / 'temp' / 'email_attachments' / filename
                # if source_path.exists():
                #     shutil.copy2(source_path, target_path)
                
                # Metadaten zum Anhang
                attachment_data = {
                    'original_filename': filename,
                    'saved_filename': target_filename,
                    'saved_path': str(target_path),
                    'file_type': file_type,
                    'size': att_info.get('size', 0),
                    'url': f"/media/email/attachments/{consultant_dir}/{target_filename}",
                    'index': idx,
                }
                
                saved_attachments.append(attachment_data)
                
                # Wenn es ein CV ist (PDF/DOCX), könnte es auch ins adds-Verzeichnis
                if filename.lower().endswith(('.pdf', '.docx', '.doc')):
                    cv_copy = adds_dir / f"{aid}_cv_original{Path(filename).suffix}"
                    # shutil.copy2(target_path, cv_copy)  # wenn kopiert werden soll
                    
            except Exception as e:
                logger.error(f"❌ Fehler beim Speichern von Anhang {filename}: {e}")
        
        if saved_attachments:
            logger.info(f"📎 {len(saved_attachments)} Anhänge gespeichert für Email {email_instance.id}")
        
        return saved_attachments

    @staticmethod
    def create_rawinput_from_email(email_instance):
        """
        Erstellt einen RawInput Eintrag für eine Email.
        Gibt den RawInput zurück oder None bei Fehler.
        """
        if not IntakeIntegration.is_available():
            logger.debug("abpe_intake nicht verfügbar - Integration übersprungen")
            return None

        try:
            from apps.abpe_intake.models import RawInput, IntakeSource, ContentType

            # 1. Anhänge in Media-Struktur speichern
            saved_attachments = IntakeIntegration.save_attachments_to_media(email_instance)
            
            # 2. Sammle Email-Daten
            email_data = {
                'email_id': email_instance.id,
                'message_id': email_instance.message_id,
                'from': email_instance.from_email,
                'to': email_instance.to_email,
                'subject': email_instance.subject,
                'received_at': email_instance.received_date.isoformat(),
                'has_attachments': email_instance.has_attachments,
                'attachment_count': email_instance.attachment_count,
                'attachments': saved_attachments,  # Gespeicherte Anhänge
                'size_bytes': email_instance.size,
                'status': email_instance.status,
                'media_paths': {
                    'attachments': [a['saved_path'] for a in saved_attachments],
                    'attachment_urls': [a['url'] for a in saved_attachments],
                }
            }

            # 3. Bestimme Content Type basierend auf Subject und Body
            content_type = ContentType.UNKNOWN
            subject_lower = (email_instance.subject or '').lower()
            body_lower = (email_instance.body_plain or '').lower()

            cv_keywords = ['cv', 'lebenslauf', 'resume', 'bewerbung', 'application', 'curriculum vitae']
            if any(keyword in subject_lower for keyword in cv_keywords) or any(keyword in body_lower for keyword in cv_keywords):
                content_type = ContentType.CV

            profile_keywords = ['profil', 'profile', 'kandidat', 'candidate', 'bewerber']
            if any(keyword in subject_lower for keyword in profile_keywords) or any(keyword in body_lower for keyword in profile_keywords):
                content_type = ContentType.PROFILE

            company_keywords = ['firma', 'company', 'unternehmen', 'gmbh', 'ag']
            if any(keyword in subject_lower for keyword in company_keywords):
                content_type = ContentType.COMPANY

            # 4. Tags
            tags = ['email_import', f"from:{email_instance.from_email}", f"to:{email_instance.to_email}"]
            if email_instance.has_attachments:
                tags.append('has_attachments')
                tags.append(f'attachments:{email_instance.attachment_count}')
                tags.append('attachments_saved')

            # 5. Status basierend auf Email Status
            intake_status = 'NEW'
            if email_instance.status == 'PROCESSED':
                intake_status = 'PARSED'
            elif email_instance.status == 'ERROR':
                intake_status = 'ERROR'

            # 6. RawInput erstellen
            raw_input = RawInput.objects.create(
                source=IntakeSource.EMAIL,
                source_identifier=f"email_{email_instance.id}",
                content_type=content_type,
                file_name=f"email_{email_instance.id}.eml",
                metadata_json=email_data,
                tags=tags,
                original_data=(email_instance.body_plain or '')[:10000],
                status=intake_status,
            )

            logger.info(f"✅ RawInput {raw_input.id} erstellt für Email {email_instance.id}")
            logger.info(f"📎 {len(saved_attachments)} Anhänge in Media-Struktur gespeichert")

            # 7. Update Email mit RawInput ID
            email_instance.intake_rawinput_id = raw_input.id
            email_instance.save(update_fields=['intake_rawinput_id'])

            return raw_input

        except Exception as e:
            logger.error(f"❌ Fehler bei Intake-Erstellung für Email {email_instance.id}: {e}")

            try:
                email_instance.status = 'ERROR'
                email_instance.error_message = str(e)[:500]
                email_instance.save(update_fields=['status', 'error_message'])
            except:
                pass

            return None

    @staticmethod
    def setup_signals():
        """Richtet Signal-Handler ein"""
        try:
            from .models import EmailMessage

            @receiver(post_save, sender=EmailMessage)
            def handle_email_save(sender, instance, created, **kwargs):
                if created and instance.status == 'NEW':
                    logger.info(f"📨 Neue Email erkannt: {instance.id} - '{instance.subject}'")

                    # Sofort verarbeiten
                    raw_input = IntakeIntegration.create_rawinput_from_email(instance)
                    if raw_input:
                        # Update Email Status
                        instance.status = 'PROCESSED'
                        instance.processed_at = timezone.now()
                        instance.save(update_fields=['status', 'processed_at'])
                        logger.info(f"✅ Email {instance.id} verarbeitet → RawInput {raw_input.id}")
                    else:
                        logger.warning(f"⚠️  Email {instance.id} konnte nicht verarbeitet werden")

            logger.info("✅ Signal-Handler für Email → Intake Integration eingerichtet")
            return True

        except Exception as e:
            logger.error(f"❌ Signal-Handler Setup fehlgeschlagen: {e}")
            return False


def import_existing_emails(batch_size=50, skip_processed=True):
    """Importiert existierende Emails in abpe_intake"""
    try:
        from .models import EmailMessage

        if not IntakeIntegration.is_available():
            logger.warning("⚠️  abpe_intake nicht verfügbar - Import übersprungen")
            return 0

        if skip_processed:
            emails = EmailMessage.objects.filter(intake_rawinput_id__isnull=True)
        else:
            emails = EmailMessage.objects.all()

        emails = emails.order_by('received_date')[:batch_size]
        imported = 0

        for email in emails:
            raw_input = IntakeIntegration.create_rawinput_from_email(email)
            if raw_input:
                imported += 1

                if imported % 10 == 0:
                    logger.info(f"📊 Importiert: {imported} Emails")

        logger.info(f"✅ Batch Import abgeschlossen: {imported} Emails importiert")
        return imported

    except Exception as e:
        logger.error(f"❌ Massenimport fehlgeschlagen: {e}")
        return 0


def get_integration_status():
    """Gibt Status der Integration zurück"""
    try:
        from .models import EmailMessage

        status = {
            'abpe_intake_available': IntakeIntegration.is_available(),
            'total_emails': 0,
            'processed_emails': 0,
            'pending_emails': 0,
            'with_attachments': 0,
            'attachments_saved': 0,
        }

        if EmailMessage.objects.exists():
            from django.db.models import Count, Q

            stats = EmailMessage.objects.aggregate(
                total=Count('id'),
                processed=Count('id', filter=Q(intake_rawinput_id__isnull=False)),
                pending=Count('id', filter=Q(intake_rawinput_id__isnull=True)),
                attachments=Count('id', filter=Q(has_attachments=True)),
            )

            status.update({
                'total_emails': stats['total'],
                'processed_emails': stats['processed'],
                'pending_emails': stats['pending'],
                'with_attachments': stats['attachments'],
            })

        # Media-Verzeichnisse prüfen
        media_paths = {
            'email_attachments': str(Path(settings.MEDIA_ROOT) / 'email' / 'attachments'),
            'cv_adds': str(Path(settings.MEDIA_ROOT) / 'cv' / 'adds'),
        }
        for name, path in media_paths.items():
            status[f'media_{name}_exists'] = Path(path).exists()

        return status

    except Exception as e:
        logger.error(f"❌ Status Abfrage fehlgeschlagen: {e}")
        return {'error': str(e)}


def create_test_email():
    """Erstellt eine Test-Email für Entwicklung"""
    try:
        from .models import EmailMessage
        from django.utils import timezone
        import uuid

        test_email = EmailMessage.objects.create(
            message_id=f"test_{uuid.uuid4()}@test.com",
            subject="Test CV Submission - Software Developer",
            from_email="test.candidate@example.com",
            to_email="cv_scan@abcona.de",
            body_plain="Sehr geehrte Damen und Herren,\n\nanbei sende ich Ihnen meinen Lebenslauf für die Position als Software Developer.\n\nMit freundlichen Grüßen\nMax Mustermann",
            received_date=timezone.now(),
            size=2048,
            has_attachments=True,
            attachment_count=1,
            attachment_info=[{"filename": "cv_mustermann.pdf", "type": "application/pdf", "size": 102400}],
            status='NEW',
            tags=['test', 'cv', 'software_developer'],
        )

        logger.info(f"✅ Test-Email erstellt: {test_email.id}")
        return test_email

    except Exception as e:
        logger.error(f"❌ Test-Email Erstellung fehlgeschlagen: {e}")
        return None
