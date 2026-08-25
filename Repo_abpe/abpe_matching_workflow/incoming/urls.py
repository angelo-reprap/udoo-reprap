"""
ABpE Matching Workflow — URLs
Alle Routes: Portal-View + API + Spectacular
"""
from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from . import views

app_name = 'abpe_matching_workflow'

urlpatterns = [

    # ============================================================
    # PORTAL VIEW (Template)
    # ============================================================
    path('', views.index, name='index'),

    # ============================================================
    # API — STATS
    # ============================================================
    path('api/stats/',                          views.api_stats,              name='api_stats'),

    # ============================================================
    # API — PROJEKTANFRAGEN
    # ============================================================
    path('api/requests/',                       views.api_project_list,       name='api_project_list'),
    path('api/account/<str:account_crm_id>/requests/', views.api_account_requests, name='api_account_requests'),
    path('api/requests/create/',                views.api_project_create,     name='api_project_create'),
    path('api/requests/<uuid:project_id>/',     views.api_project_detail,     name='api_project_detail'),
    path('api/requests/<uuid:project_id>/update/', views.api_project_update,  name='api_project_update'),

    # ============================================================
    # API — MATCHING
    # ============================================================
    path('api/requests/<uuid:project_id>/match/',
         views.api_run_matching,     name='api_run_matching'),
    path('api/requests/<uuid:project_id>/shortlist/',
         views.api_shortlist,        name='api_shortlist'),

    # ============================================================
    # API — KANBAN
    # ============================================================
    path('api/requests/<uuid:project_id>/abschluss/',
         views.api_abschluss,         name='api_abschluss'),
    path('api/requests/<uuid:project_id>/kanban/',
         views.api_kanban,           name='api_kanban'),
    path('api/match/<uuid:match_id>/placement/',
         views.api_placement_details,  name='api_placement_details'),
    path('api/match/<uuid:match_id>/move/',
         views.api_kanban_move,      name='api_kanban_move'),

    # ============================================================
    # API — PROJEKTABSCHLUSS
    # ============================================================
    path('api/requests/<uuid:project_id>/close/',
         views.api_project_close,    name='api_project_close'),
    path('api/requests/<uuid:project_id>/archive/',
         views.api_project_archive,  name='api_project_archive'),

    # ============================================================
    # API — MATCH (ProjectConsultant)
    # ============================================================
    path('api/match/<uuid:match_id>/',
         views.api_match_detail,     name='api_match_detail'),
    path('api/match/<uuid:match_id>/status/',
         views.api_match_status,     name='api_match_status'),
    path('api/match/<uuid:match_id>/call/',
         views.api_call,             name='api_call'),

    # ============================================================
    # API — OUTREACH WIZARD (Shortlist MatchResult-IDs)
    # ============================================================
    path('api/outreach/email-templates/',
         views.api_outreach_email_templates, name='api_outreach_email_templates'),
    path('api/outreach/<uuid:match_result_id>/deep-reason/',
         views.api_outreach_deep_reason,   name='api_outreach_deep_reason'),
    path('api/outreach/<uuid:match_result_id>/letter/draft/',
         views.api_outreach_letter_draft,  name='api_outreach_letter_draft'),
    path('api/outreach/letter/polish/',
         views.api_outreach_letter_polish, name='api_outreach_letter_polish'),
    path('api/outreach/<uuid:match_result_id>/complete/',
         views.api_outreach_complete,      name='api_outreach_complete'),

    # ============================================================
    # API — CRM
    # ============================================================
    path('api/crm/sync/<uuid:project_id>/',
         views.api_crm_sync,         name='api_crm_sync'),
    path('api/crm/contacts/',
         views.api_crm_contacts,     name='api_crm_contacts'),
    path('api/crm/accounts/',
         views.api_crm_accounts,     name='api_crm_accounts'),

    # ============================================================
    # API — REPORTING
    # ============================================================
    path('api/reporting/',           views.api_reporting,          name='api_reporting'),

    # ============================================================
    # API — SETTINGS
    # ============================================================
    path('api/settings/',            views.api_settings_get,       name='api_settings_get'),
    path('api/settings/save/',       views.api_settings_save,      name='api_settings_save'),

    # ============================================================
    # OPENAPI / SWAGGER
    # ============================================================
    path('api/schema/',
         SpectacularAPIView.as_view(),
         name='schema'),
    path('api/docs/',
         SpectacularSwaggerView.as_view(url_name='abpe_matching_workflow:schema'),
         name='swagger-ui'),
    path('api/redoc/',
         SpectacularRedocView.as_view(url_name='abpe_matching_workflow:schema'),
         name='redoc'),
]
