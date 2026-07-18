"""ABpE KI Wizard — URL Konfiguration"""
from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from . import views
from .schema_settings import KI_WIZARD_SPECTACULAR_SETTINGS
from .urls_api import urlpatterns as api_urlpatterns

app_name = 'ki_wizard'

urlpatterns = [
    path('', views.KiWizardIndexView.as_view(), name='index'),
    path(
        'api/schema/',
        SpectacularAPIView.as_view(
            urlconf='apps.abpe_ki_wiz.urls_api',
            custom_settings=KI_WIZARD_SPECTACULAR_SETTINGS,
        ),
        name='api-schema',
    ),
    path(
        'api/docs/',
        SpectacularSwaggerView.as_view(url_name='ki_wizard:api-schema'),
        name='api-docs',
    ),
    path(
        'api/redoc/',
        SpectacularRedocView.as_view(url_name='ki_wizard:api-schema'),
        name='api-redoc',
    ),
] + api_urlpatterns
