"""
Idempotente Prompt-Patches für cv_extractor PromptTemplate (DB).

Aufruf auf ucs5:
  cd /opt/abpe/backend
  python3 manage.py patch_prompt_template
  python3 manage.py patch_prompt_template --dry-run
  python3 manage.py patch_prompt_template --stage main_extract_personal
"""
from django.core.management.base import BaseCommand


# Marker → Patch wird nur einmal eingefügt
PATCHES = {
    'main_extract_personal': {
        'marker': '<!-- PATCH:edu-dedup-v1 -->',
        'append': '''
<!-- PATCH:edu-dedup-v1 -->
## Ausbildung (streng, Dedup)
- Pro Ausbildungsabschluss GENAU EINEN Eintrag in education[].
- degree = die vollständige Ausbildungszeile wie im CV
  (Beispiel: "Fernstudium Programmierer ILS Hamburg, Germany").
- institution nur setzen, wenn der Institutionsname NICHT bereits in degree vorkommt.
  Sonst institution="" lassen (verhindert doppelte Ausgabe "… @ Institution").
- Curriculum-/Schwerpunkt-Bullets unter Ausbildung (z.B. "Software Engineering",
  "Programmiersprachen Cobol, C/C++") gehören nach description — NICHT als eigene
  education-Einträge und NICHT als Skills.
- Keine zweite Kurzform wie degree="Programmierer" + institution="ILS …", wenn die
  volle Zeile schon erfasst ist oder im Text steht.
- education_type für Studium/Ausbildung/Lehre = "degree"; für reine Kurse/Schulungen
  nicht hier — die kommen aus dem Schulungen-Block.
'''.strip(),
    },
    'main_extract_schulungen': {
        'marker': '<!-- PATCH:schulungen-clean-v1 -->',
        'append': '''
<!-- PATCH:schulungen-clean-v1 -->
## Schulungen / Kurse (streng)
- Nur echte Kurs-/Schulungsnamen als education-Einträge (education_type=course).
- Keine Projektblöcke (Zeitraum/Firma/Projektbeschreibung) als Schulung.
- Keine Sektions-Header ("Schulungen", "Schulungen / Kurse", "Examen").
- Keine Duplikate zu bereits genannten Zertifizierungen, außer der Name ist klar ein Kurs.
'''.strip(),
    },
}


class Command(BaseCommand):
    help = 'Patched PromptTemplate.prompt_text idempotent (Ausbildung-Dedup etc.)'

    def add_arguments(self, parser):
        parser.add_argument('--stage', default='', help='Nur diese stage patchen')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        from apps.cv_extractor.models import PromptTemplate

        stages = [opts['stage']] if opts['stage'] else list(PATCHES.keys())
        dry = opts['dry_run']
        for stage in stages:
            patch = PATCHES.get(stage)
            if not patch:
                self.stderr.write(f'SKIP unknown stage: {stage}')
                continue
            pt = PromptTemplate.objects.filter(stage=stage, is_active=True).first()
            if not pt:
                self.stderr.write(f'MISSING active PromptTemplate: {stage}')
                continue
            text = pt.prompt_text or ''
            marker = patch['marker']
            if marker in text:
                self.stdout.write(f'OK already patched: {stage}')
                continue
            new_text = text.rstrip() + '\n\n' + patch['append'] + '\n'
            if dry:
                self.stdout.write(f'DRY-RUN would patch {stage} (+{len(patch["append"])} chars)')
                continue
            pt.prompt_text = new_text
            # version bump wenn Feld existiert
            if hasattr(pt, 'version') and pt.version is not None:
                try:
                    pt.version = int(pt.version) + 1
                except (TypeError, ValueError):
                    pass
            pt.save()
            self.stdout.write(self.style.SUCCESS(f'PATCHED {stage}'))
