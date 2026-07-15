#!/usr/bin/env python3
"""
Sofort-Fix auf ucs5 — braucht nur Python, kein git pull.

  cd /opt/abpe/backend
  python abpe_deepseek_raupe/fix_raupe_now_ucs5.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BACKEND = Path('/opt/abpe/backend')
PKG = Path(__file__).resolve().parent

DEEPSEEK_RAUPE = PKG / 'services' / 'deepseek_raupe.py'
SUGGEST_WITH_KEY = PKG / 'patches' / 'deepseek_api_pbx_suggest_with_key.py'

SUGGEST_WITH_KEY_INLINE = '''
    def suggest_with_key(
        self,
        text: str,
        prompt_key: str,
        instruction: Optional[str] = None,
    ) -> PbxAIResult:
        """DeepSeek mit beliebigem AiPrompt-Key (DB oder DEFAULT_PROMPTS)."""
        cfg = get_prompt_config(prompt_key)
        instr = (instruction or cfg.get('instruction_default') or '').strip() or 'Formuliere den Text um.'
        system = cfg.get('system') or ''
        user_tpl = cfg.get('user_template') or '[[INSTRUCTION]]\\n\\n[[TEXT]]'
        user_prompt = _fill(user_tpl, INSTRUCTION=instr, TEXT=text)
        t0 = time.time()
        if not self.is_available():
            return PbxAIResult(success=False, error='DeepSeek API-Key fehlt', processing_time=time.time() - t0)
        try:
            out = self._chat(system, user_prompt)
            if isinstance(out, PbxAIResult):
                out.processing_time = time.time() - t0
                return out
            if isinstance(out, tuple):
                if len(out) >= 2 and isinstance(out[0], bool):
                    return PbxAIResult(
                        success=out[0],
                        text=(out[1] or '') if out[0] else '',
                        error=out[2] if len(out) > 2 else None,
                        processing_time=time.time() - t0,
                    )
                content = (out[0] or '') if out else ''
                txt = str(content).strip()
                return PbxAIResult(success=bool(txt), text=txt, processing_time=time.time() - t0)
            if isinstance(out, str):
                txt = out.strip()
                return PbxAIResult(success=bool(txt), text=txt, processing_time=time.time() - t0)
            return PbxAIResult(success=False, error='DeepSeek: unbekanntes Antwortformat', processing_time=time.time() - t0)
        except Exception as exc:
            logger.exception('suggest_with_key(%s) fehlgeschlagen', prompt_key)
            return PbxAIResult(success=False, error=str(exc), processing_time=time.time() - t0)
'''.strip()


def backend_root() -> Path:
    root = BACKEND if BACKEND.exists() else Path.cwd()
    if not (root / 'manage.py').exists():
        print('FEHLER: manage.py nicht gefunden — bitte cd /opt/abpe/backend')
        sys.exit(1)
    return root


def fix_raupe(root: Path) -> None:
    dst = root / 'apps/abpe_email_studio/services/deepseek_raupe.py'
    src = DEEPSEEK_RAUPE if DEEPSEEK_RAUPE.exists() else None
    text = dst.read_text(encoding='utf-8')

    if '_coerce_pbx_result' in text and '_chat(system' not in text:
        print('= deepseek_raupe.py bereits gefixt')
        return

    if src and '_coerce_pbx_result' in src.read_text(encoding='utf-8'):
        dst.write_text(src.read_text(encoding='utf-8'), encoding='utf-8')
        print('OK deepseek_raupe.py ersetzt aus Paket')
        return

    # Inline-Patch falls altes Paket auf dem Server
    if '_coerce_pbx_result' not in text:
        helper = '''
def _coerce_pbx_result(result):
    """_chat() liefert oft (bool, text, err) — einheitlich als PbxAIResult."""
    from apps.abpe_crm.services.deepseek_api_pbx import PbxAIResult
    if isinstance(result, PbxAIResult):
        return result
    if isinstance(result, tuple):
        if len(result) >= 2 and isinstance(result[0], bool):
            return PbxAIResult(
                success=result[0],
                text=(result[1] or '') if result[0] else '',
                error=result[2] if len(result) > 2 else None,
            )
        content = (result[0] or '') if result else ''
        txt = str(content).strip()
        return PbxAIResult(success=bool(txt), text=txt)
    if isinstance(result, str):
        txt = result.strip()
        return PbxAIResult(success=bool(txt), text=txt)
    if hasattr(result, 'success'):
        return result
    return PbxAIResult(success=False, error='DeepSeek: unbekanntes Antwortformat')

'''
        text = text.replace('\nclass DeepSeekRaupe:', helper + '\nclass DeepSeekRaupe:', 1)

    new_suggest = '''    def suggest(
        self,
        text: str,
        *,
        prompt_key: str = 'summarize',
        instruction: Optional[str] = None,
    ):
        from apps.abpe_crm.services.deepseek_api_pbx import deepseek_pbx
        if prompt_key == 'summarize':
            from apps.abpe_crm.services.deepseek_api_pbx import get_prompt_config
            instr = instruction or get_prompt_config('summarize').get('instruction_default') or 'Fasse kurz zusammen.'
            return _coerce_pbx_result(deepseek_pbx.summarize(text, instr))
        if hasattr(deepseek_pbx, 'suggest_with_key'):
            return _coerce_pbx_result(deepseek_pbx.suggest_with_key(text, prompt_key, instruction))
        return _coerce_pbx_result(deepseek_pbx.summarize(text, instruction or 'Formuliere den Text um.'))
'''
    text = re.sub(
        r'    def suggest\(.*?return deepseek_pbx\._chat\(system, user_prompt\)',
        new_suggest.rstrip(),
        text,
        count=1,
        flags=re.DOTALL,
    )
    if '_chat(system' in text:
        print('FEHLER: suggest()-Patch fehlgeschlagen — bitte Paket aktualisieren')
        sys.exit(1)
    dst.write_text(text, encoding='utf-8')
    print('OK deepseek_raupe.py inline gepatcht')


def fix_pbx(root: Path) -> None:
    pbx = root / 'apps/abpe_crm/services/deepseek_api_pbx.py'
    text = pbx.read_text(encoding='utf-8')
    if 'def suggest_with_key' in text:
        print('= suggest_with_key bereits vorhanden')
        return

    if SUGGEST_WITH_KEY.exists():
        snippet = re.sub(r'^#.*\n', '', SUGGEST_WITH_KEY.read_text(encoding='utf-8'), flags=re.MULTILINE).strip()
    else:
        snippet = SUGGEST_WITH_KEY_INLINE

    m_sum = re.search(
        r'(    def summarize\(self, text: str.*?)(\n    def \w+\()',
        text,
        re.DOTALL,
    )
    if not m_sum:
        print('WARNUNG: summarize nicht gefunden — suggest_with_key übersprungen (summarize-Fallback aktiv)')
        return

    text = text[: m_sum.end(1)] + '\n\n' + snippet + '\n' + text[m_sum.start(2):]
    pbx.write_text(text, encoding='utf-8')
    print('OK deepseek_api_pbx.py suggest_with_key eingefügt')


def main():
    root = backend_root()
    fix_raupe(root)
    fix_pbx(root)
    print()
    print('Fertig. Bitte testen:')
    print('  python manage.py shell -c "from apps.abpe_email_studio.services.deepseek_raupe import deepseek_raupe; print(deepseek_raupe.full_pipeline(\'Test\', {\'name\':\'Max\'}, prompt_key=\'meetme_email\'))"')
    print('Dann: supervisorctl restart abpe-django')


if __name__ == '__main__':
    main()
