"""aufgaben_service — Fassade: erstellen, erledigen, fuer_ref, badge (Kap. 1)."""
from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from typing import Any, Optional
from uuid import UUID

from django.db.models import Q
from django.utils import timezone

from apps.abpe_shaduler.models import Aufgabe, ErgebnisTyp

from . import aktivitaet_service

log = logging.getLogger('abpe_shaduler.aufgaben')

_PHONE_LABELS = {
    'phone_mobile': 'Mobil',
    'phone_work': 'Büro',
    'phone_home': 'Privat',
    'phone_other': 'Sonst.',
    'phone_fax': 'Fax',
    'whatsapp': 'WhatsApp',
}


def normalize_de_phone(raw: str) -> tuple[str, bool]:
    """Normalisiert auf 0049… und prüft Länge (Mobil/Festnetz DE).

    Akzeptiert +49…, 0049…, 0… (national). Rückgabe: (norm, ok).
    """
    s = re.sub(r'[^\d+]', '', (raw or '').strip())
    if not s:
        return '', False
    if s.startswith('+'):
        s = '00' + s[1:]
    if s.startswith('0049'):
        norm = s
    elif s.startswith('49') and len(s) >= 11:
        norm = '00' + s
    elif s.startswith('0') and not s.startswith('00'):
        norm = '0049' + s[1:]
    else:
        # reine Digits ohne Ländervorwahl — nur ok wenn schon 0049-Länge
        norm = s
    ok = bool(re.match(r'^0049\d{6,13}$', norm))
    return norm, ok


def phone_to_wa_digits(raw: str) -> str:
    """wa.me braucht Ländervorwahl ohne 00/+ → 4917…"""
    norm, ok = normalize_de_phone(raw)
    if not ok:
        digits = re.sub(r'\D', '', raw or '')
        if digits.startswith('00'):
            digits = digits[2:]
        return digits
    return norm[2:] if norm.startswith('00') else norm


def _looks_like_crm_uuid(value: str) -> bool:
    v = (value or '').strip()
    if not v:
        return False
    try:
        UUID(v)
        return True
    except Exception:
        pass
    # SuiteCRM oft ohne Bindestriche
    hexish = v.replace('-', '')
    return len(hexish) == 32 and all(c in '0123456789abcdefABCDEF' for c in hexish)


def _name_hint_from_aufgabe(aufgabe: Optional[Aufgabe] = None, titel: str = '') -> str:
    """z.B. „Termin-Erinnerung an T. Lorenz“ → Lorenz."""
    text = titel or (getattr(aufgabe, 'titel', '') if aufgabe else '') or ''
    m = re.search(r'\ban\s+(.+)$', text.strip(), re.I)
    if m:
        name = m.group(1).strip()
        # „T. Lorenz“ / „Hr. Lorenz“ → Nachname bevorzugt
        parts = re.split(r'\s+', name)
        if parts:
            return parts[-1].strip('.,')
    return ''


def _resolve_contact_crm_id(
    ref_type: str,
    ref_id: str,
    *,
    name_hint: str = '',
) -> str:
    """UUID nutzen; sonst Name/Slug → CRM crm_id (ORM, optional ES)."""
    bid = (ref_id or '').strip()
    if not bid and not name_hint:
        return ''
    if ref_type not in ('berater', 'ansprechpartner', ''):
        return bid if _looks_like_crm_uuid(bid) else ''
    if bid and _looks_like_crm_uuid(bid):
        return bid

    try:
        from django.apps import apps

        Contact = apps.get_model('abpe_crm', 'CrmContact')
    except LookupError:
        return bid

    queries = []
    for term in (bid, name_hint):
        term = (term or '').strip()
        if not term or _looks_like_crm_uuid(term):
            continue
        queries.append(term)

    for term in queries:
        try:
            qs = Contact.objects.filter(
                Q(last_name__iexact=term)
                | Q(last_name__icontains=term)
                | Q(first_name__icontains=term)
            )
            # „lorenz“ exakt bevorzugen
            exact = qs.filter(last_name__iexact=term).first()
            c = exact or qs.first()
            if c and getattr(c, 'crm_id', None):
                return str(c.crm_id)
        except Exception as exc:
            log.debug('CRM name resolve fehlgeschlagen: %s', exc)

    # Elasticsearch Index „content“ (phones/name indexed)
    for term in queries:
        crm_id = _es_resolve_contact_id(term)
        if crm_id:
            return crm_id
    return bid


def _es_resolve_contact_id(q: str) -> str:
    q = (q or '').strip()
    if not q:
        return ''
    try:
        from elasticsearch import Elasticsearch

        from .inbox_service import _es_hosts

        es = Elasticsearch(_es_hosts(), request_timeout=4)
        body = {
            'size': 5,
            '_source': ['crm_id', 'name', 'phones'],
            'query': {
                'bool': {
                    'should': [
                        {'match_phrase_prefix': {'name': {'query': q, 'boost': 4}}},
                        {'multi_match': {
                            'query': q,
                            'fields': ['name^3', 'phones^2', 'emails'],
                            'fuzziness': 'AUTO',
                        }},
                    ],
                    'minimum_should_match': 1,
                }
            },
        }
        res = es.search(index='content', body=body)
        for hit in (res.get('hits') or {}).get('hits') or []:
            src = hit.get('_source') or {}
            cid = src.get('crm_id') or ''
            if cid:
                return str(cid)
    except Exception as exc:
        log.debug('ES contact resolve fehlgeschlagen: %s', exc)
    return ''


def _crm_phones_for_ref(
    ref_type: str,
    ref_id: str,
    *,
    name_hint: str = '',
) -> list[dict[str, Any]]:
    """Alle CRM-Telefone + WhatsApp-Feld; Mobil zuerst."""
    bid = _resolve_contact_crm_id(ref_type, ref_id, name_hint=name_hint)
    if not bid:
        return []
    if ref_type in ('berater', 'ansprechpartner', ''):
        mod = 'Contacts'
    elif ref_type == 'firma':
        mod = 'Accounts'
    else:
        return []

    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(raw: str, field_name: str, *, is_primary: bool = False, label: str = '') -> None:
        raw = (raw or '').strip()
        if not raw:
            return
        norm, ok = normalize_de_phone(raw)
        key = norm or re.sub(r'\D', '', raw)
        if not key or key in seen:
            return
        seen.add(key)
        out.append({
            'raw': raw,
            'norm': norm if ok else '',
            'ok': ok,
            'field_name': field_name,
            'label': label or _PHONE_LABELS.get(field_name, field_name or 'Tel'),
            'is_primary': bool(is_primary),
            'is_mobile': field_name in ('phone_mobile', 'whatsapp'),
        })

    try:
        from django.apps import apps

        Rel = apps.get_model('abpe_crm', 'CrmPhoneBeanRel')
        qs = (
            Rel.objects.filter(bean_id=bid, bean_module=mod)
            .select_related('phone')
            .order_by('-is_primary', 'field_name')
        )
        for rel in qs:
            phone = getattr(rel, 'phone', None)
            raw = (
                getattr(phone, 'phone_raw', None)
                or getattr(phone, 'phone_norm', None)
                or ''
            )
            _add(
                str(raw),
                getattr(rel, 'field_name', '') or 'phone_other',
                is_primary=bool(getattr(rel, 'is_primary', False)),
                label=getattr(rel, 'label', '') or '',
            )
    except Exception as exc:
        log.debug('CRM-Phones lookup fehlgeschlagen: %s', exc)

    if mod == 'Contacts':
        try:
            from django.apps import apps

            Contact = apps.get_model('abpe_crm', 'CrmContact')
            c = Contact.objects.filter(crm_id=bid).first()
            if c:
                wa = getattr(c, 'whatsapp_number', None) or ''
                if wa:
                    _add(str(wa), 'whatsapp', is_primary=True, label='WhatsApp')
        except Exception as exc:
            log.debug('CRM whatsapp_number fehlgeschlagen: %s', exc)

    # Mobil / WhatsApp zuerst
    out.sort(key=lambda p: (0 if p.get('is_mobile') else 1, 0 if p.get('is_primary') else 1))
    return out


def _crm_phone_for_ref(ref_type: str, ref_id: str, *, name_hint: str = '') -> str:
    """Eine bevorzugte Nummer (Mobil/WhatsApp zuerst)."""
    phones = _crm_phones_for_ref(ref_type, ref_id, name_hint=name_hint)
    for p in phones:
        if p.get('is_mobile') and (p.get('norm') or p.get('raw')):
            return p.get('norm') or p.get('raw') or ''
    for p in phones:
        if p.get('norm') or p.get('raw'):
            return p.get('norm') or p.get('raw') or ''
    return ''


def _today() -> date:
    return timezone.localdate()


def erstellen(
    *,
    art: str,
    titel: str,
    zugewiesen_an,
    faellig_am=None,
    faellig_zeit=None,
    prioritaet: int = 3,
    beschreibung: str = '',
    kanal: str = '',
    ref_type: str = '',
    ref_id: str = '',
    quelle: str = Aufgabe.Quelle.MANUELL,
    regel=None,
    parent=None,
    gruppe_id=None,
    user=None,
) -> Aufgabe:
    if faellig_am is None:
        faellig_am = _today()
    gid = gruppe_id
    if isinstance(gid, str) and gid.strip():
        try:
            gid = UUID(gid.strip())
        except (TypeError, ValueError):
            gid = None
    elif not gid:
        gid = None
    aufgabe = Aufgabe.objects.create(
        art=art,
        kanal=kanal or '',
        titel=(titel or '')[:200],
        beschreibung=beschreibung or '',
        faellig_am=faellig_am,
        faellig_zeit=faellig_zeit,
        prioritaet=prioritaet,
        zugewiesen_an=zugewiesen_an,
        ref_type=(ref_type or '')[:20],
        ref_id=str(ref_id or '')[:64],
        quelle=quelle,
        regel=regel,
        parent=parent,
        gruppe_id=gid,
    )
    aktivitaet_service.schreiben(
        medium=AktivitaetMediumForArt(art),
        titel=f'Aufgabe angelegt: {aufgabe.titel}',
        ref_type=aufgabe.ref_type,
        ref_id=aufgabe.ref_id,
        user=user or zugewiesen_an,
        details={'aufgabe_id': str(aufgabe.pk), 'art': art, 'quelle': quelle},
    )
    return aufgabe


def AktivitaetMediumForArt(art: str) -> str:
    return {
        'anruf': 'telefon',
        'email': 'email',
        'sms_messenger': 'whatsapp',
        'termin': 'termin',
        'dokument': 'dokument',
        'post': 'post',
        'radar': 'radar',
    }.get(art, 'system')


def bucket_for(aufgabe: Aufgabe, today: Optional[date] = None) -> str:
    today = today or _today()
    if aufgabe.status != Aufgabe.Status.OFFEN:
        return 'erledigt'
    if aufgabe.faellig_am < today:
        return 'ueberfaellig'
    if aufgabe.faellig_am == today:
        return 'heute'
    return 'geplant'


def due_label(aufgabe: Aufgabe, today: Optional[date] = None) -> str:
    today = today or _today()
    d = aufgabe.faellig_am
    if d < today:
        return f'seit {d.strftime("%d.%m.")}'
    if d == today:
        if aufgabe.faellig_zeit:
            return f'heute {aufgabe.faellig_zeit.strftime("%H:%M")}'
        return 'heute'
    return d.strftime('%d.%m.%Y')


_RE_HTML_URL = re.compile(
    r'(?:HTML:\s*)?(https?://[^\s<>"\']+)',
    re.I,
)


def _html_url_from_beschreibung(text: str) -> str:
    s = text or ''
    m = re.search(r'HTML:\s*(\S+)', s, re.I)
    if m:
        return m.group(1).strip()
    m = _RE_HTML_URL.search(s)
    return (m.group(1) if m else '').strip()


def _kontext_for_art(art: str) -> str:
    return {
        'anruf': 'kunde_angebot',
        'email': 'kunde_angebot',
        'sms_messenger': 'berater_ansprache',
        'wiedervorlage': 'wiedervorlage',
        'dokument': 'vertrag',
        'post': 'vertrag',
        'termin': 'termin',
        'intern': 'intern',
    }.get(art, 'intern')


def ergebnisse_fuer(aufgabe: Aufgabe) -> list[dict[str, Any]]:
    """ErgebnisTyp-Optionen fürs Popup (UI-Shape wie Demo)."""
    from .ergebnis_service import fx_labels_for

    kontext = _kontext_for_art(aufgabe.art)
    qs = ErgebnisTyp.objects.filter(aktiv=True).filter(
        Q(kontext=kontext) | Q(kontext='intern') | Q(kontext='wiedervorlage')
        | Q(code__in=('snooze', 'verworfen', 'erledigt'))
    ).order_by('sort_order', 'label')
    seen = set()
    out = []
    preferred = []
    fallback = []
    for et in qs:
        if et.code in seen:
            continue
        seen.add(et.code)
        row = {
            'id': str(et.pk),
            'code': et.code,
            'label': et.label,
            'sub': et.wirkung_status or '',
            'fx': fx_labels_for(et.code),
            'zeigt_dialog': et.zeigt_dialog,
            'eingabefelder': et.eingabefelder if isinstance(et.eingabefelder, list) else [],
        }
        if et.kontext == kontext:
            preferred.append(row)
        else:
            fallback.append(row)
    out = preferred + fallback
    if not out:
        out = [
            {'id': '', 'code': 'erledigt', 'label': 'Erledigt ✓', 'sub': '', 'fx': ['Historie-Eintrag']},
            {'id': '', 'code': 'snooze', 'label': 'Später (+1 Tag)', 'sub': '', 'fx': ['Fälligkeit +1 Tag']},
        ]
    return out


def serialize(aufgabe: Aufgabe, today: Optional[date] = None) -> dict[str, Any]:
    today = today or _today()
    b = bucket_for(aufgabe, today)
    hist = [
        f'{a.zeitpunkt.strftime("%d.%m. %H:%M")} {a.titel}'
        for a in aktivitaet_service.fuer_ref(aufgabe.ref_type, aufgabe.ref_id, limit=8)
        if a.ref_type and a.ref_id
    ]
    # Fallback: Aktivitäten zur Aufgabe selbst
    if not hist:
        from apps.abpe_shaduler.models import Aktivitaet
        hist = [
            f'{a.zeitpunkt.strftime("%d.%m. %H:%M")} {a.titel}'
            for a in Aktivitaet.objects.filter(
                details__aufgabe_id=str(aufgabe.pk),
            ).order_by('-zeitpunkt')[:8]
        ]
    ref_label = ''
    if aufgabe.ref_type or aufgabe.ref_id:
        ref_label = f'{aufgabe.ref_type} {aufgabe.ref_id}'.strip()
    crm_url = ''
    if aufgabe.ref_id:
        if aufgabe.ref_type in ('berater', 'ansprechpartner'):
            resolved = _resolve_contact_crm_id(
                aufgabe.ref_type,
                aufgabe.ref_id,
                name_hint=_name_hint_from_aufgabe(aufgabe),
            ) or aufgabe.ref_id
            crm_url = f'/crm/berater/?detail={resolved}'
        elif aufgabe.ref_type == 'firma':
            crm_url = f'/crm/kunden/?detail={aufgabe.ref_id}'
    action = {
        'anruf': ('Anrufen', 'Click-to-dial — dein Telefon klingelt zuerst.'),
        'email': ('Vorschau & senden', 'E-Mail-Studio — vorbefüllt.'),
        'sms_messenger': ('Versenden', 'Text prüfen — dann WhatsApp öffnen.'),
        'wiedervorlage': ('Geprüft — entscheiden', 'Reine Wiedervorlage.'),
        'dokument': ('Dokument bearbeiten', ''),
        'post': ('Post-Vorgang', ''),
        'termin': ('Termin öffnen', ''),
        'intern': ('Erledigen', ''),
    }.get(aufgabe.art, ('Erledigen', ''))

    whatsapp_url = ''
    phone = ''
    wa_text = ''
    phones: list[dict[str, Any]] = []
    if aufgabe.art == Aufgabe.Art.SMS_MESSENGER:
        from .whatsapp_service import build_whatsapp_link
        name_hint = _name_hint_from_aufgabe(aufgabe)
        if isinstance(aufgabe.ergebnis_daten, dict):
            phone = (
                aufgabe.ergebnis_daten.get('phone')
                or aufgabe.ergebnis_daten.get('tel')
                or ''
            )
        if not phone and 'tel:' in (aufgabe.beschreibung or '').lower():
            m = re.search(r'tel:([+\d\s\-()/]+)', aufgabe.beschreibung or '', re.I)
            if m:
                phone = m.group(1)
        phones = _crm_phones_for_ref(
            aufgabe.ref_type, aufgabe.ref_id, name_hint=name_hint,
        )
        if not phone and aufgabe.ref_id:
            phone = _crm_phone_for_ref(
                aufgabe.ref_type, aufgabe.ref_id, name_hint=name_hint,
            )
        if phone:
            norm, ok = normalize_de_phone(phone)
            if ok:
                phone = norm
        beschr = (aufgabe.beschreibung or '').strip()
        if beschr and not beschr.lower().startswith('von:') and 'mail-id:' not in beschr.lower():
            wa_text = re.sub(r'\n?tel:[^\n]+', '', beschr, flags=re.I).strip()
        if not wa_text:
            wa_text = aufgabe.titel or ''
        wa_digits = phone_to_wa_digits(phone) if phone else ''
        whatsapp_url = build_whatsapp_link(wa_digits, wa_text) if wa_digits else ''

    return {
        'id': str(aufgabe.pk),
        'art': aufgabe.art,
        'kanal': aufgabe.kanal,
        'titel': aufgabe.titel,
        'beschreibung': aufgabe.beschreibung,
        'status': aufgabe.status,
        'prioritaet': aufgabe.prioritaet,
        'ref_type': aufgabe.ref_type,
        'ref_id': aufgabe.ref_id,
        'ref_label': ref_label,
        'crm_url': crm_url,
        'gruppe_id': str(aufgabe.gruppe_id) if aufgabe.gruppe_id else None,
        'parent_id': str(aufgabe.parent_id) if aufgabe.parent_id else None,
        'html_url': _html_url_from_beschreibung(aufgabe.beschreibung),
        'faellig_am': aufgabe.faellig_am.isoformat(),
        'faellig_zeit': aufgabe.faellig_zeit.strftime('%H:%M') if aufgabe.faellig_zeit else None,
        'due_label': due_label(aufgabe, today),
        'ueberfaellig': b == 'ueberfaellig',
        'bucket': b,
        'day': aufgabe.faellig_am.day,
        'month': aufgabe.faellig_am.month,
        'year': aufgabe.faellig_am.year,
        'zeit': aufgabe.faellig_zeit.strftime('%H:%M') if aufgabe.faellig_zeit else None,
        'action_label': action[0],
        'action_note': action[1],
        'whatsapp_url': whatsapp_url,
        'phone': phone,
        'phones': phones,
        'wa_text': wa_text,
        'excerpt': {
            'stand': (aufgabe.beschreibung or '')[:240],
            'hist': hist,
        },
        'results': ergebnisse_fuer(aufgabe),
    }


def liste(
    *,
    user,
    status: str = Aufgabe.Status.OFFEN,
    include_others: bool = False,
) -> list[Aufgabe]:
    qs = Aufgabe.objects.all()
    if status:
        qs = qs.filter(status=status)
    if not include_others:
        qs = qs.filter(zugewiesen_an=user)
    return list(qs.select_related('ergebnis', 'regel', 'zugewiesen_an').order_by(
        'faellig_am', 'prioritaet', 'titel',
    ))


def stats(user) -> dict[str, Any]:
    today = _today()
    offen = Aufgabe.objects.filter(zugewiesen_an=user, status=Aufgabe.Status.OFFEN)
    heute = offen.filter(faellig_am=today).count()
    ueber = offen.filter(faellig_am__lt=today).count()
    geplant = offen.filter(faellig_am__gt=today).count()
    erledigt_heute = Aufgabe.objects.filter(
        zugewiesen_an=user,
        status=Aufgabe.Status.ERLEDIGT,
        erledigt_am__date=today,
    ).count()
    radar_a = radar_b = 0
    try:
        from apps.abpe_shaduler.models import RadarItem, RadarConsultantItem
        radar_a = RadarItem.objects.filter(status='neu').count()
        radar_b = RadarConsultantItem.objects.filter(
            status='neu', deleted_at__isnull=True,
        ).count()
    except Exception:
        pass
    return {
        'ok': True,
        'demo': False,
        'heute': heute,
        'ueberfaellig': ueber,
        'geplant': geplant,
        'erledigt_heute': erledigt_heute,
        'badges': {
            'aufgaben': heute + ueber,
            'posteingang': _inbox_unread_badge(user),
            'radar_anfragen': radar_a,
            'radar_berater': radar_b,
        },
    }


def _inbox_unread_badge(user) -> int:
    try:
        from . import inbox_service
        return int(inbox_service.unread_count(user) or 0)
    except Exception:
        return 0


def badge(user) -> int:
    return stats(user)['badges']['aufgaben']


def fuer_ref(ref_type: str, ref_id: str, status: str = Aufgabe.Status.OFFEN):
    qs = Aufgabe.objects.filter(ref_type=ref_type, ref_id=str(ref_id))
    if status:
        qs = qs.filter(status=status)
    return list(qs.order_by('faellig_am', 'prioritaet'))


def snooze(aufgabe: Aufgabe, days: int = 1, user=None) -> Aufgabe:
    aufgabe.faellig_am = aufgabe.faellig_am + timedelta(days=max(1, days))
    aufgabe.save(update_fields=['faellig_am', 'updated_at'])
    aktivitaet_service.schreiben(
        medium='system',
        titel=f'Verschoben auf {aufgabe.faellig_am:%d.%m.%Y}: {aufgabe.titel}',
        ref_type=aufgabe.ref_type,
        ref_id=aufgabe.ref_id,
        user=user,
        details={'aufgabe_id': str(aufgabe.pk), 'snooze_days': days},
    )
    return aufgabe


def delegieren(aufgabe: Aufgabe, an_user, user=None) -> Aufgabe:
    alt = aufgabe.zugewiesen_an_id
    aufgabe.zugewiesen_an = an_user
    aufgabe.status = Aufgabe.Status.DELEGIERT
    aufgabe.save(update_fields=['zugewiesen_an', 'status', 'updated_at'])
    # Wieder öffnen beim neuen Owner
    aufgabe.status = Aufgabe.Status.OFFEN
    aufgabe.save(update_fields=['status', 'updated_at'])
    aktivitaet_service.schreiben(
        medium='system',
        titel=f'Delegiert: {aufgabe.titel}',
        ref_type=aufgabe.ref_type,
        ref_id=aufgabe.ref_id,
        user=user,
        details={
            'aufgabe_id': str(aufgabe.pk),
            'von': alt,
            'an': an_user.pk,
        },
    )
    return aufgabe
