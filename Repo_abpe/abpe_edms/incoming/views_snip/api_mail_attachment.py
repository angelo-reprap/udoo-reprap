def api_mail_attachment(request, uuid=None):
    """Liefert einen Mail-Anhang als Download (per Index aus api_mail_view)."""
    from django.http import HttpResponse

    account = (request.GET.get("account") or "").strip()
    folder = (request.GET.get("folder") or "").strip()
    uid_param = (request.GET.get("uid") or "").strip()
    message_id = (request.GET.get("message_id") or "").strip()
    try:
        want_idx = int(request.GET.get("index"))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "index erforderlich"}, status=400)

    if not account or not folder or not (uid_param or message_id):
        return JsonResponse({"ok": False,
                             "error": "account, folder, uid|message_id erforderlich"},
                            status=400)

    msg, err = _imap_fetch_message(account, folder, uid_param, message_id)
    if err:
        return JsonResponse({"ok": False, "error": err}, status=404)

    idx = 0
    for part in msg.walk():
        if part.is_multipart():
            continue
        disp = str(part.get("Content-Disposition") or "")
        filename = part.get_filename()
        if "attachment" in disp.lower() or filename:
            if idx == want_idx:
                payload = part.get_payload(decode=True) or b""
                fname = _decode_mail_header(filename) if filename else f"anhang_{idx}"
                ct = part.get_content_type() or "application/octet-stream"
                resp = HttpResponse(payload, content_type=ct)
                resp["Content-Disposition"] = f'attachment; filename="{fname}"'
                return resp
            idx += 1

    return JsonResponse({"ok": False, "error": "Anhang nicht gefunden"}, status=404)
