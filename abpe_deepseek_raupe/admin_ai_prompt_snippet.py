# ── Am Ende von apps/abpe_email_studio/admin.py einfügen ──
# AiPrompt zuerst in bestehenden "from .models import (...)" Block aufnehmen!


@admin.register(AiPrompt)
class AiPromptAdmin(admin.ModelAdmin):
    list_display = ('key', 'name', 'app_scope', 'aktiv', 'updated_at', 'updated_by')
    list_filter = ('app_scope', 'aktiv')
    search_fields = ('key', 'name', 'description')
    readonly_fields = ('updated_at',)
    fieldsets = (
        (None, {
            'fields': ('key', 'name', 'description', 'app_scope', 'aktiv'),
        }),
        ('Prompt', {
            'fields': ('system', 'user_template', 'instruction_default'),
            'description': (
                'DeepSeek-Platzhalter: [[INSTRUCTION]] [[TEXT]] [[NOTES]] [[CONTEXT]] [[KOPF]]. '
                'E-Mail-Variablen nach DeepSeek: {name} {sender_name} {title} …'
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
        super().save_model(request, obj, form, change)
