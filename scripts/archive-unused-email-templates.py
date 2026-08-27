#!/usr/bin/env python
"""Ungenutzte E-Mail-Vorlagen archivieren — kein Hard-Delete.

Email Studio
  Archiv (ARCHIVED, sonst DRAFT):
    test, cv_generated_berater_copy
  Unangetastet:
    CRM, Intake/Pipeline, 7 Matching-Stage, MeetMe, inbox_anfrage_bestaetigung

Alte Parallel-Tabelle abpe_matching_workflow.EmailTemplate
  is_active=False (Django-Admin, nicht Email Studio).
  Matching-Versand läuft über Email Studio + /crm/api/email/send/.

Live:
  bash scripts/SAFE-archive-unused-email-templates.sh
"""
from django.db import transaction

KEEP_IDENTIFIERS = {
    # CRM
    "crm_berater_profilupdate",
    "crm_firmenprofil",
    "crm_manual_email",
    # Intake / Pipeline
    "cv_generated_berater",
    "pipeline_success",
    "pipeline_error",
    "upload_received",
    "upload_error",
    # Matching Kanban (Email Studio)
    "matching_outreach_wizard",
    "matching_followup_availability",
    "matching_present_to_client",
    "matching_interview_coord",
    "matching_placement_start",
    "matching_start_info",
    "matching_rejection",
    # Posteingang (git-only, falls schon auf Live)
    "inbox_anfrage_bestaetigung",
}

KEEP_PREFIXES = (
    "meetme_",
)

ARCHIVE_IDENTIFIERS = {
    "test",
    "cv_generated_berater_copy",
}


def _keep(ident: str) -> bool:
    ident = (ident or "").strip()
    if ident in KEEP_IDENTIFIERS:
        return True
    return any(ident.startswith(p) for p in KEEP_PREFIXES)


def _archive_status(TemplateStatus):
    if hasattr(TemplateStatus, "ARCHIVED"):
        return TemplateStatus.ARCHIVED, "ARCHIVED"
    return TemplateStatus.DRAFT, "DRAFT"


print("=== Email Studio — Bestand ===")
from apps.abpe_email_studio.models import EmailTemplate as EsTemplate, TemplateStatus

arch_status, arch_name = _archive_status(TemplateStatus)
print("Archiv-Status:", arch_name)

es_rows = list(EsTemplate.objects.all().order_by("identifier"))
for t in es_rows:
    ident = getattr(t, "identifier", "") or ""
    st = getattr(t, "status", "")
    flag = "KEEP" if _keep(ident) else ("ARCHIVE" if ident in ARCHIVE_IDENTIFIERS else "PRÜFEN")
    print(f"  [{flag:7}] pk={t.pk:4}  {st:12}  {ident:40}  {t.name}")

print()
print("=== Email Studio — Archivieren ===")
with transaction.atomic():
    n_es = 0
    for ident in sorted(ARCHIVE_IDENTIFIERS):
        qs = EsTemplate.objects.filter(identifier=ident)
        if not qs.exists():
            print(f"  SKIP  {ident}  (nicht vorhanden)")
            continue
        for t in qs:
            if _keep(ident):
                print(f"  SKIP  {ident}  pk={t.pk}  (steht auf Keep-Liste)")
                continue
            old = t.status
            t.status = arch_status
            t.save(update_fields=["status"])
            n_es += 1
            print(f"  {ident}  pk={t.pk}  {old} → {arch_name}")

print(f"Email Studio geändert: {n_es}")

print()
print("=== Email Studio — nicht auf Keep-Liste (unangetastet) ===")
unknown = [
    t for t in es_rows
    if not _keep(getattr(t, "identifier", "") or "")
    and (getattr(t, "identifier", "") or "") not in ARCHIVE_IDENTIFIERS
]
if not unknown:
    print("  (keine)")
else:
    for t in unknown:
        print(f"  pk={t.pk}  {t.status}  {t.identifier}  {t.name}")

print()
print("=== matching_workflow.EmailTemplate — deaktivieren ===")
try:
    from apps.abpe_matching_workflow.models import EmailTemplate as MwTemplate
except Exception as exc:
    print("  SKIP  Modell nicht ladbar:", exc)
else:
    with transaction.atomic():
        n_mw = 0
        for t in MwTemplate.objects.all().order_by("template_type", "name"):
            was = t.is_active
            if was:
                t.is_active = False
                t.save(update_fields=["is_active"])
                n_mw += 1
            print(
                f"  {'DEAKTIVIERT' if was else 'schon inaktiv':12}  "
                f"{t.template_type:24}  {t.name}"
            )
        print(f"matching_workflow geändert: {n_mw}")

print()
print("OK — Vorlagen archiviert/deaktiviert (kein Delete)")
