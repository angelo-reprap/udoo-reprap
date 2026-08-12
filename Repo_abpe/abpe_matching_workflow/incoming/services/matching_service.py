"""
ABpE Matching Workflow — MatchingService v2
Direkt gegen cv_extractor.Consultant — kein eigenes Consultant-Modell mehr
"""
import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

from django.utils import timezone
from django.db.models import Avg, Count

from ..models import ProjectRequest, ProjectConsultant

logger = logging.getLogger(__name__)


def _load_matching_cfg() -> Dict:
    import json
    from pathlib import Path
    try:
        p = Path(__file__).resolve().parent.parent.parent.parent / 'settings.json'
        return json.loads(p.read_text(encoding='utf-8')).get('matching', {})
    except Exception:
        return {}


class MatchingService:
    """Orchestriert Matching-Engine + AI-Reranker + ProjectConsultant Erstellung"""

    # ──────────────────────────────────────────────────────
    # HAUPT-METHODE
    # ──────────────────────────────────────────────────────

    @staticmethod
    def find_consultants(
        project: ProjectRequest,
        limit: int = 20,
        min_score: float = 0.30,
    ) -> List[Dict[str, Any]]:
        """
        Findet passende Berater für ein Projekt.
        Nutzt MatchingEngine (cv_extractor DB) direkt.
        """
        try:
            from .matching_engine import MatchingEngine
            results = MatchingEngine().run(project, limit=limit, min_score=min_score)
            logger.info(f"✅ {len(results)} Treffer für {project.project_number}")
            return results
        except Exception as e:
            logger.exception(f"find_consultants: {e}")
            return []

    # ──────────────────────────────────────────────────────
    # PROJECT CONSULTANT ANLEGEN / AKTUALISIEREN
    # ──────────────────────────────────────────────────────

    @staticmethod
    def create_project_consultant(
        project: ProjectRequest,
        consultant_cv,
        match_details: Dict[str, Any],
    ) -> ProjectConsultant:
        """
        Erstellt oder aktualisiert ProjectConsultant.
        consultant_cv ist ein cv_extractor.Consultant Objekt.
        """
        pc, created = ProjectConsultant.objects.update_or_create(
            project=project,
            consultant_cv=consultant_cv,
            defaults={
                'match_score':   match_details.get('score', 0),
                'match_reason':  match_details.get('match_reason', ''),
                'match_details': {
                    **match_details,
                    'calculated_at':   datetime.now().isoformat(),
                    'matched_skills':  match_details.get('matched_skills', []),
                    'missing_skills':  match_details.get('missing_skills', []),
                },
                'matched_by': 'system',
                'status':     'identified',
            }
        )

        if created:
            pc.status_history.append({
                'from':  '',
                'to':    'identified',
                'at':    datetime.now().isoformat(),
                'note':  f"Auto-Matching Score {match_details.get('score', 0):.2f}",
                'user':  'system',
            })
            pc.save(update_fields=['status_history'])
            logger.info(
                f"✅ ProjectConsultant: {consultant_cv.full_name} → "
                f"{project.project_number} (Score {match_details.get('score', 0):.2f})"
            )
        return pc

    # ──────────────────────────────────────────────────────
    # HILFSMETHODEN
    # ──────────────────────────────────────────────────────

    @staticmethod
    def _extract_min_experience(description: str) -> int:
        patterns = [
            r'(\d+)[\+]?\s*Jahre',
            r'(\d+)[\+]?\s*jährige',
            r'(\d+)[\+]?\s*years',
            r'(\d+)[\+]?\s*Jahren',
            r'min\.\s*(\d+)\s*Jahre',
            r'mindestens\s*(\d+)\s*Jahre',
        ]
        for pattern in patterns:
            m = re.search(pattern, description, re.IGNORECASE)
            if m:
                return int(m.group(1))
        return 0

    # ──────────────────────────────────────────────────────
    # BATCH MATCHING
    # ──────────────────────────────────────────────────────

    @staticmethod
    def batch_match_projects(
        project_ids: List[str],
        limit_per_project: int = 5,
    ) -> Dict[str, Any]:
        results   = {}
        total     = 0

        for pid in project_ids:
            try:
                project = ProjectRequest.objects.get(id=pid)
                matches = MatchingService.find_consultants(project, limit=limit_per_project)

                for match in matches:
                    MatchingService.create_project_consultant(
                        project,
                        match['consultant_cv'],
                        match,
                    )
                    total += 1

                results[pid] = {
                    'project':       project.title,
                    'matches_found': len(matches),
                    'status':        'success',
                }
            except Exception as e:
                results[pid] = {'error': str(e), 'status': 'failed'}

        logger.info(f"Batch-Matching: {total} Matches für {len(project_ids)} Projekte")
        return results

    # ──────────────────────────────────────────────────────
    # STATISTIKEN
    # ──────────────────────────────────────────────────────

    @staticmethod
    def get_matching_statistics() -> Dict[str, Any]:
        total_matches = ProjectConsultant.objects.count()
        avg_score     = (
            ProjectConsultant.objects.aggregate(Avg('match_score'))['match_score__avg'] or 0
        )
        project_stats = list(
            ProjectRequest.objects.annotate(match_count=Count('consultants'))
            .values('id', 'title', 'match_count')[:10]
        )
        return {
            'total_matches':    total_matches,
            'average_score':    round(avg_score, 2),
            'matches_this_week': ProjectConsultant.objects.filter(
                created_at__gte=timezone.now() - timezone.timedelta(days=7)
            ).count(),
            'project_stats':    project_stats,
            'timestamp':        timezone.now().isoformat(),
        }
