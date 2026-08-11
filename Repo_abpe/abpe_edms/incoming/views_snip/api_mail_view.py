def api_mail_view(request, uuid=None):
    """EDMS-Mail-Detail: Header + Body + Anhang-Liste als JSON."""
    account = (request.GET.get("account") or "").strip()
    folder = (request.GET.get("folder") or "").strip()
    uid_param = (request.GET.get("uid") or "").strip()
    message_id = (request.GET.get("message_id") or "").strip()

    if not account or not folder or not (uid_param or message_id):
        return JsonResponse({"ok": False,
                             "error": "account, folder, uid|message_id erforderlich"},
                            status=400)

    msg, err = _imap_fetch_message(account, folder, uid_param, message_id)
    if err:
        return JsonResponse({"ok": False, "error": err}, status=404)

    subject = _decode_mail_header(msg.get("Subject", ""))
    from_ = _decode_mail_header(msg.get("From", ""))
    to_ = _decode_mail_header(msg.get("To", ""))
    cc_ = _decode_mail_header(msg.get("Cc", ""))
    date_ = msg.get("Date", "")

    body_html = ""
    body_plain = ""
    attachments = []
    idx = 0
    for part in msg.walk():
        if part.is_multipart():
            continue
        ct = part.get_content_type()
        disp = str(part.get("Content-Disposition") or "")
        filename = part.get_filename()

        # Anhang? (Content-Disposition attachment ODER hat Dateinamen)
        if "attachment" in disp.lower() or filename:
            fname = _decode_mail_header(filename) if filename else f"anhang_{idx}"
            try:
                payload = part.get_payload(decode=True) or b""
                size = len(payload)
            except Exception:
                size = 0
            attachments.append({
                "index": idx,
                "filename": fname,
                "content_type": ct,
                "size_bytes": size,
            })
            idx += 1
            continue

        # Body-Teile
        if ct == "text/html" and not body_html:
            try:
                body_html = part.get_payload(decode=True).decode(
                    part.get_content_charset() or "utf-8", errors="replace")
            except Exception:
                pass
        elif ct == "text/plain" and not body_plain:
            try:
                body_plain = part.get_payload(decode=True).decode(
                    part.get_content_charset() or "utf-8", errors="replace")
            except Exception:
                pass

    return JsonResponse({
        "ok": True,
        "subject": subject,
        "from_addr": from_,
        "to_addr": to_,
        "cc_addr": cc_,
        "date": date_,
        "folder": folder,
        "account": account,
        "body_html": body_html,
        "body_plain": body_plain,
        "attachments": attachments,
    })
