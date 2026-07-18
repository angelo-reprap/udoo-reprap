from django.apps import AppConfig


class AbpeKiWizConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.abpe_ki_wiz'
    verbose_name = 'ABpE KI Wizard'

    def ready(self):
        # Phase 0: nur Stub-Provider. Fach-Apps registrieren in Phase 1
        # (z. B. apps.abpe_email_studio.apps → register(EmailTemplateWizardProvider))
        from . import registry  # noqa: F401
        from .providers import stubs  # noqa: F401
