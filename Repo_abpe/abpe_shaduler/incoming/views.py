"""
Shaduler Views — V1: Aufgaben-Kern an DB-Services; Demo nur noch per ?demo=1.
"""
import json

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.abpe_shaduler.models import Aufgabe, ErgebnisTyp
from apps.abpe_shaduler.services import (
    aufgaben_service,
    ergebnis_service,
    ki_client,
)

User = get_user_model()


def _stub(extra=None, status=200):
    payload = {'ok': True, 'stub': True, 'results': []}
    if extra:
        payload.update(extra)
    return JsonResponse(payload, status=status)


def _json_body(request) -> dict:
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        return {}


def _want_demo(request) -> bool:
    """demo=1 erzwingen; sonst DB. Legacy: ohne Param und leere DB → kein Auto-Demo mehr."""
    return request.GET.get('demo') == '1'


@login_required
@require_GET
def index(request):
    import json as _json
    tab = (request.GET.get('tab') or 'aufgaben').strip()
    cfg = {
        'api_base': '/shaduler/api/',
        'tab': tab,
        'user_id': request.user.pk,
        'ki_available': ki_client.available(),
    }
    return render(request, 'shaduler/index.html', {
        'active_module': 'shaduler',
        'active_tab': tab,
        'shaduler_config_json': _json.dumps(cfg),
    })


@login_required
@require_GET
def api_stats(request):
    if _want_demo(request):
        from .demo_data import demo_stats
        return JsonResponse(demo_stats())
    return JsonResponse(aufgaben_service.stats(request.user))


@login_required
@require_GET
def api_aufgaben_list(request):
    if _want_demo(request):
        from .demo_data import demo_aufgaben, demo_stats
        tasks = demo_aufgaben()
        return JsonResponse({
            'ok': True, 'demo': True,
            'results': tasks,
            'stats': demo_stats(tasks),
        })
    tasks = aufgaben_service.liste(user=request.user)
    results = [aufgaben_service.serialize(t) for t in tasks]
    return JsonResponse({
        'ok': True,
        'demo': False,
        'results': results,
        'stats': aufgaben_service.stats(request.user),
    })


@login_required
@require_POST
def api_aufgabe_create(request):
    from datetime import datetime as dt_cls

    data = _json_body(request)
    art = data.get('art') or Aufgabe.Art.INTERN
    titel = (data.get('titel') or data.get('subject') or data.get('betreff') or '').strip()
    if not titel:
        return JsonResponse({'ok': False, 'error': 'titel required'}, status=400)

    faellig_am = data.get('faellig_am') or None
    faellig_zeit = data.get('faellig_zeit') or None
    parsed_date = None
    parsed_time = None
    if faellig_am:
        try:
            if hasattr(faellig_am, 'year'):
                parsed_date = faellig_am
            else:
                parsed_date = dt_cls.strptime(str(faellig_am)[:10], '%Y-%m-%d').date()
        except Exception:
            parsed_date = None
    if faellig_zeit:
        try:
            if hasattr(faellig_zeit, 'hour'):
                parsed_time = faellig_zeit
            else:
                s = str(faellig_zeit).strip()
                if len(s) >= 5:
                    parsed_time = dt_cls.strptime(s[:5], '%H:%M').time()
        except Exception:
            parsed_time = None

    beschreibung = (data.get('beschreibung') or data.get('notiz') or data.get('note') or '').strip()
    dauer_min = data.get('dauer_min') or data.get('dauer') or None
    try:
        dauer_min = int(dauer_min) if dauer_min not in (None, '', False) else None
        if dauer_min is not None and dauer_min <= 0:
            dauer_min = None
    except Exception:
        dauer_min = None
    if dauer_min:
        beschreibung = (
            (beschreibung + '\n\n' if beschreibung else '') + f'Dauer: {dauer_min} Min'
        ).strip()

    aufgabe = aufgaben_service.erstellen(
        art=art,
        titel=titel,
        zugewiesen_an=request.user,
        beschreibung=beschreibung,
        kanal=data.get('kanal') or '',
        ref_type=data.get('ref_type') or '',
        ref_id=data.get('ref_id') or '',
        prioritaet=int(data.get('prioritaet') or 3),
        faellig_am=parsed_date,
        faellig_zeit=parsed_time,
        user=request.user,
    )
    return JsonResponse({
        'ok': True,
        'created': aufgaben_service.serialize(aufgabe),
    }, status=201)


@login_required
@require_GET
def api_aufgabe_detail(request, pk):
    aufgabe = get_object_or_404(Aufgabe, pk=pk, zugewiesen_an=request.user)
    payload = aufgaben_service.serialize(aufgabe)
    if request.GET.get('ki') == '1' and ki_client.available():
        suggestion = ki_client.suggest_naechste_aktion(
            aufgabe.titel,
            stand=aufgabe.beschreibung,
            hist=payload.get('excerpt', {}).get('hist') or [],
        )
        payload['ki'] = {
            'available': True,
            'success': suggestion.success,
            'text': suggestion.text,
            'error': suggestion.error,
        }
    return JsonResponse({'ok': True, **payload})


@login_required
@require_POST
def api_aufgabe_ergebnis(request, pk):
    aufgabe = get_object_or_404(Aufgabe, pk=pk, zugewiesen_an=request.user)
    data = _json_body(request)
    code = data.get('code') or data.get('ergebnis_code') or ''
    ergebnis_id = data.get('ergebnis_id') or data.get('id') or ''
    ergebnis = None
    if ergebnis_id:
        ergebnis = ErgebnisTyp.objects.filter(pk=ergebnis_id).first()
    result = ergebnis_service.anwenden(
        aufgabe=aufgabe,
        ergebnis=ergebnis,
        ergebnis_code=code,
        daten=data.get('daten') or {},
        user=request.user,
    )
    return JsonResponse(result)


@login_required
@require_POST
def api_aufgabe_snooze(request, pk):
    aufgabe = get_object_or_404(Aufgabe, pk=pk, zugewiesen_an=request.user)
    data = _json_body(request)
    days = int(data.get('days') or 1)
    aufgaben_service.snooze(aufgabe, days=days, user=request.user)
    return JsonResponse({'ok': True, 'aufgabe': aufgaben_service.serialize(aufgabe)})


@login_required
@require_POST
def api_aufgabe_delegieren(request, pk):
    aufgabe = get_object_or_404(Aufgabe, pk=pk, zugewiesen_an=request.user)
    data = _json_body(request)
    uid = data.get('user_id')
    if not uid:
        return JsonResponse({'ok': False, 'error': 'user_id required'}, status=400)
    an = get_object_or_404(User, pk=uid)
    aufgaben_service.delegieren(aufgabe, an, user=request.user)
    return JsonResponse({'ok': True, 'aufgabe_id': str(aufgabe.pk), 'an': an.username})


@login_required
@require_GET
def api_aufgaben_fuer_ref(request, typ, ref_id):
    tasks = aufgaben_service.fuer_ref(typ, ref_id)
    return JsonResponse({
        'ok': True,
        'ref_type': typ,
        'ref_id': ref_id,
        'results': [aufgaben_service.serialize(t) for t in tasks],
    })


@login_required
@require_GET
def api_kalender(request):
    if _want_demo(request):
        from .demo_data import demo_aufgaben
        return JsonResponse({
            'ok': True, 'demo': True,
            'view': request.GET.get('view', 'monat'),
            'results': demo_aufgaben(),
        })
    tasks = aufgaben_service.liste(user=request.user)
    return JsonResponse({
        'ok': True,
        'demo': False,
        'view': request.GET.get('view', 'monat'),
        'results': [aufgaben_service.serialize(t) for t in tasks],
    })


@login_required
@require_GET
def api_ergebnistypen(request):
    kontext = request.GET.get('kontext', '')
    qs = ErgebnisTyp.objects.filter(aktiv=True)
    if kontext:
        qs = qs.filter(kontext=kontext)
    return JsonResponse({
        'ok': True,
        'kontext': kontext,
        'results': [
            {
                'id': str(et.pk),
                'code': et.code,
                'label': et.label,
                'kontext': et.kontext,
                'label_i18n_key': et.label_i18n_key,
                'zeigt_dialog': et.zeigt_dialog,
                'schliesst_vorgang': et.schliesst_vorgang,
                'eingabefelder': et.eingabefelder,
            }
            for et in qs.order_by('kontext', 'sort_order', 'label')
        ],
    })


@login_required
@require_POST
def api_ki_vorschlag(request):
    """Optionaler DeepSeek-Vorschlag zur aktuellen Aufgabe (kein Auto-Apply)."""
    if not ki_client.available():
        return JsonResponse({'ok': False, 'error': 'DeepSeek nicht konfiguriert'}, status=503)
    data = _json_body(request)
    res = ki_client.suggest_naechste_aktion(
        data.get('titel') or '',
        stand=data.get('stand') or '',
        hist=data.get('hist') or [],
    )
    return JsonResponse({
        'ok': res.success,
        'text': res.text,
        'error': res.error,
    })


@login_required
@require_GET
def api_inbox_list(request):
    from apps.abpe_shaduler.services import inbox_service
    if request.GET.get('demo') == '1':
        from .demo_data import demo_inbox
        return JsonResponse({'ok': True, 'demo': True, 'results': demo_inbox()})
    try:
        page = int(request.GET.get('page') or 1)
    except ValueError:
        page = 1
    try:
        raw_size = request.GET.get('page_size') or request.GET.get('limit') or 20
        page_size = int(raw_size)
    except ValueError:
        page_size = 20
    force_imap = request.GET.get('imap') == '1'
    account = (request.GET.get('account') or '').strip()
    q = (request.GET.get('q') or '').strip()
    sort = (request.GET.get('sort') or 'date_desc').strip()
    unread_only = request.GET.get('unread') in ('1', 'true', 'yes')
    has_att_raw = (request.GET.get('has_attachment') or '').strip().lower()
    has_attachment = None
    if has_att_raw in ('1', 'true', 'yes', 'with'):
        has_attachment = True
    elif has_att_raw in ('0', 'false', 'no', 'without', 'ohne'):
        has_attachment = False
    data = inbox_service.list_mails(
        limit=page_size,
        page=page,
        page_size=page_size,
        force_imap=force_imap,
        user=request.user,
        account=account or None,
        q=q or None,
        has_attachment=has_attachment,
        sort=sort,
        unread_only=unread_only,
    )
    status = 200 if data.get('ok') else 503
    return JsonResponse(data, status=status)


@login_required
@require_GET
def api_inbox_view(request, mail_id):
    """Mail-Detail aus ES (Fallback wenn EDMS/IMAP 500)."""
    from apps.abpe_shaduler.services import inbox_service
    try:
        result = inbox_service.view_mail(mail_id, user=request.user)
        status = 200 if result.get('ok') else 404
        return JsonResponse(result, status=status)
    except Exception as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)


@login_required
@require_POST
def api_inbox_mark_read(request, mail_id):
    from apps.abpe_shaduler.services import inbox_service
    try:
        result = inbox_service.mark_read(mail_id, request.user)
        status = 200 if result.get('ok') else 400
        return JsonResponse(result, status=status)
    except Exception as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)


@login_required
@require_GET
def api_inbox_crm_lookup(request):
    """Absender-E-Mail → CRM Kontakt/Firma (für Aufgabe-Dialog)."""
    from apps.abpe_shaduler.services import inbox_service
    email = (request.GET.get('email') or request.GET.get('from') or '').strip()
    if not email:
        return JsonResponse({'ok': False, 'found': False, 'error': 'email fehlt'}, status=400)
    try:
        info = inbox_service.crm_lookup(email)
        return JsonResponse({'ok': True, **info})
    except Exception as exc:
        return JsonResponse({'ok': False, 'found': False, 'error': str(exc)}, status=400)


@login_required
@require_POST
def api_inbox_to_task(request, mail_id):
    from apps.abpe_shaduler.services import inbox_service
    data = _json_body(request)
    crm_raw = data.get('crm_notiz')
    if crm_raw is None:
        crm_notiz = True
    else:
        crm_notiz = crm_raw in (True, 1, '1', 'true', 'yes', 'on')
    try:
        result = inbox_service.mail_to_aufgabe(
            mail_id,
            request.user,
            art=data.get('art') or 'email',
            due=data.get('due') or '',
            faellig_am=data.get('faellig_am') or None,
            faellig_zeit=data.get('faellig_zeit') or None,
            notiz=data.get('notiz') or data.get('note') or '',
            crm_notiz=crm_notiz,
            dauer_min=data.get('dauer_min') or data.get('dauer') or None,
            titel=data.get('titel') or data.get('subject') or data.get('betreff') or '',
        )
        return JsonResponse(result, status=201)
    except Exception as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)


@login_required
@require_POST
def api_inbox_ack_send(request, mail_id):
    """
    Anfrage-Bestätigung aus dem Posteingang senden.
    Unterstützt An / CC / BCC + Absender-/Signatur-Auswahl (wie CRM-Compose).
    """
    from copy import copy

    data = _json_body(request)

    def _listify(val):
        if val is None:
            return []
        if isinstance(val, str):
            parts = [p.strip() for p in val.replace(';', ',').split(',')]
            return [p for p in parts if p]
        if isinstance(val, (list, tuple)):
            out = []
            for x in val:
                s = str(x or '').strip()
                if s:
                    out.append(s)
            return out
        return []

    to_emails = _listify(data.get('to') or data.get('to_email') or data.get('to_emails'))
    cc_emails = _listify(data.get('cc') or data.get('cc_emails'))
    bcc_emails = _listify(data.get('bcc') or data.get('bcc_emails'))
    subject = (data.get('subject') or '').strip()
    body = (data.get('body') or '').strip()
    contact_name = (data.get('contact_name') or data.get('name') or '').strip()
    template_id = (data.get('template_identifier') or 'crm_manual_email').strip()
    signature_id = data.get('signature_id') or None
    sender_id = data.get('sender_id') or None

    if not to_emails:
        return JsonResponse({'ok': False, 'error': 'Empfänger (An) fehlt'}, status=400)
    if not subject:
        return JsonResponse({'ok': False, 'error': 'Betreff fehlt'}, status=400)
    if not body:
        return JsonResponse({'ok': False, 'error': 'Nachricht fehlt'}, status=400)

    # Deduplizieren, Reihenfolge behalten; An gewinnt gegen CC/BCC
    seen = set()
    def _uniq(seq):
        out = []
        for e in seq:
            key = e.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(e)
        return out

    to_emails = _uniq(to_emails)
    cc_emails = _uniq(cc_emails)
    bcc_emails = _uniq(bcc_emails)

    try:
        from apps.abpe_email_studio.models import (
            EmailTemplate, TemplateStatus, EmailSignature,
            EmailSenderAccount, SenderMode,
        )
        from apps.abpe_email_studio.services.sender import EmailSender

        tpl = EmailTemplate.objects.filter(
            identifier=template_id, status=TemplateStatus.ACTIVE
        ).first()
        if not tpl:
            return JsonResponse(
                {'ok': False, 'error': f'Template nicht gefunden: {template_id}'},
                status=404,
            )

        tpl = copy(tpl)
        if signature_id:
            sig = EmailSignature.objects.filter(pk=int(signature_id)).first()
            if sig:
                tpl.signature = sig
                tpl.include_signature = True
            else:
                tpl.include_signature = False
        else:
            tpl.signature = None
            tpl.include_signature = False

        if sender_id:
            sender_acc = EmailSenderAccount.objects.filter(pk=int(sender_id)).first()
            if sender_acc:
                tpl.sender_account = sender_acc
                tpl.sender_mode = SenderMode.TEMPLATE

        sender = EmailSender()
        result = sender.send(
            template=tpl,
            to_emails=to_emails,
            variables={
                'subject': subject,
                'body': body,
                'name': contact_name,
                'sender_name': (
                    f'{request.user.first_name} {request.user.last_name}'.strip()
                    or request.user.username
                ),
                'sender_email': request.user.email or '',
            },
            user=request.user,
            cc_extra=cc_emails,
            bcc_extra=bcc_emails,
            task_reference=str(data.get('crm_id') or mail_id or ''),
            app_reference='shaduler_inbox_ack',
        )
        ok = bool(result.get('success', True)) and not result.get('error')
        payload = {
            'ok': ok,
            'success': ok,
            'mail_id': mail_id,
            'to': to_emails,
            'cc': cc_emails,
            'bcc': bcc_emails,
            'log_id': result.get('log_id'),
        }
        if result.get('error'):
            payload['error'] = result['error']
        return JsonResponse(payload, status=200 if ok else 500)
    except Exception as exc:
        return JsonResponse({'ok': False, 'success': False, 'error': str(exc)}, status=500)


@login_required
@require_GET
def api_radar_items(request):
    """
    Radar Anfragen.
    demo=1 → Demo-Daten.
    demo=0 (Default) → Freelancermap + Gulp live (+ DB Persistenz).
    """
    use_demo = request.GET.get('demo', '0') == '1'
    if use_demo:
        from .demo_data import demo_radar_anfragen
        return JsonResponse({'ok': True, 'demo': True, 'results': demo_radar_anfragen()})

    from apps.abpe_shaduler.services import radar_fetcher
    today_only = request.GET.get('today', '1') != '0'
    persist = request.GET.get('persist', '1') != '0'
    refresh = request.GET.get('refresh', '1') != '0'
    try:
        pages = max(1, min(5, int(request.GET.get('pages') or 1)))
    except (TypeError, ValueError):
        pages = 1
    # days=0 → alle; Default 2 (heute+gestern)
    raw_days = request.GET.get('days')
    if raw_days is None or raw_days == '':
        recent_days = 2
    else:
        try:
            recent_days = max(0, min(365, int(raw_days)))
        except (TypeError, ValueError):
            recent_days = 2
    status = (request.GET.get('status') or 'neu').strip()
    q = (request.GET.get('q') or '').strip()
    source = (request.GET.get('source') or request.GET.get('quelle') or '').strip()
    sort = (request.GET.get('sort') or 'date_desc').strip()
    try:
        limit = max(1, min(500, int(request.GET.get('limit') or 300)))
    except (TypeError, ValueError):
        limit = 300
    data = radar_fetcher.list_anfragen(
        use_live_fetch=refresh,
        today_only=today_only if recent_days > 0 else False,
        persist=persist,
        pages=pages,
        status=status,
        recent_days=recent_days,
        q=q,
        source=source,
        sort=sort,
        limit=limit,
    )
    return JsonResponse(data)


@login_required
@require_GET
def api_radar_item_detail(request, pk):
    from apps.abpe_shaduler.services import radar_fetcher
    item = radar_fetcher.get_item(str(pk))
    if not item:
        return JsonResponse({'ok': False, 'error': 'nicht gefunden'}, status=404)
    return JsonResponse({'ok': True, 'item': item})


@login_required
@require_POST
def api_radar_takeover(request, pk):
    """Interessant markieren (Matching-Vorbereitung)."""
    from apps.abpe_shaduler.services import radar_fetcher
    result = radar_fetcher.set_status(str(pk), 'interessant')
    if not result.get('ok'):
        return JsonResponse(result, status=404)
    return JsonResponse(result)


@login_required
@require_POST
def api_radar_dismiss(request, pk):
    """Archivieren / verwerfen."""
    from apps.abpe_shaduler.services import radar_fetcher
    result = radar_fetcher.set_status(str(pk), 'verworfen')
    if not result.get('ok'):
        return JsonResponse(result, status=404)
    return JsonResponse(result)


@login_required
@require_POST
def api_radar_block(request, pk):
    from apps.abpe_shaduler.services import radar_fetcher
    result = radar_fetcher.set_status(str(pk), 'gesperrt')
    if not result.get('ok'):
        return JsonResponse(result, status=404)
    return JsonResponse(result)


@login_required
@require_POST
def api_radar_refresh(request):
    """Manueller Poll Freelancermap + Gulp."""
    from apps.abpe_shaduler.services import radar_fetcher
    data = _json_body(request)
    try:
        pages = max(1, min(5, int(data.get('pages') or request.GET.get('pages') or 1)))
    except (TypeError, ValueError):
        pages = 1
    today_only = str(data.get('today', request.GET.get('today', '1'))).lower() not in (
        '0', 'false', 'no',
    )
    try:
        info = radar_fetcher.poll_once(pages=pages, today_only=today_only)
        return JsonResponse(info)
    except Exception as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=500)


@login_required
@require_POST
def api_radar_group_split(request, pk):
    from apps.abpe_shaduler.services import radar_grouper
    result = radar_grouper.split_group(pk)
    if not result.get('ok'):
        return JsonResponse(result, status=404)
    return JsonResponse(result)


@login_required
@require_POST
def api_radar_group_merge(request, pk):
    """Manuell mergen: Body {item_ids: […]} — pk = bestehende Gruppe oder erstes Item."""
    from apps.abpe_shaduler.services import radar_grouper
    data = _json_body(request)
    item_ids = data.get('item_ids') or data.get('ids') or []
    if isinstance(item_ids, str):
        item_ids = [x.strip() for x in item_ids.split(',') if x.strip()]
    result = radar_grouper.merge_items(list(item_ids), group_id=str(pk) if pk else None)
    if not result.get('ok'):
        return JsonResponse(result, status=400)
    return JsonResponse(result)


@login_required
@require_GET
def api_radar_consultants(request):
    from .demo_data import demo_radar_berater
    from .services import radar_berater_service as rbs

    use_demo = request.GET.get('demo', '0') == '1'
    if use_demo:
        return JsonResponse({'ok': True, 'demo': True, 'results': demo_radar_berater()})

    try:
        days = int(request.GET.get('days') or '0')
    except ValueError:
        days = 0
    try:
        limit = int(request.GET.get('limit') or '5000')
        limit = max(1, min(10000, limit))
    except ValueError:
        limit = 5000
    available_only = request.GET.get('available', '1') != '0'
    auto_seed = request.GET.get('seed', '1') != '0'
    result = rbs.list_berater(
        q=(request.GET.get('q') or '').strip(),
        days=days,
        source=(request.GET.get('source') or '').strip().lower(),
        status=(request.GET.get('status') or 'neu').strip(),
        match_status=(request.GET.get('match') or '').strip(),
        sort=(request.GET.get('sort') or 'date_desc').strip(),
        limit=limit,
        refresh=request.GET.get('refresh') == '1',
        available_only=available_only,
        auto_seed=auto_seed,
    )
    return JsonResponse(result)


@login_required
@require_GET
def api_radar_consultant_detail(request, pk):
    from .services import radar_berater_service as rbs
    try:
        chars = int(request.GET.get('chars') or 4000)
    except ValueError:
        chars = 4000
    result = rbs.get_berater_detail(str(pk), preview_chars=max(500, min(20000, chars)))
    return JsonResponse(result, status=200 if result.get('ok') else 404)


@login_required
@require_POST
def api_radar_consultant_confirm(request, pk):
    from .services import radar_berater_service as rbs
    result = rbs.set_status(str(pk), 'bestaetigt')
    return JsonResponse(result, status=200 if result.get('ok') else 400)


@login_required
@require_POST
def api_radar_consultant_dismiss(request, pk):
    from .services import radar_berater_service as rbs
    result = rbs.set_status(str(pk), 'verworfen')
    return JsonResponse(result, status=200 if result.get('ok') else 400)


@login_required
@require_http_methods(['POST'])
def api_radar_berater_seed(request):
    """CRM gulp_id_c → Radar + Soft-Delete + Reindex."""
    from .services import radar_berater_service as rbs
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}
    try:
        limit = int(payload.get('limit') or request.POST.get('limit') or 0)
    except ValueError:
        limit = 0
    do_reindex = payload.get('reindex', True) is not False
    result = rbs.sync_crm_index(limit=limit, reindex=do_reindex)
    return JsonResponse(result, status=200 if result.get('ok') else 400)


@login_required
@require_http_methods(['POST'])
def api_radar_berater_gulp_refresh(request):
    """
    Gulp aktualisieren: Existenz-Check + Verfügbarkeit/Satz.
    Body: {limit?: 50, ids?: [uuid…], delay?: 0.35}
    """
    from .services import radar_berater_service as rbs
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}
    try:
        limit = int(payload.get('limit') or 50)
    except (TypeError, ValueError):
        limit = 50
    try:
        delay = float(payload.get('delay') if payload.get('delay') is not None else 0.35)
    except (TypeError, ValueError):
        delay = 0.35
    ids = payload.get('ids') if isinstance(payload.get('ids'), list) else None
    result = rbs.refresh_from_gulp(limit=limit, ids=ids, delay_s=delay)
    status = 200 if result.get('ok') else 400
    if result.get('needs_auth'):
        status = 401
    return JsonResponse(result, status=status)


@login_required
@require_http_methods(['POST'])
def api_radar_berater_gulp_available(request):
    """
    Talentfinder „aktuell verfügbar“ einlesen.
    Body: {limit?: 40, pages?: 2, page_size?: 20, delay?: 0.35, enrich?: true}
    """
    from .services import radar_berater_service as rbs
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}
    try:
        limit = int(payload.get('limit') or 40)
    except (TypeError, ValueError):
        limit = 40
    try:
        pages = int(payload.get('pages') or 2)
    except (TypeError, ValueError):
        pages = 2
    try:
        page_size = int(payload.get('page_size') or 20)
    except (TypeError, ValueError):
        page_size = 20
    try:
        delay = float(payload.get('delay') if payload.get('delay') is not None else 0.35)
    except (TypeError, ValueError):
        delay = 0.35
    enrich = payload.get('enrich', True) is not False
    result = rbs.sync_available_from_gulp(
        limit=limit,
        pages=pages,
        page_size=page_size,
        delay_s=delay,
        enrich=enrich,
    )
    status = 200 if result.get('ok') else 400
    if result.get('needs_auth'):
        status = 401
    return JsonResponse(result, status=status)


@login_required
@require_http_methods(['POST'])
def api_radar_berater_fl_available(request):
    """
    Freelancermap „verfügbare Freelancer“ einlesen (öffentlich).
    Body: {limit?: 36, pages?: 2, delay?: 0.15}
    """
    from .services import radar_berater_service as rbs
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}
    try:
        limit = int(payload.get('limit') or 36)
    except (TypeError, ValueError):
        limit = 36
    try:
        pages = int(payload.get('pages') or 2)
    except (TypeError, ValueError):
        pages = 2
    try:
        delay = float(payload.get('delay') if payload.get('delay') is not None else 0.15)
    except (TypeError, ValueError):
        delay = 0.15
    result = rbs.sync_available_from_fl(
        limit=limit,
        pages=pages,
        delay_s=delay,
    )
    return JsonResponse(result, status=200 if result.get('ok') else 400)


@login_required
@require_http_methods(['POST'])
def api_radar_berater_reindex(request):
    """Manueller Index-Update: CRM-Sync + ES (wie 30-Min-Job)."""
    from .services import radar_berater_service as rbs
    from .services import radar_berater_index as rbi
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}
    # Nur ES-Reindex (ohne langen CRM-Scan), wenn sync=0
    if str(payload.get('sync', '1')).lower() in ('0', 'false', 'no'):
        result = rbi.reindex_all(
            limit=int(payload.get('limit') or 0) or 0,
            active_only=True,
            recreate=bool(payload.get('recreate')),
        )
        return JsonResponse(result, status=200 if result.get('ok') else 400)
    result = rbs.sync_crm_index(
        limit=0,
        reindex=payload.get('reindex', True) is not False,
        recreate_index=bool(payload.get('recreate')),
    )
    return JsonResponse(result, status=200 if result.get('ok') else 400)


@login_required
@require_http_methods(['POST'])
def api_radar_paste(request):
    from .services import radar_berater_service as rbs
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}
    text = (payload.get('text') or payload.get('url') or request.POST.get('text') or '').strip()
    if not text:
        return JsonResponse({'ok': False, 'error': 'text/url fehlt'}, status=400)
    result = rbs.paste_berater(text)
    return JsonResponse(result, status=200 if result.get('ok') else 400)


@login_required
@require_http_methods(['GET', 'POST'])
def api_regeln(request):
    if request.method == 'GET':
        from apps.abpe_shaduler.models import ProzessRegel
        qs = ProzessRegel.objects.filter(aktiv=True).prefetch_related('schritte')
        return JsonResponse({
            'ok': True,
            'results': [
                {
                    'id': str(r.pk),
                    'name': r.name,
                    'ausloeser_typ': r.ausloeser_typ,
                    'ausloeser_wert': r.ausloeser_wert,
                    'schritte': r.schritte.count(),
                }
                for r in qs.order_by('name')
            ],
        })
    return _stub(status=501)


@login_required
@require_http_methods(['GET', 'POST'])
def api_settings(request):
    """Quellen-Pfade (Gulp/FM/Hays) — editierbar ohne Code-Deploy."""
    from .services import settings_service

    if request.method == 'GET':
        return JsonResponse({'ok': True, 'results': settings_service.list_settings()})

    try:
        body = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        body = {}

    if body.get('reset'):
        keys = body.get('keys') if isinstance(body.get('keys'), list) else None
        return JsonResponse(settings_service.reset_to_defaults(keys))

    updates = body.get('settings') if isinstance(body.get('settings'), dict) else body
    if not isinstance(updates, dict):
        return JsonResponse({'ok': False, 'error': 'settings object required'}, status=400)
    # ignore control keys
    updates = {k: v for k, v in updates.items() if k not in ('reset', 'keys', 'ok')}
    return JsonResponse(settings_service.set_settings(updates))


# ─── Webhooks von abpe_scheduler (PUSH) ───────────────────────────────────────

def _scheduler_token_ok(request):
    from django.conf import settings
    expected = getattr(settings, 'SCHEDULER_SERVICE_TOKEN', '') or ''
    if not expected:
        return False
    auth = request.META.get('HTTP_AUTHORIZATION', '')
    if auth.startswith('Token '):
        return auth.split(' ', 1)[1].strip() == expected
    return (
        request.META.get('HTTP_X_SCHEDULER_TOKEN', '') == expected
        or request.GET.get('token', '') == expected
    )


@csrf_exempt
@require_POST
def api_webhook_job(request, job_key):
    from .tasks import JOB_HANDLERS

    if not _scheduler_token_ok(request):
        return JsonResponse({'ok': False, 'error': 'Unauthorized'}, status=401)

    handler = JOB_HANDLERS.get(job_key)
    if not handler:
        return JsonResponse({'ok': False, 'error': f'unknown job_key: {job_key}'}, status=404)

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}

    try:
        result = handler(payload if isinstance(payload, dict) else {'raw': payload})
        return JsonResponse(result if isinstance(result, dict) else {'ok': True, 'result': result})
    except Exception as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=500)
