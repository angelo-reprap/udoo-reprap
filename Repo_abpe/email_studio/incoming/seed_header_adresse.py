#!/usr/bin/env python3
"""
Seed/Fix: EmailModule abcona_header_blau_adresse

- Tippfehler-Identifier umbenennen (adrersse → adresse)
- Text „abcona e. K.“ aus Header entfernen (nur blauer Streifen + Kontakt)
- Template-Referenzen auf korrekten Tag umschreiben

Auf ucs5:
  cd /opt/abpe/backend && source /opt/abpe/venv311/bin/activate
  python manage.py shell < …/seed_header_adresse.py
"""
from __future__ import annotations

import re

IDENTIFIER = 'abcona_header_blau_adresse'
NAME = 'Header Blau + Adresse'
DESCRIPTION = 'Blauer Streifen + www.abcona.de · 06171 886710 · info@abcona.de'

# Alte/falsche IDs die auf den kanonischen Identifier zeigen
TYPO_IDS = (
    'abcona_header_blau_adrersse',
    'block_abcona_header_blau_adrersse',
    'block_abcona_header_blau_adresse',
    'abcona_header_blau_adrresse',
)

HTML = """<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr>
    <td style="background-color:#163258;padding:12px 24px;font-size:1px;line-height:12px;">&nbsp;</td>
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

TEXT = "www.abcona.de · 06171 886710 · info@abcona.de\n"

# Template-Bodies: alle Varianten → korrekter Tag
_BLOCK_REWRITES = [
    (r'\{\{block:block_abcona_header_blau_adrersse\}\}', '{{block:abcona_header_blau_adresse}}'),
    (r'\{\{block:abcona_header_blau_adrersse\}\}', '{{block:abcona_header_blau_adresse}}'),
    (r'\{\{block:block_abcona_header_blau_adresse\}\}', '{{block:abcona_header_blau_adresse}}'),
    (r'\{\{block:abcona_header_blau_adrresse\}\}', '{{block:abcona_header_blau_adresse}}'),
]


def _strip_brand_name(html: str, text: str) -> tuple[str, str]:
    """Entfernt sichtbares ‚abcona e. K.‘ aus Modul-Bodies."""
    html2 = re.sub(
        r'(?is)<span[^>]*>\s*abcona\s+e\.?\s*K\.?\s*</span>',
        '&nbsp;',
        html or '',
    )
    html2 = re.sub(r'(?is)>abcona\s+e\.?\s*K\.?\s*<', '>&nbsp;<', html2)
    text2 = re.sub(r'(?im)^\s*abcona\s+e\.?\s*K\.?\s*\n?', '', text or '')
    return html2, text2


def _rename_typo_modules() -> None:
    from apps.abpe_email_studio.models import EmailModule

    canonical = EmailModule.objects.filter(identifier=IDENTIFIER).first()
    for bad in TYPO_IDS:
        # block_* sind keine gültigen DB-Identifier üblich — trotzdem prüfen
        typo = EmailModule.objects.filter(identifier=bad).first()
        if not typo:
            continue
        if canonical and canonical.pk != typo.pk:
            print(f'DELETE typo module {bad} pk={typo.pk} (canonical existiert)')
            typo.delete()
            continue
        typo.identifier = IDENTIFIER
        typo.name = NAME
        typo.save(update_fields=['identifier', 'name'])
        print(f'RENAMED {bad} → {IDENTIFIER} pk={typo.pk}')
        canonical = typo


def _rewrite_templates() -> int:
    from apps.abpe_email_studio.models import EmailTemplate

    n = 0
    for tpl in EmailTemplate.objects.all().iterator():
        html = tpl.html_body or ''
        text = tpl.text_body or ''
        new_html, new_text = html, text
        for pat, repl in _BLOCK_REWRITES:
            new_html = re.sub(pat, repl, new_html)
            new_text = re.sub(pat, repl, new_text)
        if new_html != html or new_text != text:
            tpl.html_body = new_html
            tpl.text_body = new_text
            tpl.save(update_fields=['html_body', 'text_body'])
            n += 1
            print(f'TEMPLATE rewritten id={tpl.pk} {getattr(tpl, "identifier", "")}')
    return n


def run():
    from apps.abpe_email_studio.models import EmailModule, ModuleType

    _rename_typo_modules()

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
    # Falls Body noch Markenname enthält — bereinigen
    cleaned_html, cleaned_text = _strip_brand_name(obj.html_body, obj.text_body)
    if cleaned_html != (obj.html_body or '') or cleaned_text != (obj.text_body or ''):
        obj.html_body = HTML.strip()
        obj.text_body = TEXT
        obj.description = DESCRIPTION
        obj.name = NAME
        obj.save()
        print('STRIPPED brand name from', IDENTIFIER)

    print(('CREATED' if created else 'UPDATED'), IDENTIFIER, 'pk=', obj.pk)
    rewritten = _rewrite_templates()
    print(f'Templates updated: {rewritten}')


if __name__ == '__main__':
    run()
else:
    run()
