"""
apps/abpe_crm/management/commands/sync_crm.py

SuiteCRM MySQL → Django PostgreSQL Sync
----------------------------------------
Schalter:
  --dryrun          nur lesen, nichts schreiben
  --limit N         max N Datensätze pro Tabelle (0 = alle)
  --table NAME      nur eine Tabelle synchen
                    (contacts|accounts|emails|relations|all)
  --force           auch bereits gesynchte Datensätze updaten
  --stats           nur Zähler aus MySQL, kein Sync
  --since YYYY-MM-DD  nur Datensätze mit date_modified >= Datum

Beispiele:
  python manage.py sync_crm --stats
  python manage.py sync_crm --dryrun --limit 50
  python manage.py sync_crm --table contacts --limit 100
  python manage.py sync_crm --force
  python manage.py sync_crm --since 2026-01-01
"""

import MySQLdb
import MySQLdb.cursors
from datetime import datetime, date
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.abpe_crm.models import (
    CrmContact, CrmContactCstm,
    CrmAccount, CrmAccountCstm,
    CrmAccountContacts,
    CrmEmailAddress, CrmEmailAddrBeanRel,
)

# ── MySQL Verbindungsparameter ────────────────────────────────────────────────
MYSQL_CONF = {
    'host':    '172.20.3.150',
    'user':    'suitecrm',
    'passwd':  '3b135fd9a867a884509a13d6ceb8dd5e460f963be10e07619767301f9b9087c7',
    'db':      'suitecrm',
    'charset': 'utf8mb4',
    'connect_timeout': 10,
}

TABLES = ['contacts', 'accounts', 'emails', 'relations']


# ─────────────────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = 'Sync SuiteCRM MySQL → ABpE PostgreSQL'

    def add_arguments(self, parser):
        parser.add_argument('--dryrun',  action='store_true', help='Nichts schreiben')
        parser.add_argument('--limit',   type=int, default=0,  help='Max Datensätze pro Tabelle (0=alle)')
        parser.add_argument('--table',   type=str, default='all',
                            choices=TABLES + ['all'], help='Nur diese Tabelle synchen')
        parser.add_argument('--force',   action='store_true', help='Bereits gesynchte Datensätze updaten')
        parser.add_argument('--stats',   action='store_true', help='Nur Zähler ausgeben')
        parser.add_argument('--since',   type=str, default=None,
                            help='Nur Datensätze mit date_modified >= YYYY-MM-DD')

    # ── Entry Point ──────────────────────────────────────────────────────────

    def handle(self, *args, **options):
        self.dryrun  = options['dryrun']
        self.limit   = options['limit']
        self.table   = options['table']
        self.force   = options['force']
        self.since   = options['since']
        self.stats_only = options['stats']
        self.verbosity  = options['verbosity']

        self.ok = self.style.SUCCESS
        self.warn = self.style.WARNING
        self.err  = self.style.ERROR

        if self.dryrun:
            self.stdout.write(self.warn('⚠  DRYRUN — nichts wird geschrieben'))

        try:
            self.db = MySQLdb.connect(**MYSQL_CONF)
            self.db.autocommit(True)
        except Exception as e:
            raise CommandError(f'MySQL Verbindung fehlgeschlagen: {e}')

        self.stdout.write(f'✅ MySQL verbunden ({MYSQL_CONF["host"]})')

        if self.stats_only:
            self._show_stats()
            self.db.close()
            return

        # Sync Reihenfolge — FKs beachten!
        run = self.table
        if run in ('all', 'accounts'):   self._sync_accounts()
        if run in ('all', 'contacts'):   self._sync_contacts()
        if run in ('all', 'emails'):     self._sync_emails()
        if run in ('all', 'relations'):  self._sync_relations()

        self.db.close()
        self.stdout.write(self.ok('\n✅ Sync abgeschlossen'))

    # ── Stats ────────────────────────────────────────────────────────────────

    def _show_stats(self):
        cur = self._cursor()
        queries = [
            ("contacts",            "SELECT COUNT(*) FROM contacts WHERE deleted=0"),
            ("contacts_cstm",       "SELECT COUNT(*) FROM contacts_cstm"),
            ("accounts",            "SELECT COUNT(*) FROM accounts WHERE deleted=0"),
            ("accounts_cstm",       "SELECT COUNT(*) FROM accounts_cstm"),
            ("accounts_contacts",   "SELECT COUNT(*) FROM accounts_contacts WHERE deleted=0"),
            ("email_addresses",     "SELECT COUNT(*) FROM email_addresses WHERE deleted=0"),
            ("email_addr_bean_rel", "SELECT COUNT(*) FROM email_addr_bean_rel WHERE deleted=0 AND bean_module='Contacts'"),
        ]
        self.stdout.write('\n── MySQL Datenmenge ──────────────────────────')
        for label, sql in queries:
            cur.execute(sql)
            n = cur.fetchone()['COUNT(*)']
            self.stdout.write(f'  {label:<25} {n:>7}')

        self.stdout.write('\n── PostgreSQL (aktuell) ──────────────────────')
        pg = [
            ('CrmContact',          CrmContact.objects.count()),
            ('CrmContactCstm',      CrmContactCstm.objects.count()),
            ('CrmAccount',          CrmAccount.objects.count()),
            ('CrmAccountCstm',      CrmAccountCstm.objects.count()),
            ('CrmAccountContacts',  CrmAccountContacts.objects.count()),
            ('CrmEmailAddress',     CrmEmailAddress.objects.count()),
            ('CrmEmailAddrBeanRel', CrmEmailAddrBeanRel.objects.count()),
        ]
        for label, n in pg:
            self.stdout.write(f'  {label:<25} {n:>7}')

        # kontakt_typ_c Verteilung
        cur.execute('''
            SELECT kontakt_typ_c, COUNT(*) AS n
            FROM contacts_cstm
            GROUP BY kontakt_typ_c ORDER BY n DESC
        ''')
        self.stdout.write('\n── kontakt_typ_c Verteilung ──────────────────')
        for row in cur.fetchall():
            self.stdout.write(f'  {row["kontakt_typ_c"] or "NULL":<20} {row["n"]:>7}')

    # ── Accounts ─────────────────────────────────────────────────────────────

    def _sync_accounts(self):
        self.stdout.write('\n── Sync accounts ────────────────────────────')
        cur = self._cursor()

        sql = '''
            SELECT a.id, a.name, a.date_entered, a.date_modified, a.deleted,
                   a.account_type, a.industry, a.annual_revenue, a.description,
                   a.rating, a.ownership, a.employees, a.ticker_symbol, a.sic_code,
                   a.website, a.phone_office, a.phone_alternate, a.phone_fax,
                   a.billing_address_street, a.billing_address_city,
                   a.billing_address_state, a.billing_address_postalcode,
                   a.billing_address_country,
                   a.shipping_address_street, a.shipping_address_city,
                   a.shipping_address_state, a.shipping_address_postalcode,
                   a.shipping_address_country,
                   a.parent_id,
                   ac.account_status_c, ac.kunden_nummer_c
            FROM accounts a
            LEFT JOIN accounts_cstm ac ON ac.id_c = a.id
            WHERE a.deleted = 0
        '''
        sql += self._since_clause('a.date_modified')
        sql += self._limit_clause()

        cur.execute(sql)
        rows = cur.fetchall()
        self.stdout.write(f'  MySQL: {len(rows)} Accounts')

        created = updated = skipped = 0
        now = timezone.now()

        for row in rows:
            crm_id = row['id']

            # Account
            acc_data = dict(
                name                        = row['name'],
                crm_date_entered            = row['date_entered'],
                crm_date_modified           = row['date_modified'],
                account_type                = row['account_type'],
                industry                    = row['industry'],
                annual_revenue              = row['annual_revenue'],
                description                 = row['description'],
                rating                      = row['rating'],
                ownership                   = row['ownership'],
                employees                   = row['employees'],
                ticker_symbol               = row['ticker_symbol'],
                sic_code                    = row['sic_code'],
                website                     = row['website'],
                phone_office                = row['phone_office'],
                phone_alternate             = row['phone_alternate'],
                phone_fax                   = row['phone_fax'],
                billing_address_street      = row['billing_address_street'],
                billing_address_city        = row['billing_address_city'],
                billing_address_state       = row['billing_address_state'],
                billing_address_postalcode  = row['billing_address_postalcode'],
                billing_address_country     = row['billing_address_country'],
                shipping_address_street     = row['shipping_address_street'],
                shipping_address_city       = row['shipping_address_city'],
                shipping_address_state      = row['shipping_address_state'],
                shipping_address_postalcode = row['shipping_address_postalcode'],
                shipping_address_country    = row['shipping_address_country'],
                parent_crm_id               = row['parent_id'],
                crm_synced_at               = now,
            )

            existing = CrmAccount.objects.filter(crm_id=crm_id).first()

            if existing and not self.force:
                skipped += 1
                continue

            if not self.dryrun:
                with transaction.atomic():
                    if existing:
                        for k, v in acc_data.items():
                            setattr(existing, k, v)
                        existing.save()
                        updated += 1
                    else:
                        acc = CrmAccount.objects.create(crm_id=crm_id, **acc_data)
                        created += 1

                    # AccountCstm
                    CrmAccountCstm.objects.update_or_create(
                        account_id=crm_id,
                        defaults=dict(
                            account_status_c  = row['account_status_c'],
                            kunden_nummer_c   = row['kunden_nummer_c'],
                        )
                    )
            else:
                created += 1  # dryrun zählt als würde es passieren

        self.stdout.write(self.ok(
            f'  Accounts → neu: {created}  aktualisiert: {updated}  übersprungen: {skipped}'
        ))

    # ── Contacts ─────────────────────────────────────────────────────────────

    def _sync_contacts(self):
        self.stdout.write('\n── Sync contacts ────────────────────────────')
        cur = self._cursor()

        sql = '''
            SELECT
                c.id, c.date_entered, c.date_modified,
                c.salutation, c.first_name, c.last_name,
                c.title, c.department, c.do_not_call, c.birthdate,
                c.photo, c.description,
                c.phone_home, c.phone_mobile, c.phone_work,
                c.phone_other, c.phone_fax,
                c.primary_address_street, c.primary_address_city,
                c.primary_address_state, c.primary_address_postalcode,
                c.primary_address_country,
                c.alt_address_street, c.alt_address_city,
                c.alt_address_state, c.alt_address_postalcode,
                c.alt_address_country,
                c.assistant, c.assistant_phone,
                cc.kontakt_typ_c, cc.kontakt_status_c,
                cc.gulp_id_c, cc.gulp_last_updated_c,
                cc.verfuegbar_ab_c, cc.konditionen_c, cc.skill_priority_c,
                cc.gulp_profil_c, cc.ogo_description_c,
                cc.freelancermap_profil_c, cc.xing_profile_c,
                cc.web_profil1_typ_c, cc.web_profil1_location_c,
                cc.web_profil2_typ_c, cc.web_profil2_location_c,
                cc.web_profil3_typ_c, cc.web_profil3_location_c,
                cc.web_profil4_typ_c, cc.web_profil4_location_c,
                cc.im1_typ_c, cc.im1_id_c,
                cc.im2_typ_c, cc.im2_id_c,
                cc.emma_last_updated_c, cc.xing_last_updated_c,
                cc.freelancermap_last_updated_c, cc.martha_last_updated_c,
                cc.import_id_c, cc.import_source_c, cc.import_tag_c,
                cc.import_account_id_c
            FROM contacts c
            LEFT JOIN contacts_cstm cc ON cc.id_c = c.id
            WHERE c.deleted = 0
        '''
        sql += self._since_clause('c.date_modified')
        sql += self._limit_clause()

        cur.execute(sql)
        rows = cur.fetchall()
        self.stdout.write(f'  MySQL: {len(rows)} Contacts')

        created = updated = skipped = errors = 0
        now = timezone.now()

        for row in rows:
            crm_id = row['id']

            contact_data = dict(
                crm_date_entered            = row['date_entered'],
                crm_date_modified           = row['date_modified'],
                salutation                  = row['salutation'],
                first_name                  = row['first_name'],
                last_name                   = row['last_name'],
                title                       = row['title'],
                department                  = row['department'],
                do_not_call                 = bool(row['do_not_call']),
                birthdate                   = row['birthdate'],
                photo                       = row['photo'],
                description                 = row['description'],
                phone_home                  = row['phone_home'],
                phone_mobile                = row['phone_mobile'],
                phone_work                  = row['phone_work'],
                phone_other                 = row['phone_other'],
                phone_fax                   = row['phone_fax'],
                primary_address_street      = row['primary_address_street'],
                primary_address_city        = row['primary_address_city'],
                primary_address_state       = row['primary_address_state'],
                primary_address_postalcode  = row['primary_address_postalcode'],
                primary_address_country     = row['primary_address_country'],
                alt_address_street          = row['alt_address_street'],
                alt_address_city            = row['alt_address_city'],
                alt_address_state           = row['alt_address_state'],
                alt_address_postalcode      = row['alt_address_postalcode'],
                alt_address_country         = row['alt_address_country'],
                assistant                   = row['assistant'],
                assistant_phone             = row['assistant_phone'],
                crm_synced_at               = now,
            )

            existing = CrmContact.objects.filter(crm_id=crm_id).first()

            if existing and not self.force:
                skipped += 1
                continue

            if not self.dryrun:
                try:
                    with transaction.atomic():
                        if existing:
                            for k, v in contact_data.items():
                                setattr(existing, k, v)
                            existing.save()
                            contact = existing
                            updated += 1
                        else:
                            contact = CrmContact.objects.create(crm_id=crm_id, **contact_data)
                            created += 1

                        # ContactCstm
                        CrmContactCstm.objects.update_or_create(
                            contact_id=crm_id,
                            defaults=dict(
                                gulp_id_c                    = row['gulp_id_c'],
                                gulp_last_updated_c          = row['gulp_last_updated_c'],
                                kontakt_typ_c                = row['kontakt_typ_c'],
                                kontakt_status_c             = row['kontakt_status_c'],
                                verfuegbar_ab_c              = row['verfuegbar_ab_c'],
                                konditionen_c                = row['konditionen_c'],
                                skill_priority_c             = row['skill_priority_c'],
                                gulp_profil_c                = row['gulp_profil_c'],
                                ogo_description_c            = row['ogo_description_c'],
                                freelancermap_profil_c       = row['freelancermap_profil_c'],
                                xing_profile_c               = row['xing_profile_c'],
                                web_profil1_typ_c            = row['web_profil1_typ_c'],
                                web_profil1_location_c       = row['web_profil1_location_c'],
                                web_profil2_typ_c            = row['web_profil2_typ_c'],
                                web_profil2_location_c       = row['web_profil2_location_c'],
                                web_profil3_typ_c            = row['web_profil3_typ_c'],
                                web_profil3_location_c       = row['web_profil3_location_c'],
                                web_profil4_typ_c            = row['web_profil4_typ_c'],
                                web_profil4_location_c       = row['web_profil4_location_c'],
                                im1_typ_c                    = row['im1_typ_c'],
                                im1_id_c                     = row['im1_id_c'],
                                im2_typ_c                    = row['im2_typ_c'],
                                im2_id_c                     = row['im2_id_c'],
                                emma_last_updated_c          = row['emma_last_updated_c'],
                                xing_last_updated_c          = row['xing_last_updated_c'],
                                freelancermap_last_updated_c = row['freelancermap_last_updated_c'],
                                martha_last_updated_c        = row['martha_last_updated_c'],
                            )
                        )
                except Exception as e:
                    errors += 1
                    if self.verbosity >= 2:
                        self.stdout.write(self.err(f'  FEHLER {crm_id}: {e}'))
            else:
                created += 1

        self.stdout.write(self.ok(
            f'  Contacts → neu: {created}  aktualisiert: {updated}  übersprungen: {skipped}  fehler: {errors}'
        ))

    # ── Email Addresses ───────────────────────────────────────────────────────

    def _sync_emails(self):
        self.stdout.write('\n── Sync email_addresses ─────────────────────')
        cur = self._cursor()

        # Nur Email-Adressen die mit Contacts verknüpft sind
        sql = '''
            SELECT DISTINCT
                ea.id, ea.email_address, ea.email_address_caps,
                ea.invalid_email, ea.opt_out,
                ea.confirm_opt_in, ea.confirm_opt_in_date,
                ea.confirm_opt_in_sent_date, ea.confirm_opt_in_fail_date,
                ea.confirm_opt_in_token,
                ea.date_created, ea.date_modified
            FROM email_addresses ea
            JOIN email_addr_bean_rel rel
                ON rel.email_address_id = ea.id
                AND rel.bean_module = 'Contacts'
                AND rel.deleted = 0
            WHERE ea.deleted = 0
        '''
        sql += self._limit_clause()

        cur.execute(sql)
        rows = cur.fetchall()
        self.stdout.write(f'  MySQL: {len(rows)} Email-Adressen (Contact-verknüpft)')

        created = updated = skipped = 0

        for row in rows:
            crm_id = row['id']
            data = dict(
                email_address            = row['email_address'],
                email_address_caps       = row['email_address_caps'],
                invalid_email            = bool(row['invalid_email']),
                opt_out                  = bool(row['opt_out']),
                confirm_opt_in           = row['confirm_opt_in'],
                confirm_opt_in_date      = row['confirm_opt_in_date'],
                confirm_opt_in_sent_date = row['confirm_opt_in_sent_date'],
                confirm_opt_in_fail_date = row['confirm_opt_in_fail_date'],
                confirm_opt_in_token     = row['confirm_opt_in_token'],
                date_created             = row['date_created'],
                date_modified            = row['date_modified'],
            )

            existing = CrmEmailAddress.objects.filter(crm_id=crm_id).first()
            if existing and not self.force:
                skipped += 1
                continue

            if not self.dryrun:
                if existing:
                    for k, v in data.items():
                        setattr(existing, k, v)
                    existing.save()
                    updated += 1
                else:
                    CrmEmailAddress.objects.create(crm_id=crm_id, **data)
                    created += 1
            else:
                created += 1

        self.stdout.write(self.ok(
            f'  EmailAddress → neu: {created}  aktualisiert: {updated}  übersprungen: {skipped}'
        ))

    # ── Relations ─────────────────────────────────────────────────────────────

    def _sync_relations(self):
        self._sync_email_bean_rel()
        self._sync_account_contacts()

    def _sync_email_bean_rel(self):
        self.stdout.write('\n── Sync email_addr_bean_rel (Contacts) ──────')
        cur = self._cursor()

        sql = '''
            SELECT rel.id, rel.email_address_id, rel.bean_id, rel.bean_module,
                   rel.primary_address, rel.reply_to_address,
                   rel.date_created, rel.date_modified
            FROM email_addr_bean_rel rel
            WHERE rel.deleted = 0
              AND rel.bean_module = 'Contacts'
        '''
        sql += self._limit_clause()
        cur.execute(sql)
        rows = cur.fetchall()
        self.stdout.write(f'  MySQL: {len(rows)} Bean-Relations (Contacts)')

        created = skipped = errors = 0

        # Vorher: bekannte Email-IDs und Contact-IDs aus PostgreSQL laden
        known_email_ids   = set(CrmEmailAddress.objects.values_list('crm_id', flat=True))
        known_contact_ids = set(CrmContact.objects.values_list('crm_id', flat=True))

        missing_email   = 0
        missing_contact = 0

        for row in rows:
            crm_id       = row['id']
            email_crm_id = row['email_address_id']
            bean_id      = row['bean_id']  # = contact.crm_id

            # FK-Prüfung — Email-Adresse muss in PG existieren
            if email_crm_id not in known_email_ids:
                missing_email += 1
                continue

            # FK-Prüfung — Contact muss in PG existieren
            if bean_id not in known_contact_ids:
                missing_contact += 1
                continue

            existing = CrmEmailAddrBeanRel.objects.filter(crm_id=crm_id).first()
            if existing and not self.force:
                skipped += 1
                continue

            if not self.dryrun:
                try:
                    data = dict(
                        email_address_id  = email_crm_id,
                        bean_id           = bean_id,
                        bean_module       = row['bean_module'],
                        primary_address   = bool(row['primary_address']),
                        reply_to_address  = bool(row['reply_to_address']),
                        date_created      = row['date_created'],
                        date_modified     = row['date_modified'],
                    )
                    if existing:
                        for k, v in data.items():
                            setattr(existing, k, v)
                        existing.save()
                    else:
                        CrmEmailAddrBeanRel.objects.create(crm_id=crm_id, **data)
                    created += 1
                except Exception as e:
                    errors += 1
                    if self.verbosity >= 2:
                        self.stdout.write(self.err(f'  FEHLER {crm_id}: {e}'))
            else:
                created += 1

        self.stdout.write(self.ok(
            f'  BeanRel → neu/aktualisiert: {created}  übersprungen: {skipped}  fehler: {errors}'
        ))
        if missing_email > 0:
            self.stdout.write(self.warn(
                f'  ⚠  {missing_email} übersprungen — Email-Adresse nicht in PG (zuerst --table emails ausführen)'
            ))
        if missing_contact > 0:
            self.stdout.write(self.warn(
                f'  ⚠  {missing_contact} übersprungen — Contact nicht in PG (zuerst --table contacts ausführen)'
            ))

    def _sync_account_contacts(self):
        self.stdout.write('\n── Sync accounts_contacts ───────────────────')
        cur = self._cursor()

        sql = '''
            SELECT id, contact_id, account_id, date_modified
            FROM accounts_contacts
            WHERE deleted = 0
        '''
        sql += self._limit_clause()
        cur.execute(sql)
        rows = cur.fetchall()
        self.stdout.write(f'  MySQL: {len(rows)} Account-Contact Verknüpfungen')

        known_contact_ids = set(CrmContact.objects.values_list('crm_id', flat=True))
        known_account_ids = set(CrmAccount.objects.values_list('crm_id', flat=True))

        created = skipped = errors = missing = 0

        for row in rows:
            crm_id     = row['id']
            contact_id = row['contact_id']
            account_id = row['account_id']

            # FK-Prüfung
            if contact_id not in known_contact_ids or account_id not in known_account_ids:
                missing += 1
                continue

            existing = CrmAccountContacts.objects.filter(crm_id=crm_id).first()
            if existing and not self.force:
                skipped += 1
                continue

            if not self.dryrun:
                try:
                    data = dict(
                        contact_id    = contact_id,
                        account_id    = account_id,
                        date_modified = row['date_modified'],
                    )
                    if existing:
                        for k, v in data.items():
                            setattr(existing, k, v)
                        existing.save()
                    else:
                        CrmAccountContacts.objects.create(crm_id=crm_id, **data)
                    created += 1
                except Exception as e:
                    errors += 1
                    if self.verbosity >= 2:
                        self.stdout.write(self.err(f'  FEHLER {crm_id}: {e}'))
            else:
                created += 1

        self.stdout.write(self.ok(
            f'  AccountContacts → neu/aktualisiert: {created}  übersprungen: {skipped}  fehler: {errors}'
        ))
        if missing > 0:
            self.stdout.write(self.warn(
                f'  ⚠  {missing} übersprungen — Contact oder Account nicht in PG'
            ))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _cursor(self):
        return self.db.cursor(MySQLdb.cursors.DictCursor)

    def _since_clause(self, field):
        if self.since:
            return f" AND {field} >= '{self.since}' "
        return ' '

    def _limit_clause(self):
        if self.limit > 0:
            return f' LIMIT {self.limit}'
        return ''
