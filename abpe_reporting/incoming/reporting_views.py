"""Reporting dashboard API — in apps/abpe_crm/views.py einbinden oder importieren.

urls.py ergänzen (siehe reporting_urls_snippet.txt).
"""
from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.abpe_crm.models import (
    CrmAccount,
    CrmContact,
    CrmContactNote,
    CrmEmailAddress,
)
from apps.abpe_edms.models import CrmDocument


def _iso(dt):
    if not dt:
        return ''
    try:
        return dt.isoformat()
    except Exception:
        return str(dt)


def _last_sync(model, field='crm_synced_at'):
    try:
        val = model.objects.order_by(f'-{field}').values_list(field, flat=True).first()
        return _iso(val)
    except Exception:
        return ''


def _count_since(model, days=30):
    for field in ('date_entered', 'created_at', 'date_modified', 'crm_synced_at'):
        try:
            if not hasattr(model, field):
                continue
            since = timezone.now() - timedelta(days=days)
            return model.objects.filter(**{f'{field}__gte': since}).count()
        except Exception:
            continue
    return None


def _contacts_without_email():
    try:
        linked = (
            CrmEmailAddress.objects.filter(
                bean_relations__bean_module='Contacts',
                bean_relations__primary_address=True,
                invalid_email=False,
            )
            .values_list('bean_relations__bean_id', flat=True)
            .distinct()
        )
        return CrmContact.objects.exclude(crm_id__in=linked).count()
    except Exception:
        try:
            linked = (
                CrmEmailAddress.objects.filter(
                    bean_relations__bean_module='Contacts',
                    invalid_email=False,
                )
                .values_list('bean_relations__bean_id', flat=True)
                .distinct()
            )
            return CrmContact.objects.exclude(crm_id__in=linked).count()
        except Exception:
            return None


def _meetme_stats():
    try:
        from apps.abpe_meetme.models import MeetmeGuest, MeetmeMeeting, MeetmeReminderDelivery

        now = timezone.now()
        return {
            'meetings_total': MeetmeMeeting.objects.count(),
            'meetings_upcoming': MeetmeMeeting.objects.filter(
                start_at__gte=now,
            ).exclude(status='CANCELLED').count(),
            'meetings_cancelled': MeetmeMeeting.objects.filter(status='CANCELLED').count(),
            'guests_total': MeetmeGuest.objects.filter(is_active=True).count(),
            'reminders_open': MeetmeReminderDelivery.objects.filter(
                status__in=['PENDING', 'DUE'],
            ).count(),
        }
    except Exception:
        return {}


@login_required
@require_http_methods(['GET'])
def api_reporting_dashboard(request):
    """Aggregierte Reporting-Kennzahlen für das CRM-Dashboard."""
    contacts_total = CrmContact.objects.count()
    accounts_total = CrmAccount.objects.count()
    emails_total = CrmEmailAddress.objects.count()
    documents_total = CrmDocument.objects.count()
    notes_total = CrmContactNote.objects.count()

    emails_opt_out = CrmEmailAddress.objects.filter(opt_out=True).count()
    emails_invalid = CrmEmailAddress.objects.filter(invalid_email=True).count()
    emails_active = CrmEmailAddress.objects.filter(
        opt_out=False,
        invalid_email=False,
    ).count()
    emails_linked_contacts = CrmEmailAddress.objects.filter(
        bean_relations__bean_module='Contacts',
        bean_relations__primary_address=True,
    ).distinct().count()

    contacts_no_email = _contacts_without_email()
    last_sync = _last_sync(CrmContact)

    sync_ok = bool(last_sync)
    if contacts_total and not last_sync:
        sync_status = 'unknown'
    elif sync_ok:
        sync_status = 'ok'
    else:
        sync_status = 'empty'

    payload = {
        'generated_at': _iso(timezone.now()),
        'sync': {
            'status': sync_status,
            'last_sync': last_sync,
            'last_contact_sync': last_sync,
            'last_account_sync': _last_sync(CrmAccount),
        },
        'totals': {
            'contacts': contacts_total,
            'accounts': accounts_total,
            'emails': emails_total,
            'documents': documents_total,
            'notes': notes_total,
        },
        'growth_30d': {
            'contacts': _count_since(CrmContact, 30),
            'accounts': _count_since(CrmAccount, 30),
            'documents': _count_since(CrmDocument, 30),
        },
        'quality': {
            'contacts_without_email': contacts_no_email,
            'emails_opt_out': emails_opt_out,
            'emails_invalid': emails_invalid,
            'emails_active': emails_active,
            'emails_linked_contacts': emails_linked_contacts,
            'documents_zero': documents_total == 0,
        },
        'meetme': _meetme_stats(),
    }
    return JsonResponse(payload)


@login_required
@require_http_methods(['POST'])
def api_reporting_sync_start(request):
    """Sync-Anstoß — Platzhalter bis ein Sync-Job angebunden ist."""
    return JsonResponse({
        'ok': False,
        'message': (
            'Automatischer Voll-Sync ist noch nicht angebunden. '
            'Datenstand wird live aus der CRM-Datenbank gelesen.'
        ),
    }, status=501)
