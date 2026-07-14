#!/usr/bin/env python3
"""
Schritt 1 auf ucs5 installieren:
  cd /opt/abpe/backend
  cp -a apps/abpe_email_studio/models.py apps/abpe_email_studio/models.py.bak-ai-prompt
  python /path/to/abpe_deepseek_raupe/apply_step1_ucs5.py

Oder Paket nach /opt/abpe/backend/abpe_deepseek_raupe kopieren und:
  python abpe_deepseek_raupe/apply_step1_ucs5.py
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

BACKEND = Path('/opt/abpe/backend')
PKG = Path(__file__).resolve().parent


def main():
    backend = BACKEND if BACKEND.exists() else Path.cwd()
    if not (backend / 'manage.py').exists():
        print('FEHLER: manage.py nicht gefunden — cd /opt/abpe/backend')
        sys.exit(1)

    es = backend / 'apps' / 'abpe_email_studio'
    crm_pbx = backend / 'apps' / 'abpe_crm' / 'services' / 'deepseek_api_pbx.py'
    meetme_views = backend / 'apps' / 'abpe_meetme' / 'views.py'

    # 1) Defaults ins App-Paket
    shutil.copy2(PKG / 'ai_prompt_defaults.py', es / 'ai_prompt_defaults.py')
    print('OK ai_prompt_defaults.py')

    # 2) deepseek_raupe Service
    svc_dir = es / 'services'
    svc_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PKG / 'services' / 'deepseek_raupe.py', svc_dir / 'deepseek_raupe.py')
    print('OK services/deepseek_raupe.py')

    # 3) Management command
    cmd_dir = es / 'management' / 'commands'
    cmd_dir.mkdir(parents=True, exist_ok=True)
    (es / 'management' / '__init__.py').touch(exist_ok=True)
    (cmd_dir / '__init__.py').touch(exist_ok=True)
    # Fix import in command for ucs5
    cmd_text = (PKG / 'management' / 'commands' / 'sync_ai_prompts.py').read_text(encoding='utf-8')
    cmd_text = cmd_text.replace(
        'from abpe_deepseek_raupe.ai_prompt_defaults import AI_PROMPT_DEFAULTS',
        'from apps.abpe_email_studio.ai_prompt_defaults import AI_PROMPT_DEFAULTS',
    )
    cmd_text = re.sub(r'\nimport importlib.*?AI_PROMPT_DEFAULTS  # type: ignore\n', '\n', cmd_text, flags=re.DOTALL)
    (cmd_dir / 'sync_ai_prompts.py').write_text(cmd_text, encoding='utf-8')
    print('OK sync_ai_prompts command')

    # 4) Model AiPrompt
    models_py = es / 'models.py'
    text = models_py.read_text(encoding='utf-8')
    if 'class AiPrompt' not in text:
        if 'from django.conf import settings' not in text:
            text = 'from django.conf import settings\n' + text
        snippet = (PKG / 'models_ai_prompt_snippet.py').read_text(encoding='utf-8')
        snippet = re.sub(r'^#.*\n', '', snippet, flags=re.MULTILINE)
        text = text.rstrip() + '\n\n' + snippet
        models_py.write_text(text, encoding='utf-8')
        print('OK AiPrompt model added')
    else:
        print('= AiPrompt already in models.py')

    # 5) Admin
    admin_py = es / 'admin.py'
    admin_text = admin_py.read_text(encoding='utf-8')
    if 'AiPromptAdmin' not in admin_text:
        snippet = (PKG / 'admin_ai_prompt_snippet.py').read_text(encoding='utf-8')
        snippet = re.sub(r'^#.*\n', '', snippet, flags=re.MULTILINE)
        if 'from .models import AiPrompt' not in admin_text:
            admin_text = admin_text.replace(
                'from .models import',
                'from .models import AiPrompt,',
                1,
            ) if 'AiPrompt' not in admin_text else admin_text
        admin_text = admin_text.rstrip() + '\n\n' + snippet
        admin_py.write_text(admin_text, encoding='utf-8')
        print('OK admin registered')
    else:
        print('= AiPromptAdmin already registered')

    # 6) deepseek_api_pbx get_prompt_config
    pbx = crm_pbx.read_text(encoding='utf-8')
    if 'def get_prompt_config' not in pbx:
        pbx = pbx.replace(
            "        from apps.abpe_crm.models import PbxPrompt  # existiert erst spaeter\n"
            "        row = PbxPrompt.objects.filter(key=key, aktiv=True).first()\n"
            "        if row:\n"
            "            return (row.system or d['system'], row.user_template or d['user'])\n"
            "    except Exception:\n"
            "        pass  # Model/DB nicht da -> Konstanten\n"
            "    return (d['system'], d['user'])",
            "        from apps.abpe_email_studio.models import AiPrompt\n"
            "        row = AiPrompt.objects.filter(key=key, aktiv=True).first()\n"
            "        if row:\n"
            "            return (\n"
            "                row.system or d['system'],\n"
            "                row.user_template or d['user'],\n"
            "            )\n"
            "    except Exception:\n"
            "        pass\n"
            "    return (d['system'], d['user'])",
        )
        patch = (PKG / 'patches' / 'deepseek_api_pbx_get_prompt.py').read_text(encoding='utf-8')
        # Insert get_prompt_config before _get_prompt and replace _get_prompt body
        if 'def get_prompt_config' not in pbx:
            old_get = '''def _get_prompt(key: str):
    """(system, user_template) — spaeter DB (PbxPrompt), jetzt Fallback-Konstanten."""
    d = DEFAULT_PROMPTS.get(key, {'system': '', 'user': ''})
    try:
        from apps.abpe_email_studio.models import AiPrompt
        row = AiPrompt.objects.filter(key=key, aktiv=True).first()
        if row:
            return (
                row.system or d['system'],
                row.user_template or d['user'],
            )
    except Exception:
        pass
    return (d['system'], d['user'])'''
            new_block = patch.strip()
            if old_get in pbx:
                pbx = pbx.replace(old_get, new_block)
            else:
                # fallback: append get_prompt_config before class PbxAIResult
                pbx = pbx.replace(
                    '@dataclass\nclass PbxAIResult:',
                    patch.strip() + '\n\n\n@dataclass\nclass PbxAIResult:',
                )
        crm_pbx.write_text(pbx, encoding='utf-8')
        print('OK deepseek_api_pbx patched')
    else:
        print('= get_prompt_config already present')

    # 7) meetme api_deepseek_suggest — optional, wenn Marker gefunden
    mv = meetme_views.read_text(encoding='utf-8')
    if 'deepseek_raupe.full_pipeline' not in mv:
        old_fn = re.search(
            r'@extend_schema\(\s*\n\s*summary="DeepSeek-Vorschlag.*?\n'
            r'def api_deepseek_suggest\(request\):.*?\n'
            r'    return Response\(\{\'suggestion\': result\.text\}\)',
            mv,
            re.DOTALL,
        )
        if old_fn:
            new_fn = (PKG / 'patches' / 'meetme_api_deepseek_suggest.py').read_text(encoding='utf-8')
            new_fn = re.sub(r'^#.*\n', '', new_fn, flags=re.MULTILINE)
            mv = mv[: old_fn.start()] + new_fn.strip() + mv[old_fn.end() :]
            meetme_views.write_text(mv, encoding='utf-8')
            print('OK meetme views api_deepseek_suggest patched')
        else:
            print('WARN meetme api_deepseek_suggest — manuell patchen (patches/meetme_api_deepseek_suggest.py)')
    else:
        print('= meetme deepseek_raupe already patched')

    # 8) migrate + sync
    subprocess.run([sys.executable, 'manage.py', 'makemigrations', 'abpe_email_studio', '--name', 'ai_prompt'], cwd=backend, check=False)
    subprocess.run([sys.executable, 'manage.py', 'migrate', 'abpe_email_studio'], cwd=backend, check=False)
    subprocess.run([sys.executable, 'manage.py', 'sync_ai_prompts'], cwd=backend, check=False)
    print('\nFertig. Admin: /admin/ → KI-Prompts')


if __name__ == '__main__':
    main()
