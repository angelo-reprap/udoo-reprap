"""
Signals — Kap. 4 Architektur.
Receiver auf matching_workflow.ProjectConsultant etc. werden in V1 verdrahtet.
"""
import logging

logger = logging.getLogger(__name__)

# Placeholder: ready() importiert dieses Modul.
# Beispiel (später):
#   @receiver(post_save, sender=ProjectConsultant)
#   def on_pc_status(sender, instance, **kwargs): ...
