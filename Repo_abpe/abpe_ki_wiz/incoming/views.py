"""Phase 0/1: JSON-Index."""
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
                'schema': '/ki-wizard/api/schema/',
                'docs': '/ki-wizard/api/docs/',
                'redoc': '/ki-wizard/api/redoc/',
                'wizards': '/ki-wizard/api/wizards/',
                'prompts': '/ki-wizard/api/prompts/',
                'session_create': '/ki-wizard/api/wizards/<wizard_id>/session/',
                'session': '/ki-wizard/api/session/<uuid>/',
                'session_analyze': '/ki-wizard/api/session/<uuid>/analyze/',
                'session_clarify': '/ki-wizard/api/session/<uuid>/clarify/',
                'session_suggest_meta': '/ki-wizard/api/session/<uuid>/suggest-meta/',
                'session_generate': '/ki-wizard/api/session/<uuid>/generate/',
                'session_apply': '/ki-wizard/api/session/<uuid>/apply/',
            },
            'openapi': '3.0.3',
            'swagger_ui': '/ki-wizard/api/docs/',
            'spectacular': True,
            'schema_source': 'drf-spectacular',
            'admin': '/admin/abpe_ki_wiz/',
        })
