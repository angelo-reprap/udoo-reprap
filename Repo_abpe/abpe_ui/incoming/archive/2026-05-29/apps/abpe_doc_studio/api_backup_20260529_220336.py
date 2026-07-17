"""
ABpE Doc Studio — REST API + Python-API

REST API: HTTP-Endpoints für das Portal-Frontend
Python-API: DocStudio-Klasse für andere Django-Apps

Nutzung aus anderen Apps:
    from apps.abpe_doc_studio.api import DocStudio

    # Synchron generieren + speichern
    DocStudio.generate(
        template    = 'sub_dienstvertrag',
        context_ref = 'ANF-2026-0042',
        variables   = {'an_firma': 'ACME GmbH', 'stundensatz': 95.00},
        engine      = 'BOTH',
        user        = request.user,
    )

    # Async (Celery)
    DocStudio.generate(
        template       = 'rechnung_zeitaufwand',
        context_ref    = '26/04/0123',
        variables      = {...},
        async_generate = True,
        send_email_to  = ['kunde@example.de'],
        email_template = 'rechnung_versand',
    )
"""
import json
import logging
from datetime import timedelta

from django.http                   import JsonResponse, FileResponse
from django.views                  import View
from django.views.decorators.csrf  import csrf_exempt
from django.utils.decorators       import method_decorator
from django.contrib.auth.mixins    import LoginRequiredMixin
from django.shortcuts              import get_object_or_404
from django.utils                  import timezone
from django.db.models              import Q

from .services.assembly_preview import DocPreview
from .models import (
    DocTemplate, DocTemplateBlock, DocTemplateVersion,
    PageLayout, StyleKit, StyleDefinition, ContentBlock,
    InvoiceRecord, DocLog, DocQueue,
    DocStatus, DocScope, DocEngine, LogStatus, QueueStatus,
)

log = logging.getLogger('abpe_doc_studio.api')


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _json_body(request) -> dict:
    try:
        return json.loads(request.body)
    except Exception:
        return {}


def _template_to_dict(tpl: DocTemplate) -> dict:
    return {
        'id':             tpl.pk,
        'identifier':     tpl.identifier,
        'name':           tpl.name,
        'description':    tpl.description,
        'scope':          tpl.scope,
        'engine':         tpl.engine,
        'status':         tpl.status,
        'layout':         tpl.layout.identifier if tpl.layout_id else None,
        'layout_css': {
            'page_width_cm':    float(tpl.layout.page_width_cm)    if tpl.layout_id else 21.0,
            'page_height_cm':   float(tpl.layout.page_height_cm)   if tpl.layout_id else 29.7,
            'margin_top_cm':    float(tpl.layout.margin_top_cm)    if tpl.layout_id else 4.2,
            'margin_bottom_cm': float(tpl.layout.margin_bottom_cm) if tpl.layout_id else 5.2,
            'margin_left_cm':   float(tpl.layout.margin_left_cm)   if tpl.layout_id else 3.0,
            'margin_right_cm':  float(tpl.layout.margin_right_cm)  if tpl.layout_id else 3.0,
        } if tpl.layout_id else None,
        'style_kit':      tpl.style_kit.identifier if tpl.style_kit_id else None,
        'active_version': tpl.active_version,
        'variables':      tpl.variables,
        'usage_count':    tpl.usage_count,
        'last_used_at':   tpl.last_used_at.isoformat() if tpl.last_used_at else None,
        'created_at':     tpl.created_at.isoformat(),
        'updated_at':     tpl.updated_at.isoformat(),
    }


def _log_to_dict(entry: DocLog) -> dict:
    return {
        'log_id':          str(entry.log_id),
        'template':        entry.template.identifier if entry.template else None,
        'context_ref':     entry.context_ref,
        'scope':           entry.scope,
        'engine_used':     entry.engine_used,
        'status':          entry.status,
        'file_path_docx':  entry.file_path_docx,
        'file_path_pdf':   entry.file_path_pdf,
        'file_size_bytes': entry.file_size_bytes,
        'sent_via_email':  entry.sent_via_email,
        'error_message':   entry.error_message,
        'generated_at':    entry.generated_at.isoformat(),
    }


# ── Templates ─────────────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class TemplateListCreateAPI(LoginRequiredMixin, View):

    def get(self, request):
        scope  = request.GET.get('scope', '')
        status = request.GET.get('status', '')
        search = request.GET.get('q', '')

        qs = DocTemplate.objects.select_related('layout', 'style_kit')
        if scope:
            qs = qs.filter(scope=scope)
        if status:
            qs = qs.filter(status=status)
        if search:
            qs = qs.filter(
                Q(name__icontains=search) | Q(identifier__icontains=search)
            )
        return JsonResponse({
            'templates': [_template_to_dict(t) for t in qs.order_by('scope', 'name')],
            'total':     qs.count(),
        })

    def post(self, request):
        data     = _json_body(request)
        required = ['identifier', 'name', 'layout', 'style_kit']
        missing  = [f for f in required if not data.get(f)]
        if missing:
            return JsonResponse({'error': f'Pflichtfelder fehlen: {missing}'}, status=400)

        if DocTemplate.objects.filter(identifier=data['identifier']).exists():
            return JsonResponse(
                {'error': f"Identifier '{data['identifier']}' bereits vorhanden"},
                status=400
            )

        layout = PageLayout.objects.filter(identifier=data['layout']).first()
        if not layout:
            return JsonResponse(
                {'error': f"Layout '{data['layout']}' nicht gefunden"}, status=404
            )

        style_kit = StyleKit.objects.filter(identifier=data['style_kit']).first()
        if not style_kit:
            return JsonResponse(
                {'error': f"StyleKit '{data['style_kit']}' nicht gefunden"}, status=404
            )

        tpl = DocTemplate.objects.create(
            identifier  = data['identifier'],
            name        = data['name'],
            description = data.get('description', ''),
            scope       = data.get('scope', DocScope.GENERAL),
            engine      = data.get('engine', DocEngine.BOTH),
            status      = data.get('status', DocStatus.DRAFT),
            layout      = layout,
            style_kit   = style_kit,
            variables   = data.get('variables', []),
            created_by  = request.user,
        )
        log.info(f'Template erstellt: {tpl.identifier} von {request.user}')
        return JsonResponse({'template': _template_to_dict(tpl)}, status=201)


@method_decorator(csrf_exempt, name='dispatch')
class TemplateDetailAPI(LoginRequiredMixin, View):

    def get(self, request, pk):
        tpl  = get_object_or_404(DocTemplate, pk=pk)
        data = _template_to_dict(tpl)
        data['blocks'] = list(
            DocTemplateBlock.objects
            .filter(template=tpl)
            .order_by('slot', 'order')
            .values('id', 'slot', 'order', 'block__identifier', 'block__name',
                    'block__block_type', 'block__content', 'style_override',
                    'content_override', 'conditional', 'page_break_before')
        )
        return JsonResponse({'template': data})

    def put(self, request, pk):
        tpl  = get_object_or_404(DocTemplate, pk=pk)
        data = _json_body(request)

        updatable = ['name', 'description', 'scope', 'engine',
                     'status', 'variables']
        for field in updatable:
            if field in data:
                setattr(tpl, field, data[field])

        if data.get('layout'):
            layout = PageLayout.objects.filter(identifier=data['layout']).first()
            if layout:
                tpl.layout = layout

        if data.get('style_kit'):
            sk = StyleKit.objects.filter(identifier=data['style_kit']).first()
            if sk:
                tpl.style_kit = sk

        tpl.save()
        log.info(f'Template aktualisiert: {tpl.identifier}')
        return JsonResponse({'template': _template_to_dict(tpl)})

    def delete(self, request, pk):
        tpl = get_object_or_404(DocTemplate, pk=pk)
        tpl.status = DocStatus.ARCHIVE
        tpl.save(update_fields=['status'])
        return JsonResponse({'success': True, 'archived': tpl.identifier})


@method_decorator(csrf_exempt, name='dispatch')
class TemplateDuplicateAPI(LoginRequiredMixin, View):

    def post(self, request, pk):
        src      = get_object_or_404(DocTemplate, pk=pk)
        data     = _json_body(request)
        new_id   = data.get('identifier', f'{src.identifier}_copy')
        new_name = data.get('name',       f'{src.name} (Kopie)')

        if DocTemplate.objects.filter(identifier=new_id).exists():
            return JsonResponse(
                {'error': f"Identifier '{new_id}' bereits vorhanden"}, status=400
            )

        dup = DocTemplate.objects.create(
            identifier  = new_id,
            name        = new_name,
            description = src.description,
            scope       = data.get('scope', src.scope),
            engine      = src.engine,
            status      = DocStatus.DRAFT,
            layout      = src.layout,
            style_kit   = src.style_kit,
            variables   = src.variables,
            created_by  = request.user,
        )
        for tb in DocTemplateBlock.objects.filter(
            template=src
        ).order_by('slot', 'order'):
            DocTemplateBlock.objects.create(
                template          = dup,
                block             = tb.block,
                slot              = tb.slot,
                order             = tb.order,
                style_override    = tb.style_override,
                content_override  = tb.content_override,
                conditional       = tb.conditional,
                page_break_before = tb.page_break_before,
            )
        log.info(f'Template dupliziert: {src.identifier} → {dup.identifier}')
        return JsonResponse({'template': _template_to_dict(dup)}, status=201)


class TemplateVersionListAPI(LoginRequiredMixin, View):

    def get(self, request, pk):
        tpl      = get_object_or_404(DocTemplate, pk=pk)
        versions = DocTemplateVersion.objects.filter(
            template=tpl
        ).order_by('-version').values(
            'version', 'change_note', 'created_at', 'created_by__username'
        )
        return JsonResponse({
            'template_id':    pk,
            'active_version': tpl.active_version,
            'versions':       list(versions),
        })


@method_decorator(csrf_exempt, name='dispatch')
class TemplatePreviewAPI(LoginRequiredMixin, View):
    """
    Rendert eine Vorschau.
    format=html  → JsonResponse mit html (via DocPreview)
    format=docx  → FileResponse mit .docx (via DocAssembler)
    format=pdf   → FileResponse mit .pdf  (via DocAssembler + LibreOffice)
    """

    def post(self, request, pk):
        tpl       = get_object_or_404(DocTemplate, pk=pk)
        data      = _json_body(request)
        variables = data.get('variables', {})
        fmt       = data.get('format', 'html')

        try:
            if fmt == 'html':
                # HTML-Preview: DocPreview — kein python-docx
                html = DocPreview().preview_html(tpl, variables)
                return JsonResponse({'html': html, 'template': tpl.identifier})

            # DOCX / PDF: DocAssembler
            from .services.assembler import DocAssembler
            assembler = DocAssembler()

            if fmt == 'docx':
                buf = assembler.render_to_bytes(tpl, variables, engine='DOCX')
                from django.http import HttpResponse
                resp = HttpResponse(
                    buf,
                    content_type='application/vnd.openxmlformats-officedocument'
                                 '.wordprocessingml.document'
                )
                resp['Content-Disposition'] = (
                    f'attachment; filename="{tpl.identifier}_preview.docx"'
                )
                return resp

            if fmt == 'pdf':
                buf = assembler.render_to_bytes(tpl, variables, engine='PDF')
                from django.http import HttpResponse
                resp = HttpResponse(buf, content_type='application/pdf')
                resp['Content-Disposition'] = (
                    f'attachment; filename="{tpl.identifier}_preview.pdf"'
                )
                return resp

            return JsonResponse(
                {'error': f'Unbekanntes Format: {fmt}'}, status=400
            )

        except Exception as e:
            log.error(f'Preview fehlgeschlagen: {e}')
            return JsonResponse({'error': str(e)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class TemplateGenerateAPI(LoginRequiredMixin, View):

    def post(self, request, pk):
        tpl  = get_object_or_404(DocTemplate, pk=pk)
        data = _json_body(request)

        try:
            from .services.assembler import DocAssembler
            result = DocAssembler().generate(
                template_identifier = tpl.identifier,
                variables           = data.get('variables', {}),
                context_ref         = data.get('context_ref', ''),
                scope               = tpl.scope,
                engine              = data.get('engine', tpl.engine),
                user                = request.user,
            )
            result.pop('doc_log', None)
            return JsonResponse({'success': True, **result})
        except Exception as e:
            log.error(f'Generate fehlgeschlagen: {e}')
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ── Generierung (direkt via identifier) ──────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class GenerateAPI(LoginRequiredMixin, View):

    def post(self, request):
        data       = _json_body(request)
        identifier = data.get('template')
        if not identifier:
            return JsonResponse({'error': 'template Pflichtfeld'}, status=400)

        tpl = DocTemplate.objects.filter(
            identifier=identifier, status=DocStatus.ACTIVE
        ).first()
        if not tpl:
            return JsonResponse(
                {'error': f"Template '{identifier}' nicht gefunden oder inaktiv"},
                status=404
            )

        try:
            from .services.assembler import DocAssembler
            result = DocAssembler().generate(
                template_identifier = identifier,
                variables           = data.get('variables', {}),
                context_ref         = data.get('context_ref', ''),
                scope               = tpl.scope,
                engine              = data.get('engine', tpl.engine),
                user                = request.user,
            )
            result.pop('doc_log', None)
            return JsonResponse({'success': True, **result})
        except Exception as e:
            log.error(f'GenerateAPI Fehler: {e}')
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class GenerateAsyncAPI(LoginRequiredMixin, View):

    def post(self, request):
        data       = _json_body(request)
        identifier = data.get('template')
        if not identifier:
            return JsonResponse({'error': 'template Pflichtfeld'}, status=400)

        tpl = DocTemplate.objects.filter(
            identifier=identifier, status=DocStatus.ACTIVE
        ).first()
        if not tpl:
            return JsonResponse(
                {'error': f"Template '{identifier}' nicht gefunden"}, status=404
            )

        item = DocQueue.objects.create(
            template       = tpl,
            engine         = data.get('engine', tpl.engine),
            variables      = data.get('variables', {}),
            context_ref    = data.get('context_ref', ''),
            scope          = tpl.scope,
            send_email_to  = data.get('send_email_to', []),
            email_template = data.get('email_template', ''),
            user_id        = request.user.pk,
        )

        from .tasks import generate_queued_doc
        task = generate_queued_doc.delay(str(item.queue_id))
        item.celery_task_id = task.id
        item.save(update_fields=['celery_task_id'])

        return JsonResponse({
            'success':  True,
            'queue_id': str(item.queue_id),
            'task_id':  task.id,
        })


# ── Layouts + Styles + Blöcke ─────────────────────────────────────────────────

class LayoutListAPI(LoginRequiredMixin, View):

    def get(self, request):
        layouts = PageLayout.objects.filter(is_active=True).values(
            'id', 'identifier', 'name',
            'margin_left_cm', 'margin_right_cm',
            'margin_top_cm', 'margin_bottom_cm',
            'columns', 'show_page_numbers',
        )
        return JsonResponse({'layouts': list(layouts)})


class StyleKitListAPI(LoginRequiredMixin, View):

    def get(self, request):
        kits   = StyleKit.objects.filter(is_active=True).prefetch_related('definitions')
        result = []
        for kit in kits:
            result.append({
                'id':         kit.pk,
                'identifier': kit.identifier,
                'name':       kit.name,
                'is_default': kit.is_default,
                'styles':     list(kit.definitions.values(
                    'style_key', 'style_type', 'name',
                    'font_family', 'font_size_pt', 'bold', 'italic',
                    'color_hex', 'border_bottom', 'bg_color_hex'
                )),
            })
        return JsonResponse({'style_kits': result})


@method_decorator(csrf_exempt, name='dispatch')
class BlockListCreateAPI(LoginRequiredMixin, View):

    def get(self, request):
        block_type = request.GET.get('type', '')
        search     = request.GET.get('q', '')
        qs = ContentBlock.objects.filter(is_active=True).select_related('style_kit')
        if block_type:
            qs = qs.filter(block_type=block_type)
        if search:
            qs = qs.filter(
                Q(name__icontains=search) | Q(identifier__icontains=search)
            )
        grouped = {}
        for b in qs.order_by('block_type', 'name'):
            t = b.block_type
            grouped.setdefault(t, []).append({
                'id':         b.pk,
                'identifier': b.identifier,
                'name':       b.name,
                'block_type': b.block_type,
                'style_key':  b.style_key,
                'repeatable': b.repeatable,
                'syntax':     f'{{{{block:{b.identifier}}}}}',
            })
        return JsonResponse({
            'blocks': grouped,
            'types':  ContentBlock._meta.get_field('block_type').choices,
        })

    def post(self, request):
        data     = _json_body(request)
        required = ['identifier', 'name', 'block_type', 'style_kit']
        missing  = [f for f in required if not data.get(f)]
        if missing:
            return JsonResponse({'error': f'Pflichtfelder: {missing}'}, status=400)

        sk = StyleKit.objects.filter(identifier=data['style_kit']).first()
        if not sk:
            return JsonResponse({'error': 'StyleKit nicht gefunden'}, status=404)

        block = ContentBlock.objects.create(
            identifier         = data['identifier'],
            name               = data['name'],
            block_type         = data['block_type'],
            style_kit          = sk,
            style_key          = data.get('style_key', ''),
            content            = data.get('content', ''),
            columns            = data.get('columns', []),
            expected_variables = data.get('expected_variables', []),
            repeatable         = data.get('repeatable', False),
            conditional        = data.get('conditional', ''),
            created_by         = request.user,
        )
        return JsonResponse(
            {'id': block.pk, 'identifier': block.identifier}, status=201
        )


@method_decorator(csrf_exempt, name='dispatch')
class BlockDetailAPI(LoginRequiredMixin, View):

    def get(self, request, pk):
        b = get_object_or_404(ContentBlock, pk=pk)
        return JsonResponse({
            'id': b.pk, 'identifier': b.identifier, 'name': b.name,
            'block_type': b.block_type, 'style_key': b.style_key,
            'content': b.content, 'columns': b.columns,
            'expected_variables': b.expected_variables,
            'repeatable': b.repeatable, 'conditional': b.conditional,
        })

    def put(self, request, pk):
        b    = get_object_or_404(ContentBlock, pk=pk)
        data = _json_body(request)
        for f in ['name', 'content', 'style_key', 'columns',
                  'expected_variables', 'repeatable', 'conditional', 'is_active']:
            if f in data:
                setattr(b, f, data[f])
        b.save()
        return JsonResponse({'success': True})

    def delete(self, request, pk):
        b = get_object_or_404(ContentBlock, pk=pk)
        b.is_active = False
        b.save(update_fields=['is_active'])
        return JsonResponse({'success': True})


# ── Rechnungen ────────────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class InvoiceListCreateAPI(LoginRequiredMixin, View):

    def get(self, request):
        status = request.GET.get('status', '')
        itype  = request.GET.get('type', '')
        month  = request.GET.get('month', '')
        search = request.GET.get('q', '')

        qs = InvoiceRecord.objects.all()
        if status:
            qs = qs.filter(status=status)
        if itype:
            qs = qs.filter(invoice_type=itype)
        if month:
            qs = qs.filter(billing_month__icontains=month)
        if search:
            qs = qs.filter(
                Q(invoice_number__icontains=search) |
                Q(customer_name__icontains=search)  |
                Q(consultant_name__icontains=search)
            )

        return JsonResponse({
            'invoices': [{
                'id':              str(inv.id),
                'invoice_number':  inv.invoice_number,
                'invoice_type':    inv.invoice_type,
                'status':          inv.status,
                'customer_name':   inv.customer_name,
                'consultant_name': inv.consultant_name,
                'invoice_date':    inv.invoice_date.isoformat(),
                'billing_month':   inv.billing_month,
                'netto_euro':      float(inv.netto_euro),
                'brutto_euro':     float(inv.brutto_euro),
                'has_doc':         bool(inv.doc_log_id),
            } for inv in qs.order_by('-invoice_date')[:200]],
            'total': qs.count(),
        })

    def post(self, request):
        data     = _json_body(request)
        required = ['invoice_type', 'invoice_date', 'customer_name', 'positions']
        missing  = [f for f in required if not data.get(f)]
        if missing:
            return JsonResponse({'error': f'Pflichtfelder: {missing}'}, status=400)

        inv = InvoiceRecord(
            invoice_type      = data['invoice_type'],
            invoice_date      = data['invoice_date'],
            customer_name     = data.get('customer_name', ''),
            customer_address  = data.get('customer_address', ''),
            consultant_name   = data.get('consultant_name', ''),
            subject           = data.get('subject', ''),
            billing_month     = data.get('billing_month', ''),
            payment_term_days = data.get('payment_term_days', 30),
            mwst_satz         = data.get('mwst_satz', 19.0),
            positions         = data['positions'],
            created_by        = request.user,
        )
        inv.save()
        return JsonResponse(
            {'id': str(inv.id), 'invoice_number': inv.invoice_number}, status=201
        )


@method_decorator(csrf_exempt, name='dispatch')
class InvoiceDetailAPI(LoginRequiredMixin, View):

    def get(self, request, pk):
        inv = get_object_or_404(InvoiceRecord, pk=pk)
        return JsonResponse({
            'id':               str(inv.id),
            'invoice_number':   inv.invoice_number,
            'invoice_type':     inv.invoice_type,
            'status':           inv.status,
            'customer_name':    inv.customer_name,
            'customer_address': inv.customer_address,
            'consultant_name':  inv.consultant_name,
            'invoice_date':     inv.invoice_date.isoformat(),
            'billing_month':    inv.billing_month,
            'subject':          inv.subject,
            'payment_term_days': inv.payment_term_days,
            'positions':        inv.positions,
            'netto_euro':       float(inv.netto_euro),
            'mwst_satz':        float(inv.mwst_satz),
            'mwst_euro':        float(inv.mwst_euro),
            'brutto_euro':      float(inv.brutto_euro),
            'has_doc':          bool(inv.doc_log_id),
        })

    def put(self, request, pk):
        inv  = get_object_or_404(InvoiceRecord, pk=pk)
        data = _json_body(request)
        for f in ['status', 'customer_name', 'customer_address',
                  'consultant_name', 'subject', 'billing_month',
                  'payment_term_days', 'mwst_satz', 'positions']:
            if f in data:
                setattr(inv, f, data[f])
        inv.save()
        return JsonResponse({
            'success':    True,
            'netto_euro': float(inv.netto_euro),
            'brutto_euro':float(inv.brutto_euro),
        })


@method_decorator(csrf_exempt, name='dispatch')
class InvoiceGenerateAPI(LoginRequiredMixin, View):

    def post(self, request, pk):
        inv  = get_object_or_404(InvoiceRecord, pk=pk)
        data = _json_body(request)

        template_map = {
            'zeitaufwand':   'rechnung_zeitaufwand',
            'arbeitspakete': 'rechnung_arbeitspakete',
            'festpreis':     'rechnung_festpreis',
        }
        template_id = data.get('template') or template_map.get(inv.invoice_type)
        if not template_id:
            return JsonResponse({'error': 'Kein Template zugeordnet'}, status=400)

        def _fmt(v):
            return f'{v:,.2f}'.replace(',','X').replace('.', ',').replace('X','.')

        variables = {
            'rg_nummer':          inv.invoice_number,
            'rg_datum':           inv.invoice_date.strftime('%-d. %B %Y'),
            'empfaenger_firma':   inv.customer_name,
            'empfaenger_adresse': inv.customer_address,
            'betreff':            inv.subject,
            'abrechnungsmonat':   inv.billing_month,
            'positionen':         inv.positions,
            'summe_netto':        _fmt(inv.netto_euro),
            'mwst_satz':          f'{inv.mwst_satz:.0f}',
            'mwst_euro':          _fmt(inv.mwst_euro),
            'gesamtbetrag':       _fmt(inv.brutto_euro),
            'zahlungsziel_tage':  str(inv.payment_term_days),
        }

        try:
            from .services.assembler import DocAssembler
            result = DocAssembler().generate(
                template_identifier = template_id,
                variables           = variables,
                context_ref         = inv.invoice_number,
                scope               = 'invoice',
                engine              = data.get('engine', 'BOTH'),
                user                = request.user,
            )
            if result.get('success') and result.get('log_id'):
                doc_log = DocLog.objects.filter(
                    log_id=result['log_id']
                ).first()
                if doc_log:
                    inv.doc_log = doc_log
                    inv.save(update_fields=['doc_log'])

            result.pop('doc_log', None)
            return JsonResponse({'success': True, **result})
        except Exception as e:
            log.error(f'Invoice Generate fehlgeschlagen: {e}')
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ── Log + Stats + Queue ───────────────────────────────────────────────────────

class LogListAPI(LoginRequiredMixin, View):

    def get(self, request):
        days   = int(request.GET.get('days', 7))
        status = request.GET.get('status', '')
        search = request.GET.get('q', '')
        since  = timezone.now() - timedelta(days=days)

        qs = DocLog.objects.select_related('template').filter(
            generated_at__gte=since
        )
        if status:
            qs = qs.filter(status=status)
        if search:
            qs = qs.filter(
                Q(context_ref__icontains=search) |
                Q(template__identifier__icontains=search)
            )
        return JsonResponse({
            'logs':  [_log_to_dict(e) for e in qs.order_by('-generated_at')[:200]],
            'total': qs.count(),
        })


class LogStatsAPI(LoginRequiredMixin, View):

    def get(self, request):
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        week  = timezone.now() - timedelta(days=7)
        return JsonResponse({
            'today': {
                'total':  DocLog.objects.filter(generated_at__gte=today).count(),
                'ok':     DocLog.objects.filter(generated_at__gte=today, status='OK').count(),
                'failed': DocLog.objects.filter(generated_at__gte=today, status='FAILED').count(),
            },
            'week': {
                'total':  DocLog.objects.filter(generated_at__gte=week).count(),
                'ok':     DocLog.objects.filter(generated_at__gte=week, status='OK').count(),
                'failed': DocLog.objects.filter(generated_at__gte=week, status='FAILED').count(),
            },
        })


class QueueListAPI(LoginRequiredMixin, View):

    def get(self, request):
        qs = DocQueue.objects.select_related('template').order_by('-created_at')[:100]
        return JsonResponse({
            'queue': [{
                'queue_id':     str(q.queue_id),
                'template':     q.template.identifier,
                'engine':       q.engine,
                'context_ref':  q.context_ref,
                'status':       q.status,
                'retry_count':  q.retry_count,
                'created_at':   q.created_at.isoformat(),
                'processed_at': q.processed_at.isoformat() if q.processed_at else None,
            } for q in qs]
        })


@method_decorator(csrf_exempt, name='dispatch')
class QueueCancelAPI(LoginRequiredMixin, View):

    def post(self, request, queue_id):
        item = get_object_or_404(DocQueue, queue_id=queue_id)
        if item.status == 'PENDING':
            item.status = 'CANCELLED'
            item.save(update_fields=['status'])
            return JsonResponse({'success': True})
        return JsonResponse(
            {'error': f'Status {item.status} kann nicht abgebrochen werden'},
            status=400
        )


# ══════════════════════════════════════════════════════════════════════════════
# PYTHON API — für andere Django-Apps
# ══════════════════════════════════════════════════════════════════════════════

class DocStudio:
    """
    Zentrale Python-API für andere Django-Apps.

    Nutzung:
        from apps.abpe_doc_studio.api import DocStudio

        DocStudio.generate(
            template    = 'sub_dienstvertrag',
            context_ref = 'ANF-2026-0042',
            variables   = {'an_firma': 'ACME GmbH', 'stundensatz': 95.00},
            engine      = 'BOTH',
        )
    """

    @staticmethod
    def generate(template: str,
                 variables: dict = None,
                 context_ref: str = '',
                 scope: str = '',
                 engine: str = 'BOTH',
                 user=None,
                 async_generate: bool = False,
                 send_email_to: list = None,
                 email_template: str = '') -> dict:

        tpl = DocTemplate.objects.filter(
            identifier=template, status=DocStatus.ACTIVE
        ).first()

        if not tpl:
            log.error(f'DocStudio.generate: Template nicht gefunden: {template}')
            return {'success': False, 'error': f"Template '{template}' nicht gefunden"}

        variables = variables or {}

        if async_generate:
            item = DocQueue.objects.create(
                template       = tpl,
                engine         = engine,
                variables      = variables,
                context_ref    = context_ref,
                scope          = scope or tpl.scope,
                send_email_to  = send_email_to or [],
                email_template = email_template,
                user_id        = user.pk if user else None,
            )
            from .tasks import generate_queued_doc
            task = generate_queued_doc.delay(str(item.queue_id))
            item.celery_task_id = task.id
            item.save(update_fields=['celery_task_id'])
            return {
                'success':  True,
                'queue_id': str(item.queue_id),
                'task_id':  task.id,
            }

        from .services.assembler import DocAssembler
        return DocAssembler().generate(
            template_identifier = template,
            variables           = variables,
            context_ref         = context_ref,
            scope               = scope or tpl.scope,
            engine              = engine,
            user                = user,
        )

    @staticmethod
    def render_bytes(template: str, variables: dict = None,
                     engine: str = 'DOCX') -> bytes | None:
        tpl = DocTemplate.objects.filter(identifier=template).first()
        if not tpl:
            return None
        from .services.assembler import DocAssembler
        return DocAssembler().render_to_bytes(tpl, variables or {}, engine)

    @staticmethod
    def get_template(identifier: str) -> DocTemplate | None:
        return DocTemplate.objects.filter(
            identifier=identifier, status=DocStatus.ACTIVE
        ).first()


# ── Template-Block API ────────────────────────────────────────────────────────

class TemplateBlockReorderAPI(LoginRequiredMixin, View):
    """PUT /api/templates/<pk>/blocks/reorder/"""

    def put(self, request, pk):
        template = get_object_or_404(DocTemplate, pk=pk)
        data     = _json_body(request)
        updated  = 0
        for item in data.get('blocks', []):
            tb_pk = item.get('id')
            order = item.get('order')
            if tb_pk is None or order is None:
                continue
            try:
                tb = DocTemplateBlock.objects.get(pk=tb_pk, template=template)
                tb.order = order
                tb.save(update_fields=['order'])
                updated += 1
            except DocTemplateBlock.DoesNotExist:
                pass
        return JsonResponse({'success': True, 'updated': updated})


class TemplateBlockInlineUpdateAPI(LoginRequiredMixin, View):
    """GET/PUT /api/templates/<pk>/blocks/<tb_pk>/"""

    def get(self, request, pk, tb_pk):
        tb = get_object_or_404(DocTemplateBlock, pk=tb_pk, template__pk=pk)
        b  = tb.block
        return JsonResponse({
            'id': tb.pk, 'block_id': b.pk, 'name': b.name,
            'identifier': b.identifier, 'block_type': b.block_type,
            'content': b.content, 'style_key': b.style_key,
            'slot': tb.slot, 'order': tb.order,
        })

    def put(self, request, pk, tb_pk):
        tb      = get_object_or_404(DocTemplateBlock, pk=tb_pk, template__pk=pk)
        data    = _json_body(request)
        b       = tb.block
        changed = []
        if 'content' in data:
            b.content = data['content']
            changed.append('content')
        if 'name' in data:
            b.name = data['name']
            changed.append('name')
        if changed:
            b.save(update_fields=changed)
        return JsonResponse({
            'success':  True,
            'id':       tb.pk,
            'block_id': b.pk,
            'content':  b.content,
        })
