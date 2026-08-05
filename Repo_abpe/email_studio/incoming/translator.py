"""
ABpE Email Studio — Translation Service
=========================================
Übersetzt EmailTemplate HTML/TXT/Subject in beliebige Sprachen.
Nutzt Deepseek API (identisch mit i18n_translator.py).
10 parallele Worker — ein Worker pro Sprache.

Verwendung:
    from apps.abpe_email_studio.services.translator import EmailTranslator
    EmailTranslator.translate_template(template, langs=['en', 'fr'])
    EmailTranslator.auto_translate(template)  # default_languages aus settings.json
"""
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import requests

log = logging.getLogger('abpe_email_studio.translator')

SETTINGS_PATH = Path('/opt/abpe/backend/settings.json')
LANG_MAP_PATH = Path('/opt/abpe/backend/apps/abpe_ui/bin/lang_map.json')


def _load_settings() -> dict:
    if SETTINGS_PATH.exists():
        return json.loads(SETTINGS_PATH.read_text())
    return {}


def _load_lang_map() -> dict:
    if LANG_MAP_PATH.exists():
        return json.loads(LANG_MAP_PATH.read_text())
    return {}


def _get_api_key() -> str | None:
    cfg = _load_settings()
    return (cfg.get('ai_models', {}).get('deepseek', {}).get('api_key') or
            cfg.get('api_keys', {}).get('deepseek'))


def _deepseek_translate(text: str, source_lang: str, target_lang: str,
                         content_type: str = 'html') -> str:
    """
    Übersetzt einen Text via Deepseek API.
    content_type: 'html' | 'text' | 'subject'
    """
    api_key = _get_api_key()
    if not api_key:
        raise ValueError('Kein Deepseek API-Key in settings.json gefunden')

    lang_map  = _load_lang_map()
    src_name  = lang_map.get(source_lang, {}).get('name', source_lang)
    tgt_name  = lang_map.get(target_lang, {}).get('name', target_lang)

    if content_type == 'html':
        system = (
            f'You are a professional email translator. '
            f'Translate the HTML email body from {src_name} to {tgt_name}. '
            f'Keep all HTML tags, CSS styles, and {"{variable}"} placeholders unchanged. '
            f'Only translate visible text content. Return only the translated HTML, nothing else.'
        )
    elif content_type == 'subject':
        system = (
            f'Translate this email subject line from {src_name} to {tgt_name}. '
            f'Keep all {"{variable}"} placeholders unchanged. '
            f'Return only the translated subject, nothing else.'
        )
    else:
        system = (
            f'Translate this plain text email from {src_name} to {tgt_name}. '
            f'Keep all {"{variable}"} placeholders unchanged. '
            f'Return only the translated text, nothing else.'
        )

    cfg     = _load_settings()
    ds_cfg  = cfg.get('ai_models', {}).get('deepseek', {})
    model   = ds_cfg.get('model', 'deepseek-chat')
    timeout = ds_cfg.get('timeout', 60)

    resp = requests.post(
        'https://api.deepseek.com/v1/chat/completions',
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type':  'application/json',
        },
        json={
            'model':       model,
            'temperature': 0.1,
            'messages': [
                {'role': 'system',  'content': system},
                {'role': 'user',    'content': text},
            ],
        },
        timeout=timeout,
        verify=False,
    )
    resp.raise_for_status()
    return resp.json()['choices'][0]['message']['content'].strip()


class EmailTranslator:

    @staticmethod
    def default_languages() -> list[str]:
        cfg = _load_settings()
        return cfg.get('email_translation', {}).get('default_languages', ['de', 'en'])

    @staticmethod
    def available_languages() -> dict:
        """Gibt alle verfügbaren Sprachen aus lang_map.json zurück."""
        return _load_lang_map()

    @staticmethod
    def translate_template(template, langs: list[str],
                            force: bool = False) -> dict:
        """
        Übersetzt ein EmailTemplate in die angegebenen Sprachen.
        Erstellt/aktualisiert EmailTemplateTranslation Objekte.
        Gibt {lang: {success, error}} zurück.
        """
        from apps.abpe_email_studio.models import EmailTemplateTranslation

        results = {}
        ref_lang = _load_settings().get('email_translation', {}).get('ref_lang', 'de')

        def _translate_one(lang: str) -> tuple[str, dict]:
            try:
                existing = EmailTemplateTranslation.objects.filter(
                    template=template, lang=lang
                ).first()

                if existing and not force:
                    return lang, {'success': True, 'skipped': True,
                                  'note': 'Bereits vorhanden'}

                log.info(f'Übersetze {template.identifier} → {lang}')

                subject   = _deepseek_translate(
                    template.subject, ref_lang, lang, 'subject'
                )
                html_body = _deepseek_translate(
                    template.html_body, ref_lang, lang, 'html'
                )
                text_body = ''
                if template.text_body:
                    text_body = _deepseek_translate(
                        template.text_body, ref_lang, lang, 'text'
                    )

                if existing:
                    existing.subject   = subject
                    existing.html_body = html_body
                    existing.text_body = text_body
                    existing.save()
                else:
                    EmailTemplateTranslation.objects.create(
                        template  = template,
                        lang      = lang,
                        subject   = subject,
                        html_body = html_body,
                        text_body = text_body,
                    )

                log.info(f'✓ {template.identifier} → {lang} übersetzt')
                return lang, {'success': True}

            except Exception as e:
                log.error(f'Übersetzung {template.identifier} → {lang} fehlgeschlagen: {e}')
                return lang, {'success': False, 'error': str(e)}

        # Ref-Sprache überspringen
        translate_langs = [l for l in langs if l != ref_lang]

        cfg         = _load_settings()
        max_workers = cfg.get('email_translation', {}).get('parallel_workers', 10)

        with ThreadPoolExecutor(max_workers=min(max_workers, len(translate_langs) or 1)) as pool:
            futures = {pool.submit(_translate_one, lang): lang
                       for lang in translate_langs}
            for future in as_completed(futures):
                lang, result = future.result()
                results[lang] = result

        return results

    @staticmethod
    def auto_translate(template, force: bool = False) -> dict:
        """Übersetzt in alle default_languages aus settings.json."""
        langs = EmailTranslator.default_languages()
        return EmailTranslator.translate_template(template, langs, force)

    @staticmethod
    def get_translation(template, lang: str):
        """Gibt eine Übersetzung zurück oder None."""
        from apps.abpe_email_studio.models import EmailTemplateTranslation
        return EmailTemplateTranslation.objects.filter(
            template=template, lang=lang
        ).first()

    @staticmethod
    def detect_lang(text: str) -> str:
        """
        Erkennt die Sprache eines Textes via Deepseek.
        Gibt ISO-Code zurück (z.B. 'en', 'de').
        Fallback: 'de'
        """
        try:
            api_key = _get_api_key()
            if not api_key:
                return 'de'
            resp = requests.post(
                'https://api.deepseek.com/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type':  'application/json',
                },
                json={
                    'model':    'deepseek-chat',
                    'messages': [{
                        'role':    'user',
                        'content': (
                            f'Detect the language of this text and respond with ONLY '
                            f'the ISO 639-1 code (e.g. "en", "de", "fr"). Text: {text[:200]}'
                        )
                    }],
                    'temperature': 0.0,
                },
                timeout=15,
                verify=False,
            )
            code = resp.json()['choices'][0]['message']['content'].strip().lower()[:2]
            return code if len(code) == 2 else 'de'
        except Exception as e:
            log.warning(f'Sprach-Erkennung fehlgeschlagen: {e}')
            return 'de'
