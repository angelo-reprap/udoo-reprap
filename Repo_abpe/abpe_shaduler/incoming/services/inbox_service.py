"""
inbox_service — Posteingang read-only (POSTEINGANG_KONZEPT.md).

Quellen (Reihenfolge):
  1) Elasticsearch-Index ``abpe_emails`` (automail/ingest — Postfächer-Überblick)
  2) ``ingest_email.EmailMessage`` (bereits ingestete Mails, z.B. CV-Scan)
  3) Direkt-IMAP read-only aus ``ingest_email.EmailImportConfig``
     (imap_server/username/password/mailbox — keine zweite Credential-Ablage)

Kein Löschen/Verschieben / kein \\Seen — nur Header + ~200 Zeichen Preview.
"""
from __future__ import annotations

import email
import email.header
import imaplib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Optional

from django.conf import settings
from django.utils import timezone as dj_tz
from django.utils.dateparse import parse_datetime

log = logging.getLogger('abpe_shaduler.inbox')

SETTINGS_PATH = Path('/opt/abpe/backend/settings.json')


@dataclass
class InboxMail:
    id: str
    subj: str
    from_: str
    box: str
    age: str
    prev: str
    unread: bool = True
    crm: str = '—'
    received_at: Optional[str] = None
    account: str = ''
    folder: str = 'INBOX'
    uid: str = ''
    message_id: str = ''
    has_attachments: bool = False
    reply_email: str = ''
    request_id: str = ''
    matching_url: str = ''
    email_studio_url: str = ''
    mailto_url: str = ''
    crm_bean_id: str = ''
    crm_bean_module: str = ''

    def as_dict(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'subj': self.subj,
            'from': self.from_,
            'box': self.box,
            'age': self.age,
            'prev': self.prev,
            'unread': self.unread,
            'crm': self.crm,
            'received_at': self.received_at,
            'account': self.account,
            'folder': self.folder,
            'uid': self.uid,
            'message_id': self.message_id,
            'has_attachments': self.has_attachments,
            # EDMS api_mail_view Params (IMAP)
            'view_params': {
                'account': self.account,
                'folder': self.folder or 'INBOX',
                'uid': self.uid,
                'message_id': self.message_id,
            },
            'reply_email': self.reply_email,
            'request_id': self.request_id,
            'matching_url': self.matching_url,
            'email_studio_url': self.email_studio_url,
            'mailto_url': self.mailto_url,
            'crm_bean_id': self.crm_bean_id,
            'crm_bean_module': self.crm_bean_module,
        }


@dataclass
class ImapAccount:
    host: str
    port: int = 993
    user: str = ''
    password: str = ''
    folder: str = 'INBOX'
    ssl: bool = True
    box_label: str = ''
    extra: dict = field(default_factory=dict)

    @property
    def label(self) -> str:
        return self.box_label or self.user or self.host


def _load_json_settings() -> dict:
    try:
        if SETTINGS_PATH.exists():
            return json.loads(SETTINGS_PATH.read_text(encoding='utf-8'))
    except Exception as exc:
        log.warning('settings.json nicht lesbar: %s', exc)
    return {}


def _accounts_from_django_settings() -> list[ImapAccount]:
    raw = getattr(settings, 'SHADULER_IMAP_ACCOUNTS', None)
    if not raw:
        return []
    out = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        out.append(ImapAccount(
            host=row.get('host') or '172.20.3.150',
            port=int(row.get('port') or (993 if row.get('ssl', True) else 143)),
            user=row.get('user') or row.get('username') or '',
            password=row.get('password') or '',
            folder=row.get('folder') or 'INBOX',
            ssl=bool(row.get('ssl', True)),
            box_label=row.get('box_label') or row.get('label') or '',
        ))
    return out


def _accounts_from_settings_json() -> list[ImapAccount]:
    cfg = _load_json_settings()
    raw = (
        cfg.get('shaduler', {}).get('imap_accounts')
        or cfg.get('ingest_email', {}).get('imap_accounts')
        or cfg.get('imap_accounts')
        or []
    )
    if isinstance(raw, dict):
        raw = [raw]
    out = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        out.append(ImapAccount(
            host=row.get('host') or '172.20.3.150',
            port=int(row.get('port') or (993 if row.get('ssl', True) else 143)),
            user=row.get('user') or row.get('username') or '',
            password=row.get('password') or '',
            folder=row.get('folder') or 'INBOX',
            ssl=bool(row.get('ssl', True)),
            box_label=row.get('box_label') or row.get('label') or '',
        ))
    return out


def _accounts_from_ingest_email() -> list[ImapAccount]:
    """IMAP aus ``ingest_email.EmailImportConfig`` (exakte Felder, Konzept)."""
    try:
        from apps.ingest_email.models import EmailImportConfig
    except Exception:
        try:
            from django.apps import apps
            EmailImportConfig = apps.get_model('ingest_email', 'EmailImportConfig')
        except Exception:
            return []

    out: list[ImapAccount] = []
    try:
        qs = EmailImportConfig.objects.filter(is_active=True).order_by('name')
        for row in qs[:20]:
            user = (row.username or row.email_address or '').strip()
            host = (row.imap_server or '').strip() or '172.20.3.150'
            if not user:
                continue
            out.append(ImapAccount(
                host=host,
                port=int(row.imap_port or 993),
                user=user,
                password=str(row.password or ''),
                folder=(row.mailbox or 'INBOX').strip() or 'INBOX',
                ssl=bool(row.use_ssl),
                box_label=(row.name or row.email_address or user),
                extra={
                    'pk': str(row.pk),
                    'model': 'ingest_email.EmailImportConfig',
                    'email_address': row.email_address,
                    'protocol': row.protocol,
                },
            ))
    except Exception as exc:
        log.warning('EmailImportConfig nicht lesbar: %s', exc)
    return out


def get_imap_accounts() -> list[ImapAccount]:
    # Konzept: Zugangsdaten nur aus EmailImportConfig — danach erst Fallbacks
    for loader in (_accounts_from_ingest_email, _accounts_from_django_settings, _accounts_from_settings_json):
        acc = loader()
        if acc:
            return acc
    return []


def _decode_bytes(data: bytes, charset: Optional[str] = None) -> str:
    """Strict charset cascade — kein errors=replace (sonst `` statt Umlaute)."""
    if not data:
        return ''
    candidates: list[str] = []
    if charset:
        cs = charset.strip().lower().replace('"', '')
        aliases = {
            'unknown-8bit': 'utf-8', 'x-unknown': 'utf-8', 'default': 'utf-8',
            'utf8': 'utf-8', 'iso8859-1': 'latin-1', 'iso-8859-1': 'latin-1',
            'windows-1252': 'cp1252',
        }
        candidates.append(aliases.get(cs, cs))
    for cs in ('utf-8', 'cp1252', 'latin-1'):
        if cs not in candidates:
            candidates.append(cs)
    for cs in candidates:
        try:
            return data.decode(cs)
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode('utf-8', errors='replace')


def _decode_header(val: Optional[str]) -> str:
    if not val:
        return ''
    try:
        parts = email.header.decode_header(val)
        out = []
        for chunk, enc in parts:
            if isinstance(chunk, bytes):
                out.append(_decode_bytes(chunk, enc))
            else:
                out.append(str(chunk))
        return ''.join(out).strip()
    except Exception:
        return str(val or '').strip()


def _fix_mojibake(text: str) -> str:
    """UTF-8-als-Latin1 + HTML-Entities (KlimagerÃ¤t / &auml; → ä)."""
    if not text:
        return text
    import html as html_mod
    s = str(text)
    if 'Ã' in s or 'Â' in s:
        try:
            s = s.encode('latin-1').decode('utf-8')
        except Exception:
            pass
    if '&' in s:
        try:
            s = html_mod.unescape(s)
        except Exception:
            pass
    return s


def _subject_from_html(html: str) -> str:
    """Betreff aus <title> retten, wenn Index-Subject `` enthält."""
    if not html:
        return ''
    m = re.search(r'(?is)<title[^>]*>(.*?)</title>', html)
    if not m:
        return ''
    return _fix_mojibake(re.sub(r'\s+', ' ', m.group(1))).strip()


def _clean_subject(subj: str, *, body_html: str = '') -> str:
    s = _fix_mojibake(subj or '')
    # U+FFFD = Fehlerzeichen von errors='replace' beim Indexieren
    if '\ufffd' in s:
        alt = _subject_from_html(body_html)
        if alt:
            return alt
    return s or '(ohne Betreff)'


def _age_label(dt: Optional[datetime]) -> str:
    if not dt:
        return ''
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    delta = now - dt.astimezone(timezone.utc)
    secs = int(delta.total_seconds())
    if secs < 0:
        secs = 0
    if secs < 3600:
        m = max(1, secs // 60)
        return f'vor {m} Min'
    if secs < 86400:
        h = secs // 3600
        return f'vor {h} Std'
    d = secs // 86400
    if d == 1:
        return 'gestern'
    return f'vor {d} Tagen'


def _preview_text(msg: email.message.Message, limit: int = 180) -> str:
    text = ''
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get('Content-Disposition') or '')
            if ctype == 'text/plain' and 'attachment' not in disp.lower():
                payload = part.get_payload(decode=True) or b''
                charset = part.get_content_charset() or 'utf-8'
                text = payload.decode(charset, errors='replace')
                break
    else:
        payload = msg.get_payload(decode=True) or b''
        charset = msg.get_content_charset() or 'utf-8'
        text = payload.decode(charset, errors='replace')
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > limit:
        return text[: limit - 1] + '…'
    return text


def _extract_email(addr: str) -> str:
    if not addr:
        return ''
    s = addr.strip()
    m = re.search(r'<([^>]+)>', s)
    if m:
        return m.group(1).strip().lower()
    if '@' in s:
        return s.strip().lower().strip('<>')
    return ''


def _request_id_from_subject(subj: str) -> str:
    if not subj:
        return ''
    m = re.search(r'#\s*(\d{3,})', subj)
    return m.group(1) if m else ''


def _crm_resolve(addr: str, *, subject: str = '') -> dict[str, str]:
    """Absender → CrmEmailAddrBeanRel + Deeplinks (Konzept Kap. 2.2 / 3)."""
    email_addr = _extract_email(addr)
    request_id = _request_id_from_subject(subject)
    out = {
        'crm': '—',
        'crm_bean_id': '',
        'crm_bean_module': '',
        'reply_email': email_addr,
        'request_id': request_id,
        'matching_url': f'/matching/?request={request_id}' if request_id else '',
        'email_studio_url': (
            f'/email-studio/studio/?to={email_addr}' if email_addr else '/email-studio/studio/'
        ),
        'mailto_url': (
            f'mailto:{email_addr}?subject={_mailto_subject(subject)}' if email_addr else ''
        ),
    }
    if not email_addr:
        return out

    try:
        from django.apps import apps
        EmailAddr = None
        for label, name in (
            ('abpe_crm', 'CrmEmailAddress'),
            ('abpe_crm', 'EmailAddress'),
        ):
            try:
                EmailAddr = apps.get_model(label, name)
                break
            except Exception:
                continue
        if EmailAddr is None:
            return out

        row = None
        if hasattr(EmailAddr, 'email_address'):
            row = EmailAddr.objects.filter(email_address__iexact=email_addr).first()
        if not row:
            for field in ('email', 'address'):
                if hasattr(EmailAddr, field):
                    row = EmailAddr.objects.filter(**{f'{field}__iexact': email_addr}).first()
                    if row:
                        break
        if not row:
            return out

        bean_module = ''
        bean_id = ''
        try:
            Rel = apps.get_model('abpe_crm', 'CrmEmailAddrBeanRel')
            link = Rel.objects.filter(email_address_id=getattr(row, 'pk', None) or getattr(row, 'crm_id', None)).first()
            if link is None and hasattr(Rel, 'email_address'):
                link = Rel.objects.filter(email_address__email_address__iexact=email_addr).first()
            if link:
                bean_module = str(
                    getattr(link, 'bean_module', '')
                    or getattr(link, 'bean_type', '')
                    or getattr(link, 'module', '')
                    or ''
                )
                bean_id = str(getattr(link, 'bean_id', '') or '')
        except Exception:
            pass

        # Anzeige: Modul-Kurzname + optional Anfrage aus Betreff
        mod_label = bean_module.replace('Contacts', 'Berater').replace('Accounts', 'Firma') or 'CRM'
        parts = [mod_label]
        if request_id:
            parts.append(f'Anfrage #{request_id}')
        elif bean_id:
            parts.append(str(bean_id)[:8])
        out['crm'] = ' · '.join(parts)
        out['crm_bean_id'] = bean_id
        out['crm_bean_module'] = bean_module
        if not out['matching_url'] and bean_id:
            out['matching_url'] = f'/matching/?crm_id={bean_id}'
    except Exception:
        pass
    return out


def _mailto_subject(subj: str) -> str:
    from urllib.parse import quote
    s = (subj or '').strip()
    if s and not s.lower().startswith('re:'):
        s = f'Re: {s}'
    return quote(s[:120])


def _apply_crm_links(mail: InboxMail) -> InboxMail:
    info = _crm_resolve(mail.from_, subject=mail.subj)
    mail.crm = info['crm']
    mail.crm_bean_id = info['crm_bean_id']
    mail.crm_bean_module = info['crm_bean_module']
    mail.reply_email = info['reply_email']
    mail.request_id = info['request_id']
    mail.matching_url = info['matching_url']
    mail.email_studio_url = info['email_studio_url']
    mail.mailto_url = info['mailto_url']
    return mail


def _crm_hint_for_email(addr: str) -> str:
    """Rückwärtskompatibel: nur Label-String."""
    return _crm_resolve(addr).get('crm') or '—'


def _fetch_imap_account(acc: ImapAccount, limit: int = 25) -> list[InboxMail]:
    if not acc.user or not acc.password:
        log.warning('IMAP %s: Credentials fehlen', acc.label)
        return []
    mails: list[InboxMail] = []
    client = None
    try:
        if acc.ssl:
            client = imaplib.IMAP4_SSL(acc.host, acc.port, timeout=20)
        else:
            client = imaplib.IMAP4(acc.host, acc.port, timeout=20)
        client.login(acc.user, acc.password)
        typ, _ = client.select(acc.folder, readonly=True)
        if typ != 'OK':
            log.warning('IMAP select %s fehlgeschlagen: %s', acc.folder, typ)
            return []
        typ, data = client.search(None, 'ALL')
        if typ != 'OK' or not data or not data[0]:
            return []
        ids = data[0].split()
        ids = ids[-limit:]
        ids.reverse()  # neueste zuerst
        for uid in ids:
            typ, msg_data = client.fetch(uid, '(FLAGS BODY.PEEK[HEADER] BODY.PEEK[TEXT]<0.800>)')
            if typ != 'OK' or not msg_data:
                continue
            raw_header = b''
            raw_text = b''
            flags = b''
            for item in msg_data:
                if isinstance(item, tuple) and len(item) >= 2:
                    meta = item[0] if isinstance(item[0], (bytes, bytearray)) else b''
                    flags += meta
                    payload = item[1]
                    if b'HEADER' in meta.upper() or not raw_header:
                        # erstes Payload oft Header
                        if b'Subject:' in payload or b'From:' in payload:
                            raw_header = payload
                        else:
                            raw_text = payload
                    else:
                        raw_text = payload
            # Fallback: manches IMAP liefert nur ein Blob
            if not raw_header and msg_data:
                for item in msg_data:
                    if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], (bytes, bytearray)):
                        if not raw_header:
                            raw_header = item[1]
                        else:
                            raw_text = item[1]

            msg = email.message_from_bytes(raw_header or b'')
            # Wenn Header-Parse dünn: ganzes Message versuchen
            if not msg.get('Subject') and raw_text:
                full = email.message_from_bytes(raw_header + b'\r\n' + raw_text)
                if full.get('Subject'):
                    msg = full

            subj = _decode_header(msg.get('Subject'))
            from_ = _decode_header(msg.get('From'))
            date_hdr = msg.get('Date')
            dt = None
            try:
                if date_hdr:
                    dt = parsedate_to_datetime(date_hdr)
            except Exception:
                dt = None
            unread = b'\\Seen' not in flags
            # Preview aus TEXT-Teil
            prev = ''
            if raw_text:
                try:
                    # TEXT kann kein vollständiges MIME sein
                    prev = re.sub(r'\s+', ' ', raw_text.decode('utf-8', errors='replace')).strip()[:180]
                except Exception:
                    prev = ''
            if not prev:
                prev = _preview_text(msg)

            mid = f"{acc.user}:{acc.folder}:{uid.decode() if isinstance(uid, bytes) else uid}"
            mails.append(_apply_crm_links(InboxMail(
                id=mid,
                subj=subj or '(ohne Betreff)',
                from_=from_ or '—',
                box=acc.label,
                age=_age_label(dt),
                prev=prev or '—',
                unread=unread,
                received_at=dt.isoformat() if dt else None,
                account=acc.user,
            )))
    except Exception as exc:
        log.exception('IMAP fetch %s@%s fehlgeschlagen: %s', acc.user, acc.host, exc)
    finally:
        if client is not None:
            try:
                client.logout()
            except Exception:
                pass
    return mails


def _es_hosts() -> list[str]:
    cfg = _load_json_settings()
    es_cfg = cfg.get('elasticsearch') or {}
    hosts = es_cfg.get('hosts')
    if not hosts:
        dsl = getattr(settings, 'ELASTICSEARCH_DSL', None) or {}
        if isinstance(dsl, dict):
            hosts = (dsl.get('default') or {}).get('hosts')
    if not hosts:
        hosts = getattr(settings, 'ELASTICSEARCH_HOSTS', None)
    if not hosts:
        hosts = ['http://localhost:9200']
    if isinstance(hosts, str):
        hosts = [hosts]
    # django-elasticsearch-dsl akzeptiert manchmal "localhost:9200" ohne Schema
    out = []
    for h in hosts:
        h = str(h).strip()
        if h and '://' not in h:
            h = f'http://{h}'
        if h:
            out.append(h)
    return out or ['http://localhost:9200']


def _es_mail_index() -> str:
    cfg = _load_json_settings()
    sh = cfg.get('shaduler') or {}
    return (
        sh.get('es_mail_index')
        or (cfg.get('elasticsearch') or {}).get('mail_index')
        or getattr(settings, 'SHADULER_ES_MAIL_INDEX', None)
        or 'abpe_emails'
    )


def _es_mail_cfg() -> dict[str, Any]:
    cfg = _load_json_settings()
    return (cfg.get('shaduler') or {}).get('es_mail') or {}


def _es_sane_date_filters() -> list[dict]:
    """
    Index enthält kaputte Daten (z.B. year 4501) — die gewinnen sonst sort=date:desc.
    Nur plausible Mail-Daten erlauben.
    """
    return [
        {'range': {'date': {'gte': '2000-01-01', 'lte': 'now+1d'}}},
    ]


def _es_inbox_query(
    *,
    account: Optional[str] = None,
    q: Optional[str] = None,
    has_attachment: Optional[bool] = None,
) -> dict[str, Any]:
    """Account-/Folder-/Zeitfenster-/Suche-Filter aus settings + Request."""
    sh = _es_mail_cfg()
    accounts = sh.get('accounts') or getattr(settings, 'SHADULER_ES_ACCOUNTS', None) or []
    folder = sh.get('folder')
    if folder is None:
        folder = getattr(settings, 'SHADULER_ES_FOLDER', 'INBOX')
    days = sh.get('days')
    if days is None:
        days = getattr(settings, 'SHADULER_ES_DAYS', None)

    filters: list[dict] = list(_es_sane_date_filters())
    must: list[dict] = []
    account = (account or '').strip()
    if account:
        filters.append({
            'bool': {
                'should': [
                    {'term': {'account': account}},
                    {'term': {'account.keyword': account}},
                    {'match_phrase': {'account': account}},
                ],
                'minimum_should_match': 1,
            }
        })
    elif accounts:
        if isinstance(accounts, str):
            accounts = [accounts]
        filters.append({'terms': {'account': list(accounts)}})
    if folder:
        filters.append({
            'bool': {
                'should': [
                    {'term': {'folder': folder}},
                    {'term': {'folder.keyword': folder}},
                    {'match_phrase': {'folder': folder}},
                ],
                'minimum_should_match': 1,
            }
        })
    if days:
        try:
            d = max(1, int(days))
            filters.append({'range': {'date': {'gte': f'now-{d}d/d'}}})
        except Exception:
            pass
    if has_attachment is True:
        filters.append({
            'bool': {
                'should': [
                    {'term': {'has_attachments': True}},
                    {'term': {'has_attachment': True}},
                    {'range': {'attachment_count': {'gte': 1}}},
                ],
                'minimum_should_match': 1,
            }
        })
    elif has_attachment is False:
        filters.append({
            'bool': {
                'must_not': [
                    {'term': {'has_attachments': True}},
                    {'term': {'has_attachment': True}},
                    {'range': {'attachment_count': {'gte': 1}}},
                ],
            }
        })
    q = (q or '').strip()
    if q:
        # gleiches Muster wie EDMS api_person_mails
        must.append({
            'multi_match': {
                'query': q,
                'fields': ['subject^2', 'body', 'from_addr', 'to_addr'],
                'operator': 'and',
            }
        })
    bool_q: dict[str, Any] = {'filter': filters}
    if must:
        bool_q['must'] = must
    return {'bool': bool_q}


def _strip_html(text: str) -> str:
    t = re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>', ' ', text or '')
    t = re.sub(r'(?is)<br\s*/?>', '\n', t)
    t = re.sub(r'(?is)</p>', '\n', t)
    t = re.sub(r'(?s)<[^>]+>', ' ', t)
    t = _fix_mojibake(t)
    return re.sub(r'[ \t]+\n', '\n', re.sub(r'[ \t]{2,}', ' ', t)).strip()


def _es_preview(src: dict) -> str:
    body = src.get('body') or src.get('snippet') or src.get('preview') or ''
    text = _strip_html(str(body)) if '<' in str(body) else _fix_mojibake(str(body))
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:180] if text else '—'


def _looks_like_html(raw: str) -> bool:
    """Echte HTML-Mails — nicht Plaintext mit <email@x.de>-Klammern."""
    if not raw:
        return False
    if re.search(r'(?is)<\s*(html|body|div|p|br|table|tr|td|span|font|h[1-6]|ul|ol|li|blockquote|hr)\b', raw):
        return True
    if re.search(r'(?is)<\s*!(DOCTYPE|----)', raw):
        return True
    return False


def _plain_to_readable_html(text: str) -> str:
    """Plaintext → Absätze + Zeilenumbrüche (lesbar, nicht perfekt)."""
    import html as html_mod
    t = (text or '').replace('\r\n', '\n').replace('\r', '\n').strip()
    if not t:
        return ''
    # Soft-Wraps / lange Leerzeichenketten entschärfen
    t = re.sub(r'[ \t]+\n', '\n', t)
    # Wenig echte Absätze: Soft-Breaks an typischen Mail-Markern
    if len(re.findall(r'\n\s*\n', t)) < 2 and len(t) > 120:
        t = re.sub(r'\s*(-{3,}|_{3,}|\*{3,})\s*', r'\n\n\1\n\n', t)
        t = re.sub(
            r'(^|[\s>])(Von|From|Gesendet|Sent|An|To|Betreff|Subject|Cc|Bcc)\s*:',
            r'\1\n\n\2:',
            t,
            flags=re.I,
        )
        t = re.sub(
            r'\s+(Mit freundlichen Grüßen|Viele Grüße|Liebe Grüße|Best regards|Kind regards|Freundliche Grüße)\b',
            r'\n\n\1',
            t,
            flags=re.I,
        )
        t = re.sub(
            r'\s+(Hallo\b|Liebe[rn]?\s+\S+|Guten\s+(?:Tag|Morgen|Abend)\b)',
            r'\n\n\1',
            t,
        )
    paras = re.split(r'\n\s*\n+', t)
    chunks = []
    for p in paras:
        p = p.strip()
        if not p:
            continue
        esc = html_mod.escape(p)
        esc = esc.replace('\n', '<br>\n')
        chunks.append(f'<p class="sh-p">{esc}</p>')
    return '\n'.join(chunks)


def _split_mail_body(raw: str) -> tuple[str, str]:
    """→ (body_html, body_plain)."""
    raw = _fix_mojibake(raw or '')
    if not raw.strip():
        return '', ''
    if _looks_like_html(raw):
        return raw, _strip_html(raw)
    # Plaintext als lesbares HTML ausliefern (Absätze)
    return _plain_to_readable_html(raw), raw


def view_mail(mail_id: str, user=None) -> dict[str, Any]:
    """
    Mail-Detail für den Viewer — primär aus ES (zuverlässig).
    Liefert gleiches JSON-Shape wie EDMS api_mail_view (soweit möglich).
    """
    mid = str(mail_id or '').strip()
    if not mid:
        return {'ok': False, 'error': 'mail_id fehlt'}

    src: dict[str, Any] = {}
    mail_dict: Optional[dict[str, Any]] = None

    if mid.startswith('es:'):
        doc_id = mid[3:]
        try:
            from elasticsearch import Elasticsearch
            es = Elasticsearch(_es_hosts())
            hit = es.get(index=_es_mail_index(), id=doc_id)
            src = hit.get('_source') or {}
            mail_dict = _hit_to_mail({'_id': doc_id, '_source': src}).as_dict()
        except Exception as exc:
            log.warning('view_mail ES get fehlgeschlagen: %s', exc)
            return {'ok': False, 'error': f'ES: {exc}'}
    else:
        # Fallback: Liste durchsuchen
        data = list_mails(limit=80, user=user)
        mail_dict = next((m for m in data.get('results') or [] if m.get('id') == mid), None)
        if not mail_dict:
            return {'ok': False, 'error': 'Mail nicht gefunden'}

    if user is not None:
        try:
            mark_read(mid, user)
        except Exception:
            pass

    raw_body = str(
        src.get('body') or src.get('body_html') or src.get('html')
        or src.get('snippet') or src.get('preview') or mail_dict.get('prev') or ''
    )
    body_html, body_plain = _split_mail_body(raw_body)
    subject = _clean_subject(
        str(src.get('subject') or mail_dict.get('subj') or ''),
        body_html=body_html or raw_body,
    )
    from_ = _fix_mojibake(
        str(src.get('from_addr') or src.get('from') or mail_dict.get('from') or '')
    )
    to_ = _fix_mojibake(str(src.get('to_addr') or src.get('to') or ''))
    date_ = str(src.get('date') or mail_dict.get('received_at') or '')

    atts = []
    for i, a in enumerate(src.get('attachments') or []):
        if isinstance(a, dict):
            atts.append({
                'index': i,
                'filename': a.get('filename') or a.get('name') or f'anhang_{i}',
                'size': a.get('size') or a.get('size_bytes') or 0,
                'content_type': a.get('content_type') or a.get('type') or '',
            })

    return {
        'ok': True,
        'source': 'elasticsearch',
        'mail_id': mid,
        'subject': subject,
        'from': from_,
        'to': to_,
        'date': date_,
        'body_html': body_html,
        'body_plain': body_plain,
        'attachments': atts,
        'account': mail_dict.get('account') or src.get('account') or '',
        'folder': mail_dict.get('folder') or src.get('folder') or 'INBOX',
        'uid': str(mail_dict.get('uid') or src.get('uid') or ''),
        'message_id': mail_dict.get('message_id') or src.get('message_id') or '',
        'view_params': mail_dict.get('view_params') or {
            'account': mail_dict.get('account') or src.get('account') or '',
            'folder': mail_dict.get('folder') or src.get('folder') or 'INBOX',
            'uid': str(mail_dict.get('uid') or src.get('uid') or ''),
            'message_id': mail_dict.get('message_id') or src.get('message_id') or '',
        },
        'crm': mail_dict.get('crm'),
        'hint': 'Volltext aus ES-Index (IMAP-Detail optional über EDMS).',
    }


def _es_unread(src: dict, dt: Optional[datetime] = None) -> bool:
    """Initiale „neu“-Heuristik; ABpE-Gelesen überschreibt später via InboxMailRead."""
    if 'unread' in src:
        return bool(src.get('unread'))
    if 'seen' in src:
        return not bool(src.get('seen'))
    if 'is_read' in src:
        return not bool(src.get('is_read'))
    flags = str(src.get('flags') or src.get('flag') or '').lower()
    if flags:
        return 'seen' not in flags and '\\seen' not in flags
    # Ohne Flags: frische Mails als neu — Portal-Gelesen kommt aus InboxMailRead
    if dt is not None:
        try:
            now = dj_tz.now()
            if dj_tz.is_naive(dt):
                dt = dj_tz.make_aware(dt, timezone.utc)
            return (now - dt).total_seconds() < 48 * 3600
        except Exception:
            pass
    return False


def _read_mail_ids(user) -> set[str]:
    if user is None or not getattr(user, 'pk', None):
        return set()
    try:
        from apps.abpe_shaduler.models import InboxMailRead
        return set(
            InboxMailRead.objects.filter(user=user)
            .values_list('mail_id', flat=True)[:5000]
        )
    except Exception as exc:
        log.warning('InboxMailRead lesen fehlgeschlagen: %s', exc)
        return set()


def _apply_user_read(mails: list[InboxMail], user) -> list[InboxMail]:
    """ABpE-Gelesen überschreibt Heuristik/IMAP — IMAP bleibt unverändert."""
    read_ids = _read_mail_ids(user)
    if not read_ids:
        return mails
    for m in mails:
        if m.id in read_ids:
            m.unread = False
    return mails


def mark_read(mail_id: str, user) -> dict[str, Any]:
    """Markiert Mail als in ABpE gelesen (kein IMAP \\Seen)."""
    from apps.abpe_shaduler.models import InboxMailRead

    mid = str(mail_id or '').strip()[:255]
    if not mid:
        return {'ok': False, 'error': 'mail_id fehlt'}
    if user is None or not getattr(user, 'pk', None):
        return {'ok': False, 'error': 'user fehlt'}
    row, created = InboxMailRead.objects.update_or_create(
        user=user,
        mail_id=mid,
        defaults={'read_at': dj_tz.now()},
    )
    return {
        'ok': True,
        'mail_id': mid,
        'unread': False,
        'created': created,
        'read_at': row.read_at.isoformat() if row.read_at else None,
    }


def unread_count(user, *, limit: int = 40) -> int:
    """Badge-Zähler: ungelesen in der aktuellen Posteingang-Liste."""
    try:
        data = list_mails(limit=limit, user=user)
        return int(data.get('unread') or 0)
    except Exception as exc:
        log.warning('unread_count fehlgeschlagen: %s', exc)
        return 0


def _es_parse_date(raw) -> Optional[datetime]:
    if raw is None or raw == '':
        return None
    if isinstance(raw, datetime):
        dt = raw
    elif isinstance(raw, (int, float)):
        try:
            dt = datetime.fromtimestamp(float(raw) / (1000 if raw > 1e12 else 1), tz=timezone.utc)
        except Exception:
            return None
    else:
        s = str(raw).strip()
        dt = parse_datetime(s)
        if not dt:
            try:
                dt = parsedate_to_datetime(s)
            except Exception:
                return None
    if dt is None:
        return None
    # Kaputte Index-Daten (z.B. 4501-01-01) verwerfen
    year = dt.year
    if year < 2000 or year > 2100:
        return None
    return dt


def _hit_to_mail(hit: dict) -> InboxMail:
    src = hit.get('_source') or {}
    es_id = hit.get('_id') or ''
    raw_body = str(src.get('body') or src.get('snippet') or src.get('preview') or '')
    subj = _clean_subject(str(src.get('subject') or ''), body_html=raw_body)
    from_ = _fix_mojibake(str(src.get('from_addr') or src.get('from') or '—'))
    account = src.get('account') or ''
    folder = src.get('folder') or 'INBOX'
    box = account or folder
    dt = _es_parse_date(src.get('date') or src.get('received_at'))
    uid = src.get('uid')
    if uid is None:
        uid = ''
    else:
        uid = str(uid)
    mid = str(src.get('message_id') or '').strip()
    has_att = bool(
        src.get('has_attachments')
        or src.get('has_attachment')
        or (isinstance(src.get('attachment_count'), (int, float)) and src.get('attachment_count') > 0)
        or src.get('attachments')
    )
    return _apply_crm_links(InboxMail(
        id=f'es:{es_id}',
        subj=subj,
        from_=str(from_),
        box=str(box),
        age=_age_label(dt) if dt else '',
        prev=_es_preview(src),
        unread=_es_unread(src, dt),
        received_at=dt.isoformat() if dt else (str(src.get('date') or '') or None),
        account=str(account),
        folder=str(folder),
        uid=uid,
        message_id=mid,
        has_attachments=has_att,
    ))


def _list_from_elasticsearch(
    limit: int = 40,
    *,
    account: Optional[str] = None,
    q: Optional[str] = None,
    has_attachment: Optional[bool] = None,
    sort: str = 'date_desc',
) -> Optional[list[InboxMail]]:
    """Liest den bereits indexierten Mail-Index ``abpe_emails`` (read-only)."""
    try:
        from elasticsearch import Elasticsearch
    except ImportError:
        log.info('elasticsearch-Paket nicht installiert — Skip ES-Quelle')
        return None

    hosts = _es_hosts()
    index = _es_mail_index()
    order = 'asc' if (sort or '').lower() in ('date_asc', 'asc', 'oldest') else 'desc'
    body = {
        'size': max(1, min(int(limit), 200)),
        'query': _es_inbox_query(
            account=account, q=q, has_attachment=has_attachment,
        ),
        'sort': [{'date': {'order': order, 'unmapped_type': 'date'}}],
        '_source': [
            'subject', 'from_addr', 'to_addr', 'date', 'folder', 'account',
            'message_id', 'uid', 'has_attachments', 'has_attachment',
            'attachment_count', 'attachments', 'body', 'snippet', 'preview',
            'flags', 'unread', 'seen', 'is_read',
        ],
    }
    try:
        es = Elasticsearch(hosts)
        res = es.search(index=index, body=body)
    except Exception as exc:
        log.warning('ES %s @ %s fehlgeschlagen: %s', index, hosts, exc)
        return None

    hits = (res.get('hits') or {}).get('hits') or []
    # Fallback nur ohne Such-/Anhang-/Account-Filter
    restrictive = bool(
        (account or '').strip()
        or (q or '').strip()
        or has_attachment is not None
    )
    if not hits and not restrictive:
        sh = _es_mail_cfg()
        try:
            body2 = dict(body)
            filters = list(_es_sane_date_filters())
            accounts = sh.get('accounts') or []
            if accounts:
                if isinstance(accounts, str):
                    accounts = [accounts]
                filters.append({'terms': {'account': list(accounts)}})
            body2['query'] = {'bool': {'filter': filters}}
            res2 = es.search(index=index, body=body2)
            hits = (res2.get('hits') or {}).get('hits') or []
        except Exception as exc:
            log.warning('ES Fallback fehlgeschlagen: %s', exc)

    return [_hit_to_mail(h) for h in hits]


def _account_chips(mails: list[InboxMail], *, filter_account: str = '') -> list[dict]:
    """Postfach-Chips: konfigurierte Accounts + Treffer-Counts."""
    boxes: dict[str, int] = {}
    for m in mails:
        key = (m.account or m.box or '').strip() or '?'
        boxes[key] = boxes.get(key, 0) + 1
    configured = _es_mail_cfg().get('accounts') or getattr(settings, 'SHADULER_ES_ACCOUNTS', None) or []
    if isinstance(configured, str):
        configured = [configured]
    for acc in configured:
        acc = str(acc).strip()
        if acc and acc not in boxes:
            boxes[acc] = 0
    out = []
    for k, v in sorted(boxes.items(), key=lambda kv: (-kv[1], kv[0].lower())):
        row: dict[str, Any] = {
            'label': k,
            'active': bool(filter_account) and k == filter_account,
        }
        # Bei aktivem Filter sind Counts anderer Postfächer unzuverlässig → weglassen
        if not filter_account or k == filter_account:
            row['count'] = v
        out.append(row)
    return out


def _get_es_mail(mail_id: str) -> Optional[dict[str, Any]]:
    """Einzelne Mail aus ES (id = es:<_id>)."""
    if not str(mail_id).startswith('es:'):
        return None
    doc_id = str(mail_id)[3:]
    try:
        from elasticsearch import Elasticsearch
        es = Elasticsearch(_es_hosts())
        hit = es.get(index=_es_mail_index(), id=doc_id)
        if not hit or not hit.get('found', True):
            # ältere Clients: get wirft oder liefert _source
            pass
        mail = _hit_to_mail({'_id': doc_id, '_source': hit.get('_source') or {}})
        return mail.as_dict()
    except Exception as exc:
        log.warning('ES get %s fehlgeschlagen: %s', mail_id, exc)
        return None


def _list_from_ingest_db(limit: int = 40) -> Optional[list[InboxMail]]:
    """Liest ``ingest_email.EmailMessage`` (exakte Felder)."""
    try:
        from apps.ingest_email.models import EmailMessage
    except Exception:
        try:
            from django.apps import apps
            EmailMessage = apps.get_model('ingest_email', 'EmailMessage')
        except Exception:
            return None

    try:
        qs = (
            EmailMessage.objects
            .select_related('config')
            .order_by('-received_date')[: max(1, min(int(limit), 200))]
        )
        out: list[InboxMail] = []
        for row in qs:
            cfg = getattr(row, 'config', None)
            box = (
                (cfg.name if cfg else None)
                or (cfg.email_address if cfg else None)
                or row.to_email
                or 'Inbox'
            )
            prev = re.sub(r'\s+', ' ', str(row.body_plain or '')).strip()[:180]
            dt = row.received_date
            unread = (row.status or '') == 'NEW'
            out.append(_apply_crm_links(InboxMail(
                id=f'db:{row.pk}',
                subj=str(row.subject or '(ohne Betreff)'),
                from_=str(row.from_email or '—'),
                box=str(box),
                age=_age_label(dt) if isinstance(dt, datetime) else '',
                prev=prev or '—',
                unread=unread,
                received_at=dt.isoformat() if isinstance(dt, datetime) else None,
                account=str(getattr(cfg, 'email_address', None) or box),
            )))
        return out
    except Exception as exc:
        log.warning('EmailMessage-Liste fehlgeschlagen: %s', exc)
        return None


def _filter_by_account(mails: list[InboxMail], account: Optional[str]) -> list[InboxMail]:
    acc = (account or '').strip().lower()
    if not acc:
        return mails
    out = []
    for m in mails:
        keys = {(m.account or '').strip().lower(), (m.box or '').strip().lower()}
        if acc in keys:
            out.append(m)
    return out


def list_mails(
    limit: int = 40,
    *,
    force_imap: bool = False,
    user=None,
    account: Optional[str] = None,
    q: Optional[str] = None,
    has_attachment: Optional[bool] = None,
    sort: str = 'date_desc',
    unread_only: bool = False,
) -> dict[str, Any]:
    """
    Haupt-API für den Posteingang.
    Returns: {ok, source, results, accounts, unread, error?}
    ``user`` → ABpE-Gelesen-Overlay; ``account`` → Postfach-Filter.
    ``q`` / ``has_attachment`` / ``sort`` / ``unread_only`` → Filter.
    """
    filter_account = (account or '').strip()
    q = (q or '').strip() or None

    if not force_imap:
        es_mails = _list_from_elasticsearch(
            limit=limit,
            account=filter_account or None,
            q=q,
            has_attachment=has_attachment,
            sort=sort or 'date_desc',
        )
        if es_mails is not None:
            es_mails = _apply_user_read(es_mails, user)
            if unread_only:
                es_mails = [m for m in es_mails if m.unread]
            hint = None
            if es_mails:
                # Wenn neueste Mail > 14 Tage: Indexierung vermutlich stehengeblieben
                try:
                    newest = es_mails[0].received_at
                    dt = _es_parse_date(newest) if newest else None
                    if dt:
                        now = dj_tz.now()
                        if dj_tz.is_naive(dt):
                            dt = dj_tz.make_aware(dt, timezone.utc)
                        age_days = (now - dt).total_seconds() / 86400
                        if age_days > 14:
                            hint = (
                                f'Neueste indexierte Mail ist ~{int(age_days)} Tage alt — '
                                'Mail-Indexer (automail/ingest) prüfen.'
                            )
                except Exception:
                    pass
            return {
                'ok': True,
                'demo': False,
                'source': 'elasticsearch',
                'index': _es_mail_index(),
                'results': [m.as_dict() for m in es_mails],
                'accounts': _account_chips(es_mails, filter_account=filter_account),
                'filter_account': filter_account,
                'q': q or '',
                'sort': sort or 'date_desc',
                'has_attachment': has_attachment,
                'unread_only': unread_only,
                'unread': sum(1 for m in es_mails if m.unread),
                'hint': hint,
            }

        db_mails = _list_from_ingest_db(limit=limit)
        if db_mails is not None:
            db_mails = _apply_user_read(db_mails, user)
            db_mails = _filter_by_account(db_mails, filter_account)
            if unread_only:
                db_mails = [m for m in db_mails if m.unread]
            if q:
                ql = q.lower()
                db_mails = [
                    m for m in db_mails
                    if ql in (m.subj or '').lower()
                    or ql in (m.from_ or '').lower()
                    or ql in (m.prev or '').lower()
                ]
            return {
                'ok': True,
                'demo': False,
                'source': 'ingest_email_db',
                'results': [m.as_dict() for m in db_mails],
                'accounts': _account_chips(db_mails, filter_account=filter_account),
                'filter_account': filter_account,
                'q': q or '',
                'unread_only': unread_only,
                'unread': sum(1 for m in db_mails if m.unread),
            }

    accounts = get_imap_accounts()
    if not accounts:
        return {
            'ok': False,
            'demo': False,
            'source': 'none',
            'results': [],
            'accounts': [],
            'filter_account': filter_account,
            'unread': 0,
            'error': (
                'Keine Mail-Quelle. Elasticsearch (abpe_emails) nicht erreichbar und '
                'keine IMAP-Accounts. Prüfe ES auf localhost:9200 bzw. settings.json '
                '→ shaduler.imap_accounts (host 172.20.3.150).'
            ),
        }

    all_mails: list[InboxMail] = []
    errors = []
    for acc in accounts:
        if filter_account:
            keys = {
                (acc.user or '').strip().lower(),
                (acc.label or '').strip().lower(),
                (acc.box_label or '').strip().lower(),
            }
            if filter_account.lower() not in keys:
                continue
        try:
            all_mails.extend(_fetch_imap_account(acc, limit=max(5, limit // max(1, len(accounts)))))
        except Exception as exc:
            errors.append(f'{acc.label}: {exc}')

    # neueste zuerst
    def _sort_key(m: InboxMail):
        if m.received_at:
            try:
                return parsedate_to_datetime(m.received_at) if ' ' in m.received_at else datetime.fromisoformat(m.received_at)
            except Exception:
                return datetime.min.replace(tzinfo=timezone.utc)
        return datetime.min.replace(tzinfo=timezone.utc)

    try:
        all_mails.sort(key=_sort_key, reverse=True)
    except Exception:
        pass

    all_mails = _apply_user_read(all_mails, user)
    sliced = all_mails[:limit]
    return {
        'ok': True,
        'demo': False,
        'source': 'imap',
        'results': [m.as_dict() for m in sliced],
        'accounts': _account_chips(sliced, filter_account=filter_account) or [
            {'host': a.host, 'user': a.user, 'folder': a.folder, 'label': a.label, 'count': 0}
            for a in accounts
        ],
        'filter_account': filter_account,
        'unread': sum(1 for m in sliced if m.unread),
        'errors': errors,
    }


def mail_to_aufgabe(mail_id: str, user, *, art: str = 'email') -> dict[str, Any]:
    """Erzeugt Aufgabe aus Mail-ID (es:… / db:… oder user:folder:uid)."""
    from . import aufgaben_service, aktivitaet_service
    from apps.abpe_shaduler.models import Aufgabe

    mail = None
    mid = str(mail_id)
    if mid.startswith('es:'):
        mail = _get_es_mail(mid)
    if mail is None:
        data = list_mails(limit=80, force_imap=not mid.startswith(('db:', 'es:')))
        mail = next((m for m in data.get('results') or [] if m.get('id') == mid), None)
    if not mail:
        mail = {
            'id': mid,
            'subj': f'Mail {mid}',
            'from': '',
            'prev': '',
            'box': 'Mail',
        }

    titel = (mail.get('subj') or 'Mail-Aufgabe')[:200]
    beschreibung = (
        f"Von: {mail.get('from') or '—'}\n"
        f"Postfach: {mail.get('box') or '—'}\n"
        f"Preview: {mail.get('prev') or '—'}\n"
        f"Mail-ID: {mid}"
    )
    aufgabe = aufgaben_service.erstellen(
        art=art or Aufgabe.Art.EMAIL,
        titel=titel,
        zugewiesen_an=user,
        beschreibung=beschreibung,
        ref_type='mail',
        ref_id=str(mid)[:64],
        quelle=Aufgabe.Quelle.MAIL,
        user=user,
    )
    aktivitaet_service.schreiben(
        medium='email',
        titel=f'Aufgabe aus Posteingang: {titel}',
        ref_type='mail',
        ref_id=str(mid)[:64],
        user=user,
        details={'aufgabe_id': str(aufgabe.pk), 'mail': mail},
    )
    try:
        mark_read(mid, user)
    except Exception as exc:
        log.warning('mark_read nach Aufgabe fehlgeschlagen: %s', exc)
    return {
        'ok': True,
        'created': aufgaben_service.serialize(aufgabe),
        'mail_id': mid,
        'unread': False,
    }


def probe() -> dict[str, Any]:
    """Diagnose für manage.py / Live-Check."""
    from django.apps import apps
    models_found = []
    for app in apps.get_app_configs():
        if 'ingest' in app.label.lower() or 'mail' in app.label.lower():
            for m in app.get_models():
                models_found.append(f'{app.label}.{m.__name__}')
    accounts = get_imap_accounts()

    es_info: dict[str, Any] = {
        'hosts': _es_hosts(),
        'index': _es_mail_index(),
        'reachable': False,
        'count': None,
        'newest_date': None,
        'newest_account': None,
        'newest_subject': None,
        'top_accounts': [],
        'error': None,
    }
    try:
        from elasticsearch import Elasticsearch
        es = Elasticsearch(es_info['hosts'])
        es_info['reachable'] = bool(es.ping())
        if es_info['reachable']:
            try:
                es_info['count'] = es.count(index=es_info['index']).get('count')
            except Exception as exc:
                es_info['error'] = f'count: {exc}'
            try:
                sample = es.search(
                    index=es_info['index'],
                    body={
                        'size': 1,
                        'sort': [{'date': {'order': 'desc', 'unmapped_type': 'date'}}],
                        '_source': ['date', 'account', 'subject', 'folder'],
                        'query': {'bool': {'filter': _es_sane_date_filters()}},
                    },
                )
                hits = (sample.get('hits') or {}).get('hits') or []
                if hits:
                    src = hits[0].get('_source') or {}
                    es_info['newest_date'] = src.get('date')
                    es_info['newest_account'] = src.get('account')
                    es_info['newest_subject'] = (src.get('subject') or '')[:80]
                # Anzahl kaputter Future-Dates (Diagnose Indexer)
                try:
                    bad = es.count(
                        index=es_info['index'],
                        body={'query': {'range': {'date': {'gt': '2100-01-01'}}}},
                    ).get('count')
                    es_info['bad_future_dates'] = bad
                except Exception:
                    es_info['bad_future_dates'] = None
            except Exception as exc:
                es_info['error'] = (es_info.get('error') or '') + f' sample: {exc}'
            try:
                agg = es.search(
                    index=es_info['index'],
                    body={
                        'size': 0,
                        'aggs': {'acc': {'terms': {'field': 'account', 'size': 12}}},
                    },
                )
                buckets = (((agg.get('aggregations') or {}).get('acc') or {}).get('buckets')) or []
                es_info['top_accounts'] = [
                    {'account': b.get('key'), 'count': b.get('doc_count')} for b in buckets
                ]
            except Exception:
                # account ggf. text ohne keyword — ignorieren
                pass
        else:
            es_info['error'] = 'ping failed'
    except Exception as exc:
        es_info['error'] = str(exc)[:200]

    cfg_info: dict[str, Any] = {'active': 0, 'total': 0, 'error': None}
    msg_info: dict[str, Any] = {'total': 0, 'new': 0, 'error': None}
    try:
        from apps.ingest_email.models import EmailImportConfig, EmailMessage
        cfg_info['total'] = EmailImportConfig.objects.count()
        cfg_info['active'] = EmailImportConfig.objects.filter(is_active=True).count()
        msg_info['total'] = EmailMessage.objects.count()
        msg_info['new'] = EmailMessage.objects.filter(status='NEW').count()
    except Exception as exc:
        cfg_info['error'] = str(exc)[:200]
        msg_info['error'] = str(exc)[:200]

    return {
        'ok': True,
        'elasticsearch': es_info,
        'email_import_config': cfg_info,
        'email_message': msg_info,
        'ingest_related_models': models_found[:40],
        'accounts': [
            {
                'host': a.host, 'port': a.port, 'user': a.user, 'folder': a.folder,
                'ssl': a.ssl, 'label': a.label, 'has_password': bool(a.password),
                'source': (a.extra or {}).get('model') or 'fallback',
                'email_address': (a.extra or {}).get('email_address') or '',
            }
            for a in accounts
        ],
        'default_host_hint': '172.20.3.150',
        'source_order': [
            'elasticsearch:abpe_emails',
            'ingest_email.EmailMessage',
            'imap:EmailImportConfig',
        ],
    }


def ping():
    return True
