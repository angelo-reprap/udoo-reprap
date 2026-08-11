"""WizardPrompt aus DB laden."""
from apps.abpe_ki_wiz.models import WizardPrompt


def get_prompt_by_key(key: str) -> WizardPrompt | None:
    try:
        return WizardPrompt.objects.get(key=key, aktiv=True)
    except WizardPrompt.DoesNotExist:
        return None
