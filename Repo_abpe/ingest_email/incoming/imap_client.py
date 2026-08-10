"""
IMAP Client für E-Mail Import von cv_scan@abcona.de
REPARIERTE VERSION - Attachment wird auf Disk gespeichert
"""

import imaplib
import email
from email.header import decode_header
import logging
from datetime import datetime, timedelta
import time
import os
import tempfile
from django.utils import timezone
from django.conf import settings
from django.core.files.base import ContentFile

from .models import EmailMessage, EmailAttachment, EmailImportConfig

logger = logging.getLogger(__name__)

class IMAPClientError(Exception):
    """Custom Exception für IMAP Client Fehler"""
    pass

class IMAPClient:
    """IMAP Client für E-Mail Import"""

    def __init__(self, config=None):
        self.config = config or self.get_default_config()
        self.connection = None
        self.is_connected = False

    def get_default_config(self):
        """Holt die default Konfiguration aus settings"""
        try:
            return settings.CV_SCAN_IMAP_CONFIG
        except AttributeError:
            logger.warning("⚠️  CV_SCAN_IMAP_CONFIG nicht in settings gefunden")
            return {
                'host': 'imap.ionos.de',
                'port': 993,
                'username': 'cv_scan@abcona.de',
                'password': 'django_mail-2025',
                'use_ssl': True,
                'mailbox': 'INBOX',
            }

    def connect(self):
        """Stellt Verbindung zum IMAP Server her"""
        try:
            if self.config.get('use_ssl', True):
                self.connection = imaplib.IMAP4_SSL(
                    self.config['host'],
                    self.config['port']
                )
            else:
                self.connection = imaplib.IMAP4(
                    self.config['host'],
                    self.config['port']
                )

            # Login
            self.connection.login(
                self.config['username'],
                self.config['password']
            )

            # Select mailbox
            self.connection.select(self.config.get('mailbox', 'INBOX'))

            self.is_connected = True
            logger.info(f"✅ IMAP Verbindung hergestellt zu {self.config['host']}")
            return True

        except Exception as e:
            logger.error(f"❌ IMAP Verbindung fehlgeschlagen: {e}")
            self.is_connected = False
            return False

    def disconnect(self):
        """Trennt Verbindung"""
        if self.connection and self.is_connected:
            try:
                self.connection.close()
                self.connection.logout()
                self.is_connected = False
                logger.info("✅ IMAP Verbindung getrennt")
            except:
                pass

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def fetch_emails(self, limit=20, dry_run=False, fetch_all=False):
        """Holt Emails vom Server (standardmäßig nur ungelesene)"""
        if not self.is_connected:
            if not self.connect():
                return []

        try:
            # Search criteria: UNSEEN für normale Importe, ALL für initial/test
            search_criteria = 'ALL' if fetch_all else 'UNSEEN'

            status, messages = self.connection.search(None, search_criteria)
            if status != 'OK':
                logger.warning(f"⚠️  Keine Emails gefunden (Criteria: {search_criteria})")
                return []

            email_ids = messages[0].split()
            if not email_ids:
                logger.info(f"ℹ️  Keine neuen Emails (Criteria: {search_criteria})")
                return []

            # Limit results - NEUESTE zuerst (höchste ID)
            email_ids = email_ids[-limit:] if limit else email_ids
            emails = []

            logger.info(f"📨 Gefundene Emails ({search_criteria}): {len(email_ids)} (Dry-Run: {dry_run})")

            for i, email_id in enumerate(reversed(email_ids), 1):
                try:
                    # Fetch email
                    status, msg_data = self.connection.fetch(email_id, '(RFC822)')
                    if status != 'OK':
                        logger.warning(f"⚠️  Email {email_id} konnte nicht geladen werden")
                        continue

                    raw_email = msg_data[0][1]
                    email_obj = self.parse_email(raw_email, email_id, dry_run)

                    if email_obj:
                        emails.append(email_obj)

                except Exception as e:
                    logger.error(f"❌ Fehler beim Verarbeiten von Email {email_id}: {e}")

            return emails

        except Exception as e:
            logger.error(f"❌ Fehler beim Abrufen von Emails: {e}")
            return []

    def parse_email(self, raw_email, email_id, dry_run=False):
        """Parsed eine Roh-Email und erstellt EmailMessage Objekt MIT ATTACHMENTS"""
        try:
            # Parse email
            msg = email.message_from_bytes(raw_email)

            # Decode headers
            subject = self._decode_header(msg.get('Subject', ''))
            from_email = self._extract_email(msg.get('From', ''))
            to_email = self._extract_email(msg.get('To', ''))
            message_id = msg.get('Message-ID', f'imap_{email_id.decode()}')

            # Parse date
            date_str = msg.get('Date', '')
            received_date = self._parse_email_date(date_str)

            # Extract body and attachments
            body_plain, body_html, attachments = self._extract_content(msg)

            # Check if email already exists
            if EmailMessage.objects.filter(message_id=message_id).exists():
                logger.debug(f"Email {message_id} bereits importiert, überspringe")
                return None

            # DRY RUN: Nur loggen, nicht speichern
            if dry_run:
                logger.info(f"[DRY-RUN] Würde Email importieren: '{subject[:50]}...' von {from_email}")
                logger.info(f"[DRY-RUN] Attachments: {len(attachments)} Dateien")
                for att in attachments:
                    logger.info(f"[DRY-RUN]   - {att['filename']} ({att['size']} bytes, {att['content_type']})")

                # Simuliertes Objekt zurückgeben für Zählung
                class DryRunEmail:
                    def __init__(self):
                        self.id = f"dry_run_{email_id.decode()}"
                return DryRunEmail()

            # REAL RUN: EmailMessage erstellen
            email_obj = EmailMessage.objects.create(
                message_id=message_id,
                subject=subject,
                from_email=from_email,
                to_email=to_email,
                body_plain=body_plain,
                body_html=body_html,
                received_date=received_date,
                size=len(raw_email),
                has_attachments=len(attachments) > 0,
                attachment_count=len(attachments),
                attachment_info=[{
                    'filename': att['filename'],
                    'content_type': att['content_type'],
                    'size': att['size']
                } for att in attachments],
                status='NEW',
                raw_headers=str(msg.items()),
                raw_body=raw_email.decode('utf-8', errors='ignore')[:10000],
                tags=['imap_import', f"from:{from_email}"],
            )

            logger.info(f"✅ Email importiert: {email_obj.id} - '{subject[:50]}...'")

            # 🚀 REPARIERTE VERSION: Attachments nach Dateityp sortiert speichern
            saved_count = 0
            for att_data in attachments:
                try:
                    saved = self._save_attachment(email_obj, att_data)
                    if saved:
                        saved_count += 1
                        logger.debug(f"✅ Attachment gespeichert: {att_data['filename']}")
                except Exception as e:
                    logger.error(f"❌ Fehler beim Speichern von Attachment {att_data['filename']}: {e}")

            if saved_count > 0:
                logger.info(f"📎 {saved_count}/{len(attachments)} Attachments gespeichert")

                # Update attachment count
                email_obj.attachment_count = saved_count
                email_obj.has_attachments = saved_count > 0
                email_obj.save()

            return email_obj

        except Exception as e:
            logger.error(f"❌ Fehler beim Parsen von Email: {e}")
            return None

    def _save_attachment(self, email_message, attachment_data):
        """
        🚀 REPARIERTE VERSION
        Speichert Attachment nach Dateityp in entsprechendem Media-Verzeichnis:
        - PDF → /media/pdf/
        - Word → /media/docx/
        - CSV → /media/csv/
        - Text → /media/txt/
        - Bilder → /media/uploads/
        - Sonstige → /media/uploads/
        """
        try:
            import os
            from django.conf import settings
            
            filename = attachment_data['filename']
            content_type = attachment_data['content_type']
            
            # Zielverzeichnis basierend auf Content-Type bestimmen
            if content_type == 'application/pdf':
                target_dir = 'pdf'
            elif content_type in ['application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
                target_dir = 'docx'
            elif content_type == 'text/csv':
                target_dir = 'csv'
            elif content_type == 'text/plain':
                target_dir = 'txt'
            elif content_type.startswith('image/'):
                target_dir = 'uploads'
            else:
                target_dir = 'uploads'
            
            # Verzeichnis erstellen: /media/pdf/ etc.
            upload_dir = os.path.join(settings.MEDIA_ROOT, target_dir)
            os.makedirs(upload_dir, exist_ok=True)
            
            # Dateipfad: /media/pdf/dateiname.pdf
            # Bei Namenskonflikten mit Datum versehen
            base, ext = os.path.splitext(filename)
            file_path = os.path.join(upload_dir, filename)
            
            # Falls Datei bereits existiert, Datum anhängen
            counter = 1
            while os.path.exists(file_path):
                new_filename = f"{base}_{timezone.now().strftime('%Y%m%d_%H%M%S')}{ext}"
                file_path = os.path.join(upload_dir, new_filename)
                counter += 1
                if counter > 10:  # Sicherheitsschleife
                    file_path = os.path.join(upload_dir, f"{base}_{counter}{ext}")
                    break
            
            # Datei auf Disk speichern
            with open(file_path, 'wb') as f:
                f.write(attachment_data['payload'])
            
            # Relativen Pfad für DB (MEDIA_ROOT abgeschnitten)
            relative_path = file_path.replace(settings.MEDIA_ROOT, '').lstrip('/')
            
            # EmailAttachment ohne file Field erstellen
            attachment = EmailAttachment.objects.create(
                email=email_message,
                filename=os.path.basename(file_path),
                content_type=content_type,
                size=attachment_data['size'],
                file_path=relative_path,
                storage_backend='local',
                is_processed=False,
                metadata={
                    'original_filename': attachment_data['filename'],
                    'target_directory': target_dir,
                    'imported_at': timezone.now().isoformat(),
                    'source': 'imap_import',
                    'content_type': content_type,
                    'size_bytes': attachment_data['size'],
                    'file_exists': True,
                    'file_path_absolute': file_path,
                }
            )

            logger.info(f"📎 {target_dir.upper()}: {os.path.basename(file_path)} gespeichert ({attachment_data['size']} bytes)")
            return attachment

        except Exception as e:
            logger.error(f"❌ _save_attachment Fehler für {attachment_data.get('filename', 'unknown')}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _decode_header(self, header):
        """Decodiert Email Header"""
        try:
            decoded_parts = decode_header(header)
            decoded_str = ''
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    if encoding:
                        decoded_str += part.decode(encoding)
                    else:
                        decoded_str += part.decode('utf-8', errors='ignore')
                else:
                    decoded_str += str(part)
            return decoded_str.strip()
        except:
            return str(header)

    def _extract_email(self, header):
        """Extrahiert Email aus Header"""
        try:
            # Simple extraction
            if '<' in header and '>' in header:
                start = header.find('<') + 1
                end = header.find('>')
                return header[start:end].strip()
            return header.strip()
        except:
            return header

    def _parse_email_date(self, date_str):
        """Parsed Email Datum"""
        try:
            # Try multiple date formats
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str)
        except:
            return timezone.now()

    def _extract_content(self, msg):
        """Extrahiert Body und Attachments"""
        body_plain = ''
        body_html = ''
        attachments = []

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))

                # Skip multipart containers
                if part.get_content_maintype() == 'multipart':
                    continue

                # Attachments
                if "attachment" in content_disposition or part.get_filename():
                    attachment = self._extract_attachment(part)
                    if attachment:
                        attachments.append(attachment)

                # Body
                elif content_type == "text/plain":
                    body_plain += self._decode_part(part)
                elif content_type == "text/html":
                    body_html += self._decode_part(part)

        else:
            # Not multipart
            content_type = msg.get_content_type()
            if content_type == "text/plain":
                body_plain = self._decode_part(msg)
            elif content_type == "text/html":
                body_html = self._decode_part(msg)

        return body_plain, body_html, attachments

    def _extract_attachment(self, part):
        """Extrahiert einen Attachment"""
        try:
            filename = part.get_filename()
            if not filename:
                # Versuche Content-ID oder anderen Namen
                content_id = part.get('Content-ID', '')
                if content_id:
                    filename = f"attachment_{content_id.strip('<>')}"
                else:
                    return None

            # Decode filename
            filename = self._decode_header(filename)

            # Get content
            payload = part.get_payload(decode=True)
            if not payload:
                return None

            return {
                'filename': filename,
                'content_type': part.get_content_type(),
                'size': len(payload),
                'payload': payload,
            }

        except Exception as e:
            logger.error(f"❌ Fehler beim Extrahieren von Attachment: {e}")
            return None

    def _decode_part(self, part):
        """Decodiert einen Email Part"""
        try:
            payload = part.get_payload(decode=True)
            if payload:
                charset = part.get_content_charset() or 'utf-8'
                return payload.decode(charset, errors='ignore')
            return ''
        except:
            return ''

def import_emails_from_imap(limit=20, dry_run=False, fetch_all=False):
    """
    Importiert Emails vom IMAP Server

    Args:
        limit (int): Maximale Anzahl der zu importierenden E-Mails.
        dry_run (bool): Wenn True, werden keine Daten in der Datenbank gespeichert.
        fetch_all (bool): Wenn True, importiert ALLE Emails, nicht nur UNSEEN.

    Returns:
        int: Anzahl der importierten (oder im dry_run gefundenen) E-Mails.
    """
    try:
        client = IMAPClient()

        with client:
            emails = client.fetch_emails(limit=limit, dry_run=dry_run, fetch_all=fetch_all)

            imported = len(emails)
            if imported > 0:
                if dry_run:
                    logger.info(f"✅ [DRY-RUN] {imported} Emails wären importiert worden")
                else:
                    logger.info(f"✅ {imported} Emails vom IMAP Server importiert")

            return imported

    except Exception as e:
        logger.error(f"❌ IMAP Import fehlgeschlagen: {e}")
        return 0

def test_imap_connection():
    """Testet die IMAP Verbindung"""
    try:
        client = IMAPClient()

        with client:
            if client.is_connected:
                logger.info("✅ IMAP Verbindungstest erfolgreich")

                # Get mailbox status
                status, data = client.connection.status(client.config.get('mailbox', 'INBOX'), '(MESSAGES UNSEEN RECENT)')
                if status == 'OK':
                    logger.info(f"📊 Mailbox Status: {data[0].decode()}")

                return True
            else:
                logger.error("❌ IMAP Verbindungstest fehlgeschlagen")
                return False

    except Exception as e:
        logger.error(f"❌ IMAP Test fehlgeschlagen: {e}")
        return False
