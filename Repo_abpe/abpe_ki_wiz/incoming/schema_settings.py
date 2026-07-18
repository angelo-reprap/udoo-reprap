"""drf-spectacular Einstellungen für /ki-wizard/api/schema/."""

KI_WIZARD_SPECTACULAR_SETTINGS = {
    'TITLE': 'ABpE KI Wizard API',
    'DESCRIPTION': (
        'Session-basierte KI-Assistenten (Email Studio, Matching, …). '
        'Authentifizierung: Django-Session-Cookie (eingeloggt im Portal). '
        'POST-Endpunkte erwarten `X-CSRFToken` bei Browser-Clients.'
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SCHEMA_PATH_PREFIX': r'/ki-wizard',
    'TAGS': [
        {'name': 'monitoring', 'description': 'Health & Discovery'},
        {'name': 'wizards', 'description': 'Provider, Katalog, Prompts'},
        {'name': 'session', 'description': 'Wizard-Session Pipeline'},
    ],
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
    'SECURITY': [{'sessionAuth': []}, {'csrfToken': []}],
}
