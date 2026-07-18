"""ABpE KI Wizard — URL Konfiguration"""
from django.urls import path

from . import api, views

app_name = 'ki_wizard'

urlpatterns = [
    path('', views.KiWizardIndexView.as_view(), name='index'),
    path('api/health/', api.KiWizardHealthAPI.as_view(), name='api-health'),
    path('api/wizards/', api.KiWizardListAPI.as_view(), name='api-wizard-list'),
    path(
        'api/wizards/<str:wizard_id>/catalog/',
        api.KiWizardCatalogAPI.as_view(),
        name='api-wizard-catalog',
    ),
    path('api/prompts/', api.KiWizardPromptListAPI.as_view(), name='api-prompt-list'),
    path(
        'api/wizards/<str:wizard_id>/session/',
        api.KiWizardSessionCreateAPI.as_view(),
        name='api-session-create',
    ),
    path(
        'api/session/<uuid:session_id>/',
        api.KiWizardSessionDetailAPI.as_view(),
        name='api-session-detail',
    ),
    path(
        'api/session/<uuid:session_id>/analyze/',
        api.KiWizardSessionAnalyzeAPI.as_view(),
        name='api-session-analyze',
    ),
    path(
        'api/session/<uuid:session_id>/clarify/',
        api.KiWizardSessionClarifyAPI.as_view(),
        name='api-session-clarify',
    ),
    path(
        'api/session/<uuid:session_id>/suggest-meta/',
        api.KiWizardSessionSuggestMetaAPI.as_view(),
        name='api-session-suggest-meta',
    ),
    path(
        'api/session/<uuid:session_id>/generate/',
        api.KiWizardSessionGenerateAPI.as_view(),
        name='api-session-generate',
    ),
    path(
        'api/session/<uuid:session_id>/apply/',
        api.KiWizardSessionApplyAPI.as_view(),
        name='api-session-apply',
    ),
]
