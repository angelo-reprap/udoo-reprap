"""
ABpE Email Studio — Template Renderer
"""
import re
import json
import logging
from pathlib import Path
from django.utils import timezone

log = logging.getLogger('abpe_email_studio.renderer')


class EmailRenderer:

    def _get_system_vars(self) -> dict:
        now = timezone.now()
        return {
            'portal_url': 'https://abpe.win.abcona.info',
            'date':       now.strftime('%d.%m.%Y'),
            'year':       str(now.year),
        }

    def _get_user_vars(self, user=None) -> dict:
        if not user:
            return {}
        name = f'{user.first_name} {user.last_name}'.strip() or user.username
        return {
            'sender_name':  name,
            'sender_email': user.email or '',
            'reply_to':     user.email or '',
        }

    def _render(self, text: str, variables: dict) -> str:
        for key, value in variables.items():
            text = text.replace(f'{{{key}}}', str(value) if value else '')
        return text

    def _resolve_modules(self, html: str, variables: dict) -> str:
        """Ersetzt {{block:identifier}} durch Modul-HTML."""
        from apps.abpe_email_studio.models import EmailModule
        pattern = re.compile(r'\{\{block:([\w_-]+)\}\}')
        def replace_module(match):
            identifier = match.group(1)
            module = EmailModule.objects.filter(
                identifier=identifier, is_active=True
            ).first()
            if module:
                return self._render(module.html_body, variables)
            log.warning(f'Modul nicht gefunden: {identifier}')
            return f'<!-- Modul nicht gefunden: {identifier} -->'
        return pattern.sub(replace_module, html)

    def _resolve_modules_txt(self, text: str, variables: dict) -> str:
        """Ersetzt {{block:identifier}} durch Modul-TXT."""
        from apps.abpe_email_studio.models import EmailModule
        pattern = re.compile(r'\{\{block:([\w_-]+)\}\}')
        def replace_module(match):
            identifier = match.group(1)
            module = EmailModule.objects.filter(
                identifier=identifier, is_active=True
            ).first()
            if module and module.text_body:
                return self._render(module.text_body, variables)
            return ''
        return pattern.sub(replace_module, text)

    def render_subject(self, subject: str, variables: dict) -> str:
        all_vars = {**self._get_system_vars(), **variables}
        return self._render(subject, all_vars)

    def render_html(self, template, variables: dict, user=None) -> str:
        all_vars = {
            **self._get_system_vars(),
            **self._get_user_vars(user),
            'subject': template.subject or '',
            **variables,
        }
        html = template.html_body
        html = self._resolve_modules(html, all_vars)
        html = self._render(html, all_vars)
        if template.include_signature and template.signature:
            sig = self._render(template.signature.html_body, all_vars)
            html = html + sig
        return html

    def render_text(self, template, variables: dict, user=None) -> str:
        all_vars = {
            **self._get_system_vars(),
            **self._get_user_vars(user),
            'subject': template.subject or '',
            **variables,
        }
        text = template.text_body or ''
        if text:
            text = self._resolve_modules_txt(text, all_vars)
            return self._render(text, all_vars)
        # Fallback: HTML-Strip
        html = self._resolve_modules(template.html_body, all_vars)
        text = re.sub(r'<[^>]+>', '', html)
        return self._render(text, all_vars)

    def html_to_text_via_deepseek(self, html: str) -> str:
        """Konvertiert HTML zu sauberem Plaintext via Deepseek."""
        import requests
        settings_path = Path('/opt/abpe/backend/settings.json')
        try:
            api_key = json.loads(settings_path.read_text()).get(
                'ai_models', {}).get('deepseek', {}).get('api_key', '')
        except Exception:
            api_key = ''

        if not api_key:
            return re.sub(r'<[^>]+>', '', html)

        try:
            resp = requests.post(
                'https://api.deepseek.com/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type':  'application/json',
                },
                json={
                    'model':       'deepseek-chat',
                    'temperature': 0.1,
                    'messages': [{
                        'role':    'system',
                        'content': (
                            'Convert this HTML email to clean plain text. '
                            'Keep all {variable} placeholders unchanged. '
                            'Use proper line breaks and formatting. '
                            'No HTML tags. Return only the plain text, nothing else.'
                        )
                    }, {
                        'role':    'user',
                        'content': html
                    }]
                },
                timeout=30,
                verify=False
            )
            return resp.json()['choices'][0]['message']['content'].strip()
        except Exception as e:
            log.warning(f'Deepseek TXT-Generierung fehlgeschlagen: {e}')
            return re.sub(r'<[^>]+>', '', html)
