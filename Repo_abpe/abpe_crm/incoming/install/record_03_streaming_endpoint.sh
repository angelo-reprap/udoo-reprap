#!/bin/bash
# ============================================================
# record_03_streaming_endpoint.sh
# ABpE Call Recording — Etappe 2: Streaming (abspielen) + Liste
# - api_recording_audio: Auth-geschütztes WAV-Streaming (Range-fähig)
# - api_recording_for_contact: Aufnahmen eines Contacts/Accounts
# - api_recording_unassigned: nicht zugeordnete Aufnahmen
# - api_recording_assign: nachträglich zuordnen (DB-Update, KEIN Datei-Rename)
# ============================================================
set -e
cd /opt/abpe/backend

echo "=== [1/5] Backup urls.py ==="
python3 Archiv/backup_restore.py -save apps/abpe_crm/urls.py -m "record_03: streaming+liste urls"

echo "=== [2/5] Views in views_recording.py ergänzen ==="
cat >> apps/abpe_crm/views_recording.py << 'PYEOF'


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
    qs = CrmCallRecording.objects.filter(is_assigned=False, is_private=False).order_by('-recorded_at')
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
    rec.is_assigned = bool(rec.contact_crm_id or rec.account_crm_id)
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
PYEOF
python3 -c "import ast; ast.parse(open('apps/abpe_crm/views_recording.py').read()); print('  views_recording.py OK')"

echo "=== [3/5] Wrapper in views.py anhängen ==="
python3 - << 'PYEOF'
p = 'apps/abpe_crm/views.py'
s = open(p, encoding='utf-8').read()
if 'api_recording_audio' in s:
    print("  Wrapper existieren schon — übersprungen.")
else:
    add = '''
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
'''
    s = s.rstrip() + '\n' + add + '\n'
    open(p, 'w', encoding='utf-8').write(s)
    print("  Recording-Wrapper angehängt.")
PYEOF
python3 -c "import ast; ast.parse(open('apps/abpe_crm/views.py').read()); print('  views.py OK')"

echo "=== [4/5] URLs eintragen ==="
python3 - << 'PYEOF'
p = 'apps/abpe_crm/urls.py'
s = open(p, encoding='utf-8').read()
if 'api_recording_audio' in s:
    print("  Routes existieren schon — übersprungen.")
else:
    anchor = "    path('api/recording/sync/',                 views.api_recording_sync, name='api_recording_sync'),"
    newlines = anchor + """
    path('api/recording/unassigned/',           views.api_recording_unassigned, name='api_recording_unassigned'),
    path('api/recording/contact/<str:crm_id>/', views.api_recording_for_contact, name='api_recording_for_contact'),
    path('api/recording/<int:rec_id>/audio/',   views.api_recording_audio,  name='api_recording_audio'),
    path('api/recording/<int:rec_id>/assign/',  views.api_recording_assign, name='api_recording_assign'),
    path('api/recording/<int:rec_id>/delete/',  views.api_recording_delete, name='api_recording_delete'),"""
    assert s.count(anchor) == 1, f"Anker {s.count(anchor)}x"
    s = s.replace(anchor, newlines)
    open(p, 'w', encoding='utf-8').write(s)
    print("  5 Recording-Routes eingetragen.")
PYEOF
python3 -c "import ast; ast.parse(open('apps/abpe_crm/urls.py').read()); print('  urls.py OK')"

echo "=== [5/5] manage.py check ==="
python manage.py check 2>&1 | tail -2

echo ""
echo "============================================================"
echo "✅ record_03 fertig (Streaming + Liste + Zuordnung)."
echo "TESTS:"
echo '  TOKEN=9d90836090dd1c42191427ab36d5d811242a62c3'
echo '  # Audio streamen (ID 1):'
echo '  curl -s -H "Authorization: Token $TOKEN" https://abpe.win.abcona.info/crm/api/recording/1/audio/ -o /tmp/test.wav && ls -la /tmp/test.wav'
echo '  # Nicht zugeordnete:'
echo '  curl -s -H "Authorization: Token $TOKEN" https://abpe.win.abcona.info/crm/api/recording/unassigned/ | python3 -m json.tool'
echo ""
echo "Danach: record_04_softphone_ui.sh"
echo "============================================================"

