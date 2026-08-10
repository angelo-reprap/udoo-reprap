#!/usr/bin/env python
"""Upsert Email-Studio-Vorlage inbox_anfrage_bestaetigung (Dokumentation).

Live:
  cd /opt/abpe/backend && /opt/abpe/venv311/bin/python manage.py shell < \\
    <(git -C /mnt/public/udoo-reprap show origin/cursor/matching-ki-anfrage-wizard-7f07:scripts/ensure-inbox-anfrage-bestaetigung-template.py)

Die Posteingang-UI sendet über crm_manual_email + editierbaren Standardtext.
Diese Vorlage hält denselben Text im Email Studio fest.
"""
from apps.abpe_email_studio.models import EmailTemplate, TemplateStatus, SenderMode

IDENT = "inbox_anfrage_bestaetigung"
HTML = """{{block:abcona_header_blau}}
<p>Sehr geehrter Herr {name},</p>
<p>vielen Dank für Ihre Anfrage.</p>
<p>Wir werden Ihnen diesbezüglich schnellstmöglich Beratervorschläge unterbreiten.</p>
<p>Mit freundlichen Grüßen</p>
{{block:signature}}
"""
TEXT = """Sehr geehrter Herr {name},

vielen Dank für Ihre Anfrage.

Wir werden Ihnen diesbezüglich schnellstmöglich Beratervorschläge unterbreiten.

Mit freundlichen Grüßen

{signature}
"""

defaults = {
    "name": "Posteingang — Anfrage-Bestätigung",
    "subject": "Re: {original_subject}",
    "html_body": HTML.strip(),
    "text_body": TEXT.strip(),
    "status": TemplateStatus.ACTIVE,
    "sender_mode": SenderMode.USER,
    "include_signature": True,
    "description": "Standardtext für Antworten aus dem Shaduler-Posteingang.",
}
try:
    from apps.abpe_email_studio.models import SignatureMode
    defaults["signature_mode"] = SignatureMode.USER
except Exception:
    pass
try:
    from apps.abpe_email_studio.models import AppScope
    if hasattr(AppScope, "GENERAL"):
        defaults["app_scope"] = AppScope.GENERAL
except Exception:
    pass

field_names = {f.name for f in EmailTemplate._meta.get_fields()}
defaults = {k: v for k, v in defaults.items() if k in field_names}

tpl, created = EmailTemplate.objects.update_or_create(identifier=IDENT, defaults=defaults)
print(("CREATED" if created else "UPDATED"), IDENT, "pk=", tpl.pk)
