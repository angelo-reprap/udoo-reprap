"""
ABpE Matching Workflow — Followup Scheduler
Verarbeitet fällige Wiedervorlagen
"""
import logging
from datetime import timedelta
from typing import Dict

logger = logging.getLogger(__name__)


class FollowupScheduler:
    """Verarbeitet fällige Wiedervorlage-Tasks"""

    def process_due(self) -> Dict:
        """Findet alle ProjectConsultants die Nachfassen brauchen"""
        try:
            from django.utils import timezone
            from ..models import ProjectConsultant, FollowupRule

            now     = timezone.now()
            default = FollowupRule.get_default()
            delay_h = default.followup_delay_hours if default else 48

            # Kontaktierte Berater ohne Antwort nach delay_hours
            threshold = now - timedelta(hours=delay_h)
            due = ProjectConsultant.objects.filter(
                status='contacted',
                contacted_at__lte=threshold,
                consultant_response_at__isnull=True,
                followup_sent_at__isnull=True,
            ).select_related('project', 'consultant_cv')

            processed = 0
            for pc in due:
                try:
                    # Status auf followup_sent setzen
                    pc.set_status('followup_sent', note='Automatische Wiedervorlage')

                    # Auto-E-Mail wenn konfiguriert
                    rule = None
                    contact = pc.project.contacts.filter(
                        role='decision_maker'
                    ).first()
                    if contact and contact.followup_rule:
                        rule = contact.followup_rule

                    if (rule and rule.auto_email_on_no_reach) or \
                       (default and default.auto_email_on_no_reach):
                        logger.info(
                            f"Auto-Followup E-Mail: {pc.consultant_cv.full_name} "
                            f"→ {pc.project.project_number}"
                        )
                    processed += 1
                except Exception as e:
                    logger.warning(f"Followup fehlgeschlagen für {pc.id}: {e}")

            logger.info(f"Followup Scheduler: {processed} verarbeitet")
            return {'success': True, 'processed': processed}

        except Exception as e:
            logger.exception(f"Followup Scheduler fehlgeschlagen: {e}")
            return {'success': False, 'error': str(e)}
