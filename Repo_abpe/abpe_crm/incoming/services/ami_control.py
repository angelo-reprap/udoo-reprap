"""
apps/abpe_crm/services/ami_control.py

Fehlende AMI-Actions fuer das CRM-Telefon-Modul (HUD, Konferenz-Cockpit,
Kunde-Koenig-Flow, Queues, Voicemail-Detail, DND/FWD-write, Recording).

Portiert 1:1 aus dem Electron-Softphone (renderer/ami-service.js), das gegen
die Live-PBX (Asterisk 18.19, Issabel, 172.20.3.120) verifiziert laeuft.

Nutzt AMIClient aus ami_client.py (synchron: connect -> Action -> parse ->
disconnect). ami_client.py bleibt unveraendert.

AMI-User abpe_crm hat: write = system,call,command,reporting,originate
-> deckt alle hier genutzten Actions ab.
"""
import re
import logging
from datetime import datetime

from .ami_client import AMIClient

logger = logging.getLogger(__name__)


# ============================================================
# Helfer
# ============================================================
def _ok(raw):
    return 'Response: Success' in raw


def _blocks(raw):
    return raw.split('\r\n\r\n')


def _field(block, key):
    m = re.search(rf'^{re.escape(key)}:[ \t]*(.*)$', block, re.MULTILINE)
    return m.group(1).strip() if m else ''


def _ext_from_channel(channel):
    """PJSIP/224-000001 -> '224'  |  SIP/12-xxxx -> '12'"""
    m = re.match(r'(?:PJSIP|SIP)/([^-]+)-', channel or '')
    return m.group(1) if m else ''


# ============================================================
# Anruf-Steuerung (Channel bekannt)
# ============================================================
def hangup(channel):
    """AMI Hangup — fremden/eigenen Kanal auflegen."""
    try:
        with AMIClient() as ami:
            ami._send(f'Action: Hangup\r\nChannel: {channel}\r\n\r\n')
            raw = ami._recv(0.5)
        return {'success': _ok(raw)}
    except Exception as e:
        logger.error(f'AMI hangup Fehler: {e}')
        return {'success': False, 'error': str(e)}


def redirect(channel, exten, context='from-internal', priority='1'):
    """AMI Redirect — EINEN Kanal in Dialplan-Exten schicken.
    Fuer 'Zu mir holen' und 'In Konferenz legen' (exten=5555,
    context=from-internal-custom)."""
    try:
        with AMIClient() as ami:
            ami._send(
                f'Action: Redirect\r\nChannel: {channel}\r\n'
                f'Exten: {exten}\r\nContext: {context}\r\nPriority: {priority}\r\n\r\n'
            )
            raw = ami._recv(0.5)
        return {'success': _ok(raw), 'raw': raw[:150]}
    except Exception as e:
        logger.error(f'AMI redirect Fehler: {e}')
        return {'success': False, 'error': str(e)}


def blind_transfer(channel, exten, context='from-internal'):
    """AMI BlindTransfer — nimmt Bridge-Partner automatisch mit."""
    try:
        with AMIClient() as ami:
            ami._send(
                f'Action: BlindTransfer\r\nChannel: {channel}\r\n'
                f'Exten: {exten}\r\nContext: {context}\r\n\r\n'
            )
            raw = ami._recv(0.5)
        return {'success': _ok(raw), 'raw': raw[:150]}
    except Exception as e:
        logger.error(f'AMI blind_transfer Fehler: {e}')
        return {'success': False, 'error': str(e)}


def atxfer(channel, exten, context='from-internal'):
    """AMI Atxfer — nativer Attended Transfer (haelt Erstanruf, ruft Ziel)."""
    try:
        with AMIClient() as ami:
            ami._send(
                f'Action: Atxfer\r\nChannel: {channel}\r\n'
                f'Exten: {exten}\r\nContext: {context}\r\n\r\n'
            )
            raw = ami._recv(0.5)
        return {'success': _ok(raw), 'raw': raw[:150]}
    except Exception as e:
        logger.error(f'AMI atxfer Fehler: {e}')
        return {'success': False, 'error': str(e)}


def cancel_atxfer(channel):
    """AMI CancelAtxfer — laufenden Attended Transfer abbrechen."""
    try:
        with AMIClient() as ami:
            ami._send(f'Action: CancelAtxfer\r\nChannel: {channel}\r\n\r\n')
            raw = ami._recv(0.5)
        return {'success': _ok(raw)}
    except Exception as e:
        logger.error(f'AMI cancel_atxfer Fehler: {e}')
        return {'success': False, 'error': str(e)}


def bridge(channel1, channel2):
    """AMI Bridge — zwei Kanaele verbinden."""
    try:
        with AMIClient() as ami:
            ami._send(
                f'Action: Bridge\r\nChannel1: {channel1}\r\n'
                f'Channel2: {channel2}\r\nTone: no\r\n\r\n'
            )
            raw = ami._recv(0.5)
        return {'success': _ok(raw)}
    except Exception as e:
        logger.error(f'AMI bridge Fehler: {e}')
        return {'success': False, 'error': str(e)}


# ============================================================
# Originate-Varianten
# ============================================================
def originate_from_desk(desk_ext, target, caller_id='ABpE'):
    """Click-to-Dial: Tischtelefon (desk_ext) klingelt zuerst, dann Ziel.
    Local/<desk>@from-internal -> egal ob SIP oder PJSIP."""
    try:
        with AMIClient() as ami:
            ami._send(
                f'Action: Originate\r\nChannel: Local/{desk_ext}@from-internal\r\n'
                f'Exten: {target}\r\nContext: from-internal\r\nPriority: 1\r\n'
                f'CallerID: "{caller_id}" <{desk_ext}>\r\nTimeout: 30000\r\nAsync: true\r\n\r\n'
            )
            raw = ami._recv(1.0)
        return {'success': _ok(raw), 'raw': raw[:150]}
    except Exception as e:
        logger.error(f'AMI originate_from_desk Fehler: {e}')
        return {'success': False, 'error': str(e)}


def originate_to_conf(number, room, caller_id='Konferenz'):
    """Gast (intern/extern) direkt in Konferenzraum holen.
    Local/<nr>@from-internal -> PBX entscheidet Trunk/intern selbst."""
    try:
        with AMIClient() as ami:
            ami._send(
                f'Action: Originate\r\nChannel: Local/{number}@from-internal\r\n'
                f'Exten: {room}\r\nContext: from-internal\r\nPriority: 1\r\n'
                f'CallerID: "{caller_id}" <{number}>\r\nTimeout: 30000\r\nAsync: true\r\n\r\n'
            )
            raw = ami._recv(1.0)
        return {'success': _ok(raw), 'raw': raw[:150]}
    except Exception as e:
        logger.error(f'AMI originate_to_conf Fehler: {e}')
        return {'success': False, 'error': str(e)}


# ============================================================
# Recording (Kanal / 1:1)
# ============================================================
def start_recording(channel):
    """MixMonitor — Aufnahme des Kanals starten. Pfad wie Softphone."""
    try:
        now = datetime.now()
        safe = re.sub(r'[^A-Za-z0-9_-]', '_', channel)
        path = (f'/var/spool/asterisk/monitor/{now:%Y}/{now:%m}/{now:%d}/'
                f'abpe-{safe}-{int(now.timestamp())}.wav')
        with AMIClient() as ami:
            ami._send(f'Action: MixMonitor\r\nChannel: {channel}\r\nFile: {path}\r\n\r\n')
            raw = ami._recv(0.6)
        return {'success': _ok(raw), 'file': path}
    except Exception as e:
        logger.error(f'AMI start_recording Fehler: {e}')
        return {'success': False, 'error': str(e)}


def stop_recording(channel):
    """StopMixMonitor — Aufnahme stoppen."""
    try:
        with AMIClient() as ami:
            ami._send(f'Action: StopMixMonitor\r\nChannel: {channel}\r\n\r\n')
            raw = ami._recv(0.5)
        return {'success': _ok(raw)}
    except Exception as e:
        logger.error(f'AMI stop_recording Fehler: {e}')
        return {'success': False, 'error': str(e)}


# ============================================================
# ConfBridge-Cockpit (Steuern)
# ============================================================
def _confbridge_action(action, room, channel=None):
    try:
        with AMIClient() as ami:
            msg = f'Action: {action}\r\nConference: {room}\r\n'
            if channel:
                msg += f'Channel: {channel}\r\n'
            ami._send(msg + '\r\n')
            raw = ami._recv(0.5)
        return {'success': _ok(raw), 'raw': raw[:120]}
    except Exception as e:
        logger.error(f'AMI {action} Fehler: {e}')
        return {'success': False, 'error': str(e)}


def conf_mute(room, channel):
    return _confbridge_action('ConfbridgeMute', room, channel)


def conf_unmute(room, channel):
    return _confbridge_action('ConfbridgeUnmute', room, channel)


def conf_kick(room, channel):
    return _confbridge_action('ConfbridgeKick', room, channel)


def conf_lock(room):
    return _confbridge_action('ConfbridgeLock', room)


def conf_unlock(room):
    return _confbridge_action('ConfbridgeUnlock', room)


def get_confbridge_detail(room):
    """ConfbridgeList — Teilnehmer-Detail eines Raums:
    talking/muted/admin/duration/markeduser/waitmarked."""
    members = []
    try:
        with AMIClient() as ami:
            ami._send(f'Action: ConfbridgeList\r\nConference: {room}\r\n\r\n')
            raw = ami._recv(1.0)
        for block in _blocks(raw):
            if 'Event: ConfbridgeList' not in block:
                continue
            ch = _field(block, 'Channel')
            if not ch:
                continue
            members.append({
                'channel':    ch,
                'callerid':   _field(block, 'CallerIDNum'),
                'name':       _field(block, 'CallerIDName'),
                'muted':      _field(block, 'Muted') == 'Yes',
                'talking':    _field(block, 'Talking') == 'Yes',
                'admin':      _field(block, 'Admin') == 'Yes',
                'markeduser': _field(block, 'MarkedUser') == 'Yes',
                'waitmarked': _field(block, 'WaitMarked') == 'Yes',
                'duration':   _field(block, 'Duration'),
            })
    except Exception as e:
        logger.error(f'AMI get_confbridge_detail Fehler: {e}')
    return members


# ============================================================
# DND / FWD (lesen + schreiben)
# ============================================================
def set_dnd(extension, enabled):
    """DND setzen/loeschen via AstDB (Family DND)."""
    try:
        with AMIClient() as ami:
            if enabled:
                ami._send(f'Action: DBPut\r\nFamily: DND\r\nKey: {extension}\r\nVal: YES\r\n\r\n')
            else:
                ami._send(f'Action: DBDel\r\nFamily: DND\r\nKey: {extension}\r\n\r\n')
            raw = ami._recv(0.4)
        return {'success': _ok(raw)}
    except Exception as e:
        logger.error(f'AMI set_dnd Fehler: {e}')
        return {'success': False, 'error': str(e)}


def get_fwd(extension):
    """Rufumleitungs-Ziel lesen (AstDB Family CF). '' = keine Umleitung."""
    try:
        with AMIClient() as ami:
            ami._send(f'Action: DBGet\r\nFamily: CF\r\nKey: {extension}\r\n\r\n')
            raw = ami._recv(0.4)
        if 'Response: Success' not in raw:
            return ''
        m = re.search(r'^Val:\s*(.+)$', raw, re.MULTILINE)
        return m.group(1).strip() if m else ''
    except Exception as e:
        logger.error(f'AMI get_fwd Fehler: {e}')
        return ''


def set_fwd(extension, target):
    """Rufumleitung setzen/aufheben. Setzt CF + CustomDevstate (BLF),
    exakt wie das Softphone (dialparties.agi liest CF/<ext>)."""
    try:
        with AMIClient() as ami:
            if target:
                ami._send(f'Action: DBPut\r\nFamily: CF\r\nKey: {extension}\r\nVal: {target}\r\n\r\n')
                ami._recv(0.2)
                ami._send(f'Action: DBPut\r\nFamily: CustomDevstate\r\nKey: CF{extension}\r\nVal: BUSY\r\n\r\n')
                ami._recv(0.2)
                ami._send(f'Action: DBPut\r\nFamily: CustomDevstate\r\nKey: DEVCF{extension}\r\nVal: BUSY\r\n\r\n')
                raw = ami._recv(0.3)
            else:
                ami._send(f'Action: DBDel\r\nFamily: CF\r\nKey: {extension}\r\n\r\n')
                ami._recv(0.2)
                ami._send(f'Action: DBPut\r\nFamily: CustomDevstate\r\nKey: CF{extension}\r\nVal: NOT_INUSE\r\n\r\n')
                ami._recv(0.2)
                ami._send(f'Action: DBPut\r\nFamily: CustomDevstate\r\nKey: DEVCF{extension}\r\nVal: NOT_INUSE\r\n\r\n')
                raw = ami._recv(0.3)
        return {'success': _ok(raw), 'target': target or ''}
    except Exception as e:
        logger.error(f'AMI set_fwd Fehler: {e}')
        return {'success': False, 'error': str(e)}


# ============================================================
# Warteschlangen
# ============================================================
def get_queues():
    """QueueStatus — pro Queue: wartende Anrufer + Members."""
    queues = {}
    try:
        with AMIClient() as ami:
            ami._send('Action: QueueStatus\r\n\r\n')
            raw = ami._recv(1.2)
        for block in _blocks(raw):
            if 'Event: QueueParams' in block:
                q = _field(block, 'Queue')
                if q:
                    queues.setdefault(q, {'name': q, 'calls': int(_field(block, 'Calls') or 0),
                                          'members': [], 'callers': []})
            elif 'Event: QueueMember' in block:
                q = _field(block, 'Queue')
                if q in queues:
                    queues[q]['members'].append({
                        'name':   _field(block, 'Name'),
                        'ext':    _field(block, 'Location'),
                        'status': _field(block, 'Status'),
                        'paused': _field(block, 'Paused') == '1',
                    })
            elif 'Event: QueueEntry' in block:
                q = _field(block, 'Queue')
                if q in queues:
                    queues[q]['callers'].append({
                        'position': _field(block, 'Position'),
                        'callerid': _field(block, 'CallerIDNum'),
                        'callername': _field(block, 'CallerIDName'),
                        'channel':  _field(block, 'Channel'),
                        'wait':     _field(block, 'Wait'),
                    })
    except Exception as e:
        logger.error(f'AMI get_queues Fehler: {e}')
    return list(queues.values())


def queue_pause(queue, extension, paused=True):
    try:
        with AMIClient() as ami:
            ami._send(
                f'Action: QueuePause\r\nQueue: {queue}\r\n'
                f'Interface: PJSIP/{extension}\r\nPaused: {"true" if paused else "false"}\r\n\r\n'
            )
            raw = ami._recv(0.5)
        return {'success': _ok(raw)}
    except Exception as e:
        logger.error(f'AMI queue_pause Fehler: {e}')
        return {'success': False, 'error': str(e)}


def queue_add(queue, extension):
    try:
        with AMIClient() as ami:
            ami._send(
                f'Action: QueueAdd\r\nQueue: {queue}\r\n'
                f'Interface: PJSIP/{extension}\r\nMemberName: {extension}\r\nPaused: false\r\n\r\n'
            )
            raw = ami._recv(0.5)
        return {'success': _ok(raw)}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def queue_remove(queue, extension):
    try:
        with AMIClient() as ami:
            ami._send(f'Action: QueueRemove\r\nQueue: {queue}\r\nInterface: PJSIP/{extension}\r\n\r\n')
            raw = ami._recv(0.5)
        return {'success': _ok(raw)}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ============================================================
# Voicemail-Detail
# ============================================================
def get_voicemail_boxes():
    """VoicemailUsersList — Box-Detail: Email, max, attach, new/old."""
    boxes = []
    try:
        with AMIClient() as ami:
            ami._send('Action: VoicemailUsersList\r\n\r\n')
            raw = ami._recv(1.2)
        for block in _blocks(raw):
            if 'Event: VoicemailUserEntry' not in block:
                continue
            box = _field(block, 'VoiceMailbox')
            if not box:
                continue
            boxes.append({
                'context':   _field(block, 'VMContext') or 'default',
                'box':       box,
                'user':      _field(block, 'Fullname'),
                'email':     _field(block, 'Email'),
                'new':       int(_field(block, 'NewMessageCount') or 0),
                'old':       int(_field(block, 'OldMessageCount') or 0),
                'max':       int(_field(block, 'MaxMessageCount') or 100),
                'attach':    _field(block, 'AttachMessage') == 'Yes',
            })
    except Exception as e:
        logger.error(f'AMI get_voicemail_boxes Fehler: {e}')
    return boxes


# ============================================================
# Erweiterte Reads
# ============================================================
def get_channels_bridged():
    """CoreShowChannels + Bridge-Partner-Ermittlung (BridgeId-Matching).
    Liefert pro Nebenstellen-Kanal den Gespraechspartner-Kanal
    (bridge_channel) — noetig fuer 'Zu mir holen', Park, Kunde-Koenig."""
    all_ch = []
    try:
        with AMIClient() as ami:
            ami._send('Action: CoreShowChannels\r\n\r\n')
            raw = ami._recv(1.0)
        for block in _blocks(raw):
            if 'Event: CoreShowChannel' not in block:
                continue
            ch = _field(block, 'Channel')
            if not ch:
                continue
            all_ch.append({
                'channel':      ch,
                'extension':    _ext_from_channel(ch),
                'state':        _field(block, 'ChannelStateDesc'),
                'callerid':     _field(block, 'CallerIDNum'),
                'calleridname': _field(block, 'CallerIDName'),
                'connectednum': _field(block, 'ConnectedLineNum'),
                'connectedname':_field(block, 'ConnectedLineName'),
                'duration':     _field(block, 'Duration'),
                'bridgeid':     _field(block, 'BridgeId'),
                'app':          _field(block, 'Application'),
            })
    except Exception as e:
        logger.error(f'AMI get_channels_bridged Fehler: {e}')
    # Bridge-Partner verknuepfen
    numeric = [c for c in all_ch if c['extension'].isdigit()]
    for c in numeric:
        if c['bridgeid']:
            partner = next((x for x in all_ch
                            if x['bridgeid'] == c['bridgeid'] and x['channel'] != c['channel']), None)
            if partner:
                c['bridge_channel'] = partner['channel']
    return numeric


def get_extensions(ext_names=None):
    """Nebenstellen-Grid: pjsip + sip + iax2 gemerged, Status + proto.
    ext_names: optionales dict {ext: 'Anzeigename'}."""
    ext_names = ext_names or {}
    exts, seen = [], set()

    def _pjsip_status(state):
        s = (state or '').lower()
        if 'not in use' in s:  return 'free'
        if 'in use' in s:      return 'busy'
        if 'ringing' in s:     return 'ringing'
        if 'on hold' in s:     return 'busy'
        return 'away'

    try:
        with AMIClient() as ami:
            # PJSIP
            raw = ami.command('pjsip show endpoints', wait=1.0)
            for line in raw.splitlines():
                if not line.startswith('Output:'):
                    continue
                m = re.search(r'Endpoint:\s+(\d+)(?:/\d+)?\s+(Not in use|In use|Unavailable|Ringing|On Hold)',
                              line[7:], re.I)
                if not m or m.group(1) in seen:
                    continue
                seen.add(m.group(1))
                exts.append({'ext': m.group(1), 'name': ext_names.get(m.group(1), 'WebRTC ' + m.group(1)),
                             'status': _pjsip_status(m.group(2)), 'state': m.group(2).strip(), 'proto': 'pjsip'})
            # SIP
            raw = ami.command('sip show peers', wait=1.0)
            for line in raw.splitlines():
                if not line.startswith('Output:'):
                    continue
                m = re.search(r'^(\w[\w.-]*)(?:/\S+)?\s+.*?\s+(OK|UNREACHABLE|UNKNOWN|LAGGED)', line[7:].strip(), re.I)
                if not m:
                    continue
                ext = m.group(1)
                if not re.match(r'^\d{1,6}$', ext) or ext in seen:
                    continue
                seen.add(ext)
                st = m.group(2).lower()
                exts.append({'ext': ext, 'name': ext_names.get(ext, 'SIP ' + ext),
                             'status': 'free' if st == 'ok' else 'busy' if st == 'lagged' else 'away',
                             'state': m.group(2), 'proto': 'sip'})
            # IAX2 (Fax etc.)
            raw = ami.command('iax2 show peers', wait=0.8)
            for line in raw.splitlines():
                if not line.startswith('Output:'):
                    continue
                m = re.search(r'^(\w[\w.-]+)\s+\S+\s+.*?\s+(OK|UNREACHABLE|UNKNOWN)', line[7:].strip(), re.I)
                if not m or m.group(1) in seen:
                    continue
                seen.add(m.group(1))
                exts.append({'ext': m.group(1), 'name': ext_names.get(m.group(1), 'IAX ' + m.group(1)),
                             'status': 'free' if m.group(2).lower() == 'ok' else 'away',
                             'state': m.group(2), 'proto': 'iax2'})
    except Exception as e:
        logger.error(f'AMI get_extensions Fehler: {e}')

    def _k(e):
        try:
            return (0, int(e['ext']))
        except ValueError:
            return (1, e['ext'])
    return sorted(exts, key=_k)


def park(channel, timeout_channel=None):
    """AMI Park - nativer Weg (nicht Redirect auf parkedcalls!).
    channel: der zu parkende Kanal (Bridge-Partner).
    timeout_channel: wohin bei Park-Timeout geklingelt wird (default: channel selbst).
    Portiert 1:1 aus dem verifizierten Electron-Softphone (ami-service.js
    parkChannel()) - Redirect auf 'parkedcalls,700' kappt bei internen
    Gespraechen die Gegenseite, weil sie keine Ziel-Anweisung bekommt."""
    timeout_channel = timeout_channel or channel
    try:
        with AMIClient() as ami:
            ami._send(
                f'Action: Park\r\nChannel: {channel}\r\n'
                f'TimeoutChannel: {timeout_channel}\r\n\r\n'
            )
            raw = ami._recv(0.5)
        return {'success': _ok(raw), 'raw': raw[:150]}
    except Exception as e:
        logger.error(f'AMI park Fehler: {e}')
        return {'success': False, 'error': str(e)}


def park_partner(extension):
    """'Halten' (Parken): aktiven Gespraechspartner einer Nebenstelle parken.
    Bridge-Partner wird geparkt (nicht die eigene Seite!), eigene Extension
    ist TimeoutChannel (klingelt bei dir, falls niemand den Slot abholt).
    Findet den Bridge-Partner ueber get_channels_bridged()."""
    chans = get_channels_bridged()
    mine = next((c for c in chans if c['extension'] == str(extension)), None)
    if not mine:
        return {'success': False, 'error': 'Keine aktive Nebenstelle ' + str(extension)}
    partner = mine.get('bridge_channel')
    if not partner:
        return {'success': False, 'error': 'Kein aktiver Gespraechspartner gefunden'}
    own_channel = mine.get('channel')
    return park(partner, timeout_channel=own_channel or partner)



# ============================================================
# Kunde-Koenig-Primitive
# ============================================================
def redirect_partner_to_conference(extension, room='5555', context='from-internal-custom'):
    """'In Konferenz legen': aktiven Gespraechspartner einer Nebenstelle in
    den Konferenzraum umleiten; die eigene Seite wird beim Redirect frei.
    Findet den Bridge-Partner ueber get_channels_bridged()."""
    chans = get_channels_bridged()
    mine = next((c for c in chans if c['extension'] == str(extension)), None)
    partner = mine.get('bridge_channel') if mine else None
    if not partner:
        return {'success': False, 'error': 'Kein aktiver Gespraechspartner gefunden'}
    return redirect(partner, room, context)


# ============================================================
# Offline (Presence-Ersatz: DND-Route + eigenes Anzeige-Flag) / Steal / Barge
# ============================================================
def set_offline(extension, offline):
    """Offline = DND-Route (-> Unavail-VM) + Anzeige-Flag AbpeOffline.
    Getrennt von der DND-Taste sichtbar, nutzt aber die native VM-Route."""
    try:
        with AMIClient() as ami:
            if offline:
                ami._send(f'Action: DBPut\r\nFamily: DND\r\nKey: {extension}\r\nVal: YES\r\n\r\n'); ami._recv(0.3)
                ami._send(f'Action: DBPut\r\nFamily: AbpeOffline\r\nKey: {extension}\r\nVal: 1\r\n\r\n'); raw = ami._recv(0.3)
            else:
                ami._send(f'Action: DBDel\r\nFamily: DND\r\nKey: {extension}\r\n\r\n'); ami._recv(0.3)
                ami._send(f'Action: DBDel\r\nFamily: AbpeOffline\r\nKey: {extension}\r\n\r\n'); raw = ami._recv(0.3)
        return {'success': _ok(raw), 'offline': offline}
    except Exception as e:
        logger.error(f'AMI set_offline Fehler: {e}')
        return {'success': False, 'error': str(e)}


def steal_call(extension, to='12'):
    """Call-Steal: Gespraechspartner einer aktiven Nst auf 'to' (Tischtelefon) ziehen."""
    chans = get_channels_bridged()
    mine = next((c for c in chans if c['extension'] == str(extension)), None)
    partner = mine.get('bridge_channel') if mine else None
    if not partner:
        return {'success': False, 'error': 'Kein aktives Gespraech auf ' + str(extension)}
    return redirect(partner, str(to), 'from-internal')


def barge_call(desk, channel, mode='B'):
    """Barge/Whisper via Originate in ChanSpy (umgeht den festen chanspy-Dialplan).
    mode: 'B'=barge (beide hoeren), 'w'=whisper (nur Nst), ''=listen."""
    opt = 'q' + (mode or '')
    try:
        with AMIClient() as ami:
            ami._send(
                f'Action: Originate\r\nChannel: Local/{desk}@from-internal\r\n'
                f'Application: ChanSpy\r\nData: {channel},{opt}\r\n'
                f'CallerID: "Barge {mode}" <{desk}>\r\nTimeout: 30000\r\nAsync: true\r\n\r\n'
            )
            raw = ami._recv(1.0)
        return {'success': _ok(raw), 'mode': mode}
    except Exception as e:
        logger.error(f'AMI barge_call Fehler: {e}')
        return {'success': False, 'error': str(e)}


# ============================================================
# Aggregierter HUD-Poll — EINE Verbindung, ein Durchlauf
# ============================================================
def _pjsip_state(state):
    st = (state or '').lower()
    if 'not in use' in st: return 'free'
    if 'in use' in st:     return 'busy'
    if 'ringing' in st:    return 'ringing'
    if 'on hold' in st:    return 'busy'
    return 'away'


def get_hud_status(ext_names=None, vm_boxes=None):
    """Kompletter HUD-Status in EINEM AMI-Connect (Extensions + Kanaele mit
    Bridge-Partner + Parken + ConfBridge-Detail + Queues + Voicemail)."""
    ext_names = ext_names or {}
    res = {'extensions': [], 'channels': [], 'parked': [],
           'confbridge': [], 'queues': [], 'voicemail': []}
    try:
        with AMIClient() as ami:
            # --- Extensions: pjsip + sip + iax2 ---
            seen, exts = set(), []
            raw = ami.command('pjsip show endpoints', wait=1.0)
            for line in raw.splitlines():
                if not line.startswith('Output:'):
                    continue
                m = re.search(r'Endpoint:\s+(\d+)(?:/\d+)?\s+(Not in use|In use|Unavailable|Ringing|On Hold)', line[7:], re.I)
                if not m or m.group(1) in seen:
                    continue
                seen.add(m.group(1))
                exts.append({'ext': m.group(1), 'name': ext_names.get(m.group(1), 'WebRTC ' + m.group(1)),
                             'status': _pjsip_state(m.group(2)), 'state': m.group(2).strip(), 'proto': 'pjsip'})
            raw = ami.command('sip show peers', wait=1.0)
            for line in raw.splitlines():
                if not line.startswith('Output:'):
                    continue
                m = re.search(r'^(\w[\w.-]*)(?:/\S+)?\s+.*?\s+(OK|UNREACHABLE|UNKNOWN|LAGGED)', line[7:].strip(), re.I)
                if not m:
                    continue
                ext = m.group(1)
                if not re.match(r'^\d{1,6}$', ext) or ext in seen:
                    continue
                seen.add(ext); st = m.group(2).lower()
                exts.append({'ext': ext, 'name': ext_names.get(ext, 'SIP ' + ext),
                             'status': 'free' if st == 'ok' else 'busy' if st == 'lagged' else 'away',
                             'state': m.group(2), 'proto': 'sip'})
            raw = ami.command('iax2 show peers', wait=0.8)
            for line in raw.splitlines():
                if not line.startswith('Output:'):
                    continue
                m = re.search(r'^(\w[\w.-]+)\s+\S+\s+.*?\s+(OK|UNREACHABLE|UNKNOWN)', line[7:].strip(), re.I)
                if not m or m.group(1) in seen:
                    continue
                seen.add(m.group(1))
                exts.append({'ext': m.group(1), 'name': ext_names.get(m.group(1), 'IAX ' + m.group(1)),
                             'status': 'free' if m.group(2).lower() == 'ok' else 'away',
                             'state': m.group(2), 'proto': 'iax2'})
            def _k(e):
                try:
                    return (0, int(e['ext']))
                except ValueError:
                    return (1, e['ext'])
            res['extensions'] = sorted(exts, key=_k)

            # --- DND + Rufumleitung (AstDB, je ein Command fuer alle) ---
            dnd_set, cf_map, off_set = set(), {}, set()
            try:
                raw = ami.command('database show DND', wait=0.6)
                for line in raw.splitlines():
                    m = re.search(r'/DND/(\w+)\s*:\s*(\S+)', line)
                    if m and m.group(2).upper() in ('YES', '1', 'ON'):
                        dnd_set.add(m.group(1))
                raw = ami.command('database show CF', wait=0.6)
                for line in raw.splitlines():
                    m = re.search(r'/CF/(\w+)\s*:\s*(\S+)', line)
                    if m and m.group(2):
                        cf_map[m.group(1)] = m.group(2)
                raw = ami.command('database show AbpeOffline', wait=0.5)
                off_set = set(mm.group(1) for mm in re.finditer(r'/AbpeOffline/(\w+)\s*:', raw))
            except Exception:
                pass
            for _e in res['extensions']:
                _e['dnd'] = _e['ext'] in dnd_set
                _e['fwd'] = cf_map.get(_e['ext'], '')
                _e['offline'] = _e['ext'] in off_set

            # --- Kanaele + Bridge-Partner ---
            ami._send('Action: CoreShowChannels\r\n\r\n')
            raw = ami._recv(0.8)
            allch = []
            for b in _blocks(raw):
                if 'Event: CoreShowChannel' not in b:
                    continue
                ch = _field(b, 'Channel')
                if not ch:
                    continue
                allch.append({'channel': ch, 'extension': _ext_from_channel(ch),
                              'state': _field(b, 'ChannelStateDesc'),
                              'callerid': _field(b, 'CallerIDNum'), 'calleridname': _field(b, 'CallerIDName'),
                              'connectednum': _field(b, 'ConnectedLineNum'), 'connectedname': _field(b, 'ConnectedLineName'),
                              'duration': _field(b, 'Duration'), 'bridgeid': _field(b, 'BridgeId'),
                              'app': _field(b, 'Application')})
            numeric = [c for c in allch if c['extension'].isdigit()]
            for c in numeric:
                if c['bridgeid']:
                    p = next((x for x in allch if x['bridgeid'] == c['bridgeid'] and x['channel'] != c['channel']), None)
                    if p:
                        c['bridge_channel'] = p['channel']
            res['channels'] = numeric

            # --- Parken (Parkee*-Feldnamen dieser PBX) ---
            # Slot-Range aus PBX-Konfiguration ermitteln (z.B. "Parking Spaces : 701-709")
            park_min, park_max = 701, 709
            try:
                praw = ami.command('parking show', wait=0.6)
                pm = re.search(r'Parking Spaces\s*:\s*(\d+)-(\d+)', praw)
                if pm:
                    park_min, park_max = int(pm.group(1)), int(pm.group(2))
            except Exception:
                pass

            ami._send('Action: ParkedCalls\r\n\r\n')
            raw = ami._recv(0.6)
            occupied = {}
            for b in _blocks(raw):
                if 'Event: ParkedCall' not in b or 'Complete' in b:
                    continue
                slot = _field(b, 'ParkingSpace') or _field(b, 'Exten')
                if not slot:
                    continue
                occupied[slot] = {
                    'slot': slot,
                    'occupied': True,
                    'channel': _field(b, 'ParkeeChannel') or _field(b, 'Channel'),
                    'caller_id': _field(b, 'ParkeeCallerIDNum') or _field(b, 'CallerIDNum'),
                    'caller_name': _field(b, 'ParkeeCallerIDName') or _field(b, 'CallerIDName'),
                    'duration': _field(b, 'ParkingDuration') or _field(b, 'Duration'),
                    'timeout': _field(b, 'ParkingTimeout'),
                }

            # Komplette Range zurueckgeben - frei oder besetzt
            for s in range(park_min, park_max + 1):
                slot = str(s)
                if slot in occupied:
                    res['parked'].append(occupied[slot])
                else:
                    res['parked'].append({
                        'slot': slot, 'occupied': False, 'channel': '',
                        'caller_id': '', 'caller_name': '', 'duration': '', 'timeout': '',
                    })

            # --- ConfBridge Raeume + Teilnehmer-Detail ---
            ami._send('Action: ConfbridgeListRooms\r\n\r\n')
            raw = ami._recv(0.6)
            rooms = []
            for b in _blocks(raw):
                if 'Event: ConfbridgeListRooms' not in b:
                    continue
                conf = _field(b, 'Conference')
                if conf:
                    rooms.append({'conference': conf, 'parties': int(_field(b, 'Parties') or 0),
                                  'marked': int(_field(b, 'Marked') or 0), 'locked': _field(b, 'Locked') == 'Yes',
                                  'members': []})
            for r in rooms:
                ami._send(f"Action: ConfbridgeList\r\nConference: {r['conference']}\r\n\r\n")
                rawd = ami._recv(0.6)
                for b in _blocks(rawd):
                    if 'Event: ConfbridgeList' not in b:
                        continue
                    ch = _field(b, 'Channel')
                    if not ch:
                        continue
                    r['members'].append({'channel': ch, 'callerid': _field(b, 'CallerIDNum'),
                                         'name': _field(b, 'CallerIDName'), 'muted': _field(b, 'Muted') == 'Yes',
                                         'talking': _field(b, 'Talking') == 'Yes', 'admin': _field(b, 'Admin') == 'Yes',
                                         'markeduser': _field(b, 'MarkedUser') == 'Yes',
                                         'waitmarked': _field(b, 'WaitMarked') == 'Yes',
                                         'duration': _field(b, 'Duration')})
            res['confbridge'] = rooms

            # --- Queues ---
            ami._send('Action: QueueStatus\r\n\r\n')
            raw = ami._recv(1.0)
            qs = {}
            for b in _blocks(raw):
                if 'Event: QueueParams' in b:
                    q = _field(b, 'Queue')
                    if q:
                        qs.setdefault(q, {'name': q, 'calls': int(_field(b, 'Calls') or 0),
                                          'members': [], 'callers': []})
                elif 'Event: QueueMember' in b:
                    q = _field(b, 'Queue')
                    if q in qs:
                        qs[q]['members'].append({'name': _field(b, 'Name'), 'ext': _field(b, 'Location'),
                                                 'status': _field(b, 'Status'), 'paused': _field(b, 'Paused') == '1'})
                elif 'Event: QueueEntry' in b:
                    q = _field(b, 'Queue')
                    if q in qs:
                        qs[q]['callers'].append({'position': _field(b, 'Position'),
                                                 'callerid': _field(b, 'CallerIDNum'),
                                                 'callername': _field(b, 'CallerIDName'),
                                                 'channel': _field(b, 'Channel'),
                                                 'wait': _field(b, 'Wait')})
            res['queues'] = list(qs.values())

            # --- Voicemail (optional) ---
            if vm_boxes:
                want = set(str(x) for x in vm_boxes)
                ami._send('Action: VoicemailUsersList\r\n\r\n')
                raw = ami._recv(1.0)
                for b in _blocks(raw):
                    if 'Event: VoicemailUserEntry' not in b:
                        continue
                    box = _field(b, 'VoiceMailbox')
                    if not box or box not in want:
                        continue
                    res['voicemail'].append({'context': _field(b, 'VMContext') or 'default', 'box': box,
                                             'user': _field(b, 'Fullname'), 'email': _field(b, 'Email'),
                                             'new': int(_field(b, 'NewMessageCount') or 0),
                                             'old': int(_field(b, 'OldMessageCount') or 0),
                                             'max': int(_field(b, 'MaxMessageCount') or 100),
                                             'attach': _field(b, 'AttachMessage') == 'Yes'})
    except Exception as e:
        logger.error(f'AMI get_hud_status Fehler: {e}')
        res['error'] = str(e)
    return res


# ============================================================
# Konferenzraeume (Hints + Config-Reader kombiniert, fuer abpe_meetme)
# ============================================================
def get_conference_rooms():
    """Kombiniert zwei Quellen fuer die vollstaendige, korrekte Liste
    aller konfigurierten Konferenzraeume:

    1. Dialplan-Hints ('core show hints') — liefert fuer Issabel-GUI-
       generierte Raeume (034/035) zusaetzlich den Hint-State (Idle/
       Unavailable/...).
    2. pbx_config_reader.get_conference_rooms_from_config() — liest LIVE
       die Dialplan-Configs von der PBX und erfasst zusaetzlich hint-lose,
       handgeschriebene Raeume (z. B. 5555), die Hints niemals zeigen.

    Raeume aus (1) behalten ihren Hint-State. Raeume, die NUR in (2)
    auftauchen, bekommen hint_state='unknown' (kein Hint vorhanden).
    Anschliessend wird bei allen Raeumen die aktuelle Teilnehmerzahl
    per ConfbridgeListRooms ergaenzt.

    Keine lokale Kopie/Schatten-Tabelle — beide Quellen werden bei
    jedem Aufruf frisch gelesen."""
    from .pbx_config_reader import get_conference_rooms_from_config

    rooms_by_ext = {}

    # --- Quelle 1: Dialplan-Hints (liefert hint_state) ---
    try:
        with AMIClient() as ami:
            raw = ami.command('core show hints', wait=1.0)

        for line in raw.splitlines():
            if not line.startswith('Output:'):
                continue
            text = line[7:].strip()
            m = re.match(r'^(\d+)@ext-meetme\s*:\s*confbridge:(\d+)\s+State:(\S+)', text)
            if not m:
                continue
            room = m.group(2)
            rooms_by_ext[room] = {
                'room_extension': room,
                'hint_state': m.group(3),
                'source': 'hint',
                'parties': 0,
                'locked': False,
            }
    except Exception as e:
        logger.error(f'AMI get_conference_rooms (Hints) Fehler: {e}')

    # --- Quelle 2: Live-Config-Reader (erfasst zusaetzlich hint-lose Raeume) ---
    try:
        config_rooms = get_conference_rooms_from_config()
        for cr in config_rooms:
            room = cr['room_extension']
            if room not in rooms_by_ext:
                rooms_by_ext[room] = {
                    'room_extension': room,
                    'hint_state': 'unknown',
                    'source': 'config',
                    'parties': 0,
                    'locked': False,
                }
    except Exception as e:
        logger.error(f'get_conference_rooms (Config-Reader) Fehler: {e}')

    rooms = list(rooms_by_ext.values())
    if not rooms:
        return []

    # --- Live-Teilnehmerzahl fuer beide Quellen gemeinsam ergaenzen ---
    try:
        with AMIClient() as ami:
            ami._send('Action: ConfbridgeListRooms\r\n\r\n')
            raw = ami._recv(0.6)
        live = {}
        for block in _blocks(raw):
            if 'Event: ConfbridgeListRooms' not in block:
                continue
            conf = _field(block, 'Conference')
            if conf:
                live[conf] = {
                    'parties': int(_field(block, 'Parties') or 0),
                    'locked': _field(block, 'Locked') == 'Yes',
                }
        for r in rooms:
            if r['room_extension'] in live:
                r['parties'] = live[r['room_extension']]['parties']
                r['locked'] = live[r['room_extension']]['locked']
    except Exception as e:
        logger.error(f'AMI get_conference_rooms (Live-Teilnehmer) Fehler: {e}')

    def _k(r):
        try:
            return (0, int(r['room_extension']))
        except ValueError:
            return (1, r['room_extension'])
    return sorted(rooms, key=_k)
