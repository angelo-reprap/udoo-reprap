"""
matching_source_join.py — Gulp/FLM-Treffer gegen CRM/Consultant abgleichen.

Kein CV-Update. Nur Lookup:
  gulp_id → ContactCstm.gulp_id_c / Radar
  fm_id / Profil-Slug / Name → CRM + optional Consultant
  → E-Mail/Telefon aus CRM, wenn vorhanden
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_RE_FM_SLUG = re.compile(
    r'(?:https?://)?(?:www\.)?freelancermap\.de/profil/([A-Za-z0-9][A-Za-z0-9\-_/]*)',
    re.I,
)
_RE_FM_ID = re.compile(r'-(\d{4,8})$')
_RE_PLACEHOLDER_NAME = re.compile(
    r'^(?:gulp|fm|freelancermap)\s*[\dA-Fa-f]{3,}$',
    re.I,
)


def is_placeholder_name(name: str) -> bool:
    """Gulp/FLM-Listen liefern oft nur 'Gulp 384563' / 'FM 12345'."""
    n = (name or '').strip()
    if not n:
        return True
    if _RE_PLACEHOLDER_NAME.match(n):
        return True
    if n.lower() in ('gulp ?', 'freelancermap', 'unbekannt'):
        return True
    return False


def clean_display_name(name: str) -> str:
    n = (name or '').strip()
    return '' if is_placeholder_name(n) else n


@dataclass
class JoinHit:
    """Ergebnis eines Abgleichs gegen den Bestand."""
    known: bool = False
    join_via: str = ''
    crm_contact_id: str = ''
    consultant: Any = None
    display_name: str = ''
    email: str = ''
    phone: str = ''
    can_contact: bool = False  # E-Mail oder Telefon vorhanden
    profile_refresh_suggested: bool = False  # extern ggf. neuer — kein Auto-Update
    notes: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        c = self.consultant
        return {
            'known': self.known,
            'join_via': self.join_via,
            'crm_contact_id': self.crm_contact_id,
            'consultant_id': getattr(c, 'id', None) if c is not None else None,
            'consultant_aid': getattr(c, 'aid', '') if c is not None else '',
            'display_name': self.display_name,
            'email': self.email,
            'phone': self.phone,
            'can_contact': self.can_contact,
            'profile_refresh_suggested': self.profile_refresh_suggested,
            'notes': list(self.notes),
            # Shortlist-Status
            'crm_link_status': (
                'known' if (self.known and self.can_contact)
                else ('known_no_contact' if self.known else 'backoffice')
            ),
        }


def _crm_models():
    from django.apps import apps
    Contact = apps.get_model('abpe_crm', 'CrmContact')
    Cstm = apps.get_model('abpe_crm', 'CrmContactCstm')
    return Contact, Cstm


def _consultant_pool():
    from django.apps import apps
    Consultant = apps.get_model('cv_extractor', 'Consultant')
    return Consultant.objects.filter(
        status__in=['completed', 'validated', 'profile_ready'],
    ).exclude(aid__endswith='-en')


def _contact_channels(crm_id: str) -> Tuple[str, str]:
    """Primäre E-Mail + Telefon aus CRM-Relationen."""
    email = ''
    phone = ''
    if not crm_id:
        return email, phone
    try:
        from apps.abpe_crm.models import CrmEmailAddrBeanRel
        rows = (
            CrmEmailAddrBeanRel.objects.filter(
                bean_id=crm_id,
                bean_module__iexact='Contacts',
            )
            .select_related('email_address')
            .order_by('-primary_address')
        )
        for rel in rows[:5]:
            ea = getattr(rel, 'email_address', None)
            addr = (getattr(ea, 'email_address', None) or '').strip() if ea else ''
            if addr and '@' in addr and not getattr(ea, 'invalid_email', False):
                email = addr
                break
    except Exception as exc:
        logger.debug('email lookup: %s', exc)

    try:
        from apps.abpe_crm.models import CrmPhoneBeanRel
        rels = (
            CrmPhoneBeanRel.objects.filter(
                bean_id=crm_id,
                bean_module__iexact='Contacts',
            )
            .select_related('phone')
            .order_by('-is_primary')[:10]
        )
        for rel in rels:
            ph = getattr(rel, 'phone', None)
            raw = (
                (getattr(ph, 'phone_raw', None) or getattr(ph, 'phone_norm', None) or '')
                if ph else ''
            ).strip()
            if raw:
                phone = raw
                break
    except Exception as exc:
        logger.debug('phone lookup: %s', exc)
    return email, phone


def _finish(
    *,
    contact=None,
    consultant=None,
    join_via: str,
    display_name: str = '',
    refresh_suggested: bool = False,
    notes: Optional[List[str]] = None,
) -> JoinHit:
    crm_id = ''
    name = clean_display_name(display_name)
    if contact is not None:
        crm_id = str(getattr(contact, 'crm_id', '') or '')
        if not name:
            name = ' '.join(
                x for x in [
                    getattr(contact, 'first_name', None) or '',
                    getattr(contact, 'last_name', None) or '',
                ] if x
            ).strip()
    if consultant is not None and not name:
        name = (
            getattr(consultant, 'full_name', None)
            or f"{getattr(consultant, 'first_name', '')} {getattr(consultant, 'last_name', '')}"
        ).strip()
    email, phone = _contact_channels(crm_id) if crm_id else ('', '')
    if not email and consultant is not None:
        email = (getattr(consultant, 'email', None) or '').split(';')[0].strip()
    if not phone and consultant is not None:
        for attr in ('phone', 'mobile', 'telefon'):
            phone = (getattr(consultant, attr, None) or '').strip()
            if phone:
                break
    known = bool(crm_id or consultant is not None)
    return JoinHit(
        known=known,
        join_via=join_via,
        crm_contact_id=crm_id,
        consultant=consultant,
        display_name=name,
        email=email,
        phone=phone,
        can_contact=bool(email or phone),
        profile_refresh_suggested=bool(refresh_suggested and known),
        notes=list(notes or []),
    )


def _resolve_consultant_from_crm(contact, cstm=None, *, extra_email: str = '') -> Tuple[Any, str]:
    """
    Contact → Consultant über Radar/E-Mail/Name.
    E-Mail bevorzugt aus CRM-Kanälen (_contact_channels), nicht nur Contact-Feldern.
    """
    if contact is None:
        return None, ''
    crm_id = str(getattr(contact, 'crm_id', '') or '').strip()
    # 1) offizieller Probe-Resolver (Radar, gulp_id, Contact-Felder, Name)
    try:
        from apps.abpe_shaduler.services import matching_weight_probe as mwp
        cons, via = mwp.resolve_consultant_for_contact(
            crm_id=crm_id,
            cstm=cstm,
            contact=contact,
        )
        if cons is not None:
            return cons, via or 'contact_consultant'
    except Exception as exc:
        logger.debug('resolve_consultant_for_contact: %s', exc)

    pool = _consultant_pool()
    # 2) E-Mail aus CRM-Kanälen / explizit
    email = (extra_email or '').strip()
    if not email and crm_id:
        email, _phone = _contact_channels(crm_id)
    if email and '@' in email:
        hit = pool.filter(email__iexact=email).order_by('-created_at').first()
        if hit:
            return hit, 'crm_email'
        # SuiteCRM-Mails können ;-getrennt im Consultant.email stehen
        hit = pool.filter(email__icontains=email).order_by('-created_at').first()
        if hit:
            return hit, 'crm_email_contains'

    # 3) eindeutiger Name im Consultant-Pool
    first = (getattr(contact, 'first_name', None) or '').strip()
    last = (getattr(contact, 'last_name', None) or '').strip()
    if first and last and len(last) >= 2:
        qs = pool.filter(first_name__iexact=first, last_name__iexact=last)
        dirs = list(qs.values_list('consultant_dir', flat=True).distinct()[:5])
        if len({(d or '').lower().strip() for d in dirs}) == 1:
            hit = qs.order_by('-created_at').first()
            if hit:
                return hit, 'crm_name'
    return None, ''


def _gulp_id_variants(gid: str) -> List[str]:
    """CRM speichert gulp_id_c oft numerisch ohne führende Nullen."""
    g = str(gid or '').strip()
    if not g:
        return []
    out = [g]
    if g.isdigit():
        stripped = g.lstrip('0') or '0'
        if stripped not in out:
            out.append(stripped)
        # führende Nullen bis Feldlänge 16
        for w in (6, 7, 8):
            padded = g.zfill(w) if len(g) <= w else g
            if padded not in out:
                out.append(padded)
    return out


def resolve_gulp_hit(hit: Dict[str, Any]) -> JoinHit:
    """Gulp-Listen-Treffer → CRM/Consultant per gulp_id."""
    gid = str(hit.get('gulp_id') or '').strip()
    mongo = str(hit.get('mongo_id') or '').strip()
    if (not gid or len(gid) < 3) and mongo:
        gid = mongo
    if not gid or len(gid) < 3:
        return JoinHit(notes=['keine gulp_id'])

    Contact, Cstm = _crm_models()
    contact = None
    cstm = None
    variants = _gulp_id_variants(gid)
    if Cstm is not None:
        from django.db.models import Q
        q = Q()
        for v in variants:
            q |= Q(gulp_id_c=v)
        cstm = (
            Cstm.objects.filter(q)
            .exclude(gulp_id_c__isnull=True)
            .exclude(gulp_id_c='')
            .select_related('contact')
            .first()
        )
        if cstm is not None:
            contact = getattr(cstm, 'contact', None)
            if contact is None:
                cid = getattr(cstm, 'contact_id', None) or getattr(cstm, 'id_c', None)
                if cid and Contact is not None:
                    contact = Contact.objects.filter(crm_id=cid).first()

    consultant = None
    join_via = ''
    # Radar FK (gulp_id oder mongo)
    try:
        from django.apps import apps
        from django.db.models import Q
        Radar = apps.get_model('abpe_shaduler', 'RadarConsultantItem')
        rq = Q()
        for v in variants:
            rq |= Q(gulp_id=v)
        if mongo:
            rq |= Q(gulp_id=mongo)
        radar = (
            Radar.objects.filter(rq, deleted_at__isnull=True)
            .select_related('consultant')
            .order_by('-updated_at')
            .first()
        )
        if radar:
            if not contact and radar.crm_contact_id and Contact is not None:
                contact = Contact.objects.filter(crm_id=radar.crm_contact_id).first()
                if contact:
                    join_via = 'radar_crm'
            if radar.consultant_id:
                c = radar.consultant
                if c and not str(getattr(c, 'aid', '') or '').endswith('-en'):
                    consultant = c
                    join_via = join_via or 'radar_gulp'
    except Exception as exc:
        logger.debug('radar gulp join: %s', exc)

    if consultant is None:
        pool = _consultant_pool()
        from django.db.models import Q
        hit_c = None
        for v in variants:
            hit_c = pool.filter(consultant_dir=v).order_by('-created_at').first()
            if hit_c:
                consultant, join_via = hit_c, 'gulp_id_dir'
                break
        if consultant is None:
            qdir = Q()
            for v in variants:
                qdir |= Q(consultant_dir__endswith=f'_{v}') | Q(consultant_dir__endswith=f'-{v}')
            hit_c = pool.filter(qdir).order_by('-created_at').first()
            if hit_c:
                consultant, join_via = hit_c, 'gulp_id_dir_suffix'

    # CRM-Kontakt → Consultant (Radar / E-Mail / Name) — bisher fehlte dieser Schritt bei Gulp
    if consultant is None and contact is not None:
        email_hint, _ = _contact_channels(str(getattr(contact, 'crm_id', '') or ''))
        cons2, via2 = _resolve_consultant_from_crm(
            contact, cstm, extra_email=email_hint,
        )
        if cons2 is not None:
            consultant = cons2
            join_via = via2 or join_via or 'gulp_id_c'

    if contact is None and consultant is None:
        return JoinHit(notes=[f'gulp_id={gid} unbekannt im Bestand'])

    return _finish(
        contact=contact,
        consultant=consultant,
        join_via=join_via or 'gulp_id_c',
        display_name=(hit.get('name') or ''),
        refresh_suggested=True,  # Gulp-Liste kann neuer sein als CV
        notes=[f'gulp_id={gid}'],
    )


def _parse_fm_from_url(url: str) -> Tuple[str, str]:
    url = (url or '').strip()
    slug = ''
    fm_id = ''
    m = _RE_FM_SLUG.search(url)
    if m:
        slug = m.group(1).strip().strip('/')
        mid = _RE_FM_ID.search(slug)
        if mid:
            fm_id = mid.group(1)
    return slug, fm_id


def resolve_flm_hit(hit: Dict[str, Any]) -> JoinHit:
    """
    FLM-Treffer → CRM:
      1) fm_id / Profil-Slug in freelancermap_profil_c
      2) eindeutiger Vor+Nachname
    """
    fm_id = str(hit.get('fm_id') or '').strip()
    slug = str(hit.get('fm_slug') or '').strip().strip('/')
    if not slug:
        slug, sid = _parse_fm_from_url(hit.get('profil_url') or hit.get('url') or '')
        if sid and not fm_id:
            fm_id = sid
    if slug and not fm_id:
        mid = _RE_FM_ID.search(slug)
        if mid:
            fm_id = mid.group(1)

    Contact, Cstm = _crm_models()
    contact = None
    join_via = ''

    if Cstm is not None and (fm_id or slug):
        qs = Cstm.objects.exclude(freelancermap_profil_c__isnull=True).exclude(
            freelancermap_profil_c='',
        )
        if fm_id:
            cstm = qs.filter(freelancermap_profil_c__icontains=fm_id).select_related(
                'contact'
            ).first()
            if cstm:
                contact = getattr(cstm, 'contact', None) or Contact.objects.filter(
                    crm_id=getattr(cstm, 'contact_id', None) or getattr(cstm, 'id_c', None)
                ).first()
                join_via = 'flm_id'
        if contact is None and slug:
            cstm = qs.filter(freelancermap_profil_c__icontains=slug).select_related(
                'contact'
            ).first()
            if cstm:
                contact = getattr(cstm, 'contact', None) or Contact.objects.filter(
                    crm_id=getattr(cstm, 'contact_id', None) or getattr(cstm, 'id_c', None)
                ).first()
                join_via = 'flm_slug'

    # Name (nur wenn eindeutig; Platzhalter/Titel überspringen)
    name = clean_display_name(hit.get('name') or '')
    if not name:
        fn = clean_display_name(hit.get('first_name') or '')
        ln = clean_display_name(hit.get('last_name') or '')
        if fn and ln:
            name = f'{fn} {ln}'.strip()
    first = last = ''
    # echte Personennamen, keine Titel-Zeilen
    if name and '|' not in name and len(name.split()) <= 4 and not name.lower().startswith(
        ('full-stack', 'backend', 'senior', 'junior', 'software', 'it berater')
    ):
        parts = name.split()
        if len(parts) >= 2:
            first, last = parts[0], parts[-1]

    if contact is None and first and last and Contact is not None:
        qs = Contact.objects.filter(first_name__iexact=first, last_name__iexact=last)
        n = qs.count()
        if n == 1:
            contact = qs.first()
            join_via = 'name'
        elif n > 1:
            return JoinHit(
                notes=[f'Name {first} {last} mehrdeutig ({n} CRM-Kontakte) — Backoffice'],
            )

    consultant = None
    cstm_for_link = None
    if contact is not None and Cstm is not None:
        cstm_for_link = Cstm.objects.filter(
            contact_id=contact.crm_id
        ).first() or getattr(contact, 'cstm', None)
    if contact is not None:
        email_hint, _ = _contact_channels(str(getattr(contact, 'crm_id', '') or ''))
        cons2, via2 = _resolve_consultant_from_crm(
            contact, cstm_for_link, extra_email=email_hint,
        )
        if cons2 is not None:
            consultant = cons2
            if not join_via or join_via in ('name', 'flm_id', 'flm_slug'):
                # join_via behalten wenn flm_*, aber CV-Pfad dokumentieren
                join_via = f'{join_via}+{via2}' if join_via else via2

    if contact is None and consultant is None:
        return JoinHit(notes=[
            f'FLM unbekannt fm_id={fm_id or "-"} slug={slug or "-"} name={name or "-"}'
        ])

    return _finish(
        contact=contact,
        consultant=consultant,
        join_via=join_via or 'flm',
        display_name=name,
        refresh_suggested=True,
        notes=[f'fm_id={fm_id}', f'slug={slug}'] if (fm_id or slug) else [],
    )
