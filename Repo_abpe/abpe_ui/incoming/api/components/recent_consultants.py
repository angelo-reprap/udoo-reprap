"""
API für Recent-Consultants Komponente
Echte Berater aus der Datenbank
"""

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from apps.cv_extractor.models import Consultant


@extend_schema(summary="Letzte Berater", tags=["Dashboard Komponenten"])
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_recent_consultants(request):
    """GET /api/components/recent-consultants/"""
    
    consultants = Consultant.objects.order_by('-created_at')[:10]
    
    data = []
    for c in consultants:
        # Status-Klasse für CSS
        status_map = {
            'aktiv': 'active',
            'pending': 'new',
            'inaktiv': 'inactive',
            'gesperrt': 'blocked'
        }
        
        data.append({
            'id': c.id,
            'name': f"{c.first_name} {c.last_name}".strip() or c.aid,
            'aid': c.aid,
            'status': c.status,
            'status_class': status_map.get(c.status, 'unknown'),
            'location': c.location or '',
            'created_at': c.created_at.strftime('%Y-%m-%d'),
            'has_cv': bool(c.cv_data)
        })
    
    return JsonResponse(data, safe=False)
