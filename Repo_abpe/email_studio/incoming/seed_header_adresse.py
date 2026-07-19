#!/usr/bin/env python3
"""
Seed: EmailModule abcona_header_blau_adresse (Header + Kontaktzeile).

Auf ucs5:
  cd /opt/abpe/backend && source /opt/abpe/venv311/bin/activate
  python manage.py shell < /mnt/public/udoo-reprap/Repo_abpe/email_studio/incoming/seed_header_adresse.py

Oder via Deploy-Skript (automatisch am Ende).
"""
from pathlib import Path

IDENTIFIER = 'abcona_header_blau_adresse'
NAME = 'Header Blau + Adresse'
DESCRIPTION = 'abcona e. K. + www.abcona.de · 06171 886710 · info@abcona.de'

HTML = """<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr>
    <td style="background-color:#163258;padding:16px 24px;text-align:left;">
      <span style="color:#ffffff;font-size:18px;font-weight:bold;font-family:Arial;letter-spacing:0.2px;">abcona e. K.</span>
    </td>
  </tr>
  <tr>
    <td style="background-color:#e8f0f8;padding:10px 24px;text-align:left;font-family:Arial;font-size:12px;line-height:1.5;color:#333333;">
      <a href="https://www.abcona.de" style="color:#163258;text-decoration:none;">www.abcona.de</a>
      &nbsp;·&nbsp;
      <a href="tel:+496171886710" style="color:#163258;text-decoration:none;">06171 886710</a>
      &nbsp;·&nbsp;
      <a href="mailto:info@abcona.de" style="color:#163258;text-decoration:none;">info@abcona.de</a>
    </td>
  </tr>
</table>
"""

TEXT = "abcona e. K.\nwww.abcona.de · 06171 886710 · info@abcona.de\n"


def run():
    from apps.abpe_email_studio.models import EmailModule, ModuleType

    obj, created = EmailModule.objects.update_or_create(
        identifier=IDENTIFIER,
        defaults={
            'name': NAME,
            'module_type': ModuleType.HEADER,
            'description': DESCRIPTION,
            'html_body': HTML.strip(),
            'text_body': TEXT,
            'preview_bg': '#163258',
            'is_active': True,
        },
    )
    print(('CREATED' if created else 'UPDATED'), IDENTIFIER, 'pk=', obj.pk)


if __name__ == '__main__':
    run()
else:
    # manage.py shell < this file
    run()
