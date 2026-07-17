"""
ABpE UI Admin Konfiguration
"""

from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from .models import UserSettings


# Nicht erneut registrieren - User ist bereits registriert!
# Stattdessen: UserAdmin erweitern (unregister + register)

# User aus Admin entfernen und neu registrieren mit eigener Config
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Erweiterter User Admin mit ABpE UI Einstellungen"""
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_active', 'groups')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    
    fieldsets = UserAdmin.fieldsets + (
        ('ABpE UI Einstellungen', {
            'fields': (),
            'description': 'UI-Einstellungen werden im separaten UserSettings Modell verwaltet'
        }),
    )


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    """Admin für Benutzereinstellungen"""
    list_display = ['user', 'theme', 'language', 'sidebar_collapsed', 'updated_at']
    list_filter = ['theme', 'language']
    search_fields = ['user__username', 'user__email']
    raw_id_fields = ['user']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Benutzer', {
            'fields': ('user',)
        }),
        ('Theme Einstellungen', {
            'fields': ('theme',),
            'description': 'Dark Mode, Light Mode oder System folgen'
        }),
        ('Spracheinstellungen', {
            'fields': ('language',),
        }),
        ('UI Einstellungen', {
            'fields': ('sidebar_collapsed',),
        }),
        ('Zeitstempel', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


# ============================================================
# BeraterProfil Admin
# ============================================================
from .models import BeraterProfil

@admin.register(BeraterProfil)
class BeraterProfilAdmin(admin.ModelAdmin):
    list_display  = ['user', 'status', 'rolle', 'betreuer', 'ist_externer_berater', 'hat_profil', 'created_at']
    list_filter   = ['status', 'ist_externer_berater']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name']
    raw_id_fields = ['user', 'betreuer', 'profile']
    readonly_fields = ['created_at', 'updated_at', 'rolle', 'hat_profil']

    fieldsets = (
        ('Benutzer', {
            'fields': ('user', 'betreuer', 'status', 'ist_externer_berater')
        }),
        ('Profil-Verknüpfung', {
            'fields': ('profile', 'hat_profil')
        }),
        ('Interne Notizen', {
            'fields': ('interne_notizen',),
            'classes': ('collapse',)
        }),
        ('Metadaten', {
            'fields': ('rolle', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
