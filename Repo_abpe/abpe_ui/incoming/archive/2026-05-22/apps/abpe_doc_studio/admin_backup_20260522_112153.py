"""
ABpE Doc Studio — Django Admin
"""
from django.contrib  import admin
from django.utils    import timezone
from django.utils.html import format_html
from .models import (
    PageLayout, StyleKit, StyleDefinition,
    ContentBlock, DocTemplate, DocTemplateBlock,
    DocTemplateVersion, InvoiceRecord, DocLog, DocQueue,
)


# ── PageLayout ────────────────────────────────────────────────────────────────

@admin.register(PageLayout)
class PageLayoutAdmin(admin.ModelAdmin):
    list_display  = ('identifier', 'name', 'margin_display',
                     'columns', 'show_page_numbers', 'is_active')
    list_filter   = ('is_active', 'columns')
    search_fields = ('identifier', 'name')
    readonly_fields = ('created_at', 'updated_at')

    def margin_display(self, obj):
        return f'L{obj.margin_left_cm}/R{obj.margin_right_cm} T{obj.margin_top_cm}/B{obj.margin_bottom_cm}'
    margin_display.short_description = 'Margins L/R T/B'


# ── StyleKit + StyleDefinition ────────────────────────────────────────────────

class StyleDefinitionInline(admin.TabularInline):
    model        = StyleDefinition
    extra        = 0
    fields       = ('style_key', 'style_type', 'name', 'font_family',
                    'font_size_pt', 'bold', 'italic', 'color_hex',
                    'border_bottom', 'border_bottom_color')
    ordering     = ('style_key',)


@admin.register(StyleKit)
class StyleKitAdmin(admin.ModelAdmin):
    list_display  = ('identifier', 'name', 'is_default', 'is_active',
                     'definitions_count')
    list_filter   = ('is_default', 'is_active')
    search_fields = ('identifier', 'name')
    inlines       = [StyleDefinitionInline]
    readonly_fields = ('created_at', 'updated_at')

    def definitions_count(self, obj):
        return obj.definitions.count()
    definitions_count.short_description = 'Styles'


@admin.register(StyleDefinition)
class StyleDefinitionAdmin(admin.ModelAdmin):
    list_display  = ('style_kit', 'style_key', 'style_type', 'font_family',
                     'font_size_pt', 'bold', 'color_preview')
    list_filter   = ('style_kit', 'style_type', 'bold')
    search_fields = ('style_key', 'name')

    def color_preview(self, obj):
        return format_html(
            '<span style="display:inline-block;width:16px;height:16px;'
            'background:#{};border:1px solid #ccc;vertical-align:middle;'
            'margin-right:6px;"></span>#{}'.format(
                obj.color_hex, obj.color_hex
            )
        )
    color_preview.short_description = 'Farbe'


# ── ContentBlock ──────────────────────────────────────────────────────────────

@admin.register(ContentBlock)
class ContentBlockAdmin(admin.ModelAdmin):
    list_display  = ('identifier', 'name', 'block_type', 'style_kit',
                     'style_key', 'repeatable', 'is_active')
    list_filter   = ('block_type', 'style_kit', 'is_active', 'repeatable')
    search_fields = ('identifier', 'name', 'content')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Basis', {
            'fields': ('identifier', 'name', 'block_type', 'description',
                       'is_active')
        }),
        ('Style', {
            'fields': ('style_kit', 'style_key')
        }),
        ('Inhalt', {
            'fields': ('content', 'columns', 'expected_variables')
        }),
        ('Logik', {
            'fields': ('repeatable', 'conditional'),
            'classes': ('collapse',)
        }),
        ('Meta', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# ── DocTemplate + Blöcke ──────────────────────────────────────────────────────

class DocTemplateBlockInline(admin.TabularInline):
    model   = DocTemplateBlock
    extra   = 0
    fields  = ('slot', 'order', 'block', 'conditional',
               'page_break_before', 'content_override')
    ordering = ('slot', 'order')


@admin.register(DocTemplate)
class DocTemplateAdmin(admin.ModelAdmin):
    list_display  = ('identifier', 'name', 'scope', 'engine', 'status',
                     'active_version', 'usage_count', 'last_used_at')
    list_filter   = ('scope', 'engine', 'status')
    search_fields = ('identifier', 'name')
    readonly_fields = ('active_version', 'usage_count', 'last_used_at',
                       'created_at', 'updated_at')
    inlines       = [DocTemplateBlockInline]
    actions       = ['activate_templates', 'archive_templates']
    fieldsets = (
        ('Basis', {
            'fields': ('identifier', 'name', 'description', 'scope',
                       'engine', 'status')
        }),
        ('Layout & Style', {
            'fields': ('layout', 'style_kit')
        }),
        ('Variablen & Sprachen', {
            'fields': ('variables', 'translation_languages'),
            'classes': ('collapse',)
        }),
        ('Statistik', {
            'fields': ('active_version', 'usage_count', 'last_used_at'),
            'classes': ('collapse',)
        }),
        ('Meta', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def activate_templates(self, request, queryset):
        updated = queryset.update(status='ACTIVE')
        self.message_user(request, f'{updated} Vorlage(n) aktiviert.')
    activate_templates.short_description = 'Ausgewählte Vorlagen aktivieren'

    def archive_templates(self, request, queryset):
        updated = queryset.update(status='ARCHIVE')
        self.message_user(request, f'{updated} Vorlage(n) archiviert.')
    archive_templates.short_description = 'Ausgewählte Vorlagen archivieren'


@admin.register(DocTemplateVersion)
class DocTemplateVersionAdmin(admin.ModelAdmin):
    list_display  = ('template', 'version', 'change_note',
                     'created_by', 'created_at')
    list_filter   = ('template',)
    readonly_fields = ('template', 'version', 'snapshot',
                       'created_by', 'created_at')


# ── InvoiceRecord ─────────────────────────────────────────────────────────────

@admin.register(InvoiceRecord)
class InvoiceRecordAdmin(admin.ModelAdmin):
    list_display  = ('invoice_number', 'invoice_type', 'customer_name',
                     'invoice_date', 'billing_month',
                     'netto_euro', 'brutto_euro', 'status', 'has_doc')
    list_filter   = ('invoice_type', 'status', 'mwst_satz')
    search_fields = ('invoice_number', 'customer_name', 'consultant_name')
    readonly_fields = ('invoice_number', 'netto_euro', 'mwst_euro',
                       'brutto_euro', 'created_at', 'updated_at')
    date_hierarchy = 'invoice_date'
    fieldsets = (
        ('Basis', {
            'fields': ('invoice_number', 'invoice_type', 'status',
                       'invoice_date', 'billing_month', 'subject')
        }),
        ('Empfänger', {
            'fields': ('project_consultant', 'consultant_name',
                       'customer_name', 'customer_address')
        }),
        ('Positionen', {
            'fields': ('positions',)
        }),
        ('Summen', {
            'fields': ('netto_euro', 'mwst_satz', 'mwst_euro',
                       'brutto_euro', 'payment_term_days')
        }),
        ('Dokument', {
            'fields': ('doc_log',),
            'classes': ('collapse',)
        }),
        ('Meta', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def has_doc(self, obj):
        if obj.doc_log_id:
            return format_html('<span style="color:green">✔</span>')
        return format_html('<span style="color:#ccc">–</span>')
    has_doc.short_description = 'Dok.'


# ── DocLog ────────────────────────────────────────────────────────────────────

@admin.register(DocLog)
class DocLogAdmin(admin.ModelAdmin):
    list_display  = ('log_id_short', 'template', 'context_ref', 'scope',
                     'engine_used', 'status', 'sent_via_email',
                     'file_size_display', 'generated_at')
    list_filter   = ('status', 'engine_used', 'scope', 'sent_via_email')
    search_fields = ('context_ref', 'file_path_docx', 'file_path_pdf')
    readonly_fields = ('log_id', 'generated_at')
    date_hierarchy  = 'generated_at'

    def log_id_short(self, obj):
        return str(obj.log_id)[:8] + '…'
    log_id_short.short_description = 'ID'

    def file_size_display(self, obj):
        if not obj.file_size_bytes:
            return '–'
        kb = obj.file_size_bytes / 1024
        if kb > 1024:
            return f'{kb/1024:.1f} MB'
        return f'{kb:.0f} KB'
    file_size_display.short_description = 'Größe'


# ── DocQueue ──────────────────────────────────────────────────────────────────

@admin.register(DocQueue)
class DocQueueAdmin(admin.ModelAdmin):
    list_display  = ('queue_id_short', 'template', 'engine',
                     'context_ref', 'status', 'retry_count',
                     'created_at', 'processed_at')
    list_filter   = ('status', 'engine')
    search_fields = ('context_ref',)
    readonly_fields = ('queue_id', 'celery_task_id', 'created_at', 'processed_at')
    actions       = ['cancel_queue_items']

    def queue_id_short(self, obj):
        return str(obj.queue_id)[:8] + '…'
    queue_id_short.short_description = 'ID'

    def cancel_queue_items(self, request, queryset):
        updated = queryset.filter(status='PENDING').update(status='CANCELLED')
        self.message_user(request, f'{updated} Queue-Einträge abgebrochen.')
    cancel_queue_items.short_description = 'Ausgewählte abbrechen (nur PENDING)'
