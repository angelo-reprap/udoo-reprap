# ── In apps/abpe_email_studio/models.py einfügen (am Ende der Datei) ──


class AiPrompt(models.Model):
    """
    DeepSeek / KI-Prompts — editierbar in Django-Admin (später Email Studio).
    Fallback: ai_prompt_defaults.AI_PROMPT_DEFAULTS + deepseek_api_pbx.DEFAULT_PROMPTS
    """
    class AppScope(models.TextChoices):
        GENERAL = 'general', 'Allgemein'
        MEETME = 'meetme', 'MeetMe'
        MATCHING = 'matching', 'Matching'
        PBX = 'pbx', 'PBX / Telefon'
        CRM = 'crm', 'CRM'

    key = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    app_scope = models.CharField(
        max_length=32, choices=AppScope.choices, default=AppScope.GENERAL,
    )
    system = models.TextField(help_text='System-Prompt für DeepSeek')
    user_template = models.TextField(
        help_text='User-Template mit [[INSTRUCTION]], [[TEXT]], [[NOTES]], …',
    )
    instruction_default = models.TextField(
        blank=True,
        help_text='Standard-Instruction wenn API keine übergibt (z.B. meetme_email)',
    )
    aktiv = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='ai_prompts_updated',
    )

    class Meta:
        db_table = 'abpe_email_studio_ai_prompt'
        verbose_name = 'KI-Prompt'
        verbose_name_plural = 'KI-Prompts'
        ordering = ['app_scope', 'name']

    def __str__(self):
        return f'{self.key} — {self.name}'
