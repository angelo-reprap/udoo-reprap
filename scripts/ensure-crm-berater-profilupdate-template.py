#!/usr/bin/env python
"""Upsert Email-Studio-Vorlage crm_berater_profilupdate.

Layout wie Matching: Header blau → Anrede → Inhalt → Signatur (Composer).
Kein Gruß im Body — der steht in {{block:signature}}.

Live (ucs5), Datei von origin:
  cd /opt/abpe/backend
  git -C /mnt/public/udoo-reprap fetch origin cursor/crm-profilupdate-text-ee01
  python manage.py shell < <(
    git -C /mnt/public/udoo-reprap show origin/cursor/crm-profilupdate-text-ee01:scripts/ensure-crm-berater-profilupdate-template.py
  )
"""
from apps.abpe_email_studio.models import EmailTemplate, TemplateStatus, SenderMode

IDENT = "crm_berater_profilupdate"

_FONT = (
    "font-family:Arial,sans-serif;font-size:14px;line-height:1.5;"
    "color:#333333;"
)
_HEADER = "{{block:abcona_header_blau}}"
_SIGN = "{{block:signature}}"


def _p(inner: str) -> str:
    return f'<p style="{_FONT}margin:0 0 12px 0;">{inner}</p>'


def _ul(items: list[str]) -> str:
    lis = "".join(
        f'<li style="{_FONT}margin:0 0 4px 0;">{item}</li>' for item in items
    )
    return f'<ul style="margin:0 0 14px 18px;padding:0;">{lis}</ul>'


HTML = "\n".join([
    _HEADER,
    _p("Hallo {first_name},"),
    _p(
        "kurz zu Ihrem Profil: wir schauen gerade, was bei uns passt — "
        "und wollten hören, wo Sie stehen."
    ),
    _p("Drei kurze Fragen:"),
    _ul([
        "Sind Sie aktuell oder bald wieder verfügbar?",
        "Ab wann — und in welchem Umfang?",
        "Hat sich bei Schwerpunkten oder Konditionen etwas geändert?",
    ]),
    _p("Ein aktuelles CV als PDF an {sender_email} hilft uns. Muss aber nicht."),
    _p("Wir freuen uns über eine kurze Rückmeldung."),
    _SIGN,
]) + "\n"

TEXT = """Hallo {first_name},

kurz zu Ihrem Profil: wir schauen gerade, was bei uns passt — und wollten hören, wo Sie stehen.

Drei kurze Fragen:
- Sind Sie aktuell oder bald wieder verfügbar?
- Ab wann — und in welchem Umfang?
- Hat sich bei Schwerpunkten oder Konditionen etwas geändert?

Ein aktuelles CV als PDF an {sender_email} hilft uns. Muss aber nicht.

Wir freuen uns über eine kurze Rückmeldung.

Mit freundlichen Grüßen
"""

defaults = {
    "name": "CRM — Berater Profilupdate",
    "subject": "Kurz nachgefragt — Ihr Profil",
    "html_body": HTML.strip(),
    "text_body": TEXT.strip(),
    "status": TemplateStatus.ACTIVE,
    "sender_mode": SenderMode.USER,
    "include_signature": True,
    "description": "CRM Berater: Verfügbarkeit / Profil-Update. Layout wie Matching, Ton locker.",
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
print("OK — crm_berater_profilupdate (Ton locker)")
