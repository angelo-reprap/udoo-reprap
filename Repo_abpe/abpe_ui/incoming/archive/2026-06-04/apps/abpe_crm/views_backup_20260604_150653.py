"""
abpe_crm/views.py
CRM Portal Views — Berater, Kunden, Emails, Dokumente, Reporting
Multiuser + Multilanguage
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone

from .models import (
    CrmContact, CrmContactCstm,
    CrmAccount, CrmAccountCstm,
    CrmAccountContacts,
    CrmEmailAddress, CrmEmailAddrBeanRel,
    CrmContactNote, CrmDocument,
    CrmContactWebProfile, CrmContactPhone, CrmContactIM,
)


# ============================================================
# HELPERS
# ============================================================

def _lang(request):
    return request.session.get('language', 'de')

def _base_ctx(request, module):
    return {
        'active_module': module,
        'active':        module,
        'current_lang':  _lang(request),
    }


# ============================================================
# HAUPTSEITEN (HTML Views)
# ============================================================

@login_required
def index(request):
    """CRM Startseite — leitet zu Berater-View"""
    return berater(request)


@login_required
def berater(request):
    """Berater-Liste"""
    ctx = _base_ctx(request, 'crm_berater')
    ctx['page_title'] = 'Berater'
    ctx['tab'] = 'berater'
    return render(request, 'abpe_crm/berater.html', ctx)


@login_required
def kunden(request):
    """Kunden-Liste"""
    ctx = _base_ctx(request, 'crm_kunden')
    ctx['page_title'] = 'Kunden'
    ctx['tab'] = 'kunden'
    return render(request, 'abpe_crm/kunden.html', ctx)


@login_required
def emails(request):
    """E-Mail Adressen"""
    ctx = _base_ctx(request, 'crm_emails')
    ctx['page_title'] = 'E-Mail Adressen'
    ctx['tab'] = 'emails'
    return render(request, 'abpe_crm/emails.html', ctx)


@login_required
def dokumente(request):
    """Dokumentenablage"""
    ctx = _base_ctx(request, 'crm_dokumente')
    ctx['page_title'] = 'Dokumente'
    ctx['tab'] = 'dokumente'
    return render(request, 'abpe_crm/dokumente.html', ctx)


@login_required
def reporting(request):
    """Reporting & Sync-Log"""
    ctx = _base_ctx(request, 'crm_reporting')
    ctx['page_title'] = 'Reporting'
    ctx['tab'] = 'reporting'
    return render(request, 'abpe_crm/reporting.html', ctx)


# ============================================================
# API — BERATER
# ============================================================

@login_required
@require_http_methods(['GET'])
def api_berater_list(request):
    """Berater suchen und listen"""
    q         = request.GET.get('q', '').strip()
    status    = request.GET.get('status', '')
    sort      = request.GET.get('sort', 'last_name')
    page      = int(request.GET.get('page', 1))
    per_page  = int(request.GET.get('per_page', 20))

    qs = CrmContact.objects.select_related('cstm').all()

    if q:
        qs = qs.filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(cstm__gulp_id_c__icontains=q) |
            Q(cstm__kontakt_typ_c__icontains=q) |
            Q(primary_address_city__icontains=q)
        )

    if status:
        qs = qs.filter(cstm__kontakt_status_c=status)

    qs = qs.filter(cstm__kontakt_typ_c='berater')

    sort_map = {
        'last_name':      'last_name',
        'first_name':     'first_name',
        'city':           'primary_address_city',
        'verfuegbar':     'cstm__verfuegbar_ab_c',
        '-verfuegbar':    '-cstm__verfuegbar_ab_c',
        'modified':       '-crm_date_modified',
    }
    qs = qs.order_by(sort_map.get(sort, 'last_name'))

    paginator = Paginator(qs, per_page)
    page_obj  = paginator.get_page(page)

    results = []
    for c in page_obj:
        cstm = getattr(c, 'cstm', None)
        results.append({
            'id':           c.id,
            'crm_id':       c.crm_id,
            'full_name':    c.full_name,
            'first_name':   c.first_name or '',
            'last_name':    c.last_name or '',
            'phone_mobile': c.phone_mobile or '',
            'phone_work':   c.phone_work or '',
            'city':         c.primary_address_city or '',
            'status':       cstm.kontakt_status_c if cstm else '',
            'verfuegbar':   str(cstm.verfuegbar_ab_c) if cstm and cstm.verfuegbar_ab_c else '',
            'konditionen':  cstm.konditionen_c if cstm else '',
            'gulp_id':      cstm.gulp_id_c if cstm else '',
        })

    return JsonResponse({
        'results':   results,
        'total':     paginator.count,
        'pages':     paginator.num_pages,
        'page':      page,
    })


@login_required
@require_http_methods(['GET'])
def api_berater_detail(request, crm_id):
    """Berater Detail — alle Felder"""
    c = get_object_or_404(CrmContact, crm_id=crm_id)
    cstm = getattr(c, 'cstm', None)

    emails = list(
        CrmEmailAddrBeanRel.objects.filter(
            bean_id=crm_id, bean_module='Contacts'
        ).select_related('email_address').values_list(
            'email_address__email_address',
            'primary_address'
        )
    )

    notes = list(
        CrmContactNote.objects.filter(contact=c)
        .order_by('-created_at')
        .values('id', 'note_text', 'note_type', 'created_by', 'created_at')[:10]
    )

    docs = list(
        CrmDocument.objects.filter(contact=c)
        .order_by('-created_at')
        .values('id', 'doc_type', 'title', 'file_path', 'file_size', 'mime_type', 'created_at')[:20]
    )

    data = {
        'id':           c.id,
        'crm_id':       c.crm_id,
        'salutation':   c.salutation or '',
        'first_name':   c.first_name or '',
        'last_name':    c.last_name or '',
        'full_name':    c.full_name,
        'title':        c.title or '',
        'department':   c.department or '',
        'do_not_call':  c.do_not_call,
        'birthdate':    str(c.birthdate) if c.birthdate else '',
        'photo':        c.photo or '',
        'description':  c.description or '',
        'phone_mobile': c.phone_mobile or '',
        'phone_work':   c.phone_work or '',
        'phone_home':   c.phone_home or '',
        'phone_other':  c.phone_other or '',
        'phone_fax':    c.phone_fax or '',
        'whatsapp':     c.whatsapp_number or '',
        'assistant':    c.assistant or '',
        'assistant_phone': c.assistant_phone or '',
        'address': {
            'street':     c.primary_address_street or '',
            'city':       c.primary_address_city or '',
            'state':      c.primary_address_state or '',
            'postalcode': c.primary_address_postalcode or '',
            'country':    c.primary_address_country or '',
        },
        'emails':  [{'email': e[0], 'primary': bool(e[1])} for e in emails],
        'cstm': {
            'kontakt_typ':    cstm.kontakt_typ_c if cstm else '',
            'kontakt_status': cstm.kontakt_status_c if cstm else '',
            'verfuegbar_ab':  str(cstm.verfuegbar_ab_c) if cstm and cstm.verfuegbar_ab_c else '',
            'konditionen':    cstm.konditionen_c if cstm else '',
            'gulp_id':        cstm.gulp_id_c if cstm else '',
            'gulp_updated':   str(cstm.gulp_last_updated_c) if cstm and cstm.gulp_last_updated_c else '',
            'skill_priority': cstm.skill_priority_c if cstm else '',
            'gulp_profil':    cstm.gulp_profil_c if cstm else '',
            'ogo_description':cstm.ogo_description_c if cstm else '',
            'freelancermap':  cstm.freelancermap_profil_c if cstm else '',
            'xing':           cstm.xing_profile_c if cstm else '',
            'web_profiles': [
                {'id': wp.id, 'typ': wp.typ, 'url': wp.url, 'sort': wp.sort}
                for wp in CrmContactWebProfile.objects.filter(contact_id=crm_id).order_by('sort','typ')
            ],
        } if cstm else {},
        'phones': list(
            CrmContactPhone.objects.filter(contact_id=crm_id).order_by('sort','typ').values('id','typ','nummer')
        ),
        'im_contacts': list(
            CrmContactIM.objects.filter(contact_id=crm_id).order_by('sort','typ').values('id','typ','wert')
        ),
        'notes': notes,
        'documents': docs,
    }

    return JsonResponse(data)


# ============================================================
# API — KUNDEN
# ============================================================

@login_required
@require_http_methods(['GET'])
def api_kunden_list(request):
    """Kunden suchen und listen"""
    q        = request.GET.get('q', '').strip()
    status   = request.GET.get('status', '')
    sort     = request.GET.get('sort', 'name')
    page     = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))

    qs = CrmAccount.objects.select_related('cstm').all()

    if q:
        qs = qs.filter(
            Q(name__icontains=q) |
            Q(billing_address_city__icontains=q) |
            Q(cstm__kunden_nummer_c__icontains=q)
        )

    if status:
        qs = qs.filter(cstm__account_status_c=status)

    qs = qs.order_by(sort)

    paginator = Paginator(qs, per_page)
    page_obj  = paginator.get_page(page)

    results = []
    for a in page_obj:
        cstm = getattr(a, 'cstm', None)
        results.append({
            'id':            a.id,
            'crm_id':        a.crm_id,
            'name':          a.name or '',
            'phone_office':  a.phone_office or '',
            'website':       a.website or '',
            'city':          a.billing_address_city or '',
            'country':       a.billing_address_country or '',
            'account_type':  a.account_type or '',
            'industry':      a.industry or '',
            'status':        cstm.account_status_c if cstm else '',
            'kunden_nr':     cstm.kunden_nummer_c if cstm else '',
        })

    return JsonResponse({
        'results': results,
        'total':   paginator.count,
        'pages':   paginator.num_pages,
        'page':    page,
    })


@login_required
@require_http_methods(['GET'])
def api_kunden_detail(request, crm_id):
    """Kunden Detail mit Ansprechpartnern"""
    a = get_object_or_404(CrmAccount, crm_id=crm_id)
    cstm = getattr(a, 'cstm', None)

    ansprechpartner = list(
        CrmAccountContacts.objects.filter(account=a)
        .select_related('contact')
        .values(
            'contact__crm_id', 'contact__first_name', 'contact__last_name',
            'contact__title', 'contact__phone_work', 'contact__phone_mobile',
        )
    )

    emails = list(
        CrmEmailAddrBeanRel.objects.filter(
            bean_id=crm_id, bean_module='Accounts'
        ).select_related('email_address').values_list(
            'email_address__email_address', 'primary_address'
        )
    )

    notes = list(
        CrmContactNote.objects.filter(account=a)
        .order_by('-created_at')
        .values('id', 'note_text', 'note_type', 'created_by', 'created_at')[:10]
    )

    docs = list(
        CrmDocument.objects.filter(account=a)
        .order_by('-created_at')
        .values('id', 'doc_type', 'title', 'file_path', 'file_size', 'created_at')[:20]
    )

    return JsonResponse({
        'id':            a.id,
        'crm_id':        a.crm_id,
        'name':          a.name or '',
        'phone_office':  a.phone_office or '',
        'phone_alternate': a.phone_alternate or '',
        'website':       a.website or '',
        'description':   a.description or '',
        'account_type':  a.account_type or '',
        'industry':      a.industry or '',
        'address': {
            'street':     a.billing_address_street or '',
            'city':       a.billing_address_city or '',
            'postalcode': a.billing_address_postalcode or '',
            'country':    a.billing_address_country or '',
        },
        'cstm': {
            'status':    cstm.account_status_c if cstm else '',
            'kunden_nr': cstm.kunden_nummer_c if cstm else '',
        },
        'emails':           [{'email': e[0], 'primary': bool(e[1])} for e in emails],
        'ansprechpartner':  ansprechpartner,
        'notes':            notes,
        'documents':        docs,
    })


# ============================================================
# API — NOTIZEN
# ============================================================

@login_required
@require_POST
def api_note_save(request):
    """Telefonnotiz speichern"""
    import json
    try:
        data       = json.loads(request.body)
        note_text  = data.get('note_text', '').strip()
        note_type  = data.get('note_type', 'phone')
        contact_crm_id = data.get('contact_crm_id')
        account_crm_id = data.get('account_crm_id')

        if not note_text:
            return JsonResponse({'error': 'note_text required'}, status=400)

        contact = CrmContact.objects.filter(crm_id=contact_crm_id).first() if contact_crm_id else None
        account = CrmAccount.objects.filter(crm_id=account_crm_id).first() if account_crm_id else None

        note = CrmContactNote.objects.create(
            contact    = contact,
            account    = account,
            note_text  = note_text,
            note_type  = note_type,
            created_by = request.user.username,
        )
        return JsonResponse({'ok': True, 'id': note.id})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================
# API — DOKUMENTE
# ============================================================

@login_required
@require_http_methods(['GET'])
def api_dokumente_list(request):
    """Dokumente listen"""
    q        = request.GET.get('q', '').strip()
    doc_type = request.GET.get('doc_type', '')
    page     = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))

    qs = CrmDocument.objects.select_related('contact', 'account').all()

    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(contact__last_name__icontains=q) | Q(account__name__icontains=q))
    if doc_type:
        qs = qs.filter(doc_type=doc_type)

    qs = qs.order_by('-created_at')
    paginator = Paginator(qs, per_page)
    page_obj  = paginator.get_page(page)

    results = []
    for d in page_obj:
        results.append({
            'id':        d.id,
            'doc_type':  d.doc_type,
            'title':     d.title,
            'file_path': d.file_path,
            'file_size': d.file_size,
            'mime_type': d.mime_type,
            'contact':   d.contact.full_name if d.contact else '',
            'account':   d.account.name if d.account else '',
            'created_at': str(d.created_at),
        })

    return JsonResponse({'results': results, 'total': paginator.count})


# ============================================================
# API — SPRACHEN
# ============================================================

@require_http_methods(['GET'])
def api_available_languages(request):
    import os, json
    i18n_dir = os.path.join(os.path.dirname(__file__), 'static/abpe_crm/i18n')
    langs = []
    if os.path.exists(i18n_dir):
        for code in sorted(os.listdir(i18n_dir)):
            meta_path = os.path.join(i18n_dir, code, 'meta.json')
            if os.path.exists(meta_path):
                try:
                    meta = json.loads(open(meta_path).read())
                    if meta.get('enabled', True):
                        langs.append({'code': code, 'name': meta.get('name', code), 'native': meta.get('native', code)})
                except: pass
    current = request.session.get('language', 'de')
    return JsonResponse({'languages': langs, 'current': current})


# ============================================================
# API — REPORTING / SYNC STATUS
# ============================================================

@login_required
@require_http_methods(['GET'])
def api_sync_status(request):
    """Sync-Statistiken"""
    return JsonResponse({
        'contacts_total':  CrmContact.objects.count(),
        'accounts_total':  CrmAccount.objects.count(),
        'emails_total':    CrmEmailAddress.objects.count(),
        'documents_total': CrmDocument.objects.count(),
        'notes_total':     CrmContactNote.objects.count(),
        'last_sync':       str(CrmContact.objects.order_by('-crm_synced_at').values_list('crm_synced_at', flat=True).first() or ''),
    })


@login_required
@require_http_methods(['GET'])
def api_emails_list(request):
    """Email-Adressen suchen und listen"""
    q          = request.GET.get('q', '').strip()
    status     = request.GET.get('status', '')
    module     = request.GET.get('module', '')
    sort       = request.GET.get('sort', 'email_address')
    page       = int(request.GET.get('page', 1))
    per_page   = int(request.GET.get('per_page', 20))

    # Basis: Email-Adressen die mit Contacts verknüpft sind
    qs = CrmEmailAddress.objects.filter(
        bean_relations__bean_module='Contacts',
        bean_relations__primary_address=True,
        invalid_email=False,
    ).select_related().distinct()

    if q:
        qs = qs.filter(email_address__icontains=q)

    if status == 'opt_out':
        qs = qs.filter(opt_out=True)
    elif status == 'aktiv':
        qs = qs.filter(opt_out=False, invalid_email=False)

    sort_map = {
        'email_address': 'email_address',
        '-email_address': '-email_address',
        'modified': '-date_modified',
    }
    qs = qs.order_by(sort_map.get(sort, 'email_address'))

    paginator = Paginator(qs, per_page)
    page_obj  = paginator.get_page(page)

    results = []
    for ea in page_obj:
        # Contact über bean_relation holen
        rel = ea.bean_relations.filter(
            bean_module='Contacts',
            primary_address=True,
        ).first()
        contact = None
        if rel:
            contact = CrmContact.objects.filter(crm_id=rel.bean_id).select_related('cstm').first()

        results.append({
            'id':             ea.id,
            'crm_id':         ea.crm_id,
            'email_address':  ea.email_address or '',
            'invalid_email':  ea.invalid_email,
            'opt_out':        ea.opt_out,
            'confirm_opt_in': ea.confirm_opt_in or '',
            'date_modified':  str(ea.date_modified) if ea.date_modified else '',
            'contact': {
                'crm_id':    contact.crm_id if contact else '',
                'full_name': contact.full_name if contact else '',
                'typ':       contact.cstm.kontakt_typ_c if contact and hasattr(contact, 'cstm') else '',
                'status':    contact.cstm.kontakt_status_c if contact and hasattr(contact, 'cstm') else '',
            } if contact else None,
        })

    return JsonResponse({
        'results': results,
        'total':   paginator.count,
        'pages':   paginator.num_pages,
        'page':    page,
    })


# ============================================================
# API — CONTACT UPDATE
# ============================================================
@login_required
@require_http_methods(['POST'])
def api_contact_update(request, crm_id):
    """Universeller Update-Endpoint für CrmContact + CrmContactCstm"""
    import json
    c = get_object_or_404(CrmContact, crm_id=crm_id)
    cstm = getattr(c, 'cstm', None)
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    action = data.get('action', 'update')

    # ── Direkte Felder auf CrmContact ──────────────────────
    CONTACT_FIELDS = [
        'first_name','last_name','salutation','title','department',
        'birthdate','description','assistant','assistant_phone','do_not_call',
        'primary_address_street','primary_address_city','primary_address_state',
        'primary_address_postalcode','primary_address_country',
        'alt_address_street','alt_address_city','alt_address_state',
        'alt_address_postalcode','alt_address_country',
        'phone_mobile','phone_work','phone_home','phone_other','phone_fax','whatsapp_number',
    ]
    CSTM_FIELDS = [
        'kontakt_typ_c','kontakt_status_c','verfuegbar_ab_c','konditionen_c','skill_priority_c',
        'gulp_profil_c','ogo_description_c','freelancermap_profil_c','xing_profile_c',
    ]

    if action == 'update':
        changed = False
        for field in CONTACT_FIELDS:
            if field in data:
                setattr(c, field, data[field])
                changed = True
        if changed:
            c.save()

        if cstm:
            cstm_changed = False
            for field in CSTM_FIELDS:
                if field in data:
                    setattr(cstm, field, data[field])
                    cstm_changed = True
            if cstm_changed:
                cstm.save()

    # ── Web-Profile ────────────────────────────────────────
    elif action == 'webprofile_add':
        typ = data.get('typ', 'sonstiges')
        url = data.get('url', '').strip()
        if not url:
            return JsonResponse({'ok': False, 'error': 'URL fehlt'})
        wp = CrmContactWebProfile.objects.create(
            contact_id=crm_id, typ=typ, url=url,
            sort=CrmContactWebProfile.objects.filter(contact_id=crm_id).count()
        )
        return JsonResponse({'ok': True, 'id': wp.id})

    elif action == 'webprofile_update':
        wp_id = data.get('id')
        wp = get_object_or_404(CrmContactWebProfile, id=wp_id, contact_id=crm_id)
        if 'typ' in data: wp.typ = data['typ']
        if 'url' in data: wp.url = data['url']
        wp.save()

    elif action == 'webprofile_delete':
        CrmContactWebProfile.objects.filter(id=data.get('id'), contact_id=crm_id).delete()

    # ── Telefon ────────────────────────────────────────────
    elif action == 'phone_add':
        ph = CrmContactPhone.objects.create(
            contact_id=crm_id,
            typ=data.get('typ','mobil'),
            nummer=data.get('nummer','').strip(),
            sort=CrmContactPhone.objects.filter(contact_id=crm_id).count()
        )
        return JsonResponse({'ok': True, 'id': ph.id})

    elif action == 'phone_update':
        ph = get_object_or_404(CrmContactPhone, id=data.get('id'), contact_id=crm_id)
        if 'typ' in data: ph.typ = data['typ']
        if 'nummer' in data: ph.nummer = data['nummer']
        ph.save()

    elif action == 'phone_delete':
        CrmContactPhone.objects.filter(id=data.get('id'), contact_id=crm_id).delete()

    # ── Instant Messaging ──────────────────────────────────
    elif action == 'im_add':
        im = CrmContactIM.objects.create(
            contact_id=crm_id,
            typ=data.get('typ','whatsapp'),
            wert=data.get('wert','').strip(),
            sort=CrmContactIM.objects.filter(contact_id=crm_id).count()
        )
        return JsonResponse({'ok': True, 'id': im.id})

    elif action == 'im_update':
        im = get_object_or_404(CrmContactIM, id=data.get('id'), contact_id=crm_id)
        if 'typ' in data: im.typ = data['typ']
        if 'wert' in data: im.wert = data['wert']
        im.save()

    elif action == 'im_delete':
        CrmContactIM.objects.filter(id=data.get('id'), contact_id=crm_id).delete()

    return JsonResponse({'ok': True})
