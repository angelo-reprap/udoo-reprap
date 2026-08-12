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


def _wav_duration(path):
    """Dauer einer WAV in Sekunden (aus Header). None bei Fehler."""
    try:
        import wave
        with wave.open(path, 'rb') as w:
            fr = w.getframerate()
            if fr:
                return int(round(w.getnframes() / float(fr)))
    except Exception:
        pass
    return None



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


def sync_recording(remote_path, extension=None, callerid=None, contact_crm_id=None, account_crm_id=None):
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

    # Zuordnung: explizite IDs (offener Reiter) haben Vorrang, sonst CallerID-Auflösung
    caller_number = callerid or None
    if not contact_crm_id and not account_crm_id and caller_number:
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
        is_assigned=False,  # erst True wenn Contact UND Betreff (siehe assign)
        recorded_at=recorded_at or timezone.now(),
        file_size=local_size,
        duration_sec=_wav_duration(local_path),
        synced_at=timezone.now(),
    )
    return {
        'ok': True, 'id': rec.id, 'already': False,
        'assigned': rec.is_assigned,
        'contact_crm_id': contact_crm_id,
        'account_crm_id': account_crm_id,
        'filename': base,
    }
