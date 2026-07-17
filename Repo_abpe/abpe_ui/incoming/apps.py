from django.apps import AppConfig

class AbpeUiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.abpe_ui'
    label = 'abpe_ui'
    verbose_name = 'ABpE UI Portal'

    def ready(self):
        import apps.abpe_ui.signals  # noqa: F401
