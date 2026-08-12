"""
views_recording.py — Endpoints für Anruf-Aufnahmen.
Token- ODER Session-fähig (gleiches Muster wie CRM).
"""
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods


def _api_sync(request):
    """POST: WAV von PBX holen + CrmCallRecording anlegen.
    body: { filename | pbx_path, extension?, callerid? }"""
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    remote = data.get('pbx_path') or data.get('filename') or ''
    if not remote:
        return JsonResponse({'ok': False, 'error': 'filename/pbx_path fehlt'}, status=400)

    from apps.abpe_crm.services.recording_sync import sync_recording
    try:
        result = sync_recording(
            remote, extension=data.get('extension'), callerid=data.get('callerid'),
            contact_crm_id=data.get('contact_crm_id'), account_crm_id=data.get('account_crm_id'),
        )
        status = 200 if result.get('ok') else 500
        return JsonResponse(result, status=status)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


# ── Streaming + Liste + Zuordnung ───────────────────────────
import os
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404


def _api_audio(request, rec_id):
    """GET: WAV streamen (Auth-geschützt, Range-fähig für <audio>-Seeking)."""
    from apps.abpe_crm.models import CrmCallRecording
    rec = get_object_or_404(CrmCallRecording, id=rec_id)
    if not rec.local_path or not os.path.exists(rec.local_path):
        raise Http404('Aufnahme-Datei nicht gefunden (evtl. noch nicht synchronisiert)')
    resp = FileResponse(open(rec.local_path, 'rb'), content_type='audio/wav')
    resp['Accept-Ranges'] = 'bytes'
    resp['Content-Disposition'] = f'inline; filename="{rec.filename}"'
    return resp


def _row(r):
    return {
        'id': r.id, 'filename': r.filename, 'extension': r.extension,
        'caller_number': r.caller_number or '',
        'recorded_at': r.recorded_at.isoformat() if r.recorded_at else '',
        'duration_sec': r.duration_sec, 'file_size': r.file_size,
        'subject': r.subject or '',
        'contact_crm_id': r.contact_crm_id or '', 'account_crm_id': r.account_crm_id or '',
        'is_assigned': r.is_assigned, 'is_private': r.is_private,
        'has_target': bool(r.contact_crm_id or r.account_crm_id),
        'needs_subject': bool((r.contact_crm_id or r.account_crm_id) and not (r.subject or '').strip()),
        'has_file': bool(r.local_path),
    }


def _api_for_contact(request, crm_id):
    """GET: Aufnahmen eines Contacts ODER Accounts."""
    from apps.abpe_crm.models import CrmCallRecording
    from django.db.models import Q
    qs = CrmCallRecording.objects.filter(
        Q(contact_crm_id=crm_id) | Q(account_crm_id=crm_id)
    ).order_by('-recorded_at')
    return JsonResponse({'recordings': [_row(r) for r in qs], 'crm_id': crm_id, 'total': qs.count()})


def _api_unassigned(request):
    """GET: nicht zugeordnete Aufnahmen (is_assigned=False, nicht privat)."""
    from apps.abpe_crm.models import CrmCallRecording
    # is_assigned=False umfasst: gar nicht zugeordnet UND zugeordnet-aber-Betreff-fehlt
    qs = CrmCallRecording.objects.filter(is_assigned=False, is_private=False).order_by('-recorded_at')  # _already_patched_unassigned
    return JsonResponse({'recordings': [_row(r) for r in qs], 'total': qs.count()})


def _api_assign(request, rec_id):
    """POST: Aufnahme nachträglich zuordnen (DB-Update, KEIN Datei-Rename).
    body: { contact_crm_id? | account_crm_id?, subject?, is_private? }"""
    from apps.abpe_crm.models import CrmCallRecording
    rec = get_object_or_404(CrmCallRecording, id=rec_id)
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)
    if 'contact_crm_id' in data:
        rec.contact_crm_id = data['contact_crm_id'] or None
    if 'account_crm_id' in data:
        rec.account_crm_id = data['account_crm_id'] or None
    if 'subject' in data:
        rec.subject = (data['subject'] or '').strip() or None
    if 'is_private' in data:
        rec.is_private = bool(data['is_private'])
    # REGEL: vollständig zugeordnet nur mit Contact/Account UND Betreff
    has_target = bool(rec.contact_crm_id or rec.account_crm_id)
    has_subject = bool(rec.subject and rec.subject.strip())
    if has_target and not has_subject:
        return JsonResponse({'ok': False, 'error': 'subject_required',
                             'msg': 'Betreff/Grund ist Pflicht'}, status=400)
    rec.is_assigned = bool(has_target and has_subject)
    rec.save()
    return JsonResponse({'ok': True, 'id': rec.id, 'is_assigned': rec.is_assigned})


def _api_delete(request, rec_id):
    """POST: Aufnahme löschen (DB-Satz + lokale Kopie; PBX-Original bleibt!)."""
    from apps.abpe_crm.models import CrmCallRecording
    rec = get_object_or_404(CrmCallRecording, id=rec_id)
    if rec.local_path and os.path.exists(rec.local_path):
        try: os.remove(rec.local_path)
        except Exception: pass
    rec.delete()
    return JsonResponse({'ok': True})
