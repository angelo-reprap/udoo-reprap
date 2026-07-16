# -*- coding: utf-8 -*-
"""
apps/abpe_edms/views.py
================================================================================
EDMS JSON-API (v1, DB-basiert) — wird vom abpe_crm-Frontend per fetch konsumiert.

Auth: nutzt denselben Decorator wie das ganze CRM (login_or_token_required aus
apps.abpe_crm.views), damit der Schutz konsistent ist.

Diese erste Version geht direkt gegen die Datenbank — so siehst du sofort echte
JSON-Antworten, sobald du im Admin Testdokumente anlegst. Der schnelle
Elasticsearch-Suchpfad (documents.py) wird im nächsten Schritt davorgehängt;
die Endpunkt-Signaturen bleiben dabei gleich.

Endpunkte:
  GET /edms/api/search/                         Gesamtsuche + Filter + Sort + Paginierung
  GET /edms/api/akte/<owner_type>/<crm_id>/     Akte eines Owners, nach DocType gruppiert
  GET /edms/api/document/<uuid>/                Dokument-Detail inkl. Versionen
  GET /edms/api/inbox/                          Posteingang (needs_review)
  GET /edms/api/doctypes/                       DocType-Liste (für Filter-Dropdowns)
================================================================================
"""

import os
import json

from django.db.models import Count, Q, Prefetch
from django.http import JsonResponse, FileResponse, Http404
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

# DRF + Spectacular: macht die plain Views für Swagger/Redoc sichtbar.
# WICHTIG: DRF hat global DEFAULT_PERMISSION_CLASSES=[IsAuthenticated]. Wir setzen
# pro View Session- UND Token-Auth, damit sowohl Swagger ("Try it out") als auch
# die Token-curl-Tests funktionieren. login_or_token_required bleibt zusätzlich drauf.
from rest_framework.decorators import (
    api_view, authentication_classes, permission_classes,
)
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

# Gleicher Auth-Decorator wie im restlichen CRM
from apps.abpe_crm.views import login_or_token_required

from .models import (
    CrmDocument, CrmDocumentOwner, CrmDocumentVersion,
    DmsDocType, OwnerType, DocStatus, OwnerRole, EventType, DmsDocumentEvent,
)

# CRM-Modelle für die Owner-Auflösung (crm_id -> Anzeigename/Adresse)
from apps.abpe_crm.models import CrmContact, CrmAccount

# Elasticsearch-Index für die schnelle Gesamtsuche
from .documents import DmsDocumentIndex

# Storage-Service: löst Version -> absoluter Dateipfad auf dem Share auf
from .services import storage
from .services import preview as preview_svc


# Wiederverwendbare Auth-Dekoratoren (Reihenfolge: erst DRF, dann unser Decorator)
def _drf_get(view):
    """Bündelt die Standard-Dekoratoren für eine GET-API-View."""
    view = login_or_token_required(view)
    view = permission_classes([IsAuthenticated])(view)
    view = authentication_classes([SessionAuthentication, TokenAuthentication])(view)
    view = api_view(["GET"])(view)
    return view


def _drf_post(view):
    """Wie _drf_get, aber für POST (Mutationen). csrf_exempt, da Token-Auth bzw.
    DRF die CSRF-Behandlung übernimmt (gleiches Muster wie views_recording)."""
    view = csrf_exempt(view)
    view = login_or_token_required(view)
    view = permission_classes([IsAuthenticated])(view)
    view = authentication_classes([SessionAuthentication, TokenAuthentication])(view)
    view = api_view(["POST"])(view)
    return view


def _json_body(request):
    """Liest den JSON-Body robust (DRF hat request.data, sonst Fallback)."""
    data = getattr(request, "data", None)
    if isinstance(data, dict):
        return data
    try:
        return json.loads(request.body or "{}")
    except Exception:
        return {}


# Häufig genutzte Query-Parameter für die Schema-Doku
def _p(name, typ, desc, **kw):
    return OpenApiParameter(name=name, type=typ, location=OpenApiParameter.QUERY,
                            description=desc, **kw)


# =============================================================================
#  HILFSFUNKTIONEN
# =============================================================================

def _int(request, key, default, lo=None, hi=None):
    """Robustes Parsen eines GET-Integer-Parameters."""
    try:
        val = int(request.GET.get(key, default))
    except (TypeError, ValueError):
        val = default
    if lo is not None:
        val = max(lo, val)
    if hi is not None:
        val = min(hi, val)
    return val


def _resolve_owner(owner_type, crm_id):
    """crm_id -> Anzeigename + Kontext. Nutzt die ECHTEN CRM-Feldnamen."""
    if owner_type == OwnerType.CONTACT:
        c = CrmContact.objects.filter(crm_id=crm_id).first()
        if not c:
            return None
        name = " ".join(p for p in (c.last_name, c.first_name) if p).strip() \
            or (c.crm_id or "—")
        return {
            "crm_id": c.crm_id,
            "type": "contact",
            "name": name,
            "first_name": c.first_name or "",
            "last_name": c.last_name or "",
            "city": c.primary_address_city or "",
            "country": c.primary_address_country or "",
            "postalcode": c.primary_address_postalcode or "",
            "street": c.primary_address_street or "",
        }
    else:  # ACCOUNT
        a = CrmAccount.objects.filter(crm_id=crm_id).first()
        if not a:
            return None
        return {
            "crm_id": a.crm_id,
            "type": "account",
            "name": a.name or (a.crm_id or "—"),
            "city": a.billing_address_city or "",
            "country": a.billing_address_country or "",
            "postalcode": a.billing_address_postalcode or "",
            "street": a.billing_address_street or "",
        }


def _doc_brief(doc):
    """Kompakte Dokument-Darstellung für Listen/Treffer."""
    active = next((v for v in doc.versions.all() if v.is_active and not v.in_trash), None)
    return {
        "uuid": str(doc.uuid),
        "title": doc.title,
        "doctype": doc.doctype.key if doc.doctype_id else None,
        "doctype_label": doc.doctype.label if doc.doctype_id else None,
        "icon_class": doc.doctype.icon_class if doc.doctype_id else "crm-doc-other",
        "direction": doc.direction,
        "status": doc.status,
        "document_date": doc.document_date.isoformat() if doc.document_date else None,
        "valid_until": doc.valid_until.isoformat() if doc.valid_until else None,
        "retention_until": doc.retention_until.isoformat() if doc.retention_until else None,
        "needs_review": doc.needs_review,
        "in_trash": doc.in_trash,
        "gewerk": doc.gewerk.nummer if doc.gewerk_id else None,
        "filename": active.filename if active else None,
        "size_bytes": active.size_bytes if active else None,
        "version_no": active.version_no if active else None,
    }


def _base_qs(include_trash=False):
    """Basis-Queryset mit den nötigen Prefetches, ohne N+1."""
    qs = CrmDocument.objects.select_related("doctype", "gewerk").prefetch_related(
        Prefetch(
            "versions",
            queryset=CrmDocumentVersion.objects.order_by("-version_no"),
        ),
        "owners",
    )
    if not include_trash:
        qs = qs.filter(in_trash=False)
    return qs


# Erlaubte Sortier-Schlüssel -> ORM-Felder (DB-Fallback)
_SORT_MAP = {
    "datum": "-document_date",
    "datum_asc": "document_date",
    "name": "title",
    "name_desc": "-title",
    "groesse": "-versions__size_bytes",
    "datei": "versions__filename",
}

# Sortier-Schlüssel -> ES-Felder (raw-Unterfelder für exakte Sortierung)
_SORT_MAP_ES = {
    "datum": ("document_date", "desc"),
    "datum_asc": ("document_date", "asc"),
    "name": ("title.raw", "asc"),
    "name_desc": ("title.raw", "desc"),
    "groesse": ("size_bytes", "desc"),
    "datei": ("filename.raw", "asc"),
}

# Felder, über die die Gesamtsuche läuft (Name, Adresse, E-Mail, Telefon, Inhalt)
_ES_SEARCH_FIELDS = [
    "title^3", "content",
    "owner_names^2", "owner_emails^2", "owner_phones^2",
    "owner_cities", "owner_countries", "owner_postalcodes",
    "doctype_label", "gewerk_nummer", "filename",
]


def _es_hit_to_brief(hit):
    """Wandelt einen ES-Treffer in dasselbe JSON wie _doc_brief (DB) um."""
    g = lambda k, d=None: getattr(hit, k, d)
    return {
        "uuid": g("uuid"),
        "title": g("title"),
        "doctype": g("doctype_key"),
        "doctype_label": g("doctype_label"),
        "icon_class": _ICON_BY_DOCTYPE.get(g("doctype_key"), "crm-doc-other"),
        "direction": g("direction"),
        "status": g("status"),
        "document_date": g("document_date"),
        "valid_until": g("valid_until"),
        "retention_until": g("retention_until"),
        "needs_review": bool(g("needs_review")),
        "in_trash": bool(g("in_trash")),
        "gewerk": g("gewerk_nummer"),
        "filename": g("filename"),
        "size_bytes": g("size_bytes"),
        "version_no": None,  # nur im Detail-Endpoint relevant
    }


# Icon-Lookup einmal cachen (DocType-key -> icon_class), für ES-Treffer
_ICON_BY_DOCTYPE = {}


def _refresh_icon_cache():
    global _ICON_BY_DOCTYPE
    _ICON_BY_DOCTYPE = {
        d["key"]: d["icon_class"]
        for d in DmsDocType.objects.values("key", "icon_class")
    }


def _search_es(request):
    """Schnelle Gesamtsuche über Elasticsearch. Wirft bei ES-Problemen, damit
    der Aufrufer auf die DB-Variante zurückfallen kann."""
    if not _ICON_BY_DOCTYPE:
        _refresh_icon_cache()

    s = DmsDocumentIndex.search()

    # Archiv-/Trash-Filter
    trash = request.GET.get("trash") == "1"
    s = s.filter("term", in_trash=trash)
    # Status-Filter (z. B. status=archiviert für den Archiv-Reiter)
    status = request.GET.get("status")
    if status:
        s = s.filter("term", status=status)

    # Freitext über alle relevanten Felder.
    # Mehrere Strategien kombiniert (bool/should), damit auch E-Mail und Telefon
    # in beliebiger Schreibweise gefunden werden:
    #   1) multi_match (OR) über die analysierten Textfelder (Name, Ort, Label …)
    #   2) Wildcard-Teilstring auf die raw-Subfelder owner_emails.raw /
    #      owner_phones.raw / filename.raw — fängt 'am@abcona.de', Telefon-
    #      fragmente und Dateinamen unabhängig vom Analyzer.
    q = (request.GET.get("q") or "").strip()
    if q:
        from elasticsearch_dsl import Q as ESQ
        ql = q.lower()
        # Telefon-Suche toleranter: nur Ziffern vergleichen (Leerzeichen/+/0 raus)
        digits = "".join(ch for ch in q if ch.isdigit())
        shoulds = [
            ESQ("multi_match", query=q, fields=_ES_SEARCH_FIELDS,
                type="best_fields", operator="and"),
            ESQ("wildcard", **{"owner_emails.raw": {"value": f"*{ql}*"}}),
            ESQ("wildcard", **{"filename.raw": {"value": f"*{ql}*"}}),
        ]
        if digits:
            # Telefon: gespeicherte Formate enthalten Leerzeichen, daher Wildcard
            # auf raw mit den reinen Ziffern (matcht z. B. '...29292949')
            shoulds.append(ESQ("wildcard", **{"owner_phones.raw": {"value": f"*{digits}*"}}))
            shoulds.append(ESQ("wildcard", **{"owner_phones.raw": {"value": f"*{q}*"}}))
        s = s.query("bool", should=shoulds, minimum_should_match=1)

    # Vor-Filter
    doctype = request.GET.get("doctype")
    if doctype:
        s = s.filter("term", doctype_key=doctype)

    direction = request.GET.get("direction")
    if direction:
        s = s.filter("term", direction=direction)

    gewerk = request.GET.get("gewerk")
    if gewerk:
        s = s.filter("term", gewerk_nummer=gewerk)

    owner = request.GET.get("owner")
    if owner:
        s = s.filter("term", owner_crm_ids=owner)

    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    if date_from or date_to:
        rng = {}
        if date_from:
            rng["gte"] = date_from
        if date_to:
            rng["lte"] = date_to
        s = s.filter("range", document_date=rng)

    # Sortierung
    sort_key = request.GET.get("sort", "datum")
    field, order = _SORT_MAP_ES.get(sort_key, ("document_date", "desc"))
    s = s.sort({field: {"order": order, "missing": "_last"}})

    # Paginierung
    size = _int(request, "size", 10, lo=1, hi=100)
    page = _int(request, "page", 1, lo=1)
    start = (page - 1) * size
    s = s[start:start + size]
    s = s.extra(track_total_hits=True)   # exakte Gesamtzahl statt ES-Kappung bei 10.000

    response = s.execute()
    total = response.hits.total.value
    results = [_es_hit_to_brief(h) for h in response]

    return {
        "ok": True,
        "engine": "es",
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size if size else 1,
        "results": results,
    }


def _search_db(request):
    """DB-Fallback (icontains). Funktioniert auch ohne Elasticsearch, langsamer
    und ohne E-Mail/Telefon-Suche."""
    trash = request.GET.get("trash") == "1"
    qs = _base_qs(include_trash=trash)
    if trash:
        qs = qs.filter(in_trash=True)

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(description__icontains=q)
            | Q(content__icontains=q)
            | Q(owners__owner_crm_id__icontains=q)
        )

    doctype = request.GET.get("doctype")
    if doctype:
        qs = qs.filter(doctype__key=doctype)

    direction = request.GET.get("direction")
    if direction:
        qs = qs.filter(direction=direction)

    gewerk = request.GET.get("gewerk")
    if gewerk:
        qs = qs.filter(gewerk__nummer=gewerk)

    owner = request.GET.get("owner")
    owner_type = request.GET.get("owner_type")
    if owner:
        of = Q(owners__owner_crm_id=owner)
        if owner_type:
            of &= Q(owners__owner_type=owner_type)
        qs = qs.filter(of)

    date_from = request.GET.get("date_from")
    if date_from:
        qs = qs.filter(document_date__gte=date_from)
    date_to = request.GET.get("date_to")
    if date_to:
        qs = qs.filter(document_date__lte=date_to)

    sort = _SORT_MAP.get(request.GET.get("sort", "datum"), "-document_date")
    qs = qs.order_by(sort, "-created_at").distinct()

    size = _int(request, "size", 10, lo=1, hi=100)
    page = _int(request, "page", 1, lo=1)
    total = qs.count()
    start = (page - 1) * size
    docs = list(qs[start:start + size])

    return {
        "ok": True,
        "engine": "db",
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size if size else 1,
        "results": [_doc_brief(d) for d in docs],
    }


# =============================================================================
#  ENDPUNKTE
# =============================================================================

@extend_schema(
    summary="EDMS Gesamtsuche",
    description="Volltext-/Owner-Suche über Titel, Inhalt, Owner-Name, Stadt, "
                "Land, PLZ, E-Mail und Telefon. Primär Elasticsearch, DB-Fallback. "
                "Mit Vor-Filtern, Sortierung und Paginierung.",
    parameters=[
        _p("q", OpenApiTypes.STR, "Freitext über alle Felder"),
        _p("doctype", OpenApiTypes.STR, "DocType-key (z. B. vertrag, rechnung)"),
        _p("direction", OpenApiTypes.STR, "keine | eingang | ausgang"),
        _p("owner", OpenApiTypes.STR, "crm_id (exakter Owner-Filter)"),
        _p("owner_type", OpenApiTypes.STR, "contact | account (nur DB-Fallback)"),
        _p("gewerk", OpenApiTypes.STR, "Gewerk-Nummer"),
        _p("date_from", OpenApiTypes.DATE, "document_date >= (ISO)"),
        _p("date_to", OpenApiTypes.DATE, "document_date <= (ISO)"),
        _p("trash", OpenApiTypes.STR, "'1' = nur Archiv"),
        _p("sort", OpenApiTypes.STR, "datum|datum_asc|name|name_desc|groesse|datei"),
        _p("page", OpenApiTypes.INT, "Seite (Default 1)"),
        _p("size", OpenApiTypes.INT, "Treffer pro Seite: 5/10/20 (Default 10)"),
    ],
    responses={200: OpenApiTypes.OBJECT},
    tags=["EDMS"],
)
@_drf_get
def api_search(request):
    """Gesamtsuche über Titel/Inhalt/Owner (Name, Stadt, Land, PLZ, E-Mail,
    Telefon) + Vor-Filter + Sortierung + Paginierung. Primär Elasticsearch,
    bei ES-Problemen automatischer DB-Fallback."""
    try:
        payload = _search_es(request)
    except Exception as exc:
        # ES nicht erreichbar / Index fehlt -> Suche bleibt funktionsfähig
        payload = _search_db(request)
        payload["fallback_reason"] = str(exc)[:200]
    return JsonResponse(payload)


@extend_schema(
    summary="Akte eines Owners",
    description="Alle Dokumente eines Owners (Berater/Kunde), gruppiert nach "
                "DocType-Reitern, plus Archiv-Block. owner_type: contact|account.",
    parameters=[
        OpenApiParameter("owner_type", OpenApiTypes.STR, OpenApiParameter.PATH,
                         description="contact | account"),
        OpenApiParameter("crm_id", OpenApiTypes.STR, OpenApiParameter.PATH,
                         description="crm_id des Owners"),
        _p("trash", OpenApiTypes.STR, "'1' = Archiv mitliefern"),
    ],
    responses={200: OpenApiTypes.OBJECT},
    tags=["EDMS"],
)
@_drf_get
def api_akte(request, owner_type, crm_id):
    """Die Akte eines Owners, nach DocType gruppiert (Reiter-Struktur)."""
    if owner_type not in (OwnerType.CONTACT, OwnerType.ACCOUNT):
        return JsonResponse({"ok": False, "error": "owner_type ungültig"}, status=400)

    owner = _resolve_owner(owner_type, crm_id)
    if owner is None:
        return JsonResponse({"ok": False, "error": "Owner nicht gefunden"}, status=404)

    include_trash = request.GET.get("trash") == "1"
    qs = _base_qs(include_trash=True).filter(
        owners__owner_crm_id=crm_id,
        owners__owner_type=owner_type,
    ).distinct()

    # Nach DocType-Reitern gruppieren
    tabs = {}
    archive = []
    for doc in qs:
        brief = _doc_brief(doc)
        if doc.in_trash:
            archive.append(brief)
            continue
        key = doc.doctype.key if doc.doctype_id else "sonstiges"
        tabs.setdefault(key, []).append(brief)

    return JsonResponse({
        "ok": True,
        "owner": owner,
        "tabs": tabs,
        "archive": archive,
        "counts": {k: len(v) for k, v in tabs.items()},
        "archive_count": len(archive),
    })


@extend_schema(
    summary="Dokument-Detail",
    description="Vollständige Dokument-Information inkl. aller Versionen und "
                "aufgelöster Owner.",
    parameters=[
        OpenApiParameter("uuid", OpenApiTypes.UUID, OpenApiParameter.PATH,
                         description="UUID des Dokuments"),
    ],
    responses={200: OpenApiTypes.OBJECT},
    tags=["EDMS"],
)
@_drf_get
def api_document(request, uuid):
    """Dokument-Detail inkl. aller Versionen und Owner."""
    doc = _base_qs(include_trash=True).filter(uuid=uuid).first()
    if doc is None:
        return JsonResponse({"ok": False, "error": "Dokument nicht gefunden"}, status=404)

    owners = []
    for o in doc.owners.all():
        info = _resolve_owner(o.owner_type, o.owner_crm_id) or {
            "crm_id": o.owner_crm_id, "type": o.owner_type, "name": o.owner_crm_id,
        }
        info["role"] = o.role
        info["is_primary"] = o.is_primary
        owners.append(info)

    versions = [{
        "version_no": v.version_no,
        "volume": v.volume,
        "filename": v.filename,
        "relative_path": v.relative_path,
        "mimetype": v.mimetype,
        "size_bytes": v.size_bytes,
        "checksum": v.checksum,
        "is_active": v.is_active,
        "in_trash": v.in_trash,
        "comment": v.comment,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    } for v in doc.versions.all()]

    detail = _doc_brief(doc)
    active_v = doc.versions.filter(is_active=True).order_by("-version_no").first() \
        or doc.versions.order_by("-version_no").first()
    detail.update({
        "description": doc.description,
        "source": doc.source,
        "language": doc.language,
        "valid_from": doc.valid_from.isoformat() if doc.valid_from else None,
        "owners": owners,
        "versions": versions,
        "win_path": storage.win_path(active_v) if active_v else None,
        "unc_path": storage.unc_path(active_v) if active_v else None,
        "filename": active_v.filename if active_v else None,
    })
    return JsonResponse({"ok": True, "document": detail})


@extend_schema(
    summary="Posteingang",
    description="Dokumente, die noch zugeordnet/geprüft werden müssen (needs_review).",
    parameters=[
        _p("size", OpenApiTypes.INT, "max. Treffer (Default 20)"),
    ],
    responses={200: OpenApiTypes.OBJECT},
    tags=["EDMS"],
)
@_drf_get
def api_inbox(request):
    """Posteingang: Dokumente, die noch zugeordnet/geprüft werden müssen."""
    size = _int(request, "size", 20, lo=1, hi=100)
    qs = _base_qs().filter(needs_review=True).order_by("-created_at")
    total = qs.count()
    docs = list(qs[:size])
    return JsonResponse({
        "ok": True,
        "total": total,
        "results": [_doc_brief(d) for d in docs],
    })


@extend_schema(
    summary="Personen/Firmen mit Inhalten",
    description="Owner-Aggregation über Dokumente, Aufnahmen UND Mails. Eine Person "
                "erscheint, wenn sie mindestens eine dieser drei Inhaltsarten hat. "
                "Liefert pro Owner Name, Typ und Zählungen (docs/recs/mails).",
    parameters=[
        _p("q", OpenApiTypes.STR, "Freitext-Filter (Name/Stadt/E-Mail/…)"),
        _p("size", OpenApiTypes.INT, "max. Anzahl Owner (Default 200)"),
    ],
    responses={200: OpenApiTypes.OBJECT},
    tags=["EDMS"],
)
@_drf_get
def api_personen(request):
    """Owner-Aggregation über Dokumente + Aufnahmen + Mails."""
    import re as _re
    from elasticsearch_dsl import A

    size = _int(request, "size", 200, lo=1, hi=1000)
    q = (request.GET.get("q") or "").strip()

    # ── Sammelstruktur: crm_id -> {name, type, docs, recs, mails} ────────
    owners = {}

    def _ensure(crm_id, owner_type="contact"):
        if crm_id not in owners:
            owners[crm_id] = {"crm_id": crm_id, "owner_type": owner_type,
                              "name": None, "docs": 0, "recs": 0, "mails": 0}
        return owners[crm_id]

    # ── 1) Dokument-Owner (ES-Aggregation auf owner_crm_ids) ─────────────
    s = DmsDocumentIndex.search()
    s = s.filter("term", in_trash=False)
    if q:
        from elasticsearch_dsl import Q as ESQ
        ql = q.lower()
        digits = "".join(ch for ch in q if ch.isdigit())
        shoulds = [
            ESQ("multi_match", query=q, fields=_ES_SEARCH_FIELDS,
                type="best_fields", operator="and"),
            ESQ("wildcard", **{"owner_emails.raw": {"value": f"*{ql}*"}}),
            ESQ("wildcard", **{"filename.raw": {"value": f"*{ql}*"}}),
        ]
        if digits:
            shoulds.append(ESQ("wildcard", **{"owner_phones.raw": {"value": f"*{digits}*"}}))
            shoulds.append(ESQ("wildcard", **{"owner_phones.raw": {"value": f"*{q}*"}}))
        s = s.query("bool", should=shoulds, minimum_should_match=1)
    s = s[:0]
    s.aggs.bucket(
        "owners", A("terms", field="owner_crm_ids", size=size * 3,
                    order={"_count": "desc"})
    ).metric(
        "top", A("top_hits", size=1, _source=["owner_crm_ids", "owner_names"])
    )
    try:
        resp = s.execute()
        for b in getattr(resp.aggregations.owners, "buckets", []):
            crm_id = b.key
            o = _ensure(crm_id)
            o["docs"] = b.doc_count
            try:
                hit = b.top.hits.hits[0]["_source"]
                ids = list(hit.get("owner_crm_ids") or [])
                names = list(hit.get("owner_names") or [])
                if crm_id in ids:
                    idx = ids.index(crm_id)
                    if idx < len(names) and not o["name"]:
                        o["name"] = names[idx]
            except Exception:
                pass
    except Exception:
        pass

    # ── 2) Aufnahme-Owner (DB, Count) ───────────────────────────────────
    try:
        from apps.abpe_crm.models import CrmCallRecording
        from django.db.models import Count
        for r in (CrmCallRecording.objects
                  .exclude(contact_crm_id="").exclude(contact_crm_id=None)
                  .values("contact_crm_id").annotate(n=Count("id"))):
            o = _ensure(r["contact_crm_id"], "contact")
            o["recs"] = r["n"]
        for r in (CrmCallRecording.objects
                  .exclude(account_crm_id="").exclude(account_crm_id=None)
                  .values("account_crm_id").annotate(n=Count("id"))):
            o = _ensure(r["account_crm_id"], "account")
            o["recs"] = o["recs"] + r["n"]
    except Exception:
        pass

    # ── 3) Mail-Owner (umgekehrt: ES-Adress-Aggregation -> Owner-Map) ────
    try:
        from apps.abpe_crm.models import CrmEmailAddrBeanRel, CrmEmailAddress
        from elasticsearch import Elasticsearch

        # Adresse(lowercase) -> (bean_id, bean_module)
        rels = list(CrmEmailAddrBeanRel.objects.values(
            "email_address_id", "bean_id", "bean_module"))
        amap = dict(CrmEmailAddress.objects.values_list("crm_id", "email_address"))
        addr2owner = {}
        for r in rels:
            a = (amap.get(r["email_address_id"]) or "").strip().lower()
            if a:
                bm = (r.get("bean_module") or "Contacts")
                otype = "account" if bm == "Accounts" else "contact"
                addr2owner[a] = (r["bean_id"], otype)

        es = Elasticsearch(["http://localhost:9200"])
        rx = _re.compile(r"<([^>]+)>")
        # WICHTIG: nur from_addr ist keyword (aggregierbar). to_addr ist ein
        # text-Feld ohne keyword-Subfeld -> NICHT aggregierbar. from_addr genügt,
        # um alle Personen zu finden, die je gemailt haben (Absenderseite). Die
        # exakte Mailzahl pro Person liefert ohnehin api_person_mails (from+to).
        agg = es.search(index="abpe_emails", body={"size": 0, "aggs": {
            "from": {"terms": {"field": "from_addr", "size": 20000}},
        }})
        for b in agg["aggregations"]["from"]["buckets"]:
            m = rx.search(b["key"])
            addr = (m.group(1) if m else b["key"]).strip().lower()
            hit = addr2owner.get(addr)
            if hit:
                o = _ensure(hit[0], hit[1])
                o["mails"] = o["mails"] + b["doc_count"]
    except Exception:
        pass

    # ── Owner-Namen + Typ auflösen (für alle, die noch keinen Namen haben) ─
    people = []
    ql_words = q.lower().split() if q else []
    for crm_id, o in owners.items():
        info = _resolve_owner("contact", crm_id) or _resolve_owner("account", crm_id)
        if info:
            o["name"] = info["name"]
            o["owner_type"] = info["type"]
        if not o["name"]:
            o["name"] = crm_id
        total = o["docs"] + o["recs"] + o["mails"]
        # Bei Freitextsuche: behalte Owner, wenn ENTWEDER die Doc-Query ihn traf
        # (docs>0) ODER ALLE Suchwörter im Namen vorkommen (wortweise, Reihenfolge
        # egal -> "Angelo Malaguarnera" matcht "Malaguarnera Angelo").
        if ql_words:
            name_l = (o["name"] or "").lower()
            name_hit = all(w in name_l for w in ql_words)
            if o["docs"] == 0 and not name_hit:
                continue
        people.append({
            "crm_id": crm_id,
            "name": o["name"],
            "owner_type": o["owner_type"],
            "doc_count": o["docs"],
            "rec_count": o["recs"],
            "mail_count": o["mails"],
            "total_count": total,
        })

    # Sortierung: zuerst nach Gesamtzahl absteigend, dann Name.
    # Owner mit recs/mails aber ohne docs (z. B. Angelo) bleiben drin, weil
    # die Kappung erst NACH der Sortierung greift und sie bei kleiner total-Zahl
    # zwar hinten, aber innerhalb der size-Grenze landen (size ist großzügig).
    people.sort(key=lambda p: (-p["total_count"], (p["name"] or "").lower()))
    gesamt = len(people)              # echte Owner-Gesamtzahl VOR der Kappung
    people = people[:size]

    return JsonResponse({"ok": True, "total": gesamt, "results": people})


@extend_schema(
    summary="DocType-Liste",
    description="Alle Dokumenttypen mit Icon, Volume und Aufbewahrungsfrist "
                "(für Filter-Dropdowns im Frontend).",
    responses={200: OpenApiTypes.OBJECT},
    tags=["EDMS"],
)
@_drf_get
def api_doctypes(request):
    """DocType-Liste für Filter-Dropdowns im Frontend."""
    rows = DmsDocType.objects.order_by("sort_order", "label").values(
        "key", "label", "icon_class", "default_volume", "retention_years",
    )
    return JsonResponse({"ok": True, "doctypes": list(rows)})


@extend_schema(
    summary="Dokument-Datei abrufen",
    description="Liefert die Datei der aktiven Version eines Dokuments vom Share. "
                "Mit ?version=<n> eine bestimmte Version, mit ?download=1 als "
                "Download (Speichern-Dialog) statt Inline-Vorschau.",
    parameters=[
        OpenApiParameter("uuid", OpenApiTypes.UUID, OpenApiParameter.PATH,
                         description="UUID des Dokuments"),
        _p("version", OpenApiTypes.INT, "Versionsnummer (Default: aktive Version)"),
        _p("download", OpenApiTypes.STR, "'1' = als Datei herunterladen statt anzeigen"),
    ],
    responses={200: OpenApiTypes.BINARY},
    tags=["EDMS"],
)
@_drf_get
def api_file(request, uuid):
    """Streamt die Datei vom Share (Range-fähig für PDF-Viewer/Seeking)."""
    doc = get_object_or_404(CrmDocument, uuid=uuid)

    version_no = request.GET.get("version")
    if version_no:
        version = doc.versions.filter(version_no=version_no).first()
    else:
        version = doc.versions.filter(is_active=True).order_by("-version_no").first()

    if version is None:
        raise Http404("Keine Version vorhanden")

    abs_path = storage.absolute_path(version)
    if not abs_path or not os.path.exists(abs_path):
        raise Http404("Datei auf dem Share nicht gefunden")

    resp = FileResponse(open(abs_path, "rb"),
                        content_type=version.mimetype or "application/octet-stream")
    resp["Accept-Ranges"] = "bytes"
    disposition = "attachment" if request.GET.get("download") == "1" else "inline"
    # Dateiname sauber quoten (Umlaute/Leerzeichen)
    safe = (version.filename or "datei").replace('"', "")
    resp["Content-Disposition"] = f'{disposition}; filename="{safe}"'
    return resp


@extend_schema(
    summary="Dokument-Vorschau (PDF)",
    description="Liefert ein anzeigbares PDF der aktiven Version. PDF direkt, "
                "DOC/DOCX/RTF/ODT via LibreOffice konvertiert (SHA256-Cache). "
                "Nicht konvertierbare Formate (.msg, .xls, …) liefern HTTP 415 — "
                "das Frontend zeigt dann den Download/Outlook-Weg.",
    parameters=[OpenApiParameter("uuid", OpenApiTypes.UUID, OpenApiParameter.PATH)],
    responses={200: OpenApiTypes.BINARY, 415: OpenApiTypes.OBJECT},
    tags=["EDMS"],
)
@_drf_get
@xframe_options_sameorigin
def api_preview(request, uuid):
    """Vorschau-PDF (konvertiert bei Bedarf, gecacht)."""
    doc = get_object_or_404(CrmDocument, uuid=uuid)
    version = doc.versions.filter(is_active=True).order_by("-version_no").first() \
        or doc.versions.order_by("-version_no").first()
    if version is None:
        raise Http404("Keine Version vorhanden")

    kind = preview_svc.preview_kind(version)
    if kind == "download":
        # Kein Inline-Preview möglich (z. B. .msg, .xls)
        return JsonResponse(
            {"ok": False, "kind": "download",
             "filename": version.filename,
             "reason": "Kein Inline-Preview für dieses Format"},
            status=415)

    pdf_path = preview_svc.get_preview_pdf(version)
    if not pdf_path or not os.path.exists(pdf_path):
        return JsonResponse(
            {"ok": False, "kind": kind,
             "reason": "Vorschau konnte nicht erzeugt werden"},
            status=422)

    resp = FileResponse(open(pdf_path, "rb"), content_type="application/pdf")
    resp["Accept-Ranges"] = "bytes"
    base = os.path.splitext(version.filename or "vorschau")[0]
    resp["Content-Disposition"] = f'inline; filename="{base}.pdf"'
    return resp


# =============================================================================
#  SCHREIBENDE ENDPUNKTE (Mutationen) — POST, klein und einzeln testbar
# =============================================================================

@extend_schema(
    summary="Owner zuordnen",
    description="Weist einem Dokument einen Owner (Berater/Kunde) zu. Idempotent: "
                "ein bereits vorhandener Owner wird nicht doppelt angelegt. Setzt "
                "needs_review automatisch auf False, sobald ein Owner existiert.",
    parameters=[
        OpenApiParameter("uuid", OpenApiTypes.UUID, OpenApiParameter.PATH,
                         description="UUID des Dokuments"),
    ],
    request={"application/json": {
        "type": "object",
        "properties": {
            "owner_crm_id": {"type": "string"},
            "owner_type": {"type": "string", "enum": ["contact", "account"]},
            "role": {"type": "string", "enum": ["primaer", "geteilt", "kunde", "kopie"]},
            "is_primary": {"type": "boolean"},
        },
        "required": ["owner_crm_id", "owner_type"],
    }},
    responses={200: OpenApiTypes.OBJECT},
    tags=["EDMS"],
)
@_drf_post
def api_document_add_owner(request, uuid):
    """Fügt einem Dokument einen Owner hinzu (idempotent)."""
    doc = get_object_or_404(CrmDocument, uuid=uuid)
    body = _json_body(request)

    crm_id = (body.get("owner_crm_id") or "").strip()
    owner_type = (body.get("owner_type") or "").strip()
    if not crm_id or owner_type not in (OwnerType.CONTACT, OwnerType.ACCOUNT):
        return JsonResponse(
            {"ok": False, "error": "owner_crm_id und gültiger owner_type erforderlich"},
            status=400)

    role = body.get("role") or OwnerRole.PRIMAER
    valid_roles = {OwnerRole.PRIMAER, OwnerRole.GETEILT, OwnerRole.KUNDE, OwnerRole.KOPIE}
    if role not in valid_roles:
        role = OwnerRole.PRIMAER
    is_primary = bool(body.get("is_primary", role == OwnerRole.PRIMAER))

    # Prüfen, ob der CRM-Owner real existiert (sonst Tippfehler-Geister)
    if owner_type == OwnerType.CONTACT:
        exists = CrmContact.objects.filter(crm_id=crm_id).exists()
    else:
        exists = CrmAccount.objects.filter(crm_id=crm_id).exists()
    if not exists:
        return JsonResponse(
            {"ok": False, "error": f"Kein {owner_type} mit crm_id {crm_id} im CRM"},
            status=404)

    # Idempotent (unique_together ist leer -> selbst absichern)
    owner, created = CrmDocumentOwner.objects.get_or_create(
        document=doc, owner_crm_id=crm_id, owner_type=owner_type,
        defaults={"role": role, "is_primary": is_primary,
                  "added_by": request.user if request.user.is_authenticated else None},
    )
    if not created:
        # vorhandenen Owner ggf. aktualisieren
        owner.role = role
        owner.is_primary = is_primary
        owner.save(update_fields=["role", "is_primary"])

    # Wenn als primär markiert: andere primär-Flags zurücknehmen
    if is_primary:
        doc.owners.exclude(pk=owner.pk).filter(is_primary=True).update(is_primary=False)

    # Dokument aus dem Posteingang nehmen (hat jetzt einen Owner)
    if doc.needs_review:
        doc.needs_review = False
        doc.save(update_fields=["needs_review"])

    DmsDocumentEvent.objects.create(
        document=doc, document_uuid=doc.uuid,
        event_type=EventType.OWNER_GEAENDERT,
        actor=request.user if request.user.is_authenticated else None,
        actor_label="" if request.user.is_authenticated else "api",
        detail={"owner_crm_id": crm_id, "owner_type": owner_type,
                "role": role, "is_primary": is_primary, "created": created},
    )

    return JsonResponse({
        "ok": True,
        "created": created,
        "needs_review": doc.needs_review,
        "owner": {"crm_id": crm_id, "owner_type": owner_type,
                  "role": role, "is_primary": is_primary},
    })


def _event(doc, etype, request, **detail):
    """Kleiner Helfer: schreibt ein DmsDocumentEvent."""
    DmsDocumentEvent.objects.create(
        document=doc, document_uuid=doc.uuid, event_type=etype,
        actor=request.user if request.user.is_authenticated else None,
        actor_label="" if request.user.is_authenticated else "api",
        detail=detail,
    )


@extend_schema(
    summary="Dokument archivieren",
    description="Setzt status=archiviert (Dokument bleibt erhalten und sichtbar, "
                "nur als abgelegt markiert). NICHT der Papierkorb — GoBD-konform.",
    parameters=[OpenApiParameter("uuid", OpenApiTypes.UUID, OpenApiParameter.PATH)],
    responses={200: OpenApiTypes.OBJECT}, tags=["EDMS"],
)
@_drf_post
def api_document_archive(request, uuid):
    """status -> archiviert."""
    doc = get_object_or_404(CrmDocument, uuid=uuid)
    if doc.status == DocStatus.ARCHIVIERT:
        return JsonResponse({"ok": True, "status": doc.status, "changed": False})
    doc.status = DocStatus.ARCHIVIERT
    doc.save(update_fields=["status"])
    _event(doc, EventType.ARCHIVIERT, request)
    return JsonResponse({"ok": True, "status": doc.status, "changed": True})


@extend_schema(
    summary="Dokument wiederherstellen",
    description="Setzt ein archiviertes Dokument zurück auf status=gueltig.",
    parameters=[OpenApiParameter("uuid", OpenApiTypes.UUID, OpenApiParameter.PATH)],
    responses={200: OpenApiTypes.OBJECT}, tags=["EDMS"],
)
@_drf_post
def api_document_restore(request, uuid):
    """status archiviert -> gueltig."""
    doc = get_object_or_404(CrmDocument, uuid=uuid)
    if doc.status != DocStatus.ARCHIVIERT:
        return JsonResponse({"ok": True, "status": doc.status, "changed": False})
    doc.status = DocStatus.GUELTIG
    doc.save(update_fields=["status"])
    _event(doc, EventType.WIEDERHERGESTELLT, request)
    return JsonResponse({"ok": True, "status": doc.status, "changed": True})


@extend_schema(
    summary="Posteingang erledigt",
    description="Markiert ein Dokument als geprüft (needs_review=False), ohne dass "
                "ein Owner zugewiesen werden muss — für Fälle, wo bewusst kein Owner "
                "nötig ist (z. B. allgemeine Dokumente).",
    parameters=[OpenApiParameter("uuid", OpenApiTypes.UUID, OpenApiParameter.PATH)],
    responses={200: OpenApiTypes.OBJECT}, tags=["EDMS"],
)
@_drf_post
def api_document_review_done(request, uuid):
    """needs_review -> False (manuell als geprüft markiert)."""
    doc = get_object_or_404(CrmDocument, uuid=uuid)
    if not doc.needs_review:
        return JsonResponse({"ok": True, "needs_review": False, "changed": False})
    doc.needs_review = False
    doc.save(update_fields=["needs_review"])
    _event(doc, EventType.METADATEN, request, note="review_done")
    return JsonResponse({"ok": True, "needs_review": False, "changed": True})

# ─────────────────────────────────────────────────────────────────────
# Mails einer Person (Owner) — Mailbox-Mails aus dem ES-Index abpe_emails.
# Kette: crm_id (= bean_id) -> CrmEmailAddrBeanRel -> CrmEmailAddress
#        -> Suche in abpe_emails (match auf from_addr/to_addr, da voller Header)
# ─────────────────────────────────────────────────────────────────────
@extend_schema(
    summary="Mails einer Person",
    description="Alle Mailbox-Mails (ES-Index abpe_emails), bei denen eine "
                "E-Mail-Adresse der Person als Absender oder Empfänger vorkommt. "
                "Chronologisch, neueste zuerst.",
    parameters=[
        OpenApiParameter("crm_id", OpenApiTypes.STR, OpenApiParameter.PATH,
                         description="crm_id (bean_id) der Person/Firma"),
        _p("q", OpenApiTypes.STR, "Freitext-Filter über Betreff/Body"),
        _p("size", OpenApiTypes.INT, "max. Trefferzahl (Default 100)"),
    ],
    responses={200: OpenApiTypes.OBJECT},
    tags=["EDMS"],
)
@_drf_get
def api_person_mails(request, crm_id):
    """Mailbox-Mails einer Person, ermittelt über ihre CRM-E-Mail-Adressen."""
    from elasticsearch import Elasticsearch
    from apps.abpe_crm.models import CrmEmailAddrBeanRel, CrmEmailAddress

    # 1) E-Mail-Adressen der Person holen
    rels = CrmEmailAddrBeanRel.objects.filter(bean_id=crm_id)
    addr_ids = [r.email_address_id for r in rels]
    addresses = list(
        CrmEmailAddress.objects
        .filter(crm_id__in=addr_ids)
        .exclude(invalid_email=True)
        .values_list("email_address", flat=True)
    )
    if not addresses:
        return JsonResponse({
            "ok": True, "total": 0, "addresses": [], "results": [],
            "hint": "Keine E-Mail-Adresse zu dieser Person im CRM hinterlegt.",
        })

    # 2) In abpe_emails suchen (match, weil from/to den vollen Header enthalten)
    try:
        size = int(request.GET.get("size") or 100)
    except ValueError:
        size = 100
    size = max(1, min(size, 500))

    should = []
    for a in addresses:
        should.append({"match_phrase": {"from_addr": a}})
        should.append({"match_phrase": {"to_addr": a}})

    must = []
    q = (request.GET.get("q") or "").strip()
    if q:
        must.append({"multi_match": {
            "query": q, "fields": ["subject^2", "body"], "operator": "and",
        }})

    body = {
        "size": size,
        "query": {"bool": {
            "should": should,
            "minimum_should_match": 1,
            "must": must,
        }},
        "sort": [{"date": {"order": "desc"}}],
        "_source": ["subject", "from_addr", "to_addr", "date", "folder",
                    "account", "message_id", "uid", "has_attachments", "size_bytes"],
    }

    try:
        es = Elasticsearch(["http://localhost:9200"])
        res = es.search(index="abpe_emails", body=body)
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)[:200],
                             "addresses": addresses, "results": []}, status=200)

    results = []
    for h in res["hits"]["hits"]:
        s = h["_source"]
        # message_id im Index hat \r\n-Präfix + spitze Klammern -> säubern
        mid = (s.get("message_id") or "").strip()
        results.append({
            "id": h["_id"],
            "subject": s.get("subject") or "(kein Betreff)",
            "from_addr": s.get("from_addr") or "",
            "to_addr": s.get("to_addr") or "",
            "date": s.get("date") or "",
            "folder": s.get("folder") or "",
            "account": s.get("account") or "",
            "message_id": mid,
            "uid": s.get("uid") or "",
            "has_attachments": bool(s.get("has_attachments")),
            "size_bytes": s.get("size_bytes") or 0,
        })

    total = res["hits"]["total"]["value"]
    return JsonResponse({
        "ok": True,
        "total": total,
        "addresses": addresses,
        "results": results,
    })

# ─────────────────────────────────────────────────────────────────────
# EDMS-eigene Mail-Ansicht (auf Basis der api_email_view-Logik aus abpe_ui,
# aber sauber getrennt + mit Anhang-Extraktion).
#   api_mail_view       -> JSON: Header + Body(html/plain) + Anhang-Liste
#   api_mail_attachment -> liefert einen Anhang als Download (per Index)
# Identifikation einer Mail: account + folder + (uid ODER message_id).
# Anhänge werden per Position im walk() (Index) adressiert.
# ─────────────────────────────────────────────────────────────────────
import json as _json
from pathlib import Path as _Path


def _imap_fetch_message(account, folder, uid_param="", message_id=""):
    """Verbindet zum IMAP, holt EINE Mail als email.message-Objekt.
    Rückgabe: (msg, error_str). Bei Erfolg error_str=None."""
    import imaplib
    import email as _email
    from django.conf import settings as _settings

    cfg_path = _Path(_settings.BASE_DIR) / "apps/namazu/management/commands/email_settings.json"
    cfg = _json.load(open(cfg_path))
    acc_cfg = cfg["accounts"].get(account)
    if not acc_cfg or not acc_cfg.get("enabled"):
        return None, "account not found"

    host = cfg["imap"]["host"]
    port = cfg["imap"]["port"]
    pw = acc_cfg["password"]

    try:
        m = imaplib.IMAP4_SSL(host, port)
        m.login(account, pw)
        m.select(f'"{folder}"', readonly=True)

        if uid_param:
            uid = uid_param.encode()
        else:
            # uid aus ES holen, sonst IMAP-Header-Search (langsam)
            from elasticsearch import Elasticsearch as _ES
            _es = _ES(["http://localhost:9200"])
            _res = _es.search(index="abpe_emails", body={
                "query": {"term": {"message_id": message_id}},
                "_source": ["uid"], "size": 1,
            })
            _hits = _res["hits"]["hits"]
            if _hits and _hits[0]["_source"].get("uid"):
                uid = _hits[0]["_source"]["uid"].encode()
            else:
                r, data = m.search(None, f'HEADER Message-ID "{message_id}"')
                if r != "OK" or not data[0]:
                    m.logout()
                    return None, "E-Mail nicht gefunden"
                uid = data[0].split()[0]

        r, data = m.fetch(uid, "(RFC822)")
        m.logout()
        if r != "OK" or not data or not data[0]:
            return None, "Fetch-Fehler"
        msg = _email.message_from_bytes(data[0][1])
        return msg, None
    except Exception as exc:
        return None, str(exc)[:200]


def _decode_mail_header(v):
    import email
    if not v:
        return ""
    out = []
    for part, charset in email.header.decode_header(v):
        if isinstance(part, bytes):
            out.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            out.append(str(part))
    return " ".join(out)


@extend_schema(
    summary="Mail-Detail (EDMS)",
    description="Holt eine Mail per IMAP und liefert Header, Body (html/plain) "
                "und die Anhang-Liste als JSON. Mail-ID: account+folder+(uid|message_id).",
    parameters=[
        _p("account", OpenApiTypes.STR, "IMAP-Account-Login (ES-Feld 'account')"),
        _p("folder", OpenApiTypes.STR, "Mail-Ordner (ES-Feld 'folder')"),
        _p("uid", OpenApiTypes.STR, "IMAP-UID (bevorzugt, schnell)"),
        _p("message_id", OpenApiTypes.STR, "Message-ID (Fallback, wenn keine uid)"),
    ],
    responses={200: OpenApiTypes.OBJECT},
    tags=["EDMS"],
)
@_drf_get
def api_mail_view(request, uuid=None):
    """EDMS-Mail-Detail: Header + Body + Anhang-Liste als JSON."""
    account = (request.GET.get("account") or "").strip()
    folder = (request.GET.get("folder") or "").strip()
    uid_param = (request.GET.get("uid") or "").strip()
    message_id = (request.GET.get("message_id") or "").strip()

    if not account or not folder or not (uid_param or message_id):
        return JsonResponse({"ok": False,
                             "error": "account, folder, uid|message_id erforderlich"},
                            status=400)

    msg, err = _imap_fetch_message(account, folder, uid_param, message_id)
    if err:
        return JsonResponse({"ok": False, "error": err}, status=404)

    subject = _decode_mail_header(msg.get("Subject", ""))
    from_ = _decode_mail_header(msg.get("From", ""))
    to_ = _decode_mail_header(msg.get("To", ""))
    cc_ = _decode_mail_header(msg.get("Cc", ""))
    date_ = msg.get("Date", "")

    body_html = ""
    body_plain = ""
    attachments = []
    idx = 0
    for part in msg.walk():
        if part.is_multipart():
            continue
        ct = part.get_content_type()
        disp = str(part.get("Content-Disposition") or "")
        filename = part.get_filename()

        # Anhang? (Content-Disposition attachment ODER hat Dateinamen)
        if "attachment" in disp.lower() or filename:
            fname = _decode_mail_header(filename) if filename else f"anhang_{idx}"
            try:
                payload = part.get_payload(decode=True) or b""
                size = len(payload)
            except Exception:
                size = 0
            attachments.append({
                "index": idx,
                "filename": fname,
                "content_type": ct,
                "size_bytes": size,
            })
            idx += 1
            continue

        # Body-Teile
        if ct == "text/html" and not body_html:
            try:
                body_html = part.get_payload(decode=True).decode(
                    part.get_content_charset() or "utf-8", errors="replace")
            except Exception:
                pass
        elif ct == "text/plain" and not body_plain:
            try:
                body_plain = part.get_payload(decode=True).decode(
                    part.get_content_charset() or "utf-8", errors="replace")
            except Exception:
                pass

    return JsonResponse({
        "ok": True,
        "subject": subject,
        "from_addr": from_,
        "to_addr": to_,
        "cc_addr": cc_,
        "date": date_,
        "folder": folder,
        "account": account,
        "body_html": body_html,
        "body_plain": body_plain,
        "attachments": attachments,
    })


@extend_schema(
    summary="Mail-Anhang herunterladen (EDMS)",
    description="Lädt einen einzelnen Anhang einer Mail per Position (index) herunter. "
                "Mail-ID: account+folder+(uid|message_id), plus index.",
    parameters=[
        _p("account", OpenApiTypes.STR, "IMAP-Account-Login"),
        _p("folder", OpenApiTypes.STR, "Mail-Ordner"),
        _p("uid", OpenApiTypes.STR, "IMAP-UID"),
        _p("message_id", OpenApiTypes.STR, "Message-ID (Fallback)"),
        _p("index", OpenApiTypes.INT, "Position des Anhangs (aus api_mail_view)"),
    ],
    responses={200: OpenApiTypes.BINARY},
    tags=["EDMS"],
)
@_drf_get
def api_mail_attachment(request, uuid=None):
    """Liefert einen Mail-Anhang als Download (per Index aus api_mail_view)."""
    from django.http import HttpResponse

    account = (request.GET.get("account") or "").strip()
    folder = (request.GET.get("folder") or "").strip()
    uid_param = (request.GET.get("uid") or "").strip()
    message_id = (request.GET.get("message_id") or "").strip()
    try:
        want_idx = int(request.GET.get("index"))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "index erforderlich"}, status=400)

    if not account or not folder or not (uid_param or message_id):
        return JsonResponse({"ok": False,
                             "error": "account, folder, uid|message_id erforderlich"},
                            status=400)

    msg, err = _imap_fetch_message(account, folder, uid_param, message_id)
    if err:
        return JsonResponse({"ok": False, "error": err}, status=404)

    idx = 0
    for part in msg.walk():
        if part.is_multipart():
            continue
        disp = str(part.get("Content-Disposition") or "")
        filename = part.get_filename()
        if "attachment" in disp.lower() or filename:
            if idx == want_idx:
                payload = part.get_payload(decode=True) or b""
                fname = _decode_mail_header(filename) if filename else f"anhang_{idx}"
                ct = part.get_content_type() or "application/octet-stream"
                resp = HttpResponse(payload, content_type=ct)
                resp["Content-Disposition"] = f'attachment; filename="{fname}"'
                return resp
            idx += 1

    return JsonResponse({"ok": False, "error": "Anhang nicht gefunden"}, status=404)


# ─────────────────────────────────────────────────────────────────────
# Mail-Anhang als Inline-Vorschau (PDF im iframe). Office-Formate werden
# via LibreOffice konvertiert + SHA256-gecacht (gleiche Pipeline wie EDMS-Doks).
# ─────────────────────────────────────────────────────────────────────
@extend_schema(
    summary="Mail-Anhang Vorschau (EDMS)",
    description="Liefert einen Mail-Anhang als anzeigbares PDF (Office-Formate via "
                "LibreOffice konvertiert, gecacht). PDF direkt, Bilder als Bild. "
                "Nicht darstellbare Formate -> 415.",
    parameters=[
        _p("account", OpenApiTypes.STR, "IMAP-Account-Login"),
        _p("folder", OpenApiTypes.STR, "Mail-Ordner"),
        _p("uid", OpenApiTypes.STR, "IMAP-UID"),
        _p("message_id", OpenApiTypes.STR, "Message-ID (Fallback)"),
        _p("index", OpenApiTypes.INT, "Position des Anhangs"),
    ],
    responses={200: OpenApiTypes.BINARY},
    tags=["EDMS"],
)
@xframe_options_sameorigin
@_drf_get
def api_mail_attachment_preview(request, uuid=None):
    """Mail-Anhang als Inline-Vorschau (PDF/Bild im iframe)."""
    from django.http import HttpResponse, FileResponse
    from .services import preview as preview_svc

    account = (request.GET.get("account") or "").strip()
    folder = (request.GET.get("folder") or "").strip()
    uid_param = (request.GET.get("uid") or "").strip()
    message_id = (request.GET.get("message_id") or "").strip()
    try:
        want_idx = int(request.GET.get("index"))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "index erforderlich"}, status=400)

    if not account or not folder or not (uid_param or message_id):
        return JsonResponse({"ok": False,
                             "error": "account, folder, uid|message_id erforderlich"},
                            status=400)

    msg, err = _imap_fetch_message(account, folder, uid_param, message_id)
    if err:
        return JsonResponse({"ok": False, "error": err}, status=404)

    # Anhang per Index finden
    idx = 0
    content = None
    fname = None
    for part in msg.walk():
        if part.is_multipart():
            continue
        disp = str(part.get("Content-Disposition") or "")
        filename = part.get_filename()
        if "attachment" in disp.lower() or filename:
            if idx == want_idx:
                content = part.get_payload(decode=True) or b""
                fname = _decode_mail_header(filename) if filename else f"anhang_{idx}"
                break
            idx += 1
    if content is None:
        return JsonResponse({"ok": False, "error": "Anhang nicht gefunden"}, status=404)

    ext = (fname.rsplit(".", 1)[-1] if "." in fname else "").lower()

    # Bilder direkt als Bild ausliefern (Browser zeigt sie im iframe)
    if ext in ("jpg", "jpeg", "png", "gif", "bmp", "webp"):
        ct = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
        resp = HttpResponse(content, content_type=ct)
        resp["Content-Disposition"] = f'inline; filename="{fname}"'
        return resp

    # PDF + Office -> über gemeinsame Preview-Pipeline (mit Cache)
    kind, pdf_path = preview_svc.get_preview_pdf_for_bytes(content, fname)
    if kind == "download" or not pdf_path:
        return JsonResponse({"ok": False, "kind": "download",
                             "filename": fname,
                             "reason": "Kein Inline-Preview für dieses Format"},
                            status=415)

    resp = FileResponse(open(pdf_path, "rb"), content_type="application/pdf")
    resp["Accept-Ranges"] = "bytes"
    base = fname.rsplit(".", 1)[0] if "." in fname else fname
    resp["Content-Disposition"] = f'inline; filename="{base}.pdf"'
    return resp


# ============================================================================
# MULTI-INDEX-SUCHE (ans Ende von apps/abpe_edms/views.py anhaengen)
# ============================================================================
# Sucht ueber content (Personen) + content_firma (Firmen) + dms (Dokumente)
# + abpe_emails (Mails). Scope waehlbar. Jeder Treffer bekommt "kind".
# Response: {counts:{...}, results:[{kind,id,title,snippet,meta},...]}
# ============================================================================

# Feld-Definitionen je Index (Boosts wie in der Dokumentsuche)
_FIELDS_PERSON = [
    "name^3", "ogo^2", "gulp^2", "freelancermap^2",
    "description", "emails^2", "phones^2", "city",
    "einsatzort", "konditionen", "kontakt_typ", "notes",
    "salutation", "department", "title",
]
_FIELDS_FIRMA = [
    "name^3", "description", "industry", "contacts^2",
    "emails^2", "phones^2", "billing_city", "website",
    "account_type", "kunden_nummer", "notes",
]
_FIELDS_MAIL = [
    "subject^3", "body", "from_addr^2", "to_addr^2",
]

# Index -> (kind, felder)
_SCOPE_INDEX = {
    "personen":  ("person",   "content",       _FIELDS_PERSON),
    "firmen":    ("firma",     "content_firma", _FIELDS_FIRMA),
    "mails":     ("mail",      "abpe_emails",   _FIELDS_MAIL),
    # dokumente wird separat ueber die bestehende dms-Logik behandelt
}


def _es_client():
    from elasticsearch import Elasticsearch
    return Elasticsearch(["http://localhost:9200"])


def _build_query(q, fields):
    """Live-Suche mit den richtigen ES-Techniken:
      0) Enthaelt q Boolean-/Feld-Syntax (AND/OR/NOT/:/[.../"/~/^)?
         -> query_string (gleiche Logik wie Berater-Suche).
      1) Sonst: match_phrase_prefix auf Namensfelder -> Autocomplete
         'thomas tro' -> 'Thomas Troschke' (letztes Wort als Praefix).
      2) match_phrase_prefix auf Volltextfelder -> 'firew' -> firewall.
      3) multi_match fuzziness -> Tippfehler 'troshke' -> Troschke.
    Alle should-verknuepft; ES waehlt den besten Score."""
    import re as _re
    if _re.search(r'\b(AND|OR|NOT)\b|[:\[\]"~^]', q):
        return {
            "query_string": {
                "query": q,
                "fields": fields,
                "default_operator": "AND",
                "type": "cross_fields",
                "lenient": True,
            }
        }

    base_fields = [f.split("^")[0] for f in fields]
    name_fields = [c for c in ("name", "subject", "title") if c in base_fields]
    text_fields = [c for c in base_fields
                   if c in ("ogo", "gulp", "freelancermap", "description",
                            "body", "contacts", "industry", "content")]

    shoulds = [
        # Fuzzy ueber alles (Tippfehler)
        {"multi_match": {"query": q, "fields": fields, "fuzziness": "AUTO"}},
    ]
    # Autocomplete auf Namen (hoher Boost)
    for nf in name_fields:
        shoulds.append({"match_phrase_prefix": {nf: {"query": q, "boost": 4}}})
    # Autocomplete auf Volltext (Skills etc.)
    for tf in text_fields:
        shoulds.append({"match_phrase_prefix": {tf: {"query": q, "boost": 1}}})

    return {"bool": {"should": shoulds, "minimum_should_match": 1}}


def _count_index(es, index, q, fields):
    """Zaehlt Treffer in einem Index (0 bei Fehler/leer)."""
    try:
        body = {"query": _build_query(q, fields)}
        r = es.count(index=index, body=body)
        return r.get("count", 0)
    except Exception:
        return 0


def _hits_index(es, index, kind, q, fields, size):
    """Holt Treffer aus einem Index, normalisiert zu {kind,id,title,snippet,meta}."""
    out = []
    try:
        body = {
            "size": size,
            "query": _build_query(q, fields),
        }
        r = es.search(index=index, body=body)
        for h in r["hits"]["hits"]:
            src = h["_source"]
            out.append(_normalize_hit(kind, h["_id"], src, h.get("_score", 0)))
    except Exception:
        pass
    return out


def _normalize_hit(kind, _id, src, score):
    """Vereinheitlicht Treffer aus verschiedenen Indizes."""
    if kind == "person":
        # Funktion (title) wenn vorhanden, sonst Typ (Berater/Kunde/...)
        funktion = (src.get("title") or "").strip()
        typ = (src.get("kontakt_typ") or "").strip()
        rolle = funktion or typ.capitalize()
        meta = []
        if rolle:
            meta.append(rolle)
        if src.get("city"):
            meta.append(src["city"])
        if src.get("konditionen"):
            meta.append(src["konditionen"].strip())
        return {
            "kind": "person",
            "id": src.get("crm_id") or _id,
            "title": src.get("name") or "(ohne Name)",
            "snippet": "",
            "meta": " · ".join(m for m in meta if m),
            "score": score,
            "phones": src.get("phones") or [],
            "company": src.get("company") or src.get("account_name") or "",
        }
    if kind == "firma":
        contacts = src.get("contacts") or []
        meta = []
        if src.get("billing_city"):
            meta.append(src["billing_city"])
        if contacts:
            meta.append(f"{len(contacts)} Ansprechpartner")
        return {
            "kind": "firma",
            "id": src.get("crm_id") or _id,
            "title": src.get("name") or "(ohne Name)",
            "snippet": (src.get("description") or src.get("industry") or "")[:160],
            "meta": " · ".join(meta),
            "score": score,
        }
    if kind == "mail":
        return {
            "kind": "mail",
            "id": _id,
            "title": src.get("subject") or "(kein Betreff)",
            "snippet": (src.get("from_addr") or "")[:120],
            "meta": (src.get("date") or "")[:10],
            "account": src.get("account") or "",
            "folder": src.get("folder") or "",
            "message_id": src.get("message_id") or "",
            "uid": src.get("uid") or "",
            "score": score,
        }
    # dokument
    return {
        "kind": "dokument",
        "id": src.get("uuid") or _id,
        "title": src.get("title") or src.get("filename") or "(ohne Titel)",
        "snippet": (src.get("content") or "")[:160],
        "meta": src.get("doctype_label") or "",
        "score": score,
    }


def api_search_all(request):
    """Multi-Index-Suche. ?q=...&scope=all|personen|firmen|dokumente|mails&size=N"""
    from django.http import JsonResponse
    q = (request.GET.get("q") or "").strip()
    scope = (request.GET.get("scope") or "all").strip()
    size = _int(request, "size", 20, lo=1, hi=100)

    if not q:
        return JsonResponse({"counts": {}, "results": [], "scope": scope})

    es = _es_client()

    # --- Counts pro Kategorie (immer alle, fuer den Umschalter) ---
    counts = {}
    for sc, (kind, index, fields) in _SCOPE_INDEX.items():
        counts[sc] = _count_index(es, index, q, fields)
    # Dokumente separat (dms)
    counts["dokumente"] = _count_index(es, "dms", q, _ES_SEARCH_FIELDS)
    counts["all"] = sum(v for k, v in counts.items() if k != "all")

    # --- Treffer je nach scope ---
    results = []
    if scope == "all":
        # gemischt: von jedem Index einen Teil holen, dann nach score mischen
        per = max(3, size // 4)
        for sc, (kind, index, fields) in _SCOPE_INDEX.items():
            results += _hits_index(es, index, kind, q, fields, per)
        results += _hits_index(es, "dms", "dokument", q, _ES_SEARCH_FIELDS, per)
        results.sort(key=lambda r: -r["score"])
        results = results[:size]
    elif scope in _SCOPE_INDEX:
        kind, index, fields = _SCOPE_INDEX[scope]
        results = _hits_index(es, index, kind, q, fields, size)
    elif scope == "dokumente":
        results = _hits_index(es, "dms", "dokument", q, _ES_SEARCH_FIELDS, size)

    person_ids = [r["id"] for r in results if r["kind"] == "person" and r.get("id")]
    if person_ids:
        try:
            agg = es.search(index="dms", body={
                "size": 0,
                "query": {"terms": {"owner_crm_ids": person_ids}},
                "aggs": {"per_owner": {"terms": {
                    "field": "owner_crm_ids", "size": len(person_ids) * 2}}},
            })
            dcount = {b["key"]: b["doc_count"]
                      for b in agg["aggregations"]["per_owner"]["buckets"]}
            for r in results:
                if r["kind"] == "person":
                    r["doc_count"] = dcount.get(r["id"], 0)
        except Exception:
            for r in results:
                if r["kind"] == "person":
                    r["doc_count"] = 0

    return JsonResponse({"counts": counts, "results": results, "scope": scope})

