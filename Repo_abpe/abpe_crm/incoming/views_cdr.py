"""
abpe_crm/views_cdr.py
CDR-Anrufliste API — ausgelagert aus views.py (Session 6).

Enthaelt api_telefon_cdr() mit Erweiterungen fuer das Anrufliste-Filter-
und Sortier-Feature (Session 6): sort_by/sort_dir (Zeit oder Gespraechs-
dauer, je auf-/absteigend), hide_system (blendet Park-Slot- und Konferenz-
System-Eintraege aus).

login_or_token_required ist in views.py definiert und wird von dort
importiert, damit Token-Auth (Softphone) und Session-Auth (Browser)
weiterhin gleich funktionieren wie zuvor.
"""
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods


def api_telefon_cdr(request):
    """CDR-Anrufliste mit Kontakt-Matching gegen CrmPhoneBeanRel"""
    extension   = request.GET.get('extension', '').strip()
    mode        = request.GET.get('mode', 'all')
    days        = int(request.GET.get('days', 30))
    _limit_raw  = request.GET.get('limit')
    limit       = int(_limit_raw) if _limit_raw else None
    sort_by     = request.GET.get('sort_by', 'calldate')
    sort_dir    = request.GET.get('sort_dir', 'DESC')
    hide_system = request.GET.get('hide_system', '0') in ('1', 'true', 'True')
    date_from   = request.GET.get('date_from', '').strip() or None
    date_to     = request.GET.get('date_to', '').strip() or None
    if not extension:
        return JsonResponse({'error': 'extension fehlt'}, status=400)
    try:
        from apps.abpe_crm.services.cdr_client import get_cdr_for_extension
        from apps.abpe_crm.services.normalize_phone_nr import normalize_phone
        from apps.abpe_crm.models import (
            CrmPhoneBeanRel, CrmContact, CrmAccount, CrmEmailAddrBeanRel,
        )
        extensions = [e.strip() for e in extension.split(',') if e.strip()]
        if len(extensions) > 1:
            rows = []
            for ext in extensions:
                rows += get_cdr_for_extension(
                    ext, mode=mode, days=days, limit=limit,
                    sort_by=sort_by, sort_dir=sort_dir, hide_system=hide_system,
                    date_from=date_from, date_to=date_to,
                )
            reverse = (str(sort_dir).upper() != 'ASC')
            sort_key = (
                (lambda r: r.get('billsec') or 0) if sort_by == 'billsec'
                else (lambda r: r.get('calldate', ''))
            )
            rows = sorted(rows, key=sort_key, reverse=reverse)
            if limit:
                rows = rows[:limit]
        else:
            rows = get_cdr_for_extension(
                extension, mode=mode, days=days, limit=limit,
                sort_by=sort_by, sort_dir=sort_dir, hide_system=hide_system,
                date_from=date_from, date_to=date_to,
            )
        for row in rows:
            ext_num = row['src'] if row.get('direction') == 'incoming' else row.get('dst', '')
            contact = None
            if ext_num and ext_num not in ('anonymous', 's', ''):
                norm = normalize_phone(ext_num)
                if norm:
                    rel = CrmPhoneBeanRel.objects.filter(
                        phone__phone_norm=norm
                    ).select_related('phone').first()
                    if rel:
                        if rel.bean_module == 'Contacts':
                            c = CrmContact.objects.filter(crm_id=rel.bean_id).first()
                            if c:
                                email_rel = CrmEmailAddrBeanRel.objects.filter(
                                    bean_id=c.crm_id, bean_module='Contacts',
                                    primary_address=True
                                ).select_related('email_address').first()
                                if not email_rel:
                                    email_rel = CrmEmailAddrBeanRel.objects.filter(
                                        bean_id=c.crm_id, bean_module='Contacts'
                                    ).select_related('email_address').first()
                                email = email_rel.email_address.email_address if email_rel and email_rel.email_address else None
                                contact = {
                                    'name': c.full_name,
                                    'first_name': c.first_name,
                                    'last_name': c.last_name,
                                    'email': email,
                                    'type': 'contact',
                                    'url':  f'/crm/berater/?detail={c.crm_id}',
                                    'crm_id': c.crm_id,
                                }
                        elif rel.bean_module == 'Accounts':
                            a = CrmAccount.objects.filter(crm_id=rel.bean_id).first()
                            if a:
                                contact = {
                                    'name': a.name or '',
                                    'type': 'account',
                                    'url':  f'/crm/kunden/?highlight={a.crm_id}',
                                    'crm_id': a.crm_id,
                                }
            row['contact'] = contact
        return JsonResponse({'rows': rows, 'total': len(rows)})
    except Exception as e:
        return JsonResponse({'error': str(e), 'rows': []}, status=500)


# ============================================================
# CDR-Verlauf pro Kontakt + Pop-up-Resolver (lokale CrmCdr-Tabelle)
# Session CDR-Spiegel 2026-06-27. Nutzt services/cdr_resolver.py.
# ============================================================

def _cdr_row_dict(c):
    """Eine CrmCdr-Zeile in ein schlankes Dict fuer den Verlauf."""
    return {
        'id':           c.id,
        'calldate':     c.calldate.strftime('%Y-%m-%d %H:%M:%S') if c.calldate else '',
        'direction':    c.direction,
        'duration':     c.duration,
        'billsec':      c.billsec,
        'disposition':  c.disposition,
        'src':          c.src,
        'dst':          c.dst,
        'src_norm':     c.src_norm,
        'dst_norm':     c.dst_norm,
        'ext':          c.ext,
        'party_number': c.party_number,
        'party_crm_id': c.party_crm_id,
        'party_module': c.party_module,
        'party_name':   c.party_name,
        'confidence':   c.match_confidence,
        'candidates':   c.match_candidates or [],
        'recordingfile': c.recordingfile,
        'is_system':    c.is_system,
        'linkedid':     c.linkedid,
    }


def api_cdr_for_contact(request, crm_id):
    """
    Anruf-Verlauf eines Kontakts/einer Firma aus der lokalen CrmCdr-Tabelle.
    Schneller Index-Lookup ueber party_crm_id.

    Query-Params:
      hide_internal=1  -> interne Nst-zu-Nst-Anrufe ausblenden
      hide_system=1    -> Park/Conf/Meetme ausblenden (Default an)
      limit=N          -> max. Zeilen (Default 50)
    """
    from apps.abpe_crm.models import CrmCdr
    hide_internal = request.GET.get('hide_internal', '0') in ('1', 'true', 'True')
    hide_system   = request.GET.get('hide_system', '1') in ('1', 'true', 'True')
    try:
        limit = int(request.GET.get('limit', 50))
    except (TypeError, ValueError):
        limit = 50

    qs = CrmCdr.objects.filter(party_crm_id=crm_id)
    if hide_system:
        qs = qs.filter(is_system=False)
    if hide_internal:
        qs = qs.exclude(direction='internal')
    qs = qs.order_by('-calldate')

    # Nach linkedid gruppieren: pro Anruf nur die erste (neueste) Zeile zeigen
    seen, rows = set(), []
    for c in qs[:limit * 3]:
        key = c.linkedid or f'uid:{c.id}'
        if key in seen:
            continue
        seen.add(key)
        rows.append(_cdr_row_dict(c))
        if len(rows) >= limit:
            break

    return JsonResponse({'rows': rows, 'total': len(rows), 'crm_id': crm_id})


def api_cdr_resolve(request):
    """
    Pop-up-Resolver: eingehende Nummer -> Kontakt/Firma + Konfidenz.
    Wird vom Softphone beim Klingeln aufgerufen.

    Query-Param: number=<rohe oder normierte Nummer>
    """
    from apps.abpe_crm.services.normalize_phone_nr import normalize_phone
    from apps.abpe_crm.services.cdr_resolver import resolve_party, is_internal_ext

    raw = request.GET.get('number', '').strip()
    if not raw:
        return JsonResponse({'error': 'number fehlt'}, status=400)

    norm = normalize_phone(raw)
    if not norm or is_internal_ext(norm):
        return JsonResponse({
            'number': raw, 'norm': norm, 'matched': False,
            'reason': 'internal_or_empty',
        })

    r = resolve_party(norm)
    return JsonResponse({
        'number':      raw,
        'norm':        norm,
        'matched':     bool(r['crm_id']) or r['conf'] in ('multi',),
        'crm_id':      r['crm_id'],
        'module':      r['module'],
        'name':        r['name'],
        'confidence':  r['conf'],
        'candidates':  r['cands'],
    })

