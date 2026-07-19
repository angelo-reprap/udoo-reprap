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
            'Du erstellst E-Mail-Vorlagen für ABpE Email Studio (MCID). '
            'Drei Ebenen: Variable={name} nur Rohdaten; '
            'Modul={{block:id}} nur Format (optional {{block:id}}…{{/block}} mit Inhalt); '
            'Block=Modul+Variablen aus CONTEXT.catalog.blocks '
            '(z.B. {{block:block_teilnehmer}}, {{block:block_system_status}}, {{block:block_termin}}). '
            'Respektiere app_scope: general = keine erfundenen MeetMe-Felder; telefon = Termin OK. '
            'CONTEXT.facts NUTZEN, nicht erfinden. '
            'Struktur: {{block:abcona_header_blau}} oder '
            '{{block:abcona_header_blau_adresse}} (Header+Kontakt) '
            '→ optional label_* → Body → {{block:signature}} XOR footer_*. '
            'Header NIEMALS als {{block:block_abcona_…}} und nie adrersse tippen. '
            'Nur Inhalts-Blöcke haben Prefix block_ (block_teilnehmer …). '
            'Schrift nur Arial 14px #333333, Marke #163258, 600px Tabellen, inline CSS. '
            'CONTEXT.catalog.layout_rules und CONTEXT.catalog.blocks beachten. '
            'Format-Module: {{block:fmt_aufzaehlung}}…{{/block}} — innen nur Plaintext/{variablen}, '
            'KEIN <ul>/<li>/<table>, keine selbst getippten * oder -. '
            'Aufzählung NUR so: (A) JEDEN Punkt in EIGENE Zeile ODER (B) Einzeiler mit Semikolon '
            '„Hund; Katze; Pferd“. Nie „Hund Katze Pferd“ nur mit Leerzeichen. '
            'Tabelle: jede Tabellenzeile eigene Zeile mit | zwischen Spalten. '
            'Wenn ANSWERS.I4=yes_block oder M2=block: Teilnehmer als {{block:block_teilnehmer}}. '
            'Wenn L4=block: {{block:block_system_status}}. '
            'Bevorzuge Blocks statt {teilnehmer_liste_html}/{system_status_html}. '
            'Zusätzlich layout_suggestions[] vorschlagen (Fragen an den Nutzer). '
            'Antworte AUSSCHLIESSLICH mit JSON. Kein Markdown.'
        ),
        'user_template': (
            '[[CONTEXT]]\n\n'
            '(facts in CONTEXT — Firmendaten/User nicht halluzinieren)\n\n'
            'Briefing:\n[[BRIEFING]]\n\nAntworten:\n[[ANSWERS]]\n\n'
            'Metadaten:\n[[META]]\n\n'
            '[[INSTRUCTION]]\n\n'
            'Gib GENAU dieses JSON zurück:\n'
            '{"html_body": "", "text_body": "", "variables_used": [], '
            '"layout_suggestions": [{"id": "", "question": "", "syntax": ""}]}'
        ),
        'instruction_default': '',
        'checklist_template': (
            'Alle checklist[] Punkte aus CONTEXT einhalten\n'
            'facts._rules beachten (Adressen/Firmendaten)\n'
            '{{block:signature}} wenn signature_mode nicht NONE\n'
            'Blocks aus CONTEXT.catalog.blocks bevorzugen\n'
            'Keine unbekannten Platzhalter'
        ),
    },
    # ── Email Modul (bauen / erweitern) ───────────────────────────────────────
    {
        'key': 'wiz_email_module_analyze',
        'wizard_id': 'email_module',
        'phase': 'analyze',
        'name': 'Email-Modul: Briefing analysieren',
        'description': 'Erkennt gewünschten Modul-Typ und fehlende Infos.',
        'app_scope': 'general',
        'system': (
            'Du analysierst ein Briefing für ein einzelnes ABpE Email-Modul (MCID). '
            'Kein vollständiges Mail-Template. '
            'Erkenne module_type_hint: HEADER|SECTION|BUTTON|FOOTER|SIGNATURE|DISCLAIMER. '
            'missing_topics nur aus: T1 (Typ), M1 (neu/erweitern), C1 (Firmendaten). '
            'Antworte AUSSCHLIESSLICH mit JSON.'
        ),
        'user_template': (
            '[[CONTEXT]]\n\nBriefing:\n[[BRIEFING]]\n\n'
            'Gib GENAU dieses JSON zurück:\n'
            '{"understood": true, "summary": "", "module_type_hint": "SECTION", '
            '"missing_topics": ["T1", "M1"]}'
        ),
        'instruction_default': '',
        'checklist_template': '',
    },
    {
        'key': 'wiz_email_module_clarify',
        'wizard_id': 'email_module',
        'phase': 'clarify',
        'name': 'Email-Modul: Klärung',
        'description': 'Klärfragen für Modul-Generator.',
        'app_scope': 'general',
        'system': 'Du hilfst bei Klärfragen für Email-Module. Antworte nur JSON wenn nötig.',
        'user_template': '[[CONTEXT]]\n\nBriefing:\n[[BRIEFING]]\n\nAntworten:\n[[ANSWERS]]',
        'instruction_default': '',
        'checklist_template': '',
    },
    {
        'key': 'wiz_email_module_suggest_meta',
        'wizard_id': 'email_module',
        'phase': 'suggest_meta',
        'name': 'Email-Modul: Metadaten',
        'description': 'Name, Identifier, module_type vorschlagen.',
        'app_scope': 'general',
        'system': (
            'Du schlägst Metadaten für ein ABpE Email-Modul vor. '
            'identifier: snake_case, eindeutig, z.B. abcona_header_blau_adresse. '
            'module_type aus ANSWERS.T1. status immer DRAFT. '
            'Antworte AUSSCHLIESSLICH mit JSON.'
        ),
        'user_template': (
            '[[CONTEXT]]\n\nBriefing:\n[[BRIEFING]]\n\nAntworten:\n[[ANSWERS]]\n\n'
            'Gib GENAU dieses JSON zurück:\n'
            '{"name": "", "identifier": "", "module_type": "SECTION", '
            '"description": "", "preview_bg": "#f8f9fa", "status": "DRAFT"}'
        ),
        'instruction_default': '',
        'checklist_template': 'identifier snake_case\nstatus DRAFT',
    },
    {
        'key': 'wiz_email_module_generate',
        'wizard_id': 'email_module',
        'phase': 'generate',
        'name': 'Email-Modul: HTML erzeugen',
        'description': 'Erzeugt html_body/text_body für ein Modul-Fragment.',
        'app_scope': 'general',
        'system': (
            'Du erstellst EIN ABpE Email-Modul (Fragment für {{block:identifier}}), '
            'keine komplette E-Mail. '
            'MCID: nur table/tr/td/a/span/p/br/strong/…; nur inline CSS; '
            'Arial; Marke #163258; Text #333333; Header-Titel 18px bold; '
            'Meta/Kontakt 12px; Body 14px; kein border-radius, kein flex/grid. '
            'Firmendaten NUR aus CONTEXT.catalog.company '
            '(www.abcona.de, 06171 886710, info@abcona.de) — nichts erfinden. '
            'Wenn ANSWERS.M1=extend: bestehenden HTML-Inhalt aus INSTRUCTION '
            'erhalten und nur die gewünschte Änderung einbauen. '
            'Kein {{block:…}} verschachteln, außer ausdrücklich verlangt. '
            'Antworte AUSSCHLIESSLICH mit JSON.'
        ),
        'user_template': (
            '[[CONTEXT]]\n\n'
            'Briefing:\n[[BRIEFING]]\n\nAntworten:\n[[ANSWERS]]\n\n'
            'Metadaten:\n[[META]]\n\n'
            '[[INSTRUCTION]]\n\n'
            'Gib GENAU dieses JSON zurück:\n'
            '{"html_body": "", "text_body": "", "name": "", "identifier": "", '
            '"module_type": "SECTION", "variables_used": []}'
        ),
        'instruction_default': '',
        'checklist_template': (
            'checklist[] aus CONTEXT einhalten\n'
            'Nur Modul-Fragment\n'
            'company facts nicht halluzinieren'
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
