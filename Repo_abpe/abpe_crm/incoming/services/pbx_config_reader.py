"""
pbx_config_reader.py — liest die Asterisk-Dialplan-Config LIVE per SFTP
von der PBX (gleicher Verbindungsstil wie recording_sync.py) und parst
daraus alle konfigurierten Konferenzraeume (ConfBridge-Aufrufe).

Bewusst KEINE lokale Kopie/Tabelle — die Config-Datei auf der PBX ist
die einzige Quelle der Wahrheit. Jeder Aufruf liest frisch, damit
Aenderungen (Raum hinzufuegen/loeschen in Issabel oder handgeschrieben
in extensions_custom.conf) sofort und ohne Code-Deploy sichtbar sind.
"""
import re
import logging

logger = logging.getLogger(__name__)

CONFIG_FILES = [
    '/etc/asterisk/extensions_additional.conf',   # Issabel-GUI-generierte Raeume (z. B. 034, 035)
    '/etc/asterisk/extensions_custom.conf',       # handgeschriebene Custom-Raeume (z. B. 5555)
]

# Erfasst: exten => 5555,1,... ConfBridge(5555,default_bridge,default_user)
# sowie:   exten => 034,n,Set(MEETME_ROOMNUM=034) ... ConfBridge(${MEETME_ROOMNUM},...)
_EXTEN_LINE = re.compile(r'^\s*exten\s*=>\s*([A-Za-z0-9_*]+)\s*,')
_CONFBRIDGE_CALL = re.compile(r'ConfBridge\s*\(')
_ROOMNUM_SET = re.compile(r'Set\(MEETME_ROOMNUM=([A-Za-z0-9_]+)\)')
_COMMENT_LINE = re.compile(r'^\s*;')


def _sftp_connect():
    import paramiko
    from abpe_backend.settings import pbx
    t = paramiko.Transport((pbx.PBX_HOST, 22))
    t.connect(username=pbx.PBX_ROOT_USER, password=pbx.PBX_ROOT_PASSWORD)
    return paramiko.SFTPClient.from_transport(t), t


def _read_remote_file(sftp, remote_path):
    with sftp.open(remote_path, 'r') as f:
        return f.read().decode('utf-8', errors='replace')


def _parse_confbridge_rooms(text):
    """Findet alle Extensions, deren Definition (ueber mehrere 'exten =>'-Zeilen
    derselben Extension hinweg) einen ConfBridge(...)-Aufruf enthaelt.
    Aktive/auskommentierte Zeilen (';exten...') werden ignoriert."""
    rooms_seen = {}

    current_exten = None
    current_has_confbridge = False
    current_roomnum_ref = False

    def _flush():
        if current_exten and (current_has_confbridge or current_roomnum_ref):
            if current_exten not in rooms_seen and current_exten != 'STARTMEETME':
                rooms_seen[current_exten] = True

    for line in text.splitlines():
        if _COMMENT_LINE.match(line):
            continue

        m = _EXTEN_LINE.match(line)
        if m:
            exten = m.group(1)
            if exten != current_exten:
                _flush()
                current_exten = exten
                current_has_confbridge = False
                current_roomnum_ref = False

        if _CONFBRIDGE_CALL.search(line):
            current_has_confbridge = True
        if '${MEETME_ROOMNUM}' in line and current_exten and current_exten.isdigit():
            current_roomnum_ref = True

    _flush()
    return sorted(rooms_seen.keys(), key=lambda x: (0, int(x)) if x.isdigit() else (1, x))


def get_conference_rooms_from_config():
    """Liest beide Dialplan-Dateien live von der PBX und gibt alle
    konfigurierten Konferenzraeume zurueck (Extensions, die ConfBridge
    aufrufen — egal ob GUI-generiert oder handgeschrieben)."""
    all_rooms = []
    seen = set()

    sftp = transport = None
    try:
        sftp, transport = _sftp_connect()
        for remote_path in CONFIG_FILES:
            try:
                text = _read_remote_file(sftp, remote_path)
            except IOError as exc:
                logger.warning("PBX-Config nicht lesbar: %s (%s)", remote_path, exc)
                continue

            for room in _parse_confbridge_rooms(text):
                if room in seen:
                    continue
                seen.add(room)
                all_rooms.append({'room_extension': room, 'source_file': remote_path})
    except Exception as exc:
        logger.error("PBX-Config-Lesefehler (SFTP): %s", exc)
        return []
    finally:
        if sftp:
            sftp.close()
        if transport:
            transport.close()

    return sorted(all_rooms, key=lambda r: (0, int(r['room_extension']))
                  if r['room_extension'].isdigit() else (1, r['room_extension']))
