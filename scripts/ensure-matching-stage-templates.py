#!/usr/bin/env python
"""Upsert Email-Studio-Vorlagen für Matching-Kanban-Stufen.

Identifier = STAGE_TEMPLATE_DEFAULTS in outreach_wizard.py.
Kein Firmen-/Kundenname (Vertraulichkeit) — Signatur im Composer.

Live (ucs5):
  cd /mnt/public/udoo-reprap
  bash scripts/SAFE-ensure-matching-stage-templates.sh
"""
from apps.abpe_email_studio.models import EmailTemplate, TemplateStatus, SenderMode

# (identifier, name, subject, html_body, text_body, description)
TEMPLATES = [
    (
        "matching_outreach_wizard",
        "Matching — Outreach-Wizard Anschreiben",
        "Anfrage {project} — passt das für Sie?",
        """{{block:abcona_header_blau}}
<p>Guten Tag {first_name},</p>
<p>wir möchten Sie persönlich zu folgender Kundenanfrage anfragen:</p>
<p><strong>Was:</strong> {project}<br>
<strong>Wo:</strong> {location}<br>
<strong>Wann (Start):</strong> {start}<br>
<strong>Laufzeit:</strong> {duration}<br>
<strong>Auslastung:</strong> {workload}<br>
<strong>Remote:</strong> {remote}</p>
<p>{description}</p>
<p><strong>Gesucht u. a.:</strong> {required_skills}</p>
<p><strong>Warum wir Sie ansprechen:</strong><br>{why_short}</p>
<p>Über eine kurze Rückmeldung freuen wir uns.</p>
<p>Mit freundlichen Grüßen</p>
{{block:signature}}
""",
        """Guten Tag {first_name},

wir möchten Sie persönlich zu folgender Kundenanfrage anfragen:

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

Über eine kurze Rückmeldung freuen wir uns.

Mit freundlichen Grüßen
""",
        "Shortlist / Erstanschreiben. Kein Firmenname.",
    ),
    (
        "matching_followup_availability",
        "Matching — Nachfrage Interesse / Verfügbarkeit",
        "Nachfrage Verfügbarkeit — {project}",
        """{{block:abcona_header_blau}}
<p>Guten Tag {first_name},</p>
<p>kurze Nachfrage zu unserer Anfrage <strong>{project}</strong>:</p>
<p>Besteht Interesse, und wann wären Sie verfügbar (ab Datum / Stunden pro Woche)?</p>
<p>Standort: {location} · Start: {start} · Laufzeit: {duration} · Remote: {remote}</p>
<p>Über eine kurze Rückmeldung freuen wir uns.</p>
<p>Mit freundlichen Grüßen</p>
{{block:signature}}
""",
        """Guten Tag {first_name},

kurze Nachfrage zu unserer Anfrage {project}:

Besteht Interesse, und wann wären Sie verfügbar (ab Datum / Stunden pro Woche)?

Standort: {location} · Start: {start} · Laufzeit: {duration} · Remote: {remote}

Über eine kurze Rückmeldung freuen wir uns.

Mit freundlichen Grüßen
""",
        "Kanban: Angeschrieben → Interesse. Follow-up Verfügbarkeit.",
    ),
    (
        "matching_present_to_client",
        "Matching — Beim Kunden vorstellen",
        "Vorstellung — {project}",
        """{{block:abcona_header_blau}}
<p>Guten Tag {first_name},</p>
<p>vielen Dank für Ihr Interesse an unserer Anfrage <strong>{project}</strong>.</p>
<p>Wir möchten Sie gerne dem Kunden als passenden Kandidaten vorstellen.</p>
<p><strong>Was:</strong> {project}<br>
<strong>Wo:</strong> {location}<br>
<strong>Wann (Start):</strong> {start}<br>
<strong>Laufzeit:</strong> {duration}<br>
<strong>Remote:</strong> {remote}</p>
<p>Dürfen wir Ihr Profil weiterleiten?</p>
<p>Mit freundlichen Grüßen</p>
{{block:signature}}
""",
        """Guten Tag {first_name},

vielen Dank für Ihr Interesse an unserer Anfrage {project}.

Wir möchten Sie gerne dem Kunden als passenden Kandidaten vorstellen.

Was: {project}
Wo: {location}
Wann (Start): {start}
Laufzeit: {duration}
Remote: {remote}

Dürfen wir Ihr Profil weiterleiten?

Mit freundlichen Grüßen
""",
        "Kanban: Interesse → Beim Kunden. Einverständnis zur Vorstellung.",
    ),
    (
        "matching_interview_coord",
        "Matching — Interview koordinieren",
        "Interview-Koordination — {project}",
        """{{block:abcona_header_blau}}
<p>Guten Tag {first_name},</p>
<p>zu unserer Anfrage <strong>{project}</strong> möchten wir Sie gerne kennenlernen.</p>
<p>Welche Termine passen Ihnen (Datum/Uhrzeit, Telefon oder Video)?</p>
<p>Mit freundlichen Grüßen</p>
{{block:signature}}
""",
        """Guten Tag {first_name},

zu unserer Anfrage {project} möchten wir Sie gerne kennenlernen.

Welche Termine passen Ihnen (Datum/Uhrzeit, Telefon oder Video)?

Mit freundlichen Grüßen
""",
        "Kanban: Beim Kunden → Interview.",
    ),
    (
        "matching_placement_start",
        "Matching — Vermittlung / Startabstimmung",
        "Vermittlung — Startabstimmung {project}",
        """{{block:abcona_header_blau}}
<p>Guten Tag {first_name},</p>
<p>zur Vermittlung <strong>{project}</strong>:</p>
<p>Bitte teilen Sie uns Ihren Wunsch-Starttermin und relevante Rahmenbedingungen mit.</p>
<p>Mit freundlichen Grüßen</p>
{{block:signature}}
""",
        """Guten Tag {first_name},

zur Vermittlung {project}:

Bitte teilen Sie uns Ihren Wunsch-Starttermin und relevante Rahmenbedingungen mit.

Mit freundlichen Grüßen
""",
        "Kanban: Interview → Vermittelt.",
    ),
    (
        "matching_start_info",
        "Matching — Startinfo",
        "Startinfo — {project}",
        """{{block:abcona_header_blau}}
<p>Guten Tag {first_name},</p>
<p>zur Aufnahme bei <strong>{project}</strong>:</p>
<ul>
<li>Start: {start}</li>
<li>Ort / Remote: {location}</li>
<li>Ansprechpartner: bitte melden Sie sich bei Bedarf über uns.</li>
</ul>
<p>Viel Erfolg und viele Grüße</p>
{{block:signature}}
""",
        """Guten Tag {first_name},

zur Aufnahme bei {project}:
• Start: {start}
• Ort / Remote: {location}
• Ansprechpartner: bitte melden Sie sich bei Bedarf über uns.

Viel Erfolg und viele Grüße
""",
        "Kanban: Vermittelt — Startinfo.",
    ),
    (
        "matching_rejection",
        "Matching — Absage",
        "Rückmeldung zur Anfrage {project}",
        """{{block:abcona_header_blau}}
<p>Guten Tag {first_name},</p>
<p>vielen Dank für Ihr Interesse an <strong>{project}</strong>.</p>
<p>Leider hat sich die Auswahl anderweitig entschieden. Wir melden uns gerne bei passenden Folgeanfragen.</p>
<p>Freundliche Grüße</p>
{{block:signature}}
""",
        """Guten Tag {first_name},

vielen Dank für Ihr Interesse an {project}.

Leider hat sich die Auswahl anderweitig entschieden. Wir melden uns gerne bei passenden Folgeanfragen.

Freundliche Grüße
""",
        "Kanban: Absage.",
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

print("OK —", len(TEMPLATES), "Matching-Stage-Vorlagen")
