"""
ABpE Doc Studio — Celery Tasks

Tasks:
  generate_queued_doc   : verarbeitet DocQueue-Einträge
  generate_doc_async    : direkter Async-Aufruf (ohne Queue-Model)
  convert_to_pdf_task   : konvertiert .docx → .pdf via LibreOffice
  cleanup_old_doc_logs  : löscht Log-Einträge älter als N Tage
"""
import logging
from celery import shared_task
from django.utils import timezone

log = logging.getLogger('abpe_doc_studio.tasks')


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def generate_queued_doc(self, queue_id: str):
    """
    Verarbeitet einen DocQueue-Eintrag.
    Wird von DocStudio.generate(async_generate=True) aufgerufen.
    """
    from .models import DocQueue, QueueStatus

    try:
        item = DocQueue.objects.get(queue_id=queue_id)
    except DocQueue.DoesNotExist:
        log.error(f'DocQueue {queue_id} nicht gefunden')
        return

    if item.status == QueueStatus.CANCELLED:
        log.info(f'DocQueue {queue_id} wurde abgebrochen — überspringe')
        return

    item.status = QueueStatus.RUNNING
    item.save(update_fields=['status'])

    try:
        from .services.assembler import DocAssembler

        user = None
        if item.user_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.filter(pk=item.user_id).first()

        assembler = DocAssembler()
        result = assembler.generate(
            template_identifier = item.template.identifier,
            variables           = item.variables,
            context_ref         = item.context_ref,
            scope               = item.scope,
            engine              = item.engine,
            user                = user,
        )

        # Optional: E-Mail versenden
        if item.send_email_to and item.email_template and result.get('success'):
            _send_doc_via_email(
                doc_log          = result['doc_log'],
                email_template   = item.email_template,
                recipients       = item.send_email_to,
                user             = user,
                context_ref      = item.context_ref,
            )

        item.status       = QueueStatus.DONE
        item.processed_at = timezone.now()
        item.save(update_fields=['status', 'processed_at'])

        log.info(f'DocQueue {queue_id} erfolgreich verarbeitet')
        return result

    except Exception as exc:
        log.error(f'DocQueue {queue_id} fehlgeschlagen: {exc}')
        item.retry_count  += 1
        item.error_message = str(exc)

        if item.retry_count >= item.max_retries:
            item.status = QueueStatus.FAILED
            item.save(update_fields=['status', 'retry_count', 'error_message'])
        else:
            item.status = QueueStatus.PENDING
            item.save(update_fields=['status', 'retry_count', 'error_message'])
            raise self.retry(exc=exc, countdown=60 * item.retry_count)


@shared_task
def generate_doc_async(template_identifier: str, variables: dict,
                       context_ref: str = '', scope: str = '',
                       engine: str = 'BOTH', user_id: int = None,
                       send_email_to: list = None,
                       email_template: str = ''):
    """
    Direkter Async-Task ohne Queue-Model.
    Für einfache Fire-and-Forget Aufrufe.
    """
    from .services.assembler import DocAssembler

    user = None
    if user_id:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.filter(pk=user_id).first()

    assembler = DocAssembler()
    result = assembler.generate(
        template_identifier = template_identifier,
        variables           = variables,
        context_ref         = context_ref,
        scope               = scope,
        engine              = engine,
        user                = user,
    )

    if send_email_to and email_template and result.get('success'):
        _send_doc_via_email(
            doc_log        = result['doc_log'],
            email_template = email_template,
            recipients     = send_email_to,
            user           = user,
            context_ref    = context_ref,
        )

    return result


@shared_task
def convert_to_pdf_task(docx_path: str, output_dir: str = None):
    """
    Konvertiert eine .docx-Datei zu PDF via LibreOffice.
    Wird von DocAssembler aufgerufen wenn engine=BOTH oder PDF.
    """
    from .services.exporter import DocExporter
    exporter = DocExporter()
    return exporter.convert_docx_to_pdf(docx_path, output_dir)


@shared_task
def cleanup_old_doc_logs(days: int = 365):
    """
    Bereinigt alte DocLog-Einträge (Standard: älter als 1 Jahr).
    Löscht NICHT die Dateien — nur die DB-Einträge.
    Empfehlung: täglich via Celery Beat laufen lassen.
    """
    from .models import DocLog
    cutoff = timezone.now() - timezone.timedelta(days=days)
    deleted, _ = DocLog.objects.filter(generated_at__lt=cutoff).delete()
    log.info(f'DocLog Cleanup: {deleted} Einträge gelöscht (älter als {days} Tage)')
    return {'deleted': deleted}


# ── Hilfsfunktion ─────────────────────────────────────────────────────────────

def _send_doc_via_email(doc_log, email_template: str, recipients: list,
                         user=None, context_ref: str = ''):
    """
    Sendet generiertes Dokument als E-Mail-Anhang via Email Studio.
    """
    try:
        from apps.abpe_email_studio.api import EmailStudio

        # PDF bevorzugen, sonst DOCX
        attach_path = doc_log.file_path_pdf or doc_log.file_path_docx
        if not attach_path:
            log.warning(f'Kein Dateipfad in DocLog {doc_log.log_id}')
            return

        EmailStudio.send(
            template       = email_template,
            recipient      = recipients,
            variables      = {'context_ref': context_ref},
            user           = user,
            task_reference = context_ref,
            app_reference  = 'abpe_doc_studio',
            attachments    = [attach_path],
        )
        log.info(f'Dokument per E-Mail versendet: {attach_path} → {recipients}')

    except Exception as e:
        log.error(f'E-Mail-Versand nach Generierung fehlgeschlagen: {e}')
