# -*- coding: utf-8 -*-
"""
apps/abpe_edms/urls.py
EDMS-Routen. Eingebunden in abpe_backend/urls.py unter:
    path('edms/', include('apps.abpe_edms.urls', namespace='abpe_edms'))
=> Endpunkte liegen unter /edms/api/...
"""

from django.urls import path

from . import views

app_name = "abpe_edms"

urlpatterns = [
    # Gesamtsuche + Filter + Sort + Paginierung
    path("api/search/", views.api_search, name="api_search"),

    # Akte eines Owners (nach DocType-Reitern gruppiert)
    path("api/akte/<str:owner_type>/<str:crm_id>/", views.api_akte, name="api_akte"),

    # Dokument-Detail inkl. Versionen
    path("api/document/<uuid:uuid>/", views.api_document, name="api_document"),

    # Datei der (aktiven) Version vom Share streamen (?version=, ?download=1)
    path("api/file/<uuid:uuid>/", views.api_file, name="api_file"),

    # Vorschau-PDF (PDF direkt, DOC/DOCX via LibreOffice, gecacht)
    path("api/preview/<uuid:uuid>/", views.api_preview, name="api_preview"),

    # --- Schreibende Endpunkte (POST) ---
    # Owner zuordnen (idempotent, nimmt aus Posteingang)
    path("api/document/<uuid:uuid>/owner/", views.api_document_add_owner,
         name="api_document_add_owner"),
    # Archivieren / Wiederherstellen (status, GoBD-konform — kein Papierkorb)
    path("api/document/<uuid:uuid>/archive/", views.api_document_archive,
         name="api_document_archive"),
    path("api/document/<uuid:uuid>/restore/", views.api_document_restore,
         name="api_document_restore"),
    # Posteingang erledigt (needs_review=False ohne Owner)
    path("api/document/<uuid:uuid>/review-done/", views.api_document_review_done,
         name="api_document_review_done"),

    # Posteingang
    path("api/inbox/", views.api_inbox, name="api_inbox"),
    path("api/personen/", views.api_personen, name="api_personen"),
    path("api/search_all/", views.api_search_all, name="api_search_all"),
    path("api/person/<str:crm_id>/mails/", views.api_person_mails, name="api_person_mails"),
    path("api/mail/view/", views.api_mail_view, name="api_mail_view"),
    path("api/mail/attachment/", views.api_mail_attachment, name="api_mail_attachment"),
    path("api/mail/attachment/preview/", views.api_mail_attachment_preview, name="api_mail_attachment_preview"),

    # DocType-Liste (Filter-Dropdowns)
    path("api/doctypes/", views.api_doctypes, name="api_doctypes"),
]

