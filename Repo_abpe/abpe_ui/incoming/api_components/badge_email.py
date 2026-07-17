"""
API für E-Mail-Badge in der Sidebar
Echte Anzahl ungelesener E-Mails
"""

from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from apps.ingest_email.models import EmailMessage


@extend_schema(summary="E-Mail Badge", tags=["Dashboard Komponenten"])
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_email_badge(request):
    """GET /api/components/badge/email/"""
    
    unread_count = EmailMessage.objects.filter(status='NEW').count()
    
    return JsonResponse({
        'count': unread_count,
        'has_unread': unread_count > 0
    })
