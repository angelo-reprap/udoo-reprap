"""
ABpE Matching Workflow — Availability Alert Service
Prüft ob Berater aus archivierten Projekten wieder verfügbar sind
"""
import logging
from datetime import date
from typing import Dict

logger = logging.getLogger(__name__)


class AvailabilityAlertService:
    """
    Scheduler-Task: Prüft täglich ob Berater die früher
    in der engeren Auswahl waren wieder verfügbar sind.
    """

    def check_all(self) -> Dict:
        """Prüft alle platzierten Berater auf Verfügbarkeit"""
        try:
            from apps.cv_extractor.models import Consultant
            from ..models import ProjectConsultant, ProjectRequest

            alerts = []
            today  = date.today()

            # Berater die in archivierten Projekten waren aber nicht platziert
            pcs = ProjectConsultant.objects.filter(
                project__is_archived=True,
                status__in=['interested', 'offer_sent', 'client_interested',
                            'interview_done', 'rejected'],
            ).select_related('consultant_cv', 'project').distinct()

            for pc in pcs:
                c = pc.consultant_cv
                # Ist availability gesetzt und liegt in der Zukunft/Gegenwart?
                avail = getattr(c, 'availability', '') or ''
                if not avail:
                    continue

                # Prüfe ob "ab sofort" oder Datum in der Vergangenheit
                is_available = (
                    'sofort' in avail.lower() or
                    'immediately' in avail.lower() or
                    'verfügbar' in avail.lower()
                )

                if is_available:
                    alerts.append({
                        'consultant_aid':  c.aid,
                        'consultant_name': c.full_name,
                        'project_number':  pc.project.project_number,
                        'project_title':   pc.project.title,
                        'customer_name':   pc.project.customer_name,
                        'last_status':     pc.status,
                        'match_score':     pc.match_score,
                    })

            logger.info(f"Availability Alerts: {len(alerts)} potenzielle Treffer")
            return {'success': True, 'alerts': alerts, 'count': len(alerts)}

        except Exception as e:
            logger.exception(f"Availability Alert fehlgeschlagen: {e}")
            return {'success': False, 'error': str(e)}
