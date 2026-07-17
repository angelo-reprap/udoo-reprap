"""
EDMS Owner-Rollup: Firma + Ansprechpartner zusammenführen.

Firma (account): Dokumente/Mails der Firma UND aller verknüpften Ansprechpartner.
Person (contact): nur die eigene Person (unverändert).
"""
from __future__ import annotations

from django.db.models import Q

from apps.abpe_crm.models import (
    CrmAccount,
    CrmAccountContacts,
    CrmEmailAddrBeanRel,
    CrmEmailAddress,
)


def is_account_crm_id(crm_id: str) -> bool:
    return bool(crm_id) and CrmAccount.objects.filter(crm_id=crm_id).exists()


def account_contact_crm_ids(account_crm_id: str) -> list[str]:
    """crm_ids aller Ansprechpartner (Contacts) einer Firma."""
    return list(
        CrmAccountContacts.objects.filter(account_id=account_crm_id)
        .exclude(contact_id__isnull=True)
        .values_list("contact_id", flat=True)
        .distinct()
    )


def related_crm_ids_for_entity(crm_id: str) -> list[str]:
    """
    Firma → [account_id, contact_id, …]
    Person → [contact_id]
    """
    if not crm_id:
        return []
    if is_account_crm_id(crm_id):
        out: list[str] = []
        seen: set[str] = set()
        for cid in [crm_id, *account_contact_crm_ids(crm_id)]:
            if cid and cid not in seen:
                seen.add(cid)
                out.append(cid)
        return out
    return [crm_id]


def es_owner_crm_ids(owner_crm_id: str) -> list[str]:
    """CRM-IDs für ES-Filter owner_crm_ids (terms)."""
    return related_crm_ids_for_entity(owner_crm_id)


def email_addresses_for_crm_ids(crm_ids: list[str]) -> list[str]:
    """Alle gültigen E-Mail-Adressen zu einer oder mehreren CRM-Entitäten."""
    if not crm_ids:
        return []
    rels = CrmEmailAddrBeanRel.objects.filter(bean_id__in=crm_ids)
    addr_ids = list(rels.values_list("email_address_id", flat=True).distinct())
    if not addr_ids:
        return []
    return list(
        CrmEmailAddress.objects.filter(crm_id__in=addr_ids)
        .exclude(invalid_email=True)
        .exclude(email_address__isnull=True)
        .exclude(email_address="")
        .values_list("email_address", flat=True)
        .distinct()
    )


def document_filter_for_entity(crm_id: str, owner_type: str) -> Q:
    """Q-Filter für api_akte — account inkl. Ansprechpartner."""
    from apps.abpe_edms.models import OwnerType

    if owner_type == OwnerType.ACCOUNT:
        ids = related_crm_ids_for_entity(crm_id)
        return Q(owners__owner_crm_id__in=ids)
    return Q(owners__owner_crm_id=crm_id, owners__owner_type=owner_type)


def document_filter_for_owner_search(owner_crm_id: str, owner_type: str | None = None) -> Q:
    """Q-Filter für Suche (?owner=) — account auto-rollt hoch."""
    if owner_type == "account" or (not owner_type and is_account_crm_id(owner_crm_id)):
        return Q(owners__owner_crm_id__in=related_crm_ids_for_entity(owner_crm_id))
    filt = Q(owners__owner_crm_id=owner_crm_id)
    if owner_type:
        filt &= Q(owners__owner_type=owner_type)
    return filt
