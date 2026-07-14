# Ersetzt api_deepseek_suggest in apps/abpe_meetme/views.py (Funktion komplett)


@extend_schema(
    summary="DeepSeek-Vorschlag fuer Erinnerungs-/Einladungstext generieren",
    request={'application/json': {'type': 'object', 'properties': {
        'text': {'type': 'string'},
        'prompt_key': {'type': 'string'},
        'variables': {'type': 'object'},
        'subject': {'type': 'string'},
        'format': {'type': 'string', 'enum': ['text', 'html']},
    }}},
    responses={200: None},
)
@api_view(['POST'])
def api_deepseek_suggest(request):
    text = (request.data.get('text') or '').strip()
    if not text:
        return Response({'error': 'text erforderlich'}, status=400)
    prompt_key = (request.data.get('prompt_key') or 'meetme_email').strip()
    variables = request.data.get('variables') or {}
    subject = (request.data.get('subject') or '').strip()
    fmt = (request.data.get('format') or 'text').strip()
    try:
        from apps.abpe_email_studio.services.deepseek_raupe import deepseek_raupe
        out = deepseek_raupe.full_pipeline(
            text,
            variables,
            request.user,
            prompt_key=prompt_key,
            subject=subject,
            fmt=fmt,
        )
    except Exception as exc:
        logger.warning("DeepSeek-Vorschlag fehlgeschlagen: %s", exc)
        return Response({'error': 'DeepSeek nicht verfuegbar'}, status=502)
    if not out.get('success'):
        return Response({'error': out.get('error') or 'DeepSeek-Fehler'}, status=502)
    return Response({
        'suggestion': out['suggestion'],
        'suggestion_raw': out['raw'],
    })
