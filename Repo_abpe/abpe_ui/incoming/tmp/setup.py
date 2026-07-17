"""
setup.py — Email Studio WYSIWYG Installer
Aufruf: python3 apps/abpe_ui/tmp/setup.py
        aus /opt/abpe/backend/

Was passiert:
  1. Sichert alle Zieldateien per backup_restore.py
  2. Kopiert neue Dateien an die richtigen Stellen
  3. Prueft Ergebnis
"""
import sys
import os
import shutil
import subprocess
from pathlib import Path

BASE = Path(__file__).parent.parent.parent.parent  # /opt/abpe/backend
TMP  = Path(__file__).parent                        # apps/abpe_ui/tmp

print(f'BASE: {BASE}')
print(f'TMP:  {TMP}')
print()

# ── Mapping: Quelle (in tmp/) → Ziel (relativ zu BASE) ────────────────────────
FILES = [
    (
        TMP / 'studio.html',
        BASE / 'apps/abpe_ui/templates/abpe_ui/modules/email_studio/studio.html',
    ),
    (
        TMP / 'mod-email_studio-delta.css',
        BASE / 'apps/abpe_ui/static/abpe_ui/css/mod/mod-email_studio-delta.css',
    ),
    (
        TMP / 'es-studio.js',
        BASE / 'staticfiles/email_studio/js/es-studio.js',
    ),
]

BACKUP_SCRIPT = BASE / 'apps/abpe_ui/backup_restore.py'

def backup(path_rel):
    """Sichert eine Datei per backup_restore.py."""
    result = subprocess.run(
        [sys.executable, str(BACKUP_SCRIPT), '-save', str(path_rel),
         '-m', 'vor: WYSIWYG Email Studio Install'],
        cwd=str(BASE),
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print(f'  ✓ Backup: {path_rel}')
    else:
        print(f'  ⚠ Backup fehlgeschlagen (OK wenn Datei neu): {path_rel}')

def check_source_files():
    """Prueft ob alle Quelldateien vorhanden sind."""
    ok = True
    for src, _ in FILES:
        if src.exists():
            print(f'  ✓ Quelle vorhanden: {src.name}')
        else:
            print(f'  ✗ Quelle FEHLT: {src}')
            ok = False
    return ok

def install():
    """Kopiert alle Dateien."""
    errors = []
    for src, dst in FILES:
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            # Backup nur wenn Zieldatei existiert
            if dst.exists():
                rel = dst.relative_to(BASE)
                backup(str(rel))
            shutil.copy2(str(src), str(dst))
            print(f'  ✓ Installiert: {dst.relative_to(BASE)}')
        except Exception as e:
            print(f'  ✗ Fehler bei {dst.name}: {e}')
            errors.append(str(e))
    return errors

def append_css_delta():
    """
    Haengt das CSS-Delta an mod-email_studio.css an —
    nur wenn die Delta-Datei neu angelegt wurde.
    Prueft vorher ob die Klassen schon drin sind.
    """
    main_css  = BASE / 'apps/abpe_ui/static/abpe_ui/css/mod/mod-email_studio.css'
    delta_css = BASE / 'apps/abpe_ui/static/abpe_ui/css/mod/mod-email_studio-delta.css'

    if not delta_css.exists():
        print('  ⚠ Delta-CSS nicht gefunden, ueberspringe Append')
        return

    if not main_css.exists():
        print('  ⚠ Haupt-CSS nicht gefunden, ueberspringe Append')
        return

    main_content  = main_css.read_text(encoding='utf-8')
    delta_content = delta_css.read_text(encoding='utf-8')

    if 'es-studio-layout' in main_content:
        print('  ℹ CSS-Delta bereits in mod-email_studio.css enthalten')
        return

    backup(str(main_css.relative_to(BASE)))

    with open(str(main_css), 'a', encoding='utf-8') as f:
        f.write('\n\n')
        f.write(delta_content)

    print(f'  ✓ CSS-Delta angehaengt an mod-email_studio.css')

def copy_js_to_static():
    """
    Kopiert es-studio.js auch in apps/abpe_email_studio/static/
    damit collectstatic es findet.
    """
    src = BASE / 'staticfiles/email_studio/js/es-studio.js'
    dst = BASE / 'apps/abpe_email_studio/static/email_studio/js/es-studio.js'
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dst))
        print(f'  ✓ JS auch nach apps/.../static/ kopiert')
    else:
        print('  ⚠ JS-Quelle nicht gefunden fuer static-Kopie')

def check_django():
    """Fuehrt python manage.py check aus."""
    result = subprocess.run(
        [sys.executable, 'manage.py', 'check'],
        cwd=str(BASE),
        capture_output=True,
        text=True
    )
    if 'no issues' in result.stdout or 'no issues' in result.stderr:
        print('  ✓ Django check: keine Fehler')
        return True
    else:
        print('  ⚠ Django check Ausgabe:')
        print(result.stdout[-500:] if result.stdout else '')
        print(result.stderr[-500:] if result.stderr else '')
        return False

# ── MAIN ──────────────────────────────────────────────────────────────────────

print('=' * 60)
print('Email Studio WYSIWYG Installer')
print('=' * 60)
print()

print('Schritt 1: Quelldateien pruefen...')
if not check_source_files():
    print('\n✗ Quelldateien fehlen — Abbruch')
    sys.exit(1)
print()

print('Schritt 2: Dateien installieren...')
errors = install()
print()

print('Schritt 3: CSS-Delta anhängen...')
append_css_delta()
print()

print('Schritt 4: JS in apps/static/ kopieren...')
copy_js_to_static()
print()

print('Schritt 5: Django check...')
check_django()
print()

if errors:
    print(f'✗ {len(errors)} Fehler aufgetreten:')
    for e in errors:
        print(f'  - {e}')
    sys.exit(1)
else:
    print('=' * 60)
    print('✓ Installation abgeschlossen!')
    print()
    print('Naechste Schritte:')
    print('  python manage.py collectstatic --noinput')
    print('  supervisorctl restart abpe-django')
    print('=' * 60)
