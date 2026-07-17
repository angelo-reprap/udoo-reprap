"""
API für Quick Actions Komponente
Liefert nur IDs, Labels kommen aus Sprachpaket
"""

from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiResponse


@extend_schema(
    summary="Quick Actions",
    description="Liefert verfügbare Aktionen für das Dashboard",
    responses={
        200: OpenApiResponse(description="Erfolgreich"),
        401: OpenApiResponse(description="Nicht authentifiziert"),
    },
    tags=["Dashboard Komponenten"]
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_actions(request):
    """
    GET /api/components/actions/
    
    Response: Nur IDs, keine Labels
    """
    
    actions = [
        {
            'id': 'upload_pdf',
            'icon': 'cloud-upload',
            'url': '/cv-editor/upload/',
            'color': 'primary'
        },
        {
            'id': 'add_consultant',
            'icon': 'person-plus',
            'url': '/consultants/add/',
            'color': 'success'
        },
        {
            'id': 'start_matching',
            'icon': 'search',
            'url': '/matching/start/',
            'color': 'info'
        },
        {
            'id': 'contact',
            'icon': 'envelope-paper',
            'url': '/email/compose/',
            'color': 'warning'
        }
    ]
    
    return JsonResponse(actions, safe=False)
