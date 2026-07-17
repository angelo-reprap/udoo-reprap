"""
ABpE Doc Studio — URL-Konfiguration
"""
from django.urls import path
from . import views, api

app_name = 'doc_studio'

api_patterns = [
    path('templates/',                          api.TemplateListCreateAPI.as_view(),   name='api_template_list'),
    path('templates/<int:pk>/',                 api.TemplateDetailAPI.as_view(),       name='api_template_detail'),
    path('templates/<int:pk>/duplicate/',       api.TemplateDuplicateAPI.as_view(),    name='api_template_duplicate'),
    path('templates/<int:pk>/versions/',        api.TemplateVersionListAPI.as_view(),  name='api_template_versions'),
    path('templates/<int:pk>/preview/',         api.TemplatePreviewAPI.as_view(),      name='api_template_preview'),
    path('templates/<int:pk>/generate/',        api.TemplateGenerateAPI.as_view(),     name='api_template_generate'),
    path('generate/',                           api.GenerateAPI.as_view(),             name='api_generate'),
    path('generate/async/',                     api.GenerateAsyncAPI.as_view(),        name='api_generate_async'),
    path('layouts/',                            api.LayoutListAPI.as_view(),           name='api_layout_list'),
    path('styles/',                             api.StyleKitListAPI.as_view(),         name='api_style_list'),
    path('blocks/',                             api.BlockListCreateAPI.as_view(),      name='api_block_list'),
    path('blocks/<int:pk>/',                    api.BlockDetailAPI.as_view(),          name='api_block_detail'),
    path('invoices/',                           api.InvoiceListCreateAPI.as_view(),    name='api_invoice_list'),
    path('invoices/<uuid:pk>/',                 api.InvoiceDetailAPI.as_view(),        name='api_invoice_detail'),
    path('invoices/<uuid:pk>/generate/',        api.InvoiceGenerateAPI.as_view(),      name='api_invoice_generate'),
    path('log/',                                api.LogListAPI.as_view(),              name='api_log_list'),
    path('log/stats/',                          api.LogStatsAPI.as_view(),             name='api_log_stats'),
    path('queue/',                              api.QueueListAPI.as_view(),            name='api_queue_list'),
    path('queue/<uuid:queue_id>/cancel/',       api.QueueCancelAPI.as_view(),          name='api_queue_cancel'),
    path('fixtures/reload/',                    views.api_reload_fixtures,             name='api_fixtures_reload'),
]

urlpatterns = [
    path('',           views.index,    name='index'),
    path('studio/',    views.studio,   name='studio'),
    path('log/',       views.log,      name='log'),
    path('config/',    views.config,   name='config'),
    path('invoices/',  views.invoices, name='invoices'),

    # Download-Endpunkt
    path('download/<str:log_id>/', views.download_doc, name='download'),

    path('api/', __import__('django.urls', fromlist=['include']).include(
        (api_patterns, 'doc_studio_api')
    )),
]
