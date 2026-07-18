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

    # API Berater — new + delete VOR <str:crm_id>/
    path('api/berater/new/',                    views.api_berater_new,    name='api_berater_new'),
    path('api/berater/',                        views.api_berater_list,   name='api_berater_list'),
    path('api/berater/<str:crm_id>/',           views.api_berater_detail, name='api_berater_detail'),
    path('api/berater/<str:crm_id>/delete/',    views.api_berater_delete, name='api_berater_delete'),

    # API Kunden — new + delete VOR <str:crm_id>/
    path('api/kunden/new/',                     views.api_kunden_new,     name='api_kunden_new'),
    path('api/kunden/',                         views.api_kunden_list,    name='api_kunden_list'),
    path('api/kunden/<str:crm_id>/',            views.api_kunden_detail,  name='api_kunden_detail'),
    path('api/kunden/<str:crm_id>/delete/',     views.api_kunden_delete,  name='api_kunden_delete'),

    # API Notizen
    path('api/note/save/',                      views.api_note_save,      name='api_note_save'),

    # API Dokumente
    path('api/dokumente/',                      views.api_dokumente_list, name='api_dokumente_list'),

    # API Emails
    path('api/emails/',                         views.api_emails_list,    name='api_emails_list'),

    # API Sprachen
    path('api/available-languages/',            views.api_available_languages, name='api_available_languages'),

    # API Contact Update
    path('api/contact/<str:crm_id>/update/',       views.api_contact_update,       name='api_contact_update'),
    path('api/contact/<str:crm_id>/photo/',         views.api_contact_photo,        name='api_contact_photo'),
    path('api/contact/<str:crm_id>/link-account/',  views.api_contact_link_account, name='api_contact_link_account'),
    path('api/account/<str:crm_id>/update/',        views.api_account_update,       name='api_account_update'),

    # API Reporting
    path('api/sync/status/',                    views.api_sync_status,    name='api_sync_status'),
]
