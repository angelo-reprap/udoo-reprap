# -*- coding: utf-8 -*-
"""
apps/abpe_edms/admin.py
================================================================================
Django-Admin für das ABpE EDMS.

Zweck: DocTypes, Tags, Gewerke und Dokumente sofort pflegen und prüfen können —
BEVOR Frontend existiert. Die Inlines machen die Beziehungen sichtbar:
  - Dokument  -> Owner (n:m) + Versionen + Metadaten + Positionen direkt im Dok
  - Gewerk    -> Berater + Arbeitspakete direkt im Gewerk
  - DocType   -> Metadaten-Felder direkt im DocType
Audit- und Sync-Logs sind schreibgeschützt (Protokolle, keine Handpflege).
================================================================================
"""

from django.contrib import admin

from .models import (
    DmsDocType, DmsTag, DmsMetadataType, DmsDocTypeMetadata,
    DmsGewerk, DmsGewerkBerater, DmsArbeitspaket,
    CrmDocument, CrmDocumentOwner, CrmDocumentVersion,
    DmsDocumentMetadata, DmsDocumentTag, DmsDocumentLink,
    DmsLeistungsposition, DmsDocumentEvent, DmsSyncRun,
)


# =============================================================================
#  INLINES
# =============================================================================

class DmsDocTypeMetadataInline(admin.TabularInline):
    model = DmsDocTypeMetadata
    extra = 0
    autocomplete_fields = ("metadata_type",)


class DmsGewerkBeraterInline(admin.TabularInline):
    model = DmsGewerkBerater
    extra = 0
    fields = ("contact_crm_id", "role", "start_date", "end_date")


class DmsArbeitspaketInline(admin.TabularInline):
    model = DmsArbeitspaket
    extra = 0
    fields = ("key", "label", "unit", "sort_order")


class CrmDocumentOwnerInline(admin.TabularInline):
    model = CrmDocumentOwner
    extra = 1
    fields = ("owner_type", "owner_crm_id", "role", "is_primary")
    autocomplete_fields = ()


class CrmDocumentVersionInline(admin.TabularInline):
    model = CrmDocumentVersion
    extra = 0
    fk_name = "document"
    fields = (
        "version_no", "volume", "relative_path", "filename",
        "size_bytes", "is_active", "in_trash",
    )
    readonly_fields = ("size_bytes",)
    show_change_link = True


class DmsDocumentMetadataInline(admin.TabularInline):
    model = DmsDocumentMetadata
    extra = 0
    autocomplete_fields = ("metadata_type",)


class DmsLeistungspositionInline(admin.TabularInline):
    model = DmsLeistungsposition
    extra = 0
    fields = (
        "direction", "arbeitspaket", "owner_crm_id",
        "beschreibung", "menge", "einheit", "einzelpreis", "betrag",
    )


class DmsDocumentLinkInline(admin.TabularInline):
    model = DmsDocumentLink
    fk_name = "source_document"
    extra = 0
    fields = ("link_type", "target_document", "note")
    autocomplete_fields = ("target_document",)


# =============================================================================
#  KONFIGURATION
# =============================================================================

@admin.register(DmsDocType)
class DmsDocTypeAdmin(admin.ModelAdmin):
    list_display = (
        "label", "key", "retention_years", "delete_after_days",
        "default_volume", "is_system", "sort_order",
    )
    list_filter = ("default_volume", "is_system")
    search_fields = ("key", "label", "description")
    ordering = ("sort_order", "label")
    inlines = (DmsDocTypeMetadataInline,)


@admin.register(DmsTag)
class DmsTagAdmin(admin.ModelAdmin):
    list_display = (
        "label", "slug", "color", "is_inbox_tag",
        "matching_algorithm", "is_system",
    )
    list_filter = ("is_inbox_tag", "is_system", "matching_algorithm")
    search_fields = ("label", "slug", "match")
    prepopulated_fields = {"slug": ("label",)}


@admin.register(DmsMetadataType)
class DmsMetadataTypeAdmin(admin.ModelAdmin):
    list_display = ("label", "name", "default")
    search_fields = ("name", "label")


# =============================================================================
#  GEWERK
# =============================================================================

@admin.register(DmsGewerk)
class DmsGewerkAdmin(admin.ModelAdmin):
    list_display = (
        "nummer", "title", "account_crm_id", "status",
        "start_date", "end_date",
    )
    list_filter = ("status",)
    search_fields = ("nummer", "title", "account_crm_id")
    date_hierarchy = "start_date"
    inlines = (DmsGewerkBeraterInline, DmsArbeitspaketInline)
    readonly_fields = ("uuid", "created_at", "modified_at")


@admin.register(DmsArbeitspaket)
class DmsArbeitspaketAdmin(admin.ModelAdmin):
    list_display = ("key", "label", "gewerk", "unit", "sort_order")
    search_fields = ("key", "label")
    list_filter = ("gewerk",)


# =============================================================================
#  DOKUMENT
# =============================================================================

@admin.register(CrmDocument)
class CrmDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "title", "doctype", "direction", "gewerk", "status",
        "document_date", "retention_until", "needs_review", "in_trash",
    )
    list_filter = (
        "doctype", "direction", "status", "source",
        "needs_review", "in_trash",
    )
    search_fields = ("title", "description", "content", "uuid")
    date_hierarchy = "document_date"
    ordering = ("-document_date", "-created_at")
    autocomplete_fields = ("doctype", "gewerk")
    readonly_fields = (
        "uuid", "retention_until", "created_at", "modified_at",
        "created_by", "modified_by", "trashed_at", "trashed_by",
    )
    inlines = (
        CrmDocumentOwnerInline,
        CrmDocumentVersionInline,
        DmsDocumentMetadataInline,
        DmsLeistungspositionInline,
        DmsDocumentLinkInline,
    )
    fieldsets = (
        (None, {
            "fields": ("title", "description", "doctype", "gewerk", "direction")
        }),
        ("Lebenszyklus", {
            "fields": (
                "document_date", "valid_from", "valid_until",
                "retention_years_override", "retention_until", "status",
            )
        }),
        ("Zustand", {
            "fields": ("source", "language", "is_stub", "needs_review")
        }),
        ("Archiv", {
            "classes": ("collapse",),
            "fields": ("in_trash", "trashed_at", "trashed_by", "trashed_reason"),
        }),
        ("Volltext", {
            "classes": ("collapse",),
            "fields": ("content",),
        }),
        ("System", {
            "classes": ("collapse",),
            "fields": ("uuid", "created_at", "created_by", "modified_at", "modified_by"),
        }),
    )


@admin.register(CrmDocumentOwner)
class CrmDocumentOwnerAdmin(admin.ModelAdmin):
    list_display = ("document", "owner_type", "owner_crm_id", "role", "is_primary")
    list_filter = ("owner_type", "role", "is_primary")
    search_fields = ("owner_crm_id", "document__title")


@admin.register(CrmDocumentVersion)
class CrmDocumentVersionAdmin(admin.ModelAdmin):
    list_display = (
        "document", "version_no", "volume", "filename",
        "size_bytes", "is_active", "in_trash",
    )
    list_filter = ("volume", "is_active", "in_trash", "mimetype")
    search_fields = ("filename", "relative_path", "checksum", "document__title")
    readonly_fields = ("created_at", "created_by")


@admin.register(DmsDocumentLink)
class DmsDocumentLinkAdmin(admin.ModelAdmin):
    list_display = ("source_document", "link_type", "target_document")
    list_filter = ("link_type",)
    search_fields = ("source_document__title", "target_document__title", "note")


@admin.register(DmsLeistungsposition)
class DmsLeistungspositionAdmin(admin.ModelAdmin):
    list_display = (
        "document", "direction", "arbeitspaket",
        "owner_crm_id", "menge", "einheit", "betrag",
    )
    list_filter = ("direction",)
    search_fields = ("document__title", "owner_crm_id", "beschreibung")


# =============================================================================
#  PROTOKOLLE — schreibgeschützt
# =============================================================================

@admin.register(DmsDocumentEvent)
class DmsDocumentEventAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "event_type", "document", "actor", "actor_label")
    list_filter = ("event_type",)
    search_fields = ("document__title", "actor_label", "document_uuid")
    date_hierarchy = "timestamp"
    readonly_fields = (
        "document", "document_uuid", "event_type", "actor",
        "actor_label", "timestamp", "detail",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(DmsSyncRun)
class DmsSyncRunAdmin(admin.ModelAdmin):
    list_display = (
        "started_at", "finished_at", "volume", "status",
        "files_seen", "files_new", "files_updated", "files_removed",
        "documents_indexed", "triggered_by",
    )
    list_filter = ("status", "volume", "triggered_by")
    date_hierarchy = "started_at"
    readonly_fields = tuple(
        f.name for f in DmsSyncRun._meta.fields
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

