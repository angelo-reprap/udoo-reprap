from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class IngestEmailConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.ingest_email'
    verbose_name = "E-Mail Import"
    
    def ready(self):
        """Wird aufgerufen wenn App geladen ist"""
        try:
            # Importiere und aktiviere Signals
            from . import signals_auto_reply
            signals_auto_reply.connect_auto_reply_signals()
            
            # Aktiviere auch die bestehenden Intake Integration Signals
            try:
                from . import signals
                signals.connect_signals()
                logger.info("✅ Intake Integration Signals aktiviert")
            except ImportError:
                logger.warning("⚠️  Intake Integration Signals nicht gefunden")
                
            logger.info("✅ IngestEmail App bereit mit Auto-Reply")
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Laden von IngestEmail App: {e}")
