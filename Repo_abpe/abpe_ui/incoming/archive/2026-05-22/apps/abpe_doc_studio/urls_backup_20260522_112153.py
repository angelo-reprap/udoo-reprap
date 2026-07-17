"""
ABpE Doc Studio — URL-Konfiguration

Prefix in abpe_backend/urls.py:  path('doc-studio/', include('apps.abpe_doc_studio.urls'))

API-Endpunkte:
  /doc-studio/api/templates/              GET list, POST create
  /doc-studio/api/templates/<pk>/         GET, PUT, DELETE
  /doc-studio/api/templates/<pk>/duplicate/  POST
  /doc-studio/api/templates/<pk>/versions/   GET
  /doc-studio/api/templates/<pk>/preview/    POST → bytes (docx/pdf/html)
  /doc-studio/api/templates/<pk>/generate/   POST → generiert + speichert
  /doc-studio/api/generate/              POST → sync (identifier + variables)
  /doc-studio/api/generate/async/        POST → async (Celery Queue)

  /doc-studio/api/layouts/               GET list
  /doc-studio/api/styles/                GET list (StyleKits)
  /doc-studio/api/blocks/                GET list, POST create
  /doc-studio/api/blocks/<pk>/           GET, PUT, DELETE

  /doc-studio/api/invoices/              GET list, POST create
  /doc-studio/api/invoices/<pk>/         GET, PUT
  /doc-studio/api/invoices/<pk>/generate/ POST → Rechnung generieren

  /doc-studio/api/log/                   GET (DocLog)
  /doc-studio/api/log/stats/             GET (Statistik)
  /doc-studio/api/queue/                 GET
  /doc-studio/api/queue/<queue_id>/cancel/ POST

Portal-Views (HTML — für abpe_ui Templates):
  /doc-studio/                           → index (Vorlagen-Liste)
  /doc-studio/studio/                    → Studio / Editor
  /doc-studio/log/                       → Generierungs-Log
  /doc-studio/config/                    → Konfiguration (Layouts, Styles, Blöcke)
  /doc-studio/invoices/                  → Rechnungen
"""
from django.urls import path
from . import views, api

app_name = 'doc_studio'

# ── API ───────────────────────────────────────────────────────────────────────
api_patterns = [
    # Templates
    path('templates/',
         api.TemplateListCreateAPI.as_view(),
         name='api_template_list'),
    path('templates/<int:pk>/',
         api.TemplateDetailAPI.as_view(),
         name='api_template_detail'),
    path('templates/<int:pk>/duplicate/',
         api.TemplateDuplicateAPI.as_view(),
         name='api_template_duplicate'),
    path('templates/<int:pk>/versions/',
         api.TemplateVersionListAPI.as_view(),
         name='api_template_versions'),
    path('templates/<int:pk>/preview/',
         api.TemplatePreviewAPI.as_view(),
         name='api_template_preview'),
    path('templates/<int:pk>/generate/',
         api.TemplateGenerateAPI.as_view(),
         name='api_template_generate'),

    # Generierung (direkt via identifier)
    path('generate/',
         api.GenerateAPI.as_view(),
         name='api_generate'),
    path('generate/async/',
         api.GenerateAsyncAPI.as_view(),
         name='api_generate_async'),

    # Layouts + Styles + Blöcke
    path('layouts/',
         api.LayoutListAPI.as_view(),
         name='api_layout_list'),
    path('styles/',
         api.StyleKitListAPI.as_view(),
         name='api_style_list'),
    path('blocks/',
         api.BlockListCreateAPI.as_view(),
         name='api_block_list'),
    path('blocks/<int:pk>/',
         api.BlockDetailAPI.as_view(),
         name='api_block_detail'),

    # Rechnungen
    path('invoices/',
         api.InvoiceListCreateAPI.as_view(),
         name='api_invoice_list'),
    path('invoices/<uuid:pk>/',
         api.InvoiceDetailAPI.as_view(),
         name='api_invoice_detail'),
    path('invoices/<uuid:pk>/generate/',
         api.InvoiceGenerateAPI.as_view(),
         name='api_invoice_generate'),

    # Log + Statistik + Queue
    path('log/',
         api.LogListAPI.as_view(),
         name='api_log_list'),
    path('log/stats/',
         api.LogStatsAPI.as_view(),
         name='api_log_stats'),
    path('queue/',
         api.QueueListAPI.as_view(),
         name='api_queue_list'),
    path('queue/<uuid:queue_id>/cancel/',
         api.QueueCancelAPI.as_view(),
         name='api_queue_cancel'),
]

# ── Portal-Views (HTML) ───────────────────────────────────────────────────────
urlpatterns = [
    # Portal-Views — werden von abpe_ui/module_view() gerendert
    path('',           views.index,    name='index'),
    path('studio/',    views.studio,   name='studio'),
    path('log/',       views.log,      name='log'),
    path('config/',    views.config,   name='config'),
    path('invoices/',  views.invoices, name='invoices'),

    # API-Prefix
    path('api/', __import__('django.urls', fromlist=['include']).include(
        (api_patterns, 'doc_studio_api')
    )),
]
