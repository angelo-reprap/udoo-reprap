from django.apps import AppConfig


class AbpeKiWizConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.abpe_ki_wiz'
    verbose_name = 'ABpE KI Wizard'

    def ready(self):
        from . import registry  # noqa: F401
        from .providers import stubs  # noqa: F401
        try:
            from .providers.email_template import register_email_provider
            register_email_provider()
        except Exception as exc:
            import logging
            logging.getLogger('abpe_ki_wiz').warning(
                'EmailTemplateWizardProvider nicht registriert: %s', exc,
            )
