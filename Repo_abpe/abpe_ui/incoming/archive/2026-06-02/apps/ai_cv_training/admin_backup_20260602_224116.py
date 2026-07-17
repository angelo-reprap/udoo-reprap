from django.contrib import admin
from django.utils.html import format_html
from django.contrib.admin import SimpleListFilter
from django.urls import path
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from .models import (
    TrainingTerm, TrainingSource, TrainingRelation,
    TrainingStatistics, TrainingFeedback, TrainingBatch,
    ExtractionRule, BlockMarker, ProcessingLog
)
import json


# =========================================================
# DROPDOWN-FILTER FÜR BLOCK-TYPEN
# =========================================================

class BlockTypeFilter(SimpleListFilter):
    """Dropdown-Filter für Block-Typen"""
    title = 'Block-Typ'
    parameter_name = 'block_type'

    def lookups(self, request, model_admin):
        return (
            ('all', '📋 Alle Regeln'),
            ('experience', '💼 Experience / Projekte'),
            ('skills', '🔧 Skills'),
            ('personal', '👤 Persönliche Daten'),
            ('header', '📌 Header / Schwerpunkt'),
            ('education', '🎓 Ausbildung'),
            ('certifications', '🏆 Zertifikate'),
            ('industries', '🏢 Branchen'),
            ('focus_areas', '🎯 Fachbereiche'),
            ('splitter', '✂️ Splitter'),
            ('other', '📦 Sonstiges'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'all' or self.value() is None:
            return queryset
        return queryset.filter(block_type=self.value())


# =========================================================
# BESCHREIBUNGSTEXT FÜR DIE ADMIN-SEITE
# =========================================================

ADMIN_HELP_TEXT = """
<div style="background: #f0f8ff; border-left: 4px solid #007cba; padding: 15px; margin-bottom: 20px; border-radius: 4px;">
    <h3>📖 Funktionsweise der CV-Extraktion</h3>
    <p>Dieses System lernt selbstständig, wie CVs extrahiert werden.</p>

    <h4>🔄 Ablauf:</h4>
    <ol>
        <li><strong>PDF → Text</strong>: Das PDF wird mit pdfplumber in Text umgewandelt</li>
        <li><strong>Block-Erkennung</strong>: Der Text wird in 9 Blöcke aufgeteilt</li>
        <li><strong>Entscheidungsschleife</strong>: Für jeden Block wird geprüft:</li>
        <ul>
            <li>✅ <strong>Regex</strong> - wenn bekannte Marker in der DB existieren (schnell)</li>
            <li>🤖 <strong>KI</strong> - wenn keine Marker bekannt sind (langsam, lernt)</li>
        </ul>
        <li><strong>Selbstlernen</strong>: Die KI erkennt neue Marker und speichert sie in dieser DB</li>
        <li><strong>Extraktion</strong>: Mit den gespeicherten Regex-Regeln werden die Daten extrahiert</li>
    </ol>

    <h4>📊 Diese Tabellen enthalten:</h4>
    <ul>
        <li><strong>ExtractionRule</strong> - Regex-Patterns für die Extraktion</li>
        <li><strong>BlockMarker</strong> - Marker für Block-Erkennung</li>
        <li><strong>ProcessingLog</strong> - Logs der Verarbeitungen</li>
    </ul>

    <h4>💡 Tipps:</h4>
    <ul>
        <li>Neue Patterns können <strong>manuell hinzugefügt</strong> oder <strong>von der KI gelernt</strong> werden</li>
        <li>Patterns mit <strong>niedriger Konfidenz</strong> können deaktiviert oder gelöscht werden</li>
        <li>Die <strong>ProcessingLog</strong> Tabelle zeigt, wie oft Regex vs KI verwendet wurde</li>
    </ul>
</div>
"""


# =========================================================
# BESTEHENDE ADMIN-CLASSES
# =========================================================

@admin.register(TrainingTerm)
class TrainingTermAdmin(admin.ModelAdmin):
    list_display = ('term', 'category', 'confidence', 'frequency', 'created_at')
    list_filter = ('category', 'confidence', 'created_at')
    search_fields = ('term', 'canonical_term')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-frequency',)


@admin.register(TrainingSource)
class TrainingSourceAdmin(admin.ModelAdmin):
    list_display = ('source_type', 'source_name', 'status', 'created_at')
    list_filter = ('source_type', 'status')


@admin.register(TrainingRelation)
class TrainingRelationAdmin(admin.ModelAdmin):
    list_display = ('term_from', 'term_to', 'relation_type', 'weight')
    list_filter = ('relation_type',)


@admin.register(TrainingStatistics)
class TrainingStatisticsAdmin(admin.ModelAdmin):
    list_display = ('stat_type', 'category', 'total_terms', 'calculated_at')


@admin.register(TrainingFeedback)
class TrainingFeedbackAdmin(admin.ModelAdmin):
    list_display = ('term', 'feedback_type', 'user_email', 'created_at')


@admin.register(TrainingBatch)
class TrainingBatchAdmin(admin.ModelAdmin):
    list_display = ('name', 'batch_type', 'status', 'progress_percent')


# =========================================================
# NEUE ADMIN-CLASSES FÜR REGEX-EXTRAKTION
# =========================================================

@admin.register(ExtractionRule)
class ExtractionRuleAdmin(admin.ModelAdmin):
    """Admin für Regex-Extraktionsregeln"""

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['help_text'] = format_html(ADMIN_HELP_TEXT)
        return super().changelist_view(request, extra_context=extra_context)

    list_display = (
        'id',
        'block_type_badge',
        'field_label',
        'regex_preview',
        'notes_preview',
        'confidence_display',
        'usage_badge',
        'is_active'
    )
    list_filter = (BlockTypeFilter, 'is_active', 'learned_by_ai')
    list_editable = ('is_active',)
    search_fields = ('field_label', 'regex_pattern', 'notes', 'block_type')

    fieldsets = (
        ('Basis-Informationen', {
            'fields': ('block_type', 'field_name', 'field_label')
        }),
        ('Regex-Pattern', {
            'fields': ('regex_pattern',),
            'description': 'Python Regex mit r"..." Syntax. Beispiel: r"Zeitraum:\\s*(.*?)(?:\\n|$)"'
        }),
        ('Beschreibung für KI (notes)', {
            'fields': ('notes',),
            'description': 'Dieser Text wird der KI als Kontext für die Extraktion gegeben. Je detaillierter, desto besser.'
        }),
        ('Kontext (optional)', {
            'fields': ('context_before', 'context_after'),
            'classes': ('collapse',),
        }),
        ('Statistik & Status', {
            'fields': ('confidence', 'is_active', 'learned_by_ai', 'usage_count', 'success_count'),
            'classes': ('collapse',),
        }),
    )

    readonly_fields = ('usage_count', 'success_count', 'created_at', 'updated_at')

    def block_type_badge(self, obj):
        badges = {
            'experience': '💼 Experience',
            'skills': '🔧 Skills',
            'personal': '👤 Personal',
            'header': '📌 Header',
            'education': '🎓 Education',
            'certifications': '🏆 Certs',
            'industries': '🏢 Industries',
            'focus_areas': '🎯 Focus',
            'splitter': '✂️ Splitter',
            'other': '📦 Other',
        }
        text = badges.get(obj.block_type, obj.block_type)
        return format_html('<span style="font-weight: bold;">{}</span>', text)
    block_type_badge.short_description = 'Block-Typ'

    def regex_preview(self, obj):
        return format_html('<code style="font-size: 11px; background: #f5f5f5; padding: 2px 4px;">{}</code>', obj.regex_pattern[:50])
    regex_preview.short_description = 'Regex'

    def notes_preview(self, obj):
        if obj.notes:
            preview = obj.notes[:60]
            return format_html('<span style="color: #666; font-style: italic;">{}{}</span>', preview, '...' if len(obj.notes) > 60 else '')
        return format_html('<span style="color: #999;">-</span>')
    notes_preview.short_description = 'KI-Beschreibung'

    def confidence_display(self, obj):
        width = obj.confidence * 100
        color = '#28a745' if obj.confidence > 0.7 else '#ffc107' if obj.confidence > 0.3 else '#dc3545'
        return format_html(
            '<div style="width: 80px; background: #e9ecef; border-radius: 4px; overflow: hidden;">'
            '<div style="width: {}%; background: {}; height: 18px;"></div>'
            '</div>',
            int(width), color
        )
    confidence_display.short_description = 'Konfidenz'

    def usage_badge(self, obj):
        if obj.usage_count == 0:
            return format_html('<span style="color: #6c757d;">-</span>')
        rate = obj.success_count / obj.usage_count if obj.usage_count > 0 else 0
        color = '#28a745' if rate > 0.8 else '#ffc107' if rate > 0.5 else '#dc3545'
        percent = int(rate * 100)
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 6px; border-radius: 12px; font-size: 11px;">{}% ({}/{})</span>',
            color, percent, obj.success_count, obj.usage_count
        )
    usage_badge.short_description = 'Erfolgsquote'

    # ========== ZUSÄTZLICHE AKTIONEN ==========
    actions = ['export_as_json', 'export_notes_for_ki']

    def export_as_json(self, request, queryset):
        """Exportiert ausgewählte Regeln als JSON"""
        data = []
        for rule in queryset:
            data.append({
                'id': rule.id,
                'block_type': rule.block_type,
                'field_name': rule.field_name,
                'field_label': rule.field_label,
                'regex_pattern': rule.regex_pattern,
                'notes': rule.notes,
                'confidence': rule.confidence,
                'is_active': rule.is_active,
            })
        response = HttpResponse(json.dumps(data, indent=2, ensure_ascii=False), content_type='application/json')
        response['Content-Disposition'] = 'attachment; filename="extraction_rules.json"'
        return response
    export_as_json.short_description = '📤 Als JSON exportieren'

    def export_notes_for_ki(self, request, queryset):
        """Exportiert die notes als KI-Prompt"""
        prompt = "Du bist ein CV-Parsing-Experte. Extrahiere folgende Felder:\n\n"
        for rule in queryset.order_by('block_type', 'field_name'):
            prompt += f"### {rule.field_label} ({rule.field_name})\n"
            if rule.notes:
                prompt += f"Beschreibung: {rule.notes}\n"
            prompt += f"Regex: {rule.regex_pattern}\n\n"
        prompt += "\nGib das Ergebnis als JSON zurück."

        response = HttpResponse(prompt, content_type='text/plain')
        response['Content-Disposition'] = 'attachment; filename="ki_prompt.txt"'
        return response
    export_notes_for_ki.short_description = '🤖 Notes als KI-Prompt exportieren'


@admin.register(BlockMarker)
class BlockMarkerAdmin(admin.ModelAdmin):
    """Admin für Block-Marker"""

    list_display = ('block_type_badge', 'marker_text', 'confidence_display', 'is_active', 'learned_by_ai', 'usage_count')
    list_filter = (BlockTypeFilter, 'is_active', 'learned_by_ai')
    search_fields = ('marker_text',)
    list_editable = ('is_active',)
    readonly_fields = ('usage_count',)

    fieldsets = (
        ('Marker-Informationen', {
            'fields': ('block_type', 'marker_text'),
        }),
        ('Regex (optional)', {
            'fields': ('start_regex', 'end_regex'),
            'classes': ('collapse',),
        }),
        ('Status', {
            'fields': ('confidence', 'is_active', 'learned_by_ai', 'usage_count'),
        }),
    )

    def block_type_badge(self, obj):
        badges = {
            'experience': '💼 Experience',
            'skills': '🔧 Skills',
            'personal': '👤 Personal',
            'header': '📌 Header',
            'education': '🎓 Education',
            'certifications': '🏆 Certs',
            'industries': '🏢 Industries',
            'focus_areas': '🎯 Focus',
            'splitter': '✂️ Splitter',
        }
        text = badges.get(obj.block_type, obj.block_type)
        return format_html('<span style="font-weight: bold;">{}</span>', text)
    block_type_badge.short_description = 'Block-Typ'

    def confidence_display(self, obj):
        width = obj.confidence * 100
        color = '#28a745' if obj.confidence > 0.7 else '#ffc107' if obj.confidence > 0.3 else '#dc3545'
        return format_html(
            '<div style="width: 60px; background: #e9ecef; border-radius: 4px; overflow: hidden;">'
            '<div style="width: {}%; background: {}; height: 16px;"></div>'
            '</div>',
            int(width), color
        )
    confidence_display.short_description = 'Konfidenz'


@admin.register(ProcessingLog)
class ProcessingLogAdmin(admin.ModelAdmin):
    """Admin für Verarbeitungslogs"""

    list_display = ('block_type', 'method', 'success', 'duration_ms', 'created_at')
    list_filter = (BlockTypeFilter, 'method', 'success')
    readonly_fields = ('created_at',)

    fieldsets = (
        ('Log-Informationen', {
            'fields': ('block_type', 'method', 'success', 'duration_ms', 'marker_used', 'error_message', 'created_at'),
        }),
    )

    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return True
