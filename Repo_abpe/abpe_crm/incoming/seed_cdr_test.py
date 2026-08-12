# apps/abpe_crm/seed_cdr_test.py
# Wegwerf-Seed: befuellt CrmCdr mit echten CDR-Zeilen aus dem PBX-Dump
# plus 1 konstruierte PIRACON-Zeile (company-Fall).
# Ausfuehren:  python manage.py shell < apps/abpe_crm/seed_cdr_test.py
import re
from datetime import datetime
from django.utils import timezone
from apps.abpe_crm.services.normalize_phone_nr import normalize_phone
from apps.abpe_crm.models import (
    CrmCdr, CrmPhoneBeanRel, CrmContact, CrmAccount, CrmAccountContacts,
)

PARK_SLOTS = {str(n) for n in range(700, 710)}
SYS_APPS   = {'Park', 'ParkedCall', 'ConfBridge', 'MeetMe'}
SYS_DST    = {'STARTMEETME'}

def channel_ext(chan):
    if not chan:
        return None
    m = re.match(r'(?:SIP|PJSIP)/(\d+)-', chan)
    return m.group(1) if m else None

def is_internal_ext(norm):
    return bool(norm) and norm.isdigit() and len(norm) <= 5 and not norm.startswith('0049')

def classify(app, src, dst, chan, dchan):
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

def resolve(norm):
    # 5-Stufen-Kaskade (Person vor Firma, aber nur bei EINDEUTIGER Person):
    #  1) genau 1 Contact            -> Person          (exact)
    #  2) mehrere Contacts, 1 Firma  -> Firma + Kand.   (company)
    #  3) mehrere Contacts, !=1 Firma-> nicht raten     (multi)
    #  4) nur Account-Treffer        -> Firma           (exact, Accounts)
    #  5) nichts                     -> roh             ('')
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
            link = CrmAccountContacts.objects.filter(contact__crm_id=cid).select_related('account').first()
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
    acc_rel = CrmPhoneBeanRel.objects.filter(phone__phone_norm=norm, bean_module='Accounts').first()
    if acc_rel:
        a = CrmAccount.objects.filter(crm_id=acc_rel.bean_id).first()
        if a:
            r.update(crm_id=a.crm_id, module='Accounts', name=a.name or '', conf='exact')

    # Stufe 5: nichts -> r bleibt leer
    return r

# (calldate, src, dst, channel, dstchannel, lastapp, duration, billsec, disposition, uniqueid)
ROWS = [
    ('2026-06-27 12:40:56', '015758750109', '612', 'SIP/EasySIP8867-in-0000017b', 'SIP/12-0000017c', 'Dial', 2, 0, 'NO ANSWER', '1782556856.7348'),
    ('2026-06-26 18:10:09', '01788886712', '124', 'SIP/EasySIP8867-out-00000179', 'PJSIP/124-0000017f', 'Dial', 19, 19, 'ANSWERED', '1782490194.7305'),
    ('2026-06-26 18:02:26', '0049617188670', '01788886712', 'SIP/12-00000176', 'SIP/EasySIP8867-out-00000177', 'Dial', 90, 87, 'ANSWERED', '1782489746.7286'),
    ('2026-06-26 18:22:08', '12', '124', 'SIP/12-0000017a', 'PJSIP/124-00000180', 'Dial', 18, 14, 'ANSWERED', '1782490928.7331'),
    ('2026-06-26 17:05:16', '12', 'STARTMEETME', 'SIP/12-00000174', '', 'ConfBridge', 31, 31, 'ANSWERED', '1782486251.7226'),
    ('2026-06-26 17:05:13', '124', '701', 'PJSIP/124-0000017d', '', 'ParkedCall', 2, 0, 'ANSWERED', '1782486313.7240'),
    ('2026-06-26 16:30:00', '07144 5011 672', '124', 'SIP/EasySIP8867-in-00000999', 'PJSIP/124-00000999', 'Dial', 120, 110, 'ANSWERED', 'SEED-PIRACON-0001'),
    ('2026-06-26 16:45:00', '07144 5011 673', '124', 'SIP/EasySIP8867-in-00000aaa', 'PJSIP/124-00000aaa', 'Dial', 60, 55, 'ANSWERED', 'SEED-PIRACON-FAX-0002'),
    ('2026-06-26 16:45:00', '07144 5011 673', '124', 'SIP/EasySIP8867-in-00000aaa', 'PJSIP/124-00000aaa', 'Dial', 60, 55, 'ANSWERED', 'SEED-PIRACON-FAX-0002'),
]

created = 0
print("\n%-19s %-9s %-9s %-9s %-9s %s" % ("calldate", "richtung", "bill/dur", "disp", "conf", "party"))
print("-" * 92)
for (cd, src, dst, chan, dchan, app, dur, bill, disp, uid) in ROWS:
    direction, ext, party_raw, is_sys = classify(app, src, dst, chan, dchan)
    src_norm = normalize_phone(src)
    dst_norm = normalize_phone(dst)
    party_norm = normalize_phone(party_raw) if party_raw else ''
    res = resolve(party_norm) if not is_sys else {'crm_id': None, 'module': '', 'name': '', 'conf': '', 'cands': []}
    dt = timezone.make_aware(datetime.strptime(cd, '%Y-%m-%d %H:%M:%S'))
    _, was_created = CrmCdr.objects.update_or_create(
        uniqueid=uid,
        defaults=dict(
            calldate=dt, src=src, dst=dst, channel=chan, dstchannel=dchan,
            lastapp=app, duration=dur, billsec=bill, disposition=disp,
            src_norm=src_norm, dst_norm=dst_norm, direction=direction, ext=ext,
            party_number=party_norm, party_crm_id=res['crm_id'],
            party_module=res['module'], party_name=res['name'],
            match_confidence=res['conf'], match_candidates=res['cands'], is_system=is_sys,
        ),
    )
    created += 1 if was_created else 0
    tag = 'SYSTEM' if is_sys else (direction or '-')
    pn = res['name'] or (party_norm or '-')
    if res['conf'] == 'multi':
        pn += "  (?%d Kandidaten)" % len(res['cands'])
    dauer = "%s/%ss" % (bill, dur)
    print("%-19s %-9s %-9s %-9s %-9s %s" % (cd, tag, dauer, disp, res['conf'] or '-', pn))

print("-" * 92)
print("\nGesamt CrmCdr-Zeilen: %d  (neu angelegt: %d)" % (CrmCdr.objects.count(), created))
