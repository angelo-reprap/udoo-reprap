"""
Signals — Kap. 4 Architektur.
Receiver auf matching_workflow.ProjectConsultant → prozess_engine + Aktivität.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)

try:
    from apps.abpe_matching_workflow.models import ProjectConsultant
except Exception:  # App optional beim migrate
    ProjectConsultant = None


if ProjectConsultant is not None:

    @receiver(post_save, sender=ProjectConsultant, dispatch_uid='shaduler_pc_status')
    def on_project_consultant_save(sender, instance, created, **kwargs):
        """Statuswechsel → Aktivität + Regeln (ausloeser status_wechsel)."""
        try:
            hist = getattr(instance, 'status_history', None) or []
            alt = ''
            if isinstance(hist, list) and len(hist) >= 2:
                prev = hist[-2]
                alt = prev.get('status') if isinstance(prev, dict) else str(prev)
            elif isinstance(hist, list) and len(hist) == 1 and not created:
                # nur ein Eintrag — Wechsel nicht sicher erkennbar
                pass
            neu = getattr(instance, 'status', '') or ''
            if created:
                alt = ''
            if not neu:
                return
            # Bei create immer loggen; bei update nur wenn History ≥2 oder status gesetzt
            if not created and len(hist) < 2:
                return
            from .services import prozess_engine
            owner = getattr(instance, 'assigned_to', None) or getattr(instance, 'owner', None)
            prozess_engine.on_status(instance, alt, neu, user=owner)
        except Exception:
            logger.exception('shaduler ProjectConsultant signal failed')
