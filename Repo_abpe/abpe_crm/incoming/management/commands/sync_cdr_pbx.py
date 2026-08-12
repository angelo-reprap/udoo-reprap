# apps/abpe_crm/management/commands/sync_cdr_pbx.py
"""
Sync der Asterisk-CDR (PBX-MariaDB asteriskcdrdb.cdr) -> lokale CrmCdr (Postgres).

Modi:
  (Standard)    inkrementell: nur Zeilen neuer als der juengste CrmCdr.calldate
  --full        Erstbefuellung: ALLE Zeilen (Upsert dedupt ueber uniqueid)
  --reresolve   nur unaufgeloeste (party_crm_id IS NULL, nicht-system) neu aufloesen
  --since=YYYY-MM-DD   ab Datum (ueberschreibt Watermark)
  --limit=N     max. N Zeilen (Debug)
  --dry-run     nichts schreiben, nur zaehlen

Verbindung: settings.CDR_DB (PyMySQL). Resolver/Classify: services/cdr_resolver.
Dedup: update_or_create(uniqueid=...). Watermark: MAX(calldate) aus CrmCdr.
"""
import pymysql
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Max

from apps.abpe_crm.models import CrmCdr
from apps.abpe_crm.services.normalize_phone_nr import normalize_phone
from apps.abpe_crm.services.cdr_resolver import classify, resolve_party

CDR_COLS = [
    'calldate', 'clid', 'src', 'dst', 'dcontext', 'channel', 'dstchannel',
    'lastapp', 'lastdata', 'duration', 'billsec', 'disposition', 'amaflags',
    'accountcode', 'uniqueid', 'userfield', 'did', 'recordingfile', 'cnum',
    'cnam', 'outbound_cnum', 'outbound_cnam', 'dst_cnam', 'linkedid',
    'peeraccount', 'sequence',
]
BATCH = 500


def _aware(dt):
    if dt is None:
        return None
    if timezone.is_naive(dt):
        return timezone.make_aware(dt)
    return dt


class Command(BaseCommand):
    help = 'Synchronisiert die PBX-CDR in die lokale CrmCdr-Tabelle.'

    def add_arguments(self, parser):
        parser.add_argument('--full', action='store_true')
        parser.add_argument('--reresolve', action='store_true')
        parser.add_argument('--since', type=str, default='')
        parser.add_argument('--limit', type=int, default=0)
        parser.add_argument('--dry-run', action='store_true')

    def _resolve_row(self, row):
        direction, ext, party_raw, is_sys = classify(
            row['lastapp'], row['src'], row['dst'], row['channel'], row['dstchannel'])
        src_norm = normalize_phone(row['src'] or '')
        dst_norm = normalize_phone(row['dst'] or '')
        party_norm = normalize_phone(party_raw) if party_raw else ''
        if is_sys:
            res = {'crm_id': None, 'module': '', 'name': '', 'conf': '', 'cands': []}
        else:
            res = resolve_party(party_norm)
        return dict(
            src_norm=src_norm, dst_norm=dst_norm, direction=direction, ext=ext,
            party_number=party_norm, party_crm_id=res['crm_id'],
            party_module=res['module'], party_name=res['name'],
            match_confidence=res['conf'], match_candidates=res['cands'],
            is_system=is_sys,
        )

    def _reresolve(self, dry):
        qs = CrmCdr.objects.filter(
            party_crm_id__isnull=True, is_system=False).exclude(party_number='')
        total = qs.count()
        self.stdout.write("Re-Resolve: %d unaufgeloeste Zeilen mit Nummer." % total)
        changed = 0
        for c in qs.iterator(chunk_size=BATCH):
            res = resolve_party(c.party_number)
            if res['crm_id'] or res['conf']:
                if not dry:
                    c.party_crm_id     = res['crm_id']
                    c.party_module     = res['module']
                    c.party_name       = res['name']
                    c.match_confidence = res['conf']
                    c.match_candidates = res['cands']
                    c.save(update_fields=['party_crm_id', 'party_module', 'party_name',
                                          'match_confidence', 'match_candidates', 'synced_at'])
                changed += 1
        self.stdout.write(self.style.SUCCESS("Re-Resolve fertig: %d aktualisiert." % changed))

    def handle(self, *args, **opts):
        if opts['reresolve']:
            return self._reresolve(opts['dry_run'])

        where, params = '', []
        if opts['since']:
            where = 'WHERE calldate >= %s'
            params = [opts['since']]
            self.stdout.write("Modus: ab --since=%s" % opts['since'])
        elif opts['full']:
            self.stdout.write("Modus: FULL (alle Zeilen).")
        else:
            wm = CrmCdr.objects.aggregate(m=Max('calldate'))['m']
            if wm:
                where = 'WHERE calldate >= %s'
                params = [wm.strftime('%Y-%m-%d %H:%M:%S')]
                self.stdout.write("Modus: inkrementell ab Watermark %s" % params[0])
            else:
                self.stdout.write("Modus: inkrementell, Tabelle leer -> wie FULL.")

        limit_sql = (" LIMIT %d" % int(opts['limit'])) if opts['limit'] else ""
        sql = ("SELECT %s FROM cdr %s ORDER BY calldate ASC%s"
               % (', '.join(CDR_COLS), where, limit_sql))

        cfg = dict(settings.CDR_DB)
        con = pymysql.connect(cursorclass=pymysql.cursors.DictCursor, **cfg)
        seen = created = updated = skipped = 0
        try:
            with con.cursor() as cur:
                cur.execute(sql, params)
                while True:
                    chunk = cur.fetchmany(BATCH)
                    if not chunk:
                        break
                    for row in chunk:
                        seen += 1
                        uid = (row.get('uniqueid') or '').strip()
                        cd = _aware(row.get('calldate'))
                        if not uid or cd is None:
                            skipped += 1
                            continue
                        base = {k: (row.get(k) or '') for k in CDR_COLS
                                if k not in ('calldate', 'duration', 'billsec',
                                             'amaflags', 'sequence', 'uniqueid')}
                        base['calldate'] = cd
                        base['duration'] = int(row.get('duration') or 0)
                        base['billsec'] = int(row.get('billsec') or 0)
                        base['amaflags'] = int(row.get('amaflags') or 0)
                        base['sequence'] = int(row.get('sequence') or 0)
                        base.update(self._resolve_row(row))
                        if opts['dry_run']:
                            continue
                        _, was_created = CrmCdr.objects.update_or_create(
                            uniqueid=uid, defaults=base)
                        created += 1 if was_created else 0
                        updated += 0 if was_created else 1
                    self.stdout.write("  ... %d gelesen (neu %d, akt. %d, skip %d)"
                                      % (seen, created, updated, skipped))
        finally:
            con.close()

        self.stdout.write(self.style.SUCCESS(
            "Fertig. Gelesen %d, neu %d, aktualisiert %d, uebersprungen %d. "
            "CrmCdr gesamt: %d"
            % (seen, created, updated, skipped, CrmCdr.objects.count())))
