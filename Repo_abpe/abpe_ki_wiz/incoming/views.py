"""Phase 0: keine HTML-Views — Portal nutzt abpe_ui + REST API."""
from django.http import JsonResponse
from django.views import View


class KiWizardIndexView(View):
    """GET /ki-wizard/ — Kurzinfo."""

    def get(self, request):
        return JsonResponse({
            'service': 'abpe_ki_wiz',
            'phase': 1,
            'api': {
                'health': '/ki-wizard/api/health/',
                'wizards': '/ki-wizard/api/wizards/',
                'prompts': '/ki-wizard/api/prompts/',
                'session_create': '/ki-wizard/api/wizards/<wizard_id>/session/',
                'session': '/ki-wizard/api/session/<uuid>/',
            },
            'admin': '/admin/abpe_ki_wiz/',
        })
