"""Phase 0/1: JSON-Index + drf-spectacular Schema."""
from django.http import JsonResponse
from django.views import View
from drf_spectacular.views import SpectacularAPIView
from rest_framework.permissions import AllowAny

from .schema_settings import KI_WIZARD_SPECTACULAR_SETTINGS


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


class KiWizardSpectacularAPIView(SpectacularAPIView):
    """OpenAPI Schema — auto-generiert aus DRF @extend_schema."""

    authentication_classes = []
    permission_classes = [AllowAny]
    urlconf = 'apps.abpe_ki_wiz.urls_api'
    custom_settings = KI_WIZARD_SPECTACULAR_SETTINGS
    serve_public = True
