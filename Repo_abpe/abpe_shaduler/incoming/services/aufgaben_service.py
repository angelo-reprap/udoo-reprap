"""aufgaben_service — Fassade: erstellen, erledigen, fuer_ref, badge (Kap. 1)."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

from django.db.models import Q
from django.utils import timezone

from apps.abpe_shaduler.models import Aufgabe, ErgebnisTyp

from . import aktivitaet_service


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
        gruppe_id=gruppe_id,
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
    action = {
        'anruf': ('Anrufen', 'Click-to-dial — dein Telefon klingelt zuerst.'),
        'email': ('Vorschau & senden', 'E-Mail-Studio — vorbefüllt.'),
        'sms_messenger': ('In WhatsApp öffnen', 'Text vorbefüllt — nur Senden.'),
        'wiedervorlage': ('Geprüft — entscheiden', 'Reine Wiedervorlage.'),
        'dokument': ('Dokument bearbeiten', ''),
        'post': ('Post-Vorgang', ''),
        'termin': ('Termin öffnen', ''),
        'intern': ('Erledigen', ''),
    }.get(aufgabe.art, ('Erledigen', ''))

    whatsapp_url = ''
    if aufgabe.art == Aufgabe.Art.SMS_MESSENGER:
        from .whatsapp_service import build_whatsapp_link
        phone = ''
        if isinstance(aufgabe.ergebnis_daten, dict):
            phone = aufgabe.ergebnis_daten.get('phone') or aufgabe.ergebnis_daten.get('tel') or ''
        # optional in beschreibung: "tel:+49123..."
        if not phone and 'tel:' in (aufgabe.beschreibung or '').lower():
            import re
            m = re.search(r'tel:([+\d\s\-()/]+)', aufgabe.beschreibung or '', re.I)
            if m:
                phone = m.group(1)
        text = aufgabe.beschreibung or aufgabe.titel
        whatsapp_url = build_whatsapp_link(phone, text) if phone else ''

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
            'radar_anfragen': 0,
            'radar_berater': 0,
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
