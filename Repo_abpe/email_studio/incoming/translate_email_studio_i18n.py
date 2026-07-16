#!/usr/bin/env python3
"""Email Studio UI-Keys gezielt übersetzen (Deepseek).

Der globale i18n_translator.py prüft das gesamte CRM — fehlende Keys in
modules/email_studio/email_studio.json werden oft nicht ergänzt.
Dieses Script übersetzt fehlende oder EN-Platzhalter-Keys aus DE.

ucs5:
  python3 /mnt/public/udoo-reprap/Repo_abpe/email_studio/incoming/translate_email_studio_i18n.py
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

DEFAULT_BACKEND = Path(os.environ.get('ABPE_BACKEND', '/opt/abpe/backend'))
DEFAULT_REPO = Path(os.environ.get('UDOO_REPO', '/mnt/public/udoo-reprap'))
SETTINGS_PATH = Path(os.environ.get('ABPE_SETTINGS', '/opt/abpe/backend/settings.json'))
LANG_MAP_PATH = Path(os.environ.get('ABPE_LANG_MAP', '/opt/abpe/backend/apps/abpe_ui/bin/lang_map.json'))

LANGS = ['ar', 'es', 'fr', 'it', 'ja', 'ko', 'nl', 'pl', 'pt', 'ru', 'tr', 'zh']
MODULE_REL = Path('modules/email_studio/email_studio.json')
INCOMING = 'Repo_abpe/email_studio/incoming'
CHUNK_SIZE = 25


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=4) + '\n', encoding='utf-8')


def _api_key() -> str:
    if not SETTINGS_PATH.is_file():
        raise RuntimeError(f'settings.json nicht gefunden: {SETTINGS_PATH}')
    cfg = _load_json(SETTINGS_PATH)
    key = (cfg.get('ai_models', {}).get('deepseek', {}).get('api_key')
           or cfg.get('api_keys', {}).get('deepseek'))
    if not key:
        raise RuntimeError('Kein Deepseek API-Key in settings.json')
    return key


def _lang_name(code: str) -> str:
    if LANG_MAP_PATH.is_file():
        return _load_json(LANG_MAP_PATH).get(code, {}).get('name', code)
    return code


def _needs_translation(key: str, val: str | None, en_val: str | None) -> bool:
    if not val:
        return True
    if en_val and val == en_val:
        return True
    return False


def _translate_chunk(texts: dict[str, str], lang: str, api_key: str, model: str, timeout: int) -> dict[str, str]:
    tgt = _lang_name(lang)
    payload = json.dumps(texts, ensure_ascii=False, indent=2)
    system = (
        f'You are a professional UI translator for a business web application. '
        f'Translate the JSON values from German to {tgt}. '
        f'Keep keys unchanged. Return ONLY valid JSON with the same keys. '
        f'Preserve placeholders like {{name}}, {{block:signature}}, HTML entities, and punctuation style.'
    )
    resp = requests.post(
        'https://api.deepseek.com/v1/chat/completions',
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        json={
            'model': model,
            'temperature': 0.1,
            'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': payload},
            ],
        },
        timeout=timeout,
        verify=False,
    )
    resp.raise_for_status()
    raw = resp.json()['choices'][0]['message']['content'].strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError('Deepseek-Antwort ist kein JSON-Objekt')
    return {k: str(v) for k, v in data.items()}


def translate_lang(
    lang: str,
    i18n_root: Path,
    de_es: dict,
    en_es: dict,
    *,
    api_key: str,
    model: str,
    timeout: int,
    dry_run: bool,
) -> int:
    path = i18n_root / lang / MODULE_REL
    data = _load_json(path) if path.is_file() else {'es': {}, 'help': {}}
    es = data.setdefault('es', {})

    pending = {
        k: de_es[k]
        for k in de_es
        if _needs_translation(k, es.get(k), en_es.get(k))
    }
    if not pending:
        print(f'  {lang}: ✓ nichts zu übersetzen')
        return 0

    print(f'  {lang}: {len(pending)} Keys → Deepseek')
    if dry_run:
        print(f'    Keys: {", ".join(sorted(pending)[:8])}{"…" if len(pending) > 8 else ""}')
        return len(pending)

    keys = list(pending.keys())
    translated: dict[str, str] = {}
    for i in range(0, len(keys), CHUNK_SIZE):
        chunk = {k: pending[k] for k in keys[i:i + CHUNK_SIZE]}
        try:
            part = _translate_chunk(chunk, lang, api_key, model, timeout)
            translated.update(part)
        except Exception as exc:
            print(f'    WARN Chunk {i // CHUNK_SIZE + 1}: {exc}', file=sys.stderr)
        time.sleep(0.3)

    n = 0
    for k, v in translated.items():
        if k in de_es and v:
            es[k] = v
            n += 1
    _save_json(path, data)
    print(f'  {lang}: ✓ {n} Keys geschrieben')
    return n


def main() -> int:
    parser = argparse.ArgumentParser(description='Email Studio UI-i18n via Deepseek')
    parser.add_argument('--backend', default=str(DEFAULT_BACKEND))
    parser.add_argument('--repo', default=str(DEFAULT_REPO))
    parser.add_argument('--langs', nargs='*', default=LANGS)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    repo = Path(args.repo)
    de_file = repo / INCOMING / 'email_studio.json'
    en_file = repo / INCOMING / 'i18n/en/email_studio.json'
    i18n_root = Path(args.backend) / 'apps/abpe_ui/static/abpe_ui/i18n'

    for p in (de_file, en_file, i18n_root):
        if not p.exists():
            print(f'FEHLER: {p} nicht gefunden', file=sys.stderr)
            return 1

    de_es = _load_json(de_file).get('es', {})
    en_es = _load_json(en_file).get('es', {})

    cfg = _load_json(SETTINGS_PATH) if SETTINGS_PATH.is_file() else {}
    ds = cfg.get('ai_models', {}).get('deepseek', {})
    model = ds.get('model', 'deepseek-chat')
    timeout = int(ds.get('timeout', 90))

    print('Email Studio i18n — Deepseek-Übersetzung')
    print(f'DE-Keys: {len(de_es)}  Ziel: {i18n_root}')
    api_key = None if args.dry_run else _api_key()

    total = 0
    for lang in args.langs:
        if lang in ('de', 'en'):
            continue
        total += translate_lang(
            lang, i18n_root, de_es, en_es,
            api_key=api_key or '',
            model=model,
            timeout=timeout,
            dry_run=args.dry_run,
        )

    print(f'\nFertig — {total} Keys übersetzt')
    if not args.dry_run:
        print('  python manage.py collectstatic --noinput')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
