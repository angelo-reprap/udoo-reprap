#!/bin/bash
# ============================================================
# record_02_sync_endpoint.sh
# ABpE Call Recording — Etappe 1b: SFTP-Sync-Endpoint
# Holt WAV von PBX (paramiko), legt unter data/call_record/ ab,
# CrmCallRecording-Satz anlegen, Auto-Zuordnung via CallerID.
# Erzeugt: services/recording_sync.py + views_recording.py + URLs
# ============================================================
set -e
cd /opt/abpe/backend

echo "=== [1/6] Backups ==="
python3 Archiv/backup_restore.py -save apps/abpe_crm/urls.py -m "record_02: vor recording-urls"

echo "=== [2/6] Sync-Service (paramiko SFTP) anlegen ==="
mkdir -p apps/abpe_crm/services
cat > apps/abpe_crm/services/recording_sync.py << 'PYEOF'
"""
recording_sync.py — holt Aufnahme-WAVs per SFTP von der PBX nach ucs5.
WAV behält Original-Namen. Zuordnung lebt in der DB (CrmCallRecording).
"""
import os
import time
import datetime
from django.conf import settings
from django.utils import timezone

PBX_MONITOR_BASE = '/var/spool/asterisk/monitor'


def _sftp_connect():
    import paramiko
    from abpe_backend.settings import pbx
    t = paramiko.Transport((pbx.PBX_HOST, 22))
    t.connect(username=pbx.PBX_ROOT_USER, password=pbx.PBX_ROOT_PASSWORD)
    return paramiko.SFTPClient.from_transport(t), t


def _parse_filename(filename):
    """abpe-PJSIP_<ext>-<seq>-<ts_ms>.wav -> (extension, recorded_at, ts_ms)"""
    import re
    base = os.path.basename(filename)
    m = re.match(r'abpe-PJSIP_(\d+)-[0-9a-fA-F]+-(\d+)\.wav', base)
    if not m:
        m2 = re.match(r'abpe-.*?_(\d+)-.*?-(\d+)\.wav', base)
        if not m2:
            return None, None, None
        m = m2
    ext = m.group(1)
    ts_ms = int(m.group(2))
    recorded_at = timezone.make_aware(datetime.datetime.fromtimestamp(ts_ms / 1000.0))
    return ext, recorded_at, ts_ms


def _wait_stable(sftp, remote_path, tries=5, pause=0.6):
    """Stabilitätscheck: Dateigröße muss zweimal gleich sein (Datei fertig geschrieben)."""
    last = -1
    for _ in range(tries):
        try:
            sz = sftp.stat(remote_path).st_size
        except Exception:
            return None
        if sz == last and sz > 0:
            return sz
        last = sz
        time.sleep(pause)
    return last if last > 0 else None


def sync_recording(remote_path, extension=None, callerid=None):
    """
    Holt eine WAV von der PBX, legt sie lokal ab, erstellt CrmCallRecording.
    remote_path: voller PBX-Pfad ODER nur Dateiname (dann wird Pfad aus Datum gebaut)
    Returns: dict mit ok, id, assigned, ...
    """
    from apps.abpe_crm.models import CrmCallRecording, CrmPhoneBeanRel, CrmContact, CrmAccount

    base = os.path.basename(remote_path)

    # Schon vorhanden? (idempotent)
    existing = CrmCallRecording.objects.filter(filename=base).first()
    if existing:
        return {'ok': True, 'id': existing.id, 'already': True, 'assigned': existing.is_assigned}

    ext, recorded_at, ts_ms = _parse_filename(base)
    if extension:
        ext = extension

    # Vollen PBX-Pfad bestimmen
    if remote_path.startswith('/'):
        pbx_path = remote_path
    elif recorded_at:
        d = recorded_at
        pbx_path = f"{PBX_MONITOR_BASE}/{d.year}/{d.month:02d}/{d.day:02d}/{base}"
    else:
        pbx_path = f"{PBX_MONITOR_BASE}/{base}"

    sftp, transport = _sftp_connect()
    try:
        size = _wait_stable(sftp, pbx_path)
        if not size:
            return {'ok': False, 'error': f'Datei nicht stabil/leer: {pbx_path}'}

        # Lokales Zielverzeichnis: data/call_record/YYYY/MM/DD/
        d = recorded_at or timezone.now()
        local_dir = os.path.join(str(settings.MEDIA_ROOT), 'call_record',
                                 f"{d.year}", f"{d.month:02d}", f"{d.day:02d}")
        os.makedirs(local_dir, exist_ok=True)
        local_path = os.path.join(local_dir, base)

        sftp.get(pbx_path, local_path)
        local_size = os.path.getsize(local_path)
    finally:
        sftp.close()
        transport.close()

    # Auto-Zuordnung via CallerID
    contact_crm_id = None
    account_crm_id = None
    caller_number = callerid or None
    if caller_number:
        from apps.abpe_crm.services.normalize_phone_nr import normalize_phone
        norm = normalize_phone(caller_number)
        rel = CrmPhoneBeanRel.objects.filter(phone__phone_norm=norm).select_related('phone').first()
        if rel:
            if rel.bean_module == 'Contacts':
                contact_crm_id = rel.bean_id
            elif rel.bean_module == 'Accounts':
                account_crm_id = rel.bean_id

    rec = CrmCallRecording.objects.create(
        filename=base,
        pbx_path=pbx_path,
        local_path=local_path,
        extension=ext or '',
        caller_number=caller_number,
        contact_crm_id=contact_crm_id,
        account_crm_id=account_crm_id,
        is_assigned=bool(contact_crm_id or account_crm_id),
        recorded_at=recorded_at or timezone.now(),
        file_size=local_size,
        synced_at=timezone.now(),
    )
    return {
        'ok': True, 'id': rec.id, 'already': False,
        'assigned': rec.is_assigned,
        'contact_crm_id': contact_crm_id,
        'account_crm_id': account_crm_id,
        'filename': base,
    }
PYEOF
python3 -c "import ast; ast.parse(open('apps/abpe_crm/services/recording_sync.py').read()); print('  recording_sync.py OK')"

echo "=== [3/6] Views (Sync-Endpoint) anlegen ==="
cat > apps/abpe_crm/views_recording.py << 'PYEOF'
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
        result = sync_recording(remote, extension=data.get('extension'), callerid=data.get('callerid'))
        status = 200 if result.get('ok') else 500
        return JsonResponse(result, status=status)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)
PYEOF
python3 -c "import ast; ast.parse(open('apps/abpe_crm/views_recording.py').read()); print('  views_recording.py OK')"

echo "=== [4/6] Wrapper in views.py (Token-Auth) anhängen ==="
python3 - << 'PYEOF'
p = 'apps/abpe_crm/views.py'
s = open(p, encoding='utf-8').read()
if 'api_recording_sync' in s:
    print("  api_recording_sync existiert schon — übersprungen.")
else:
    add = '''

# ============================================================
# API — CALL RECORDING (Wrapper mit Token-Auth)
# ============================================================
from .views_recording import _api_sync as _rec_sync_impl
api_recording_sync = csrf_exempt(login_or_token_required(require_POST(_rec_sync_impl)))
'''
    s = s.rstrip() + '\n' + add + '\n'
    open(p, 'w', encoding='utf-8').write(s)
    print("  api_recording_sync Wrapper angehängt.")
PYEOF
python3 -c "import ast; ast.parse(open('apps/abpe_crm/views.py').read()); print('  views.py OK')"

echo "=== [5/6] URL eintragen ==="
python3 - << 'PYEOF'
p = 'apps/abpe_crm/urls.py'
s = open(p, encoding='utf-8').read()
if 'api_recording_sync' in s:
    print("  Route existiert schon — übersprungen.")
else:
    anchor = "    path('api/note/save/',                      views.api_note_save,      name='api_note_save'),"
    newline = anchor + "\n    path('api/recording/sync/',                 views.api_recording_sync, name='api_recording_sync'),"
    assert s.count(anchor) == 1, f"URL-Anker {s.count(anchor)}x"
    s = s.replace(anchor, newline)
    open(p, 'w', encoding='utf-8').write(s)
    print("  Route api_recording_sync eingetragen.")
PYEOF
python3 -c "import ast; ast.parse(open('apps/abpe_crm/urls.py').read()); print('  urls.py OK')"

echo "=== [6/6] manage.py check ==="
python manage.py check 2>&1 | tail -2

echo ""
echo "============================================================"
echo "✅ record_02 fertig (Sync-Endpoint)."
echo "TEST mit echter WAV von der PBX (eine der gefundenen):"
echo '  TOKEN=9d90836090dd1c42191427ab36d5d811242a62c3'
echo '  curl -s -X POST -H "Authorization: Token $TOKEN" -H "Content-Type: application/json" \'
echo '    -d "{\"pbx_path\":\"/var/spool/asterisk/monitor/2026/06/20/abpe-PJSIP_224-00000018-1781906825108.wav\",\"extension\":\"224\"}" \'
echo '    https://abpe.win.abcona.info/crm/api/recording/sync/'
echo ""
echo "Danach: record_03_streaming_endpoint.sh"
echo "============================================================"

