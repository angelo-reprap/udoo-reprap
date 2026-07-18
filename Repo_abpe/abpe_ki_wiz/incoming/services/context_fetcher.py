"""
Fakten für KI-Wizard — DB/Settings/CRM statt LLM-Halluzination.

Liefert strukturierte Daten (User, abcona, CRM Kontakte/Firmen) für CONTEXT.facts.
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

_CRM_ID_RE = re.compile(
    r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
    re.IGNORECASE,
)
_COMPANY_KW = re.compile(
    r'abcona|firmenadresse|unternehmensadresse|impressum|footer|signatur|'
    r'geschäftsadresse|geschaeftsadresse|firmensitz|bornhohl|info@abcona',
    re.IGNORECASE,
)
_ADDRESS_KW = re.compile(
    r'\badresse\b|\banschrift\b|\bpostadresse\b|\bfirmendaten\b',
    re.IGNORECASE,
)
_CONTACT_KW = re.compile(
    r'\bberater\b|\bkontakt\b|\bkandidat\b|\bansprechpartner\b|\bempfänger\b|'
    r'\bempfaenger\b|\bteilnehmer\b|\bprofil\b',
    re.IGNORECASE,
)
_ACCOUNT_KW = re.compile(
    r'\bkunde\b|\bfirma\b|\bunternehmen\b|\baccount\b|\bcompany\b|\bkunden\b',
    re.IGNORECASE,
)

_CRM_ID_KEYS = (
    'contact_crm_id', 'account_crm_id', 'crm_id',
    'berater_crm_id', 'kunde_crm_id', 'entity_crm_id',
)

FACTS_USAGE_RULES: list[str] = [
    'Firmendaten/Adressen NUR aus facts.company_abcona oder {{block:signature}} — nie erfinden.',
    'User-Absender: {sender_name} und {sender_email} aus facts.user — nicht erfinden.',
    'CRM-Personen/Firmen: facts.contact / facts.account / facts.crm_candidates — nie erfinden.',
    'Nutze facts.*.variables für konkrete Werte in {name}, {email}, {firma}, {berater_name}, …',
    'Dynamische unbekannte Empfänger weiter als {variablen} aus CONTEXT.catalog.variables.',
    'Bei KI-Verfeinern: facts weiterhin gültig; HTML anpassen, Fakten nicht erfinden.',
    'Corporate-Layout: Header-Modul (abcona_header_blau/gruen/rot) → Body → Footer-Modul.',
    'Header, Body, Footer linksbündig; Body/Footer Arial 14px, Farbe #333333.',
]

_ES_FIELDS_BERATER = [
    'name^3', 'ogo^0.3', 'gulp^0.3', 'freelancermap^0.3', 'description^0.3',
    'emails^2', 'phones^2', 'city', 'einsatzort', 'konditionen^0.3',
    'kontakt_typ', 'kontakt_status', 'company^2', 'notes^0.2',
    'salutation', 'department', 'title',
]
_ES_FIELDS_KUNDEN = [
    'name^3', 'kunden_nummer^2', 'industry', 'description',
    'emails^2', 'phones^2', 'billing_city', 'billing_postalcode',
    'contacts^2', 'account_status', 'account_type', 'notes', 'website',
]


def _crm_available() -> bool:
    try:
        from apps.abpe_crm.models import CrmContact  # noqa: F401
        return True
    except ImportError:
        return False


def _pick_primary_email(emails: list[dict[str, Any]]) -> str:
    for row in emails:
        if row.get('primary') and row.get('email'):
            return row['email']
    for row in emails:
        if row.get('email'):
            return row['email']
    return ''


def _pick_primary_phone(phones: list[dict[str, Any]]) -> str:
    for row in phones:
        if row.get('is_primary') and row.get('raw'):
            return row['raw']
    for row in phones:
        if row.get('raw'):
            return row['raw']
    return ''


def _format_address(street: str, postal: str, city: str, country: str = '') -> str:
    parts = [p for p in [street.strip(), ' '.join(p for p in [postal, city] if p).strip()] if p]
    line = ', '.join(parts)
    if country and country.strip() not in line:
        line = f'{line}, {country.strip()}'.strip(', ')
    return line


def extract_entity_refs(
    *,
    briefing: str = '',
    answers: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
    refinement: str = '',
) -> dict[str, Any]:
    """CRM-IDs und Suchbegriffe aus Session/Briefing extrahieren."""
    answers = answers or {}
    meta = meta or {}
    blobs = [briefing or '', refinement or '']

    contact_id = ''
    account_id = ''
    for src in (answers, meta, meta.get('analyze') or {}):
        if not isinstance(src, dict):
            continue
        for key in _CRM_ID_KEYS:
            val = str(src.get(key) or '').strip()
            if not val:
                continue
            if 'account' in key or key == 'kunde_crm_id':
                account_id = account_id or val
            else:
                contact_id = contact_id or val

    for blob in blobs:
        for match in _CRM_ID_RE.findall(blob):
            if not contact_id:
                contact_id = match
            elif not account_id and match != contact_id:
                account_id = match

    combined = ' '.join(blobs + [
        str(answers.get('S1', '')),
        str(meta.get('app_scope', '')),
    ])
    want_contacts = bool(_CONTACT_KW.search(combined))
    want_accounts = bool(_ACCOUNT_KW.search(combined))
    app_scope = str(
        answers.get('S1') or meta.get('app_scope')
        or (meta.get('analyze') or {}).get('app_scope') or ''
    ).lower()
    if app_scope == 'matching':
        want_contacts = True
        want_accounts = True

    search_query = ''
    if (want_contacts or want_accounts) and not contact_id and not account_id:
        search_query = _derive_search_query(briefing, refinement)

    return {
        'contact_crm_id': contact_id,
        'account_crm_id': account_id,
        'search_query': search_query,
        'want_contacts': want_contacts,
        'want_accounts': want_accounts,
    }


def _derive_search_query(briefing: str, refinement: str = '') -> str:
    """Kurzer Suchbegriff aus Briefing/Verfeinerung (ohne Boilerplate)."""
    raw = (refinement or briefing or '').strip()
    if not raw:
        return ''
    cleaned = re.sub(
        r'(?i)\b(bitte|erstelle|generiere|schreibe|mail|email|vorlage|template|'
        r'weihnacht|grüße|gruesse|abcona|adresse|footer|signatur)\b',
        ' ',
        raw,
    )
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' ,.;:-')
    if len(cleaned) >= 3:
        return cleaned[:120]
    return raw[:120]


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

    refs = extract_entity_refs(
        briefing=briefing,
        answers=answers,
        meta=meta,
        refinement=refinement,
    )
    if refs.get('contact_crm_id') or refs.get('want_contacts'):
        keys.add('crm_contact')
    if refs.get('account_crm_id') or refs.get('want_accounts'):
        keys.add('crm_account')
    if refs.get('search_query') and _crm_available():
        keys.add('crm_search')

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


def _get_crm_phones(bean_id: str, bean_module: str) -> list[dict[str, Any]]:
    from apps.abpe_crm.models import CrmPhoneBeanRel

    rels = CrmPhoneBeanRel.objects.filter(
        bean_id=bean_id, bean_module=bean_module,
    ).select_related('phone').order_by('field_name')
    return [
        {
            'field_name': r.field_name,
            'label': r.label or '',
            'raw': r.phone.phone_raw if r.phone_id else '',
            'norm': r.phone.phone_norm if r.phone_id else '',
            'is_primary': bool(r.is_primary),
        }
        for r in rels
    ]


def _get_crm_emails(bean_id: str, bean_module: str) -> list[dict[str, Any]]:
    from apps.abpe_crm.models import CrmEmailAddrBeanRel

    rows = CrmEmailAddrBeanRel.objects.filter(
        bean_id=bean_id, bean_module=bean_module,
    ).select_related('email_address').values_list(
        'email_address__email_address',
        'primary_address',
    )
    return [
        {'email': email or '', 'primary': bool(primary)}
        for email, primary in rows
        if email
    ]


def _es_search_ids(index: str, query: str, fields: list[str], size: int = 5) -> list[str]:
    if not query.strip():
        return []
    try:
        from elasticsearch import Elasticsearch
        es = Elasticsearch(['http://localhost:9200'])
        res = es.search(
            index=index,
            size=size,
            _source=['crm_id'],
            query={
                'query_string': {
                    'query': query,
                    'fields': fields,
                    'default_operator': 'AND',
                    'type': 'cross_fields',
                    'lenient': True,
                },
            },
        )
        return [
            h['_source']['crm_id']
            for h in res.get('hits', {}).get('hits', [])
            if h.get('_source', {}).get('crm_id')
        ]
    except Exception as exc:
        log.warning('ES-Suche (%s) fehlgeschlagen: %s', index, exc)
        return []


def search_crm_contacts(query: str, limit: int = 5) -> list[dict[str, Any]]:
    if not _crm_available() or not query.strip():
        return []
    from apps.abpe_crm.models import CrmContact
    from django.db.models import Q

    ids = _es_search_ids('content', query, _ES_FIELDS_BERATER, size=limit)
    qs = CrmContact.objects.select_related('cstm')
    if ids:
        qs = qs.filter(crm_id__in=ids)
    else:
        parts = query.split()
        q_obj = Q()
        for part in parts[:4]:
            q_obj |= Q(first_name__icontains=part) | Q(last_name__icontains=part)
        qs = qs.filter(q_obj)

    results = []
    for c in qs[:limit]:
        emails = _get_crm_emails(c.crm_id, 'Contacts')
        phones = _get_crm_phones(c.crm_id, 'Contacts')
        results.append({
            'crm_id': c.crm_id,
            'full_name': c.full_name,
            'first_name': c.first_name or '',
            'last_name': c.last_name or '',
            'email': _pick_primary_email(emails),
            'phone': _pick_primary_phone(phones),
            'city': c.primary_address_city or '',
        })
    return results


def search_crm_accounts(query: str, limit: int = 5) -> list[dict[str, Any]]:
    if not _crm_available() or not query.strip():
        return []
    from apps.abpe_crm.models import CrmAccount
    from django.db.models import Q

    ids = _es_search_ids('content_firma', query, _ES_FIELDS_KUNDEN, size=limit)
    qs = CrmAccount.objects.select_related('cstm')
    if ids:
        qs = qs.filter(crm_id__in=ids)
    else:
        qs = qs.filter(Q(name__icontains=query) | Q(billing_address_city__icontains=query))

    results = []
    for a in qs[:limit]:
        emails = _get_crm_emails(a.crm_id, 'Accounts')
        phones = _get_crm_phones(a.crm_id, 'Accounts')
        results.append({
            'crm_id': a.crm_id,
            'name': a.name or '',
            'email': _pick_primary_email(emails),
            'phone': _pick_primary_phone(phones),
            'city': a.billing_address_city or '',
            'website': a.website or '',
        })
    return results


def fetch_crm_contact(crm_id: str) -> dict[str, Any] | None:
    if not _crm_available() or not crm_id:
        return None
    from apps.abpe_crm.models import CrmAccountContacts, CrmContact

    try:
        c = CrmContact.objects.select_related('cstm').get(crm_id=crm_id)
    except CrmContact.DoesNotExist:
        return None

    emails = _get_crm_emails(c.crm_id, 'Contacts')
    phones = _get_crm_phones(c.crm_id, 'Contacts')
    address_line = _format_address(
        c.primary_address_street or '',
        c.primary_address_postalcode or '',
        c.primary_address_city or '',
        c.primary_address_country or '',
    )
    company_name = ''
    link = CrmAccountContacts.objects.filter(contact_id=c.crm_id).select_related('account').first()
    if link and link.account_id:
        company_name = link.account.name or ''

    full_name = c.full_name
    primary_email = _pick_primary_email(emails)
    variables = {
        'name': full_name,
        'first_name': c.first_name or '',
        'last_name': c.last_name or '',
        'email': primary_email,
        'berater_name': full_name,
        'kandidat_name': full_name,
    }
    if company_name:
        variables['firma'] = company_name
        variables['unternehmen'] = company_name

    return {
        'source': 'crm_contact',
        'crm_id': c.crm_id,
        'full_name': full_name,
        'first_name': c.first_name or '',
        'last_name': c.last_name or '',
        'title': c.title or '',
        'department': c.department or '',
        'email': primary_email,
        'emails': emails[:5],
        'phone': _pick_primary_phone(phones),
        'phones': phones[:5],
        'city': c.primary_address_city or '',
        'address_line': address_line,
        'company_name': company_name,
        'variables': variables,
    }


def fetch_crm_account(crm_id: str) -> dict[str, Any] | None:
    if not _crm_available() or not crm_id:
        return None
    from apps.abpe_crm.models import CrmAccount, CrmAccountContacts

    try:
        a = CrmAccount.objects.select_related('cstm').get(crm_id=crm_id)
    except CrmAccount.DoesNotExist:
        return None

    emails = _get_crm_emails(a.crm_id, 'Accounts')
    phones = _get_crm_phones(a.crm_id, 'Accounts')
    address_line = _format_address(
        a.billing_address_street or '',
        a.billing_address_postalcode or '',
        a.billing_address_city or '',
        a.billing_address_country or '',
    )
    name = a.name or ''
    contacts = []
    for link in CrmAccountContacts.objects.filter(account_id=a.crm_id).select_related('contact')[:8]:
        if not link.contact_id:
            continue
        c = link.contact
        c_emails = _get_crm_emails(c.crm_id, 'Contacts')
        contacts.append({
            'crm_id': c.crm_id,
            'full_name': c.full_name,
            'email': _pick_primary_email(c_emails),
            'title': c.title or '',
        })

    return {
        'source': 'crm_account',
        'crm_id': a.crm_id,
        'name': name,
        'email': _pick_primary_email(emails),
        'emails': emails[:5],
        'phone': _pick_primary_phone(phones),
        'phones': phones[:5],
        'city': a.billing_address_city or '',
        'address_line': address_line,
        'website': a.website or '',
        'contacts': contacts,
        'variables': {
            'firma': name,
            'unternehmen': name,
        },
    }


def _resolve_crm_facts(
    keys: set[str],
    *,
    briefing: str = '',
    answers: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
    refinement: str = '',
) -> dict[str, Any]:
    if not _crm_available():
        return {}

    refs = extract_entity_refs(
        briefing=briefing,
        answers=answers,
        meta=meta,
        refinement=refinement,
    )
    out: dict[str, Any] = {}
    contact_id = refs.get('contact_crm_id') or ''
    account_id = refs.get('account_crm_id') or ''

    if 'crm_search' in keys and refs.get('search_query'):
        q = refs['search_query']
        candidates: dict[str, Any] = {'query': q, 'contacts': [], 'accounts': []}
        if 'crm_contact' in keys or refs.get('want_contacts'):
            candidates['contacts'] = search_crm_contacts(q, limit=5)
            if not contact_id and len(candidates['contacts']) == 1:
                contact_id = candidates['contacts'][0]['crm_id']
        if 'crm_account' in keys or refs.get('want_accounts'):
            candidates['accounts'] = search_crm_accounts(q, limit=5)
            if not account_id and len(candidates['accounts']) == 1:
                account_id = candidates['accounts'][0]['crm_id']
        if candidates['contacts'] or candidates['accounts']:
            out['crm_candidates'] = candidates

    if contact_id and 'crm_contact' in keys:
        contact = fetch_crm_contact(contact_id)
        if contact:
            out['contact'] = contact

    if account_id and 'crm_account' in keys:
        account = fetch_crm_account(account_id)
        if account:
            out['account'] = account

    return out


def fetch_facts(
    keys: set[str] | list[str],
    *,
    user=None,
    briefing: str = '',
    answers: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
    refinement: str = '',
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

    crm_keys = key_set & {'crm_contact', 'crm_account', 'crm_search'}
    if crm_keys:
        out.update(_resolve_crm_facts(
            crm_keys,
            briefing=briefing,
            answers=answers,
            meta=meta,
            refinement=refinement,
        ))

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
    facts = fetch_facts(
        keys,
        user=user,
        briefing=briefing,
        answers=answers,
        meta=meta,
        refinement=refinement,
    )
    facts['_requested_keys'] = sorted(keys)
    return facts
