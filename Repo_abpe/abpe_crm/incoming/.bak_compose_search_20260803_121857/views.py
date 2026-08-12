"""
abpe_crm/views.py
CRM Portal Views — Berater, Kunden, Emails, Dokumente, Reporting
Multiuser + Multilanguage
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from rest_framework.authtoken.models import Token as AuthToken

def login_or_token_required(view_func):
    """Decorator: akzeptiert Session-Login ODER Token-Auth (Authorization: Token xxx)."""
    from functools import wraps
    from django.contrib.auth import authenticate
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # 1. Session-Auth (normaler Browser-Login)
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
        # 2. Token-Auth (Softphone)
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Token '):
            token_key = auth_header.split(' ', 1)[1].strip()
            try:
                token = AuthToken.objects.select_related('user').get(key=token_key)
                request.user = token.user
                return view_func(request, *args, **kwargs)
            except AuthToken.DoesNotExist:
                pass
        from django.http import JsonResponse
        return JsonResponse({'error': 'Nicht authentifiziert'}, status=401)
    return wrapper
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator


def _get_phones(bean_id, bean_module):
    """Telefonnummern aus CrmPhoneBeanRel laden"""
    from apps.abpe_crm.models import CrmPhoneBeanRel
    rels = CrmPhoneBeanRel.objects.filter(
        bean_id=bean_id, bean_module=bean_module
    ).select_related('phone').order_by('field_name')
    return [
        {
            'id':         r.id,
            'field_name': r.field_name,
            'label':      r.label or '',
            'raw':        r.phone.phone_raw,
            'norm':       r.phone.phone_norm,
            'is_primary': r.is_primary,
        }
        for r in rels
    ]

from django.db.models import Q, Count
from django.utils import timezone

from .models import (
    CrmContact, CrmContactCstm,
    CrmAccount, CrmAccountCstm,
    CrmAccountContacts,
    CrmEmailAddress, CrmEmailAddrBeanRel,
    CrmContactNote, CrmDocument,
    CrmContactWebProfile, CrmContactIM,
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
def edms(request):
    ctx = {}
    ctx['page_title'] = 'EDMS'
    ctx['tab'] = 'edms'
    return render(request, 'abpe_crm/edms.html', ctx)


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

@login_or_token_required
@require_http_methods(['GET'])
def api_berater_list(request):
    """Berater suchen und listen"""
    q         = request.GET.get('q', '').strip()
    status    = request.GET.get('status', '')
    typ       = request.GET.get('typ', '')
    sort      = request.GET.get('sort', 'last_name')
    page      = int(request.GET.get('page', 1))
    per_page  = int(request.GET.get('per_page', 20))

    qs = CrmContact.objects.select_related('cstm').all()

    matched_ids = []
    if q:
        import logging as _logging
        from elasticsearch import Elasticsearch as _ES
        # Namens-/Kontaktfelder normal gewichtet; grosse Freitextfelder
        # (Profiltexte, Notizen) stark abgeschwaecht -- sonst reicht eine
        # beilaeufige Erwaehnung (z.B. in einer Telefonnotiz) aus, um vor
        # echten Namenstreffern zu stehen (cross_fields matcht schon bei
        # einem einzigen erfuellten Feld).
        _ES_FIELDS_BERATER = [
            'name^3', 'ogo^0.3', 'gulp^0.3', 'freelancermap^0.3', 'description^0.3',
            'emails^2', 'phones^2', 'city', 'einsatzort', 'konditionen^0.3',
            'kontakt_typ', 'kontakt_status', 'company^2', 'notes^0.2',
            'salutation', 'department', 'title',
        ]
        _es = _ES(['http://localhost:9200'])
        try:
            _res = _es.search(
                index='content',
                size=10000,
                _source=['crm_id'],
                query={
                    'query_string': {
                        'query': q,
                        'fields': _ES_FIELDS_BERATER,
                        'default_operator': 'AND',
                        'type': 'cross_fields',
                        'lenient': True,
                    }
                },
            )
            matched_ids = [
                h['_source']['crm_id'] for h in _res['hits']['hits']
                if h.get('_source', {}).get('crm_id')
            ]
        except Exception as _e:
            _logging.getLogger(__name__).error(f'ES-Suche (api_berater_list) fehlgeschlagen: {_e}')
        qs = qs.filter(crm_id__in=matched_ids)

    if status:
        qs = qs.filter(cstm__kontakt_status_c=status)

    if typ and typ != 'alle':
        qs = qs.filter(cstm__kontakt_typ_c=typ)
    elif not typ:
        qs = qs.exclude(cstm__kontakt_typ_c='kunde')
    # typ='alle' → kein Filter

    if q:
        # Bei aktiver Textsuche: ES-Relevanz-Reihenfolge statt Sortierdropdown,
        # damit starke Treffer vor schwachen Zufallstreffern stehen.
        allowed_ids = set(qs.values_list('crm_id', flat=True))
        ordered_ids = [cid for cid in matched_ids if cid in allowed_ids]
        paginator = Paginator(ordered_ids, per_page)
        page_obj  = paginator.get_page(page)
        contacts_by_id = {c.crm_id: c for c in qs.filter(crm_id__in=list(page_obj))}
        results = [_berater_row(contacts_by_id[cid]) for cid in page_obj if cid in contacts_by_id]
    else:
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
        results = [_berater_row(c) for c in page_obj]

    return JsonResponse({
        'results':   results,
        'total':     paginator.count,
        'pages':     paginator.num_pages,
        'page':      page,
    })


@login_or_token_required
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
            'primary_address',
            'email_address__kampagne_ok',
            'email_address__opt_out',
            'email_address__invalid_email'
        )
    )

    notes = list(
        CrmContactNote.objects.filter(contact=c)
        .order_by('-created_at')
        .values('id', 'note_text', 'note_type', 'created_by', 'created_at')[:10]
    )

    from apps.abpe_edms.models import CrmDocument as _EdmsCrmDocument, OwnerType as _EdmsOwnerType
    _docs_qs = _EdmsCrmDocument.objects.filter(
        owners__owner_crm_id=crm_id,
        owners__owner_type=_EdmsOwnerType.CONTACT,
        in_trash=False,
    ).select_related('doctype').order_by('-document_date', '-created_at').distinct()[:20]
    docs = [{
        'id': str(_d.uuid),
        'doc_type': _d.doctype.label if _d.doctype_id else '',
        'title': _d.title,
        'file_path': f'/edms/api/file/{_d.uuid}/?download=1',
        'view_url': f'/crm/dms/?doc={_d.uuid}',
        'created_at': _d.document_date.isoformat() if _d.document_date else str(_d.created_at)[:10],
    } for _d in _docs_qs]

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
        'phones':       _get_phones(c.crm_id, 'Contacts'),
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
        'emails':  [{'email': e[0], 'primary': bool(e[1]), 'kampagne_ok': bool(e[2]) if len(e) > 2 else False, 'opt_out': bool(e[3]) if len(e) > 3 else False, 'invalid_email': bool(e[4]) if len(e) > 4 else False} for e in emails],
        'cstm': {
            'kontakt_typ':    cstm.kontakt_typ_c if cstm else '',
            'kontakt_status': cstm.kontakt_status_c if cstm else '',
            'verfuegbar_ab':  str(cstm.verfuegbar_ab_c) if cstm and cstm.verfuegbar_ab_c else '',
            'konditionen':    cstm.konditionen_c if cstm else '',
            'gulp_id':        cstm.gulp_id_c if cstm else '',
            'gulp_updated':   str(cstm.gulp_last_updated_c) if cstm and cstm.gulp_last_updated_c else '',
            'skill_priority': cstm.skill_priority_c if cstm else '',
            'einsatzort_stadt':  cstm.einsatzort_stadt_c if cstm else '',
            'einsatzort_region': cstm.einsatzort_region_c if cstm else '',
            'einsatzort_plz':    cstm.einsatzort_plz_c if cstm else '',
            'gulp_profil':    cstm.gulp_profil_c if cstm else '',
            'ogo_description':cstm.ogo_description_c if cstm else '',
            'freelancermap':  cstm.freelancermap_profil_c if cstm else '',
            'xing':           cstm.xing_profile_c if cstm else '',
            'web_profiles': [
                {'id': wp.id, 'typ': wp.typ, 'url': wp.url, 'sort': wp.sort}
                for wp in CrmContactWebProfile.objects.filter(contact_id=crm_id).order_by('sort','typ')
            ],
        } if cstm else {},
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


@login_or_token_required
@require_http_methods(['GET'])
def api_berater_cv(request, crm_id):
    """Neuestes CV-Profil (Dateiname beginnt mit 'AID', PDF) eines Beraters."""
    from apps.abpe_edms.models import CrmDocument as _EdmsCrmDocument, OwnerType as _EdmsOwnerType

    qs = _EdmsCrmDocument.objects.filter(
        owners__owner_crm_id=crm_id,
        owners__owner_type=_EdmsOwnerType.CONTACT,
        in_trash=False,
        title__istartswith='AID',
    ).prefetch_related('versions').order_by('-document_date', '-created_at').distinct()

    for doc in qs:
        active = next((v for v in doc.versions.all() if v.is_active and not v.in_trash), None)
        if active and active.filename and active.filename.lower().endswith('.pdf'):
            return redirect(f'/edms/api/file/{doc.uuid}/')

    return JsonResponse({'error': 'Kein aktuelles CV-Profil (AID*, PDF) gefunden'}, status=404)


# ============================================================
# API — KUNDEN
# ============================================================

@login_or_token_required
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
        import logging as _logging
        from elasticsearch import Elasticsearch as _ES
        _ES_FIELDS_KUNDEN = [
            'name^3', 'kunden_nummer^2', 'industry', 'description',
            'emails^2', 'phones^2', 'billing_city', 'billing_postalcode',
            'contacts^2', 'account_status', 'account_type', 'notes', 'website',
        ]
        _es = _ES(['http://localhost:9200'])
        matched_ids = []
        try:
            _res = _es.search(
                index='content_firma',
                size=10000,
                _source=['crm_id'],
                query={
                    'query_string': {
                        'query': q,
                        'fields': _ES_FIELDS_KUNDEN,
                        'default_operator': 'AND',
                        'type': 'cross_fields',
                        'lenient': True,
                    }
                },
            )
            matched_ids = [
                h['_source']['crm_id'] for h in _res['hits']['hits']
                if h.get('_source', {}).get('crm_id')
            ]
        except Exception as _e:
            _logging.getLogger(__name__).error(f'ES-Suche (api_kunden_list) fehlgeschlagen: {_e}')
        qs = qs.filter(crm_id__in=matched_ids)

    if status:
        qs = qs.filter(cstm__account_status_c=status)

    qs = qs.order_by(sort)

    paginator = Paginator(qs, per_page)
    page_obj  = paginator.get_page(page)

    results = [_kunden_row(a) for a in page_obj]

    return JsonResponse({
        'results': results,
        'total':   paginator.count,
        'pages':   paginator.num_pages,
        'page':    page,
    })


@login_or_token_required
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
            'contact__title',
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
        ap['phones'] = _get_phones(ap_crm_id, 'Contacts') if ap_crm_id else []
        ansprechpartner.append(ap)

    emails = list(
        CrmEmailAddrBeanRel.objects.filter(
            bean_id=crm_id, bean_module='Accounts'
        ).select_related('email_address').values_list(
            'email_address__email_address', 'primary_address',
            'email_address__kampagne_ok', 'email_address__opt_out',
            'email_address__invalid_email'
        )
    )

    notes = list(
        CrmContactNote.objects.filter(account=a)
        .order_by('-created_at')
        .values('id', 'note_text', 'note_type', 'created_by', 'created_at')[:10]
    )

    from apps.abpe_edms.models import CrmDocument as _EdmsCrmDocument
    from apps.abpe_edms.owner_rollup import related_crm_ids_for_entity
    _rollup_ids = related_crm_ids_for_entity(crm_id)
    _docs_qs = _EdmsCrmDocument.objects.filter(
        owners__owner_crm_id__in=_rollup_ids,
        in_trash=False,
    ).select_related('doctype').order_by('-document_date', '-created_at').distinct()[:20]
    docs = [{
        'id': str(_d.uuid),
        'doc_type': _d.doctype.label if _d.doctype_id else '',
        'title': _d.title,
        'file_path': f'/edms/api/file/{_d.uuid}/?download=1',
        'view_url': f'/crm/dms/?doc={_d.uuid}',
        'created_at': _d.document_date.isoformat() if _d.document_date else str(_d.created_at)[:10],
    } for _d in _docs_qs]

    return JsonResponse({
        'id':            a.id,
        'crm_id':        a.crm_id,
        'name':          a.name or '',
        'phones':        _get_phones(a.crm_id, 'Accounts'),
        'website':       a.website or '',
        'description':   a.description or '',
        'account_type':  a.account_type or '',
        'industry':      a.industry or '',
        'employees':     a.employees or '',
        'annual_revenue': a.annual_revenue or '',
        'rating':        a.rating or '',
        'ownership':     a.ownership or '',
        'crm_date_entered':  str(a.crm_date_entered)[:16] if a.crm_date_entered else '',
        'crm_date_modified': str(a.crm_date_modified)[:16] if a.crm_date_modified else '',
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
        'emails':           [{'email': e[0], 'primary': bool(e[1]), 'kampagne_ok': bool(e[2]) if len(e) > 2 else False, 'opt_out': bool(e[3]) if len(e) > 3 else False, 'invalid_email': bool(e[4]) if len(e) > 4 else False} for e in emails],
        'ansprechpartner':  ansprechpartner,
        'notes':            notes,
        'documents':        docs,
    })


# ============================================================
# API — NOTIZEN
# ============================================================

@csrf_exempt
@login_or_token_required
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
    try:
        from apps.abpe_edms.models import CrmDocument as _EdmsCrmDocument
        _sync_documents_total = _EdmsCrmDocument.objects.count()
    except Exception:
        _sync_documents_total = 0
    return JsonResponse({
        'contacts_total':  CrmContact.objects.count(),
        'accounts_total':  CrmAccount.objects.count(),
        'emails_total':    CrmEmailAddress.objects.count(),
        'documents_total': _sync_documents_total,
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
@csrf_exempt
@login_or_token_required
@require_POST
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

    elif action == 'email_delete':
        from apps.abpe_crm.models import CrmEmailAddress, CrmEmailAddrBeanRel
        email_addr = data.get('email', '').strip()
        if email_addr:
            ea = CrmEmailAddress.objects.filter(email_address=email_addr).first()
            if ea:
                CrmEmailAddrBeanRel.objects.filter(bean_id=crm_id, email_address=ea).delete()
                if not CrmEmailAddrBeanRel.objects.filter(email_address=ea).exists():
                    ea.delete()

    elif action == 'email_set_primary':
        from apps.abpe_crm.models import CrmEmailAddress, CrmEmailAddrBeanRel
        email_addr = data.get('email', '').strip()
        if email_addr:
            ea = CrmEmailAddress.objects.filter(email_address=email_addr).first()
            if ea:
                CrmEmailAddrBeanRel.objects.filter(bean_id=crm_id, bean_module='Accounts').update(primary_address=False)
                CrmEmailAddrBeanRel.objects.filter(bean_id=crm_id, email_address=ea, bean_module='Accounts').update(primary_address=True)

    elif action == 'email_kampagne_toggle':
        from apps.abpe_crm.models import CrmEmailAddress
        email_addr = data.get('email', '').strip()
        kampagne_ok = bool(data.get('kampagne_ok', False))
        if email_addr:
            CrmEmailAddress.objects.filter(email_address=email_addr).update(kampagne_ok=kampagne_ok)

    elif action == 'email_gesperrt_toggle':
        from apps.abpe_crm.models import CrmEmailAddress
        email_addr = data.get('email', '').strip()
        gesperrt = bool(data.get('gesperrt', False))
        if email_addr:
            CrmEmailAddress.objects.filter(email_address=email_addr).update(opt_out=gesperrt, invalid_email=gesperrt)

    elif action == 'phone_add':
        from apps.abpe_crm.models import CrmPhoneNumber, CrmPhoneBeanRel
        from apps.abpe_crm.services.normalize_phone_nr import normalize_phone
        raw = data.get('nummer', '').strip()
        field_name = data.get('field_name', 'phone_office')
        label      = data.get('label', '').strip()
        if raw:
            phone = CrmPhoneNumber.objects.create(
                phone_raw=raw,
                phone_norm=normalize_phone(raw)
            )
            rel = CrmPhoneBeanRel.objects.create(
                phone=phone,
                bean_id=crm_id,
                bean_module='Accounts',
                field_name=field_name,
                label=label or None,
                is_primary=data.get('is_primary', False),
            )
            # CDR-Hook: neue Nummer sofort in unaufgeloeste CDR-Zeilen nachtragen
            try:
                from apps.abpe_crm.services.cdr_resolver import reresolve_number
                reresolve_number(normalize_phone(raw))
            except Exception:
                pass
            return JsonResponse({'ok': True, 'id': rel.id})

    elif action == 'phone_delete':
        from apps.abpe_crm.models import CrmPhoneBeanRel
        rel = CrmPhoneBeanRel.objects.filter(id=data.get('id'), bean_id=crm_id, bean_module='Accounts').first()
        if rel:
            phone = rel.phone
            rel.delete()
            if not phone.bean_relations.exists():
                phone.delete()

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
        # Prüfen ob Verknüpfung schon existiert
        if not CrmAccountContacts.objects.filter(contact=c, account=account).exists():
            import uuid
            CrmAccountContacts.objects.create(
                crm_id=str(uuid.uuid4()),
                contact=c,
                account=account
            )
        return JsonResponse({'ok': True})
    elif request.method == 'DELETE':
        CrmAccountContacts.objects.filter(contact=c).delete()
        return JsonResponse({'ok': True})
    return JsonResponse({'ok': False}, status=405)

@csrf_exempt
@login_or_token_required
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
        'whatsapp_number',
    ]
    CSTM_FIELDS = [
        'kontakt_typ_c','kontakt_status_c','verfuegbar_ab_c','konditionen_c','skill_priority_c','gulp_id_c','einsatzort_stadt_c','einsatzort_region_c','einsatzort_plz_c',
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
        from apps.abpe_crm.models import CrmPhoneNumber, CrmPhoneBeanRel
        from apps.abpe_crm.services.normalize_phone_nr import normalize_phone
        raw = data.get('nummer', '').strip()
        field_name = data.get('field_name', 'phone_mobile')
        label      = data.get('label', '').strip()
        if raw:
            phone = CrmPhoneNumber.objects.create(
                phone_raw=raw,
                phone_norm=normalize_phone(raw)
            )
            rel = CrmPhoneBeanRel.objects.create(
                phone=phone,
                bean_id=crm_id,
                bean_module=data.get('bean_module', 'Contacts'),
                field_name=field_name,
                label=label or None,
                is_primary=data.get('is_primary', False),
            )
            # CDR-Hook: neue Nummer sofort in unaufgeloeste CDR-Zeilen nachtragen
            try:
                from apps.abpe_crm.services.cdr_resolver import reresolve_number
                reresolve_number(normalize_phone(raw))
            except Exception:
                pass
            return JsonResponse({'ok': True, 'id': rel.id})

    elif action == 'phone_update':
        from apps.abpe_crm.models import CrmPhoneBeanRel
        from apps.abpe_crm.services.normalize_phone_nr import normalize_phone
        rel = get_object_or_404(CrmPhoneBeanRel, id=data.get('id'), bean_id=crm_id)
        if 'nummer' in data:
            rel.phone.phone_raw  = data['nummer'].strip()
            rel.phone.phone_norm = normalize_phone(data['nummer'])
            rel.phone.save()
        rel.save()

    elif action == 'phone_delete':
        from apps.abpe_crm.models import CrmPhoneBeanRel
        rel = CrmPhoneBeanRel.objects.filter(id=data.get('id'), bean_id=crm_id).first()
        if rel:
            phone = rel.phone
            rel.delete()
            if not phone.bean_relations.exists():
                phone.delete()

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

    # ── E-Mail löschen ────────────────────────────────────
    elif action == 'email_delete':
        from apps.abpe_crm.models import CrmEmailAddress, CrmEmailAddrBeanRel
        email_addr = data.get('email', '').strip()
        if email_addr:
            ea = CrmEmailAddress.objects.filter(email_address=email_addr).first()
            if ea:
                CrmEmailAddrBeanRel.objects.filter(
                    bean_id=crm_id, email_address=ea
                ).delete()
                if not CrmEmailAddrBeanRel.objects.filter(email_address=ea).exists():
                    ea.delete()

    # ── E-Mail als Primär setzen ───────────────────────────
    elif action == 'email_set_primary':
        email_addr = data.get('email', '').strip()
        if email_addr:
            ea = CrmEmailAddress.objects.filter(email_address=email_addr).first()
            if ea:
                CrmEmailAddrBeanRel.objects.filter(
                    bean_id=crm_id, bean_module='Contacts'
                ).update(primary_address=False)
                CrmEmailAddrBeanRel.objects.filter(
                    bean_id=crm_id, email_address=ea, bean_module='Contacts'
                ).update(primary_address=True)

    # ── E-Mail hinzufügen ─────────────────────────────────
    elif action == 'email_add':
        import uuid as _uuid
        from apps.abpe_crm.models import CrmEmailAddress, CrmEmailAddrBeanRel
        email = data.get('email', '').strip()
        primaer  = bool(data.get('primaer', False))
        gesperrt = bool(data.get('gesperrt', False))
        if email:
            ea, _ = CrmEmailAddress.objects.get_or_create(
                email_address=email,
                defaults={
                    'crm_id':             'LOCAL-' + str(_uuid.uuid4())[:8].upper(),
                    'email_address_caps': email.upper(),
                    'invalid_email':      gesperrt,
                    'opt_out':            gesperrt,
                    'kampagne_ok':        False,
                }
            )
            CrmEmailAddrBeanRel.objects.get_or_create(
                bean_id=crm_id,
                email_address=ea,
                defaults={
                    'crm_id':          'LOCAL-' + str(_uuid.uuid4())[:8].upper(),
                    'bean_module':     'Contacts',
                    'primary_address': primaer,
                }
            )

    # ── E-Mail Gesperrt Toggle ────────────────────────────
    elif action == 'email_gesperrt_toggle':
        email_addr = data.get('email', '').strip()
        gesperrt = bool(data.get('gesperrt', False))
        if email_addr:
            CrmEmailAddress.objects.filter(email_address=email_addr).update(
                opt_out=gesperrt, invalid_email=gesperrt
            )

    # ── Kampagne OK Toggle ─────────────────────────────────
    elif action == 'email_kampagne_toggle':
        email_addr = data.get('email', '').strip()
        kampagne_ok = bool(data.get('kampagne_ok', False))
        if email_addr:
            CrmEmailAddress.objects.filter(email_address=email_addr).update(kampagne_ok=kampagne_ok)

    return JsonResponse({'ok': True})


# ============================================================
# API — NEUER BERATER / NEUER KUNDE
# ============================================================

@csrf_exempt
@login_or_token_required
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

    # Optional: Telefonnummer mit anlegen (Muster wie phone_add)
    phone_raw = data.get('phone', '').strip()
    if phone_raw:
        try:
            from apps.abpe_crm.models import CrmPhoneNumber, CrmPhoneBeanRel
            from apps.abpe_crm.services.normalize_phone_nr import normalize_phone
            phone = CrmPhoneNumber.objects.create(
                phone_raw=phone_raw, phone_norm=normalize_phone(phone_raw),
            )
            CrmPhoneBeanRel.objects.create(
                phone=phone, bean_id=crm_id, bean_module='Contacts',
                field_name='phone_mobile', is_primary=True,
            )
            try:
                from apps.abpe_crm.services.cdr_resolver import reresolve_number
                reresolve_number(normalize_phone(phone_raw))
            except Exception:
                pass
        except Exception:
            pass

    # Optional: E-Mail mit anlegen
    email_raw = data.get('email', '').strip()
    if email_raw:
        try:
            from apps.abpe_crm.models import CrmEmailAddress, CrmEmailAddrBeanRel
            ea = CrmEmailAddress.objects.create(
                crm_id=str(uuid.uuid4()),
                email_address=email_raw, email_address_caps=email_raw.upper(),
            )
            CrmEmailAddrBeanRel.objects.create(
                crm_id=str(uuid.uuid4()), email_address=ea,
                bean_id=crm_id, bean_module='Contacts', primary_address=True,
            )
        except Exception:
            pass

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

    signatures = list(EmailSignature.objects.all().values('id', 'name', 'identifier', 'is_default', 'html_body'))

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

        # Template kopieren damit Original nicht verändert wird
        tpl = copy(tpl)
        tpl.pk = None  # copy() braucht kein save(), aber FK-Refs bleiben

        # Signatur setzen
        if signature_id:
            sig = EmailSignature.objects.filter(pk=int(signature_id)).first()
            if sig:
                tpl.signature        = sig
                tpl.include_signature = True
            else:
                tpl.include_signature = False
        else:
            tpl.signature        = None
            tpl.include_signature = False

        # Absender überschreiben
        if sender_id:
            from apps.abpe_email_studio.models import EmailSenderAccount, SenderMode
            sender_acc = EmailSenderAccount.objects.filter(pk=int(sender_id)).first()
            if sender_acc:
                tpl.sender_account = sender_acc
                tpl.sender_mode    = SenderMode.TEMPLATE

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


# ============================================================
# CRM — E-MAIL COMPOSE FENSTER
# ============================================================

# ============================================================
# CRM — Empfänger-Suche (Compose / Elasticsearch fuzzy)
# ============================================================

@login_required
@login_or_token_required
@require_http_methods(['GET'])
def api_contacts_suggest(request):
    """
    Empfänger-Vorschläge für Compose (fuzzy).
    GET /crm/api/contacts/suggest/?q=troshke&limit=8
    → name, first/last, email, phone, company
    """
    import logging as _logging
    import re as _re

    q = (request.GET.get('q') or '').strip()
    try:
        limit = max(1, min(20, int(request.GET.get('limit', 8))))
    except (TypeError, ValueError):
        limit = 8

    if len(q) < 2:
        return JsonResponse({'results': [], 'q': q})

    fields = [
        'name^3', 'emails^3', 'phones^2', 'company^2',
        'city', 'title', 'department', 'notes^0.2',
        'ogo^0.3', 'gulp^0.3', 'description^0.3',
    ]

    if _re.search(r'\b(AND|OR|NOT)\b|[:\[\]"~^]', q):
        query = {
            'query_string': {
                'query': q,
                'fields': fields,
                'default_operator': 'AND',
                'type': 'cross_fields',
                'lenient': True,
            }
        }
    else:
        query = {
            'bool': {
                'should': [
                    {'multi_match': {
                        'query': q, 'fields': fields, 'fuzziness': 'AUTO',
                    }},
                    {'match_phrase_prefix': {'name': {'query': q, 'boost': 4}}},
                    {'match_phrase_prefix': {'emails': {'query': q, 'boost': 3}}},
                    {'match_phrase_prefix': {'company': {'query': q, 'boost': 2}}},
                ],
                'minimum_should_match': 1,
            }
        }

    hits = []
    try:
        from elasticsearch import Elasticsearch as _ES
        _es = _ES(['http://localhost:9200'])
        _res = _es.search(
            index='content',
            size=limit,
            _source=[
                'crm_id', 'name', 'emails', 'phones', 'company',
                'account_name', 'city', 'title', 'kontakt_typ',
            ],
            query=query,
        )
        hits = _res.get('hits', {}).get('hits', []) or []
    except Exception as exc:
        _logging.getLogger(__name__).warning(
            'api_contacts_suggest ES fehlgeschlagen: %s — ORM-Fallback', exc,
        )
        # Fallback: ORM icontains (Name / Stadt / E-Mail)
        email_ids = list(
            CrmEmailAddrBeanRel.objects.filter(
                bean_module='Contacts',
                email_address__email_address__icontains=q,
            ).values_list('bean_id', flat=True)[:limit]
        )
        qs = (
            CrmContact.objects
            .filter(
                Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(primary_address_city__icontains=q)
                | Q(crm_id__in=email_ids)
            )
            .order_by('last_name', 'first_name')[:limit]
        )
        results = []
        for c in qs:
            emails = list(
                CrmEmailAddrBeanRel.objects.filter(
                    bean_id=c.crm_id, bean_module='Contacts',
                ).select_related('email_address').values_list(
                    'email_address__email_address', 'primary_address',
                )[:3]
            )
            email = ''
            for addr, primary in emails:
                if primary or not email:
                    email = addr or ''
                    if primary:
                        break
            phones = _get_phones(c.crm_id, 'Contacts')
            phone = ''
            for p in phones:
                if p.get('is_primary') or not phone:
                    phone = p.get('raw') or p.get('norm') or ''
                    if p.get('is_primary'):
                        break
            company = ''
            try:
                link = CrmAccountContacts.objects.filter(
                    contact_id=c.crm_id,
                ).select_related('account').first()
                if link and link.account_id:
                    company = link.account.name or ''
            except Exception:
                pass
            results.append({
                'crm_id': c.crm_id,
                'full_name': c.full_name or '',
                'first_name': c.first_name or '',
                'last_name': c.last_name or '',
                'email': email,
                'phone': phone,
                'company': company,
                'city': c.primary_address_city or '',
                'score': 0,
            })
        return JsonResponse({'results': results, 'q': q, 'source': 'orm'})

    def _first_email(raw):
        if not raw:
            return ''
        if isinstance(raw, str):
            return raw.strip()
        if isinstance(raw, dict):
            return (raw.get('email') or raw.get('address') or '').strip()
        if isinstance(raw, (list, tuple)):
            for item in raw:
                e = _first_email(item)
                if e:
                    return e
        return ''

    def _first_phone(raw):
        if not raw:
            return ''
        if isinstance(raw, str):
            return raw.strip()
        if isinstance(raw, dict):
            return (raw.get('raw') or raw.get('norm') or raw.get('phone') or '').strip()
        if isinstance(raw, (list, tuple)):
            for item in raw:
                p = _first_phone(item)
                if p:
                    return p
        return ''

    crm_ids = []
    for h in hits:
        src = h.get('_source') or {}
        cid = src.get('crm_id') or h.get('_id')
        if cid:
            crm_ids.append(cid)

    # ORM-Enrich: fehlende E-Mails / Vor-Nachname nachziehen
    by_id = {}
    if crm_ids:
        for c in CrmContact.objects.filter(crm_id__in=crm_ids):
            by_id[c.crm_id] = c
        email_map = {}
        for bean_id, addr, primary in CrmEmailAddrBeanRel.objects.filter(
            bean_id__in=crm_ids, bean_module='Contacts',
        ).select_related('email_address').values_list(
            'bean_id', 'email_address__email_address', 'primary_address',
        ):
            if not addr:
                continue
            cur = email_map.get(bean_id)
            if cur is None or primary:
                email_map[bean_id] = addr
        phone_map = {}
        for cid in crm_ids:
            phones = _get_phones(cid, 'Contacts')
            phone = ''
            for p in phones:
                if p.get('is_primary') or not phone:
                    phone = p.get('raw') or p.get('norm') or ''
                    if p.get('is_primary'):
                        break
            phone_map[cid] = phone
    else:
        email_map, phone_map = {}, {}

    results = []
    for h in hits:
        src = h.get('_source') or {}
        cid = src.get('crm_id') or h.get('_id') or ''
        contact = by_id.get(cid)
        full = (src.get('name') or '').strip()
        first = contact.first_name if contact else ''
        last = contact.last_name if contact else ''
        if contact and not full:
            full = contact.full_name or ''
        if not first and full:
            parts = full.split(None, 1)
            first = parts[0] if parts else ''
            last = parts[1] if len(parts) > 1 else last
        email = _first_email(src.get('emails')) or email_map.get(cid, '')
        phone = _first_phone(src.get('phones')) or phone_map.get(cid, '')
        company = (
            (src.get('company') or src.get('account_name') or '').strip()
        )
        results.append({
            'crm_id': cid,
            'full_name': full,
            'first_name': first or '',
            'last_name': last or '',
            'email': email,
            'phone': phone,
            'company': company,
            'city': (src.get('city') or '').strip(),
            'score': h.get('_score') or 0,
        })

    return JsonResponse({'results': results, 'q': q, 'source': 'es'})

@login_required
def crm_email_compose(request):
    """E-Mail Compose — öffnet als neues Fenster, nutzt Email Studio Editor"""
    from apps.abpe_email_studio.models import (
        EmailTemplate, EmailSignature, EmailSenderAccount,
        TemplateStatus, AppScope
    )
    from apps.abpe_email_studio.views import _base_context as es_base_ctx

    import json as _json
    to_email     = request.GET.get('to', '')
    contact_name = request.GET.get('name', '')
    crm_id       = request.GET.get('crm_id', '')
    firma_name   = request.GET.get('firma', '')
    # Empfänger-Liste für Kunden-Compose
    try:
        recipients = _json.loads(request.GET.get('recipients', '[]'))
    except Exception:
        recipients = []
    # Ersten Empfänger als Default
    if not to_email and recipients:
        to_email = recipients[0].get('email', '')
    if not contact_name and recipients:
        contact_name = recipients[0].get('name', '') or recipients[0].get('first_name', '')
    # firma_name nur als letzter Fallback wenn wirklich kein Personenname
    if not contact_name and firma_name:
        contact_name = firma_name

    # Leeres Template-Objekt für den Editor
    default_tpl = EmailTemplate.objects.filter(
        identifier='crm_manual_email', status=TemplateStatus.ACTIVE
    ).first()

    templates  = EmailTemplate.objects.filter(status=TemplateStatus.ACTIVE)
    signatures = EmailSignature.objects.all()
    senders    = EmailSenderAccount.objects.filter(is_active=True)

    # ES base context (lädt i18n, ES_CONFIG etc.)
    try:
        ctx = es_base_ctx(request, 'studio')
    except Exception:
        ctx = {}

    ctx.update({
        'page_title':   'E-Mail verfassen',
        'to_email':     to_email,
        'contact_name': contact_name,
        'crm_id':       crm_id,
        'firma_name':   firma_name,
        'recipients':   recipients,
        'templates':    templates,
        'signatures':   signatures,
        'senders':      senders,
        'template':     default_tpl,
        'versions':     [],
        'milestones':   [],
        'all_templates': templates,
        'edit_lang':    '',
        'scopes':       AppScope.choices,
        'context_vars': [
            {'name': 'name'},{'name': 'first_name'},{'name': 'last_name'},
            {'name': 'email'},{'name': 'cv_link'},{'name': 'task_ref'},
        ],
        'user_vars': [
            {'name': 'sender_name'},{'name': 'sender_email'},{'name': 'reply_to'},
        ],
        'system_vars': [
            {'name': 'portal_url'},{'name': 'date'},{'name': 'year'},
        ],
        'signature_modes': [],
        'signatures_list': list(signatures),
    })
    return render(request, 'abpe_crm/email_compose.html', ctx)


# ============================================================
# API — KAMPAGNE
# ============================================================

@login_required
@require_http_methods(['GET'])
def api_kampagne_list(request):
    """Kampagnen-fähige E-Mail Adressen listen"""
    q           = request.GET.get('q', '').strip()
    typ         = request.GET.get('typ', '')
    status      = request.GET.get('status', '')
    kampagne_ok = request.GET.get('kampagne_ok', '')
    page        = int(request.GET.get('page', 1))
    per_page    = int(request.GET.get('per_page', 25))

    qs = CrmEmailAddrBeanRel.objects.filter(
        bean_module='Contacts',
        email_address__invalid_email=False,
    ).select_related('email_address').order_by('email_address__email_address')

    if kampagne_ok == '1':
        qs = qs.filter(email_address__kampagne_ok=True)
    elif kampagne_ok == '0':
        qs = qs.filter(email_address__kampagne_ok=False)

    if q:
        qs = qs.filter(
            Q(email_address__email_address__icontains=q) |
            Q(bean_id__in=CrmContact.objects.filter(
                Q(first_name__icontains=q) | Q(last_name__icontains=q)
            ).values_list('crm_id', flat=True))
        )

    known_contact_ids = set()
    if typ or status:
        cstm_qs = CrmContactCstm.objects.all()
        if typ == 'berater':
            cstm_qs = cstm_qs.filter(kontakt_typ_c='berater')
        elif typ == 'kunden':
            cstm_qs = cstm_qs.filter(kontakt_typ_c='kunde')
        if status:
            cstm_qs = cstm_qs.filter(kontakt_status_c=status)
        known_contact_ids = set(cstm_qs.values_list('contact_id', flat=True))
        qs = qs.filter(bean_id__in=known_contact_ids)

    paginator = Paginator(qs, per_page)
    page_obj  = paginator.get_page(page)

    contact_ids = [rel.bean_id for rel in page_obj]
    contacts    = {c.crm_id: c for c in CrmContact.objects.filter(crm_id__in=contact_ids).select_related('cstm')}

    results = []
    for rel in page_obj:
        c    = contacts.get(rel.bean_id)
        cstm = getattr(c, 'cstm', None) if c else None
        results.append({
            'email_id':   rel.email_address.crm_id,
            'email':      rel.email_address.email_address or '',
            'kampagne_ok': rel.email_address.kampagne_ok,
            'name':       c.full_name if c else '',
            'crm_id':     rel.bean_id,
            'typ':        cstm.kontakt_typ_c if cstm else '',
            'status':     cstm.kontakt_status_c if cstm else '',
        })

    return JsonResponse({
        'results': results,
        'total':   paginator.count,
        'pages':   paginator.num_pages,
        'page':    page,
    })


@login_required
@require_POST
def api_kampagne_send(request):
    """Kampagnen-Versand"""
    import json as _json
    try:
        data = _json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    template_id = data.get('template_identifier', '')
    sender_id   = data.get('sender_id')
    email_ids   = data.get('email_ids', [])
    name        = data.get('name', 'Kampagne')

    if not template_id:
        return JsonResponse({'error': 'Vorlage fehlt'}, status=400)
    if not email_ids:
        return JsonResponse({'error': 'Keine Empfänger'}, status=400)

    from apps.abpe_email_studio.models import EmailTemplate, TemplateStatus, EmailSenderAccount, SenderMode
    from apps.abpe_email_studio.services.sender import EmailSender
    from copy import copy

    tpl = EmailTemplate.objects.filter(
        identifier=template_id, status=TemplateStatus.ACTIVE
    ).first()
    if not tpl:
        return JsonResponse({'error': 'Vorlage nicht gefunden'}, status=404)

    if sender_id:
        sender_acc = EmailSenderAccount.objects.filter(pk=int(sender_id)).first()
    else:
        sender_acc = EmailSenderAccount.objects.filter(is_active=True, is_default=True).first()

    email_rels = CrmEmailAddrBeanRel.objects.filter(
        email_address__crm_id__in=email_ids,
        bean_module='Contacts',
        email_address__invalid_email=False,
        email_address__kampagne_ok=True,
    ).select_related('email_address')

    contacts = {c.crm_id: c for c in CrmContact.objects.filter(
        crm_id__in=[r.bean_id for r in email_rels]
    )}

    sender_svc = EmailSender()
    results = []

    for rel in email_rels:
        c = contacts.get(rel.bean_id)
        tpl_copy = copy(tpl)
        tpl_copy.pk = None
        if sender_acc:
            tpl_copy.sender_account = sender_acc
            tpl_copy.sender_mode    = SenderMode.TEMPLATE

        try:
            result = sender_svc.send(
                template       = tpl_copy,
                to_emails      = [rel.email_address.email_address],
                variables      = {
                    'name':         c.full_name if c else '',
                    'first_name':   c.first_name or '' if c else '',
                    'last_name':    c.last_name or '' if c else '',
                    'sender_name':  f'{request.user.first_name} {request.user.last_name}'.strip() or request.user.username,
                    'sender_email': request.user.email,
                },
                user           = request.user,
                task_reference = name,
                app_reference  = 'crm_kampagne',
            )
            results.append({
                'email':  rel.email_address.email_address,
                'name':   c.full_name if c else '',
                'ok':     result.get('success', False),
                'error':  result.get('error', ''),
            })
        except Exception as e:
            results.append({
                'email': rel.email_address.email_address,
                'name':  c.full_name if c else '',
                'ok':    False,
                'error': str(e),
            })

    ok_count  = sum(1 for r in results if r['ok'])
    err_count = len(results) - ok_count

    return JsonResponse({
        'ok':        True,
        'sent':      len(results),
        'ok_count':  ok_count,
        'err_count': err_count,
        'results':   results,
    })


# ============================================================
# TELEFON STUDIO
# ============================================================

@login_required
def telefon(request):
    """Telefonanlage / CDR Studio"""
    ctx = _base_ctx(request, 'crm_telefon')
    ctx['page_title'] = 'Telefonanlage'
    ctx['tab'] = 'telefon'
    # Eigene Nebenstelle aus CrmUserSettings (kein Hardcoding mehr auf '12')
    ext = ''
    settings_obj = getattr(request.user, 'crm_settings', None)
    if settings_obj and settings_obj.phone_extension:
        ext = settings_obj.phone_extension
    ctx['pbx_extension'] = ext
    return render(request, 'abpe_crm/telefon.html', ctx)


@login_required
@require_http_methods(['GET'])
def api_telefon_peers(request):
    """SIP-Peers via AMI — für Nebenstellen-Dropdown"""
    try:
        from apps.abpe_crm.services.ami_client import get_sip_peers
        peers = get_sip_peers()
        return JsonResponse({'peers': peers})
    except Exception as e:
        return JsonResponse({'peers': [], 'error': str(e)})


# api_telefon_cdr wurde in Session 6 nach views_cdr.py ausgelagert
# (views.py war zu gross geworden, siehe Handover-Dokument "views.py
# aufteilen" als offener Punkt). Decorators bleiben hier, damit Token-
# Auth (Softphone) und Session-Auth (Browser) unveraendert funktionieren,
# und urls.py weiterhin unveraendert "views.api_telefon_cdr" referenzieren
# kann.
from .views_cdr import api_telefon_cdr as _api_telefon_cdr_impl
api_telefon_cdr = login_or_token_required(require_http_methods(['GET'])(_api_telefon_cdr_impl))

# CDR-Spiegel (Session 2026-06-27): Verlauf pro Kontakt + Pop-up-Resolver.
# Gleiches Wrapper-Muster wie api_telefon_cdr (Token- ODER Session-Auth).
from .views_cdr import api_cdr_for_contact as _api_cdr_for_contact_impl
from .views_cdr import api_cdr_resolve as _api_cdr_resolve_impl
api_cdr_for_contact = login_or_token_required(require_http_methods(['GET'])(_api_cdr_for_contact_impl))
api_cdr_resolve     = login_or_token_required(require_http_methods(['GET'])(_api_cdr_resolve_impl))
@login_required
@require_http_methods(['GET'])
def api_telefon_stats(request):
    """CDR-Statistiken für eine Nebenstelle"""
    extension = request.GET.get('extension', '').strip()
    if not extension:
        return JsonResponse({'error': 'extension fehlt'}, status=400)
    try:
        from apps.abpe_crm.services.cdr_client import get_stats_for_extension
        stats = get_stats_for_extension(extension)

        def safe(d):
            if not d:
                return {}
            return {k: (int(v) if v is not None else 0) for k, v in d.items()}

        stats['heute'] = safe(stats.get('heute'))
        stats['woche'] = safe(stats.get('woche'))
        stats['monat'] = safe(stats.get('monat'))
        return JsonResponse({'stats': stats})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def api_telefon_call(request):
    """Click-to-Call via AMI Originate"""
    import json as _json
    try:
        data = _json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Ungültiges JSON'}, status=400)

    extension   = data.get('extension', '').strip()
    destination = data.get('destination', '').strip()

    if not extension or not destination:
        return JsonResponse({'error': 'extension und destination erforderlich'}, status=400)

    try:
        from apps.abpe_crm.services.ami_client import originate_call
        from apps.abpe_crm.services.normalize_phone_nr import normalize_phone
        # Sondernummern (*97, *98 etc.) nicht normalisieren
        dest_norm = destination if destination.startswith('*') else (normalize_phone(destination) or destination)
        result = originate_call(extension, dest_norm)
        return JsonResponse({
            'success':          result.get('success', False),
            'destination_norm': dest_norm,
            'extension':        extension,
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(['GET'])
def api_telefon_status(request):
    """Nebenstellen-Status via AMI"""
    extension = request.GET.get('extension', '').strip()
    if not extension:
        return JsonResponse({'error': 'extension fehlt'}, status=400)
    try:
        from apps.abpe_crm.services.ami_client import get_extension_status
        status = get_extension_status(extension)
        return JsonResponse({'extension': extension, 'status': status})
    except Exception as e:
        return JsonResponse({'extension': extension, 'status': 'unknown', 'error': str(e)})


# ============================================================
# API — CRM USER SETTINGS
# ============================================================

@login_or_token_required
def api_crm_user_settings(request):
    """CRM-eigene User-Settings — unabhängig von abpe_ui"""
    import json as _json
    from apps.abpe_crm.models import CrmUserSettings

    s, _ = CrmUserSettings.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        try:
            data = _json.loads(request.body)
        except Exception:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

        if 'language'           in data:
            s.language = data['language']
            request.session['language'] = data['language']
        if 'theme'              in data: s.theme             = data['theme']
        if 'timezone'           in data: s.timezone          = data['timezone']
        if 'phone_enabled'      in data: s.phone_enabled     = bool(data['phone_enabled'])
        if 'phone_extension'    in data: s.phone_extension   = data['phone_extension']
        if 'phone_pin'          in data: s.phone_pin         = data['phone_pin']
        if 'phone_display_name' in data: s.phone_display_name = data['phone_display_name']
        if 'phone_webdial_url'  in data: s.phone_webdial_url = data['phone_webdial_url']
        if 'phone_context'      in data: s.phone_context     = data['phone_context']
        if 'phone_timeout'      in data: s.phone_timeout     = int(data.get('phone_timeout') or 10)
        if 'phone_int_prefix'   in data: s.phone_int_prefix  = data['phone_int_prefix']
        if 'phone_pre'          in data: s.phone_pre         = data['phone_pre']
        if 'softphone_ws'          in data: s.softphone_ws         = data['softphone_ws']
        if 'softphone_vm_ext'      in data: s.softphone_vm_ext     = data['softphone_vm_ext']
        if 'softphone_dnd_ext'     in data: s.softphone_dnd_ext    = data['softphone_dnd_ext']
        if 'softphone_fwd_target'  in data: s.softphone_fwd_target = data['softphone_fwd_target']
        if 'softphone_speed_dials' in data: s.softphone_speed_dials = data['softphone_speed_dials']
        if 'softphone_status_exts' in data: s.softphone_status_exts = data['softphone_status_exts']
        s.save()
        return JsonResponse({'success': True})

    return JsonResponse({'success': True, 'data': {
        'language':           s.language,
        'theme':              s.theme,
        'timezone':           s.timezone or 'Europe/Berlin',
        'phone_enabled':      s.phone_enabled,
        'phone_extension':    s.phone_extension,
        'phone_pin':          s.phone_pin,
        'phone_display_name': s.phone_display_name,
        'phone_webdial_url':  s.phone_webdial_url,
        'phone_context':      s.phone_context,
        'phone_timeout':      s.phone_timeout,
        'phone_int_prefix':   s.phone_int_prefix,
        'softphone_ws':           s.softphone_ws,
        'softphone_vm_ext':       s.softphone_vm_ext,
        'softphone_dnd_ext':      s.softphone_dnd_ext,
        'softphone_fwd_target':   s.softphone_fwd_target,
        'softphone_speed_dials':  s.softphone_speed_dials,
        'softphone_status_exts':  s.softphone_status_exts,
        'phone_pre':          s.phone_pre,
    }})



@login_required
def api_softphone_languages(request):
    """Gibt Liste der verfügbaren Softphone-Sprachen zurück (scan i18n/*.json)"""
    import os, glob
    from django.conf import settings as django_settings

    # Flag-Mapping: ISO-Code → Flaggen-Emoji + Bezeichnung
    META = {
        'de': {'flag': '🇩🇪', 'label': 'Deutsch'},
        'en': {'flag': '🇬🇧', 'label': 'English'},
        'fr': {'flag': '🇫🇷', 'label': 'Français'},
        'es': {'flag': '🇪🇸', 'label': 'Español'},
        'it': {'flag': '🇮🇹', 'label': 'Italiano'},
        'pl': {'flag': '🇵🇱', 'label': 'Polski'},
        'ru': {'flag': '🇷🇺', 'label': 'Русский'},
        'ar': {'flag': '🇸🇦', 'label': 'العربية'},
        'zh': {'flag': '🇨🇳', 'label': '中文'},
    }

    # i18n-Verzeichnis scannen
    i18n_dir = os.path.join(
        django_settings.BASE_DIR,
        'apps', 'abpe_crm', 'static', 'abpe_crm', 'softphone', 'i18n'
    )
    langs = []
    for path in sorted(glob.glob(os.path.join(i18n_dir, '*_phone.json'))):
        code = os.path.basename(path).replace('_phone.json', '')
        meta = META.get(code, {'flag': '🌐', 'label': code.upper()})
        # Nur Dateien mit Inhalt (> 5 Bytes)
        if os.path.getsize(path) > 5:
            langs.append({
                'code':  code,
                'iso':   code.upper(),
                'flag':  meta['flag'],
                'label': meta['label'],
                'rtl':   code in ('ar', 'he', 'fa', 'ur'),
            })

    return JsonResponse({'success': True, 'languages': langs})

@login_or_token_required
@require_POST
def api_telefon_dnd(request):
    """DND setzen/aufheben via AMI Database"""
    import json as _json
    try:
        data = _json.loads(request.body)
    except Exception:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    extension = data.get('extension', '').strip()
    active    = bool(data.get('active', False))

    if not extension:
        return JsonResponse({'success': False, 'error': 'extension fehlt'}, status=400)

    try:
        from apps.abpe_crm.services.ami_client import AMIClient
        extensions = [e.strip() for e in extension.split(',') if e.strip()]
        with AMIClient() as ami:
            for ext in extensions:
                if active:
                    ami._send(f'Action: DBPut\r\nFamily: DND\r\nKey: {ext}\r\nVal: YES\r\n\r\n')
                else:
                    ami._send(f'Action: DBDel\r\nFamily: DND\r\nKey: {ext}\r\n\r\n')
                ami._recv(0.3)
        return JsonResponse({'success': True, 'active': active, 'extension': extension})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_or_token_required
@require_http_methods(['GET'])
def api_telefon_voicemail(request):
    """Voicemail-Count via AMI MailboxCount — eine Extension ODER mehrere Boxen (Komma-getrennt)."""
    boxes_param = request.GET.get('boxes', '').strip()
    extension   = request.GET.get('extension', '').strip()
    boxes = [b.strip() for b in boxes_param.split(',') if b.strip()] if boxes_param else ([extension] if extension else [])
    if not boxes:
        return JsonResponse({'error': 'extension oder boxes fehlt'}, status=400)
    try:
        from apps.abpe_crm.services.ami_client import get_voicemail_counts
        data = get_voicemail_counts(boxes)
        if not boxes_param and extension:
            # Abwaerts-kompatibel: altes Format (flach) wenn nur eine Extension abgefragt wurde
            return JsonResponse(data.get(extension, {'new_messages': 0, 'old_messages': 0}))
        return JsonResponse({'boxes': data})
    except Exception as e:
        return JsonResponse({'new_messages': 0, 'old_messages': 0, 'error': str(e)})


@login_or_token_required
@require_http_methods(['GET'])
def api_telefon_fop(request):
    """FOP-Status: Extensions, Parking, Konferenzen, Voicemail — alles in einem Call."""
    extensions   = [e.strip() for e in request.GET.get('extensions', '').split(',') if e.strip()]
    vm_extensions = [e.strip() for e in request.GET.get('vm_extensions', '').split(',') if e.strip()]

    if not extensions:
        # Fallback: alle pjsip Extensions aus Settings
        from apps.abpe_crm.models import CrmUserSettings
        exts = set()
        for s in CrmUserSettings.objects.exclude(softphone_status_exts=''):
            for e in s.softphone_status_exts.split(','):
                e = e.strip()
                if e:
                    exts.add(e)
        extensions = sorted(exts, key=lambda x: int(x) if x.isdigit() else x)

    try:
        from apps.abpe_crm.services.ami_client import get_fop_status
        data = get_fop_status(extensions, vm_extensions)
        return JsonResponse({'success': True, 'data': data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_or_token_required
@require_POST
def api_telefon_conference(request):
    """Aktiven Kanal in eine Konferenz redirecten."""
    import json as _json
    try:
        data = _json.loads(request.body)
    except Exception:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    extension  = data.get('extension', '').strip()
    conference = data.get('conference', '5555').strip()

    if not extension:
        return JsonResponse({'success': False, 'error': 'extension fehlt'}, status=400)

    # Context je nach Konferenztyp
    context = 'from-internal-custom' if conference == '5555' else 'from-internal'

    try:
        from apps.abpe_crm.services.ami_client import get_and_conference
        result = get_and_conference(extension, conference, context)
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ============================================================
# SOFTPHONE PWA
# ============================================================

@login_required
def softphone_app(request):
    """Softphone PWA — standalone HTML App"""
    from apps.abpe_crm.models import CrmUserSettings
    s, _ = CrmUserSettings.objects.get_or_create(user=request.user)
    ctx = {
        'api_base':    '/crm/api',
        'user':        request.user,
        'sp_settings': {
            'ws':          s.softphone_ws or '',
            'extension':   s.phone_extension or '',
            'display':     s.phone_display_name or request.user.get_full_name() or request.user.username,
            'vm_ext':      s.softphone_vm_ext or '',
            'dnd_ext':     s.softphone_dnd_ext or '',
            'status_exts': s.softphone_status_exts or '',
            'speed_dials': s.softphone_speed_dials or '',
        },
    }
    return render(request, 'abpe_crm/softphone/softphone.html', ctx)


@login_required
def softphone_sw(request):
    """Service Worker für Softphone PWA.
    Wird unter /crm/softphone/sw.js ausgeliefert damit der Browser
    den SW-Scope /crm/softphone/ erlaubt (SW muss im selben Pfad liegen).
    """
    import os
    from django.http import HttpResponse
    sw_path = os.path.join(
        os.path.dirname(__file__),
        'static', 'abpe_crm', 'softphone', 'js', 'service-worker.js'
    )
    try:
        with open(sw_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        return HttpResponse('// service-worker.js not found', content_type='application/javascript', status=404)
    response = HttpResponse(content, content_type='application/javascript; charset=utf-8')
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


@login_or_token_required
@require_http_methods(['GET'])
def api_softphone_contacts(request):
    """contacts.json aus CRM generieren — fuer Softphone Kontakt-Lookup"""
    from apps.abpe_crm.models import CrmUserSettings

    contacts = []
    for c in CrmContact.objects.select_related('cstm').order_by('last_name', 'first_name'):
        phones = _get_phones(c.crm_id, 'Contacts')
        if not phones:
            continue
        contacts.append({
            'id':         c.crm_id,
            'first_name': c.first_name or '',
            'last_name':  c.last_name or '',
            'full_name':  c.full_name,
            'company':    '',
            'phones':     [
                {
                    'number': p['norm'] or p['raw'],
                    'raw':    p['raw'],
                    'type':   p['field_name'],
                    'label':  p['label'] or p['field_name'],
                }
                for p in phones
            ],
        })

    # Interne Nebenstellen aus CrmUserSettings
    extensions = {}
    for s in CrmUserSettings.objects.exclude(phone_extension=''):
        if s.phone_extension and s.phone_display_name:
            extensions[s.phone_extension] = s.phone_display_name
        elif s.phone_extension and s.user:
            name = s.user.get_full_name() or s.user.username
            if name:
                extensions[s.phone_extension] = name

    return JsonResponse({
        'version':        '1.0',
        'contacts':       contacts,
        'pbx_extensions': extensions,
        'speed_dials':    [],
    }, json_dumps_params={'ensure_ascii': False})


# ============================================================
# API — CALL RECORDING (Wrapper mit Token-Auth)
# ============================================================
from .views_recording import _api_sync as _rec_sync_impl
api_recording_sync = csrf_exempt(login_or_token_required(require_POST(_rec_sync_impl)))

from .views_recording import (
    _api_audio as _rec_audio_impl,
    _api_for_contact as _rec_for_contact_impl,
    _api_unassigned as _rec_unassigned_impl,
    _api_assign as _rec_assign_impl,
    _api_delete as _rec_delete_impl,
)
api_recording_audio        = login_or_token_required(require_http_methods(['GET'])(_rec_audio_impl))
api_recording_for_contact  = login_or_token_required(require_http_methods(['GET'])(_rec_for_contact_impl))
api_recording_unassigned   = login_or_token_required(require_http_methods(['GET'])(_rec_unassigned_impl))
api_recording_assign       = csrf_exempt(login_or_token_required(require_POST(_rec_assign_impl)))
api_recording_delete       = csrf_exempt(login_or_token_required(require_POST(_rec_delete_impl)))



def api_notes_for_contact(request, crm_id):
    """Notizen (CrmContactNote) fuer einen Contact ODER Account per crm_id.
    Response parallel zu Recordings: {'notes': [...]}"""
    from django.http import JsonResponse
    qs = CrmContactNote.objects.filter(contact_id=crm_id)
    if not qs.exists():
        qs = CrmContactNote.objects.filter(account_id=crm_id)
    notes = list(
        qs.order_by('-created_at')
        .values('id', 'note_text', 'note_type', 'created_by', 'created_at')[:50]
    )
    for n in notes:
        if n.get('created_at'):
            n['created_at'] = n['created_at'].isoformat()
    return JsonResponse({'notes': notes})


@csrf_exempt
@login_or_token_required
@require_POST
def api_contact_quick_create(request):
    """Kombiniertes Schnellanlegen: optional neue Firma + Kontakt +
    mehrere Telefonnummern + mehrere E-Mails, alles in einer Transaktion.
    Gedacht fuer Kontext, in denen man ohne Umweg direkt einen neuen
    Ansprechpartner (und ggf. dessen Firma) anlegen will, z. B. waehrend
    der Terminkoordination (abpe_meetme)."""
    import json, uuid
    from django.db import transaction
    from apps.abpe_crm.models import (
        CrmAccount, CrmAccountCstm, CrmContact, CrmContactCstm,
        CrmAccountContacts, CrmPhoneNumber, CrmPhoneBeanRel,
        CrmEmailAddress, CrmEmailAddrBeanRel,
    )
    from apps.abpe_crm.services.normalize_phone_nr import normalize_phone

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    last_name = (data.get('last_name') or '').strip()
    if not last_name:
        return JsonResponse({'error': 'Nachname ist Pflichtfeld'}, status=400)

    company = data.get('company') or {}
    new_company_name = (company.get('new_name') or '').strip()
    existing_account_crm_id = (company.get('existing_crm_id') or '').strip()

    phones = data.get('phones') or []
    emails = data.get('emails') or []

    try:
        with transaction.atomic():
            account_crm_id = None

            if new_company_name:
                account_crm_id = 'LOCAL-' + str(uuid.uuid4())[:8].upper()
                CrmAccount.objects.create(
                    crm_id=account_crm_id,
                    name=new_company_name,
                    billing_address_city=(company.get('city') or '').strip(),
                )
                CrmAccountCstm.objects.get_or_create(
                    account_id=account_crm_id,
                    defaults={'account_status_c': 'unbekannt'},
                )
            elif existing_account_crm_id:
                get_object_or_404(CrmAccount, crm_id=existing_account_crm_id)
                account_crm_id = existing_account_crm_id

            contact_crm_id = 'LOCAL-' + str(uuid.uuid4())[:8].upper()
            CrmContact.objects.create(
                crm_id=contact_crm_id,
                salutation=data.get('salutation', 'Hr.'),
                first_name=(data.get('first_name') or '').strip(),
                last_name=last_name,
            )
            CrmContactCstm.objects.get_or_create(
                contact_id=contact_crm_id,
                defaults={
                    'kontakt_typ_c': data.get('category', 'andere'),
                    'kontakt_status_c': 'passiv',
                },
            )

            if account_crm_id:
                CrmAccountContacts.objects.create(
                    crm_id=str(uuid.uuid4()),
                    contact_id=contact_crm_id,
                    account_id=account_crm_id,
                )

            for i, p in enumerate(phones):
                raw = (p.get('raw') or '').strip()
                if not raw:
                    continue
                phone = CrmPhoneNumber.objects.create(
                    phone_raw=raw, phone_norm=normalize_phone(raw),
                )
                CrmPhoneBeanRel.objects.create(
                    phone=phone, bean_id=contact_crm_id, bean_module='Contacts',
                    field_name=p.get('field_name', 'phone_mobile'),
                    is_primary=(i == 0),
                )

            for i, e in enumerate(emails):
                addr = (e.get('address') or '').strip()
                if not addr:
                    continue
                ea = CrmEmailAddress.objects.create(
                    crm_id=str(uuid.uuid4()),
                    email_address=addr, email_address_caps=addr.upper(),
                )
                CrmEmailAddrBeanRel.objects.create(
                    crm_id=str(uuid.uuid4()), email_address=ea,
                    bean_id=contact_crm_id, bean_module='Contacts',
                    primary_address=bool(e.get('primary', i == 0)),
                )

    except Exception as exc:
        return JsonResponse({'error': f'Anlegen fehlgeschlagen: {exc}'}, status=500)

    return JsonResponse({
        'ok': True,
        'contact_crm_id': contact_crm_id,
        'account_crm_id': account_crm_id,
        'name': f"{data.get('first_name', '')} {last_name}".strip(),
        'email': emails[0].get('address') if emails else '',
        'phone': phones[0].get('raw') if phones else '',
    })


# ============================================================
# API — FAVORITEN (pro Benutzer, CrmUserSettings)
# ============================================================

def _berater_row(c):
    """Zeilen-Dict fuer Berater-Liste. Von api_berater_list UND
    api_favoriten_list genutzt (kein Duplikat der Feldliste)."""
    cstm = getattr(c, 'cstm', None)
    return {
        'id':           c.id,
        'crm_id':       c.crm_id,
        'full_name':    c.full_name,
        'first_name':   c.first_name or '',
        'last_name':    c.last_name or '',
        'phones':       _get_phones(c.crm_id, 'Contacts'),
        'city':         c.primary_address_city or '',
        'status':       cstm.kontakt_status_c if cstm else '',
        'verfuegbar':   str(cstm.verfuegbar_ab_c) if cstm and cstm.verfuegbar_ab_c else '',
        'konditionen':  cstm.konditionen_c if cstm else '',
        'gulp_id':      cstm.gulp_id_c if cstm else '',
    }


def _kunden_row(a):
    """Zeilen-Dict fuer Kunden-Liste. Von api_kunden_list UND
    api_favoriten_list genutzt (kein Duplikat der Feldliste)."""
    cstm = getattr(a, 'cstm', None)
    return {
        'id':            a.id,
        'crm_id':        a.crm_id,
        'name':          a.name or '',
        'phones':        _get_phones(a.crm_id, 'Accounts'),
        'website':       a.website or '',
        'city':          a.billing_address_city or '',
        'country':       a.billing_address_country or '',
        'account_type':  a.account_type or '',
        'industry':      a.industry or '',
        'status':        cstm.account_status_c if cstm else '',
        'kunden_nr':     cstm.kunden_nummer_c if cstm else '',
    }


@login_or_token_required
@require_http_methods(['GET'])
def api_favoriten_list(request):
    """Favoriten-Liste (Berater oder Kunden), pro Benutzer.
    ?type=berater|kunden"""
    from apps.abpe_crm.models import CrmUserSettings
    typ = request.GET.get('type', 'berater')
    settings_obj, _ = CrmUserSettings.objects.get_or_create(user=request.user)

    if typ == 'kunden':
        ids = list(settings_obj.favoriten_kunden or [])
        qs = CrmAccount.objects.select_related('cstm').filter(crm_id__in=ids)
        by_id = {a.crm_id: a for a in qs}
        results = [_kunden_row(by_id[i]) for i in ids if i in by_id]
    else:
        ids = list(settings_obj.favoriten_berater or [])
        qs = CrmContact.objects.select_related('cstm').filter(crm_id__in=ids)
        by_id = {c.crm_id: c for c in qs}
        results = [_berater_row(by_id[i]) for i in ids if i in by_id]

    return JsonResponse({'results': results, 'ids': ids})


@csrf_exempt
@login_or_token_required
@require_POST
def api_favoriten_toggle(request):
    """Favorit an/aus. body: {type: 'berater'|'kunden', crm_id}"""
    import json
    from apps.abpe_crm.models import CrmUserSettings
    try:
        d = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    typ = d.get('type', 'berater')
    crm_id = d.get('crm_id')
    if not crm_id:
        return JsonResponse({'error': 'crm_id fehlt'}, status=400)

    settings_obj, _ = CrmUserSettings.objects.get_or_create(user=request.user)
    field = 'favoriten_kunden' if typ == 'kunden' else 'favoriten_berater'
    ids = list(getattr(settings_obj, field) or [])
    if crm_id in ids:
        ids.remove(crm_id)
        favorited = False
    else:
        ids.append(crm_id)
        favorited = True
    setattr(settings_obj, field, ids)
    settings_obj.save(update_fields=[field, 'updated_at'])
    return JsonResponse({'ok': True, 'favorited': favorited, 'crm_id': crm_id})
