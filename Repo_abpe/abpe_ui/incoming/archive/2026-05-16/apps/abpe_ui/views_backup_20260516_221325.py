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


# ============================================================
# ADMIN PORTAL API
# ============================================================
from django.contrib.auth.models import User, Group
from django.contrib.admin.views.decorators import staff_member_required
from functools import wraps

def admin_required(view_func):
    """Decorator: nur für Admins (is_staff oder Gruppe 'admin')"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
        if not (request.user.is_staff or request.user.groups.filter(name='admin').exists()):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        return view_func(request, *args, **kwargs)
    return wrapper


@admin_required
def api_admin_stats(request):
    """Übersicht-Zahlen für Admin-Portal Index"""
    from apps.abpe_ui.core.module_scanner import scanner
    return JsonResponse({
        'success': True,
        'users':   User.objects.count(),
        'groups':  Group.objects.count(),
        'modules': len(scanner.scan()),
        'status':  'OK',
    })


@admin_required
def api_admin_users(request):
    """GET: Userliste  POST: User anlegen"""
    if request.method == 'POST':
        data = json.loads(request.body)
        try:
            u = User.objects.create_user(
                username   = data['username'],
                email      = data.get('email', ''),
                password   = data.get('password') or None,
                first_name = data.get('first_name', ''),
                last_name  = data.get('last_name', ''),
                is_active  = data.get('is_active', True),
            )
            if data.get('group'):
                g, _ = Group.objects.get_or_create(name=data['group'])
                u.groups.set([g])
            return JsonResponse({'success': True, 'id': u.id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    # GET
    group  = request.GET.get('group', '')
    status = request.GET.get('status', '')
    search = request.GET.get('search', '')

    qs = User.objects.prefetch_related('groups').all()
    if group:
        qs = qs.filter(groups__name=group)
    if status == 'active':
        qs = qs.filter(is_active=True)
    elif status == 'inactive':
        qs = qs.filter(is_active=False)
    if search:
        qs = qs.filter(
            models.Q(username__icontains=search) |
            models.Q(email__icontains=search) |
            models.Q(first_name__icontains=search) |
            models.Q(last_name__icontains=search)
        )

    users = [{
        'id':         u.id,
        'username':   u.username,
        'first_name': u.first_name,
        'last_name':  u.last_name,
        'email':      u.email,
        'is_active':  u.is_active,
        'is_staff':   u.is_staff,
        'groups':     list(u.groups.values_list('name', flat=True)),
        'last_login': u.last_login.strftime('%d.%m.%Y %H:%M') if u.last_login else None,
    } for u in qs]

    return JsonResponse({'success': True, 'users': users})


@admin_required
def api_admin_user_detail(request, uid):
    """GET: User-Detail  PUT: User aktualisieren"""
    try:
        u = User.objects.prefetch_related('groups').get(id=uid)
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Not found'}, status=404)

    if request.method == 'PUT':
        data = json.loads(request.body)
        u.username   = data.get('username',   u.username)
        u.first_name = data.get('first_name', u.first_name)
        u.last_name  = data.get('last_name',  u.last_name)
        u.email      = data.get('email',      u.email)
        u.is_active  = data.get('is_active',  u.is_active)
        if data.get('password'):
            u.set_password(data['password'])
        u.save()
        if 'group' in data:
            if data['group']:
                g, _ = Group.objects.get_or_create(name=data['group'])
                u.groups.set([g])
            else:
                u.groups.clear()
        return JsonResponse({'success': True})

    return JsonResponse({
        'success':    True,
        'id':         u.id,
        'username':   u.username,
        'first_name': u.first_name,
        'last_name':  u.last_name,
        'email':      u.email,
        'is_active':  u.is_active,
        'is_staff':   u.is_staff,
        'groups':     list(u.groups.values_list('name', flat=True)),
        'last_login': u.last_login.strftime('%d.%m.%Y %H:%M') if u.last_login else None,
    })


@admin_required
def api_admin_user_toggle(request, uid):
    """POST: User aktiv/inaktiv umschalten"""
    try:
        u = User.objects.get(id=uid)
        u.is_active = not u.is_active
        u.save()
        return JsonResponse({'success': True, 'is_active': u.is_active})
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Not found'}, status=404)


@admin_required
def api_admin_groups(request):
    """Gruppen mit Mitgliedern"""
    groups = []
    for g in Group.objects.prefetch_related('user_set').all():
        groups.append({
            'id':         g.id,
            'name':       g.name,
            'user_count': g.user_set.count(),
            'users':      list(g.user_set.values_list('username', flat=True)),
        })
    return JsonResponse({'success': True, 'groups': groups})


@admin_required
def api_admin_modules(request):
    """Alle Module aus Scanner — auch deaktivierte"""
    from pathlib import Path as P
    modules_dir = P(__file__).parent / 'templates' / 'abpe_ui' / 'modules'
    modules = []
    if modules_dir.exists():
        for module_dir in sorted(modules_dir.iterdir()):
            if module_dir.is_dir():
                config_file = module_dir / 'module.json'
                if config_file.exists():
                    with open(config_file) as f:
                        config = json.load(f)
                    modules.append(config)
    modules.sort(key=lambda x: x.get('order', 999))
    return JsonResponse({'success': True, 'modules': modules})


@admin_required
def api_admin_module_update(request, mid):
    """PATCH: Modul-Einstellungen ändern (enabled, order)"""
    if request.method != 'PATCH':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    data = json.loads(request.body)
    # Modul-JSON direkt aktualisieren
    import os
    from pathlib import Path
    module_dir = Path(__file__).parent / 'templates' / 'abpe_ui' / 'modules' / mid
    config_file = module_dir / 'module.json'
    if not config_file.exists():
        return JsonResponse({'success': False, 'error': 'Module not found'}, status=404)
    with open(config_file) as f:
        config = json.load(f)
    if 'enabled' in data:
        config['enabled'] = bool(data['enabled'])
    if 'order' in data:
        config['order'] = int(data['order'])
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=4)
    # Scanner in ALLEN Threads neu laden via Import-Reload
    import importlib
    import apps.abpe_ui.core.module_scanner as scanner_module
    importlib.reload(scanner_module)
    # Auch lokalen Scanner aktualisieren
    from apps.abpe_ui.core.module_scanner import scanner
    scanner.scan()
    return JsonResponse({'success': True, 'reload_nav': True})


@admin_required
def api_admin_backups(request):
    """Backup-Liste aus index.json"""
    from pathlib import Path
    index_file = Path(__file__).parent / 'archive' / 'index.json'
    if not index_file.exists():
        return JsonResponse({'success': True, 'last_backup': None, 'recent': []})
    with open(index_file) as f:
        idx = json.load(f)
    backups = idx.get('backups', [])
    # Gruppiere nach Datum
    from itertools import groupby
    grouped = {}
    for b in sorted(backups, key=lambda x: x['timestamp'], reverse=True):
        date = b['date']
        if date not in grouped:
            grouped[date] = {'timestamp': date, 'message': '', 'files': 0}
        grouped[date]['files'] += 1
        if b.get('message') and not grouped[date]['message']:
            grouped[date]['message'] = b['message']
    recent = list(grouped.values())[:10]
    last   = backups[-1]['date'] if backups else None
    return JsonResponse({'success': True, 'last_backup': last, 'recent': recent})


@admin_required
def api_admin_audit_log(request):
    """Einfacher Audit-Log aus Django LogEntry"""
    from django.contrib.admin.models import LogEntry
    entries = []
    for e in LogEntry.objects.select_related('user').order_by('-action_time')[:50]:
        entries.append({
            'time':   e.action_time.strftime('%d.%m.%Y %H:%M'),
            'user':   e.user.username if e.user else '–',
            'action': str(e),
        })
    return JsonResponse({'success': True, 'entries': entries})
