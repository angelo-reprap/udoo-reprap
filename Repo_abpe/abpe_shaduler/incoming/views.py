"""
Shaduler Views — V1-Skelett.
JSON-APIs liefern vorerst leere/Stub-Antworten; Logik kommt in Services.
"""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST


def _stub(extra=None, status=200):
    payload = {'ok': True, 'stub': True, 'results': []}
    if extra:
        payload.update(extra)
    return JsonResponse(payload, status=status)


@login_required
@require_GET
def index(request):
    """Portal-Einstieg — Reiter-Gerüst, Lazy-Load via JS."""
    import json as _json
    tab = (request.GET.get('tab') or 'aufgaben').strip()
    cfg = {
        'api_base': '/shaduler/api/',
        'tab': tab,
        'user_id': request.user.pk,
    }
    return render(request, 'shaduler/index.html', {
        'active_module': 'shaduler',
        'active_tab': tab,
        'shaduler_config_json': _json.dumps(cfg),
    })


@login_required
@require_GET
def api_stats(request):
    return _stub({
        'heute': 0, 'ueberfaellig': 0, 'geplant': 0, 'erledigt_heute': 0,
        'badges': {
            'aufgaben': 0, 'posteingang': 0,
            'radar_anfragen': 0, 'radar_berater': 0,
        },
    })


@login_required
@require_GET
def api_aufgaben_list(request):
    return _stub()


@login_required
@require_POST
def api_aufgabe_create(request):
    return _stub({'created': None}, status=501)


@login_required
@require_GET
def api_aufgabe_detail(request, pk):
    return _stub({'id': str(pk)}, status=501)


@login_required
@require_POST
def api_aufgabe_ergebnis(request, pk):
    return _stub({'id': str(pk)}, status=501)


@login_required
@require_POST
def api_aufgabe_snooze(request, pk):
    return _stub({'id': str(pk)}, status=501)


@login_required
@require_POST
def api_aufgabe_delegieren(request, pk):
    return _stub({'id': str(pk)}, status=501)


@login_required
@require_GET
def api_aufgaben_fuer_ref(request, typ, ref_id):
    return _stub({'ref_type': typ, 'ref_id': ref_id})


@login_required
@require_GET
def api_kalender(request):
    return _stub({'view': request.GET.get('view', 'week')})


@login_required
@require_GET
def api_ergebnistypen(request):
    return _stub({'kontext': request.GET.get('kontext', '')})


@login_required
@require_GET
def api_inbox_list(request):
    return _stub()


@login_required
@require_POST
def api_inbox_to_task(request, mail_id):
    return _stub({'mail_id': mail_id}, status=501)


@login_required
@require_GET
def api_radar_items(request):
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
        return _stub()
    return _stub(status=501)


# ─── Webhooks von abpe_scheduler (PUSH) ───────────────────────────────────────

def _scheduler_token_ok(request):
    """Gleicher Service-Token wie MeetMe → SCHEDULER_SERVICE_TOKEN."""
    from django.conf import settings
    expected = getattr(settings, 'SCHEDULER_SERVICE_TOKEN', '') or ''
    if not expected:
        return False
    auth = request.META.get('HTTP_AUTHORIZATION', '')
    if auth.startswith('Token '):
        return auth.split(' ', 1)[1].strip() == expected
    # Fallback: Body/Header
    return (
        request.META.get('HTTP_X_SCHEDULER_TOKEN', '') == expected
        or request.GET.get('token', '') == expected
    )


@csrf_exempt
@require_POST
def api_webhook_job(request, job_key):
    """
    Callback-Ziel für SchedulerJob (owner_app=abpe_shaduler).
    URL: /shaduler/api/webhook/<job_key>/
    """
    import json as _json
    from .tasks import JOB_HANDLERS

    if not _scheduler_token_ok(request):
        return JsonResponse({'ok': False, 'error': 'Unauthorized'}, status=401)

    handler = JOB_HANDLERS.get(job_key)
    if not handler:
        return JsonResponse({'ok': False, 'error': f'unknown job_key: {job_key}'}, status=404)

    try:
        payload = _json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}

    try:
        result = handler(payload if isinstance(payload, dict) else {'raw': payload})
        return JsonResponse(result if isinstance(result, dict) else {'ok': True, 'result': result})
    except Exception as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=500)
