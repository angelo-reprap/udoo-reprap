"""
ABpE Email Studio — REST API
==============================
Zentrale API für:
  - Template CRUD + Versionierung + Vorschau + Test
  - Zentraler Versand (alle anderen Apps nutzen dies)
  - Log + Statistik
  - Signaturen + Absender-Konten

Andere Apps importieren:
    from apps.abpe_email_studio.api import EmailStudio
    EmailStudio.send(template='cv_generated', recipient='...', variables={...}, user=request.user)
"""
import json
import logging
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Count
from django.utils import timezone
from django.shortcuts import get_object_or_404
from datetime import timedelta

from .models import (
    EmailTemplate, EmailTemplateVersion, EmailLog,
    EmailSignature, EmailSenderAccount, EmailQueue,
    TemplateStatus, AppScope, SenderMode, LogStatus
)

log = logging.getLogger('abpe_email_studio.api')


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _json_body(request) -> dict:
    try:
        return json.loads(request.body)
    except Exception:
        return {}


def _template_to_dict(tpl: EmailTemplate) -> dict:
    return {
        'id':               tpl.pk,
        'identifier':       tpl.identifier,
        'name':             tpl.name,
        'description':      tpl.description,
        'app_scope':        tpl.app_scope,
        'event_type':       tpl.event_type,
        'sender_mode':      tpl.sender_mode,
        'sender_account':   tpl.sender_account.email if tpl.sender_account else None,
        'signature_id':     tpl.signature_id,
        'cc_emails':        tpl.cc_emails,
        'bcc_emails':       tpl.bcc_emails,
        'subject':          tpl.subject,
        'html_body':        tpl.html_body,
        'text_body':        tpl.text_body,
        'variables':        tpl.variables,
        'status':           tpl.status,
        'active_version':   tpl.active_version,
        'include_signature': tpl.include_signature,
        'signature_mode':   tpl.signature_mode,
        'translation_languages': tpl.translation_languages,
        'usage_count':      tpl.usage_count,
        'last_used_at':     tpl.last_used_at.isoformat() if tpl.last_used_at else None,
        'created_at':       tpl.created_at.isoformat(),
        'updated_at':       tpl.updated_at.isoformat(),
    }


def _log_to_dict(entry: EmailLog) -> dict:
    return {
        'log_id':          str(entry.log_id),
        'template':        entry.template.identifier if entry.template else None,
        'from_email':      entry.from_email,
        'from_name':       entry.from_name,
        'sender_mode':     entry.sender_mode,
        'to_emails':       entry.to_emails,
        'cc_emails':       entry.cc_emails,
        'subject':         entry.subject,
        'status':          entry.status,
        'error_message':   entry.error_message,
        'task_reference':  entry.task_reference,
        'app_reference':   entry.app_reference,
        'sent_at':         entry.sent_at.isoformat(),
    }


# ── Template List + Create ────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class TemplateListCreateAPI(LoginRequiredMixin, View):

    def get(self, request):
        scope      = request.GET.get('scope', '')
        status     = request.GET.get('status', '')
        search     = request.GET.get('q', '')
        event_type = request.GET.get('event_type', '')

        qs = EmailTemplate.objects.select_related('sender_account')
        if scope:
            qs = qs.filter(app_scope=scope)
        if status:
            qs = qs.filter(status=status)
        if event_type:
            qs = qs.filter(event_type=event_type)
        if search:
            qs = qs.filter(
                Q(name__icontains=search) | Q(identifier__icontains=search)
            )

        return JsonResponse({
            'templates': [_template_to_dict(t) for t in qs.order_by('app_scope', 'name')],
            'total':     qs.count(),
        })

    def post(self, request):
        data = _json_body(request)
        required = ['identifier', 'name', 'subject', 'html_body']
        missing  = [f for f in required if not data.get(f)]
        if missing:
            return JsonResponse({'error': f'Pflichtfelder fehlen: {missing}'}, status=400)

        if EmailTemplate.objects.filter(identifier=data['identifier']).exists():
            return JsonResponse({'error': f"Identifier '{data['identifier']}' bereits vorhanden"}, status=400)

        sender_account = None
        if data.get('sender_account_id'):
            sender_account = EmailSenderAccount.objects.filter(
                pk=data['sender_account_id']
            ).first()

        tpl = EmailTemplate.objects.create(
            identifier       = data['identifier'],
            name             = data['name'],
            description      = data.get('description', ''),
            app_scope        = data.get('app_scope', AppScope.GENERAL),
            event_type       = data.get('event_type', 'general'),
            sender_mode      = data.get('sender_mode', SenderMode.TEMPLATE),
            sender_account   = sender_account,
            cc_emails        = data.get('cc_emails', ''),
            bcc_emails       = data.get('bcc_emails', ''),
            subject          = data['subject'],
            html_body        = data['html_body'],
            text_body        = data.get('text_body', ''),
            variables        = data.get('variables', []),
            status           = data.get('status', TemplateStatus.DRAFT),
            include_signature = data.get('include_signature', True),
            signature_mode   = data.get('signature_mode', 'USER'),
            created_by       = request.user,
        )
        log.info(f'Template erstellt: {tpl.identifier} von {request.user}')
        return JsonResponse({'template': _template_to_dict(tpl)}, status=201)


# ── Template Detail + Update + Delete ────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class TemplateDetailAPI(LoginRequiredMixin, View):

    def get(self, request, pk):
        tpl = get_object_or_404(EmailTemplate, pk=pk)
        return JsonResponse({'template': _template_to_dict(tpl)})

    def put(self, request, pk):
        tpl  = get_object_or_404(EmailTemplate, pk=pk)
        data = _json_body(request)
        change_note = data.pop('change_note', '')

        updatable = [
            'name', 'description', 'app_scope', 'event_type',
            'sender_mode', 'cc_emails', 'bcc_emails',
            'subject', 'html_body', 'text_body',
            'variables', 'status', 'include_signature', 'signature_mode',
        ]
        for field in updatable:
            if field in data:
                setattr(tpl, field, data[field])

        if data.get('sender_account_id'):
            tpl.sender_account = EmailSenderAccount.objects.filter(
                pk=data['sender_account_id']
            ).first()

        sig_mode = data.get('signature_mode', tpl.signature_mode)
        if sig_mode == 'FIXED' and data.get('signature_id'):
            tpl.signature = EmailSignature.objects.filter(
                pk=data['signature_id']
            ).first()
        elif sig_mode == 'NONE':
            tpl.include_signature = False

        # TXT automatisch via Deepseek generieren wenn HTML geändert
        if 'html_body' in data and data['html_body'] != tpl.html_body:
            try:
                from .services.renderer import EmailRenderer
                renderer = EmailRenderer()
                tpl.text_body = renderer.html_to_text_via_deepseek(data['html_body'])
                log.info(f'TXT auto-generiert für {tpl.identifier}')
            except Exception as e:
                log.warning(f'TXT Auto-Generierung fehlgeschlagen: {e}')

        tpl.save()

        # Neue Version anlegen
        last = EmailTemplateVersion.objects.filter(
            template=tpl
        ).order_by('-version').first()
        next_version = (last.version + 1) if last else 1
        EmailTemplateVersion.objects.create(
            template     = tpl,
            version      = next_version,
            subject      = tpl.subject,
            html_body    = tpl.html_body,
            text_body    = tpl.text_body,
            variables    = tpl.variables,
            sender_mode  = tpl.sender_mode,
            change_note  = change_note,
            is_milestone = False,
            created_by   = request.user,
        )
        tpl.active_version = next_version
        tpl.save(update_fields=['active_version'])

        log.info(f'Template aktualisiert: {tpl.identifier} v{next_version} von {request.user}')
        return JsonResponse({'template': _template_to_dict(tpl)})

    def delete(self, request, pk):
        tpl = get_object_or_404(EmailTemplate, pk=pk)
        identifier = tpl.identifier
        tpl.status = TemplateStatus.ARCHIVE
        tpl.save(update_fields=['status'])
        log.info(f'Template archiviert: {identifier} von {request.user}')
        return JsonResponse({'success': True, 'archived': identifier})



# ── Template Duplicate ────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class TemplateDuplicateAPI(LoginRequiredMixin, View):

    def post(self, request, pk):
        src  = get_object_or_404(EmailTemplate, pk=pk)
        data = _json_body(request)

        new_id   = data.get('identifier', f'{src.identifier}_copy')
        new_name = data.get('name', f'{src.name} (Kopie)')
        scope    = data.get('app_scope', src.app_scope)

        if EmailTemplate.objects.filter(identifier=new_id).exists():
            return JsonResponse(
                {'error': f"Identifier '{new_id}' bereits vorhanden"}, status=400
            )

        dup = EmailTemplate.objects.create(
            identifier       = new_id,
            name             = new_name,
            description      = src.description,
            app_scope        = scope,
            event_type       = src.event_type,
            sender_mode      = src.sender_mode,
            sender_account   = src.sender_account,
            signature        = src.signature,
            cc_emails        = src.cc_emails,
            bcc_emails       = src.bcc_emails,
            subject          = src.subject,
            html_body        = src.html_body,
            text_body        = src.text_body,
            variables        = src.variables,
            status           = TemplateStatus.DRAFT,
            include_signature = src.include_signature,
            created_by       = request.user,
        )
        log.info(f'Template dupliziert: {src.identifier} → {dup.identifier}')
        return JsonResponse({'template': _template_to_dict(dup)}, status=201)


# ── Template Versions ─────────────────────────────────────────────────────────

class TemplateVersionListAPI(LoginRequiredMixin, View):

    def get(self, request, pk):
        tpl      = get_object_or_404(EmailTemplate, pk=pk)
        versions = EmailTemplateVersion.objects.filter(
            template=tpl
        ).order_by('-version').values(
            'version', 'sender_mode', 'change_note',
            'created_at', 'created_by__username'
        )
        return JsonResponse({
            'template_id':     pk,
            'active_version':  tpl.active_version,
            'versions':        list(versions),
        })


@method_decorator(csrf_exempt, name='dispatch')
class TemplateVersionActivateAPI(LoginRequiredMixin, View):

    def post(self, request, pk, version):
        tpl = get_object_or_404(EmailTemplate, pk=pk)
        ver = get_object_or_404(
            EmailTemplateVersion, template=tpl, version=version
        )
        tpl.subject      = ver.subject
        tpl.html_body    = ver.html_body
        tpl.text_body    = ver.text_body
        tpl.variables    = ver.variables
        tpl.sender_mode  = ver.sender_mode
        tpl.active_version = ver.version
        tpl.save()
        log.info(f'Version aktiviert: {tpl.identifier} v{version}')
        return JsonResponse({'success': True, 'active_version': version})


# ── Template Preview ──────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class TemplatePreviewAPI(LoginRequiredMixin, View):

    def post(self, request, pk):
        tpl       = get_object_or_404(EmailTemplate, pk=pk)
        data      = _json_body(request)
        variables = data.get('variables', {})
        mode      = data.get('mode', 'html')  # html | txt | both

        from .services.renderer import EmailRenderer
        renderer = EmailRenderer()

        sender_mode = data.get('sender_mode') or tpl.sender_mode
        if sender_mode == SenderMode.USER:
            from_email = request.user.email or 'max@example.de'
        elif sender_mode == SenderMode.AUTO:
            from_email = 'noreply@abcona.de'
        else:
            from_email = (
                tpl.sender_account.email if tpl.sender_account else 'noreply@abcona.de'
            )

        signature_mode = data.get('signature_mode')
        signature_id   = data.get('signature_id')
        include_sig    = data.get('include_signature')
        if include_sig is None and signature_mode == 'NONE':
            include_sig = False

        preview = renderer.render_preview(
            tpl,
            variables,
            request.user,
            html_body=data.get('html_body'),
            subject=data.get('subject'),
            text_body=data.get('text_body'),
            signature_mode=signature_mode,
            signature_id=signature_id,
            include_signature=include_sig,
        )

        result = {
            'from_email':   from_email,
            'sender_mode':  sender_mode,
            'subject':      preview['subject'],
            'dummy_vars':   renderer.get_default_preview_vars(request.user),
        }

        if mode in ['html', 'both']:
            result['html'] = preview['html']
        if mode in ['txt', 'both']:
            result['text'] = preview['text']

        return JsonResponse(result)


@method_decorator(csrf_exempt, name='dispatch')
class DraftPreviewAPI(LoginRequiredMixin, View):
    """POST /email-studio/api/preview/draft/ — Vorschau ohne gespeichertes Template (KI-Neu)."""

    def post(self, request):
        from .models import EmailTemplate, SenderMode
        from .services.renderer import EmailRenderer

        data = _json_body(request)
        renderer = EmailRenderer()

        tpl = EmailTemplate(
            subject=data.get('subject') or '',
            html_body=data.get('html_body') or '',
            text_body=data.get('text_body') or '',
            sender_mode=data.get('sender_mode') or SenderMode.USER,
            signature_mode=data.get('signature_mode') or 'USER',
            status='DRAFT',
        )

        sender_mode = data.get('sender_mode') or SenderMode.USER
        if sender_mode == SenderMode.USER:
            from_email = request.user.email or 'max@example.de'
        elif sender_mode == SenderMode.AUTO:
            from_email = 'noreply@abcona.de'
        else:
            from_email = 'noreply@abcona.de'

        variables = data.get('variables') or {}
        signature_mode = data.get('signature_mode')
        signature_id = data.get('signature_id')
        include_sig = data.get('include_signature')
        if include_sig is None and signature_mode == 'NONE':
            include_sig = False

        preview = renderer.render_preview(
            tpl,
            variables,
            request.user,
            html_body=data.get('html_body'),
            subject=data.get('subject'),
            text_body=data.get('text_body'),
            signature_mode=signature_mode,
            signature_id=signature_id,
            include_signature=include_sig,
        )

        mode = data.get('mode', 'both')
        result = {
            'from_email': from_email,
            'sender_mode': sender_mode,
            'subject': preview['subject'],
            'dummy_vars': renderer.get_default_preview_vars(request.user),
        }
        if mode in ('html', 'both'):
            result['html'] = preview['html']
        if mode in ('txt', 'both'):
            result['text'] = preview['text']
        return JsonResponse(result)


# ── Template Send Test ────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class TemplateSendTestAPI(LoginRequiredMixin, View):

    def post(self, request, pk):
        tpl       = get_object_or_404(EmailTemplate, pk=pk)
        data      = _json_body(request)
        recipient = data.get('recipient', request.user.email)
        variables = data.get('variables', {})

        if not recipient:
            return JsonResponse({'error': 'Kein Empfänger angegeben'}, status=400)

        from .services.sender import EmailSender
        sender = EmailSender()
        try:
            result = sender.send(
                template      = tpl,
                to_emails     = [recipient],
                variables     = variables,
                user          = request.user,
                task_reference = 'TEST',
                app_reference  = 'email_studio_test',
            )
            return JsonResponse({'success': True, 'result': result})
        except Exception as e:
            log.error(f'Test-Versand fehlgeschlagen: {e}')
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ── Template Compatibility Check ──────────────────────────────────────────────

class TemplateCompatibilityAPI(LoginRequiredMixin, View):

    def get(self, request, pk):
        tpl = get_object_or_404(EmailTemplate, pk=pk)
        from .services.compatibility import CompatibilityChecker
        checker = CompatibilityChecker()
        result  = checker.check(tpl.html_body)
        return JsonResponse(result)


class TemplateMcidValidateAPI(LoginRequiredMixin, View):
    """GET /api/templates/<pk>/mcid-validate/ — MCID Regel 1."""

    def get(self, request, pk):
        tpl = get_object_or_404(EmailTemplate, pk=pk)
        try:
            from .services.mcid_validator import McidValidator
        except ImportError:
            from apps.abpe_email_studio.services.mcid_validator import McidValidator  # type: ignore
        return JsonResponse(McidValidator().validate(tpl.html_body, context='template'))


@method_decorator(csrf_exempt, name='dispatch')
class DraftMcidValidateAPI(LoginRequiredMixin, View):
    """POST /api/mcid-validate/ — Regel 1 für aktuellen Editor-Inhalt."""

    def post(self, request):
        data = _json_body(request)
        html = data.get('html_body') or data.get('html') or ''
        context = data.get('context') or 'template'
        try:
            from .services.mcid_validator import McidValidator
        except ImportError:
            from apps.abpe_email_studio.services.mcid_validator import McidValidator  # type: ignore
        return JsonResponse(McidValidator().validate(html, context=context))


# ── Zentraler Versand (für andere Apps) ──────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class SendAPI(LoginRequiredMixin, View):
    """
    Synchroner Versand — direkt per SMTP.
    Nutzung aus anderen Apps:
        POST /email_studio/api/send/
        {
            "template": "cv_generated_berater",
            "to":       ["max@example.de"],
            "variables": {"name": "Max", "cv_link": "..."},
            "task_reference": "AID-12345"
        }
    """

    def post(self, request):
        data = _json_body(request)

        identifier = data.get('template')
        if not identifier:
            return JsonResponse({'error': 'template Pflichtfeld'}, status=400)

        tpl = EmailTemplate.objects.filter(
            identifier=identifier,
            status=TemplateStatus.ACTIVE
        ).first()
        if not tpl:
            return JsonResponse(
                {'error': f"Template '{identifier}' nicht gefunden oder inaktiv"},
                status=404
            )

        to_emails = data.get('to', [])
        if isinstance(to_emails, str):
            to_emails = [to_emails]
        if not to_emails:
            return JsonResponse({'error': 'to Pflichtfeld'}, status=400)

        from .services.sender import EmailSender
        sender = EmailSender()
        try:
            result = sender.send(
                template       = tpl,
                to_emails      = to_emails,
                variables      = data.get('variables', {}),
                user           = request.user,
                cc_extra       = data.get('cc', []),
                bcc_extra      = data.get('bcc', []),
                task_reference = data.get('task_reference', ''),
                app_reference  = data.get('app_reference', ''),
            )
            return JsonResponse({'success': True, 'log_id': result.get('log_id')})
        except Exception as e:
            log.error(f'SendAPI Fehler: {e}')
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class SendAsyncAPI(LoginRequiredMixin, View):
    """
    Asynchroner Versand über Celery-Queue.
    Gibt sofort queue_id zurück.
    """

    def post(self, request):
        data = _json_body(request)

        identifier = data.get('template')
        if not identifier:
            return JsonResponse({'error': 'template Pflichtfeld'}, status=400)

        tpl = EmailTemplate.objects.filter(
            identifier=identifier,
            status=TemplateStatus.ACTIVE
        ).first()
        if not tpl:
            return JsonResponse(
                {'error': f"Template '{identifier}' nicht gefunden"},
                status=404
            )

        to_emails = data.get('to', [])
        if isinstance(to_emails, str):
            to_emails = [to_emails]

        item = EmailQueue.objects.create(
            template       = tpl,
            to_emails      = to_emails,
            cc_emails      = data.get('cc', []),
            bcc_emails     = data.get('bcc', []),
            variables      = data.get('variables', {}),
            sender_mode    = tpl.sender_mode,
            user_id        = request.user.pk,
            task_reference = data.get('task_reference', ''),
            app_reference  = data.get('app_reference', ''),
        )

        from .tasks import send_queued_email
        task = send_queued_email.delay(str(item.queue_id))
        item.celery_task_id = task.id
        item.save(update_fields=['celery_task_id'])

        return JsonResponse({
            'success':  True,
            'queue_id': str(item.queue_id),
            'task_id':  task.id,
        })


# ── Log API ───────────────────────────────────────────────────────────────────

class LogListAPI(LoginRequiredMixin, View):

    def get(self, request):
        days   = int(request.GET.get('days', 7))
        status = request.GET.get('status', '')
        search = request.GET.get('q', '')
        since  = timezone.now() - timedelta(days=days)

        qs = EmailLog.objects.select_related('template').filter(sent_at__gte=since)
        if status:
            qs = qs.filter(status=status)
        if search:
            qs = qs.filter(
                Q(subject__icontains=search) |
                Q(from_email__icontains=search) |
                Q(task_reference__icontains=search)
            )

        return JsonResponse({
            'logs':  [_log_to_dict(e) for e in qs.order_by('-sent_at')[:200]],
            'total': qs.count(),
        })


class LogStatsAPI(LoginRequiredMixin, View):

    def get(self, request):
        today = timezone.now().replace(hour=0, minute=0, second=0)
        week  = timezone.now() - timedelta(days=7)
        return JsonResponse({
            'today': {
                'total':  EmailLog.objects.filter(sent_at__gte=today).count(),
                'ok':     EmailLog.objects.filter(sent_at__gte=today, status='OK').count(),
                'failed': EmailLog.objects.filter(sent_at__gte=today, status='FAILED').count(),
            },
            'week': {
                'total':  EmailLog.objects.filter(sent_at__gte=week).count(),
                'ok':     EmailLog.objects.filter(sent_at__gte=week, status='OK').count(),
                'failed': EmailLog.objects.filter(sent_at__gte=week, status='FAILED').count(),
            },
        })


# ── Signaturen API ────────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class SignatureListCreateAPI(LoginRequiredMixin, View):

    def get(self, request):
        sigs = EmailSignature.objects.select_related('sender_account')
        return JsonResponse({
            'signatures': [{
                'id':             s.pk,
                'name':           s.name,
                'identifier':     s.identifier,
                'sender_account': s.sender_account.email if s.sender_account else None,
                'sender_account_id': s.sender_account_id,
                'is_default':     s.is_default,
                'is_public':      s.is_public,
            } for s in sigs]
        })

    def post(self, request):
        data = _json_body(request)
        identifier = (data.get('identifier') or '').strip()
        name = (data.get('name') or '').strip()
        if not name or not identifier:
            return JsonResponse(
                {'error': 'name und identifier sind Pflichtfelder'},
                status=400,
            )
        if EmailSignature.objects.filter(identifier=identifier).exists():
            return JsonResponse(
                {'error': f'Identifier „{identifier}" bereits vergeben'},
                status=400,
            )
        sender_id = data.get('sender_account_id') or None
        sig = EmailSignature.objects.create(
            name             = name,
            identifier       = identifier,
            html_body        = data.get('html_body', ''),
            text_body        = data.get('text_body', ''),
            sender_account_id = sender_id,
            is_default       = data.get('is_default', False),
            is_public        = data.get('is_public', False),
            created_by       = request.user,
        )
        if sig.is_default:
            EmailSignature.objects.exclude(pk=sig.pk).update(is_default=False)
        return JsonResponse({'id': sig.pk, 'name': sig.name}, status=201)


@method_decorator(csrf_exempt, name='dispatch')
class SignatureDetailAPI(LoginRequiredMixin, View):

    def get(self, request, pk):
        sig = get_object_or_404(
            EmailSignature.objects.select_related('sender_account'),
            pk=pk,
        )
        return JsonResponse({
            'id':                sig.pk,
            'name':              sig.name,
            'identifier':        sig.identifier,
            'html_body':         sig.html_body,
            'text_body':         sig.text_body,
            'sender_account_id': sig.sender_account_id,
            'sender_account':    sig.sender_account.email if sig.sender_account else None,
            'is_default':        sig.is_default,
            'is_public':         sig.is_public,
        })

    def put(self, request, pk):
        sig  = get_object_or_404(EmailSignature, pk=pk)
        data = _json_body(request)
        if 'identifier' in data:
            new_id = (data['identifier'] or '').strip()
            if not new_id:
                return JsonResponse({'error': 'identifier darf nicht leer sein'}, status=400)
            if EmailSignature.objects.filter(identifier=new_id).exclude(pk=pk).exists():
                return JsonResponse(
                    {'error': f'Identifier „{new_id}" bereits vergeben'},
                    status=400,
                )
            sig.identifier = new_id
        for f in ['name', 'html_body', 'text_body', 'is_default', 'is_public']:
            if f in data:
                setattr(sig, f, data[f])
        if 'sender_account_id' in data:
            sig.sender_account_id = data['sender_account_id'] or None
        sig.save()
        if sig.is_default:
            EmailSignature.objects.exclude(pk=sig.pk).update(is_default=False)
        return JsonResponse({'success': True})

    def delete(self, request, pk):
        get_object_or_404(EmailSignature, pk=pk).delete()
        return JsonResponse({'success': True})


# ── Absender-Konten API ───────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class SenderAccountListAPI(LoginRequiredMixin, View):

    def get(self, request):
        return JsonResponse({
            'senders': [{
                'id':           s.pk,
                'email':        s.email,
                'display_name': s.display_name,
                'sender_mode':  s.sender_mode,
                'is_default':   s.is_default,
                'is_active':    s.is_active,
            } for s in EmailSenderAccount.objects.all()]
        })

    def post(self, request):
        data = _json_body(request)
        if not data.get('email'):
            return JsonResponse({'error': 'email Pflichtfeld'}, status=400)
        acc = EmailSenderAccount.objects.create(
            email        = data['email'],
            display_name = data.get('display_name', data['email']),
            sender_mode  = data.get('sender_mode', SenderMode.TEMPLATE),
            is_default   = data.get('is_default', False),
            description  = data.get('description', ''),
        )
        return JsonResponse({'id': acc.pk, 'email': acc.email}, status=201)


@method_decorator(csrf_exempt, name='dispatch')
class SenderAccountDetailAPI(LoginRequiredMixin, View):

    def put(self, request, pk):
        acc  = get_object_or_404(EmailSenderAccount, pk=pk)
        data = _json_body(request)
        for f in ['display_name', 'sender_mode', 'is_default', 'is_active', 'description']:
            if f in data:
                setattr(acc, f, data[f])
        acc.save()
        return JsonResponse({'success': True})

    def delete(self, request, pk):
        get_object_or_404(EmailSenderAccount, pk=pk).delete()
        return JsonResponse({'success': True})


@method_decorator(csrf_exempt, name='dispatch')
class SenderSMTPTestAPI(LoginRequiredMixin, View):

    def post(self, request):
        from .services.sender import EmailSender
        try:
            EmailSender().test_connection()
            return JsonResponse({'success': True, 'message': 'SMTP Verbindung OK'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ── Variablen API ─────────────────────────────────────────────────────────────

class VariableListAPI(LoginRequiredMixin, View):
    """
    Gibt alle bekannten Variablen zurück — kontextabhängig nach app_scope.
    """

    def get(self, request):
        from .variables_registry import get_sidebar_variable_groups, get_variables
        scope = request.GET.get('scope', 'general')
        identifier = request.GET.get('identifier', '')
        return JsonResponse({
            'variables': get_variables(scope, identifier),
            'groups': get_sidebar_variable_groups(scope, identifier),
        })


# ── Queue API ─────────────────────────────────────────────────────────────────

class QueueListAPI(LoginRequiredMixin, View):

    def get(self, request):
        qs = EmailQueue.objects.select_related('template').order_by('-created_at')[:100]
        return JsonResponse({
            'queue': [{
                'queue_id':      str(q.queue_id),
                'template':      q.template.identifier,
                'status':        q.status,
                'retry_count':   q.retry_count,
                'created_at':    q.created_at.isoformat(),
                'processed_at':  q.processed_at.isoformat() if q.processed_at else None,
            } for q in qs]
        })


@method_decorator(csrf_exempt, name='dispatch')
class QueueCancelAPI(LoginRequiredMixin, View):

    def post(self, request, queue_id):
        item = get_object_or_404(EmailQueue, queue_id=queue_id)
        if item.status in ['PENDING']:
            item.status = 'CANCELLED'
            item.save(update_fields=['status'])
            return JsonResponse({'success': True})
        return JsonResponse(
            {'error': f'Status {item.status} kann nicht abgebrochen werden'},
            status=400
        )


# ══════════════════════════════════════════════════════════════════════════════
# PYTHON API — für andere Apps
# Nutzung:
#   from apps.abpe_email_studio.api import EmailStudio
#   EmailStudio.send(template='cv_generated_berater', recipient='...', variables={})
# ══════════════════════════════════════════════════════════════════════════════

class EmailStudio:
    """
    Zentrale Python-API für andere Django-Apps.
    Kein HTTP — direkter Python-Aufruf.
    """

    @staticmethod
    def send(template: str, recipient: str | list,
             variables: dict = None, user=None,
             cc: list = None, bcc: list = None,
             task_reference: str = '', app_reference: str = '',
             async_send: bool = False,
             lang: str = 'de') -> dict:
        """
        Sendet eine E-Mail über ein Template.

        Args:
            template:       Identifier der Vorlage (z.B. 'cv_generated_berater')
            recipient:      E-Mail Adresse oder Liste
            variables:      Variablen für die Vorlage
            user:           Django User (für User-Modus)
            cc:             Zusätzliche CC-Adressen
            bcc:            Zusätzliche BCC-Adressen
            task_reference: Referenz (z.B. 'AID-12345')
            app_reference:  Welche App sendet (z.B. 'cv_extractor')
            async_send:     True = Celery Queue, False = direkt

        Returns:
            {'success': True, 'log_id': '...'}  oder
            {'success': False, 'error': '...'}
        """
        tpl = EmailTemplate.objects.filter(
            identifier=template,
            status=TemplateStatus.ACTIVE
        ).first()

        if not tpl:
            log.error(f'EmailStudio.send: Template nicht gefunden: {template}')
            return {'success': False, 'error': f"Template '{template}' nicht gefunden"}

        to_emails = [recipient] if isinstance(recipient, str) else recipient
        variables = variables or {}

        if async_send:
            from .tasks import send_queued_email
            item = EmailQueue.objects.create(
                template       = tpl,
                to_emails      = to_emails,
                cc_emails      = cc or [],
                bcc_emails     = bcc or [],
                variables      = variables,
                sender_mode    = tpl.sender_mode,
                user_id        = user.pk if user else None,
                task_reference = task_reference,
                app_reference  = app_reference,
            )
            task = send_queued_email.delay(str(item.queue_id))
            return {'success': True, 'queue_id': str(item.queue_id), 'task_id': task.id}

        from .services.sender import EmailSender
        from .services.translator import EmailTranslator

        sender = EmailSender()

        # Sprach-Logik: lang Parameter oder aus Empfänger-Kontext erkennen
        send_lang = lang or 'de'

        # Wenn Sprache != DE → Übersetzung laden oder erstellen
        if send_lang != 'de':
            translation = EmailTranslator.get_translation(tpl, send_lang)
            if not translation:
                log.info(f'Übersetzung {tpl.identifier}→{send_lang} fehlt, erstelle...')
                EmailTranslator.translate_template(tpl, [send_lang])
                translation = EmailTranslator.get_translation(tpl, send_lang)
            if translation:
                # Temporäres Template-Objekt mit übersetztem Inhalt
                from copy import copy
                tpl_translated = copy(tpl)
                tpl_translated.subject   = translation.subject
                tpl_translated.html_body = translation.html_body
                tpl_translated.text_body = translation.text_body
                tpl = tpl_translated

        return sender.send(
            template       = tpl,
            to_emails      = to_emails,
            variables      = variables,
            user           = user,
            cc_extra       = cc or [],
            bcc_extra      = bcc or [],
            task_reference = task_reference,
            app_reference  = app_reference,
        )

    @staticmethod
    def preview(template: str, variables: dict = None, user=None) -> dict:
        """Rendert eine Vorschau ohne zu senden."""
        tpl = EmailTemplate.objects.filter(identifier=template).first()
        if not tpl:
            return {'error': f"Template '{template}' nicht gefunden"}
        from .services.renderer import EmailRenderer
        renderer = EmailRenderer()
        return {
            'subject': renderer.render_subject(tpl.subject, variables or {}),
            'html':    renderer.render_html(tpl, variables or {}, user),
            'text':    renderer.render_text(tpl, variables or {}),
        }

    @staticmethod
    def get_template(identifier: str) -> EmailTemplate | None:
        """Gibt ein Template-Objekt zurück."""
        return EmailTemplate.objects.filter(
            identifier=identifier,
            status=TemplateStatus.ACTIVE
        ).first()


# ── Template Translation API ──────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class TemplateTranslateAPI(LoginRequiredMixin, View):
    """
    Übersetzt ein Template in eine oder mehrere Sprachen.
    POST { langs: ['en', 'fr'], force: false }
    """

    def post(self, request, pk):
        tpl  = get_object_or_404(EmailTemplate, pk=pk)
        data = _json_body(request)
        langs = data.get('langs', [])
        force = data.get('force', False)

        if not langs:
            from .services.translator import EmailTranslator
            langs = EmailTranslator.default_languages()

        try:
            from .services.translator import EmailTranslator
            results = EmailTranslator.translate_template(tpl, langs, force=force)
            log.info(f'Translation {tpl.identifier} → {langs}: {results}')
            return JsonResponse({'success': True, 'results': results})
        except Exception as e:
            log.error(f'Translation fehlgeschlagen: {e}')
            return JsonResponse({'success': False, 'error': str(e)}, status=500)



# ── Translation Detail API ────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class TranslationDetailAPI(LoginRequiredMixin, View):

    def get(self, request, pk, lang):
        from .models import EmailTemplateTranslation
        tpl = get_object_or_404(EmailTemplate, pk=pk)
        tr  = get_object_or_404(EmailTemplateTranslation, template=tpl, lang=lang)
        return JsonResponse({
            'lang':             tr.lang,
            'subject':          tr.subject,
            'html_body':        tr.html_body,
            'text_body':        tr.text_body,
            'auto_translated':  tr.auto_translated,
            'reviewed':         tr.reviewed,
            'translated_at':    tr.translated_at.isoformat(),
        })

    def put(self, request, pk, lang):
        from .models import EmailTemplateTranslation
        tpl  = get_object_or_404(EmailTemplate, pk=pk)
        data = _json_body(request)
        tr, created = EmailTemplateTranslation.objects.get_or_create(
            template=tpl, lang=lang,
            defaults={'subject': '', 'html_body': '', 'text_body': ''}
        )
        for f in ['subject', 'html_body', 'text_body', 'reviewed', 'auto_translated']:
            if f in data:
                setattr(tr, f, data[f])
        tr.save()
        log.info(f'Übersetzung gespeichert: {tpl.identifier} [{lang}] von {request.user}')
        return JsonResponse({'success': True, 'lang': lang, 'created': created})

    def delete(self, request, pk, lang):
        from .models import EmailTemplateTranslation
        tpl = get_object_or_404(EmailTemplate, pk=pk)
        EmailTemplateTranslation.objects.filter(template=tpl, lang=lang).delete()
        return JsonResponse({'success': True})


# ── Template Set Languages API ────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class TemplateSetLangsAPI(LoginRequiredMixin, View):
    """
    Aktiviert oder deaktiviert eine Sprache für ein Template.
    POST { lang: 'it', enabled: true }
    """
    def post(self, request, pk):
        tpl  = get_object_or_404(EmailTemplate, pk=pk)
        data = _json_body(request)
        lang    = data.get('lang', '')
        enabled = data.get('enabled', True)
        if not lang:
            return JsonResponse({'error': 'lang fehlt'}, status=400)
        langs = list(tpl.translation_languages or [])
        if enabled and lang not in langs:
            langs.append(lang)
        elif not enabled and lang in langs:
            langs.remove(lang)
        tpl.translation_languages = langs
        tpl.save(update_fields=['translation_languages'])
        log.info(f'{tpl.identifier} Sprachen: {langs}')
        return JsonResponse({'success': True, 'languages': langs})


# ── Module API ────────────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class ModuleListAPI(LoginRequiredMixin, View):
    """GET /api/modules/ — Liste · POST — neues Modul anlegen."""

    def get(self, request):
        from .models import EmailModule, ModuleType
        module_type = request.GET.get('type', '')
        qs = EmailModule.objects.filter(is_active=True)
        if module_type:
            qs = qs.filter(module_type=module_type)

        try:
            from .blocks_registry import (
                FORMAT_MODULE_META,
                FORMAT_MODULE_ORDER,
                MODULE_GROUP_ORDER,
                PAIRED_MODULE_IDS,
                block_insert_syntax,
                format_module_label,
                get_blocks,
                get_module_husk,
                module_insert_syntax,
            )
        except ImportError:
            from apps.abpe_email_studio.blocks_registry import (  # type: ignore
                FORMAT_MODULE_META,
                FORMAT_MODULE_ORDER,
                MODULE_GROUP_ORDER,
                PAIRED_MODULE_IDS,
                block_insert_syntax,
                format_module_label,
                get_blocks,
                get_module_husk,
                module_insert_syntax,
            )

        lang = (request.GET.get('lang') or getattr(request, 'LANGUAGE_CODE', None) or 'de')[:2]
        raw: dict = {}

        for m in qs:
            if m.identifier == 'signature':
                continue
            t = m.module_type
            raw.setdefault(t, []).append({
                'id':          m.pk,
                'identifier':  m.identifier,
                'name':        m.name,
                'module_type': m.module_type,
                'description': m.description,
                'syntax':      module_insert_syntax(m.identifier),
                'paired':      m.identifier in PAIRED_MODULE_IDS,
                'preview_bg':  m.preview_bg,
            })

        # MCID Format-Module (feste Reihenfolge, klare Namen)
        fmt_group = []
        existing_ids = {m['identifier'] for lst in raw.values() for m in lst}
        for fmt_id in FORMAT_MODULE_ORDER:
            if fmt_id in existing_ids:
                # DB-Eintrag: Name ggf. belassen, aber Reihenfolge später steuern
                continue
            meta = FORMAT_MODULE_META.get(fmt_id) or {}
            fmt_group.append({
                'id': 0,
                'identifier': fmt_id,
                'name': format_module_label(fmt_id, lang),
                'module_type': 'FORMAT',
                'description': meta.get('description') or 'MCID Format-Modul',
                'syntax': module_insert_syntax(fmt_id),
                'paired': fmt_id in PAIRED_MODULE_IDS,
                'preview_bg': '#f8f9fa',
                'is_virtual': True,
                'husk_html': get_module_husk(fmt_id, 'html'),
            })
        if fmt_group:
            raw['FORMAT'] = fmt_group

        # MCID Blöcke (Registry-Reihenfolge)
        block_group = []
        for b in get_blocks():
            block_group.append({
                'id': 0,
                'identifier': b['id'],
                'name': b['name'],
                'module_type': 'BLOCK',
                'description': b.get('description') or '',
                'syntax': block_insert_syntax(b['id']),
                'paired': bool(b.get('paired')),
                'module': b.get('module'),
                'variables': b.get('variables') or [],
                'preview_bg': '#fff8e6',
                'is_virtual': True,
            })
        if block_group:
            raw['BLOCK'] = block_group

        raw['SIGNATURE'] = [{
            'id':          0,
            'identifier':  'signature',
            'name':        'Signatur (auswählbar)',
            'module_type': 'SIGNATURE',
            'description': 'Signatur-Quelle links im Panel wählen',
            'syntax':      '{{block:signature}}',
            'preview_bg':  '#ffffff',
            'is_virtual':  True,
        }]

        # Stabile Gruppenreihenfolge für Sidebar
        grouped = {}
        for key in MODULE_GROUP_ORDER:
            if key in raw and raw[key]:
                grouped[key] = raw[key]
        for key, lst in raw.items():
            if key not in grouped and lst:
                grouped[key] = lst

        return JsonResponse({
            'modules': grouped,
            'types':   list(ModuleType.choices) + [('FORMAT', 'Format'), ('BLOCK', 'Block')],
            'blocks':  block_group,
            'group_order': list(MODULE_GROUP_ORDER),
        })

    def post(self, request):
        from .models import EmailModule, ModuleType
        data = _json_body(request)
        identifier = (data.get('identifier') or '').strip()
        name = (data.get('name') or '').strip()
        if not name or not identifier:
            return JsonResponse(
                {'error': 'name und identifier sind Pflichtfelder'},
                status=400,
            )
        if EmailModule.objects.filter(identifier=identifier).exists():
            return JsonResponse(
                {'error': f'Identifier „{identifier}" bereits vergeben'},
                status=400,
            )
        mod = EmailModule.objects.create(
            name         = name,
            identifier   = identifier,
            module_type  = data.get('module_type', ModuleType.SECTION),
            description  = data.get('description', ''),
            html_body    = data.get('html_body', ''),
            text_body    = data.get('text_body', ''),
            preview_bg   = data.get('preview_bg', '#ffffff'),
            created_by   = request.user,
        )
        return JsonResponse({
            'id': mod.pk, 'name': mod.name, 'identifier': mod.identifier,
        }, status=201)


@method_decorator(csrf_exempt, name='dispatch')
class ModuleDetailAPI(LoginRequiredMixin, View):
    """GET/PUT/DELETE /api/modules/<pk>/ — Modul-Detail für Studio-Editor."""

    def get(self, request, pk):
        from .models import EmailModule
        mod = get_object_or_404(EmailModule, pk=pk, is_active=True)
        return JsonResponse({
            'id':          mod.pk,
            'identifier':  mod.identifier,
            'name':        mod.name,
            'module_type': mod.module_type,
            'description': mod.description,
            'html_body':   mod.html_body,
            'text_body':   mod.text_body,
            'preview_bg':  mod.preview_bg,
        })

    def put(self, request, pk):
        from .models import EmailModule
        mod  = get_object_or_404(EmailModule, pk=pk)
        data = _json_body(request)
        if 'identifier' in data:
            new_id = (data['identifier'] or '').strip()
            if not new_id:
                return JsonResponse({'error': 'identifier darf nicht leer sein'}, status=400)
            if EmailModule.objects.filter(identifier=new_id).exclude(pk=pk).exists():
                return JsonResponse(
                    {'error': f'Identifier „{new_id}" bereits vergeben'},
                    status=400,
                )
            mod.identifier = new_id
        for f in ['name', 'html_body', 'text_body', 'description',
                  'module_type', 'preview_bg', 'is_active']:
            if f in data:
                setattr(mod, f, data[f])
        mod.save()
        return JsonResponse({'success': True})

    def delete(self, request, pk):
        from .models import EmailModule
        mod = get_object_or_404(EmailModule, pk=pk)
        mod.is_active = False
        mod.save()
        return JsonResponse({'success': True})


# ── Meilenstein API ───────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class MilestoneListCreateAPI(LoginRequiredMixin, View):
    """
    GET  /api/templates/<pk>/milestones/
         Gibt alle Meilensteine eines Templates zurueck.
    POST /api/templates/<pk>/milestones/
         Erstellt einen neuen Meilenstein aus dem aktuellen Stand.
         Body: { "label": "vor Farb-Test" }
    """

    def get(self, request, pk):
        tpl = get_object_or_404(EmailTemplate, pk=pk)
        milestones = EmailTemplateVersion.objects.filter(
            template=tpl,
            is_milestone=True
        ).order_by('-created_at').values(
            'id', 'version', 'milestone_label', 'change_note',
            'subject', 'html_body', 'text_body',
            'created_at', 'created_by__username'
        )
        return JsonResponse({
            'template_id': pk,
            'milestones':  list(milestones),
        })

    def post(self, request, pk):
        tpl  = get_object_or_404(EmailTemplate, pk=pk)
        data = _json_body(request)
        label = data.get('label', '').strip()
        if not label:
            return JsonResponse({'error': 'label ist Pflichtfeld'}, status=400)

        # Maximale Versionsnummer bestimmen
        last = EmailTemplateVersion.objects.filter(
            template=tpl
        ).order_by('-version').first()
        next_version = (last.version + 1) if last else 1

        # Aktuellen Stand als Meilenstein speichern
        ms = EmailTemplateVersion.objects.create(
            template        = tpl,
            version         = next_version,
            subject         = tpl.subject,
            html_body       = tpl.html_body,
            text_body       = tpl.text_body,
            variables       = tpl.variables,
            sender_mode     = tpl.sender_mode,
            change_note     = label,
            is_milestone    = True,
            milestone_label = label,
            created_by      = request.user,
        )
        log.info(f'Meilenstein erstellt: {tpl.identifier} "{label}" v{next_version}')
        return JsonResponse({
            'id':      ms.pk,
            'version': ms.version,
            'label':   ms.milestone_label,
        }, status=201)


@method_decorator(csrf_exempt, name='dispatch')
class MilestoneRestoreAPI(LoginRequiredMixin, View):
    """
    POST /api/templates/<pk>/milestones/<mid>/restore/
         Spielt einen Meilenstein-Stand zurueck.
         Der aktuelle Stand wird dabei als Auto-Version gesichert.
    """

    def post(self, request, pk, mid):
        tpl = get_object_or_404(EmailTemplate, pk=pk)
        ms  = get_object_or_404(
            EmailTemplateVersion,
            pk=mid,
            template=tpl,
            is_milestone=True
        )

        # Aktuellen Stand zuerst als Auto-Version sichern
        last = EmailTemplateVersion.objects.filter(
            template=tpl
        ).order_by('-version').first()
        auto_version = (last.version + 1) if last else 1

        EmailTemplateVersion.objects.create(
            template     = tpl,
            version      = auto_version,
            subject      = tpl.subject,
            html_body    = tpl.html_body,
            text_body    = tpl.text_body,
            variables    = tpl.variables,
            sender_mode  = tpl.sender_mode,
            change_note  = 'Auto-Version vor Meilenstein-Wiederherstellung',
            is_milestone = False,
            created_by   = request.user,
        )

        # Meilenstein-Stand zurueckspielen
        tpl.subject      = ms.subject
        tpl.html_body    = ms.html_body
        tpl.text_body    = ms.text_body
        tpl.variables    = ms.variables
        tpl.sender_mode  = ms.sender_mode
        tpl.active_version = auto_version
        tpl.save()

        log.info(
            f'Meilenstein zurueckgespielt: {tpl.identifier} '
            f'"{ms.milestone_label}" von {request.user}'
        )
        return JsonResponse({
            'success':       True,
            'restored_from': ms.milestone_label,
            'auto_saved_as': auto_version,
        })
