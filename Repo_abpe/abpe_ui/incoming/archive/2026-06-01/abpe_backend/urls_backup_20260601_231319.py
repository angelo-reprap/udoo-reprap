"""abpe_backend URL Configuration - OPTIMIZED FOR NEW SEARCH SYSTEM"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from datetime import datetime
from rest_framework.authtoken.views import obtain_auth_token
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView


# ========== EXTERNE DASHBOARD VIEWS ==========
@staff_member_required
def simple_dashboard(request):
    from cv_processing.models import CVJob
    total_jobs = CVJob.objects.count()
    completed_jobs = CVJob.objects.filter(status='completed').count()

    stats = {
        'total_processed': total_jobs,
        'successful': completed_jobs,
        'failed': CVJob.objects.filter(status='failed').count(),
        'fallback_used': CVJob.objects.filter(fallback_used=True).count(),
        'avg_processing_time': 38.25,
        'success_rate': (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0,
        'fallback_rate': 0
    }

    recent_activity = []
    for job in CVJob.objects.order_by('-created_at')[:10]:
        recent_activity.append({
            'timestamp': job.created_at,
            'cv_id': f"job_{job.id}",
            'success': job.status == 'completed',
            'processing_time': job.processing_time,
            'method': job.extraction_method or 'ai_with_fallback_backup'
        })

    return render(
        request,
        'admin/cv_processing/dashboard_minimal.html',
        {
            'title': 'ABpE CV Pipeline - Simple Dashboard',
            'stats': stats,
            'recent_activity': recent_activity,
            'timestamp': datetime.now(),
        }
    )


@staff_member_required
def minimal_dashboard(request):
    from cv_processing.models import CVJob
    total = CVJob.objects.count()
    completed = CVJob.objects.filter(status='completed').count()

    return render(
        request,
        'admin/cv_processing/dashboard_minimal.html',
        {
            'title': 'CV Pipeline - Minimal View',
            'stats': {
                'total_processed': total,
                'successful': completed,
                'failed': CVJob.objects.filter(status='failed').count(),
                'avg_processing_time': 38.25,
                'success_rate': (completed / total * 100) if total > 0 else 0,
            },
            'timestamp': datetime.now(),
        }
    )


# ========== URL PATTERNS ==========
urlpatterns = [
    # Favicon
    path('favicon.ico', lambda r: __import__('django.http', fromlist=['FileResponse']).FileResponse(
        open(__import__('os').path.join(__import__('django.conf', fromlist=['settings']).settings.BASE_DIR, 'static', 'favicon.ico'), 'rb')
    )),

    # AI CV Processor App
    path('ai-cv/', include('apps.ai_cv_processor.urls')),

    # Matching Workflow App
    path('matching/', include('apps.abpe_matching_workflow.urls')),

    # Haupt-Admin
    path('admin/', admin.site.urls),

    # ABpE Intake Hub
    path('intake/', include('apps.abpe_intake.urls', namespace='abpe_intake')),

    # Word Document Import
    path('word/', include('apps.ingest_word.urls', namespace='ingest_word')),

    # CSV Import
    path('csv/', include('apps.ingest_csv.urls', namespace='ingest_csv')),

    # TXT Import
    path('txt/', include('apps.ingest_txt.urls', namespace='ingest_txt')),

    # PDF-App
    path('pdf/', include('apps.ingest_pdf.urls', namespace='ingest_pdf')),

    # CV Pipeline
    path('cv-pipeline/', include('apps.cv_pipeline.urls', namespace='cv_pipeline')),

    # CV Extractor
    path('cv-extractor/', include('apps.cv_extractor.urls', namespace='cv_extractor')),

    # URL-APP
    path('url/', include('apps.ingest_url.urls')),

    # EMAIL SYSTEM
    path('email/', include('apps.automail_engine.urls')),

    # Profile / Search
    path('profiles/', include('apps.abpe_profile.urls')),
    path('search/', include('apps.abpe_search.urls')),

    # Auth
    path('accounts/', include('django.contrib.auth.urls')),

    # CRM Bridge
    path('crm-bridge/', include('apps.crm_bridge.urls')),

    # Token Auth
    path('api-token-auth/', obtain_auth_token, name='api_token_auth'),

    # Presort
    path('api/presort/', include('apps.abpe_presort.urls')),

    # Dashboards
    path('admin/cvjob/dashboard/', simple_dashboard, name='simple_dashboard'),
    path('admin/cvjob/dashboard/minimal/', minimal_dashboard, name='minimal_dashboard'),

    # APIs
    path('api/health/', include('cv_processing.urls')),
    path('api/', include('apps.api.urls')),
    path('dashboard/', include('apps.dashboard.urls')),

    # Intranet Portal
    path('portal/', include('apps.abpe_intranet_portal.urls')),

    # Email Studio
    path('email-studio/', include('apps.abpe_email_studio.urls', namespace='email_studio')),

    # doc Studio
    path('doc-studio/', include('apps.abpe_doc_studio.urls', namespace='doc_studio')),

    # ABpE UI (Neues modulares Portal)
    path('', include('apps.abpe_ui.urls')),

    # Django CMS
    path('cms/', include('cms.urls')),
]

# ========== API DOKUMENTATION ==========
urlpatterns += [
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

# ========== HEALTH CHECK ==========
urlpatterns += [
    path('health/', lambda request: JsonResponse({'status': 'healthy', 'service': 'abpe_backend'})),
    path('crm-bridge/health/', lambda request: JsonResponse({'status': 'healthy', 'service': 'crm_bridge'})),
]

# ========== DEBUG MODE ==========
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
