from pathlib import Path
import json
from .core.module_scanner import scanner

def current_language(request):
    """Stellt die aktuelle Sprache für Templates bereit"""
    language = request.session.get('language')
    if not language:
        language = request.COOKIES.get('language', 'de')
    return {'current_lang': language}

def available_languages(request):
    """Stellt alle verfügbaren Sprachen für Templates bereit"""
    i18n_dir = Path(__file__).parent / 'static' / 'abpe_ui' / 'i18n'
    languages = []
    if i18n_dir.exists():
        for lang_dir in i18n_dir.iterdir():
            if lang_dir.is_dir() and not lang_dir.name.startswith('.'):
                meta_file = lang_dir / 'meta.json'
                if meta_file.exists():
                    with open(meta_file) as f:
                        meta = json.load(f)
                    languages.append({
                        'code': lang_dir.name,
                        'name': meta.get('name', lang_dir.name),
                        'native': meta.get('native', lang_dir.name),
                        'flag': meta.get('flag', '🏳️'),
                    })
    return {'available_languages': languages}

def navigation(request):
    """Stellt Navigation für Sidebar bereit:
       1. Dashboard + Core-Module aus modules.json
       2. Dynamische Module aus module.json Dateien (Scanner)
       3. System-Navigation aus modules.json (Admin, API Docs)
    """
    # modules.json laden
    modules_json = Path(__file__).parent / 'modules.json'
    dashboard = {}
    system_navigation = []

    if modules_json.exists():
        with open(modules_json) as f:
            base = json.load(f)
        dashboard = base.get('dashboard', {})
        system_navigation = base.get('system', [])

    # Dynamische Module aus Scanner (module.json Dateien)
    dynamic_modules = scanner.get_navigation()

    # Hauptnavigation: Dashboard zuerst, dann dynamische Module
    main_navigation = []
    if dashboard:
        main_navigation.append(dashboard)
    main_navigation.extend(dynamic_modules)

    return {
        'main_navigation': main_navigation,
        'system_navigation': system_navigation,
    }
