"""
abpe_crm/models.py
SuiteCRM MySQL → Django PostgreSQL Sync Models
1:1 Abbild der SuiteCRM Tabellenstruktur + CrmContactNote + CrmDocument
"""
from django.db import models


# ============================================================
# 1. CrmContact  (← contacts)
# ============================================================

class CrmContact(models.Model):
    # SuiteCRM PK — wird als unique key behalten
    crm_id                  = models.CharField(max_length=36, unique=True, db_index=True)
    crm_date_entered        = models.DateTimeField(null=True, blank=True)
    crm_date_modified       = models.DateTimeField(null=True, blank=True)

    # Stammdaten
    salutation              = models.CharField(max_length=255, blank=True, null=True)
    first_name              = models.CharField(max_length=100, blank=True, null=True)
    last_name               = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    title                   = models.CharField(max_length=100, blank=True, null=True)
    department              = models.CharField(max_length=255, blank=True, null=True)
    do_not_call             = models.BooleanField(default=False, null=True)
    birthdate               = models.DateField(null=True, blank=True)
    photo                   = models.CharField(max_length=255, blank=True, null=True)
    description             = models.TextField(blank=True, null=True)

    # Telefon
    whatsapp_number         = models.CharField(max_length=100, blank=True, null=True)

    # Adresse (primär)
    primary_address_street      = models.CharField(max_length=150, blank=True, null=True)
    primary_address_city        = models.CharField(max_length=100, blank=True, null=True)
    primary_address_state       = models.CharField(max_length=100, blank=True, null=True)
    primary_address_postalcode  = models.CharField(max_length=20,  blank=True, null=True)
    primary_address_country     = models.CharField(max_length=255, blank=True, null=True)

    # Adresse (alternativ)
    alt_address_street          = models.CharField(max_length=150, blank=True, null=True)
    alt_address_city            = models.CharField(max_length=100, blank=True, null=True)
    alt_address_state           = models.CharField(max_length=100, blank=True, null=True)
    alt_address_postalcode      = models.CharField(max_length=20,  blank=True, null=True)
    alt_address_country         = models.CharField(max_length=255, blank=True, null=True)

    # Sekretariat
    assistant                   = models.CharField(max_length=75,  blank=True, null=True)
    assistant_phone             = models.CharField(max_length=100, blank=True, null=True)

    # Sync
    crm_synced_at               = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = 'CRM Kontakt'
        verbose_name_plural = 'CRM Kontakte'
        ordering            = ['last_name', 'first_name']
        indexes = [
            models.Index(fields=['last_name', 'first_name']),
            models.Index(fields=['crm_id']),
        ]

    def __str__(self):
        return f"{self.first_name or ''} {self.last_name or ''}".strip() or self.crm_id

    @property
    def full_name(self):
        return f"{self.first_name or ''} {self.last_name or ''}".strip()


# ============================================================
# 2. CrmContactCstm  (← contacts_cstm)
# ============================================================

class CrmContactCstm(models.Model):
    contact                     = models.OneToOneField(
                                    CrmContact, on_delete=models.CASCADE,
                                    related_name='cstm', to_field='crm_id',
                                    db_column='crm_id_c')
    # Berater-Felder
    gulp_id_c                   = models.CharField(max_length=16,  blank=True, null=True, db_index=True)
    gulp_last_updated_c         = models.DateField(null=True, blank=True)
    kontakt_typ_c               = models.CharField(max_length=255, blank=True, null=True, default='andere', db_index=True)
    kontakt_status_c            = models.CharField(max_length=255, blank=True, null=True, default='unbekannt', db_index=True)
    verfuegbar_ab_c             = models.DateField(null=True, blank=True, db_index=True)
    konditionen_c               = models.CharField(max_length=128, blank=True, null=True)
    skill_priority_c            = models.CharField(max_length=100, blank=True, null=True)
    einsatzort_stadt_c          = models.CharField(max_length=100, blank=True, null=True)
    einsatzort_region_c         = models.CharField(max_length=100, blank=True, null=True)
    einsatzort_plz_c            = models.CharField(max_length=20,  blank=True, null=True)

    # Profiltexte
    gulp_profil_c               = models.TextField(blank=True, null=True)
    ogo_description_c           = models.TextField(blank=True, null=True)
    freelancermap_profil_c      = models.TextField(blank=True, null=True)
    xing_profile_c              = models.TextField(blank=True, null=True)

    # Webprofile
    web_profil1_typ_c           = models.CharField(max_length=255, blank=True, null=True)
    web_profil1_location_c      = models.CharField(max_length=511, blank=True, null=True)
    web_profil2_typ_c           = models.CharField(max_length=255, blank=True, null=True)
    web_profil2_location_c      = models.CharField(max_length=511, blank=True, null=True)
    web_profil3_typ_c           = models.CharField(max_length=100, blank=True, null=True)
    web_profil3_location_c      = models.CharField(max_length=511, blank=True, null=True)
    web_profil4_typ_c           = models.CharField(max_length=100, blank=True, null=True)
    web_profil4_location_c      = models.CharField(max_length=511, blank=True, null=True)

    # Instant Messaging
    im1_typ_c                   = models.CharField(max_length=255, blank=True, null=True)
    im1_id_c                    = models.CharField(max_length=32,  blank=True, null=True)
    im2_typ_c                   = models.CharField(max_length=255, blank=True, null=True)
    im2_id_c                    = models.CharField(max_length=32,  blank=True, null=True)

    # Update-Timestamps
    emma_last_updated_c         = models.DateTimeField(null=True, blank=True)
    xing_last_updated_c         = models.DateTimeField(null=True, blank=True)
    freelancermap_last_updated_c = models.DateTimeField(null=True, blank=True)
    martha_last_updated_c       = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = 'CRM Kontakt Custom'
        verbose_name_plural = 'CRM Kontakte Custom'

    def __str__(self):
        return f"cstm: {self.contact}"


# ============================================================
# 3. CrmAccount  (← accounts)
# ============================================================

class CrmAccount(models.Model):
    crm_id                      = models.CharField(max_length=36, unique=True, db_index=True)
    crm_date_entered            = models.DateTimeField(null=True, blank=True)
    crm_date_modified           = models.DateTimeField(null=True, blank=True)

    # Stammdaten
    name                        = models.CharField(max_length=150, blank=True, null=True, db_index=True)
    account_type                = models.CharField(max_length=50,  blank=True, null=True)
    industry                    = models.CharField(max_length=50,  blank=True, null=True)
    annual_revenue              = models.CharField(max_length=100, blank=True, null=True)
    description                 = models.TextField(blank=True, null=True)
    rating                      = models.CharField(max_length=100, blank=True, null=True)
    ownership                   = models.CharField(max_length=100, blank=True, null=True)
    employees                   = models.CharField(max_length=10,  blank=True, null=True)
    ticker_symbol               = models.CharField(max_length=10,  blank=True, null=True)
    sic_code                    = models.CharField(max_length=10,  blank=True, null=True)
    website                     = models.CharField(max_length=255, blank=True, null=True)

    # Telefon

    # Rechnungsadresse
    billing_address_street      = models.CharField(max_length=150, blank=True, null=True)
    billing_address_city        = models.CharField(max_length=100, blank=True, null=True)
    billing_address_state       = models.CharField(max_length=100, blank=True, null=True)
    billing_address_postalcode  = models.CharField(max_length=20,  blank=True, null=True)
    billing_address_country     = models.CharField(max_length=255, blank=True, null=True)

    # Lieferadresse
    shipping_address_street     = models.CharField(max_length=150, blank=True, null=True)
    shipping_address_city       = models.CharField(max_length=100, blank=True, null=True)
    shipping_address_state      = models.CharField(max_length=100, blank=True, null=True)
    shipping_address_postalcode = models.CharField(max_length=20,  blank=True, null=True)
    shipping_address_country    = models.CharField(max_length=255, blank=True, null=True)

    # Übergeordnete Firma
    parent_crm_id               = models.CharField(max_length=36, blank=True, null=True)

    # Sync
    crm_synced_at               = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = 'CRM Account'
        verbose_name_plural = 'CRM Accounts'
        ordering            = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['crm_id']),
        ]

    def __str__(self):
        return self.name or self.crm_id


# ============================================================
# 4. CrmAccountCstm  (← accounts_cstm)
# ============================================================

class CrmAccountCstm(models.Model):
    account                     = models.OneToOneField(
                                    CrmAccount, on_delete=models.CASCADE,
                                    related_name='cstm', to_field='crm_id',
                                    db_column='crm_id_c')
    account_status_c            = models.CharField(max_length=255, blank=True, null=True, default='unbekannt')
    kunden_nummer_c             = models.CharField(max_length=32,  blank=True, null=True)

    class Meta:
        verbose_name        = 'CRM Account Custom'
        verbose_name_plural = 'CRM Accounts Custom'

    def __str__(self):
        return f"cstm: {self.account}"


# ============================================================
# 5. CrmAccountContacts  (← accounts_contacts)
# ============================================================

class CrmAccountContacts(models.Model):
    crm_id          = models.CharField(max_length=36, unique=True, db_index=True)
    contact         = models.ForeignKey(CrmContact, on_delete=models.CASCADE,
                        related_name='account_links', to_field='crm_id',
                        null=True, blank=True)
    account         = models.ForeignKey(CrmAccount, on_delete=models.CASCADE,
                        related_name='contact_links', to_field='crm_id',
                        null=True, blank=True)
    date_modified   = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = 'CRM Account-Kontakt Verknüpfung'
        verbose_name_plural = 'CRM Account-Kontakt Verknüpfungen'
        unique_together     = [['contact', 'account']]

    def __str__(self):
        return f"{self.account} ↔ {self.contact}"


# ============================================================
# 6. CrmEmailAddress  (← email_addresses)
# ============================================================

class CrmEmailAddress(models.Model):
    crm_id                  = models.CharField(max_length=36, unique=True, db_index=True)
    email_address           = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    email_address_caps      = models.CharField(max_length=255, blank=True, null=True)
    invalid_email           = models.BooleanField(default=False, null=True)
    opt_out                 = models.BooleanField(default=False, null=True)
    kampagne_ok             = models.BooleanField(default=False, verbose_name='Kampagne erlaubt')
    confirm_opt_in          = models.CharField(max_length=255, blank=True, null=True, default='not-opt-in')
    confirm_opt_in_date     = models.DateTimeField(null=True, blank=True)
    confirm_opt_in_sent_date = models.DateTimeField(null=True, blank=True)
    confirm_opt_in_fail_date = models.DateTimeField(null=True, blank=True)
    confirm_opt_in_token    = models.CharField(max_length=255, blank=True, null=True)
    date_created            = models.DateTimeField(null=True, blank=True)
    date_modified           = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = 'CRM E-Mail-Adresse'
        verbose_name_plural = 'CRM E-Mail-Adressen'

    def __str__(self):
        return self.email_address or self.crm_id


# ============================================================
# 7. CrmEmailAddrBeanRel  (← email_addr_bean_rel)
# ============================================================

class CrmEmailAddrBeanRel(models.Model):
    crm_id              = models.CharField(max_length=36, unique=True, db_index=True)
    email_address       = models.ForeignKey(CrmEmailAddress, on_delete=models.CASCADE,
                            related_name='bean_relations', to_field='crm_id',
                            null=True, blank=True)
    bean_id             = models.CharField(max_length=36, db_index=True)
    bean_module         = models.CharField(max_length=100, blank=True, null=True)
    primary_address     = models.BooleanField(default=False, null=True)
    reply_to_address    = models.BooleanField(default=False, null=True)
    date_created        = models.DateTimeField(null=True, blank=True)
    date_modified       = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = 'CRM E-Mail Bean Relation'
        verbose_name_plural = 'CRM E-Mail Bean Relationen'
        indexes = [
            models.Index(fields=['bean_id', 'bean_module']),
        ]

    def __str__(self):
        return f"{self.email_address} → {self.bean_module}:{self.bean_id}"


# ============================================================
# 8. CrmContactNote  (NEU — nur Django)
# ============================================================

class CrmContactNote(models.Model):
    NOTE_TYPE_CHOICES = [
        ('phone',   'Telefonnotiz'),
        ('email',   'E-Mail Notiz'),
        ('meeting', 'Besprechung'),
        ('general', 'Allgemein'),
    ]
    contact         = models.ForeignKey(CrmContact, on_delete=models.CASCADE,
                        related_name='notes', to_field='crm_id',
                        null=True, blank=True)
    account         = models.ForeignKey(CrmAccount, on_delete=models.CASCADE,
                        related_name='notes', to_field='crm_id',
                        null=True, blank=True)
    note_text       = models.TextField()
    note_type       = models.CharField(max_length=20, choices=NOTE_TYPE_CHOICES, default='phone')
    created_by      = models.CharField(max_length=100, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    # WAV-Notizen (NEU) — Referenz auf Quell-Voicemail, verhindert Doppel-
    # Dokumentation und behaelt den Whisper-Rohtext als Beleg.
    wavnote_mailbox   = models.CharField(max_length=10, blank=True, null=True, db_index=True)
    wavnote_msg_id    = models.CharField(max_length=20, blank=True, null=True)
    wavnote_raw_text  = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name        = 'CRM Notiz'
        verbose_name_plural = 'CRM Notizen'
        ordering            = ['-created_at']

    def __str__(self):
        return f"{self.note_type} — {self.created_at.date()}"


# ============================================================
# 9. CrmDocument  (NEU — nur Django)
# ============================================================

class CrmDocument(models.Model):
    DOC_TYPE_CHOICES = [
        ('cv',           'Lebenslauf / CV'),
        ('contract',     'Vertrag'),
        ('invoice',      'Rechnung'),
        ('offer',        'Angebot'),
        ('email',        'E-Mail Korrespondenz'),
        ('certificate',  'Zertifikat'),
        ('other',        'Sonstiges'),
    ]
    contact         = models.ForeignKey(CrmContact, on_delete=models.SET_NULL,
                        related_name='documents', to_field='crm_id',
                        null=True, blank=True)
    account         = models.ForeignKey(CrmAccount, on_delete=models.SET_NULL,
                        related_name='documents', to_field='crm_id',
                        null=True, blank=True)
    doc_type        = models.CharField(max_length=20, choices=DOC_TYPE_CHOICES, default='other', db_index=True)
    title           = models.CharField(max_length=255)
    file_path       = models.CharField(max_length=500, blank=True)
    file_size       = models.IntegerField(null=True, blank=True)
    mime_type       = models.CharField(max_length=100, blank=True)
    uploaded_by     = models.CharField(max_length=100, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'CRM Dokument'
        verbose_name_plural = 'CRM Dokumente'
        ordering            = ['-created_at']
        indexes = [
            models.Index(fields=['doc_type']),
            models.Index(fields=['contact']),
            models.Index(fields=['account']),
        ]

    def __str__(self):
        return f"{self.get_doc_type_display()}: {self.title}"


# ============================================================
# 10. CrmContactWebProfile  (NEU — unbegrenzt viele Web-Profile)
# ============================================================

class CrmContactWebProfile(models.Model):
    TYP_CHOICES = [
        ('xing',          'Xing'),
        ('linkedin',      'LinkedIn'),
        ('gulp',          'Gulp'),
        ('freelancermap', 'Freelancermap'),
        ('homepage',      'Homepage'),
        ('github',        'GitHub'),
        ('facebook',      'Facebook'),
        ('twitter',       'Twitter'),
        ('kununu',        'Kununu'),
        ('experteer',     'Experteer'),
        ('sonstiges',     'Sonstiges'),
    ]
    contact  = models.ForeignKey(CrmContact, on_delete=models.CASCADE,
                 related_name='web_profiles', to_field='crm_id')
    typ      = models.CharField(max_length=50, choices=TYP_CHOICES, default='sonstiges')
    url      = models.CharField(max_length=1024)
    sort     = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Web-Profil'
        verbose_name_plural = 'Web-Profile'
        ordering            = ['sort', 'typ']

    def __str__(self):
        return f"{self.typ}: {self.url}"


# ============================================================
# 12. CrmContactIM  (NEU — Instant Messaging / Messenger)
# ============================================================

class CrmContactIM(models.Model):
    TYP_CHOICES = [
        ('whatsapp',  'WhatsApp'),
        ('signal',    'Signal'),
        ('telegram',  'Telegram'),
        ('teams',     'MS Teams'),
        ('skype',     'Skype'),
        ('slack',     'Slack'),
        ('sonstiges', 'Sonstiges'),
    ]
    contact  = models.ForeignKey(CrmContact, on_delete=models.CASCADE,
                 related_name='im_contacts', to_field='crm_id')
    typ      = models.CharField(max_length=20, choices=TYP_CHOICES, default='whatsapp')
    wert     = models.CharField(max_length=255)  # Nummer oder ID
    sort     = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Messenger'
        verbose_name_plural = 'Messenger'
        ordering            = ['sort', 'typ']

    def __str__(self):
        return f"{self.typ}: {self.wert}"


# ============================================================
# 13. CrmPhoneNumber  (NEU — normalisierte Telefonnummern)
# ============================================================

class CrmPhoneNumber(models.Model):
    phone_raw       = models.CharField(max_length=100)
    phone_norm      = models.CharField(max_length=30, blank=True, db_index=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Telefonnummer'
        verbose_name_plural = 'Telefonnummern'

    def __str__(self):
        return self.phone_raw


# ============================================================
# 14. CrmPhoneBeanRel  (NEU — Telefon Bean Relation)
# ============================================================

class CrmPhoneBeanRel(models.Model):
    phone           = models.ForeignKey(CrmPhoneNumber, on_delete=models.CASCADE,
                        related_name='bean_relations')
    bean_id         = models.CharField(max_length=36, db_index=True)
    bean_module     = models.CharField(max_length=20)   # 'Contacts' oder 'Accounts'
    field_name      = models.CharField(max_length=30)   # phone_mobile, phone_office etc.
    label           = models.CharField(max_length=100, blank=True, null=True)  # z.B. 'Filiale München'
    is_primary      = models.BooleanField(default=False)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Telefon Bean Relation'
        verbose_name_plural = 'Telefon Bean Relationen'
        indexes = [
            models.Index(fields=['bean_id', 'bean_module']),
        ]
        unique_together = [['bean_id', 'bean_module', 'field_name']]

    def __str__(self):
        return f"{self.phone} → {self.bean_module}:{self.bean_id} ({self.field_name})"


# ============================================================
# CrmUserSettings  (NEU — CRM-spezifische User-Einstellungen)
# ============================================================

class CrmUserSettings(models.Model):
    """CRM-eigene Benutzereinstellungen — unabhängig von abpe_ui"""
    from django.contrib.auth.models import User as _User

    user = models.OneToOneField(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='crm_settings',
        verbose_name='Benutzer'
    )
    # ── UI ────────────────────────────────────────────────────
    language        = models.CharField(max_length=5,  default='de', verbose_name='Sprache')
    theme           = models.CharField(max_length=10, default='light', verbose_name='Theme')

    # ── Telefon / Issabel Asterisk ────────────────────────────
    phone_enabled       = models.BooleanField(default=False, verbose_name='Telefon aktiv')
    phone_extension     = models.CharField(max_length=20,  blank=True, default='', verbose_name='Durchwahl')
    phone_pin           = models.CharField(max_length=20,  blank=True, default='', verbose_name='PIN')
    phone_display_name  = models.CharField(max_length=100, blank=True, default='', verbose_name='Anzeigename')
    phone_webdial_url   = models.CharField(max_length=200, blank=True, default='http://172.20.3.120/cgi-bin/webdial.cgi', verbose_name='Webdial URL')
    phone_context       = models.CharField(max_length=50,  blank=True, default='from-internal', verbose_name='Asterisk Context')
    phone_timeout       = models.IntegerField(default=10,  verbose_name='Timeout (Sek)')
    phone_int_prefix    = models.CharField(max_length=5,   blank=True, default='00', verbose_name='Intl. Prefix')
    phone_pre           = models.CharField(max_length=5,   blank=True, default='',  verbose_name='Amtsvorwahl Prefix')
    softphone_ws         = models.CharField(max_length=200, blank=True, default='wss://pbx.win.abcona.info:8089/ws', verbose_name='Softphone WebSocket URL')
    softphone_vm_ext     = models.CharField(max_length=20,  blank=True, default='', verbose_name='Voicemail Nebenstelle')
    softphone_dnd_ext    = models.CharField(max_length=20,  blank=True, default='', verbose_name='DND Nebenstelle')
    softphone_fwd_target = models.CharField(max_length=50,  blank=True, default='', verbose_name='Weiterleitungsziel')
    softphone_speed_dials = models.JSONField(default=list, blank=True, verbose_name='Schnellwahltasten')
    softphone_status_exts = models.CharField(max_length=200, blank=True, default='', verbose_name='Überwachte Extensions')

    favoriten_berater = models.JSONField(default=list, blank=True, verbose_name='Favoriten (Berater)')
    favoriten_kunden  = models.JSONField(default=list, blank=True, verbose_name='Favoriten (Kunden)')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'CRM Benutzereinstellungen'
        verbose_name_plural = 'CRM Benutzereinstellungen'

    def __str__(self):
        return f"{self.user.username} — CRM Settings"
# wird nach phone_pre ergänzt — softphone_ws Feld



# ============================================================
# CrmCallRecording  (NEU — Anruf-Aufnahmen, Zuordnung lebt in DB)
# ============================================================

class CrmCallRecording(models.Model):
    """Anruf-Aufnahme. Die WAV behält ihren Original-Namen (PBX = lokal),
    die Zuordnung zu Contact/Account ist eine DB-Spalte (jederzeit korrigierbar,
    ohne die Datei anzufassen). Siehe Archiv/Call_record_future_architecture_v1.md"""
    filename        = models.CharField(max_length=255, unique=True, db_index=True)
    pbx_path        = models.CharField(max_length=500)
    local_path      = models.CharField(max_length=500, blank=True, null=True)
    extension       = models.CharField(max_length=10, db_index=True)
    caller_number   = models.CharField(max_length=50, blank=True, null=True, db_index=True)

    # Zuordnung (Kern — in der DB, nie im Dateinamen)
    contact_crm_id  = models.CharField(max_length=36, blank=True, null=True, db_index=True)
    account_crm_id  = models.CharField(max_length=36, blank=True, null=True, db_index=True)
    subject         = models.CharField(max_length=255, blank=True, null=True)
    is_assigned     = models.BooleanField(default=False, db_index=True)
    is_private      = models.BooleanField(default=False)

    # Metadaten
    recorded_at     = models.DateTimeField(db_index=True)
    duration_sec    = models.IntegerField(null=True, blank=True)
    file_size       = models.BigIntegerField(null=True, blank=True)
    synced_at       = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Anruf-Aufnahme'
        verbose_name_plural = 'Anruf-Aufnahmen'
        ordering            = ['-recorded_at']
        indexes = [
            models.Index(fields=['contact_crm_id']),
            models.Index(fields=['account_crm_id']),
            models.Index(fields=['is_assigned', 'recorded_at']),
        ]

    def __str__(self):
        return f"{self.filename} ({self.recorded_at})"


class CrmExtensionOwner(models.Model):
    """Mapping Extension -> Person (CRM-Contact). Konfigurierbar, für Default-
    Zuordnung nicht-aufgelöster Aufnahmen. Kein Hardcoding."""
    extension      = models.CharField(max_length=10, unique=True, db_index=True)
    contact_crm_id = models.CharField(max_length=36, blank=True, null=True)
    label          = models.CharField(max_length=100, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Extension-Besitzer'
        verbose_name_plural = 'Extension-Besitzer'

    def __str__(self):
        return f"{self.extension} -> {self.label or self.contact_crm_id or '?'}"


# ── CDR-Spiegel (asteriskcdrdb.cdr) ──
from .models_cdr import *  # noqa: F401,F403,E402

# ============================================================
# CrmWavnoteStatus  (NEU — manuelle Archivierung von Voicemails
# ohne Notiz, unabhaengig von CrmContactNote)
# ============================================================

class CrmWavnoteStatus(models.Model):
    """Markiert eine Voicemail (mailbox+msg_id) als manuell archiviert/
    nicht relevant. Reine Markierung, kein Notiztext -> keine
    Elasticsearch-Indexierung. 'erledigt' = has_note ODER hier vorhanden."""
    mailbox     = models.CharField(max_length=10, db_index=True)
    msg_id      = models.CharField(max_length=20)
    archived_at = models.DateTimeField(auto_now_add=True)
    archived_by = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name        = 'WAV-Notiz Status'
        verbose_name_plural = 'WAV-Notiz Status'
        unique_together     = [['mailbox', 'msg_id']]

    def __str__(self):
        return f"{self.mailbox}/{self.msg_id} archiviert"

