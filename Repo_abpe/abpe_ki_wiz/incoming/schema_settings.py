"""drf-spectacular Einstellungen für /ki-wizard/api/schema/.

Hinweis: Keys mit Prefix ``SERVE_`` dürfen NICHT in custom_settings stehen
(drf-spectacular wirft AttributeError). Diese steuern wir am View:
``KiWizardSpectacularAPIView.serve_public = True``.
"""

KI_WIZARD_SPECTACULAR_SETTINGS = {
    'TITLE': 'ABpE KI Wizard API',
    'DESCRIPTION': (
        'Session-basierte KI-Assistenten (Email Studio, Matching, …). '
        'Authentifizierung: Django-Session-Cookie (eingeloggt im Portal). '
        'POST-Endpunkte erwarten `X-CSRFToken` bei Browser-Clients.'
    ),
    'VERSION': '1.0.0',
    'SCHEMA_PATH_PREFIX': '/ki-wizard/',
    'APPEND_COMPONENTS': {
        'securitySchemes': {
            'sessionAuth': {
                'type': 'apiKey',
                'in': 'cookie',
                'name': 'sessionid',
                'description': 'Django Session — im Portal eingeloggt sein',
            },
            'csrfToken': {
                'type': 'apiKey',
                'in': 'header',
                'name': 'X-CSRFToken',
                'description': 'CSRF-Token aus Cookie csrftoken (POST)',
            },
        },
    },
    'SECURITY': [{'sessionAuth': [], 'csrfToken': []}],
}
