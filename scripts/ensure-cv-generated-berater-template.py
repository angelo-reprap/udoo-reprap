#!/usr/bin/env python
"""Upsert Email-Studio-Vorlage cv_generated_berater.

Kein Portal-Link / kein Button (WAN→LAN zu).
Text sagt: PDF liegt als Anhang bei.

Live:
  cd /opt/abpe/backend
  git -C /mnt/public/udoo-reprap fetch origin cursor/crm-profilupdate-text-ee01
  python manage.py shell < <(
    git -C /mnt/public/udoo-reprap show origin/cursor/crm-profilupdate-text-ee01:scripts/ensure-cv-generated-berater-template.py
  )
"""
from apps.abpe_email_studio.models import EmailTemplate, TemplateStatus, SenderMode

IDENT = "cv_generated_berater"

_FONT = (
    "font-family:Arial,sans-serif;font-size:14px;line-height:1.5;"
    "color:#333333;"
)
_HEADER = "{{block:abcona_header_blau}}"
_LABEL = "{{block:label_bestaetigt}}"
_SIGN = "{{block:signature}}"


def _p(inner: str) -> str:
    return f'<p style="{_FONT}margin:0 0 12px 0;">{inner}</p>'


HTML = "\n".join([
    _HEADER,
    _LABEL,
    _p("Guten Tag {name},"),
    _p("Ihr Berater-Profil ist fertig. Das PDF liegt als Anhang bei."),
    _p("Version: {cv_version} &nbsp;·&nbsp; Erstellt am: {created_date}"),
    _SIGN,
]) + "\n"

TEXT = """Guten Tag {name},

Ihr Berater-Profil ist fertig. Das PDF liegt als Anhang bei.

Version: {cv_version} · Erstellt am: {created_date}

Mit freundlichen Grüßen
"""

defaults = {
    "name": "CV fertig — Berater",
    "subject": "Ihr Berater-Profil ist fertig — {name}",
    "html_body": HTML.strip(),
    "text_body": TEXT.strip(),
    "status": TemplateStatus.ACTIVE,
    "sender_mode": SenderMode.USER,
    "include_signature": True,
    "description": "CV fertig an den Berater. Kein Portal-Link. PDF als Anhang (cv_pdf_path / lokale Datei).",
}
try:
    from apps.abpe_email_studio.models import SignatureMode
    defaults["signature_mode"] = SignatureMode.USER
except Exception:
    pass
try:
    from apps.abpe_email_studio.models import AppScope
    if hasattr(AppScope, "INTAKE"):
        defaults["app_scope"] = AppScope.INTAKE
    elif hasattr(AppScope, "GENERAL"):
        defaults["app_scope"] = AppScope.GENERAL
except Exception:
    pass

field_names = {f.name for f in EmailTemplate._meta.get_fields()}
defaults = {k: v for k, v in defaults.items() if k in field_names}

tpl, created = EmailTemplate.objects.update_or_create(
    identifier=IDENT, defaults=defaults,
)
print(("CREATED" if created else "UPDATED"), IDENT, "pk=", tpl.pk, "|", tpl.name)
print("OK — cv_generated_berater (PDF-Anhang, ohne Link)")
