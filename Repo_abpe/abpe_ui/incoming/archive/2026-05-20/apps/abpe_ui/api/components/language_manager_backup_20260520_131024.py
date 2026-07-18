"""
api/components/language_manager.py
"""
import json
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser


def _get_manager():
    from apps.abpe_ui.bin.add_new_language import LanguageManager
    return LanguageManager()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_languages(request):
    mgr = _get_manager()
    return JsonResponse({'languages': mgr.list_languages()})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def available_languages(request):
    mgr = _get_manager()
    return JsonResponse({'languages': mgr.get_available_to_add()})


@api_view(['POST'])
@permission_classes([IsAdminUser])
def add_language(request):
    try:
        body = json.loads(request.body)
        code = body.get('code', '').strip().lower()
    except Exception:
        return JsonResponse({'success': False, 'error': 'Ungültiger Request-Body'}, status=400)
    if not code:
        return JsonResponse({'success': False, 'error': 'Sprachcode fehlt'}, status=400)
    result = _get_manager().add_language(code)
    return JsonResponse(result, status=200 if result['success'] else 500)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def hide_language(request):
    try:
        code = json.loads(request.body).get('code', '').strip().lower()
    except Exception:
        return JsonResponse({'success': False, 'error': 'Ungültiger Request-Body'}, status=400)
    result = _get_manager().hide_language(code)
    return JsonResponse(result, status=200 if result['success'] else 400)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def show_language(request):
    try:
        code = json.loads(request.body).get('code', '').strip().lower()
    except Exception:
        return JsonResponse({'success': False, 'error': 'Ungültiger Request-Body'}, status=400)
    result = _get_manager().show_language(code)
    return JsonResponse(result, status=200 if result['success'] else 400)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def resolve_language(request):
    """
    POST /api/languages/resolve/
    Body: { "description": "Ägyptisches Arabisch" }
    Deepseek ermittelt ISO-Code, Name, Native, Flag
    und trägt die Sprache in lang_map.json ein.
    """
    try:
        body        = json.loads(request.body)
        description = body.get('description', '').strip()
    except Exception:
        return JsonResponse({'success': False, 'error': 'Ungültiger Body'}, status=400)

    if not description:
        return JsonResponse({'success': False, 'error': 'Beschreibung fehlt'}, status=400)

    import requests as req, json as _json
    from pathlib import Path

    settings_path = Path('/opt/abpe/backend/settings.json')
    api_key = _json.loads(settings_path.read_text()).get('ai_models', {}).get('deepseek', {}).get('api_key')

    prompt = (
        f"For the language described as: \"{description}\"\n"
        f"Return ONLY a JSON object with these exact fields:\n"
        f"{{\"code\": \"ISO-639-1 code\", \"name\": \"English name\", "
        f"\"native\": \"Native name\", \"flag\": \"Flag emoji\", "
        f"\"direction\": \"ltr or rtl\"}}\n"
        f"No explanation, only JSON."
    )

    try:
        resp = req.post(
            'https://api.deepseek.com/v1/chat/completions',
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json={'model': 'deepseek-chat', 'messages': [
                {'role': 'system', 'content': 'You are a linguistics expert. Reply only with JSON.'},
                {'role': 'user', 'content': prompt}
            ], 'temperature': 0},
            timeout=30, verify=False
        )
        raw  = resp.json()['choices'][0]['message']['content'].strip()
        if raw.startswith('```'): raw = raw.split('\n',1)[1].rsplit('```',1)[0].strip()
        info = _json.loads(raw)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Deepseek Fehler: {e}'}, status=500)

    # In lang_map.json eintragen
    lang_map_path = Path('/opt/abpe/backend/apps/abpe_ui/bin/lang_map.json')
    try:
        lang_map = _json.loads(lang_map_path.read_text(encoding='utf-8')) if lang_map_path.exists() else {}
        lang_map[info['code']] = {
            'name':   info['name'],
            'native': info['native'],
            'flag':   info.get('flag', '🏳️'),
        }
        lang_map_path.write_text(_json.dumps(lang_map, ensure_ascii=False, indent=4), encoding='utf-8')
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'lang_map.json Fehler: {e}'}, status=500)

    return JsonResponse({'success': True, **info})
