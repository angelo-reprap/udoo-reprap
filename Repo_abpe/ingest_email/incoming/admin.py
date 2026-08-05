from django.contrib import admin
from django.utils.html import format_html
from .models import EmailImportConfig, EmailMessage, EmailAttachment

@admin.register(EmailImportConfig)
class EmailImportConfigAdmin(admin.ModelAdmin):
    list_display = ['name', 'email_address', 'protocol', 'is_active', 'last_check']
    list_filter = ['is_active', 'protocol']
    search_fields = ['name', 'email_address']
    
    fieldsets = (
        ('Allgemein', {
            'fields': ('name', 'email_address', 'is_active')
        }),
        ('Server Konfiguration', {
            'fields': ('protocol', 'imap_server', 'imap_port', 'smtp_server', 'smtp_port')
        }),
        ('Authentifizierung', {
            'fields': ('username', 'password', 'use_ssl')
        }),
        ('Import Einstellungen', {
            'fields': ('mailbox', 'check_frequency', 'delete_after_import')
        }),
        ('Verarbeitungsregeln', {
            'fields': ('process_attachments', 'attachment_types', 'keywords')
        }),
        ('Status', {
            'fields': ('last_check',)
        }),
    )

@admin.register(EmailMessage)
class EmailMessageAdmin(admin.ModelAdmin):
    list_display = [
        'subject_short',
        'from_email',
        'to_email',
        'received_date_short',
        'status_badge',
        'has_attachments_badge',
        'intake_linked',
    ]
    
    list_filter = ['status', 'has_attachments', 'received_date']
    search_fields = ['subject', 'from_email', 'to_email', 'body_plain']
    readonly_fields = ['received_date', 'sent_date', 'size', 'message_id']
    
    fieldsets = (
        ('Header', {
            'fields': ('message_id', 'subject', 'from_email', 'to_email', 'cc', 'bcc')
        }),
        ('Inhalt', {
            'fields': ('body_plain', 'body_html'),
            'classes': ('collapse',)
        }),
        ('Metadaten', {
            'fields': ('received_date', 'sent_date', 'size', 'config')
        }),
        ('Status', {
            'fields': ('status', 'processed_at', 'error_message')
        }),
        ('Integration', {
            'fields': ('intake_rawinput_id', 'tags'),
            'classes': ('collapse',)
        }),
        ('Raw Data', {
            'fields': ('raw_headers', 'raw_body'),
            'classes': ('collapse',)
        }),
    )
    
    # Custom Methods für List Display
    def subject_short(self, obj):
        return obj.subject[:50] + ('...' if len(obj.subject) > 50 else '')
    subject_short.short_description = 'Betreff'
    
    def received_date_short(self, obj):
        return obj.received_date.strftime('%d.%m. %H:%M')
    received_date_short.short_description = 'Empfangen'
    
    def status_badge(self, obj):
        colors = {
            'NEW': 'gray',
            'PROCESSING': 'blue',
            'PROCESSED': 'green',
            'ERROR': 'red',
            'ARCHIVED': 'orange'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 10px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def has_attachments_badge(self, obj):
        if obj.has_attachments:
            return format_html(
                '<span style="background-color: green; color: white; padding: 2px 8px; border-radius: 10px;">{} Anhänge</span>',
                obj.attachment_count
            )
        return format_html(
            '<span style="background-color: gray; color: white; padding: 2px 8px; border-radius: 10px;">Keine</span>'
        )
    has_attachments_badge.short_description = 'Anhänge'
    
    def intake_linked(self, obj):
        if obj.intake_rawinput_id:
            return format_html(
                '<a href="/admin/abpe_intake/rawinput/{}/change/">📝 RawInput</a>',
                obj.intake_rawinput_id
            )
        return '-'
    intake_linked.short_description = 'Intake'

@admin.register(EmailAttachment)
class EmailAttachmentAdmin(admin.ModelAdmin):
    list_display = ['filename', 'email_subject', 'content_type', 'size_formatted', 'is_processed']
    list_filter = ['content_type', 'is_processed']
    search_fields = ['filename', 'email__subject']
    
    def email_subject(self, obj):
        return obj.email.subject[:50]
    email_subject.short_description = 'E-Mail Betreff'
    
    def size_formatted(self, obj):
        if obj.size < 1024:
            return f"{obj.size} B"
        elif obj.size < 1024 * 1024:
            return f"{obj.size / 1024:.1f} KB"
        else:
            return f"{obj.size / (1024 * 1024):.1f} MB"
    size_formatted.short_description = 'Größe'

