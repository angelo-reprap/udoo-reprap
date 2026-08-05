"""
Management Command: E-Mails von Zimbra IMAP in Elasticsearch indizieren.

Usage:
  python manage.py index_emails
  python manage.py index_emails --account vertrieb
  python manage.py index_emails --since-days 14
  python manage.py index_emails --all-folders --since-days 90
  python manage.py index_emails --reset   # Index löschen + neu anlegen (Achtung!)
  python manage.py index_emails --account angelo --prune-orphans
      # gelöschte INBOX-Mails aus ES entfernen (volle Ordner-Abgleich)

Hinweis: email_settings.json liegt neben diesem Command auf Live und enthält
Passwörter — Repo-Kopie ist redacted; SYNC darf sie NICHT überschreiben.

Löschen: Standard-Lauf prune't nur im since-days-Fenster. Für Outlook-Löschungen
älterer Mails einmal ``--prune-orphans`` (oder ``--since-days 0``) laufen lassen.
"""
from __future__ import annotations

import email
import email.header
import hashlib
import imaplib
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Optional

from django.core.management.base import BaseCommand
from elasticsearch import helpers

logger = logging.getLogger(__name__)

SETTINGS_FILE = Path(__file__).parent / 'email_settings.json'


def load_settings():
    with open(SETTINGS_FILE, encoding='utf-8') as f:
        return json.load(f)


def make_doc_id(account: str, folder: str, msg_id: str) -> str:
    return hashlib.md5(f'{account}{folder}{msg_id}'.encode()).hexdigest()


def decode_bytes(data: bytes, charset: str | None = None) -> str:
    """Strict charset cascade — kein errors=replace (sonst `` statt Umlaute)."""
    if not data:
        return ''
    candidates: list[str] = []
    if charset:
        cs = charset.strip().lower().replace('"', '')
        # häufige Aliase
        aliases = {
            'unknown-8bit': 'utf-8',
            'x-unknown': 'utf-8',
            'default': 'utf-8',
            'utf8': 'utf-8',
            'iso8859-1': 'latin-1',
            'iso-8859-1': 'latin-1',
            'windows-1252': 'cp1252',
        }
        candidates.append(aliases.get(cs, cs))
    for cs in ('utf-8', 'cp1252', 'latin-1'):
        if cs not in candidates:
            candidates.append(cs)
    for cs in candidates:
        try:
            return data.decode(cs)  # strict
        except (LookupError, UnicodeDecodeError):
            continue
    # letzter Fallback: utf-8 replace nur wenn alles scheitert
    return data.decode('utf-8', errors='replace')


def decode_header(value):
    if not value:
        return ''
    try:
        parts = email.header.decode_header(value)
        result = []
        for part, charset in parts:
            if isinstance(part, bytes):
                result.append(decode_bytes(part, charset))
            else:
                result.append(str(part))
        return ''.join(result).strip()
    except Exception:
        return str(value or '').strip()


def get_body(msg, max_len=10000):
    body = ''
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == 'text/plain':
                try:
                    payload = part.get_payload(decode=True) or b''
                    body += decode_bytes(payload, part.get_content_charset())
                except Exception:
                    pass
            elif part.get_content_type() == 'text/html' and not body:
                try:
                    payload = part.get_payload(decode=True) or b''
                    body += decode_bytes(payload, part.get_content_charset())
                except Exception:
                    pass
    else:
        try:
            payload = msg.get_payload(decode=True) or b''
            body = decode_bytes(payload, msg.get_content_charset())
        except Exception:
            pass
    return body[:max_len]


def has_attachments(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_disposition() == 'attachment':
                return True
    return False


def sane_date_iso(raw: Any) -> Optional[str]:
    """
    Nur plausible Mail-Daten (2000–2100). Verhindert Index-Müll wie 4501-01-01,
    der sort=date:desc kaputt macht.
    """
    if raw is None or raw == '':
        return None
    dt: Optional[datetime] = None
    if isinstance(raw, datetime):
        dt = raw
    else:
        s = str(raw).strip()
        if not s:
            return None
        try:
            dt = parsedate_to_datetime(s)
        except Exception:
            try:
                # IMAP INTERNALDATE: 03-Jun-2026 12:00:00 +0200
                dt = datetime.strptime(s, '%d-%b-%Y %H:%M:%S %z')
            except Exception:
                return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if dt.year < 2000 or dt.year > 2100:
        logger.warning('skip insane date year=%s raw=%r', dt.year, raw)
        return None
    return dt.isoformat()


def _parse_internaldate(meta: bytes) -> Optional[str]:
    """Extrahiert INTERNALDATE aus IMAP FETCH-Metadaten."""
    try:
        text = meta.decode('utf-8', errors='replace') if isinstance(meta, bytes) else str(meta)
        m = re.search(r'INTERNALDATE "([^"]+)"', text)
        if m:
            return sane_date_iso(m.group(1))
    except Exception:
        pass
    return None


def prune_missing_from_es(
    es,
    es_index: str,
    account: str,
    folder: str,
    live_doc_ids: set[str],
    *,
    since_days: Optional[int] = None,
) -> int:
    """
    Löscht ES-Docs für account+folder, die nicht mehr in ``live_doc_ids`` sind.
    Mit since_days nur Docs im gleichen Datumsfenster (sicher bei Teil-Index).
    """
    filters: list[dict] = [
        {'term': {'account': account}},
    ]
    # Ordner-Varianten (INBOX/Inbox)
    if folder.upper() == 'INBOX':
        filters.append({
            'bool': {
                'should': [
                    {'term': {'folder': 'INBOX'}},
                    {'term': {'folder': 'Inbox'}},
                ],
                'minimum_should_match': 1,
            }
        })
    else:
        filters.append({'term': {'folder': folder}})
    if since_days and since_days > 0:
        since = (datetime.now(timezone.utc) - timedelta(days=int(since_days))).strftime('%Y-%m-%d')
        filters.append({'range': {'date': {'gte': since}}})

    query = {'bool': {'filter': filters}}
    to_delete: list[dict] = []
    try:
        for hit in helpers.scan(
            es,
            index=es_index,
            query={'query': query},
            _source=False,
            size=500,
        ):
            hid = hit.get('_id')
            if hid and hid not in live_doc_ids:
                to_delete.append({
                    '_op_type': 'delete',
                    '_index': es_index,
                    '_id': hid,
                })
    except Exception as exc:
        logger.warning('prune scan %s/%s: %s', account, folder, exc)
        return 0

    if not to_delete:
        return 0
    deleted = 0
    try:
        for i in range(0, len(to_delete), 500):
            ok, _ = helpers.bulk(es, to_delete[i:i + 500], raise_on_error=False)
            deleted += ok
    except Exception as exc:
        logger.warning('prune bulk %s/%s: %s', account, folder, exc)
    return deleted


def collect_live_doc_ids_headers(
    account: str,
    password: str,
    folder: str,
    cfg: dict,
) -> set[str]:
    """Alle Message-IDs im Ordner (nur Header) → doc_ids. Für --prune-orphans."""
    host = cfg['imap']['host']
    port = cfg['imap']['port']
    live: set[str] = set()
    try:
        m = imaplib.IMAP4_SSL(host, port)
        m.login(account, password)
        r, _ = m.select(f'"{folder}"', readonly=True)
        if r != 'OK':
            m.logout()
            return live
        r, data = m.search(None, 'ALL')
        if r != 'OK' or not data or not data[0]:
            m.logout()
            return live
        seqs = data[0].split()
        for seq in seqs:
            try:
                r, data = m.fetch(seq, '(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])')
                if r != 'OK' or not data or not data[0]:
                    continue
                raw = data[0][1] if isinstance(data[0], tuple) else None
                if not isinstance(raw, (bytes, bytearray)):
                    continue
                msg = email.message_from_bytes(raw)
                msg_id = (msg.get('Message-ID') or '').strip()
                if not msg_id:
                    # ohne Message-ID: gleicher Fallback wie beim Index (Hash Header-Bytes)
                    msg_id = hashlib.md5(raw[:200]).hexdigest()
                live.add(make_doc_id(account, folder, msg_id))
            except Exception:
                continue
        m.logout()
    except Exception as exc:
        logger.error('collect_live_doc_ids %s/%s: %s', account, folder, exc)
    return live


def existing_es_ids(es, es_index: str, doc_ids: list[str]) -> set[str]:
    """Welche doc_ids existieren bereits in ES (mget, chunks)."""
    found: set[str] = set()
    if not doc_ids:
        return found
    for i in range(0, len(doc_ids), 500):
        chunk = doc_ids[i:i + 500]
        try:
            # ES 7 body=… / ES 8 ids=…
            try:
                resp = es.mget(index=es_index, ids=chunk, _source=False)
            except TypeError:
                resp = es.mget(index=es_index, body={'ids': chunk}, _source=False)
            for doc in resp.get('docs') or []:
                if doc.get('found') and doc.get('_id'):
                    found.add(doc['_id'])
        except Exception as exc:
            logger.warning('mget %s: %s', es_index, exc)
    return found


def fetch_folder(
    account,
    password,
    folder,
    es,
    cfg,
    *,
    since_days: Optional[int] = None,
    prune: bool = True,
    incremental: bool = False,
):
    indexed = 0
    errors = 0
    skipped_bad_date = 0
    skipped_existing = 0
    pruned = 0
    es_index = cfg['indexing']['es_index']
    batch_size = cfg['indexing']['batch_size']
    max_body = cfg['indexing']['max_body_length']
    host = cfg['imap']['host']
    port = cfg['imap']['port']
    live_doc_ids: set[str] = set()

    try:
        m = imaplib.IMAP4_SSL(host, port)
        m.login(account, password)
        r, data = m.select(f'"{folder}"', readonly=True)
        if r != 'OK':
            m.logout()
            return 0, 0, 0, 0

        if since_days and since_days > 0:
            since = (datetime.now(timezone.utc) - timedelta(days=int(since_days))).strftime('%d-%b-%Y')
            r, data = m.search(None, f'(SINCE {since})')
        else:
            r, data = m.search(None, 'ALL')
        if r != 'OK' or not data or not data[0]:
            # leerer Ordner / keine Treffer im Fenster → ggf. alles im Fenster prune'n
            m.logout()
            if prune:
                pruned = prune_missing_from_es(
                    es, es_index, account, folder, set(), since_days=since_days,
                )
            return 0, 0, 0, pruned

        seqs = data[0].split()
        docs = []
        first_errors: list[str] = []

        # Inkrementell: Message-IDs zuerst, schon indizierte überspringen (1‑Min-Takt)
        need_full: list = list(seqs)
        if incremental and seqs:
            seq_to_doc: dict = {}
            for seq in seqs:
                try:
                    r, data = m.fetch(seq, '(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])')
                    if r != 'OK' or not data or not data[0]:
                        continue
                    raw_h = data[0][1] if isinstance(data[0], tuple) else None
                    if not isinstance(raw_h, (bytes, bytearray)):
                        continue
                    msg_h = email.message_from_bytes(raw_h)
                    msg_id = (msg_h.get('Message-ID') or '').strip()
                    if not msg_id:
                        msg_id = hashlib.md5(raw_h[:200]).hexdigest()
                    doc_id = make_doc_id(account, folder, msg_id)
                    seq_to_doc[seq] = doc_id
                    live_doc_ids.add(doc_id)
                except Exception as e:
                    errors += 1
                    if len(first_errors) < 5:
                        first_errors.append(f'hdr:{e}'[:160])
            already = existing_es_ids(es, es_index, list(seq_to_doc.values()))
            need_full = [s for s, did in seq_to_doc.items() if did not in already]
            skipped_existing = len(seq_to_doc) - len(need_full)
            for seq in seqs:
                if seq not in seq_to_doc:
                    need_full.append(seq)

        for seq in need_full:
            try:
                r, data = m.fetch(seq, '(RFC822 INTERNALDATE)')
                if r != 'OK' or not data or not data[0]:
                    continue
                # data[0] = (b'… INTERNALDATE "…" RFC822 {n}', raw_bytes)
                meta = data[0][0] if isinstance(data[0], tuple) else b''
                raw = data[0][1] if isinstance(data[0], tuple) else None
                if not isinstance(raw, (bytes, bytearray)):
                    continue

                msg = email.message_from_bytes(raw)
                subject = decode_header(msg.get('Subject', ''))
                from_ = decode_header(msg.get('From', ''))
                to_ = decode_header(msg.get('To', ''))
                date_str = msg.get('Date', '')
                msg_id = msg.get('Message-ID', '') or hashlib.md5(raw[:200]).hexdigest()

                date = sane_date_iso(date_str) or _parse_internaldate(meta)
                if date is None:
                    skipped_bad_date += 1

                body = get_body(msg, max_body)
                size_bytes = len(raw)
                doc_id = make_doc_id(account, folder, msg_id)
                live_doc_ids.add(doc_id)

                docs.append({
                    '_index': es_index,
                    '_id': doc_id,
                    '_source': {
                        'account': account,
                        'folder': folder,
                        'message_id': msg_id,
                        'subject': subject,
                        'from_addr': from_,
                        'to_addr': to_,
                        'date': date,
                        'body': body,
                        'has_attachments': has_attachments(msg),
                        'size_bytes': size_bytes,
                        'indexed_at': datetime.now(timezone.utc).isoformat(),
                        'uid': seq.decode() if isinstance(seq, bytes) else str(seq),
                    },
                })

                if len(docs) >= batch_size:
                    ok, _ = helpers.bulk(es, docs, raise_on_error=False)
                    indexed += ok
                    docs = []

            except Exception as e:
                errors += 1
                if len(first_errors) < 5:
                    first_errors.append(str(e)[:160])
                continue

        if docs:
            ok, _ = helpers.bulk(es, docs, raise_on_error=False)
            indexed += ok

        m.logout()
        for err in first_errors:
            logger.warning('%s/%s sample error: %s', account, folder, err)
        if skipped_existing:
            logger.info(
                '%s/%s incremental: skipped_existing=%s new=%s',
                account, folder, skipped_existing, indexed,
            )

        if prune:
            # since_days=0 / None → voller Ordner-Abgleich (live_doc_ids = komplette Suche)
            # Inkrementell: live_doc_ids enthält alle Message-IDs aus dem Fenster.
            pruned = prune_missing_from_es(
                es, es_index, account, folder, live_doc_ids,
                since_days=since_days if (since_days and since_days > 0) else None,
            )
    except Exception as e:
        logger.error('%s/%s: %s', account, folder, e)

    return indexed, errors, skipped_bad_date, pruned


def _folder_name(raw_line: bytes) -> Optional[str]:
    try:
        parts = raw_line.decode()
        if '"' in parts:
            return parts.split('"')[-2]
        return parts.split()[-1]
    except Exception:
        return None


class Command(BaseCommand):
    help = 'E-Mails von Zimbra IMAP in Elasticsearch indizieren (+ optionales Prune gelöschter)'

    def add_arguments(self, parser):
        parser.add_argument('--account', type=str, default=None,
                            help='Nur dieses Konto (z.B. vertrieb)')
        parser.add_argument('--reset', action='store_true',
                            help='Index löschen und neu anlegen')
        parser.add_argument('--since-days', type=int, default=14,
                            help='Nur Mails der letzten N Tage (0=alle). Default 14.')
        parser.add_argument('--all-folders', action='store_true',
                            help='Alle Ordner (sonst nur INBOX)')
        parser.add_argument('--folders', type=str, default='INBOX',
                            help='Kommagetrennte Ordnerliste (Default INBOX)')
        parser.add_argument('--no-prune', action='store_true',
                            help='Keine ES-Löschung fehlender Mails im Index-Fenster')
        parser.add_argument(
            '--prune-orphans',
            action='store_true',
            help=(
                'Volle Ordner-Abgleich: IMAP ALL (nur Message-ID) vs ES — '
                'entfernt gelöschte Mails auch außerhalb von since-days. '
                'Einmal nach großen Outlook-Löschungen empfohlen.'
            ),
        )
        parser.add_argument(
            '--prune-only',
            action='store_true',
            help='Nur --prune-orphans ausführen, nicht neu indexieren',
        )
        parser.add_argument(
            '--incremental',
            action='store_true',
            help=(
                'Nur neue Message-IDs voll laden (Header-Scan + ES-mget). '
                'Für 1‑Min-Scheduler; bestehende Docs werden übersprungen.'
            ),
        )

    def handle(self, *args, **options):
        from apps.abpe_search.services.search_service import get_es_client
        es = get_es_client()
        cfg = load_settings()

        es_index = cfg['indexing']['es_index']
        host = cfg['imap']['host']
        port = cfg['imap']['port']
        since_days = options['since_days']
        do_prune = not options['no_prune']
        prune_orphans = bool(options['prune_orphans'] or options['prune_only'])
        incremental = bool(options['incremental'])

        ES_MAPPING = {
            'mappings': {
                'properties': {
                    'account': {'type': 'keyword'},
                    'folder': {'type': 'keyword'},
                    'message_id': {'type': 'keyword'},
                    'subject': {'type': 'text', 'analyzer': 'german'},
                    'from_addr': {'type': 'keyword'},
                    'to_addr': {'type': 'text'},
                    'date': {'type': 'date'},
                    'body': {'type': 'text', 'analyzer': 'german'},
                    'has_attachments': {'type': 'boolean'},
                    'size_bytes': {'type': 'long'},
                    'indexed_at': {'type': 'date'},
                    'uid': {'type': 'keyword'},
                }
            },
            'settings': {
                'number_of_shards': 1,
                'number_of_replicas': 0,
            },
        }

        if options['reset'] and es.indices.exists(index=es_index):
            es.indices.delete(index=es_index)
            self.stdout.write('✓ Index gelöscht')

        if not es.indices.exists(index=es_index):
            es.indices.create(index=es_index, body=ES_MAPPING)
            self.stdout.write(f'✓ Index {es_index} angelegt')

        accounts = {
            user: data
            for user, data in cfg['accounts'].items()
            if data.get('enabled', False)
            and data.get('password', '')
            and data.get('password') != '***REDACTED***'
            and (options['account'] is None or user == options['account'])
        }

        if not accounts:
            self.stdout.write(self.style.ERROR(
                'Keine aktiven Accounts (enabled+password). '
                'Live-email_settings.json prüfen — Repo-Kopie ist redacted.'
            ))
            return

        want_folders = None
        if not options['all_folders']:
            want_folders = {
                f.strip() for f in (options['folders'] or 'INBOX').split(',') if f.strip()
            }

        total_indexed = 0
        total_errors = 0
        total_bad = 0
        total_pruned = 0
        start = datetime.now(timezone.utc)

        self.stdout.write(
            f'IMAP {host}:{port} → ES {es_index} | '
            f'since_days={since_days} folders='
            f'{"ALL" if options["all_folders"] else sorted(want_folders or [])} | '
            f'prune={do_prune} prune_orphans={prune_orphans} incremental={incremental}'
        )

        for account, data in accounts.items():
            password = data['password']
            description = data.get('description', account)
            self.stdout.write(f'\n📬 {account} ({description})...')

            try:
                m = imaplib.IMAP4_SSL(host, port)
                m.login(account, password)
                r, folders = m.list()
                m.logout()
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ❌ Login fehler: {e}'))
                continue

            for f in folders or []:
                fname = _folder_name(f)
                if not fname:
                    continue
                if want_folders is not None and fname not in want_folders:
                    # Zimbra: manchmal INBOX vs Inbox
                    if not any(fname.upper() == w.upper() for w in want_folders):
                        continue

                if prune_orphans:
                    self.stdout.write(f'  🧹 {fname}: orphan-prune (IMAP ALL vs ES)…')
                    live = collect_live_doc_ids_headers(account, password, fname, cfg)
                    pruned = prune_missing_from_es(
                        es, es_index, account, fname, live, since_days=None,
                    )
                    total_pruned += pruned
                    self.stdout.write(
                        f'  ✓ {fname}: orphan-prune live={len(live)} entfernt={pruned}'
                    )
                    if options['prune_only']:
                        continue

                indexed, errors, bad, pruned = fetch_folder(
                    account, password, fname, es, cfg,
                    since_days=since_days or None,
                    prune=do_prune and not prune_orphans,
                    incremental=incremental,
                    # orphan-Lauf hat schon voll geprunt → kein Doppel-Prune im Fenster
                )
                total_errors += errors
                total_bad += bad
                total_pruned += pruned
                if indexed > 0 or errors or bad or pruned:
                    self.stdout.write(
                        f'  ✓ {fname}: {indexed} indiziert'
                        f'{f"  errors={errors}" if errors else ""}'
                        f'{f"  bad_dates={bad}" if bad else ""}'
                        f'{f"  pruned={pruned}" if pruned else ""}'
                    )
                    total_indexed += indexed

        elapsed = int((datetime.now(timezone.utc) - start).total_seconds())
        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Fertig: {total_indexed} E-Mails in {elapsed}s '
            f'(errors={total_errors}, skipped_bad_date={total_bad}, pruned={total_pruned})'
        ))
