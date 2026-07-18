"""Berechnung der Faelligkeit einzelner Erinnerungen und Abgleich
mit dem abpe_scheduler (Anlegen/Aktualisieren/Canceln von SchedulerJobs)."""
import datetime as dt_module
import logging

from django.utils import timezone

from . import scheduler_client
from .models import MeetmeReminderDelivery

logger = logging.getLogger(__name__)


def compute_scheduled_at(meeting, rule):
    """Berechnet den Faelligkeitszeitpunkt einer Erinnerungsregel fuer ein Meeting."""
    if rule.offset_unit == 'DAYS':
        target_date = (meeting.start_at - dt_module.timedelta(days=rule.offset_value)).date()
        time_part = rule.time_of_day or dt_module.time(9, 0)
        naive = dt_module.datetime.combine(target_date, time_part)
        if timezone.is_naive(naive):
            return timezone.make_aware(naive)
        return naive
    elif rule.offset_unit == 'HOURS':
        return meeting.start_at - dt_module.timedelta(hours=rule.offset_value)
    else:  # MINUTES
        return meeting.start_at - dt_module.timedelta(minutes=rule.offset_value)


def sync_reminder_deliveries(meeting):
    """Materialisiert MeetmeReminderDelivery-Zeilen fuer alle aktiven Gaeste
    und alle Regeln eines Meetings, und registriert je einen SchedulerJob
    (PUSH-Modus) ueber die abpe_scheduler-API."""
    rules = meeting.reminder_rules.all()
    active_guests = meeting.guests.filter(is_active=True)

    for rule in rules:
        scheduled_at = compute_scheduled_at(meeting, rule)

        if rule.guest_id:
            guests_for_rule = [rule.guest] if rule.guest.is_active else []
        else:
            guests_for_rule = list(active_guests)

        for guest in guests_for_rule:
            delivery, created = MeetmeReminderDelivery.objects.update_or_create(
                rule=rule, guest=guest,
                defaults={'scheduled_at': scheduled_at},
            )
            if not created and delivery.status in ('SENT', 'SKIPPED'):
                # Bereits erledigte Erinnerungen werden nicht neu terminiert
                continue

            job_key = f"meetme-delivery-{delivery.id}"
            try:
                job = scheduler_client.upsert_job(
                    owner_type='reminder_delivery',
                    owner_ref=str(delivery.id),
                    job_key=job_key,
                    schedule_type='ONCE',
                    run_at=scheduled_at,
                    callback_url=scheduler_client.build_callback_url('reminder-due'),
                    payload={'delivery_id': delivery.id},
                )
                delivery.scheduler_job_id = job.get('id')
                delivery.save(update_fields=['scheduler_job_id'])
            except scheduler_client.SchedulerClientError as exc:
                logger.warning("Konnte SchedulerJob fuer delivery=%s nicht anlegen: %s", delivery.id, exc)


def cancel_reminder_deliveries(meeting):
    """Storniert alle offenen Erinnerungen eines Meetings (z. B. bei Absage)."""
    deliveries = MeetmeReminderDelivery.objects.filter(
        rule__meeting=meeting
    ).exclude(status__in=['SENT', 'SKIPPED'])

    for delivery in deliveries:
        if delivery.scheduler_job_id:
            try:
                scheduler_client.cancel_job(delivery.scheduler_job_id)
            except scheduler_client.SchedulerClientError as exc:
                logger.warning("Konnte SchedulerJob %s nicht canceln: %s", delivery.scheduler_job_id, exc)
        delivery.status = 'SKIPPED'
        delivery.save(update_fields=['status'])


def reschedule_meeting(meeting, new_start_at):
    """Verschiebt ein Meeting auf einen neuen Zeitpunkt.

    Fuer Gaeste, die bereits mindestens eine gesendete Erinnerung (status=SENT)
    hatten, wird automatisch eine 'Termin hat sich geaendert'-Delivery angelegt
    (is_change_notice=True), die sofort im Sende-Assistenten auftaucht.

    Gaeste ohne jede gesendete E-Mail werden separat zurueckgegeben, damit
    das Frontend sie als 'bitte anrufen'-Liste anzeigen kann.

    Bereits eingeplante, noch nicht gesendete Erinnerungen (PENDING/DUE)
    werden auf Basis der neuen Zeit neu berechnet (ueber sync_reminder_deliveries).
    """
    from .models import MeetmeReminderRule, MeetmeReminderDelivery

    old_start_at = meeting.start_at
    meeting.start_at = new_start_at
    meeting.save(update_fields=['start_at'])

    already_notified_guest_ids = set(
        MeetmeReminderDelivery.objects.filter(
            rule__meeting=meeting, status='SENT'
        ).values_list('guest_id', flat=True)
    )

    active_guests = list(meeting.guests.filter(is_active=True))
    not_notified = [g for g in active_guests if g.id not in already_notified_guest_ids]

    change_notice_rule, _ = MeetmeReminderRule.objects.get_or_create(
        meeting=meeting, offset_value=0, offset_unit='MINUTES', is_change_notice=True,
        defaults={'mode': 'MANUAL'},
    )

    change_deliveries = []
    for guest in active_guests:
        if guest.id not in already_notified_guest_ids:
            continue
        delivery = MeetmeReminderDelivery.objects.create(
            rule=change_notice_rule, guest=guest,
            scheduled_at=timezone.now(),
            status='DUE',
            subject=f"Terminänderung: {meeting.title}",
            body=(
                f"Hallo {guest.name},\n\n"
                f"der Termin \"{meeting.title}\" wurde verschoben:\n"
                f"Bisher: {old_start_at.strftime('%d.%m.%Y, %H:%M')} Uhr\n"
                f"Neu: {new_start_at.strftime('%d.%m.%Y, %H:%M')} Uhr\n\n"
                f"Viele Grüße"
            ),
        )
        change_deliveries.append(delivery)

    # Noch nicht gesendete, normale Erinnerungen an die neue Zeit anpassen
    sync_reminder_deliveries(meeting)

    return {
        'change_notice_count': len(change_deliveries),
        'not_notified_guests': [{'id': g.id, 'name': g.name, 'phone': g.phone, 'contact_crm_id': g.contact_crm_id} for g in not_notified],
    }
