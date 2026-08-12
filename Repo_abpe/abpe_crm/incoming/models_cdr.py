"""
abpe_crm/models_cdr.py
Spiegel der Asterisk/Issabel CDR-Tabelle (asteriskcdrdb.cdr) in Postgres.

Die ersten 26 Felder sind 1:1 aus der PBX-Tabelle uebernommen (Feldnamen
bitgleich zu information_schema.COLUMNS, TABLE_NAME='cdr'). Danach folgen
unsere Zusatzspalten fuer Normalisierung, Kontakt-Aufloesung (Cache) und
Sync-Meta.

Wird in models.py via `from .models_cdr import *` eingebunden, damit Django
die Modelle bei makemigrations findet.
"""
from django.db import models


class CrmCdr(models.Model):
    # -- 1:1 aus asteriskcdrdb.cdr (26 Felder, NOT NULL + Default wie PBX) --
    calldate       = models.DateTimeField(db_index=True)
    clid           = models.CharField(max_length=80,  default='', blank=True)
    src            = models.CharField(max_length=80,  default='', blank=True)
    dst            = models.CharField(max_length=80,  default='', blank=True, db_index=True)
    dcontext       = models.CharField(max_length=80,  default='', blank=True)
    channel        = models.CharField(max_length=80,  default='', blank=True)
    dstchannel     = models.CharField(max_length=80,  default='', blank=True)
    lastapp        = models.CharField(max_length=80,  default='', blank=True)
    lastdata       = models.CharField(max_length=80,  default='', blank=True)
    duration       = models.IntegerField(default=0)
    billsec        = models.IntegerField(default=0)
    disposition    = models.CharField(max_length=45,  default='', blank=True, db_index=True)
    amaflags       = models.IntegerField(default=0)
    accountcode    = models.CharField(max_length=20,  default='', blank=True)
    uniqueid       = models.CharField(max_length=32,  unique=True, db_index=True)
    userfield      = models.CharField(max_length=255, default='', blank=True)
    did            = models.CharField(max_length=50,  default='', blank=True)
    recordingfile  = models.CharField(max_length=255, default='', blank=True)
    cnum           = models.CharField(max_length=80,  default='', blank=True)
    cnam           = models.CharField(max_length=80,  default='', blank=True)
    outbound_cnum  = models.CharField(max_length=80,  default='', blank=True)
    outbound_cnam  = models.CharField(max_length=80,  default='', blank=True)
    dst_cnam       = models.CharField(max_length=80,  default='', blank=True)
    linkedid       = models.CharField(max_length=32,  default='', blank=True, db_index=True)
    peeraccount    = models.CharField(max_length=80,  default='', blank=True)
    sequence       = models.IntegerField(default=0)

    # -- NEU: normalisierte Nummern (via apps.abpe_crm.services.normalize_phone_nr) --
    src_norm       = models.CharField(max_length=30, default='', blank=True, db_index=True)
    dst_norm       = models.CharField(max_length=30, default='', blank=True, db_index=True)

    # -- NEU: Richtung / eigene Nebenstelle --
    direction      = models.CharField(max_length=10, default='', blank=True, db_index=True)
    ext            = models.CharField(max_length=20, default='', blank=True, db_index=True)

    # -- NEU: aufgeloeste Gegenstelle (Cache, denormalisiert) --
    party_number     = models.CharField(max_length=30,  default='', blank=True)
    party_crm_id     = models.CharField(max_length=36,  blank=True, null=True, db_index=True)
    party_module     = models.CharField(max_length=10,  default='', blank=True)
    party_name       = models.CharField(max_length=150, default='', blank=True)
    match_confidence = models.CharField(max_length=12,  default='', blank=True, db_index=True)
    match_candidates = models.JSONField(default=list, blank=True)

    # -- NEU: Filter-Flags + Sync-Meta --
    is_system      = models.BooleanField(default=False, db_index=True)
    synced_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'CDR-Anruf'
        verbose_name_plural = 'CDR-Anrufe'
        ordering            = ['-calldate']
        indexes = [
            models.Index(fields=['party_crm_id', '-calldate']),
            models.Index(fields=['ext', '-calldate']),
            models.Index(fields=['linkedid']),
        ]

    def __str__(self):
        return f"{self.calldate} {self.src}->{self.dst} ({self.disposition})"
