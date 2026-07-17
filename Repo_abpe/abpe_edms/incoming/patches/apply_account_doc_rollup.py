#!/usr/bin/env python3
"""
Idempotentes Patch-Script: Firma-Dokumente inkl. Ansprechpartner.

Deploy owner_rollup.py nach apps/abpe_edms/, dann:

  python Repo_abpe/abpe_edms/incoming/patches/apply_account_doc_rollup.py
  supervisorctl restart abpe-django

Betroffene Endpunkte:
  GET /edms/api/akte/account/<crm_id>/     — Dokumente Firma + APs
  GET /edms/api/person/<crm_id>/mails/     — Mails Firma + APs (wenn account)
  GET /edms/api/search/?owner=<crm_id>     — ES/DB-Suche rollup
  GET /crm/api/kunden/<crm_id>/            — Dokumente-Tab Vorschau
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(os.environ.get("ABPE_BACKEND", "/opt/abpe/backend"))
EDMS_VIEWS = BACKEND / "apps/abpe_edms/views.py"
CRM_VIEWS = BACKEND / "apps/abpe_crm/views.py"
ROLLUP = BACKEND / "apps/abpe_edms/owner_rollup.py"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _write(p: Path, text: str) -> None:
    p.write_text(text, encoding="utf-8")


def patch_edms_views() -> bool:
    text = _read(EDMS_VIEWS)
    changed = False

    # ── api_akte: account + Ansprechpartner ──
    old_akte = """    qs = _base_qs(include_trash=True).filter(
        owners__owner_crm_id=crm_id,
        owners__owner_type=owner_type,
    ).distinct()"""
    new_akte = """    from apps.abpe_edms.owner_rollup import document_filter_for_entity
    qs = _base_qs(include_trash=True).filter(
        document_filter_for_entity(crm_id, owner_type)
    ).distinct()"""
    if "document_filter_for_entity" not in text:
        if old_akte not in text:
            print("FEHLER: api_akte-Anchor nicht gefunden in edms/views.py", file=sys.stderr)
            sys.exit(1)
        text = text.replace(old_akte, new_akte, 1)
        changed = True
        print("OK: api_akte — Firma + Ansprechpartner")

    # ── _search_es: owner rollup ──
    old_es = """    owner = request.GET.get("owner")
    if owner:
        s = s.filter("term", owner_crm_ids=owner)"""
    new_es = """    owner = request.GET.get("owner")
    if owner:
        from apps.abpe_edms.owner_rollup import es_owner_crm_ids
        _owner_ids = es_owner_crm_ids(owner)
        if len(_owner_ids) == 1:
            s = s.filter("term", owner_crm_ids=_owner_ids[0])
        else:
            s = s.filter("terms", owner_crm_ids=_owner_ids)"""
    if "es_owner_crm_ids" not in text:
        if old_es not in text:
            print("WARN: _search_es owner-Anchor nicht gefunden", file=sys.stderr)
        else:
            text = text.replace(old_es, new_es, 1)
            changed = True
            print("OK: _search_es — owner rollup")

    # ── _search_db: owner rollup ──
    old_db = """    owner = request.GET.get("owner")
    owner_type = request.GET.get("owner_type")
    if owner:
        of = Q(owners__owner_crm_id=owner)
        if owner_type:
            of &= Q(owners__owner_type=owner_type)
        qs = qs.filter(of)"""
    new_db = """    owner = request.GET.get("owner")
    owner_type = request.GET.get("owner_type")
    if owner:
        from apps.abpe_edms.owner_rollup import document_filter_for_owner_search
        qs = qs.filter(document_filter_for_owner_search(owner, owner_type))"""
    if "document_filter_for_owner_search" not in text:
        if old_db not in text:
            print("WARN: _search_db owner-Anchor nicht gefunden", file=sys.stderr)
        else:
            text = text.replace(old_db, new_db, 1)
            changed = True
            print("OK: _search_db — owner rollup")

    # ── api_person_mails: Firma + AP E-Mails ──
    old_mails = """    # 1) E-Mail-Adressen der Person holen
    rels = CrmEmailAddrBeanRel.objects.filter(bean_id=crm_id)
    addr_ids = [r.email_address_id for r in rels]
    addresses = list(
        CrmEmailAddress.objects
        .filter(crm_id__in=addr_ids)
        .exclude(invalid_email=True)
        .values_list("email_address", flat=True)
    )"""
    new_mails = """    # 1) E-Mail-Adressen — Firma inkl. Ansprechpartner, Person nur eigene
    from apps.abpe_edms.owner_rollup import related_crm_ids_for_entity, email_addresses_for_crm_ids
    _mail_crm_ids = related_crm_ids_for_entity(crm_id)
    addresses = email_addresses_for_crm_ids(_mail_crm_ids)"""
    if "email_addresses_for_crm_ids" not in text:
        if old_mails not in text:
            print("FEHLER: api_person_mails-Anchor nicht gefunden", file=sys.stderr)
            sys.exit(1)
        text = text.replace(old_mails, new_mails, 1)
        changed = True
        print("OK: api_person_mails — Firma + Ansprechpartner E-Mails")

    if changed:
        _write(EDMS_VIEWS, text)
    else:
        print("OK: edms/views.py — Rollup bereits angewendet")
    return changed


def patch_crm_kunden_detail() -> bool:
    text = _read(CRM_VIEWS)
    old = """    from apps.abpe_edms.models import CrmDocument as _EdmsCrmDocument, OwnerType as _EdmsOwnerType
    _docs_qs = _EdmsCrmDocument.objects.filter(
        owners__owner_crm_id=crm_id,
        owners__owner_type=_EdmsOwnerType.ACCOUNT,
        in_trash=False,
    ).select_related('doctype').order_by('-document_date', '-created_at').distinct()[:20]"""
    new = """    from apps.abpe_edms.models import CrmDocument as _EdmsCrmDocument
    from apps.abpe_edms.owner_rollup import related_crm_ids_for_entity
    _rollup_ids = related_crm_ids_for_entity(crm_id)
    _docs_qs = _EdmsCrmDocument.objects.filter(
        owners__owner_crm_id__in=_rollup_ids,
        in_trash=False,
    ).select_related('doctype').order_by('-document_date', '-created_at').distinct()[:20]"""
    if "related_crm_ids_for_entity" in text and "_rollup_ids" in text:
        print("OK: crm/views.py api_kunden_detail — Rollup bereits angewendet")
        return False
    if old not in text:
        print("WARN: api_kunden_detail Dokumente-Anchor nicht gefunden (evtl. anderer Stand)", file=sys.stderr)
        return False
    _write(CRM_VIEWS, text.replace(old, new, 1))
    print("OK: api_kunden_detail — Dokumente Firma + Ansprechpartner")
    return True


def main() -> None:
    repo_rollup = Path(__file__).resolve().parents[1] / "owner_rollup.py"
    if not repo_rollup.is_file():
        print(f"FEHLER: {repo_rollup} fehlt", file=sys.stderr)
        sys.exit(1)
    if not EDMS_VIEWS.is_file():
        print(f"FEHLER: {EDMS_VIEWS} nicht gefunden", file=sys.stderr)
        sys.exit(1)

    ROLLUP.parent.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copy2(repo_rollup, ROLLUP)
    print(f"OK: owner_rollup.py → {ROLLUP}")

    patch_edms_views()
    if CRM_VIEWS.is_file():
        patch_crm_kunden_detail()
    else:
        print(f"WARN: {CRM_VIEWS} nicht gefunden — Kunden-Tab übersprungen")

    print("")
    print("Danach: supervisorctl restart abpe-django")


if __name__ == "__main__":
    main()
