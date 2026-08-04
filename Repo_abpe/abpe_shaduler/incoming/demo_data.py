"""
Demo-Aufgaben für UI-V1 (solange Migration/DB noch leer).
Entspricht dem Final-Mockup — keine Persistenz.
"""


def demo_aufgaben():
    return [
        {
            'id': 'demo-1',
            'art': 'anruf',
            'titel': 'Nachfassen: Angebot #2481 — Hays (M. Weber)',
            'ref_type': 'anfrage',
            'ref_id': '2481',
            'ref_label': 'Anfrage #2481 · 3 Profile gesendet',
            'due_label': 'seit 31.07.',
            'ueberfaellig': True,
            'bucket': 'ueberfaellig',
            'action_label': 'Anrufen (Durchwahl 12)',
            'action_note': 'Click-to-dial — dein Telefon klingelt zuerst.',
            'excerpt': {
                'stand': 'Angebot mit 3 Profilen am 29.07. gesendet.',
                'hist': [
                    '01.08. Nachfass-Mail an Kunde',
                    '29.07. Angebot gesendet',
                    '27.07. Interesse aller 3 Berater',
                ],
            },
            'results': [
                {
                    'label': 'Angebot angenommen 🎉',
                    'sub': 'Kunde wählt einen Berater',
                    'fx': [
                        'Kanban: Berater → „Vermittelt"',
                        'Neue Aufgabe: Vertrag erstellen',
                        'Historie-Eintrag',
                    ],
                },
                {
                    'label': 'In Prüfung',
                    'sub': 'Wiedervorlage +3 Tage',
                    'fx': ['Status „in Prüfung"', 'Wiedervorlage', 'Historie'],
                },
                {
                    'label': 'Nicht erreicht',
                    'sub': 'Kaskade laut Regel',
                    'fx': ['Erneut anrufen morgen', 'Historie: Versuch 1'],
                },
                {
                    'label': 'Abgelehnt',
                    'sub': 'Grund erfassen',
                    'fx': ['Anfrage → „verloren"', 'Vorgang zu', 'Historie'],
                },
            ],
        },
        {
            'id': 'demo-3',
            'art': 'sms_messenger',
            'titel': 'Termin-Erinnerung an T. Lorenz',
            'ref_label': 'Interview morgen 10:00 · Bechtle',
            'due_label': 'heute 11:00',
            'ueberfaellig': False,
            'bucket': 'heute',
            'action_label': 'In WhatsApp öffnen',
            'action_note': 'Text vorbefüllt — nur Senden drücken.',
            'excerpt': {
                'stand': 'Erinnerung für Interview morgen 10:00 bei Bechtle.',
                'hist': [],
            },
            'results': [
                {'label': 'Wurde versendet ✓', 'sub': '', 'fx': ['Historie: WhatsApp']},
                {'label': 'Verworfen', 'sub': '', 'fx': ['geschlossen']},
            ],
        },
        {
            'id': 'demo-4',
            'art': 'wiedervorlage',
            'titel': 'Vertragseingang R. Simon prüfen',
            'ref_label': 'per Post 28.07. (+5 Tage)',
            'due_label': 'heute',
            'ueberfaellig': False,
            'bucket': 'heute',
            'action_label': 'Geprüft — entscheiden',
            'action_note': 'Reine Wiedervorlage.',
            'excerpt': {
                'stand': 'Vertrag am 28.07. per Post gesendet.',
                'hist': ['28.07. Postversand bestätigt'],
            },
            'results': [
                {
                    'label': 'Eingegangen ✓',
                    'sub': 'Vorgang zu',
                    'fx': ['„Vertrag eingegangen"', 'Vorgang abgeschlossen'],
                },
                {
                    'label': 'Nicht da — nachfassen',
                    'sub': 'erzeugt Anruf',
                    'fx': ['Anruf Vertragsklärung (heute)'],
                },
            ],
        },
        {
            'id': 'demo-5',
            'art': 'email',
            'titel': 'Absagen: 2 Berater (#2440)',
            'ref_label': 'Massenaktion · „Absage Berater"',
            'due_label': 'heute',
            'ueberfaellig': False,
            'bucket': 'heute',
            'action_label': 'Vorschau & senden',
            'action_note': 'Email Studio — alles vorbefüllt.',
            'excerpt': {
                'stand': '#2440 vermittelt — 2 Absagen offen.',
                'hist': ['01.08. Roth vermittelt'],
            },
            'results': [
                {
                    'label': 'Gesendet ✓',
                    'sub': '',
                    'fx': ['2× gesendet', 'beide → „Absage"', 'Vorgänge zu'],
                },
            ],
        },
        {
            'id': 'demo-7',
            'art': 'intern',
            'titel': 'Druckerkartuschen bestellen',
            'ref_label': 'Intern · Büro',
            'due_label': 'heute',
            'ueberfaellig': False,
            'bucket': 'heute',
            'action_label': 'Erledigen',
            'action_note': '',
            'excerpt': {'stand': 'Schwarz + Cyan fast leer.', 'hist': []},
            'results': [
                {'label': 'Erledigt ✓', 'sub': '', 'fx': ['Historie (Intern)']},
            ],
        },
        {
            'id': 'demo-8',
            'art': 'intern',
            'titel': 'Werkstatttermin Fuhrpark',
            'ref_label': 'Intern · Inspektion',
            'due_label': '05.08. 09:30',
            'ueberfaellig': False,
            'bucket': 'geplant',
            'action_label': 'Erledigen',
            'action_note': '',
            'excerpt': {'stand': 'Inspektion geplant.', 'hist': []},
            'results': [
                {'label': 'Erledigt ✓', 'sub': '', 'fx': ['Historie']},
            ],
        },
        {
            'id': 'demo-6',
            'art': 'wiedervorlage',
            'titel': 'Bestandspflege: Fa. Bechtle',
            'ref_label': 'Rahmenvertrag ansprechen',
            'due_label': '10.08.',
            'ueberfaellig': False,
            'bucket': 'geplant',
            'action_label': 'Erledigen',
            'action_note': '',
            'excerpt': {'stand': 'Rahmenvertrag ansprechen.', 'hist': []},
            'results': [
                {'label': 'Erledigt ✓', 'sub': '', 'fx': ['Historie']},
            ],
        },
    ]


def demo_stats(tasks=None):
    tasks = tasks if tasks is not None else demo_aufgaben()
    heute = sum(1 for t in tasks if t.get('bucket') == 'heute')
    ov = sum(1 for t in tasks if t.get('ueberfaellig'))
    geplant = sum(1 for t in tasks if t.get('bucket') == 'geplant')
    return {
        'heute': heute,
        'ueberfaellig': ov,
        'geplant': geplant,
        'erledigt_heute': 0,
        'badges': {
            'aufgaben': heute + ov,
            'posteingang': 0,
            'radar_anfragen': 0,
            'radar_berater': 0,
        },
        'demo': True,
    }
