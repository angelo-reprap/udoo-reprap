"""
abpe_crm/urls.py
"""
from django.urls import path
from . import views
from apps.abpe_crm import reporting_api
from . import views_ami
from .views_auth import login_view, logout_view
from .views_token import obtain_token_view

app_name = 'abpe_crm'

urlpatterns = [
    # ============================================================
    # AUTH
    # ============================================================
    path('login/',  login_view,  name='login'),
    path('logout/', logout_view, name='logout'),
    path('api/auth/token/', obtain_token_view, name='obtain_token'),

    # ============================================================
    # HTML Seiten
    # ============================================================
    path('',             views.index,      name='index'),
    path('berater/',     views.berater,    name='berater'),
    path('dms/',         views.edms,       name='edms'),
    path('kunden/',      views.kunden,     name='kunden'),
    path('emails/',      views.emails,     name='emails'),
    path('dokumente/',   views.dokumente,  name='dokumente'),
    path('reporting/',   views.reporting,  name='reporting'),

    # ============================================================
    # Telefon Studio  (Monitoring-/Steuer-Cockpit -> views_ami)
    # ============================================================
    path('telefon/',                    views.telefon,                        name='telefon'),

    # --- CDR / Anrufliste (bleibt views_cdr via views) ---
    path('api/telefon/cdr/',            views.api_telefon_cdr,                name='api_telefon_cdr'),
    path('api/cdr/contact/<str:crm_id>/', views.api_cdr_for_contact,          name='api_cdr_for_contact'),
    path('api/cdr/resolve/',            views.api_cdr_resolve,                name='api_cdr_resolve'),

    # --- Status / HUD ---
    path('api/telefon/peers/',          views_ami.api_telefon_peers,          name='api_telefon_peers'),
    path('api/telefon/extensions/',     views_ami.api_telefon_extensions,     name='api_telefon_extensions'),
    path('api/telefon/status/',         views_ami.api_telefon_status,         name='api_telefon_status'),
    path('api/telefon/stats/',          views_ami.api_telefon_stats,          name='api_telefon_stats'),
    path('api/telefon/hud/',            views_ami.api_telefon_hud,            name='api_telefon_hud'),
    path('api/telefon/transfer-targets/', views_ami.api_telefon_transfer_targets, name='api_telefon_transfer_targets'),
    path('api/telefon/fop/',            views_ami.api_telefon_fop,            name='api_telefon_fop'),

    # --- Waehlen / Click-to-Dial ---
    path('api/telefon/call/',           views_ami.api_telefon_call,           name='api_telefon_call'),
    path('api/telefon/dial/',           views_ami.api_telefon_dial,           name='api_telefon_dial'),

    # --- Anruf-Steuerung ---
    path('api/telefon/hangup/',         views_ami.api_telefon_hangup,         name='api_telefon_hangup'),
    path('api/telefon/redirect/',       views_ami.api_telefon_redirect,       name='api_telefon_redirect'),
    path('api/telefon/blind-transfer/', views_ami.api_telefon_blind_transfer, name='api_telefon_blind_transfer'),
    path('api/telefon/atxfer/',         views_ami.api_telefon_atxfer,         name='api_telefon_atxfer'),
    path('api/telefon/cancel-atxfer/',  views_ami.api_telefon_cancel_atxfer,  name='api_telefon_cancel_atxfer'),
    path('api/telefon/record/',         views_ami.api_telefon_record,         name='api_telefon_record'),

    # --- DND / FWD / Park ---
    path('api/telefon/dnd/',            views_ami.api_telefon_dnd,            name='api_telefon_dnd'),
    path('api/telefon/fwd/',            views_ami.api_telefon_fwd,            name='api_telefon_fwd'),
    path('api/telefon/fwd/set/',        views_ami.api_telefon_fwd_set,        name='api_telefon_fwd_set'),
    path('api/telefon/park/',           views_ami.api_telefon_park,           name='api_telefon_park'),
    path('api/telefon/presence/',       views_ami.api_telefon_presence,       name='api_telefon_presence'),
    path('api/telefon/steal/',          views_ami.api_telefon_steal,          name='api_telefon_steal'),
    path('api/telefon/barge/',          views_ami.api_telefon_barge,          name='api_telefon_barge'),

    # --- Konferenz-Cockpit ---
    path('api/telefon/conference/',     views_ami.api_telefon_conference,     name='api_telefon_conference'),
    path('api/telefon/conference-rooms/', views_ami.api_telefon_conference_rooms, name='api_telefon_conference_rooms'),
    path('api/conf/detail/',            views_ami.api_conf_detail,            name='api_conf_detail'),
    path('api/conf/member/',            views_ami.api_conf_member,            name='api_conf_member'),
    path('api/conf/lock/',              views_ami.api_conf_lock,              name='api_conf_lock'),
    path('api/conf/invite/',            views_ami.api_conf_invite,            name='api_conf_invite'),

    # --- Kunde-Koenig (Call-and-Drop) ---
    path('api/conf/pull-partner/',      views_ami.api_conf_pull_partner,      name='api_conf_pull_partner'),
    path('api/conf/join-self/',         views_ami.api_conf_join_self,         name='api_conf_join_self'),

    # --- Queues ---
    path('api/telefon/queues/',         views_ami.api_telefon_queues,         name='api_telefon_queues'),
    path('api/telefon/queue-member/',   views_ami.api_telefon_queue_member,   name='api_telefon_queue_member'),

    # --- Voicemail ---
    path('api/telefon/voicemail/',      views_ami.api_telefon_voicemail,      name='api_telefon_voicemail'),
    path('api/telefon/vmboxes/',        views_ami.api_telefon_vmboxes,        name='api_telefon_vmboxes'),

    # --- Protokoll / Notiz (DeepSeek) ---
    path('api/telefon/protokoll/',      views_ami.api_protokoll_format,       name='api_protokoll_format'),
    path('api/telefon/notiz/',          views_ami.api_notiz_format,           name='api_notiz_format'),
    path('api/telefon/wavnotes/',            views_ami.api_telefon_wavnotes,            name='api_telefon_wavnotes'),
    path('api/telefon/wavnotes/audio/',      views_ami.api_telefon_wavnote_audio,       name='api_telefon_wavnote_audio'),
    path('api/telefon/wavnotes/transcribe/', views_ami.api_telefon_wavnote_transcribe,  name='api_telefon_wavnote_transcribe'),
    path('api/telefon/wavnotes/save/',       views_ami.api_telefon_wavnote_save,        name='api_telefon_wavnote_save'),
    path('api/telefon/wavnotes/archive/',    views_ami.api_telefon_wavnote_archive,     name='api_telefon_wavnote_archive'),

    # ============================================================
    # API Berater
    # ============================================================
    path('api/berater/new/',                    views.api_berater_new,    name='api_berater_new'),
    path('api/contact/quick-create/',           views.api_contact_quick_create, name='api_contact_quick_create'),
    path('api/berater/',                        views.api_berater_list,   name='api_berater_list'),
    path('api/berater/<str:crm_id>/',           views.api_berater_detail, name='api_berater_detail'),
    path('api/berater/<str:crm_id>/delete/',    views.api_berater_delete, name='api_berater_delete'),

    # ============================================================
    # API Kunden
    # ============================================================
    path('api/kunden/new/',                     views.api_kunden_new,     name='api_kunden_new'),
    path('api/kunden/',                         views.api_kunden_list,    name='api_kunden_list'),
    path('api/kunden/<str:crm_id>/',            views.api_kunden_detail,  name='api_kunden_detail'),
    path('api/kunden/<str:crm_id>/delete/',     views.api_kunden_delete,  name='api_kunden_delete'),
    path('api/favoriten/',        views.api_favoriten_list,   name='api_favoriten_list'),
    path('api/favoriten/toggle/', views.api_favoriten_toggle, name='api_favoriten_toggle'),

    # ============================================================
    # API Contact / Account
    # ============================================================
    path('api/contact/<str:crm_id>/update/',       views.api_contact_update,       name='api_contact_update'),
    path('api/contact/<str:crm_id>/photo/',        views.api_contact_photo,        name='api_contact_photo'),
    path('api/contact/<str:crm_id>/link-account/', views.api_contact_link_account, name='api_contact_link_account'),
    path('api/account/<str:crm_id>/update/',       views.api_account_update,       name='api_account_update'),

    # ============================================================
    # API Notizen
    # ============================================================
    path('api/note/save/',                      views.api_note_save,      name='api_note_save'),
    path('api/recording/sync/',                 views.api_recording_sync, name='api_recording_sync'),
    path('api/recording/unassigned/',           views.api_recording_unassigned, name='api_recording_unassigned'),
    path('api/recording/contact/<str:crm_id>/', views.api_recording_for_contact, name='api_recording_for_contact'),
    path('api/notes/contact/<str:crm_id>/',     views.api_notes_for_contact, name='api_notes_for_contact'),
    path('api/recording/<int:rec_id>/audio/',   views.api_recording_audio,  name='api_recording_audio'),
    path('api/recording/<int:rec_id>/assign/',  views.api_recording_assign, name='api_recording_assign'),
    path('api/recording/<int:rec_id>/delete/',  views.api_recording_delete, name='api_recording_delete'),

    # ============================================================
    # API Dokumente
    # ============================================================
    path('api/dokumente/',                      views.api_dokumente_list, name='api_dokumente_list'),

    # ============================================================
    # API Emails
    # ============================================================
    path('api/emails/',                         views.api_emails_list,    name='api_emails_list'),
    path('api/email/templates/',                views.api_email_templates, name='api_email_templates'),
    path('api/email/send/',                     views.api_email_send,      name='api_email_send'),
    path('api/contacts/suggest/',               views.api_contacts_suggest, name='api_contacts_suggest'),

    # E-Mail Compose Fenster
    path('email/compose/', views.crm_email_compose, name='crm_email_compose'),

    # ============================================================
    # API Kampagne
    # ============================================================
    path('api/kampagne/list/',  views.api_kampagne_list,  name='api_kampagne_list'),
    path('api/kampagne/send/',  views.api_kampagne_send,  name='api_kampagne_send'),

    # ============================================================
    # API Sprachen
    # ============================================================
    path('api/available-languages/', views.api_available_languages, name='api_available_languages'),

    # ============================================================
    # API User Settings
    # ============================================================
    path('api/user-settings/', views.api_crm_user_settings, name='api_crm_user_settings'),

    # ============================================================
    # API Reporting / Sync
    # ============================================================
    path('api/sync/status/', views.api_sync_status, name='api_sync_status'),
    path('api/reporting/dashboard/', reporting_api.api_reporting_dashboard, name='api_reporting_dashboard'),
    path('api/reporting/sync/start/', reporting_api.api_reporting_sync_start, name='api_reporting_sync_start'),

    # ============================================================
    # SOFTPHONE PWA
    # ============================================================
    path('softphone/',                   views.softphone_app,            name='softphone_app'),
    path('softphone/sw.js',              views.softphone_sw,             name='softphone_sw'),
    path('api/softphone/contacts/',      views.api_softphone_contacts,   name='api_softphone_contacts'),
    path('api/softphone/languages/',     views.api_softphone_languages,  name='api_softphone_languages'),
]
