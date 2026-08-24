"""
ABpE Matching Workflow — Celery Tasks
"""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def run_matching_async(self, project_id: str):
    """Matching für ein Projekt async ausführen"""
    try:
        from .models import ProjectRequest, MatchResult
        from .services.matching_engine import MatchingEngine
        from .services.matching_service import MatchingService

        project = ProjectRequest.objects.get(id=project_id)
        logger.info(f"[Task] Matching startet: {project.project_number}")

        results = MatchingEngine().run(project)

        # MatchResult Datensätze anlegen
        MatchResult.objects.filter(project_request=project).delete()
        for r in results:
            skill_details = dict(r.get('skill_details') or {})
            if r.get('match_source') and 'match_source' not in skill_details:
                skill_details['match_source'] = r['match_source']
            if r.get('match_sources') and 'match_sources' not in skill_details:
                skill_details['match_sources'] = r['match_sources']
            MatchResult.objects.create(
                project_request  = project,
                consultant_cv    = r['consultant_cv'],
                overall_score    = r['overall_score'],
                skill_score      = r['skill_score'],
                industry_score   = r['industry_score'],
                experience_score = r['experience_score'],
                location_score   = r['location_score'],
                rank             = r['rank'],
                matched_skills   = r['matched_skills'],
                missing_skills   = r['missing_skills'],
                skill_details    = skill_details,
                calculated_by    = 'matching_engine',
            )

            # ProjectConsultant mitsynchronisieren (Shortlist/Outreach)
            try:
                MatchingService.create_project_consultant(
                    project, r['consultant_cv'], r,
                )
            except Exception as pc_exc:
                logger.warning('ProjectConsultant sync: %s', pc_exc)

        project.status = 'matching'
        project.save(update_fields=['status'])

        logger.info(f"[Task] Matching fertig: {len(results)} Treffer für {project.project_number}")
        return {'success': True, 'count': len(results)}

    except Exception as exc:
        logger.exception(f"[Task] Matching fehlgeschlagen: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task
def run_llm_reranking(project_id: str):
    """LLM-Begründungen für Top-N Ergebnisse generieren"""
    try:
        from .models import ProjectRequest, MatchResult
        from .services.ai_reranker import AIReranker

        project = ProjectRequest.objects.get(id=project_id)
        results = MatchResult.objects.filter(
            project_request=project, rank__lte=20
        ).select_related('consultant_cv')

        reranker = AIReranker()
        for r in results:
            reason = reranker.generate_reason(project, r.consultant_cv)
            r.match_reason   = reason
            r.reason_model   = reranker.model_used
            r.save(update_fields=['match_reason', 'reason_model'])

        logger.info(f"[Task] LLM Reranking fertig: {results.count()} Begründungen")
        return {'success': True}
    except Exception as e:
        logger.exception(f"[Task] LLM Reranking fehlgeschlagen: {e}")
        return {'success': False, 'error': str(e)}


@shared_task
def check_availability_alerts():
    """Prüft ob Berater aus archivierten Projekten wieder verfügbar sind"""
    try:
        from .services.availability_alert import AvailabilityAlertService
        result = AvailabilityAlertService().check_all()
        logger.info(f"[Task] Availability Alerts: {result}")
        return result
    except Exception as e:
        logger.exception(f"[Task] Availability Alert fehlgeschlagen: {e}")
        return {'success': False, 'error': str(e)}


@shared_task
def send_followup_reminders():
    """Sendet Wiedervorlage-Erinnerungen"""
    try:
        from .services.followup_scheduler import FollowupScheduler
        result = FollowupScheduler().process_due()
        logger.info(f"[Task] Followup Reminders: {result}")
        return result
    except Exception as e:
        logger.exception(f"[Task] Followup fehlgeschlagen: {e}")
        return {'success': False, 'error': str(e)}


@shared_task
def sync_crm_batch():
    """Batch-Sync aller ungesyncten Projekte zu SuiteCRM"""
    try:
        from .models import ProjectRequest
        from .services.crm_sync_service import CRMSyncService
        from django.utils import timezone
        import datetime

        # Projekte die noch nicht oder vor >15min gesyncted wurden
        threshold = timezone.now() - datetime.timedelta(minutes=15)
        projects  = ProjectRequest.objects.filter(
            is_archived=False
        ).filter(
            models.Q(crm_synced_at__isnull=True) |
            models.Q(crm_synced_at__lt=threshold)
        )[:50]

        synced = 0
        svc = CRMSyncService()
        for p in projects:
            try:
                svc.sync_project(p)
                synced += 1
            except Exception as e:
                logger.warning(f"CRM Sync fehlgeschlagen für {p.project_number}: {e}")

        logger.info(f"[Task] CRM Batch-Sync: {synced} Projekte")
        return {'success': True, 'synced': synced}
    except Exception as e:
        logger.exception(f"[Task] CRM Batch-Sync fehlgeschlagen: {e}")
        return {'success': False, 'error': str(e)}
