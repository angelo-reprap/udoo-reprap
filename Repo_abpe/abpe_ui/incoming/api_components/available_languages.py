from django.http import JsonResponse
from pathlib import Path
import json

def get_available_languages(request):
    i18n_dir = Path(__file__).parent.parent.parent / 'static' / 'abpe_ui' / 'i18n'
    languages = []
    
    if i18n_dir.exists():
        for lang_dir in i18n_dir.iterdir():
            if lang_dir.is_dir() and not lang_dir.name.startswith('.'):
                meta_file = lang_dir / 'meta.json'
                if meta_file.exists():
                    with open(meta_file) as f:
                        meta = json.load(f)
                    if meta.get('enabled', True):
                        languages.append({
                            'code': lang_dir.name,
                            'name': meta.get('name', lang_dir.name),
                            'native': meta.get('native', lang_dir.name),
                            'flag': meta.get('flag', '🏳️'),
                        })
    
    languages.sort(key=lambda x: x['code'])
    current = request.session.get('language', request.COOKIES.get('language', 'de'))
    
    return JsonResponse({'languages': languages, 'current': current})
