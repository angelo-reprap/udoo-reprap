from django.contrib import admin

from . import models


class ProzessSchrittInline(admin.TabularInline):
    model = models.ProzessSchritt
    extra = 1
    ordering = ['reihenfolge']


@admin.register(models.ProzessRegel)
class ProzessRegelAdmin(admin.ModelAdmin):
    list_display = ('name', 'ausloeser_typ', 'ausloeser_wert', 'aktiv', 'erstellt_von')
    list_filter = ('aktiv', 'ausloeser_typ')
    search_fields = ('name', 'beschreibung')
    inlines = [ProzessSchrittInline]


@admin.register(models.ErgebnisTyp)
class ErgebnisTypAdmin(admin.ModelAdmin):
    list_display = ('code', 'label', 'kontext', 'sort_order', 'aktiv', 'schliesst_vorgang')
    list_filter = ('kontext', 'aktiv')
    search_fields = ('code', 'label')
    ordering = ('kontext', 'sort_order')


@admin.register(models.Aufgabe)
class AufgabeAdmin(admin.ModelAdmin):
    list_display = (
        'titel', 'art', 'status', 'faellig_am', 'prioritaet',
        'zugewiesen_an', 'quelle', 'ref_type',
    )
    list_filter = ('status', 'art', 'quelle')
    search_fields = ('titel', 'beschreibung', 'ref_id')
    raw_id_fields = ('zugewiesen_an', 'erledigt_von', 'regel', 'ergebnis', 'parent')
    filter_horizontal = ('delegiert_an',)
    date_hierarchy = 'faellig_am'


@admin.register(models.Aktivitaet)
class AktivitaetAdmin(admin.ModelAdmin):
    list_display = ('zeitpunkt', 'medium', 'titel', 'ref_type', 'ref_id', 'user')
    list_filter = ('medium',)
    search_fields = ('titel', 'ref_id')
    date_hierarchy = 'zeitpunkt'


@admin.register(models.RadarSource)
class RadarSourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'typ', 'ziel', 'intervall_min', 'aktiv', 'letzter_lauf')
    list_filter = ('typ', 'ziel', 'aktiv')


@admin.register(models.RadarItem)
class RadarItemAdmin(admin.ModelAdmin):
    list_display = ('headline', 'status', 'quick_score', 'quelle', 'eingegangen_am')
    list_filter = ('status',)
    search_fields = ('headline', 'dedup_hash')


@admin.register(models.RadarItemGroup)
class RadarItemGroupAdmin(admin.ModelAdmin):
    list_display = ('titel_norm', 'anbieter_anzahl', 'erstellt_am')
    search_fields = ('titel_norm', 'merkmal_hash')


@admin.register(models.RadarConsultantItem)
class RadarConsultantItemAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'gulp_id', 'match_status', 'status', 'ort',
        'crm_contact_id', 'verfuegbar_ab', 'deleted_at', 'updated_at',
    )
    list_filter = ('match_status', 'status')
    search_fields = ('name', 'gulp_id', 'profil_url', 'dedup_hash', 'crm_contact_id', 'ort')
    readonly_fields = ('dedup_hash', 'auto_update_log', 'cv_versions', 'deleted_at')


@admin.register(models.Sperrliste)
class SperrlisteAdmin(admin.ModelAdmin):
    list_display = (
        'firma_name', 'firma_name_norm', 'crm_account_id',
        'richtung', 'seit', 'aktiv', 'angelegt_von',
    )
    list_filter = ('richtung', 'aktiv')
    search_fields = ('firma_name', 'firma_name_norm', 'crm_account_id')
    readonly_fields = ('firma_name_norm',)
    raw_id_fields = ('angelegt_von',)


@admin.register(models.InboxMailRead)
class InboxMailReadAdmin(admin.ModelAdmin):
    list_display = ('mail_id', 'user', 'read_at')
    list_filter = ('read_at',)
    search_fields = ('mail_id',)
    raw_id_fields = ('user',)
    date_hierarchy = 'read_at'
