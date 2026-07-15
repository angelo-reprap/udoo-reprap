"""Reporting dashboard API — eigenständiges Modul für apps/abpe_crm/reporting_api.py"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)


def _iso(dt):
    if not dt:
        return ''
    try:
        return dt.isoformat()
    except Exception:
        return str(dt)


def _safe_count(qs_or_model, default=0):
    try:
        if hasattr(qs_or_model, 'count'):
            return qs_or_model.count()
        return default
    except Exception as exc:
        logger.warning('reporting count failed: %s', exc)
        return default


def _last_sync(model, field='crm_synced_at'):
    try:
        val = model.objects.order_by(f'-{field}').values_list(field, flat=True).first()
        return _iso(val)
    except Exception as exc:
        logger.warning('reporting last_sync failed for %s.%s: %s', model, field, exc)
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


def _contacts_without_email(CrmContact, CrmEmailAddress):
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
        except Exception as exc:
            logger.warning('reporting contacts_without_email failed: %s', exc)
            return None


def _email_quality(CrmEmailAddress):
    out = {
        'emails_opt_out': None,
        'emails_invalid': None,
        'emails_active': None,
        'emails_linked_contacts': None,
    }
    try:
        out['emails_opt_out'] = _safe_count(CrmEmailAddress.objects.filter(opt_out=True))
        out['emails_invalid'] = _safe_count(CrmEmailAddress.objects.filter(invalid_email=True))
        out['emails_active'] = _safe_count(
            CrmEmailAddress.objects.filter(opt_out=False, invalid_email=False),
        )
    except Exception as exc:
        logger.warning('reporting email counts failed: %s', exc)
    try:
        out['emails_linked_contacts'] = _safe_count(
            CrmEmailAddress.objects.filter(
                bean_relations__bean_module='Contacts',
                bean_relations__primary_address=True,
            ).distinct(),
        )
    except Exception as exc:
        logger.warning('reporting emails_linked_contacts failed: %s', exc)
    return out


def _meetme_stats():
    try:
        from apps.abpe_meetme.models import MeetmeGuest, MeetmeMeeting, MeetmeReminderDelivery

        now = timezone.now()
        return {
            'meetings_total': _safe_count(MeetmeMeeting.objects.all()),
            'meetings_upcoming': _safe_count(
                MeetmeMeeting.objects.filter(start_at__gte=now).exclude(status='CANCELLED'),
            ),
            'meetings_cancelled': _safe_count(
                MeetmeMeeting.objects.filter(status='CANCELLED'),
            ),
            'guests_total': _safe_count(MeetmeGuest.objects.filter(is_active=True)),
            'reminders_open': _safe_count(
                MeetmeReminderDelivery.objects.filter(status__in=['PENDING', 'DUE']),
            ),
        }
    except Exception as exc:
        logger.warning('reporting meetme stats failed: %s', exc)
        return {}


@login_required
@require_http_methods(['GET'])
def api_reporting_dashboard(request):
    """Aggregierte Reporting-Kennzahlen für das CRM-Dashboard."""
    errors = []
    try:
        from apps.abpe_crm.models import (
            CrmAccount,
            CrmContact,
            CrmContactNote,
            CrmEmailAddress,
        )
    except Exception as exc:
        logger.exception('reporting imports failed')
        return JsonResponse({'error': str(exc)}, status=500)

    CrmDocument = None
    try:
        from apps.abpe_edms.models import CrmDocument
    except Exception as exc:
        errors.append(f'CrmDocument: {exc}')

    contacts_total = _safe_count(CrmContact.objects.all())
    accounts_total = _safe_count(CrmAccount.objects.all())
    emails_total = _safe_count(CrmEmailAddress.objects.all())
    documents_total = _safe_count(CrmDocument.objects.all()) if CrmDocument else 0
    notes_total = _safe_count(CrmContactNote.objects.all())

    email_q = _email_quality(CrmEmailAddress)
    contacts_no_email = _contacts_without_email(CrmContact, CrmEmailAddress)
    last_sync = _last_sync(CrmContact)

    if contacts_total and not last_sync:
        sync_status = 'unknown'
    elif last_sync:
        sync_status = 'ok'
    else:
        sync_status = 'empty'

    growth = {'contacts': None, 'accounts': None, 'documents': None}
    try:
        growth['contacts'] = _count_since(CrmContact, 30)
        growth['accounts'] = _count_since(CrmAccount, 30)
        if CrmDocument:
            growth['documents'] = _count_since(CrmDocument, 30)
    except Exception as exc:
        errors.append(f'growth: {exc}')

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
        'growth_30d': growth,
        'quality': {
            'contacts_without_email': contacts_no_email,
            'documents_zero': documents_total == 0,
            **email_q,
        },
        'meetme': _meetme_stats(),
    }
    if errors:
        payload['warnings'] = errors
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
