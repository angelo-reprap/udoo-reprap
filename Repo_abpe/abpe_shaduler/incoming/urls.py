"""
Shaduler URLs — Kap. 3/4 Architektur_zielvorlage.md
Mount (Live, manuell): path('shaduler/', include('apps.abpe_shaduler.urls'))
"""
from django.urls import path

from . import views

app_name = 'abpe_shaduler'

urlpatterns = [
    # Portal
    path('', views.index, name='index'),

    # Stats / Aufgaben
    path('api/stats/', views.api_stats, name='api_stats'),
    path('api/aufgaben/', views.api_aufgaben_list, name='api_aufgaben_list'),
    path('api/aufgaben/create/', views.api_aufgabe_create, name='api_aufgabe_create'),
    path('api/aufgaben/<uuid:pk>/', views.api_aufgabe_detail, name='api_aufgabe_detail'),
    path('api/aufgaben/<uuid:pk>/ergebnis/', views.api_aufgabe_ergebnis, name='api_aufgabe_ergebnis'),
    path('api/aufgaben/<uuid:pk>/snooze/', views.api_aufgabe_snooze, name='api_aufgabe_snooze'),
    path('api/aufgaben/<uuid:pk>/delegieren/', views.api_aufgabe_delegieren, name='api_aufgabe_delegieren'),
    path('api/aufgaben/ref/<str:typ>/<str:ref_id>/', views.api_aufgaben_fuer_ref, name='api_aufgaben_fuer_ref'),

    # Kalender / Ergebnis / Inbox
    path('api/kalender/', views.api_kalender, name='api_kalender'),
    path('api/ergebnistypen/', views.api_ergebnistypen, name='api_ergebnistypen'),
    path('api/ki/vorschlag/', views.api_ki_vorschlag, name='api_ki_vorschlag'),
    path('api/inbox/', views.api_inbox_list, name='api_inbox_list'),
    path('api/inbox/<str:mail_id>/aufgabe/', views.api_inbox_to_task, name='api_inbox_to_task'),

    # Radar Anfragen
    path('api/radar/anfragen/', views.api_radar_items, name='api_radar_items'),
    path('api/radar/anfragen/<uuid:pk>/uebernehmen/', views.api_radar_takeover, name='api_radar_takeover'),
    path('api/radar/anfragen/<uuid:pk>/verwerfen/', views.api_radar_dismiss, name='api_radar_dismiss'),
    path('api/radar/anfragen/<uuid:pk>/sperren/', views.api_radar_block, name='api_radar_block'),
    path('api/radar/gruppe/<uuid:pk>/trennen/', views.api_radar_group_split, name='api_radar_group_split'),
    path('api/radar/gruppe/<uuid:pk>/mergen/', views.api_radar_group_merge, name='api_radar_group_merge'),

    # Radar Berater
    path('api/radar/berater/', views.api_radar_consultants, name='api_radar_consultants'),
    path('api/radar/berater/<uuid:pk>/bestaetigen/', views.api_radar_consultant_confirm, name='api_radar_consultant_confirm'),
    path('api/radar/berater/<uuid:pk>/verwerfen/', views.api_radar_consultant_dismiss, name='api_radar_consultant_dismiss'),
    path('api/radar/berater/einfuegen/', views.api_radar_paste, name='api_radar_paste'),

    # Regeln
    path('api/regeln/', views.api_regeln, name='api_regeln'),

    # Webhooks von abpe_scheduler (Kap. 0 — kein Celery Beat)
    path('api/webhook/<str:job_key>/', views.api_webhook_job, name='api_webhook_job'),
]
