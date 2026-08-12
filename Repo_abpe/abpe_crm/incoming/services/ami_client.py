import socket
import time
import re
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

AMI_HOST = getattr(settings, 'AMI_HOST', '172.20.3.120')
AMI_PORT = getattr(settings, 'AMI_PORT', 5038)
AMI_USER = getattr(settings, 'AMI_USER', 'abpe_crm')
AMI_SECRET = getattr(settings, 'AMI_SECRET', 'abcona2025')


class AMIClient:
    """Einfacher synchroner AMI-Client für kurze Abfragen."""

    def __init__(self, host=AMI_HOST, port=AMI_PORT,
                 user=AMI_USER, secret=AMI_SECRET, timeout=5):
        self.host = host
        self.port = port
        self.user = user
        self.secret = secret
        self.timeout = timeout
        self._sock = None

    def connect(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(self.timeout)
        self._sock.connect((self.host, self.port))
        self._recv()  # Banner: Asterisk Call Manager/7.0.3

        self._send(
            f'Action: Login\r\n'
            f'Username: {self.user}\r\n'
            f'Secret: {self.secret}\r\n\r\n'
        )
        resp = self._recv(0.5)
        if 'Authentication accepted' not in resp:
            raise ConnectionError(f'AMI Login fehlgeschlagen: {resp}')

    def disconnect(self):
        if self._sock:
            try:
                self._send('Action: Logoff\r\n\r\n')
            except Exception:
                pass
            self._sock.close()
            self._sock = None

    def _send(self, data):
        self._sock.sendall(data.encode())

    def _recv(self, wait=0.3):
        # Bis zu `wait` auf das ERSTE Byte warten, dann zuegig leerlesen
        # (kein starres time.sleep(wait) mehr -> antwortet so schnell wie die PBX).
        chunks = []
        self._sock.settimeout(wait)
        try:
            first = self._sock.recv(4096)
            if first:
                chunks.append(first.decode(errors='replace'))
                self._sock.settimeout(0.06)  # Idle-Erkennung: Antwort komplett (lokale PBX)
                while True:
                    chunk = self._sock.recv(4096)
                    if not chunk:
                        break
                    chunks.append(chunk.decode(errors='replace'))
        except socket.timeout:
            pass
        self._sock.settimeout(self.timeout)
        return ''.join(chunks)

    def command(self, cmd, wait=1.0):
        self._send(f'Action: Command\r\nCommand: {cmd}\r\n\r\n')
        return self._recv(wait)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()


def get_sip_peers():
    """
    Gibt Liste von Nebenstellen zurück:
    [{'name': '12', 'host': '172.20.3.86', 'status': 'OK', 'ms': 5}, ...]
    """
    peers = []
    try:
        with AMIClient() as ami:
            raw = ami.command('sip show peers', wait=1.5)

        for line in raw.splitlines():
            if not line.startswith('Output:'):
                continue
            # "Output: 12/12                     172.20.3.86  ...  5060  OK (5 ms)"
            content = line[7:].strip()
            if content.startswith('Name') or content.startswith('---') or not content:
                continue

            # Name parsen (vor dem ersten Leerzeichen)
            parts = content.split()
            if len(parts) < 2:
                continue

            raw_name = parts[0]
            # "12/12" → "12", "1977610/1977610" → "1977610"
            name = raw_name.split('/')[0]

            # Status: OK oder UNKNOWN
            if 'OK' in content:
                ms_match = re.search(r'OK \((\d+) ms\)', content)
                ms = int(ms_match.group(1)) if ms_match else 0
                host = parts[1] if len(parts) > 1 else ''
                peers.append({
                    'name': name,
                    'raw_name': raw_name,
                    'host': host,
                    'status': 'OK',
                    'ms': ms,
                    'online': True,
                })
            elif 'UNKNOWN' in content:
                peers.append({
                    'name': name,
                    'raw_name': raw_name,
                    'host': '',
                    'status': 'UNKNOWN',
                    'ms': None,
                    'online': False,
                })

    except Exception as e:
        logger.error(f'AMI get_sip_peers Fehler: {e}')

    # Sortierung: Interne kurze Nummern zuerst, dann Trunks
    def sort_key(p):
        try:
            return (0, int(p['name']))
        except ValueError:
            return (1, p['name'])

    return sorted(peers, key=sort_key)


def originate_call(extension, destination, caller_id='ABpE CRM'):
    """
    Startet einen Anruf: extension klingelt zuerst, dann wird destination gewählt.
    extension: z.B. '12'
    destination: normalisierte Nummer z.B. '004917812345678'
    """
    try:
        with AMIClient() as ami:
            action = (
                f'Action: Originate\r\n'
                f'Channel: SIP/{extension}\r\n'
                f'Exten: {destination}\r\n'
                f'Context: from-internal\r\n'
                f'Priority: 1\r\n'
                f'CallerID: {caller_id}\r\n'
                f'Timeout: 30000\r\n'
                f'Async: true\r\n'
                f'\r\n'
            )
            ami._send(action)
            resp = ami._recv(1.0)
            success = 'Originate successfully' in resp or 'Response: Success' in resp
            return {'success': success, 'raw': resp[:200]}
    except Exception as e:
        logger.error(f'AMI originate Fehler: {e}')
        return {'success': False, 'error': str(e)}


def get_extension_status(extension):
    """Prüft ob eine Nebenstelle gerade aktiv ist."""
    try:
        with AMIClient() as ami:
            raw = ami.command(f'sip show peer {extension}', wait=0.8)
        status = 'unknown'
        for line in raw.splitlines():
            if 'Status' in line and 'Output:' in line:
                if 'OK' in line:
                    status = 'free'
                elif 'BUSY' in line:
                    status = 'busy'
                else:
                    status = 'offline'
        return status
    except Exception as e:
        logger.error(f'AMI extension_status Fehler: {e}')
        return 'unknown'


def get_voicemail_count(extension):
    """Voicemail-Count via AMI MailboxCount"""
    try:
        with AMIClient() as ami:
            ami._send(f'Action: MailboxCount\r\nMailbox: {extension}@default\r\n\r\n')
            raw = ami._recv(0.5)
        new_msg = int(re.search(r'NewMessages:\s*(\d+)', raw).group(1)) if re.search(r'NewMessages:\s*(\d+)', raw) else 0
        old_msg = int(re.search(r'OldMessages:\s*(\d+)', raw).group(1)) if re.search(r'OldMessages:\s*(\d+)', raw) else 0
        urg_msg = int(re.search(r'UrgMessages:\s*(\d+)', raw).group(1)) if re.search(r'UrgMessages:\s*(\d+)', raw) else 0
        return {'new_messages': new_msg, 'old_messages': old_msg, 'urgent_messages': urg_msg}
    except Exception as e:
        return {'new_messages': 0, 'old_messages': 0, 'error': str(e)}


def get_voicemail_counts(boxes):
    """Voicemail-Count fuer MEHRERE Boxen ueber eine einzige AMI-Verbindung."""
    result = {}
    try:
        with AMIClient() as ami:
            for box in boxes:
                ami._send(f'Action: MailboxCount\r\nMailbox: {box}@default\r\n\r\n')
                raw = ami._recv(0.5)
                new_msg = int(re.search(r'NewMessages:\s*(\d+)', raw).group(1)) if re.search(r'NewMessages:\s*(\d+)', raw) else 0
                old_msg = int(re.search(r'OldMessages:\s*(\d+)', raw).group(1)) if re.search(r'OldMessages:\s*(\d+)', raw) else 0
                urg_msg = int(re.search(r'UrgMessages:\s*(\d+)', raw).group(1)) if re.search(r'UrgMessages:\s*(\d+)', raw) else 0
                result[box] = {'new_messages': new_msg, 'old_messages': old_msg, 'urgent_messages': urg_msg}
    except Exception as e:
        for box in boxes:
            if box not in result:
                result[box] = {'new_messages': 0, 'old_messages': 0, 'error': str(e)}
    return result


def get_pjsip_endpoint_status(extension):
    """Extension-Status via pjsip show endpoint — korrekt für WebRTC/pjsip."""
    try:
        with AMIClient() as ami:
            raw = ami.command(f'pjsip show endpoint {extension}', wait=0.8)
        for line in raw.splitlines():
            if not line.startswith('Output:'):
                continue
            content = line[7:].strip()
            if 'Not in use' in content:
                return 'free'
            elif 'In use' in content or 'Busy' in content:
                return 'busy'
            elif 'Unavailable' in content:
                return 'offline'
        return 'unknown'
    except Exception as e:
        logger.error(f'AMI pjsip_endpoint_status Fehler: {e}')
        return 'unknown'


def get_dnd_status(extension):
    """DND-Status aus Asterisk DB lesen."""
    try:
        with AMIClient() as ami:
            ami._send(f'Action: DBGet\r\nFamily: DND\r\nKey: {extension}\r\n\r\n')
            raw = ami._recv(0.3)
        return 'YES' in raw
    except Exception:
        return False


def get_active_channels():
    """Aktive Kanäle — für Redirect/Transfer."""
    channels = []
    try:
        with AMIClient() as ami:
            raw = ami.command('core show channels concise', wait=0.8)
        for line in raw.splitlines():
            if not line.startswith('Output:'):
                continue
            content = line[7:].strip()
            if not content or content.startswith('Channel') or '!' in content:
                continue
            parts = content.split('!')
            if len(parts) >= 2:
                channel = parts[0].strip()
                # Extension aus Channel-Name extrahieren: PJSIP/224-xxx → 224
                ext_match = re.search(r'PJSIP/(\d+)-', channel)
                if ext_match:
                    channels.append({
                        'channel': channel,
                        'extension': ext_match.group(1),
                    })
    except Exception as e:
        logger.error(f'AMI active_channels Fehler: {e}')
    return channels


def get_parked_calls():
    """Geparkte Anrufe via AMI ParkedCalls."""
    parked = []
    try:
        with AMIClient() as ami:
            ami._send('Action: ParkedCalls\r\n\r\n')
            raw = ami._recv(1.0)
        # Blöcke parsen
        blocks = raw.split('\r\n\r\n')
        for block in blocks:
            if 'Event: ParkedCall' not in block:
                continue
            def _get(key):
                m = re.search(rf'{key}:\s*(.+)', block)
                return m.group(1).strip() if m else ''
            parked.append({
                'slot':      _get('Exten'),
                'channel':   _get('Channel'),
                'caller_id': _get('CallerIDNum'),
                'caller_name': _get('CallerIDName'),
                'duration':  _get('Duration'),
                'parked_by': _get('ParkerDialString'),
            })
    except Exception as e:
        logger.error(f'AMI parked_calls Fehler: {e}')
    return parked


def get_meetme_rooms():
    """Aktive MeetMe Konferenzen."""
    rooms = {}
    try:
        with AMIClient() as ami:
            ami._send('Action: MeetmeList\r\n\r\n')
            raw = ami._recv(1.0)
        blocks = raw.split('\r\n\r\n')
        for block in blocks:
            if 'Event: MeetmeList' not in block:
                continue
            def _get(key):
                m = re.search(rf'{key}:\s*(.+)', block)
                return m.group(1).strip() if m else ''
            conf = _get('Conference')
            if conf:
                if conf not in rooms:
                    rooms[conf] = {'conference': conf, 'users': []}
                rooms[conf]['users'].append({
                    'usernum':   _get('UserNumber'),
                    'caller_id': _get('CallerIDNum'),
                    'name':      _get('CallerIDName'),
                    'muted':     _get('Muted') == 'Yes',
                })
    except Exception as e:
        logger.error(f'AMI meetme_rooms Fehler: {e}')
    return list(rooms.values())


def get_confbridge_rooms():
    """Aktive ConfBridge Konferenzen."""
    rooms = {}
    try:
        with AMIClient() as ami:
            ami._send('Action: ConfbridgeListRooms\r\n\r\n')
            raw = ami._recv(1.0)
        blocks = raw.split('\r\n\r\n')
        for block in blocks:
            if 'Event: ConfbridgeListRooms' not in block:
                continue
            def _get(key):
                m = re.search(rf'{key}:\s*(.+)', block)
                return m.group(1).strip() if m else ''
            conf = _get('Conference')
            if conf:
                rooms[conf] = {
                    'conference': conf,
                    'parties':    int(_get('Parties') or 0),
                    'marked':     int(_get('Marked') or 0),
                    'locked':     _get('Locked') == 'Yes',
                }
    except Exception as e:
        logger.error(f'AMI confbridge_rooms Fehler: {e}')
    return list(rooms.values())


def get_fop_status(extensions, vm_extensions=None):
    """
    Alles in einem AMI-Connect:
    - pjsip Status + DND pro Extension
    - Aktive Kanäle
    - Parking
    - MeetMe + ConfBridge
    - Voicemail
    """
    result = {
        'extensions': [],
        'channels':   [],
        'parking':    [],
        'meetme':     [],
        'confbridge': [],
        'voicemail':  {},
    }
    if vm_extensions is None:
        vm_extensions = []

    try:
        with AMIClient() as ami:
            # 1a. pjsip Status ALLE auf einmal
            raw_all = ami.command('pjsip show endpoints', wait=1.0)
            pjsip_status = {}
            for line in raw_all.splitlines():
                if not line.startswith('Output:'):
                    continue
                c = line[7:].strip()
                if 'Endpoint:' not in c[:20]:
                    continue
                for ext in extensions:
                    if f'/{ext} ' in c or f'/{ext}\t' in c or c.strip().endswith(f'/{ext}'):
                        if 'Not in use' in c:
                            pjsip_status[ext] = 'free'
                        elif 'In use' in c or 'Busy' in c:
                            pjsip_status[ext] = 'busy'
                        elif 'Unavailable' in c:
                            pjsip_status[ext] = 'offline'
                        else:
                            pjsip_status[ext] = 'unknown'

            # 1b. SIP Status fuer Extensions die nicht in pjsip sind
            sip_extensions = [e for e in extensions if e not in pjsip_status]
            sip_status = {}
            if sip_extensions:
                raw_sip = ami.command('sip show peers', wait=1.0)
                for line in raw_sip.splitlines():
                    if not line.startswith('Output:'):
                        continue
                    c = line[7:].strip()
                    for ext in sip_extensions:
                        if c.startswith(ext + '/') or c.startswith(ext + ' '):
                            if 'OK' in c:
                                sip_status[ext] = 'free'
                            elif 'UNREACHABLE' in c or 'LAGGED' in c:
                                sip_status[ext] = 'offline'
                            elif 'UNKNOWN' in c:
                                sip_status[ext] = 'offline'
                            else:
                                sip_status[ext] = 'unknown'

            # DND + Extension zusammenbauen
            for ext in extensions:
                ami._send(f'Action: DBGet\r\nFamily: DND\r\nKey: {ext}\r\n\r\n')
                raw_dnd = ami._recv(0.15)
                dnd = 'YES' in raw_dnd
                if ext in pjsip_status:
                    status = pjsip_status[ext]
                elif ext in sip_status:
                    status = sip_status[ext]
                else:
                    status = 'offline'
                if dnd and status == 'free':
                    status = 'dnd'
                result['extensions'].append({
                    'extension': ext,
                    'status':    status,
                    'dnd':       dnd,
                })

            # 2. Aktive Kanäle
            raw_ch = ami.command('core show channels concise', wait=0.5)
            for line in raw_ch.splitlines():
                if not line.startswith('Output:'):
                    continue
                content = line[7:].strip()
                if not content:
                    continue
                parts = content.split('!')
                if len(parts) >= 2:
                    channel = parts[0].strip()
                    ext_match = re.search(r'PJSIP/(\d+)-', channel)
                    if ext_match:
                        result['channels'].append({
                            'channel':   channel,
                            'extension': ext_match.group(1),
                        })

            # 3. Parking
            ami._send('Action: ParkedCalls\r\n\r\n')
            raw_park = ami._recv(0.5)
            for block in raw_park.split('\r\n\r\n'):
                if 'Event: ParkedCall\r' not in block and 'Event: ParkedCall\n' not in block:
                    continue
                if 'ParkedCallsComplete' in block or 'ParkedCallGiveUp' in block:
                    continue
                def _g(key, b=block):
                    m = re.search(rf'{key}:\s*(.+)', b)
                    return m.group(1).strip() if m else ''
                result['parking'].append({
                    'slot':        _g('ParkingSpace'),
                    'caller_id':   _g('ParkeeCallerIDNum'),
                    'caller_name': _g('ParkeeCallerIDName'),
                    'duration':    _g('ParkingDuration'),
                })

            # 4. MeetMe
            ami._send('Action: MeetmeList\r\n\r\n')
            raw_mm = ami._recv(0.5)
            mm_rooms = {}
            for block in raw_mm.split('\r\n\r\n'):
                if 'Event: MeetmeList' not in block:
                    continue
                def _g(key, b=block):
                    m = re.search(rf'{key}:\s*(.+)', b)
                    return m.group(1).strip() if m else ''
                conf = _g('Conference')
                if conf:
                    if conf not in mm_rooms:
                        mm_rooms[conf] = {'conference': conf, 'users': []}
                    mm_rooms[conf]['users'].append({'caller_id': _g('CallerIDNum'), 'name': _g('CallerIDName')})
            result['meetme'] = list(mm_rooms.values())

            # 5. ConfBridge
            ami._send('Action: ConfbridgeListRooms\r\n\r\n')
            raw_cb = ami._recv(0.5)
            for block in raw_cb.split('\r\n\r\n'):
                if 'Event: ConfbridgeListRooms' not in block:
                    continue
                def _g(key, b=block):
                    m = re.search(rf'{key}:\s*(.+)', b)
                    return m.group(1).strip() if m else ''
                conf = _g('Conference')
                if conf:
                    result['confbridge'].append({
                        'conference': conf,
                        'parties':    int(_g('Parties') or 0),
                    })

            # 6. Voicemail
            for vm_ext in vm_extensions:
                ami._send(f'Action: MailboxCount\r\nMailbox: {vm_ext}@default\r\n\r\n')
                raw_vm = ami._recv(0.3)
                new_msg = int(re.search(r'NewMessages:\s*(\d+)', raw_vm).group(1)) if re.search(r'NewMessages:\s*(\d+)', raw_vm) else 0
                result['voicemail'][vm_ext] = new_msg

    except Exception as e:
        logger.error(f'AMI get_fop_status Fehler: {e}')

    return result


def get_my_channel(extension):
    """Aktiven Kanal einer Extension finden — gibt Trunk-Kanal zurueck fuer Park."""
    try:
        with AMIClient() as ami:
            raw = ami.command('core show channels concise', wait=0.8)
        lines = []
        call_id = None
        for line in raw.splitlines():
            if not line.startswith('Output:'):
                continue
            content = line[7:].strip()
            if not content:
                continue
            lines.append(content)
            # Eigenen Kanal + Call-ID finden
            m = re.search(r'((?:PJSIP|SIP)/' + re.escape(extension) + r'-[^\s!]+)', content)
            if m:
                # Call-ID ist das vorletzte Feld in concise output
                parts = content.split('!')
                if len(parts) >= 12:
                    call_id = parts[11].strip()
        # Trunk-Kanal mit gleicher Call-ID finden
        if call_id:
            for content in lines:
                if call_id in content and 'AppDial' in content:
                    trunk = content.split('!')[0].strip()
                    return trunk
        # Fallback: eigenen Kanal zurueckgeben
        for content in lines:
            m = re.search(r'((?:PJSIP|SIP)/' + re.escape(extension) + r'-[^\s!]+)', content)
            if m:
                return m.group(1)
    except Exception as e:
        logger.error(f'AMI get_my_channel Fehler: {e}')
    return None


def park_channel(channel, parking_lot='default'):
    """Kanal in Parking-Lot parken via AMI Park Action."""
    try:
        with AMIClient() as ami:
            ami._send(
                f'Action: Park\r\n'
                f'Channel: {channel}\r\n'
                f'Timeout: 60\r\n'
                f'Parkinglot: {parking_lot}\r\n'
                f'\r\n'
            )
            raw = ami._recv(0.5)
            success = 'Response: Success' in raw or 'Parked' in raw
            return {'success': success, 'raw': raw[:200]}
    except Exception as e:
        logger.error(f'AMI park_channel Fehler: {e}')
        return {'success': False, 'error': str(e)}


def get_and_park(extension):
    """Aktiven Kanal finden und in einem AMI-Connect sofort parken."""
    try:
        with AMIClient() as ami:
            # 1. Kanal finden
            raw = ami.command('core show channels concise', wait=0.5)
            channel = None
            call_id = None
            lines = []
            for line in raw.splitlines():
                if not line.startswith('Output:'):
                    continue
                content = line[7:].strip()
                if not content:
                    continue
                lines.append(content)
                m = re.search(r'(?:PJSIP|SIP)/' + re.escape(extension) + r'-[^\s!]+', content)
                if m:
                    parts = content.split('!')
                    if len(parts) >= 12:
                        call_id = parts[11].strip()

            # Trunk-Kanal mit gleicher Call-ID finden
            if call_id:
                for content in lines:
                    if call_id in content and 'AppDial' in content:
                        channel = content.split('!')[0].strip()
                        break

            # Fallback: eigenen Kanal
            if not channel:
                for content in lines:
                    m = re.search(r'((?:PJSIP|SIP)/' + re.escape(extension) + r'-[^\s!]+)', content)
                    if m:
                        channel = m.group(1)
                        break

            if not channel:
                return {'success': False, 'error': 'Kein aktiver Kanal gefunden'}

            # 2. Sofort Redirect zu parkedcalls 700
            ami._send(
                f'Action: Redirect\r\n'
                f'Channel: {channel}\r\n'
                f'Exten: 700\r\n'
                f'Context: parkedcalls\r\n'
                f'Priority: 1\r\n'
                f'\r\n'
            )
            raw2 = ami._recv(0.5)
            success = 'Response: Success' in raw2
            return {'success': success, 'channel': channel, 'raw': raw2[:100]}
    except Exception as e:
        logger.error(f'AMI get_and_park Fehler: {e}')
        return {'success': False, 'error': str(e)}


def get_and_conference(extension, conference='5555', context='from-internal-custom'):
    """Aktiven Kanal finden und in Konferenz redirecten."""
    try:
        with AMIClient() as ami:
            raw = ami.command('core show channels concise', wait=0.5)
            channel = None
            call_id = None
            lines = []
            for line in raw.splitlines():
                if not line.startswith('Output:'):
                    continue
                content = line[7:].strip()
                if not content:
                    continue
                lines.append(content)
                m = re.search(r'(?:PJSIP|SIP)/' + re.escape(extension) + r'-[^\s!]+', content)
                if m:
                    parts = content.split('!')
                    if len(parts) >= 12:
                        call_id = parts[11].strip()

            # Trunk-Kanal mit gleicher Call-ID
            if call_id:
                for content in lines:
                    if call_id in content and 'AppDial' in content:
                        channel = content.split('!')[0].strip()
                        break

            # Fallback: eigener Kanal
            if not channel:
                for content in lines:
                    m = re.search(r'((?:PJSIP|SIP)/' + re.escape(extension) + r'-[^\s!]+)', content)
                    if m:
                        channel = m.group(1)
                        break

            if not channel:
                return {'success': False, 'error': 'Kein aktiver Kanal gefunden'}

            ami._send(
                f'Action: Redirect\r\n'
                f'Channel: {channel}\r\n'
                f'Exten: {conference}\r\n'
                f'Context: {context}\r\n'
                f'Priority: 1\r\n'
                f'\r\n'
            )
            raw2 = ami._recv(0.5)
            success = 'Response: Success' in raw2
            return {'success': success, 'channel': channel, 'conference': conference}
    except Exception as e:
        logger.error(f'AMI get_and_conference Fehler: {e}')
        return {'success': False, 'error': str(e)}
