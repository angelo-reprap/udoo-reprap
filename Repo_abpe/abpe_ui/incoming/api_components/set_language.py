import json
from pathlib import Path

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


def _enabled_language_codes():
    """Erlaubte Sprachen = i18n-Ordner mit meta.json enabled (wie available_languages)."""
    i18n_dir = Path(__file__).resolve().parent.parent.parent / 'static' / 'abpe_ui' / 'i18n'
    codes = []
    if i18n_dir.exists():
        for lang_dir in sorted(i18n_dir.iterdir()):
            if not lang_dir.is_dir() or lang_dir.name.startswith('.'):
                continue
            meta_file = lang_dir / 'meta.json'
            if not meta_file.exists():
                continue
            try:
                meta = json.loads(meta_file.read_text())
            except Exception:
                continue
            if meta.get('enabled', True):
                codes.append(lang_dir.name)
    return codes or ['de']


@csrf_exempt
@require_http_methods(["POST"])
def set_language(request):
    try:
        data = json.loads(request.body)
        language = data.get('language', 'de')
    except Exception:
        language = 'de'

    if language not in _enabled_language_codes():
        return JsonResponse({'error': 'Invalid language'}, status=400)
    
    request.session['language'] = language
    response = JsonResponse({'status': 'ok', 'language': language})
    response.set_cookie('language', language, max_age=31536000)
    
    if request.user.is_authenticated:
        try:
            from apps.abpe_ui.models import UserSettings
            settings, _ = UserSettings.objects.get_or_create(user=request.user)
            settings.language = language
            settings.save()
        except:
            pass
    
    return response

def get_language(request):
    language = request.session.get('language', request.COOKIES.get('language', 'de'))
    return JsonResponse({'language': language})
