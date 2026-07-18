import json
import os
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.conf import settings

# Importiere bestehende Modelle
from apps.cv_extractor.models import Consultant
from apps.ingest_email.models import EmailMessage


@login_required
def dashboard(request):
    """Haupt-Dashboard Seite"""
    return render(request, 'abpe_ui/pages/dashboard.html')


@require_http_methods(['GET'])
def api_stats(request):
    """Liefert Statistik-Daten für das Dashboard (JSON)"""
    stats = {
        'consultants': Consultant.objects.count(),
        'emails': EmailMessage.objects.count(),
        'projects': 8,  # TODO: Aus ProjectRequest
        'matches': 42,  # TODO: Aus Matching
        'trends': {
            'consultants': {'value': 3, 'percentage': 12, 'direction': 'up'},
            'emails': {'value': 12, 'percentage': 8, 'direction': 'up'},
            'projects': {'value': -2, 'percentage': 5, 'direction': 'down'},
            'matches': {'value': 8, 'percentage': 23, 'direction': 'up'},
        },
        'unread_emails': EmailMessage.objects.filter(status='NEW').count(),
    }
    return JsonResponse({'success': True, 'data': stats})


@require_http_methods(['GET'])
def api_system_status(request):
    """Liefert System-Status (CPU, RAM, Services)"""
    # TODO: Echte System-Werte abfragen
    status = {
        'django': {'status': 'online', 'value': 'online'},
        'celery': {'status': 'ok', 'value': 'RUNNING'},
        'postgresql': {'status': 'ok', 'value': 'active'},
        'cpu': {'status': 'ok', 'value': '23%'},
        'ram': {'status': 'warning', 'value': '4.2/8 GB (52%)'},
        'gpu': {'status': 'ok', 'value': 'NVIDIA T4'},
    }
    return JsonResponse({'success': True, 'data': status})


@require_http_methods(['GET'])
def api_recent_consultants(request):
    """Liefert die letzten 5 Berater"""
    consultants = Consultant.objects.order_by('-created_at')[:5]
    data = []
    for c in consultants:
        data.append({
            'name': f"{c.first_name} {c.last_name}",
            'aid': c.aid,
            'status': c.status,
            'created_at': c.created_at.isoformat() if c.created_at else None,
        })
    return JsonResponse({'success': True, 'data': data})


@require_http_methods(['GET'])
def api_recent_emails(request):
    """Liefert die letzten 5 E-Mails"""
    emails = EmailMessage.objects.order_by('-received_date')[:5]
    data = []
    for e in emails:
        data.append({
            'subject': e.subject[:60],
            'from_email': e.from_email,
            'received_date': e.received_date.isoformat() if e.received_date else None,
            'has_attachments': e.has_attachments,
        })
    return JsonResponse({'success': True, 'data': data})


@require_http_methods(['GET'])
def api_translations(request, lang):
    """Liefert Übersetzungen für eine Sprache (JSON)"""
    lang_file = os.path.join(settings.BASE_DIR, 'apps/abpe_ui/static/abpe_ui/i18n', f'{lang}.json')
    if os.path.exists(lang_file):
        with open(lang_file, 'r', encoding='utf-8') as f:
            translations = json.load(f)
        return JsonResponse({'success': True, 'data': translations})
    return JsonResponse({'success': False, 'error': f'Language {lang} not found'}, status=404)


@login_required
def help_page(request):
    """Hilfe Übersichtsseite"""
    return render(request, 'abpe_ui/help/index.html')


@login_required
def help_detail(request, topic):
    """Detail-Hilfe zu einem Thema"""
    context = {'topic': topic}
    return render(request, 'abpe_ui/help/detail.html', context)
