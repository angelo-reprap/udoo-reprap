"""
Management Command: import_aid_profiles
Importiert abcona AID-Profile EXAKT wie ein manueller Upload:
  PDF kopieren → UploadedPDF anlegen → process_pdf_task (sync oder async)
  → erscheint in upload.html mit Status-Updates

Aufruf:
  python3 manage.py import_aid_profiles --limit 20 --sync   # Test synchron
  python3 manage.py import_aid_profiles --letter kkk --sync  # Einen Buchstaben
  python3 manage.py import_aid_profiles                      # Alle via Celery
  python3 manage.py import_aid_profiles --dry-run            # Nur prüfen
"""
import re, time, shutil, logging
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings

logger = logging.getLogger(__name__)

BASE_DIR  = Path('/var/share/public/Berater/AID_profile')
SKIP_DIRS = {
    'gulp_id','Anfragen','Auftragsbestätigung',
    'xxx','zzzSONSTIGES','aaa_low-level','aaaMuster'
}


def get_best_pdf(folder: Path) -> Path:
    """
    Neuestes deutsches AID-*.pdf nach Änderungsdatum (mtime).
    Englische Versionen (_engl, _en., -en., _en_) werden ausgeschlossen.
    Fallback: neuestes beliebiges deutsches PDF.
    """
    def is_german(p):
        n = p.name.lower()
        return not any(x in n for x in ['engl', '_en.', '-en.', '_en_'])

    aid_pdfs = [p for p in folder.glob('AID-*.pdf') if is_german(p)]
    if aid_pdfs:
        return sorted(aid_pdfs, key=lambda p: p.stat().st_mtime, reverse=True)[0]

    all_pdfs = [p for p in folder.glob('*.pdf') if is_german(p)]
    if all_pdfs:
        return sorted(all_pdfs, key=lambda p: p.stat().st_mtime, reverse=True)[0]

    return None


def name_from_dir(dir_name: str):
    """nachname_vorname → (Vorname, Nachname)"""
    clean = re.sub(r'-\d+$', '', dir_name.strip())
    parts = clean.split('_')
    if len(parts) >= 2:
        last  = parts[0].capitalize()
        first = ' '.join(p.capitalize() for p in parts[1:])
        return first, last
    return 'Unbekannt', dir_name.capitalize()


class Command(BaseCommand):
    help = 'Importiert abcona AID-Profile als echte Uploads (sichtbar in upload.html)'

    def add_arguments(self, parser):
        parser.add_argument('--limit',           type=int, default=0,
                            help='Max. Anzahl Profile (0=alle)')
        parser.add_argument('--letter',          type=str, default='',
                            help='Nur diesen Ordner (z.B. kkk)')
        parser.add_argument('--dry-run',         action='store_true',
                            help='Nur prüfen, nicht importieren')
        parser.add_argument('--no-skip-existing',action='store_true',
                            help='Auch bereits importierte nochmal importieren')
        parser.add_argument('--sync',            action='store_true',
                            help='Synchron statt Celery (für Tests)')

    def handle(self, *args, **options):
        from apps.cv_extractor.models import Consultant, UploadedPDF
        from apps.cv_extractor.tasks import process_pdf_task

        limit         = options['limit']
        letter_filter = options['letter'].lower()
        dry_run       = options['dry_run']
        skip_existing = not options['no_skip_existing']
        sync_mode     = options['sync']

        # Upload-Verzeichnis für AID-Importe
        upload_base = Path(settings.BASE_DIR) / 'data' / 'uploads' / 'cv' / 'aid_import'
        upload_base.mkdir(parents=True, exist_ok=True)

        self.stdout.write(f"=== AID-Profil Import ===")
        self.stdout.write(f"Basis:    {BASE_DIR}")
        self.stdout.write(f"Limit:    {limit or 'alle'}")
        self.stdout.write(f"Letter:   {letter_filter or 'alle'}")
        self.stdout.write(f"Dry-run:  {dry_run}")
        self.stdout.write(f"Sync:     {sync_mode}")
        self.stdout.write(f"Skip existing: {skip_existing}")

        stats = {'total':0,'ok':0,'error':0,'skip':0,'no_pdf':0}
        t_start = time.time()

        for letter_dir in sorted(BASE_DIR.iterdir()):
            if not letter_dir.is_dir():
                continue
            if letter_dir.name in SKIP_DIRS:
                continue
            if letter_filter and letter_dir.name != letter_filter:
                continue

            for person_dir in sorted(letter_dir.iterdir()):
                if not person_dir.is_dir():
                    continue
                if limit and stats['total'] >= limit:
                    break

                pdf = get_best_pdf(person_dir)
                if not pdf:
                    stats['no_pdf'] += 1
                    continue

                dir_name              = person_dir.name
                first_name, last_name = name_from_dir(dir_name)
                stats['total'] += 1

                # Bereits importiert?
                if skip_existing:
                    if Consultant.objects.filter(consultant_dir=dir_name).exists():
                        stats['skip'] += 1
                        continue

                self.stdout.write(
                    f"  [{stats['total']:4d}] {first_name} {last_name}"
                    f" ← {pdf.name}"
                )

                if dry_run:
                    stats['ok'] += 1
                    continue

                try:
                    # PDF ins Upload-Verzeichnis kopieren
                    dest_path = upload_base / pdf.name
                    shutil.copy2(str(pdf), str(dest_path))

                    # Relativer Pfad für FileField
                    rel_path = dest_path.relative_to(
                        Path(settings.BASE_DIR) / 'data'
                    )

                    # UploadedPDF anlegen — exakt wie echter Upload
                    upload = UploadedPDF.objects.create(
                        file             = str(rel_path),
                        filename         = pdf.name,
                        first_name       = first_name,
                        last_name        = last_name,
                        target_directory = dir_name,
                        action_type      = 'aid_import',
                        status           = 'uploaded',
                    )

                    if sync_mode:
                        # Synchron — blockiert, für Tests
                        result = process_pdf_task(upload.id)
                        if result.get('success'):
                            stats['ok'] += 1
                            self.stdout.write(
                                f"    ✅ {result.get('aid','?')}"
                            )
                        else:
                            stats['error'] += 1
                            self.stdout.write(
                                f"    ❌ {result.get('error','?')[:100]}"
                            )
                    else:
                        # Asynchron via Celery — erscheint in upload.html
                        task = process_pdf_task.delay(upload.id)
                        stats['ok'] += 1
                        self.stdout.write(
                            f"    ⏳ Task gestartet → upload.html"
                        )

                except Exception as e:
                    stats['error'] += 1
                    self.stdout.write(f"    ❌ {str(e)[:100]}")
                    logger.exception(f"Import {dir_name}: {e}")

            if limit and stats['total'] >= limit:
                break

        dur = time.time() - t_start
        self.stdout.write(f"\n{'='*50}")
        self.stdout.write(f"ERGEBNIS nach {dur:.0f}s ({dur/60:.1f} min):")
        self.stdout.write(f"  Versucht:     {stats['total']}")
        self.stdout.write(f"  Gestartet:    {stats['ok']}")
        self.stdout.write(f"  Fehler:       {stats['error']}")
        self.stdout.write(f"  Übersprungen: {stats['skip']}")
        self.stdout.write(f"  Kein PDF:     {stats['no_pdf']}")
        if not sync_mode and not dry_run and stats['ok'] > 0:
            self.stdout.write(f"\n  → {stats['ok']} Tasks laufen via Celery")
            self.stdout.write(f"  → Status in upload.html sichtbar")
