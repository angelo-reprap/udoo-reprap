#!/bin/bash
# ============================================================
# wavnotes_02_services.sh
# WAV-Notizen — Etappe 2: Services
#   services/voicemail_wavnotes.py  — SFTP-Scan INBOX+Old, .txt-Metadaten
#   services/whisper_service.py     — faster-whisper Singleton (GPU)
# Gleicher SFTP-Verbindungsstil wie recording_sync.py.
# ============================================================
set -e
cd /opt/abpe/backend

echo "=== [1/4] voicemail_wavnotes.py anlegen ==="
mkdir -p apps/abpe_crm/services
cat > apps/abpe_crm/services/voicemail_wavnotes.py << 'PYEOF'
"""
voicemail_wavnotes.py — WAV-Notizen: sammelt Voicemail-Nachrichten
(INBOX + Old) ueber alle konfigurierten Mailboxen (siehe
ami_control.get_voicemail_boxes fuer die Mailbox-Liste), liest
Metadaten aus der begleitenden .txt (Standard-Asterisk-Voicemail-
Format, [message]-Section). Gleicher Verbindungsstil wie
recording_sync.py (paramiko SFTP, PBX_ROOT_USER/PBX_ROOT_PASSWORD
aus settings/pbx.py).
"""
import os
import configparser
import datetime
from django.utils import timezone

VM_BASE = '/var/spool/asterisk/voicemail/default'
FOLDERS = ('INBOX', 'Old')
MIN_WAV_SIZE = 200  # Byte - filtert leere/kaputte Testnachrichten (z.B. 44 Byte)


def _sftp_connect():
    import paramiko
    from abpe_backend.settings import pbx
    t = paramiko.Transport((pbx.PBX_HOST, 22))
    t.connect(username=pbx.PBX_ROOT_USER, password=pbx.PBX_ROOT_PASSWORD)
    return paramiko.SFTPClient.from_transport(t), t


def _parse_msg_txt(raw_text):
    """Parst Asterisk-Voicemail-.txt ([message]-Section) zu einem Dict."""
    parser = configparser.ConfigParser(strict=False)
    try:
        parser.read_string(raw_text)
        if parser.has_section('message'):
            return dict(parser.items('message'))
    except Exception:
        pass
    data = {}
    for line in raw_text.splitlines():
        line = line.strip()
        if not line or line.startswith('[') or line.startswith(';'):
            continue
        if '=' in line:
            k, v = line.split('=', 1)
            data[k.strip()] = v.strip()
    return data


def list_wavnotes(mailboxes):
    """
    mailboxes: Liste von Mailbox-Nummern (str), z.B. aus get_voicemail_boxes().
    Liest INBOX + Old jeder Box, gibt Liste zurueck (neueste zuerst):
    [{mailbox, folder, msg_id, filename, callerid, duration, origtime, size}, ...]
    """
    sftp, transport = _sftp_connect()
    result = []
    try:
        for box in mailboxes:
            for folder in FOLDERS:
                dir_path = f'{VM_BASE}/{box}/{folder}'
                try:
                    entries = sftp.listdir(dir_path)
                except IOError:
                    continue
                wav_files = [e for e in entries if e.lower().endswith('.wav')]
                for wav_name in wav_files:
                    msg_id = os.path.splitext(wav_name)[0]
                    wav_path = f'{dir_path}/{wav_name}'
                    try:
                        st = sftp.stat(wav_path)
                    except IOError:
                        continue
                    if st.st_size < MIN_WAV_SIZE:
                        continue
                    txt_path = f'{dir_path}/{msg_id}.txt'
                    meta = {}
                    try:
                        with sftp.open(txt_path, 'r') as f:
                            raw = f.read()
                            if isinstance(raw, bytes):
                                raw = raw.decode('utf-8', errors='replace')
                            meta = _parse_msg_txt(raw)
                    except IOError:
                        pass
                    origtime_raw = meta.get('origtime')
                    if origtime_raw:
                        try:
                            origtime = timezone.make_aware(
                                datetime.datetime.fromtimestamp(int(origtime_raw)))
                        except Exception:
                            origtime = timezone.make_aware(
                                datetime.datetime.fromtimestamp(st.st_mtime))
                    else:
                        origtime = timezone.make_aware(
                            datetime.datetime.fromtimestamp(st.st_mtime))
                    duration_raw = meta.get('duration')
                    try:
                        duration = int(duration_raw) if duration_raw else None
                    except ValueError:
                        duration = None
                    result.append({
                        'mailbox': box,
                        'folder': folder,
                        'msg_id': msg_id,
                        'filename': wav_name,
                        'callerid': meta.get('callerid', ''),
                        'duration': duration,
                        'origtime': origtime.isoformat(),
                        'size': st.st_size,
                    })
    finally:
        transport.close()
    result.sort(key=lambda r: r['origtime'], reverse=True)
    return result


def fetch_wav_bytes(mailbox, folder, msg_id):
    """Holt eine einzelne WAV per SFTP (fuer Cache-Miss)."""
    if folder not in FOLDERS:
        raise ValueError(f'Ungueltiger Ordner: {folder}')
    sftp, transport = _sftp_connect()
    try:
        path = f'{VM_BASE}/{mailbox}/{folder}/{msg_id}.wav'
        with sftp.open(path, 'rb') as f:
            return f.read()
    finally:
        transport.close()
PYEOF
python3 -c "import ast; ast.parse(open('apps/abpe_crm/services/voicemail_wavnotes.py').read()); print('  voicemail_wavnotes.py OK')"

echo "=== [2/4] whisper_service.py anlegen ==="
cat > apps/abpe_crm/services/whisper_service.py << 'PYEOF'
"""
whisper_service.py — Singleton-Wrapper fuer faster-whisper (WAV -> Rohtext).
Modell wird einmal pro Django-Worker-Prozess geladen (nicht pro Request),
analog zum deepseek_pbx-Singleton in deepseek_api_pbx.py.
Getestet: 'medium' auf GPU (RTX PRO 2000, float16), ~1.6s Ladezeit aus Cache.
"""
import time
import logging

logger = logging.getLogger(__name__)

MODEL_SIZE = 'medium'


class WhisperService:
    def __init__(self):
        self._model = None

    def _get_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            t0 = time.time()
            self._model = WhisperModel(MODEL_SIZE, device='cuda', compute_type='float16')
            logger.info(f'Whisper-Modell "{MODEL_SIZE}" geladen in {time.time() - t0:.1f}s')
        return self._model

    def transcribe(self, path, language='de'):
        model = self._get_model()
        segments, info = model.transcribe(path, language=language, beam_size=5)
        text = ''.join(seg.text for seg in segments).strip()
        return {
            'text': text,
            'language': info.language,
            'language_probability': round(info.language_probability, 2),
        }


whisper_service = WhisperService()
PYEOF
python3 -c "import ast; ast.parse(open('apps/abpe_crm/services/whisper_service.py').read()); print('  whisper_service.py OK')"

echo "=== [3/4] faster-whisper Modell einmalig vorwaermen (laedt HF-Cache, ~1.5GB) ==="
python3 -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
from apps.abpe_crm.services.whisper_service import whisper_service
whisper_service._get_model()
print('  Modell-Cache vorgewaermt.')
"

echo "=== [4/4] fertig ==="
echo ""
echo "============================================================"
echo "✅ wavnotes_02 fertig (Services)."
echo "Danach: wavnotes_03_views_urls.sh"
echo "============================================================"
