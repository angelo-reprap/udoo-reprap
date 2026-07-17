"""
abpe_crm/urls.py
"""
from django.urls import path
from . import views

app_name = 'abpe_crm'

urlpatterns = [
    # HTML Seiten
    path('',             views.index,      name='index'),
    path('berater/',     views.berater,    name='berater'),
    path('kunden/',      views.kunden,     name='kunden'),
    path('emails/',      views.emails,     name='emails'),
    path('dokumente/',   views.dokumente,  name='dokumente'),
    path('reporting/',   views.reporting,  name='reporting'),

    # API Berater
    path('api/berater/',                    views.api_berater_list,   name='api_berater_list'),
    path('api/berater/<str:crm_id>/',       views.api_berater_detail, name='api_berater_detail'),

    # API Kunden
    path('api/kunden/',                     views.api_kunden_list,    name='api_kunden_list'),
    path('api/kunden/<str:crm_id>/',        views.api_kunden_detail,  name='api_kunden_detail'),

    # API Notizen
    path('api/note/save/',                  views.api_note_save,      name='api_note_save'),

    # API Dokumente
    path('api/dokumente/',                  views.api_dokumente_list, name='api_dokumente_list'),

    # API Sprachen
    path('api/available-languages/', views.api_available_languages, name='api_available_languages'),

    # API Reporting
    path('api/sync/status/',                views.api_sync_status,    name='api_sync_status'),
]
