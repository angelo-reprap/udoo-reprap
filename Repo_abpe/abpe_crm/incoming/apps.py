from django.apps import AppConfig

class AbpeCrmConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'apps.abpe_crm'
    verbose_name       = 'ABpE CRM'

    def ready(self):
        # documents_content.py / documents_content_firma.py heissen nicht
        # "documents.py" -> django_elasticsearch_dsl's Auto-Discovery findet
        # sie nie von allein. Explizit importieren, damit
        # @registry.register_document tatsaechlich laeuft und der
        # RealTimeSignalProcessor bei CrmContactNote/CrmContact/CrmAccount
        # etc. greift.
        from . import documents_content        # noqa: F401
        from . import documents_content_firma   # noqa: F401
