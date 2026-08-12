"""
Bestehende AID-HTMLs offline-fähig machen (CSS/JS/Logo einbetten).

  cd /opt/abpe/backend
  python3 manage.py fix_html_offline --aid AID-mn_5.2.3.3
  python3 manage.py fix_html_offline --dir nowka_matthias
  python3 manage.py fix_html_offline --neu-cv   # nur Share neu/cv
  python3 manage.py fix_html_offline --all
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'HTML Offline-Embed (Inline CSS/JS + Logo Data-URI) für html_out und/oder neu/cv'

    def add_arguments(self, parser):
        parser.add_argument('--aid', default='')
        parser.add_argument('--dir', default='', dest='consultant_dir')
        parser.add_argument('--all', action='store_true')
        parser.add_argument(
            '--neu-cv', action='store_true',
            help='Auch/nur Dateien unter AID_profile/.../neu/cv patchen',
        )
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        from apps.cv_extractor.generator.cv_display_utils import (
            is_html_offline,
            make_html_offline_friendly,
        )
        from apps.cv_extractor.services.aid_profile_publish import (
            letter_bucket,
            resolve_aid_profile_root,
        )
        from apps.cv_extractor.models import Consultant

        targets = []
        base = Path(settings.BASE_DIR)

        qs = Consultant.objects.all()
        if opts['aid']:
            qs = qs.filter(aid=opts['aid'])
        elif opts['consultant_dir']:
            qs = qs.filter(consultant_dir=opts['consultant_dir'])
        elif not opts['all'] and not opts['neu_cv']:
            self.stderr.write('Bitte --aid, --dir, --neu-cv oder --all angeben')
            return

        # html_out aus DB-Consultants
        if opts['aid'] or opts['consultant_dir'] or opts['all']:
            for c in qs.iterator():
                cdir = c.consultant_dir or ''
                if not cdir:
                    continue
                for name in (f'{c.aid}.html', f'{c.aid}-short.html'):
                    p = base / 'data' / 'html_out' / cdir / name
                    if p.is_file():
                        targets.append((p, getattr(c, 'language', 'de') or 'de', cdir, c.last_name or ''))

        # neu/cv Share
        if opts['neu_cv'] or opts['all'] or opts['aid'] or opts['consultant_dir']:
            root = resolve_aid_profile_root()
            if root:
                seen = set()
                for c in qs.iterator() if (opts['aid'] or opts['consultant_dir'] or opts['all']) else []:
                    cdir = c.consultant_dir or ''
                    if not cdir:
                        continue
                    bucket = letter_bucket(cdir, last_name=c.last_name or '')
                    neu = root / bucket / cdir / 'neu' / 'cv'
                    for p in neu.glob('AID-*.html'):
                        key = str(p)
                        if key not in seen:
                            seen.add(key)
                            targets.append((p, getattr(c, 'language', 'de') or 'de', cdir, c.last_name or ''))
                if opts['neu_cv'] and not (opts['aid'] or opts['consultant_dir'] or opts['all']):
                    # alle HTML unter neu/cv
                    for p in root.glob('*/*/neu/cv/AID-*.html'):
                        targets.append((p, 'de', '', ''))

        # dedup paths
        uniq = {}
        for t in targets:
            uniq[str(t[0])] = t
        targets = list(uniq.values())

        fixed = 0
        skipped = 0
        for path, lang, _cdir, _last in targets:
            raw = path.read_text(encoding='utf-8', errors='replace')
            if is_html_offline(raw):
                skipped += 1
                continue
            new = make_html_offline_friendly(raw, base_dir=str(base), language=lang)
            if opts['dry_run']:
                self.stdout.write(f'DRY-RUN would fix {path}')
                continue
            if new == raw:
                self.stderr.write(f'WARN unchanged (Assets?): {path}')
                continue
            path.write_text(new, encoding='utf-8')
            fixed += 1
            self.stdout.write(self.style.SUCCESS(f'FIXED {path}'))

        self.stdout.write(f'Done: fixed={fixed} already_offline={skipped} total={len(targets)}')
