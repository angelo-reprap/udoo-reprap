"""
cv_extractor/signals.py
"""

import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import ExtractionJob, ExtractedCV, ExtractionLog, UploadedPDF

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ExtractionJob)
def job_completed(sender, instance, created, **kwargs):
    """Logeintrag wenn ein Job abgeschlossen wird."""
    if instance.status == 'completed':
        ExtractionLog.objects.create(
            job=instance,
            step='completion',
            message=f'Job {instance.id} abgeschlossen: {instance.file_name}',
            level='INFO',
        )
        logger.info(f"Job {instance.id} abgeschlossen: {instance.file_name}")


@receiver(pre_save, sender=ExtractionJob)
def job_started(sender, instance, **kwargs):
    """Logeintrag wenn ein neuer Job angelegt wird."""
    if instance.id is None and instance.status == 'pending':
        logger.info(f"Job gestartet: {instance.file_name}")


@receiver(post_save, sender=ExtractedCV)
def extracted_cv_saved(sender, instance, created, **kwargs):
    """Logeintrag wenn ein ExtractedCV gespeichert wird."""
    if created:
        ExtractionLog.objects.create(
            job=instance.job,
            step='save',
            message=f'ExtractedCV gespeichert: {instance.consultant_name or instance.consultant_aid or "Unnamed"}',
            level='INFO',
        )


@receiver(post_save, sender=UploadedPDF)
def start_pipeline_on_new_pdf(sender, instance, created, **kwargs):
    """
    Startet den Celery-Task wenn ein neues PDF mit status='uploaded' gespeichert wird.

    Dies ist der EINZIGE Ort wo process_pdf_task gestartet wird.
    Die View (upload_pdf_api_async) startet keinen Task – nur speichern.

    update_fields-Guard verhindert Rekursion beim Speichern von
    task_id und status innerhalb dieses Signals.
    """
    if not created:
        return
    if instance.status != 'uploaded':
        return

    from .tasks import process_pdf_task

    # Status sofort auf processing setzen
    UploadedPDF.objects.filter(pk=instance.pk).update(status='processing')

    # Task starten
    task = process_pdf_task.delay(instance.id)

    # Task-ID speichern (update_fields verhindert erneutes Signal)
    UploadedPDF.objects.filter(pk=instance.pk).update(task_id=task.id)

    logger.info(f"Task gestartet: {instance.filename} → task_id={task.id}")
