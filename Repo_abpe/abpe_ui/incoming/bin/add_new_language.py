#!/usr/bin/env python3
"""
add_new_language.py - Sprachpaket-Manager fuer das ABpE Portal
Aufruf: python3 add_new_language.py --add es | --hide it | --show it | --list | --available
"""
import argparse, json, subprocess, sys
from datetime import date
from pathlib import Path

BASE_DIR   = Path('/opt/abpe/backend')
I18N_DIR   = BASE_DIR / 'apps/abpe_ui/static/abpe_ui/i18n'
TRANSLATOR = BASE_DIR / 'apps/abpe_ui/bin/i18n_translator.py'
RTL_LANGS  = {'ar', 'he', 'fa', 'ur'}

LANG_MAP = {
    'af': {'name': 'Afrikaans',   'native': 'Afrikaans',    'flag': '🇿🇦'},
    'ar': {'name': 'Arabic',      'native': 'العربية',       'flag': '🇸🇦'},
    'bg': {'name': 'Bulgarian',   'native': 'Български',     'flag': '🇧🇬'},
    'cs': {'name': 'Czech',       'native': 'Čeština',       'flag': '🇨🇿'},
    'da': {'name': 'Danish',      'native': 'Dansk',         'flag': '🇩🇰'},
    'el': {'name': 'Greek',       'native': 'Ελληνικά',      'flag': '🇬🇷'},
    'en': {'name': 'English',     'native': 'English',       'flag': '🇬🇧'},
    'es': {'name': 'Spanish',     'native': 'Español',       'flag': '🇪🇸'},
    'et': {'name': 'Estonian',    'native': 'Eesti',         'flag': '🇪🇪'},
    'fi': {'name': 'Finnish',     'native': 'Suomi',         'flag': '🇫🇮'},
    'fr': {'name': 'French',      'native': 'Français',      'flag': '🇫🇷'},
    'hr': {'name': 'Croatian',    'native': 'Hrvatski',      'flag': '🇭🇷'},
    'hu': {'name': 'Hungarian',   'native': 'Magyar',        'flag': '🇭🇺'},
    'it': {'name': 'Italian',     'native': 'Italiano',      'flag': '🇮🇹'},
    'ja': {'name': 'Japanese',    'native': '日本語',         'flag': '🇯🇵'},
    'ko': {'name': 'Korean',      'native': '한국어',          'flag': '🇰🇷'},
    'lt': {'name': 'Lithuanian',  'native': 'Lietuvių',      'flag': '🇱🇹'},
    'lv': {'name': 'Latvian',     'native': 'Latviešu',      'flag': '🇱🇻'},
    'nl': {'name': 'Dutch',       'native': 'Nederlands',    'flag': '🇳🇱'},
    'no': {'name': 'Norwegian',   'native': 'Norsk',         'flag': '🇳🇴'},
    'pl': {'name': 'Polish',      'native': 'Polski',        'flag': '🇵🇱'},
    'pt': {'name': 'Portuguese',  'native': 'Português',     'flag': '🇵🇹'},
    'ro': {'name': 'Romanian',    'native': 'Română',        'flag': '🇷🇴'},
    'ru': {'name': 'Russian',     'native': 'Русский',       'flag': '🇷🇺'},
    'sk': {'name': 'Slovak',      'native': 'Slovenčina',    'flag': '🇸🇰'},
    'sl': {'name': 'Slovenian',   'native': 'Slovenščina',   'flag': '🇸🇮'},
    'sq': {'name': 'Albanian',    'native': 'Shqip',         'flag': '🇦🇱'},
    'sr': {'name': 'Serbian',     'native': 'Српски',        'flag': '🇷🇸'},
    'sv': {'name': 'Swedish',     'native': 'Svenska',       'flag': '🇸🇪'},
    'tr': {'name': 'Turkish',     'native': 'Türkçe',        'flag': '🇹🇷'},
    'uk': {'name': 'Ukrainian',   'native': 'Українська',    'flag': '🇺🇦'},
    'vi': {'name': 'Vietnamese',  'native': 'Tiếng Việt',    'flag': '🇻🇳'},
    'zh': {'name': 'Chinese',     'native': '中文',           'flag': '🇨🇳'},
}


LANG_MAP_JSON = Path('/opt/abpe/backend/apps/abpe_ui/bin/lang_map.json')

def _load_lang_map():
    """Lädt lang_map.json und merged mit hardcoded LANG_MAP (JSON hat Vorrang)."""
    if LANG_MAP_JSON.exists():
        try:
            ext = json.loads(LANG_MAP_JSON.read_text(encoding='utf-8'))
            return {**LANG_MAP, **ext}
        except Exception:
            pass
    return LANG_MAP

def _today(): return date.today().isoformat()

class LanguageManager:

    def list_languages(self):
        result = []
        if not I18N_DIR.exists(): return result
        for lang_dir in sorted(I18N_DIR.iterdir()):
            if not lang_dir.is_dir() or lang_dir.name.startswith('.'): continue
            meta_file = lang_dir / 'meta.json'
            meta = {}
            if meta_file.exists():
                try: meta = json.loads(meta_file.read_text(encoding='utf-8'))
                except: pass
            code = lang_dir.name
            info = _load_lang_map().get(code, {})
            result.append({
                'code':       code,
                'name':       meta.get('name',   info.get('name',   code.upper())),
                'native':     meta.get('native', info.get('native', code.upper())),
                'flag':       meta.get('flag',   info.get('flag',   '🏳️')),
                'enabled':    meta.get('enabled', True),
                'file_count': len(list(lang_dir.rglob('*.json'))),
                'has_meta':   meta_file.exists(),
                'is_ref':     code == 'de',
            })
        return result

    def get_available_to_add(self):
        existing = {d.name for d in I18N_DIR.iterdir() if d.is_dir()} if I18N_DIR.exists() else set()
        return [{'code': code, **info} for code, info in sorted(_load_lang_map().items())
                if code not in existing and code != 'de']

    def add_language(self, lang_code):
        lang_code = lang_code.lower().strip()
        if lang_code == 'de':
            return {'success': False, 'error': 'DE ist Referenzsprache.'}
        info = _load_lang_map().get(lang_code, {'name': lang_code.upper(), 'native': lang_code.upper(), 'flag': '🏳️'})
        lang_dir = I18N_DIR / lang_code
        lang_dir.mkdir(parents=True, exist_ok=True)
        meta = {
            'code': lang_code, 'name': info['name'], 'native': info['native'],
            'flag': info['flag'], 'direction': 'rtl' if lang_code in RTL_LANGS else 'ltr',
            'version': '1.0', 'author': 'ABpE i18n Translator',
            'last_updated': _today(), 'enabled': True, 'fallback': 'de', 'completeness': 0,
        }
        meta_path = lang_dir / 'meta.json'
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=4), encoding='utf-8')
        log_lines = [f"Installiere: {lang_code} ({info['name']})"]
        try:
            proc = subprocess.run(
                [sys.executable, str(TRANSLATOR), '--lang', lang_code],
                capture_output=True, text=True, timeout=600, cwd=str(BASE_DIR))
            log_lines.append(proc.stdout.strip())
            if proc.returncode != 0:
                return {'success': False, 'error': proc.stderr, 'log': '\n'.join(log_lines)}
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Timeout (600s)', 'log': '\n'.join(log_lines)}
        except Exception as e:
            return {'success': False, 'error': str(e), 'log': '\n'.join(log_lines)}
        try:
            cs = subprocess.run([sys.executable, 'manage.py', 'collectstatic', '--noinput'],
                capture_output=True, text=True, timeout=120, cwd=str(BASE_DIR))
            last = cs.stdout.strip().splitlines()[-1] if cs.stdout.strip() else 'OK'
            log_lines.append(f"collectstatic: {last}")
        except Exception as e:
            log_lines.append(f"collectstatic Warnung: {e}")
        # module.json Dateien mit neuer Sprache ergänzen
        modules_dir = BASE_DIR / 'apps/abpe_ui/templates/abpe_ui/modules'
        import json as _json
        for mod_json in modules_dir.rglob('module.json'):
            try:
                mod = _json.loads(mod_json.read_text(encoding='utf-8'))
                if 'titles' in mod and lang_code not in mod['titles']:
                    mod['titles'][lang_code] = mod['titles'].get('en', mod.get('title', lang_code))
                for sp in mod.get('subpages', []):
                    if 'titles' in sp and lang_code not in sp['titles']:
                        sp['titles'][lang_code] = sp['titles'].get('en', sp.get('title', lang_code))
                mod_json.write_text(_json.dumps(mod, ensure_ascii=False, indent=4), encoding='utf-8')
                log_lines.append(f"  module.json aktualisiert: {mod_json.parent.name}")
            except Exception as e:
                log_lines.append(f"  module.json Warnung: {e}")

        file_count = len(list(lang_dir.rglob('*.json')))
        meta['completeness'] = 100
        meta['last_updated'] = _today()
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=4), encoding='utf-8')
        log_lines.append(f"✅ {lang_code} installiert — {file_count} Dateien")
        return {'success': True, 'code': lang_code, 'name': info['name'],
                'native': info['native'], 'flag': info['flag'],
                'file_count': file_count, 'log': '\n'.join(log_lines)}

    def hide_language(self, lang_code): return self._set_enabled(lang_code, False)
    def show_language(self, lang_code): return self._set_enabled(lang_code, True)

    def _set_enabled(self, lang_code, enabled):
        lang_code = lang_code.lower().strip()
        if lang_code == 'de':
            return {'success': False, 'error': 'DE kann nicht ausgeblendet werden.'}
        meta_path = I18N_DIR / lang_code / 'meta.json'
        if not meta_path.exists():
            return {'success': False, 'error': f'{lang_code} nicht gefunden.'}
        try:
            meta = json.loads(meta_path.read_text(encoding='utf-8'))
            meta['enabled'] = enabled
            meta['last_updated'] = _today()
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=4), encoding='utf-8')
            action = 'eingeblendet' if enabled else 'ausgeblendet'
            return {'success': True, 'code': lang_code, 'enabled': enabled,
                    'message': f'{lang_code} wurde {action}.'}
        except Exception as e:
            return {'success': False, 'error': str(e)}


def main():
    parser = argparse.ArgumentParser(description='ABpE Sprachpaket-Manager')
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument('--list',      action='store_true')
    grp.add_argument('--available', action='store_true')
    grp.add_argument('--add',  metavar='CODE')
    grp.add_argument('--hide', metavar='CODE')
    grp.add_argument('--show', metavar='CODE')
    args = parser.parse_args()
    mgr  = LanguageManager()

    if args.list:
        for l in mgr.list_languages():
            ref    = ' (Ref)' if l['is_ref'] else ''
            status = '✓' if l['enabled'] else '✗'
            print(f"  {l['flag']} {l['code']:<4} {l['name']:<15} {status} {l['file_count']} Dateien{ref}")
    elif args.available:
        for l in mgr.get_available_to_add():
            print(f"  {l['flag']} {l['code']:<5} {l['name']:<15} ({l['native']})")
    elif args.add:
        r = mgr.add_language(args.add)
        print(f"{'✅' if r['success'] else '✗'} {r.get('name','?')} ({args.add})")
        if r.get('log'): print(r['log'])
    elif args.hide:
        r = mgr.hide_language(args.hide)
        print(r.get('message') or r.get('error'))
    elif args.show:
        r = mgr.show_language(args.show)
        print(r.get('message') or r.get('error'))

if __name__ == '__main__':
    main()
