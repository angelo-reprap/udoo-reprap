"""
ABpE Matching Workflow — Django Admin
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    FollowupRule,
    EmailTemplate,
    ProjectRequest,
    ProjectContact,
    ProjectConsultant,
    MatchResult,
    EmailHistory,
)


# ============================================================
# FOLLOWUP RULE
# ============================================================

@admin.register(FollowupRule)
class FollowupRuleAdmin(admin.ModelAdmin):
    list_display  = ['name', 'preferred_channel', 'available_from',
                     'available_until', 'followup_delay_hours', 'is_default']
    list_filter   = ['preferred_channel', 'is_default']
    search_fields = ['name']
    ordering      = ['name']


# ============================================================
# EMAIL TEMPLATE
# ============================================================

@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display  = ['name', 'template_type', 'is_active', 'use_ollama', 'sort_order']
    list_filter   = ['template_type', 'is_active', 'use_ollama']
    search_fields = ['name', 'subject', 'body']
    ordering      = ['template_type', 'sort_order']


# ============================================================
# PROJECT CONTACT (inline für ProjectRequest)
# ============================================================

class ProjectContactInline(admin.TabularInline):
    model      = ProjectContact
    extra      = 0
    fields     = ['first_name', 'last_name', 'email', 'phone', 'role', 'personal_note', 'followup_rule']
    ordering   = ['sort_order']


# ============================================================
# PROJECT REQUEST
# ============================================================

@admin.register(ProjectRequest)
class ProjectRequestAdmin(admin.ModelAdmin):
    list_display  = ['project_number', 'title', 'customer_name', 'status',
                     'priority', 'is_archived', 'crm_synced_at', 'created_at']
    list_filter   = ['status', 'priority', 'is_archived', 'remote_possible', 'rate_type']
    search_fields = ['project_number', 'title', 'customer_name', 'description']
    ordering      = ['-created_at']
    readonly_fields = ['project_number', 'created_at', 'updated_at', 'crm_synced_at']
    inlines       = [ProjectContactInline]

    fieldsets = [
        ('Projekt', {
            'fields': ['project_number', 'title', 'description', 'status', 'priority']
        }),
        ('Kunde', {
            'fields': ['customer_name', 'customer_contact_person', 'customer_email',
                       'customer_phone', 'customer_id']
        }),
        ('SuiteCRM', {
            'fields': ['crm_account_id', 'crm_contact_id', 'crm_opportunity_id', 'crm_synced_at'],
            'classes': ['collapse']
        }),
        ('Anforderungen', {
            'fields': ['required_skills', 'nice_to_have_skills', 'extracted_technologies',
                       'min_experience_years', 'required_languages', 'required_certs']
        }),
        ('Gewichtungen', {
            'fields': ['weight_skills_required', 'weight_skills_nice', 'weight_industry',
                       'weight_experience', 'weight_location', 'shortlist_threshold'],
            'classes': ['collapse']
        }),
        ('Rahmenbedingungen', {
            'fields': ['start_date', 'duration_months', 'location', 'remote_possible',
                       'workload_percent', 'rate_min', 'rate_max', 'rate_type']
        }),
        ('Quelle', {
            'fields': ['source_text', 'source_email_id', 'source_email_date', 'source_document'],
            'classes': ['collapse']
        }),
        ('Abschluss', {
            'fields': ['is_archived', 'close_reason', 'close_note', 'closed_at',
                       'placed_consultant', 'placed_at', 'placed_rate',
                       'placed_start', 'placed_end', 'placed_notes'],
            'classes': ['collapse']
        }),
        ('Meta', {
            'fields': ['created_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]


# ============================================================
# PROJECT CONSULTANT
# ============================================================

@admin.register(ProjectConsultant)
class ProjectConsultantAdmin(admin.ModelAdmin):
    list_display  = ['project', 'consultant_name', 'match_score_display',
                     'status', 'contacted_at', 'needs_followup_display']
    list_filter   = ['status', 'rejection_reason', 'rejected_by']
    search_fields = ['project__project_number', 'project__title',
                     'consultant_cv__first_name', 'consultant_cv__last_name']
    ordering      = ['-match_score']
    readonly_fields = ['matched_at', 'created_at', 'updated_at', 'status_history']

    fieldsets = [
        ('Verknüpfung', {
            'fields': ['project', 'consultant_cv', 'matched_by']
        }),
        ('Matching', {
            'fields': ['match_score', 'match_reason', 'match_details']
        }),
        ('Status', {
            'fields': ['status', 'status_history']
        }),
        ('Berater-Kommunikation', {
            'fields': ['contacted_at', 'consultant_response_at',
                       'consultant_response_note', 'followup_sent_at', 'reminder_sent_at',
                       'unavailable_at', 'unavailable_note']
        }),
        ('Angebot', {
            'fields': ['offer_text', 'offer_sent_at', 'offer_documents'],
            'classes': ['collapse']
        }),
        ('Kunden-Kommunikation', {
            'fields': ['client_contacted_at', 'client_response_at', 'client_response_note'],
            'classes': ['collapse']
        }),
        ('Interview', {
            'fields': ['interview_date', 'interview_notes', 'interview_feedback'],
            'classes': ['collapse']
        }),
        ('Absage', {
            'fields': ['rejection_reason', 'rejection_note', 'rejected_at', 'rejected_by'],
            'classes': ['collapse']
        }),
        ('Vermittlung', {
            'fields': ['accepted_at', 'placed_at', 'agreed_rate',
                       'agreed_start_date', 'agreed_duration'],
            'classes': ['collapse']
        }),
        ('CRM + Email Studio', {
            'fields': ['crm_email_id', 'email_studio_id'],
            'classes': ['collapse']
        }),
    ]

    def consultant_name(self, obj):
        return obj.consultant_cv.full_name
    consultant_name.short_description = 'Berater'

    def match_score_display(self, obj):
        pct = int(obj.match_score * 100)
        color = '#155724' if pct >= 70 else '#856404' if pct >= 50 else '#666'
        return format_html(
            '<span style="font-weight:bold;color:{}">{} %</span>', color, pct
        )
    match_score_display.short_description = 'Score'

    def needs_followup_display(self, obj):
        if obj.needs_followup:
            return format_html('<span style="color:#ef4444">⚠ Nachfassen</span>')
        return '—'
    needs_followup_display.short_description = 'Followup'


# ============================================================
# MATCH RESULT
# ============================================================

@admin.register(MatchResult)
class MatchResultAdmin(admin.ModelAdmin):
    list_display  = ['project_request', 'consultant_name', 'overall_score',
                     'rank', 'reason_model', 'calculated_at']
    list_filter   = ['reason_model', 'match_reason_lang']
    search_fields = ['project_request__project_number',
                     'consultant_cv__first_name', 'consultant_cv__last_name']
    ordering      = ['-overall_score']
    readonly_fields = ['calculated_at']

    def consultant_name(self, obj):
        return obj.consultant_cv.full_name
    consultant_name.short_description = 'Berater'


# ============================================================
# PROJECT CONTACT
# ============================================================

@admin.register(ProjectContact)
class ProjectContactAdmin(admin.ModelAdmin):
    list_display  = ['full_name', 'project', 'role', 'email', 'phone']
    list_filter   = ['role']
    search_fields = ['first_name', 'last_name', 'email', 'project__project_number']
    ordering      = ['last_name', 'first_name']


# ============================================================
# EMAIL HISTORY
# ============================================================

@admin.register(EmailHistory)
class EmailHistoryAdmin(admin.ModelAdmin):
    list_display  = ['email_type', 'recipient', 'status', 'sent_at', 'crm_email_id']
    list_filter   = ['email_type', 'status']
    search_fields = ['recipient', 'subject', 'crm_email_id']
    ordering      = ['-sent_at']
    readonly_fields = ['sent_at', 'opened_at', 'replied_at']
