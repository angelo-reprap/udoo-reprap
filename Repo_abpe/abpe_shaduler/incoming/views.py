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
    data = _json_body(request)
    art = data.get('art') or Aufgabe.Art.INTERN
    titel = (data.get('titel') or '').strip()
    if not titel:
        return JsonResponse({'ok': False, 'error': 'titel required'}, status=400)
    aufgabe = aufgaben_service.erstellen(
        art=art,
        titel=titel,
        zugewiesen_an=request.user,
        beschreibung=data.get('beschreibung') or '',
        kanal=data.get('kanal') or '',
        ref_type=data.get('ref_type') or '',
        ref_id=data.get('ref_id') or '',
        prioritaet=int(data.get('prioritaet') or 3),
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
        limit = int(request.GET.get('limit') or 40)
    except ValueError:
        limit = 40
    force_imap = request.GET.get('imap') == '1'
    account = (request.GET.get('account') or '').strip()
    data = inbox_service.list_mails(
        limit=limit,
        force_imap=force_imap,
        user=request.user,
        account=account or None,
    )
    status = 200 if data.get('ok') else 503
    return JsonResponse(data, status=status)


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
@require_POST
def api_inbox_to_task(request, mail_id):
    from apps.abpe_shaduler.services import inbox_service
    data = _json_body(request)
    try:
        result = inbox_service.mail_to_aufgabe(
            mail_id,
            request.user,
            art=data.get('art') or 'email',
        )
        return JsonResponse(result, status=201)
    except Exception as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)


@login_required
@require_GET
def api_radar_items(request):
    from .demo_data import demo_radar_anfragen
    use_demo = request.GET.get('demo', '1') != '0'
    if use_demo:
        return JsonResponse({'ok': True, 'demo': True, 'results': demo_radar_anfragen()})
    return _stub()


@login_required
@require_POST
def api_radar_takeover(request, pk):
    return _stub({'id': str(pk)}, status=501)


@login_required
@require_POST
def api_radar_dismiss(request, pk):
    return _stub({'id': str(pk)}, status=501)


@login_required
@require_POST
def api_radar_block(request, pk):
    return _stub({'id': str(pk)}, status=501)


@login_required
@require_POST
def api_radar_group_split(request, pk):
    return _stub({'id': str(pk)}, status=501)


@login_required
@require_POST
def api_radar_group_merge(request, pk):
    return _stub({'id': str(pk)}, status=501)


@login_required
@require_GET
def api_radar_consultants(request):
    from .demo_data import demo_radar_berater
    use_demo = request.GET.get('demo', '1') != '0'
    if use_demo:
        return JsonResponse({'ok': True, 'demo': True, 'results': demo_radar_berater()})
    return _stub()


@login_required
@require_POST
def api_radar_consultant_confirm(request, pk):
    return _stub({'id': str(pk)}, status=501)


@login_required
@require_POST
def api_radar_consultant_dismiss(request, pk):
    return _stub({'id': str(pk)}, status=501)


@login_required
@require_http_methods(['POST'])
def api_radar_paste(request):
    return _stub(status=501)


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
