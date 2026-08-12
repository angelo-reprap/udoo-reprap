from pathlib import Path
import json
# CRM hat keinen module_scanner — Navigation ist statisch

def _jsonify_titles(item):
    """Konvertiert titles dict zu JSON-String für Templates"""
    if 'titles' in item and isinstance(item['titles'], dict):
        item = dict(item)
        item['titles_json'] = json.dumps(item['titles'], ensure_ascii=False)
    else:
        item = dict(item)
        item['titles_json'] = '{}'
    return item

def current_language(request):
    """Stellt die aktuelle Sprache für Templates bereit"""
    language = request.session.get('language')
    if not language:
        language = request.COOKIES.get('language', 'de')
    return {'current_lang': language}

def available_languages(request):
    """Stellt alle verfügbaren Sprachen für Templates bereit"""
    i18n_dir = Path(__file__).parent.parent / 'static' / 'abpe_crm' / 'i18n'
    languages = []
    if i18n_dir.exists():
        for lang_dir in i18n_dir.iterdir():
            if lang_dir.is_dir() and not lang_dir.name.startswith('.'):
                meta_file = lang_dir / 'meta.json'
                if meta_file.exists():
                    with open(meta_file) as f:
                        meta = json.load(f)
                    languages.append({
                        'code':   lang_dir.name,
                        'name':   meta.get('name', lang_dir.name),
                        'native': meta.get('native', lang_dir.name),
                        'flag':   meta.get('flag', '🏳️'),
                    })
    return {'available_languages': languages}

def navigation(request):
    """
    Stellt Navigation für Sidebar bereit — gefiltert nach Benutzer-Rollen.
    """
    modules_json = Path(__file__).parent / 'modules.json'
    dashboard = {}
    system_navigation = []

    if modules_json.exists():
        with open(modules_json) as f:
            base = json.load(f)
        dashboard = base.get('dashboard', {})
        system_navigation = base.get('system', [])
        if dashboard and 'titles' not in dashboard:
            dashboard['titles'] = {}
        for item in system_navigation:
            if 'titles' not in item:
                item['titles'] = {}

    # User an Scanner übergeben → Rollenfilter greift
    user = getattr(request, 'user', None)
    dynamic_modules = scanner.get_navigation(user=user)

    # titles zu JSON-Strings konvertieren
    if dashboard:
        dashboard = _jsonify_titles(dashboard)
    dynamic_modules    = [_jsonify_titles(m) for m in dynamic_modules]
    system_navigation  = [_jsonify_titles(i) for i in system_navigation]

    for m in dynamic_modules:
        if m.get('subpages'):
            m['subpages'] = [_jsonify_titles(sp) for sp in m['subpages']]

    # User-spezifische Reihenfolge
    if user and user.is_authenticated:
        try:
            from apps.abpe_ui.models import UserSettings
            us = UserSettings.objects.filter(user=user).first()
            if us and us.nav_order:
                order_map = {mid: idx for idx, mid in enumerate(us.nav_order)}
                dynamic_modules.sort(key=lambda m: order_map.get(m['id'], 999))
        except Exception:
            pass

    main_navigation = []
    if dashboard:
        main_navigation.append(dashboard)
    main_navigation.extend(dynamic_modules)

    return {
        'main_navigation':   main_navigation,
        'system_navigation': system_navigation,
        'user_is_admin':     bool(user and user.is_authenticated and (user.is_staff or user.is_superuser)),
        'user_is_auth':      bool(user and user.is_authenticated),
    }
