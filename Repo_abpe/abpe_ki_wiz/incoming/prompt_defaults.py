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
            'CONTEXT.facts enthält verifizierte Firmen-, User- und CRM-Daten — diese NUTZEN, '
            'nicht erfinden. CRM: facts.contact.variables / facts.account.variables. '
            'Firmenfooter: {{block:signature}} mit signature_mode TEAM '
            'oder facts.company_abcona. User-Absender: {sender_name}, {sender_email}. '
            'Antworte AUSSCHLIESSLICH mit JSON. '
            'HTML: inline CSS, 600px Tabellen-Layout, Outlook-tauglich. '
            'Corporate-Layout (CI): zuerst Header-Modul {{block:abcona_header_blau|gruen|rot}}, '
            'dann Body-Text, dann Footer {{block:footer_standard}} oder {{block:signature}}. '
            'Header, Body und Footer linksbündig (text-align:left). '
            'Body und Footer gleiche Schrift (Arial 14px) und Farbe (#333333). '
            'CONTEXT.catalog.layout_rules beachten. '
            'Module NUR als {{block:identifier}} aus CONTEXT.catalog.modules. '
            'Variablen NUR als {name} aus CONTEXT.catalog.variables. '
            'Kein Markdown, kein erfundenes Datum, keine erfundene Adresse.'
        ),
        'user_template': (
            '[[CONTEXT]]\n\n'
            '(facts in CONTEXT — Firmendaten/User nicht halluzinieren)\n\n'
            'Briefing:\n[[BRIEFING]]\n\nAntworten:\n[[ANSWERS]]\n\n'
            'Metadaten:\n[[META]]\n\n'
            '[[INSTRUCTION]]\n\n'
            'Gib GENAU dieses JSON zurück:\n'
            '{"html_body": "", "text_body": "", "variables_used": []}'
        ),
        'instruction_default': '',
        'checklist_template': (
            'Alle checklist[] Punkte aus CONTEXT einhalten\n'
            'facts._rules beachten (Adressen/Firmendaten)\n'
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
    # ── Matching Neue Anfrage (E-Mail → Formular) ─────────────────────────────
    {
        'key': 'wiz_matching_anfrage_generate',
        'wizard_id': 'matching_anfrage',
        'phase': 'generate',
        'name': 'Matching Anfrage: E-Mail extrahieren',
        'description': (
            'Extrahiert Kunde, Ansprechpartner und Anfrage-Details aus E-Mail '
            'für Matching „Neue Anfrage“ (DeepSeek).'
        ),
        'app_scope': 'matching',
        'system': (
            'Du bist Extraktor für Matching-Anfragen (IT-/Freelance-Projekte, deutschsprachig).\n'
            'Aus einer E-Mail erzeugst du genau ein JSON-Objekt — kein Markdown, '
            'keine Erklärtexte außerhalb des JSON.\n'
            '\n'
            '## Aufgabe\n'
            'Lies Betreff, äußeren Absender und Mail-Body. Erkenne, ob die Mail eine Weiterleitung ist.\n'
            'Fülle das Schema unten nur mit Informationen, die im Text stehen oder sich daraus '
            'eindeutig ableiten lassen.\n'
            '\n'
            '## Verhaltensregeln\n'
            '1. Nichts erfinden: keine Daten, Sätze, Firmen- oder Personennamen, die nicht im Text vorkommen.\n'
            '2. Weiterleitungen (Kennzeichen u.a. WG:/AW:/Fwd:, eingebettete „Von:“/„Gesendet:“/„Betreff:“-Blöcke):\n'
            '   - Der äußere Absender ist typischerweise der Weiterleitende, nicht der Auftraggeber.\n'
            '   - Kunde und Ansprechpartner kommen aus dem ursprünglichen (inneren) Anfrage-Teil.\n'
            '   - Den Weiterleitenden nur unter „weiterleitung“ erfassen.\n'
            '3. Wenn im Text ein anonymer Endkunde erwähnt wird („unser Kunde …“), setze dessen '
            'Branchen-/Kontext-Hinweis nur unter „hinweise“ — nicht als kunde.name.\n'
            '4. Entferne aus der Beschreibung: Disclaimer, Legal-/Datenschutz-Footer, '
            'SMIME-/Anhang-Hinweise, reine Signatur-Boilerplates des Weiterleitenden.\n'
            '5. beschreibung: kompakter Anfragekern auf Deutsch (Rolle, Aufgaben, Qualifikationen). '
            'Rahmendaten (Start, Dauer, Ort) kurz mitnehmen, sofern genannt. Die strukturierten '
            'Felder bleiben trotzdem die Quelle für Formularwerte.\n'
            '6. start.asap = true bei Formulierungen wie asap / sofort / ab sofort. '
            'start.datum nur bei konkretem Kalenderdatum (YYYY-MM-DD), sonst null.\n'
            '7. dauer_monate als Zahl, wenn erkennbar (z.B. aus „3 MM“, „3 Monate“). '
            'Verlängerungsoptionen gehören in hinweise, nicht in die Zahl.\n'
            '8. stundensatz_max nur setzen, wenn klar ein Kunden- oder Projektbudget genannt ist. '
            'Wird der Stundensatz des Bewerbers erfragt → null.\n'
            '9. skills: 5–15 kurze, relevante Stichworte aus Anforderungen/Technologien/Rolle.\n'
            '10. confidence je Block zwischen 0.0 und 1.0 (wie sicher die Zuordnung ist).\n'
            '11. ansprechpartner.email und ansprechpartner.phone aus der Signatur des '
            'inneren Absenders (Zeilen E:/T:/Tel./Mail) — exakt übernehmen, nichts vertauschen.\n'
            '12. Signatur-Block (Name, Funktion, Firmenname, Adresse, T:/F:/E:): '
            'Name → ansprechpartner.name, Firmenzeile (z.B. „… AG“) → kunde.name, '
            'E: → ansprechpartner.email, T: → ansprechpartner.phone.\n'
            '13. kunde.name nicht leer lassen, wenn Firma in Signatur oder Betreff klar steht.\n'
            '14. Keine Verwechslung ähnlich klingender Namen — nur den Namen aus dem Anfrage-/Signaturtext.\n'
            '\n'
            '## Ausgabe-Schema (exakt diese Keys)\n'
            '{\n'
            '  "kunde": { "name": string|null, "email_domain": string|null, "confidence": number },\n'
            '  "ansprechpartner": { "name": string|null, "email": string|null, '
            '"phone": string|null, "confidence": number },\n'
            '  "weiterleitung": { "ja": boolean, "von": string|null, "email": string|null },\n'
            '  "titel": string|null,\n'
            '  "beschreibung": string|null,\n'
            '  "start": { "asap": boolean, "datum": string|null },\n'
            '  "dauer_monate": number|null,\n'
            '  "standort": string|null,\n'
            '  "remote": boolean|null,\n'
            '  "stundensatz_max": number|null,\n'
            '  "skills": string[],\n'
            '  "hinweise": string[]\n'
            '}'
        ),
        'user_template': (
            '[[BRIEFING]]\n\n'
            'Antworte NUR mit dem JSON-Objekt gemäß System-Schema.'
        ),
        'instruction_default': 'Nur JSON. Nichts erfinden. Weiterleitungen korrekt trennen.',
        'checklist_template': (
            'Nur Fakten aus dem Text\n'
            'Weiterleitung: Kunde/AP aus innerem Teil\n'
            'Kein Markdown außerhalb JSON'
        ),
    },
    # ── Firma Web Enrich (Matching / CRM) ─────────────────────────────────────
    {
        'key': 'wiz_firma_web_enrich',
        'wizard_id': 'firma_web',
        'phase': 'generate',
        'name': 'Firma: Web-Anreicherung',
        'description': (
            'Extrahiert Website, Adresse, Tel, E-Mail und Kurznotiz aus '
            'öffentlichen Firmen-Seiten (Impressum/About) — on-demand.'
        ),
        'app_scope': 'matching',
        'system': (
            'Du extrahierst Firmenstammdaten aus öffentlichen Webseiten '
            '(Impressum, About, Kontakt).\n'
            'Antworte AUSSCHLIESSLICH mit einem JSON-Objekt — kein Markdown.\n'
            'Keine Halluzinationen: nur was im Text oder im Regex-Hinweis steht.\n'
            'Unbekannt = null oder [].\n'
            'E-Mails/Telefone aus Seiteninhalt oder Regex-Hinweis übernehmen.\n'
            'contacts nur wenn klar als Person mit Rolle genannt '
            '(z.B. Geschäftsführer im Impressum) — nicht erfinden.\n'
            'summary_de: 2–4 Sätze Firmennotiz auf Deutsch, sachlich.\n'
            '\n'
            'Schema:\n'
            '{\n'
            '  "website": string|null,\n'
            '  "legal_name": string|null,\n'
            '  "street": string|null,\n'
            '  "zip": string|null,\n'
            '  "city": string|null,\n'
            '  "country": string|null,\n'
            '  "emails": string[],\n'
            '  "phones": string[],\n'
            '  "contacts": [{"name": "", "role": "", "email": null, "phone": null}],\n'
            '  "summary_de": string|null,\n'
            '  "sources": string[]\n'
            '}'
        ),
        'user_template': (
            '[[BRIEFING]]\n\n'
            'Antworte NUR mit dem JSON-Objekt gemäß System-Schema.'
        ),
        'instruction_default': 'Nur JSON. Nur öffentliche Fakten. Nichts erfinden.',
        'checklist_template': (
            'Impressum bevorzugen\n'
            'Regex-Hinweis nutzen wenn KI unsicher\n'
            'Kein Markdown'
        ),
    },
]
