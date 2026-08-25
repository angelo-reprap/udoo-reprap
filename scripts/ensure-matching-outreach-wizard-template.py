#!/usr/bin/env python
"""Upsert Email-Studio-Vorlage matching_outreach_wizard.

Default-Anschreiben für den Matching Outreach-Wizard.
Struktur: Begrüßung → Anfrage ausführlich → Warum kurz → Abschluss.
Signatur kommt separat über den Wizard (Email-Studio-Signaturen).

Platzhalter:
  {first_name} {name} {last_name} {berater_name}
  {project} {projekt_titel} {project_number} {anfragen_id}
  {customer} {kunde}
  {location} {standort} {start} {duration} {workload} {remote}
  {description} {project_details} {required_skills}
  {skills} {talking_points} {why} {why_short} {match_score}

Live (ucs5):
  cd /opt/abpe/backend && source /opt/abpe/venv311/bin/activate
  export DJANGO_SETTINGS_MODULE=abpe_backend.settings
  python /mnt/public/udoo-reprap/scripts/ensure-matching-outreach-wizard-template.py
"""
from apps.abpe_email_studio.models import EmailTemplate, TemplateStatus, SenderMode

IDENT = "matching_outreach_wizard"

HTML = """{{block:abcona_header_blau}}
<p>Guten Tag {first_name},</p>
<p>wir möchten Sie persönlich zu folgender Kundenanfrage anfragen:</p>
<p><strong>Was:</strong> {project}<br>
<strong>Kunde:</strong> {customer}<br>
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
"""

TEXT = """Guten Tag {first_name},

wir möchten Sie persönlich zu folgender Kundenanfrage anfragen:

Was: {project}
Kunde: {customer}
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
"""

defaults = {
    "name": "Matching — Outreach-Wizard Anschreiben",
    "subject": "Anfrage {project} — passt das für Sie?",
    "html_body": HTML.strip(),
    "text_body": TEXT.strip(),
    "status": TemplateStatus.ACTIVE,
    "sender_mode": SenderMode.USER,
    "include_signature": True,
    "description": (
        "Default-Vorlage Outreach-Wizard. Struktur: Begrüßung → Anfrage "
        "(Was/Wo/Wann/…) → Warum kurz in Sie-Form "
        "(‚Aus Ihrem Werdegang entnehmen wir …‘). Signatur im Wizard wählbar. "
        "Platzhalter: {first_name}, {project}, {customer}, {location}, {start}, "
        "{duration}, {workload}, {remote}, {description}, {required_skills}, {why_short}."
    ),
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
    identifier=IDENT,
    defaults=defaults,
)
print(("CREATED" if created else "UPDATED"), IDENT, "pk=", tpl.pk)
print("name:", tpl.name)
print("subject:", tpl.subject)
print("status:", getattr(tpl, "status", ""))
