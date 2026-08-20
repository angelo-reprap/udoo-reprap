"""
Cleanup Test-Importe aus AID-Pipeline (DB + optional Dateien/neu/cv).

  # Nur Inventar (nichts löschen)
  python3 manage.py cleanup_aid_test_imports

  # Bekannte Random-10 + Golden-Set Dirs
  python3 manage.py cleanup_aid_test_imports --preset random10 --dry-run
  python3 manage.py cleanup_aid_test_imports --preset random10 --yes

  # Alle aid_import Uploads seit Datum
  python3 manage.py cleanup_aid_test_imports --since 2026-08-01 --dry-run
  python3 manage.py cleanup_aid_test_imports --since 2026-08-01 --yes --neu-cv

  # Einzelne Dirs
  python3 manage.py cleanup_aid_test_imports --dir al-kenani_muhanned --dir troschke_thomas --yes

Löscht pro Treffer (wie delete_consultant_api):
  Consultant (+ Cascades), UploadedPDF, ConsultantVersion,
  data/{html_out,doc_out,extracted,pdf}/… wenn kein anderer Consultant denselben Dir nutzt.

Optional:
  --neu-cv   auch AID_profile/.../neu/cv/ leeren (nur Treffer-Dirs)
  --uploads  data/uploads/cv/aid_import/ Quell-Kopien der Treffer löschen
"""
from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime


# Random-10 Manifest 2026-08-14 + Golden-Set aus Batch-Skript
PRESETS = {
    'random10': [
        'mueller_mario', 'kobek_marco', 'knezevic_matija', 'reichel_thomas',
        'lorenz_michael', 'al-kenani_muhanned', 'seifried_martin',
        'nowka_matthias', 'pautsch_sven', 'nakonz_steffen',
    ],
    'golden': [
        'troschke_thomas', 'pfirrmann_peter', 'vogelgesang_oliver',
    ],
    'tests': [],  # random10 + golden, unten gefüllt
}
PRESETS['tests'] = PRESETS['random10'] + PRESETS['golden']


class Command(BaseCommand):
    help = 'Test-AID-Importe aus DB (+ optional neu/cv) entfernen'

    def add_arguments(self, parser):
        parser.add_argument(
            '--preset',
            choices=sorted(PRESETS.keys()),
            default='',
            help='Dir-Liste: random10 | golden | tests (=beides)',
        )
        parser.add_argument(
            '--dir', action='append', default=[], dest='dirs',
            help='consultant_dir (mehrfach)',
        )
        parser.add_argument(
            '--since', default='',
            help='Uploads/Consultants ab Datum (YYYY-MM-DD oder ISO)',
        )
        parser.add_argument(
            '--before', default='',
            help='Nur Consultants/Uploads VOR Datum (YYYY-MM-DD oder ISO) — Alt-Reste nach Re-Import',
        )
        parser.add_argument(
            '--any-source', action='store_true',
            help='Auch ohne aid_import (nur Dir/Since-Filter)',
        )
        parser.add_argument(
            '--neu-cv', action='store_true',
            help='Auch AID_profile/.../neu/cv/ der Treffer leeren',
        )
        parser.add_argument(
            '--uploads', action='store_true',
            help='Auch data/uploads/cv/aid_import Kopien der Treffer löschen',
        )
        parser.add_argument(
            '--dry-run', action='store_true', default=False,
            help='Nur listen (implizit wenn --yes fehlt)',
        )
        parser.add_argument(
            '--yes', action='store_true',
            help='Wirklich löschen (ohne --yes = Dry-Run)',
        )
        parser.add_argument(
            '--limit', type=int, default=0,
            help='Max. Consultants löschen (0=alle Treffer)',
        )

    def handle(self, *args, **opts):
        from apps.cv_extractor.models import (
            Consultant,
            ConsultantDirectory,
            ConsultantVersion,
            UploadedPDF,
        )
        from apps.cv_extractor.services.aid_profile_publish import (
            letter_bucket,
            resolve_aid_profile_root,
        )

        dirs = list(opts['dirs'] or [])
        preset = (opts['preset'] or '').strip()
        if preset:
            dirs.extend(PRESETS[preset])
        dirs = sorted(set(d.strip() for d in dirs if d and d.strip()))

        since = self._parse_since(opts['since'])
        aid_import_only = not opts['any_source']
        do_delete = bool(opts['yes']) and not opts['dry_run']
        # ohne --yes immer dry-run
        if not opts['yes']:
            do_delete = False

        self.stdout.write('=== cleanup_aid_test_imports ===')
        self.stdout.write(f'Modus:     {"DELETE" if do_delete else "DRY-RUN"}')
        self.stdout.write(f'Dirs:      {dirs or "(keine — nur since/aid_import)"}')
        self.stdout.write(f'Since:     {since or "(kein)"}')
        self.stdout.write(f'aid_import_only: {aid_import_only}')
        self.stdout.write(f'neu/cv:    {opts["neu_cv"]}')
        self.stdout.write(f'uploads:   {opts["uploads"]}')

        if not dirs and not since and aid_import_only:
            # Inventar: alle aid_import Uploads zeigen
            ups = UploadedPDF.objects.filter(action_type='aid_import').order_by('-created_at')
            self.stdout.write(f'\nUploadedPDF aid_import: {ups.count()}')
            for u in ups[:80]:
                self.stdout.write(
                    f"  {u.created_at:%Y-%m-%d %H:%M}  "
                    f"{u.target_directory or u.consultant_dir or '?':40s}  "
                    f"{u.aid or '-':20s}  {u.status}  {u.filename}"
                )
            if ups.count() > 80:
                self.stdout.write(f'  … +{ups.count() - 80} weitere')
            dir_names = set(
                ups.exclude(target_directory='')
                .values_list('target_directory', flat=True)
            ) | set(
                ups.exclude(consultant_dir='')
                .values_list('consultant_dir', flat=True)
            )
            cs = Consultant.objects.filter(consultant_dir__in=dir_names)
            self.stdout.write(f'\nConsultants zu diesen Dirs: {cs.count()}')
            for c in cs.order_by('consultant_dir')[:60]:
                self.stdout.write(
                    f"  {c.aid:22s}  {c.consultant_dir:35s}  "
                    f"{c.created_at:%Y-%m-%d}"
                )
            self.stdout.write(
                '\nWeiter z.B.:\n'
                '  python3 manage.py cleanup_aid_test_imports --preset tests --dry-run\n'
                '  python3 manage.py cleanup_aid_test_imports --since 2026-08-01 --dry-run\n'
                '  python3 manage.py cleanup_aid_test_imports --preset tests --yes --neu-cv'
            )
            return

        # UploadedPDF Treffer
        uq = UploadedPDF.objects.all()
        if aid_import_only:
            uq = uq.filter(action_type='aid_import')
        if dirs:
            uq = uq.filter(
                Q(target_directory__in=dirs) | Q(consultant_dir__in=dirs)
            )
        if since:
            uq = uq.filter(created_at__gte=since)

        upload_dirs = set()
        upload_aids = set()
        for u in uq:
            if u.target_directory:
                upload_dirs.add(u.target_directory)
            if u.consultant_dir:
                upload_dirs.add(u.consultant_dir)
            if u.aid:
                upload_aids.add(u.aid)

        # Consultants
        cq = Consultant.objects.all()
        if dirs or upload_dirs:
            want = set(dirs) | upload_dirs
            cq = cq.filter(consultant_dir__in=want)
        elif since:
            cq = cq.filter(created_at__gte=since)
        else:
            cq = cq.none()

        if aid_import_only and not dirs:
            # ohne explizite Dirs: nur Consultants die zu aid_import Uploads gehören
            cq = cq.filter(
                Q(aid__in=upload_aids) | Q(consultant_dir__in=upload_dirs)
            )

        consultants = list(cq.order_by('consultant_dir', 'aid'))
        if opts['limit']:
            consultants = consultants[: opts['limit']]

        self.stdout.write(f'\nTreffer UploadedPDF: {uq.count()}')
        self.stdout.write(f'Treffer Consultant:  {len(consultants)}')
        for c in consultants:
            self.stdout.write(
                f"  {c.aid:22s}  {c.consultant_dir:35s}  "
                f"{c.first_name} {c.last_name}  "
                f"created={c.created_at:%Y-%m-%d}"
            )

        if not do_delete:
            self.stdout.write(self.style.WARNING(
                '\nDry-Run — nichts gelöscht. Zum Löschen: dieselben Flags + --yes'
            ))
            return

        data_root = Path(settings.BASE_DIR) / 'data'
        aid_root = resolve_aid_profile_root()
        deleted_aids = []
        cleared_neu = []

        for c in consultants:
            aid = c.aid
            cdir = (c.consultant_dir or '').strip()
            others = (
                Consultant.objects.filter(consultant_dir=cdir)
                .exclude(aid=aid)
                .count()
                if cdir else 0
            )

            if others == 0 and cdir:
                for subdir in ('html_out', 'extracted', 'doc_out'):
                    p = data_root / subdir / cdir
                    if p.is_dir():
                        shutil.rmtree(p, ignore_errors=True)
                ConsultantDirectory.objects.filter(directory_name=cdir).delete()
                ConsultantVersion.objects.filter(consultant_dir=cdir).delete()
            else:
                for suffix in (f'{aid}.html', f'{aid}-short.html',
                               f'{aid}-en.html', f'{aid}-en-short.html'):
                    f = data_root / 'html_out' / cdir / suffix
                    if f.is_file():
                        f.unlink(missing_ok=True)
                for suffix in (f'{aid}.docx',):
                    f = data_root / 'doc_out' / cdir / suffix
                    if f.is_file():
                        f.unlink(missing_ok=True)
                ConsultantVersion.objects.filter(aid=aid).delete()

            pdf = data_root / 'pdf' / f'{aid}.pdf'
            if pdf.is_file():
                pdf.unlink(missing_ok=True)

            UploadedPDF.objects.filter(aid=aid).delete()
            if cdir:
                UploadedPDF.objects.filter(
                    action_type='aid_import',
                    target_directory=cdir,
                ).delete()
            c.delete()
            deleted_aids.append(aid)
            self.stdout.write(self.style.SUCCESS(f'  deleted {aid} ({cdir})'))

            if opts['neu_cv'] and cdir and aid_root:
                bucket = letter_bucket(cdir, last_name=c.last_name or '')
                neu = aid_root / bucket / cdir / 'neu' / 'cv'
                if neu.is_dir():
                    for f in neu.iterdir():
                        if f.is_file():
                            try:
                                f.unlink()
                            except OSError as e:
                                self.stderr.write(f'  neu/cv skip {f.name}: {e}')
                    cleared_neu.append(str(neu))
                    self.stdout.write(f'  cleared neu/cv {neu}')

        # Orphan Uploads (aid_import ohne Consultant)
        orphan_q = UploadedPDF.objects.filter(action_type='aid_import')
        if dirs:
            orphan_q = orphan_q.filter(
                Q(target_directory__in=dirs) | Q(consultant_dir__in=dirs)
            )
        if since:
            orphan_q = orphan_q.filter(created_at__gte=since)
        orphan_n = orphan_q.count()
        if orphan_n:
            orphan_q.delete()
            self.stdout.write(f'  orphan UploadedPDF deleted: {orphan_n}')

        if opts['uploads']:
            up_dir = data_root / 'uploads' / 'cv' / 'aid_import'
            if up_dir.is_dir():
                # nur Dateien deren Name zu gelöschten AIDs/Dirs passt — konservativ: alles unter aid_import wenn since+preset
                n = 0
                for f in up_dir.iterdir():
                    if not f.is_file():
                        continue
                    # AID-*.pdf Importe
                    if f.name.upper().startswith('AID-') or any(
                        d.replace('_', '') in f.name.lower().replace('_', '')
                        for d in dirs
                    ):
                        f.unlink(missing_ok=True)
                        n += 1
                self.stdout.write(f'  uploads/aid_import removed ~{n} files')

        self.stdout.write(self.style.SUCCESS(
            f'\nFertig: {len(deleted_aids)} Consultants gelöscht, '
            f'{len(cleared_neu)} neu/cv geleert'
        ))
        self.stdout.write(
            'Hinweis: Elasticsearch-Index ggf. manuell bereinigen '
            '(abpe_consultants_index), falls Suche Alt-Treffer zeigt.'
        )

    def _parse_since(self, raw: str):
        raw = (raw or '').strip()
        if not raw:
            return None
        dt = parse_datetime(raw)
        if dt is None:
            d = parse_date(raw)
            if d:
                dt = datetime(d.year, d.month, d.day)
        if dt is None:
            raise SystemExit(f'Ungültiges --since: {raw}')
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt
