"""
ABpE KI Wizard — REST API
"""
from __future__ import annotations

import json
import logging
import uuid

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .models import WizardPrompt, WizardSession
from .registry import WizardNotRegisteredError, get_provider, provider_info
from .services.orchestrator import (
    analyze_session,
    apply_session,
    clarify_session,
    generate_session,
    suggest_meta_session,
)
from .services.session_store import create_session, get_session_for_user, session_to_dict

log = logging.getLogger('abpe_ki_wiz.api')


def _json_body(request) -> dict:
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


class KiWizardHealthAPI(View):
    """GET /ki-wizard/api/health/ — ohne Login (Monitoring)."""

    def get(self, request):
        prompt_count = WizardPrompt.objects.filter(aktiv=True).count()
        wizards = [
            w for w in provider_info()
            if not w.get('wizard_id', '').startswith('_')
        ]
        return JsonResponse({
            'status': 'ok',
            'service': 'abpe_ki_wiz',
            'phase': 1,
            'active_prompts': prompt_count,
            'registered_wizards': len(provider_info()),
            'public_wizards': len(wizards),
        })


@method_decorator(csrf_exempt, name='dispatch')
class KiWizardListAPI(LoginRequiredMixin, View):
    """GET /ki-wizard/api/wizards/ — registrierte Wizard-Provider."""

    def get(self, request):
        wizards = [
            w for w in provider_info()
            if not w.get('wizard_id', '').startswith('_')
        ]
        return JsonResponse({'wizards': wizards})


@method_decorator(csrf_exempt, name='dispatch')
class KiWizardCatalogAPI(LoginRequiredMixin, View):
    """GET /ki-wizard/api/wizards/<wizard_id>/catalog/"""

    def get(self, request, wizard_id):
        try:
            provider = get_provider(wizard_id)
        except WizardNotRegisteredError as exc:
            return JsonResponse({'error': str(exc)}, status=404)

        try:
            catalog = provider.get_catalog()
            questions = provider.get_question_catalog()
        except Exception as exc:
            log.exception('Katalog laden fehlgeschlagen: %s', wizard_id)
            return JsonResponse({'error': str(exc)}, status=500)

        return JsonResponse({
            'wizard_id': wizard_id,
            'title': provider.title,
            'description': provider.description,
            'catalog': catalog,
            'questions': questions,
        })


@method_decorator(csrf_exempt, name='dispatch')
class KiWizardPromptListAPI(LoginRequiredMixin, View):
    """GET /ki-wizard/api/prompts/ — aktive Prompts aus DB."""

    def get(self, request):
        wizard_id = request.GET.get('wizard_id', '').strip()
        qs = WizardPrompt.objects.filter(aktiv=True).order_by('wizard_id', 'phase', 'key')
        if wizard_id:
            qs = qs.filter(wizard_id=wizard_id)

        prompts = [{
            'key': p.key,
            'wizard_id': p.wizard_id,
            'phase': p.phase,
            'name': p.name,
            'app_scope': p.app_scope,
        } for p in qs]

        return JsonResponse({'prompts': prompts})


@method_decorator(csrf_exempt, name='dispatch')
class KiWizardSessionCreateAPI(LoginRequiredMixin, View):
    """POST /ki-wizard/api/wizards/<wizard_id>/session/ — Session starten."""

    def post(self, request, wizard_id):
        data = _json_body(request)
        briefing = (data.get('briefing') or '').strip()
        if len(briefing) < 10:
            return JsonResponse(
                {'error': 'briefing zu kurz (min. 10 Zeichen)'},
                status=400,
            )
        try:
            session = create_session(wizard_id, request.user, briefing)
        except WizardNotRegisteredError as exc:
            return JsonResponse({'error': str(exc)}, status=404)
        except Exception as exc:
            log.exception('Session create failed')
            return JsonResponse({'error': str(exc)}, status=500)

        return JsonResponse(session_to_dict(session), status=201)


@method_decorator(csrf_exempt, name='dispatch')
class KiWizardSessionDetailAPI(LoginRequiredMixin, View):
    """GET /ki-wizard/api/session/<uuid>/"""

    def get(self, request, session_id):
        try:
            sid = uuid.UUID(str(session_id))
            session = get_session_for_user(sid, request.user)
        except (ValueError, WizardSession.DoesNotExist):
            return JsonResponse({'error': 'Session nicht gefunden'}, status=404)
        return JsonResponse(session_to_dict(session))


@method_decorator(csrf_exempt, name='dispatch')
class KiWizardSessionAnalyzeAPI(LoginRequiredMixin, View):
    """POST /ki-wizard/api/session/<uuid>/analyze/"""

    def post(self, request, session_id):
        try:
            sid = uuid.UUID(str(session_id))
            session = get_session_for_user(sid, request.user)
            result = analyze_session(session)
            return JsonResponse(result)
        except (ValueError, WizardSession.DoesNotExist):
            return JsonResponse({'error': 'Session nicht gefunden'}, status=404)
        except Exception as exc:
            log.exception('analyze failed')
            return JsonResponse({'error': str(exc)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class KiWizardSessionClarifyAPI(LoginRequiredMixin, View):
    """POST /ki-wizard/api/session/<uuid>/clarify/ — body: { answers: { S1: ... } }"""

    def post(self, request, session_id):
        data = _json_body(request)
        answers = data.get('answers') or {}
        if not isinstance(answers, dict):
            return JsonResponse({'error': 'answers muss ein Objekt sein'}, status=400)
        try:
            sid = uuid.UUID(str(session_id))
            session = get_session_for_user(sid, request.user)
            result = clarify_session(session, answers)
            return JsonResponse(result)
        except (ValueError, WizardSession.DoesNotExist):
            return JsonResponse({'error': 'Session nicht gefunden'}, status=404)
        except Exception as exc:
            log.exception('clarify failed')
            return JsonResponse({'error': str(exc)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class KiWizardSessionSuggestMetaAPI(LoginRequiredMixin, View):
    """POST /ki-wizard/api/session/<uuid>/suggest-meta/"""

    def post(self, request, session_id):
        try:
            sid = uuid.UUID(str(session_id))
            session = get_session_for_user(sid, request.user)
            result = suggest_meta_session(session)
            return JsonResponse(result)
        except (ValueError, WizardSession.DoesNotExist):
            return JsonResponse({'error': 'Session nicht gefunden'}, status=404)
        except Exception as exc:
            log.exception('suggest_meta failed')
            return JsonResponse({'error': str(exc)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class KiWizardSessionGenerateAPI(LoginRequiredMixin, View):
    """POST /ki-wizard/api/session/<uuid>/generate/"""

    def post(self, request, session_id):
        try:
            sid = uuid.UUID(str(session_id))
            session = get_session_for_user(sid, request.user)
            data = _json_body(request)
            refinement = (data.get('refinement') or '').strip()
            result = generate_session(session, refinement=refinement)
            if result.get('error'):
                return JsonResponse(result, status=502)
            return JsonResponse(result)
        except (ValueError, WizardSession.DoesNotExist):
            return JsonResponse({'error': 'Session nicht gefunden'}, status=404)
        except Exception as exc:
            log.exception('generate failed')
            return JsonResponse({'error': str(exc)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class KiWizardSessionApplyAPI(LoginRequiredMixin, View):
    """POST /ki-wizard/api/session/<uuid>/apply/"""

    def post(self, request, session_id):
        try:
            sid = uuid.UUID(str(session_id))
            session = get_session_for_user(sid, request.user)
            result = apply_session(session)
            if result.get('error'):
                return JsonResponse(result, status=400)
            return JsonResponse(result)
        except (ValueError, WizardSession.DoesNotExist):
            return JsonResponse({'error': 'Session nicht gefunden'}, status=404)
        except Exception as exc:
            log.exception('apply failed')
            return JsonResponse({'error': str(exc)}, status=500)


from .services.prompt_loader import get_prompt_by_key