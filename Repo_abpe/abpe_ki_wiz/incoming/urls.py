"""ABpE KI Wizard — URL Konfiguration"""
from django.urls import path

from . import api
from . import views

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
]
