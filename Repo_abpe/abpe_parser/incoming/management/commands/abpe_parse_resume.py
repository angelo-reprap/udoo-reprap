"""
abpe_parser — vereinigte Features (DeepSeek):

  OmkarPathak/ResumeParser  → Extract, Summary, Strengths, JD-Optimize
  orasik/resume-parser      → reiches Schema (basics/work/skills/certs/…)
  pushkar-hue/AI-Resume-Parser → Score, Match, Suggestions

Beispiele:
  python manage.py abpe_parse_resume /pfad/AID.pdf --out /tmp/out.json
  python manage.py abpe_parse_resume /pfad.pdf --score --suggest --out /tmp/out.json
  python manage.py abpe_parse_resume /pfad.pdf --jd /pfad/stelle.txt --match --suggest
"""
from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        'abpe_parser: PDF/DOCX → DeepSeek JSON '
        '(+ optional Score / JD-Match / Suggestions)'
    )

    def add_arguments(self, parser):
        parser.add_argument('file', type=str, help='Pfad zu PDF oder DOCX')
        parser.add_argument('--out', type=str, default='', help='JSON speichern')
        parser.add_argument(
            '--max-chars', type=int, default=24000,
            help='Max. Textzeichen an DeepSeek',
        )
        parser.add_argument(
            '--score', action='store_true',
            help='Coverage + Quality-Score (Default: an wenn --full)',
        )
        parser.add_argument(
            '--no-score', action='store_true',
            help='Score aus',
        )
        parser.add_argument(
            '--jd', type=str, default='',
            help='Job Description (Textdatei oder PDF/DOCX)',
        )
        parser.add_argument(
            '--match', action='store_true',
            help='JD-Match (braucht --jd; sonst auto wenn --jd gesetzt)',
        )
        parser.add_argument(
            '--suggest', action='store_true',
            help='AI-Verbesserungsvorschläge',
        )
        parser.add_argument(
            '--full', action='store_true',
            help='Score + Suggest (JD-Match wenn --jd)',
        )

    def handle(self, *args, **options):
        path = Path(options['file'])
        if not path.is_file():
            raise CommandError(f'Datei nicht gefunden: {path}')

        from apps.abpe_parser.services.pipeline import run_pipeline

        full = bool(options['full'])
        do_score = True
        if options['no_score']:
            do_score = False
        elif options['score'] or full:
            do_score = True
        # Default: immer score (billig, lokal) — außer --no-score
        if not options['score'] and not full and not options['no_score']:
            do_score = True

        do_suggest = bool(options['suggest'] or full)
        jd = options.get('jd') or ''
        do_match = bool(options['match'] or jd)

        self.stdout.write(
            f'[abpe_parser] {path.name} | score={do_score} '
            f'match={do_match} suggest={do_suggest}'
        )

        result = run_pipeline(
            file_path=str(path),
            jd_path=jd or None,
            do_score=do_score,
            do_match=do_match,
            do_suggest=do_suggest,
            max_chars=int(options['max_chars']),
        )

        text = json.dumps(result, ensure_ascii=False, indent=2)
        self.stdout.write(text)

        out = options.get('out') or ''
        if out:
            out_path = Path(out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(text, encoding='utf-8')
            self.stdout.write(self.style.SUCCESS(f'geschrieben: {out_path}'))

        # Kurz-Summary
        if result.get('success') and result.get('resume'):
            r = result['resume']
            q = (result.get('analysis') or {}).get('quality') or {}
            self.stdout.write(self.style.SUCCESS(
                f"OK | work={len(r.get('work') or [])} "
                f"skills={len(r.get('skills') or [])} "
                f"overall={q.get('overall_score', '—')}"
            ))

        if not result.get('success'):
            raise CommandError(result.get('error') or 'parse failed')
