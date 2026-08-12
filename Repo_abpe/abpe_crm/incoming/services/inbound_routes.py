"""
inbound_routes.py — ermittelt interne Nebenstellen fuer Telefonnummern der
Firma abcona (Zentrale + Ansprechpartner), direkt aus der PBX-Konfiguration
(extensions_additional.conf + ringgroups-Tabelle). Kein Datenbank-Zugriff
per Remote-MySQL moeglich (nur localhost erlaubt) - daher per SSH-Kommando
auf der PBX selbst ausgefuehrt, analog recording_sync.py.

Matching-Algorithmus (bewaehrt, siehe Session-Historie):
1. Exakter Treffer als Mobil-Weiterleitung: 'exten => <EXT>,hint,SIP/EasySIP8867-out/<NUMMER>,'
2. Sonst: DID-Suffix-Suche in extensions_additional.conf (9,8,7,6,5,4 Ziffern,
   absteigend, bis genau 1 eindeutiger Treffer) -> liefert Goto(context,ziel,prio)
   - Bei 'from-did-direct': Ziel ist direkt die Nebenstelle
   - Bei 'ext-group': Ring-Group-Mitgliederliste (ringgroups.grplist) auflösen,
     dann die Nummer gegen jedes Mitglied per Suffix-Abgleich pruefen
"""
import re
import time as _time
import logging

logger = logging.getLogger(__name__)

_CACHE_TTL = 300  # Sekunden
_conf_cache = {'lines': None, 'ts': 0}
_ringgroups_cache = {'data': None, 'ts': 0}

ABCONA_ACCOUNT_CRM_ID = '51691c10-97fd-2e65-75ef-4b1eb782b729'


def _ssh_exec(command, timeout=15):
    import paramiko
    from abpe_backend.settings import pbx
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(pbx.PBX_HOST, username=pbx.PBX_ROOT_USER,
                    password=pbx.PBX_ROOT_PASSWORD, timeout=timeout)
    try:
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        out = stdout.read().decode('utf-8', errors='replace')
        err = stderr.read().decode('utf-8', errors='replace')
        return out, err
    finally:
        client.close()


def _normalize_digits(value):
    return re.sub(r'\D', '', value or '')


def _get_conf_lines(force_refresh=False):
    now = _time.time()
    if not force_refresh and _conf_cache['lines'] is not None and (now - _conf_cache['ts']) < _CACHE_TTL:
        return _conf_cache['lines']

    out, err = _ssh_exec("cat /etc/asterisk/extensions_additional.conf")
    if err.strip():
        logger.warning(f'_get_conf_lines SSH stderr: {err[:300]}')
    lines = out.splitlines()
    _conf_cache['lines'] = lines
    _conf_cache['ts'] = now
    return lines


def fetch_ringgroups(force_refresh=False):
    """Liste von {'grpnum': str, 'extensions': [str,...]}."""
    now = _time.time()
    if not force_refresh and _ringgroups_cache['data'] is not None and (now - _ringgroups_cache['ts']) < _CACHE_TTL:
        return _ringgroups_cache['data']

    result = []
    try:
        cmd = "mysql -u asteriskuser -p'abcona' asterisk -N -e \"SELECT grpnum, grplist FROM ringgroups;\""
        out, err = _ssh_exec(cmd)
        if err.strip() and 'Warning' not in err:
            logger.warning(f'fetch_ringgroups SSH stderr: {err[:300]}')
        for line in out.splitlines():
            parts = line.split('\t')
            if len(parts) < 2:
                continue
            grpnum, grplist = parts[0], parts[1]
            extensions = [e.strip() for e in grplist.split('-') if e.strip()]
            if extensions:
                result.append({'grpnum': grpnum, 'extensions': extensions})
    except Exception as e:
        logger.error(f'fetch_ringgroups Fehler: {e}')
        return _ringgroups_cache['data'] or []

    _ringgroups_cache['data'] = result
    _ringgroups_cache['ts'] = now
    return result


def _match_mobile_hint(digits, conf_lines):
    pattern = re.compile(r'^exten => (\d+),hint,SIP/EasySIP8867-out/' + re.escape(digits) + r',')
    for line in conf_lines:
        m = pattern.match(line)
        if m:
            return m.group(1)
    return None


def _find_did_target(digits, conf_lines):
    for length in (9, 8, 7, 6, 5, 4):
        if len(digits) < length:
            continue
        suffix = digits[-length:]
        pattern = re.compile(r'^exten => ' + re.escape(suffix) + r',.*Goto\(([^)]+)\)')
        matches = []
        for line in conf_lines:
            m = pattern.match(line)
            if m:
                matches.append(m.group(1))
        if len(matches) == 1:
            return matches[0]
    return None


def lookup_extension_for_number(phone_number, force_refresh=False):
    """Gibt die interne Nebenstelle zurueck, falls die Telefonnummer (in
    beliebigem Format) einer bekannten PBX-Route entspricht, sonst None."""
    digits = _normalize_digits(phone_number)
    if not digits:
        return None

    conf_lines = _get_conf_lines(force_refresh=force_refresh)

    mobile_ext = _match_mobile_hint(digits, conf_lines)
    if mobile_ext:
        return mobile_ext

    target = _find_did_target(digits, conf_lines)
    if not target:
        return None

    parts = target.split(',')
    if len(parts) < 2:
        return None
    ctx, val = parts[0], parts[1]

    if ctx == 'from-did-direct':
        return val
    elif ctx == 'ext-group':
        for rg in fetch_ringgroups():
            if rg['grpnum'] == val:
                for cand in rg['extensions']:
                    if digits.endswith(cand):
                        return cand
    return None


def _resolve_all_extensions_for_person(phones):
    """phones: iterable von CrmPhoneBeanRel - liefert dict
    {extension: raw_number} aller gefundenen Nebenstellen
    (ueberspringt phone_fax). raw_number ist die lesbare Original-
    Telefonnummer aus dem CRM (mit Leerzeichen, wie eingetragen)."""
    extensions = {}
    for p in phones:
        if p.field_name == 'phone_fax':
            continue
        norm_num = p.phone.phone_norm or p.phone.phone_raw
        ext = lookup_extension_for_number(norm_num)
        if ext and ext not in extensions:
            extensions[ext] = p.phone.phone_raw
    return extensions


def get_zentrale_group():
    """Zentrale-Nebenstellen aus den Telefonnummern des Accounts abcona selbst."""
    from apps.abpe_crm.models import CrmAccount, CrmPhoneBeanRel

    try:
        abcona = CrmAccount.objects.get(crm_id=ABCONA_ACCOUNT_CRM_ID)
        phones = CrmPhoneBeanRel.objects.filter(bean_id=abcona.crm_id, bean_module='Accounts')
        ext_map = _resolve_all_extensions_for_person(phones)
    except Exception as e:
        logger.error(f'get_zentrale_group Fehler: {e}')
        ext_map = {}

    extensions = [{'ext': ext, 'phone': ext_map[ext]} for ext in sorted(ext_map)]
    return {'name': 'Zentrale', 'extensions': extensions}


def get_transfer_groups():
    """Personen-Gruppen (Name -> alle zugehoerigen Nebenstellen) aus den
    CRM-Ansprechpartnern der Firma abcona."""
    from apps.abpe_crm.models import CrmAccount, CrmAccountContacts, CrmPhoneBeanRel

    groups = []
    try:
        abcona = CrmAccount.objects.get(crm_id=ABCONA_ACCOUNT_CRM_ID)
        links = CrmAccountContacts.objects.filter(account=abcona).select_related('contact')

        for link in links:
            c = link.contact
            if not c:
                continue
            name = f'{c.first_name or ""} {c.last_name or ""}'.strip()
            if not name:
                continue

            phones = CrmPhoneBeanRel.objects.filter(bean_id=c.crm_id, bean_module='Contacts')
            ext_map = _resolve_all_extensions_for_person(phones)

            if ext_map:
                extensions = [{'ext': ext, 'phone': ext_map[ext]} for ext in sorted(ext_map)]
                groups.append({'name': name, 'extensions': extensions})
    except Exception as e:
        logger.error(f'get_transfer_groups Fehler: {e}')

    return groups
