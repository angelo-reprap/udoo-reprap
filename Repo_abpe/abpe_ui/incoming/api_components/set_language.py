import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

@csrf_exempt
@require_http_methods(["POST"])
def set_language(request):
    try:
        data = json.loads(request.body)
        language = data.get('language', 'de')
    except:
        language = 'de'
    
    if language not in ['de', 'en', 'fr', 'it', 'es', 'pt', 'nl', 'pl', 'ru', 'tr', 'zh', 'ja', 'ko', 'ar']:
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
