"""
ABpE Email Studio — URL Konfiguration
"""
from django.urls import path
from . import views
from . import api

app_name = 'email_studio'

urlpatterns = [

    # ── Portal Views ──────────────────────────────────────────────────────────
    path('',         views.index,  name='index'),
    path('studio/',  views.studio, name='studio'),
    path('log/',     views.log,    name='log'),
    path('config/',  views.config, name='config'),

    # ── Template CRUD ─────────────────────────────────────────────────────────
    path('api/templates/',
         api.TemplateListCreateAPI.as_view(),        name='api-template-list'),
    path('api/templates/<int:pk>/',
         api.TemplateDetailAPI.as_view(),            name='api-template-detail'),
    path('api/templates/<int:pk>/duplicate/',
         api.TemplateDuplicateAPI.as_view(),         name='api-template-duplicate'),

    # ── Versionen ─────────────────────────────────────────────────────────────
    path('api/templates/<int:pk>/versions/',
         api.TemplateVersionListAPI.as_view(),       name='api-template-versions'),
    path('api/templates/<int:pk>/versions/<int:version>/activate/',
         api.TemplateVersionActivateAPI.as_view(),   name='api-template-version-activate'),

    # ── Meilensteine ──────────────────────────────────────────────────────────
    path('api/templates/<int:pk>/milestones/',
         api.MilestoneListCreateAPI.as_view(),       name='api-milestone-list'),
    path('api/templates/<int:pk>/milestones/<int:mid>/restore/',
         api.MilestoneRestoreAPI.as_view(),          name='api-milestone-restore'),

    # ── Vorschau + Test ───────────────────────────────────────────────────────
    path('api/templates/<int:pk>/preview/',
         api.TemplatePreviewAPI.as_view(),           name='api-template-preview'),
    path('api/templates/<int:pk>/send-test/',
         api.TemplateSendTestAPI.as_view(),          name='api-template-send-test'),
    path('api/templates/<int:pk>/compatibility/',
         api.TemplateCompatibilityAPI.as_view(),     name='api-template-compatibility'),

    # ── Übersetzungen ─────────────────────────────────────────────────────────
    path('api/templates/<int:pk>/translate/',
         api.TemplateTranslateAPI.as_view(),         name='api-template-translate'),
    path('api/templates/<int:pk>/set-langs/',
         api.TemplateSetLangsAPI.as_view(),          name='api-template-set-langs'),
    path('api/templates/<int:pk>/translation/<str:lang>/',
         api.TranslationDetailAPI.as_view(),         name='api-translation-detail'),

    # ── Versand ───────────────────────────────────────────────────────────────
    path('api/send/',
         api.SendAPI.as_view(),                      name='api-send'),
    path('api/send-async/',
         api.SendAsyncAPI.as_view(),                 name='api-send-async'),

    # ── Log ───────────────────────────────────────────────────────────────────
    path('api/log/',
         api.LogListAPI.as_view(),                   name='api-log-list'),
    path('api/log/stats/',
         api.LogStatsAPI.as_view(),                  name='api-log-stats'),

    # ── Signaturen ────────────────────────────────────────────────────────────
    path('api/signatures/',
         api.SignatureListCreateAPI.as_view(),       name='api-signature-list'),
    path('api/signatures/<int:pk>/',
         api.SignatureDetailAPI.as_view(),           name='api-signature-detail'),

    # ── Absender-Konten ───────────────────────────────────────────────────────
    path('api/senders/',
         api.SenderAccountListAPI.as_view(),         name='api-sender-list'),
    path('api/senders/<int:pk>/',
         api.SenderAccountDetailAPI.as_view(),       name='api-sender-detail'),
    path('api/senders/test-smtp/',
         api.SenderSMTPTestAPI.as_view(),            name='api-sender-smtp-test'),

    # ── Variablen ─────────────────────────────────────────────────────────────
    path('api/variables/',
         api.VariableListAPI.as_view(),              name='api-variables'),

    # ── Module ────────────────────────────────────────────────────────────────
    path('api/modules/',
         api.ModuleListAPI.as_view(),                name='api-module-list'),
    path('api/modules/<int:pk>/',
         api.ModuleDetailAPI.as_view(),              name='api-module-detail'),

    # ── Queue ─────────────────────────────────────────────────────────────────
    path('api/queue/',
         api.QueueListAPI.as_view(),                 name='api-queue-list'),
    path('api/queue/<str:queue_id>/cancel/',
         api.QueueCancelAPI.as_view(),               name='api-queue-cancel'),
]
