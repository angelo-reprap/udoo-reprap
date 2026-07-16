#!/usr/bin/env python3
"""i18n Qualitäts-Audit — Stichproben: noch DE/EN-Kopien in Fremdsprachen?

Vergleicht alle JSON-Dateien unter i18n/de/ mit den Zielsprachen.
Verdächtig = Wert identisch mit DE (obwohl übersetzbar) oder EN-Platzhalter.

ucs5:
  python3 /mnt/public/udoo-reprap/Repo_abpe/email_studio/incoming/audit_i18n_quality.py
  python3 .../audit_i18n_quality.py --sample 5
  python3 .../audit_i18n_quality.py --file modules/email_studio/email_studio.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

DEFAULT_BACKEND = Path(os.environ.get('ABPE_BACKEND', '/opt/abpe/backend'))
I18N_REL = Path('apps/abpe_ui/static/abpe_ui/i18n')
LANGS = ['ar', 'en', 'es', 'fr', 'it', 'ja', 'ko', 'nl', 'pl', 'pt', 'ru', 'tr', 'zh']

INVARIANT_ACRONYMS = frozenset({
    'HTML', 'TXT', 'TLS', 'SMTP', 'CC', 'BCC', 'API', 'URL', 'PDF', 'OK', 'ID',
    'CRM', 'UI', 'CSS', 'JS',
})

# Bekannte internationale Begriffe (DE == EN == Fremdsprache OK)
INTERNATIONAL = frozenset({
    'Auto', 'Visual', 'Host', 'Studio', 'Editor', 'Log', 'Config', 'Status',
    'Template', 'Online', 'Offline', 'Default', 'Admin', 'Portal',
})


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding='utf-8'))


def _is_invariant(val: str) -> bool:
    v = val.strip()
    if not v:
        return True
    if v.upper() in INVARIANT_ACRONYMS:
        return True
    if v in INTERNATIONAL:
        return True
    if '{{' in v and '}}' in v:
        return True
    if re.match(r'^[\w.@+-]+$', v) and '@' in v:
        return True
    if re.match(r'^v?\d+(\.\d+)*$', v):
        return True
    if len(v) <= 2 and v.isascii():
        return True
    return False


def _walk_strings(obj: object, prefix: str = '') -> dict[str, str]:
    out: dict[str, str] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f'{prefix}.{k}' if prefix else k
            out.update(_walk_strings(v, p))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(_walk_strings(v, f'{prefix}[{i}]'))
    elif isinstance(obj, str):
        out[prefix] = obj
    return out


def _is_suspect(
    tgt: str, de: str, en: str | None, lang: str,
) -> str | None:
    """Grund zurückgeben oder None wenn OK."""
    if not tgt.strip():
        return 'leer'
    if _is_invariant(de) or _is_invariant(tgt):
        return None
    if de and en and de == en:
        return None
    if de and tgt == de and lang != 'de':
        return 'noch DE'
    if lang not in ('de', 'en') and en and tgt == en and de and de != en:
        return 'EN-Platzhalter'
    return None


def _de_files(de_root: Path) -> list[Path]:
    return sorted(de_root.rglob('*.json'))


def _audit_file(
    rel: Path,
    de_root: Path,
    i18n_root: Path,
    langs: list[str],
) -> dict[str, list[tuple[str, str, str]]]:
    """lang -> [(path, grund, wert)]"""
    de_path = de_root / rel
    if not de_path.is_file():
        return {}
    de_flat = _walk_strings(_load(de_path))
    en_flat: dict[str, str] = {}
    en_path = i18n_root / 'en' / rel
    if en_path.is_file():
        en_flat = _walk_strings(_load(en_path))

    report: dict[str, list[tuple[str, str, str]]] = {}
    for lang in langs:
        if lang == 'de':
            continue
        tgt_path = i18n_root / lang / rel
        if not tgt_path.is_file():
            report.setdefault(lang, []).append(('__file__', 'FEHLT', str(rel)))
            continue
        tgt_flat = _walk_strings(_load(tgt_path))
        bad: list[tuple[str, str, str]] = []
        for key, de_val in de_flat.items():
            tgt_val = tgt_flat.get(key, '')
            reason = _is_suspect(tgt_val, de_val, en_flat.get(key), lang)
            if reason:
                bad.append((key, reason, tgt_val[:60]))
        if bad:
            report[lang] = bad
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description='i18n Qualitäts-Audit (DE-Kopien / EN-Platzhalter)')
    parser.add_argument('--backend', default=str(DEFAULT_BACKEND))
    parser.add_argument('--langs', nargs='*', default=LANGS)
    parser.add_argument('--file', help='Nur diese Relativdatei (z.B. modules/email_studio/email_studio.json)')
    parser.add_argument('--sample', type=int, default=3, help='Beispiele pro Datei/Sprache')
    parser.add_argument('--max-files', type=int, default=0, help='Max Dateien (0=alle)')
    args = parser.parse_args()

    i18n_root = Path(args.backend) / I18N_REL
    de_root = i18n_root / 'de'
    if not de_root.is_dir():
        print(f'FEHLER: {de_root} nicht gefunden', file=sys.stderr)
        return 1

    files = _de_files(de_root)
    if args.file:
        files = [de_root / args.file]
    if args.max_files:
        files = files[: args.max_files]

    total_suspect = 0
    total_missing = 0
    clean_files = 0

    print('══ i18n Qualitäts-Audit ══')
    print(f'DE-Quelle: {de_root}')
    print(f'Dateien:   {len(files)}')
    print('Verdächtig: noch DE-Text · EN-Platzhalter · leer · FEHLT')
    print()

    for de_path in files:
        rel = de_path.relative_to(de_root)
        per_lang = _audit_file(rel, de_root, i18n_root, args.langs)
        if not per_lang:
            clean_files += 1
            continue

        file_bad = sum(len(v) for v in per_lang.values())
        total_suspect += file_bad
        print(f'── {rel} ──')
        for lang, items in sorted(per_lang.items()):
            missing = [x for x in items if x[0] == '__file__']
            if missing:
                total_missing += 1
                print(f'  {lang}: DATEI FEHLT')
                continue
            n = len(items)
            total_suspect += 0
            print(f'  {lang}: {n} verdächtig')
            for key, reason, val in items[: args.sample]:
                print(f'    • [{reason}] {key} = {val!r}')
            if n > args.sample:
                print(f'    … (+{n - args.sample} weitere)')
        print()

    print('══ Zusammenfassung ══')
    print(f'  Dateien geprüft:     {len(files)}')
    print(f'  Dateien ohne Befund: {clean_files}')
    print(f'  Verdächtige Labels:  {total_suspect}')
    print(f'  Fehlende Dateien:    {total_missing}')
    if total_suspect == 0 and total_missing == 0:
        print('  ✅ Keine verdächtigen Stichproben')
        return 0
    print('  ⚠ Stichproben prüfen — Lehnwörter/technische Begriffe können False-Positives sein')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
