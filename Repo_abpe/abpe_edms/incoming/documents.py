# -*- coding: utf-8 -*-
"""
apps/abpe_edms/documents.py
================================================================================
Elasticsearch-Index `abpe_dms` für die EDMS-Gesamtsuche.

WICHTIG zum Index-Namen:
  In den Settings ist ELASTICSEARCH_DSL_INDEX_PREFIX = 'abpe_' gesetzt.
  Wir nennen den Index hier 'dms' -> die Library macht daraus 'abpe_dms'.
  NICHT 'abpe_dms' schreiben, sonst wird 'abpe_abpe_dms'.

Designentscheidung: DENORMALISIEREN.
  Owner-Stammdaten (Name/Stadt/Land/PLZ) werden über prepare_*-Methoden aus dem
  CRM aufgelöst und MIT in das Dokument geschrieben. So sucht ein einziges
  multi_match-Query über Titel + Volltext + Owner gleichzeitig (schnell, korrektes
  Ranking, universell erweiterbar um E-Mail/Telefon). ES kann nicht index-übergreifend
  joinen — deshalb die Kopie. Auffrischung über Reindex / Scanner.

Sync: Der RealTimeSignalProcessor ist aktiv -> jedes CrmDocument.save() landet
automatisch im Index. Änderungen an Ownern/Versionen ziehen das Dokument über
related_models + get_instances_from_related() automatisch nach. `dms_reindex`
ist für Erst-Befüllung und Reparatur.
================================================================================
"""

from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry

from .models import CrmDocument, CrmDocumentOwner, CrmDocumentVersion
from apps.abpe_crm.models import (
    CrmContact, CrmAccount, CrmEmailAddrBeanRel, CrmPhoneBeanRel,
    CrmContactNote,
)


@registry.register_document
class DmsDocumentIndex(Document):
    # --- Stammfelder (eigene, nicht aus model.fields) -----------------------
    uuid = fields.KeywordField()
    title = fields.TextField(
        fields={"raw": fields.KeywordField()}  # raw = exakte Sortierung nach Name
    )
    description = fields.TextField()
    content = fields.TextField()

    doctype_key = fields.KeywordField()
    doctype_label = fields.KeywordField()
    direction = fields.KeywordField()
    status = fields.KeywordField()
    source = fields.KeywordField()

    gewerk_nummer = fields.KeywordField()

    document_date = fields.DateField()
    valid_until = fields.DateField()
    retention_until = fields.DateField()

    needs_review = fields.BooleanField()
    in_trash = fields.BooleanField()

    # --- aktive Version (für Datei-Suche/-Sortierung) -----------------------
    filename = fields.TextField(fields={"raw": fields.KeywordField()})
    size_bytes = fields.LongField()
    mimetype = fields.KeywordField()

    # --- Owner (denormalisiert) ---------------------------------------------
    owner_crm_ids = fields.KeywordField()        # für exakte Owner-Filter
    owner_names = fields.TextField()             # Namen (Volltext-Suche)
    owner_cities = fields.TextField()
    owner_countries = fields.TextField()
    owner_postalcodes = fields.KeywordField()
    owner_emails = fields.TextField(fields={"raw": fields.KeywordField()})
    owner_phones = fields.TextField(fields={"raw": fields.KeywordField()})
    owner_notes = fields.TextField()  # Notizen des Owners (Telefonnotizen etc.)

    class Index:
        name = "dms"  # -> wird mit Prefix zu 'abpe_dms'
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 0,
        }

    class Django:
        model = CrmDocument
        # Felder, die direkt 1:1 aus dem Modell kommen, holen wir bewusst NICHT
        # über `fields`, weil wir fast alles via prepare_* aufbereiten (Owner-Join,
        # aktive Version). Das hält das Mapping unter unserer Kontrolle.
        fields = []
        # Ändert sich ein Owner oder eine Version, muss das zugehörige Dokument
        # neu indexiert werden (sonst veralten die denormalisierten Owner-Daten).
        related_models = [CrmDocumentOwner, CrmDocumentVersion, CrmContactNote]

    def get_instances_from_related(self, related_instance):
        """Sagt der Library, welches CrmDocument neu zu indexieren ist, wenn sich
        ein verknüpftes Owner-/Version-Objekt ändert."""
        if isinstance(related_instance, (CrmDocumentOwner, CrmDocumentVersion)):
            # related_instance.document kann None sein (z. B. beim Löschen) -> abfangen
            return getattr(related_instance, "document", None)
        return None

    # ------------------------------------------------------------------ prepares

    def prepare_uuid(self, instance):
        return str(instance.uuid)

    def prepare_doctype_key(self, instance):
        return instance.doctype.key if instance.doctype_id else None

    def prepare_doctype_label(self, instance):
        return instance.doctype.label if instance.doctype_id else None

    def prepare_gewerk_nummer(self, instance):
        return instance.gewerk.nummer if instance.gewerk_id else None

    def _active_version(self, instance):
        return (
            instance.versions.filter(is_active=True, in_trash=False)
            .order_by("-version_no")
            .first()
        )

    def prepare_filename(self, instance):
        v = self._active_version(instance)
        return v.filename if v else None

    def prepare_size_bytes(self, instance):
        v = self._active_version(instance)
        return v.size_bytes if v else None

    def prepare_mimetype(self, instance):
        v = self._active_version(instance)
        return v.mimetype if v else None

    # ---- Owner-Denormalisierung -------------------------------------------

    def _emails_for(self, crm_id, module):
        """E-Mail-Adressen einer crm_id über CrmEmailAddrBeanRel (FK auflösen)."""
        out = []
        rels = (
            CrmEmailAddrBeanRel.objects
            .filter(bean_id=crm_id, bean_module=module)
            .select_related("email_address")
        )
        for r in rels:
            ea = getattr(r, "email_address", None)
            addr = getattr(ea, "email_address", None) if ea else None
            if addr:
                out.append(addr)
        return out

    def _phones_for(self, crm_id, module):
        """Telefonnummern einer crm_id über CrmPhoneBeanRel (FK auflösen).
        Liefert sowohl die normalisierte als auch die Roh-Form für die Suche."""
        out = []
        rels = (
            CrmPhoneBeanRel.objects
            .filter(bean_id=crm_id, bean_module=module)
            .select_related("phone")
        )
        for r in rels:
            ph = getattr(r, "phone", None)
            if not ph:
                continue
            for val in (getattr(ph, "phone_norm", None), getattr(ph, "phone_raw", None)):
                if val and val not in out:
                    out.append(val)
        return out

    def _notes_for(self, crm_id, owner_type):
        """Notiz-Texte einer crm_id (contact->contact_id, account->account_id)."""
        if owner_type == "contact":
            qs = CrmContactNote.objects.filter(contact_id=crm_id)
        elif owner_type == "account":
            qs = CrmContactNote.objects.filter(account_id=crm_id)
        else:
            return []
        return [n.note_text for n in qs if n.note_text]

    def _owners(self, instance):
        """Löst alle Owner des Dokuments zu CRM-Stammdaten auf
        (Name/Stadt/Land/PLZ + E-Mail + Telefon)."""
        out = []
        for o in instance.owners.all():
            if o.owner_type == "contact":
                c = CrmContact.objects.filter(crm_id=o.owner_crm_id).first()
                if c:
                    name = " ".join(p for p in (c.last_name, c.first_name) if p).strip()
                    out.append({
                        "crm_id": o.owner_crm_id,
                        "name": name or o.owner_crm_id,
                        "city": c.primary_address_city or "",
                        "country": c.primary_address_country or "",
                        "plz": c.primary_address_postalcode or "",
                        "emails": self._emails_for(o.owner_crm_id, "Contacts"),
                        "phones": self._phones_for(o.owner_crm_id, "Contacts"),
                        "notes": self._notes_for(o.owner_crm_id, "contact"),
                    })
                    continue
            elif o.owner_type == "account":
                a = CrmAccount.objects.filter(crm_id=o.owner_crm_id).first()
                if a:
                    out.append({
                        "crm_id": o.owner_crm_id,
                        "name": a.name or o.owner_crm_id,
                        "city": a.billing_address_city or "",
                        "country": a.billing_address_country or "",
                        "plz": a.billing_address_postalcode or "",
                        "emails": self._emails_for(o.owner_crm_id, "Accounts"),
                        "phones": self._phones_for(o.owner_crm_id, "Accounts"),
                        "notes": self._notes_for(o.owner_crm_id, "account"),
                    })
                    continue
            # Fallback: Owner ohne auflösbaren CRM-Datensatz
            out.append({
                "crm_id": o.owner_crm_id, "name": o.owner_crm_id,
                "city": "", "country": "", "plz": "", "emails": [], "phones": [], "notes": [],
            })
        return out

    def prepare_owner_crm_ids(self, instance):
        return [o["crm_id"] for o in self._owners(instance)]

    def prepare_owner_names(self, instance):
        return [o["name"] for o in self._owners(instance) if o["name"]]

    def prepare_owner_cities(self, instance):
        return [o["city"] for o in self._owners(instance) if o["city"]]

    def prepare_owner_countries(self, instance):
        return [o["country"] for o in self._owners(instance) if o["country"]]

    def prepare_owner_postalcodes(self, instance):
        return [o["plz"] for o in self._owners(instance) if o["plz"]]

    def prepare_owner_emails(self, instance):
        vals = []
        for o in self._owners(instance):
            vals.extend(o.get("emails", []))
        return vals

    def prepare_owner_phones(self, instance):
        vals = []
        for o in self._owners(instance):
            vals.extend(o.get("phones", []))
        return vals

    def prepare_owner_notes(self, instance):
        vals = []
        for o in self._owners(instance):
            vals.extend(o.get("notes", []))
        return vals

    # Für effizientes Reindexieren: Querysets mit den nötigen Relationen
    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("doctype", "gewerk")
            .prefetch_related("owners", "versions")
        )

