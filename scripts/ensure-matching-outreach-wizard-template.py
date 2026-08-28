#!/usr/bin/env python
"""Upsert matching_outreach_wizard — Erstanschreiben, zurückhaltender.

Kein Firmenname. Kein steifer Schluss. Kein Frage-Verhör.
"""
from apps.abpe_email_studio.models import EmailTemplate, TemplateStatus, SenderMode

IDENT = "matching_outreach_wizard"

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
    _p("wir haben eine Anfrage vorliegen, die nach unserem Eindruck "
       "zu Ihrem Profil passen könnte. Ob sie das tut, möchten wir gerne "
       "mit Ihnen klären — ohne Druck."),
    _p("Kurz der Stand:"),
    _facts([
        ("Was", "{project}"),
        ("Wo", "{location}"),
        ("Wann (Start)", "{start}"),
        ("Laufzeit", "{duration}"),
        ("Auslastung", "{workload}"),
        ("Remote", "{remote}"),
    ]),
    _p("{description}"),
    _p("<strong>Gesucht u.&nbsp;a.:</strong> {required_skills}"),
    _p("<strong>Was uns an Ihrem Profil aufgefallen ist:</strong><br>{why_short}"),
    _p("Wenn Sie mögen, reicht eine kurze Rückmeldung: ob grundsätzlich Interesse "
       "besteht, und ob Start {start} sowie Ort / Remote / Auslastung grob passen. "
       "Wenn nicht, genügt ein Satz — dann bleibt es dabei."),
    _SIGN,
]) + "\n"

TEXT = """Guten Tag {first_name},

wir haben eine Anfrage vorliegen, die nach unserem Eindruck zu Ihrem Profil passen könnte. Ob sie das tut, möchten wir gerne mit Ihnen klären — ohne Druck.

Kurz der Stand:
Was: {project}
Wo: {location}
Wann (Start): {start}
Laufzeit: {duration}
Auslastung: {workload}
Remote: {remote}

{description}

Gesucht u. a.: {required_skills}

Was uns an Ihrem Profil aufgefallen ist:
{why_short}

Wenn Sie mögen, reicht eine kurze Rückmeldung: ob grundsätzlich Interesse besteht, und ob Start {start} sowie Ort / Remote / Auslastung grob passen. Wenn nicht, genügt ein Satz — dann bleibt es dabei.

Mit freundlichen Grüßen
"""

defaults = {
    "name": "Matching — Outreach-Wizard Anschreiben",
    "subject": "Anfrage {project}",
    "html_body": HTML.strip(),
    "text_body": TEXT.strip(),
    "status": TemplateStatus.ACTIVE,
    "sender_mode": SenderMode.USER,
    "include_signature": True,
    "description": "Shortlist / Erstanschreiben. Zurückhaltend, kein Firmenname.",
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
print("OK — matching_outreach_wizard (zurückhaltend)")
