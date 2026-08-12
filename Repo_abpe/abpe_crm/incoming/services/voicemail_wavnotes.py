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
