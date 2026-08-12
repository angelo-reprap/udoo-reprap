"""
ABpE Matching Workflow — App Config
"""
from django.apps import AppConfig


class AbpeMatchingWorkflowConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'apps.abpe_matching_workflow'
    verbose_name       = 'ABpE Matching Workflow'

    def ready(self):
        import apps.abpe_matching_workflow.signals  # noqa
