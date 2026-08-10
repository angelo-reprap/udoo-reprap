from django.contrib import admin

from .models import WizardPrompt, WizardSession


@admin.register(WizardPrompt)
class WizardPromptAdmin(admin.ModelAdmin):
    list_display = (
        'key',
        'name',
        'wizard_id',
        'phase',
        'app_scope',
        'aktiv',
        'updated_at',
        'updated_by',
    )
    list_filter = ('wizard_id', 'phase', 'app_scope', 'aktiv')
    search_fields = ('key', 'name', 'description', 'wizard_id')
    readonly_fields = ('updated_at',)
    ordering = ('wizard_id', 'phase', 'key')
    fieldsets = (
        (None, {
            'fields': (
                'key',
                'name',
                'description',
                'wizard_id',
                'phase',
                'app_scope',
                'aktiv',
            ),
        }),
        ('Prompt', {
            'fields': (
                'system',
                'user_template',
                'instruction_default',
                'checklist_template',
            ),
        }),
        ('Meta', {
            'fields': ('updated_by', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.updated_by_id:
            obj.updated_by = request.user
        elif change:
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(WizardSession)
class WizardSessionAdmin(admin.ModelAdmin):
    list_display = (
        'short_id',
        'wizard_id',
        'user',
        'status',
        'phase',
        'created_at',
        'updated_at',
    )
    list_filter = ('wizard_id', 'status', 'phase')
    search_fields = ('wizard_id', 'briefing', 'id')
    readonly_fields = (
        'id',
        'wizard_id',
        'user',
        'status',
        'phase',
        'briefing',
        'answers',
        'meta_suggestions',
        'result',
        'error_message',
        'created_at',
        'updated_at',
        'completed_at',
    )
    ordering = ('-created_at',)

    def short_id(self, obj):
        return str(obj.id)[:8]
    short_id.short_description = 'Session'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
