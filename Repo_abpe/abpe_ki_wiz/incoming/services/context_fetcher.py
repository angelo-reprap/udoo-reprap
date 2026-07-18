"""
Fakten für KI-Wizard — DB/Settings statt LLM-Halluzination.

Liefert strukturierte Daten (User, abcona-Firmendaten, …) für [[CONTEXT]].facts.
Generate und KI-Verfeinern nutzen dieselbe resolve_facts()-Pipeline.
"""
from __future__ import annotations

import logging
import re
from typing import Any

log = logging.getLogger('abpe_ki_wiz.context_fetcher')

# Kanonische abcona-Daten (identisch zu EmailRenderer.TEAM_SIGNATURE_FALLBACK)
ABCONA_COMPANY_FALLBACK: dict[str, Any] = {
    'name': 'abcona e. K.',
    'legal_form': 'e. K.',
    'tagline': 'active business consulting agency',
    'street': 'Bornhohl 26',
    'postal_code': '61449',
    'city': 'Steinbach/Ts.',
    'country': 'DE',
    'address_line': 'Bornhohl 26 | D-61449 Steinbach/Ts.',
    'email': 'info@abcona.de',
    'phone': '+49 6171 8867 10',
    'phone_display': '+49 0 6171 8867 10',
    'vat_id': 'DE813519516',
    'register': 'Amtsgericht Bad Homburg v.d.H. HRA 3662',
    'owner': 'Angelo Malaguarnera',
    'portal_url': 'https://abpe.win.abcona.info',
}

_COMPANY_KW = re.compile(
    r'abcona|firmenadresse|unternehmensadresse|impressum|footer|signatur|'
    r'geschäftsadresse|geschaeftsadresse|firmensitz|bornhohl|info@abcona',
    re.IGNORECASE,
)
_ADDRESS_KW = re.compile(
    r'\badresse\b|\banschrift\b|\bpostadresse\b|\bfirmendaten\b',
    re.IGNORECASE,
)

FACTS_USAGE_RULES: list[str] = [
    'Firmendaten/Adressen NUR aus facts.company_abcona oder {{block:signature}} — nie erfinden.',
    'User-Absender: {sender_name} und {sender_email} aus facts.user — nicht erfinden.',
    'Dynamische Empfängerdaten als {variablen} aus CONTEXT.catalog.variables belassen.',
    'Bei KI-Verfeinern: facts weiterhin gültig; HTML anpassen, Fakten nicht erfinden.',
]


def detect_fact_keys(
    *,
    wizard_id: str = '',
    briefing: str = '',
    answers: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
    refinement: str = '',
) -> set[str]:
    """Welche Fetcher für diese Anfrage laufen sollen."""
    keys: set[str] = {'user'}
    answers = answers or {}
    meta = meta or {}

    text = ' '.join([
        briefing or '',
        refinement or '',
        str(answers.get('G1', '')),
        str(answers.get('A1', '')),
        str(meta.get('signature_mode', '')),
        str(meta.get('sender_mode', '')),
    ])

    team_signature = (
        str(answers.get('G1', '')).upper() == 'TEAM'
        or str(answers.get('A1', '')).upper() == 'TEAM'
        or str(meta.get('signature_mode', '')).upper() == 'TEAM'
    )

    if wizard_id == 'email_template':
        keys.add('company_abcona')
    elif _COMPANY_KW.search(text) or _ADDRESS_KW.search(text) or team_signature:
        keys.add('company_abcona')

    if _COMPANY_KW.search(text) or _ADDRESS_KW.search(text):
        keys.add('company_abcona')

    return keys


def fetch_user_context(user) -> dict[str, Any]:
    if not user or not getattr(user, 'is_authenticated', False):
        return {}
    first = (getattr(user, 'first_name', '') or '').strip()
    last = (getattr(user, 'last_name', '') or '').strip()
    name = f'{first} {last}'.strip() or getattr(user, 'username', '') or ''
    email = (getattr(user, 'email', '') or '').strip()
    return {
        'sender_name': name,
        'sender_email': email,
        'reply_to': email,
    }


def fetch_company_abcona() -> dict[str, Any]:
    """Team-Firmendaten — DB-Signatur wenn vorhanden, sonst kanonischer Fallback."""
    data = dict(ABCONA_COMPANY_FALLBACK)
    data['source'] = 'fallback'

    try:
        from apps.abpe_email_studio.models import EmailSignature
    except ImportError:
        data['signature_hint'] = (
            'Nutze {{block:signature}} mit signature_mode TEAM für den Footer.'
        )
        return data

    sig = None
    for ident in ('abcona_team', 'team', 'general_team'):
        sig = EmailSignature.objects.filter(identifier=ident).first()
        if sig and sig.html_body:
            break
    if not sig:
        sig = EmailSignature.objects.filter(
            name__icontains='team', is_public=True
        ).first()

    if sig and sig.html_body:
        data['source'] = 'email_signature'
        data['signature_identifier'] = sig.identifier
        data['signature_name'] = sig.name
        data['signature_html_length'] = len(sig.html_body)
        data['signature_hint'] = (
            f'Footer/Adresse: {{block:signature}} oder signature_mode TEAM '
            f'(DB: {sig.identifier}) — nicht als Klartext halluzinieren.'
        )
    else:
        data['signature_hint'] = (
            'Footer/Adresse: {{block:signature}} mit signature_mode TEAM '
            'oder Module abcona_header_blau — facts.company_abcona für Metadaten.'
        )
    return data


def fetch_facts(
    keys: set[str] | list[str],
    *,
    user=None,
) -> dict[str, Any]:
    """Führt registrierte Fetcher aus."""
    out: dict[str, Any] = {'_rules': FACTS_USAGE_RULES}
    key_set = set(keys)

    if 'user' in key_set:
        user_facts = fetch_user_context(user)
        if user_facts:
            out['user'] = user_facts

    if 'company_abcona' in key_set:
        out['company_abcona'] = fetch_company_abcona()

    return out


def resolve_facts(
    *,
    wizard_id: str = '',
    user=None,
    briefing: str = '',
    answers: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
    refinement: str = '',
) -> dict[str, Any]:
    """
    Haupt-Einstieg: Detect + Fetch für Analyze, Generate und KI-Verfeinern.
    """
    keys = detect_fact_keys(
        wizard_id=wizard_id,
        briefing=briefing,
        answers=answers,
        meta=meta,
        refinement=refinement,
    )
    facts = fetch_facts(keys, user=user)
    facts['_requested_keys'] = sorted(keys)
    return facts
