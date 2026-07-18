"""Phase 0/1: JSON-Index + OpenAPI/Swagger UI."""
from django.http import HttpResponse, JsonResponse
from django.views import View

from .openapi_schema import build_openapi_schema

SWAGGER_UI_HTML = """<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ABpE KI Wizard — API Docs</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui.css">
  <style>
    html { box-sizing: border-box; overflow-y: scroll; }
    *, *:before, *:after { box-sizing: inherit; }
    body { margin: 0; background: #fafafa; }
  </style>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-bundle.js"></script>
  <script src="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-standalone-preset.js"></script>
  <script>
    window.onload = function() {
      SwaggerUIBundle({
        url: "{schema_url}",
        dom_id: '#swagger-ui',
        deepLinking: true,
        presets: [SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset],
        layout: "StandaloneLayout",
        persistAuthorization: true,
        tryItOutEnabled: true,
      });
    };
  </script>
</body>
</html>
"""


class KiWizardIndexView(View):
    """GET /ki-wizard/ — Kurzinfo."""

    def get(self, request):
        return JsonResponse({
            'service': 'abpe_ki_wiz',
            'phase': 1,
            'api': {
                'health': '/ki-wizard/api/health/',
                'schema': '/ki-wizard/api/schema/',
                'docs': '/ki-wizard/api/docs/',
                'wizards': '/ki-wizard/api/wizards/',
                'prompts': '/ki-wizard/api/prompts/',
                'session_create': '/ki-wizard/api/wizards/<wizard_id>/session/',
                'session': '/ki-wizard/api/session/<uuid>/',
                'session_analyze': '/ki-wizard/api/session/<uuid>/analyze/',
                'session_clarify': '/ki-wizard/api/session/<uuid>/clarify/',
                'session_suggest_meta': '/ki-wizard/api/session/<uuid>/suggest-meta/',
                'session_generate': '/ki-wizard/api/session/<uuid>/generate/',
                'session_apply': '/ki-wizard/api/session/<uuid>/apply/',
            },
            'openapi': '3.0.3',
            'swagger_ui': '/ki-wizard/api/docs/',
            'admin': '/admin/abpe_ki_wiz/',
        })


class KiWizardOpenAPISchemaView(View):
    """GET /ki-wizard/api/schema/ — OpenAPI 3.0 JSON."""

    def get(self, request):
        base = request.build_absolute_uri('/ki-wizard/')
        schema = build_openapi_schema(base_url=base)
        return JsonResponse(schema)


class KiWizardSwaggerUIView(View):
    """GET /ki-wizard/api/docs/ — Swagger UI (OpenAPI)."""

    def get(self, request):
        schema_url = request.build_absolute_uri('/ki-wizard/api/schema/')
        html = SWAGGER_UI_HTML.format(schema_url=schema_url)
        return HttpResponse(html, content_type='text/html; charset=utf-8')
