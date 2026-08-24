"""
ABpE Matching Workflow — Views + API Endpoints
Alle API-Endpunkte für das Matching-Portal
"""
import json
import logging
from datetime import date, timedelta

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count, Avg
from django.utils import timezone
from django.core.paginator import Paginator

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes

from .models import (
    ProjectRequest,
    ProjectContact,
    ProjectConsultant,
    MatchResult,
    EmailTemplate,
    EmailHistory,
    FollowupRule,
)

logger = logging.getLogger(__name__)


def _load_matching_settings():
    """Lädt matching-Block aus settings.json"""
    import json
    from pathlib import Path
    try:
        p = Path(__file__).resolve().parent.parent.parent / 'settings.json'
        cfg = json.loads(p.read_text(encoding='utf-8'))
        return cfg.get('matching', {})
    except Exception:
        return {}


def _matching_shortlist_limit() -> int:
    """
    Top-N nach Score. 0 = kein Limit (alle ≥ Schwellwert).
    settings matching.shortlist_limit; Default 0.
    """
    try:
        raw = _load_matching_settings().get('shortlist_limit', 0)
        n = int(0 if raw is None else raw)
    except (TypeError, ValueError):
        n = 0
    if n <= 0:
        return 0
    return max(1, min(n, 2000))


# ============================================================
# PORTAL-VIEWS (Template-Render)
# ============================================================

@login_required
def index(request):
    """Haupt-View — lädt alle Tabs via JS"""
    import os
    lang       = request.session.get('language', 'de')
    cfg        = _load_matching_settings()
    active_tab = request.GET.get('tab', 'anfragen')
    active_project_id = request.GET.get('project', '')

    # i18n inline laden — kein async, kein Timing-Problem
    i18n_data = {}
    try:
        from django.conf import settings as django_settings
        i18n_path = os.path.join(
            django_settings.BASE_DIR,
            'apps', 'abpe_ui', 'static', 'abpe_ui',
            'i18n', lang, 'modules', 'matching', 'matching.json'
        )
        if not os.path.exists(i18n_path):
            i18n_path = i18n_path.replace(f'/{lang}/', '/de/')
        with open(i18n_path, encoding='utf-8') as f:
            i18n_data = json.load(f)
    except Exception:
        pass

    return render(request, 'matching/index.html', {
        'current_lang':       lang,
        'matching_cfg':       json.dumps(cfg),
        'matching_i18n':      json.dumps(i18n_data),
        'active_module':      'matching',
        'active_tab':         active_tab,
        'active_project_id':  active_project_id,
    })


# ============================================================
# API: DASHBOARD STATS
# ============================================================

@extend_schema(
    summary="Matching Dashboard Statistiken",
    responses={200: OpenApiResponse(description="Stats", response=OpenApiTypes.OBJECT)}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_stats(request):
    try:
        total    = ProjectRequest.objects.count()
        active   = ProjectRequest.objects.filter(status__in=['active','matching','offers_sent','interviews']).count()
        placed   = ProjectRequest.objects.filter(status='placed').count()
        archived = ProjectRequest.objects.filter(is_archived=True).count()

        contacted    = ProjectConsultant.objects.filter(status='contacted').count()
        in_progress  = ProjectConsultant.objects.filter(
            status__in=['interested','offer_sent','client_interested','interview_scheduled']
        ).count()
        needs_followup = sum(
            1 for pc in ProjectConsultant.objects.filter(status='contacted').select_related()
            if pc.needs_followup
        )

        return Response({
            'success': True,
            'projects': {
                'total': total, 'active': active,
                'placed': placed, 'archived': archived,
            },
            'consultants': {
                'contacted': contacted,
                'in_progress': in_progress,
                'needs_followup': needs_followup,
            }
        })
    except Exception as e:
        logger.exception(f"api_stats: {e}")
        return Response({'success': False, 'error': str(e)}, status=500)


# ============================================================
# API: PROJECT REQUESTS
# ============================================================

@extend_schema(summary="Projektanfragen Liste")
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_project_list(request):
    try:
        qs = ProjectRequest.objects.all().order_by('-created_at')

        # Filter
        status   = request.GET.get('status')
        priority = request.GET.get('priority')
        search   = request.GET.get('search')
        archived = request.GET.get('archived', '0')

        if status:
            qs = qs.filter(status=status)
        if priority:
            qs = qs.filter(priority=priority)
        if search:
            qs = qs.filter(
                Q(project_number__icontains=search) |
                Q(title__icontains=search) |
                Q(customer_name__icontains=search)
            )
        if archived == '0':
            qs = qs.filter(is_archived=False)

        # Paginierung
        page     = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        paginator = Paginator(qs, per_page)
        page_obj  = paginator.get_page(page)

        data = []
        for p in page_obj:
            match_count = p.consultants.count()
            data.append({
                'id':             str(p.id),
                'project_number': p.project_number,
                'title':          p.title,
                'customer_name':  p.customer_name,
                'status':         p.status,
                'priority':       p.priority,
                'match_count':    match_count,
                'is_archived':    p.is_archived,
                'created_at':     p.created_at.isoformat(),
                'crm_account_id': p.crm_account_id,
            })

        return Response({
            'success':    True,
            'results':    data,
            'total':      paginator.count,
            'page':       page,
            'num_pages':  paginator.num_pages,
        })
    except Exception as e:
        logger.exception(f"api_project_list: {e}")
        return Response({'success': False, 'error': str(e)}, status=500)


@extend_schema(summary="Projektanfrage Detail")
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_project_detail(request, project_id):
    try:
        p = get_object_or_404(ProjectRequest, id=project_id)
        contacts = []
        for c in p.contacts.all().order_by('sort_order'):
            contacts.append({
                'id':            str(c.id),
                'full_name':     c.full_name,
                'email':         c.email,
                'phone':         c.phone,
                'role':          c.role,
                'personal_note': c.personal_note,
                'crm_contact_id': c.crm_contact_id,
            })

        return Response({
            'success': True,
            'project': {
                'id':               str(p.id),
                'project_number':   p.project_number,
                'title':            p.title,
                'description':      p.description,
                'customer_name':    p.customer_name,
                'status':           p.status,
                'priority':         p.priority,
                'required_skills':  p.required_skills,
                'nice_to_have_skills': p.nice_to_have_skills,
                'start_date':       p.start_date.isoformat() if p.start_date else None,
                'duration_months':  p.duration_months,
                'location':         p.location,
                'remote_possible':  p.remote_possible,
                'rate_min':         p.rate_min,
                'rate_max':         p.rate_max,
                'shortlist_threshold': p.shortlist_threshold,
                'crm_account_id':   p.crm_account_id,
                'crm_opportunity_id': p.crm_opportunity_id,
                'crm_synced_at':    p.crm_synced_at.isoformat() if p.crm_synced_at else None,
                'is_archived':      p.is_archived,
                'close_reason':     p.close_reason,
                'contacts':         contacts,
            }
        })
    except Exception as e:
        logger.exception(f"api_project_detail: {e}")
        return Response({'success': False, 'error': str(e)}, status=500)


@extend_schema(summary="Projektanfrage erstellen")
@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_project_create(request):
    try:
        data = request.data
        p = ProjectRequest.objects.create(
            title=data.get('title', ''),
            description=data.get('description', ''),
            customer_name=data.get('customer_name', ''),
            customer_contact_person=data.get('customer_contact_person', ''),
            customer_email=data.get('customer_email', ''),
            customer_phone=data.get('customer_phone', ''),
            customer_id=data.get('customer_id', ''),
            crm_account_id=data.get('crm_account_id', ''),
            crm_contact_id=data.get('crm_contact_id', ''),
            required_skills=data.get('required_skills', []),
            nice_to_have_skills=data.get('nice_to_have_skills', []),
            extracted_technologies=data.get('extracted_technologies', []),
            start_date=data.get('start_date') or None,
            duration_months=int(data.get('duration_months', 0)),
            location=data.get('location', ''),
            remote_possible=data.get('remote_possible', True),
            workload_percent=int(data.get('workload_percent', 100)),
            rate_min=data.get('rate_min') or None,
            rate_max=data.get('rate_max') or None,
            rate_type=data.get('rate_type', 'hourly'),
            source_text=data.get('source_text', ''),
            source_email_id=data.get('source_email_id', ''),
            priority=int(data.get('priority', 3)),
            shortlist_threshold=float(data.get('shortlist_threshold', 0.50)),
            created_by=request.user.username,
        )
        logger.info(f"ProjectRequest erstellt: {p.project_number}")
        return Response({'success': True, 'id': str(p.id), 'project_number': p.project_number})
    except Exception as e:
        logger.exception(f"api_project_create: {e}")
        return Response({'success': False, 'error': str(e)}, status=500)


@extend_schema(summary="Projektanfrage aktualisieren")
@csrf_exempt
@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def api_project_update(request, project_id):
    try:
        p    = get_object_or_404(ProjectRequest, id=project_id)
        data = request.data

        updatable = [
            'title', 'description', 'customer_name', 'customer_contact_person',
            'customer_email', 'customer_phone', 'status', 'priority',
            'required_skills', 'nice_to_have_skills', 'extracted_technologies',
            'start_date', 'duration_months', 'location', 'remote_possible',
            'rate_min', 'rate_max', 'rate_type', 'shortlist_threshold',
            'crm_account_id', 'crm_contact_id', 'crm_opportunity_id',
            'weight_skills_required', 'weight_skills_nice',
            'weight_industry', 'weight_experience', 'weight_location',
        ]
        for field in updatable:
            if field in data:
                setattr(p, field, data[field])
        p.save()
        return Response({'success': True, 'id': str(p.id)})
    except Exception as e:
        logger.exception(f"api_project_update: {e}")
        return Response({'success': False, 'error': str(e)}, status=500)


# ============================================================
# API: MATCHING
# ============================================================

def _project_skill_names(project) -> list:
    """Flache Skill-Namen aus required_skills + extracted_technologies."""
    names = []
    for s in (project.required_skills or []):
        if isinstance(s, dict) and s.get('name'):
            names.append(str(s['name']).strip())
        elif isinstance(s, str) and s.strip():
            names.append(s.strip())
    for t in (getattr(project, 'extracted_technologies', None) or []):
        if t and str(t).strip() and str(t).strip() not in names:
            names.append(str(t).strip())
    return names


@extend_schema(summary="Matching starten (async)")
@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_run_matching(request, project_id):
    """Startet Matching-Celery-Task für ein Projekt"""
    try:
        p = get_object_or_404(ProjectRequest, id=project_id)
        skill_names = _project_skill_names(p)
        if not skill_names:
            return Response({
                'success': False,
                'error': (
                    'Anfrage hat keine Skills (required_skills). '
                    'Bitte Skills setzen („Erneut matchen“ oder Anfrage bearbeiten) '
                    '— sonst liefert Matching Blindlinge.'
                ),
                'code': 'no_skills',
            }, status=400)

        p.status = 'matching'
        p.save(update_fields=['status'])

        # Celery Task starten
        try:
            from .tasks import run_matching_async
            task = run_matching_async.delay(str(p.id))
            task_id = task.id
        except Exception as te:
            logger.warning(f"Celery nicht verfügbar: {te} — synchrones Matching")
            task_id = None
            from .tasks import run_matching_async
            # bind=True → .run() setzt self; direkter Aufruf würde project_id als self nehmen
            run_matching_async.run(str(p.id))

        return Response({
            'success':  True,
            'task_id':  task_id,
            'status':   p.status,
            'skills':   skill_names,
            'message':  'Matching gestartet',
        })
    except Exception as e:
        logger.exception(f"api_run_matching: {e}")
        return Response({'success': False, 'error': str(e)}, status=500)


@extend_schema(summary="Shortlist abrufen")
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_shortlist(request, project_id):
    """Shortlist-Ergebnisse für ein Projekt"""
    try:
        p         = get_object_or_404(ProjectRequest, id=project_id)
        threshold = float(request.GET.get('threshold', p.shortlist_threshold or 0.45))
        skill_names = _project_skill_names(p)

        try:
            results = MatchResult.objects.filter(
                project_request=p
            ).select_related('consultant_cv').order_by('rank', '-overall_score')
        except Exception:
            results = MatchResult.objects.filter(
                project_request=p
            ).select_related('consultant_cv').order_by('-overall_score')

        # ProjectConsultant-IDs für Outreach/Mail (MatchResult.id ≠ PC.id)
        pc_by_cv = {
            pc.consultant_cv_id: pc
            for pc in ProjectConsultant.objects.filter(project=p).only(
                'id', 'consultant_cv_id', 'status'
            )
        }

        def _as_dict(val):
            return val if isinstance(val, dict) else {}

        def _as_list(val, fallback=None):
            if isinstance(val, list):
                return list(val)
            if isinstance(val, tuple):
                return list(val)
            if isinstance(val, str) and val.strip():
                return [val.strip()]
            return list(fallback or [])

        data = []
        source_counts = {'db': 0, 'es': 0, 'gulp': 0, 'flm': 0}
        for r in results:
            try:
                c = r.consultant_cv
                if c is None:
                    continue
                pc = pc_by_cv.get(c.id)
                email = ''
                try:
                    email = (getattr(c, 'email', None) or '').split(';')[0].strip()
                except Exception:
                    email = ''
                sd = _as_dict(r.skill_details)
                crm = _as_dict(sd.get('crm_link'))
                match_source = sd.get('match_source') or None
                if not match_source and pc is not None:
                    md = _as_dict(getattr(pc, 'match_details', None))
                    match_source = md.get('match_source')
                match_source = str(match_source or 'db').lower().strip()
                if match_source not in source_counts:
                    match_source = 'db'
                match_sources = _as_list(sd.get('match_sources'), [match_source])
                if not match_sources:
                    match_sources = [match_source]
                # Jede Quelle einmal zählen (db+es → beide Dropdowns)
                for s in match_sources:
                    s = str(s or '').lower().strip()
                    if s in source_counts:
                        source_counts[s] += 1
                    elif match_source == s:
                        source_counts['db'] += 1
                crm_link_status = sd.get('crm_link_status') or 'known'
                try:
                    strength = round(float(sd.get('strength') or 0), 3)
                except (TypeError, ValueError):
                    strength = 0.0
                try:
                    coverage = round(float(sd.get('coverage') or 0), 3)
                except (TypeError, ValueError):
                    coverage = 0.0
                data.append({
                    'id':             str(r.id),
                    'match_result_id': str(r.id),
                    'project_consultant_id': str(pc.id) if pc else None,
                    'pc_status':      pc.status if pc else None,
                    'consultant_id':  getattr(c, 'aid', '') or '',
                    'name':           getattr(c, 'full_name', None) or (
                        f"{getattr(c, 'first_name', '')} {getattr(c, 'last_name', '')}".strip()
                    ) or getattr(c, 'aid', '') or '—',
                    'email':          email or (crm.get('email') or ''),
                    'phone':          crm.get('phone') or '',
                    'location':       getattr(c, 'location', None) or '',
                    'availability':   getattr(c, 'availability', None) or '',
                    'overall_score':  round(float(r.overall_score or 0), 3),
                    'skill_score':    round(float(r.skill_score or 0), 3),
                    'industry_score': round(float(r.industry_score or 0), 3),
                    'rank':           r.rank,
                    'strength':       strength,
                    'coverage':       coverage,
                    'matched_skills': r.matched_skills or [],
                    'missing_skills': r.missing_skills or [],
                    'match_reason':   r.match_reason or '',
                    'match_source':   match_source,
                    'match_sources':  match_sources,
                    'crm_link_status': crm_link_status,
                    'profile_refresh_suggested': bool(sd.get('profile_refresh_suggested')),
                    'above_threshold': float(r.overall_score or 0) >= threshold,
                    'cv_editor_url':  f'/cv-extractor/editor/{getattr(c, "aid", "")}/',
                })
            except Exception as row_exc:
                logger.warning('api_shortlist row skip %s: %s', getattr(r, 'id', '?'), row_exc)
                continue

        # Backoffice-Liste (Gulp/FLM ohne Kontakt / unbekannt)
        backoffice = []
        ext_stats = {}
        er = p.extracted_requirements if isinstance(p.extracted_requirements, dict) else {}
        if isinstance(er, dict):
            raw_bo = er.get('_matching_backoffice') or []
            # Nur JSON-sichere Dicts
            if isinstance(raw_bo, list):
                for b in raw_bo:
                    if isinstance(b, dict):
                        backoffice.append(b)
            ext_stats = er.get('_matching_external_stats') or {}
            if not isinstance(ext_stats, dict):
                ext_stats = {}

        try:
            shortlist_limit = _matching_shortlist_limit()
        except Exception:
            shortlist_limit = 20

        return Response({
            'success':   True,
            'threshold': threshold,
            'results':   data,
            'count':     len(data),
            'above_threshold': sum(1 for d in data if d['above_threshold']),
            'source_counts': source_counts,
            'backoffice': backoffice,
            'backoffice_count': len(backoffice),
            'external_stats': ext_stats,
            'project_status': getattr(p, 'status', '') or '',
            'shortlist_limit': shortlist_limit,
            # UI braucht Skills am Projekt — sonst Warnung „Keine Skills“ immer falsch
            'project_id':       str(p.id),
            'project_number':   p.project_number or '',
            'project_title':    p.title or '',
            'title':            p.title or '',
            'required_skills':  p.required_skills or [],
            'skills':           skill_names,
            'extracted_technologies': list(getattr(p, 'extracted_technologies', None) or []),
            'has_skills':       bool(skill_names),
        })
    except Exception as e:
        logger.exception(f"api_shortlist: {e}")
        return Response({'success': False, 'error': str(e)}, status=500)


# ============================================================
# API: PROJECT CONSULTANT STATUS
# ============================================================

@extend_schema(summary="Match-Status aktualisieren")
@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_match_status(request, match_id):
    try:
        pc   = get_object_or_404(ProjectConsultant, id=match_id)
        data = request.data
        new_status = data.get('status')
        note       = data.get('note', '')

        if not new_status:
            return Response({'error': 'status fehlt'}, status=400)

        pc.set_status(new_status, note=note, user=request.user.username)

        # Zusätzliche Felder
        if new_status == 'interested':
            pc.consultant_response_at   = timezone.now()
            pc.consultant_response_note = note
        elif new_status in ('not_interested', 'unavailable'):
            pc.rejection_reason = data.get('reason', '')
            pc.rejected_at      = timezone.now()
            pc.rejected_by      = 'consultant'
            if new_status == 'unavailable':
                pc.unavailable_at   = timezone.now()
                pc.unavailable_note = note
        elif new_status == 'client_interested':
            pc.client_response_at   = timezone.now()
            pc.client_response_note = note
        elif new_status == 'client_not_interested':
            pc.rejection_reason = data.get('reason', '')
            pc.rejected_at      = timezone.now()
            pc.rejected_by      = 'client'
        elif new_status == 'accepted':
            pc.accepted_at = timezone.now()
        elif new_status == 'placed':
            pc.placed_at = timezone.now()
        pc.save()

        return Response({
            'success':        True,
            'status':         pc.status,
            'status_history': pc.status_history,
        })
    except Exception as e:
        logger.exception(f"api_match_status: {e}")
        return Response({'success': False, 'error': str(e)}, status=500)


@extend_schema(summary="Match-Details abrufen")
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_match_detail(request, match_id):
    try:
        pc = get_object_or_404(
            ProjectConsultant.objects.select_related('project', 'consultant_cv'),
            id=match_id
        )
        c = pc.consultant_cv
        return Response({
            'success': True,
            'match': {
                'id':            str(pc.id),
                'project':       {'id': str(pc.project.id), 'number': pc.project.project_number, 'title': pc.project.title},
                'consultant':    {'aid': c.aid, 'name': c.full_name, 'email': c.email, 'location': c.location},
                'match_score':   pc.match_score,
                'match_reason':  pc.match_reason,
                'status':        pc.status,
                'status_history':pc.status_history,
                'contacted_at':  pc.contacted_at.isoformat() if pc.contacted_at else None,
                'needs_followup':pc.needs_followup,
                'days_since_contacted': pc.days_since_contacted,
                'emails':        list(pc.emails.values('email_type', 'subject', 'sent_at', 'status')),
            }
        })
    except Exception as e:
        logger.exception(f"api_match_detail: {e}")
        return Response({'success': False, 'error': str(e)}, status=500)


# ============================================================
# API: PROJEKTABSCHLUSS
# ============================================================

@extend_schema(summary="Projekt abschließen")
@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_project_close(request, project_id):
    try:
        p    = get_object_or_404(ProjectRequest, id=project_id)
        data = request.data
        outcome = data.get('outcome')  # 'placed' | 'not_placed'

        if outcome == 'placed':
            from cv_extractor.models import Consultant as CVConsultant
            consultant_aid = data.get('consultant_aid')
            consultant     = get_object_or_404(CVConsultant, aid=consultant_aid)
            p.status            = 'placed'
            p.placed_consultant = consultant
            p.placed_at         = timezone.now()
            p.placed_rate       = data.get('placed_rate')
            p.placed_start      = data.get('placed_start') or None
            p.placed_end        = data.get('placed_end') or None
            p.placed_notes      = data.get('placed_notes', '')
            p.close_reason      = 'placed'
            p.closed_at         = timezone.now()
            p.save()

            # Anderen Beratern Absage schicken
            rejected_count = ProjectConsultant.objects.filter(
                project=p
            ).exclude(consultant_cv=consultant).exclude(
                status__in=['rejected', 'not_interested', 'unavailable']
            ).count()

            logger.info(f"Projekt {p.project_number} abgeschlossen — Vermittelt: {consultant.full_name}, {rejected_count} Absagen ausstehend")

        else:
            p.status       = 'not_placed'
            p.close_reason = data.get('close_reason', 'other')
            p.close_note   = data.get('close_note', '')
            p.closed_at    = timezone.now()
            p.save()

        return Response({'success': True, 'status': p.status, 'project_number': p.project_number})
    except Exception as e:
        logger.exception(f"api_project_close: {e}")
        return Response({'success': False, 'error': str(e)}, status=500)


@extend_schema(summary="Projekt archivieren")
@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_project_archive(request, project_id):
    try:
        p            = get_object_or_404(ProjectRequest, id=project_id)
        p.is_archived = True
        p.save(update_fields=['is_archived'])
        logger.info(f"Projekt archiviert: {p.project_number}")
        return Response({'success': True})
    except Exception as e:
        logger.exception(f"api_project_archive: {e}")
        return Response({'success': False, 'error': str(e)}, status=500)


# ============================================================
# API: CLICK-TO-CALL
# ============================================================

@extend_schema(summary="Click-to-Call")
@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_call(request, match_id):
    try:
        pc   = get_object_or_404(ProjectConsultant, id=match_id)
        data = request.data
        to   = data.get('phone', '')

        if not to:
            return Response({'error': 'Keine Telefonnummer'}, status=400)

        from .services.phone_service import PhoneService
        result = PhoneService().call(to=to)

        # Als SuiteCRM call loggen
        logger.info(f"Click-to-Call: {pc.consultant_cv.full_name} — {to}")

        return Response({'success': result.get('success', False), 'to': to})
    except Exception as e:
        logger.exception(f"api_call: {e}")
        return Response({'success': False, 'error': str(e)}, status=500)


# ============================================================
# API: CRM SYNC
# ============================================================

@extend_schema(summary="CRM Sync für Projekt")
@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_crm_sync(request, project_id):
    try:
        p = get_object_or_404(ProjectRequest, id=project_id)
        from .services.crm_sync_service import CRMSyncService
        result = CRMSyncService().sync_project(p)
        return Response({'success': True, 'result': result})
    except Exception as e:
        logger.exception(f"api_crm_sync: {e}")
        return Response({'success': False, 'error': str(e)}, status=500)


@extend_schema(summary="SuiteCRM Kontakte suchen")
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_crm_contacts(request):
    """Suche in SuiteCRM contacts für Ansprechpartner-Auswahl"""
    try:
        search = request.GET.get('q', '')
        if len(search) < 2:
            return Response({'success': True, 'results': []})

        from apps.crm_bridge.connectors.suitecrm_db import SuiteCRMDBConnector
        db = SuiteCRMDBConnector()
        rows = db.execute_query("""
            SELECT c.id, c.first_name, c.last_name, c.title, c.phone_work, c.phone_mobile,
                   a.name as account_name,
                   ea.email_address
            FROM contacts c
            LEFT JOIN accounts_contacts ac ON ac.contact_id = c.id AND ac.deleted = 0
            LEFT JOIN accounts a ON a.id = ac.account_id AND a.deleted = 0
            LEFT JOIN email_addr_bean_rel eabr ON eabr.bean_id = c.id
                AND eabr.bean_module = 'Contacts' AND eabr.deleted = 0 AND eabr.primary_address = 1
            LEFT JOIN email_addresses ea ON ea.id = eabr.email_address_id AND ea.deleted = 0
            WHERE c.deleted = 0
              AND (c.first_name LIKE %s OR c.last_name LIKE %s OR a.name LIKE %s)
            ORDER BY c.last_name, c.first_name
            LIMIT 20
        """, (f'%{search}%', f'%{search}%', f'%{search}%'))

        results = []
        for r in rows:
            results.append({
                'id':           r['id'],
                'first_name':   r['first_name'] or '',
                'last_name':    r['last_name'] or '',
                'full_name':    f"{r['first_name'] or ''} {r['last_name'] or ''}".strip(),
                'title':        r['title'] or '',
                'phone':        r['phone_work'] or r['phone_mobile'] or '',
                'email':        r['email_address'] or '',
                'account_name': r['account_name'] or '',
            })
        return Response({'success': True, 'results': results})
    except Exception as e:
        logger.exception(f"api_crm_contacts: {e}")
        return Response({'success': False, 'error': str(e)}, status=500)


@extend_schema(summary="SuiteCRM Accounts suchen")
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_crm_accounts(request):
    """Suche in SuiteCRM accounts für Kunden-Auswahl"""
    try:
        search = request.GET.get('q', '')
        if len(search) < 2:
            return Response({'success': True, 'results': []})

        from apps.crm_bridge.connectors.suitecrm_db import SuiteCRMDBConnector
        db = SuiteCRMDBConnector()
        rows = db.execute_query("""
            SELECT id, name, phone_office, billing_address_city, industry, account_type
            FROM accounts
            WHERE deleted = 0 AND name LIKE %s
            ORDER BY name
            LIMIT 20
        """, (f'%{search}%',))

        results = [{'id': r['id'], 'name': r['name'], 'phone': r['phone_office'] or '',
                    'city': r['billing_address_city'] or '', 'industry': r['industry'] or ''
                   } for r in rows]
        return Response({'success': True, 'results': results})
    except Exception as e:
        logger.exception(f"api_crm_accounts: {e}")
        return Response({'success': False, 'error': str(e)}, status=500)


# ============================================================
# API: REPORTING
# ============================================================

@extend_schema(summary="Reporting-Daten")
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_reporting(request):
    try:
        from django.db.models import Count, Avg, F
        from django.db.models.functions import TruncMonth

        # Vermittlungsquote
        total_closed = ProjectRequest.objects.filter(
            status__in=['placed', 'not_placed']
        ).count()
        total_placed = ProjectRequest.objects.filter(status='placed').count()
        placement_rate = round(total_placed / max(total_closed, 1) * 100, 1)

        # Absagegründe
        close_reasons = list(
            ProjectRequest.objects.exclude(close_reason='')
            .values('close_reason')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        # Top-Berater (am häufigsten vorgestellt)
        top_consultants = list(
            ProjectConsultant.objects.values(
                'consultant_cv__first_name', 'consultant_cv__last_name', 'consultant_cv__aid'
            ).annotate(count=Count('id'))
            .order_by('-count')[:10]
        )

        # Anfragen pro Monat
        monthly = list(
            ProjectRequest.objects.annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('month')
        )

        return Response({
            'success':         True,
            'placement_rate':  placement_rate,
            'total_placed':    total_placed,
            'total_closed':    total_closed,
            'close_reasons':   close_reasons,
            'top_consultants': top_consultants,
            'monthly':         [{'month': m['month'].strftime('%Y-%m'), 'count': m['count']} for m in monthly],
        })
    except Exception as e:
        logger.exception(f"api_reporting: {e}")
        return Response({'success': False, 'error': str(e)}, status=500)


# ============================================================
# API: SETTINGS
# ============================================================

@extend_schema(summary="Matching-Settings lesen")
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_settings_get(request):
    try:
        cfg = _load_matching_settings()
        return Response({'success': True, 'settings': cfg})
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)


@extend_schema(summary="Matching-Settings speichern")
@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_settings_save(request):
    try:
        import json
        from pathlib import Path
        p   = Path(__file__).resolve().parent.parent.parent / 'settings.json'
        cfg = json.loads(p.read_text(encoding='utf-8'))
        cfg['matching'] = request.data
        p.write_text(json.dumps(cfg, indent=4, ensure_ascii=False), encoding='utf-8')
        logger.info("Matching-Settings gespeichert")
        return Response({'success': True})
    except Exception as e:
        logger.exception(f"api_settings_save: {e}")
        return Response({'success': False, 'error': str(e)}, status=500)


# ============================================================
# API: KANBAN
# ============================================================

@extend_schema(summary="Kanban Board für ein Projekt")
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_kanban(request, project_id):
    try:
        p   = get_object_or_404(ProjectRequest, id=project_id)
        cfg = _load_matching_settings()
        columns_cfg = cfg.get('kanban_columns', [])

        status_to_col = {}
        for col in columns_cfg:
            for status in col.get('statuses', []):
                status_to_col[status] = col['id']

        pcs = ProjectConsultant.objects.filter(
            project=p
        ).select_related('consultant_cv').order_by('-match_score')

        columns = {col['id']: [] for col in columns_cfg}

        for pc in pcs:
            col_id = status_to_col.get(pc.status, 'shortlist')
            c = pc.consultant_cv
            columns[col_id].append({
                'id':             str(pc.id),
                'consultant_aid': c.aid,
                'name':           c.full_name,
                'location':       c.location or '',
                'match_score':    round(pc.match_score, 2),
                'status':         pc.status,
                'contacted_at':   pc.contacted_at.isoformat() if pc.contacted_at else None,
                'days_since':     pc.days_since_contacted,
                'needs_followup': pc.needs_followup,
                'match_reason':   pc.match_reason or '',
            })

        result = []
        for col in columns_cfg:
            result.append({
                'id':         col['id'],
                'label':      col['label'],
                'color':      col['color'],
                'text_color': col['text_color'],
                'cards':      columns.get(col['id'], []),
                'count':      len(columns.get(col['id'], [])),
            })

        return Response({
            'success':        True,
            'project_number': p.project_number,
            'project_title':  p.title,
            'columns':        result,
            'total':          pcs.count(),
        })
    except Exception as e:
        logger.exception(f"api_kanban: {e}")
        return Response({'success': False, 'error': str(e)}, status=500)


@extend_schema(summary="Kanban Karte verschieben")
@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_kanban_move(request, match_id):
    try:
        pc         = get_object_or_404(ProjectConsultant, id=match_id)
        data       = request.data
        new_status = data.get('status')
        note       = data.get('note', '')

        if not new_status:
            return Response({'error': 'status fehlt'}, status=400)

        col_to_status = {
            'shortlist':  'identified',
            'contacted':  'contacted',
            'interested': 'interested',
            'client':     'client_interested',
            'interview':  'interview_scheduled',
            'placed':     'accepted',
            'rejected':   'rejected',
        }

        if new_status in col_to_status:
            new_status = col_to_status[new_status]

        pc.set_status(new_status, note=note, user=request.user.username)

        return Response({'success': True, 'status': pc.status, 'match_id': str(pc.id)})
    except Exception as e:
        logger.exception(f"api_kanban_move: {e}")
        return Response({'success': False, 'error': str(e)}, status=500)


# ============================================================
# API: PROJEKTABSCHLUSS
# ============================================================

@extend_schema(summary="Projektabschluss Daten")
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_abschluss(request, project_id):
    try:
        p   = get_object_or_404(ProjectRequest, id=project_id)
        pcs = ProjectConsultant.objects.filter(
            project=p
        ).select_related('consultant_cv')

        placed = []
        for pc in pcs.filter(status='placed'):
            placed.append({
                'id':                str(pc.id),
                'name':              pc.consultant_cv.full_name,
                'aid':               pc.consultant_cv.aid,
                'match_score':       round(pc.match_score, 2),
                'placed_at':         pc.placed_at.strftime('%Y-%m-%d') if pc.placed_at else None,
                'agreed_rate':       float(pc.agreed_rate) if pc.agreed_rate else None,
                'agreed_start_date': pc.agreed_start_date.strftime('%Y-%m-%d') if pc.agreed_start_date else None,
                'agreed_duration':   pc.agreed_duration,
                'placement_notes':             pc.offer_text or '',
                'client_contract_received':     pc.client_contract_received,
                'client_contract_received_at':  pc.client_contract_received_at.strftime('%Y-%m-%d') if pc.client_contract_received_at else '',
                'client_contract_channel':      pc.client_contract_channel or '',
                'client_contract_note':         pc.client_contract_note or '',
                'client_contract_sender':       pc.client_contract_sender or '',
            })

        return Response({
            'success': True,
            'project': {
                'id':             str(p.id),
                'project_number': p.project_number,
                'title':          p.title,
                'open_positions': p.open_positions,
                'status':         p.status,
            },
            'placed':            placed,
            'total_consultants': pcs.count(),
        })
    except Exception as e:
        logger.exception(f"api_abschluss: {e}")
        return Response({'success': False, 'error': str(e)}, status=500)


# ============================================================
# API: PROJEKTABSCHLUSS
# ============================================================

@extend_schema(summary="Projektabschluss Daten")
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_abschluss(request, project_id):
    try:
        p   = get_object_or_404(ProjectRequest, id=project_id)
        pcs = ProjectConsultant.objects.filter(
            project=p
        ).select_related('consultant_cv')

        placed = []
        for pc in pcs.filter(status='placed'):
            placed.append({
                'id':                str(pc.id),
                'name':              pc.consultant_cv.full_name,
                'aid':               pc.consultant_cv.aid,
                'match_score':       round(pc.match_score, 2),
                'placed_at':         pc.placed_at.strftime('%Y-%m-%d') if pc.placed_at else None,
                'agreed_rate':       float(pc.agreed_rate) if pc.agreed_rate else None,
                'agreed_start_date': pc.agreed_start_date.strftime('%Y-%m-%d') if pc.agreed_start_date else None,
                'agreed_duration':   pc.agreed_duration,
                'placement_notes':             pc.offer_text or '',
                'client_contract_received':     pc.client_contract_received,
                'client_contract_received_at':  pc.client_contract_received_at.strftime('%Y-%m-%d') if pc.client_contract_received_at else '',
                'client_contract_channel':      pc.client_contract_channel or '',
                'client_contract_note':         pc.client_contract_note or '',
                'client_contract_sender':       pc.client_contract_sender or '',
            })

        return Response({
            'success': True,
            'project': {
                'id':             str(p.id),
                'project_number': p.project_number,
                'title':          p.title,
                'open_positions': p.open_positions,
                'status':         p.status,
            },
            'placed':            placed,
            'total_consultants': pcs.count(),
        })
    except Exception as e:
        logger.exception(f"api_abschluss: {e}")
        return Response({'success': False, 'error': str(e)}, status=500)


@extend_schema(summary="Vermittlungsdetails speichern")
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_placement_details(request, match_id):
    try:
        pc   = get_object_or_404(ProjectConsultant, id=match_id)
        data = request.data

        if data.get('agreed_rate') is not None:
            pc.agreed_rate = data['agreed_rate']
        if data.get('agreed_start_date'):
            pc.agreed_start_date = data['agreed_start_date']
        if data.get('agreed_duration') is not None:
            pc.agreed_duration = data['agreed_duration']
        if data.get('placed_at'):
            pc.placed_at = data['placed_at']
        if 'placement_notes' in data:
            pc.offer_text = data['placement_notes']
        # Vertragseingang
        if 'client_contract_received' in data:
            pc.client_contract_received = bool(data['client_contract_received'])
        if data.get('client_contract_received_at'):
            from django.utils.dateparse import parse_datetime, parse_date
            pc.client_contract_received_at = parse_datetime(data['client_contract_received_at']) or parse_date(data['client_contract_received_at'])
        if 'client_contract_channel' in data:
            pc.client_contract_channel = data['client_contract_channel']
        if 'client_contract_note' in data:
            pc.client_contract_note = data['client_contract_note']
        if 'client_contract_sender' in data:
            pc.client_contract_sender = data['client_contract_sender']

        pc.save(update_fields=[
            'agreed_rate','agreed_start_date','agreed_duration',
            'placed_at','offer_text',
            'client_contract_received','client_contract_received_at',
            'client_contract_channel','client_contract_note','client_contract_sender',
        ])
        return Response({'success': True})
    except Exception as e:
        logger.exception(f"api_placement_details: {e}")
        return Response({'success': False, 'error': str(e)}, status=500)

# ============================================================
# API — ANFRAGEN PRO FIRMA (Softphone, Token-faehig, read-only)
# ============================================================
from apps.abpe_crm.views import login_or_token_required as _crm_login_or_token

@_crm_login_or_token
@require_http_methods(['GET'])
def api_account_requests(request, account_crm_id):
    """Projektanfragen einer Firma (crm_account_id) — read-only fuer Softphone Firma-Reiter."""
    include_archived = request.GET.get('archived', '0') == '1'
    account_name = (request.GET.get('name', '') or '').strip()

    # ID-Verknuepfung hat Vorrang; Name-Fallback nur fuer noch-unverknuepfte Anfragen.
    # Name-Match ist tolerant: Rechtsformen/Gross-Klein/Leerzeichen werden normalisiert.
    cond = Q(crm_account_id=account_crm_id)
    if account_name:
        import re as _re
        def _norm(x):
            x = (x or '').lower()
            x = _re.sub(r'\b(gmbh|ag|kg|ohg|se|mbh|co|kgaa|ug|e\.k\.|ek|inc|ltd|llc|group|gruppe)\b', '', x)
            x = _re.sub(r'[^a-z0-9]', '', x)
            return x
        norm_target = _norm(account_name)
        if norm_target:
            # Kandidaten: unverknuepfte Anfragen, deren Name den Ziel-Namen enthaelt (oder umgekehrt)
            name_ids = []
            for pr in ProjectRequest.objects.filter(crm_account_id='').only('id', 'customer_name'):
                n = _norm(pr.customer_name)
                if n and (n == norm_target or n in norm_target or norm_target in n):
                    name_ids.append(pr.id)
            if name_ids:
                cond = cond | Q(id__in=name_ids)

    qs = ProjectRequest.objects.filter(cond)
    if not include_archived:
        qs = qs.filter(is_archived=False)
    qs = qs.order_by('-created_at')
    rows = []
    for p in qs:
        rows.append({
            'id':             str(p.id),
            'project_number': p.project_number or '',
            'title':          p.title or '',
            'customer_name':  p.customer_name or '',
            'status':         p.status or '',
            'priority':       p.priority,
            'match_count':    p.consultants.count(),
            'created_at':     p.created_at.isoformat() if p.created_at else '',
        })
    return JsonResponse({'requests': rows, 'account_crm_id': account_crm_id, 'total': len(rows)})


# ============================================================
# API: OUTREACH WIZARD (Alle anschreiben)
# ============================================================

def _ui_status_to_db(status: str) -> str:
    """UI/STAGE_MAIL → ProjectConsultant.STATUS_CHOICES."""
    mapping = {
        'angeschrieben': 'contacted',
        'contacted': 'contacted',
        'interesse': 'interested',
        'interested': 'interested',
        'beim_kunden': 'client_interested',
        'interview': 'interview_scheduled',
        'vermittelt': 'accepted',
        'absage': 'rejected',
        'shortlist': 'identified',
        'identified': 'identified',
    }
    return mapping.get((status or '').strip(), status or 'contacted')


@extend_schema(summary="Outreach: DeepSeek-Begründung zu MatchResult")
@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_outreach_deep_reason(request, match_result_id):
    try:
        from .services.outreach_wizard import resolve_match_result, build_deep_reason, ensure_project_consultant
        mr = resolve_match_result(match_result_id)
        pc = ensure_project_consultant(mr)
        data = build_deep_reason(mr)
        data['project_consultant_id'] = str(pc.id)
        data['project_id'] = str(mr.project_request_id)
        # Persist reason on PC if empty / refresh
        if data.get('why') and (not pc.match_reason or request.data.get('persist', True)):
            pc.match_reason = data['why']
            pc.save(update_fields=['match_reason'])
        return Response(data)
    except Exception as e:
        logger.exception('api_outreach_deep_reason: %s', e)
        return Response({'ok': False, 'error': str(e)}, status=500)


@extend_schema(summary="Outreach: Anschreiben-Draft")
@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_outreach_letter_draft(request, match_result_id):
    try:
        from .services.outreach_wizard import (
            resolve_match_result, build_letter_draft, build_deep_reason, ensure_project_consultant,
        )
        mr = resolve_match_result(match_result_id)
        pc = ensure_project_consultant(mr)
        body = request.data or {}
        deep = body.get('deep_reason') if isinstance(body.get('deep_reason'), dict) else None
        if body.get('refresh_reason') or not deep:
            deep = build_deep_reason(mr)
        data = build_letter_draft(mr, deep=deep, extra_notes=body.get('extra_notes') or '')
        data['project_consultant_id'] = str(pc.id)
        data['deep_reason'] = deep
        return Response(data)
    except Exception as e:
        logger.exception('api_outreach_letter_draft: %s', e)
        return Response({'ok': False, 'error': str(e)}, status=500)


@extend_schema(summary="Outreach: Anschreiben polieren")
@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_outreach_letter_polish(request):
    try:
        from .services.outreach_wizard import polish_letter
        body = request.data or {}
        text = body.get('draft_text') or body.get('body') or body.get('draft_html') or ''
        if not str(text).strip():
            return Response({'ok': False, 'error': 'draft_text fehlt'}, status=400)
        data = polish_letter(str(text), keep_style=bool(body.get('keep_style', True)))
        return Response(data)
    except Exception as e:
        logger.exception('api_outreach_letter_polish: %s', e)
        return Response({'ok': False, 'error': str(e)}, status=500)


@extend_schema(summary="Outreach: nach Send Status + optional Wiedervorlage-Meta")
@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_outreach_complete(request, match_result_id):
    """
    Nach erfolgreichem CRM-Send: ProjectConsultant sicherstellen, Status contacted,
    optional Task-Payload zurückgeben (Frontend ruft Shaduler auf).
    """
    try:
        from .services.outreach_wizard import resolve_match_result, ensure_project_consultant
        mr = resolve_match_result(match_result_id)
        pc = ensure_project_consultant(mr)
        body = request.data or {}
        new_status = _ui_status_to_db(body.get('status') or 'contacted')
        note = body.get('note') or 'Outreach-Wizard Anschreiben'
        pc.set_status(new_status, note=note, user=getattr(request.user, 'username', 'system') or 'system')

        c = mr.consultant_cv
        project = mr.project_request
        task = None
        if body.get('create_task', True):
            # Default +1 Tag (wie Shaduler Art-Default WV) — Frontend sendet faellig_am aus Regeln-Tab
            due = (timezone.now() + timedelta(days=int(body.get('task_days') or 1))).date().isoformat()
            task = {
                'art': 'wiedervorlage',
                'titel': f'WV Anschreiben — {c.full_name} — {project.project_number or project.title}',
                'beschreibung': (
                    f'Follow-up nach Outreach zu „{project.title}“.\n'
                    f'Berater: {c.full_name} ({c.aid})\n'
                    f'Match-Score: {mr.overall_score}'
                ),
                'ref_type': 'berater',
                'ref_id': c.aid,
                'prioritaet': int(body.get('task_priority') or 3),
                'faellig_am': body.get('faellig_am') or due,
            }
            if body.get('faellig_zeit'):
                task['faellig_zeit'] = body.get('faellig_zeit')

        return Response({
            'ok': True,
            'success': True,
            'match_result_id': str(mr.id),
            'project_consultant_id': str(pc.id),
            'status': pc.status,
            'task': task,
        })
    except Exception as e:
        logger.exception('api_outreach_complete: %s', e)
        return Response({'ok': False, 'error': str(e)}, status=500)

