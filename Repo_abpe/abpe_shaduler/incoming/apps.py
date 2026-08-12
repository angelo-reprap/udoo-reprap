from django.apps import AppConfig


class AbpeShadulerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.abpe_shaduler'
    label = 'abpe_shaduler'
    verbose_name = 'ABpE Shaduler (Aufgaben)'

    def ready(self):
        # Signals erst nach App-Registry laden
        try:
            from . import signals  # noqa: F401
        except Exception:
            # Bei migrate / erstem Import ohne Abhängigkeiten still bleiben
            pass
