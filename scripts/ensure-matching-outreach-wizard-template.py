#!/usr/bin/env python
"""Upsert Email-Studio-Vorlage matching_outreach_wizard.

Default-Anschreiben für den Matching Outreach-Wizard.
Platzhalter (Email Studio / Composer):
  {name} {first_name} {last_name} {berater_name}
  {project} {projekt_titel} {project_number} {anfragen_id}
  {customer} {kunde}
  {skills} {talking_points} {why} {match_score}
  {signature}

Live (ucs5):
  cd /opt/abpe/backend && source /opt/abpe/venv311/bin/activate
  export DJANGO_SETTINGS_MODULE=abpe_backend.settings
  python /mnt/public/udoo-reprap/scripts/ensure-matching-outreach-wizard-template.py
"""
from apps.abpe_email_studio.models import EmailTemplate, TemplateStatus, SenderMode

IDENT = "matching_outreach_wizard"

HTML = """{{block:abcona_header_blau}}
<p>Guten Tag {first_name},</p>
<p>zu unserer aktuellen Kundenanfrage „<strong>{project}</strong>“{customer_clause} möchten wir Sie gerne anfragen.</p>
<p>Passt das thematisch zu Ihrem Profil{skills_clause}?</p>
<p>{why_clause}</p>
<p>Über eine kurze Rückmeldung freuen wir uns.</p>
<p>Mit freundlichen Grüßen</p>
{{block:signature}}
"""

TEXT = """Guten Tag {first_name},

zu unserer aktuellen Kundenanfrage „{project}“{customer_clause} möchten wir Sie gerne anfragen.

Passt das thematisch zu Ihrem Profil{skills_clause}?

{why_clause}

Über eine kurze Rückmeldung freuen wir uns.

Mit freundlichen Grüßen

{signature}
"""

# Hinweis: customer_clause / skills_clause / why_clause werden vom Wizard
# vor dem Rendern gesetzt (leer oder „ (Kunde)“, „ (u. a. …)“, Why-Satz).
# Fallback ohne Wizard-Preprocess: feste Formulierungen unten in description.

defaults = {
    "name": "Matching — Outreach-Wizard Anschreiben",
    "subject": "Anfrage {project} — passt das für Sie?",
    "html_body": HTML.strip(),
    "text_body": TEXT.strip(),
    "status": TemplateStatus.ACTIVE,
    "sender_mode": SenderMode.USER,
    "include_signature": True,
    "description": (
        "Default-Vorlage für Matching Outreach-Wizard (Shortlist → Anschreiben). "
        "Platzhalter: {first_name}, {name}, {berater_name}, {project}, {projekt_titel}, "
        "{project_number}, {customer}, {kunde}, {skills}, {talking_points}, {why}, "
        "{match_score}, {signature}. "
        "Weitere Vorlagen später im Wizard wählbar; diese bleibt Default."
    ),
}

# Einfachere Variante ohne *_clause (falls Renderer keine leeren Clause-Vars mag):
HTML_SIMPLE = """{{block:abcona_header_blau}}
<p>Guten Tag {first_name},</p>
<p>zu unserer aktuellen Kundenanfrage „<strong>{project}</strong>“ ({customer}) möchten wir Sie gerne anfragen.</p>
<p>Passt das thematisch zu Ihrem Profil (u.&nbsp;a. {skills})?</p>
<p>{why}</p>
<p>Über eine kurze Rückmeldung freuen wir uns.</p>
<p>Mit freundlichen Grüßen</p>
{{block:signature}}
"""

TEXT_SIMPLE = """Guten Tag {first_name},

zu unserer aktuellen Kundenanfrage „{project}“ ({customer}) möchten wir Sie gerne anfragen.

Passt das thematisch zu Ihrem Profil (u. a. {skills})?

{why}

Über eine kurze Rückmeldung freuen wir uns.

Mit freundlichen Grüßen

{signature}
"""

defaults["html_body"] = HTML_SIMPLE.strip()
defaults["text_body"] = TEXT_SIMPLE.strip()

try:
    from apps.abpe_email_studio.models import SignatureMode
    defaults["signature_mode"] = SignatureMode.USER
except Exception:
    pass
try:
    from apps.abpe_email_studio.models import AppScope
    # Matching-Scope wenn vorhanden, sonst GENERAL
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
