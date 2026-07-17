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
    phone_home              = models.CharField(max_length=100, blank=True, null=True)
    phone_mobile            = models.CharField(max_length=100, blank=True, null=True)
    phone_work              = models.CharField(max_length=100, blank=True, null=True)
    phone_other             = models.CharField(max_length=100, blank=True, null=True)
    phone_fax               = models.CharField(max_length=100, blank=True, null=True)
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
    phone_office                = models.CharField(max_length=100, blank=True, null=True)
    phone_alternate             = models.CharField(max_length=100, blank=True, null=True)
    phone_fax                   = models.CharField(max_length=100, blank=True, null=True)

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
