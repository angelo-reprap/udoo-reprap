"""
ABpE KI Wizard — REST API (Phase 0)
"""
import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .models import WizardPrompt
from .registry import WizardNotRegisteredError, get_provider, provider_info

log = logging.getLogger('abpe_ki_wiz.api')


class KiWizardHealthAPI(View):
    """GET /ki-wizard/api/health/ — ohne Login (Monitoring)."""

    def get(self, request):
        prompt_count = WizardPrompt.objects.filter(aktiv=True).count()
        return JsonResponse({
            'status': 'ok',
            'service': 'abpe_ki_wiz',
            'phase': 0,
            'active_prompts': prompt_count,
            'registered_wizards': len(provider_info()),
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
    """
    GET /ki-wizard/api/wizards/<wizard_id>/catalog/
    Phase 0: Provider-Katalog + Fragen (Stub oder Fach-Provider).
    """

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
    """GET /ki-wizard/api/prompts/ — aktive Prompts aus DB (Admin-Debug)."""

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


def get_prompt_by_key(key: str) -> WizardPrompt | None:
    """Hilfsfunktion für Phase 1 — lädt aktiven Prompt aus DB."""
    try:
        return WizardPrompt.objects.get(key=key, aktiv=True)
    except WizardPrompt.DoesNotExist:
        return None
