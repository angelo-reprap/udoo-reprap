"""
apps/abpe_crm/management/commands/sync_crm.py

SuiteCRM MySQL -> Django PostgreSQL Sync
----------------------------------------
Schalter:
  --dryrun          nur lesen, nichts schreiben
  --limit N         max N Datensaetze pro Tabelle (0 = alle)
  --table NAME      nur eine Tabelle synchen
                    (contacts|accounts|emails|relations|all)
  --force           auch bereits gesynchte Datensaetze updaten
  --update          inkrementeller Update via date_modified
  --stats           nur Zaehler aus MySQL, kein Sync
  --since YYYY-MM-DD  nur Datensaetze mit date_modified >= Datum

Beispiele:
  python manage.py sync_crm --stats
  python manage.py sync_crm --dryrun --limit 50
  python manage.py sync_crm --table contacts --limit 100
  python manage.py sync_crm --force
  python manage.py sync_crm --update
  python manage.py sync_crm --since 2026-01-01
"""

import MySQLdb
import MySQLdb.cursors
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.abpe_crm.services.normalize_phone_nr import normalize_phone
from apps.abpe_crm.models import (
    CrmContact, CrmContactCstm,
    CrmAccount, CrmAccountCstm,
    CrmAccountContacts,
    CrmEmailAddress, CrmEmailAddrBeanRel,
    CrmPhoneNumber, CrmPhoneBeanRel,
)

MYSQL_CONF = {
    'host':    '172.20.3.150',
    'user':    'suitecrm',
    'passwd':  '3b135fd9a867a884509a13d6ceb8dd5e460f963be10e07619767301f9b9087c7',
    'db':      'suitecrm',
    'charset': 'utf8mb4',
    'connect_timeout': 10,
}

TABLES = ['contacts', 'accounts', 'emails', 'relations']
CHUNK  = 500


class Command(BaseCommand):
    help = 'Sync SuiteCRM MySQL -> ABpE PostgreSQL'

    def add_arguments(self, parser):
        parser.add_argument('--dryrun',  action='store_true', help='Nichts schreiben')
        parser.add_argument('--limit',   type=int, default=0,  help='Max Datensaetze pro Tabelle (0=alle)')
        parser.add_argument('--table',   type=str, default='all',
                            choices=TABLES + ['all'], help='Nur diese Tabelle synchen')
        parser.add_argument('--force',   action='store_true', help='Bereits gesynchte Datensaetze updaten')
        parser.add_argument('--update',  action='store_true', help='Inkrementeller Update via date_modified')
        parser.add_argument('--stats',   action='store_true', help='Nur Zaehler ausgeben')
        parser.add_argument('--since',   type=str, default=None,
                            help='Nur Datensaetze mit date_modified >= YYYY-MM-DD')

    def handle(self, *args, **options):
        self.dryrun     = options['dryrun']
        self.limit      = options['limit']
        self.table      = options['table']
        self.force      = options['force']
        self.update     = options['update']
        self.since      = options['since']
        self.stats_only = options['stats']
        self.verbosity  = options['verbosity']

        if self.dryrun:
            self.stdout.write(self.style.WARNING('  DRYRUN - nichts wird geschrieben'))

        try:
            self.db = MySQLdb.connect(**MYSQL_CONF)
            self.db.autocommit(True)
        except Exception as e:
            raise CommandError(f'MySQL Verbindung fehlgeschlagen: {e}')

        self.stdout.write(f'MySQL verbunden ({MYSQL_CONF["host"]})')

        if self.stats_only:
            self._show_stats()
            self.db.close()
            return

        run = self.table
        if run in ('all', 'accounts'):   self._sync_accounts()
        if run in ('all', 'contacts'):   self._sync_contacts()
        if run in ('all', 'emails'):     self._sync_emails()
        if run in ('all', 'relations'):  self._sync_relations()

        self.db.close()
        self.stdout.write(self.style.SUCCESS('\nSync abgeschlossen'))

    # ── Stats ────────────────────────────────────────────────────────────────

    def _show_stats(self):
        cur = self._cursor()
        queries = [
            ("contacts",                   "SELECT COUNT(*) FROM contacts WHERE deleted=0"),
            ("contacts_cstm",              "SELECT COUNT(*) FROM contacts_cstm"),
            ("accounts",                   "SELECT COUNT(*) FROM accounts WHERE deleted=0"),
            ("accounts_cstm",              "SELECT COUNT(*) FROM accounts_cstm"),
            ("accounts_contacts",          "SELECT COUNT(*) FROM accounts_contacts WHERE deleted=0"),
            ("email_addresses",            "SELECT COUNT(*) FROM email_addresses WHERE deleted=0"),
            ("email_addr_bean_rel (Contacts)", "SELECT COUNT(*) FROM email_addr_bean_rel WHERE deleted=0 AND bean_module='Contacts'"),
            ("email_addr_bean_rel (Accounts)", "SELECT COUNT(*) FROM email_addr_bean_rel WHERE deleted=0 AND bean_module='Accounts'"),
        ]
        self.stdout.write('\n-- MySQL Datenmenge --')
        for label, sql in queries:
            cur.execute(sql)
            n = cur.fetchone()['COUNT(*)']
            self.stdout.write(f'  {label:<40} {n:>7}')

        self.stdout.write('\n-- PostgreSQL (aktuell) --')
        pg = [
            ('CrmContact',                      CrmContact.objects.count()),
            ('CrmContactCstm',                  CrmContactCstm.objects.count()),
            ('CrmAccount',                      CrmAccount.objects.count()),
            ('CrmAccountCstm',                  CrmAccountCstm.objects.count()),
            ('CrmAccountContacts',              CrmAccountContacts.objects.count()),
            ('CrmEmailAddress',                 CrmEmailAddress.objects.count()),
            ('CrmEmailAddrBeanRel (Contacts)',   CrmEmailAddrBeanRel.objects.filter(bean_module='Contacts').count()),
            ('CrmEmailAddrBeanRel (Accounts)',   CrmEmailAddrBeanRel.objects.filter(bean_module='Accounts').count()),
        ]
        for label, n in pg:
            self.stdout.write(f'  {label:<40} {n:>7}')

        cur.execute('''
            SELECT kontakt_typ_c, COUNT(*) AS n
            FROM contacts_cstm
            GROUP BY kontakt_typ_c ORDER BY n DESC
        ''')
        self.stdout.write('\n-- kontakt_typ_c Verteilung --')
        for row in cur.fetchall():
            self.stdout.write(f'  {row["kontakt_typ_c"] or "NULL":<20} {row["n"]:>7}')

    # ── Accounts ─────────────────────────────────────────────────────────────

    def _sync_accounts(self):
        self.stdout.write('\n-- Sync accounts --')
        cur = self._cursor()
        sql = '''
            SELECT a.id, a.name, a.date_entered, a.date_modified,
                   a.account_type, a.industry, a.annual_revenue, a.description,
                   a.rating, a.ownership, a.employees, a.ticker_symbol, a.sic_code,
                   a.website, a.phone_office, a.phone_alternate, a.phone_fax,
                   a.billing_address_street, a.billing_address_city,
                   a.billing_address_state, a.billing_address_postalcode,
                   a.billing_address_country,
                   a.shipping_address_street, a.shipping_address_city,
                   a.shipping_address_state, a.shipping_address_postalcode,
                   a.shipping_address_country, a.parent_id,
                   ac.account_status_c, ac.kunden_nummer_c
            FROM accounts a
            LEFT JOIN accounts_cstm ac ON ac.id_c = a.id
            WHERE a.deleted = 0
        ''' + self._since_clause('a.date_modified') + self._limit_clause()
        cur.execute(sql)
        rows = cur.fetchall()
        self.stdout.write(f'  MySQL: {len(rows)} Accounts gelesen')

        if self.dryrun:
            self.stdout.write(self.style.SUCCESS(f'  Accounts -> neu: {len(rows)}  (dryrun)'))
            return

        existing_ids = set(CrmAccount.objects.values_list('crm_id', flat=True))
        now = timezone.now()
        new_accounts = []
        update_accounts = []
        new_cstms = []
        update_cstms = []

        for row in rows:
            crm_id = row['id']
            acc_data = dict(
                crm_date_entered            = row['date_entered'],
                crm_date_modified           = row['date_modified'],
                name                        = row['name'],
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
            cstm_data = dict(
                account_status_c = row['account_status_c'],
                kunden_nummer_c  = row['kunden_nummer_c'],
            )
            if crm_id in existing_ids:
                if self.force or self.update:
                    update_accounts.append((crm_id, acc_data))
                    update_cstms.append((crm_id, cstm_data))
            else:
                new_accounts.append(CrmAccount(crm_id=crm_id, **acc_data))
                new_cstms.append((crm_id, cstm_data))

        # Insert new
        created = 0
        for i in range(0, len(new_accounts), CHUNK):
            with transaction.atomic():
                CrmAccount.objects.bulk_create(new_accounts[i:i+CHUNK], ignore_conflicts=True)
            created += len(new_accounts[i:i+CHUNK])
            self.stdout.write(f'  ... {created}/{len(new_accounts)} Accounts neu')

        # Update existing
        updated = 0
        for crm_id, data in update_accounts:
            CrmAccount.objects.filter(crm_id=crm_id).update(**data)
            updated += 1

        # Cstm insert
        for crm_id, data in new_cstms:
            CrmAccountCstm.objects.get_or_create(
                account_id=crm_id, defaults=data
            )

        # Cstm update
        for crm_id, data in update_cstms:
            CrmAccountCstm.objects.filter(account_id=crm_id).update(**data)

        self.stdout.write(self.style.SUCCESS(
            f'  Accounts -> neu: {created}  aktualisiert: {updated}  bereits vorhanden: {len(existing_ids)}'
        ))

    # ── Contacts ─────────────────────────────────────────────────────────────

    def _sync_contacts(self):
        self.stdout.write('\n-- Sync contacts --')
        cur = self._cursor()
        sql = '''
            SELECT c.id, c.date_entered, c.date_modified,
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
                   cc.freelancermap_last_updated_c, cc.martha_last_updated_c
            FROM contacts c
            LEFT JOIN contacts_cstm cc ON cc.id_c = c.id
            WHERE c.deleted = 0
        ''' + self._since_clause('c.date_modified') + self._limit_clause()
        cur.execute(sql)
        rows = cur.fetchall()
        self.stdout.write(f'  MySQL: {len(rows)} Contacts gelesen')

        if self.dryrun:
            self.stdout.write(self.style.SUCCESS(f'  Contacts -> neu: {len(rows)}  (dryrun)'))
            return

        existing_ids = set(CrmContact.objects.values_list('crm_id', flat=True))
        now = timezone.now()
        new_contacts = []
        update_contacts = []
        new_cstms = []
        update_cstms = []

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
            cstm_data = dict(
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
            if crm_id in existing_ids:
                if self.force or self.update:
                    update_contacts.append((crm_id, contact_data))
                    update_cstms.append((crm_id, cstm_data))
            else:
                new_contacts.append(CrmContact(crm_id=crm_id, **contact_data))
                new_cstms.append((crm_id, cstm_data))

        # Insert new contacts
        created = 0
        for i in range(0, len(new_contacts), CHUNK):
            with transaction.atomic():
                CrmContact.objects.bulk_create(new_contacts[i:i+CHUNK], ignore_conflicts=True)
            created += len(new_contacts[i:i+CHUNK])
            self.stdout.write(f'  ... {created}/{len(new_contacts)} Contacts neu')

        # Update existing contacts
        updated = 0
        for i in range(0, len(update_contacts), CHUNK):
            with transaction.atomic():
                for crm_id, data in update_contacts[i:i+CHUNK]:
                    CrmContact.objects.filter(crm_id=crm_id).update(**data)
                    updated += 1
            self.stdout.write(f'  ... {updated}/{len(update_contacts)} Contacts aktualisiert')

        # Cstm insert
        for crm_id, data in new_cstms:
            CrmContactCstm.objects.get_or_create(contact_id=crm_id, defaults=data)

        # Cstm update
        for i in range(0, len(update_cstms), CHUNK):
            with transaction.atomic():
                for crm_id, data in update_cstms[i:i+CHUNK]:
                    CrmContactCstm.objects.filter(contact_id=crm_id).update(**data)

        self.stdout.write(self.style.SUCCESS(
            f'  Contacts -> neu: {created}  aktualisiert: {updated}  bereits vorhanden: {len(existing_ids)}'
        ))

    # ── Email Addresses ───────────────────────────────────────────────────────

    def _sync_emails(self):
        self.stdout.write('\n-- Sync email_addresses (Contacts + Accounts) --')
        cur = self._cursor()
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
                AND rel.bean_module IN ('Contacts', 'Accounts')
                AND rel.deleted = 0
            WHERE ea.deleted = 0
        ''' + self._limit_clause()
        cur.execute(sql)
        rows = cur.fetchall()
        self.stdout.write(f'  MySQL: {len(rows)} Email-Adressen (Contact + Account verknuepft)')

        if self.dryrun:
            self.stdout.write(self.style.SUCCESS(f'  EmailAddress -> neu: {len(rows)}  (dryrun)'))
            return

        existing_ids = set(CrmEmailAddress.objects.values_list('crm_id', flat=True))
        new_emails = []
        update_emails = []

        for row in rows:
            crm_id = row['id']
            ea_data = dict(
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
            if crm_id in existing_ids:
                if self.force or self.update:
                    update_emails.append((crm_id, ea_data))
            else:
                new_emails.append(CrmEmailAddress(crm_id=crm_id, **ea_data))

        created = 0
        for i in range(0, len(new_emails), CHUNK):
            with transaction.atomic():
                CrmEmailAddress.objects.bulk_create(new_emails[i:i+CHUNK], ignore_conflicts=True)
            created += len(new_emails[i:i+CHUNK])
            self.stdout.write(f'  ... {created}/{len(new_emails)} Emails neu')

        updated = 0
        for crm_id, data in update_emails:
            CrmEmailAddress.objects.filter(crm_id=crm_id).update(**data)
            updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'  EmailAddress -> neu: {created}  aktualisiert: {updated}  bereits vorhanden: {len(existing_ids)}'
        ))

    # ── Relations ─────────────────────────────────────────────────────────────

    def _sync_relations(self):
        self._sync_email_bean_rel_contacts()
        self._sync_email_bean_rel_accounts()
        self._sync_account_contacts()
        self._sync_phones()

    def _sync_email_bean_rel_contacts(self):
        self.stdout.write('\n-- Sync email_addr_bean_rel (Contacts) --')
        cur = self._cursor()
        sql = '''
            SELECT rel.id, rel.email_address_id, rel.bean_id, rel.bean_module,
                   rel.primary_address, rel.reply_to_address,
                   rel.date_created, rel.date_modified
            FROM email_addr_bean_rel rel
            WHERE rel.deleted = 0 AND rel.bean_module = 'Contacts'
        ''' + self._limit_clause()
        cur.execute(sql)
        rows = cur.fetchall()
        self.stdout.write(f'  MySQL: {len(rows)} Contact Bean-Relations')

        if self.dryrun:
            self.stdout.write(self.style.SUCCESS(f'  BeanRel Contacts -> neu: {len(rows)}  (dryrun)'))
            return

        known_email_ids   = set(CrmEmailAddress.objects.values_list('crm_id', flat=True))
        known_contact_ids = set(CrmContact.objects.values_list('crm_id', flat=True))
        existing_ids      = set(CrmEmailAddrBeanRel.objects.values_list('crm_id', flat=True))

        missing_email = missing_contact = 0
        new_rels = []

        for row in rows:
            crm_id       = row['id']
            email_crm_id = row['email_address_id']
            bean_id      = row['bean_id']

            if email_crm_id not in known_email_ids:
                missing_email += 1
                continue
            if bean_id not in known_contact_ids:
                missing_contact += 1
                continue
            if crm_id in existing_ids and not self.force:
                continue

            new_rels.append(CrmEmailAddrBeanRel(
                crm_id           = crm_id,
                email_address_id = email_crm_id,
                bean_id          = bean_id,
                bean_module      = row['bean_module'],
                primary_address  = bool(row['primary_address']),
                reply_to_address = bool(row['reply_to_address']),
                date_created     = row['date_created'],
                date_modified    = row['date_modified'],
            ))

        created = 0
        for i in range(0, len(new_rels), CHUNK):
            with transaction.atomic():
                CrmEmailAddrBeanRel.objects.bulk_create(new_rels[i:i+CHUNK], ignore_conflicts=True)
            created += len(new_rels[i:i+CHUNK])

        self.stdout.write(self.style.SUCCESS(f'  BeanRel Contacts -> neu: {created}'))
        if missing_email:
            self.stdout.write(self.style.WARNING(f'  {missing_email} uebersprungen - Email nicht in PG'))
        if missing_contact:
            self.stdout.write(self.style.WARNING(f'  {missing_contact} uebersprungen - Contact nicht in PG'))

    def _sync_email_bean_rel_accounts(self):
        self.stdout.write('\n-- Sync email_addr_bean_rel (Accounts) --')
        cur = self._cursor()
        sql = '''
            SELECT rel.id, rel.email_address_id, rel.bean_id, rel.bean_module,
                   rel.primary_address, rel.reply_to_address,
                   rel.date_created, rel.date_modified
            FROM email_addr_bean_rel rel
            WHERE rel.deleted = 0 AND rel.bean_module = 'Accounts'
        ''' + self._limit_clause()
        cur.execute(sql)
        rows = cur.fetchall()
        self.stdout.write(f'  MySQL: {len(rows)} Account Bean-Relations')

        if self.dryrun:
            self.stdout.write(self.style.SUCCESS(f'  BeanRel Accounts -> neu: {len(rows)}  (dryrun)'))
            return

        known_email_ids   = set(CrmEmailAddress.objects.values_list('crm_id', flat=True))
        known_account_ids = set(CrmAccount.objects.values_list('crm_id', flat=True))
        existing_ids      = set(CrmEmailAddrBeanRel.objects.values_list('crm_id', flat=True))

        missing_email = missing_account = 0
        new_rels = []

        for row in rows:
            crm_id       = row['id']
            email_crm_id = row['email_address_id']
            bean_id      = row['bean_id']

            if email_crm_id not in known_email_ids:
                missing_email += 1
                continue
            if bean_id not in known_account_ids:
                missing_account += 1
                continue
            if crm_id in existing_ids and not self.force:
                continue

            new_rels.append(CrmEmailAddrBeanRel(
                crm_id           = crm_id,
                email_address_id = email_crm_id,
                bean_id          = bean_id,
                bean_module      = row['bean_module'],
                primary_address  = bool(row['primary_address']),
                reply_to_address = bool(row['reply_to_address']),
                date_created     = row['date_created'],
                date_modified    = row['date_modified'],
            ))

        created = 0
        for i in range(0, len(new_rels), CHUNK):
            with transaction.atomic():
                CrmEmailAddrBeanRel.objects.bulk_create(new_rels[i:i+CHUNK], ignore_conflicts=True)
            created += len(new_rels[i:i+CHUNK])

        self.stdout.write(self.style.SUCCESS(f'  BeanRel Accounts -> neu: {created}'))
        if missing_email:
            self.stdout.write(self.style.WARNING(f'  {missing_email} uebersprungen - Email nicht in PG'))
        if missing_account:
            self.stdout.write(self.style.WARNING(f'  {missing_account} uebersprungen - Account nicht in PG'))

    def _sync_account_contacts(self):
        self.stdout.write('\n-- Sync accounts_contacts --')
        cur = self._cursor()
        sql = '''
            SELECT id, contact_id, account_id, date_modified
            FROM accounts_contacts WHERE deleted = 0
        ''' + self._limit_clause()
        cur.execute(sql)
        rows = cur.fetchall()
        self.stdout.write(f'  MySQL: {len(rows)} Account-Contact Verknuepfungen')

        if self.dryrun:
            self.stdout.write(self.style.SUCCESS(f'  AccountContacts -> neu: {len(rows)}  (dryrun)'))
            return

        known_contact_ids = set(CrmContact.objects.values_list('crm_id', flat=True))
        known_account_ids = set(CrmAccount.objects.values_list('crm_id', flat=True))
        existing_ids      = set(CrmAccountContacts.objects.values_list('crm_id', flat=True))

        missing = 0
        new_rels = []

        for row in rows:
            crm_id     = row['id']
            contact_id = row['contact_id']
            account_id = row['account_id']

            if contact_id not in known_contact_ids or account_id not in known_account_ids:
                missing += 1
                continue
            if crm_id in existing_ids and not self.force:
                continue

            new_rels.append(CrmAccountContacts(
                crm_id        = crm_id,
                contact_id    = contact_id,
                account_id    = account_id,
                date_modified = row['date_modified'],
            ))

        created = 0
        for i in range(0, len(new_rels), CHUNK):
            with transaction.atomic():
                CrmAccountContacts.objects.bulk_create(new_rels[i:i+CHUNK], ignore_conflicts=True)
            created += len(new_rels[i:i+CHUNK])

        self.stdout.write(self.style.SUCCESS(f'  AccountContacts -> neu: {created}'))
        if missing:
            self.stdout.write(self.style.WARNING(
                f'  {missing} uebersprungen - Contact oder Account nicht in PG'))

    # ── Phone Sync ───────────────────────────────────────────────────────────

    def _normalize_phone(self, nr):
        return normalize_phone(nr)

    def _sync_phones(self):
        self.stdout.write('\n-- Sync phones (Contacts + Accounts) --')
        if self.dryrun:
            self.stdout.write(self.style.SUCCESS('  Phones -> (dryrun)'))
            return

        CONTACT_FIELDS = ['phone_home', 'phone_mobile', 'phone_work', 'phone_other', 'phone_fax']
        ACCOUNT_FIELDS = ['phone_office', 'phone_alternate', 'phone_fax']

        # Bestehende Bean-Relations löschen bei --force
        if self.force:
            CrmPhoneBeanRel.objects.all().delete()
            CrmPhoneNumber.objects.all().delete()
            self.stdout.write('  Phones -> alle gelöscht (force)')

        existing_rels = set(
            CrmPhoneBeanRel.objects.values_list('bean_id', 'bean_module', 'field_name')
        )

        created_numbers = 0
        created_rels = 0

        # Contacts
        cur = self._cursor()
        cur.execute('SELECT id, phone_home, phone_mobile, phone_work, phone_other, phone_fax FROM contacts WHERE deleted=0' + self._limit_clause())
        for row in cur.fetchall():
            bean_id = row['id']
            for field in CONTACT_FIELDS:
                raw = row[field]
                if not raw or not raw.strip():
                    continue
                if (bean_id, 'Contacts', field) in existing_rels:
                    continue
                norm = self._normalize_phone(raw)
                phone = CrmPhoneNumber.objects.create(phone_raw=raw.strip(), phone_norm=norm)
                CrmPhoneBeanRel.objects.create(
                    phone=phone,
                    bean_id=bean_id,
                    bean_module='Contacts',
                    field_name=field,
                    is_primary=(field == 'phone_mobile'),
                )
                created_numbers += 1
                created_rels += 1

        # Accounts
        cur.execute('SELECT id, phone_office, phone_alternate, phone_fax FROM accounts WHERE deleted=0' + self._limit_clause())
        for row in cur.fetchall():
            bean_id = row['id']
            for field in ACCOUNT_FIELDS:
                raw = row[field]
                if not raw or not raw.strip():
                    continue
                if (bean_id, 'Accounts', field) in existing_rels:
                    continue
                norm = self._normalize_phone(raw)
                phone = CrmPhoneNumber.objects.create(phone_raw=raw.strip(), phone_norm=norm)
                CrmPhoneBeanRel.objects.create(
                    phone=phone,
                    bean_id=bean_id,
                    bean_module='Accounts',
                    field_name=field,
                    is_primary=(field == 'phone_office'),
                )
                created_numbers += 1
                created_rels += 1

        self.stdout.write(self.style.SUCCESS(
            f'  Phones -> {created_numbers} Nummern, {created_rels} Relationen angelegt'
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
