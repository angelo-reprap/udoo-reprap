from django.apps import AppConfig

class AbpeEmailStudioConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.abpe_email_studio'
    label = 'abpe_email_studio'
    verbose_name = 'ABpE Email Studio'

    def ready(self):
        import apps.abpe_email_studio.signals
