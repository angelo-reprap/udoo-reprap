def api_mail_attachment_preview(request, uuid=None):
    """Mail-Anhang als Inline-Vorschau (PDF/Bild im iframe)."""
    from django.http import HttpResponse, FileResponse
    from .services import preview as preview_svc

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

    # Anhang per Index finden
    idx = 0
    content = None
    fname = None
    for part in msg.walk():
        if part.is_multipart():
            continue
        disp = str(part.get("Content-Disposition") or "")
        filename = part.get_filename()
        if "attachment" in disp.lower() or filename:
            if idx == want_idx:
                content = part.get_payload(decode=True) or b""
                fname = _decode_mail_header(filename) if filename else f"anhang_{idx}"
                break
            idx += 1
    if content is None:
        return JsonResponse({"ok": False, "error": "Anhang nicht gefunden"}, status=404)

    ext = (fname.rsplit(".", 1)[-1] if "." in fname else "").lower()

    # Bilder direkt als Bild ausliefern (Browser zeigt sie im iframe)
    if ext in ("jpg", "jpeg", "png", "gif", "bmp", "webp"):
        ct = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
        resp = HttpResponse(content, content_type=ct)
        resp["Content-Disposition"] = f'inline; filename="{fname}"'
        return resp

    # PDF + Office -> über gemeinsame Preview-Pipeline (mit Cache)
    kind, pdf_path = preview_svc.get_preview_pdf_for_bytes(content, fname)
    if kind == "download" or not pdf_path:
        return JsonResponse({"ok": False, "kind": "download",
                             "filename": fname,
                             "reason": "Kein Inline-Preview für dieses Format"},
                            status=415)

    resp = FileResponse(open(pdf_path, "rb"), content_type="application/pdf")
    resp["Accept-Ranges"] = "bytes"
    base = fname.rsplit(".", 1)[0] if "." in fname else fname
    resp["Content-Disposition"] = f'inline; filename="{base}.pdf"'
    return resp
