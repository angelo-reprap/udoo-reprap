"""
Management Command: E-Mails von Zimbra IMAP in Elasticsearch indizieren
Usage: python manage.py index_emails
       python manage.py index_emails --account vertrieb
       python manage.py index_emails --reset
"""
import imaplib
import email
import email.header
import hashlib
import json
import logging
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

from django.core.management.base import BaseCommand
from elasticsearch import helpers

logger = logging.getLogger(__name__)

SETTINGS_FILE = Path(__file__).parent / 'email_settings.json'

def load_settings():
    with open(SETTINGS_FILE) as f:
        return json.load(f)

def decode_header(value):
    if not value:
        return ''
    try:
        parts = email.header.decode_header(value)
        result = []
        for part, charset in parts:
            if isinstance(part, bytes):
                result.append(part.decode(charset or 'utf-8', errors='replace'))
            else:
                result.append(str(part))
        return ' '.join(result)
    except:
        return str(value)

def get_body(msg, max_len=10000):
    body = ''
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == 'text/plain':
                try:
                    body += part.get_payload(decode=True).decode(
                        part.get_content_charset() or 'utf-8', errors='replace')
                except:
                    pass
    else:
        try:
            body = msg.get_payload(decode=True).decode(
                msg.get_content_charset() or 'utf-8', errors='replace')
        except:
            pass
    return body[:max_len]

def has_attachments(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_disposition() == 'attachment':
                return True
    return False

def fetch_folder(account, password, folder, es, cfg):
    indexed = 0
    errors  = 0
    es_index   = cfg['indexing']['es_index']
    batch_size = cfg['indexing']['batch_size']
    max_body   = cfg['indexing']['max_body_length']
    host       = cfg['imap']['host']
    port       = cfg['imap']['port']

    try:
        m = imaplib.IMAP4_SSL(host, port)
        m.login(account, password)
        r, data = m.select(f'"{folder}"', readonly=True)
        if r != 'OK':
            m.logout()
            return 0, 0
        total = int(data[0].decode())
        if total == 0:
            m.logout()
            return 0, 0

        r, data = m.search(None, 'ALL')
        if r != 'OK':
            m.logout()
            return 0, 0

        uids = data[0].split()
        docs = []

        for uid in uids:
            try:
                r, data = m.fetch(uid, '(RFC822)')
                if r != 'OK' or not data[0]:
                    continue
                raw = data[0][1]
                msg = email.message_from_bytes(raw)

                subject  = decode_header(msg.get('Subject', ''))
                from_    = decode_header(msg.get('From', ''))
                to_      = decode_header(msg.get('To', ''))
                date_str = msg.get('Date', '')
                msg_id   = msg.get('Message-ID', '') or hashlib.md5(raw[:200]).hexdigest()

                try:
                    date = parsedate_to_datetime(date_str).isoformat() if date_str else None
                except:
                    date = None

                body   = get_body(msg, max_body)
                doc_id = hashlib.md5(f"{account}{folder}{msg_id}".encode()).hexdigest()

                docs.append({
                    '_index': es_index,
                    '_id':    doc_id,
                    '_source': {
                        'account':         account,
                        'folder':          folder,
                        'message_id':      msg_id,
                        'subject':         subject,
                        'from_addr':       from_,
                        'to_addr':         to_,
                        'date':            date,
                        'body':            body,
                        'has_attachments': has_attachments(msg),
                        'size_bytes':      size_bytes,
                        'indexed_at':      datetime.utcnow().isoformat(),
                        'uid':             uid.decode() if isinstance(uid, bytes) else str(uid),
                    }
                })

                if len(docs) >= batch_size:
                    ok, _ = helpers.bulk(es, docs, raise_on_error=False)
                    indexed += ok
                    docs = []

            except Exception as e:
                errors += 1
                continue

        if docs:
            ok, _ = helpers.bulk(es, docs, raise_on_error=False)
            indexed += ok

        m.logout()
    except Exception as e:
        logger.error(f"{account}/{folder}: {e}")

    return indexed, errors


class Command(BaseCommand):
    help = 'E-Mails von Zimbra IMAP in Elasticsearch indizieren'

    def add_arguments(self, parser):
        parser.add_argument('--account', type=str, default=None)
        parser.add_argument('--reset',   action='store_true')

    def handle(self, *args, **options):
        from apps.abpe_search.services.search_service import get_es_client
        es  = get_es_client()
        cfg = load_settings()

        es_index   = cfg['indexing']['es_index']
        host       = cfg['imap']['host']
        port       = cfg['imap']['port']

        ES_MAPPING = {
            'mappings': {
                'properties': {
                    'account':         {'type': 'keyword'},
                    'folder':          {'type': 'keyword'},
                    'message_id':      {'type': 'keyword'},
                    'subject':         {'type': 'text', 'analyzer': 'german'},
                    'from_addr':       {'type': 'keyword'},
                    'to_addr':         {'type': 'text'},
                    'date':            {'type': 'date'},
                    'body':            {'type': 'text', 'analyzer': 'german'},
                    'has_attachments': {'type': 'boolean'},
                    'size_bytes':      {'type': 'long'},
                    'indexed_at':      {'type': 'date'},
                }
            },
            'settings': {
                'number_of_shards':   1,
                'number_of_replicas': 0,
            }
        }

        if options['reset'] and es.indices.exists(index=es_index):
            es.indices.delete(index=es_index)
            self.stdout.write('✓ Index gelöscht')

        if not es.indices.exists(index=es_index):
            es.indices.create(index=es_index, body=ES_MAPPING)
            self.stdout.write(f'✓ Index {es_index} angelegt')

        # Accounts aus JSON — gefiltert nach enabled + optional --account
        accounts = {
            user: data
            for user, data in cfg['accounts'].items()
            if data.get('enabled', False)
            and data.get('password', '')
            and (options['account'] is None or user == options['account'])
        }

        if not accounts:
            self.stdout.write('❌ Keine aktiven Accounts gefunden')
            return

        total_indexed = 0
        start = datetime.now()

        for account, data in accounts.items():
            password    = data['password']
            description = data.get('description', account)
            self.stdout.write(f'\n📬 {account} ({description})...')

            try:
                m = imaplib.IMAP4_SSL(host, port)
                m.login(account, password)
                r, folders = m.list()
                m.logout()
            except Exception as e:
                self.stdout.write(f'  ❌ Login fehler: {e}')
                continue

            for f in folders:
                try:
                    parts = f.decode()
                    fname = parts.split('"')[-2] if '"' in parts else parts.split()[-1]
                except:
                    continue

                indexed, errors = fetch_folder(account, password, fname, es, cfg)
                if indexed > 0:
                    self.stdout.write(f'  ✓ {fname}: {indexed} indiziert')
                    total_indexed += indexed

        elapsed = (datetime.now() - start).seconds
        self.stdout.write(f'\n✅ Fertig: {total_indexed} E-Mails in {elapsed}s')
