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
            'is_new': False,
            'day': 1,
            'zeit': None,
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
            'is_new': True,
            'day': 3,
            'zeit': '11:00',
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
            'day': 3,
            'zeit': None,
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
            'day': 3,
            'zeit': None,
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
            'day': 3,
            'zeit': None,
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
            'day': 5,
            'zeit': '09:30',
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
            'day': 10,
            'zeit': None,
            'action_label': 'Erledigen',
            'action_note': '',
            'excerpt': {'stand': 'Rahmenvertrag ansprechen.', 'hist': []},
            'results': [
                {'label': 'Erledigt ✓', 'sub': '', 'fx': ['Historie']},
            ],
        },
    ]


def demo_inbox():
    return [
        {
            'id': 'mail-1',
            'unread': True,
            'box': 'vertrieb@',
            'from': 'K. Brandt',
            'crm': 'Berater · Anfrage #2477',
            'subj': 'Re: Projektanfrage Java Backend — Rückfrage zum Satz',
            'age': '07:41',
            'prev': 'Guten Morgen, beim genannten Rahmen hätte ich eine Frage zur Remote-Regelung …',
        },
        {
            'id': 'mail-2',
            'unread': True,
            'box': 'vertrieb@',
            'from': 'M. Weber (Hays AG)',
            'crm': 'Ansprechpartner · Anfrage #2481',
            'subj': 'AW: Angebot — interne Abstimmung heute',
            'age': '07:12',
            'prev': '…wir stimmen uns heute Vormittag intern ab und melden uns bis Mittag.',
        },
        {
            'id': 'mail-3',
            'unread': False,
            'box': 'angelo@',
            'from': 'freelancermap',
            'crm': '—',
            'subj': '5 neue Projekte für Ihre Suche „SAP Berater"',
            'age': 'gestern 22:03',
            'prev': 'Ihre gespeicherte Suche hat neue Treffer … (läuft parallel bereits in den Radar)',
        },
    ]


def demo_radar_anfragen():
    return [
        {
            'id': 'ra-1',
            'score': 87,
            'headline': 'SAP S/4HANA Migration — Senior Consultant (m/w/d)',
            'sources': ['freelancermap', 'GULP', 'XING'],
            'grp': 3,
            'age': 'vor 4 Min',
            'meta': 'Start 01.10. · 8 Monate · Stuttgart/Remote · bis 105 €/h',
            'top': ['S. Krüger 94%', 'M. Hoffmann 89%', 'A. Weber 85%'],
        },
        {
            'id': 'ra-2',
            'score': 74,
            'headline': 'Java Backend Entwickler — Zahlungsverkehr',
            'sources': ['freelancermap'],
            'grp': 1,
            'age': 'vor 18 Min',
            'meta': 'Start asap · 6 Monate · Frankfurt · Satz n/a',
            'top': ['K. Brandt 91%', 'T. Lorenz 78%'],
        },
        {
            'id': 'ra-3',
            'score': 62,
            'headline': 'DevOps Engineer AWS/K8s — Logistikplattform',
            'sources': ['GULP', 'XING'],
            'grp': 2,
            'age': 'vor 41 Min',
            'meta': 'Start 15.09. · 12 Monate · Remote',
            'top': ['R. Simon 81%'],
        },
    ]


def demo_radar_berater():
    return [
        {
            'id': 'rb-1',
            'match_status': 'bekannt',
            'st': 'known',
            'name': 'M. Hoffmann',
            'meta': 'SAP FI/CO · Ludwigsburg · 98 €/h · verfügbar ab 01.09.',
            'src': 'freelancermap',
            'note': 'Auto-Update: verfügbar_ab + Satz am Profil aktualisiert (Quelle: fm, heute)',
        },
        {
            'id': 'rb-2',
            'match_status': 'unsicher',
            'st': 'maybe',
            'name': 'Anonymes Profil #4471',
            'meta': 'Java/Spring · Raum Frankfurt · 92 €/h · ab sofort',
            'src': 'freelancermap',
            'note': 'Vermutlich: K. Brandt (Skills+Ort+Satz 88% ähnlich)',
        },
        {
            'id': 'rb-3',
            'match_status': 'unbekannt',
            'st': 'new',
            'name': 'Anonymes Profil #4519',
            'meta': 'Rust/Embedded · München · 110 €/h · ab 01.11.',
            'src': 'Talentfinder (eingefügt)',
            'note': 'Nicht im Bestand — beobachten oder Kontakt über Börse',
        },
    ]


def demo_stats(tasks=None):
    tasks = tasks if tasks is not None else demo_aufgaben()
    heute = sum(1 for t in tasks if t.get('bucket') == 'heute')
    ov = sum(1 for t in tasks if t.get('ueberfaellig'))
    geplant = sum(1 for t in tasks if t.get('bucket') == 'geplant')
    inbox = demo_inbox()
    ra = demo_radar_anfragen()
    rb = demo_radar_berater()
    return {
        'heute': heute,
        'ueberfaellig': ov,
        'geplant': geplant,
        'erledigt_heute': 0,
        'badges': {
            'aufgaben': heute + ov,
            'posteingang': sum(1 for m in inbox if m.get('unread')),
            'radar_anfragen': len(ra),
            'radar_berater': len(rb),
        },
        'demo': True,
    }
