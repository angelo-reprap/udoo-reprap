from django.contrib import admin
from .models import (
    EmailSenderAccount, EmailSignature, EmailTemplate,
    EmailTemplateVersion, EmailLog, EmailQueue, EmailModule
)

@admin.register(EmailSenderAccount)
class EmailSenderAccountAdmin(admin.ModelAdmin):
    list_display  = ['email', 'display_name', 'sender_mode', 'is_default', 'is_active']
    list_filter   = ['sender_mode', 'is_active', 'is_default']
    search_fields = ['email', 'display_name']


@admin.register(EmailSignature)
class EmailSignatureAdmin(admin.ModelAdmin):
    list_display  = ['name', 'identifier', 'sender_account', 'is_default', 'is_public']
    list_filter   = ['is_default', 'is_public']
    search_fields = ['name', 'identifier']


class EmailTemplateVersionInline(admin.TabularInline):
    model           = EmailTemplateVersion
    extra           = 0
    readonly_fields = ['version', 'sender_mode', 'change_note',
                       'is_milestone', 'milestone_label', 'created_by', 'created_at']
    fields          = ['version', 'sender_mode', 'change_note',
                       'is_milestone', 'milestone_label', 'created_by', 'created_at']
    can_delete      = False


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display    = ['name', 'identifier', 'app_scope', 'sender_mode',
                       'signature_mode', 'status', 'active_version',
                       'usage_count', 'last_used_at']
    list_filter     = ['status', 'app_scope', 'sender_mode', 'signature_mode']
    search_fields   = ['name', 'identifier', 'subject']
    readonly_fields = ['usage_count', 'last_used_at', 'created_at', 'updated_at']
    inlines         = [EmailTemplateVersionInline]
    fieldsets       = [
        ('Basis',    {'fields': ['identifier', 'name', 'description',
                                 'app_scope', 'event_type']}),
        ('Absender', {'fields': ['sender_mode', 'sender_account',
                                 'signature', 'include_signature', 'signature_mode']}),
        ('CC / BCC', {'fields': ['cc_emails', 'bcc_emails']}),
        ('Inhalt',   {'fields': ['subject', 'html_body', 'text_body', 'variables']}),
        ('Status',   {'fields': ['status', 'active_version']}),
        ('Tracking', {'fields': ['usage_count', 'last_used_at',
                                 'created_by', 'created_at', 'updated_at']}),
    ]


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display    = ['subject_short', 'from_email', 'to_display',
                       'sender_mode', 'status', 'app_reference', 'sent_at']
    list_filter     = ['status', 'sender_mode', 'app_reference']
    search_fields   = ['subject', 'from_email', 'task_reference']
    readonly_fields = [f.name for f in EmailLog._meta.fields]
    ordering        = ['-sent_at']

    def subject_short(self, obj):
        return obj.subject[:60]
    subject_short.short_description = 'Betreff'

    def to_display(self, obj):
        return obj.to_emails_display[:50]
    to_display.short_description = 'An'


@admin.register(EmailModule)
class EmailModuleAdmin(admin.ModelAdmin):
    list_display    = ['name', 'identifier', 'module_type', 'is_active', 'updated_at']
    list_filter     = ['module_type', 'is_active']
    search_fields   = ['name', 'identifier']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(EmailQueue)
class EmailQueueAdmin(admin.ModelAdmin):
    list_display    = ['queue_id', 'template', 'status', 'retry_count', 'created_at']
    list_filter     = ['status']
    readonly_fields = ['queue_id', 'celery_task_id', 'created_at', 'processed_at']
