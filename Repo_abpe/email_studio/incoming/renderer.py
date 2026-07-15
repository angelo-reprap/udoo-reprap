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

    def get_default_preview_vars(self, user=None) -> dict:
        """Beispieldaten für die Live-Vorschau im Editor."""
        now = timezone.now()
        vars = {
            'name':            'Max Mustermann',
            'first_name':      'Max',
            'last_name':       'Mustermann',
            'vorname':         'Max',
            'nachname':        'Mustermann',
            'email':           'max@example.de',
            'firma':           'Muster GmbH',
            'unternehmen':     'Muster GmbH',
            'termin_datum':    now.strftime('%d.%m.%Y'),
            'termin_zeit':     '14:00 Uhr',
            'termin_uhrzeit':  '14:00 Uhr',
            'raum':            'Meetingraum 3',
            'einwahl_info':    'Einwahl: +49 30 123456, PIN 4711',
            'teilnehmer_liste_html': (
                '<ul><li>Max Mustermann</li><li>Erika Musterfrau</li></ul>'
            ),
            'strasse':         'Musterstraße 1',
            'plz':             '12345',
            'ort':             'Musterstadt',
            'telefon':         '+49 123 456789',
            'link':            'https://abpe.win.abcona.info',
            'button_url':      'https://abpe.win.abcona.info',
            'button_text':     'Zum Portal',
            'cv_link':         'https://abpe.win.abcona.info/cv/beispiel',
            'cv_version':      'v3',
            'created_date':    now.strftime('%d.%m.%Y'),
            'task_ref':        'TASK-4711',
            'signature':       'Mit freundlichen Grüßen\nMax Mustermann\nmax@example.de',
            'signature_name':  'Max Mustermann',
            'berater_name':    'Tanja Groß',
            'kandidat_name':   'Max Mustermann',
            'betreff':         'Beispiel-Betreff',
        }
        vars.update(self._get_user_vars(user))
        if not vars.get('sender_name'):
            vars['sender_name'] = 'Max Mustermann'
        if not vars.get('sender_email'):
            vars['sender_email'] = 'max@example.de'
        return vars

    def merge_preview_variables(self, variables: dict = None, user=None) -> dict:
        return {**self.get_default_preview_vars(user), **(variables or {})}

    def _expand_placeholder_vars(self, variables: dict, *texts: str) -> dict:
        """Ergänzt fehlende Platzhalter aus dem Template-Text."""
        pattern = re.compile(r'\{(\w+)\}')
        found = set()
        for text in texts:
            if text:
                found.update(pattern.findall(text))
        defaults = self.get_default_preview_vars()
        expanded = dict(variables)
        for key in found:
            if key not in expanded:
                expanded[key] = defaults.get(key, f'[{key}]')
        return expanded

    def _resolve_preview_signature_html(
        self, template, all_vars: dict, user=None,
        signature_mode=None, signature_id=None, include_signature=None,
    ) -> str:
        from apps.abpe_email_studio.models import SignatureMode, EmailSignature
        from .services.signature import SignatureResolver

        if include_signature is False:
            return ''
        mode = signature_mode or template.signature_mode
        if mode == SignatureMode.NONE:
            return ''
        if include_signature is None and not template.include_signature:
            return ''

        if mode == SignatureMode.TEAM:
            html = (
                '<div style="margin-top:16px;">'
                '<p>Mit freundlichen Grüßen<br><strong>abcona e. K. Team</strong></p>'
                '</div>'
            )
            return self._render(html, all_vars)

        if mode == SignatureMode.USER:
            sig = None
            if user and user.email:
                sig = EmailSignature.objects.filter(
                    sender_account__email=user.email
                ).first()
            if not sig:
                sig = SignatureResolver().resolve(template, user)
            if sig and sig.html_body:
                return self._render(sig.html_body, all_vars)
            html = (
                '<div style="margin-top:16px;">'
                '<p>Mit freundlichen Grüßen<br><strong>{sender_name}</strong>'
                '<br>{sender_email}</p></div>'
            )
            return self._render(html, all_vars)

        if mode == SignatureMode.FIXED:
            sig = None
            if signature_id:
                sig = EmailSignature.objects.filter(pk=signature_id).first()
            if not sig:
                sig = template.signature
            if sig and sig.html_body:
                sig_vars = {**all_vars, 'signature_name': sig.name}
                return self._render(sig.html_body, sig_vars)
            return ''

        if mode == SignatureMode.DYNAMIC:
            sig = SignatureResolver().resolve(template, user)
            if sig and sig.html_body:
                return self._render(sig.html_body, all_vars)
            placeholder = (
                '<div style="margin-top:16px;color:#888;">'
                '<p>{signature}</p></div>'
            )
            return self._render(placeholder, all_vars)

        return ''

    def render_preview(
        self, template, variables: dict = None, user=None, *,
        html_body=None, subject=None, text_body=None,
        signature_mode=None, signature_id=None, include_signature=None,
    ) -> dict:
        """Rendert Editor-Vorschau mit aktuellem HTML und Beispieldaten."""
        from apps.abpe_email_studio.models import SignatureMode

        merged = self.merge_preview_variables(variables, user)
        subj_src = subject if subject is not None else template.subject
        html_src = html_body if html_body is not None else template.html_body
        txt_src = text_body if text_body is not None else (template.text_body or '')

        merged = self._expand_placeholder_vars(merged, subj_src or '', html_src or '', txt_src or '')
        all_vars = {
            **self._get_system_vars(),
            **merged,
            'subject': subj_src or '',
        }

        html = html_src
        html = self._resolve_modules(html, all_vars)
        html = self._render(html, all_vars)

        sig_html = self._resolve_preview_signature_html(
            template, all_vars, user,
            signature_mode=signature_mode,
            signature_id=signature_id,
            include_signature=include_signature,
        )
        mode = signature_mode or template.signature_mode
        if sig_html and mode in (SignatureMode.FIXED, SignatureMode.DYNAMIC):
            html = html + sig_html

        vars_for_subj = {k: v for k, v in all_vars.items() if k != 'subject'}
        rendered_subject = self.render_subject(subj_src or '', vars_for_subj)

        if txt_src:
            txt = self._resolve_modules_txt(txt_src, all_vars)
            rendered_text = self._render(txt, all_vars)
        else:
            rendered_text = re.sub(r'<[^>]+>', '\n', html)
            rendered_text = re.sub(r'\n{3,}', '\n\n', rendered_text).strip()

        if sig_html and mode in (SignatureMode.FIXED, SignatureMode.DYNAMIC):
            sig_text = re.sub(r'<[^>]+>', '', sig_html).strip()
            if sig_text:
                rendered_text = f'{rendered_text}\n\n{sig_text}' if rendered_text else sig_text

        return {
            'subject': rendered_subject,
            'html':    html,
            'text':    rendered_text,
        }

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
