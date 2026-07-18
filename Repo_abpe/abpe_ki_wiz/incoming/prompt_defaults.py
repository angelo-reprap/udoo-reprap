"""
Seed-Prompts für WizardPrompt (DB via sync_wizard_prompts).

Platzhalter DeepSeek-intern:
  [[INSTRUCTION]] [[TEXT]] [[NOTES]] [[CONTEXT]] [[KOPF]] [[BRIEFING]] [[ANSWERS]]

[[CONTEXT]] wird in Phase 1 vom prompt_builder mit JSON aus Provider-Katalog befüllt.
"""

WIZARD_PROMPT_DEFAULTS = [
    # ── Shared ────────────────────────────────────────────────────────────────
    {
        'key': 'wiz_shared_analyze',
        'wizard_id': 'general',
        'phase': 'analyze',
        'name': 'Shared: Briefing analysieren',
        'description': 'Erkennt Wizard-Typ, Scope und offene Klärpunkte aus Freitext.',
        'app_scope': 'general',
        'system': (
            'Du analysierst Anforderungen für ABpE-Assistenten (E-Mail-Vorlagen, '
            'Matching-Anschreiben, Dokumente). Antworte AUSSCHLIESSLICH mit JSON, '
            'ohne Markdown, ohne Vorspann.'
        ),
        'user_template': (
            '[[CONTEXT]]\n\nBriefing:\n[[BRIEFING]]\n\n'
            'Gib GENAU dieses JSON zurück:\n'
            '{"understood": true, "wizard_id_hint": "", "app_scope_hint": "", '
            '"event_type_hint": "", "summary": "", "missing_topics": []}'
        ),
        'instruction_default': '',
        'checklist_template': (
            'Nur JSON zurückgeben\n'
            'missing_topics: Liste von Klärpunkt-IDs aus dem Katalog\n'
            'Keine erfundenen Fakten'
        ),
    },
    # ── Email Template Wizard ─────────────────────────────────────────────────
    {
        'key': 'wiz_email_analyze',
        'wizard_id': 'email_template',
        'phase': 'analyze',
        'name': 'Email: Briefing analysieren',
        'description': 'E-Mail-Vorlage — Intent, App-Bereich und fehlende Klärpunkte.',
        'app_scope': 'general',
        'system': (
            'Du analysierst Anforderungen für E-Mail-Vorlagen im ABpE Email Studio. '
            'Erkenne app_scope aus dem Briefing: telefon (MeetMe/PBX), matching, intake, '
            'portal, general (Abwesenheit, Festgrüße, allgemeine Infos). '
            'Antworte AUSSCHLIESSLICH mit JSON, ohne Markdown.'
        ),
        'user_template': (
            '[[CONTEXT]]\n\nBriefing:\n[[BRIEFING]]\n\n'
            'Gib GENAU dieses JSON zurück:\n'
            '{"understood": true, "summary": "", "app_scope": "general", '
            '"event_type": "info", "missing_topics": []}'
        ),
        'instruction_default': '',
        'checklist_template': (
            'missing_topics nur aus dem mitgelieferten question_catalog\n'
            'app_scope aus erlaubter Liste in CONTEXT\n'
            'event_type: invite|reminder|confirm|cancel|info'
        ),
    },
    {
        'key': 'wiz_email_clarify',
        'wizard_id': 'email_template',
        'phase': 'clarify',
        'name': 'Email: Klärung auswerten',
        'description': 'Prüft ob alle Pflicht-Klärpunkte beantwortet sind.',
        'app_scope': 'general',
        'system': (
            'Du prüfst Antworten eines Email-Studio-Wizards. '
            'Antworte AUSSCHLIESSLICH mit JSON.'
        ),
        'user_template': (
            '[[CONTEXT]]\n\nBriefing:\n[[BRIEFING]]\n\nAntworten:\n[[ANSWERS]]\n\n'
            'Gib GENAU dieses JSON zurück:\n'
            '{"complete": true, "missing_topics": [], "notes": ""}'
        ),
        'instruction_default': '',
        'checklist_template': '',
    },
    {
        'key': 'wiz_email_suggest_meta',
        'wizard_id': 'email_template',
        'phase': 'suggest_meta',
        'name': 'Email: Metadaten vorschlagen',
        'description': 'Name, Betreff, Identifier, Sender, Signatur — Autofill.',
        'app_scope': 'general',
        'system': (
            'Du schlägst Metadaten für eine E-Mail-Vorlage vor. '
            'Nutze app_scope aus Antworten (S1). '
            'Bei general: keine MeetMe-Variablen im Betreff unless Briefing verlangt es. '
            'Bei telefon: {termin_datum} etc. erlaubt. '
            'Antworte AUSSCHLIESSLICH mit JSON. Identifier: snake_case, nur a-z0-9_. '
            'Betreff darf {variablen} aus CONTEXT enthalten.'
        ),
        'user_template': (
            '[[CONTEXT]]\n\nBriefing:\n[[BRIEFING]]\n\nAntworten:\n[[ANSWERS]]\n\n'
            'Gib GENAU dieses JSON zurück:\n'
            '{"name": "", "identifier": "", "subject": "", "description": "", '
            '"app_scope": "general", "event_type": "info", "sender_mode": "USER", '
            '"signature_mode": "USER", "status": "DRAFT"}'
        ),
        'instruction_default': '',
        'checklist_template': (
            'identifier eindeutig, snake_case\n'
            'status immer DRAFT\n'
            'Variablen im Betreff nur aus CONTEXT.variables'
        ),
    },
    {
        'key': 'wiz_email_generate',
        'wizard_id': 'email_template',
        'phase': 'generate',
        'name': 'Email: HTML + TXT generieren',
        'description': 'Erzeugt html_body und text_body mit Modulen und Variablen.',
        'app_scope': 'general',
        'system': (
            'Du erstellst E-Mail-Vorlagen für ABpE Email Studio. '
            'Respektiere app_scope aus META/ANSWERS: '
            'general = keine erfundenen MeetMe-Felder; telefon = Termin-Variablen OK. '
            'User-Absender: {sender_name}, {sender_email} erlaubt. '
            'Antworte AUSSCHLIESSLICH mit JSON. '
            'HTML: inline CSS, 600px Tabellen-Layout, Outlook-tauglich. '
            'Module NUR als {{block:identifier}} aus CONTEXT.modules. '
            'Variablen NUR als {name} aus CONTEXT.variables. '
            'Kein Markdown, kein erfundenes Datum.'
        ),
        'user_template': (
            '[[CONTEXT]]\n\nBriefing:\n[[BRIEFING]]\n\nAntworten:\n[[ANSWERS]]\n\n'
            'Metadaten:\n[[META]]\n\n'
            '[[INSTRUCTION]]\n\n'
            'Gib GENAU dieses JSON zurück:\n'
            '{"html_body": "", "text_body": "", "variables_used": []}'
        ),
        'instruction_default': '',
        'checklist_template': (
            'Alle checklist[] Punkte aus CONTEXT einhalten\n'
            '{{block:signature}} wenn signature_mode nicht NONE\n'
            'Keine unbekannten Platzhalter'
        ),
    },
    # ── Matching (Vorbereitung Phase 3) ───────────────────────────────────────
    {
        'key': 'wiz_matching_berater_analyze',
        'wizard_id': 'matching_berater',
        'phase': 'analyze',
        'name': 'Matching Berater: Briefing analysieren',
        'description': 'Anfrage an Beraterprofil — Intent erkennen.',
        'app_scope': 'matching',
        'system': (
            'Du analysierst Anforderungen für Matching-Anschreiben an Berater. '
            'Antworte AUSSCHLIESSLICH mit JSON.'
        ),
        'user_template': (
            '[[CONTEXT]]\n\nBriefing:\n[[BRIEFING]]\n\n'
            'Gib GENAU dieses JSON zurück:\n'
            '{"understood": true, "summary": "", "missing_topics": []}'
        ),
        'instruction_default': '',
        'checklist_template': '',
    },
    {
        'key': 'wiz_matching_kunde_analyze',
        'wizard_id': 'matching_kunde',
        'phase': 'analyze',
        'name': 'Matching Kunde: Briefing analysieren',
        'description': 'Kandidatenvorschläge an Kunde — Intent erkennen.',
        'app_scope': 'matching',
        'system': (
            'Du analysierst Anforderungen für Matching-Anschreiben an Kunden. '
            'Antworte AUSSCHLIESSLICH mit JSON.'
        ),
        'user_template': (
            '[[CONTEXT]]\n\nBriefing:\n[[BRIEFING]]\n\n'
            'Gib GENAU dieses JSON zurück:\n'
            '{"understood": true, "summary": "", "missing_topics": []}'
        ),
        'instruction_default': '',
        'checklist_template': '',
    },
]
