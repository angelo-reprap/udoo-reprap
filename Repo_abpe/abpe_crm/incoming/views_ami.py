"""
apps/abpe_crm/views_ami.py

Telefon-/AMI-API fuer das CRM-Telefon-Modul (HUD, Konferenz-Cockpit,
Kunde-Koenig-Flow, Queues, Voicemail, Control, Protokoll/Notiz).

Muster wie abpe_edms/views.py: DRF (@api_view) + drf-spectacular
(@extend_schema) + login_or_token_required (Session ODER Token-Auth).
POST via csrf_exempt (Token-Auth / DRF uebernimmt CSRF).

Services:
  ami_client.py       — bestehende Reads + Originate/Park
  ami_control.py       — Control-Actions + Detail-Reads + HUD-Aggregat
  cdr_client.py        — Statistik
  deepseek_api_pbx.py  — Protokoll/Notiz-Formulierung
"""
import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from rest_framework.decorators import (
    api_view, authentication_classes, permission_classes,
)
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from apps.abpe_crm.views import login_or_token_required

logger = logging.getLogger(__name__)
TAGS = ["Telefon"]


# =============================================================================
#  Auth-Dekoratoren (identisch zu abpe_edms/views.py)
# =============================================================================
def _drf_get(view):
    view = login_or_token_required(view)
    view = permission_classes([IsAuthenticated])(view)
    view = authentication_classes([SessionAuthentication, TokenAuthentication])(view)
    view = api_view(["GET"])(view)
    return view


def _drf_post(view):
    view = csrf_exempt(view)
    view = login_or_token_required(view)
    view = permission_classes([IsAuthenticated])(view)
    view = authentication_classes([SessionAuthentication, TokenAuthentication])(view)
    view = api_view(["POST"])(view)
    return view


def _json_body(request):
    data = getattr(request, "data", None)
    if isinstance(data, dict):
        return data
    try:
        return json.loads(request.body or "{}")
    except Exception:
        return {}


def _p(name, typ, desc, **kw):
    return OpenApiParameter(name=name, type=typ, location=OpenApiParameter.QUERY,
                            description=desc, **kw)


def _ext_names():
    """{ext: Anzeigename} aus CrmUserSettings — fuer das HUD-Grid."""
    names = {}
    try:
        from apps.abpe_crm.models import CrmUserSettings
        for s in CrmUserSettings.objects.exclude(phone_extension=''):
            if s.phone_extension:
                names[str(s.phone_extension)] = s.phone_display_name or str(s.phone_extension)
    except Exception as e:
        logger.warning(f'_ext_names Fehler: {e}')
    return names


# =============================================================================
#  NEBENSTELLEN / STATUS
# =============================================================================
@extend_schema(summary="SIP-Peers (Nebenstellen-Dropdown)", tags=TAGS,
               responses={200: OpenApiTypes.OBJECT})
@_drf_get
def api_telefon_peers(request):
    from apps.abpe_crm.services.ami_client import get_sip_peers
    try:
        return JsonResponse({'peers': get_sip_peers()})
    except Exception as e:
        return JsonResponse({'peers': [], 'error': str(e)})


@extend_schema(summary="Alle Nebenstellen (HUD-Grid): pjsip+sip+iax2, Status+proto",
               tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_get
def api_telefon_extensions(request):
    from apps.abpe_crm.services.ami_control import get_extensions
    try:
        return JsonResponse({'extensions': get_extensions(_ext_names())})
    except Exception as e:
        return JsonResponse({'extensions': [], 'error': str(e)}, status=500)


@extend_schema(summary="Status einer Nebenstelle",
               parameters=[_p("extension", OpenApiTypes.STR, "Nebenstelle")],
               tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_get
def api_telefon_status(request):
    extension = request.GET.get('extension', '').strip()
    if not extension:
        return JsonResponse({'error': 'extension fehlt'}, status=400)
    from apps.abpe_crm.services.ami_client import get_extension_status
    try:
        return JsonResponse({'extension': extension, 'status': get_extension_status(extension)})
    except Exception as e:
        return JsonResponse({'extension': extension, 'status': 'unknown', 'error': str(e)})


@extend_schema(summary="CDR-Statistik einer Nebenstelle",
               parameters=[_p("extension", OpenApiTypes.STR, "Nebenstelle")],
               tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_get
def api_telefon_stats(request):
    extension = request.GET.get('extension', '').strip()
    if not extension:
        return JsonResponse({'error': 'extension fehlt'}, status=400)
    from apps.abpe_crm.services.cdr_client import get_stats_for_extension

    def _safe(d):
        return {k: (int(v) if v is not None else 0) for k, v in d.items()} if d else {}
    try:
        stats = get_stats_for_extension(extension)
        for k in ('heute', 'woche', 'monat'):
            stats[k] = _safe(stats.get(k))
        return JsonResponse({'stats': stats})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# =============================================================================
#  HUD SAMMEL-POLL
# =============================================================================
@extend_schema(
    summary="HUD-Sammelstatus (ein Poll)",
    description="Nebenstellen + aktive Kanaele (mit Bridge-Partner) + Parken + "
                "ConfBridge-Detail + Queues + Voicemail in einem Rutsch.",
    parameters=[
        _p("vm_boxes", OpenApiTypes.STR, "Komma-Liste VM-Boxen (optional)"),
    ], tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_get
def api_telefon_hud(request):
    from apps.abpe_crm.services.ami_control import get_hud_status
    vm_boxes = [b.strip() for b in request.GET.get('vm_boxes', '').split(',') if b.strip()]
    try:
        data = get_hud_status(_ext_names(), vm_boxes)
        return JsonResponse({'success': True, 'data': data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@extend_schema(summary="Uebergabe-Ziele: Zentrale, Personen, Nebenstellen (nur online)",
               tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_get
def api_telefon_transfer_targets(request):
    from apps.abpe_crm.services.ami_control import get_hud_status
    from apps.abpe_crm.services.inbound_routes import get_zentrale_group, get_transfer_groups

    try:
        hud = get_hud_status(_ext_names())
        live_exts = hud.get('extensions', [])

        online_map = {}
        for e in live_exts:
            status = e.get('status', 'free')
            if e.get('dnd'):
                status = 'dnd'
            if e.get('offline'):
                status = 'offline'
            online_map[e['ext']] = {
                'ext': e['ext'],
                'name': e.get('name', e['ext']),
                'status': status,
                'proto': e.get('proto', ''),
            }

        assigned = set()
        groups = []

        def _build_group_entries(group_extensions):
            entries = []
            for item in group_extensions:
                ext = item['ext']
                assigned.add(ext)
                live = online_map.get(ext)
                # offline oder Fax (iax2) raus; Weiterleitungen ohne eigenen
                # Peer (z.B. Mobil 2200) IMMER anzeigen
                if live and (live.get('status') == 'offline' or live.get('proto') == 'iax2'):
                    continue
                entries.append({
                    'ext': ext,
                    'name': live['name'] if live else ext,
                    'status': live['status'] if live else 'unbekannt',
                    'phone': item.get('phone', ''),
                })
            return entries

        zentrale = get_zentrale_group()
        zentrale_online = _build_group_entries(zentrale['extensions'])
        if zentrale_online:
            groups.append({'name': zentrale['name'], 'extensions': zentrale_online})

        for g in get_transfer_groups():
            g_online = _build_group_entries(g['extensions'])
            if g_online:
                groups.append({'name': g['name'], 'extensions': g_online})

        rest = []
        for ext, live in online_map.items():
            if ext in assigned:
                continue
            if live.get('proto') == 'iax2' or live.get('status') == 'offline':
                continue
            rest.append({'ext': ext, 'name': live['name'], 'status': live['status'], 'phone': ''})
        rest.sort(key=lambda x: (len(x['ext']), x['ext']))
        if rest:
            groups.append({'name': 'Nebenstellen', 'extensions': rest})

        return JsonResponse({'success': True, 'groups': groups})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# =============================================================================
#  WAEHLEN / CLICK-TO-DIAL
# =============================================================================
@extend_schema(summary="Click-to-Call (Nebenstelle klingelt, dann Ziel)",
               tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_post
def api_telefon_call(request):
    data = _json_body(request)
    extension = (data.get('extension') or '').strip()
    destination = (data.get('destination') or '').strip()
    if not extension or not destination:
        return JsonResponse({'error': 'extension und destination erforderlich'}, status=400)
    from apps.abpe_crm.services.ami_client import originate_call
    from apps.abpe_crm.services.normalize_phone_nr import normalize_phone
    try:
        dest = destination if destination.startswith('*') else (normalize_phone(destination) or destination)
        res = originate_call(extension, dest)
        return JsonResponse({'success': res.get('success', False),
                             'destination_norm': dest, 'extension': extension})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@extend_schema(summary="Click-to-Dial ueber Tischtelefon (Local/desk -> Ziel)",
               tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_post
def api_telefon_dial(request):
    data = _json_body(request)
    desk = (data.get('desk') or data.get('extension') or '').strip()
    target = (data.get('target') or data.get('destination') or '').strip()
    if not desk or not target:
        return JsonResponse({'error': 'desk und target erforderlich'}, status=400)
    from apps.abpe_crm.services.ami_control import originate_from_desk
    from apps.abpe_crm.services.normalize_phone_nr import normalize_phone
    try:
        t = target if (target.startswith('*') or target.isdigit() and len(target) <= 5) \
            else (normalize_phone(target) or target)
        return JsonResponse(originate_from_desk(desk, t))
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# =============================================================================
#  ANRUF-STEUERUNG
# =============================================================================
@extend_schema(summary="Kanal auflegen (Hangup)", tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_post
def api_telefon_hangup(request):
    ch = (_json_body(request).get('channel') or '').strip()
    if not ch:
        return JsonResponse({'error': 'channel fehlt'}, status=400)
    from apps.abpe_crm.services.ami_control import hangup
    return JsonResponse(hangup(ch))


@extend_schema(summary="Kanal umleiten (Redirect)", tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_post
def api_telefon_redirect(request):
    d = _json_body(request)
    ch = (d.get('channel') or '').strip()
    exten = (d.get('exten') or '').strip()
    context = (d.get('context') or 'from-internal').strip()
    if not ch or not exten:
        return JsonResponse({'error': 'channel und exten erforderlich'}, status=400)
    from apps.abpe_crm.services.ami_control import redirect
    return JsonResponse(redirect(ch, exten, context))


@extend_schema(summary="Blind-Transfer", tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_post
def api_telefon_blind_transfer(request):
    d = _json_body(request)
    ch = (d.get('channel') or '').strip()
    exten = (d.get('exten') or '').strip()
    if not ch or not exten:
        return JsonResponse({'error': 'channel und exten erforderlich'}, status=400)
    from apps.abpe_crm.services.ami_control import blind_transfer
    return JsonResponse(blind_transfer(ch, exten, (d.get('context') or 'from-internal').strip()))


@extend_schema(summary="Attended-Transfer (Atxfer)", tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_post
def api_telefon_atxfer(request):
    d = _json_body(request)
    ch = (d.get('channel') or '').strip()
    exten = (d.get('exten') or '').strip()
    if not ch or not exten:
        return JsonResponse({'error': 'channel und exten erforderlich'}, status=400)
    from apps.abpe_crm.services.ami_control import atxfer
    return JsonResponse(atxfer(ch, exten, (d.get('context') or 'from-internal').strip()))


@extend_schema(summary="Attended-Transfer abbrechen", tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_post
def api_telefon_cancel_atxfer(request):
    ch = (_json_body(request).get('channel') or '').strip()
    if not ch:
        return JsonResponse({'error': 'channel fehlt'}, status=400)
    from apps.abpe_crm.services.ami_control import cancel_atxfer
    return JsonResponse(cancel_atxfer(ch))


# =============================================================================
#  RECORDING (Kanal)
# =============================================================================
@extend_schema(summary="Aufnahme starten/stoppen (MixMonitor)",
               description="body: {channel, action: 'start'|'stop'}",
               tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_post
def api_telefon_record(request):
    d = _json_body(request)
    ch = (d.get('channel') or '').strip()
    action = (d.get('action') or 'start').strip()
    if not ch:
        return JsonResponse({'error': 'channel fehlt'}, status=400)
    from apps.abpe_crm.services.ami_control import start_recording, stop_recording
    return JsonResponse(stop_recording(ch) if action == 'stop' else start_recording(ch))


# =============================================================================
#  DND / FWD
# =============================================================================
@extend_schema(summary="DND setzen/aufheben", tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_post
def api_telefon_dnd(request):
    d = _json_body(request)
    extension = (d.get('extension') or '').strip()
    active = bool(d.get('active', False))
    if not extension:
        return JsonResponse({'success': False, 'error': 'extension fehlt'}, status=400)
    from apps.abpe_crm.services.ami_control import set_dnd
    try:
        results = {ext.strip(): set_dnd(ext.strip(), active).get('success', False)
                   for ext in extension.split(',') if ext.strip()}
        return JsonResponse({'success': all(results.values()), 'active': active, 'results': results})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@extend_schema(summary="Rufumleitung lesen",
               parameters=[_p("extension", OpenApiTypes.STR, "Nebenstelle")],
               tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_get
def api_telefon_fwd(request):
    extension = request.GET.get('extension', '').strip()
    if not extension:
        return JsonResponse({'error': 'extension fehlt'}, status=400)
    from apps.abpe_crm.services.ami_control import get_fwd
    target = get_fwd(extension)
    return JsonResponse({'extension': extension, 'target': target, 'active': bool(target)})


@extend_schema(summary="Rufumleitung setzen/aufheben (target leer = aus)",
               tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_post
def api_telefon_fwd_set(request):
    d = _json_body(request)
    extension = (d.get('extension') or '').strip()
    target = (d.get('target') or '').strip()
    if not extension:
        return JsonResponse({'success': False, 'error': 'extension fehlt'}, status=400)
    from apps.abpe_crm.services.ami_control import set_fwd
    from apps.abpe_crm.services.normalize_phone_nr import normalize_phone
    t = ''
    if target:
        t = target if (target.isdigit() and len(target) <= 5) else (normalize_phone(target) or target)
    return JsonResponse(set_fwd(extension, t))


# =============================================================================
#  PARKEN
# =============================================================================
@extend_schema(summary="Aktiven Kanal einer Nebenstelle parken",
               tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_post
def api_telefon_park(request):
    extension = (_json_body(request).get('extension') or '').strip()
    if not extension:
        return JsonResponse({'success': False, 'error': 'extension fehlt'}, status=400)
    from apps.abpe_crm.services.ami_control import park_partner
    return JsonResponse(park_partner(extension))


# =============================================================================
#  KONFERENZ-COCKPIT
# =============================================================================
@extend_schema(summary="ConfBridge-Teilnehmer (Detail eines Raums)",
               parameters=[_p("room", OpenApiTypes.STR, "Konferenzraum, z.B. 5555")],
               tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_get
def api_conf_detail(request):
    room = request.GET.get('room', '').strip()
    if not room:
        return JsonResponse({'error': 'room fehlt'}, status=400)
    from apps.abpe_crm.services.ami_control import get_confbridge_detail
    return JsonResponse({'room': room, 'members': get_confbridge_detail(room)})


@extend_schema(summary="Konferenz: Teilnehmer muten/entmuten/kicken (action)",
               description="body: {room, channel, action: 'mute'|'unmute'|'kick'}",
               tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_post
def api_conf_member(request):
    d = _json_body(request)
    room = (d.get('room') or '').strip()
    channel = (d.get('channel') or '').strip()
    action = (d.get('action') or '').strip()
    if not room or not channel or action not in ('mute', 'unmute', 'kick'):
        return JsonResponse({'error': 'room, channel und action (mute|unmute|kick) noetig'}, status=400)
    from apps.abpe_crm.services import ami_control as ac
    fn = {'mute': ac.conf_mute, 'unmute': ac.conf_unmute, 'kick': ac.conf_kick}[action]
    return JsonResponse(fn(room, channel))


@extend_schema(summary="Konferenz sperren/entsperren (action)",
               description="body: {room, action: 'lock'|'unlock'}",
               tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_post
def api_conf_lock(request):
    d = _json_body(request)
    room = (d.get('room') or '').strip()
    action = (d.get('action') or 'lock').strip()
    if not room:
        return JsonResponse({'error': 'room fehlt'}, status=400)
    from apps.abpe_crm.services import ami_control as ac
    return JsonResponse(ac.conf_unlock(room) if action == 'unlock' else ac.conf_lock(room))


@extend_schema(summary="Konferenz-Invite (Nummer/Nst in Raum holen)",
               description="body: {number, room}", tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_post
def api_conf_invite(request):
    d = _json_body(request)
    number = (d.get('number') or '').strip()
    room = (d.get('room') or '').strip()
    if not number or not room:
        return JsonResponse({'error': 'number und room erforderlich'}, status=400)
    from apps.abpe_crm.services.ami_control import originate_to_conf
    from apps.abpe_crm.services.normalize_phone_nr import normalize_phone
    n = number if (number.isdigit() and len(number) <= 5) else (normalize_phone(number) or number)
    return JsonResponse(originate_to_conf(n, room, d.get('caller_id') or 'Konferenz'))


@extend_schema(summary="Eigenen aktiven Kanal in Konferenz redirecten",
               description="body: {extension, conference}", tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_post
def api_telefon_conference(request):
    d = _json_body(request)
    extension = (d.get('extension') or '').strip()
    conference = (d.get('conference') or '5555').strip()
    if not extension:
        return JsonResponse({'success': False, 'error': 'extension fehlt'}, status=400)
    context = 'from-internal-custom' if conference == '5555' else 'from-internal'
    from apps.abpe_crm.services.ami_client import get_and_conference
    return JsonResponse(get_and_conference(extension, conference, context))


# =============================================================================
#  KUNDE-KOENIG (Call-and-Drop)
# =============================================================================
@extend_schema(
    summary="In Konferenz legen: Gespraechspartner einer Nst in den Raum umleiten",
    description="body: {extension, room}. Findet den Bridge-Partner der Nst und "
                "redirected ihn nach room (5555@from-internal-custom); eigene Seite "
                "wird frei ('transfer to hangup').",
    tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_post
def api_conf_pull_partner(request):
    d = _json_body(request)
    extension = (d.get('extension') or '').strip()
    room = (d.get('room') or '5555').strip()
    if not extension:
        return JsonResponse({'error': 'extension fehlt'}, status=400)
    context = 'from-internal-custom' if room == '5555' else 'from-internal'
    from apps.abpe_crm.services.ami_control import redirect_partner_to_conference
    return JsonResponse(redirect_partner_to_conference(extension, room, context))


@extend_schema(summary="Selbst beitreten: Tischtelefon in Konferenz holen",
               description="body: {desk, room}", tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_post
def api_conf_join_self(request):
    d = _json_body(request)
    desk = (d.get('desk') or d.get('extension') or '').strip()
    room = (d.get('room') or '5555').strip()
    if not desk:
        return JsonResponse({'error': 'desk fehlt'}, status=400)
    from apps.abpe_crm.services.ami_control import originate_from_desk
    return JsonResponse(originate_from_desk(desk, room, 'Konferenz'))


@extend_schema(summary="Alle konfigurierten Konferenzraeume (Hints + Live-Config, mit Live-Belegung)",
               tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_get
def api_telefon_conference_rooms(request):
    from apps.abpe_crm.services.ami_control import get_conference_rooms
    try:
        return JsonResponse({'success': True, 'rooms': get_conference_rooms()})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# =============================================================================
#  QUEUES
# =============================================================================
@extend_schema(summary="Warteschlangen (wartende Anrufer + Members)",
               tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_get
def api_telefon_queues(request):
    from apps.abpe_crm.services.ami_control import get_queues
    try:
        return JsonResponse({'queues': get_queues()})
    except Exception as e:
        return JsonResponse({'queues': [], 'error': str(e)}, status=500)


@extend_schema(summary="Queue-Agent: add/remove/pause (action)",
               description="body: {queue, extension, action: 'add'|'remove'|'pause'|'unpause'}",
               tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_post
def api_telefon_queue_member(request):
    d = _json_body(request)
    queue = (d.get('queue') or '').strip()
    ext = (d.get('extension') or '').strip()
    action = (d.get('action') or '').strip()
    if not queue or not ext or action not in ('add', 'remove', 'pause', 'unpause'):
        return JsonResponse({'error': 'queue, extension und action noetig'}, status=400)
    from apps.abpe_crm.services import ami_control as ac
    if action == 'add':
        return JsonResponse(ac.queue_add(queue, ext))
    if action == 'remove':
        return JsonResponse(ac.queue_remove(queue, ext))
    return JsonResponse(ac.queue_pause(queue, ext, paused=(action == 'pause')))


# =============================================================================
#  VOICEMAIL
# =============================================================================
@extend_schema(summary="Voicemail-Zaehler (eine Nst oder mehrere Boxen)",
               parameters=[_p("extension", OpenApiTypes.STR, "Nebenstelle"),
                           _p("boxes", OpenApiTypes.STR, "Komma-Liste Boxen")],
               tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_get
def api_telefon_voicemail(request):
    boxes_param = request.GET.get('boxes', '').strip()
    extension = request.GET.get('extension', '').strip()
    boxes = [b.strip() for b in boxes_param.split(',') if b.strip()] if boxes_param \
        else ([extension] if extension else [])
    if not boxes:
        return JsonResponse({'error': 'extension oder boxes fehlt'}, status=400)
    from apps.abpe_crm.services.ami_client import get_voicemail_counts
    try:
        data = get_voicemail_counts(boxes)
        if not boxes_param and extension:
            return JsonResponse(data.get(extension, {'new_messages': 0, 'old_messages': 0}))
        return JsonResponse({'boxes': data})
    except Exception as e:
        return JsonResponse({'new_messages': 0, 'old_messages': 0, 'error': str(e)})


@extend_schema(summary="Voicemail-Boxen Detail (Email/max/attach/new/old)",
               tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_get
def api_telefon_vmboxes(request):
    from apps.abpe_crm.services.ami_control import get_voicemail_boxes
    try:
        return JsonResponse({'boxes': get_voicemail_boxes()})
    except Exception as e:
        return JsonResponse({'boxes': [], 'error': str(e)}, status=500)


# =============================================================================
#  FOP (Legacy-Aggregat, beibehalten)
# =============================================================================
@extend_schema(summary="FOP-Status (Legacy-Aggregat)",
               parameters=[_p("extensions", OpenApiTypes.STR, "Komma-Liste"),
                           _p("vm_extensions", OpenApiTypes.STR, "Komma-Liste")],
               tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_get
def api_telefon_fop(request):
    extensions = [e.strip() for e in request.GET.get('extensions', '').split(',') if e.strip()]
    vm_extensions = [e.strip() for e in request.GET.get('vm_extensions', '').split(',') if e.strip()]
    if not extensions:
        from apps.abpe_crm.models import CrmUserSettings
        exts = set()
        for s in CrmUserSettings.objects.exclude(softphone_status_exts=''):
            for e in (s.softphone_status_exts or '').split(','):
                if e.strip():
                    exts.add(e.strip())
        extensions = sorted(exts, key=lambda x: int(x) if x.isdigit() else 0)
    from apps.abpe_crm.services.ami_client import get_fop_status
    try:
        return JsonResponse({'success': True, 'data': get_fop_status(extensions, vm_extensions)})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# =============================================================================
#  OFFLINE (Presence) / STEAL / BARGE
# =============================================================================
@extend_schema(summary="Nebenstelle offline/online setzen",
               description="body: {extension, offline: true|false}. Offline = DND-Route "
                           "(-> Unavail-VM) + Anzeige-Flag.", tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_post
def api_telefon_presence(request):
    d = _json_body(request)
    extension = (d.get('extension') or '').strip()
    offline = bool(d.get('offline', False))
    if not extension:
        return JsonResponse({'success': False, 'error': 'extension fehlt'}, status=400)
    from apps.abpe_crm.services.ami_control import set_offline
    return JsonResponse(set_offline(extension, offline))


@extend_schema(summary="Call-Steal: Gespraech einer Nst zu mir ziehen",
               description="body: {extension, to?}. Zieht den Partner auf 'to' (Default Tischtelefon).",
               tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_post
def api_telefon_steal(request):
    d = _json_body(request)
    extension = (d.get('extension') or '').strip()
    to = (d.get('to') or '12').strip()
    if not extension:
        return JsonResponse({'success': False, 'error': 'extension fehlt'}, status=400)
    from apps.abpe_crm.services.ami_control import steal_call
    return JsonResponse(steal_call(extension, to))


@extend_schema(summary="Barge/Whisper: in ein laufendes Gespraech dazuschalten",
               description="body: {extension, desk, mode: 'B'|'w'|''}. B=barge (alle hoeren), "
                           "w=whisper (nur Nst), ''=listen.", tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_post
def api_telefon_barge(request):
    d = _json_body(request)
    extension = (d.get('extension') or '').strip()
    desk = (d.get('desk') or '').strip()
    mode = (d.get('mode') or 'B').strip()
    if not extension or not desk:
        return JsonResponse({'success': False, 'error': 'extension und desk erforderlich'}, status=400)
    from apps.abpe_crm.services.ami_control import get_channels_bridged, barge_call
    ch = next((c for c in get_channels_bridged() if c['extension'] == extension), None)
    if not ch:
        return JsonResponse({'success': False, 'error': 'Kein aktives Gespraech auf ' + extension}, status=404)
    return JsonResponse(barge_call(desk, ch['channel'], mode))


# =============================================================================
#  PROTOKOLL / NOTIZ (DeepSeek)
# =============================================================================
@extend_schema(summary="Konferenzprotokoll formulieren (DeepSeek)",
               description="body: {notes, meta:{titel,datum,teilnehmer}, output:'txt'|'json'}",
               tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_post
def api_protokoll_format(request):
    d = _json_body(request)
    notes = (d.get('notes') or '').strip()
    if not notes:
        return JsonResponse({'success': False, 'error': 'notes fehlt'}, status=400)
    output = (d.get('output') or 'txt').strip()
    from apps.abpe_crm.services.deepseek_api_pbx import deepseek_pbx
    res = deepseek_pbx.format_protocol(notes, meta=d.get('meta') or {}, output=output)
    return JsonResponse({'success': res.success, 'text': res.text, 'data': res.data,
                         'error': res.error})


@extend_schema(summary="Gespraechsnotiz formulieren (DeepSeek)",
               description="body: {note, context}", tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_post
def api_notiz_format(request):
    d = _json_body(request)
    note = (d.get('note') or '').strip()
    if not note:
        return JsonResponse({'success': False, 'error': 'note fehlt'}, status=400)
    from apps.abpe_crm.services.deepseek_api_pbx import deepseek_pbx
    res = deepseek_pbx.format_note(note, context=d.get('context'))
    return JsonResponse({'success': res.success, 'text': res.text, 'error': res.error})


# =============================================================================
#  WAV-NOTIZEN (Voicemail zentral, unabhaengig von Kontakt-Zuordnung)
# =============================================================================
@extend_schema(summary="WAV-Notizen: alle Voicemail-Nachrichten (INBOX+Old)",
               tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_get
def api_telefon_wavnotes(request):
    try:
        from .services.ami_control import get_voicemail_boxes
        from .services.voicemail_wavnotes import list_wavnotes
        from apps.abpe_crm.models import CrmContactNote

        mailboxes = [b['box'] for b in get_voicemail_boxes()]
        notes = list_wavnotes(mailboxes)

        documented = set(
            CrmContactNote.objects.filter(
                wavnote_mailbox__isnull=False, wavnote_msg_id__isnull=False,
            ).values_list('wavnote_mailbox', 'wavnote_msg_id')
        )
        from apps.abpe_crm.models import CrmWavnoteStatus
        archived = set(CrmWavnoteStatus.objects.values_list('mailbox', 'msg_id'))
        for n in notes:
            key = (n['mailbox'], n['msg_id'])
            n['has_note'] = key in documented
            n['archived_manual'] = key in archived
            n['is_done'] = n['has_note'] or n['archived_manual']

        return JsonResponse({'success': True, 'data': notes})
    except Exception as e:
        logger.error(f'api_telefon_wavnotes Fehler: {e}')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@extend_schema(summary="WAV-Notiz Audio streamen (Cache-first von PBX)",
               tags=TAGS,
               parameters=[
                   _p('mailbox', OpenApiTypes.STR, 'Mailbox-Nummer'),
                   _p('folder', OpenApiTypes.STR, 'INBOX oder Old'),
                   _p('msg_id', OpenApiTypes.STR, 'z.B. msg0002'),
               ])
@_drf_get
def api_telefon_wavnote_audio(request):
    import os
    from django.conf import settings
    from django.http import FileResponse
    from .services.voicemail_wavnotes import fetch_wav_bytes, FOLDERS

    mailbox = request.GET.get('mailbox', '').strip()
    folder = request.GET.get('folder', '').strip()
    msg_id = request.GET.get('msg_id', '').strip()
    if not mailbox or folder not in FOLDERS or not msg_id:
        return JsonResponse({'success': False, 'error': 'mailbox/folder/msg_id fehlt oder ungueltig'}, status=400)

    cache_dir = os.path.join(str(settings.MEDIA_ROOT), 'wavnotes_cache', mailbox, folder)
    cache_path = os.path.join(cache_dir, f'{msg_id}.wav')
    if not os.path.exists(cache_path):
        try:
            data = fetch_wav_bytes(mailbox, folder, msg_id)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
        os.makedirs(cache_dir, exist_ok=True)
        with open(cache_path, 'wb') as f:
            f.write(data)

    resp = FileResponse(open(cache_path, 'rb'), content_type='audio/wav')
    resp['Accept-Ranges'] = 'bytes'
    return resp


@extend_schema(summary="WAV-Notiz transkribieren + glaetten (Whisper + DeepSeek)",
               description="body: {mailbox, folder, msg_id}",
               tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_post
def api_telefon_wavnote_transcribe(request):
    import os
    from django.conf import settings
    from .services.voicemail_wavnotes import fetch_wav_bytes, FOLDERS

    d = _json_body(request)
    mailbox = (d.get('mailbox') or '').strip()
    folder = (d.get('folder') or '').strip()
    msg_id = (d.get('msg_id') or '').strip()
    if not mailbox or folder not in FOLDERS or not msg_id:
        return JsonResponse({'success': False, 'error': 'mailbox/folder/msg_id fehlt oder ungueltig'}, status=400)

    cache_dir = os.path.join(str(settings.MEDIA_ROOT), 'wavnotes_cache', mailbox, folder)
    cache_path = os.path.join(cache_dir, f'{msg_id}.wav')
    if not os.path.exists(cache_path):
        try:
            data = fetch_wav_bytes(mailbox, folder, msg_id)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
        os.makedirs(cache_dir, exist_ok=True)
        with open(cache_path, 'wb') as f:
            f.write(data)

    from .services.whisper_service import whisper_service
    try:
        raw = whisper_service.transcribe(cache_path, language='de')
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Transkription fehlgeschlagen: {e}'}, status=500)

    from .services.deepseek_api_pbx import deepseek_pbx
    polished_text = raw['text']
    deepseek_error = None
    if deepseek_pbx.is_available():
        res = deepseek_pbx.format_note(
            raw['text'],
            context='Automatisches Whisper-Transkript einer Voicemail, kann Verhoerer/Tippfehler enthalten.',
        )
        if res.success:
            polished_text = res.text
        else:
            deepseek_error = res.error

    return JsonResponse({
        'success': True,
        'raw_text': raw['text'],
        'polished_text': polished_text,
        'language': raw['language'],
        'deepseek_error': deepseek_error,
    })


@extend_schema(summary="WAV-Notiz als Telefonnotiz speichern (CrmContactNote)",
               description="body: {mailbox, folder, msg_id, note_text, raw_text?, contact_crm_id?, account_crm_id?}",
               tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_post
def api_telefon_wavnote_save(request):
    from apps.abpe_crm.models import CrmContact, CrmAccount, CrmContactNote

    d = _json_body(request)
    note_text = (d.get('note_text') or '').strip()
    if not note_text:
        return JsonResponse({'success': False, 'error': 'note_text fehlt'}, status=400)

    contact_crm_id = d.get('contact_crm_id')
    account_crm_id = d.get('account_crm_id')
    contact = CrmContact.objects.filter(crm_id=contact_crm_id).first() if contact_crm_id else None
    account = CrmAccount.objects.filter(crm_id=account_crm_id).first() if account_crm_id else None

    note = CrmContactNote.objects.create(
        contact=contact,
        account=account,
        note_text=note_text,
        note_type='phone',
        created_by=request.user.username,
        wavnote_mailbox=d.get('mailbox') or None,
        wavnote_msg_id=d.get('msg_id') or None,
        wavnote_raw_text=d.get('raw_text') or None,
    )
    return JsonResponse({'success': True, 'id': note.id})

@extend_schema(summary="WAV-Notiz archivieren (nicht relevant, ohne Notiz)",
               description="body: {mailbox, msg_id}",
               tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_post
def api_telefon_wavnote_archive(request):
    from apps.abpe_crm.models import CrmWavnoteStatus

    d = _json_body(request)
    mailbox = (d.get('mailbox') or '').strip()
    msg_id = (d.get('msg_id') or '').strip()
    if not mailbox or not msg_id:
        return JsonResponse({'success': False, 'error': 'mailbox/msg_id fehlt'}, status=400)

    obj, created = CrmWavnoteStatus.objects.get_or_create(
        mailbox=mailbox, msg_id=msg_id,
        defaults={'archived_by': request.user.username},
    )
    return JsonResponse({'success': True, 'created': created})

