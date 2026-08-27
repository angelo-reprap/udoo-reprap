#!/usr/bin/env python
"""Upsert Email-Studio-Vorlagen für Matching-Kanban-Stufen.

Einheitliches Layout (v2):
  Header blau → Anrede → Inhalt/Bausteine → Schluss → Signatur
Kein Firmen-/Kundenname (Vertraulichkeit) — Signatur im Composer.

Identifier = STAGE_TEMPLATE_DEFAULTS in outreach_wizard.py.

Live (ucs5):
  cd /mnt/public/udoo-reprap
  git pull origin cursor/email-matching-layout-ee01
  bash scripts/SAFE-ensure-matching-stage-templates.sh
"""
from apps.abpe_email_studio.models import EmailTemplate, TemplateStatus, SenderMode

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


def _ul(items: list[str]) -> str:
    lis = "".join(
        f'<li style="{_FONT}margin:0 0 4px 0;">{item}</li>' for item in items
    )
    return f'<ul style="margin:0 0 14px 18px;padding:0;">{lis}</ul>'


def _mail(*parts: str) -> str:
    body = "\n".join(p for p in parts if p)
    return f"{_HEADER}\n{body}\n{_p('Mit freundlichen Grüßen')}\n{_SIGN}\n"


FACTS_PROJEKT = _facts([
    ("Was", "{project}"),
    ("Wo", "{location}"),
    ("Wann (Start)", "{start}"),
    ("Laufzeit", "{duration}"),
    ("Auslastung", "{workload}"),
    ("Remote", "{remote}"),
])

FACTS_KOMPAKT = _facts([
    ("Was", "{project}"),
    ("Wo", "{location}"),
    ("Wann (Start)", "{start}"),
    ("Remote", "{remote}"),
])

FACTS_START = _facts([
    ("Projekt", "{project}"),
    ("Start", "{start}"),
    ("Ort", "{location}"),
    ("Remote", "{remote}"),
])

# (identifier, name, subject, html_body, text_body, description)
TEMPLATES = [
    (
        "matching_outreach_wizard",
        "Matching — Outreach-Wizard Anschreiben",
        "Anfrage {project} — passt das für Sie?",
        _mail(
            _p("Guten Tag {first_name},"),
            _p("wir haben eine Anfrage, die gut zu Ihrem Profil passen könnte."),
            FACTS_PROJEKT,
            _p("{description}"),
            _p("<strong>Gesucht u.&nbsp;a.:</strong> {required_skills}"),
            _p("<strong>Warum wir Sie ansprechen:</strong><br>{why_short}"),
            _p("Bitte kurz:"),
            _ul([
                "Interesse?",
                "Verfügbar ab {start}?",
                "Rahmen (Ort / Remote / Auslastung) passt?",
            ]),
            _p("Über eine kurze Rückmeldung freuen wir uns."),
        ),
        """Guten Tag {first_name},

wir haben eine Anfrage, die gut zu Ihrem Profil passen könnte.

Was: {project}
Wo: {location}
Wann (Start): {start}
Laufzeit: {duration}
Auslastung: {workload}
Remote: {remote}

{description}

Gesucht u. a.: {required_skills}

Warum wir Sie ansprechen:
{why_short}

Bitte kurz:
- Interesse?
- Verfügbar ab {start}?
- Rahmen (Ort / Remote / Auslastung) passt?

Über eine kurze Rückmeldung freuen wir uns.

Mit freundlichen Grüßen
""",
        "Shortlist / Erstanschreiben. Kein Firmenname. Layout v2.",
    ),
    (
        "matching_followup_availability",
        "Matching — Nachfrage Interesse / Verfügbarkeit",
        "Nachfrage — {project}",
        _mail(
            _p("Guten Tag {first_name},"),
            _p("kurze Nachfrage zu unserer Anfrage <strong>{project}</strong>."),
            _p("Besteht weiterhin Interesse — und ab wann wären Sie verfügbar "
               "(Datum / Tage pro Woche)?"),
            FACTS_KOMPAKT,
            _p("Über eine kurze Rückmeldung freuen wir uns."),
        ),
        """Guten Tag {first_name},

kurze Nachfrage zu unserer Anfrage {project}.

Besteht weiterhin Interesse — und ab wann wären Sie verfügbar (Datum / Tage pro Woche)?

Was: {project}
Wo: {location}
Wann (Start): {start}
Remote: {remote}

Über eine kurze Rückmeldung freuen wir uns.

Mit freundlichen Grüßen
""",
        "Kanban: Angeschrieben. Follow-up Interesse/Verfügbarkeit. Layout v2.",
    ),
    (
        "matching_present_to_client",
        "Matching — Beim Kunden vorstellen",
        "Vorstellung — {project}",
        _mail(
            _p("Guten Tag {first_name},"),
            _p("vielen Dank für Ihr Interesse an <strong>{project}</strong>."),
            _p("Wir möchten Ihr Profil dem Auftraggeber vorstellen."),
            FACTS_KOMPAKT,
            _p("Dürfen wir Ihr Profil weiterleiten?"),
        ),
        """Guten Tag {first_name},

vielen Dank für Ihr Interesse an {project}.

Wir möchten Ihr Profil dem Auftraggeber vorstellen.

Was: {project}
Wo: {location}
Wann (Start): {start}
Remote: {remote}

Dürfen wir Ihr Profil weiterleiten?

Mit freundlichen Grüßen
""",
        "Kanban: Interesse → Beim Kunden. Einverständnis, kein Kundenname. Layout v2.",
    ),
    (
        "matching_interview_coord",
        "Matching — Interview koordinieren",
        "Kennlerntermin — {project}",
        _mail(
            _p("Guten Tag {first_name},"),
            _p("zu <strong>{project}</strong> möchten wir Sie gerne kennenlernen."),
            FACTS_KOMPAKT,
            _p("Welche Termine passen Ihnen (Datum / Uhrzeit, Telefon oder Video)?"),
        ),
        """Guten Tag {first_name},

zu {project} möchten wir Sie gerne kennenlernen.

Was: {project}
Wo: {location}
Wann (Start): {start}
Remote: {remote}

Welche Termine passen Ihnen (Datum / Uhrzeit, Telefon oder Video)?

Mit freundlichen Grüßen
""",
        "Kanban: Beim Kunden → Interview. Layout v2.",
    ),
    (
        "matching_placement_start",
        "Matching — Vermittlung / Startabstimmung",
        "Startabstimmung — {project}",
        _mail(
            _p("Guten Tag {first_name},"),
            _p("zur Vermittlung <strong>{project}</strong> stimmen wir den Start ab."),
            FACTS_PROJEKT,
            _p("Bitte nennen Sie uns:"),
            _ul([
                "Wunsch-Starttermin",
                "verfügbare Tage pro Woche",
                "weitere Rahmenbedingungen",
            ]),
        ),
        """Guten Tag {first_name},

zur Vermittlung {project} stimmen wir den Start ab.

Was: {project}
Wo: {location}
Wann (Start): {start}
Laufzeit: {duration}
Auslastung: {workload}
Remote: {remote}

Bitte nennen Sie uns:
- Wunsch-Starttermin
- verfügbare Tage pro Woche
- weitere Rahmenbedingungen

Mit freundlichen Grüßen
""",
        "Kanban: Interview → Vermittelt. Layout v2.",
    ),
    (
        "matching_start_info",
        "Matching — Startinfo",
        "Startinfo — {project}",
        _mail(
            _p("Guten Tag {first_name},"),
            _p("zum Start von <strong>{project}</strong>:"),
            FACTS_START,
            _p("Ansprechpartner vor Ort klären wir über uns. "
               "Viel Erfolg — bei Fragen sind wir erreichbar."),
        ),
        """Guten Tag {first_name},

zum Start von {project}:

Projekt: {project}
Start: {start}
Ort: {location}
Remote: {remote}

Ansprechpartner vor Ort klären wir über uns. Viel Erfolg — bei Fragen sind wir erreichbar.

Mit freundlichen Grüßen
""",
        "Kanban: Vermittelt — Startinfo. Layout v2.",
    ),
    (
        "matching_rejection",
        "Matching — Absage",
        "Rückmeldung zur Anfrage {project}",
        _mail(
            _p("Guten Tag {first_name},"),
            _p("vielen Dank für Ihr Interesse an <strong>{project}</strong>."),
            _p("Die Auswahl ist anders ausgefallen. "
               "Wir kommen gerne wieder auf Sie zu, wenn etwas Passendes ansteht."),
        ),
        """Guten Tag {first_name},

vielen Dank für Ihr Interesse an {project}.

Die Auswahl ist anders ausgefallen. Wir kommen gerne wieder auf Sie zu, wenn etwas Passendes ansteht.

Mit freundlichen Grüßen
""",
        "Kanban: Absage. Header bleibt blau. Layout v2.",
    ),
]


def _base_defaults():
    defaults = {
        "status": TemplateStatus.ACTIVE,
        "sender_mode": SenderMode.USER,
        "include_signature": True,
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
    return defaults


field_names = {f.name for f in EmailTemplate._meta.get_fields()}
base = _base_defaults()

for ident, name, subject, html, text, desc in TEMPLATES:
    defaults = dict(base)
    defaults.update({
        "name": name,
        "subject": subject,
        "html_body": html.strip(),
        "text_body": text.strip(),
        "description": desc,
    })
    defaults = {k: v for k, v in defaults.items() if k in field_names}
    tpl, created = EmailTemplate.objects.update_or_create(
        identifier=ident,
        defaults=defaults,
    )
    print(("CREATED" if created else "UPDATED"), ident, "pk=", tpl.pk, "|", tpl.name)

print("OK —", len(TEMPLATES), "Matching-Stage-Vorlagen (Layout v2)")
