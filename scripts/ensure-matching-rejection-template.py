#!/usr/bin/env python
"""Upsert nur matching_rejection — empathischer, mit Erlaubnis für Folgeanfragen.

Kein steifer Schluss. Signatur übernimmt den Gruß.
Kein Firmenname.

Live:
  cd /opt/abpe/backend
  git -C /mnt/public/udoo-reprap fetch origin cursor/crm-profilupdate-text-ee01
  python manage.py shell < <(
    git -C /mnt/public/udoo-reprap show origin/cursor/crm-profilupdate-text-ee01:scripts/ensure-matching-rejection-template.py
  )
"""
from apps.abpe_email_studio.models import EmailTemplate, TemplateStatus, SenderMode

IDENT = "matching_rejection"

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
    _p("Guten Tag {first_name},"),
    _p("vielen Dank für Ihr Interesse an <strong>{project}</strong> "
       "und für die Zeit, die Sie uns gegeben haben."),
    _p("Es tut uns leid: diesmal hat es nicht gepasst. "
       "Die Auswahl ist anders ausgefallen — das bedauern wir. "
       "Das sagt nichts über Ihr Profil; oft entscheiden Zeitpunkt, "
       "Rahmen oder ein sehr spezieller Schwerpunkt."),
    _p("Wenn Sie einverstanden sind, kommen wir wieder auf Sie zu, "
       "sobald eine Anfrage wirklich zu Ihnen passt. "
       "Weitere Anfragen senden wir nur mit Ihrer Erlaubnis."),
    _p("Dürfen wir Sie bei passenden Themen wieder ansprechen? "
       "Eine kurze Rückmeldung reicht."),
    _SIGN,
]) + "\n"

TEXT = """Guten Tag {first_name},

vielen Dank für Ihr Interesse an {project} und für die Zeit, die Sie uns gegeben haben.

Es tut uns leid: diesmal hat es nicht gepasst. Die Auswahl ist anders ausgefallen — das bedauern wir. Das sagt nichts über Ihr Profil; oft entscheiden Zeitpunkt, Rahmen oder ein sehr spezieller Schwerpunkt.

Wenn Sie einverstanden sind, kommen wir wieder auf Sie zu, sobald eine Anfrage wirklich zu Ihnen passt. Weitere Anfragen senden wir nur mit Ihrer Erlaubnis.

Dürfen wir Sie bei passenden Themen wieder ansprechen? Eine kurze Rückmeldung reicht.

Mit freundlichen Grüßen
"""

defaults = {
    "name": "Matching — Absage",
    "subject": "Rückmeldung zur Anfrage {project}",
    "html_body": HTML.strip(),
    "text_body": TEXT.strip(),
    "status": TemplateStatus.ACTIVE,
    "sender_mode": SenderMode.USER,
    "include_signature": True,
    "description": "Kanban Absage. Empathisch, Folgeanfragen nur mit Erlaubnis. Header blau.",
}
try:
    from apps.abpe_email_studio.models import SignatureMode
    defaults["signature_mode"] = SignatureMode.USER
except Exception:
    pass
try:
    from apps.abpe_email_studio.models import AppScope
    if hasattr(AppScope, "MATCHING"):
        defaults["app_scope"] = AppScope.MATCHING
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
print("OK — matching_rejection (empathisch / Erlaubnis)")
