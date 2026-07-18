"""
ABpE Email Studio — Template Renderer
"""
import re
import json
import logging
from datetime import timedelta
from pathlib import Path
from django.utils import timezone

log = logging.getLogger('abpe_email_studio.renderer')


class EmailRenderer:

    def _get_system_vars(self) -> dict:
        now = timezone.now()
        out = {
            'portal_url': 'https://abpe.win.abcona.info',
            'date':       now.strftime('%d.%m.%Y'),
            'year':       str(now.year),
        }
        try:
            from .system_status import collect_system_status
            out.update(collect_system_status(use_cache=True))
        except Exception as exc:
            log.debug('system_status unavailable: %s', exc)
        return out

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

    def _resolve_modules(
        self, html: str, variables: dict, template=None, user=None,
        signature_mode=None, signature_id=None, include_signature=None,
    ) -> str:
        """Ersetzt {{block:identifier}} durch Modul-HTML."""
        from apps.abpe_email_studio.models import EmailModule
        pattern = re.compile(r'\{\{block:([\w_-]+)\}\}')

        def replace_module(match):
            identifier = match.group(1)
            if identifier == 'signature' and template is not None:
                return self._resolve_signature_html(
                    template, variables, user,
                    signature_mode=signature_mode,
                    signature_id=signature_id,
                    include_signature=include_signature,
                    dynamic_sig_id=variables.get('signature'),
                )
            module = EmailModule.objects.filter(
                identifier=identifier, is_active=True
            ).first()
            if module:
                return self._render(module.html_body, variables)
            log.warning(f'Modul nicht gefunden: {identifier}')
            return f'<!-- Modul nicht gefunden: {identifier} -->'

        return pattern.sub(replace_module, html)

    def _resolve_modules_txt(
        self, text: str, variables: dict, template=None, user=None,
        signature_mode=None, signature_id=None, include_signature=None,
    ) -> str:
        """Ersetzt {{block:identifier}} durch Modul-TXT."""
        from apps.abpe_email_studio.models import EmailModule
        pattern = re.compile(r'\{\{block:([\w_-]+)\}\}')

        def replace_module(match):
            identifier = match.group(1)
            if identifier == 'signature' and template is not None:
                sig_html = self._resolve_signature_html(
                    template, variables, user,
                    signature_mode=signature_mode,
                    signature_id=signature_id,
                    include_signature=include_signature,
                    dynamic_sig_id=variables.get('signature'),
                )
                return re.sub(r'<[^>]+>', '', sig_html).strip()
            module = EmailModule.objects.filter(
                identifier=identifier, is_active=True
            ).first()
            if module and module.text_body:
                return self._render(module.text_body, variables)
            return ''

        return pattern.sub(replace_module, text)

    def _has_signature_block(self, *texts: str) -> bool:
        return any('{{block:signature}}' in (t or '') for t in texts)

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
        html = self._resolve_modules(
            html, all_vars, template=template, user=user,
            signature_mode=template.signature_mode,
            signature_id=template.signature_id,
            include_signature=template.include_signature,
        )
        html = self._render(html, all_vars)

        if not self._has_signature_block(template.html_body):
            sig = self._resolve_signature_html(
                template, all_vars, user,
                signature_mode=template.signature_mode,
                signature_id=template.signature_id,
                include_signature=template.include_signature,
                dynamic_sig_id=variables.get('signature'),
            )
            if sig:
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
            text = self._resolve_modules_txt(
                text, all_vars, template=template, user=user,
                signature_mode=template.signature_mode,
                signature_id=template.signature_id,
                include_signature=template.include_signature,
            )
            return self._render(text, all_vars)
        html = self._resolve_modules(
            template.html_body, all_vars, template=template, user=user,
            signature_mode=template.signature_mode,
            signature_id=template.signature_id,
            include_signature=template.include_signature,
        )
        text = re.sub(r'<[^>]+>', '', html)
        if not self._has_signature_block(template.html_body, template.text_body):
            sig = self._resolve_signature_html(
                template, all_vars, user,
                signature_mode=template.signature_mode,
                signature_id=template.signature_id,
                include_signature=template.include_signature,
                dynamic_sig_id=variables.get('signature'),
            )
            if sig:
                sig_txt = re.sub(r'<[^>]+>', '', sig).strip()
                if sig_txt:
                    text = f'{text}\n\n{sig_txt}' if text else sig_txt
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
            'teilnehmer_liste': 'Max Mustermann, Erika Musterfrau',
            'vertretung_name':     'Erika Musterfrau',
            'vertretung_email':    'erika.musterfrau@abcona.de',
            'vertretung_telefon':  '+49 171 1234567',
            'mobil_nummer':        '+49 171 9876543',
            'abwesenheit_von':     now.strftime('%d.%m.%Y'),
            'abwesenheit_bis':     (now + timedelta(days=5)).strftime('%d.%m.%Y'),
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

    def _resolve_signature_html(
        self, template, all_vars: dict, user=None,
        signature_mode=None, signature_id=None, include_signature=None,
        dynamic_sig_id=None,
    ) -> str:
        from apps.abpe_email_studio.models import SignatureMode, EmailSignature
        from .signature import SignatureResolver

        if include_signature is False:
            return ''
        mode = signature_mode or template.signature_mode
        if mode == SignatureMode.NONE:
            return ''
        if include_signature is None and not template.include_signature:
            return ''

        if mode == SignatureMode.TEAM:
            return self._render(self._get_team_signature_html(), all_vars)

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
            sig = None
            if dynamic_sig_id:
                sig = EmailSignature.objects.filter(
                    identifier=dynamic_sig_id
                ).first()
                if not sig and str(dynamic_sig_id).isdigit():
                    sig = EmailSignature.objects.filter(
                        pk=int(dynamic_sig_id)
                    ).first()
            if not sig:
                sig = SignatureResolver().resolve(template, user)
            if sig and sig.html_body:
                return self._render(sig.html_body, all_vars)
            placeholder = (
                '<div style="margin-top:16px;color:#888;">'
                '<p>{signature}</p></div>'
            )
            return self._render(placeholder, all_vars)

        return ''

    TEAM_SIGNATURE_FALLBACK = (
        '<div style="margin-top:20px;font-family:Arial,Helvetica,sans-serif;font-size:13px;'
        'line-height:1.5;color:#333;">'
        '<p style="margin:0 0 4px 0;">Mit freundlichen Grüßen</p>'
        '<p style="margin:0 0 8px 0;"><strong>Ihr abcona e. K. Team</strong></p>'
        '<p style="margin:0 0 4px 0;font-size:12px;">'
        'E-Mail: <a href="mailto:info@abcona.de" style="color:#163258;">info@abcona.de</a><br>'
        'Telefon: +49 0 6171 8867 10</p>'
        '<p style="margin:12px 0 0 0;font-size:10px;color:#666;line-height:1.4;">'
        '<strong>abcona e. K.</strong> | active business consulting agency<br>'
        'Bornhohl 26 | D-61449 Steinbach/Ts.<br>'
        'USt-ID: DE813519516 | Amtsgericht: Bad Homburg v.d.H. HRA 3662<br>'
        'Inhaber: Angelo Malaguarnera</p></div>'
    )

    def _get_team_signature_html(self) -> str:
        """Team-Signatur aus DB (identifier abcona_team) oder Fallback."""
        from apps.abpe_email_studio.models import EmailSignature
        for ident in ('abcona_team', 'team', 'general_team'):
            sig = EmailSignature.objects.filter(identifier=ident).first()
            if sig and sig.html_body:
                return sig.html_body
        sig = EmailSignature.objects.filter(
            name__icontains='team', is_public=True
        ).first()
        if sig and sig.html_body:
            return sig.html_body
        return self.TEAM_SIGNATURE_FALLBACK

    def render_preview(
        self, template, variables: dict = None, user=None, *,
        html_body=None, subject=None, text_body=None,
        signature_mode=None, signature_id=None, include_signature=None,
    ) -> dict:
        """Rendert Editor-Vorschau mit aktuellem HTML und Beispieldaten."""
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
        html = self._resolve_modules(
            html, all_vars, template=template, user=user,
            signature_mode=signature_mode,
            signature_id=signature_id,
            include_signature=include_signature,
        )
        html = self._render(html, all_vars)

        if not self._has_signature_block(html_src):
            sig_html = self._resolve_signature_html(
                template, all_vars, user,
                signature_mode=signature_mode,
                signature_id=signature_id,
                include_signature=include_signature,
            )
            if sig_html:
                html = html + sig_html

        vars_for_subj = {k: v for k, v in all_vars.items() if k != 'subject'}
        rendered_subject = self.render_subject(subj_src or '', vars_for_subj)

        if txt_src:
            txt = self._resolve_modules_txt(
                txt_src, all_vars, template=template, user=user,
                signature_mode=signature_mode,
                signature_id=signature_id,
                include_signature=include_signature,
            )
            rendered_text = self._render(txt, all_vars)
        else:
            rendered_text = re.sub(r'<[^>]+>', '\n', html)
            rendered_text = re.sub(r'\n{3,}', '\n\n', rendered_text).strip()

        if not self._has_signature_block(html_src, txt_src):
            sig_html = self._resolve_signature_html(
                template, all_vars, user,
                signature_mode=signature_mode,
                signature_id=signature_id,
                include_signature=include_signature,
            )
            if sig_html:
                sig_text = re.sub(r'<[^>]+>', '', sig_html).strip()
                if sig_text:
                    rendered_text = (
                        f'{rendered_text}\n\n{sig_text}' if rendered_text else sig_text
                    )

        return {
            'subject': rendered_subject,
            'html':    self._strip_scripts(html),
            'text':    rendered_text,
        }

    def _strip_scripts(self, html: str) -> str:
        if not html:
            return ''
        html = re.sub(r'<script\b[^>]*>[\s\S]*?</script>', '', html, flags=re.I)
        return re.sub(r'<script\b[^>]*\/>', '', html, flags=re.I)

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
