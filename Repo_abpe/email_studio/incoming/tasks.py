"""
ABpE Email Studio — Celery Tasks
==================================
Asynchroner E-Mail Versand über die Warteschlange.
"""
from celery import shared_task
from django.utils import timezone
import logging

log = logging.getLogger('abpe_email_studio.tasks')


@shared_task(name='email_studio.send_queued', bind=True, max_retries=3)
def send_queued_email(self, queue_id: str):
    """
    Verarbeitet einen Queue-Eintrag und sendet die E-Mail.
    """
    from .models import EmailQueue, QueueStatus
    from .services.sender import EmailSender

    try:
        item = EmailQueue.objects.select_related('template').get(queue_id=queue_id)
    except EmailQueue.DoesNotExist:
        log.error(f'Queue item nicht gefunden: {queue_id}')
        return

    if item.status not in [QueueStatus.PENDING, QueueStatus.FAILED]:
        return

    item.status = QueueStatus.RUNNING
    item.celery_task_id = self.request.id or ''
    item.save(update_fields=['status', 'celery_task_id'])

    try:
        user = None
        if item.user_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.filter(pk=item.user_id).first()

        sender = EmailSender()
        result = sender.send(
            template      = item.template,
            to_emails     = item.to_emails,
            variables     = item.variables,
            user          = user,
            cc_extra      = item.cc_emails,
            bcc_extra     = item.bcc_emails,
            task_reference = item.task_reference,
            app_reference  = item.app_reference,
        )

        item.status       = QueueStatus.DONE
        item.processed_at = timezone.now()
        item.save(update_fields=['status', 'processed_at'])
        log.info(f'Queue {queue_id} erfolgreich gesendet')
        return result

    except Exception as exc:
        item.retry_count  += 1
        item.error_message = str(exc)

        if item.retry_count >= item.max_retries:
            item.status = QueueStatus.FAILED
            item.save(update_fields=['status', 'retry_count', 'error_message'])
            log.error(f'Queue {queue_id} endgültig fehlgeschlagen: {exc}')
        else:
            item.status = QueueStatus.PENDING
            item.save(update_fields=['status', 'retry_count', 'error_message'])
            raise self.retry(exc=exc, countdown=60 * item.retry_count)


@shared_task(name='email_studio.cleanup_log')
def cleanup_old_logs(days: int = 90):
    """
    Löscht E-Mail Logs älter als X Tage.
    """
    from .models import EmailLog
    from django.utils import timezone
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = EmailLog.objects.filter(sent_at__lt=cutoff).delete()
    log.info(f'EmailLog Cleanup: {deleted} Einträge gelöscht (älter als {days} Tage)')
    return deleted
