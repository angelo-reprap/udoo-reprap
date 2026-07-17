"""
ABpE Doc Studio — Portal Views (HTML) + Download
"""
import logging
import os
from django.contrib.auth.decorators import login_required
from django.shortcuts                import render
from django.http                     import FileResponse, Http404, JsonResponse
from django.utils                    import timezone

from .models import DocTemplate, DocLog, DocScope, DocStatus

log = logging.getLogger('abpe_doc_studio.views')


def _base_context(request, active_subpage='index'):
    lang = request.session.get('language', 'de')
    return {
        'active_module':  'doc_studio',
        'active_subpage': active_subpage,
        'current_lang':   lang,
        'active_tab':     active_subpage,
        'is_admin':       request.user.is_staff,
    }


@login_required
def index(request):
    ctx = _base_context(request, 'index')
    ctx['stats'] = {
        'total':    DocTemplate.objects.filter(status=DocStatus.ACTIVE).count(),
        'contract': DocTemplate.objects.filter(scope=DocScope.CONTRACT, status=DocStatus.ACTIVE).count(),
        'invoice':  DocTemplate.objects.filter(scope=DocScope.INVOICE,  status=DocStatus.ACTIVE).count(),
        'draft':    DocTemplate.objects.filter(status=DocStatus.DRAFT).count(),
    }
    ctx['scopes'] = DocScope.choices
    return render(request, 'abpe_ui/modules/doc_studio/index.html', ctx)


@login_required
def studio(request):
    ctx = _base_context(request, 'studio')
    template_pk = request.GET.get('template')
    if template_pk:
        try:
            ctx['active_template'] = DocTemplate.objects.select_related(
                'layout', 'style_kit'
            ).prefetch_related('template_blocks__block').get(pk=template_pk)
        except DocTemplate.DoesNotExist:
            ctx['active_template'] = None
    return render(request, 'abpe_ui/modules/doc_studio/studio.html', ctx)


@login_required
def log(request):
    ctx = _base_context(request, 'log')
    today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    ctx['stats'] = {
        'today_total':  DocLog.objects.filter(generated_at__gte=today).count(),
        'today_ok':     DocLog.objects.filter(generated_at__gte=today, status='OK').count(),
        'today_failed': DocLog.objects.filter(generated_at__gte=today, status='FAILED').count(),
    }
    return render(request, 'abpe_ui/modules/doc_studio/log.html', ctx)


@login_required
def config(request):
    from .models import PageLayout, StyleKit, ContentBlock
    ctx = _base_context(request, 'config')
    ctx['config_stats'] = {
        'layouts': PageLayout.objects.filter(is_active=True).count(),
        'styles':  StyleKit.objects.filter(is_active=True).count(),
        'blocks':  ContentBlock.objects.filter(is_active=True).count(),
    }
    return render(request, 'abpe_ui/modules/doc_studio/config.html', ctx)


@login_required
def invoices(request):
    from .models import InvoiceRecord
    from django.db.models import Sum
    ctx = _base_context(request, 'invoices')
    this_month = timezone.now().replace(day=1, hour=0, minute=0, second=0)
    ctx['invoice_stats'] = {
        'this_month_count': InvoiceRecord.objects.filter(invoice_date__gte=this_month).count(),
        'this_month_netto': InvoiceRecord.objects.filter(
            invoice_date__gte=this_month, status='sent'
        ).aggregate(total=Sum('netto_euro'))['total'] or 0,
        'open_count': InvoiceRecord.objects.filter(status__in=['draft', 'sent']).count(),
    }
    return render(request, 'abpe_ui/modules/doc_studio/invoices.html', ctx)


# ── Download-View ─────────────────────────────────────────────────────────────

@login_required
def download_doc(request, log_id):
    """
    Liefert eine generierte DOCX- oder PDF-Datei zum Download.
    GET /doc-studio/download/<log_id>/?type=docx  (oder pdf)
    """
    try:
        import uuid
        doc_log = DocLog.objects.get(log_id=uuid.UUID(log_id))
    except (DocLog.DoesNotExist, ValueError):
        raise Http404('Dokument nicht gefunden')

    file_type = request.GET.get('type', 'docx').lower()

    if file_type == 'pdf':
        file_path = doc_log.file_path_pdf
        content_type = 'application/pdf'
        ext = '.pdf'
    else:
        file_path = doc_log.file_path_docx
        content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        ext = '.docx'

    if not file_path or not os.path.exists(file_path):
        raise Http404(f'Datei nicht gefunden: {file_path}')

    filename = os.path.basename(file_path)
    response = FileResponse(
        open(file_path, 'rb'),
        content_type=content_type,
        as_attachment=True,
        filename=filename,
    )
    return response


# ── API: Fixtures neu laden ────────────────────────────────────────────────────

@login_required
def api_reload_fixtures(request):
    """POST /doc-studio/api/fixtures/reload/ — nur für Admins."""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Nur für Admins'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        import sys, os, importlib.util
        from django.conf import settings
        fixtures_path = os.path.join(
            settings.BASE_DIR, 'apps', 'abpe_doc_studio', 'bin', 'init_fixtures.py'
        )
        spec   = importlib.util.spec_from_file_location('init_fixtures', fixtures_path)
        module = importlib.util.module_from_spec(spec)
        sys.argv = ['init_fixtures.py']
        spec.loader.exec_module(module)

        from io import StringIO
        import contextlib
        buf = StringIO()
        with contextlib.redirect_stdout(buf):
            module.main()
        output = buf.getvalue()

        from .models import DocTemplate
        count = DocTemplate.objects.filter(status='ACTIVE').count()
        return JsonResponse({'success': True, 'output': output, 'active_templates': count})
    except Exception as e:
        log.error(f'Fixtures reload Fehler: {e}')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def download_doc(request, log_id):
    import os, uuid
    from django.http import FileResponse, Http404
    from .models import DocLog
    try:
        doc_log = DocLog.objects.get(log_id=uuid.UUID(log_id))
    except (DocLog.DoesNotExist, ValueError):
        raise Http404('Dokument nicht gefunden')
    file_type = request.GET.get('type', 'docx').lower()
    if file_type == 'pdf':
        file_path = doc_log.file_path_pdf
        content_type = 'application/pdf'
    else:
        file_path = doc_log.file_path_docx
        content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    if not file_path or not os.path.exists(file_path):
        raise Http404(f'Datei nicht gefunden: {file_path}')
    return FileResponse(
        open(file_path, 'rb'),
        content_type=content_type,
        as_attachment=True,
        filename=os.path.basename(file_path),
    )


@login_required
def api_reload_fixtures(request):
    from django.http import JsonResponse
    if not request.user.is_staff:
        return JsonResponse({'error': 'Nur fuer Admins'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        import sys, os, importlib.util
        from django.conf import settings as dj_settings
        fixtures_path = os.path.join(
            dj_settings.BASE_DIR, 'apps', 'abpe_doc_studio', 'bin', 'init_fixtures.py'
        )
        spec = importlib.util.spec_from_file_location('init_fixtures', fixtures_path)
        module = importlib.util.module_from_spec(spec)
        sys.argv = ['init_fixtures.py']
        spec.loader.exec_module(module)
        from io import StringIO
        import contextlib
        buf = StringIO()
        with contextlib.redirect_stdout(buf):
            module.main()
        from .models import DocTemplate
        return JsonResponse({'success': True, 'active_templates': DocTemplate.objects.filter(status='ACTIVE').count()})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
