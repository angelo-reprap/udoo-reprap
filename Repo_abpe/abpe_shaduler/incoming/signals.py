"""
Signals — Kap. 4 Architektur.
Receiver auf matching_workflow.ProjectConsultant → prozess_engine + Aktivität.
Status-Altwert per pre_save (zuverlässiger als nur status_history).
"""
import logging

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)
User = get_user_model()

try:
    from apps.abpe_matching_workflow.models import ProjectConsultant
except Exception:
    ProjectConsultant = None


def _resolve_owner(instance):
    """Zugewiesenen Disponenten finden (ProjectRequest.created_by = Username)."""
    for attr in ('assigned_to', 'owner', 'created_by'):
        val = getattr(instance, attr, None)
        if val is not None and hasattr(val, 'pk'):
            return val
    project = getattr(instance, 'project', None)
    if project is not None:
        for attr in ('assigned_to', 'owner', 'created_by'):
            val = getattr(project, attr, None)
            if val is not None and hasattr(val, 'pk'):
                return val
            if isinstance(val, str) and val.strip():
                u = User.objects.filter(username=val.strip()).first()
                if u:
                    return u
    return None


if ProjectConsultant is not None:

    @receiver(pre_save, sender=ProjectConsultant, dispatch_uid='shaduler_pc_presave')
    def cache_old_pc_status(sender, instance, **kwargs):
        if not instance.pk:
            instance._shaduler_old_status = None
            return
        try:
            old = (
                sender.objects.filter(pk=instance.pk)
                .values_list('status', flat=True)
                .first()
            )
            instance._shaduler_old_status = old
        except Exception:
            instance._shaduler_old_status = None

    @receiver(post_save, sender=ProjectConsultant, dispatch_uid='shaduler_pc_status')
    def on_project_consultant_save(sender, instance, created, **kwargs):
        """Statuswechsel → Aktivität + Regeln (ausloeser status_wechsel)."""
        try:
            neu = getattr(instance, 'status', '') or ''
            if not neu:
                return
            alt = getattr(instance, '_shaduler_old_status', None)
            if alt is None and not created:
                # Fallback status_history
                hist = getattr(instance, 'status_history', None) or []
                if isinstance(hist, list) and len(hist) >= 2:
                    prev = hist[-2]
                    alt = prev.get('status') if isinstance(prev, dict) else str(prev)
            if not created and alt == neu:
                return
            if created:
                alt = ''

            from .services import prozess_engine
            owner = _resolve_owner(instance)
            # Ohne Owner: nur Aktivität, keine Folgeaufgaben (run_regel braucht User)
            if owner is None and not created:
                # trotzdem Historie
                from .services import aktivitaet_service
                aktivitaet_service.schreiben(
                    medium='system',
                    titel=f'Status {alt or "—"} → {neu}',
                    ref_type='match',
                    ref_id=str(instance.pk),
                    user=None,
                    details={'alt': alt, 'neu': neu, 'no_owner': True},
                )
                return
            if owner is None:
                return
            prozess_engine.on_status(instance, alt or '', neu, user=owner)
        except Exception:
            logger.exception('shaduler ProjectConsultant signal failed')
