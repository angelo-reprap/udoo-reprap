"""
Management Command: publish_neu_cv
Publiziert vorhandene Consultant-Outputs nach
  /mnt/public/Berater/AID_profile/{lll}/{consultant_dir}/neu/cv/

Aufruf:
  python3 manage.py publish_neu_cv --aid AID-tt_1.2.4.2
  python3 manage.py publish_neu_cv --dir troschke_thomas
  python3 manage.py publish_neu_cv --limit 5
  python3 manage.py publish_neu_cv --all
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Kopiert HTML/DOCX (+PDF) nach AID_profile/.../neu/cv/ (chmod 0666/0777)'

    def add_arguments(self, parser):
        parser.add_argument('--aid', type=str, default='', help='Eine AID')
        parser.add_argument('--dir', type=str, default='', help='consultant_dir')
        parser.add_argument('--limit', type=int, default=0, help='Max. Anzahl')
        parser.add_argument('--all', action='store_true', help='Alle profile_ready')
        parser.add_argument('--no-word', action='store_true', help='Kein Word erzeugen')
        parser.add_argument('--no-pdf', action='store_true', help='Kein PDF erzeugen')

    def handle(self, *args, **options):
        from apps.cv_extractor.models import Consultant
        from apps.cv_extractor.services.aid_profile_publish import (
            publish_consultant_outputs,
            resolve_aid_profile_root,
        )

        root = resolve_aid_profile_root()
        self.stdout.write(f'AID_profile Root: {root}')

        qs = Consultant.objects.all().order_by('-updated_at')
        if options['aid']:
            qs = qs.filter(aid=options['aid'])
        elif options['dir']:
            qs = qs.filter(consultant_dir=options['dir'])
        elif options['all']:
            qs = qs.filter(status__in=('profile_ready', 'enriched', 'completed'))
        else:
            self.stderr.write('Bitte --aid, --dir oder --all angeben')
            return

        if options['limit']:
            qs = qs[: options['limit']]

        make_word = not options['no_word']
        make_pdf = not options['no_pdf']
        ok = err = 0

        for c in qs:
            self.stdout.write(f'  {c.aid} ({c.consultant_dir}) …')
            res = publish_consultant_outputs(
                c, make_word=make_word, make_pdf=make_pdf,
            )
            if res.get('success'):
                ok += 1
                files = ', '.join(
                    Path_name(p) for p in (res.get('files') or [])
                )
                self.stdout.write(f"    ✅ {res.get('neu_cv')} → {files}")
            else:
                err += 1
                self.stdout.write(f"    ❌ {res.get('error')}")

        self.stdout.write(f'\nFertig: {ok} ok, {err} Fehler')


def Path_name(p: str) -> str:
    from pathlib import Path
    return Path(p).name
