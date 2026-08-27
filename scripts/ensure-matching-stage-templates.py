#!/usr/bin/env python
"""Upsert Email-Studio-Vorlagen für Matching-Kanban-Stufen.

Einheitliches Layout (v3):
  Header blau → Anrede → Inhalt/Bausteine → Signatur (Composer).
Kein Firmen-/Kundenname (Vertraulichkeit).
Kein „Mit freundlichen Grüßen“ im Body — das steht in {{block:signature}}.

Identifier = STAGE_TEMPLATE_DEFAULTS in outreach_wizard.py.

Live (ucs5) — Datei von origin lesen (lokales git auf ucs5 oft divergent):
  cd /opt/abpe/backend
  git -C /mnt/public/udoo-reprap fetch origin cursor/email-matching-layout-ee01
  /opt/abpe/venv311/bin/python manage.py shell < <(
    git -C /mnt/public/udoo-reprap show origin/cursor/email-matching-layout-ee01:scripts/ensure-matching-stage-templates.py
  )
Oder: bash scripts/SAFE-ensure-matching-stage-templates.sh
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
    return f"{_HEADER}\n{body}\n{_SIGN}\n"


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
            _p("Könnten Sie uns bitte kurz sagen:"),
            _ul([
                "Haben Sie Interesse?",
                "Sind Sie ab {start} verfügbar?",
                "Passt der Rahmen (Ort / Remote / Auslastung)?",
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

Könnten Sie uns bitte kurz sagen:
- Haben Sie Interesse?
- Sind Sie ab {start} verfügbar?
- Passt der Rahmen (Ort / Remote / Auslastung)?

Über eine kurze Rückmeldung freuen wir uns.

Mit freundlichen Grüßen
""",
        "Shortlist / Erstanschreiben. Kein Firmenname. Layout v3.",
    ),
    (
        "matching_followup_availability",
        "Matching — Nachfrage Interesse / Verfügbarkeit",
        "Nachfrage — {project}",
        _mail(
            _p("Guten Tag {first_name},"),
            _p("wir möchten kurz nachfassen zu <strong>{project}</strong>."),
            _p("Besteht weiterhin Interesse — und ab wann wären Sie verfügbar "
               "(Datum / Tage pro Woche)?"),
            FACTS_KOMPAKT,
            _p("Über eine kurze Rückmeldung freuen wir uns."),
        ),
        """Guten Tag {first_name},

wir möchten kurz nachfassen zu {project}.

Besteht weiterhin Interesse — und ab wann wären Sie verfügbar (Datum / Tage pro Woche)?

Was: {project}
Wo: {location}
Wann (Start): {start}
Remote: {remote}

Über eine kurze Rückmeldung freuen wir uns.

Mit freundlichen Grüßen
""",
        "Kanban: Angeschrieben. Follow-up Interesse/Verfügbarkeit. Layout v3.",
    ),
    (
        "matching_present_to_client",
        "Matching — Beim Kunden vorstellen",
        "Vorstellung — {project}",
        _mail(
            _p("Guten Tag {first_name},"),
            _p("vielen Dank für Ihr Interesse an <strong>{project}</strong>."),
            _p("Wenn Sie einverstanden sind, stellen wir Ihr Profil dem Auftraggeber vor."),
            FACTS_KOMPAKT,
            _p("Dürfen wir Ihr Profil weiterleiten?"),
        ),
        """Guten Tag {first_name},

vielen Dank für Ihr Interesse an {project}.

Wenn Sie einverstanden sind, stellen wir Ihr Profil dem Auftraggeber vor.

Was: {project}
Wo: {location}
Wann (Start): {start}
Remote: {remote}

Dürfen wir Ihr Profil weiterleiten?

Mit freundlichen Grüßen
""",
        "Kanban: Interesse → Beim Kunden. Einverständnis, kein Kundenname. Layout v3.",
    ),
    (
        "matching_interview_coord",
        "Matching — Interview koordinieren",
        "Kennlerntermin — {project}",
        _mail(
            _p("Guten Tag {first_name},"),
            _p("für <strong>{project}</strong> möchten wir gerne einen "
               "Kennenlerntermin mit Ihnen vereinbaren."),
            FACTS_KOMPAKT,
            _p("Welche Termine passen Ihnen (Datum / Uhrzeit, Telefon oder Video)?"),
        ),
        """Guten Tag {first_name},

für {project} möchten wir gerne einen Kennenlerntermin mit Ihnen vereinbaren.

Was: {project}
Wo: {location}
Wann (Start): {start}
Remote: {remote}

Welche Termine passen Ihnen (Datum / Uhrzeit, Telefon oder Video)?

Mit freundlichen Grüßen
""",
        "Kanban: Beim Kunden → Interview. Layout v3.",
    ),
    (
        "matching_placement_start",
        "Matching — Vermittlung / Startabstimmung",
        "Startabstimmung — {project}",
        _mail(
            _p("Guten Tag {first_name},"),
            _p("für <strong>{project}</strong> möchten wir den Start mit Ihnen abstimmen."),
            FACTS_PROJEKT,
            _p("Bitte nennen Sie uns:"),
            _ul([
                "Wunsch-Starttermin",
                "verfügbare Tage pro Woche",
                "weitere Rahmenbedingungen",
            ]),
        ),
        """Guten Tag {first_name},

für {project} möchten wir den Start mit Ihnen abstimmen.

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
        "Kanban: Interview → Vermittelt. Layout v3.",
    ),
    (
        "matching_start_info",
        "Matching — Startinfo",
        "Startinfo — {project}",
        _mail(
            _p("Guten Tag {first_name},"),
            _p("hier die Eckdaten zum Start von <strong>{project}</strong>:"),
            FACTS_START,
            _p("Ansprechpartner vor Ort klären wir über uns. "
               "Viel Erfolg — bei Fragen sind wir erreichbar."),
        ),
        """Guten Tag {first_name},

hier die Eckdaten zum Start von {project}:

Projekt: {project}
Start: {start}
Ort: {location}
Remote: {remote}

Ansprechpartner vor Ort klären wir über uns. Viel Erfolg — bei Fragen sind wir erreichbar.

Mit freundlichen Grüßen
""",
        "Kanban: Vermittelt — Startinfo. Layout v3.",
    ),
    (
        "matching_rejection",
        "Matching — Absage",
        "Rückmeldung zur Anfrage {project}",
        _mail(
            _p("Guten Tag {first_name},"),
            _p("vielen Dank für Ihr Interesse an <strong>{project}</strong>."),
            _p("Leider ist die Auswahl anders ausgefallen. "
               "Wir kommen gerne wieder auf Sie zu, wenn etwas Passendes ansteht."),
        ),
        """Guten Tag {first_name},

vielen Dank für Ihr Interesse an {project}.

Leider ist die Auswahl anders ausgefallen. Wir kommen gerne wieder auf Sie zu, wenn etwas Passendes ansteht.

Mit freundlichen Grüßen
""",
        "Kanban: Absage. Header bleibt blau. Layout v3.",
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

print("OK —", len(TEMPLATES), "Matching-Stage-Vorlagen (Layout v3)")
