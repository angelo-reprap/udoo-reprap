"""
cv_extractor/apps.py - App-Konfiguration für das CV-Extraktor-Modul
"""

from django.apps import AppConfig


class CvExtractorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.cv_extractor'
    verbose_name = 'CV Extractor'
    
    def ready(self):
        """Wird beim Start der App aufgerufen"""
        # Importiere Signale
        try:
            from . import signals
        except ImportError:
            pass
        
        print(f"✅ {self.verbose_name} bereit")
