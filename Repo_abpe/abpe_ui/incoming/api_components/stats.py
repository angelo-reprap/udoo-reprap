"""
API für Stats-Grid Komponente
Echte Daten aus der Datenbank
"""

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from apps.cv_extractor.models import Consultant
from apps.ingest_email.models import EmailMessage


def calculate_trend(current, previous):
    """Berechnet Trend aus aktuellen und vorherigen Werten"""
    if previous == 0:
        return None, None, None
    diff = current - previous
    percent = round((diff / previous) * 100)
    direction = 'up' if diff > 0 else 'down' if diff < 0 else 'flat'
    return diff, abs(percent), direction


@extend_schema(summary="Dashboard Statistiken", tags=["Dashboard Komponenten"])
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_stats(request):
    """GET /api/components/stats/"""
    
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    
    # Berater Statistiken
    consultants_total = Consultant.objects.count()
    consultants_new_week = Consultant.objects.filter(created_at__gte=week_ago).count()
    trend_diff, trend_percent, trend_dir = calculate_trend(consultants_new_week, consultants_total * 0.1)
    
    # E-Mail Statistiken
    emails_total = EmailMessage.objects.count()
    emails_unread = EmailMessage.objects.filter(status='NEW').count()
    emails_today = EmailMessage.objects.filter(received_date__gte=today_start).count()
    
    data = {
        'consultants': {
            'total': consultants_total,
            'trend': f'+{consultants_new_week}' if consultants_new_week > 0 else '0',
            'trend_percent': trend_percent,
            'direction': trend_dir,
            'new_this_week': consultants_new_week
        },
        'emails': {
            'total': emails_total,
            'unread': emails_unread,
            'today': emails_today,
            'trend': f'+{emails_today}' if emails_today > 0 else '0',
            'trend_percent': None,
            'direction': 'up' if emails_today > 0 else 'flat'
        },
        'projects': {
            'total': 0,
            'note': 'Wird über Matching App bereitgestellt'
        },
        'matches': {
            'total': 0,
            'note': 'Wird über Matching App bereitgestellt'
        }
    }
    
    return JsonResponse(data)
