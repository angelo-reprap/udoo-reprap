# Ersetzt in apps/abpe_crm/services/deepseek_api_pbx.py die Funktion _get_prompt
# und fügt get_prompt_config hinzu (nach DEFAULT_PROMPTS, vor class PbxAIResult).


def get_prompt_config(key: str) -> dict:
    """system, user_template, instruction_default — DB (AiPrompt) mit Fallback DEFAULT_PROMPTS."""
    d = DEFAULT_PROMPTS.get(key, {})
    base = {
        'system': d.get('system', ''),
        'user_template': d.get('user_template', ''),
        'instruction_default': d.get('instruction_default', ''),
    }
    try:
        from apps.abpe_email_studio.models import AiPrompt
        row = AiPrompt.objects.filter(key=key, aktiv=True).first()
        if row:
            return {
                'system': row.system or base['system'],
                'user_template': row.user_template or base['user_template'],
                'instruction_default': row.instruction_default or base['instruction_default'],
            }
    except Exception:
        pass
    return base


def _get_prompt(key: str):
    """(system, user_template) — Abwärtskompatibel."""
    cfg = get_prompt_config(key)
    return (cfg['system'], cfg['user_template'])
