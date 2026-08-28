#!/usr/bin/env python
"""Upsert Email-Studio-Vorlage crm_manual_email.

Hülle für freie CRM-Mails: {subject} + {body}.
Kein steifer Schluss — Gruß in {{block:signature}}.
Beim Versand setzt Compose subject/body/name.

Live (ucs5):
  cd /opt/abpe/backend
  git -C /mnt/public/udoo-reprap fetch origin cursor/crm-profilupdate-text-ee01
  python manage.py shell < <(
    git -C /mnt/public/udoo-reprap show origin/cursor/crm-profilupdate-text-ee01:scripts/ensure-crm-manual-email-template.py
  )
"""
from apps.abpe_email_studio.models import EmailTemplate, TemplateStatus, SenderMode

IDENT = "crm_manual_email"

_FONT = (
    "font-family:Arial,sans-serif;font-size:14px;line-height:1.5;"
    "color:#333333;"
)
_HEADER = "{{block:abcona_header_blau}}"
_SIGN = "{{block:signature}}"


def _p(inner: str) -> str:
    return f'<p style="{_FONT}margin:0 0 12px 0;">{inner}</p>'


HTML = "\n".join([
    _HEADER,
    _p("Guten Tag {name},"),
    f'<div style="{_FONT}margin:0 0 12px 0;">{{body}}</div>',
    _SIGN,
]) + "\n"

TEXT = """Guten Tag {name},

{body}

Mit freundlichen Grüßen
"""

defaults = {
    "name": "CRM — Manuelle E-Mail",
    "subject": "{subject}",
    "html_body": HTML.strip(),
    "text_body": TEXT.strip(),
    "status": TemplateStatus.ACTIVE,
    "sender_mode": SenderMode.USER,
    "include_signature": True,
    "description": "CRM freie Mail: {subject}/{body}. Layout wie Matching, Schluss über Signatur.",
}
try:
    from apps.abpe_email_studio.models import SignatureMode
    defaults["signature_mode"] = SignatureMode.USER
except Exception:
    pass
try:
    from apps.abpe_email_studio.models import AppScope
    if hasattr(AppScope, "CRM"):
        defaults["app_scope"] = AppScope.CRM
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
print("OK — crm_manual_email (Hülle / ohne steifen Schluss)")
