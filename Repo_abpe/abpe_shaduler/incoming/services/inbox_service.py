"""
inbox_service — Posteingang read-only (Architektur Kap. 1 / 6).

Quellen (Reihenfolge):
  1) Elasticsearch-Index ``abpe_emails`` (von ingest/automail bereits indexiert)
  2) ingest_email-DB (EmailMessage), falls App vorhanden
  3) Direkt-IMAP laut Settings / settings.json (Host z.B. 172.20.3.150)

Kein Löschen/Verschieben — nur Header + kurzer Preview.
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
    """Versucht typische ingest_email-Modelle zu finden."""
    try:
        from django.apps import apps
    except Exception:
        return []

    candidates = [
        ('ingest_email', 'MailAccount'),
        ('ingest_email', 'EmailAccount'),
        ('ingest_email', 'ImapAccount'),
        ('ingest_email', 'Mailbox'),
        ('abpe_ingest_email', 'MailAccount'),
        ('abpe_ingest_email', 'EmailAccount'),
    ]
    model = None
    for app_label, model_name in candidates:
        try:
            model = apps.get_model(app_label, model_name)
            if model is not None:
                break
        except Exception:
            continue
    if model is None:
        return []

    out = []
    try:
        qs = model.objects.all()
        # aktive filtern falls Feld existiert
        if hasattr(model, 'aktiv'):
            qs = qs.filter(aktiv=True)
        elif hasattr(model, 'active'):
            qs = qs.filter(active=True)
        elif hasattr(model, 'is_active'):
            qs = qs.filter(is_active=True)
        for row in qs[:20]:
            host = (
                getattr(row, 'imap_host', None)
                or getattr(row, 'host', None)
                or getattr(row, 'server', None)
                or '172.20.3.150'
            )
            user = (
                getattr(row, 'username', None)
                or getattr(row, 'user', None)
                or getattr(row, 'email', None)
                or ''
            )
            password = (
                getattr(row, 'password', None)
                or getattr(row, 'imap_password', None)
                or getattr(row, 'secret', None)
                or ''
            )
            port = getattr(row, 'imap_port', None) or getattr(row, 'port', None) or 993
            folder = getattr(row, 'folder', None) or getattr(row, 'mailbox', None) or 'INBOX'
            ssl = getattr(row, 'use_ssl', None)
            if ssl is None:
                ssl = getattr(row, 'ssl', True)
            label = (
                getattr(row, 'name', None)
                or getattr(row, 'label', None)
                or str(user)
            )
            if not user:
                continue
            out.append(ImapAccount(
                host=str(host),
                port=int(port),
                user=str(user),
                password=str(password or ''),
                folder=str(folder),
                ssl=bool(ssl),
                box_label=str(label),
                extra={'pk': str(getattr(row, 'pk', ''))},
            ))
    except Exception as exc:
        log.warning('ingest_email Accounts nicht lesbar: %s', exc)
    return out


def get_imap_accounts() -> list[ImapAccount]:
    for loader in (_accounts_from_django_settings, _accounts_from_settings_json, _accounts_from_ingest_email):
        acc = loader()
        if acc:
            return acc
    # Fallback: Host bekannt, Credentials fehlen → leere Liste (Probe zeigt Hinweis)
    return []


def _decode_header(val: Optional[str]) -> str:
    if not val:
        return ''
    parts = email.header.decode_header(val)
    out = []
    for chunk, enc in parts:
        if isinstance(chunk, bytes):
            out.append(chunk.decode(enc or 'utf-8', errors='replace'))
        else:
            out.append(str(chunk))
    return ' '.join(out).strip()


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


def _crm_hint_for_email(addr: str) -> str:
    """Optional: SuiteCRM-Zuordnung über abpe_crm Spiegel."""
    if not addr or '@' not in addr:
        return '—'
    email_addr = addr.strip().lower()
    # From: Name <mail@x>
    m = re.search(r'<([^>]+)>', email_addr)
    if m:
        email_addr = m.group(1).strip().lower()
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
            return '—'
        row = EmailAddr.objects.filter(email_address__iexact=email_addr).first()
        if not row:
            # Feldvarianten
            for field in ('email', 'address'):
                if hasattr(EmailAddr, field):
                    row = EmailAddr.objects.filter(**{f'{field}__iexact': email_addr}).first()
                    if row:
                        break
        if not row:
            return '—'
        # Bean-Rel falls vorhanden
        try:
            Rel = apps.get_model('abpe_crm', 'CrmEmailAddrBeanRel')
            link = Rel.objects.filter(email_address_id=row.pk).first() or Rel.objects.filter(
                **{'email_address__email_address__iexact': email_addr}
            ).first()
            if link:
                bean = getattr(link, 'bean_module', '') or getattr(link, 'bean_type', '')
                bean_id = getattr(link, 'bean_id', '') or ''
                return f'{bean} {str(bean_id)[:8]}'.strip() or 'CRM'
        except Exception:
            pass
        return 'CRM'
    except Exception:
        return '—'


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
            mails.append(InboxMail(
                id=mid,
                subj=subj or '(ohne Betreff)',
                from_=from_ or '—',
                box=acc.label,
                age=_age_label(dt),
                prev=prev or '—',
                unread=unread,
                crm=_crm_hint_for_email(from_),
                received_at=dt.isoformat() if dt else None,
                account=acc.user,
            ))
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


def _es_inbox_query() -> dict[str, Any]:
    """Optional: Account-/Folder-Filter aus settings.json → shaduler.es_mail."""
    cfg = _load_json_settings()
    sh = (cfg.get('shaduler') or {}).get('es_mail') or {}
    accounts = sh.get('accounts') or getattr(settings, 'SHADULER_ES_ACCOUNTS', None) or []
    folder = sh.get('folder')
    if folder is None:
        folder = getattr(settings, 'SHADULER_ES_FOLDER', 'INBOX')

    filters: list[dict] = []
    if accounts:
        if isinstance(accounts, str):
            accounts = [accounts]
        filters.append({'terms': {'account': list(accounts)}})
    if folder:
        # folder ist je nach Mapping keyword oder text — beides versuchen
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
    if filters:
        return {'bool': {'filter': filters}}
    return {'match_all': {}}


def _es_preview(src: dict) -> str:
    body = src.get('body') or src.get('snippet') or src.get('preview') or ''
    text = re.sub(r'\s+', ' ', str(body)).strip()
    return text[:180] if text else '—'


def _es_unread(src: dict) -> bool:
    if 'unread' in src:
        return bool(src.get('unread'))
    if 'seen' in src:
        return not bool(src.get('seen'))
    if 'is_read' in src:
        return not bool(src.get('is_read'))
    flags = str(src.get('flags') or src.get('flag') or '').lower()
    if flags:
        return 'seen' not in flags and '\\seen' not in flags
    return True


def _es_parse_date(raw) -> Optional[datetime]:
    if raw is None or raw == '':
        return None
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(float(raw) / (1000 if raw > 1e12 else 1), tz=timezone.utc)
        except Exception:
            return None
    s = str(raw).strip()
    dt = parse_datetime(s)
    if dt:
        return dt
    try:
        return parsedate_to_datetime(s)
    except Exception:
        return None


def _hit_to_mail(hit: dict) -> InboxMail:
    src = hit.get('_source') or {}
    es_id = hit.get('_id') or ''
    subj = src.get('subject') or '(ohne Betreff)'
    from_ = src.get('from_addr') or src.get('from') or '—'
    account = src.get('account') or ''
    folder = src.get('folder') or 'INBOX'
    box = account or folder
    dt = _es_parse_date(src.get('date') or src.get('received_at'))
    return InboxMail(
        id=f'es:{es_id}',
        subj=str(subj),
        from_=str(from_),
        box=str(box),
        age=_age_label(dt) if dt else '',
        prev=_es_preview(src),
        unread=_es_unread(src),
        crm=_crm_hint_for_email(str(from_)),
        received_at=dt.isoformat() if dt else (str(src.get('date') or '') or None),
        account=str(account),
    )


def _list_from_elasticsearch(limit: int = 40) -> Optional[list[InboxMail]]:
    """Liest den bereits indexierten Mail-Index ``abpe_emails`` (read-only)."""
    try:
        from elasticsearch import Elasticsearch
    except ImportError:
        log.info('elasticsearch-Paket nicht installiert — Skip ES-Quelle')
        return None

    hosts = _es_hosts()
    index = _es_mail_index()
    body = {
        'size': max(1, min(int(limit), 200)),
        'query': _es_inbox_query(),
        'sort': [{'date': {'order': 'desc'}}],
        '_source': [
            'subject', 'from_addr', 'to_addr', 'date', 'folder', 'account',
            'message_id', 'uid', 'has_attachments', 'body', 'snippet', 'preview',
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
    # Wenn Folder-Filter nichts liefert: ohne Folder nochmal (Accounts behalten)
    if not hits:
        cfg = _load_json_settings()
        sh = (cfg.get('shaduler') or {}).get('es_mail') or {}
        folder = sh.get('folder', getattr(settings, 'SHADULER_ES_FOLDER', 'INBOX'))
        if folder:
            try:
                body2 = dict(body)
                body2['query'] = {'match_all': {}}
                accounts = sh.get('accounts') or []
                if accounts:
                    if isinstance(accounts, str):
                        accounts = [accounts]
                    body2['query'] = {'bool': {'filter': [{'terms': {'account': list(accounts)}}]}}
                res2 = es.search(index=index, body=body2)
                hits = (res2.get('hits') or {}).get('hits') or []
            except Exception as exc:
                log.warning('ES Fallback match_all fehlgeschlagen: %s', exc)

    return [_hit_to_mail(h) for h in hits]


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
    """Liest bereits ingestete Mails aus der DB, wenn Modell existiert."""
    try:
        from django.apps import apps
    except Exception:
        return None

    model = None
    for app_label, model_name in (
        ('ingest_email', 'EmailMessage'),
        ('ingest_email', 'IngestedEmail'),
        ('ingest_email', 'MailMessage'),
        ('abpe_ingest_email', 'EmailMessage'),
    ):
        try:
            model = apps.get_model(app_label, model_name)
            break
        except Exception:
            continue
    if model is None:
        return None

    try:
        qs = model.objects.all()
        # Sortierung
        for order in ('-received_at', '-date', '-created_at', '-id'):
            field = order.lstrip('-')
            if hasattr(model, field):
                qs = qs.order_by(order)
                break
        rows = list(qs[:limit])
        out: list[InboxMail] = []
        for row in rows:
            subj = getattr(row, 'subject', None) or getattr(row, 'betreff', None) or '(ohne Betreff)'
            from_ = getattr(row, 'from_address', None) or getattr(row, 'sender', None) or getattr(row, 'from_email', None) or '—'
            box = getattr(row, 'mailbox', None) or getattr(row, 'account_name', None) or 'Inbox'
            prev = getattr(row, 'preview', None) or getattr(row, 'snippet', None) or getattr(row, 'body_preview', None) or ''
            if not prev:
                body = getattr(row, 'body_text', None) or getattr(row, 'text', None) or ''
                prev = re.sub(r'\s+', ' ', str(body)).strip()[:180]
            unread = getattr(row, 'is_unread', None)
            if unread is None:
                unread = not bool(getattr(row, 'is_read', False))
            dt = getattr(row, 'received_at', None) or getattr(row, 'date', None) or getattr(row, 'created_at', None)
            if isinstance(dt, str):
                dt = parse_datetime(dt)
            out.append(InboxMail(
                id=f'db:{row.pk}',
                subj=str(subj),
                from_=str(from_),
                box=str(box),
                age=_age_label(dt) if isinstance(dt, datetime) else '',
                prev=str(prev) or '—',
                unread=bool(unread),
                crm=_crm_hint_for_email(str(from_)),
                received_at=dt.isoformat() if isinstance(dt, datetime) else None,
                account=str(box),
            ))
        return out
    except Exception as exc:
        log.warning('ingest_email DB-Liste fehlgeschlagen: %s', exc)
        return None


def list_mails(limit: int = 40, *, force_imap: bool = False) -> dict[str, Any]:
    """
    Haupt-API für den Posteingang.
    Returns: {ok, source, results, accounts, error?}
    """
    if not force_imap:
        es_mails = _list_from_elasticsearch(limit=limit)
        if es_mails is not None:
            # leere Liste zählt als Erfolg (Index erreichbar, nur keine Treffer)
            boxes: dict[str, int] = {}
            for m in es_mails:
                boxes[m.box or m.account or '?'] = boxes.get(m.box or m.account or '?', 0) + 1
            return {
                'ok': True,
                'demo': False,
                'source': 'elasticsearch',
                'index': _es_mail_index(),
                'results': [m.as_dict() for m in es_mails],
                'accounts': [{'label': k, 'count': v} for k, v in boxes.items()],
                'unread': sum(1 for m in es_mails if m.unread),
            }

        db_mails = _list_from_ingest_db(limit=limit)
        if db_mails is not None:
            return {
                'ok': True,
                'demo': False,
                'source': 'ingest_email_db',
                'results': [m.as_dict() for m in db_mails],
                'accounts': [],
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

    return {
        'ok': True,
        'demo': False,
        'source': 'imap',
        'results': [m.as_dict() for m in all_mails[:limit]],
        'accounts': [{'host': a.host, 'user': a.user, 'folder': a.folder, 'label': a.label} for a in accounts],
        'unread': sum(1 for m in all_mails if m.unread),
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
    return {
        'ok': True,
        'created': aufgaben_service.serialize(aufgabe),
        'mail_id': mid,
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
        else:
            es_info['error'] = 'ping failed'
    except Exception as exc:
        es_info['error'] = str(exc)[:200]

    return {
        'ok': True,
        'elasticsearch': es_info,
        'ingest_related_models': models_found[:40],
        'accounts': [
            {'host': a.host, 'port': a.port, 'user': a.user, 'folder': a.folder,
             'ssl': a.ssl, 'label': a.label, 'has_password': bool(a.password)}
            for a in accounts
        ],
        'default_host_hint': '172.20.3.150',
        'source_order': ['elasticsearch:abpe_emails', 'ingest_email_db', 'imap'],
    }


def ping():
    return True
