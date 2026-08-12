#!/bin/bash
# ============================================================
# wavnotes_03_views_urls.sh
# WAV-Notizen — Etappe 3: Views (in views_ami.py, gleiches Muster wie
# api_notiz_format/api_telefon_vmboxes) + URLs.
# ============================================================
set -e
cd /opt/abpe/backend

VIEWS="apps/abpe_crm/views_ami.py"
URLS="apps/abpe_crm/urls.py"

echo "=== [1/5] Backups ==="
python3 Archiv/backup_restore.py -save "$VIEWS" -m "wavnotes_03: vor wavnotes views"
python3 Archiv/backup_restore.py -save "$URLS" -m "wavnotes_03: vor wavnotes urls"

echo "=== [2/5] Views anhaengen (idempotent) ==="
python3 - << 'PYEOF'
p = 'apps/abpe_crm/views_ami.py'
s = open(p, encoding='utf-8').read()

if 'api_telefon_wavnotes' in s:
    print("  api_telefon_wavnotes existiert schon — uebersprungen.")
else:
    add = '''

# =============================================================================
#  WAV-NOTIZEN (Voicemail zentral, unabhaengig von Kontakt-Zuordnung)
# =============================================================================
@extend_schema(summary="WAV-Notizen: alle Voicemail-Nachrichten (INBOX+Old)",
               tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_get
def api_telefon_wavnotes(request):
    try:
        from .services.ami_control import get_voicemail_boxes
        from .services.voicemail_wavnotes import list_wavnotes
        from apps.abpe_crm.models import CrmContactNote

        mailboxes = [b['box'] for b in get_voicemail_boxes()]
        notes = list_wavnotes(mailboxes)

        documented = set(
            CrmContactNote.objects.filter(
                wavnote_mailbox__isnull=False, wavnote_msg_id__isnull=False,
            ).values_list('wavnote_mailbox', 'wavnote_msg_id')
        )
        for n in notes:
            n['has_note'] = (n['mailbox'], n['msg_id']) in documented

        return JsonResponse({'success': True, 'data': notes})
    except Exception as e:
        logger.error(f'api_telefon_wavnotes Fehler: {e}')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@extend_schema(summary="WAV-Notiz Audio streamen (Cache-first von PBX)",
               tags=TAGS,
               parameters=[
                   _p('mailbox', OpenApiTypes.STR, 'Mailbox-Nummer'),
                   _p('folder', OpenApiTypes.STR, 'INBOX oder Old'),
                   _p('msg_id', OpenApiTypes.STR, 'z.B. msg0002'),
               ])
@_drf_get
def api_telefon_wavnote_audio(request):
    import os
    from django.conf import settings
    from django.http import FileResponse
    from .services.voicemail_wavnotes import fetch_wav_bytes, FOLDERS

    mailbox = request.GET.get('mailbox', '').strip()
    folder = request.GET.get('folder', '').strip()
    msg_id = request.GET.get('msg_id', '').strip()
    if not mailbox or folder not in FOLDERS or not msg_id:
        return JsonResponse({'success': False, 'error': 'mailbox/folder/msg_id fehlt oder ungueltig'}, status=400)

    cache_dir = os.path.join(str(settings.MEDIA_ROOT), 'wavnotes_cache', mailbox, folder)
    cache_path = os.path.join(cache_dir, f'{msg_id}.wav')
    if not os.path.exists(cache_path):
        try:
            data = fetch_wav_bytes(mailbox, folder, msg_id)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
        os.makedirs(cache_dir, exist_ok=True)
        with open(cache_path, 'wb') as f:
            f.write(data)

    resp = FileResponse(open(cache_path, 'rb'), content_type='audio/wav')
    resp['Accept-Ranges'] = 'bytes'
    return resp


@extend_schema(summary="WAV-Notiz transkribieren + glaetten (Whisper + DeepSeek)",
               description="body: {mailbox, folder, msg_id}",
               tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_post
def api_telefon_wavnote_transcribe(request):
    import os
    from django.conf import settings
    from .services.voicemail_wavnotes import fetch_wav_bytes, FOLDERS

    d = _json_body(request)
    mailbox = (d.get('mailbox') or '').strip()
    folder = (d.get('folder') or '').strip()
    msg_id = (d.get('msg_id') or '').strip()
    if not mailbox or folder not in FOLDERS or not msg_id:
        return JsonResponse({'success': False, 'error': 'mailbox/folder/msg_id fehlt oder ungueltig'}, status=400)

    cache_dir = os.path.join(str(settings.MEDIA_ROOT), 'wavnotes_cache', mailbox, folder)
    cache_path = os.path.join(cache_dir, f'{msg_id}.wav')
    if not os.path.exists(cache_path):
        try:
            data = fetch_wav_bytes(mailbox, folder, msg_id)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
        os.makedirs(cache_dir, exist_ok=True)
        with open(cache_path, 'wb') as f:
            f.write(data)

    from .services.whisper_service import whisper_service
    try:
        raw = whisper_service.transcribe(cache_path, language='de')
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Transkription fehlgeschlagen: {e}'}, status=500)

    from .services.deepseek_api_pbx import deepseek_pbx
    polished_text = raw['text']
    deepseek_error = None
    if deepseek_pbx.is_available():
        res = deepseek_pbx.format_note(
            raw['text'],
            context='Automatisches Whisper-Transkript einer Voicemail, kann Verhoerer/Tippfehler enthalten.',
        )
        if res.success:
            polished_text = res.text
        else:
            deepseek_error = res.error

    return JsonResponse({
        'success': True,
        'raw_text': raw['text'],
        'polished_text': polished_text,
        'language': raw['language'],
        'deepseek_error': deepseek_error,
    })


@extend_schema(summary="WAV-Notiz als Telefonnotiz speichern (CrmContactNote)",
               description="body: {mailbox, folder, msg_id, note_text, raw_text?, contact_crm_id?, account_crm_id?}",
               tags=TAGS, responses={200: OpenApiTypes.OBJECT})
@_drf_post
def api_telefon_wavnote_save(request):
    from apps.abpe_crm.models import CrmContact, CrmAccount, CrmContactNote

    d = _json_body(request)
    note_text = (d.get('note_text') or '').strip()
    if not note_text:
        return JsonResponse({'success': False, 'error': 'note_text fehlt'}, status=400)

    contact_crm_id = d.get('contact_crm_id')
    account_crm_id = d.get('account_crm_id')
    contact = CrmContact.objects.filter(crm_id=contact_crm_id).first() if contact_crm_id else None
    account = CrmAccount.objects.filter(crm_id=account_crm_id).first() if account_crm_id else None

    note = CrmContactNote.objects.create(
        contact=contact,
        account=account,
        note_text=note_text,
        note_type='phone',
        created_by=request.user.username,
        wavnote_mailbox=d.get('mailbox') or None,
        wavnote_msg_id=d.get('msg_id') or None,
        wavnote_raw_text=d.get('raw_text') or None,
    )
    return JsonResponse({'success': True, 'id': note.id})
'''
    s = s.rstrip() + '\n' + add + '\n'
    open(p, 'w', encoding='utf-8').write(s)
    print("  4 Views angehaengt (wavnotes/audio/transcribe/save).")
PYEOF

echo "=== [3/5] Syntax-Check views_ami.py ==="
python3 -c "import ast; ast.parse(open('$VIEWS').read()); print('  views_ami.py OK')"

echo "=== [4/5] URLs eintragen ==="
python3 - << 'PYEOF'
p = 'apps/abpe_crm/urls.py'
s = open(p, encoding='utf-8').read()
if 'api_telefon_wavnotes' in s:
    print("  Routen existieren schon — uebersprungen.")
else:
    anchor = "    path('api/telefon/notiz/',          views_ami.api_notiz_format,           name='api_notiz_format'),"
    add = anchor + "\n" + \
        "    path('api/telefon/wavnotes/',            views_ami.api_telefon_wavnotes,            name='api_telefon_wavnotes'),\n" \
        "    path('api/telefon/wavnotes/audio/',      views_ami.api_telefon_wavnote_audio,       name='api_telefon_wavnote_audio'),\n" \
        "    path('api/telefon/wavnotes/transcribe/', views_ami.api_telefon_wavnote_transcribe,  name='api_telefon_wavnote_transcribe'),\n" \
        "    path('api/telefon/wavnotes/save/',       views_ami.api_telefon_wavnote_save,        name='api_telefon_wavnote_save'),"
    assert s.count(anchor) == 1, f"URL-Anker {s.count(anchor)}x gefunden statt 1"
    s = s.replace(anchor, add)
    open(p, 'w', encoding='utf-8').write(s)
    print("  4 Routen eingetragen.")
PYEOF

echo "=== [5/5] Syntax-Check + manage.py check ==="
python3 -c "import ast; ast.parse(open('$URLS').read()); print('  urls.py OK')"
python manage.py check 2>&1 | tail -5

echo ""
echo "============================================================"
echo "✅ wavnotes_03 fertig (Views + URLs)."
echo "Danach: wavnotes_04_frontend.sh"
echo "============================================================"
