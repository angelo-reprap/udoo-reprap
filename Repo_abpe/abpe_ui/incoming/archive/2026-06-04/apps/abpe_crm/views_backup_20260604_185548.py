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
        'alt_address': {
            'street':     c.alt_address_street or '',
            'city':       c.alt_address_city or '',
            'state':      c.alt_address_state or '',
            'postalcode': c.alt_address_postalcode or '',
            'country':    c.alt_address_country or '',
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
        'account': (lambda rel: {'crm_id': rel.account.crm_id, 'name': rel.account.name} if rel else None)(
            CrmAccountContacts.objects.filter(contact_id=crm_id).select_related('account').first()
        ),
        'crm_date_entered':  str(c.crm_date_entered)[:16] if c.crm_date_entered else '',
        'crm_date_modified': str(c.crm_date_modified)[:16] if c.crm_date_modified else '',
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

    ansprechpartner_raw = list(
        CrmAccountContacts.objects.filter(account=a)
        .select_related('contact')
        .values(
            'contact__crm_id', 'contact__first_name', 'contact__last_name',
            'contact__title', 'contact__phone_work', 'contact__phone_mobile',
        )
    )
    # E-Mails der Ansprechpartner direkt mitlesen
    ansprechpartner = []
    for ap in ansprechpartner_raw:
        ap_crm_id = ap.get('contact__crm_id', '')
        ap_emails = list(
            CrmEmailAddrBeanRel.objects.filter(
                bean_id=ap_crm_id, bean_module='Contacts'
            ).select_related('email_address').values_list(
                'email_address__email_address', 'primary_address'
            )
        )
        ap['emails'] = [{'email': e[0], 'primary': bool(e[1])} for e in ap_emails]
        ansprechpartner.append(ap)

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
            'state':      a.billing_address_state or '',
            'postalcode': a.billing_address_postalcode or '',
            'country':    a.billing_address_country or '',
        },
        'billing_address': {
            'street':     a.billing_address_street or '',
            'city':       a.billing_address_city or '',
            'state':      a.billing_address_state or '',
            'postalcode': a.billing_address_postalcode or '',
            'country':    a.billing_address_country or '',
        },
        'shipping_address': {
            'street':     a.shipping_address_street or '',
            'city':       a.shipping_address_city or '',
            'state':      a.shipping_address_state or '',
            'postalcode': a.shipping_address_postalcode or '',
            'country':    a.shipping_address_country or '',
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

@require_POST
@login_required
def api_account_update(request, crm_id):
    """Universeller Update-Endpoint für CrmAccount + CrmAccountCstm"""
    import json
    from apps.abpe_crm.models import CrmAccount, CrmAccountCstm
    acc = get_object_or_404(CrmAccount, crm_id=crm_id)
    cstm = getattr(acc, 'cstm', None)
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    action = data.get('action', 'update')

    ACCOUNT_FIELDS = [
        'name', 'account_type', 'industry', 'website', 'description',
        'phone_office', 'phone_alternate', 'phone_fax',
        'employees', 'annual_revenue', 'rating', 'ownership',
        'billing_address_street', 'billing_address_city', 'billing_address_state',
        'billing_address_postalcode', 'billing_address_country',
        'shipping_address_street', 'shipping_address_city', 'shipping_address_state',
        'shipping_address_postalcode', 'shipping_address_country',
    ]
    CSTM_FIELDS = ['account_status_c', 'kunden_nummer_c']

    if action == 'update':
        changed = False
        for field in ACCOUNT_FIELDS:
            if field in data:
                setattr(acc, field, data[field])
                changed = True
        if changed:
            acc.save()
        if cstm:
            cstm_changed = False
            for field in CSTM_FIELDS:
                if field in data:
                    setattr(cstm, field, data[field])
                    cstm_changed = True
            if cstm_changed:
                cstm.save()
        elif any(f in data for f in CSTM_FIELDS):
            cstm = CrmAccountCstm(account=acc)
            for field in CSTM_FIELDS:
                if field in data:
                    setattr(cstm, field, data[field])
            cstm.save()

    elif action == 'email_add':
        email = data.get('email', '').strip()
        if email:
            from apps.abpe_crm.models import CrmEmailAddress, CrmEmailAddrBeanRel
            ea, _ = CrmEmailAddress.objects.get_or_create(
                email_address=email,
                defaults={'email_address_caps': email.upper(), 'opt_out': data.get('gesperrt', False), 'invalid_email': False}
            )
            CrmEmailAddrBeanRel.objects.get_or_create(
                bean_id=crm_id, email_address=ea,
                defaults={'primary_address': data.get('primaer', False), 'bean_module': 'Accounts'}
            )

    return JsonResponse({'ok': True})


@login_required
def api_contact_photo(request, crm_id):
    if request.method == 'DELETE':
        import os
        from django.conf import settings
        c = get_object_or_404(CrmContact, crm_id=crm_id)
        if c.photo:
            try:
                path = c.photo.replace(settings.MEDIA_URL, settings.MEDIA_ROOT + '/')
                if os.path.exists(path): os.remove(path)
            except Exception:
                pass
            c.photo = ''
            c.save()
        return JsonResponse({'ok': True})
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    """Foto-Upload für CrmContact"""
    import os, uuid
    from django.conf import settings
    c = get_object_or_404(CrmContact, crm_id=crm_id)
    photo = request.FILES.get('photo')
    if not photo:
        return JsonResponse({'ok': False, 'error': 'Kein Foto'}, status=400)
    ext = os.path.splitext(photo.name)[1].lower() or '.jpg'
    if ext not in ['.jpg','.jpeg','.png','.gif','.webp']:
        return JsonResponse({'ok': False, 'error': 'Ungültiges Format'}, status=400)
    upload_dir = os.path.join(settings.MEDIA_ROOT, 'crm_photos')
    os.makedirs(upload_dir, exist_ok=True)
    filename = 'contact_' + crm_id + ext
    filepath = os.path.join(upload_dir, filename)
    with open(filepath, 'wb') as dest:
        for chunk in photo.chunks():
            dest.write(chunk)
    photo_url = settings.MEDIA_URL + 'crm_photos/' + filename
    c.photo = photo_url
    c.save()
    return JsonResponse({'ok': True, 'photo': photo_url})


@login_required
def api_contact_link_account(request, crm_id):
    import json
    c = get_object_or_404(CrmContact, crm_id=crm_id)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except Exception:
            return JsonResponse({'ok': False}, status=400)
        account_crm_id = data.get('account_crm_id')
        account = get_object_or_404(CrmAccount, crm_id=account_crm_id)
        CrmAccountContacts.objects.get_or_create(account=account, contact=c)
        return JsonResponse({'ok': True})
    elif request.method == 'DELETE':
        CrmAccountContacts.objects.filter(contact=c).delete()
        return JsonResponse({'ok': True})
    return JsonResponse({'ok': False}, status=405)

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


# ============================================================
# API — NEUER BERATER / NEUER KUNDE
# ============================================================

@login_required
@require_POST
def api_berater_new(request):
    """Neuen Berater anlegen"""
    import json, uuid
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    last_name  = data.get('last_name', '').strip()
    first_name = data.get('first_name', '').strip()
    salutation = data.get('salutation', 'Hr.')

    if not last_name:
        return JsonResponse({'error': 'Nachname ist Pflichtfeld'}, status=400)

    crm_id = 'LOCAL-' + str(uuid.uuid4())[:8].upper()

    contact = CrmContact.objects.create(
        crm_id=crm_id,
        salutation=salutation,
        first_name=first_name,
        last_name=last_name,
    )
    CrmContactCstm.objects.get_or_create(
        contact_id=crm_id,
        defaults={'kontakt_typ_c': 'berater', 'kontakt_status_c': 'passiv'},
    )

    return JsonResponse({'ok': True, 'crm_id': crm_id})


@login_required
@require_POST
def api_kunden_new(request):
    """Neuen Kunden anlegen"""
    import json, uuid
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    name = data.get('name', '').strip()
    city = data.get('city', '').strip()

    if not name:
        return JsonResponse({'error': 'Firmenname ist Pflichtfeld'}, status=400)

    crm_id = 'LOCAL-' + str(uuid.uuid4())[:8].upper()

    CrmAccount.objects.create(
        crm_id=crm_id,
        name=name,
        billing_address_city=city,
    )
    CrmAccountCstm.objects.get_or_create(
        account_id=crm_id,
        defaults={'account_status_c': 'unbekannt'},
    )

    return JsonResponse({'ok': True, 'crm_id': crm_id})


# ============================================================
# API — DELETE BERATER / DELETE KUNDE
# ============================================================

@login_required
@require_POST
def api_berater_delete(request, crm_id):
    """Berater (CrmContact) löschen"""
    import json
    try:
        data = json.loads(request.body)
    except Exception:
        data = {}
    confirm = data.get('confirm', False)
    if not confirm:
        return JsonResponse({'error': 'confirm fehlt'}, status=400)

    c = get_object_or_404(CrmContact, crm_id=crm_id)
    CrmContactWebProfile.objects.filter(contact_id=crm_id).delete()
    CrmContactPhone.objects.filter(contact_id=crm_id).delete()
    CrmContactIM.objects.filter(contact_id=crm_id).delete()
    CrmContactCstm.objects.filter(contact_id=crm_id).delete()
    CrmAccountContacts.objects.filter(contact_id=crm_id).delete()
    CrmEmailAddrBeanRel.objects.filter(bean_id=crm_id, bean_module='Contacts').delete()
    CrmContactNote.objects.filter(contact=c).delete()
    CrmDocument.objects.filter(contact=c).delete()
    c.delete()
    return JsonResponse({'ok': True})


@login_required
@require_POST
def api_kunden_delete(request, crm_id):
    """Kunden (CrmAccount) löschen"""
    import json
    try:
        data = json.loads(request.body)
    except Exception:
        data = {}
    confirm = data.get('confirm', False)
    if not confirm:
        return JsonResponse({'error': 'confirm fehlt'}, status=400)

    a = get_object_or_404(CrmAccount, crm_id=crm_id)
    CrmAccountContacts.objects.filter(account=a).delete()
    CrmEmailAddrBeanRel.objects.filter(bean_id=crm_id, bean_module='Accounts').delete()
    CrmContactNote.objects.filter(account=a).delete()
    CrmDocument.objects.filter(account=a).delete()
    CrmAccountCstm.objects.filter(account_id=crm_id).delete()
    a.delete()
    return JsonResponse({'ok': True})


# ============================================================
# API — E-MAIL AUS VORLAGE (CRM)
# ============================================================

@login_required
@require_http_methods(['GET'])
def api_email_templates(request):
    """Verfügbare E-Mail Vorlagen + Signaturen + Variablen + Module für CRM-Versand"""
    from apps.abpe_email_studio.models import EmailTemplate, TemplateStatus, EmailSignature, EmailModule

    templates  = list(EmailTemplate.objects.filter(
        status=TemplateStatus.ACTIVE
    ).values('id', 'identifier', 'name', 'subject', 'app_scope', 'sender_mode'))

    signatures = list(EmailSignature.objects.all().values('id', 'name', 'identifier', 'is_default'))

    variables = [
        {'name': 'name',         'label': 'Vollständiger Name'},
        {'name': 'first_name',   'label': 'Vorname'},
        {'name': 'last_name',    'label': 'Nachname'},
        {'name': 'email',        'label': 'E-Mail'},
        {'name': 'sender_name',  'label': 'Absender Name'},
        {'name': 'sender_email', 'label': 'Absender E-Mail'},
        {'name': 'date',         'label': 'Datum'},
        {'name': 'year',         'label': 'Jahr'},
        {'name': 'portal_url',   'label': 'Portal URL'},
    ]

    modules = []
    for m in EmailModule.objects.filter(is_active=True).order_by('module_type', 'name'):
        modules.append({
            'identifier':  m.identifier,
            'name':        m.name,
            'module_type': m.module_type,
            'syntax':      '{{block:' + m.identifier + '}}',
        })

    from apps.abpe_email_studio.models import EmailSenderAccount
    senders = list(EmailSenderAccount.objects.filter(is_active=True).values(
        'id', 'email', 'display_name', 'is_default'
    ))

    return JsonResponse({
        'templates':  templates,
        'signatures': signatures,
        'variables':  variables,
        'modules':    modules,
        'senders':    senders,
    })


@login_required
@require_POST
def api_email_send(request):
    """E-Mail aus Vorlage senden"""
    import json
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    template_id = data.get('template_identifier', 'crm_manual_email')
    to_email    = data.get('to_email', '').strip()
    subject     = data.get('subject', '').strip()
    body        = data.get('body', '').strip()
    contact_name = data.get('contact_name', '')

    if not to_email:
        return JsonResponse({'error': 'Empfänger fehlt'}, status=400)
    if not subject:
        return JsonResponse({'error': 'Betreff fehlt'}, status=400)
    if not body:
        return JsonResponse({'error': 'Nachricht fehlt'}, status=400)

    signature_id = data.get('signature_id')
    sender_id    = data.get('sender_id')

    try:
        from apps.abpe_email_studio.api import EmailStudio
        from apps.abpe_email_studio.models import EmailTemplate, TemplateStatus, EmailSignature
        from copy import copy

        # Template-Objekt holen und ggf. Signatur überschreiben
        tpl = EmailTemplate.objects.filter(
            identifier=template_id, status=TemplateStatus.ACTIVE
        ).first()
        if not tpl:
            return JsonResponse({'error': f'Template nicht gefunden: {template_id}'}, status=404)

        # Signatur setzen
        tpl = copy(tpl)
        if signature_id:
            sig = EmailSignature.objects.filter(pk=signature_id).first()
            if sig:
                tpl.signature = sig
                tpl.include_signature = True
        else:
            tpl.include_signature = False

        # Absender überschreiben
        if sender_id:
            from apps.abpe_email_studio.models import EmailSenderAccount
            sender_acc = EmailSenderAccount.objects.filter(pk=sender_id).first()
            if sender_acc:
                tpl.sender_account = sender_acc
                tpl.sender_mode = 'TEMPLATE'

        from apps.abpe_email_studio.services.sender import EmailSender
        sender = EmailSender()
        result = sender.send(
            template       = tpl,
            to_emails      = [to_email],
            variables      = {
                'subject':      subject,
                'body':         body,
                'name':         contact_name,
                'sender_name':  f'{request.user.first_name} {request.user.last_name}'.strip() or request.user.username,
                'sender_email': request.user.email,
            },
            user           = request.user,
            task_reference = data.get('crm_id', ''),
            app_reference  = 'crm_manual',
        )
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
