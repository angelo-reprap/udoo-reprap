#!/usr/bin/env python3
"""Email Studio i18n — DE kanonisch patchen, fehlende Keys in alle Sprachen mergen.

Workflow (ucs5):
  1. git fetch && git show … > /tmp/…  ODER Repo unter /mnt/public/udoo-reprap
  2. python3 Repo_abpe/email_studio/incoming/patch_email_studio_i18n.py
  3. python apps/abpe_crm/bin/i18n_translator.py
  4. python apps/abpe_crm/bin/i18n_validate.py   # optional
  5. python manage.py collectstatic --noinput
  6. supervisorctl restart abpe-django
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from copy import deepcopy
from pathlib import Path

DEFAULT_BACKEND = Path(os.environ.get('ABPE_BACKEND', '/opt/abpe/backend'))
DEFAULT_REPO = Path(os.environ.get('UDOO_REPO', '/mnt/public/udoo-reprap'))
INCOMING = 'Repo_abpe/email_studio/incoming'

LANGS = [
    'ar', 'de', 'en', 'es', 'fr', 'it', 'ja', 'ko', 'nl', 'pl', 'pt', 'ru', 'tr', 'zh',
]

# Keys mit EN-Platzhalter entfernen → i18n_translator übersetzt fehlende Keys neu
INVALIDATE_FOR_TRANSLATOR = {
    'btn_create_module', 'btn_create_signature', 'btn_save_module', 'btn_save_signature',
    'milestone_save_short', 'btn_new_signature_short',
    'duplicate_suffix', 'version_prefix', 'history_template_only',
}

MODULE_DIR = Path('modules/email_studio')
FILE_NAME = 'email_studio.json'


def _target_path(i18n_root: Path, lang: str) -> Path:
    return i18n_root / lang / MODULE_DIR / FILE_NAME


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=4) + '\n', encoding='utf-8')


def _invalidate_en_placeholders(
    es: dict, lang: str, en_es: dict, de_es: dict, *, force: bool = False,
) -> int:
    """EN/DE-Platzhalter löschen → i18n_translator übersetzt fehlende Keys neu."""
    if lang in ('de', 'en'):
        return 0
    n = 0
    for key in INVALIDATE_FOR_TRANSLATOR:
        if key not in es:
            continue
        val = es[key]
        en_val = en_es.get(key)
        de_val = de_es.get(key)
        if force or val in (en_val, de_val):
            del es[key]
            n += 1
    return n


def _merge_section(target: dict, source: dict, lang: str, ref_en: dict) -> int:
    """Fehlende Keys ergänzen. DE=kanonisch, EN=Referenz, andere=EN dann DE."""
    n = 0
    for key, de_val in source.items():
        if key in target and target[key] not in (None, ''):
            continue
        if lang not in ('de', 'en') and key in INVALIDATE_FOR_TRANSLATOR:
            continue
        if lang == 'de':
            val = de_val
        elif lang == 'en':
            val = ref_en.get(key, de_val)
        else:
            val = ref_en.get(key, de_val)
        target[key] = val
        n += 1
    return n


def patch_all(
    i18n_root: Path, canonical_de: dict, ref_en: dict, langs: list[str], *, force: bool = False,
) -> int:
    de_es = canonical_de.get('es', {})
    en_es = ref_en.get('es', {})
    de_help = canonical_de.get('help', {})
    en_help = ref_en.get('help', {})
    top_keys = {k: v for k, v in canonical_de.items() if k not in ('es', 'help')}

    total = 0
    for lang in langs:
        path = _target_path(i18n_root, lang)
        if lang == 'de':
            _save_json(path, deepcopy(canonical_de))
            print(f'  {lang}: vollständig ersetzt ({len(de_es)} es-Keys)')
            total += len(de_es)
            continue

        if path.is_file():
            data = _load_json(path)
        else:
            data = {'es': {}, 'help': {}}

        es = data.setdefault('es', {})
        help_sec = data.setdefault('help', {})

        inv = _invalidate_en_placeholders(es, lang, en_es, de_es, force=force)
        n_es = _merge_section(es, de_es, lang, en_es)
        n_help = _merge_section(help_sec, de_help, lang, en_help)
        if inv:
            print(f'  {lang}: {inv} Keys für Translator invalidiert')
        missing = [k for k in INVALIDATE_FOR_TRANSLATOR if k not in es]
        if missing and lang not in ('de', 'en'):
            print(f'  {lang}: fehlend für Translator: {", ".join(missing)}')

        for k, v in top_keys.items():
            if k not in data:
                data[k] = v
                n_es += 1

        _save_json(path, data)
        print(f'  {lang}: +{n_es} es, +{n_help} help Keys')
        total += n_es

    return total


def main() -> int:
    parser = argparse.ArgumentParser(description='Email Studio i18n in alle Sprachen patchen')
    parser.add_argument('--backend', default=str(DEFAULT_BACKEND))
    parser.add_argument('--repo', default=str(DEFAULT_REPO))
    parser.add_argument('--langs', nargs='*', default=LANGS)
    parser.add_argument(
        '--force-invalidate', action='store_true',
        help='INVALIDATE_FOR_TRANSLATOR-Keys in allen Nicht-DE/EN-Sprachen löschen',
    )
    args = parser.parse_args()

    repo = Path(args.repo)
    incoming = repo / INCOMING
    de_file = incoming / 'email_studio.json'
    en_file = incoming / 'i18n/en/email_studio.json'

    if not de_file.is_file():
        print(f'FEHLER: {de_file} nicht gefunden', file=sys.stderr)
        return 1
    if not en_file.is_file():
        print(f'FEHLER: {en_file} nicht gefunden', file=sys.stderr)
        return 1

    canonical_de = _load_json(de_file)
    ref_en = _load_json(en_file)
    i18n_root = Path(args.backend) / 'apps/abpe_ui/static/abpe_ui/i18n'

    if not i18n_root.is_dir():
        print(f'FEHLER: {i18n_root} nicht gefunden', file=sys.stderr)
        return 1

    print(f'Kanonisch DE: {de_file}')
    print(f'Referenz EN:  {en_file}')
    print(f'Ziel:         {i18n_root}')
    print('Patche Sprachen:')
    patch_all(i18n_root, canonical_de, ref_en, args.langs, force=args.force_invalidate)

    print('\n--- Nächste Schritte auf ucs5 ---')
    print('  cd /opt/abpe/backend')
    print('  python apps/abpe_crm/bin/i18n_translator.py')
    print('  python manage.py collectstatic --noinput')
    print('  supervisorctl restart abpe-django')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
