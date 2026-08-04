# EDMS Mail-Schnittstellen (PROBE 04.08.2026, ucs5)

## Mount
- API: `/edms/api/...` (`path('edms/', include('apps.abpe_edms.urls'))`)
- UI-Seite CRM: `/crm/dms/` (`abpe_crm` → `views.edms`)

## Endpoints

| Pfad | Params | Quelle |
|---|---|---|
| `GET /edms/api/mail/view/` | `account`, `folder`, `uid` **oder** `message_id` | IMAP `_imap_fetch_message` |
| `GET /edms/api/mail/attachment/` | + `index` | IMAP Download |
| `GET /edms/api/mail/attachment/preview/` | + `index` | IMAP Preview |
| `GET /edms/api/person/<crm_id>/mails/` | `q`, `size` | ES `abpe_emails` |

## JS (nicht mod-dms*)
Treffer: `mod-namazu.js` nutzt `/api/email/view/` (Namazu/Automail-Alias,
gleiche Query-Form: `account`+`folder`+`message_id`).

Posteingang verdrahtet **direkt** `/edms/api/mail/view/` mit `view_params`
aus der Shaduler-Inbox-Liste.

## PEEK
`_imap_fetch_message` existiert (views.py:1129). Ob `BODY.PEEK` — bei Bedarf
einzeln prüfen. Leitplanke: kein `\\Seen` setzen.
