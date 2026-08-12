# ABpE — API- & Index-Inventar

_Automatisch generiert am 2026-07-04 14:44 via `gen_inventory.py` — nicht von Hand editieren, neu ausfuehren._

> Zweck: Ueberblick, welche Endpoints/Views + ES-Indizes bereits existieren,
> um Doppelbauten zu vermeiden und den Baukasten wiederzuverwenden.

## 1. HTTP-Endpoints (aus urls.py / Views)

Insgesamt **1670** URL-Patterns in **37** Apps/Modulen.

### abpe_backend  (5)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/admin/cvjob/dashboard/` | `simple_dashboard` | simple_dashboard |  |
| `/admin/cvjob/dashboard/minimal/` | `minimal_dashboard` | minimal_dashboard |  |
| `/crm-bridge/health/` | `<lambda>` |  |  |
| `/favicon.ico` | `<lambda>` |  |  |
| `/health/` | `<lambda>` |  |  |

### abpe_crm  (82)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/crm/` | `index` | index | CRM Startseite — leitet zu Berater-View |
| `/crm/api/account/<str:crm_id>/update/` | `api_account_update` | api_account_update | Universeller Update-Endpoint für CrmAccount + CrmAccountCstm |
| `/crm/api/auth/token/` | `obtain_token_view` | obtain_token |  |
| `/crm/api/available-languages/` | `api_available_languages` | api_available_languages |  |
| `/crm/api/berater/` | `api_berater_list` | api_berater_list | Berater suchen und listen |
| `/crm/api/berater/<str:crm_id>/` | `api_berater_detail` | api_berater_detail | Berater Detail — alle Felder |
| `/crm/api/berater/<str:crm_id>/delete/` | `api_berater_delete` | api_berater_delete | Berater (CrmContact) löschen |
| `/crm/api/berater/new/` | `api_berater_new` | api_berater_new | Neuen Berater anlegen |
| `/crm/api/cdr/contact/<str:crm_id>/` | `api_cdr_for_contact` | api_cdr_for_contact | Anruf-Verlauf eines Kontakts/einer Firma aus der lokalen CrmCdr-Tabelle. |
| `/crm/api/cdr/resolve/` | `api_cdr_resolve` | api_cdr_resolve | Pop-up-Resolver: eingehende Nummer -> Kontakt/Firma + Konfidenz. |
| `/crm/api/conf/detail/` | `view` | api_conf_detail |  |
| `/crm/api/conf/invite/` | `view` | api_conf_invite |  |
| `/crm/api/conf/join-self/` | `view` | api_conf_join_self |  |
| `/crm/api/conf/lock/` | `view` | api_conf_lock |  |
| `/crm/api/conf/member/` | `view` | api_conf_member |  |
| `/crm/api/conf/pull-partner/` | `view` | api_conf_pull_partner |  |
| `/crm/api/contact/<str:crm_id>/link-account/` | `api_contact_link_account` | api_contact_link_account |  |
| `/crm/api/contact/<str:crm_id>/photo/` | `api_contact_photo` | api_contact_photo |  |
| `/crm/api/contact/<str:crm_id>/update/` | `api_contact_update` | api_contact_update | Universeller Update-Endpoint für CrmContact + CrmContactCstm |
| `/crm/api/dokumente/` | `api_dokumente_list` | api_dokumente_list | Dokumente listen |
| `/crm/api/email/send/` | `api_email_send` | api_email_send | E-Mail aus Vorlage senden |
| `/crm/api/email/templates/` | `api_email_templates` | api_email_templates | Verfügbare E-Mail Vorlagen + Signaturen + Variablen + Module für CRM-Versand |
| `/crm/api/emails/` | `api_emails_list` | api_emails_list | Email-Adressen suchen und listen |
| `/crm/api/kampagne/list/` | `api_kampagne_list` | api_kampagne_list | Kampagnen-fähige E-Mail Adressen listen |
| `/crm/api/kampagne/send/` | `api_kampagne_send` | api_kampagne_send | Kampagnen-Versand |
| `/crm/api/kunden/` | `api_kunden_list` | api_kunden_list | Kunden suchen und listen |
| `/crm/api/kunden/<str:crm_id>/` | `api_kunden_detail` | api_kunden_detail | Kunden Detail mit Ansprechpartnern |
| `/crm/api/kunden/<str:crm_id>/delete/` | `api_kunden_delete` | api_kunden_delete | Kunden (CrmAccount) löschen |
| `/crm/api/kunden/new/` | `api_kunden_new` | api_kunden_new | Neuen Kunden anlegen |
| `/crm/api/note/save/` | `api_note_save` | api_note_save | Telefonnotiz speichern |
| `/crm/api/notes/contact/<str:crm_id>/` | `api_notes_for_contact` | api_notes_for_contact | Notizen (CrmContactNote) fuer einen Contact ODER Account per crm_id. |
| `/crm/api/recording/<int:rec_id>/assign/` | `_api_assign` | api_recording_assign | POST: Aufnahme nachträglich zuordnen (DB-Update, KEIN Datei-Rename). |
| `/crm/api/recording/<int:rec_id>/audio/` | `_api_audio` | api_recording_audio | GET: WAV streamen (Auth-geschützt, Range-fähig für <audio>-Seeking). |
| `/crm/api/recording/<int:rec_id>/delete/` | `_api_delete` | api_recording_delete | POST: Aufnahme löschen (DB-Satz + lokale Kopie; PBX-Original bleibt!). |
| `/crm/api/recording/contact/<str:crm_id>/` | `_api_for_contact` | api_recording_for_contact | GET: Aufnahmen eines Contacts ODER Accounts. |
| `/crm/api/recording/sync/` | `_api_sync` | api_recording_sync | POST: WAV von PBX holen + CrmCallRecording anlegen. |
| `/crm/api/recording/unassigned/` | `_api_unassigned` | api_recording_unassigned | GET: nicht zugeordnete Aufnahmen (is_assigned=False, nicht privat). |
| `/crm/api/softphone/contacts/` | `api_softphone_contacts` | api_softphone_contacts | contacts.json aus CRM generieren — fuer Softphone Kontakt-Lookup |
| `/crm/api/softphone/languages/` | `api_softphone_languages` | api_softphone_languages | Gibt Liste der verfügbaren Softphone-Sprachen zurück (scan i18n/*.json) |
| `/crm/api/sync/status/` | `api_sync_status` | api_sync_status | Sync-Statistiken |
| `/crm/api/telefon/atxfer/` | `view` | api_telefon_atxfer |  |
| `/crm/api/telefon/barge/` | `view` | api_telefon_barge |  |
| `/crm/api/telefon/blind-transfer/` | `view` | api_telefon_blind_transfer |  |
| `/crm/api/telefon/call/` | `view` | api_telefon_call |  |
| `/crm/api/telefon/cancel-atxfer/` | `view` | api_telefon_cancel_atxfer |  |
| `/crm/api/telefon/cdr/` | `api_telefon_cdr` | api_telefon_cdr | CDR-Anrufliste mit Kontakt-Matching gegen CrmPhoneBeanRel |
| `/crm/api/telefon/conference/` | `view` | api_telefon_conference |  |
| `/crm/api/telefon/dial/` | `view` | api_telefon_dial |  |
| `/crm/api/telefon/dnd/` | `view` | api_telefon_dnd |  |
| `/crm/api/telefon/extensions/` | `view` | api_telefon_extensions |  |
| `/crm/api/telefon/fop/` | `view` | api_telefon_fop |  |
| `/crm/api/telefon/fwd/` | `view` | api_telefon_fwd |  |
| `/crm/api/telefon/fwd/set/` | `view` | api_telefon_fwd_set |  |
| `/crm/api/telefon/hangup/` | `view` | api_telefon_hangup |  |
| `/crm/api/telefon/hud/` | `view` | api_telefon_hud |  |
| `/crm/api/telefon/notiz/` | `view` | api_notiz_format |  |
| `/crm/api/telefon/park/` | `view` | api_telefon_park |  |
| `/crm/api/telefon/peers/` | `view` | api_telefon_peers |  |
| `/crm/api/telefon/presence/` | `view` | api_telefon_presence |  |
| `/crm/api/telefon/protokoll/` | `view` | api_protokoll_format |  |
| `/crm/api/telefon/queue-member/` | `view` | api_telefon_queue_member |  |
| `/crm/api/telefon/queues/` | `view` | api_telefon_queues |  |
| `/crm/api/telefon/record/` | `view` | api_telefon_record |  |
| `/crm/api/telefon/redirect/` | `view` | api_telefon_redirect |  |
| `/crm/api/telefon/stats/` | `view` | api_telefon_stats |  |
| `/crm/api/telefon/status/` | `view` | api_telefon_status |  |
| `/crm/api/telefon/steal/` | `view` | api_telefon_steal |  |
| `/crm/api/telefon/vmboxes/` | `view` | api_telefon_vmboxes |  |
| `/crm/api/telefon/voicemail/` | `view` | api_telefon_voicemail |  |
| `/crm/api/user-settings/` | `api_crm_user_settings` | api_crm_user_settings | CRM-eigene User-Settings — unabhängig von abpe_ui |
| `/crm/berater/` | `berater` | berater | Berater-Liste |
| `/crm/dms/` | `edms` | edms |  |
| `/crm/dokumente/` | `dokumente` | dokumente | Dokumentenablage |
| `/crm/email/compose/` | `crm_email_compose` | crm_email_compose | E-Mail Compose — öffnet als neues Fenster, nutzt Email Studio Editor |
| `/crm/emails/` | `emails` | emails | E-Mail Adressen |
| `/crm/kunden/` | `kunden` | kunden | Kunden-Liste |
| `/crm/login/` | `login_view` | login |  |
| `/crm/logout/` | `logout_view` | logout |  |
| `/crm/reporting/` | `reporting` | reporting | Reporting & Sync-Log |
| `/crm/softphone/` | `softphone_app` | softphone_app | Softphone PWA — standalone HTML App |
| `/crm/softphone/sw.js` | `softphone_sw` | softphone_sw | Service Worker für Softphone PWA. |
| `/crm/telefon/` | `telefon` | telefon | Telefonanlage / CDR Studio |

### abpe_doc_studio  (28)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/doc-studio/` | `index` | index |  |
| `/doc-studio/api/blocks/` | `view` | api_block_list |  |
| `/doc-studio/api/blocks/<int:pk>/` | `view` | api_block_detail |  |
| `/doc-studio/api/fixtures/reload/` | `api_reload_fixtures` | api_fixtures_reload | POST /doc-studio/api/fixtures/reload/ — nur für Admins. |
| `/doc-studio/api/generate/` | `view` | api_generate |  |
| `/doc-studio/api/generate/async/` | `view` | api_generate_async |  |
| `/doc-studio/api/invoices/` | `view` | api_invoice_list |  |
| `/doc-studio/api/invoices/<uuid:pk>/` | `view` | api_invoice_detail |  |
| `/doc-studio/api/invoices/<uuid:pk>/generate/` | `view` | api_invoice_generate |  |
| `/doc-studio/api/layouts/` | `view` | api_layout_list |  |
| `/doc-studio/api/log/` | `view` | api_log_list |  |
| `/doc-studio/api/log/stats/` | `view` | api_log_stats |  |
| `/doc-studio/api/queue/` | `view` | api_queue_list |  |
| `/doc-studio/api/queue/<uuid:queue_id>/cancel/` | `view` | api_queue_cancel |  |
| `/doc-studio/api/styles/` | `view` | api_style_list |  |
| `/doc-studio/api/templates/` | `view` | api_template_list |  |
| `/doc-studio/api/templates/<int:pk>/` | `view` | api_template_detail |  |
| `/doc-studio/api/templates/<int:pk>/blocks/<int:tb_pk>/` | `view` | api_template_block_update | GET/PUT /api/templates/<pk>/blocks/<tb_pk>/ |
| `/doc-studio/api/templates/<int:pk>/blocks/reorder/` | `view` | api_template_block_reorder | PUT /api/templates/<pk>/blocks/reorder/ |
| `/doc-studio/api/templates/<int:pk>/duplicate/` | `view` | api_template_duplicate |  |
| `/doc-studio/api/templates/<int:pk>/generate/` | `view` | api_template_generate |  |
| `/doc-studio/api/templates/<int:pk>/preview/` | `view` | api_template_preview | Rendert eine Vorschau. |
| `/doc-studio/api/templates/<int:pk>/versions/` | `view` | api_template_versions |  |
| `/doc-studio/config/` | `config` | config |  |
| `/doc-studio/download/<str:log_id>/` | `download_doc` | download | Liefert eine generierte DOCX- oder PDF-Datei zum Download. |
| `/doc-studio/invoices/` | `invoices` | invoices |  |
| `/doc-studio/log/` | `log` | log |  |
| `/doc-studio/studio/` | `studio` | studio |  |

### abpe_edms  (17)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/edms/api/akte/<str:owner_type>/<str:crm_id>/` | `view` | api_akte | Die Akte eines Owners, nach DocType gruppiert (Reiter-Struktur). |
| `/edms/api/doctypes/` | `view` | api_doctypes | DocType-Liste für Filter-Dropdowns im Frontend. |
| `/edms/api/document/<uuid:uuid>/` | `view` | api_document | Dokument-Detail inkl. aller Versionen und Owner. |
| `/edms/api/document/<uuid:uuid>/archive/` | `view` | api_document_archive | status -> archiviert. |
| `/edms/api/document/<uuid:uuid>/owner/` | `view` | api_document_add_owner | Fügt einem Dokument einen Owner hinzu (idempotent). |
| `/edms/api/document/<uuid:uuid>/restore/` | `view` | api_document_restore | status archiviert -> gueltig. |
| `/edms/api/document/<uuid:uuid>/review-done/` | `view` | api_document_review_done | needs_review -> False (manuell als geprüft markiert). |
| `/edms/api/file/<uuid:uuid>/` | `view` | api_file | Streamt die Datei vom Share (Range-fähig für PDF-Viewer/Seeking). |
| `/edms/api/inbox/` | `view` | api_inbox | Posteingang: Dokumente, die noch zugeordnet/geprüft werden müssen. |
| `/edms/api/mail/attachment/` | `view` | api_mail_attachment | Liefert einen Mail-Anhang als Download (per Index aus api_mail_view). |
| `/edms/api/mail/attachment/preview/` | `view` | api_mail_attachment_preview | Mail-Anhang als Inline-Vorschau (PDF/Bild im iframe). |
| `/edms/api/mail/view/` | `view` | api_mail_view | EDMS-Mail-Detail: Header + Body + Anhang-Liste als JSON. |
| `/edms/api/person/<str:crm_id>/mails/` | `view` | api_person_mails | Mailbox-Mails einer Person, ermittelt über ihre CRM-E-Mail-Adressen. |
| `/edms/api/personen/` | `view` | api_personen | Owner-Aggregation über Dokumente + Aufnahmen + Mails. |
| `/edms/api/preview/<uuid:uuid>/` | `view` | api_preview | Vorschau-PDF (konvertiert bei Bedarf, gecacht). |
| `/edms/api/search/` | `view` | api_search | Gesamtsuche über Titel/Inhalt/Owner (Name, Stadt, Land, PLZ, E-Mail, |
| `/edms/api/search_all/` | `api_search_all` | api_search_all | Multi-Index-Suche. ?q=...&scope=all\|personen\|firmen\|dokumente\|mails&size=N |

### abpe_email_studio  (30)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/email-studio/` | `index` | index | Vorlagen gruppiert nach app_scope — Bibliothek. |
| `/email-studio/api/log/` | `view` | api-log-list |  |
| `/email-studio/api/log/stats/` | `view` | api-log-stats |  |
| `/email-studio/api/modules/` | `view` | api-module-list | Gibt alle Module zurück — für Modul-Panel im Studio. |
| `/email-studio/api/queue/` | `view` | api-queue-list |  |
| `/email-studio/api/queue/<str:queue_id>/cancel/` | `view` | api-queue-cancel |  |
| `/email-studio/api/send-async/` | `view` | api-send-async | Asynchroner Versand über Celery-Queue. |
| `/email-studio/api/send/` | `view` | api-send | Synchroner Versand — direkt per SMTP. |
| `/email-studio/api/senders/` | `view` | api-sender-list |  |
| `/email-studio/api/senders/<int:pk>/` | `view` | api-sender-detail |  |
| `/email-studio/api/senders/test-smtp/` | `view` | api-sender-smtp-test |  |
| `/email-studio/api/signatures/` | `view` | api-signature-list |  |
| `/email-studio/api/signatures/<int:pk>/` | `view` | api-signature-detail |  |
| `/email-studio/api/templates/` | `view` | api-template-list |  |
| `/email-studio/api/templates/<int:pk>/` | `view` | api-template-detail |  |
| `/email-studio/api/templates/<int:pk>/compatibility/` | `view` | api-template-compatibility |  |
| `/email-studio/api/templates/<int:pk>/duplicate/` | `view` | api-template-duplicate |  |
| `/email-studio/api/templates/<int:pk>/milestones/` | `view` | api-milestone-list | GET  /api/templates/<pk>/milestones/ |
| `/email-studio/api/templates/<int:pk>/milestones/<int:mid>/restore/` | `view` | api-milestone-restore | POST /api/templates/<pk>/milestones/<mid>/restore/ |
| `/email-studio/api/templates/<int:pk>/preview/` | `view` | api-template-preview |  |
| `/email-studio/api/templates/<int:pk>/send-test/` | `view` | api-template-send-test |  |
| `/email-studio/api/templates/<int:pk>/set-langs/` | `view` | api-template-set-langs | Aktiviert oder deaktiviert eine Sprache für ein Template. |
| `/email-studio/api/templates/<int:pk>/translate/` | `view` | api-template-translate | Übersetzt ein Template in eine oder mehrere Sprachen. |
| `/email-studio/api/templates/<int:pk>/translation/<str:lang>/` | `view` | api-translation-detail |  |
| `/email-studio/api/templates/<int:pk>/versions/` | `view` | api-template-versions |  |
| `/email-studio/api/templates/<int:pk>/versions/<int:version>/activate/` | `view` | api-template-version-activate |  |
| `/email-studio/api/variables/` | `view` | api-variables | Gibt alle bekannten Variablen zurück — kontextabhängig nach Quelle. |
| `/email-studio/config/` | `config` | config | SMTP · Absender-Konten · Signaturen — nur Admin. |
| `/email-studio/log/` | `log` | log | Protokoll aller gesendeten E-Mails mit Filter. |
| `/email-studio/studio/` | `studio` | studio | HTML-Editor mit Variablen-Panel, Vorschau und Versionsverlauf. |

### abpe_intake  (23)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/intake/` | `view` | dashboard | Dashboard für Intake Hub |
| `/intake/api/check-duplicate/` | `view` | api_check_duplicate | Platzhalter für API Endpoints |
| `/intake/api/presort/map/` | `view` | api_presort_map | Platzhalter für API Endpoints |
| `/intake/api/processing-status/<uuid:document_id>/` | `view` | api_processing_status | API für Verarbeitungsstatus |
| `/intake/api/upload/` | `view` | api_upload | Platzhalter für API Endpoints |
| `/intake/api/upload/file/upload/` | `view` | file_upload | API für Datei-Upload |
| `/intake/api/upload/status/<uuid:session_id>/` | `view` | upload_status | API für Upload-Status |
| `/intake/api/upload/text/import/` | `view` | text_import | API für Text-Import |
| `/intake/api/upload/url/import/` | `view` | url_import | API für URL Import (Einzel-URL und CSV-Liste) |
| `/intake/approval/<uuid:document_id>/` | `view` | approval | Platzhalter für noch nicht implementierte Views |
| `/intake/dashboard/` | `view` | dashboard_explicit | Dashboard für Intake Hub |
| `/intake/presort/<uuid:document_id>/` | `view` | presort | Platzhalter für noch nicht implementierte Views |
| `/intake/preview/<uuid:document_id>/` | `view` | preview | Dokument-Vorschau View |
| `/intake/processing/<uuid:job_id>/` | `view` | processing | Verarbeitungsstatus View |
| `/intake/result/<uuid:document_id>/` | `view` | result | Platzhalter für noch nicht implementierte Views |
| `/intake/review/<uuid:review_id>/` | `view` | review | Platzhalter für noch nicht implementierte Views |
| `/intake/status/` | `view` | status | System Status API |
| `/intake/upload/` | `view` | upload | Haupt-Upload Interface |
| `/intake/upload/csv/` | `view` | upload_csv | CSV Import View |
| `/intake/upload/email/` | `view` | upload_email | Email Import View |
| `/intake/upload/file/` | `view` | upload_file | Datei-Upload View |
| `/intake/upload/text/` | `view` | upload_text | Text-Eingabe View |
| `/intake/upload/url/` | `view` | upload_url | URL Import View |

### abpe_intranet_portal  (3)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/portal/` | `portal_dashboard` | dashboard | Main portal dashboard with all modules and quick access |
| `/portal/go/<slug:module_slug>/` | `module_redirect` | module_redirect | Redirect to module and track access history |
| `/portal/workspace/` | `my_workspace` | my_workspace | Personal workspace for the logged-in user |

### abpe_matching_workflow  (24)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/matching/` | `index` | index | Haupt-View — lädt alle Tabs via JS |
| `/matching/api/account/<str:account_crm_id>/requests/` | `api_account_requests` | api_account_requests | Projektanfragen einer Firma (crm_account_id) — read-only fuer Softphone Firma-Reiter. |
| `/matching/api/crm/accounts/` | `view` | api_crm_accounts | Suche in SuiteCRM accounts für Kunden-Auswahl |
| `/matching/api/crm/contacts/` | `view` | api_crm_contacts | Suche in SuiteCRM contacts für Ansprechpartner-Auswahl |
| `/matching/api/crm/sync/<uuid:project_id>/` | `view` | api_crm_sync |  |
| `/matching/api/match/<uuid:match_id>/` | `view` | api_match_detail |  |
| `/matching/api/match/<uuid:match_id>/call/` | `view` | api_call |  |
| `/matching/api/match/<uuid:match_id>/move/` | `view` | api_kanban_move |  |
| `/matching/api/match/<uuid:match_id>/placement/` | `view` | api_placement_details |  |
| `/matching/api/match/<uuid:match_id>/status/` | `view` | api_match_status |  |
| `/matching/api/reporting/` | `view` | api_reporting |  |
| `/matching/api/requests/` | `view` | api_project_list |  |
| `/matching/api/requests/<uuid:project_id>/` | `view` | api_project_detail |  |
| `/matching/api/requests/<uuid:project_id>/abschluss/` | `view` | api_abschluss |  |
| `/matching/api/requests/<uuid:project_id>/archive/` | `view` | api_project_archive |  |
| `/matching/api/requests/<uuid:project_id>/close/` | `view` | api_project_close |  |
| `/matching/api/requests/<uuid:project_id>/kanban/` | `view` | api_kanban |  |
| `/matching/api/requests/<uuid:project_id>/match/` | `view` | api_run_matching | Startet Matching-Celery-Task für ein Projekt |
| `/matching/api/requests/<uuid:project_id>/shortlist/` | `view` | api_shortlist | Shortlist-Ergebnisse für ein Projekt |
| `/matching/api/requests/<uuid:project_id>/update/` | `view` | api_project_update |  |
| `/matching/api/requests/create/` | `view` | api_project_create |  |
| `/matching/api/settings/` | `view` | api_settings_get |  |
| `/matching/api/settings/save/` | `view` | api_settings_save |  |
| `/matching/api/stats/` | `view` | api_stats |  |

### abpe_presort  (22)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/admin/abpe_presort/presortjob/<path:object_id>/commit/` | `commit_single_job` | presortjob_commit | Einzelnen Job über URL committen MIT VALIDIERUNG |
| `/admin/abpe_presort/presortjob/<path:object_id>/validate/` | `validate_single_job` | presortjob_validate | Einzelnen Job nur validieren |
| `/api/presort/^api/process/$` | `PresortAPIViewSet` | presort-api-process | Presort API Endpoints |
| `/api/presort/^api/process\.(?P<format>[a-z0-9]+)/?$` | `PresortAPIViewSet` | presort-api-process | Presort API Endpoints |
| `/api/presort/^jobs/$` | `PresortJobViewSet` | presort-job-list |  |
| `/api/presort/^jobs/(?P<pk>[^/.]+)/$` | `PresortJobViewSet` | presort-job-detail |  |
| `/api/presort/^jobs/(?P<pk>[^/.]+)/cancel/$` | `PresortJobViewSet` | presort-job-cancel |  |
| `/api/presort/^jobs/(?P<pk>[^/.]+)/cancel\.(?P<format>[a-z0-9]+)/?$` | `PresortJobViewSet` | presort-job-cancel |  |
| `/api/presort/^jobs/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | `PresortJobViewSet` | presort-job-detail |  |
| `/api/presort/^jobs\.(?P<format>[a-z0-9]+)/?$` | `PresortJobViewSet` | presort-job-list |  |
| `/api/presort/^results/$` | `PresortResultViewSet` | presort-result-list |  |
| `/api/presort/^results/(?P<pk>[^/.]+)/$` | `PresortResultViewSet` | presort-result-detail |  |
| `/api/presort/^results/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | `PresortResultViewSet` | presort-result-detail |  |
| `/api/presort/^results/by_job/$` | `PresortResultViewSet` | presort-result-by-job |  |
| `/api/presort/^results/by_job\.(?P<format>[a-z0-9]+)/?$` | `PresortResultViewSet` | presort-result-by-job |  |
| `/api/presort/^results\.(?P<format>[a-z0-9]+)/?$` | `PresortResultViewSet` | presort-result-list |  |
| `/api/presort/^templates/$` | `PresortTemplateViewSet` | presort-template-list |  |
| `/api/presort/^templates/(?P<pk>[^/.]+)/$` | `PresortTemplateViewSet` | presort-template-detail |  |
| `/api/presort/^templates/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | `PresortTemplateViewSet` | presort-template-detail |  |
| `/api/presort/^templates/active/$` | `PresortTemplateViewSet` | presort-template-active |  |
| `/api/presort/^templates/active\.(?P<format>[a-z0-9]+)/?$` | `PresortTemplateViewSet` | presort-template-active |  |
| `/api/presort/^templates\.(?P<format>[a-z0-9]+)/?$` | `PresortTemplateViewSet` | presort-template-list |  |

### abpe_profile  (9)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/profiles/` | `<lambda>` |  |  |
| `/profiles/api/` | `api_root` | api_root | Root API Endpoint |
| `/profiles/api/health/` | `api_health` | api_health | Öffentlicher Health Check Endpoint |
| `/profiles/api/profile/<str:profile_id>/` | `api_profile_detail` | api_profile_detail | API für Profil-Details |
| `/profiles/api/search/` | `api_search` | api_search | Öffentliche Such-API für Profile |
| `/profiles/api/stats/` | `api_stats` | api_stats | Statistiken-API |
| `/profiles/api/suggest/` | `api_search` | api_suggest | Öffentliche Such-API für Profile |
| `/profiles/old/` | `<lambda>` |  |  |
| `/profiles/search/` | `html_search_view` | html_search_view | HTML-Suchmaske für Profile |

### abpe_search  (12)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/search/` | `search_home` | search_home | Startseite der Suche (wie deine ABCONA Seite). |
| `/search/admin/` | `view` | admin_dashboard | Admin Dashboard für Search System Management. |
| `/search/admin/api-status/` | `admin_api_status` | admin_api_status | JSON API für Admin Status. |
| `/search/admin/logs/` | `view` | admin_logs | Admin View für Log-Anzeige. |
| `/search/admin/reindex/` | `view` | admin_reindex | Admin View für Index-Neuerstellung. |
| `/search/api/` | `view` | search_api | JSON API für die Namazu-basierte Suche. |
| `/search/api/schema/` | `view` | api_schema | OpenAPI Schema für das Search-System (kann von drf-spectacular verwendet werden). |
| `/search/api/stats/` | `view` | search_stats | Statistik-API für das Search-System. |
| `/search/api/status/` | `view` | index_status | Index Status und Health Check API. |
| `/search/profile/<str:profile_id>/` | `profile_detail_enhanced` | profile_detail_enhanced | Detailliertes Profil-Datenblatt (wie Birgit Kratz Seite). |
| `/search/profile/<str:profile_id>/<str:filename>/` | `profile_detail_enhanced` | profile_detail_with_file | Detailliertes Profil-Datenblatt (wie Birgit Kratz Seite). |
| `/search/results/` | `search_results` | search_results | Suchergebnisse-Seite (parst Namazu-Ausgabe). |

### abpe_ui  (62)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/` | `dashboard` | dashboard |  |
| `/<str:module_id>/` | `module_view` | module |  |
| `/<str:module_id>/<str:subpage>/` | `module_view` | module_subpage |  |
| `/api/^consultants/$` | `ConsultantViewSet` | consultant-list |  |
| `/api/^consultants/(?P<pk>[^/.]+)/$` | `ConsultantViewSet` | consultant-detail |  |
| `/api/^consultants/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | `ConsultantViewSet` | consultant-detail |  |
| `/api/^consultants\.(?P<format>[a-z0-9]+)/?$` | `ConsultantViewSet` | consultant-list |  |
| `/api/^cvs/$` | `CVViewSet` | cv-list |  |
| `/api/^cvs/my-cv/$` | `CVViewSet` | cv-my_cv |  |
| `/api/^cvs/my-cv\.(?P<format>[a-z0-9]+)/?$` | `CVViewSet` | cv-my_cv |  |
| `/api/^cvs\.(?P<format>[a-z0-9]+)/?$` | `CVViewSet` | cv-list |  |
| `/api/^emails/$` | `EmailViewSet` | email-list |  |
| `/api/^emails/unread-count/$` | `EmailViewSet` | email-unread_count |  |
| `/api/^emails/unread-count\.(?P<format>[a-z0-9]+)/?$` | `EmailViewSet` | email-unread_count |  |
| `/api/^emails\.(?P<format>[a-z0-9]+)/?$` | `EmailViewSet` | email-list |  |
| `/api/admin-portal/audit-log/` | `api_admin_audit_log` | api_admin_audit_log |  |
| `/api/admin-portal/backups/` | `api_admin_backups` | api_admin_backups |  |
| `/api/admin-portal/groups/` | `api_admin_groups` | api_admin_groups |  |
| `/api/admin-portal/groups/<int:gid>/module-permissions/` | `api_admin_group_module_permissions` | api_admin_group_module_permissions |  |
| `/api/admin-portal/modules/` | `api_admin_modules` | api_admin_modules |  |
| `/api/admin-portal/modules/<str:mid>/` | `api_admin_module_update` | api_admin_module_update |  |
| `/api/admin-portal/stats/` | `api_admin_stats` | api_admin_stats |  |
| `/api/admin-portal/users/` | `api_admin_users` | api_admin_users |  |
| `/api/admin-portal/users/<int:uid>/` | `api_admin_user_detail` | api_admin_user_detail |  |
| `/api/admin-portal/users/<int:uid>/module-permissions/` | `api_admin_user_module_permissions` | api_admin_user_module_permissions |  |
| `/api/admin-portal/users/<int:uid>/toggle/` | `api_admin_user_toggle` | api_admin_user_toggle |  |
| `/api/available-languages/` | `get_available_languages` | available_languages |  |
| `/api/components/actions/` | `view` | api_component_actions | GET /api/components/actions/ |
| `/api/components/badge/email/` | `view` | api_component_badge_email | GET /api/components/badge/email/ |
| `/api/components/recent-consultants/` | `view` | api_component_recent_consultants | GET /api/components/recent-consultants/ |
| `/api/components/recent-emails/` | `view` | api_component_recent_emails | GET /api/components/recent-emails/ |
| `/api/components/stats/` | `view` | api_component_stats | GET /api/components/stats/ |
| `/api/components/system/` | `view` | api_component_system | GET /api/components/system/ |
| `/api/cv-editor/consultant/<str:aid>/` | `api_cv_editor_consultant` | api_cv_editor_consultant |  |
| `/api/email/view/` | `api_email_view` | api_email_view |  |
| `/api/es/search/` | `api_es_search` | api_es_search |  |
| `/api/get-language/` | `get_language` | get_language |  |
| `/api/languages/add/` | `view` | lang_add |  |
| `/api/languages/available/` | `view` | lang_available |  |
| `/api/languages/hide/` | `view` | lang_hide |  |
| `/api/languages/list/` | `view` | lang_list |  |
| `/api/languages/show/` | `view` | lang_show |  |
| `/api/namazu/accounts/` | `api_namazu_accounts` | api_namazu_accounts |  |
| `/api/namazu/accounts/update/` | `api_namazu_accounts_update` | api_namazu_accounts_update |  |
| `/api/namazu/profile/` | `api_namazu_profile` | api_namazu_profile |  |
| `/api/namazu/reindex/` | `api_namazu_reindex` | api_namazu_reindex |  |
| `/api/namazu/search/` | `api_namazu_search` | api_namazu_search |  |
| `/api/namazu/status/` | `api_namazu_status` | api_namazu_status |  |
| `/api/recent-consultants/` | `api_recent_consultants` | api_recent_consultants |  |
| `/api/recent-emails/` | `api_recent_emails` | api_recent_emails |  |
| `/api/set-language/` | `set_language` | set_language |  |
| `/api/stats/` | `api_stats` | api_stats |  |
| `/api/system/` | `api_system_status` | api_system |  |
| `/api/user-settings/` | `api_user_settings` | api_user_settings |  |
| `/cv_editor/` | `cv_editor_view` | cv_editor |  |
| `/docs/` | `documentation_page` | docs |  |
| `/docs/<str:subpage>/` | `documentation_page` | docs_subpage |  |
| `/help/` | `help_page` | help |  |
| `/help/<str:topic>/` | `help_detail` | help_detail |  |
| `/login/` | `login_view` | login |  |
| `/logout/` | `logout_view` | logout |  |
| `/register/` | `register_view` | register |  |

### ai_cv_processor  (36)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/admin/ai_cv_processor/aicvdocument/<uuid:pk>/commit-json/` | `commit_json_view` | ai_cv_processor_aicvdocument_commit_json | Speichert editiertes JSON und erstellt neue Version (Commit) |
| `/admin/ai_cv_processor/aicvdocument/<uuid:pk>/edit-json/` | `edit_json_view` | ai_cv_processor_aicvdocument_edit_json | JSON-Editor View |
| `/admin/ai_cv_processor/aicvdocument/<uuid:pk>/projects/` | `projects_view` | ai_cv_processor_aicvdocument_projects | Projekte-Übersicht für CV |
| `/admin/ai_cv_processor/aicvdocument/stats/` | `stats_view` | ai_cv_processor_stats | Statistik-View für Dashboard |
| `/ai-cv/<uuid:doc_id>/match/` | `match_profile_view` | match_profile | Match ein CV mit einer Job-Anfrage |
| `/ai-cv/<uuid:doc_id>/matches/` | `match_history_view` | match_history | Zeigt die Match-Historie eines CVs |
| `/ai-cv/<uuid:doc_id>/projects/` | `project_list_view` | project_list | Listet alle Projekte eines CVs |
| `/ai-cv/<uuid:doc_id>/projects/add/` | `project_add_view` | project_add | Fügt ein neues Projekt hinzu |
| `/ai-cv/<uuid:doc_id>/recommendations/` | `recommendations_view` | recommendations | Zeigt KI-generierte Empfehlungen für ein CV |
| `/ai-cv/<uuid:doc_id>/technologies/` | `technology_list_view` | technology_list | Listet alle Technologie-Erfahrungen eines CVs |
| `/ai-cv/bulk/archive/` | `bulk_archive_view` | bulk_archive | Bulk-Archivierung von CVs |
| `/ai-cv/bulk/commit/` | `bulk_commit_view` | bulk_commit | Bulk-Commit von CVs |
| `/ai-cv/bulk/sync-crm/` | `bulk_sync_crm_view` | bulk_sync_crm | Bulk-Sync mit CRM |
| `/ai-cv/create/` | `create_view` | create | Erstellt ein neues CV |
| `/ai-cv/delete/<uuid:doc_id>/` | `delete_view` | delete | Löscht ein CV (Soft Delete = archivieren) |
| `/ai-cv/detail/<uuid:doc_id>/` | `detail_view` | detail | Zeigt ein CV mit allen Details an |
| `/ai-cv/export/<uuid:doc_id>/master.json/` | `export_master_json` | export_master_json | Exportiert master.json für ein CV (generiert aus DB) |
| `/ai-cv/export/all.json/` | `export_all_json` | export_all_json | Exportiert all.json mit aggregierten Statistiken |
| `/ai-cv/export/csv/` | `export_csv` | export_csv | Exportiert CVs als CSV |
| `/ai-cv/health/` | `health_view` | health | Health Check für Monitoring |
| `/ai-cv/import/` | `import_master_json_view` | import | Importiert eine master.json Datei |
| `/ai-cv/list/` | `list_view` | list | Listet alle CVs auf mit Filteroptionen |
| `/ai-cv/matching/scores/` | `matching_scores_view` | matching_scores | Globale Matching-Statistiken |
| `/ai-cv/projects/<uuid:project_id>/delete/` | `project_delete_view` | project_delete | Löscht ein Projekt |
| `/ai-cv/projects/<uuid:project_id>/edit/` | `project_edit_view` | project_edit | Bearbeitet ein Projekt |
| `/ai-cv/recommendations/<uuid:rec_id>/apply/` | `recommendation_apply_view` | recommendation_apply | Markiert eine Empfehlung als umgesetzt |
| `/ai-cv/search/` | `search_view` | search | Volltextsuche über CVs |
| `/ai-cv/search/advanced/` | `advanced_search_view` | advanced_search | Erweiterte Suche mit Filtern |
| `/ai-cv/search/suggest/` | `search_suggest_view` | search_suggest | Suchvorschläge (Autocomplete) |
| `/ai-cv/statistics/` | `statistics_view` | statistics | Aggregierte Statistiken |
| `/ai-cv/statistics/dashboard/` | `dashboard_view` | dashboard | Dashboard mit Key Metrics |
| `/ai-cv/statistics/industries/` | `industry_statistics_view` | industry_statistics | Branchen-Statistiken |
| `/ai-cv/statistics/technologies/` | `technology_statistics_view` | technology_statistics | Technologie-Statistiken |
| `/ai-cv/status/` | `status_view` | status | Status-Endpunkt mit Statistiken |
| `/ai-cv/technologies/<uuid:tech_id>/edit/` | `technology_edit_view` | technology_edit | Bearbeitet eine Technologie-Erfahrung |
| `/ai-cv/update/<uuid:doc_id>/` | `update_view` | update | Aktualisiert ein CV |

### ai_cv_prompt  (2)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/admin/ai_cv_prompt/prompttest/<path:object_id>/change/` | `change_view` | ai_cv_prompt_prompttest_change |  |
| `/admin/ai_cv_prompt/prompttest/run-test/<int:test_id>/` | `run_test_view` | ai_cv_prompt_run_test |  |

### ai_cv_training  (1)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/admin/ai_cv_training/extractionrule/` | `changelist_view` | ai_cv_training_extractionrule_changelist |  |

### api  (1)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/api/ai/chat/stream/` | `ai_chat_stream` | ai_chat_stream |  |

### auth_ldap  (3)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/admin/auth_ldap/ldapusersnapshot/` | `changelist_view` | auth_ldap_ldapusersnapshot_changelist |  |
| `/admin/auth_ldap/ldapusersnapshot/<int:pk>/analyze/` | `analyze_user_view` | auth_ldap_ldapusersnapshot_analyze | Custom View für User-Analyse |
| `/admin/auth_ldap/ldapusersnapshot/<int:pk>/sync/` | `sync_user_view` | auth_ldap_ldapusersnapshot_sync | Custom View für User-Synchronisation |

### automail_engine  (6)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/email/api/email/health/` | `view` | email-health | API for email search health check |
| `/email/api/email/reindex/` | `view` | email-reindex | API for reindexing emails (admin only) |
| `/email/api/email/search/` | `view` | email-search | API for searching EmailLogs |
| `/email/api/email/stats/` | `view` | email-stats | API for email statistics |
| `/email/api/email/timeline/` | `view` | email-timeline | API for email timeline |
| `/email/api/email/timeline/<str:person_id>/` | `view` | email-timeline-person | API for email timeline |

### cms  (36)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/admin/cms/page/` | `changelist_view` | cms_page_changelist |  |
| `/admin/cms/page/^([0-9]+)/([a-z\-]+)/edit-field/$` | `edit_title_fields` | cms_page_edit_title_fields |  |
| `/admin/cms/page/^([0-9]+)/actions-menu/$` | `actions_menu` | cms_page_actions_menu |  |
| `/admin/cms/page/^([0-9]+)/advanced-settings/$` | `advanced` | cms_page_advanced |  |
| `/admin/cms/page/^([0-9]+)/copy-page/$` | `copy_page` | cms_page_copy_page | Copy the page and all its plugins and descendants to the requested |
| `/admin/cms/page/^([0-9]+)/dialog/copy/$` | `get_copy_dialog` | cms_page_get_copy_dialog |  |
| `/admin/cms/page/^([0-9]+)/move-page/$` | `move_page` | cms_page_move_page | Move the page to the requested target, at the given position. |
| `/admin/cms/page/^([0-9]+)/permissions/$` | `get_permissions` | cms_page_get_permissions |  |
| `/admin/cms/page/^([0-9]+)/set-home/$` | `set_home` | cms_page_set_home |  |
| `/admin/cms/page/^list/$` | `get_list` | cms_page_get_list | This view is used by the PageSmartLinkWidget as the user type to feed the autocomplete drop-down. |
| `/admin/cms/pagecontent/` | `changelist_view` | cms_pagecontent_changelist |  |
| `/admin/cms/pagecontent/<path:object_id>/change/` | `change_view` | cms_pagecontent_change | The 'change' admin view for the PageContent model. |
| `/admin/cms/pagecontent/<path:object_id>/delete/` | `delete_view` | cms_pagecontent_delete |  |
| `/admin/cms/pagecontent/^([0-9]+)/change-template/$` | `change_template` | cms_pagecontent_change_template |  |
| `/admin/cms/pagecontent/^([0-9]+)/duplicate/$` | `duplicate` | cms_pagecontent_duplicate | Leverages the add view logic to duplicate the page. |
| `/admin/cms/pagecontent/^get-tree/$` | `get_tree` | cms_pagecontent_get_tree | Get html for the descendants (only) of given page or if no page_id is |
| `/admin/cms/pagecontent/add/` | `add_view` | cms_pagecontent_add |  |
| `/admin/cms/placeholder/^add-plugin/$` | `add_plugin` | cms_placeholder_add_plugin | Shows the add plugin form and saves it on POST. |
| `/admin/cms/placeholder/^clear-placeholder/([0-9]+)/$` | `clear_placeholder` | cms_placeholder_clear_placeholder |  |
| `/admin/cms/placeholder/^cms_wizard/^create/$` | `view` | cms_wizard_create |  |
| `/admin/cms/placeholder/^copy-plugins/$` | `copy_plugins` | cms_placeholder_copy_plugins | POST request should have the following data: |
| `/admin/cms/placeholder/^delete-plugin/([0-9]+)/$` | `delete_plugin` | cms_placeholder_delete_plugin |  |
| `/admin/cms/placeholder/^edit-field/([0-9]+)/([a-z\-]+)/$` | `edit_field` | cms_placeholder_edit_field | Endpoint which manages frontend-editable fields |
| `/admin/cms/placeholder/^edit-plugin/([0-9]+)/$` | `edit_plugin` | cms_placeholder_edit_plugin |  |
| `/admin/cms/placeholder/^move-plugin/$` | `move_plugin` | cms_placeholder_move_plugin | Performs a move or a "paste" operation (when «move_a_copy» is set) |
| `/admin/cms/placeholder/^object/([0-9]+)/edit/([0-9]+)/$` | `render_object_edit` | cms_placeholder_render_object_edit |  |
| `/admin/cms/placeholder/^object/([0-9]+)/preview/([0-9]+)/$` | `render_object_preview` | cms_placeholder_render_object_preview |  |
| `/admin/cms/placeholder/^object/([0-9]+)/structure/([0-9]+)/$` | `render_object_structure` | cms_placeholder_render_object_structure |  |
| `/admin/cms/usersettings/` | `change_view` | cms_usersettings_change |  |
| `/admin/cms/usersettings/^(.+)/$` | `change_view` | cms_usersettings_change |  |
| `/admin/cms/usersettings/cms-toolbar/` | `get_toolbar` | cms_usersettings_get_toolbar |  |
| `/admin/cms/usersettings/session_store/` | `session_store` | cms_usersettings_session_store | either POST or GET |
| `/cms/` | `details` | pages-root | The main view of the Django-CMS! Takes a request and a slug, renders the |
| `/cms/^(?P<slug>[0-9A-Za-z-_.//]+)/$` | `details` | pages-details-by-slug | The main view of the Django-CMS! Takes a request and a slug, renders the |
| `/cms/cms_login/` | `login` | cms_login |  |
| `/cms/cms_wizard/^create/$` | `view` | cms_wizard_create |  |

### crm_bridge  (4)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/crm-bridge/api/dashboard-stats/` | `view` | dashboard_stats |  |
| `/crm-bridge/api/modules/` | `view` | modules_list |  |
| `/crm-bridge/api/run-command/` | `view` | run_command |  |
| `/crm-bridge/api/system-status/` | `view` | system_status |  |

### cv_extractor  (31)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/cv-extractor/` | `index` | index |  |
| `/cv-extractor/api/check-duplicate/` | `check_duplicate_api` | check_duplicate | Prüft ob eine Person mit diesem Namen bereits existiert. |
| `/cv-extractor/api/cv-editor/<str:aid>/archive/` | `archive_consultant_api` | archive_consultant | Berater archivieren — status='archived', bleibt in DB erhalten |
| `/cv-extractor/api/cv-editor/<str:aid>/delete/` | `view` | delete_consultant | Löscht einen Consultant vollständig (DB + Dateien). |
| `/cv-extractor/api/cv-editor/<str:aid>/generate-word/` | `generate_word_api` | generate_word | Generiert ein Word-Dokument (.docx) fuer einen Consultant. |
| `/cv-extractor/api/cv-editor/<str:aid>/move-skill/` | `move_skill_api` | move_skill | Verschiebt einen Skill in eine andere Kategorie. |
| `/cv-extractor/api/cv-editor/<str:aid>/reactivate/` | `reactivate_consultant_api` | reactivate_consultant | Berater reaktivieren — status zurück auf completed |
| `/cv-extractor/api/cv-editor/<str:aid>/update/` | `editor_update_api` | editor_update | Speichert einen Abschnitt des CV-Editors in die DB. |
| `/cv-extractor/api/cv-editor/<str:aid>/validate/` | `view` | validate_consultant | Setzt validated=True/False für einen Consultant. |
| `/cv-extractor/api/extract/file/` | `view` | extract_file |  |
| `/cv-extractor/api/extract/text/` | `view` | extract_text |  |
| `/cv-extractor/api/flm-session/` | `freelancermap_session_api` | flm_session | GET:  Prüft ob Session-Cookies vorhanden und gültig sind |
| `/cv-extractor/api/gu-session/` | `gulp_session_api` | gulp_session | GET:  Prüft ob GULP Session-Cookies vorhanden sind |
| `/cv-extractor/api/import-url-to-db/` | `import_url_to_db_api` | import_url_to_db | Startet DB-Import für einen bereits geholten URL-Import. |
| `/cv-extractor/api/import-url/` | `import_url_api` | import_url | URL-Import Endpoint. |
| `/cv-extractor/api/import-url/pdf/` | `import_url_pdf_api` | import_url_pdf | PDF von Browser direkt empfangen und in url-Verzeichnis speichern. |
| `/cv-extractor/api/job/<int:job_id>/` | `view` | job_status |  |
| `/cv-extractor/api/job/<int:job_id>/reprocess/` | `view` | reprocess_job |  |
| `/cv-extractor/api/job/<int:job_id>/result/` | `view` | job_result |  |
| `/cv-extractor/api/jobs/` | `view` | list_jobs |  |
| `/cv-extractor/api/rename-url-dir/` | `rename_url_dir_api` | rename_url_dir | Benennt ein URL-Import-Verzeichnis um. |
| `/cv-extractor/api/settings/` | `settings_api` | settings |  |
| `/cv-extractor/api/templates-config/` | `templates_config_api` | templates_config |  |
| `/cv-extractor/api/upload/<int:upload_id>/status/` | `get_upload_status` | upload_status | Status eines laufenden oder abgeschlossenen Uploads abfragen. |
| `/cv-extractor/api/upload/async/` | `upload_pdf_api_async` | upload_pdf_async | PDF-Upload Endpunkt. |
| `/cv-extractor/api/uploads/` | `list_uploads_api` | list_uploads | Gibt alle UploadedPDF-Eintraege zurueck – neueste zuerst. |
| `/cv-extractor/api/url-platforms/` | `get_url_platforms` | url_platforms | Liefert url_platforms.json für das Frontend. |
| `/cv-extractor/api/word-templates/` | `view` | word_templates | Gibt alle Word-Templates aus templates_config.json zurueck. |
| `/cv-extractor/editor/<str:aid>/` | `editor_view` | editor |  |
| `/cv-extractor/health/` | `view` | health |  |
| `/cv-extractor/upload/` | `upload_page` | upload_page |  |

### cv_pipeline  (21)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/cv-pipeline/` | `dashboard` | dashboard | Dashboard mit Statistiken |
| `/cv-pipeline/api/enrich-all/` | `api_enrich_all` | api_enrich_all | Enricht alle Consultants |
| `/cv-pipeline/api/enrich/<str:aid>/` | `api_enrich_consultant` | api_enrich | Enricht einen einzelnen Consultant |
| `/cv-pipeline/api/search/` | `api_search` | api_search | API Search Endpoint |
| `/cv-pipeline/api/status/<str:aid>/` | `api_status` | api_status | API Status Endpoint |
| `/cv-pipeline/api/upload/` | `api_upload` | api_upload | REST API Upload Endpoint |
| `/cv-pipeline/batch/` | `batch_process` | batch | Batch-Verarbeitung |
| `/cv-pipeline/detail/<str:aid>/` | `cv_detail` | detail | Detailansicht eines CVs |
| `/cv-pipeline/detail/<str:aid>/<str:version>/` | `cv_detail_version` | detail_version | Detailansicht einer bestimmten Version |
| `/cv-pipeline/json/<str:aid>/` | `get_master_json` | master_json | Gibt master.json zurück (generiert aus DB) |
| `/cv-pipeline/json/<str:aid>/<str:version>/` | `get_master_json_version` | master_json_version | Gibt master.json einer bestimmten Version zurück |
| `/cv-pipeline/learning/patterns/` | `view_patterns` | patterns | Zeigt alle gelernten Patterns |
| `/cv-pipeline/learning/stats/` | `learning_stats` | learning_stats | Self-Learning Statistiken |
| `/cv-pipeline/list/` | `cv_list` | list | Liste aller CVs |
| `/cv-pipeline/pre/<str:aid>/` | `get_pre_json` | pre_json | Gibt extracted_json zurück (aus consultant.master_json_export) |
| `/cv-pipeline/process/<str:cv_id>/` | `process_cv` | process | CV Verarbeitung starten |
| `/cv-pipeline/stats/` | `stats` | stats | Statistiken Seite |
| `/cv-pipeline/test/extract/` | `test_extract` | test_extract | Testet Extraktion ohne Speicherung |
| `/cv-pipeline/test/parse/` | `test_parse` | test_parse | Testet Parsing |
| `/cv-pipeline/test/segment/` | `test_segment` | test_segment | Testet Segmentierung |
| `/cv-pipeline/upload/` | `upload_cv` | upload | CV Upload Formular |

### cv_processing  (1)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/api/health/health/` | `health_check` | cv_health_check | Health Check Endpoint |

### dashboard  (4)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/dashboard/` | `dashboard_home` | dashboard_home | Haupt-Dashboard mit allen KPIs und Charts |
| `/dashboard/charts/` | `dashboard_charts` | dashboard_charts | API für Chart-Daten als JSON |
| `/dashboard/kpis/` | `dashboard_kpis` | dashboard_kpis | API für KPI-Daten als JSON |
| `/dashboard/widgets/` | `dashboard_widgets` | dashboard_widgets | API für dynamische Widget-Updates |

### django  (1099)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/^data/(?P<path>.*)$` | `serve` |  | Serve static files below a given point in the directory structure. |
| `/^static/(?P<path>.*)$` | `serve` |  | Serve static files below a given point in the directory structure. |
| `/accounts/login/` | `view` | login | Display the login form and handle the login action. |
| `/accounts/logout/` | `view` | logout | Log out the user and display the 'You are logged out' message. |
| `/accounts/password_change/` | `view` | password_change |  |
| `/accounts/password_change/done/` | `view` | password_change_done |  |
| `/accounts/password_reset/` | `view` | password_reset |  |
| `/accounts/password_reset/done/` | `view` | password_reset_done |  |
| `/accounts/reset/<uidb64>/<token>/` | `view` | password_reset_confirm |  |
| `/accounts/reset/done/` | `view` | password_reset_complete |  |
| `/admin/` | `index` | index | Display the main admin index page, which lists all of the installed |
| `/admin/(?P<url>.*)$` | `catch_all_view` |  |  |
| `/admin/^(?P<app_label>auth\|sites\|authtoken\|cms\|filer\|djangocms_link\|djangocms_snippet\|ai_cv_prompt\|abe_admin\|abe_audit\|abe_core\|abpe_scheduler\|abpe_identity\|abpe_profile\|abpe_presort\|abpe_intake\|abpe_matching_workflow\|crm_bridge\|abpe_edms\|ingest_custom\|ingest_email\|ingest_pdf\|ingest_word\|ingest_csv\|ingest_txt\|ingest_url\|cv_pipeline\|cv_extractor\|ai_cv_processor\|ai_cv_training\|normalizer\|parser_json\|api\|auth_ldap\|automail_engine\|export_suitecrm\|legacy_emma\|dashboard\|documentation\|admin\|namazu\|abpe_ui\|abpe_email_studio\|abpe_doc_studio\|djangocms_versioning)/$` | `app_index` | app_list |  |
| `/admin/abe_admin/admintask/` | `changelist_view` | abe_admin_admintask_changelist | The 'change list' admin view for this model. |
| `/admin/abe_admin/admintask/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abe_admin/admintask/<path:object_id>/change/` | `change_view` | abe_admin_admintask_change |  |
| `/admin/abe_admin/admintask/<path:object_id>/delete/` | `delete_view` | abe_admin_admintask_delete |  |
| `/admin/abe_admin/admintask/<path:object_id>/history/` | `history_view` | abe_admin_admintask_history | The 'history' admin view for this model. |
| `/admin/abe_admin/admintask/add/` | `add_view` | abe_admin_admintask_add |  |
| `/admin/abe_admin/systembackup/` | `changelist_view` | abe_admin_systembackup_changelist | The 'change list' admin view for this model. |
| `/admin/abe_admin/systembackup/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abe_admin/systembackup/<path:object_id>/change/` | `change_view` | abe_admin_systembackup_change |  |
| `/admin/abe_admin/systembackup/<path:object_id>/delete/` | `delete_view` | abe_admin_systembackup_delete |  |
| `/admin/abe_admin/systembackup/<path:object_id>/history/` | `history_view` | abe_admin_systembackup_history | The 'history' admin view for this model. |
| `/admin/abe_admin/systembackup/add/` | `add_view` | abe_admin_systembackup_add |  |
| `/admin/abe_audit/auditlog/` | `changelist_view` | abe_audit_auditlog_changelist | The 'change list' admin view for this model. |
| `/admin/abe_audit/auditlog/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abe_audit/auditlog/<path:object_id>/change/` | `change_view` | abe_audit_auditlog_change |  |
| `/admin/abe_audit/auditlog/<path:object_id>/delete/` | `delete_view` | abe_audit_auditlog_delete |  |
| `/admin/abe_audit/auditlog/<path:object_id>/history/` | `history_view` | abe_audit_auditlog_history | The 'history' admin view for this model. |
| `/admin/abe_audit/auditlog/add/` | `add_view` | abe_audit_auditlog_add |  |
| `/admin/abe_core/applicationlog/` | `changelist_view` | abe_core_applicationlog_changelist | The 'change list' admin view for this model. |
| `/admin/abe_core/applicationlog/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abe_core/applicationlog/<path:object_id>/change/` | `change_view` | abe_core_applicationlog_change |  |
| `/admin/abe_core/applicationlog/<path:object_id>/delete/` | `delete_view` | abe_core_applicationlog_delete |  |
| `/admin/abe_core/applicationlog/<path:object_id>/history/` | `history_view` | abe_core_applicationlog_history | The 'history' admin view for this model. |
| `/admin/abe_core/applicationlog/add/` | `add_view` | abe_core_applicationlog_add |  |
| `/admin/abe_core/importjob/` | `changelist_view` | abe_core_importjob_changelist | The 'change list' admin view for this model. |
| `/admin/abe_core/importjob/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abe_core/importjob/<path:object_id>/change/` | `change_view` | abe_core_importjob_change |  |
| `/admin/abe_core/importjob/<path:object_id>/delete/` | `delete_view` | abe_core_importjob_delete |  |
| `/admin/abe_core/importjob/<path:object_id>/history/` | `history_view` | abe_core_importjob_history | The 'history' admin view for this model. |
| `/admin/abe_core/importjob/add/` | `add_view` | abe_core_importjob_add |  |
| `/admin/abe_core/systemconfig/` | `changelist_view` | abe_core_systemconfig_changelist | The 'change list' admin view for this model. |
| `/admin/abe_core/systemconfig/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abe_core/systemconfig/<path:object_id>/change/` | `change_view` | abe_core_systemconfig_change |  |
| `/admin/abe_core/systemconfig/<path:object_id>/delete/` | `delete_view` | abe_core_systemconfig_delete |  |
| `/admin/abe_core/systemconfig/<path:object_id>/history/` | `history_view` | abe_core_systemconfig_history | The 'history' admin view for this model. |
| `/admin/abe_core/systemconfig/add/` | `add_view` | abe_core_systemconfig_add |  |
| `/admin/abe_core/systemsetting/` | `changelist_view` | abe_core_systemsetting_changelist | The 'change list' admin view for this model. |
| `/admin/abe_core/systemsetting/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abe_core/systemsetting/<path:object_id>/change/` | `change_view` | abe_core_systemsetting_change |  |
| `/admin/abe_core/systemsetting/<path:object_id>/delete/` | `delete_view` | abe_core_systemsetting_delete |  |
| `/admin/abe_core/systemsetting/<path:object_id>/history/` | `history_view` | abe_core_systemsetting_history | The 'history' admin view for this model. |
| `/admin/abe_core/systemsetting/add/` | `add_view` | abe_core_systemsetting_add |  |
| `/admin/abpe_doc_studio/contentblock/` | `changelist_view` | abpe_doc_studio_contentblock_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_doc_studio/contentblock/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_doc_studio/contentblock/<path:object_id>/change/` | `change_view` | abpe_doc_studio_contentblock_change |  |
| `/admin/abpe_doc_studio/contentblock/<path:object_id>/delete/` | `delete_view` | abpe_doc_studio_contentblock_delete |  |
| `/admin/abpe_doc_studio/contentblock/<path:object_id>/history/` | `history_view` | abpe_doc_studio_contentblock_history | The 'history' admin view for this model. |
| `/admin/abpe_doc_studio/contentblock/add/` | `add_view` | abpe_doc_studio_contentblock_add |  |
| `/admin/abpe_doc_studio/doclog/` | `changelist_view` | abpe_doc_studio_doclog_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_doc_studio/doclog/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_doc_studio/doclog/<path:object_id>/change/` | `change_view` | abpe_doc_studio_doclog_change |  |
| `/admin/abpe_doc_studio/doclog/<path:object_id>/delete/` | `delete_view` | abpe_doc_studio_doclog_delete |  |
| `/admin/abpe_doc_studio/doclog/<path:object_id>/history/` | `history_view` | abpe_doc_studio_doclog_history | The 'history' admin view for this model. |
| `/admin/abpe_doc_studio/doclog/add/` | `add_view` | abpe_doc_studio_doclog_add |  |
| `/admin/abpe_doc_studio/docqueue/` | `changelist_view` | abpe_doc_studio_docqueue_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_doc_studio/docqueue/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_doc_studio/docqueue/<path:object_id>/change/` | `change_view` | abpe_doc_studio_docqueue_change |  |
| `/admin/abpe_doc_studio/docqueue/<path:object_id>/delete/` | `delete_view` | abpe_doc_studio_docqueue_delete |  |
| `/admin/abpe_doc_studio/docqueue/<path:object_id>/history/` | `history_view` | abpe_doc_studio_docqueue_history | The 'history' admin view for this model. |
| `/admin/abpe_doc_studio/docqueue/add/` | `add_view` | abpe_doc_studio_docqueue_add |  |
| `/admin/abpe_doc_studio/doctemplate/` | `changelist_view` | abpe_doc_studio_doctemplate_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_doc_studio/doctemplate/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_doc_studio/doctemplate/<path:object_id>/change/` | `change_view` | abpe_doc_studio_doctemplate_change |  |
| `/admin/abpe_doc_studio/doctemplate/<path:object_id>/delete/` | `delete_view` | abpe_doc_studio_doctemplate_delete |  |
| `/admin/abpe_doc_studio/doctemplate/<path:object_id>/history/` | `history_view` | abpe_doc_studio_doctemplate_history | The 'history' admin view for this model. |
| `/admin/abpe_doc_studio/doctemplate/add/` | `add_view` | abpe_doc_studio_doctemplate_add |  |
| `/admin/abpe_doc_studio/doctemplateversion/` | `changelist_view` | abpe_doc_studio_doctemplateversion_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_doc_studio/doctemplateversion/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_doc_studio/doctemplateversion/<path:object_id>/change/` | `change_view` | abpe_doc_studio_doctemplateversion_change |  |
| `/admin/abpe_doc_studio/doctemplateversion/<path:object_id>/delete/` | `delete_view` | abpe_doc_studio_doctemplateversion_delete |  |
| `/admin/abpe_doc_studio/doctemplateversion/<path:object_id>/history/` | `history_view` | abpe_doc_studio_doctemplateversion_history | The 'history' admin view for this model. |
| `/admin/abpe_doc_studio/doctemplateversion/add/` | `add_view` | abpe_doc_studio_doctemplateversion_add |  |
| `/admin/abpe_doc_studio/invoicerecord/` | `changelist_view` | abpe_doc_studio_invoicerecord_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_doc_studio/invoicerecord/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_doc_studio/invoicerecord/<path:object_id>/change/` | `change_view` | abpe_doc_studio_invoicerecord_change |  |
| `/admin/abpe_doc_studio/invoicerecord/<path:object_id>/delete/` | `delete_view` | abpe_doc_studio_invoicerecord_delete |  |
| `/admin/abpe_doc_studio/invoicerecord/<path:object_id>/history/` | `history_view` | abpe_doc_studio_invoicerecord_history | The 'history' admin view for this model. |
| `/admin/abpe_doc_studio/invoicerecord/add/` | `add_view` | abpe_doc_studio_invoicerecord_add |  |
| `/admin/abpe_doc_studio/pagelayout/` | `changelist_view` | abpe_doc_studio_pagelayout_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_doc_studio/pagelayout/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_doc_studio/pagelayout/<path:object_id>/change/` | `change_view` | abpe_doc_studio_pagelayout_change |  |
| `/admin/abpe_doc_studio/pagelayout/<path:object_id>/delete/` | `delete_view` | abpe_doc_studio_pagelayout_delete |  |
| `/admin/abpe_doc_studio/pagelayout/<path:object_id>/history/` | `history_view` | abpe_doc_studio_pagelayout_history | The 'history' admin view for this model. |
| `/admin/abpe_doc_studio/pagelayout/add/` | `add_view` | abpe_doc_studio_pagelayout_add |  |
| `/admin/abpe_doc_studio/styledefinition/` | `changelist_view` | abpe_doc_studio_styledefinition_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_doc_studio/styledefinition/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_doc_studio/styledefinition/<path:object_id>/change/` | `change_view` | abpe_doc_studio_styledefinition_change |  |
| `/admin/abpe_doc_studio/styledefinition/<path:object_id>/delete/` | `delete_view` | abpe_doc_studio_styledefinition_delete |  |
| `/admin/abpe_doc_studio/styledefinition/<path:object_id>/history/` | `history_view` | abpe_doc_studio_styledefinition_history | The 'history' admin view for this model. |
| `/admin/abpe_doc_studio/styledefinition/add/` | `add_view` | abpe_doc_studio_styledefinition_add |  |
| `/admin/abpe_doc_studio/stylekit/` | `changelist_view` | abpe_doc_studio_stylekit_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_doc_studio/stylekit/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_doc_studio/stylekit/<path:object_id>/change/` | `change_view` | abpe_doc_studio_stylekit_change |  |
| `/admin/abpe_doc_studio/stylekit/<path:object_id>/delete/` | `delete_view` | abpe_doc_studio_stylekit_delete |  |
| `/admin/abpe_doc_studio/stylekit/<path:object_id>/history/` | `history_view` | abpe_doc_studio_stylekit_history | The 'history' admin view for this model. |
| `/admin/abpe_doc_studio/stylekit/add/` | `add_view` | abpe_doc_studio_stylekit_add |  |
| `/admin/abpe_edms/crmdocument/` | `changelist_view` | abpe_edms_crmdocument_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_edms/crmdocument/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_edms/crmdocument/<path:object_id>/change/` | `change_view` | abpe_edms_crmdocument_change |  |
| `/admin/abpe_edms/crmdocument/<path:object_id>/delete/` | `delete_view` | abpe_edms_crmdocument_delete |  |
| `/admin/abpe_edms/crmdocument/<path:object_id>/history/` | `history_view` | abpe_edms_crmdocument_history | The 'history' admin view for this model. |
| `/admin/abpe_edms/crmdocument/add/` | `add_view` | abpe_edms_crmdocument_add |  |
| `/admin/abpe_edms/crmdocumentowner/` | `changelist_view` | abpe_edms_crmdocumentowner_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_edms/crmdocumentowner/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_edms/crmdocumentowner/<path:object_id>/change/` | `change_view` | abpe_edms_crmdocumentowner_change |  |
| `/admin/abpe_edms/crmdocumentowner/<path:object_id>/delete/` | `delete_view` | abpe_edms_crmdocumentowner_delete |  |
| `/admin/abpe_edms/crmdocumentowner/<path:object_id>/history/` | `history_view` | abpe_edms_crmdocumentowner_history | The 'history' admin view for this model. |
| `/admin/abpe_edms/crmdocumentowner/add/` | `add_view` | abpe_edms_crmdocumentowner_add |  |
| `/admin/abpe_edms/crmdocumentversion/` | `changelist_view` | abpe_edms_crmdocumentversion_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_edms/crmdocumentversion/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_edms/crmdocumentversion/<path:object_id>/change/` | `change_view` | abpe_edms_crmdocumentversion_change |  |
| `/admin/abpe_edms/crmdocumentversion/<path:object_id>/delete/` | `delete_view` | abpe_edms_crmdocumentversion_delete |  |
| `/admin/abpe_edms/crmdocumentversion/<path:object_id>/history/` | `history_view` | abpe_edms_crmdocumentversion_history | The 'history' admin view for this model. |
| `/admin/abpe_edms/crmdocumentversion/add/` | `add_view` | abpe_edms_crmdocumentversion_add |  |
| `/admin/abpe_edms/dmsarbeitspaket/` | `changelist_view` | abpe_edms_dmsarbeitspaket_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_edms/dmsarbeitspaket/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_edms/dmsarbeitspaket/<path:object_id>/change/` | `change_view` | abpe_edms_dmsarbeitspaket_change |  |
| `/admin/abpe_edms/dmsarbeitspaket/<path:object_id>/delete/` | `delete_view` | abpe_edms_dmsarbeitspaket_delete |  |
| `/admin/abpe_edms/dmsarbeitspaket/<path:object_id>/history/` | `history_view` | abpe_edms_dmsarbeitspaket_history | The 'history' admin view for this model. |
| `/admin/abpe_edms/dmsarbeitspaket/add/` | `add_view` | abpe_edms_dmsarbeitspaket_add |  |
| `/admin/abpe_edms/dmsdoctype/` | `changelist_view` | abpe_edms_dmsdoctype_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_edms/dmsdoctype/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_edms/dmsdoctype/<path:object_id>/change/` | `change_view` | abpe_edms_dmsdoctype_change |  |
| `/admin/abpe_edms/dmsdoctype/<path:object_id>/delete/` | `delete_view` | abpe_edms_dmsdoctype_delete |  |
| `/admin/abpe_edms/dmsdoctype/<path:object_id>/history/` | `history_view` | abpe_edms_dmsdoctype_history | The 'history' admin view for this model. |
| `/admin/abpe_edms/dmsdoctype/add/` | `add_view` | abpe_edms_dmsdoctype_add |  |
| `/admin/abpe_edms/dmsdocumentevent/` | `changelist_view` | abpe_edms_dmsdocumentevent_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_edms/dmsdocumentevent/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_edms/dmsdocumentevent/<path:object_id>/change/` | `change_view` | abpe_edms_dmsdocumentevent_change |  |
| `/admin/abpe_edms/dmsdocumentevent/<path:object_id>/delete/` | `delete_view` | abpe_edms_dmsdocumentevent_delete |  |
| `/admin/abpe_edms/dmsdocumentevent/<path:object_id>/history/` | `history_view` | abpe_edms_dmsdocumentevent_history | The 'history' admin view for this model. |
| `/admin/abpe_edms/dmsdocumentevent/add/` | `add_view` | abpe_edms_dmsdocumentevent_add |  |
| `/admin/abpe_edms/dmsdocumentlink/` | `changelist_view` | abpe_edms_dmsdocumentlink_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_edms/dmsdocumentlink/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_edms/dmsdocumentlink/<path:object_id>/change/` | `change_view` | abpe_edms_dmsdocumentlink_change |  |
| `/admin/abpe_edms/dmsdocumentlink/<path:object_id>/delete/` | `delete_view` | abpe_edms_dmsdocumentlink_delete |  |
| `/admin/abpe_edms/dmsdocumentlink/<path:object_id>/history/` | `history_view` | abpe_edms_dmsdocumentlink_history | The 'history' admin view for this model. |
| `/admin/abpe_edms/dmsdocumentlink/add/` | `add_view` | abpe_edms_dmsdocumentlink_add |  |
| `/admin/abpe_edms/dmsgewerk/` | `changelist_view` | abpe_edms_dmsgewerk_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_edms/dmsgewerk/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_edms/dmsgewerk/<path:object_id>/change/` | `change_view` | abpe_edms_dmsgewerk_change |  |
| `/admin/abpe_edms/dmsgewerk/<path:object_id>/delete/` | `delete_view` | abpe_edms_dmsgewerk_delete |  |
| `/admin/abpe_edms/dmsgewerk/<path:object_id>/history/` | `history_view` | abpe_edms_dmsgewerk_history | The 'history' admin view for this model. |
| `/admin/abpe_edms/dmsgewerk/add/` | `add_view` | abpe_edms_dmsgewerk_add |  |
| `/admin/abpe_edms/dmsleistungsposition/` | `changelist_view` | abpe_edms_dmsleistungsposition_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_edms/dmsleistungsposition/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_edms/dmsleistungsposition/<path:object_id>/change/` | `change_view` | abpe_edms_dmsleistungsposition_change |  |
| `/admin/abpe_edms/dmsleistungsposition/<path:object_id>/delete/` | `delete_view` | abpe_edms_dmsleistungsposition_delete |  |
| `/admin/abpe_edms/dmsleistungsposition/<path:object_id>/history/` | `history_view` | abpe_edms_dmsleistungsposition_history | The 'history' admin view for this model. |
| `/admin/abpe_edms/dmsleistungsposition/add/` | `add_view` | abpe_edms_dmsleistungsposition_add |  |
| `/admin/abpe_edms/dmsmetadatatype/` | `changelist_view` | abpe_edms_dmsmetadatatype_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_edms/dmsmetadatatype/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_edms/dmsmetadatatype/<path:object_id>/change/` | `change_view` | abpe_edms_dmsmetadatatype_change |  |
| `/admin/abpe_edms/dmsmetadatatype/<path:object_id>/delete/` | `delete_view` | abpe_edms_dmsmetadatatype_delete |  |
| `/admin/abpe_edms/dmsmetadatatype/<path:object_id>/history/` | `history_view` | abpe_edms_dmsmetadatatype_history | The 'history' admin view for this model. |
| `/admin/abpe_edms/dmsmetadatatype/add/` | `add_view` | abpe_edms_dmsmetadatatype_add |  |
| `/admin/abpe_edms/dmssyncrun/` | `changelist_view` | abpe_edms_dmssyncrun_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_edms/dmssyncrun/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_edms/dmssyncrun/<path:object_id>/change/` | `change_view` | abpe_edms_dmssyncrun_change |  |
| `/admin/abpe_edms/dmssyncrun/<path:object_id>/delete/` | `delete_view` | abpe_edms_dmssyncrun_delete |  |
| `/admin/abpe_edms/dmssyncrun/<path:object_id>/history/` | `history_view` | abpe_edms_dmssyncrun_history | The 'history' admin view for this model. |
| `/admin/abpe_edms/dmssyncrun/add/` | `add_view` | abpe_edms_dmssyncrun_add |  |
| `/admin/abpe_edms/dmstag/` | `changelist_view` | abpe_edms_dmstag_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_edms/dmstag/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_edms/dmstag/<path:object_id>/change/` | `change_view` | abpe_edms_dmstag_change |  |
| `/admin/abpe_edms/dmstag/<path:object_id>/delete/` | `delete_view` | abpe_edms_dmstag_delete |  |
| `/admin/abpe_edms/dmstag/<path:object_id>/history/` | `history_view` | abpe_edms_dmstag_history | The 'history' admin view for this model. |
| `/admin/abpe_edms/dmstag/add/` | `add_view` | abpe_edms_dmstag_add |  |
| `/admin/abpe_email_studio/emaillog/` | `changelist_view` | abpe_email_studio_emaillog_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_email_studio/emaillog/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_email_studio/emaillog/<path:object_id>/change/` | `change_view` | abpe_email_studio_emaillog_change |  |
| `/admin/abpe_email_studio/emaillog/<path:object_id>/delete/` | `delete_view` | abpe_email_studio_emaillog_delete |  |
| `/admin/abpe_email_studio/emaillog/<path:object_id>/history/` | `history_view` | abpe_email_studio_emaillog_history | The 'history' admin view for this model. |
| `/admin/abpe_email_studio/emaillog/add/` | `add_view` | abpe_email_studio_emaillog_add |  |
| `/admin/abpe_email_studio/emailmodule/` | `changelist_view` | abpe_email_studio_emailmodule_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_email_studio/emailmodule/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_email_studio/emailmodule/<path:object_id>/change/` | `change_view` | abpe_email_studio_emailmodule_change |  |
| `/admin/abpe_email_studio/emailmodule/<path:object_id>/delete/` | `delete_view` | abpe_email_studio_emailmodule_delete |  |
| `/admin/abpe_email_studio/emailmodule/<path:object_id>/history/` | `history_view` | abpe_email_studio_emailmodule_history | The 'history' admin view for this model. |
| `/admin/abpe_email_studio/emailmodule/add/` | `add_view` | abpe_email_studio_emailmodule_add |  |
| `/admin/abpe_email_studio/emailqueue/` | `changelist_view` | abpe_email_studio_emailqueue_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_email_studio/emailqueue/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_email_studio/emailqueue/<path:object_id>/change/` | `change_view` | abpe_email_studio_emailqueue_change |  |
| `/admin/abpe_email_studio/emailqueue/<path:object_id>/delete/` | `delete_view` | abpe_email_studio_emailqueue_delete |  |
| `/admin/abpe_email_studio/emailqueue/<path:object_id>/history/` | `history_view` | abpe_email_studio_emailqueue_history | The 'history' admin view for this model. |
| `/admin/abpe_email_studio/emailqueue/add/` | `add_view` | abpe_email_studio_emailqueue_add |  |
| `/admin/abpe_email_studio/emailsenderaccount/` | `changelist_view` | abpe_email_studio_emailsenderaccount_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_email_studio/emailsenderaccount/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_email_studio/emailsenderaccount/<path:object_id>/change/` | `change_view` | abpe_email_studio_emailsenderaccount_change |  |
| `/admin/abpe_email_studio/emailsenderaccount/<path:object_id>/delete/` | `delete_view` | abpe_email_studio_emailsenderaccount_delete |  |
| `/admin/abpe_email_studio/emailsenderaccount/<path:object_id>/history/` | `history_view` | abpe_email_studio_emailsenderaccount_history | The 'history' admin view for this model. |
| `/admin/abpe_email_studio/emailsenderaccount/add/` | `add_view` | abpe_email_studio_emailsenderaccount_add |  |
| `/admin/abpe_email_studio/emailsignature/` | `changelist_view` | abpe_email_studio_emailsignature_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_email_studio/emailsignature/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_email_studio/emailsignature/<path:object_id>/change/` | `change_view` | abpe_email_studio_emailsignature_change |  |
| `/admin/abpe_email_studio/emailsignature/<path:object_id>/delete/` | `delete_view` | abpe_email_studio_emailsignature_delete |  |
| `/admin/abpe_email_studio/emailsignature/<path:object_id>/history/` | `history_view` | abpe_email_studio_emailsignature_history | The 'history' admin view for this model. |
| `/admin/abpe_email_studio/emailsignature/add/` | `add_view` | abpe_email_studio_emailsignature_add |  |
| `/admin/abpe_email_studio/emailtemplate/` | `changelist_view` | abpe_email_studio_emailtemplate_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_email_studio/emailtemplate/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_email_studio/emailtemplate/<path:object_id>/change/` | `change_view` | abpe_email_studio_emailtemplate_change |  |
| `/admin/abpe_email_studio/emailtemplate/<path:object_id>/delete/` | `delete_view` | abpe_email_studio_emailtemplate_delete |  |
| `/admin/abpe_email_studio/emailtemplate/<path:object_id>/history/` | `history_view` | abpe_email_studio_emailtemplate_history | The 'history' admin view for this model. |
| `/admin/abpe_email_studio/emailtemplate/add/` | `add_view` | abpe_email_studio_emailtemplate_add |  |
| `/admin/abpe_identity/entity/` | `changelist_view` | abpe_identity_entity_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_identity/entity/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_identity/entity/<path:object_id>/change/` | `change_view` | abpe_identity_entity_change |  |
| `/admin/abpe_identity/entity/<path:object_id>/delete/` | `delete_view` | abpe_identity_entity_delete |  |
| `/admin/abpe_identity/entity/<path:object_id>/history/` | `history_view` | abpe_identity_entity_history | The 'history' admin view for this model. |
| `/admin/abpe_identity/entity/add/` | `add_view` | abpe_identity_entity_add |  |
| `/admin/abpe_identity/entityalias/` | `changelist_view` | abpe_identity_entityalias_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_identity/entityalias/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_identity/entityalias/<path:object_id>/change/` | `change_view` | abpe_identity_entityalias_change |  |
| `/admin/abpe_identity/entityalias/<path:object_id>/delete/` | `delete_view` | abpe_identity_entityalias_delete |  |
| `/admin/abpe_identity/entityalias/<path:object_id>/history/` | `history_view` | abpe_identity_entityalias_history | The 'history' admin view for this model. |
| `/admin/abpe_identity/entityalias/add/` | `add_view` | abpe_identity_entityalias_add |  |
| `/admin/abpe_identity/identityresolutionlog/` | `changelist_view` | abpe_identity_identityresolutionlog_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_identity/identityresolutionlog/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_identity/identityresolutionlog/<path:object_id>/change/` | `change_view` | abpe_identity_identityresolutionlog_change |  |
| `/admin/abpe_identity/identityresolutionlog/<path:object_id>/delete/` | `delete_view` | abpe_identity_identityresolutionlog_delete |  |
| `/admin/abpe_identity/identityresolutionlog/<path:object_id>/history/` | `history_view` | abpe_identity_identityresolutionlog_history | The 'history' admin view for this model. |
| `/admin/abpe_identity/identityresolutionlog/add/` | `add_view` | abpe_identity_identityresolutionlog_add |  |
| `/admin/abpe_intake/intakejob/` | `changelist_view` | abpe_intake_intakejob_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_intake/intakejob/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_intake/intakejob/<path:object_id>/change/` | `change_view` | abpe_intake_intakejob_change |  |
| `/admin/abpe_intake/intakejob/<path:object_id>/delete/` | `delete_view` | abpe_intake_intakejob_delete |  |
| `/admin/abpe_intake/intakejob/<path:object_id>/history/` | `history_view` | abpe_intake_intakejob_history | The 'history' admin view for this model. |
| `/admin/abpe_intake/intakejob/add/` | `add_view` | abpe_intake_intakejob_add |  |
| `/admin/abpe_intake/intakereview/` | `changelist_view` | abpe_intake_intakereview_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_intake/intakereview/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_intake/intakereview/<path:object_id>/change/` | `change_view` | abpe_intake_intakereview_change |  |
| `/admin/abpe_intake/intakereview/<path:object_id>/delete/` | `delete_view` | abpe_intake_intakereview_delete |  |
| `/admin/abpe_intake/intakereview/<path:object_id>/history/` | `history_view` | abpe_intake_intakereview_history | The 'history' admin view for this model. |
| `/admin/abpe_intake/intakereview/add/` | `add_view` | abpe_intake_intakereview_add |  |
| `/admin/abpe_intake/intakesource/` | `changelist_view` | abpe_intake_intakesource_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_intake/intakesource/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_intake/intakesource/<path:object_id>/change/` | `change_view` | abpe_intake_intakesource_change |  |
| `/admin/abpe_intake/intakesource/<path:object_id>/delete/` | `delete_view` | abpe_intake_intakesource_delete |  |
| `/admin/abpe_intake/intakesource/<path:object_id>/history/` | `history_view` | abpe_intake_intakesource_history | The 'history' admin view for this model. |
| `/admin/abpe_intake/intakesource/add/` | `add_view` | abpe_intake_intakesource_add |  |
| `/admin/abpe_intake/jobdocument/` | `changelist_view` | abpe_intake_jobdocument_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_intake/jobdocument/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_intake/jobdocument/<path:object_id>/change/` | `change_view` | abpe_intake_jobdocument_change |  |
| `/admin/abpe_intake/jobdocument/<path:object_id>/delete/` | `delete_view` | abpe_intake_jobdocument_delete |  |
| `/admin/abpe_intake/jobdocument/<path:object_id>/history/` | `history_view` | abpe_intake_jobdocument_history | The 'history' admin view for this model. |
| `/admin/abpe_intake/jobdocument/add/` | `add_view` | abpe_intake_jobdocument_add |  |
| `/admin/abpe_intake/rawdocument/` | `changelist_view` | abpe_intake_rawdocument_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_intake/rawdocument/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_intake/rawdocument/<path:object_id>/change/` | `change_view` | abpe_intake_rawdocument_change |  |
| `/admin/abpe_intake/rawdocument/<path:object_id>/delete/` | `delete_view` | abpe_intake_rawdocument_delete |  |
| `/admin/abpe_intake/rawdocument/<path:object_id>/history/` | `history_view` | abpe_intake_rawdocument_history | The 'history' admin view for this model. |
| `/admin/abpe_intake/rawdocument/add/` | `add_view` | abpe_intake_rawdocument_add |  |
| `/admin/abpe_matching_workflow/emailhistory/` | `changelist_view` | abpe_matching_workflow_emailhistory_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_matching_workflow/emailhistory/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_matching_workflow/emailhistory/<path:object_id>/change/` | `change_view` | abpe_matching_workflow_emailhistory_change |  |
| `/admin/abpe_matching_workflow/emailhistory/<path:object_id>/delete/` | `delete_view` | abpe_matching_workflow_emailhistory_delete |  |
| `/admin/abpe_matching_workflow/emailhistory/<path:object_id>/history/` | `history_view` | abpe_matching_workflow_emailhistory_history | The 'history' admin view for this model. |
| `/admin/abpe_matching_workflow/emailhistory/add/` | `add_view` | abpe_matching_workflow_emailhistory_add |  |
| `/admin/abpe_matching_workflow/emailtemplate/` | `changelist_view` | abpe_matching_workflow_emailtemplate_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_matching_workflow/emailtemplate/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_matching_workflow/emailtemplate/<path:object_id>/change/` | `change_view` | abpe_matching_workflow_emailtemplate_change |  |
| `/admin/abpe_matching_workflow/emailtemplate/<path:object_id>/delete/` | `delete_view` | abpe_matching_workflow_emailtemplate_delete |  |
| `/admin/abpe_matching_workflow/emailtemplate/<path:object_id>/history/` | `history_view` | abpe_matching_workflow_emailtemplate_history | The 'history' admin view for this model. |
| `/admin/abpe_matching_workflow/emailtemplate/add/` | `add_view` | abpe_matching_workflow_emailtemplate_add |  |
| `/admin/abpe_matching_workflow/followuprule/` | `changelist_view` | abpe_matching_workflow_followuprule_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_matching_workflow/followuprule/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_matching_workflow/followuprule/<path:object_id>/change/` | `change_view` | abpe_matching_workflow_followuprule_change |  |
| `/admin/abpe_matching_workflow/followuprule/<path:object_id>/delete/` | `delete_view` | abpe_matching_workflow_followuprule_delete |  |
| `/admin/abpe_matching_workflow/followuprule/<path:object_id>/history/` | `history_view` | abpe_matching_workflow_followuprule_history | The 'history' admin view for this model. |
| `/admin/abpe_matching_workflow/followuprule/add/` | `add_view` | abpe_matching_workflow_followuprule_add |  |
| `/admin/abpe_matching_workflow/matchresult/` | `changelist_view` | abpe_matching_workflow_matchresult_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_matching_workflow/matchresult/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_matching_workflow/matchresult/<path:object_id>/change/` | `change_view` | abpe_matching_workflow_matchresult_change |  |
| `/admin/abpe_matching_workflow/matchresult/<path:object_id>/delete/` | `delete_view` | abpe_matching_workflow_matchresult_delete |  |
| `/admin/abpe_matching_workflow/matchresult/<path:object_id>/history/` | `history_view` | abpe_matching_workflow_matchresult_history | The 'history' admin view for this model. |
| `/admin/abpe_matching_workflow/matchresult/add/` | `add_view` | abpe_matching_workflow_matchresult_add |  |
| `/admin/abpe_matching_workflow/projectconsultant/` | `changelist_view` | abpe_matching_workflow_projectconsultant_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_matching_workflow/projectconsultant/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_matching_workflow/projectconsultant/<path:object_id>/change/` | `change_view` | abpe_matching_workflow_projectconsultant_change |  |
| `/admin/abpe_matching_workflow/projectconsultant/<path:object_id>/delete/` | `delete_view` | abpe_matching_workflow_projectconsultant_delete |  |
| `/admin/abpe_matching_workflow/projectconsultant/<path:object_id>/history/` | `history_view` | abpe_matching_workflow_projectconsultant_history | The 'history' admin view for this model. |
| `/admin/abpe_matching_workflow/projectconsultant/add/` | `add_view` | abpe_matching_workflow_projectconsultant_add |  |
| `/admin/abpe_matching_workflow/projectcontact/` | `changelist_view` | abpe_matching_workflow_projectcontact_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_matching_workflow/projectcontact/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_matching_workflow/projectcontact/<path:object_id>/change/` | `change_view` | abpe_matching_workflow_projectcontact_change |  |
| `/admin/abpe_matching_workflow/projectcontact/<path:object_id>/delete/` | `delete_view` | abpe_matching_workflow_projectcontact_delete |  |
| `/admin/abpe_matching_workflow/projectcontact/<path:object_id>/history/` | `history_view` | abpe_matching_workflow_projectcontact_history | The 'history' admin view for this model. |
| `/admin/abpe_matching_workflow/projectcontact/add/` | `add_view` | abpe_matching_workflow_projectcontact_add |  |
| `/admin/abpe_matching_workflow/projectrequest/` | `changelist_view` | abpe_matching_workflow_projectrequest_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_matching_workflow/projectrequest/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_matching_workflow/projectrequest/<path:object_id>/change/` | `change_view` | abpe_matching_workflow_projectrequest_change |  |
| `/admin/abpe_matching_workflow/projectrequest/<path:object_id>/delete/` | `delete_view` | abpe_matching_workflow_projectrequest_delete |  |
| `/admin/abpe_matching_workflow/projectrequest/<path:object_id>/history/` | `history_view` | abpe_matching_workflow_projectrequest_history | The 'history' admin view for this model. |
| `/admin/abpe_matching_workflow/projectrequest/add/` | `add_view` | abpe_matching_workflow_projectrequest_add |  |
| `/admin/abpe_presort/presortjob/` | `changelist_view` | abpe_presort_presortjob_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_presort/presortjob/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_presort/presortjob/<path:object_id>/change/` | `change_view` | abpe_presort_presortjob_change |  |
| `/admin/abpe_presort/presortjob/<path:object_id>/delete/` | `delete_view` | abpe_presort_presortjob_delete |  |
| `/admin/abpe_presort/presortjob/<path:object_id>/history/` | `history_view` | abpe_presort_presortjob_history | The 'history' admin view for this model. |
| `/admin/abpe_presort/presortjob/add/` | `add_view` | abpe_presort_presortjob_add |  |
| `/admin/abpe_presort/presortresult/` | `changelist_view` | abpe_presort_presortresult_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_presort/presortresult/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_presort/presortresult/<path:object_id>/change/` | `change_view` | abpe_presort_presortresult_change |  |
| `/admin/abpe_presort/presortresult/<path:object_id>/delete/` | `delete_view` | abpe_presort_presortresult_delete |  |
| `/admin/abpe_presort/presortresult/<path:object_id>/history/` | `history_view` | abpe_presort_presortresult_history | The 'history' admin view for this model. |
| `/admin/abpe_presort/presortresult/add/` | `add_view` | abpe_presort_presortresult_add |  |
| `/admin/abpe_presort/presorttemplate/` | `changelist_view` | abpe_presort_presorttemplate_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_presort/presorttemplate/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_presort/presorttemplate/<path:object_id>/change/` | `change_view` | abpe_presort_presorttemplate_change |  |
| `/admin/abpe_presort/presorttemplate/<path:object_id>/delete/` | `delete_view` | abpe_presort_presorttemplate_delete |  |
| `/admin/abpe_presort/presorttemplate/<path:object_id>/history/` | `history_view` | abpe_presort_presorttemplate_history | The 'history' admin view for this model. |
| `/admin/abpe_presort/presorttemplate/add/` | `add_view` | abpe_presort_presorttemplate_add |  |
| `/admin/abpe_profile/aidregistry/` | `changelist_view` | abpe_profile_aidregistry_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_profile/aidregistry/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_profile/aidregistry/<path:object_id>/change/` | `change_view` | abpe_profile_aidregistry_change |  |
| `/admin/abpe_profile/aidregistry/<path:object_id>/delete/` | `delete_view` | abpe_profile_aidregistry_delete |  |
| `/admin/abpe_profile/aidregistry/<path:object_id>/history/` | `history_view` | abpe_profile_aidregistry_history | The 'history' admin view for this model. |
| `/admin/abpe_profile/aidregistry/add/` | `add_view` | abpe_profile_aidregistry_add |  |
| `/admin/abpe_profile/profile/` | `changelist_view` | abpe_profile_profile_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_profile/profile/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_profile/profile/<path:object_id>/change/` | `change_view` | abpe_profile_profile_change |  |
| `/admin/abpe_profile/profile/<path:object_id>/delete/` | `delete_view` | abpe_profile_profile_delete |  |
| `/admin/abpe_profile/profile/<path:object_id>/history/` | `history_view` | abpe_profile_profile_history | The 'history' admin view for this model. |
| `/admin/abpe_profile/profile/add/` | `add_view` | abpe_profile_profile_add |  |
| `/admin/abpe_profile/profileversion/` | `changelist_view` | abpe_profile_profileversion_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_profile/profileversion/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_profile/profileversion/<path:object_id>/change/` | `change_view` | abpe_profile_profileversion_change |  |
| `/admin/abpe_profile/profileversion/<path:object_id>/delete/` | `delete_view` | abpe_profile_profileversion_delete |  |
| `/admin/abpe_profile/profileversion/<path:object_id>/history/` | `history_view` | abpe_profile_profileversion_history | The 'history' admin view for this model. |
| `/admin/abpe_profile/profileversion/add/` | `add_view` | abpe_profile_profileversion_add |  |
| `/admin/abpe_scheduler/scheduledtask/` | `changelist_view` | abpe_scheduler_scheduledtask_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_scheduler/scheduledtask/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_scheduler/scheduledtask/<path:object_id>/change/` | `change_view` | abpe_scheduler_scheduledtask_change |  |
| `/admin/abpe_scheduler/scheduledtask/<path:object_id>/delete/` | `delete_view` | abpe_scheduler_scheduledtask_delete |  |
| `/admin/abpe_scheduler/scheduledtask/<path:object_id>/history/` | `history_view` | abpe_scheduler_scheduledtask_history | The 'history' admin view for this model. |
| `/admin/abpe_scheduler/scheduledtask/add/` | `add_view` | abpe_scheduler_scheduledtask_add |  |
| `/admin/abpe_scheduler/taskexecution/` | `changelist_view` | abpe_scheduler_taskexecution_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_scheduler/taskexecution/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_scheduler/taskexecution/<path:object_id>/change/` | `change_view` | abpe_scheduler_taskexecution_change |  |
| `/admin/abpe_scheduler/taskexecution/<path:object_id>/delete/` | `delete_view` | abpe_scheduler_taskexecution_delete |  |
| `/admin/abpe_scheduler/taskexecution/<path:object_id>/history/` | `history_view` | abpe_scheduler_taskexecution_history | The 'history' admin view for this model. |
| `/admin/abpe_scheduler/taskexecution/add/` | `add_view` | abpe_scheduler_taskexecution_add |  |
| `/admin/abpe_ui/beraterprofil/` | `changelist_view` | abpe_ui_beraterprofil_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_ui/beraterprofil/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_ui/beraterprofil/<path:object_id>/change/` | `change_view` | abpe_ui_beraterprofil_change |  |
| `/admin/abpe_ui/beraterprofil/<path:object_id>/delete/` | `delete_view` | abpe_ui_beraterprofil_delete |  |
| `/admin/abpe_ui/beraterprofil/<path:object_id>/history/` | `history_view` | abpe_ui_beraterprofil_history | The 'history' admin view for this model. |
| `/admin/abpe_ui/beraterprofil/add/` | `add_view` | abpe_ui_beraterprofil_add |  |
| `/admin/abpe_ui/usersettings/` | `changelist_view` | abpe_ui_usersettings_changelist | The 'change list' admin view for this model. |
| `/admin/abpe_ui/usersettings/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/abpe_ui/usersettings/<path:object_id>/change/` | `change_view` | abpe_ui_usersettings_change |  |
| `/admin/abpe_ui/usersettings/<path:object_id>/delete/` | `delete_view` | abpe_ui_usersettings_delete |  |
| `/admin/abpe_ui/usersettings/<path:object_id>/history/` | `history_view` | abpe_ui_usersettings_history | The 'history' admin view for this model. |
| `/admin/abpe_ui/usersettings/add/` | `add_view` | abpe_ui_usersettings_add |  |
| `/admin/admin/logentry/` | `changelist_view` | admin_logentry_changelist | The 'change list' admin view for this model. |
| `/admin/admin/logentry/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/admin/logentry/<path:object_id>/change/` | `change_view` | admin_logentry_change |  |
| `/admin/admin/logentry/<path:object_id>/delete/` | `delete_view` | admin_logentry_delete |  |
| `/admin/admin/logentry/<path:object_id>/history/` | `history_view` | admin_logentry_history | The 'history' admin view for this model. |
| `/admin/admin/logentry/add/` | `add_view` | admin_logentry_add |  |
| `/admin/ai_cv_processor/aicvdocument/` | `changelist_view` | ai_cv_processor_aicvdocument_changelist | The 'change list' admin view for this model. |
| `/admin/ai_cv_processor/aicvdocument/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ai_cv_processor/aicvdocument/<path:object_id>/change/` | `change_view` | ai_cv_processor_aicvdocument_change |  |
| `/admin/ai_cv_processor/aicvdocument/<path:object_id>/delete/` | `delete_view` | ai_cv_processor_aicvdocument_delete |  |
| `/admin/ai_cv_processor/aicvdocument/<path:object_id>/history/` | `history_view` | ai_cv_processor_aicvdocument_history | The 'history' admin view for this model. |
| `/admin/ai_cv_processor/aicvdocument/add/` | `add_view` | ai_cv_processor_aicvdocument_add |  |
| `/admin/ai_cv_processor/globalstatistics/` | `changelist_view` | ai_cv_processor_globalstatistics_changelist | The 'change list' admin view for this model. |
| `/admin/ai_cv_processor/globalstatistics/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ai_cv_processor/globalstatistics/<path:object_id>/change/` | `change_view` | ai_cv_processor_globalstatistics_change |  |
| `/admin/ai_cv_processor/globalstatistics/<path:object_id>/delete/` | `delete_view` | ai_cv_processor_globalstatistics_delete |  |
| `/admin/ai_cv_processor/globalstatistics/<path:object_id>/history/` | `history_view` | ai_cv_processor_globalstatistics_history | The 'history' admin view for this model. |
| `/admin/ai_cv_processor/globalstatistics/add/` | `add_view` | ai_cv_processor_globalstatistics_add |  |
| `/admin/ai_cv_processor/industryexperience/` | `changelist_view` | ai_cv_processor_industryexperience_changelist | The 'change list' admin view for this model. |
| `/admin/ai_cv_processor/industryexperience/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ai_cv_processor/industryexperience/<path:object_id>/change/` | `change_view` | ai_cv_processor_industryexperience_change |  |
| `/admin/ai_cv_processor/industryexperience/<path:object_id>/delete/` | `delete_view` | ai_cv_processor_industryexperience_delete |  |
| `/admin/ai_cv_processor/industryexperience/<path:object_id>/history/` | `history_view` | ai_cv_processor_industryexperience_history | The 'history' admin view for this model. |
| `/admin/ai_cv_processor/industryexperience/add/` | `add_view` | ai_cv_processor_industryexperience_add |  |
| `/admin/ai_cv_processor/matchingscore/` | `changelist_view` | ai_cv_processor_matchingscore_changelist | The 'change list' admin view for this model. |
| `/admin/ai_cv_processor/matchingscore/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ai_cv_processor/matchingscore/<path:object_id>/change/` | `change_view` | ai_cv_processor_matchingscore_change |  |
| `/admin/ai_cv_processor/matchingscore/<path:object_id>/delete/` | `delete_view` | ai_cv_processor_matchingscore_delete |  |
| `/admin/ai_cv_processor/matchingscore/<path:object_id>/history/` | `history_view` | ai_cv_processor_matchingscore_history | The 'history' admin view for this model. |
| `/admin/ai_cv_processor/matchingscore/add/` | `add_view` | ai_cv_processor_matchingscore_add |  |
| `/admin/ai_cv_processor/project/` | `changelist_view` | ai_cv_processor_project_changelist | The 'change list' admin view for this model. |
| `/admin/ai_cv_processor/project/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ai_cv_processor/project/<path:object_id>/change/` | `change_view` | ai_cv_processor_project_change |  |
| `/admin/ai_cv_processor/project/<path:object_id>/delete/` | `delete_view` | ai_cv_processor_project_delete |  |
| `/admin/ai_cv_processor/project/<path:object_id>/history/` | `history_view` | ai_cv_processor_project_history | The 'history' admin view for this model. |
| `/admin/ai_cv_processor/project/add/` | `add_view` | ai_cv_processor_project_add |  |
| `/admin/ai_cv_processor/recommendation/` | `changelist_view` | ai_cv_processor_recommendation_changelist | The 'change list' admin view for this model. |
| `/admin/ai_cv_processor/recommendation/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ai_cv_processor/recommendation/<path:object_id>/change/` | `change_view` | ai_cv_processor_recommendation_change |  |
| `/admin/ai_cv_processor/recommendation/<path:object_id>/delete/` | `delete_view` | ai_cv_processor_recommendation_delete |  |
| `/admin/ai_cv_processor/recommendation/<path:object_id>/history/` | `history_view` | ai_cv_processor_recommendation_history | The 'history' admin view for this model. |
| `/admin/ai_cv_processor/recommendation/add/` | `add_view` | ai_cv_processor_recommendation_add |  |
| `/admin/ai_cv_processor/roleexperience/` | `changelist_view` | ai_cv_processor_roleexperience_changelist | The 'change list' admin view for this model. |
| `/admin/ai_cv_processor/roleexperience/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ai_cv_processor/roleexperience/<path:object_id>/change/` | `change_view` | ai_cv_processor_roleexperience_change |  |
| `/admin/ai_cv_processor/roleexperience/<path:object_id>/delete/` | `delete_view` | ai_cv_processor_roleexperience_delete |  |
| `/admin/ai_cv_processor/roleexperience/<path:object_id>/history/` | `history_view` | ai_cv_processor_roleexperience_history | The 'history' admin view for this model. |
| `/admin/ai_cv_processor/roleexperience/add/` | `add_view` | ai_cv_processor_roleexperience_add |  |
| `/admin/ai_cv_processor/technologyexperience/` | `changelist_view` | ai_cv_processor_technologyexperience_changelist | The 'change list' admin view for this model. |
| `/admin/ai_cv_processor/technologyexperience/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ai_cv_processor/technologyexperience/<path:object_id>/change/` | `change_view` | ai_cv_processor_technologyexperience_change |  |
| `/admin/ai_cv_processor/technologyexperience/<path:object_id>/delete/` | `delete_view` | ai_cv_processor_technologyexperience_delete |  |
| `/admin/ai_cv_processor/technologyexperience/<path:object_id>/history/` | `history_view` | ai_cv_processor_technologyexperience_history | The 'history' admin view for this model. |
| `/admin/ai_cv_processor/technologyexperience/add/` | `add_view` | ai_cv_processor_technologyexperience_add |  |
| `/admin/ai_cv_prompt/promptstage/` | `changelist_view` | ai_cv_prompt_promptstage_changelist | The 'change list' admin view for this model. |
| `/admin/ai_cv_prompt/promptstage/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ai_cv_prompt/promptstage/<path:object_id>/change/` | `change_view` | ai_cv_prompt_promptstage_change |  |
| `/admin/ai_cv_prompt/promptstage/<path:object_id>/delete/` | `delete_view` | ai_cv_prompt_promptstage_delete |  |
| `/admin/ai_cv_prompt/promptstage/<path:object_id>/history/` | `history_view` | ai_cv_prompt_promptstage_history | The 'history' admin view for this model. |
| `/admin/ai_cv_prompt/promptstage/add/` | `add_view` | ai_cv_prompt_promptstage_add |  |
| `/admin/ai_cv_prompt/prompttemplate/` | `changelist_view` | ai_cv_prompt_prompttemplate_changelist | The 'change list' admin view for this model. |
| `/admin/ai_cv_prompt/prompttemplate/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ai_cv_prompt/prompttemplate/<path:object_id>/change/` | `change_view` | ai_cv_prompt_prompttemplate_change |  |
| `/admin/ai_cv_prompt/prompttemplate/<path:object_id>/delete/` | `delete_view` | ai_cv_prompt_prompttemplate_delete |  |
| `/admin/ai_cv_prompt/prompttemplate/<path:object_id>/history/` | `history_view` | ai_cv_prompt_prompttemplate_history | The 'history' admin view for this model. |
| `/admin/ai_cv_prompt/prompttemplate/add/` | `add_view` | ai_cv_prompt_prompttemplate_add |  |
| `/admin/ai_cv_prompt/prompttest/` | `changelist_view` | ai_cv_prompt_prompttest_changelist | The 'change list' admin view for this model. |
| `/admin/ai_cv_prompt/prompttest/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ai_cv_prompt/prompttest/<path:object_id>/delete/` | `delete_view` | ai_cv_prompt_prompttest_delete |  |
| `/admin/ai_cv_prompt/prompttest/<path:object_id>/history/` | `history_view` | ai_cv_prompt_prompttest_history | The 'history' admin view for this model. |
| `/admin/ai_cv_prompt/prompttest/add/` | `add_view` | ai_cv_prompt_prompttest_add |  |
| `/admin/ai_cv_prompt/skillcategory/` | `changelist_view` | ai_cv_prompt_skillcategory_changelist | The 'change list' admin view for this model. |
| `/admin/ai_cv_prompt/skillcategory/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ai_cv_prompt/skillcategory/<path:object_id>/change/` | `change_view` | ai_cv_prompt_skillcategory_change |  |
| `/admin/ai_cv_prompt/skillcategory/<path:object_id>/delete/` | `delete_view` | ai_cv_prompt_skillcategory_delete |  |
| `/admin/ai_cv_prompt/skillcategory/<path:object_id>/history/` | `history_view` | ai_cv_prompt_skillcategory_history | The 'history' admin view for this model. |
| `/admin/ai_cv_prompt/skillcategory/add/` | `add_view` | ai_cv_prompt_skillcategory_add |  |
| `/admin/ai_cv_training/blockmarker/` | `changelist_view` | ai_cv_training_blockmarker_changelist | The 'change list' admin view for this model. |
| `/admin/ai_cv_training/blockmarker/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ai_cv_training/blockmarker/<path:object_id>/change/` | `change_view` | ai_cv_training_blockmarker_change |  |
| `/admin/ai_cv_training/blockmarker/<path:object_id>/delete/` | `delete_view` | ai_cv_training_blockmarker_delete |  |
| `/admin/ai_cv_training/blockmarker/<path:object_id>/history/` | `history_view` | ai_cv_training_blockmarker_history | The 'history' admin view for this model. |
| `/admin/ai_cv_training/blockmarker/add/` | `add_view` | ai_cv_training_blockmarker_add |  |
| `/admin/ai_cv_training/extractionrule/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ai_cv_training/extractionrule/<path:object_id>/change/` | `change_view` | ai_cv_training_extractionrule_change |  |
| `/admin/ai_cv_training/extractionrule/<path:object_id>/delete/` | `delete_view` | ai_cv_training_extractionrule_delete |  |
| `/admin/ai_cv_training/extractionrule/<path:object_id>/history/` | `history_view` | ai_cv_training_extractionrule_history | The 'history' admin view for this model. |
| `/admin/ai_cv_training/extractionrule/add/` | `add_view` | ai_cv_training_extractionrule_add |  |
| `/admin/ai_cv_training/namazutrainingterm/` | `changelist_view` | ai_cv_training_namazutrainingterm_changelist | The 'change list' admin view for this model. |
| `/admin/ai_cv_training/namazutrainingterm/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ai_cv_training/namazutrainingterm/<path:object_id>/change/` | `change_view` | ai_cv_training_namazutrainingterm_change |  |
| `/admin/ai_cv_training/namazutrainingterm/<path:object_id>/delete/` | `delete_view` | ai_cv_training_namazutrainingterm_delete |  |
| `/admin/ai_cv_training/namazutrainingterm/<path:object_id>/history/` | `history_view` | ai_cv_training_namazutrainingterm_history | The 'history' admin view for this model. |
| `/admin/ai_cv_training/namazutrainingterm/add/` | `add_view` | ai_cv_training_namazutrainingterm_add |  |
| `/admin/ai_cv_training/processinglog/` | `changelist_view` | ai_cv_training_processinglog_changelist | The 'change list' admin view for this model. |
| `/admin/ai_cv_training/processinglog/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ai_cv_training/processinglog/<path:object_id>/change/` | `change_view` | ai_cv_training_processinglog_change |  |
| `/admin/ai_cv_training/processinglog/<path:object_id>/delete/` | `delete_view` | ai_cv_training_processinglog_delete |  |
| `/admin/ai_cv_training/processinglog/<path:object_id>/history/` | `history_view` | ai_cv_training_processinglog_history | The 'history' admin view for this model. |
| `/admin/ai_cv_training/processinglog/add/` | `add_view` | ai_cv_training_processinglog_add |  |
| `/admin/ai_cv_training/trainingbatch/` | `changelist_view` | ai_cv_training_trainingbatch_changelist | The 'change list' admin view for this model. |
| `/admin/ai_cv_training/trainingbatch/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ai_cv_training/trainingbatch/<path:object_id>/change/` | `change_view` | ai_cv_training_trainingbatch_change |  |
| `/admin/ai_cv_training/trainingbatch/<path:object_id>/delete/` | `delete_view` | ai_cv_training_trainingbatch_delete |  |
| `/admin/ai_cv_training/trainingbatch/<path:object_id>/history/` | `history_view` | ai_cv_training_trainingbatch_history | The 'history' admin view for this model. |
| `/admin/ai_cv_training/trainingbatch/add/` | `add_view` | ai_cv_training_trainingbatch_add |  |
| `/admin/ai_cv_training/trainingfeedback/` | `changelist_view` | ai_cv_training_trainingfeedback_changelist | The 'change list' admin view for this model. |
| `/admin/ai_cv_training/trainingfeedback/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ai_cv_training/trainingfeedback/<path:object_id>/change/` | `change_view` | ai_cv_training_trainingfeedback_change |  |
| `/admin/ai_cv_training/trainingfeedback/<path:object_id>/delete/` | `delete_view` | ai_cv_training_trainingfeedback_delete |  |
| `/admin/ai_cv_training/trainingfeedback/<path:object_id>/history/` | `history_view` | ai_cv_training_trainingfeedback_history | The 'history' admin view for this model. |
| `/admin/ai_cv_training/trainingfeedback/add/` | `add_view` | ai_cv_training_trainingfeedback_add |  |
| `/admin/ai_cv_training/trainingrelation/` | `changelist_view` | ai_cv_training_trainingrelation_changelist | The 'change list' admin view for this model. |
| `/admin/ai_cv_training/trainingrelation/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ai_cv_training/trainingrelation/<path:object_id>/change/` | `change_view` | ai_cv_training_trainingrelation_change |  |
| `/admin/ai_cv_training/trainingrelation/<path:object_id>/delete/` | `delete_view` | ai_cv_training_trainingrelation_delete |  |
| `/admin/ai_cv_training/trainingrelation/<path:object_id>/history/` | `history_view` | ai_cv_training_trainingrelation_history | The 'history' admin view for this model. |
| `/admin/ai_cv_training/trainingrelation/add/` | `add_view` | ai_cv_training_trainingrelation_add |  |
| `/admin/ai_cv_training/trainingsource/` | `changelist_view` | ai_cv_training_trainingsource_changelist | The 'change list' admin view for this model. |
| `/admin/ai_cv_training/trainingsource/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ai_cv_training/trainingsource/<path:object_id>/change/` | `change_view` | ai_cv_training_trainingsource_change |  |
| `/admin/ai_cv_training/trainingsource/<path:object_id>/delete/` | `delete_view` | ai_cv_training_trainingsource_delete |  |
| `/admin/ai_cv_training/trainingsource/<path:object_id>/history/` | `history_view` | ai_cv_training_trainingsource_history | The 'history' admin view for this model. |
| `/admin/ai_cv_training/trainingsource/add/` | `add_view` | ai_cv_training_trainingsource_add |  |
| `/admin/ai_cv_training/trainingstatistics/` | `changelist_view` | ai_cv_training_trainingstatistics_changelist | The 'change list' admin view for this model. |
| `/admin/ai_cv_training/trainingstatistics/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ai_cv_training/trainingstatistics/<path:object_id>/change/` | `change_view` | ai_cv_training_trainingstatistics_change |  |
| `/admin/ai_cv_training/trainingstatistics/<path:object_id>/delete/` | `delete_view` | ai_cv_training_trainingstatistics_delete |  |
| `/admin/ai_cv_training/trainingstatistics/<path:object_id>/history/` | `history_view` | ai_cv_training_trainingstatistics_history | The 'history' admin view for this model. |
| `/admin/ai_cv_training/trainingstatistics/add/` | `add_view` | ai_cv_training_trainingstatistics_add |  |
| `/admin/ai_cv_training/trainingterm/` | `changelist_view` | ai_cv_training_trainingterm_changelist | The 'change list' admin view for this model. |
| `/admin/ai_cv_training/trainingterm/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ai_cv_training/trainingterm/<path:object_id>/change/` | `change_view` | ai_cv_training_trainingterm_change |  |
| `/admin/ai_cv_training/trainingterm/<path:object_id>/delete/` | `delete_view` | ai_cv_training_trainingterm_delete |  |
| `/admin/ai_cv_training/trainingterm/<path:object_id>/history/` | `history_view` | ai_cv_training_trainingterm_history | The 'history' admin view for this model. |
| `/admin/ai_cv_training/trainingterm/add/` | `add_view` | ai_cv_training_trainingterm_add |  |
| `/admin/api/apikey/` | `changelist_view` | api_apikey_changelist | The 'change list' admin view for this model. |
| `/admin/api/apikey/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/api/apikey/<path:object_id>/change/` | `change_view` | api_apikey_change |  |
| `/admin/api/apikey/<path:object_id>/delete/` | `delete_view` | api_apikey_delete |  |
| `/admin/api/apikey/<path:object_id>/history/` | `history_view` | api_apikey_history | The 'history' admin view for this model. |
| `/admin/api/apikey/add/` | `add_view` | api_apikey_add |  |
| `/admin/auth/group/` | `changelist_view` | auth_group_changelist | The 'change list' admin view for this model. |
| `/admin/auth/group/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/auth/group/<path:object_id>/change/` | `change_view` | auth_group_change |  |
| `/admin/auth/group/<path:object_id>/delete/` | `delete_view` | auth_group_delete |  |
| `/admin/auth/group/<path:object_id>/history/` | `history_view` | auth_group_history | The 'history' admin view for this model. |
| `/admin/auth/group/add/` | `add_view` | auth_group_add |  |
| `/admin/auth/user/` | `changelist_view` | auth_user_changelist | The 'change list' admin view for this model. |
| `/admin/auth/user/<id>/password/` | `user_change_password` | auth_user_password_change |  |
| `/admin/auth/user/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/auth/user/<path:object_id>/change/` | `change_view` | auth_user_change |  |
| `/admin/auth/user/<path:object_id>/delete/` | `delete_view` | auth_user_delete |  |
| `/admin/auth/user/<path:object_id>/history/` | `history_view` | auth_user_history | The 'history' admin view for this model. |
| `/admin/auth/user/add/` | `add_view` | auth_user_add |  |
| `/admin/auth_ldap/ldapgroupsnapshot/` | `changelist_view` | auth_ldap_ldapgroupsnapshot_changelist | The 'change list' admin view for this model. |
| `/admin/auth_ldap/ldapgroupsnapshot/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/auth_ldap/ldapgroupsnapshot/<path:object_id>/change/` | `change_view` | auth_ldap_ldapgroupsnapshot_change |  |
| `/admin/auth_ldap/ldapgroupsnapshot/<path:object_id>/delete/` | `delete_view` | auth_ldap_ldapgroupsnapshot_delete |  |
| `/admin/auth_ldap/ldapgroupsnapshot/<path:object_id>/history/` | `history_view` | auth_ldap_ldapgroupsnapshot_history | The 'history' admin view for this model. |
| `/admin/auth_ldap/ldapgroupsnapshot/add/` | `add_view` | auth_ldap_ldapgroupsnapshot_add |  |
| `/admin/auth_ldap/ldapsynclog/` | `changelist_view` | auth_ldap_ldapsynclog_changelist | The 'change list' admin view for this model. |
| `/admin/auth_ldap/ldapsynclog/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/auth_ldap/ldapsynclog/<path:object_id>/change/` | `change_view` | auth_ldap_ldapsynclog_change |  |
| `/admin/auth_ldap/ldapsynclog/<path:object_id>/delete/` | `delete_view` | auth_ldap_ldapsynclog_delete |  |
| `/admin/auth_ldap/ldapsynclog/<path:object_id>/history/` | `history_view` | auth_ldap_ldapsynclog_history | The 'history' admin view for this model. |
| `/admin/auth_ldap/ldapsynclog/add/` | `add_view` | auth_ldap_ldapsynclog_add |  |
| `/admin/auth_ldap/ldapusersnapshot/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/auth_ldap/ldapusersnapshot/<path:object_id>/change/` | `change_view` | auth_ldap_ldapusersnapshot_change |  |
| `/admin/auth_ldap/ldapusersnapshot/<path:object_id>/delete/` | `delete_view` | auth_ldap_ldapusersnapshot_delete |  |
| `/admin/auth_ldap/ldapusersnapshot/<path:object_id>/history/` | `history_view` | auth_ldap_ldapusersnapshot_history | The 'history' admin view for this model. |
| `/admin/auth_ldap/ldapusersnapshot/add/` | `add_view` | auth_ldap_ldapusersnapshot_add |  |
| `/admin/authtoken/tokenproxy/` | `changelist_view` | authtoken_tokenproxy_changelist | The 'change list' admin view for this model. |
| `/admin/authtoken/tokenproxy/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/authtoken/tokenproxy/<path:object_id>/change/` | `change_view` | authtoken_tokenproxy_change |  |
| `/admin/authtoken/tokenproxy/<path:object_id>/delete/` | `delete_view` | authtoken_tokenproxy_delete |  |
| `/admin/authtoken/tokenproxy/<path:object_id>/history/` | `history_view` | authtoken_tokenproxy_history | The 'history' admin view for this model. |
| `/admin/authtoken/tokenproxy/add/` | `add_view` | authtoken_tokenproxy_add |  |
| `/admin/autocomplete/` | `autocomplete_view` | autocomplete |  |
| `/admin/automail_engine/emaillog/` | `changelist_view` | automail_engine_emaillog_changelist | The 'change list' admin view for this model. |
| `/admin/automail_engine/emaillog/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/automail_engine/emaillog/<path:object_id>/change/` | `change_view` | automail_engine_emaillog_change |  |
| `/admin/automail_engine/emaillog/<path:object_id>/delete/` | `delete_view` | automail_engine_emaillog_delete |  |
| `/admin/automail_engine/emaillog/<path:object_id>/history/` | `history_view` | automail_engine_emaillog_history | The 'history' admin view for this model. |
| `/admin/automail_engine/emaillog/add/` | `add_view` | automail_engine_emaillog_add |  |
| `/admin/automail_engine/emailtemplate/` | `changelist_view` | automail_engine_emailtemplate_changelist | The 'change list' admin view for this model. |
| `/admin/automail_engine/emailtemplate/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/automail_engine/emailtemplate/<path:object_id>/change/` | `change_view` | automail_engine_emailtemplate_change |  |
| `/admin/automail_engine/emailtemplate/<path:object_id>/delete/` | `delete_view` | automail_engine_emailtemplate_delete |  |
| `/admin/automail_engine/emailtemplate/<path:object_id>/history/` | `history_view` | automail_engine_emailtemplate_history | The 'history' admin view for this model. |
| `/admin/automail_engine/emailtemplate/add/` | `add_view` | automail_engine_emailtemplate_add |  |
| `/admin/automail_engine/templateattachment/` | `changelist_view` | automail_engine_templateattachment_changelist | The 'change list' admin view for this model. |
| `/admin/automail_engine/templateattachment/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/automail_engine/templateattachment/<path:object_id>/change/` | `change_view` | automail_engine_templateattachment_change |  |
| `/admin/automail_engine/templateattachment/<path:object_id>/delete/` | `delete_view` | automail_engine_templateattachment_delete |  |
| `/admin/automail_engine/templateattachment/<path:object_id>/history/` | `history_view` | automail_engine_templateattachment_history | The 'history' admin view for this model. |
| `/admin/automail_engine/templateattachment/add/` | `add_view` | automail_engine_templateattachment_add |  |
| `/admin/cms/page/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cms/page/<path:object_id>/change/` | `change_view` | cms_page_change |  |
| `/admin/cms/page/<path:object_id>/delete/` | `delete_view` | cms_page_delete |  |
| `/admin/cms/page/<path:object_id>/history/` | `history_view` | cms_page_history | The 'history' admin view for this model. |
| `/admin/cms/page/add/` | `add_view` | cms_page_add |  |
| `/admin/cms/pagecontent/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cms/pagecontent/<path:object_id>/history/` | `history_view` | cms_pagecontent_history | The 'history' admin view for this model. |
| `/admin/crm_bridge/crmfield/` | `changelist_view` | crm_bridge_crmfield_changelist | The 'change list' admin view for this model. |
| `/admin/crm_bridge/crmfield/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/crm_bridge/crmfield/<path:object_id>/change/` | `change_view` | crm_bridge_crmfield_change |  |
| `/admin/crm_bridge/crmfield/<path:object_id>/delete/` | `delete_view` | crm_bridge_crmfield_delete |  |
| `/admin/crm_bridge/crmfield/<path:object_id>/history/` | `history_view` | crm_bridge_crmfield_history | The 'history' admin view for this model. |
| `/admin/crm_bridge/crmfield/add/` | `add_view` | crm_bridge_crmfield_add |  |
| `/admin/crm_bridge/crmmodule/` | `changelist_view` | crm_bridge_crmmodule_changelist | The 'change list' admin view for this model. |
| `/admin/crm_bridge/crmmodule/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/crm_bridge/crmmodule/<path:object_id>/change/` | `change_view` | crm_bridge_crmmodule_change |  |
| `/admin/crm_bridge/crmmodule/<path:object_id>/delete/` | `delete_view` | crm_bridge_crmmodule_delete |  |
| `/admin/crm_bridge/crmmodule/<path:object_id>/history/` | `history_view` | crm_bridge_crmmodule_history | The 'history' admin view for this model. |
| `/admin/crm_bridge/crmmodule/add/` | `add_view` | crm_bridge_crmmodule_add |  |
| `/admin/crm_bridge/crmsyncstate/` | `changelist_view` | crm_bridge_crmsyncstate_changelist | The 'change list' admin view for this model. |
| `/admin/crm_bridge/crmsyncstate/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/crm_bridge/crmsyncstate/<path:object_id>/change/` | `change_view` | crm_bridge_crmsyncstate_change |  |
| `/admin/crm_bridge/crmsyncstate/<path:object_id>/delete/` | `delete_view` | crm_bridge_crmsyncstate_delete |  |
| `/admin/crm_bridge/crmsyncstate/<path:object_id>/history/` | `history_view` | crm_bridge_crmsyncstate_history | The 'history' admin view for this model. |
| `/admin/crm_bridge/crmsyncstate/add/` | `add_view` | crm_bridge_crmsyncstate_add |  |
| `/admin/cv_extractor/certification/` | `changelist_view` | cv_extractor_certification_changelist | The 'change list' admin view for this model. |
| `/admin/cv_extractor/certification/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_extractor/certification/<path:object_id>/change/` | `change_view` | cv_extractor_certification_change |  |
| `/admin/cv_extractor/certification/<path:object_id>/delete/` | `delete_view` | cv_extractor_certification_delete |  |
| `/admin/cv_extractor/certification/<path:object_id>/history/` | `history_view` | cv_extractor_certification_history | The 'history' admin view for this model. |
| `/admin/cv_extractor/certification/add/` | `add_view` | cv_extractor_certification_add |  |
| `/admin/cv_extractor/consultant/` | `changelist_view` | cv_extractor_consultant_changelist | The 'change list' admin view for this model. |
| `/admin/cv_extractor/consultant/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_extractor/consultant/<path:object_id>/change/` | `change_view` | cv_extractor_consultant_change |  |
| `/admin/cv_extractor/consultant/<path:object_id>/delete/` | `delete_view` | cv_extractor_consultant_delete |  |
| `/admin/cv_extractor/consultant/<path:object_id>/history/` | `history_view` | cv_extractor_consultant_history | The 'history' admin view for this model. |
| `/admin/cv_extractor/consultant/add/` | `add_view` | cv_extractor_consultant_add |  |
| `/admin/cv_extractor/consultantdirectory/` | `changelist_view` | cv_extractor_consultantdirectory_changelist | The 'change list' admin view for this model. |
| `/admin/cv_extractor/consultantdirectory/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_extractor/consultantdirectory/<path:object_id>/change/` | `change_view` | cv_extractor_consultantdirectory_change |  |
| `/admin/cv_extractor/consultantdirectory/<path:object_id>/delete/` | `delete_view` | cv_extractor_consultantdirectory_delete |  |
| `/admin/cv_extractor/consultantdirectory/<path:object_id>/history/` | `history_view` | cv_extractor_consultantdirectory_history | The 'history' admin view for this model. |
| `/admin/cv_extractor/consultantdirectory/add/` | `add_view` | cv_extractor_consultantdirectory_add |  |
| `/admin/cv_extractor/consultantversion/` | `changelist_view` | cv_extractor_consultantversion_changelist | The 'change list' admin view for this model. |
| `/admin/cv_extractor/consultantversion/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_extractor/consultantversion/<path:object_id>/change/` | `change_view` | cv_extractor_consultantversion_change |  |
| `/admin/cv_extractor/consultantversion/<path:object_id>/delete/` | `delete_view` | cv_extractor_consultantversion_delete |  |
| `/admin/cv_extractor/consultantversion/<path:object_id>/history/` | `history_view` | cv_extractor_consultantversion_history | The 'history' admin view for this model. |
| `/admin/cv_extractor/consultantversion/add/` | `add_view` | cv_extractor_consultantversion_add |  |
| `/admin/cv_extractor/education/` | `changelist_view` | cv_extractor_education_changelist | The 'change list' admin view for this model. |
| `/admin/cv_extractor/education/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_extractor/education/<path:object_id>/change/` | `change_view` | cv_extractor_education_change |  |
| `/admin/cv_extractor/education/<path:object_id>/delete/` | `delete_view` | cv_extractor_education_delete |  |
| `/admin/cv_extractor/education/<path:object_id>/history/` | `history_view` | cv_extractor_education_history | The 'history' admin view for this model. |
| `/admin/cv_extractor/education/add/` | `add_view` | cv_extractor_education_add |  |
| `/admin/cv_extractor/experience/` | `changelist_view` | cv_extractor_experience_changelist | The 'change list' admin view for this model. |
| `/admin/cv_extractor/experience/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_extractor/experience/<path:object_id>/change/` | `change_view` | cv_extractor_experience_change |  |
| `/admin/cv_extractor/experience/<path:object_id>/delete/` | `delete_view` | cv_extractor_experience_delete |  |
| `/admin/cv_extractor/experience/<path:object_id>/history/` | `history_view` | cv_extractor_experience_history | The 'history' admin view for this model. |
| `/admin/cv_extractor/experience/add/` | `add_view` | cv_extractor_experience_add |  |
| `/admin/cv_extractor/focusarea/` | `changelist_view` | cv_extractor_focusarea_changelist | The 'change list' admin view for this model. |
| `/admin/cv_extractor/focusarea/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_extractor/focusarea/<path:object_id>/change/` | `change_view` | cv_extractor_focusarea_change |  |
| `/admin/cv_extractor/focusarea/<path:object_id>/delete/` | `delete_view` | cv_extractor_focusarea_delete |  |
| `/admin/cv_extractor/focusarea/<path:object_id>/history/` | `history_view` | cv_extractor_focusarea_history | The 'history' admin view for this model. |
| `/admin/cv_extractor/focusarea/add/` | `add_view` | cv_extractor_focusarea_add |  |
| `/admin/cv_extractor/focusexperience/` | `changelist_view` | cv_extractor_focusexperience_changelist | The 'change list' admin view for this model. |
| `/admin/cv_extractor/focusexperience/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_extractor/focusexperience/<path:object_id>/change/` | `change_view` | cv_extractor_focusexperience_change |  |
| `/admin/cv_extractor/focusexperience/<path:object_id>/delete/` | `delete_view` | cv_extractor_focusexperience_delete |  |
| `/admin/cv_extractor/focusexperience/<path:object_id>/history/` | `history_view` | cv_extractor_focusexperience_history | The 'history' admin view for this model. |
| `/admin/cv_extractor/focusexperience/add/` | `add_view` | cv_extractor_focusexperience_add |  |
| `/admin/cv_extractor/industry/` | `changelist_view` | cv_extractor_industry_changelist | The 'change list' admin view for this model. |
| `/admin/cv_extractor/industry/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_extractor/industry/<path:object_id>/change/` | `change_view` | cv_extractor_industry_change |  |
| `/admin/cv_extractor/industry/<path:object_id>/delete/` | `delete_view` | cv_extractor_industry_delete |  |
| `/admin/cv_extractor/industry/<path:object_id>/history/` | `history_view` | cv_extractor_industry_history | The 'history' admin view for this model. |
| `/admin/cv_extractor/industry/add/` | `add_view` | cv_extractor_industry_add |  |
| `/admin/cv_extractor/issuer/` | `changelist_view` | cv_extractor_issuer_changelist | The 'change list' admin view for this model. |
| `/admin/cv_extractor/issuer/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_extractor/issuer/<path:object_id>/change/` | `change_view` | cv_extractor_issuer_change |  |
| `/admin/cv_extractor/issuer/<path:object_id>/delete/` | `delete_view` | cv_extractor_issuer_delete |  |
| `/admin/cv_extractor/issuer/<path:object_id>/history/` | `history_view` | cv_extractor_issuer_history | The 'history' admin view for this model. |
| `/admin/cv_extractor/issuer/add/` | `add_view` | cv_extractor_issuer_add |  |
| `/admin/cv_extractor/language/` | `changelist_view` | cv_extractor_language_changelist | The 'change list' admin view for this model. |
| `/admin/cv_extractor/language/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_extractor/language/<path:object_id>/change/` | `change_view` | cv_extractor_language_change |  |
| `/admin/cv_extractor/language/<path:object_id>/delete/` | `delete_view` | cv_extractor_language_delete |  |
| `/admin/cv_extractor/language/<path:object_id>/history/` | `history_view` | cv_extractor_language_history | The 'history' admin view for this model. |
| `/admin/cv_extractor/language/add/` | `add_view` | cv_extractor_language_add |  |
| `/admin/cv_extractor/prompttemplate/` | `changelist_view` | cv_extractor_prompttemplate_changelist | The 'change list' admin view for this model. |
| `/admin/cv_extractor/prompttemplate/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_extractor/prompttemplate/<path:object_id>/change/` | `change_view` | cv_extractor_prompttemplate_change |  |
| `/admin/cv_extractor/prompttemplate/<path:object_id>/delete/` | `delete_view` | cv_extractor_prompttemplate_delete |  |
| `/admin/cv_extractor/prompttemplate/<path:object_id>/history/` | `history_view` | cv_extractor_prompttemplate_history | The 'history' admin view for this model. |
| `/admin/cv_extractor/prompttemplate/add/` | `add_view` | cv_extractor_prompttemplate_add |  |
| `/admin/cv_extractor/skill/` | `changelist_view` | cv_extractor_skill_changelist | The 'change list' admin view for this model. |
| `/admin/cv_extractor/skill/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_extractor/skill/<path:object_id>/change/` | `change_view` | cv_extractor_skill_change |  |
| `/admin/cv_extractor/skill/<path:object_id>/delete/` | `delete_view` | cv_extractor_skill_delete |  |
| `/admin/cv_extractor/skill/<path:object_id>/history/` | `history_view` | cv_extractor_skill_history | The 'history' admin view for this model. |
| `/admin/cv_extractor/skill/add/` | `add_view` | cv_extractor_skill_add |  |
| `/admin/cv_extractor/skillcategory/` | `changelist_view` | cv_extractor_skillcategory_changelist | The 'change list' admin view for this model. |
| `/admin/cv_extractor/skillcategory/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_extractor/skillcategory/<path:object_id>/change/` | `change_view` | cv_extractor_skillcategory_change |  |
| `/admin/cv_extractor/skillcategory/<path:object_id>/delete/` | `delete_view` | cv_extractor_skillcategory_delete |  |
| `/admin/cv_extractor/skillcategory/<path:object_id>/history/` | `history_view` | cv_extractor_skillcategory_history | The 'history' admin view for this model. |
| `/admin/cv_extractor/skillcategory/add/` | `add_view` | cv_extractor_skillcategory_add |  |
| `/admin/cv_extractor/uploadedpdf/` | `changelist_view` | cv_extractor_uploadedpdf_changelist | The 'change list' admin view for this model. |
| `/admin/cv_extractor/uploadedpdf/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_extractor/uploadedpdf/<path:object_id>/change/` | `change_view` | cv_extractor_uploadedpdf_change |  |
| `/admin/cv_extractor/uploadedpdf/<path:object_id>/delete/` | `delete_view` | cv_extractor_uploadedpdf_delete |  |
| `/admin/cv_extractor/uploadedpdf/<path:object_id>/history/` | `history_view` | cv_extractor_uploadedpdf_history | The 'history' admin view for this model. |
| `/admin/cv_extractor/uploadedpdf/add/` | `add_view` | cv_extractor_uploadedpdf_add |  |
| `/admin/cv_pipeline/aidcounter/` | `changelist_view` | cv_pipeline_aidcounter_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/aidcounter/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/aidcounter/<path:object_id>/change/` | `change_view` | cv_pipeline_aidcounter_change |  |
| `/admin/cv_pipeline/aidcounter/<path:object_id>/delete/` | `delete_view` | cv_pipeline_aidcounter_delete |  |
| `/admin/cv_pipeline/aidcounter/<path:object_id>/history/` | `history_view` | cv_pipeline_aidcounter_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/aidcounter/add/` | `add_view` | cv_pipeline_aidcounter_add |  |
| `/admin/cv_pipeline/blockmarker/` | `changelist_view` | cv_pipeline_blockmarker_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/blockmarker/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/blockmarker/<path:object_id>/change/` | `change_view` | cv_pipeline_blockmarker_change |  |
| `/admin/cv_pipeline/blockmarker/<path:object_id>/delete/` | `delete_view` | cv_pipeline_blockmarker_delete |  |
| `/admin/cv_pipeline/blockmarker/<path:object_id>/history/` | `history_view` | cv_pipeline_blockmarker_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/blockmarker/add/` | `add_view` | cv_pipeline_blockmarker_add |  |
| `/admin/cv_pipeline/certification/` | `changelist_view` | cv_pipeline_certification_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/certification/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/certification/<path:object_id>/change/` | `change_view` | cv_pipeline_certification_change |  |
| `/admin/cv_pipeline/certification/<path:object_id>/delete/` | `delete_view` | cv_pipeline_certification_delete |  |
| `/admin/cv_pipeline/certification/<path:object_id>/history/` | `history_view` | cv_pipeline_certification_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/certification/add/` | `add_view` | cv_pipeline_certification_add |  |
| `/admin/cv_pipeline/consultant/` | `changelist_view` | cv_pipeline_consultant_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/consultant/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/consultant/<path:object_id>/change/` | `change_view` | cv_pipeline_consultant_change |  |
| `/admin/cv_pipeline/consultant/<path:object_id>/delete/` | `delete_view` | cv_pipeline_consultant_delete |  |
| `/admin/cv_pipeline/consultant/<path:object_id>/history/` | `history_view` | cv_pipeline_consultant_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/consultant/add/` | `add_view` | cv_pipeline_consultant_add |  |
| `/admin/cv_pipeline/consultantcertification/` | `changelist_view` | cv_pipeline_consultantcertification_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/consultantcertification/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/consultantcertification/<path:object_id>/change/` | `change_view` | cv_pipeline_consultantcertification_change |  |
| `/admin/cv_pipeline/consultantcertification/<path:object_id>/delete/` | `delete_view` | cv_pipeline_consultantcertification_delete |  |
| `/admin/cv_pipeline/consultantcertification/<path:object_id>/history/` | `history_view` | cv_pipeline_consultantcertification_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/consultantcertification/add/` | `add_view` | cv_pipeline_consultantcertification_add |  |
| `/admin/cv_pipeline/consultantcrm/` | `changelist_view` | cv_pipeline_consultantcrm_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/consultantcrm/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/consultantcrm/<path:object_id>/change/` | `change_view` | cv_pipeline_consultantcrm_change |  |
| `/admin/cv_pipeline/consultantcrm/<path:object_id>/delete/` | `delete_view` | cv_pipeline_consultantcrm_delete |  |
| `/admin/cv_pipeline/consultantcrm/<path:object_id>/history/` | `history_view` | cv_pipeline_consultantcrm_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/consultantcrm/add/` | `add_view` | cv_pipeline_consultantcrm_add |  |
| `/admin/cv_pipeline/consultantfocusarea/` | `changelist_view` | cv_pipeline_consultantfocusarea_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/consultantfocusarea/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/consultantfocusarea/<path:object_id>/change/` | `change_view` | cv_pipeline_consultantfocusarea_change |  |
| `/admin/cv_pipeline/consultantfocusarea/<path:object_id>/delete/` | `delete_view` | cv_pipeline_consultantfocusarea_delete |  |
| `/admin/cv_pipeline/consultantfocusarea/<path:object_id>/history/` | `history_view` | cv_pipeline_consultantfocusarea_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/consultantfocusarea/add/` | `add_view` | cv_pipeline_consultantfocusarea_add |  |
| `/admin/cv_pipeline/consultantidentity/` | `changelist_view` | cv_pipeline_consultantidentity_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/consultantidentity/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/consultantidentity/<path:object_id>/change/` | `change_view` | cv_pipeline_consultantidentity_change |  |
| `/admin/cv_pipeline/consultantidentity/<path:object_id>/delete/` | `delete_view` | cv_pipeline_consultantidentity_delete |  |
| `/admin/cv_pipeline/consultantidentity/<path:object_id>/history/` | `history_view` | cv_pipeline_consultantidentity_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/consultantidentity/add/` | `add_view` | cv_pipeline_consultantidentity_add |  |
| `/admin/cv_pipeline/consultantindustry/` | `changelist_view` | cv_pipeline_consultantindustry_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/consultantindustry/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/consultantindustry/<path:object_id>/change/` | `change_view` | cv_pipeline_consultantindustry_change |  |
| `/admin/cv_pipeline/consultantindustry/<path:object_id>/delete/` | `delete_view` | cv_pipeline_consultantindustry_delete |  |
| `/admin/cv_pipeline/consultantindustry/<path:object_id>/history/` | `history_view` | cv_pipeline_consultantindustry_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/consultantindustry/add/` | `add_view` | cv_pipeline_consultantindustry_add |  |
| `/admin/cv_pipeline/consultantlanguage/` | `changelist_view` | cv_pipeline_consultantlanguage_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/consultantlanguage/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/consultantlanguage/<path:object_id>/change/` | `change_view` | cv_pipeline_consultantlanguage_change |  |
| `/admin/cv_pipeline/consultantlanguage/<path:object_id>/delete/` | `delete_view` | cv_pipeline_consultantlanguage_delete |  |
| `/admin/cv_pipeline/consultantlanguage/<path:object_id>/history/` | `history_view` | cv_pipeline_consultantlanguage_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/consultantlanguage/add/` | `add_view` | cv_pipeline_consultantlanguage_add |  |
| `/admin/cv_pipeline/consultantmatching/` | `changelist_view` | cv_pipeline_consultantmatching_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/consultantmatching/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/consultantmatching/<path:object_id>/change/` | `change_view` | cv_pipeline_consultantmatching_change |  |
| `/admin/cv_pipeline/consultantmatching/<path:object_id>/delete/` | `delete_view` | cv_pipeline_consultantmatching_delete |  |
| `/admin/cv_pipeline/consultantmatching/<path:object_id>/history/` | `history_view` | cv_pipeline_consultantmatching_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/consultantmatching/add/` | `add_view` | cv_pipeline_consultantmatching_add |  |
| `/admin/cv_pipeline/consultantothercontent/` | `changelist_view` | cv_pipeline_consultantothercontent_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/consultantothercontent/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/consultantothercontent/<path:object_id>/change/` | `change_view` | cv_pipeline_consultantothercontent_change |  |
| `/admin/cv_pipeline/consultantothercontent/<path:object_id>/delete/` | `delete_view` | cv_pipeline_consultantothercontent_delete |  |
| `/admin/cv_pipeline/consultantothercontent/<path:object_id>/history/` | `history_view` | cv_pipeline_consultantothercontent_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/consultantothercontent/add/` | `add_view` | cv_pipeline_consultantothercontent_add |  |
| `/admin/cv_pipeline/consultantskill/` | `changelist_view` | cv_pipeline_consultantskill_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/consultantskill/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/consultantskill/<path:object_id>/change/` | `change_view` | cv_pipeline_consultantskill_change |  |
| `/admin/cv_pipeline/consultantskill/<path:object_id>/delete/` | `delete_view` | cv_pipeline_consultantskill_delete |  |
| `/admin/cv_pipeline/consultantskill/<path:object_id>/history/` | `history_view` | cv_pipeline_consultantskill_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/consultantskill/add/` | `add_view` | cv_pipeline_consultantskill_add |  |
| `/admin/cv_pipeline/consultantskillgraph/` | `changelist_view` | cv_pipeline_consultantskillgraph_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/consultantskillgraph/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/consultantskillgraph/<path:object_id>/change/` | `change_view` | cv_pipeline_consultantskillgraph_change |  |
| `/admin/cv_pipeline/consultantskillgraph/<path:object_id>/delete/` | `delete_view` | cv_pipeline_consultantskillgraph_delete |  |
| `/admin/cv_pipeline/consultantskillgraph/<path:object_id>/history/` | `history_view` | cv_pipeline_consultantskillgraph_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/consultantskillgraph/add/` | `add_view` | cv_pipeline_consultantskillgraph_add |  |
| `/admin/cv_pipeline/consultantstatistics/` | `changelist_view` | cv_pipeline_consultantstatistics_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/consultantstatistics/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/consultantstatistics/<path:object_id>/change/` | `change_view` | cv_pipeline_consultantstatistics_change |  |
| `/admin/cv_pipeline/consultantstatistics/<path:object_id>/delete/` | `delete_view` | cv_pipeline_consultantstatistics_delete |  |
| `/admin/cv_pipeline/consultantstatistics/<path:object_id>/history/` | `history_view` | cv_pipeline_consultantstatistics_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/consultantstatistics/add/` | `add_view` | cv_pipeline_consultantstatistics_add |  |
| `/admin/cv_pipeline/consultantworkflow/` | `changelist_view` | cv_pipeline_consultantworkflow_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/consultantworkflow/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/consultantworkflow/<path:object_id>/change/` | `change_view` | cv_pipeline_consultantworkflow_change |  |
| `/admin/cv_pipeline/consultantworkflow/<path:object_id>/delete/` | `delete_view` | cv_pipeline_consultantworkflow_delete |  |
| `/admin/cv_pipeline/consultantworkflow/<path:object_id>/history/` | `history_view` | cv_pipeline_consultantworkflow_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/consultantworkflow/add/` | `add_view` | cv_pipeline_consultantworkflow_add |  |
| `/admin/cv_pipeline/education/` | `changelist_view` | cv_pipeline_education_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/education/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/education/<path:object_id>/change/` | `change_view` | cv_pipeline_education_change |  |
| `/admin/cv_pipeline/education/<path:object_id>/delete/` | `delete_view` | cv_pipeline_education_delete |  |
| `/admin/cv_pipeline/education/<path:object_id>/history/` | `history_view` | cv_pipeline_education_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/education/add/` | `add_view` | cv_pipeline_education_add |  |
| `/admin/cv_pipeline/experience/` | `changelist_view` | cv_pipeline_experience_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/experience/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/experience/<path:object_id>/change/` | `change_view` | cv_pipeline_experience_change |  |
| `/admin/cv_pipeline/experience/<path:object_id>/delete/` | `delete_view` | cv_pipeline_experience_delete |  |
| `/admin/cv_pipeline/experience/<path:object_id>/history/` | `history_view` | cv_pipeline_experience_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/experience/add/` | `add_view` | cv_pipeline_experience_add |  |
| `/admin/cv_pipeline/experienceactivity/` | `changelist_view` | cv_pipeline_experienceactivity_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/experienceactivity/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/experienceactivity/<path:object_id>/change/` | `change_view` | cv_pipeline_experienceactivity_change |  |
| `/admin/cv_pipeline/experienceactivity/<path:object_id>/delete/` | `delete_view` | cv_pipeline_experienceactivity_delete |  |
| `/admin/cv_pipeline/experienceactivity/<path:object_id>/history/` | `history_view` | cv_pipeline_experienceactivity_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/experienceactivity/add/` | `add_view` | cv_pipeline_experienceactivity_add |  |
| `/admin/cv_pipeline/experiencetechnology/` | `changelist_view` | cv_pipeline_experiencetechnology_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/experiencetechnology/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/experiencetechnology/<path:object_id>/change/` | `change_view` | cv_pipeline_experiencetechnology_change |  |
| `/admin/cv_pipeline/experiencetechnology/<path:object_id>/delete/` | `delete_view` | cv_pipeline_experiencetechnology_delete |  |
| `/admin/cv_pipeline/experiencetechnology/<path:object_id>/history/` | `history_view` | cv_pipeline_experiencetechnology_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/experiencetechnology/add/` | `add_view` | cv_pipeline_experiencetechnology_add |  |
| `/admin/cv_pipeline/extractionrule/` | `changelist_view` | cv_pipeline_extractionrule_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/extractionrule/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/extractionrule/<path:object_id>/change/` | `change_view` | cv_pipeline_extractionrule_change |  |
| `/admin/cv_pipeline/extractionrule/<path:object_id>/delete/` | `delete_view` | cv_pipeline_extractionrule_delete |  |
| `/admin/cv_pipeline/extractionrule/<path:object_id>/history/` | `history_view` | cv_pipeline_extractionrule_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/extractionrule/add/` | `add_view` | cv_pipeline_extractionrule_add |  |
| `/admin/cv_pipeline/focusarea/` | `changelist_view` | cv_pipeline_focusarea_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/focusarea/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/focusarea/<path:object_id>/change/` | `change_view` | cv_pipeline_focusarea_change |  |
| `/admin/cv_pipeline/focusarea/<path:object_id>/delete/` | `delete_view` | cv_pipeline_focusarea_delete |  |
| `/admin/cv_pipeline/focusarea/<path:object_id>/history/` | `history_view` | cv_pipeline_focusarea_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/focusarea/add/` | `add_view` | cv_pipeline_focusarea_add |  |
| `/admin/cv_pipeline/industry/` | `changelist_view` | cv_pipeline_industry_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/industry/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/industry/<path:object_id>/change/` | `change_view` | cv_pipeline_industry_change |  |
| `/admin/cv_pipeline/industry/<path:object_id>/delete/` | `delete_view` | cv_pipeline_industry_delete |  |
| `/admin/cv_pipeline/industry/<path:object_id>/history/` | `history_view` | cv_pipeline_industry_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/industry/add/` | `add_view` | cv_pipeline_industry_add |  |
| `/admin/cv_pipeline/issuer/` | `changelist_view` | cv_pipeline_issuer_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/issuer/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/issuer/<path:object_id>/change/` | `change_view` | cv_pipeline_issuer_change |  |
| `/admin/cv_pipeline/issuer/<path:object_id>/delete/` | `delete_view` | cv_pipeline_issuer_delete |  |
| `/admin/cv_pipeline/issuer/<path:object_id>/history/` | `history_view` | cv_pipeline_issuer_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/issuer/add/` | `add_view` | cv_pipeline_issuer_add |  |
| `/admin/cv_pipeline/language/` | `changelist_view` | cv_pipeline_language_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/language/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/language/<path:object_id>/change/` | `change_view` | cv_pipeline_language_change |  |
| `/admin/cv_pipeline/language/<path:object_id>/delete/` | `delete_view` | cv_pipeline_language_delete |  |
| `/admin/cv_pipeline/language/<path:object_id>/history/` | `history_view` | cv_pipeline_language_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/language/add/` | `add_view` | cv_pipeline_language_add |  |
| `/admin/cv_pipeline/layoutfeature/` | `changelist_view` | cv_pipeline_layoutfeature_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/layoutfeature/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/layoutfeature/<path:object_id>/change/` | `change_view` | cv_pipeline_layoutfeature_change |  |
| `/admin/cv_pipeline/layoutfeature/<path:object_id>/delete/` | `delete_view` | cv_pipeline_layoutfeature_delete |  |
| `/admin/cv_pipeline/layoutfeature/<path:object_id>/history/` | `history_view` | cv_pipeline_layoutfeature_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/layoutfeature/add/` | `add_view` | cv_pipeline_layoutfeature_add |  |
| `/admin/cv_pipeline/ocrlog/` | `changelist_view` | cv_pipeline_ocrlog_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/ocrlog/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/ocrlog/<path:object_id>/change/` | `change_view` | cv_pipeline_ocrlog_change |  |
| `/admin/cv_pipeline/ocrlog/<path:object_id>/delete/` | `delete_view` | cv_pipeline_ocrlog_delete |  |
| `/admin/cv_pipeline/ocrlog/<path:object_id>/history/` | `history_view` | cv_pipeline_ocrlog_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/ocrlog/add/` | `add_view` | cv_pipeline_ocrlog_add |  |
| `/admin/cv_pipeline/othercontent/` | `changelist_view` | cv_pipeline_othercontent_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/othercontent/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/othercontent/<path:object_id>/change/` | `change_view` | cv_pipeline_othercontent_change |  |
| `/admin/cv_pipeline/othercontent/<path:object_id>/delete/` | `delete_view` | cv_pipeline_othercontent_delete |  |
| `/admin/cv_pipeline/othercontent/<path:object_id>/history/` | `history_view` | cv_pipeline_othercontent_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/othercontent/add/` | `add_view` | cv_pipeline_othercontent_add |  |
| `/admin/cv_pipeline/processinglog/` | `changelist_view` | cv_pipeline_processinglog_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/processinglog/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/processinglog/<path:object_id>/change/` | `change_view` | cv_pipeline_processinglog_change |  |
| `/admin/cv_pipeline/processinglog/<path:object_id>/delete/` | `delete_view` | cv_pipeline_processinglog_delete |  |
| `/admin/cv_pipeline/processinglog/<path:object_id>/history/` | `history_view` | cv_pipeline_processinglog_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/processinglog/add/` | `add_view` | cv_pipeline_processinglog_add |  |
| `/admin/cv_pipeline/prompttemplate/` | `changelist_view` | cv_pipeline_prompttemplate_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/prompttemplate/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/prompttemplate/<path:object_id>/change/` | `change_view` | cv_pipeline_prompttemplate_change |  |
| `/admin/cv_pipeline/prompttemplate/<path:object_id>/delete/` | `delete_view` | cv_pipeline_prompttemplate_delete |  |
| `/admin/cv_pipeline/prompttemplate/<path:object_id>/history/` | `history_view` | cv_pipeline_prompttemplate_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/prompttemplate/add/` | `add_view` | cv_pipeline_prompttemplate_add |  |
| `/admin/cv_pipeline/skill/` | `changelist_view` | cv_pipeline_skill_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/skill/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/skill/<path:object_id>/change/` | `change_view` | cv_pipeline_skill_change |  |
| `/admin/cv_pipeline/skill/<path:object_id>/delete/` | `delete_view` | cv_pipeline_skill_delete |  |
| `/admin/cv_pipeline/skill/<path:object_id>/history/` | `history_view` | cv_pipeline_skill_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/skill/add/` | `add_view` | cv_pipeline_skill_add |  |
| `/admin/cv_pipeline/skillgraphcache/` | `changelist_view` | cv_pipeline_skillgraphcache_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/skillgraphcache/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/skillgraphcache/<path:object_id>/change/` | `change_view` | cv_pipeline_skillgraphcache_change |  |
| `/admin/cv_pipeline/skillgraphcache/<path:object_id>/delete/` | `delete_view` | cv_pipeline_skillgraphcache_delete |  |
| `/admin/cv_pipeline/skillgraphcache/<path:object_id>/history/` | `history_view` | cv_pipeline_skillgraphcache_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/skillgraphcache/add/` | `add_view` | cv_pipeline_skillgraphcache_add |  |
| `/admin/cv_pipeline/skillrelation/` | `changelist_view` | cv_pipeline_skillrelation_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/skillrelation/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/skillrelation/<path:object_id>/change/` | `change_view` | cv_pipeline_skillrelation_change |  |
| `/admin/cv_pipeline/skillrelation/<path:object_id>/delete/` | `delete_view` | cv_pipeline_skillrelation_delete |  |
| `/admin/cv_pipeline/skillrelation/<path:object_id>/history/` | `history_view` | cv_pipeline_skillrelation_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/skillrelation/add/` | `add_view` | cv_pipeline_skillrelation_add |  |
| `/admin/cv_pipeline/stopword/` | `changelist_view` | cv_pipeline_stopword_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/stopword/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/stopword/<path:object_id>/change/` | `change_view` | cv_pipeline_stopword_change |  |
| `/admin/cv_pipeline/stopword/<path:object_id>/delete/` | `delete_view` | cv_pipeline_stopword_delete |  |
| `/admin/cv_pipeline/stopword/<path:object_id>/history/` | `history_view` | cv_pipeline_stopword_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/stopword/add/` | `add_view` | cv_pipeline_stopword_add |  |
| `/admin/cv_pipeline/trainingterm/` | `changelist_view` | cv_pipeline_trainingterm_changelist | The 'change list' admin view for this model. |
| `/admin/cv_pipeline/trainingterm/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/cv_pipeline/trainingterm/<path:object_id>/change/` | `change_view` | cv_pipeline_trainingterm_change |  |
| `/admin/cv_pipeline/trainingterm/<path:object_id>/delete/` | `delete_view` | cv_pipeline_trainingterm_delete |  |
| `/admin/cv_pipeline/trainingterm/<path:object_id>/history/` | `history_view` | cv_pipeline_trainingterm_history | The 'history' admin view for this model. |
| `/admin/cv_pipeline/trainingterm/add/` | `add_view` | cv_pipeline_trainingterm_add |  |
| `/admin/dashboard/dashboardwidget/` | `changelist_view` | dashboard_dashboardwidget_changelist | The 'change list' admin view for this model. |
| `/admin/dashboard/dashboardwidget/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/dashboard/dashboardwidget/<path:object_id>/change/` | `change_view` | dashboard_dashboardwidget_change |  |
| `/admin/dashboard/dashboardwidget/<path:object_id>/delete/` | `delete_view` | dashboard_dashboardwidget_delete |  |
| `/admin/dashboard/dashboardwidget/<path:object_id>/history/` | `history_view` | dashboard_dashboardwidget_history | The 'history' admin view for this model. |
| `/admin/dashboard/dashboardwidget/add/` | `add_view` | dashboard_dashboardwidget_add |  |
| `/admin/djangocms_snippet/snippet/` | `changelist_view` | djangocms_snippet_snippet_changelist | The 'change list' admin view for this model. |
| `/admin/djangocms_snippet/snippet/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/djangocms_snippet/snippet/<path:object_id>/change/` | `change_view` | djangocms_snippet_snippet_change |  |
| `/admin/djangocms_snippet/snippet/<path:object_id>/delete/` | `delete_view` | djangocms_snippet_snippet_delete |  |
| `/admin/djangocms_snippet/snippet/<path:object_id>/history/` | `history_view` | djangocms_snippet_snippet_history | The 'history' admin view for this model. |
| `/admin/djangocms_snippet/snippet/add/` | `add_view` | djangocms_snippet_snippet_add |  |
| `/admin/djangocms_versioning/pagecontentversion/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/djangocms_versioning/pagecontentversion/<path:object_id>/change/` | `change_view` | djangocms_versioning_pagecontentversion_change |  |
| `/admin/djangocms_versioning/pagecontentversion/<path:object_id>/history/` | `history_view` | djangocms_versioning_pagecontentversion_history | The 'history' admin view for this model. |
| `/admin/djangocms_versioning/pagecontentversion/add/` | `add_view` | djangocms_versioning_pagecontentversion_add |  |
| `/admin/djangocms_versioning/snippetversion/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/djangocms_versioning/snippetversion/<path:object_id>/change/` | `change_view` | djangocms_versioning_snippetversion_change |  |
| `/admin/djangocms_versioning/snippetversion/<path:object_id>/history/` | `history_view` | djangocms_versioning_snippetversion_history | The 'history' admin view for this model. |
| `/admin/djangocms_versioning/snippetversion/add/` | `add_view` | djangocms_versioning_snippetversion_add |  |
| `/admin/documentation/apidocumentation/` | `changelist_view` | documentation_apidocumentation_changelist | The 'change list' admin view for this model. |
| `/admin/documentation/apidocumentation/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/documentation/apidocumentation/<path:object_id>/change/` | `change_view` | documentation_apidocumentation_change |  |
| `/admin/documentation/apidocumentation/<path:object_id>/delete/` | `delete_view` | documentation_apidocumentation_delete |  |
| `/admin/documentation/apidocumentation/<path:object_id>/history/` | `history_view` | documentation_apidocumentation_history | The 'history' admin view for this model. |
| `/admin/documentation/apidocumentation/add/` | `add_view` | documentation_apidocumentation_add |  |
| `/admin/documentation/documentationcategory/` | `changelist_view` | documentation_documentationcategory_changelist | The 'change list' admin view for this model. |
| `/admin/documentation/documentationcategory/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/documentation/documentationcategory/<path:object_id>/change/` | `change_view` | documentation_documentationcategory_change |  |
| `/admin/documentation/documentationcategory/<path:object_id>/delete/` | `delete_view` | documentation_documentationcategory_delete |  |
| `/admin/documentation/documentationcategory/<path:object_id>/history/` | `history_view` | documentation_documentationcategory_history | The 'history' admin view for this model. |
| `/admin/documentation/documentationcategory/add/` | `add_view` | documentation_documentationcategory_add |  |
| `/admin/documentation/documentationpage/` | `changelist_view` | documentation_documentationpage_changelist | The 'change list' admin view for this model. |
| `/admin/documentation/documentationpage/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/documentation/documentationpage/<path:object_id>/change/` | `change_view` | documentation_documentationpage_change |  |
| `/admin/documentation/documentationpage/<path:object_id>/delete/` | `delete_view` | documentation_documentationpage_delete |  |
| `/admin/documentation/documentationpage/<path:object_id>/history/` | `history_view` | documentation_documentationpage_history | The 'history' admin view for this model. |
| `/admin/documentation/documentationpage/add/` | `add_view` | documentation_documentationpage_add |  |
| `/admin/export_suitecrm/suitecrmexportconfig/` | `changelist_view` | export_suitecrm_suitecrmexportconfig_changelist | The 'change list' admin view for this model. |
| `/admin/export_suitecrm/suitecrmexportconfig/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/export_suitecrm/suitecrmexportconfig/<path:object_id>/change/` | `change_view` | export_suitecrm_suitecrmexportconfig_change |  |
| `/admin/export_suitecrm/suitecrmexportconfig/<path:object_id>/delete/` | `delete_view` | export_suitecrm_suitecrmexportconfig_delete |  |
| `/admin/export_suitecrm/suitecrmexportconfig/<path:object_id>/history/` | `history_view` | export_suitecrm_suitecrmexportconfig_history | The 'history' admin view for this model. |
| `/admin/export_suitecrm/suitecrmexportconfig/add/` | `add_view` | export_suitecrm_suitecrmexportconfig_add |  |
| `/admin/filer/clipboard/` | `changelist_view` | filer_clipboard_changelist | The 'change list' admin view for this model. |
| `/admin/filer/clipboard/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/filer/clipboard/<path:object_id>/change/` | `change_view` | filer_clipboard_change |  |
| `/admin/filer/clipboard/<path:object_id>/delete/` | `delete_view` | filer_clipboard_delete |  |
| `/admin/filer/clipboard/<path:object_id>/history/` | `history_view` | filer_clipboard_history | The 'history' admin view for this model. |
| `/admin/filer/clipboard/add/` | `add_view` | filer_clipboard_add |  |
| `/admin/filer/file/` | `changelist_view` | filer_file_changelist | The 'change list' admin view for this model. |
| `/admin/filer/file/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/filer/file/<path:object_id>/change/` | `change_view` | filer_file_change |  |
| `/admin/filer/file/<path:object_id>/history/` | `history_view` | filer_file_history | The 'history' admin view for this model. |
| `/admin/filer/file/add/` | `add_view` | filer_file_add |  |
| `/admin/filer/folder/` | `changelist_view` | filer_folder_changelist | The 'change list' admin view for this model. |
| `/admin/filer/folder/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/filer/folder/<path:object_id>/change/` | `change_view` | filer_folder_change |  |
| `/admin/filer/folder/<path:object_id>/history/` | `history_view` | filer_folder_history | The 'history' admin view for this model. |
| `/admin/filer/folder/add/` | `add_view` | filer_folder_add |  |
| `/admin/filer/folderpermission/` | `changelist_view` | filer_folderpermission_changelist | The 'change list' admin view for this model. |
| `/admin/filer/folderpermission/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/filer/folderpermission/<path:object_id>/change/` | `change_view` | filer_folderpermission_change |  |
| `/admin/filer/folderpermission/<path:object_id>/delete/` | `delete_view` | filer_folderpermission_delete |  |
| `/admin/filer/folderpermission/<path:object_id>/history/` | `history_view` | filer_folderpermission_history | The 'history' admin view for this model. |
| `/admin/filer/folderpermission/add/` | `add_view` | filer_folderpermission_add |  |
| `/admin/filer/image/` | `changelist_view` | filer_image_changelist | The 'change list' admin view for this model. |
| `/admin/filer/image/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/filer/image/<path:object_id>/change/` | `change_view` | filer_image_change |  |
| `/admin/filer/image/<path:object_id>/history/` | `history_view` | filer_image_history | The 'history' admin view for this model. |
| `/admin/filer/image/add/` | `add_view` | filer_image_add |  |
| `/admin/filer/thumbnailoption/` | `changelist_view` | filer_thumbnailoption_changelist | The 'change list' admin view for this model. |
| `/admin/filer/thumbnailoption/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/filer/thumbnailoption/<path:object_id>/change/` | `change_view` | filer_thumbnailoption_change |  |
| `/admin/filer/thumbnailoption/<path:object_id>/delete/` | `delete_view` | filer_thumbnailoption_delete |  |
| `/admin/filer/thumbnailoption/<path:object_id>/history/` | `history_view` | filer_thumbnailoption_history | The 'history' admin view for this model. |
| `/admin/filer/thumbnailoption/add/` | `add_view` | filer_thumbnailoption_add |  |
| `/admin/ingest_csv/csvdocument/` | `changelist_view` | ingest_csv_csvdocument_changelist | The 'change list' admin view for this model. |
| `/admin/ingest_csv/csvdocument/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ingest_csv/csvdocument/<path:object_id>/change/` | `change_view` | ingest_csv_csvdocument_change |  |
| `/admin/ingest_csv/csvdocument/<path:object_id>/delete/` | `delete_view` | ingest_csv_csvdocument_delete |  |
| `/admin/ingest_csv/csvdocument/<path:object_id>/history/` | `history_view` | ingest_csv_csvdocument_history | The 'history' admin view for this model. |
| `/admin/ingest_csv/csvdocument/add/` | `add_view` | ingest_csv_csvdocument_add |  |
| `/admin/ingest_custom/customimportconfig/` | `changelist_view` | ingest_custom_customimportconfig_changelist | The 'change list' admin view for this model. |
| `/admin/ingest_custom/customimportconfig/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ingest_custom/customimportconfig/<path:object_id>/change/` | `change_view` | ingest_custom_customimportconfig_change |  |
| `/admin/ingest_custom/customimportconfig/<path:object_id>/delete/` | `delete_view` | ingest_custom_customimportconfig_delete |  |
| `/admin/ingest_custom/customimportconfig/<path:object_id>/history/` | `history_view` | ingest_custom_customimportconfig_history | The 'history' admin view for this model. |
| `/admin/ingest_custom/customimportconfig/add/` | `add_view` | ingest_custom_customimportconfig_add |  |
| `/admin/ingest_email/emailattachment/` | `changelist_view` | ingest_email_emailattachment_changelist | The 'change list' admin view for this model. |
| `/admin/ingest_email/emailattachment/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ingest_email/emailattachment/<path:object_id>/change/` | `change_view` | ingest_email_emailattachment_change |  |
| `/admin/ingest_email/emailattachment/<path:object_id>/delete/` | `delete_view` | ingest_email_emailattachment_delete |  |
| `/admin/ingest_email/emailattachment/<path:object_id>/history/` | `history_view` | ingest_email_emailattachment_history | The 'history' admin view for this model. |
| `/admin/ingest_email/emailattachment/add/` | `add_view` | ingest_email_emailattachment_add |  |
| `/admin/ingest_email/emailimportconfig/` | `changelist_view` | ingest_email_emailimportconfig_changelist | The 'change list' admin view for this model. |
| `/admin/ingest_email/emailimportconfig/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ingest_email/emailimportconfig/<path:object_id>/change/` | `change_view` | ingest_email_emailimportconfig_change |  |
| `/admin/ingest_email/emailimportconfig/<path:object_id>/delete/` | `delete_view` | ingest_email_emailimportconfig_delete |  |
| `/admin/ingest_email/emailimportconfig/<path:object_id>/history/` | `history_view` | ingest_email_emailimportconfig_history | The 'history' admin view for this model. |
| `/admin/ingest_email/emailimportconfig/add/` | `add_view` | ingest_email_emailimportconfig_add |  |
| `/admin/ingest_email/emailmessage/` | `changelist_view` | ingest_email_emailmessage_changelist | The 'change list' admin view for this model. |
| `/admin/ingest_email/emailmessage/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ingest_email/emailmessage/<path:object_id>/change/` | `change_view` | ingest_email_emailmessage_change |  |
| `/admin/ingest_email/emailmessage/<path:object_id>/delete/` | `delete_view` | ingest_email_emailmessage_delete |  |
| `/admin/ingest_email/emailmessage/<path:object_id>/history/` | `history_view` | ingest_email_emailmessage_history | The 'history' admin view for this model. |
| `/admin/ingest_email/emailmessage/add/` | `add_view` | ingest_email_emailmessage_add |  |
| `/admin/ingest_pdf/pdfdocument/` | `changelist_view` | ingest_pdf_pdfdocument_changelist | The 'change list' admin view for this model. |
| `/admin/ingest_pdf/pdfdocument/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ingest_pdf/pdfdocument/<path:object_id>/change/` | `change_view` | ingest_pdf_pdfdocument_change |  |
| `/admin/ingest_pdf/pdfdocument/<path:object_id>/delete/` | `delete_view` | ingest_pdf_pdfdocument_delete |  |
| `/admin/ingest_pdf/pdfdocument/<path:object_id>/history/` | `history_view` | ingest_pdf_pdfdocument_history | The 'history' admin view for this model. |
| `/admin/ingest_pdf/pdfdocument/add/` | `add_view` | ingest_pdf_pdfdocument_add |  |
| `/admin/ingest_pdf/pdfparserconfig/` | `changelist_view` | ingest_pdf_pdfparserconfig_changelist | The 'change list' admin view for this model. |
| `/admin/ingest_pdf/pdfparserconfig/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ingest_pdf/pdfparserconfig/<path:object_id>/change/` | `change_view` | ingest_pdf_pdfparserconfig_change |  |
| `/admin/ingest_pdf/pdfparserconfig/<path:object_id>/delete/` | `delete_view` | ingest_pdf_pdfparserconfig_delete |  |
| `/admin/ingest_pdf/pdfparserconfig/<path:object_id>/history/` | `history_view` | ingest_pdf_pdfparserconfig_history | The 'history' admin view for this model. |
| `/admin/ingest_pdf/pdfparserconfig/add/` | `add_view` | ingest_pdf_pdfparserconfig_add |  |
| `/admin/ingest_txt/txtdocument/` | `changelist_view` | ingest_txt_txtdocument_changelist | The 'change list' admin view for this model. |
| `/admin/ingest_txt/txtdocument/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ingest_txt/txtdocument/<path:object_id>/change/` | `change_view` | ingest_txt_txtdocument_change |  |
| `/admin/ingest_txt/txtdocument/<path:object_id>/delete/` | `delete_view` | ingest_txt_txtdocument_delete |  |
| `/admin/ingest_txt/txtdocument/<path:object_id>/history/` | `history_view` | ingest_txt_txtdocument_history | The 'history' admin view for this model. |
| `/admin/ingest_txt/txtdocument/add/` | `add_view` | ingest_txt_txtdocument_add |  |
| `/admin/ingest_url/urldocument/` | `changelist_view` | ingest_url_urldocument_changelist | The 'change list' admin view for this model. |
| `/admin/ingest_url/urldocument/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ingest_url/urldocument/<path:object_id>/change/` | `change_view` | ingest_url_urldocument_change |  |
| `/admin/ingest_url/urldocument/<path:object_id>/delete/` | `delete_view` | ingest_url_urldocument_delete |  |
| `/admin/ingest_url/urldocument/<path:object_id>/history/` | `history_view` | ingest_url_urldocument_history | The 'history' admin view for this model. |
| `/admin/ingest_url/urldocument/add/` | `add_view` | ingest_url_urldocument_add |  |
| `/admin/ingest_url/urlimportconfig/` | `changelist_view` | ingest_url_urlimportconfig_changelist | The 'change list' admin view for this model. |
| `/admin/ingest_url/urlimportconfig/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ingest_url/urlimportconfig/<path:object_id>/change/` | `change_view` | ingest_url_urlimportconfig_change |  |
| `/admin/ingest_url/urlimportconfig/<path:object_id>/delete/` | `delete_view` | ingest_url_urlimportconfig_delete |  |
| `/admin/ingest_url/urlimportconfig/<path:object_id>/history/` | `history_view` | ingest_url_urlimportconfig_history | The 'history' admin view for this model. |
| `/admin/ingest_url/urlimportconfig/add/` | `add_view` | ingest_url_urlimportconfig_add |  |
| `/admin/ingest_word/worddocument/` | `changelist_view` | ingest_word_worddocument_changelist | The 'change list' admin view for this model. |
| `/admin/ingest_word/worddocument/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ingest_word/worddocument/<path:object_id>/change/` | `change_view` | ingest_word_worddocument_change |  |
| `/admin/ingest_word/worddocument/<path:object_id>/delete/` | `delete_view` | ingest_word_worddocument_delete |  |
| `/admin/ingest_word/worddocument/<path:object_id>/history/` | `history_view` | ingest_word_worddocument_history | The 'history' admin view for this model. |
| `/admin/ingest_word/worddocument/add/` | `add_view` | ingest_word_worddocument_add |  |
| `/admin/ingest_word/wordimportbatch/` | `changelist_view` | ingest_word_wordimportbatch_changelist | The 'change list' admin view for this model. |
| `/admin/ingest_word/wordimportbatch/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/ingest_word/wordimportbatch/<path:object_id>/change/` | `change_view` | ingest_word_wordimportbatch_change |  |
| `/admin/ingest_word/wordimportbatch/<path:object_id>/delete/` | `delete_view` | ingest_word_wordimportbatch_delete |  |
| `/admin/ingest_word/wordimportbatch/<path:object_id>/history/` | `history_view` | ingest_word_wordimportbatch_history | The 'history' admin view for this model. |
| `/admin/ingest_word/wordimportbatch/add/` | `add_view` | ingest_word_wordimportbatch_add |  |
| `/admin/jsi18n/` | `i18n_javascript` | jsi18n | Display the i18n JavaScript that the Django admin requires. |
| `/admin/legacy_emma/emmacontact/` | `changelist_view` | legacy_emma_emmacontact_changelist | The 'change list' admin view for this model. |
| `/admin/legacy_emma/emmacontact/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/legacy_emma/emmacontact/<path:object_id>/change/` | `change_view` | legacy_emma_emmacontact_change |  |
| `/admin/legacy_emma/emmacontact/<path:object_id>/delete/` | `delete_view` | legacy_emma_emmacontact_delete |  |
| `/admin/legacy_emma/emmacontact/<path:object_id>/history/` | `history_view` | legacy_emma_emmacontact_history | The 'history' admin view for this model. |
| `/admin/legacy_emma/emmacontact/add/` | `add_view` | legacy_emma_emmacontact_add |  |
| `/admin/legacy_emma/emmaimportsource/` | `changelist_view` | legacy_emma_emmaimportsource_changelist | The 'change list' admin view for this model. |
| `/admin/legacy_emma/emmaimportsource/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/legacy_emma/emmaimportsource/<path:object_id>/change/` | `change_view` | legacy_emma_emmaimportsource_change |  |
| `/admin/legacy_emma/emmaimportsource/<path:object_id>/delete/` | `delete_view` | legacy_emma_emmaimportsource_delete |  |
| `/admin/legacy_emma/emmaimportsource/<path:object_id>/history/` | `history_view` | legacy_emma_emmaimportsource_history | The 'history' admin view for this model. |
| `/admin/legacy_emma/emmaimportsource/add/` | `add_view` | legacy_emma_emmaimportsource_add |  |
| `/admin/legacy_emma/emmaproject/` | `changelist_view` | legacy_emma_emmaproject_changelist | The 'change list' admin view for this model. |
| `/admin/legacy_emma/emmaproject/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/legacy_emma/emmaproject/<path:object_id>/change/` | `change_view` | legacy_emma_emmaproject_change |  |
| `/admin/legacy_emma/emmaproject/<path:object_id>/delete/` | `delete_view` | legacy_emma_emmaproject_delete |  |
| `/admin/legacy_emma/emmaproject/<path:object_id>/history/` | `history_view` | legacy_emma_emmaproject_history | The 'history' admin view for this model. |
| `/admin/legacy_emma/emmaproject/add/` | `add_view` | legacy_emma_emmaproject_add |  |
| `/admin/login/` | `login` | login | Display the login form for the given HttpRequest. |
| `/admin/logout/` | `logout` | logout | Log out the user for the given HttpRequest. |
| `/admin/namazu/namazudocument/` | `changelist_view` | namazu_namazudocument_changelist | The 'change list' admin view for this model. |
| `/admin/namazu/namazudocument/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/namazu/namazudocument/<path:object_id>/change/` | `change_view` | namazu_namazudocument_change |  |
| `/admin/namazu/namazudocument/<path:object_id>/delete/` | `delete_view` | namazu_namazudocument_delete |  |
| `/admin/namazu/namazudocument/<path:object_id>/history/` | `history_view` | namazu_namazudocument_history | The 'history' admin view for this model. |
| `/admin/namazu/namazudocument/add/` | `add_view` | namazu_namazudocument_add |  |
| `/admin/namazu/namazuindex/` | `changelist_view` | namazu_namazuindex_changelist | The 'change list' admin view for this model. |
| `/admin/namazu/namazuindex/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/namazu/namazuindex/<path:object_id>/change/` | `change_view` | namazu_namazuindex_change |  |
| `/admin/namazu/namazuindex/<path:object_id>/delete/` | `delete_view` | namazu_namazuindex_delete |  |
| `/admin/namazu/namazuindex/<path:object_id>/history/` | `history_view` | namazu_namazuindex_history | The 'history' admin view for this model. |
| `/admin/namazu/namazuindex/add/` | `add_view` | namazu_namazuindex_add |  |
| `/admin/normalizer/normalizationrule/` | `changelist_view` | normalizer_normalizationrule_changelist | The 'change list' admin view for this model. |
| `/admin/normalizer/normalizationrule/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/normalizer/normalizationrule/<path:object_id>/change/` | `change_view` | normalizer_normalizationrule_change |  |
| `/admin/normalizer/normalizationrule/<path:object_id>/delete/` | `delete_view` | normalizer_normalizationrule_delete |  |
| `/admin/normalizer/normalizationrule/<path:object_id>/history/` | `history_view` | normalizer_normalizationrule_history | The 'history' admin view for this model. |
| `/admin/normalizer/normalizationrule/add/` | `add_view` | normalizer_normalizationrule_add |  |
| `/admin/parser_json/jsonparserconfig/` | `changelist_view` | parser_json_jsonparserconfig_changelist | The 'change list' admin view for this model. |
| `/admin/parser_json/jsonparserconfig/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/parser_json/jsonparserconfig/<path:object_id>/change/` | `change_view` | parser_json_jsonparserconfig_change |  |
| `/admin/parser_json/jsonparserconfig/<path:object_id>/delete/` | `delete_view` | parser_json_jsonparserconfig_delete |  |
| `/admin/parser_json/jsonparserconfig/<path:object_id>/history/` | `history_view` | parser_json_jsonparserconfig_history | The 'history' admin view for this model. |
| `/admin/parser_json/jsonparserconfig/add/` | `add_view` | parser_json_jsonparserconfig_add |  |
| `/admin/password_change/` | `password_change` | password_change | Handle the "change password" task -- both form display and validation. |
| `/admin/password_change/done/` | `password_change_done` | password_change_done | Display the "success" page after a password change. |
| `/admin/r/<path:content_type_id>/<path:object_id>/` | `shortcut` | view_on_site | Redirect to an object's page based on a content-type ID and an object ID. |
| `/admin/sites/site/` | `changelist_view` | sites_site_changelist | The 'change list' admin view for this model. |
| `/admin/sites/site/<path:object_id>/` | `view` |  | Provide a redirect on any GET request. |
| `/admin/sites/site/<path:object_id>/change/` | `change_view` | sites_site_change |  |
| `/admin/sites/site/<path:object_id>/delete/` | `delete_view` | sites_site_delete |  |
| `/admin/sites/site/<path:object_id>/history/` | `history_view` | sites_site_history | The 'history' admin view for this model. |
| `/admin/sites/site/add/` | `add_view` | sites_site_add |  |
| `/crm-bridge/` | `view` | dashboard | Render a template. Pass keyword arguments from the URLconf to the context. |
| `/crm-bridge/status/` | `view` | status | Render a template. Pass keyword arguments from the URLconf to the context. |
| `/intake/admin/` | `view` | admin_redirect | Provide a redirect on any GET request. |
| `/password-reset/` | `view` | password_reset |  |
| `/password-reset/complete/` | `view` | password_reset_complete |  |
| `/password-reset/confirm/<uidb64>/<token>/` | `view` | password_reset_confirm |  |
| `/password-reset/done/` | `view` | password_reset_done |  |

### djangocms_link  (1)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/admin/djangocms_link/link/urls` | `url_view` | djangocms_link_link_urls |  |

### djangocms_snippet  (1)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/admin/djangocms_snippet/snippet/<int:snippet_id>/preview/` | `preview_view` | djangocms_snippet_snippet_preview | Custom preview endpoint to display a change form in read only mode |

### djangocms_text_ckeditor  (2)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/admin/cms/page/^plugin/text_plugin/^delete-on-cancel/$` | `delete_on_cancel` | djangocms_text_ckeditor_textplugin_delete_on_cancel |  |
| `/admin/cms/page/^plugin/text_plugin/^render-plugin/$` | `render_plugin` | djangocms_text_ckeditor_textplugin_render_plugin |  |

### djangocms_versioning  (24)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/admin/cms/pagecontent/^([0-9]+)/change-navigation/$` | `change_innavigation` | cms_pagecontent_change_innavigation |  |
| `/admin/cms/pagecontent/^([0-9]+)/copy-language/$` | `copy_language` | cms_pagecontent_copy_language |  |
| `/admin/djangocms_versioning/pagecontentversion/` | `changelist_view` | djangocms_versioning_pagecontentversion_changelist | Handle grouper filtering on the changelist |
| `/admin/djangocms_versioning/pagecontentversion/<path:object_id>/archive/` | `archive_view` | djangocms_versioning_pagecontentversion_archive | Archives the specified version and redirects back to the |
| `/admin/djangocms_versioning/pagecontentversion/<path:object_id>/compare/` | `compare_view` | djangocms_versioning_pagecontentversion_compare | Compares two versions |
| `/admin/djangocms_versioning/pagecontentversion/<path:object_id>/delete/` | `delete_view` | djangocms_versioning_pagecontentversion_delete | Do not allow deleting single version objects. Use discard instead. |
| `/admin/djangocms_versioning/pagecontentversion/<path:object_id>/discard/` | `discard_view` | djangocms_versioning_pagecontentversion_discard | Discards the specified version |
| `/admin/djangocms_versioning/pagecontentversion/<path:object_id>/edit-redirect/` | `edit_redirect_view` | djangocms_versioning_pagecontentversion_edit_redirect | Redirects to the admin change view and creates a draft version |
| `/admin/djangocms_versioning/pagecontentversion/<path:object_id>/publish/` | `publish_view` | djangocms_versioning_pagecontentversion_publish | Publishes the specified version and redirects back to the |
| `/admin/djangocms_versioning/pagecontentversion/<path:object_id>/revert/` | `revert_view` | djangocms_versioning_pagecontentversion_revert | Reverts to the specified version i.e. creates a draft from it. |
| `/admin/djangocms_versioning/pagecontentversion/<path:object_id>/unlock/` | `unlock_view` | djangocms_versioning_pagecontentversion_unlock | Unlock a locked version |
| `/admin/djangocms_versioning/pagecontentversion/<path:object_id>/unpublish/` | `unpublish_view` | djangocms_versioning_pagecontentversion_unpublish | Unpublishes the specified version and redirects back to the |
| `/admin/djangocms_versioning/pagecontentversion/select/` | `grouper_form_view` | djangocms_versioning_pagecontentversion_grouper | Displays an intermediary page to select a grouper object |
| `/admin/djangocms_versioning/snippetversion/` | `changelist_view` | djangocms_versioning_snippetversion_changelist | Handle grouper filtering on the changelist |
| `/admin/djangocms_versioning/snippetversion/<path:object_id>/archive/` | `archive_view` | djangocms_versioning_snippetversion_archive | Archives the specified version and redirects back to the |
| `/admin/djangocms_versioning/snippetversion/<path:object_id>/compare/` | `compare_view` | djangocms_versioning_snippetversion_compare | Compares two versions |
| `/admin/djangocms_versioning/snippetversion/<path:object_id>/delete/` | `delete_view` | djangocms_versioning_snippetversion_delete | Do not allow deleting single version objects. Use discard instead. |
| `/admin/djangocms_versioning/snippetversion/<path:object_id>/discard/` | `discard_view` | djangocms_versioning_snippetversion_discard | Discards the specified version |
| `/admin/djangocms_versioning/snippetversion/<path:object_id>/edit-redirect/` | `edit_redirect_view` | djangocms_versioning_snippetversion_edit_redirect | Redirects to the admin change view and creates a draft version |
| `/admin/djangocms_versioning/snippetversion/<path:object_id>/publish/` | `publish_view` | djangocms_versioning_snippetversion_publish | Publishes the specified version and redirects back to the |
| `/admin/djangocms_versioning/snippetversion/<path:object_id>/revert/` | `revert_view` | djangocms_versioning_snippetversion_revert | Reverts to the specified version i.e. creates a draft from it. |
| `/admin/djangocms_versioning/snippetversion/<path:object_id>/unlock/` | `unlock_view` | djangocms_versioning_snippetversion_unlock | Unlock a locked version |
| `/admin/djangocms_versioning/snippetversion/<path:object_id>/unpublish/` | `unpublish_view` | djangocms_versioning_snippetversion_unpublish | Unpublishes the specified version and redirects back to the |
| `/admin/djangocms_versioning/snippetversion/select/` | `grouper_form_view` | djangocms_versioning_snippetversion_grouper | Displays an intermediary page to select a grouper object |

### drf_spectacular  (9)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/api/docs/` | `view` | swagger-ui |  |
| `/api/redoc/` | `view` | redoc |  |
| `/api/schema/` | `view` | schema | OpenApi3 schema for this API. Format can be selected via content negotiation. |
| `/cv-extractor/api/docs/` | `view` | swagger-ui |  |
| `/cv-extractor/api/redoc/` | `view` | redoc |  |
| `/cv-extractor/api/schema/` | `view` | schema | OpenApi3 schema for this API. Format can be selected via content negotiation. |
| `/matching/api/docs/` | `view` | swagger-ui |  |
| `/matching/api/redoc/` | `view` | redoc |  |
| `/matching/api/schema/` | `view` | schema | OpenApi3 schema for this API. Format can be selected via content negotiation. |

### filer  (18)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/admin/filer/clipboard/operations/delete_clipboard/` | `delete_clipboard` | filer-delete_clipboard |  |
| `/admin/filer/clipboard/operations/discard_clipboard/` | `discard_clipboard` | filer-discard_clipboard |  |
| `/admin/filer/clipboard/operations/paste_clipboard_to_folder/` | `paste_clipboard_to_folder` | filer-paste_clipboard_to_folder |  |
| `/admin/filer/clipboard/operations/upload/<int:folder_id>/` | `ajax_upload` | filer-ajax_upload | Receives an upload from the uploader. Receives only one file at a time. |
| `/admin/filer/clipboard/operations/upload/no_folder/` | `ajax_upload` | filer-ajax_upload | Receives an upload from the uploader. Receives only one file at a time. |
| `/admin/filer/file/<path:object_id>/delete/` | `delete_view` | filer_file_delete | Overrides the default to enable redirecting to the directory view after |
| `/admin/filer/file/icon/<int:file_id>/<int:size>` | `icon_view` | filer_file_fileicon |  |
| `/admin/filer/folder/` | `directory_listing` | filer-directory_listing-root |  |
| `/admin/filer/folder/<int:folder_id>/list/` | `directory_listing` | filer-directory_listing |  |
| `/admin/filer/folder/<int:folder_id>/make_folder/` | `make_folder` | filer-directory_listing-make_folder |  |
| `/admin/filer/folder/<path:object_id>/delete/` | `delete_view` | filer_folder_delete | Overrides the default to enable redirecting to the directory view after |
| `/admin/filer/folder/images_with_missing_data/` | `directory_listing` | filer-directory_listing-images_with_missing_data |  |
| `/admin/filer/folder/last/` | `directory_listing` | filer-directory_listing-last |  |
| `/admin/filer/folder/make_folder/` | `make_folder` | filer-directory_listing-make_root_folder |  |
| `/admin/filer/folder/unfiled_images/` | `directory_listing` | filer-directory_listing-unfiled_images |  |
| `/admin/filer/image/<path:object_id>/delete/` | `delete_view` | filer_image_delete | Overrides the default to enable redirecting to the directory view after |
| `/admin/filer/image/expand/<int:file_id>` | `expand_view` | filer_image_expand |  |
| `/admin/filer/image/icon/<int:file_id>/<int:size>` | `icon_view` | filer_image_fileicon |  |

### ingest_csv  (7)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/csv/` | `csv_dashboard` | csv_dashboard | CSV Dashboard View |
| `/csv/api/list/` | `view` | csv_api_list | API View for CSV List |
| `/csv/api/upload/` | `view` | csv_api_upload | API View for CSV Upload |
| `/csv/dashboard/` | `csv_dashboard` | csv_dashboard | CSV Dashboard View |
| `/csv/detail/<uuid:pk>/` | `csv_detail` | csv_detail | CSV Detail View |
| `/csv/list/` | `csv_dashboard` | csv_list | CSV Dashboard View |
| `/csv/upload/` | `csv_upload` | csv_upload | CSV Upload View |

### ingest_pdf  (14)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/pdf/` | `upload_pdf` | upload_pdf | Main PDF upload view |
| `/pdf/<int:pdf_id>/` | `pdf_detail` | pdf_detail | Show PDF details |
| `/pdf/<int:pdf_id>/delete/` | `delete_pdf` | delete_pdf | Delete PDF document |
| `/pdf/<int:pdf_id>/download/` | `download_pdf` | download_pdf | Download PDF file |
| `/pdf/<int:pdf_id>/pipeline/` | `start_pipeline` | start_pipeline | Manuell Pipeline starten (für Tests/Fallback) |
| `/pdf/<int:pdf_id>/reprocess/` | `reprocess_pdf` | reprocess_pdf | Fehlgeschlagenes PDF erneut verarbeiten |
| `/pdf/<int:pdf_id>/status/` | `pdf_status` | pdf_status | Get PDF processing status |
| `/pdf/ajax/upload/` | `handle_upload` | handle_upload | Handle PDF file upload via AJAX |
| `/pdf/api/check-duplicate/` | `check_duplicate_api` | check_duplicate_api | API-Endpoint zur Dublettenprüfung - findet ALLE Personen mit diesem Namen |
| `/pdf/api/preview/<str:directory>/<str:filename>/` | `get_json_preview` | get_json_preview | GET: /api/preview/{directory}/{filename} |
| `/pdf/api/upload/` | `upload_pdf_api` | upload_pdf_api | API-Endpoint für PDF-Upload mit Dublettenprüfung |
| `/pdf/list/` | `pdf_list` | pdf_list | List all PDF documents |
| `/pdf/stats/` | `pdf_stats` | pdf_stats | Statistiken über PDF-Importe |
| `/pdf/upload/` | `upload_pdf` | upload_pdf | Main PDF upload view |

### ingest_txt  (7)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/txt/` | `txt_dashboard` | txt_dashboard | TXT Dashboard View |
| `/txt/api/list/` | `view` | txt_api_list | API View for TXT List |
| `/txt/api/upload/` | `view` | txt_api_upload | API View for TXT Upload |
| `/txt/dashboard/` | `txt_dashboard` | txt_dashboard | TXT Dashboard View |
| `/txt/detail/<uuid:pk>/` | `txt_detail` | txt_detail | TXT Detail View |
| `/txt/list/` | `txt_dashboard` | txt_list | TXT Dashboard View |
| `/txt/upload/` | `txt_upload` | txt_upload | TXT Upload View |

### ingest_url  (7)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/url/` | `url_dashboard` | dashboard | Dashboard für URL-Import |
| `/url/api/list/` | `view` | api_list | API für URL-Dokumente Liste |
| `/url/api/upload/` | `view` | api_upload | API für URL-Upload |
| `/url/dashboard/` | `url_dashboard` | dashboard | Dashboard für URL-Import |
| `/url/detail/<uuid:pk>/` | `url_detail` | detail | Detailansicht eines URL-Dokuments |
| `/url/list/` | `url_list` | list | Liste aller URL-Dokumente |
| `/url/upload/` | `url_upload` | upload | Upload-Seite für URLs |

### ingest_word  (10)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/word/api/batch/` | `view` | api_batch | API für Batch-Verarbeitung |
| `/word/api/documents/` | `view` | api_documents | API für Liste aller Word-Dokumente |
| `/word/api/documents/<uuid:pk>/` | `view` | api_document_detail | API für einzelne Word-Dokument-Details |
| `/word/api/parse/` | `view` | api_parse | API für reines Parsing (ohne Speicherung) |
| `/word/api/process/<uuid:document_id>/` | `process_word_pipeline` | api_process | Word mit voller Pipeline verarbeiten |
| `/word/api/upload/` | `view` | api_upload | API für Word Upload |
| `/word/batch/<uuid:batch_id>/` | `batch_detail_view` | batch_detail | Web UI für Batch-Details |
| `/word/dashboard/` | `word_dashboard_view` | dashboard | Dashboard für Word Importe |
| `/word/health/` | `health_check` | health | Einfacher Health Check |
| `/word/upload/` | `word_upload_view` | upload | Web UI für Word Upload |

### rest_framework  (5)

| Pfad | View | Name | Beschreibung |
|------|------|------|--------------|
| `/api-token-auth/` | `view` | api_token_auth |  |
| `/api/` | `view` | api-root | The default basic root view for DefaultRouter |
| `/api/<drf_format_suffix:format>` | `view` | api-root | The default basic root view for DefaultRouter |
| `/api/presort/` | `view` | api-root | The default basic root view for DefaultRouter |
| `/api/presort/<drf_format_suffix:format>` | `view` | api-root | The default basic root view for DefaultRouter |

## 2. Elasticsearch-Indizes

Insgesamt **10** Indizes.

### `abpe_consultants_index`  —  160 Dokumente

Felder: `aid`, `availability`, `consultant_dir`, `degree`, `enriched_at`, `facets`, `first_name`, `full_name`, `headline`, `indexed_at`, `last_name`, `location`, `matching`, `searchable_text`, `statistics`, `summary`, `version`

### `abpe_emails`  —  1015722 Dokumente

Felder: `account`, `body`, `date`, `folder`, `from_addr`, `has_attachments`, `indexed_at`, `message_id`, `size_bytes`, `subject`, `to_addr`, `uid`

### `abpe_namazu_profiles`  —  23656 Dokumente

Felder: `body_text`, `email`, `filename`, `first_name`, `full_name`, `funktion`, `gulp_id`, `indexed_at`, `last_name`, `profile_url`, `status`, `telefon`, `verfuegbar_ab`

### `abpe_profile_versions`  —  22 Dokumente

Felder: `created_at`, `data`, `entity_id`, `id`, `is_current`, `origin`, `profile_current_version`, `profile_id`, `profile_type`, `source`, `status`, `updated_at`, `version`

### `abpe_profile_versions_v2`  —  14 Dokumente

Felder: `created_at`, `data`, `email`, `full_name`, `is_current`, `location`, `metadata`, `profile_id`, `profile_type`, `profile_version_id`, `search_text`, `skills`, `updated_at`, `version`

### `abpe_profiles_v2`  —  0 Dokumente

Felder: `ai_specializations`, `aid_experience_years`, `aid_id`, `aid_landscape_code`, `aid_role_code`, `aid_role_name`, `cloud`, `created_at`, `daily_rate`, `email`, `first_name`, `frameworks`, `full_data`, `headline`, `id`, `is_current`, `is_remote_ready`, `last_name`, `location_city`, `location_country`, `profile_id`, `programming_languages`, `seniority_score`, `skill_vector`, `summary`, `tools`, `total_years`, `updated_at`, `version`

### `abpe_skills_index`  —  10281 Dokumente

Felder: `category`, `confidence`, `created_at`, `embedding`, `frequency`, `metadata`, `term`, `updated_at`, `variations`

### `content`  —  23678 Dokumente

Felder: `address_street`, `alt_address_street`, `alt_city`, `alt_country`, `alt_postalcode`, `alt_state`, `assistant`, `assistant_phone`, `birth_day`, `birth_month`, `birthdate`, `city`, `country`, `crm_id`, `department`, `description`, `do_not_call`, `einsatzort`, `emails`, `first_name`, `freelancermap`, `gulp`, `kind`, `konditionen`, `kontakt_status`, `kontakt_typ`, `last_name`, `name`, `notes`, `ogo`, `phones`, `postalcode`, `salutation`, `state`, `title`, `verfuegbar_ab`, `web_urls`, `whatsapp_number`

### `content_firma`  —  1319 Dokumente

Felder: `account_status`, `account_type`, `annual_revenue`, `billing_city`, `billing_country`, `billing_postalcode`, `billing_state`, `billing_street`, `contact_crm_ids`, `contacts`, `crm_id`, `description`, `emails`, `employees`, `industry`, `kind`, `kunden_nummer`, `name`, `notes`, `ownership`, `parent_crm_id`, `phones`, `rating`, `shipping_city`, `shipping_country`, `shipping_postalcode`, `shipping_state`, `shipping_street`, `sic_code`, `ticker_symbol`, `website`

### `dms`  —  24637 Dokumente

Felder: `content`, `description`, `direction`, `doctype_key`, `doctype_label`, `document_date`, `filename`, `gewerk_nummer`, `in_trash`, `mimetype`, `needs_review`, `owner_cities`, `owner_countries`, `owner_crm_ids`, `owner_emails`, `owner_names`, `owner_notes`, `owner_phones`, `owner_postalcodes`, `retention_until`, `size_bytes`, `source`, `status`, `title`, `uuid`, `valid_until`
