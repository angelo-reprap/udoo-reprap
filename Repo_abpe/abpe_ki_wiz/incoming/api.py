"""
ABpE KI Wizard — REST API (DRF + drf-spectacular)
"""
from __future__ import annotations

import logging
import uuid

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import WizardPrompt, WizardSession
from .registry import WizardNotRegisteredError, get_provider, provider_info
from .serializers import (
    AnalyzeResponseSerializer,
    ApplyResponseSerializer,
    CatalogResponseSerializer,
    ClarifyRequestSerializer,
    ClarifyResponseSerializer,
    ErrorSerializer,
    GenerateRequestSerializer,
    GenerateResponseSerializer,
    HealthResponseSerializer,
    MatchingAnfrageExtractRequestSerializer,
    MatchingAnfrageExtractResponseSerializer,
    PromptListResponseSerializer,
    SessionCreateRequestSerializer,
    SessionSerializer,
    SuggestMetaResponseSerializer,
    WizardListResponseSerializer,
)
from .services.orchestrator import (
    analyze_session,
    apply_session,
    clarify_session,
    generate_session,
    suggest_meta_session,
)
from .services.matching_anfrage_extract import extract_matching_anfrage
from .services.session_store import create_session, get_session_for_user, session_to_dict

log = logging.getLogger('abpe_ki_wiz.api')

SESSION_ID_PARAM = OpenApiParameter(
    name='session_id',
    type=OpenApiTypes.UUID,
    location=OpenApiParameter.PATH,
    required=True,
    description='Wizard-Session UUID',
)
WIZARD_ID_PARAM = OpenApiParameter(
    name='wizard_id',
    type=OpenApiTypes.STR,
    location=OpenApiParameter.PATH,
    required=True,
    description='Wizard-ID, z.B. email_template',
)


class KiWizardHealthAPI(APIView):
    """GET /ki-wizard/api/health/ — ohne Login (Monitoring)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=['monitoring'],
        summary='Health Check',
        responses={200: HealthResponseSerializer},
        auth=[],
    )
    def get(self, request):
        prompt_count = WizardPrompt.objects.filter(aktiv=True).count()
        wizards = [
            w for w in provider_info()
            if not w.get('wizard_id', '').startswith('_')
        ]
        return Response({
            'status': 'ok',
            'service': 'abpe_ki_wiz',
            'phase': 1,
            'active_prompts': prompt_count,
            'registered_wizards': len(provider_info()),
            'public_wizards': len(wizards),
        })


@method_decorator(csrf_exempt, name='dispatch')
class KiWizardListAPI(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['wizards'],
        summary='Registrierte Wizard-Provider',
        responses={200: WizardListResponseSerializer, 401: ErrorSerializer},
    )
    def get(self, request):
        wizards = [
            w for w in provider_info()
            if not w.get('wizard_id', '').startswith('_')
        ]
        return Response({'wizards': wizards})


@method_decorator(csrf_exempt, name='dispatch')
class KiWizardCatalogAPI(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['wizards'],
        summary='Domain-Katalog (Variablen, Module, Fragen)',
        parameters=[WIZARD_ID_PARAM],
        responses={
            200: CatalogResponseSerializer,
            401: ErrorSerializer,
            404: ErrorSerializer,
            500: ErrorSerializer,
        },
    )
    def get(self, request, wizard_id):
        try:
            provider = get_provider(wizard_id)
        except WizardNotRegisteredError as exc:
            return Response({'error': str(exc)}, status=404)

        try:
            catalog = provider.get_catalog()
            questions = provider.get_question_catalog()
        except Exception as exc:
            log.exception('Katalog laden fehlgeschlagen: %s', wizard_id)
            return Response({'error': str(exc)}, status=500)

        return Response({
            'wizard_id': wizard_id,
            'title': provider.title,
            'description': provider.description,
            'catalog': catalog,
            'questions': questions,
        })


@method_decorator(csrf_exempt, name='dispatch')
class KiWizardPromptListAPI(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['wizards'],
        summary='Aktive WizardPrompts (DB)',
        parameters=[
            OpenApiParameter(
                name='wizard_id',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
            ),
        ],
        responses={200: PromptListResponseSerializer, 401: ErrorSerializer},
    )
    def get(self, request):
        wizard_id = request.GET.get('wizard_id', '').strip()
        qs = WizardPrompt.objects.filter(aktiv=True).order_by('wizard_id', 'phase', 'key')
        if wizard_id:
            qs = qs.filter(wizard_id=wizard_id)

        prompts = [{
            'key': p.key,
            'wizard_id': p.wizard_id,
            'phase': p.phase,
            'name': p.name,
            'app_scope': p.app_scope,
        } for p in qs]

        return Response({'prompts': prompts})


@method_decorator(csrf_exempt, name='dispatch')
class KiWizardSessionCreateAPI(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['session'],
        summary='Session starten',
        parameters=[WIZARD_ID_PARAM],
        request=SessionCreateRequestSerializer,
        responses={
            201: SessionSerializer,
            400: ErrorSerializer,
            401: ErrorSerializer,
            404: ErrorSerializer,
            500: ErrorSerializer,
        },
    )
    def post(self, request, wizard_id):
        serializer = SessionCreateRequestSerializer(data=request.data)
        if not serializer.is_valid():
            first_err = next(iter(serializer.errors.values()))[0]
            return Response({'error': str(first_err)}, status=400)

        briefing = serializer.validated_data['briefing'].strip()
        try:
            session = create_session(wizard_id, request.user, briefing)
        except WizardNotRegisteredError as exc:
            return Response({'error': str(exc)}, status=404)
        except Exception as exc:
            log.exception('Session create failed')
            return Response({'error': str(exc)}, status=500)

        return Response(session_to_dict(session), status=201)


@method_decorator(csrf_exempt, name='dispatch')
class KiWizardSessionDetailAPI(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['session'],
        summary='Session-Details',
        parameters=[SESSION_ID_PARAM],
        responses={200: SessionSerializer, 401: ErrorSerializer, 404: ErrorSerializer},
    )
    def get(self, request, session_id):
        try:
            sid = uuid.UUID(str(session_id))
            session = get_session_for_user(sid, request.user)
        except (ValueError, WizardSession.DoesNotExist):
            return Response({'error': 'Session nicht gefunden'}, status=404)
        return Response(session_to_dict(session))


@method_decorator(csrf_exempt, name='dispatch')
class KiWizardSessionAnalyzeAPI(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['session'],
        summary='Briefing analysieren',
        parameters=[SESSION_ID_PARAM],
        responses={
            200: AnalyzeResponseSerializer,
            401: ErrorSerializer,
            404: ErrorSerializer,
            500: ErrorSerializer,
        },
    )
    def post(self, request, session_id):
        try:
            sid = uuid.UUID(str(session_id))
            session = get_session_for_user(sid, request.user)
            result = analyze_session(session)
            return Response(result)
        except (ValueError, WizardSession.DoesNotExist):
            return Response({'error': 'Session nicht gefunden'}, status=404)
        except Exception as exc:
            log.exception('analyze failed')
            return Response({'error': str(exc)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class KiWizardSessionClarifyAPI(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['session'],
        summary='Klärfragen beantworten',
        parameters=[SESSION_ID_PARAM],
        request=ClarifyRequestSerializer,
        responses={
            200: ClarifyResponseSerializer,
            400: ErrorSerializer,
            401: ErrorSerializer,
            404: ErrorSerializer,
            500: ErrorSerializer,
        },
    )
    def post(self, request, session_id):
        serializer = ClarifyRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'error': 'answers muss ein Objekt sein'}, status=400)

        answers = serializer.validated_data['answers']
        if not isinstance(answers, dict):
            return Response({'error': 'answers muss ein Objekt sein'}, status=400)

        try:
            sid = uuid.UUID(str(session_id))
            session = get_session_for_user(sid, request.user)
            result = clarify_session(session, answers)
            return Response(result)
        except (ValueError, WizardSession.DoesNotExist):
            return Response({'error': 'Session nicht gefunden'}, status=404)
        except Exception as exc:
            log.exception('clarify failed')
            return Response({'error': str(exc)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class KiWizardSessionSuggestMetaAPI(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['session'],
        summary='Metadaten vorschlagen (Autofill)',
        parameters=[SESSION_ID_PARAM],
        responses={
            200: SuggestMetaResponseSerializer,
            401: ErrorSerializer,
            404: ErrorSerializer,
            500: ErrorSerializer,
        },
    )
    def post(self, request, session_id):
        try:
            sid = uuid.UUID(str(session_id))
            session = get_session_for_user(sid, request.user)
            result = suggest_meta_session(session)
            return Response(result)
        except (ValueError, WizardSession.DoesNotExist):
            return Response({'error': 'Session nicht gefunden'}, status=404)
        except Exception as exc:
            log.exception('suggest_meta failed')
            return Response({'error': str(exc)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class KiWizardSessionGenerateAPI(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['session'],
        summary='HTML + TXT generieren',
        parameters=[SESSION_ID_PARAM],
        request=GenerateRequestSerializer,
        responses={
            200: GenerateResponseSerializer,
            401: ErrorSerializer,
            404: ErrorSerializer,
            502: ErrorSerializer,
            500: ErrorSerializer,
        },
    )
    def post(self, request, session_id):
        try:
            sid = uuid.UUID(str(session_id))
            session = get_session_for_user(sid, request.user)
        except (ValueError, WizardSession.DoesNotExist):
            return Response({'error': 'Session nicht gefunden'}, status=404)

        serializer = GenerateRequestSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        meta_override = data.get('meta')
        if meta_override is not None and not isinstance(meta_override, dict):
            meta_override = None

        try:
            result = generate_session(
                session,
                refinement=(data.get('refinement') or '').strip(),
                meta_override=meta_override,
                html_body=(data.get('html_body') or '').strip(),
                text_body=(data.get('text_body') or '').strip(),
            )
            if result.get('error'):
                return Response(result, status=502)
            return Response(result)
        except Exception as exc:
            log.exception('generate failed')
            return Response({'error': str(exc)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class KiWizardSessionApplyAPI(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['session'],
        summary='Ergebnis anwenden / Session abschließen',
        parameters=[SESSION_ID_PARAM],
        responses={
            200: ApplyResponseSerializer,
            400: ErrorSerializer,
            401: ErrorSerializer,
            404: ErrorSerializer,
            500: ErrorSerializer,
        },
    )
    def post(self, request, session_id):
        try:
            sid = uuid.UUID(str(session_id))
            session = get_session_for_user(sid, request.user)
            result = apply_session(session)
            if result.get('error'):
                return Response(result, status=400)
            return Response(result)
        except (ValueError, WizardSession.DoesNotExist):
            return Response({'error': 'Session nicht gefunden'}, status=404)
        except Exception as exc:
            log.exception('apply failed')
            return Response({'error': str(exc)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class KiWizardMatchingAnfrageExtractAPI(APIView):
    """
    POST /ki-wizard/api/matching-anfrage/extract/
    E-Mail → Matching-Formularfelder (Prompt aus DB, DeepSeek).
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['matching'],
        summary='Matching-Anfrage aus E-Mail extrahieren',
        request=MatchingAnfrageExtractRequestSerializer,
        responses={
            200: MatchingAnfrageExtractResponseSerializer,
            400: ErrorSerializer,
            401: ErrorSerializer,
            502: MatchingAnfrageExtractResponseSerializer,
            500: ErrorSerializer,
        },
    )
    def post(self, request):
        serializer = MatchingAnfrageExtractRequestSerializer(data=request.data or {})
        if not serializer.is_valid():
            first = next(iter(serializer.errors.values()))
            msg = first[0] if isinstance(first, (list, tuple)) else first
            return Response({'error': str(msg)}, status=400)

        data = serializer.validated_data
        try:
            result = extract_matching_anfrage(
                data['email_text'],
                subject=(data.get('subject') or '').strip(),
                outer_from=(data.get('outer_from') or '').strip(),
            )
            if not result.get('success'):
                status = 502 if result.get('extract') else 400
                if 'Prompt' in (result.get('error') or ''):
                    status = 503
                return Response(result, status=status)
            return Response(result)
        except Exception as exc:
            log.exception('matching_anfrage extract failed')
            return Response({'error': str(exc)}, status=500)
