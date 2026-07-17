"""
ABpE Doc Studio — Portal Views (HTML)

Alle Views rendern Templates aus:
  apps/abpe_ui/templates/abpe_ui/modules/doc_studio/

Analog zum Email Studio: Views sind schlank,
die Logik liegt in der API (api.py) und den Services.
"""
import logging
from django.contrib.auth.decorators import login_required
from django.shortcuts                import render
from django.utils                    import timezone

from .models import DocTemplate, DocLog, DocScope, DocStatus

log = logging.getLogger('abpe_doc_studio.views')


def _base_context(request, active_subpage='index'):
    """Gemeinsamer Kontext für alle Doc Studio Views."""
    lang = request.session.get('language', 'de')
    return {
        'active_module':  'doc_studio',
        'active_subpage': active_subpage,
        'current_lang':   lang,
        'active_tab':     active_subpage,
    }


@login_required
def index(request):
    """
    Vorlagen-Liste — Übersicht aller DocTemplates.
    Gefiltert nach scope + status, analog Email Studio Index.
    """
    ctx = _base_context(request, 'index')

    # Schnell-Statistik für die Übersicht
    ctx['stats'] = {
        'total':    DocTemplate.objects.filter(status=DocStatus.ACTIVE).count(),
        'contract': DocTemplate.objects.filter(
            scope=DocScope.CONTRACT, status=DocStatus.ACTIVE).count(),
        'invoice':  DocTemplate.objects.filter(
            scope=DocScope.INVOICE, status=DocStatus.ACTIVE).count(),
        'draft':    DocTemplate.objects.filter(status=DocStatus.DRAFT).count(),
    }

    # Verfügbare Scopes für Filter-Dropdown
    ctx['scopes'] = DocScope.choices

    return render(request,
                  'abpe_ui/modules/doc_studio/index.html', ctx)


@login_required
def studio(request):
    """
    Studio / Editor — Template bearbeiten, Blöcke anordnen, Vorschau.
    Template-ID kommt per GET-Parameter (?template=<pk>).
    """
    ctx = _base_context(request, 'studio')

    template_pk = request.GET.get('template')
    if template_pk:
        try:
            ctx['active_template'] = DocTemplate.objects.select_related(
                'layout', 'style_kit'
            ).prefetch_related(
                'template_blocks__block'
            ).get(pk=template_pk)
        except DocTemplate.DoesNotExist:
            ctx['active_template'] = None

    return render(request,
                  'abpe_ui/modules/doc_studio/studio.html', ctx)


@login_required
def log(request):
    """
    Generierungs-Log — alle erzeugten Dokumente.
    Mit Tages-Statistik analog Email Studio Log.
    """
    ctx = _base_context(request, 'log')

    today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    ctx['stats'] = {
        'today_total':  DocLog.objects.filter(generated_at__gte=today).count(),
        'today_ok':     DocLog.objects.filter(
            generated_at__gte=today, status='OK').count(),
        'today_failed': DocLog.objects.filter(
            generated_at__gte=today, status='FAILED').count(),
    }

    return render(request,
                  'abpe_ui/modules/doc_studio/log.html', ctx)


@login_required
def config(request):
    """
    Konfiguration — PageLayouts, StyleKits, ContentBlöcke verwalten.
    Nur für Admins (Frontend-Check via is_admin).
    """
    from .models import PageLayout, StyleKit, ContentBlock

    ctx = _base_context(request, 'config')
    ctx['is_admin'] = request.user.is_staff

    # Schnell-Counts für Config-Übersicht
    ctx['config_stats'] = {
        'layouts': PageLayout.objects.filter(is_active=True).count(),
        'styles':  StyleKit.objects.filter(is_active=True).count(),
        'blocks':  ContentBlock.objects.filter(is_active=True).count(),
    }

    return render(request,
                  'abpe_ui/modules/doc_studio/config.html', ctx)


@login_required
def invoices(request):
    """
    Rechnungen — Liste und Erstellung.
    Verknüpft mit InvoiceRecord + Generierung.
    """
    from .models import InvoiceRecord

    ctx = _base_context(request, 'invoices')

    # Schnell-Statistik
    from django.db.models import Sum
    this_month = timezone.now().replace(day=1, hour=0, minute=0, second=0)
    ctx['invoice_stats'] = {
        'this_month_count': InvoiceRecord.objects.filter(
            invoice_date__gte=this_month).count(),
        'this_month_netto': InvoiceRecord.objects.filter(
            invoice_date__gte=this_month, status='sent'
        ).aggregate(total=Sum('netto_euro'))['total'] or 0,
        'open_count': InvoiceRecord.objects.filter(
            status__in=['draft', 'sent']).count(),
    }

    return render(request,
                  'abpe_ui/modules/doc_studio/invoices.html', ctx)
