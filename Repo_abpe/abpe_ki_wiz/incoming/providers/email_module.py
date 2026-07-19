"""
KI-Wizard: Email-Modul erzeugen oder erweitern (wizard_id=email_module).

Erzeugt ein einzelnes EmailModule-Fragment (html_body/text_body),
kein vollständiges Mail-Template.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from apps.abpe_ki_wiz.providers.base import ValidationResult, WizardDomainProvider
from apps.abpe_ki_wiz.registry import register
from apps.abpe_ki_wiz.services.validator import (
    extract_vars,
    validate_email_module_output,
)

log = logging.getLogger('abpe_ki_wiz.email_module')

_QUESTIONS_PATH = Path(__file__).resolve().parent.parent / 'questions' / 'email_module.json'

_HEADER_KW = re.compile(r'header|kopf|banner|marke|logo', re.I)
_FOOTER_KW = re.compile(r'footer|impressum|fu[sß]zeile', re.I)
_BTN_KW = re.compile(r'button|cta|aufruf|klick', re.I)
_SIG_KW = re.compile(r'signatur|gr[uü][sß]', re.I)
_ADDR_KW = re.compile(
    r'adresse|kontakt|www\.|telefon|tel\.|e-?mail|info@|06171|abcona\.de',
    re.I,
)


def _load_questions() -> list[dict[str, Any]]:
    try:
        return json.loads(_QUESTIONS_PATH.read_text(encoding='utf-8'))
    except Exception as exc:
        log.warning('email_module questions nicht geladen: %s', exc)
        return []


def _slug(text: str, fallback: str = 'new_module') -> str:
    s = re.sub(r'[^a-z0-9]+', '_', (text or '').lower()).strip('_')
    return (s[:60] or fallback)


class EmailModuleWizardProvider(WizardDomainProvider):
    wizard_id = 'email_module'
    title = 'E-Mail-Modul mit KI'
    description = 'Neues Modul bauen oder bestehendes Modul erweitern (MCID-konform).'

    def get_catalog(self, **kwargs) -> dict[str, Any]:
        module_types = [
            {'value': 'HEADER', 'label': 'Header'},
            {'value': 'SECTION', 'label': 'Abschnitt'},
            {'value': 'BUTTON', 'label': 'Button'},
            {'value': 'FOOTER', 'label': 'Footer'},
            {'value': 'SIGNATURE', 'label': 'Signatur'},
            {'value': 'DISCLAIMER', 'label': 'Disclaimer'},
        ]
        try:
            from apps.abpe_email_studio.models import ModuleType
            module_types = [{'value': v, 'label': l} for v, l in ModuleType.choices]
        except Exception:
            pass

        company = {
            'name': 'abcona e. K.',
            'web': 'https://www.abcona.de',
            'web_label': 'www.abcona.de',
            'phone': '06171 886710',
            'phone_tel': '+496171886710',
            'email': 'info@abcona.de',
            'brand_color': '#163258',
            'info_bg': '#e8f0f8',
            'text_color': '#333333',
        }

        return {
            'module_types': module_types,
            'company': company,
            'layout_rules': {
                'font': 'Arial',
                'font_size_px': 14,
                'font_size_small_px': 12,
                'font_size_header_px': 18,
                'text_color': '#333333',
                'brand_color': '#163258',
                'width_px': 600,
                'no_border_radius': True,
                'tables_only_layout': True,
                'inline_css_only': True,
                'output': 'single_module_fragment',
                'ci_notes': (
                    'Du erzeugst EIN Email-Modul (Fragment), keine komplette Mail. '
                    'Kein {{block:…}} verschachteln außer wenn Briefing es verlangt. '
                    'Nur erlaubte Tags (table/tr/td/a/span/p/br/…). '
                    'Arial, Marke #163258, Body 14px, Meta 12px, Header-Text 18px bold. '
                    'Kein border-radius, kein flex/grid. '
                    'Firmendaten NUR aus CONTEXT.catalog.company — nicht erfinden.'
                ),
            },
            'variables': [
                {'name': 'button_text', 'example': 'Zum Portal'},
                {'name': 'button_url', 'example': 'https://abpe.win.abcona.info'},
                {'name': 'sender_name', 'example': 'Max Mustermann'},
                {'name': 'sender_email', 'example': 'max@example.de'},
                {'name': 'name', 'example': 'Max Mustermann'},
            ],
        }

    def get_question_catalog(self) -> list[dict[str, Any]]:
        return _load_questions()

    def resolve_questions(
        self,
        briefing: str,
        answers: dict[str, Any] | None = None,
        analyze_result: dict[str, Any] | None = None,
    ) -> list[str]:
        answers = answers or {}
        pending: list[str] = []
        for qid in ('T1', 'M1'):
            if answers.get(qid) in (None, '', []):
                pending.append(qid)
        # C1 nur wenn Typ passt und noch offen
        t1 = answers.get('T1') or (analyze_result or {}).get('module_type_hint')
        if t1 in ('HEADER', 'FOOTER', 'SECTION') and answers.get('C1') in (None, '', []):
            if _ADDR_KW.search(briefing or '') or t1 == 'HEADER':
                pending.append('C1')
        return pending

    def build_checklist(self, answers: dict[str, Any]) -> list[str]:
        t1 = answers.get('T1') or 'SECTION'
        items = [
            'Nur ein Modul-Fragment (kein vollständiges Mail-Template)',
            'MCID: Tabellen + inline CSS, Arial, #163258 / #333333',
            'Kein border-radius, kein flex/grid, kein <script>/<style>',
            f'module_type = {t1}',
            'identifier snake_case, eindeutig',
            'text_body 1:1 sichtbarer Text aus HTML',
        ]
        if answers.get('C1') == 'yes':
            items.append(
                'Kontaktdaten aus catalog.company: www.abcona.de · 06171 886710 · info@abcona.de'
            )
        if answers.get('M1') == 'extend':
            items.append('Bestehendes HTML aus INSTRUCTION behalten und gezielt erweitern')
        return items

    def default_meta_suggestions(
        self,
        briefing: str,
        answers: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        answers = answers or {}
        t1 = answers.get('T1') or self._guess_type(briefing)
        name = (briefing or '').strip().split('\n')[0][:80] or 'Neues Modul'
        # Kurzname aus Typ + Stichwort
        if t1 == 'HEADER' and _ADDR_KW.search(briefing or ''):
            name = 'Header Blau + Adresse'
            ident = 'abcona_header_blau_adresse'
        else:
            ident = _slug(name, f'{t1.lower()}_module')
        return {
            'name': name[:120],
            'identifier': ident,
            'module_type': t1,
            'description': (briefing or '')[:500],
            'preview_bg': '#163258' if t1 == 'HEADER' else '#f8f9fa',
            'status': 'DRAFT',
            'source': 'rules',
        }

    def _guess_type(self, briefing: str) -> str:
        text = briefing or ''
        if _HEADER_KW.search(text):
            return 'HEADER'
        if _FOOTER_KW.search(text):
            return 'FOOTER'
        if _BTN_KW.search(text):
            return 'BUTTON'
        if _SIG_KW.search(text):
            return 'SIGNATURE'
        return 'SECTION'

    def generate_fallback(
        self,
        briefing: str,
        answers: dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        answers = answers or {}
        meta = meta or {}
        merged = {**self.default_meta_suggestions(briefing, answers), **meta}
        t1 = answers.get('T1') or merged.get('module_type') or 'SECTION'
        want_addr = answers.get('C1') == 'yes' or bool(_ADDR_KW.search(briefing or ''))

        if t1 == 'HEADER':
            html, text = self._fallback_header(want_addr)
        elif t1 == 'BUTTON':
            html, text = self._fallback_button()
        elif t1 == 'FOOTER':
            html, text = self._fallback_footer(want_addr)
        else:
            html, text = self._fallback_section(briefing, want_addr)

        return {
            'html_body': html,
            'text_body': text,
            'name': merged.get('name'),
            'identifier': merged.get('identifier'),
            'module_type': t1,
            'description': merged.get('description') or '',
            'variables_used': list(extract_vars(html + text)),
            'source': 'rules',
        }

    @staticmethod
    def _fallback_header(with_address: bool) -> tuple[str, str]:
        html = (
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
            '<tr><td style="background-color:#163258;padding:16px 24px;text-align:left;">'
            '<span style="color:#ffffff;font-size:18px;font-weight:bold;font-family:Arial;">'
            'abcona e. K.</span></td></tr>'
        )
        text = 'abcona e. K.'
        if with_address:
            html += (
                '<tr><td style="background-color:#e8f0f8;padding:10px 24px;text-align:left;'
                'font-family:Arial;font-size:12px;line-height:1.5;color:#333333;">'
                '<a href="https://www.abcona.de" style="color:#163258;text-decoration:none;">'
                'www.abcona.de</a>&nbsp;·&nbsp;'
                '<a href="tel:+496171886710" style="color:#163258;text-decoration:none;">'
                '06171 886710</a>&nbsp;·&nbsp;'
                '<a href="mailto:info@abcona.de" style="color:#163258;text-decoration:none;">'
                'info@abcona.de</a></td></tr>'
            )
            text += '\nwww.abcona.de · 06171 886710 · info@abcona.de'
        html += '</table>'
        return html, text

    @staticmethod
    def _fallback_button() -> tuple[str, str]:
        html = (
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
            '<tr><td style="padding:16px 24px;text-align:center;">'
            '<a href="{button_url}" style="font-family:Arial;font-size:14px;font-weight:bold;'
            'color:#ffffff;background-color:#163258;padding:12px 24px;text-decoration:none;">'
            '{button_text}</a></td></tr></table>'
        )
        return html, '{button_text}: {button_url}'

    @staticmethod
    def _fallback_footer(with_address: bool) -> tuple[str, str]:
        lines = [
            'abcona e. K. | active business consulting agency',
            'Bornhohl 26 | D-61449 Steinbach/Ts.',
        ]
        if with_address:
            lines.append('www.abcona.de · 06171 886710 · info@abcona.de')
        body = '<br>'.join(lines)
        html = (
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
            '<tr><td style="background-color:#f8f9fa;padding:14px 24px;font-family:Arial;'
            f'font-size:12px;line-height:1.5;color:#6c757d;text-align:left;">{body}</td></tr>'
            '</table>'
        )
        return html, '\n'.join(lines)

    @staticmethod
    def _fallback_section(briefing: str, with_address: bool) -> tuple[str, str]:
        tip = (briefing or 'Inhalt').strip()[:300]
        html = (
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
            '<tr><td style="padding:16px 24px;font-family:Arial;font-size:14px;'
            f'color:#333333;line-height:1.5;">{tip}</td></tr>'
        )
        text = tip
        if with_address:
            html += (
                '<tr><td style="padding:0 24px 16px;font-family:Arial;font-size:12px;'
                'color:#333333;">'
                '<a href="https://www.abcona.de" style="color:#163258;">www.abcona.de</a>'
                ' · 06171 886710 · '
                '<a href="mailto:info@abcona.de" style="color:#163258;">info@abcona.de</a>'
                '</td></tr>'
            )
            text += '\nwww.abcona.de · 06171 886710 · info@abcona.de'
        html += '</table>'
        return html, text

    def validate_output(self, result: dict[str, Any]) -> ValidationResult:
        allowed_vars = {
            'button_text', 'button_url', 'sender_name', 'sender_email',
            'name', 'first_name', 'last_name', 'email', 'link', 'date', 'year',
        }
        return validate_email_module_output(result, allowed_vars)

    def apply_result(
        self,
        result: dict[str, Any],
        session_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        meta = session_meta or {}
        return {
            'target': 'email_studio_module',
            'fields': {
                'name': result.get('name') or meta.get('name') or '',
                'identifier': result.get('identifier') or meta.get('identifier') or '',
                'module_type': (
                    result.get('module_type')
                    or meta.get('module_type')
                    or 'SECTION'
                ),
                'description': result.get('description') or meta.get('description') or '',
                'preview_bg': result.get('preview_bg') or meta.get('preview_bg') or '',
                'html_body': result.get('html_body') or '',
                'text_body': result.get('text_body') or '',
                'variables': result.get('variables_used') or [],
            },
            'validation': result.get('validation'),
        }


def register_email_module_provider() -> None:
    register(EmailModuleWizardProvider())
