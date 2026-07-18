"""Email Studio — Wizard Domain Provider (Phase 1)."""
from __future__ import annotations

import json
import logging
import re
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

_ABSENCE_KW = re.compile(r'abwesenheit|vertretung|urlaub|krank|out[\s-]?of[\s-]?office', re.IGNORECASE)
_GREETING_KW = re.compile(r'weihnacht|festtag|silvester|neujahr|grüße|gruesse|season', re.IGNORECASE)


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
                'font_size_px': 14,
                'text_color': '#333333',
                'text_align': 'left',
                'structure': ['header_module', 'event_label', 'body', 'closing'],
                'header_modules': ['abcona_header_blau'],
                'event_labels': ['label_info', 'label_bestaetigt', 'label_warnung'],
                'footer_modules': ['footer_standard', 'footer_auto_reply'],
                'button_modules': ['cta_blau', 'cta_gruen', 'cta_with_secondary'],
                'default_header': 'abcona_header_blau',
                # Signatur XOR Footer (DE-Impressum) — siehe EMAIL_LAYOUT_DECLARATION.md
                'closing_xor': ['signature', 'footer'],
                'footer_style': 'imprint',
                'text_fallback': 'html_1to1',
                'ci_notes': (
                    '{{block:abcona_header_blau}} → optional label_info|bestaetigt|warnung → Body '
                    '→ entweder {{block:signature}} ODER {{block:footer_standard|footer_auto_reply}}. '
                    'Body: Arial 14px #333 left. TXT 1:1 aus HTML. CTA: cta_blau/cta_gruen.'
                ),
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
        scope = answers.get('S1') or 'general'
        items = [
            'Nur Variablen aus catalog.variables verwenden',
            'Module nur als {{block:identifier}}',
            'Kein Markdown, kein erfundenes Datum',
            'Deutsch, geschäftlich',
            'status immer DRAFT',
            '{sender_name} und {sender_email} für User-Absender erlaubt',
            'Corporate: {{block:abcona_header_blau}} → optional label_* → Body',
            'Abschluss XOR: Signatur ODER Footer (nie beides) — DE-Impressum',
            'Body linksbündig, Arial 14px, Farbe #333333',
            'text_body Pflicht: sichtbarer Text 1:1 aus HTML',
            'Event-Badge: label_info (blau) / label_bestaetigt (grün) / label_warnung (rot)',
        ]
        if scope == 'telefon':
            items.append('MeetMe/Termin-Variablen nur bei app_scope telefon')
        if scope == 'general':
            items.append('Keine MeetMe-Variablen ({termin_datum} etc.) ohne Termin-Kontext')
        if answers.get('I1') == 'bullet_list':
            items.append('Kerninfos als Aufzählung (<ul> oder Fakten-Box)')
        g1 = answers.get('G1')
        if g1 and g1 != 'NONE':
            items.append('{{block:signature}} im Body — kein Footer-Modul')
        else:
            items.append('Keine Signatur → {{block:footer_standard}} oder footer_auto_reply')
        if answers.get('L3') and answers.get('L3') != 'none':
            items.append(f"Button-Modul: {{block:{answers['L3']}}}")
        if answers.get('L1') and answers.get('L1') != 'none':
            items.append(f"Header-Modul: {{block:{answers['L1']}}}")
        if answers.get('L2') and answers.get('L2') != 'none':
            items.append(f"Event-Label: {{block:{answers['L2']}}}")
        return items

    def default_meta_suggestions(
        self,
        briefing: str,
        answers: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        base = super().default_meta_suggestions(briefing, answers)
        answers = answers or {}
        scope = answers.get('S1') or base.get('app_scope') or 'general'
        event = answers.get('S2') or base.get('event_type') or 'info'
        text = briefing or ''

        if scope == 'telefon' and event == 'invite':
            base['name'] = base.get('name') or 'Einladung — MeetMe'
            base['identifier'] = base.get('identifier') or 'meetme_invite_custom'
            base['subject'] = base.get('subject') or 'Termin am {termin_datum}'
            base['app_scope'] = 'telefon'
            base['event_type'] = 'invite'
        elif scope == 'general':
            base['app_scope'] = 'general'
            base['event_type'] = event
            if _ABSENCE_KW.search(text):
                base['name'] = base.get('name') or 'Abwesenheit — Vertretung'
                base['identifier'] = base.get('identifier') or 'abwesenheit_vertretung'
                base['subject'] = base.get('subject') or 'Abwesenheit — Vertretung durch {vertretung_name}'
            elif _GREETING_KW.search(text):
                base['name'] = base.get('name') or 'Festliche Grüße'
                base['identifier'] = base.get('identifier') or 'festliche_gruesse'
                base['subject'] = base.get('subject') or 'Frohe Festtage vom abcona Team'
            else:
                base['subject'] = base.get('subject') or '{subject}'
        elif scope == 'matching':
            base['app_scope'] = 'matching'
            base['subject'] = base.get('subject') or 'Kandidatenvorschlag — {kandidat_name}'

        base['sender_mode'] = answers.get('A1') or 'USER'
        base['signature_mode'] = answers.get('G1') or 'USER'
        base['status'] = 'DRAFT'
        return base

    def validate_output(self, result: dict[str, Any]) -> ValidationResult:
        scope = result.get('app_scope') or 'general'
        ident = result.get('identifier') or ''
        catalog = self.get_catalog(app_scope=scope, identifier=ident)
        allowed_vars = {v['name'] for v in catalog.get('variables') or [] if isinstance(v, dict)}
        allowed_vars.update({
            'subject', 'name', 'date', 'year', 'portal_url',
            'sender_name', 'sender_email', 'reply_to',
        })
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
        scope = answers.get('S1') or merged.get('app_scope') or 'general'

        if scope == 'telefon':
            return self._generate_fallback_telefon(briefing, answers, merged)
        return self._generate_fallback_general(briefing, answers, merged)

    def _generate_fallback_telefon(
        self,
        briefing: str,
        answers: dict[str, Any],
        merged: dict[str, Any],
    ) -> dict[str, Any]:
        blocks: list[str] = []
        l1 = answers.get('L1') or 'abcona_header_blau'
        if l1 != 'none':
            blocks.append(f'{{{{block:{l1}}}}}')
        l2 = answers.get('L2') or 'none'
        if l2 != 'none':
            blocks.append(f'{{{{block:{l2}}}}}')

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
        else:
            blocks.append('{{block:footer_standard}}')

        html_body = self._wrap_email_table('\n'.join(blocks))
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

    def _generate_fallback_general(
        self,
        briefing: str,
        answers: dict[str, Any],
        merged: dict[str, Any],
    ) -> dict[str, Any]:
        blocks: list[str] = []
        l1 = answers.get('L1') or 'abcona_header_blau'
        if l1 != 'none':
            blocks.append(f'{{{{block:{l1}}}}}')
        l2 = answers.get('L2') or 'none'
        if l2 != 'none':
            blocks.append(f'{{{{block:{l2}}}}}')

        intro = (briefing or merged.get('description') or '').strip()
        text = briefing or ''
        body_html = ''
        body_text = ''
        variables_used: list[str] = ['sender_name', 'sender_email', 'date']

        if _ABSENCE_KW.search(text):
            body_html = (
                '<p>Guten Tag,</p>'
                f'<p>{intro or "ich bin abwesend und werde durch eine Vertretung vertreten."}</p>'
                '<p>Vertretung: <strong>{vertretung_name}</strong><br>'
                'E-Mail: {vertretung_email}<br>'
                'Telefon: {vertretung_telefon}</p>'
                '<p>Abwesenheit: {abwesenheit_von} — {abwesenheit_bis}</p>'
            )
            body_text = (
                'Guten Tag,\n\n'
                f'{intro or "Ich bin abwesend und werde durch eine Vertretung vertreten."}\n\n'
                'Vertretung: {vertretung_name}\n'
                'E-Mail: {vertretung_email}\n'
                'Telefon: {vertretung_telefon}\n\n'
                'Abwesenheit: {abwesenheit_von} — {abwesenheit_bis}'
            )
            variables_used.extend([
                'vertretung_name', 'vertretung_email', 'vertretung_telefon',
                'abwesenheit_von', 'abwesenheit_bis', 'mobil_nummer',
            ])
        elif _GREETING_KW.search(text):
            body_html = (
                '<p>Liebe Kolleginnen und Kollegen,</p>'
                f'<p>{intro or "wir wünschen Ihnen frohe Festtage und einen guten Rutsch ins neue Jahr {year}."}</p>'
                '<p>Herzliche Grüße<br>{sender_name}<br>{sender_email}</p>'
            )
            body_text = (
                'Liebe Kolleginnen und Kollegen,\n\n'
                f'{intro or "Wir wünschen Ihnen frohe Festtage und einen guten Rutsch ins neue Jahr {year}."}\n\n'
                'Herzliche Grüße\n{sender_name}\n{sender_email}'
            )
            variables_used.append('year')
        else:
            if answers.get('I1') == 'bullet_list':
                body_html = (
                    '<p>Guten Tag,</p>'
                    f'<p>{intro or "folgende Informationen:"}</p>'
                    '<ul><li>{subject}</li></ul>'
                )
                body_text = f'Guten Tag,\n\n{intro or "Folgende Informationen:"}\n\n- {{subject}}'
            else:
                body_html = (
                    '<p>Guten Tag,</p>'
                    f'<p>{intro or "vielen Dank für Ihre Nachricht."}</p>'
                )
                body_text = f'Guten Tag,\n\n{intro or "Vielen Dank für Ihre Nachricht."}'
            variables_used.append('subject')

        blocks.append(body_html)

        if answers.get('L3') and answers.get('L3') != 'none':
            blocks.append(f'{{{{block:{answers["L3"]}}}}}')

        sig_mode = answers.get('G1') or merged.get('signature_mode') or 'USER'
        if sig_mode and sig_mode != 'NONE' and '{{block:signature}}' not in body_html:
            blocks.append('{{block:signature}}')
        elif not sig_mode or sig_mode == 'NONE':
            blocks.append('{{block:footer_standard}}')

        return {
            'html_body': self._wrap_email_table('\n'.join(blocks)),
            'text_body': body_text.strip(),
            'variables_used': variables_used,
            'source': 'rules',
        }

    @staticmethod
    def _wrap_email_table(inner: str) -> str:
        return (
            '<table role="presentation" width="600" cellpadding="0" cellspacing="0" '
            'style="width:600px;max-width:600px;font-family:Arial,sans-serif;font-size:14px;'
            'color:#333333;text-align:left;">'
            '<tr><td style="padding:16px 24px;text-align:left;">'
            + inner
            + '</td></tr></table>'
        )

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
