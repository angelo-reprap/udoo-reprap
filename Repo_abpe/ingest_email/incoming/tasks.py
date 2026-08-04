from celery import shared_task
from .cv_parser import process_cv_email
from .models import EmailMessage
import logging

logger = logging.getLogger(__name__)

@shared_task(name='process_cv_email_task')
def process_cv_email_task(email_id):
    """Verarbeitet CV-E-Mail asynchron"""
    try:
        email = EmailMessage.objects.get(id=email_id)
        result = process_cv_email(email)
        logger.info(f"CV-Parser Ergebnis für E-Mail {email_id}: {result}")
        return result
    except Exception as e:
        logger.error(f"Fehler in CV-Parser Task: {e}")
        return {'success': False, 'error': str(e)}
