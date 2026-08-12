# apps/abpe_crm/services/cdr_resolver.py
"""
CDR-Resolver — Single Source of Truth fuer:
  - is_internal_ext(norm)  : Nebenstelle erkennen
  - classify(...)          : Richtung (incoming/outgoing/internal) + System-Flag
  - resolve_party(norm)    : 5-Stufen-Kaskade Nummer -> Kontakt/Firma + Konfidenz

Genutzt von: views_cdr.py (Lese-API), sync_cdr_pbx_db.py (Sync), seed_cdr_test.py.
Die Logik ist gegen echte PBX-Daten verifiziert (Seed, 2026-06-27).
"""
import re

PARK_SLOTS = {str(n) for n in range(700, 710)}
SYS_APPS   = {'Park', 'ParkedCall', 'ConfBridge', 'MeetMe'}
SYS_DST    = {'STARTMEETME'}


def channel_ext(chan):
    """Nebenstellen-Nummer aus einem Kanalnamen ziehen: SIP/12-xxxx -> '12'."""
    if not chan:
        return None
    m = re.match(r'(?:SIP|PJSIP)/(\d+)-', chan)
    return m.group(1) if m else None


def is_internal_ext(norm):
    """Nebenstelle = kurz, rein numerisch, KEIN 0049-Praefix."""
    return bool(norm) and norm.isdigit() and len(norm) <= 5 and not norm.startswith('0049')


def classify(app, src, dst, chan, dchan):
    """
    Liefert (direction, ext, party_raw, is_system).
      direction: 'incoming' | 'outgoing' | 'internal' | ''
      ext:       eigene Nebenstelle des Anrufs (aus Kanal)
      party_raw: die ROHE Gegennummer (vor Normalisierung), '' wenn keine
      is_system: True bei Park/Conf/Meetme-Zeilen
    """
    if app in SYS_APPS or dst in SYS_DST or dst in PARK_SLOTS:
        return ('', '', '', True)
    a_ext = channel_ext(chan)
    b_ext = channel_ext(dchan)
    if a_ext and b_ext:
        return ('internal', a_ext, '', False)
    if a_ext and not b_ext:
        return ('outgoing', a_ext, dst, False)
    if b_ext and not a_ext:
        return ('incoming', b_ext, src, False)
    return ('', '', '', False)


def resolve_party(norm):
    """
    5-Stufen-Kaskade (Person vor Firma, aber nur bei EINDEUTIGER Person):
      1) genau 1 Contact            -> Person          (exact)
      2) mehrere Contacts, 1 Firma  -> Firma + Kand.   (company)
      3) mehrere Contacts, !=1 Firma-> nicht raten     (multi)
      4) nur Account-Treffer        -> Firma           (exact, Accounts)
      5) nichts                     -> roh             ('')
    Rueckgabe-Dict: {crm_id, module, name, conf, cands}
    """
    from apps.abpe_crm.models import (
        CrmPhoneBeanRel, CrmContact, CrmAccount, CrmAccountContacts,
    )
    r = {'crm_id': None, 'module': '', 'name': '', 'conf': '', 'cands': []}
    if not norm or is_internal_ext(norm):
        return r

    cids = list(dict.fromkeys(
        CrmPhoneBeanRel.objects.filter(phone__phone_norm=norm, bean_module='Contacts')
        .values_list('bean_id', flat=True)))

    # Stufe 1: genau ein Contact -> Person
    if len(cids) == 1:
        c = CrmContact.objects.filter(crm_id=cids[0]).first()
        if c:
            r.update(crm_id=c.crm_id, module='Contacts', name=c.full_name, conf='exact')
        return r

    # Stufe 2/3: mehrere Contacts -> Firma wenn alle dieselbe, sonst multi
    if len(cids) > 1:
        contacts = {c.crm_id: c for c in CrmContact.objects.filter(crm_id__in=cids)}
        accts, anames = set(), {}
        for cid in cids:
            c = contacts.get(cid)
            if not c:
                continue
            r['cands'].append({'crm_id': cid, 'name': c.full_name, 'module': 'Contacts'})
            link = CrmAccountContacts.objects.filter(
                contact__crm_id=cid).select_related('account').first()
            if link and link.account:
                accts.add(link.account.crm_id)
                anames[link.account.crm_id] = link.account.name
        if len(accts) == 1:
            aid = next(iter(accts))
            r.update(crm_id=aid, module='Accounts', name=anames.get(aid, ''), conf='company')
        else:
            r.update(conf='multi')
        return r

    # Stufe 4: kein Contact, aber Account direkt -> Firma
    acc_rel = CrmPhoneBeanRel.objects.filter(
        phone__phone_norm=norm, bean_module='Accounts').first()
    if acc_rel:
        a = CrmAccount.objects.filter(crm_id=acc_rel.bean_id).first()
        if a:
            r.update(crm_id=a.crm_id, module='Accounts', name=a.name or '', conf='exact')

    # Stufe 5: nichts -> r bleibt leer
    return r


def reresolve_number(norm):
    """
    Nachtraegliches Re-Resolve: alle bisher UNAUFGELOESTEN CrmCdr-Zeilen, deren
    party_number == norm ist, erneut aufloesen und (falls jetzt Treffer) updaten.
    Wird vom phone_add-Hook aufgerufen, wenn eine neue Nummer angelegt wurde.
    Gibt die Anzahl aktualisierter Zeilen zurueck.
    """
    if not norm or is_internal_ext(norm):
        return 0
    from apps.abpe_crm.models import CrmCdr
    res = resolve_party(norm)
    if not (res['crm_id'] or res['conf']):
        return 0
    return CrmCdr.objects.filter(
        party_crm_id__isnull=True, is_system=False, party_number=norm
    ).update(
        party_crm_id=res['crm_id'], party_module=res['module'],
        party_name=res['name'], match_confidence=res['conf'],
        match_candidates=res['cands'],
    )

