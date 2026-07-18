import json
import os
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_http_methods
from django.conf import settings

# Importiere bestehende Modelle
from apps.cv_extractor.models import Consultant
from apps.ingest_email.models import EmailMessage
from apps.abpe_ui.core.module_scanner import scanner


# ============================================================
# DASHBOARD VIEW
# ============================================================

@login_required
def dashboard(request):
    """Haupt-Dashboard Seite"""
    return render(request, 'abpe_ui/pages/dashboard.html', {
        'active_module': 'dashboard',
        'active': 'dashboard',
        'current_lang': request.session.get('language', 'de'),
    })


# ============================================================
# API VIEWS (JSON Endpoints)
# ============================================================

@require_http_methods(['GET'])
def api_stats(request):
    """Liefert Statistik-Daten für das Dashboard (JSON)"""
    stats = {
        'consultants': Consultant.objects.count(),
        'emails': EmailMessage.objects.count(),
        'projects': 8,
        'matches': 42,
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
            'subject': e.subject[:60] if e.subject else '',
            'from_email': e.from_email,
            'received_date': e.received_date.isoformat() if e.received_date else None,
            'has_attachments': e.has_attachments,
        })
    return JsonResponse({'success': True, 'data': data})


@require_http_methods(['POST'])
def api_set_language(request):
    """Setzt die Sprache für die Session"""
    data = json.loads(request.body)
    lang = data.get('language', 'de')
    request.session['language'] = lang

    if request.user.is_authenticated:
        try:
            from apps.abpe_ui.models import UserSettings
            settings, created = UserSettings.objects.get_or_create(user=request.user)
            settings.language = lang
            settings.save()
        except:
            pass

    return JsonResponse({'success': True, 'language': lang})


@require_http_methods(['GET', 'POST'])
def api_user_settings(request):
    """Get/Set User-Einstellungen (Theme, Sprache, Sidebar)"""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)

    from apps.abpe_ui.models import UserSettings

    settings, created = UserSettings.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        data = json.loads(request.body)

        if 'theme' in data:
            settings.theme = data['theme']
        if 'language' in data:
            settings.language = data['language']
            request.session['language'] = data['language']
        if 'sidebar_collapsed' in data:
            settings.sidebar_collapsed = data['sidebar_collapsed']

        settings.save()
        return JsonResponse({'success': True})

    return JsonResponse({
        'success': True,
        'data': {
            'theme': settings.theme,
            'language': settings.language,
            'sidebar_collapsed': settings.sidebar_collapsed,
        }
    })


# ============================================================
# MODUL VIEWS (generisch über module.json)
# ============================================================

def module_view(request, module_id, subpage=None):
    """
    Generische View für alle Module
    Lädt Template und Konfiguration aus module.json
    """
    module = scanner.get_module(module_id)
    if not module:
        raise Http404(f"Modul '{module_id}' nicht gefunden")

    template = None
    active_subpage = None

    if subpage:
        for sp in module.get('subpages', []):
            if sp['id'] == subpage:
                template = sp.get('template')
                active_subpage = subpage
                break

    if not template:
        template = module.get('template', f'abpe_ui/modules/{module_id}/index.html')

    from django.template.loader import get_template
    from django.template.exceptions import TemplateDoesNotExist

    try:
        get_template(template)
    except TemplateDoesNotExist:
        template = f'abpe_ui/modules/{module_id}/index.html'

    return render(request, template, {
        'active_module': module_id,
        'active': module_id,
        'active_subpage': active_subpage,
        'module_config': module,
        'current_lang': request.session.get('language', 'de'),
    })


# ============================================================
# DOKUMENTATIONS-MODUL
# ============================================================

def documentation_page(request, subpage=None):
    """
    Generische View für Dokumentations-Seiten
    Lädt automatisch das passende Template aus module.json
    """
    module = scanner.get_module('documentation')
    if not module:
        raise Http404("Dokumentations-Modul nicht gefunden")

    template = None
    active_subpage = 'architecture'

    if subpage:
        for sp in module.get('subpages', []):
            if sp['id'] == subpage:
                template = sp.get('template')
                active_subpage = subpage
                break

    if not template:
        template = 'abpe_ui/modules/documentation/architecture.html'

    return render(request, template, {
        'active_module': 'documentation',
        'active': 'documentation',
        'active_subpage': active_subpage,
        'module_config': module,
        'current_lang': request.session.get('language', 'de'),
    })


# ============================================================
# HILFE VIEWS
# ============================================================

@login_required
def help_page(request):
    """Hilfe Übersichtsseite"""
    return render(request, 'abpe_ui/help/index.html', {
        'active_module': 'help',
        'active': 'help',
        'current_lang': request.session.get('language', 'de'),
    })


@login_required
def help_detail(request, topic):
    """Detail-Hilfe zu einem Thema"""
    return render(request, 'abpe_ui/help/detail.html', {
        'active_module': 'help',
        'active': 'help',
        'topic': topic,
        'current_lang': request.session.get('language', 'de'),
    })


# ============================================================
# AUTH VIEWS
# ============================================================

def login_view(request):
    """Benutzerdefinierte Login-Seite"""
    from django.contrib.auth.views import LoginView
    return LoginView.as_view(template_name='abpe_ui/login.html')(request)


def register_view(request):
    """Benutzerregistrierung"""
    from django.contrib.auth.forms import UserCreationForm
    from django.shortcuts import redirect

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = UserCreationForm()

    return render(request, 'abpe_ui/register.html', {
        'form': form,
        'current_lang': request.session.get('language', 'de'),
    })
