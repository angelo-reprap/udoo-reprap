#!/usr/bin/env python3
"""
backup_restore.py - Backup & Restore Helper für ABpE Portal

Aufruf (aus /opt/abpe/backend/):
    python apps/abpe_ui/backup_restore.py -save apps/abpe_ui/models.py -m "Grund"
    python apps/abpe_ui/backup_restore.py -list
    python apps/abpe_ui/backup_restore.py -list apps/abpe_ui/models.py
    python apps/abpe_ui/backup_restore.py -list --date 2026-05-16
    python apps/abpe_ui/backup_restore.py -restore apps/abpe_ui/models.py
    python apps/abpe_ui/backup_restore.py -restore apps/abpe_ui/models.py --version 20260516_143022
    python apps/abpe_ui/backup_restore.py -delete apps/abpe_ui/models.py --version 20260516_143022
    python apps/abpe_ui/backup_restore.py -cleanup --days 30
    python apps/abpe_ui/backup_restore.py -man
"""

import os
import sys
import json
import shutil
import hashlib
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# ============================================================
# KONFIGURATION
# ============================================================
BASE_DIR    = Path('/opt/abpe/backend')
ABPE_UI_DIR = BASE_DIR / 'apps' / 'abpe_ui'
ARCHIVE_DIR = ABPE_UI_DIR / 'archive'
INDEX_FILE  = ARCHIVE_DIR / 'index.json'

# ============================================================
# FARBEN
# ============================================================
class C:
    G = '\033[92m'
    Y = '\033[93m'
    R = '\033[91m'
    B = '\033[94m'
    CY= '\033[96m'
    X = '\033[0m'
    BD= '\033[1m'

def ok(msg):   print(f"{C.G}✓{C.X} {msg}")
def err(msg):  print(f"{C.R}✗{C.X} {msg}")
def warn(msg): print(f"{C.Y}⚠{C.X} {msg}")
def info(msg): print(f"{C.B}ℹ{C.X} {msg}")
def head(msg): print(f"\n{C.CY}{C.BD}{msg}{C.X}")

# ============================================================
# ARCHIVE INIT
# ============================================================
def ensure_archive():
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    gi = ARCHIVE_DIR / '.gitignore'
    if not gi.exists():
        gi.write_text('*\n!.gitignore\n!README.md\n!index.json\n')
    rm = ARCHIVE_DIR / 'README.md'
    if not rm.exists():
        rm.write_text('# ABpE Archive\nBackup-System für Entwicklung.\n\nVerwende backup_restore.py\n')
    if not INDEX_FILE.exists():
        INDEX_FILE.write_text(json.dumps({'backups': []}, indent=2))

# ============================================================
# INDEX
# ============================================================
def load_index() -> Dict:
    if INDEX_FILE.exists():
        with open(INDEX_FILE) as f:
            return json.load(f)
    return {'backups': []}

def save_index(idx: Dict):
    idx['last_updated'] = datetime.now().isoformat()
    with open(INDEX_FILE, 'w') as f:
        json.dump(idx, f, indent=2)

def add_to_index(original: str, backup_path: Path, timestamp: str, message: str):
    idx = load_index()
    rel = str(backup_path.relative_to(ARCHIVE_DIR))
    src = BASE_DIR / original
    entry = {
        'original_file': original,
        'backup_path':   rel,
        'timestamp':     timestamp,
        'date':          timestamp[:4] + '-' + timestamp[4:6] + '-' + timestamp[6:8],
        'time':          timestamp[9:11] + ':' + timestamp[11:13] + ':' + timestamp[13:],
        'size':          src.stat().st_size if src.exists() else 0,
        'checksum':      md5(src) if src.exists() else '',
        'message':       message,
        'backup_by':     os.environ.get('USER', 'root'),
    }
    idx['backups'].append(entry)
    save_index(idx)

def remove_from_index(backup_rel: str):
    idx = load_index()
    idx['backups'] = [b for b in idx['backups'] if b['backup_path'] != backup_rel]
    save_index(idx)

def get_versions(original: str) -> List[Dict]:
    idx = load_index()
    vers = [b for b in idx['backups'] if b['original_file'] == original]
    return sorted(vers, key=lambda x: x['timestamp'], reverse=True)

# ============================================================
# HILFSFUNKTIONEN
# ============================================================
def md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            h.update(chunk)
    return h.hexdigest()

def make_backup_path(original: str, timestamp: str) -> Path:
    rel      = Path(original)
    date     = timestamp[:4] + '-' + timestamp[4:6] + '-' + timestamp[6:8]
    dest_dir = ARCHIVE_DIR / date / rel.parent
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{rel.stem}_backup_{timestamp}{rel.suffix}"
    return dest_dir / filename

def update_latest():
    dirs = [d for d in ARCHIVE_DIR.iterdir()
            if d.is_dir() and d.name != 'latest' and len(d.name) == 10]
    if not dirs:
        return
    newest = max(dirs, key=lambda d: d.name)
    latest = ARCHIVE_DIR / 'latest'
    if latest.is_symlink() or latest.exists():
        latest.unlink()
    latest.symlink_to(newest.name, target_is_directory=True)
    ok(f"Symlink 'latest' -> {newest.name}")

# ============================================================
# AKTIONEN
# ============================================================
def do_save(original: str, message: str):
    src = BASE_DIR / original
    if not src.exists():
        err(f"Datei nicht gefunden: {src}")
        sys.exit(1)
    ts   = datetime.now().strftime('%Y%m%d_%H%M%S')
    dest = make_backup_path(original, ts)
    shutil.copy2(src, dest)
    ok(f"Backup: {dest.relative_to(BASE_DIR)}")
    info(f"MD5:    {md5(src)}")
    if message:
        info(f"Notiz:  {message}")
    add_to_index(original, dest, ts, message)
    update_latest()


def do_list(original: Optional[str], date: Optional[str]):
    idx     = load_index()
    entries = idx['backups']
    if original:
        entries = [b for b in entries if b['original_file'] == original]
    if date:
        entries = [b for b in entries if b['date'] == date]
    if not entries:
        warn("Keine Backups gefunden.")
        return
    head(f"Backups ({len(entries)})")
    for b in entries:
        print(f"\n  {C.CY}{b['original_file']}{C.X}")
        print(f"    Version : {C.BD}{b['timestamp']}{C.X}")
        print(f"    Datum   : {b['date']} {b['time']}")
        print(f"    Größe   : {b['size']:,} Bytes")
        print(f"    Von     : {b['backup_by']}")
        if b.get('message'):
            print(f"    Notiz   : {C.Y}{b['message']}{C.X}")
        print(f"    Pfad    : {b['backup_path']}")


def do_restore(original: str, version: Optional[str]):
    versions = get_versions(original)
    if not versions:
        err(f"Keine Backups für: {original}")
        sys.exit(1)
    if version:
        sel = [v for v in versions if v['timestamp'] == version]
        if not sel:
            err(f"Version nicht gefunden: {version}")
            info(f"Verfügbar: {[v['timestamp'] for v in versions]}")
            sys.exit(1)
        binfo = sel[0]
    else:
        binfo = versions[0]
        info(f"Neuestes Backup: {binfo['timestamp']}")
    backup_file = ARCHIVE_DIR / binfo['backup_path']
    if not backup_file.exists():
        err(f"Backup-Datei fehlt: {backup_file}")
        sys.exit(1)
    dest = BASE_DIR / original
    if dest.exists():
        temp = dest.with_suffix(dest.suffix + '.before_restore')
        shutil.copy2(dest, temp)
        warn(f"Original gesichert: {temp.name}")
    shutil.copy2(backup_file, dest)
    ok(f"Wiederhergestellt: {original}")
    if md5(dest) == binfo['checksum']:
        ok("Checksum OK")
    else:
        warn("Checksum weicht ab!")


def do_delete(original: str, version: str):
    versions = get_versions(original)
    sel = [v for v in versions if v['timestamp'] == version]
    if not sel:
        err(f"Version nicht gefunden: {version}")
        sys.exit(1)
    binfo       = sel[0]
    backup_file = ARCHIVE_DIR / binfo['backup_path']
    if backup_file.exists():
        backup_file.unlink()
        ok(f"Gelöscht: {backup_file.name}")
        p = backup_file.parent
        while p != ARCHIVE_DIR and not any(p.iterdir()):
            p.rmdir()
            p = p.parent
    remove_from_index(binfo['backup_path'])
    update_latest()
    ok("Index aktualisiert")


def do_cleanup(days: int):
    from datetime import timedelta
    cutoff       = datetime.now() - timedelta(days=days)
    idx          = load_index()
    deleted_dirs = 0
    for d in ARCHIVE_DIR.iterdir():
        if not d.is_dir() or d.name == 'latest' or len(d.name) != 10:
            continue
        try:
            if datetime.strptime(d.name, '%Y-%m-%d') < cutoff:
                shutil.rmtree(d)
                ok(f"Ordner gelöscht: {d.name}")
                deleted_dirs += 1
        except ValueError:
            continue
    before = len(idx['backups'])
    idx['backups'] = [b for b in idx['backups']
                      if datetime.strptime(b['date'], '%Y-%m-%d') >= cutoff]
    save_index(idx)
    update_latest()
    head("Cleanup abgeschlossen")
    ok(f"{deleted_dirs} Ordner, {before - len(idx['backups'])} Index-Einträge entfernt")


def do_man():
    """Zeigt man_backup_restore.md farbig im Terminal an"""
    man_file = ABPE_UI_DIR / 'man_backup_restore.md'
    if not man_file.exists():
        err("man_backup_restore.md nicht gefunden")
        return
    print()
    for line in man_file.read_text().splitlines():
        if line.startswith('# '):
            print(f"{C.CY}{C.BD}{line}{C.X}")
        elif line.startswith('## '):
            print(f"\n{C.B}{C.BD}{line}{C.X}")
        elif line.startswith('### '):
            print(f"\n{C.Y}{line}{C.X}")
        elif line.startswith('```'):
            print(f"{C.G}{line}{C.X}")
        elif line.startswith('|'):
            print(f"{C.CY}{line}{C.X}")
        elif line.startswith('> '):
            print(f"{C.Y}{line}{C.X}")
        else:
            print(line)
    print()


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description='Backup & Restore Helper — ABpE Portal',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  python apps/abpe_ui/backup_restore.py -save apps/abpe_ui/models.py -m "Erweiterung"
  python apps/abpe_ui/backup_restore.py -list
  python apps/abpe_ui/backup_restore.py -list apps/abpe_ui/models.py
  python apps/abpe_ui/backup_restore.py -list --date 2026-05-16
  python apps/abpe_ui/backup_restore.py -restore apps/abpe_ui/models.py
  python apps/abpe_ui/backup_restore.py -restore apps/abpe_ui/models.py --version 20260516_143022
  python apps/abpe_ui/backup_restore.py -delete apps/abpe_ui/models.py --version 20260516_143022
  python apps/abpe_ui/backup_restore.py -cleanup --days 30
  python apps/abpe_ui/backup_restore.py -man
        """
    )

    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument('-save',    metavar='FILE',            help='Datei sichern')
    grp.add_argument('-list',    metavar='FILE', nargs='?', const='', help='Backups auflisten')
    grp.add_argument('-restore', metavar='FILE',            help='Datei wiederherstellen')
    grp.add_argument('-delete',  metavar='FILE',            help='Backup löschen')
    grp.add_argument('-cleanup', action='store_true',       help='Alte Backups löschen')
    grp.add_argument('-man',     action='store_true',       help='Gebrauchsanweisung anzeigen')

    parser.add_argument('-m', '--message', default='', help='Kommentar')
    parser.add_argument('--date',    help='Datum (YYYY-MM-DD)')
    parser.add_argument('--version', help='Version (YYYYMMDD_HHMMSS)')
    parser.add_argument('--days', type=int, default=30, help='Tage für Cleanup')

    args = parser.parse_args()
    ensure_archive()

    if args.save:
        do_save(args.save, args.message)
    elif args.list is not None:
        do_list(args.list or None, args.date)
    elif args.restore:
        do_restore(args.restore, args.version)
    elif args.delete:
        if not args.version:
            err("--version ist für -delete erforderlich")
            sys.exit(1)
        do_delete(args.delete, args.version)
    elif args.cleanup:
        do_cleanup(args.days)
    elif args.man:
        do_man()

if __name__ == '__main__':
    main()
