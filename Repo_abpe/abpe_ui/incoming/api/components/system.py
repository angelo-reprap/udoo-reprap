"""
API für System-Grid Komponente
Liefert nur Status, Labels kommen aus Sprachpaket
"""

import psutil
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django.conf import settings


@extend_schema(
    summary="System Status",
    description="Liefert den aktuellen System-Status für das Dashboard",
    responses={
        200: OpenApiResponse(description="Erfolgreich"),
        401: OpenApiResponse(description="Nicht authentifiziert"),
    },
    tags=["Dashboard Komponenten"]
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_system_status(request):
    """
    GET /api/components/system/
    
    Response: Nur Status, keine Labels
    """
    
    cpu_percent = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    ram_used_gb = round(mem.used / (1024**3), 1)
    ram_total_gb = round(mem.total / (1024**3), 1)
    
    def get_status_class(percent):
        if percent < 70:
            return 'ok'
        elif percent < 85:
            return 'warning'
        return 'danger'
    
    data = {
        'services': {
            'django': {
                'status': 'online',
                'icon': 'globe',
                'status_class': 'ok',
                'detail': f'v{settings.DEBUG and "DEBUG" or "PROD"}'
            },
            'celery': {
                'status': 'RUNNING',
                'icon': 'diagram-3',
                'status_class': 'ok',
                'detail': 'Worker: 4'
            },
            'postgresql': {
                'status': 'active',
                'icon': 'database',
                'status_class': 'ok',
                'detail': 'Connections: 12'
            }
        },
        'resources': {
            'cpu': {
                'usage': round(cpu_percent),
                'status_class': get_status_class(cpu_percent),
                'icon': 'cpu'
            },
            'ram': {
                'used': ram_used_gb,
                'total': ram_total_gb,
                'percent': round(mem.percent),
                'status_class': get_status_class(mem.percent),
                'icon': 'memory'
            },
            'gpu': {
                'name': 'NVIDIA T4',
                'status_class': 'ok',
                'icon': 'gpu-card',
                'memory': '16GB'
            }
        }
    }
    
    return JsonResponse(data)
