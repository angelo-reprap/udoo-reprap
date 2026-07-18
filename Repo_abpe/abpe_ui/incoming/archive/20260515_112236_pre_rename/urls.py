from django.urls import path
from . import views

app_name = 'abpe_ui'

urlpatterns = [
    # Hauptseite
    path('', views.dashboard, name='dashboard'),
    
    # API Endpunkte (für dynamische Daten)
    path('api/stats/', views.api_stats, name='api_stats'),
    path('api/system/', views.api_system_status, name='api_system'),
    path('api/recent/consultants/', views.api_recent_consultants, name='api_recent_consultants'),
    path('api/recent/emails/', views.api_recent_emails, name='api_recent_emails'),
    path('api/translations/<str:lang>/', views.api_translations, name='api_translations'),
    
    # Hilfeseiten
    path('help/', views.help_page, name='help'),
    path('help/<str:topic>/', views.help_detail, name='help_detail'),
]
