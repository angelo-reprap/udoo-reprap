"""
cv_extractor/urls.py - URL-Konfiguration für CV-Extraktor
"""
from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from . import views

app_name = 'cv_extractor'

urlpatterns = [
    # ===== HAUPTSEITEN =====
    path('upload/', views.upload_page, name='upload_page'),
    path('', views.index, name='index'),
    path('editor/<str:aid>/', views.editor_view, name='editor'),

    # ===== API ENDPOINTS =====
    path('api/extract/text/', views.extract_from_text, name='extract_text'),
    path('api/extract/file/', views.extract_from_file, name='extract_file'),
    path('api/job/<int:job_id>/', views.get_job_status, name='job_status'),
    path('api/job/<int:job_id>/result/', views.get_extracted_cv, name='job_result'),
    path('api/job/<int:job_id>/reprocess/', views.reprocess_job, name='reprocess_job'),
    path('api/jobs/', views.list_jobs, name='list_jobs'),

    # ===== CV UPLOAD API ENDPOINTS =====
    path('api/check-duplicate/', views.check_duplicate_api, name='check_duplicate'),
    path('api/upload/async/', views.upload_pdf_api_async, name='upload_pdf_async'),
    path('api/upload/<int:upload_id>/status/', views.get_upload_status, name='upload_status'),
    path('api/uploads/', views.list_uploads_api, name='list_uploads'),

    # ===== CV EDITOR API =====
    path('api/cv-editor/<str:aid>/update/', views.editor_update_api, name='editor_update'),
    path('api/cv-editor/<str:aid>/generate-word/', views.generate_word_api, name='generate_word'),

    # ===== DELETE & VALIDIERUNG =====
    path('api/cv-editor/<str:aid>/delete/', views.delete_consultant_api, name='delete_consultant'),
    path('api/cv-editor/<str:aid>/archive/',  views.archive_consultant_api,  name='archive_consultant'),
    path('api/cv-editor/<str:aid>/validate/', views.validate_consultant_api, name='validate_consultant'),

    # ===== SKILL MOVE =====
    path('api/cv-editor/<str:aid>/move-skill/', views.move_skill_api, name='move_skill'),

    # ===== URL IMPORT =====
    path('api/import-url-to-db/', views.import_url_to_db_api, name='import_url_to_db'),
    path('api/import-url/', views.import_url_api, name='import_url'),
    path('api/import-url/pdf/', views.import_url_pdf_api, name='import_url_pdf'),

    # ===== FREELANCERMAP SESSION =====
    path('api/flm-session/', views.freelancermap_session_api, name='flm_session'),

    # ===== GULP SESSION =====
    path('api/gu-session/', views.gulp_session_api, name='gulp_session'),

    # ===== URL PLATFORMS =====
    path('api/url-platforms/', views.get_url_platforms, name='url_platforms'),
    path('api/rename-url-dir/', views.rename_url_dir_api, name='rename_url_dir'),

    # ===== SETTINGS =====
    path('api/settings/', views.settings_api, name='settings'),
    path('api/templates-config/', views.templates_config_api, name='templates_config'),
    # ===== HEALTH & TEMPLATES =====
    path('health/', views.health, name='health'),
    path('api/word-templates/', views.list_word_templates, name='word_templates'),

    # ===== OPENAPI / SWAGGER DOKUMENTATION =====
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='cv_extractor:schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='cv_extractor:schema'), name='redoc'),
]
