from django.urls import path
from . import views

app_name = 'abpe_meetme'

urlpatterns = [
    # Meetings
    path('api/meetings/', views.api_meeting_list, name='api_meeting_list'),
    path('api/meetings/create/', views.api_meeting_create, name='api_meeting_create'),
    path('api/meetings/<int:meeting_id>/', views.api_meeting_detail, name='api_meeting_detail'),
    path('api/meetings/<int:meeting_id>/update/', views.api_meeting_update, name='api_meeting_update'),
    path('api/meetings/<int:meeting_id>/cancel/', views.api_meeting_cancel, name='api_meeting_cancel'),
    path('api/meetings/<int:meeting_id>/reschedule/', views.api_meeting_reschedule, name='api_meeting_reschedule'),

    # Gaeste
    path('api/meetings/<int:meeting_id>/guests/create/', views.api_guest_create, name='api_guest_create'),
    path('api/guests/<int:guest_id>/update/', views.api_guest_update, name='api_guest_update'),
    path('api/guests/<int:guest_id>/delete/', views.api_guest_delete, name='api_guest_delete'),
    path('api/guests/<int:guest_id>/send-adhoc/', views.api_guest_send_adhoc, name='api_guest_send_adhoc'),
    path('api/meetings/<int:meeting_id>/invite-queue/', views.api_invite_queue, name='api_invite_queue'),
    path('api/guests/<int:guest_id>/invite-preview/', views.api_invite_preview, name='api_invite_preview'),
    path('api/guests/<int:guest_id>/invite-send/', views.api_invite_send, name='api_invite_send'),

    # Erinnerungsregeln
    path('api/meetings/<int:meeting_id>/reminder-rules/create/', views.api_reminder_rule_create, name='api_reminder_rule_create'),
    path('api/reminder-rules/<int:rule_id>/update/', views.api_reminder_rule_update, name='api_reminder_rule_update'),
    path('api/reminder-rules/<int:rule_id>/delete/', views.api_reminder_rule_delete, name='api_reminder_rule_delete'),

    # Sende-Assistent
    path('api/deliveries/queue/', views.api_delivery_queue, name='api_delivery_queue'),
    path('api/deliveries/<int:delivery_id>/mark-sent/', views.api_delivery_mark_sent, name='api_delivery_mark_sent'),
    path('api/deliveries/<int:delivery_id>/skip/', views.api_delivery_skip, name='api_delivery_skip'),

    # Webhook (von abpe_scheduler aufgerufen)
    path('api/webhook/reminder-due/', views.api_webhook_reminder_due, name='api_webhook_reminder_due'),

    # PBX/AMI
    path('api/rooms/', views.api_rooms_available, name='api_rooms_available'),

    path('api/deepseek-suggest/', views.api_deepseek_suggest, name='api_deepseek_suggest'),
    path('api/health/', views.api_health, name='api_health'),
]
