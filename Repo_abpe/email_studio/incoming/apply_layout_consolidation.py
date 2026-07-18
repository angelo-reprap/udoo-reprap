#!/usr/bin/env python3
"""
Wendet Layout-Deklaration auf Snapshot und/oder Live-DB an.

Offline (Git / Cloud Agent):
  python3 Repo_abpe/email_studio/incoming/apply_layout_consolidation.py --dry-run
  python3 Repo_abpe/email_studio/incoming/apply_layout_consolidation.py --write-snapshot

Auf ucs5 (Django, mit Backup vorher!):
  cd /opt/abpe/backend && source /opt/abpe/venv311/bin/activate
  # 1) Backup
  python manage.py dumpdata abpe_email_studio.EmailModule \\
    abpe_email_studio.EmailTemplate abpe_email_studio.EmailSignature \\
    abpe_email_studio.EmailSenderAccount --indent 2 \\
    -o /tmp/email_studio_backup_before_consolidation.json
  # 2) Apply
  python /mnt/public/udoo-reprap/Repo_abpe/email_studio/incoming/apply_layout_consolidation.py --apply-db

Was geändert wird:
  - footer_standard / footer_auto_reply → Impressum (Deklaration §3)
  - System-Mails (pipeline_*, upload_*): signature_mode=NONE, include_signature=False
  - Alle Vorlagen: text_body 1:1 aus HTML (+ Modul-text_body) ableiten
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / 'Repo_abpe' / 'email_studio' / 'data'
FIXTURES = REPO_ROOT / 'Repo_abpe' / 'email_studio' / 'fixtures' / 'ci_modules'

SYSTEM_TEMPLATE_IDS = frozenset({
    'pipeline_error',
    'pipeline_success',
    'upload_error',
    'upload_received',
})

BLOCK_RE = re.compile(r'\{\{block:([a-zA-Z0-9_\-]+)\}\}')
TAG_RE = re.compile(r'<[^>]+>')
BR_RE = re.compile(r'<br\s*/?>', re.I)
BLOCK_TAGS = re.compile(
    r'</?(p|div|tr|table|h[1-6]|li|ul|ol)[^>]*>',
    re.I,
)


def _load_fixture(name: str) -> str:
    path = FIXTURES / name
    if not path.is_file():
        raise SystemExit(f'Fixture fehlt: {path}')
    return path.read_text(encoding='utf-8').strip()


def _find_snapshot() -> Path:
    latest = DATA_DIR / 'email_studio_snapshot_latest.json'
    if latest.is_file():
        return latest
    snaps = sorted(DATA_DIR.glob('email_studio_snapshot_*.json'))
    if not snaps:
        raise SystemExit(f'Kein Snapshot unter {DATA_DIR}')
    return snaps[-1]


def html_to_text(html: str) -> str:
    """Sichtbaren Text 1:1 aus HTML (ohne Module-Auflösung)."""
    if not html:
        return ''
    text = html.replace('\r\n', '\n').replace('\r', '\n')
    text = BR_RE.sub('\n', text)
    text = BLOCK_TAGS.sub('\n', text)
    text = TAG_RE.sub('', text)
    text = html_lib.unescape(text)
    # Whitespace normalisieren, Absätze erhalten
    lines = [re.sub(r'[ \t]+', ' ', ln).strip() for ln in text.split('\n')]
    out: list[str] = []
    blank = 0
    for ln in lines:
        if not ln:
            blank += 1
            if blank <= 1 and out:
                out.append('')
            continue
        blank = 0
        out.append(ln)
    return '\n'.join(out).strip() + ('\n' if out else '')


def derive_text_body(html_body: str, modules_txt: dict[str, str]) -> str:
    """HTML → TXT, {{block:x}} durch Modul-text_body ersetzen."""
    def repl(m: re.Match) -> str:
        ident = m.group(1)
        if ident == 'signature':
            return '{signature}'
        return modules_txt.get(ident, m.group(0))

    expanded = BLOCK_RE.sub(repl, html_body or '')
    return html_to_text(expanded)


def consolidate_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """Mutiert Kopie der dumpdata-Rows. Returns (new_rows, log)."""
    footer_std_html = _load_fixture('footer_standard.html')
    footer_auto_html = _load_fixture('footer_auto_reply.html')
    footer_std_txt = _load_fixture('footer_standard.txt')
    footer_auto_txt = _load_fixture('footer_auto_reply.txt')

    out = deepcopy(rows)
    log: list[str] = []

    modules_txt: dict[str, str] = {}
    for row in out:
        if row['model'] != 'abpe_email_studio.emailmodule':
            continue
        f = row['fields']
        ident = f['identifier']
        if ident == 'footer_standard':
            f['html_body'] = footer_std_html
            f['text_body'] = footer_std_txt
            log.append(f'Module {ident}: Impressum-HTML/TXT gesetzt')
        elif ident == 'footer_auto_reply':
            f['html_body'] = footer_auto_html
            f['text_body'] = footer_auto_txt
            log.append(f'Module {ident}: Impressum-HTML/TXT + Auto-Reply gesetzt')
        else:
            # Immer 1:1 aus HTML (keine Altlast wie "=== Titel ===")
            tb = html_to_text(f.get('html_body') or '')
            if (f.get('text_body') or '') != tb:
                f['text_body'] = tb
                log.append(f'Module {ident}: text_body 1:1 aus HTML')
        modules_txt[ident] = f.get('text_body') or ''

    for row in out:
        if row['model'] != 'abpe_email_studio.emailtemplate':
            continue
        f = row['fields']
        ident = f['identifier']

        if ident in SYSTEM_TEMPLATE_IDS:
            old_mode = f.get('signature_mode')
            f['signature_mode'] = 'NONE'
            f['include_signature'] = False
            if old_mode != 'NONE':
                log.append(
                    f'Template {ident}: signature_mode {old_mode}→NONE '
                    f'(XOR: Footer behalten, keine Auto-Sig)'
                )

        new_txt = derive_text_body(f.get('html_body') or '', modules_txt)
        old_txt = f.get('text_body') or ''
        if new_txt and new_txt != old_txt:
            f['text_body'] = new_txt
            log.append(f'Template {ident}: text_body gesetzt ({len(new_txt)} chars)')

    return out, log


def write_snapshot(rows: list[dict[str, Any]], path: Path | None = None) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    dated = DATA_DIR / f'email_studio_snapshot_{stamp}.json'
    latest = DATA_DIR / 'email_studio_snapshot_latest.json'
    target = path or dated
    payload = json.dumps(rows, indent=2, ensure_ascii=False) + '\n'
    target.write_text(payload, encoding='utf-8')
    if target != latest:
        latest.write_text(payload, encoding='utf-8')
    return target


def apply_db(rows: list[dict[str, Any]], log: list[str]) -> None:
    """Live-DB aktualisieren (nur auf ucs5 mit Django)."""
    import os
    import django

    backend = os.environ.get('ABPE_BACKEND', '/opt/abpe/backend')
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
    django.setup()

    from apps.abpe_email_studio.models import EmailModule, EmailTemplate

    for row in rows:
        f = row['fields']
        if row['model'] == 'abpe_email_studio.emailmodule':
            obj = EmailModule.objects.filter(identifier=f['identifier']).first()
            if not obj:
                log.append(f'SKIP Module fehlt in DB: {f["identifier"]}')
                continue
            obj.html_body = f['html_body']
            obj.text_body = f.get('text_body') or ''
            obj.save(update_fields=['html_body', 'text_body', 'updated_at'])
        elif row['model'] == 'abpe_email_studio.emailtemplate':
            obj = EmailTemplate.objects.filter(identifier=f['identifier']).first()
            if not obj:
                log.append(f'SKIP Template fehlt in DB: {f["identifier"]}')
                continue
            obj.text_body = f.get('text_body') or ''
            obj.signature_mode = f.get('signature_mode') or obj.signature_mode
            obj.include_signature = bool(f.get('include_signature', obj.include_signature))
            obj.save(update_fields=[
                'text_body', 'signature_mode', 'include_signature', 'updated_at',
            ])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, default=None)
    parser.add_argument('--dry-run', action='store_true', help='Nur Log, nichts schreiben')
    parser.add_argument('--write-snapshot', action='store_true', help='Konsolidierten Snapshot nach data/ schreiben')
    parser.add_argument('--apply-db', action='store_true', help='Live-DB aktualisieren (ucs5)')
    args = parser.parse_args()

    snap_path = args.snapshot or _find_snapshot()
    rows = json.loads(snap_path.read_text(encoding='utf-8'))
    new_rows, log = consolidate_rows(rows)

    print(f'Source: {snap_path}')
    print(f'Changes: {len(log)}')
    for line in log:
        print(f'  • {line}')

    if args.dry_run or (not args.write_snapshot and not args.apply_db):
        print('\nDry-run / keine Schreib-Flags — nichts gespeichert.')
        print('  --write-snapshot  → Git data/')
        print('  --apply-db        → Live-DB (nach Backup)')
        return 0

    if args.write_snapshot:
        out = write_snapshot(new_rows)
        print(f'\nOK Snapshot: {out}')
        print(f'OK Latest:   {DATA_DIR / "email_studio_snapshot_latest.json"}')

    if args.apply_db:
        apply_db(new_rows, log)
        print('\nOK Live-DB aktualisiert.')
        print('Danach: RUN-phase1-iststand.sh --commit --push')

    return 0


if __name__ == '__main__':
    sys.exit(main())
