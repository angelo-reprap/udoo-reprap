"""
OpenAPI 3.0 Schema für abpe_ki_wiz REST API.

Handgeschriebenes Schema — Swagger/ReDoc UI via drf-spectacular
(SpectacularSwaggerView → /ki-wizard/api/schema/).
"""
from __future__ import annotations

from typing import Any


def build_openapi_schema(*, base_url: str = '/ki-wizard/') -> dict[str, Any]:
    """OpenAPI 3.0 Dokument (JSON)."""
    base = base_url.rstrip('/')
    api = f'{base}/api'

    return {
        'openapi': '3.0.3',
        'info': {
            'title': 'ABpE KI Wizard API',
            'description': (
                'Session-basierte KI-Assistenten (Email Studio, Matching, …). '
                'Authentifizierung: Django-Session-Cookie (eingeloggt im Portal). '
                'POST-Endpunkte erwarten `X-CSRFToken` bei Browser-Clients.'
            ),
            'version': '1.0.0',
            'contact': {'name': 'ABpE', 'url': 'https://abpe.win.abcona.info/'},
        },
        'servers': [{'url': base, 'description': 'KI Wizard Base'}],
        'tags': [
            {'name': 'monitoring', 'description': 'Health & Discovery'},
            {'name': 'wizards', 'description': 'Provider, Katalog, Prompts'},
            {'name': 'session', 'description': 'Wizard-Session Pipeline'},
        ],
        'paths': {
            f'{api}/health/': {
                'get': {
                    'tags': ['monitoring'],
                    'summary': 'Health Check',
                    'operationId': 'kiWizardHealth',
                    'security': [],
                    'responses': {
                        '200': {
                            'description': 'Service OK',
                            'content': {
                                'application/json': {
                                    'schema': {'$ref': '#/components/schemas/HealthResponse'},
                                },
                            },
                        },
                    },
                },
            },
            f'{api}/wizards/': {
                'get': {
                    'tags': ['wizards'],
                    'summary': 'Registrierte Wizard-Provider',
                    'operationId': 'kiWizardList',
                    'responses': {
                        '200': {
                            'description': 'Wizard-Liste',
                            'content': {
                                'application/json': {
                                    'schema': {'$ref': '#/components/schemas/WizardListResponse'},
                                },
                            },
                        },
                        '401': {'$ref': '#/components/responses/Unauthorized'},
                    },
                },
            },
            f'{api}/wizards/{{wizard_id}}/catalog/': {
                'get': {
                    'tags': ['wizards'],
                    'summary': 'Domain-Katalog (Variablen, Module, Fragen)',
                    'operationId': 'kiWizardCatalog',
                    'parameters': [_param('wizard_id', 'Wizard-ID, z.B. email_template')],
                    'responses': {
                        '200': {'description': 'Katalog'},
                        '404': {'$ref': '#/components/responses/NotFound'},
                        '401': {'$ref': '#/components/responses/Unauthorized'},
                    },
                },
            },
            f'{api}/prompts/': {
                'get': {
                    'tags': ['wizards'],
                    'summary': 'Aktive WizardPrompts (DB)',
                    'operationId': 'kiWizardPromptList',
                    'parameters': [
                        {
                            'name': 'wizard_id',
                            'in': 'query',
                            'required': False,
                            'schema': {'type': 'string'},
                        },
                    ],
                    'responses': {
                        '200': {'description': 'Prompt-Liste'},
                        '401': {'$ref': '#/components/responses/Unauthorized'},
                    },
                },
            },
            f'{api}/wizards/{{wizard_id}}/session/': {
                'post': {
                    'tags': ['session'],
                    'summary': 'Session starten',
                    'operationId': 'kiWizardSessionCreate',
                    'parameters': [_param('wizard_id')],
                    'requestBody': {
                        'required': True,
                        'content': {
                            'application/json': {
                                'schema': {'$ref': '#/components/schemas/SessionCreateRequest'},
                            },
                        },
                    },
                    'responses': {
                        '201': {
                            'description': 'Session angelegt',
                            'content': {
                                'application/json': {
                                    'schema': {'$ref': '#/components/schemas/Session'},
                                },
                            },
                        },
                        '400': {'$ref': '#/components/responses/BadRequest'},
                        '404': {'$ref': '#/components/responses/NotFound'},
                        '401': {'$ref': '#/components/responses/Unauthorized'},
                    },
                },
            },
            f'{api}/session/{{session_id}}/': {
                'get': {
                    'tags': ['session'],
                    'summary': 'Session-Details',
                    'operationId': 'kiWizardSessionDetail',
                    'parameters': [_param_uuid('session_id')],
                    'responses': {
                        '200': {
                            'description': 'Session',
                            'content': {
                                'application/json': {
                                    'schema': {'$ref': '#/components/schemas/Session'},
                                },
                            },
                        },
                        '404': {'$ref': '#/components/responses/NotFound'},
                        '401': {'$ref': '#/components/responses/Unauthorized'},
                    },
                },
            },
            f'{api}/session/{{session_id}}/analyze/': {
                'post': {
                    'tags': ['session'],
                    'summary': 'Briefing analysieren',
                    'operationId': 'kiWizardSessionAnalyze',
                    'parameters': [_param_uuid('session_id')],
                    'responses': {
                        '200': {'description': 'Analyze-Ergebnis + offene Fragen'},
                        '404': {'$ref': '#/components/responses/NotFound'},
                        '401': {'$ref': '#/components/responses/Unauthorized'},
                    },
                },
            },
            f'{api}/session/{{session_id}}/clarify/': {
                'post': {
                    'tags': ['session'],
                    'summary': 'Klärfragen beantworten',
                    'operationId': 'kiWizardSessionClarify',
                    'parameters': [_param_uuid('session_id')],
                    'requestBody': {
                        'required': True,
                        'content': {
                            'application/json': {
                                'schema': {'$ref': '#/components/schemas/ClarifyRequest'},
                            },
                        },
                    },
                    'responses': {
                        '200': {'description': 'complete=true wenn alle Pflichtfragen beantwortet'},
                        '400': {'$ref': '#/components/responses/BadRequest'},
                        '404': {'$ref': '#/components/responses/NotFound'},
                        '401': {'$ref': '#/components/responses/Unauthorized'},
                    },
                },
            },
            f'{api}/session/{{session_id}}/suggest-meta/': {
                'post': {
                    'tags': ['session'],
                    'summary': 'Metadaten vorschlagen (Autofill)',
                    'operationId': 'kiWizardSessionSuggestMeta',
                    'parameters': [_param_uuid('session_id')],
                    'responses': {
                        '200': {'description': 'Metadaten-Vorschläge'},
                        '404': {'$ref': '#/components/responses/NotFound'},
                        '401': {'$ref': '#/components/responses/Unauthorized'},
                    },
                },
            },
            f'{api}/session/{{session_id}}/generate/': {
                'post': {
                    'tags': ['session'],
                    'summary': 'HTML + TXT generieren',
                    'operationId': 'kiWizardSessionGenerate',
                    'parameters': [_param_uuid('session_id')],
                    'requestBody': {
                        'required': False,
                        'content': {
                            'application/json': {
                                'schema': {'$ref': '#/components/schemas/GenerateRequest'},
                            },
                        },
                    },
                    'responses': {
                        '200': {'description': 'Generiertes Ergebnis'},
                        '502': {'description': 'DeepSeek / Generate fehlgeschlagen'},
                        '404': {'$ref': '#/components/responses/NotFound'},
                        '401': {'$ref': '#/components/responses/Unauthorized'},
                    },
                },
            },
            f'{api}/session/{{session_id}}/apply/': {
                'post': {
                    'tags': ['session'],
                    'summary': 'Ergebnis anwenden / Session abschließen',
                    'operationId': 'kiWizardSessionApply',
                    'parameters': [_param_uuid('session_id')],
                    'responses': {
                        '200': {'description': 'Apply-Payload für Ziel-UI'},
                        '400': {'description': 'Kein Ergebnis vorhanden'},
                        '404': {'$ref': '#/components/responses/NotFound'},
                        '401': {'$ref': '#/components/responses/Unauthorized'},
                    },
                },
            },
        },
        'components': {
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
            'schemas': {
                'HealthResponse': {
                    'type': 'object',
                    'properties': {
                        'status': {'type': 'string', 'example': 'ok'},
                        'service': {'type': 'string', 'example': 'abpe_ki_wiz'},
                        'phase': {'type': 'integer', 'example': 1},
                        'active_prompts': {'type': 'integer'},
                        'registered_wizards': {'type': 'integer'},
                        'public_wizards': {'type': 'integer'},
                    },
                },
                'WizardListResponse': {
                    'type': 'object',
                    'properties': {
                        'wizards': {
                            'type': 'array',
                            'items': {'$ref': '#/components/schemas/WizardInfo'},
                        },
                    },
                },
                'WizardInfo': {
                    'type': 'object',
                    'properties': {
                        'wizard_id': {'type': 'string', 'example': 'email_template'},
                        'title': {'type': 'string'},
                        'description': {'type': 'string'},
                    },
                },
                'SessionCreateRequest': {
                    'type': 'object',
                    'required': ['briefing'],
                    'properties': {
                        'briefing': {
                            'type': 'string',
                            'minLength': 10,
                            'example': 'MeetMe Einladung zur Telefon-Abstimmung',
                        },
                    },
                },
                'ClarifyRequest': {
                    'type': 'object',
                    'required': ['answers'],
                    'properties': {
                        'answers': {
                            'type': 'object',
                            'additionalProperties': True,
                            'example': {
                                'S1': 'telefon',
                                'S2': 'invite',
                                'I1': 'bullet_list',
                                'G1': 'USER',
                                'A1': 'USER',
                            },
                        },
                    },
                },
                'GenerateRequest': {
                    'type': 'object',
                    'properties': {
                        'refinement': {
                            'type': 'string',
                            'description': 'Optional: Verfeinerungs-Anweisung für Neu-Generierung',
                            'example': 'Kürzerer Text, kein Footer, Bibelzitat einfügen',
                        },
                        'meta': {
                            'type': 'object',
                            'description': 'Optional: Metadaten aus dem Modal (name, subject, …)',
                        },
                        'html_body': {
                            'type': 'string',
                            'description': 'Optional: aktueller HTML-Stand als Ausgangsbasis',
                        },
                        'text_body': {
                            'type': 'string',
                            'description': 'Optional: aktueller Text-Stand als Ausgangsbasis',
                        },
                    },
                },
                'Session': {
                    'type': 'object',
                    'properties': {
                        'session_id': {'type': 'string', 'format': 'uuid'},
                        'wizard_id': {'type': 'string'},
                        'status': {'type': 'string'},
                        'phase': {'type': 'string'},
                        'briefing': {'type': 'string'},
                        'answers': {'type': 'object'},
                        'meta_suggestions': {'type': 'object'},
                        'result': {'type': 'object'},
                    },
                },
                'Error': {
                    'type': 'object',
                    'properties': {'error': {'type': 'string'}},
                },
            },
            'responses': {
                'Unauthorized': {
                    'description': 'Nicht eingeloggt',
                    'content': {
                        'application/json': {
                            'schema': {'$ref': '#/components/schemas/Error'},
                        },
                    },
                },
                'NotFound': {
                    'description': 'Nicht gefunden',
                    'content': {
                        'application/json': {
                            'schema': {'$ref': '#/components/schemas/Error'},
                        },
                    },
                },
                'BadRequest': {
                    'description': 'Ungültige Anfrage',
                    'content': {
                        'application/json': {
                            'schema': {'$ref': '#/components/schemas/Error'},
                        },
                    },
                },
            },
        },
        'security': [{'sessionAuth': []}, {'csrfToken': []}],
    }


def _param(name: str, description: str = '') -> dict[str, Any]:
    return {
        'name': name,
        'in': 'path',
        'required': True,
        'schema': {'type': 'string'},
        'description': description,
    }


def _param_uuid(name: str) -> dict[str, Any]:
    return {
        'name': name,
        'in': 'path',
        'required': True,
        'schema': {'type': 'string', 'format': 'uuid'},
    }
