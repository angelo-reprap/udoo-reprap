"""abpe_meetme API — Konferenz-/MeetMe-Planung, vollstaendig dokumentiert
via drf-spectacular. Reminder-Terminierung laeuft ueber abpe_scheduler
(HTTP-API, siehe scheduler_client.py)."""
import logging

from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from . import reminder_engine
from .models import MeetmeMeeting, MeetmeGuest, MeetmeReminderRule, MeetmeReminderDelivery
from .serializers import (
    MeetmeMeetingSerializer, MeetmeGuestSerializer,
    MeetmeReminderRuleSerializer, MeetmeReminderDeliverySerializer,
)

logger = logging.getLogger(__name__)


def _mm_resolve_signature(signature_id=None):
    """Loest die Signatur fuer Verschieben/Absagen-Mails auf.
    Eigenstaendig, unabhaengig vom (aktuell nicht verdrahteten)
    EmailStudio signature_mode-Mechanismus.
    Default: is_default=True Signatur ("Team"). Override per signature_id."""
    from apps.abpe_email_studio.models import EmailSignature
    sig = None
    if signature_id:
        sig = EmailSignature.objects.filter(pk=signature_id).first()
    if not sig:
        sig = EmailSignature.objects.filter(is_default=True).first()
    if not sig:
        return ""
    if sig.text_body:
        return sig.text_body
    import re as _re
    html = sig.html_body or ""
    html = _re.sub(r"<br\s*/?>", "\n", html, flags=_re.IGNORECASE)
    html = _re.sub(r"</(p|div|tr|td|table)>", "\n", html, flags=_re.IGNORECASE)
    text = _re.sub(r"<[^>]+>", "", html)
    text = _re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _mm_append_signature(body, signature_id=None):
    sig_text = _mm_resolve_signature(signature_id)
    if not sig_text:
        return body
    return f"{body}\n\n{sig_text}"


def _mm_email_header_module(action):
    """Header-Zeile live aus dem Email-Studio-Baukasten - blau fuer
    Verschieben/Einladen, rot fuer Absagen. Aenderungen am Modul im
    Studio wirken sich automatisch hier aus."""
    from apps.abpe_email_studio.models import EmailModule
    identifier = 'abcona_header_rot' if action == 'cancel' else 'abcona_header_blau'
    mod = EmailModule.objects.filter(identifier=identifier, is_active=True).first()
    if mod:
        return mod.html_body
    color = '#dc3545' if action == 'cancel' else '#163258'
    return (
        f'<tr><td style="background:{color};padding:16px 24px;text-align:center;">'
        f'<span style="color:white;font-size:18px;font-weight:bold;">abcona e. K.</span></td></tr>'
    )


def _mm_email_footer_module():
    from apps.abpe_email_studio.models import EmailModule
    mod = EmailModule.objects.filter(identifier='footer_standard', is_active=True).first()
    if mod:
        return mod.html_body
    return (
        '<tr><td style="background:#f8fafc;padding:12px 24px;font-size:11px;color:#6c757d;'
        'text-align:center;">ABpE — Automatisiertes Berater Profil Erfassungssystem</td></tr>'
    )


def _mm_text_to_html_paragraphs(text):
    """Reine Absatz-Konvertierung (Text -> <p>), ohne Rahmen/Layout."""
    import html as _html
    parts = []
    for para in (text or "").split("\n\n"):
        escaped = _html.escape(para).replace("\n", "<br>")
        parts.append(f'<p style="margin:0 0 12px;">{escaped}</p>')
    return "".join(parts)


def _mm_resolve_signature_html(signature_id=None):
    from apps.abpe_email_studio.models import EmailSignature
    sig = None
    if signature_id:
        sig = EmailSignature.objects.filter(pk=signature_id).first()
    if not sig:
        sig = EmailSignature.objects.filter(is_default=True).first()
    if not sig:
        return ""
    if sig.html_body:
        return sig.html_body
    import html as _html
    return "".join(
        f'<p style="margin:0 0 4px;">{_html.escape(line)}</p>'
        for line in (sig.text_body or "").split("\n") if line.strip()
    )


def _mm_text_to_html(text, action=None, signature_id=None):
    """Baut die komplette HTML-Mail im abcona-Standardlayout (600px
    weisse Karte, farbiger Header je Aktionstyp, Standard-Footer)."""
    content = _mm_text_to_html_paragraphs(text)
    sig_html = _mm_resolve_signature_html(signature_id)
    header = _mm_email_header_module(action)
    footer = _mm_email_footer_module()
    return (
        '<!DOCTYPE html><html><head><meta charset="UTF-8"></head>'
        '<body style="margin:0;background:#f4f4f4;font-family:Arial,sans-serif;">'
        '<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:20px 10px;">'
        '<table width="600" cellpadding="0" cellspacing="0" style="background:white;border-radius:8px;overflow:hidden;">'
        f'{header}'
        f'<tr><td style="padding:24px;">{content}{sig_html}</td></tr>'
        f'{footer}'
        '</table></td></tr></table></body></html>'
    )


def _mm_build_final_bodies(body, signature_id=None, action=None):
    """Baut die finalen Text- und HTML-Versionen inkl. Signatur - dieselbe
    Funktion wird sowohl beim tatsaechlichen Versand als auch bei der
    Live-Vorschau im Modal genutzt (WYSIWYG-Garantie, keine zwei getrennten
    Rendering-Pfade die auseinanderlaufen koennten)."""
    text_final = _mm_append_signature(body, signature_id)
    html_final = _mm_text_to_html(body, action=action, signature_id=signature_id)
    return text_final, html_final


# ========== Anhaenge (EDMS-Suche + Live-Ordner-Browser fuer Office/Public) ==========

_MM_ATTACH_MAX_TOTAL_BYTES = 7 * 1024 * 1024  # ~7MB roh (Postfix-Limit 10MB inkl. Base64-Overhead)


def _mm_resolve_attachment(ref):
    """ref: {'type': 'edms', 'uuid': '...'} oder
    {'type': 'fs', 'volume': 'office'|'public', 'relative_path': '...'}.
    Rueckgabe: (abs_path, filename, mimetype, size_bytes) oder None bei Fehler."""
    import os
    from django.conf import settings as django_settings

    ref_type = ref.get('type')
    if ref_type == 'edms':
        from apps.abpe_edms.models import CrmDocument
        from apps.abpe_edms.services import storage as edms_storage
        uuid_val = ref.get('uuid')
        if not uuid_val:
            return None
        doc = CrmDocument.objects.filter(uuid=uuid_val).first()
        if not doc:
            return None
        version = doc.versions.filter(is_active=True).order_by('-version_no').first()
        if not version:
            return None
        abs_path = edms_storage.absolute_path(version)
        if not abs_path or not os.path.exists(abs_path):
            return None
        return abs_path, version.filename, (version.mimetype or 'application/octet-stream'), (version.size_bytes or 0)

    if ref_type == 'fs':
        volume = ref.get('volume')
        rel_path = ref.get('relative_path') or ''
        mounts = {
            'office': getattr(django_settings, 'DMS_OFFICE_MOUNT', '/mnt/office'),
            'public': getattr(django_settings, 'DMS_PUBLIC_MOUNT', '/mnt/public'),
        }
        mount_root = mounts.get(volume)
        if not mount_root:
            return None
        norm_rel = os.path.normpath(rel_path).lstrip(os.sep)
        abs_path = os.path.normpath(os.path.join(mount_root, norm_rel))
        mount_norm = os.path.normpath(mount_root)
        if not (abs_path == mount_norm or abs_path.startswith(mount_norm + os.sep)):
            return None
        if not os.path.isfile(abs_path):
            return None
        import mimetypes
        mt, _ = mimetypes.guess_type(abs_path)
        try:
            size = os.path.getsize(abs_path)
        except OSError:
            size = 0
        return abs_path, os.path.basename(abs_path), (mt or 'application/octet-stream'), size

    return None


def _mm_resolve_and_read_attachments(attachment_refs):
    """Loest eine Liste von Anhang-Referenzen auf und liest die Datei-Bytes.
    Wirft ValueError bei nicht aufloesbaren Referenzen oder Groessenueberschreitung,
    damit der Aufrufer VOR dem Versand sauber antworten kann (kein halb-gesendeter
    Zustand)."""
    if not attachment_refs:
        return []
    total = 0
    out = []
    for ref in attachment_refs:
        info = _mm_resolve_attachment(ref)
        if info is None:
            raise ValueError(f"Anhang konnte nicht aufgeloest werden: {ref.get('filename') or ref}")
        abs_path, filename, mimetype, size_bytes = info
        total += size_bytes or 0
        if total > _MM_ATTACH_MAX_TOTAL_BYTES:
            raise ValueError(
                f"Anhaenge zu gross ({total // 1024} KB, Limit {_MM_ATTACH_MAX_TOTAL_BYTES // 1024} KB)"
            )
        with open(abs_path, 'rb') as f:
            out.append((filename, f.read(), mimetype))
    return out


@api_view(['GET'])
def api_attachment_search(request):
    """Durchsucht den EDMS-Dokumentenindex (ES-Index 'dms') nach Dateiname/Titel,
    fuer die Anhang-Auswahl im MeetMe-Modal. Eigenstaendige, schlanke Suche statt
    Anzapfen von abpe_edms.api_search, damit das Antwortformat hier unter eigener
    Kontrolle bleibt."""
    from elasticsearch import Elasticsearch
    q = (request.query_params.get('q') or '').strip()
    if not q:
        return Response({'results': []})
    try:
        size = int(request.query_params.get('size', 8))
    except (TypeError, ValueError):
        size = 8
    size = max(1, min(size, 20))
    volume = request.query_params.get('volume')  # 'office' | 'public' | None -> ungefiltert

    es = Elasticsearch(["http://localhost:9200"])
    fetch_size = min(max(size * 15, 150), 300) if volume in ('office', 'public') else size
    body = {
        "size": fetch_size,
        "sort": [
            {"document_date": {"order": "desc", "missing": "_last"}},
            "_score",
        ],
        "query": {
            "bool": {
                "should": [
                    {"multi_match": {"query": q, "fields": ["title^3", "filename^2", "content", "owner_names^2", "owner_emails^2", "owner_phones^2"], "type": "best_fields"}},
                    {"wildcard": {"filename.raw": {"value": f"*{q.lower()}*"}}},
                ],
                "minimum_should_match": 1,
            }
        },
    }
    try:
        res = es.search(index="dms", body=body)
    except Exception as exc:
        logger.error("Anhang-Suche fehlgeschlagen: %s", exc)
        return Response({'error': 'Suche fehlgeschlagen', 'results': []}, status=502)

    hits = res.get('hits', {}).get('hits', [])

    if volume in ('office', 'public'):
        from apps.abpe_edms.models import CrmDocument
        uuids = [h.get('_source', {}).get('uuid') for h in hits if h.get('_source', {}).get('uuid')]
        docs = CrmDocument.objects.filter(uuid__in=uuids).prefetch_related('versions')
        volume_by_uuid = {}
        for doc in docs:
            v = doc.versions.filter(is_active=True).order_by('-version_no').first()
            if v:
                volume_by_uuid[str(doc.uuid)] = v.volume
        hits = [h for h in hits if volume_by_uuid.get(h.get('_source', {}).get('uuid')) == volume]

    hits = hits[:size]

    results = []
    for hit in hits:
        src_doc = hit.get('_source', {})
        results.append({
            'uuid': src_doc.get('uuid'),
            'filename': src_doc.get('filename') or src_doc.get('title'),
            'title': src_doc.get('title'),
            'doctype_label': src_doc.get('doctype_label'),
            'size_bytes': src_doc.get('size_bytes'),
        })
    return Response({'results': results})


@api_view(['GET'])
def api_attachment_browse(request):
    """Listet Ordner/Dateien live auf den Samba-Shares. Kein ES-Index noetig,
    da EDMS nach DocType/Owner organisiert ist, nicht nach Ordnern -- fuer den
    klassischen Datei-Browser braucht es den direkten Mount-Zugriff."""
    import os
    from django.conf import settings as django_settings

    volume = request.query_params.get('volume')
    rel = request.query_params.get('path', '') or ''
    mounts = {
        'office': getattr(django_settings, 'DMS_OFFICE_MOUNT', '/mnt/office'),
        'public': getattr(django_settings, 'DMS_PUBLIC_MOUNT', '/mnt/public'),
    }
    if volume not in mounts:
        return Response({'error': "volume muss 'office' oder 'public' sein"}, status=400)

    mount_root = mounts[volume]
    norm_rel = os.path.normpath(rel).lstrip(os.sep)
    if norm_rel == '.':
        norm_rel = ''
    abs_path = os.path.normpath(os.path.join(mount_root, norm_rel))
    mount_norm = os.path.normpath(mount_root)
    if not (abs_path == mount_norm or abs_path.startswith(mount_norm + os.sep)):
        return Response({'error': 'Ungueltiger Pfad'}, status=400)
    if not os.path.isdir(abs_path):
        return Response({'error': 'Ordner nicht gefunden'}, status=404)

    folders, files = [], []
    try:
        with os.scandir(abs_path) as it:
            for entry in it:
                if entry.name.startswith('.'):
                    continue
                if entry.is_dir():
                    folders.append(entry.name)
                elif entry.is_file():
                    try:
                        size = entry.stat().st_size
                    except OSError:
                        size = 0
                    files.append({'name': entry.name, 'size_bytes': size})
    except OSError as exc:
        return Response({'error': f'Lesefehler: {exc}'}, status=500)

    folders.sort(key=str.lower)
    files.sort(key=lambda f: f['name'].lower())
    return Response({'volume': volume, 'path': norm_rel, 'folders': folders, 'files': files})


# ========== Meetings ==========

@extend_schema(summary="Meetings auflisten", responses=MeetmeMeetingSerializer(many=True))
@api_view(['GET'])
def api_meeting_list(request):
    from django.db.models import Q
    from django.utils import timezone
    from django.utils.dateparse import parse_datetime

    qs = MeetmeMeeting.objects.all()
    status_filter = request.query_params.get('status')
    if status_filter:
        qs = qs.filter(status=status_filter)

    archived_param = request.query_params.get('archived')
    now = timezone.now()
    archived_q = Q(status='CANCELLED') | Q(start_at__lt=now)

    if archived_param == 'true':
        qs = qs.filter(archived_q)
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        if date_from:
            parsed = parse_datetime(date_from)
            if parsed:
                qs = qs.filter(start_at__gte=parsed)
        if date_to:
            parsed = parse_datetime(date_to)
            if parsed:
                qs = qs.filter(start_at__lte=parsed)
        qs = qs.order_by('-start_at')
    elif archived_param == 'false':
        qs = qs.exclude(archived_q)
        qs = qs.order_by('start_at')
    else:
        qs = qs.order_by('-start_at')

    return Response(MeetmeMeetingSerializer(qs, many=True).data)


@extend_schema(summary="Meeting anlegen", request=MeetmeMeetingSerializer, responses=MeetmeMeetingSerializer)
@api_view(['POST'])
def api_meeting_create(request):
    serializer = MeetmeMeetingSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    meeting = serializer.save(created_by=request.user if request.user.is_authenticated else None)
    return Response(MeetmeMeetingSerializer(meeting).data, status=status.HTTP_201_CREATED)


@extend_schema(summary="Meeting-Detail inkl. Gaeste und Regeln", responses=MeetmeMeetingSerializer)
@api_view(['GET'])
def api_meeting_detail(request, meeting_id):
    meeting = get_object_or_404(MeetmeMeeting, id=meeting_id)
    return Response(MeetmeMeetingSerializer(meeting).data)


@extend_schema(summary="Meeting aendern", request=MeetmeMeetingSerializer, responses=MeetmeMeetingSerializer)
@api_view(['PATCH'])
def api_meeting_update(request, meeting_id):
    meeting = get_object_or_404(MeetmeMeeting, id=meeting_id)
    serializer = MeetmeMeetingSerializer(meeting, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    meeting = serializer.save()
    if 'start_at' in request.data:
        reminder_engine.sync_reminder_deliveries(meeting)
    return Response(MeetmeMeetingSerializer(meeting).data)


@extend_schema(summary="Meeting absagen (storniert offene Erinnerungen)", responses={204: None})
@api_view(['DELETE'])
def api_meeting_cancel(request, meeting_id):
    meeting = get_object_or_404(MeetmeMeeting, id=meeting_id)
    meeting.status = 'CANCELLED'
    meeting.save(update_fields=['status'])
    reminder_engine.cancel_reminder_deliveries(meeting)
    return Response(status=status.HTTP_204_NO_CONTENT)


# ========== Gaeste ==========

@extend_schema(summary="Gast zu einem Meeting hinzufuegen", request=MeetmeGuestSerializer, responses=MeetmeGuestSerializer)
@api_view(['POST'])
def api_guest_create(request, meeting_id):
    meeting = get_object_or_404(MeetmeMeeting, id=meeting_id)
    data = dict(request.data)
    data['meeting'] = meeting.id
    serializer = MeetmeGuestSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    guest = serializer.save()
    reminder_engine.sync_reminder_deliveries(meeting)
    return Response(MeetmeGuestSerializer(guest).data, status=status.HTTP_201_CREATED)


@extend_schema(summary="Gast aendern (z. B. is_active=false zum Entfernen aus Erinnerungen)",
                request=MeetmeGuestSerializer, responses=MeetmeGuestSerializer)
@api_view(['PATCH'])
def api_guest_update(request, guest_id):
    guest = get_object_or_404(MeetmeGuest, id=guest_id)
    serializer = MeetmeGuestSerializer(guest, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    guest = serializer.save()
    reminder_engine.sync_reminder_deliveries(guest.meeting)
    return Response(MeetmeGuestSerializer(guest).data)


@extend_schema(summary="Gast endgueltig loeschen", responses={204: None})
@api_view(['DELETE'])
def api_guest_delete(request, guest_id):
    guest = get_object_or_404(MeetmeGuest, id=guest_id)
    meeting = guest.meeting
    guest.delete()
    reminder_engine.sync_reminder_deliveries(meeting)
    return Response(status=status.HTTP_204_NO_CONTENT)


# ========== Erinnerungsregeln ==========

@extend_schema(summary="Erinnerungsregel anlegen", request=MeetmeReminderRuleSerializer,
                responses=MeetmeReminderRuleSerializer)
@api_view(['POST'])
def api_reminder_rule_create(request, meeting_id):
    meeting = get_object_or_404(MeetmeMeeting, id=meeting_id)
    data = dict(request.data)
    data['meeting'] = meeting.id
    guest_id = data.get('guest')
    if guest_id and not meeting.guests.filter(id=guest_id).exists():
        return Response({'error': 'Gast gehoert nicht zu diesem Meeting'}, status=status.HTTP_400_BAD_REQUEST)
    serializer = MeetmeReminderRuleSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    rule = serializer.save()
    reminder_engine.sync_reminder_deliveries(meeting)
    return Response(MeetmeReminderRuleSerializer(rule).data, status=status.HTTP_201_CREATED)


@extend_schema(summary="Erinnerungsregel aendern", request=MeetmeReminderRuleSerializer,
                responses=MeetmeReminderRuleSerializer)
@api_view(['PATCH'])
def api_reminder_rule_update(request, rule_id):
    rule = get_object_or_404(MeetmeReminderRule, id=rule_id)
    serializer = MeetmeReminderRuleSerializer(rule, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    rule = serializer.save()
    reminder_engine.sync_reminder_deliveries(rule.meeting)
    return Response(MeetmeReminderRuleSerializer(rule).data)


@extend_schema(summary="Erinnerungsregel loeschen", responses={204: None})
@api_view(['DELETE'])
def api_reminder_rule_delete(request, rule_id):
    rule = get_object_or_404(MeetmeReminderRule, id=rule_id)
    meeting = rule.meeting
    reminder_engine.cancel_reminder_deliveries(meeting)
    rule.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ========== Sende-Assistent (Erinnerungs-Queue) ==========

@extend_schema(
    summary="Faellige/offene Erinnerungen fuer den Sende-Assistenten abrufen",
    parameters=[OpenApiParameter('meeting_id', int, required=False)],
    responses=MeetmeReminderDeliverySerializer(many=True),
)
@api_view(['GET'])
def api_delivery_queue(request):
    qs = MeetmeReminderDelivery.objects.filter(status__in=['PENDING', 'DUE'])
    meeting_id = request.query_params.get('meeting_id')
    if meeting_id:
        qs = qs.filter(rule__meeting_id=meeting_id)
    return Response(MeetmeReminderDeliverySerializer(qs, many=True).data)


@extend_schema(
    summary="Erinnerung als gesendet markieren (Sende-Assistent: Senden & weiter)",
    request={'application/json': {'type': 'object', 'properties': {
        'subject': {'type': 'string'}, 'body': {'type': 'string'},
        'email_log_id': {'type': 'integer'},
    }}},
    responses=MeetmeReminderDeliverySerializer,
)
@api_view(['POST'])
def api_delivery_mark_sent(request, delivery_id):
    delivery = get_object_or_404(MeetmeReminderDelivery, id=delivery_id)
    subject = request.data.get('subject', delivery.subject)
    body = request.data.get('body', delivery.body)

    from django.core.mail import send_mail
    from django.conf import settings as django_settings
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(django_settings, 'DEFAULT_FROM_EMAIL', None),
            recipient_list=[delivery.guest.email],
            fail_silently=False,
        )
    except Exception as exc:
        logger.error("E-Mail-Versand fuer delivery=%s fehlgeschlagen: %s", delivery.id, exc)
        delivery.status = 'FAILED'
        delivery.failed_reason = str(exc)[:2000]
        delivery.save(update_fields=['status', 'failed_reason'])
        return Response({'error': f'Versand fehlgeschlagen: {exc}'}, status=502)

    delivery.subject = subject
    delivery.body = body
    delivery.status = 'SENT'
    delivery.sent_at = timezone.now()
    delivery.save()
    return Response(MeetmeReminderDeliverySerializer(delivery).data)


@extend_schema(summary="Erinnerung ueberspringen (Sende-Assistent: Ueberspringen)",
                responses=MeetmeReminderDeliverySerializer)
@api_view(['POST'])
def api_delivery_skip(request, delivery_id):
    delivery = get_object_or_404(MeetmeReminderDelivery, id=delivery_id)
    delivery.status = 'SKIPPED'
    delivery.save(update_fields=['status'])
    return Response(MeetmeReminderDeliverySerializer(delivery).data)


# ========== Webhook: wird von abpe_scheduler aufgerufen ==========

@extend_schema(
    summary="Webhook: abpe_scheduler meldet, dass eine Erinnerung faellig ist",
    request={'application/json': {'type': 'object', 'properties': {
        'delivery_id': {'type': 'integer'}}}},
    responses={200: None},
)
@api_view(['POST'])
@permission_classes([AllowAny])
def api_webhook_reminder_due(request):
    delivery_id = request.data.get('delivery_id')
    if not delivery_id:
        return Response({'error': 'delivery_id fehlt'}, status=400)

    try:
        delivery = MeetmeReminderDelivery.objects.get(id=delivery_id)
    except MeetmeReminderDelivery.DoesNotExist:
        return Response({'error': 'delivery nicht gefunden'}, status=404)

    if delivery.status not in ('SENT', 'SKIPPED'):
        delivery.status = 'DUE'
        delivery.save(update_fields=['status'])
        logger.info("Erinnerung faellig: delivery=%s guest=%s rule=%s",
                    delivery.id, delivery.guest.name, delivery.rule)

    # Bei mode=AUTO koennte hier direkt der Versand ueber abpe_email_studio
    # angestossen werden. Fuer mode=MANUAL bleibt es bei status=DUE, das
    # Frontend zeigt die Erinnerung dann im Sende-Assistenten (api_delivery_queue) an.

    return Response({'status': 'ok'})


# ========== Konferenzraeume (PBX/AMI) ==========

@extend_schema(summary="Verfuegbare Konferenzraeume/MeetMe-Nummern von der PBX abfragen",
                responses={200: None})
@api_view(['GET'])
def api_rooms_available(request):
    """Liest die aktuell konfigurierten Konferenzraeume live von der PBX —
    kombiniert Dialplan-Hints (034/035) und direktes Config-Auslesen per
    SFTP (erfasst zusaetzlich hint-lose Custom-Raeume wie 5555).
    Siehe apps.abpe_crm.services.ami_control.get_conference_rooms."""
    try:
        from apps.abpe_crm.services.ami_control import get_conference_rooms
        rooms = get_conference_rooms()
    except Exception as exc:
        logger.warning("AMI/Config-Abfrage der Konferenzraeume fehlgeschlagen: %s", exc)
        rooms = []
    return Response({'rooms': rooms})


@extend_schema(summary="Health-Check", responses={200: None})
@api_view(['GET'])
@permission_classes([AllowAny])
def api_health(request):
    return Response({
        'status': 'ok',
        'meetings': MeetmeMeeting.objects.count(),
        'open_reminders': MeetmeReminderDelivery.objects.filter(status__in=['PENDING', 'DUE']).count(),
    })


@extend_schema(
    summary="DeepSeek-Vorschlag fuer Erinnerungs-/Einladungstext generieren",
    request={'application/json': {'type': 'object', 'properties': {'text': {'type': 'string'}}}},
    responses={200: None},
)
@api_view(['POST'])
def api_deepseek_suggest(request):
    text = (request.data.get('text') or '').strip()
    if not text:
        return Response({'error': 'text erforderlich'}, status=400)

    try:
        from apps.abpe_crm.services.deepseek_api_pbx import deepseek_pbx
        result = deepseek_pbx.summarize(
            text,
            instruction=(
                "Formuliere diesen Text als freundliche, professionelle "
                "geschaeftliche E-Mail-Einladung bzw. Erinnerung um. Behalte "
                "alle Fakten (Datum, Uhrzeit, Ort) exakt bei, erfinde nichts "
                "hinzu, schreibe auf Deutsch."
            ),
        )
    except Exception as exc:
        logger.warning("DeepSeek-Vorschlag fehlgeschlagen: %s", exc)
        return Response({'error': 'DeepSeek nicht verfuegbar'}, status=502)

    if not result.success:
        return Response({'error': result.error or 'DeepSeek-Fehler'}, status=502)

    return Response({'suggestion': result.text})


@extend_schema(
    summary="Ad-hoc E-Mail an einen Gast senden (nicht an eine Erinnerung gebunden)",
    request={'application/json': {'type': 'object', 'properties': {
        'subject': {'type': 'string'}, 'body': {'type': 'string'},
        'notification_kind': {'type': 'string', 'enum': ['reschedule', 'cancel']},
        'target_start_at': {'type': 'string'},
    }}},
    responses={200: None},
)
@api_view(['POST'])
def api_guest_send_adhoc(request, guest_id):
    guest = get_object_or_404(MeetmeGuest, id=guest_id)
    subject = (request.data.get('subject') or '').strip()
    body = (request.data.get('body') or '').strip()
    if not subject or not body:
        return Response({'error': 'subject und body erforderlich'}, status=400)

    text_final, html_final = _mm_build_final_bodies(
        body, request.data.get('signature_id'), request.data.get('notification_kind')
    )

    attachment_refs = request.data.get('attachment_refs') or []
    try:
        guest_attachments = _mm_resolve_and_read_attachments(attachment_refs)
    except ValueError as exc:
        return Response({'error': str(exc)}, status=400)

    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings as django_settings
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_final,
            from_email=getattr(django_settings, 'DEFAULT_FROM_EMAIL', None),
            to=[guest.email],
        )
        msg.attach_alternative(html_final, "text/html")
        for fn, data, mt in guest_attachments:
            msg.attach(fn, data, mt)
        msg.send(fail_silently=False)
    except Exception as exc:
        logger.error("Ad-hoc-Mail an guest=%s fehlgeschlagen: %s", guest_id, exc)
        return Response({'error': f'Versand fehlgeschlagen: {exc}'}, status=502)

    notification_kind = request.data.get('notification_kind')
    if notification_kind == 'reschedule':
        from django.utils.dateparse import parse_datetime
        target_raw = request.data.get('target_start_at')
        target_start_at = parse_datetime(target_raw) if target_raw else guest.meeting.start_at
        guest.last_notified_start_at = target_start_at
        guest.save(update_fields=['last_notified_start_at'])
    elif notification_kind == 'cancel':
        guest.notified_cancelled = True
        guest.save(update_fields=['notified_cancelled'])

    return Response({'success': True})


@extend_schema(summary="Einladungs-Warteschlange: aktive Gaeste ohne Einladung", responses=MeetmeGuestSerializer(many=True))
@api_view(['GET'])
def api_invite_queue(request, meeting_id):
    meeting = get_object_or_404(MeetmeMeeting, id=meeting_id)
    guests = meeting.guests.filter(is_active=True, invited_at__isnull=True)
    return Response(MeetmeGuestSerializer(guests, many=True).data)


@extend_schema(
    summary="Einladungstext-Vorschau (Variablen bereits ausgefuellt)",
    parameters=[OpenApiParameter(name='template_identifier', type=str, required=True)],
)
@api_view(['GET'])
def api_invite_preview(request, guest_id):
    guest = get_object_or_404(MeetmeGuest, id=guest_id)
    meeting = guest.meeting
    template_identifier = request.query_params.get('template_identifier', '')
    if not template_identifier:
        return Response({'error': 'template_identifier erforderlich'}, status=400)
    from apps.abpe_meetme.email_helpers import build_meetme_variables
    from apps.abpe_email_studio.models import EmailTemplate, TemplateStatus
    from apps.abpe_email_studio.services.renderer import EmailRenderer
    tpl = EmailTemplate.objects.filter(identifier=template_identifier, status=TemplateStatus.ACTIVE).first()
    if not tpl:
        return Response({'error': f'Vorlage nicht gefunden: {template_identifier}'}, status=404)
    variables = build_meetme_variables(meeting, guest, request.user)
    renderer = EmailRenderer()
    subject = renderer.render_subject(tpl.subject, {**renderer._get_system_vars(), **variables})
    body = renderer.render_text(tpl, variables, request.user)
    return Response({'subject': subject, 'body': body})


@extend_schema(
    summary="Einladung an Gast senden (Einladungs-Assistent: Senden & weiter)",
    request={'application/json': {'type': 'object', 'properties': {
        'subject': {'type': 'string'}, 'body': {'type': 'string'},
    }}},
    responses=MeetmeGuestSerializer,
)
@api_view(['POST'])
def api_invite_send(request, guest_id):
    guest = get_object_or_404(MeetmeGuest, id=guest_id)
    subject = (request.data.get('subject') or '').strip()
    body = (request.data.get('body') or '').strip()
    if not subject or not body:
        return Response({'error': 'subject und body erforderlich'}, status=400)
    from django.core.mail import send_mail
    from django.conf import settings as django_settings
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(django_settings, 'DEFAULT_FROM_EMAIL', None),
            recipient_list=[guest.email],
            fail_silently=False,
        )
    except Exception as exc:
        logger.error("Einladung an guest=%s fehlgeschlagen: %s", guest_id, exc)
        return Response({'error': f'Versand fehlgeschlagen: {exc}'}, status=502)
    guest.invited_at = timezone.now()
    guest.save(update_fields=['invited_at'])
    return Response(MeetmeGuestSerializer(guest).data)


@extend_schema(
    summary="Meeting-bezogene Vorlagen-Vorschau mit echter Variablen-Substitution",
    parameters=[OpenApiParameter(name='template_id', type=int, required=True),
                OpenApiParameter(name='guest_id', type=int, required=False)],
)
@api_view(['GET'])
def api_meeting_render_preview(request, meeting_id):
    meeting = get_object_or_404(MeetmeMeeting, id=meeting_id)
    template_id = request.query_params.get('template_id')
    if not template_id:
        return Response({'error': 'template_id erforderlich'}, status=400)

    guest_id = request.query_params.get('guest_id')
    if guest_id:
        guest = get_object_or_404(MeetmeGuest, id=guest_id, meeting=meeting)
    else:
        guest = meeting.guests.filter(is_active=True).first()
    if not guest:
        return Response({'error': 'Kein Gast fuer Vorschau vorhanden'}, status=400)

    from apps.abpe_email_studio.models import EmailTemplate
    from apps.abpe_email_studio.services.renderer import EmailRenderer
    tpl = EmailTemplate.objects.filter(pk=template_id).first()
    if not tpl:
        return Response({'error': 'Vorlage nicht gefunden'}, status=404)

    from apps.abpe_meetme.email_helpers import build_meetme_variables
    variables = build_meetme_variables(meeting, guest, request.user)
    renderer = EmailRenderer()
    subject = renderer.render_subject(tpl.subject, {**renderer._get_system_vars(), **variables})
    html = renderer.render_html(tpl, variables, request.user)
    text = renderer.render_text(tpl, variables, request.user)
    return Response({'subject': subject, 'html': html, 'text': text})


@extend_schema(
    summary="Meeting verschieben - benachrichtigte Gaeste bekommen automatisch Terminaenderungs-Hinweis",
    request={'application/json': {'type': 'object', 'properties': {'new_start_at': {'type': 'string'}}}},
    responses={200: None},
)
@api_view(['POST'])
def api_meeting_reschedule(request, meeting_id):
    from django.utils.dateparse import parse_datetime
    meeting = get_object_or_404(MeetmeMeeting, id=meeting_id)

    new_start_raw = request.data.get('new_start_at')
    if not new_start_raw:
        return Response({'error': 'new_start_at erforderlich'}, status=400)

    new_start_at = parse_datetime(new_start_raw)
    if not new_start_at:
        return Response({'error': 'new_start_at ungueltiges Format'}, status=400)

    result = reminder_engine.reschedule_meeting(meeting, new_start_at)
    return Response({
        'meeting': MeetmeMeetingSerializer(meeting).data,
        'change_notice_count': result['change_notice_count'],
        'not_notified_guests': result['not_notified_guests'],
    })


@extend_schema(
    summary="Live-Vorschau (Text+HTML) - identische Logik wie beim tatsaechlichen Versand",
    request={'application/json': {'type': 'object', 'properties': {
        'body': {'type': 'string'}, 'signature_id': {'type': 'integer'},
    }}},
)
@api_view(['POST'])
def api_notify_preview(request):
    body = (request.data.get('body') or '').strip()
    action = request.data.get('action')
    text_final, html_final = _mm_build_final_bodies(body, request.data.get('signature_id'), action)
    return Response({'text': text_final, 'html': html_final})


@extend_schema(
    summary="Alle aktiven Gaeste eines Meetings informieren (Verschiebung/Absage), mit Duplikat-Schutz",
    request={'application/json': {'type': 'object', 'properties': {
        'notification_kind': {'type': 'string', 'enum': ['reschedule', 'cancel']},
        'subject': {'type': 'string'}, 'body': {'type': 'string'},
        'target_start_at': {'type': 'string'},
        'force': {'type': 'boolean'},
    }}},
    responses={200: None},
)
@api_view(['POST'])
def api_meeting_notify_bulk(request, meeting_id):
    from django.utils.dateparse import parse_datetime
    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings as django_settings

    meeting = get_object_or_404(MeetmeMeeting, id=meeting_id)
    notification_kind = request.data.get('notification_kind')
    if notification_kind not in ('reschedule', 'cancel'):
        return Response({'error': "notification_kind muss 'reschedule' oder 'cancel' sein"}, status=400)

    subject = (request.data.get('subject') or '').strip()
    body = (request.data.get('body') or '').strip()
    if not subject or not body:
        return Response({'error': 'subject und body erforderlich'}, status=400)

    force = bool(request.data.get('force'))
    text_final, html_final = _mm_build_final_bodies(body, request.data.get('signature_id'), notification_kind)

    attachment_refs = request.data.get('attachment_refs') or []
    try:
        shared_attachments = _mm_resolve_and_read_attachments(attachment_refs)
    except ValueError as exc:
        return Response({'error': str(exc)}, status=400)

    target_start_at = None
    if notification_kind == 'reschedule':
        target_raw = request.data.get('target_start_at')
        target_start_at = parse_datetime(target_raw) if target_raw else meeting.start_at

    sent, skipped, failed = [], [], []
    for guest in meeting.guests.filter(is_active=True):
        if not force:
            if notification_kind == 'reschedule' and guest.last_notified_start_at == target_start_at:
                skipped.append(guest.id)
                continue
            if notification_kind == 'cancel' and guest.notified_cancelled:
                skipped.append(guest.id)
                continue
        try:
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_final,
                from_email=getattr(django_settings, 'DEFAULT_FROM_EMAIL', None),
                to=[guest.email],
            )
            msg.attach_alternative(html_final, "text/html")
            for fn, data, mt in shared_attachments:
                msg.attach(fn, data, mt)
            msg.send(fail_silently=False)
        except Exception as exc:
            logger.error("Bulk-Mail an guest=%s fehlgeschlagen: %s", guest.id, exc)
            failed.append(guest.id)
            continue

        if notification_kind == 'reschedule':
            guest.last_notified_start_at = target_start_at
            guest.save(update_fields=['last_notified_start_at'])
        else:
            guest.notified_cancelled = True
            guest.save(update_fields=['notified_cancelled'])
        sent.append(guest.id)

    return Response({'sent': sent, 'skipped': skipped, 'failed': failed})
