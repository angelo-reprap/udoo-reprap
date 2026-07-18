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


# ========== Meetings ==========

@extend_schema(summary="Meetings auflisten", responses=MeetmeMeetingSerializer(many=True))
@api_view(['GET'])
def api_meeting_list(request):
    qs = MeetmeMeeting.objects.all()
    status_filter = request.query_params.get('status')
    if status_filter:
        qs = qs.filter(status=status_filter)
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
        'subject': {'type': 'string'}, 'body': {'type': 'string'}}}},
    responses={200: None},
)
@api_view(['POST'])
def api_guest_send_adhoc(request, guest_id):
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
        logger.error("Ad-hoc-Mail an guest=%s fehlgeschlagen: %s", guest_id, exc)
        return Response({'error': f'Versand fehlgeschlagen: {exc}'}, status=502)

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
