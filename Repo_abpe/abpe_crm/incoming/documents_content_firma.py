# -*- coding: utf-8 -*-
"""
apps/abpe_crm/documents_content_firma.py
================================================================================
Elasticsearch-Index `content_firma` = FIRMEN (ein Eintrag = ein CrmAccount).

VOLLSTAENDIG: alle inhaltlichen Account-Felder + Custom (Status/Kundennummer)
+ beide Adressen (billing/shipping) + Kontaktwege (Mail/Telefon ueber Accounts)
+ ANSPRECHPARTNER (Namen der verknuepften Kontakte) + Notizen.

Weggelassen (rein technisch): id, crm_date_entered/modified, crm_synced_at.
crm_id ist DRIN (Referenz).

WICHTIG (verifiziert): CrmAccountCstm.account ist FK to_field='crm_id' (STRING).
Kontaktwege ueber bean_module="Accounts" (890 Mail, 1893 Telefon vorhanden).
Ansprechpartner ueber CrmAccountContacts (contact + account, 5009 Relationen).
================================================================================
"""

from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry

from .models import (
    CrmAccount, CrmAccountCstm, CrmAccountContacts, CrmContact,
    CrmEmailAddrBeanRel, CrmPhoneBeanRel, CrmContactNote,
)


@registry.register_document
class ContentAccountIndex(Document):
    kind = fields.KeywordField()
    crm_id = fields.KeywordField()

    name = fields.TextField(fields={"raw": fields.KeywordField()})
    account_type = fields.KeywordField()
    industry = fields.TextField()
    annual_revenue = fields.TextField()
    description = fields.TextField()
    rating = fields.TextField()
    ownership = fields.TextField()
    employees = fields.TextField()
    ticker_symbol = fields.KeywordField()
    sic_code = fields.KeywordField()
    website = fields.TextField(fields={"raw": fields.KeywordField()})

    # Rechnungsadresse
    billing_street = fields.TextField()
    billing_city = fields.TextField()
    billing_state = fields.TextField()
    billing_postalcode = fields.KeywordField()
    billing_country = fields.TextField()
    # Lieferadresse
    shipping_street = fields.TextField()
    shipping_city = fields.TextField()
    shipping_state = fields.TextField()
    shipping_postalcode = fields.KeywordField()
    shipping_country = fields.TextField()

    parent_crm_id = fields.KeywordField()

    # Custom
    account_status = fields.KeywordField()
    kunden_nummer = fields.KeywordField()

    # Kontaktwege
    emails = fields.TextField(fields={"raw": fields.KeywordField()})
    phones = fields.TextField(fields={"raw": fields.KeywordField()})

    # Ansprechpartner (Namen der verknuepften Kontakte)
    contacts = fields.TextField()
    contact_crm_ids = fields.KeywordField()

    notes = fields.TextField()

    class Index:
        name = "content_firma"
        settings = {"number_of_shards": 1, "number_of_replicas": 0}

    class Django:
        model = CrmAccount
        fields = []
        related_models = [CrmAccountCstm, CrmAccountContacts, CrmContactNote]

    def get_instances_from_related(self, related_instance):
        return getattr(related_instance, "account", None)

    def get_queryset(self):
        return super().get_queryset()

    # ---- Stammdaten ----
    def prepare_kind(self, o): return "firma"
    def prepare_crm_id(self, o): return o.crm_id
    def prepare_name(self, o): return o.name or ""
    def prepare_account_type(self, o): return o.account_type or ""
    def prepare_industry(self, o): return o.industry or ""
    def prepare_annual_revenue(self, o): return str(o.annual_revenue or "")
    def prepare_description(self, o): return o.description or ""
    def prepare_rating(self, o): return o.rating or ""
    def prepare_ownership(self, o): return o.ownership or ""
    def prepare_employees(self, o): return str(o.employees or "")
    def prepare_ticker_symbol(self, o): return o.ticker_symbol or ""
    def prepare_sic_code(self, o): return o.sic_code or ""
    def prepare_website(self, o): return o.website or ""

    def prepare_billing_street(self, o): return o.billing_address_street or ""
    def prepare_billing_city(self, o): return o.billing_address_city or ""
    def prepare_billing_state(self, o): return o.billing_address_state or ""
    def prepare_billing_postalcode(self, o): return o.billing_address_postalcode or ""
    def prepare_billing_country(self, o): return o.billing_address_country or ""
    def prepare_shipping_street(self, o): return o.shipping_address_street or ""
    def prepare_shipping_city(self, o): return o.shipping_address_city or ""
    def prepare_shipping_state(self, o): return o.shipping_address_state or ""
    def prepare_shipping_postalcode(self, o): return o.shipping_address_postalcode or ""
    def prepare_shipping_country(self, o): return o.shipping_address_country or ""
    def prepare_parent_crm_id(self, o): return o.parent_crm_id or ""

    # ---- Custom (ueber crm_id!) ----
    def _cstm(self, o):
        return CrmAccountCstm.objects.filter(account_id=o.crm_id).first()

    def prepare_account_status(self, o):
        c = self._cstm(o); return (c.account_status_c or "") if c else ""
    def prepare_kunden_nummer(self, o):
        c = self._cstm(o); return (c.kunden_nummer_c or "") if c else ""

    # ---- Kontaktwege (bean_module="Accounts") ----
    def prepare_emails(self, o):
        rels = CrmEmailAddrBeanRel.objects.filter(
            bean_id=o.crm_id, bean_module="Accounts").select_related("email_address")
        out = []
        for r in rels:
            ea = getattr(r, "email_address", None)
            addr = getattr(ea, "email_address", None) if ea else None
            if addr:
                out.append(addr)
        return out

    def prepare_phones(self, o):
        rels = CrmPhoneBeanRel.objects.filter(
            bean_id=o.crm_id, bean_module="Accounts").select_related("phone")
        out = []
        for r in rels:
            ph = getattr(r, "phone", None)
            if ph:
                for v in (getattr(ph, "phone_norm", None), getattr(ph, "phone_raw", None)):
                    if v and v not in out:
                        out.append(v)
        return out

    # ---- Ansprechpartner (verknuepfte Kontakte) ----
    def _linked_contacts(self, o):
        rels = CrmAccountContacts.objects.filter(account_id=o.crm_id)
        ids = [r.contact_id for r in rels if r.contact_id]
        return ids

    def prepare_contacts(self, o):
        ids = self._linked_contacts(o)
        names = []
        for c in CrmContact.objects.filter(crm_id__in=ids):
            nm = " ".join(p for p in (c.first_name, c.last_name) if p).strip()
            if nm:
                names.append(nm)
        return names

    def prepare_contact_crm_ids(self, o):
        return self._linked_contacts(o)

    def prepare_notes(self, o):
        return [n.note_text for n in
                CrmContactNote.objects.filter(account_id=o.crm_id) if n.note_text]

