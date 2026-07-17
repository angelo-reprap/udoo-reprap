"""
URLs für CV Processing
"""
from django.urls import path
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from datetime import datetime

@require_GET
def health_check(request):
    """Health Check Endpoint"""
    return JsonResponse({
        'status': 'healthy',
        'service': 'cv_processing',
        'timestamp': datetime.now().isoformat(),
        'message': 'CV Processing Service is running'
    })

urlpatterns = [
    path('health/', health_check, name='cv_health_check'),
]
