#!/usr/bin/env python
"""Upsert matching_present_to_client — Vorstellung nur nach Absprache.

Kein Firmenname. Kein steifer Schluss.
"""
from apps.abpe_email_studio.models import EmailTemplate, TemplateStatus, SenderMode

IDENT = "matching_present_to_client"

_FONT = (
    "font-family:Arial,sans-serif;font-size:14px;line-height:1.5;"
    "color:#333333;"
)
_HEADER = "{{block:abcona_header_blau}}"
_SIGN = "{{block:signature}}"


def _p(inner: str) -> str:
    return f'<p style="{_FONT}margin:0 0 12px 0;">{inner}</p>'


def _facts(rows: list[tuple[str, str]]) -> str:
    lines = "<br>\n".join(
        f"<strong>{label}:</strong> {value}" for label, value in rows
    )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"'
        ' border="0" style="margin:0 0 14px 0;">'
        f'<tr><td style="background-color:#e8f0f8;padding:12px 14px;{_FONT}">'
        f"{lines}</td></tr></table>"
    )


HTML = "\n".join([
    _HEADER,
    _p("Guten Tag {first_name},"),
    _p("vielen Dank für Ihr Interesse an <strong>{project}</strong> "
       "und dass Sie sich gemeldet haben."),
    _p("Nächster Schritt: Wir möchten Ihr Profil dem Auftraggeber vorstellen. "
       "Das tun wir nur nach Absprache mit Ihnen — ohne Ihr OK geht nichts "
       "an den Auftraggeber."),
    _p("Weitergeleitet wird Ihr Profil (Schwerpunkte, Verfügbarkeit, Fit zur Anfrage). "
       "Den Namen des Auftraggebers nennen wir Ihnen, sobald es konkret wird."),
    _p("Kurz der Stand:"),
    _facts([
        ("Was", "{project}"),
        ("Wo", "{location}"),
        ("Wann (Start)", "{start}"),
        ("Remote", "{remote}"),
    ]),
    _p("Wenn der Rahmen für Sie noch passt, geben Sie uns bitte kurz Bescheid. "
       "Dann stellen wir Sie vor."),
    _SIGN,
]) + "\n"

TEXT = """Guten Tag {first_name},

vielen Dank für Ihr Interesse an {project} und dass Sie sich gemeldet haben.

Nächster Schritt: Wir möchten Ihr Profil dem Auftraggeber vorstellen. Das tun wir nur nach Absprache mit Ihnen — ohne Ihr OK geht nichts an den Auftraggeber.

Weitergeleitet wird Ihr Profil (Schwerpunkte, Verfügbarkeit, Fit zur Anfrage). Den Namen des Auftraggebers nennen wir Ihnen, sobald es konkret wird.

Kurz der Stand:
Was: {project}
Wo: {location}
Wann (Start): {start}
Remote: {remote}

Wenn der Rahmen für Sie noch passt, geben Sie uns bitte kurz Bescheid. Dann stellen wir Sie vor.

Mit freundlichen Grüßen
"""

defaults = {
    "name": "Matching — Beim Kunden vorstellen",
    "subject": "Vorstellung — {project}",
    "html_body": HTML.strip(),
    "text_body": TEXT.strip(),
    "status": TemplateStatus.ACTIVE,
    "sender_mode": SenderMode.USER,
    "include_signature": True,
    "description": "Kanban Interesse → Beim Kunden. Einverständnis, kein Kundenname.",
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
print("OK — matching_present_to_client (Einverständnis)")
