"""
abpe_crm/views_token.py
Token-Login Endpoint für ABpE Softphone Electron App.

POST /crm/api/auth/token/
Content-Type: application/json
Body: {"username": "admin", "password": "abcona2025"}

Returns:
  200: {"token": "abc123...", "user_id": 1, "username": "admin", "name": "Admin"}
  400: {"error": "..."}
  401: {"error": "Ungültige Zugangsdaten"}
"""
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token


@csrf_exempt
@require_http_methods(['POST'])
def obtain_token_view(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Ungültiges JSON'}, status=400)

    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return JsonResponse(
            {'error': 'Username und Passwort erforderlich'}, status=400
        )

    user = authenticate(request, username=username, password=password)

    if not user:
        return JsonResponse({'error': 'Ungültige Zugangsdaten'}, status=401)

    if not user.is_active:
        return JsonResponse({'error': 'Benutzer deaktiviert'}, status=403)

    token, _ = Token.objects.get_or_create(user=user)

    return JsonResponse({
        'token':    token.key,
        'user_id':  user.id,
        'username': user.username,
        'name':     f"{user.first_name} {user.last_name}".strip() or user.username,
    })
