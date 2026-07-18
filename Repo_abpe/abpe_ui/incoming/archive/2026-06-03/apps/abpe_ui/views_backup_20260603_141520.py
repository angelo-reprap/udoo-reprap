from django.db import models
import json
import os
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.clickjacking import xframe_options_exempt
from django.conf import settings
from django.contrib.auth.models import User, Group
from django.contrib.admin.views.decorators import staff_member_required
from functools import wraps

from apps.cv_extractor.models import Consultant
from apps.namazu.services.search import search as namazu_search
from apps.namazu.services.indexer import get_status as namazu_get_status, reindex as namazu_reindex, get_profile_html as namazu_get_profile_html
from apps.ingest_email.models import EmailMessage
from apps.abpe_ui.core.module_scanner import scanner


# Index-spezifische Keyword-Felder (text+keyword Mapping, brauchen .keyword für Sort)
SORT_KEYWORD_FIELDS = {
    'abpe_consultants_index': {'first_name', 'full_name', 'last_name'},
    'abpe_emails':            set(),
    'abpe_namazu_profiles':   {'first_name', 'last_name'},
}

# Felder die grundsätzlich nicht sortierbar sind (text-only)
SORT_UNSORTABLE_FIELDS = {
    'headline', 'searchable_text', 'summary',
    'body', 'body_text', 'funktion', 'to_addr',
    'subject', 'full_name',  # text-only in emails/profiles
    # 'size_bytes',           # jetzt im Index vorhanden
}


def build_es_sort(sort_raw, es_index=''):
    """
    Baut ES sort-Liste aus URL-Parameter, index-spezifisch.
    Beispiel: 'full_name:asc,date:desc' -> [{'full_name.keyword': 'asc'}, {'date': 'desc'}]
    Unsortierbare Felder werden übersprungen.
    """
    if not sort_raw:
        return [{'_score': 'desc'}]
    keyword_fields = SORT_KEYWORD_FIELDS.get(es_index, set())
    es_sort = []
    for part in sort_raw.split(','):
        part = part.strip()
        if ':' not in part:
            continue
        field, direction = part.split(':', 1)
        if field in SORT_UNSORTABLE_FIELDS:
            continue
        if field in keyword_fields:
            field = field + '.keyword'
        es_sort.append({field: direction})
    return es_sort if es_sort else [{'_score': 'desc'}]


# ============================================================
# DASHBOARD VIEW
# ============================================================

@login_required
def dashboard(request):
    return render(request, 'abpe_ui/pages/dashboard.html', {
        'active_module': 'dashboard',
        'active':        'dashboard',
        'current_lang':  request.session.get('language', 'de'),
    })


# ============================================================
# API VIEWS (JSON Endpoints)
# ============================================================

@require_http_methods(['GET'])
def api_stats(request):
    stats = {
        'consultants': Consultant.objects.count(),
        'emails':      EmailMessage.objects.count(),
        'projects':    8,
        'matches':     42,
        'trends': {
            'consultants': {'value': 3,   'percentage': 12, 'direction': 'up'},
            'emails':      {'value': 12,  'percentage': 8,  'direction': 'up'},
            'projects':    {'value': -2,  'percentage': 5,  'direction': 'down'},
            'matches':     {'value': 8,   'percentage': 23, 'direction': 'up'},
        },
        'unread_emails': EmailMessage.objects.filter(status='NEW').count(),
    }
    return JsonResponse({'success': True, 'data': stats})


@require_http_methods(['GET'])
def api_system_status(request):
    status = {
        'django':     {'status': 'online',  'value': 'online'},
        'celery':     {'status': 'ok',      'value': 'RUNNING'},
        'postgresql': {'status': 'ok',      'value': 'active'},
        'cpu':        {'status': 'ok',      'value': '23%'},
        'ram':        {'status': 'warning', 'value': '4.2/8 GB (52%)'},
        'gpu':        {'status': 'ok',      'value': 'NVIDIA T4'},
    }
    return JsonResponse({'success': True, 'data': status})


@require_http_methods(['GET'])
def api_recent_consultants(request):
    consultants = Consultant.objects.order_by('-created_at')[:5]
    data = [{
        'name':       f"{c.first_name} {c.last_name}",
        'aid':        c.aid,
        'status':     c.status,
        'created_at': c.created_at.isoformat() if c.created_at else None,
    } for c in consultants]
    return JsonResponse({'success': True, 'data': data})


@require_http_methods(['GET'])
def api_recent_emails(request):
    emails = EmailMessage.objects.order_by('-received_date')[:5]
    data = [{
        'subject':       e.subject[:60] if e.subject else '',
        'from_email':    e.from_email,
        'received_date': e.received_date.isoformat() if e.received_date else None,
        'has_attachments': e.has_attachments,
    } for e in emails]
    return JsonResponse({'success': True, 'data': data})


@require_http_methods(['POST'])
@csrf_exempt
def api_set_language(request):
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    lang = data.get('language', 'de')
    allowed = ['de', 'en', 'fr', 'it', 'es', 'pt', 'nl', 'pl', 'ru', 'tr', 'zh', 'ja', 'ko', 'ar']
    if lang not in allowed:
        lang = 'de'
    request.session['language'] = lang
    if request.user.is_authenticated:
        try:
            from apps.abpe_ui.models import UserSettings
            s, _ = UserSettings.objects.get_or_create(user=request.user)
            s.language = lang
            s.save()
        except Exception:
            pass
    return JsonResponse({'success': True, 'language': lang})


@require_http_methods(['GET', 'POST'])
def api_user_settings(request):
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
    from apps.abpe_ui.models import UserSettings
    s, _ = UserSettings.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        data = json.loads(request.body)
        if 'theme'            in data: s.theme            = data['theme']
        if 'language'         in data:
            s.language = data['language']
            request.session['language'] = data['language']
        if 'sidebar_collapsed' in data: s.sidebar_collapsed = data['sidebar_collapsed']
        if 'nav_order'         in data: s.nav_order         = data['nav_order']
        s.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': True, 'data': {
        'theme':             s.theme,
        'language':          s.language,
        'sidebar_collapsed': s.sidebar_collapsed,
        'nav_order':         s.nav_order or [],
    }})


# ============================================================
# MODUL VIEWS
# ============================================================

def module_view(request, module_id, subpage=None):
    module = scanner.get_module(module_id)
    if not module:
        raise Http404(f"Modul '{module_id}' nicht gefunden")
    template       = None
    active_subpage = None
    if subpage:
        for sp in module.get('subpages', []):
            if sp['id'] == subpage:
                template       = sp.get('template')
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
        'active':        module_id,
        'active_subpage': active_subpage,
        'module_config': module,
        'current_lang':  request.session.get('language', 'de'),
    })


def documentation_page(request, subpage=None):
    module = scanner.get_module('documentation')
    if not module:
        raise Http404("Dokumentations-Modul nicht gefunden")
    template       = None
    active_subpage = 'architecture'
    if subpage:
        for sp in module.get('subpages', []):
            if sp['id'] == subpage:
                template       = sp.get('template')
                active_subpage = subpage
                break
    if not template:
        template = 'abpe_ui/modules/documentation/architecture.html'
    return render(request, template, {
        'active_module': 'documentation',
        'active':        'documentation',
        'active_subpage': active_subpage,
        'module_config': module,
        'current_lang':  request.session.get('language', 'de'),
    })


# ============================================================
# HILFE VIEWS
# ============================================================

@login_required
def help_page(request):
    return render(request, 'abpe_ui/help/index.html', {
        'active_module': 'help',
        'active':        'help',
        'current_lang':  request.session.get('language', 'de'),
    })

@login_required
def help_detail(request, topic):
    return render(request, 'abpe_ui/help/detail.html', {
        'active_module': 'help',
        'active':        'help',
        'topic':         topic,
        'current_lang':  request.session.get('language', 'de'),
    })


# ============================================================
# AUTH VIEWS
# ============================================================

def login_view(request):
    from django.contrib.auth.views import LoginView
    return LoginView.as_view(template_name='abpe_ui/login.html')(request)

def register_view(request):
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
        'form':         form,
        'current_lang': request.session.get('language', 'de'),
    })


# ============================================================
# ADMIN PORTAL API
# ============================================================

def admin_required(view_func):
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
    group  = request.GET.get('group', '')
    status = request.GET.get('status', '')
    search = request.GET.get('search', '')
    qs = User.objects.prefetch_related('groups').all()
    if group:            qs = qs.filter(groups__name=group)
    if status == 'active':   qs = qs.filter(is_active=True)
    elif status == 'inactive': qs = qs.filter(is_active=False)
    if search:
        qs = qs.filter(
            models.Q(username__icontains=search)   |
            models.Q(email__icontains=search)      |
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
    try:
        u = User.objects.get(id=uid)
        if u == request.user:
            return JsonResponse({'success': False, 'error': 'Eigenen Account nicht deaktivieren!'}, status=400)
        u.is_active = not u.is_active
        u.save()
        return JsonResponse({'success': True, 'is_active': u.is_active})
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Not found'}, status=404)


@admin_required
def api_admin_groups(request):
    groups = [{
        'id':         g.id,
        'name':       g.name,
        'user_count': g.user_set.count(),
        'users':      list(g.user_set.values_list('username', flat=True)),
    } for g in Group.objects.prefetch_related('user_set').all()]
    return JsonResponse({'success': True, 'groups': groups})


@admin_required
def api_admin_modules(request):
    from pathlib import Path as P
    modules_dir = P(__file__).parent / 'templates' / 'abpe_ui' / 'modules'
    modules = []
    if modules_dir.exists():
        for module_dir in sorted(modules_dir.iterdir()):
            if module_dir.is_dir():
                config_file = module_dir / 'module.json'
                if config_file.exists():
                    with open(config_file) as f:
                        modules.append(json.load(f))
    modules.sort(key=lambda x: x.get('order', 999))
    return JsonResponse({'success': True, 'modules': modules})


@admin_required
def api_admin_module_update(request, mid):
    if request.method != 'PATCH':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    from pathlib import Path
    data       = json.loads(request.body)
    config_file = Path(__file__).parent / 'templates' / 'abpe_ui' / 'modules' / mid / 'module.json'
    if not config_file.exists():
        return JsonResponse({'success': False, 'error': 'Module not found'}, status=404)
    with open(config_file) as f:
        config = json.load(f)
    if 'enabled' in data: config['enabled'] = bool(data['enabled'])
    if 'order'   in data: config['order']   = int(data['order'])
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=4)
    import importlib
    import apps.abpe_ui.core.module_scanner as scanner_module
    importlib.reload(scanner_module)
    from apps.abpe_ui.core.module_scanner import scanner
    scanner.scan()
    return JsonResponse({'success': True, 'reload_nav': True})


@admin_required
def api_admin_backups(request):
    from pathlib import Path
    from itertools import groupby
    index_file = Path(__file__).parent / 'archive' / 'index.json'
    if not index_file.exists():
        return JsonResponse({'success': True, 'last_backup': None, 'recent': []})
    with open(index_file) as f:
        idx = json.load(f)
    backups = idx.get('backups', [])
    grouped = {}
    for b in sorted(backups, key=lambda x: x['timestamp'], reverse=True):
        date = b['date']
        if date not in grouped:
            grouped[date] = {'timestamp': date, 'message': '', 'files': 0}
        grouped[date]['files'] += 1
        if b.get('message') and not grouped[date]['message']:
            grouped[date]['message'] = b['message']
    return JsonResponse({
        'success':     True,
        'last_backup': backups[-1]['date'] if backups else None,
        'recent':      list(grouped.values())[:10],
    })


@admin_required
def api_admin_audit_log(request):
    from django.contrib.admin.models import LogEntry
    entries = [{
        'time':   e.action_time.strftime('%d.%m.%Y %H:%M'),
        'user':   e.user.username if e.user else '–',
        'action': str(e),
    } for e in LogEntry.objects.select_related('user').order_by('-action_time')[:50]]
    return JsonResponse({'success': True, 'entries': entries})


# ============================================================
# USER / GROUP MODULE PERMISSIONS API
# ============================================================

@admin_required
def api_admin_user_module_permissions(request, uid):
    from apps.abpe_ui.models import UserModulePermission
    from apps.abpe_ui.core.module_scanner import scanner
    try:
        user = User.objects.get(id=uid)
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'User nicht gefunden'}, status=404)
    if request.method == 'POST':
        data           = json.loads(request.body)
        denied_modules = data.get('denied_modules', [])
        UserModulePermission.objects.filter(user=user).delete()
        for module_id in denied_modules:
            UserModulePermission.objects.create(user=user, module_id=module_id, denied=True)
        return JsonResponse({'success': True, 'denied': denied_modules})
    denied = list(UserModulePermission.objects.filter(user=user, denied=True).values_list('module_id', flat=True))
    all_modules = [{'id': m['id'], 'title': m['title'], 'icon': m.get('icon', 'puzzle')} for m in scanner.scan()]
    return JsonResponse({'success': True, 'denied_modules': denied, 'all_modules': all_modules})


@admin_required
def api_admin_group_module_permissions(request, gid):
    from apps.abpe_ui.models import GroupModulePermission
    from apps.abpe_ui.core.module_scanner import scanner
    from django.contrib.auth.models import Group as DjangoGroup
    try:
        group = DjangoGroup.objects.get(id=gid)
    except DjangoGroup.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Gruppe nicht gefunden'}, status=404)
    if request.method == 'POST':
        data           = json.loads(request.body)
        denied_modules = data.get('denied_modules', [])
        GroupModulePermission.objects.filter(group=group).delete()
        for module_id in denied_modules:
            GroupModulePermission.objects.create(group=group, module_id=module_id, denied=True)
        return JsonResponse({'success': True, 'denied': denied_modules})
    denied = list(GroupModulePermission.objects.filter(group=group, denied=True).values_list('module_id', flat=True))
    all_modules = [{'id': m['id'], 'title': m['title'], 'icon': m.get('icon', 'puzzle')} for m in scanner.scan()]
    return JsonResponse({
        'success':        True,
        'group_id':       gid,
        'group_name':     group.name,
        'denied_modules': denied,
        'all_modules':    all_modules,
    })


# ============================================================
# CV EDITOR MODUL
# ============================================================

@login_required
def cv_editor_view(request):
    from apps.cv_extractor.models import SkillCategory
    skill_categories = SkillCategory.objects.filter(is_active=True).order_by('sort_order', 'name')
    return render(request, 'abpe_ui/modules/cv_editor/index.html', {
        'active_module':    'cv_editor',
        'active':           'cv_editor',
        'current_lang':     request.session.get('language', 'de'),
        'skill_categories': skill_categories,
    })


@login_required
def api_cv_editor_consultant(request, aid):
    from apps.cv_extractor.models import Consultant, ConsultantSkill, SkillCategory
    try:
        consultant = Consultant.objects.get(aid=aid)
    except Consultant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Nicht gefunden'}, status=404)
    skill_cats = {}
    for cs in ConsultantSkill.objects.filter(consultant=consultant).select_related('skill'):
        cat = cs.category_name or cs.skill.category_name or 'Sonstige'
        skill_cats.setdefault(cat, []).append(cs.skill.name)
    languages  = [f"{cl.language.name}{' (' + cl.level + ')' if cl.level else ''}" for cl in consultant.languages.all()]
    education  = [{'degree': e.degree, 'institution': e.institution, 'period': e.period or '', 'type': e.education_type} for e in consultant.education.all()]
    industries = [i.industry.name for i in consultant.industries.all()]
    focus_areas= [fa.focus_area.name for fa in consultant.focus_areas.all()]
    certs      = [c.certification.name for c in consultant.certifications.all()]
    produkte   = [p.name for p in consultant.focus_experience_items.all()]
    projects   = []
    for exp in consultant.experience.all().order_by('sort_order'):
        projects.append({
            'id':           exp.id,
            'period':       exp.period or '',
            'company':      exp.company or '',
            'role':         exp.role or exp.title or '',
            'activities':   [a.activity_text for a in exp.activities.all().order_by('sort_order')],
            'technologies': [t.skill.name for t in exp.technologies.all()],
        })
    all_cats     = list(SkillCategory.objects.filter(is_active=True).order_by('sort_order', 'name').values_list('name', flat=True))
    pdf_filename = os.path.basename(consultant.source_filename or f'{consultant.aid}.pdf')
    return JsonResponse({
        'success':      True,
        'id':           consultant.id,
        'aid':          consultant.aid,
        'first_name':   consultant.first_name or '',
        'last_name':    consultant.last_name  or '',
        'headline':     consultant.headline   or '',
        'email':        consultant.email      or '',
        'phone':        consultant.phone      or '',
        'location':     consultant.location   or '',
        'company':      consultant.company    or '',
        'address':      consultant.address    or '',
        'website':      consultant.website    or '',
        'birth_year':   consultant.birth_year,
        'nationality':  consultant.nationality or '',
        'edv_experience_since': consultant.edv_experience_since,
        'availability': consultant.availability or '',
        'stand':        consultant.stand or '',
        'show_name':    consultant.show_name,
        'pdf_filename': pdf_filename,
        'consultant_dir': consultant.consultant_dir or '',
        'languages':    languages,
        'education':    education,
        'industries':   industries,
        'focus_areas':  focus_areas,
        'certifications': certs,
        'produkte':     produkte,
        'skills_by_cat': skill_cats,
        'projects':     projects,
        'skill_categories': all_cats,
    })


# ============================================================
# NAMAZU VIEWS
# ============================================================

def api_namazu_search(request):
    query       = request.GET.get('q', '').strip()
    max_results = int(request.GET.get('max', 20))
    if not query:
        return JsonResponse({'error': 'q required'}, status=400)
    result = namazu_search(query, max_results=min(max_results, 100))
    return JsonResponse(result)


def api_namazu_status(request):
    return JsonResponse(namazu_get_status())


@require_POST
def api_namazu_reindex(request):
    if not request.user.is_staff:
        return JsonResponse({'error': 'forbidden'}, status=403)
    result = namazu_reindex()
    return JsonResponse(result, status=202 if result.get('started') else 500)


@xframe_options_exempt
def api_namazu_profile(request):
    from django.http import HttpResponse
    filename = request.GET.get('file', '').strip()
    if not filename:
        return JsonResponse({'error': 'file required'}, status=400)
    html = namazu_get_profile_html(filename)
    if not html:
        raise Http404('Profil nicht gefunden')
    return HttpResponse(html, content_type='text/html; charset=utf-8')


def api_es_search(request):
    from apps.abpe_search.services.search_service import get_es_client

    query       = request.GET.get('q', '').strip()
    index_name  = request.GET.get('index', 'consultants')
    max_results = int(request.GET.get('max', 10))
    from_offset = int(request.GET.get('from', 0))
    exclude_str = request.GET.get('exclude', '').strip()
    sort_raw    = request.GET.get('sort', '').strip()

    if not query:
        return JsonResponse({'error': 'q required'}, status=400)

    indices = {
        'consultants': ('abpe_consultants_index', 'consultant'),
        'emails':      ('abpe_emails',            'email'),
        'profiles':    ('abpe_namazu_profiles',   'profile'),
    }
    es_index, idx_type = indices.get(index_name, ('abpe_consultants_index', 'consultant'))

    try:
        es       = get_es_client()
        excludes = [e.strip() for e in exclude_str.split(',') if e.strip()]

        if idx_type == 'email':
            must_not = [{'term': {'account': acc}} for acc in excludes] if excludes else []
            body = {
                'size': min(max_results, 50),
                'from': from_offset,
                'query': {
                    'bool': {
                        'must': [{'query_string': {
                            'query':                query,
                            'fields':               ['subject^3', 'body', 'from_addr', 'account', 'folder'],
                            'default_operator':     'AND',
                            'allow_leading_wildcard': True,
                        }}],
                        'must_not': must_not,
                    }
                },
            }
        else:
            fields_map = {
                'profile':    ['body_text^1', 'funktion^2', 'full_name^3'],
                'consultant': ['searchable_text^2', 'full_name^3', 'location', 'availability'],
            }
            body = {
                'size': min(max_results, 50),
                'from': from_offset,
                'query': {'query_string': {
                    'query':                query,
                    'fields':               fields_map.get(idx_type, ['searchable_text^2', 'full_name^3']),
                    'default_operator':     'AND',
                    'allow_leading_wildcard': True,
                }},
            }

        body['sort'] = build_es_sort(sort_raw, es_index)

        count_result = es.count(index=es_index, body={'query': body['query']})
        real_total   = count_result['count']
        result       = es.search(index=es_index, body=body)
        hits         = result['hits']['hits']
        results      = []

        for h in hits:
            src = h['_source']
            if idx_type == 'email':
                results.append({
                    'score':      round(h['_score'] or 0, 2),
                    'type':       'email',
                    'subject':    src.get('subject', '')[:80],
                    'from':       src.get('from_addr', '')[:60],
                    'date':       src.get('date', '')[:10] if src.get('date') else '',
                    'account':    src.get('account', ''),
                    'folder':     src.get('folder', ''),
                    'message_id': src.get('message_id', ''),
                    'snippet':    src.get('body', '')[:150],
                })
            elif idx_type == 'profile':
                results.append({
                    'score':       round(h['_score'] or 0, 2),
                    'type':        'profile',
                    'first':       src.get('first_name', ''),
                    'last':        src.get('last_name', ''),
                    'status':      src.get('status', ''),
                    'funktion':    src.get('funktion', '')[:100],
                    'profile_url': src.get('profile_url', ''),
                })
            else:
                results.append({
                    'score':        round(h['_score'] or 0, 2),
                    'type':         'consultant',
                    'first':        src.get('first_name', ''),
                    'last':         src.get('last_name', ''),
                    'headline':     src.get('headline', '')[:120],
                    'location':     src.get('location', ''),
                    'availability': src.get('availability', ''),
                    'aid':          src.get('aid', ''),
                })

        return JsonResponse({'total': real_total, 'results': results, 'query': query, 'type': idx_type})

    except Exception as e:
        return JsonResponse({'error': str(e), 'results': [], 'total': 0}, status=500)


def api_email_view(request):
    import imaplib, email
    from pathlib import Path
    from django.http import HttpResponse

    account    = request.GET.get('account', '').strip()
    folder     = request.GET.get('folder', '').strip()
    message_id = request.GET.get('message_id', '').strip()
    uid_param  = request.GET.get('uid', '').strip()

    if not all([account, folder]) or not (message_id or uid_param):
        return JsonResponse({'error': 'account, folder, message_id required'}, status=400)

    cfg_path = Path(settings.BASE_DIR) / 'apps/namazu/management/commands/email_settings.json'
    cfg      = json.load(open(cfg_path))
    acc_cfg  = cfg['accounts'].get(account)
    if not acc_cfg or not acc_cfg.get('enabled'):
        return JsonResponse({'error': 'account not found'}, status=404)

    host = cfg['imap']['host']
    port = cfg['imap']['port']
    pw   = acc_cfg['password']

    try:
        m = imaplib.IMAP4_SSL(host, port)
        m.login(account, pw)
        m.select(f'"{folder}"', readonly=True)
        # Zuerst UID aus Elasticsearch holen — viel schneller als IMAP HEADER-Search
        from elasticsearch import Elasticsearch as _ES
        _es  = _ES(['http://localhost:9200'])
        _res = _es.search(index='abpe_emails', body={
            'query': {'term': {'message_id': message_id}},
            '_source': ['uid'], 'size': 1
        })
        _hits = _res['hits']['hits']
        if _hits and _hits[0]['_source'].get('uid'):
            uid = _hits[0]['_source']['uid'].encode()
        else:
            # Fallback: IMAP HEADER-Search (langsam)
            r, data = m.search(None, f'HEADER Message-ID "{message_id}"')
            if r != 'OK' or not data[0]:
                m.logout()
                return JsonResponse({'error': 'E-Mail nicht gefunden'}, status=404)
            uid = data[0].split()[0]
        r, data = m.fetch(uid, '(RFC822)')
        m.logout()
        if r != 'OK':
            return JsonResponse({'error': 'Fetch fehler'}, status=500)

        msg = email.message_from_bytes(data[0][1])

        def decode_h(v):
            if not v: return ''
            parts  = email.header.decode_header(v)
            result = []
            for part, charset in parts:
                if isinstance(part, bytes):
                    result.append(part.decode(charset or 'utf-8', errors='replace'))
                else:
                    result.append(str(part))
            return ' '.join(result)

        subject = decode_h(msg.get('Subject', ''))
        from_   = decode_h(msg.get('From', ''))
        to_     = decode_h(msg.get('To', ''))
        date_   = msg.get('Date', '')

        body_html = body_plain = ''
        if msg.is_multipart():
            for part in msg.walk():
                ct = part.get_content_type()
                if ct == 'text/html' and not body_html:
                    body_html = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='replace')
                elif ct == 'text/plain' and not body_plain:
                    body_plain = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='replace')
        else:
            ct      = msg.get_content_type()
            payload = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8', errors='replace')
            if ct == 'text/html': body_html  = payload
            else:                 body_plain = payload

        body = body_html or f'<pre style="white-space:pre-wrap">{body_plain}</pre>'
        html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
body{{font-family:Arial,sans-serif;margin:0;padding:16px;font-size:13px}}
.header{{background:#f5f5f5;padding:12px;border-radius:6px;margin-bottom:16px;border:1px solid #ddd}}
.header table{{width:100%;border-collapse:collapse}}
.header td{{padding:3px 8px;vertical-align:top}}
.header td:first-child{{font-weight:bold;color:#555;width:80px;white-space:nowrap}}
.body{{border:1px solid #eee;padding:12px;border-radius:6px}}
</style></head><body>
<div class="header"><table>
<tr><td>Von:</td><td>{from_}</td></tr>
<tr><td>An:</td><td>{to_}</td></tr>
<tr><td>Betreff:</td><td><strong>{subject}</strong></td></tr>
<tr><td>Datum:</td><td>{date_}</td></tr>
</table></div>
<div class="body">{body}</div>
</body></html>"""
        return HttpResponse(html, content_type='text/html; charset=utf-8')

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def api_namazu_accounts(request):
    from pathlib import Path
    cfg_path = Path(settings.BASE_DIR) / 'apps/namazu/management/commands/email_settings.json'
    cfg      = json.load(open(cfg_path))
    accounts = {
        user: {
            'description': data.get('description', ''),
            'enabled':     data.get('enabled', False),
            'password':    '••••••••' if data.get('password') else '',
        }
        for user, data in cfg['accounts'].items()
    }
    return JsonResponse({'accounts': accounts})


def api_namazu_accounts_update(request):
    from pathlib import Path
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    if not request.user.is_staff:
        return JsonResponse({'error': 'forbidden'}, status=403)
    data     = json.loads(request.body)
    user     = data.get('user', '').strip()
    password = data.get('password', '').strip()
    enabled  = data.get('enabled', False)
    cfg_path = Path(settings.BASE_DIR) / 'apps/namazu/management/commands/email_settings.json'
    cfg      = json.load(open(cfg_path))
    if user not in cfg['accounts']:
        cfg['accounts'][user] = {'description': user, 'enabled': enabled, 'password': password}
    else:
        if password:
            cfg['accounts'][user]['password'] = password
        cfg['accounts'][user]['enabled'] = enabled
    with open(cfg_path, 'w') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=4)
    return JsonResponse({'success': True})
