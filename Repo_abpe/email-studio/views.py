"""
ABpE Email Studio — Portal Views
==================================
4 Reiter: Vorlagen · Studio · Log · Konfiguration
Phase 1: eigenständige Templates (email_studio/base.html)
Phase 2: extends abpe_ui/base.html → eine Zeile ändern
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta

from .models import (
    EmailTemplate, EmailTemplateVersion, EmailLog,
    EmailSignature, EmailSenderAccount, EmailQueue,
    TemplateStatus, AppScope, SignatureMode
)


def _load_es_i18n(lang):
    """Lädt email_studio i18n JSON für inline Script."""
    import json, pathlib
    p = pathlib.Path(f'apps/abpe_ui/static/abpe_ui/i18n/{lang}/modules/email_studio/email_studio.json')
    if not p.exists():
        p = pathlib.Path('apps/abpe_ui/static/abpe_ui/i18n/de/modules/email_studio/email_studio.json')
    try:
        return json.dumps(json.loads(p.read_text()))
    except:
        return '{}'


def _base_context(request, active_tab='index'):
    """Gemeinsamer Context für alle Views."""
    from django.conf import settings as django_settings
    return {
        'active_tab':    active_tab,
        'active_module': 'email',
        'active':        'email',
        'active_subpage': 'studio',
        'current_lang':  request.session.get('language', 'de'),
        'es_i18n':       _load_es_i18n(request.session.get('language', 'de')),
        'user_is_admin': request.user.is_staff,
        'debug':         django_settings.DEBUG,
    }


# ── Reiter 1: Vorlagen-Bibliothek ─────────────────────────────────────────────

@login_required
def index(request):
    """Vorlagen gruppiert nach app_scope — Bibliothek."""
    scope_filter  = request.GET.get('scope', '')
    status_filter = request.GET.get('status', 'ACTIVE')
    search        = request.GET.get('q', '')

    templates = EmailTemplate.objects.select_related(
        'sender_account', 'signature', 'created_by'
    )

    if scope_filter:
        templates = templates.filter(app_scope=scope_filter)
    if status_filter:
        templates = templates.filter(status=status_filter)
    if search:
        templates = templates.filter(
            Q(name__icontains=search) |
            Q(identifier__icontains=search) |
            Q(subject__icontains=search)
        )

    # Gruppieren nach app_scope
    grouped = {}
    for tpl in templates.order_by('app_scope', 'name'):
        scope = tpl.app_scope
        if scope not in grouped:
            grouped[scope] = []
        grouped[scope].append(tpl)

    # Statistik
    stats = {
        'total':   EmailTemplate.objects.count(),
        'active':  EmailTemplate.objects.filter(status=TemplateStatus.ACTIVE).count(),
        'draft':   EmailTemplate.objects.filter(status=TemplateStatus.DRAFT).count(),
        'archive': EmailTemplate.objects.filter(status=TemplateStatus.ARCHIVE).count(),
    }

    ctx = _base_context(request, 'index')
    ctx.update({
        'grouped':       grouped,
        'stats':         stats,
        'scopes':        AppScope.choices,
        'scope_filter':  scope_filter,
        'status_filter': status_filter,
        'search':        search,
    })
    return render(request, 'abpe_ui/modules/email_studio/index.html', ctx)


# ── Reiter 2: Studio / Editor ─────────────────────────────────────────────────

@login_required
def studio(request):
    """HTML-Editor mit Variablen-Panel, Vorschau und Versionsverlauf."""
    template_id = request.GET.get('template')
    template    = None
    versions    = []

    if template_id:
        template = get_object_or_404(
            EmailTemplate.objects.select_related('sender_account', 'signature'),
            pk=template_id
        )
        versions = EmailTemplateVersion.objects.filter(
            template=template
        ).select_related('created_by').order_by('-version')

    # Alle Templates für Sidebar-Liste
    all_templates = EmailTemplate.objects.order_by('app_scope', 'name')
    senders       = EmailSenderAccount.objects.filter(is_active=True)
    signatures    = EmailSignature.objects.all()

    # ?new=blank → leeres Template vorbereiten
    new_mode = request.GET.get('new', '')
    if new_mode == 'blank':
        template = EmailTemplate(
            identifier='', name='', subject='', html_body='', text_body='',
            sender_mode='TEMPLATE', app_scope='general', status='DRAFT',
        )
        template.pk = None
    elif new_mode == 'skeleton':
        template = EmailTemplate(
            identifier='', name='',
            subject='{subject}',
            html_body='''<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;background:#eef2f5;font-family:Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0">
 <tr><td align="center" style="padding:20px 10px;">
  <table width="600" cellpadding="0" cellspacing="0"
         style="background:white;border-radius:8px;overflow:hidden;">
   <tr><td style="background:#163258;padding:16px 24px;text-align:center;">
    <span style="color:white;font-size:18px;font-weight:bold;">abcona e. K.</span>
   </td></tr>
   <tr><td style="padding:24px;">
    <p>Hallo {name},</p>
    <p>Ihr Text hier.</p>
    <p>Mit freundlichen Grüßen<br>{sender_name}</p>
   </td></tr>
   <tr><td style="background:#f8fafc;padding:12px 24px;
                  font-size:11px;color:#6c757d;text-align:center;">
    abcona e. K.
   </td></tr>
  </table>
 </td></tr>
</table>
</body></html>''',
            text_body='''Hallo {name},

Ihr Text hier.

Mit freundlichen Grüßen
{sender_name}''',
            sender_mode='TEMPLATE', app_scope='general', status='DRAFT',
        )
        template.pk = None

    # ?duplicate=<pk> → bestehende Vorlage duplizieren
    elif request.GET.get('duplicate'):
        src_pk = request.GET.get('duplicate')
        src = EmailTemplate.objects.filter(pk=src_pk).first()
        if src:
            template = EmailTemplate(
                identifier=f'{src.identifier}_copy',
                name=f'{src.name} (Kopie)',
                subject=src.subject,
                html_body=src.html_body,
                text_body=src.text_body,
                sender_mode=src.sender_mode,
                app_scope=src.app_scope,
                status='DRAFT',
                variables=src.variables,
            )
            template.pk = None

    # ?lang= → Übersetzung in Editor laden
    edit_lang = request.GET.get('lang', '')
    if edit_lang and template and template.pk:
        from apps.abpe_email_studio.models import EmailTemplateTranslation
        tr = EmailTemplateTranslation.objects.filter(
            template=template, lang=edit_lang
        ).first()
        if tr:
            # Übersetzung temporär als Template-Inhalt einsetzen
            template.subject   = tr.subject
            template.html_body = tr.html_body
            template.text_body = tr.text_body

    # Meilensteine separat laden
    milestones = []
    if template and template.pk:
        milestones = EmailTemplateVersion.objects.filter(
            template=template,
            is_milestone=True
        ).order_by('-created_at')

    ctx = _base_context(request, 'studio')
    ctx.update({
        'template':           template,
        'versions':           versions,
        'milestones':         milestones,
        'all_templates':      all_templates,
        'senders':            senders,
        'signatures':         signatures,
        'scopes':             AppScope.choices,
        'signature_modes':    SignatureMode.choices,
        'new_mode':           new_mode,
        'edit_lang':          edit_lang,
        'context_vars': [
            {'name': 'name'},
            {'name': 'first_name'},
            {'name': 'last_name'},
            {'name': 'email'},
            {'name': 'cv_link'},
            {'name': 'cv_version'},
            {'name': 'created_date'},
            {'name': 'task_ref'},
        ],
        'user_vars': [
            {'name': 'sender_name'},
            {'name': 'sender_email'},
            {'name': 'reply_to'},
        ],
        'system_vars': [
            {'name': 'portal_url'},
            {'name': 'date'},
            {'name': 'year'},
            {'name': 'subject'},
        ],
    })
    return render(request, 'abpe_ui/modules/email_studio/studio.html', ctx)


# ── Reiter 3: Versand-Log ─────────────────────────────────────────────────────

@login_required
def log(request):
    """Protokoll aller gesendeten E-Mails mit Filter."""
    days        = int(request.GET.get('days', 7))
    status      = request.GET.get('status', '')
    template_id = request.GET.get('template', '')
    search      = request.GET.get('q', '')

    since  = timezone.now() - timedelta(days=days)
    logs   = EmailLog.objects.select_related('template', 'sent_by_user')
    logs   = logs.filter(sent_at__gte=since)

    if status:
        logs = logs.filter(status=status)
    if template_id:
        logs = logs.filter(template_id=template_id)
    if search:
        logs = logs.filter(
            Q(subject__icontains=search) |
            Q(from_email__icontains=search) |
            Q(task_reference__icontains=search)
        )

    logs = logs.order_by('-sent_at')[:500]

    # Tages-Statistik
    today_start = timezone.now().replace(hour=0, minute=0, second=0)
    stats = {
        'today_total':   EmailLog.objects.filter(sent_at__gte=today_start).count(),
        'today_ok':      EmailLog.objects.filter(sent_at__gte=today_start, status='OK').count(),
        'today_failed':  EmailLog.objects.filter(sent_at__gte=today_start, status='FAILED').count(),
        'week_total':    EmailLog.objects.filter(sent_at__gte=since).count(),
    }

    templates_used = EmailTemplate.objects.filter(
        logs__sent_at__gte=since
    ).distinct()

    ctx = _base_context(request, 'log')
    ctx.update({
        'logs':           logs,
        'stats':          stats,
        'days':           days,
        'status_filter':  status,
        'template_filter': template_id,
        'search':         search,
        'templates_used': templates_used,
    })
    return render(request, 'abpe_ui/modules/email_studio/log.html', ctx)


# ── Reiter 4: Konfiguration ───────────────────────────────────────────────────

@login_required
@staff_member_required
def config(request):
    """SMTP · Absender-Konten · Signaturen — nur Admin."""
    senders    = EmailSenderAccount.objects.all().order_by('-is_default', 'email')
    signatures = EmailSignature.objects.select_related(
        'sender_account', 'created_by'
    ).order_by('-is_default', 'name')

    ctx = _base_context(request, 'config')
    ctx.update({
        'senders':    senders,
        'signatures': signatures,
    })
    return render(request, 'abpe_ui/modules/email_studio/config.html', ctx)
