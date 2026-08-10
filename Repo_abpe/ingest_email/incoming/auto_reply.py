"""
Auto-Reply System für E-Mail Import Bestätigung
Umgestellt auf EmailStudio.send() — kein direktes SMTP mehr.
"""
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


class EmailAutoReply:
    """Sendet automatische Bestätigungs-E-Mails via EmailStudio"""

    def send_auto_reply(self, to_email, subject, original_subject,
                        email_id, attachment_count):
        try:
            from apps.abpe_email_studio.api import EmailStudio

            EmailStudio.send(
                template      = 'upload_received',
                recipient     = to_email,
                variables     = {
                    'original_subject':  original_subject,
                    'email_id':          str(email_id),
                    'attachment_count':  str(attachment_count),
                    'import_time':       timezone.now().strftime('%d.%m.%Y %H:%M:%S'),
                },
                app_reference = 'ingest_email',
            )
            logger.info(f"✅ Auto-Reply (upload_received) gesendet an {to_email}")
            return True

        except Exception as e:
            logger.error(f"❌ Auto-Reply Fehler für {to_email}: {e}")
            return False


def send_import_confirmation(email_obj):
    """Sendet Bestätigung für importierte E-Mail"""
    try:
        auto_reply = EmailAutoReply()
        success = auto_reply.send_auto_reply(
            to_email         = email_obj.from_email,
            subject          = f"✅ ABpE Import Bestätigung: {email_obj.subject[:50]}...",
            original_subject = email_obj.subject,
            email_id         = email_obj.id,
            attachment_count = email_obj.attachment_count,
        )
        if success:
            email_obj.status = 'CONFIRMED'
            email_obj.confirmation_sent = timezone.now()
            email_obj.save()
            logger.info(f"✅ Import Bestätigung gespeichert für E-Mail {email_obj.id}")
        return success

    except Exception as e:
        logger.error(f"❌ Import Confirmation Fehler für E-Mail {email_obj.id}: {e}")
        return False
