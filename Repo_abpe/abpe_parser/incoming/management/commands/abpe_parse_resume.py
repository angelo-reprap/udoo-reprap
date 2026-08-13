"""
Testet den experimentellen abpe_parser (DeepSeek, ResumeParser-Stil).

  cd /opt/abpe/backend
  source venv311/bin/activate   # oder euer venv
  python manage.py abpe_parse_resume /pfad/zum/profil.pdf
  python manage.py abpe_parse_resume /pfad.pdf --out /tmp/out.json
"""
from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'abpe_parser: PDF/DOCX → DeepSeek JSON (Experiment, nicht Pipeline)'

    def add_arguments(self, parser):
        parser.add_argument('file', type=str, help='Pfad zu PDF oder DOCX')
        parser.add_argument(
            '--out', type=str, default='',
            help='JSON-Ausgabe speichern (optional)',
        )
        parser.add_argument(
            '--max-chars', type=int, default=24000,
            help='Max. Textzeichen an DeepSeek (Default 24000)',
        )

    def handle(self, *args, **options):
        path = Path(options['file'])
        if not path.is_file():
            raise CommandError(f'Datei nicht gefunden: {path}')

        from apps.abpe_parser.services.resume_extract import abpe_resume_parser

        self.stdout.write(f'[abpe_parser] parse {path}')
        result = abpe_resume_parser.parse_file(
            str(path), max_chars=int(options['max_chars']),
        )

        text = json.dumps(result, ensure_ascii=False, indent=2)
        self.stdout.write(text)

        out = options.get('out') or ''
        if out:
            out_path = Path(out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(text, encoding='utf-8')
            self.stdout.write(self.style.SUCCESS(f'geschrieben: {out_path}'))

        if not result.get('success'):
            raise CommandError(result.get('error') or 'parse failed')
