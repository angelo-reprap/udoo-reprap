"""
ABpE Matching Workflow — Signals
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ProjectConsultant

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ProjectConsultant)
def on_project_consultant_saved(sender, instance, created, **kwargs):
    """CRM Sync bei Status-Änderung (wenn aktiviert)"""
    try:
        import json
        from pathlib import Path
        p   = Path(__file__).resolve().parent.parent.parent / 'settings.json'
        cfg = json.loads(p.read_text(encoding='utf-8'))
        if cfg.get('matching', {}).get('crm_sync', {}).get('auto_sync_on_status_change'):
            from .services.crm_sync_service import CRMSyncService
            CRMSyncService().sync_project_consultant(instance)
    except Exception as e:
        logger.warning(f"CRM Auto-Sync fehlgeschlagen: {e}")
