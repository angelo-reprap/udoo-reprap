"""Email Studio — Wizard Domain Provider (Phase 1)."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from apps.abpe_ki_wiz.providers.base import ValidationResult, WizardDomainProvider
from apps.abpe_ki_wiz.registry import register
from apps.abpe_ki_wiz.services.validator import (
    extract_blocks,
    extract_vars,
    validate_email_template_output,
)

log = logging.getLogger('abpe_ki_wiz.email_template')

_QUESTIONS_PATH = Path(__file__).resolve().parent.parent / 'questions' / 'email_template.json'

# Pflichtfragen wenn nicht aus Briefing erkennbar
_DEFAULT_REQUIRED = ['S1', 'S2', 'I1', 'G1', 'A1']


def _load_questions() -> list[dict[str, Any]]:
    if not _QUESTIONS_PATH.exists():
        return []
    return json.loads(_QUESTIONS_PATH.read_text(encoding='utf-8'))


def _question_visible(q: dict[str, Any], answers: dict[str, Any]) -> bool:
    show_if = q.get('show_if') or {}
    if not show_if:
        return True
    for key, allowed in show_if.items():
        val = answers.get(key)
        if isinstance(allowed, list):
            if val not in allowed:
                return False
        elif val != allowed:
            return False
    return True


class EmailTemplateWizardProvider(WizardDomainProvider):
    wizard_id = 'email_template'
    title = 'E-Mail-Vorlage (Email Studio)'
    description = (
        'KI-Assistent für neue Email-Studio-Vorlagen mit Variablen, Modulen und Corporate-Layout.'
    )

    def get_catalog(
        self,
        app_scope: str = '',
        identifier: str = '',
        **kwargs,
    ) -> dict[str, Any]:
        scope = app_scope or 'general'
        ident = identifier or ''

        variables: list[dict] = []
        modules: list[dict] = []
        signature_modes: list = []
        sender_modes: list = []
        app_scopes: list = []

        try:
            from apps.abpe_email_studio.variables_registry import get_variables
            variables = get_variables(scope, ident or None)
        except ImportError as exc:
            log.warning('variables_registry nicht verfügbar: %s', exc)

        try:
            from apps.abpe_email_studio.models import EmailModule
            modules = list(
                EmailModule.objects.filter(is_active=True).values(
                    'identifier', 'name', 'module_type', 'description',
                )
            )
        except ImportError as exc:
            log.warning('EmailModule nicht verfügbar: %s', exc)

        try:
            from apps.abpe_email_studio.models import (
                AppScope,
                SenderMode,
                SignatureMode,
            )
            signature_modes = [{'value': v, 'label': l} for v, l in SignatureMode.choices]
            sender_modes = [{'value': v, 'label': l} for v, l in SenderMode.choices]
            app_scopes = [{'value': v, 'label': l} for v, l in AppScope.choices]
        except ImportError as exc:
            log.warning('EmailTemplate Enums nicht verfügbar: %s', exc)

        return {
            'variables': variables,
            'modules': modules,
            'signature_modes': signature_modes,
            'sender_modes': sender_modes,
            'app_scopes': app_scopes,
            'layout_rules': {
                'width_px': 600,
                'brand': 'abcona',
                'font': 'Arial,sans-serif',
            },
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
        catalog = self.get_question_catalog()
        pending: list[str] = []

        for q in catalog:
            qid = q['id']
            val = answers.get(qid)
            if val not in (None, '', []):
                continue
            if not _question_visible(q, answers):
                continue
            if q.get('required') or qid in _DEFAULT_REQUIRED:
                pending.append(qid)

        return pending

    def build_checklist(self, answers: dict[str, Any]) -> list[str]:
        items = [
            'Nur Variablen aus catalog.variables verwenden',
            'Module nur als {{block:identifier}}',
            'Kein Markdown, kein erfundenes Datum',
            'Deutsch, geschäftlich',
            'status immer DRAFT',
        ]
        if answers.get('I1') == 'bullet_list':
            items.append('Kerninfos als Aufzählung (<ul> oder Fakten-Box)')
        if answers.get('G1') and answers.get('G1') != 'NONE':
            items.append('{{block:signature}} im Body einfügen')
        if answers.get('L3') and answers.get('L3') != 'none':
            items.append(f"Button-Modul: {{block:{answers['L3']}}}")
        if answers.get('L1') and answers.get('L1') != 'none':
            items.append(f"Header-Modul: {{block:{answers['L1']}}}")
        return items

    def default_meta_suggestions(
        self,
        briefing: str,
        answers: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        base = super().default_meta_suggestions(briefing, answers)
        answers = answers or {}
        scope = answers.get('S1') or base.get('app_scope') or 'telefon'
        event = answers.get('S2') or 'invite'

        if scope == 'telefon' and event == 'invite':
            base['name'] = base.get('name') or 'Einladung — MeetMe'
            base['identifier'] = 'meetme_invite_custom'
            base['subject'] = 'Termin am {termin_datum}'
            base['app_scope'] = 'telefon'
            base['event_type'] = 'invite'

        base['sender_mode'] = answers.get('A1') or 'USER'
        base['signature_mode'] = answers.get('G1') or 'USER'
        base['status'] = 'DRAFT'
        return base

    def validate_output(self, result: dict[str, Any]) -> ValidationResult:
        scope = result.get('app_scope') or 'general'
        ident = result.get('identifier') or ''
        catalog = self.get_catalog(app_scope=scope, identifier=ident)
        allowed_vars = {v['name'] for v in catalog.get('variables') or [] if isinstance(v, dict)}
        allowed_vars.update({'subject', 'name', 'date', 'year', 'portal_url'})
        allowed_blocks = {m['identifier'] for m in catalog.get('modules') or [] if isinstance(m, dict)}
        allowed_blocks.add('signature')
        return validate_email_template_output(result, allowed_vars, allowed_blocks)

    def _default_meetme_fields(self, answers: dict[str, Any]) -> list[str]:
        raw = answers.get('M1')
        if isinstance(raw, list) and raw:
            return raw
        if isinstance(raw, str) and raw:
            return [raw]
        return ['termin_datum', 'termin_uhrzeit', 'raum', 'einwahl_info', 'title']

    def _render_info_block(self, answers: dict[str, Any]) -> tuple[str, str]:
        fields = self._default_meetme_fields(answers)
        labels = {
            'termin_datum': 'Datum',
            'termin_uhrzeit': 'Uhrzeit',
            'raum': 'Raum',
            'einwahl_info': 'Einwahl',
            'title': 'Titel',
        }
        html_items = ''.join(
            f'<li><strong>{labels.get(f, f)}:</strong> {{{f}}}</li>'
            for f in fields
        )
        text_items = '\n'.join(
            f'- {labels.get(f, f)}: {{{f}}}'
            for f in fields
        )
        if answers.get('I1') == 'prose':
            html = (
                '<p>Termin: <strong>{termin_datum}</strong> um <strong>{termin_uhrzeit}</strong> '
                'im Raum <strong>{raum}</strong>.</p>'
                '<p>Einwahl: {einwahl_info}</p>'
            )
            text = (
                'Termin: {termin_datum} um {termin_uhrzeit} im Raum {raum}.\n'
                'Einwahl: {einwahl_info}'
            )
            return html, text
        return f'<ul>{html_items}</ul>', text_items

    def generate_fallback(
        self,
        briefing: str,
        answers: dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Regelbasierte Vorlage wenn DeepSeek ausfällt."""
        answers = answers or {}
        meta = meta or {}
        merged = {**self.default_meta_suggestions(briefing, answers), **meta}

        blocks: list[str] = []
        if answers.get('L1') and answers.get('L1') != 'none':
            blocks.append(f'{{{{block:{answers["L1"]}}}}}')

        info_html, info_text = self._render_info_block(answers)
        intro = (briefing or merged.get('description') or '').strip()
        blocks.append(
            '<p>Guten Tag,</p>'
            f'<p>{intro or "hiermit laden wir Sie zu einer Telefon-Abstimmung ein."}</p>'
            f'{info_html}'
        )

        m2 = answers.get('M2') or 'none'
        if m2 == 'plain':
            blocks.append('<p><strong>Teilnehmer:</strong></p><p>{teilnehmer_liste}</p>')
        elif m2 == 'html':
            blocks.append('{teilnehmer_liste_html}')

        if answers.get('L3') and answers.get('L3') != 'none':
            blocks.append(f'{{{{block:{answers["L3"]}}}}}')

        sig_mode = answers.get('G1') or merged.get('signature_mode') or 'USER'
        if sig_mode and sig_mode != 'NONE':
            blocks.append('{{block:signature}}')

        html_body = (
            '<table role="presentation" width="600" cellpadding="0" cellspacing="0" '
            'style="width:600px;max-width:600px;font-family:Arial,sans-serif;font-size:14px;'
            'color:#333333;">'
            '<tr><td style="padding:16px 24px;">'
            + '\n'.join(blocks)
            + '</td></tr></table>'
        )

        text_parts = [
            'Guten Tag,',
            '',
            intro or 'Hiermit laden wir Sie zu einer Telefon-Abstimmung ein.',
            '',
            info_text,
        ]
        if m2 == 'plain':
            text_parts.extend(['', 'Teilnehmer:', '{teilnehmer_liste}'])
        elif m2 == 'html':
            text_parts.extend(['', '{teilnehmer_liste}'])

        variables_used = list(self._default_meetme_fields(answers))
        if m2 in ('plain', 'html'):
            variables_used.append('teilnehmer_liste')
        if m2 == 'html':
            variables_used.append('teilnehmer_liste_html')

        return {
            'html_body': html_body,
            'text_body': '\n'.join(text_parts).strip(),
            'variables_used': variables_used,
            'source': 'rules',
        }

    def apply_result(
        self,
        result: dict[str, Any],
        session_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Struktur für Email Studio Editor (Phase 2 UI paste)."""
        return {
            'target': 'email_studio',
            'fields': {
                'name': result.get('name', ''),
                'identifier': result.get('identifier', ''),
                'subject': result.get('subject', ''),
                'description': result.get('description', ''),
                'app_scope': result.get('app_scope', 'general'),
                'event_type': result.get('event_type', 'general'),
                'sender_mode': result.get('sender_mode', 'USER'),
                'signature_mode': result.get('signature_mode', 'USER'),
                'status': result.get('status', 'DRAFT'),
                'html_body': result.get('html_body', ''),
                'text_body': result.get('text_body', ''),
                'variables': result.get('variables_used') or [],
            },
            'validation': result.get('validation'),
        }


def register_email_provider() -> None:
    register(EmailTemplateWizardProvider())
