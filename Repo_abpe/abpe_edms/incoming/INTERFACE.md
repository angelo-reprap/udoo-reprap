# EDMS Mail-Schnittstellen (aus Live-PROBE 04.08.2026)

## URLs (`abpe_edms/urls.py`)

```
api/person/<crm_id>/mails/     → api_person_mails   (ES-Liste je Person)
api/mail/view/                 → api_mail_view      (IMAP Detail)
api/mail/attachment/           → api_mail_attachment
api/mail/attachment/preview/   → api_mail_attachment_preview
```

## api_mail_view — Viewer

**Pflicht-Query:** `account` + `folder` + (`uid` **oder** `message_id`)

```
GET …/api/mail/view/?account=vertrieb&folder=INBOX&uid=12345
GET …/api/mail/view/?account=vertrieb&folder=INBOX&message_id=<…>
```

Intern: `_imap_fetch_message(account, folder, uid, message_id)` → MIME walk →
JSON Header + body_html/body_plain + attachments[].

**Nicht** ES-`_id`. Posteingang muss uid/message_id aus dem Index mitgeben.

## api_mail_attachment(+preview)

Gleiche Identifikation + `index` (0-basiert aus view-Response).

## api_person_mails — Suchmuster für Inbox `?q=`

ES `abpe_emails`, `multi_match` auf `subject^2`, `body`, `operator: and`.
Zusätzlich Adress-Match über `from_addr` / `to_addr` (Person) — im Posteingang
stattdessen Account/Folder-Filter.

## JS

`mod-dms*.js` unter `static/abpe_ui/js/mod/` **nicht gefunden** (PROBE §3/4 leer).
Live nachsuchen:

```bash
find /opt/abpe/backend/apps/abpe_ui -iname '*dms*' 2>/dev/null | head -40
grep -rn "mail/view\|api/mail" /opt/abpe/backend/apps/abpe_ui --include='*.js' --include='*.html' 2>/dev/null | head -40
grep -rn "edms" /opt/abpe/backend/abpe_backend/urls.py /opt/abpe/backend/apps/*/urls.py 2>/dev/null | head -20
```
