"""
API für Recent-Emails Komponente
Echte E-Mails aus der Datenbank
"""

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from apps.ingest_email.models import EmailMessage


def format_time_ago(date):
    """Berechnet Zeitdifferenz als lesbaren String"""
    if not date:
        return {'value': 0, 'unit': 'minutes', 'text': 'unbekannt'}
    
    delta = timezone.now() - date
    if delta.days > 0:
        return {'value': delta.days, 'unit': 'days', 'text': f'vor {delta.days} Tag(en)'}
    elif delta.seconds < 3600:
        minutes = max(delta.seconds // 60, 1)
        return {'value': minutes, 'unit': 'minutes', 'text': f'vor {minutes} Min.'}
    else:
        hours = delta.seconds // 3600
        return {'value': hours, 'unit': 'hours', 'text': f'vor {hours} Std.'}


@extend_schema(summary="Letzte E-Mails", tags=["Dashboard Komponenten"])
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_recent_emails(request):
    """GET /api/components/recent-emails/"""
    
    emails = EmailMessage.objects.order_by('-received_date')[:10]
    
    data = []
    for e in emails:
        data.append({
            'id': e.id,
            'subject': e.subject[:80] if e.subject else '(Kein Betreff)',
            'from': e.from_email,
            'received_at': e.received_date.isoformat() if e.received_date else None,
            'time_ago': format_time_ago(e.received_date),
            'is_read': e.status != 'NEW',
            'has_attachments': e.has_attachments,
            'attachment_count': e.attachment_count
        })
    
    return JsonResponse(data, safe=False)
