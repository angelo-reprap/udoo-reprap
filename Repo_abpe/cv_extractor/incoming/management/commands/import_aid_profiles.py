"""
Management Command: import_aid_profiles
Importiert abcona AID-Profile EXAKT wie ein manueller Upload:
  PDF kopieren → UploadedPDF anlegen → process_pdf_task (sync oder async)
  → erscheint in upload.html mit Status-Updates
  → nach HTML: Spiegel nach …/AID_profile/{lll}/{dir}/neu/cv/ (html/docx/pdf)

Aufruf:
  python3 manage.py import_aid_profiles --limit 20 --sync   # Test synchron
  python3 manage.py import_aid_profiles --letter kkk --sync  # Einen Buchstaben
  python3 manage.py import_aid_profiles --dir troschke_thomas --sync
  python3 manage.py import_aid_profiles                      # Alle via Celery
  python3 manage.py import_aid_profiles --dry-run            # Nur prüfen
"""
import os
import re
import time
import shutil
import logging
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings

logger = logging.getLogger(__name__)

_DEFAULT_ROOTS = (
    '/mnt/public/Berater/AID_profile',
    '/var/share/public/Berater/AID_profile',
)
SKIP_DIRS = {
    'gulp_id', 'Anfragen', 'Auftragsbestätigung',
    'xxx', 'zzzSONSTIGES', 'aaa_low-level', 'aaaMuster',
    'neu',  # nie neu/ als Letter-Bucket
}

# Keine Berater-Profile (Ordner unter Letter-Bucket)
SKIP_PERSON_DIRS = {
    'audit', 'neu',
    'Neuer Ordner', 'Neuer Ordner (2)', 'Neuer Ordner (3)',
    'ada',  # Unterordner mit fremden Profilen, kein eigener Berater
}


def resolve_aid_profile_root() -> Path:
    env = os.environ.get('AID_PROFILE_ROOT', '').strip()
    candidates = [env] if env else []
    candidates.extend(_DEFAULT_ROOTS)
    for raw in candidates:
        if not raw:
            continue
        p = Path(raw)
        if p.is_dir():
            return p
    return Path(candidates[0] if candidates else _DEFAULT_ROOTS[0])


def get_best_pdf(folder: Path):
    """
    Neuestes deutsches AID-*.pdf direkt im Person-Ordner (mtime).

    Ausgeschlossen:
      - Englisch (_engl, _en., -en., _en_, _Englisch)
      - Alt-/Lösch-Varianten (_alt, löschen, alt im Namen)
      - Unterordner (alt/, AID_alt/, neu/cv/, …) — nur folder/*.pdf
    Fallback: neuestes beliebiges deutsches PDF im Ordner.
    """
    def is_german(p: Path) -> bool:
        n = p.name.lower()
        return not any(x in n for x in (
            'engl', '_en.', '-en.', '_en_', 'englisch',
        ))

    def is_junk_variant(p: Path) -> bool:
        n = p.name.lower()
        return any(x in n for x in (
            '_alt', '-alt', 'löschen', 'loeschen', ' delete',
        ))

    def score(p: Path):
        # höher = besser: mtime, dann „sauberer“ AID-Name
        mtime = p.stat().st_mtime
        clean = 1 if re.match(
            r'(?i)^AID-[A-Za-z]{1,5}_\d+\.\d+\.\d+\.\d+\.pdf$', p.name
        ) else 0
        return (mtime, clean)

    aid_pdfs = [
        p for p in folder.glob('AID-*.pdf')
        if p.is_file() and is_german(p) and not is_junk_variant(p)
    ]
    if aid_pdfs:
        return sorted(aid_pdfs, key=score, reverse=True)[0]

    all_pdfs = [
        p for p in folder.glob('*.pdf')
        if p.is_file() and is_german(p) and not is_junk_variant(p)
    ]
    if all_pdfs:
        return sorted(all_pdfs, key=score, reverse=True)[0]

    return None


def name_from_dir(dir_name: str):
    """nachname_vorname → (Vorname, Nachname)"""
    clean = re.sub(r'-\d+$', '', dir_name.strip())
    parts = clean.split('_')
    if len(parts) >= 2:
        last = parts[0].capitalize()
        first = ' '.join(p.capitalize() for p in parts[1:])
        return first, last
    return 'Unbekannt', dir_name.capitalize()


class Command(BaseCommand):
    help = 'Importiert abcona AID-Profile als echte Uploads (sichtbar in upload.html)'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=0,
                            help='Max. Anzahl Profile (0=alle)')
        parser.add_argument('--letter', type=str, default='',
                            help='Nur diesen Ordner (z.B. kkk)')
        parser.add_argument('--dir', type=str, default='',
                            help='Nur diesen Person-Ordner (z.B. troschke_thomas)')
        parser.add_argument('--dry-run', action='store_true',
                            help='Nur prüfen, nicht importieren')
        parser.add_argument('--no-skip-existing', action='store_true',
                            help='Auch bereits importierte nochmal importieren')
        parser.add_argument('--sync', action='store_true',
                            help='Synchron statt Celery (für Tests)')
        parser.add_argument('--root', type=str, default='',
                            help='AID_profile Root (Default: /mnt/public/... oder Env)')

    def handle(self, *args, **options):
        from apps.cv_extractor.models import Consultant, UploadedPDF
        from apps.cv_extractor.tasks import process_pdf_task

        limit = options['limit']
        letter_filter = options['letter'].lower()
        dir_filter = options['dir'].strip()
        dry_run = options['dry_run']
        skip_existing = not options['no_skip_existing']
        sync_mode = options['sync']
        base_dir = Path(options['root']) if options['root'] else resolve_aid_profile_root()

        upload_base = Path(settings.BASE_DIR) / 'data' / 'uploads' / 'cv' / 'aid_import'
        upload_base.mkdir(parents=True, exist_ok=True)

        self.stdout.write('=== AID-Profil Import ===')
        self.stdout.write(f'Basis:    {base_dir} (exists={base_dir.is_dir()})')
        self.stdout.write(f'Limit:    {limit or "alle"}')
        self.stdout.write(f'Letter:   {letter_filter or "alle"}')
        self.stdout.write(f'Dir:      {dir_filter or "alle"}')
        self.stdout.write(f'Dry-run:  {dry_run}')
        self.stdout.write(f'Sync:     {sync_mode}')
        self.stdout.write(f'Skip existing: {skip_existing}')

        if not base_dir.is_dir():
            self.stderr.write(self.style.ERROR(
                f'AID_profile Root fehlt: {base_dir}\n'
                f'  Setze AID_PROFILE_ROOT oder --root /mnt/public/Berater/AID_profile'
            ))
            return

        stats = {'total': 0, 'ok': 0, 'error': 0, 'skip': 0, 'no_pdf': 0}
        t_start = time.time()

        for letter_dir in sorted(base_dir.iterdir()):
            if not letter_dir.is_dir():
                continue
            if letter_dir.name in SKIP_DIRS:
                continue
            if letter_filter and letter_dir.name != letter_filter:
                continue

            for person_dir in sorted(letter_dir.iterdir()):
                if not person_dir.is_dir():
                    continue
                if person_dir.name in ('neu',) or person_dir.name in SKIP_PERSON_DIRS:
                    continue
                if person_dir.name.lower().startswith('neuer ordner'):
                    continue
                if dir_filter and person_dir.name != dir_filter:
                    continue
                if limit and stats['total'] >= limit:
                    break

                pdf = get_best_pdf(person_dir)
                if not pdf:
                    stats['no_pdf'] += 1
                    continue

                dir_name = person_dir.name
                first_name, last_name = name_from_dir(dir_name)
                stats['total'] += 1

                if skip_existing:
                    if Consultant.objects.filter(consultant_dir=dir_name).exists():
                        stats['skip'] += 1
                        continue

                self.stdout.write(
                    f'  [{stats["total"]:4d}] {first_name} {last_name}'
                    f' ← {pdf.name}'
                )

                if dry_run:
                    stats['ok'] += 1
                    continue

                try:
                    dest_path = upload_base / pdf.name
                    shutil.copy2(str(pdf), str(dest_path))

                    rel_path = dest_path.relative_to(
                        Path(settings.BASE_DIR) / 'data'
                    )

                    # WICHTIG: Signal start_pipeline_on_new_pdf startet bei
                    # status='uploaded' automatisch Celery. Deshalb:
                    #   --sync  → status=processing (kein Signal), dann sync call
                    #   async   → status=uploaded, NUR Signal (kein .delay())
                    if sync_mode:
                        upload = UploadedPDF.objects.create(
                            file=str(rel_path),
                            filename=pdf.name,
                            first_name=first_name,
                            last_name=last_name,
                            target_directory=dir_name,
                            action_type='aid_import',
                            status='processing',
                        )
                        result = process_pdf_task(upload.id)
                        if result.get('success'):
                            neu = person_dir / 'neu' / 'cv'
                            neu_pdfs = (
                                sorted(neu.glob('AID-*.pdf'))
                                if neu.is_dir() else []
                            )
                            if neu_pdfs:
                                stats['ok'] += 1
                                self.stdout.write(
                                    f"    ✅ {result.get('aid', '?')}"
                                )
                                files = sorted(
                                    p.name for p in neu.iterdir() if p.is_file()
                                )
                                self.stdout.write(
                                    f"    📁 neu/cv: {', '.join(files)}"
                                )
                            else:
                                # Pipeline OK, aber Publish fehlt → kein Import-OK
                                stats['error'] += 1
                                self.stdout.write(
                                    f"    ❌ {result.get('aid', '?')} — "
                                    f"Pipeline OK, aber kein neu/cv AID-*.pdf "
                                    f"unter {neu}"
                                )
                                self.stderr.write(
                                    self.style.ERROR(
                                        f'no_neu_cv: {dir_name} '
                                        f'(aid={result.get("aid", "?")})'
                                    )
                                )
                        else:
                            stats['error'] += 1
                            self.stdout.write(
                                f"    ❌ {result.get('error', '?')[:100]}"
                            )
                    else:
                        UploadedPDF.objects.create(
                            file=str(rel_path),
                            filename=pdf.name,
                            first_name=first_name,
                            last_name=last_name,
                            target_directory=dir_name,
                            action_type='aid_import',
                            status='uploaded',  # Signal startet Celery einmal
                        )
                        stats['ok'] += 1
                        self.stdout.write(
                            '    ⏳ Signal → Celery → upload.html → neu/cv/'
                        )

                except Exception as e:
                    stats['error'] += 1
                    self.stdout.write(f'    ❌ {str(e)[:100]}')
                    logger.exception(f'Import {dir_name}: {e}')

            if limit and stats['total'] >= limit:
                break

        dur = time.time() - t_start
        self.stdout.write(f"\n{'=' * 50}")
        self.stdout.write(f'ERGEBNIS nach {dur:.0f}s ({dur / 60:.1f} min):')
        self.stdout.write(f"  Versucht:     {stats['total']}")
        self.stdout.write(f"  Gestartet:    {stats['ok']}")
        self.stdout.write(f"  Fehler:       {stats['error']}")
        self.stdout.write(f"  Übersprungen: {stats['skip']}")
        self.stdout.write(f"  Ohne PDF:     {stats['no_pdf']}")
        self.stdout.write('  Outputs:      {letter}/{nachname_vorname}/neu/cv/')
