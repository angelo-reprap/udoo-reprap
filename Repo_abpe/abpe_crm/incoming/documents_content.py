# -*- coding: utf-8 -*-
"""
apps/abpe_crm/documents_content.py
================================================================================
Elasticsearch-Index `content` = PERSONEN (ein Eintrag = ein CrmContact).

VOLLSTAENDIG: alle inhaltlichen Contact-Felder + Custom-Profiltexte
(ogo/gulp/freelancermap) + Adressen + Assistenz + Geburtstag + Kontaktwege
+ Web-URLs + Notizen.

Weggelassen (rein technisch): id, crm_date_entered/modified, crm_synced_at, photo.
crm_id ist DRIN (Referenz fuer URLs/Verknuepfung, z.B. Namazu).

WICHTIG (verifiziert): CrmContactCstm.contact ist FK to_field='crm_id' (STRING).
Zugriff auf Custom-Felder daher IMMER ueber o.crm_id, nie o.id.

birthdate ist ein echtes date -> ermoeglicht spaeter Geburtstags-Dashboard
(wer hat heute/morgen Geburtstag, Jahr egal).
================================================================================
"""

from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry

from .models import (
    CrmContact, CrmContactCstm, CrmAccountContacts,
    CrmEmailAddrBeanRel, CrmPhoneBeanRel, CrmContactWebProfile,
    CrmContactNote,
)


@registry.register_document
class ContentPersonIndex(Document):
    kind = fields.KeywordField()
    crm_id = fields.KeywordField()          # Referenz fuer URLs/Verknuepfung

    # Name / Anrede / Titel
    salutation = fields.KeywordField()      # Herr/Frau/... -> filterbar
    first_name = fields.TextField()
    last_name = fields.TextField()
    name = fields.TextField(fields={"raw": fields.KeywordField()})  # kombiniert
    title = fields.TextField()
    department = fields.TextField()
    do_not_call = fields.BooleanField()

    # Geburtstag (fuer Dashboard)
    birthdate = fields.DateField()
    birth_day = fields.IntegerField()       # Tag  (1-31) fuer schnelle Abfrage
    birth_month = fields.IntegerField()     # Monat (1-12)

    description = fields.TextField()
    whatsapp_number = fields.TextField(fields={"raw": fields.KeywordField()})

    # Primaeradresse
    address_street = fields.TextField()
    city = fields.TextField()
    state = fields.TextField()
    postalcode = fields.KeywordField()
    country = fields.TextField()
    # Zweitadresse (kann Firmenanschrift sein)
    alt_address_street = fields.TextField()
    alt_city = fields.TextField()
    alt_state = fields.TextField()
    alt_postalcode = fields.KeywordField()
    alt_country = fields.TextField()

    # Assistenz
    assistant = fields.TextField()
    assistant_phone = fields.TextField(fields={"raw": fields.KeywordField()})

    # Profiltexte (der Schatz)
    ogo = fields.TextField()
    gulp = fields.TextField()
    freelancermap = fields.TextField()

    # CRM-Custom Steuerfelder
    kontakt_typ = fields.KeywordField()
    kontakt_status = fields.KeywordField()
    einsatzort = fields.TextField()
    verfuegbar_ab = fields.DateField()
    konditionen = fields.TextField()
    stundensatz = fields.FloatField()   # aus konditionen_c extrahiert (Plausibilitaet 10-500)

    # Kontaktwege
    emails = fields.TextField(fields={"raw": fields.KeywordField()})
    phones = fields.TextField(fields={"raw": fields.KeywordField()})
    web_urls = fields.TextField()

    # Firma-Verknuepfung (Ansprechpartner-Kennzeichen)
    company = fields.TextField(fields={"raw": fields.KeywordField()})
    account_crm_ids = fields.KeywordField()
    is_ansprechpartner = fields.BooleanField()

    notes = fields.TextField()

    class Index:
        name = "content"
        settings = {"number_of_shards": 1, "number_of_replicas": 0}

    class Django:
        model = CrmContact
        fields = []
        related_models = [CrmContactCstm, CrmContactWebProfile, CrmContactNote, CrmAccountContacts]

    def get_instances_from_related(self, related_instance):
        return getattr(related_instance, "contact", None)

    def get_queryset(self):
        return super().get_queryset()

    # ---- Stammdaten ----
    def prepare_kind(self, o): return "person"
    def prepare_crm_id(self, o): return o.crm_id
    def prepare_salutation(self, o): return o.salutation or ""
    def prepare_first_name(self, o): return o.first_name or ""
    def prepare_last_name(self, o): return o.last_name or ""
    def prepare_name(self, o):
        return " ".join(p for p in (o.first_name, o.last_name) if p).strip()
    def prepare_title(self, o): return o.title or ""
    def prepare_department(self, o): return o.department or ""
    def prepare_do_not_call(self, o): return bool(o.do_not_call)
    def prepare_description(self, o): return o.description or ""
    def prepare_whatsapp_number(self, o): return o.whatsapp_number or ""

    def prepare_birthdate(self, o): return o.birthdate
    def prepare_birth_day(self, o): return o.birthdate.day if o.birthdate else None
    def prepare_birth_month(self, o): return o.birthdate.month if o.birthdate else None

    # Primaeradresse
    def prepare_address_street(self, o): return o.primary_address_street or ""
    def prepare_city(self, o): return o.primary_address_city or ""
    def prepare_state(self, o): return o.primary_address_state or ""
    def prepare_postalcode(self, o): return o.primary_address_postalcode or ""
    def prepare_country(self, o): return o.primary_address_country or ""
    # Zweitadresse
    def prepare_alt_address_street(self, o): return o.alt_address_street or ""
    def prepare_alt_city(self, o): return o.alt_address_city or ""
    def prepare_alt_state(self, o): return o.alt_address_state or ""
    def prepare_alt_postalcode(self, o): return o.alt_address_postalcode or ""
    def prepare_alt_country(self, o): return o.alt_address_country or ""

    # Assistenz
    def prepare_assistant(self, o): return o.assistant or ""
    def prepare_assistant_phone(self, o): return o.assistant_phone or ""

    # ---- Custom-Felder (WICHTIG: ueber crm_id!) ----
    def _cstm(self, o):
        return CrmContactCstm.objects.filter(contact_id=o.crm_id).first()

    def prepare_ogo(self, o):
        c = self._cstm(o); return (c.ogo_description_c or "") if c else ""
    def prepare_gulp(self, o):
        c = self._cstm(o); return (c.gulp_profil_c or "") if c else ""
    def prepare_freelancermap(self, o):
        c = self._cstm(o); return (c.freelancermap_profil_c or "") if c else ""
    def prepare_kontakt_typ(self, o):
        c = self._cstm(o); return (c.kontakt_typ_c or "") if c else ""
    def prepare_kontakt_status(self, o):
        c = self._cstm(o); return (c.kontakt_status_c or "") if c else ""
    def prepare_einsatzort(self, o):
        c = self._cstm(o)
        if not c: return ""
        return " ".join(p for p in (c.einsatzort_stadt_c, c.einsatzort_region_c,
                                     c.einsatzort_plz_c) if p)
    def prepare_verfuegbar_ab(self, o):
        c = self._cstm(o); return c.verfuegbar_ab_c if c else None
    def prepare_konditionen(self, o):
        c = self._cstm(o); return (c.konditionen_c or "") if c else ""
    def prepare_stundensatz(self, o):
        c = self._cstm(o)
        if not c or not c.konditionen_c:
            return None
        import re
        for m in re.findall(r'\d{1,3}(?:[.,]\d{1,2})?', c.konditionen_c):
            val = float(m.replace(',', '.'))
            if 10 <= val <= 500:
                return val
        return None

    # ---- Kontaktwege ----
    def prepare_emails(self, o):
        rels = CrmEmailAddrBeanRel.objects.filter(
            bean_id=o.crm_id, bean_module="Contacts").select_related("email_address")
        out = []
        for r in rels:
            ea = getattr(r, "email_address", None)
            addr = getattr(ea, "email_address", None) if ea else None
            if addr:
                out.append(addr)
        return out

    def prepare_phones(self, o):
        rels = CrmPhoneBeanRel.objects.filter(
            bean_id=o.crm_id, bean_module="Contacts").select_related("phone")
        out = []
        for r in rels:
            ph = getattr(r, "phone", None)
            if ph:
                for v in (getattr(ph, "phone_norm", None), getattr(ph, "phone_raw", None)):
                    if v and v not in out:
                        out.append(v)
        return out

    def prepare_web_urls(self, o):
        return [w.url for w in
                CrmContactWebProfile.objects.filter(contact_id=o.crm_id) if w.url]

    # ---- Firma-Verknuepfung (Ansprechpartner) ----
    def _linked_accounts(self, o):
        return list(CrmAccountContacts.objects.filter(
            contact_id=o.crm_id).select_related("account"))

    def prepare_company(self, o):
        rels = self._linked_accounts(o)
        return [r.account.name for r in rels if r.account and r.account.name]

    def prepare_account_crm_ids(self, o):
        rels = self._linked_accounts(o)
        return [r.account_id for r in rels if r.account_id]

    def prepare_is_ansprechpartner(self, o):
        return bool(self._linked_accounts(o))

    def prepare_notes(self, o):
        return [n.note_text for n in
                CrmContactNote.objects.filter(contact_id=o.crm_id) if n.note_text]

