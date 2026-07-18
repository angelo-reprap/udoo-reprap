"""DRF Serializers für abpe_ki_wiz — drf-spectacular OpenAPI."""
from __future__ import annotations

from rest_framework import serializers


class ErrorSerializer(serializers.Serializer):
    error = serializers.CharField()


class HealthResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    service = serializers.CharField()
    phase = serializers.IntegerField()
    active_prompts = serializers.IntegerField()
    registered_wizards = serializers.IntegerField()
    public_wizards = serializers.IntegerField()


class WizardInfoSerializer(serializers.Serializer):
    wizard_id = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField()


class WizardListResponseSerializer(serializers.Serializer):
    wizards = WizardInfoSerializer(many=True)


class PromptInfoSerializer(serializers.Serializer):
    key = serializers.CharField()
    wizard_id = serializers.CharField()
    phase = serializers.CharField()
    name = serializers.CharField()
    app_scope = serializers.CharField()


class PromptListResponseSerializer(serializers.Serializer):
    prompts = PromptInfoSerializer(many=True)


class CatalogResponseSerializer(serializers.Serializer):
    wizard_id = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField()
    catalog = serializers.JSONField()
    questions = serializers.JSONField()


class SessionCreateRequestSerializer(serializers.Serializer):
    briefing = serializers.CharField(
        min_length=10,
        help_text='Freitext-Briefing (min. 10 Zeichen)',
    )


class SessionSerializer(serializers.Serializer):
    session_id = serializers.CharField()
    wizard_id = serializers.CharField()
    status = serializers.CharField()
    phase = serializers.CharField()
    briefing = serializers.CharField(required=False, allow_blank=True)
    answers = serializers.JSONField(required=False)
    meta_suggestions = serializers.JSONField(required=False)
    result = serializers.JSONField(required=False, allow_null=True)
    error_message = serializers.CharField(required=False, allow_blank=True)


class ClarifyRequestSerializer(serializers.Serializer):
    answers = serializers.JSONField(
        help_text='Antworten auf Klärfragen, z.B. {"S1":"telefon","S2":"invite"}',
    )


class MetaOverrideSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=True)
    identifier = serializers.CharField(required=False, allow_blank=True)
    subject = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    app_scope = serializers.CharField(required=False, allow_blank=True)
    event_type = serializers.CharField(required=False, allow_blank=True)
    sender_mode = serializers.CharField(required=False, allow_blank=True)
    signature_mode = serializers.CharField(required=False, allow_blank=True)
    status = serializers.CharField(required=False, allow_blank=True)


class GenerateRequestSerializer(serializers.Serializer):
    refinement = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='Verfeinerungs-Anweisung für Neu-Generierung',
    )
    meta = MetaOverrideSerializer(required=False)
    html_body = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='Aktueller HTML-Stand als Ausgangsbasis',
    )
    text_body = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='Aktueller Text-Stand als Ausgangsbasis',
    )


class GeneratedContentSerializer(serializers.Serializer):
    html_body = serializers.CharField(required=False, allow_blank=True)
    text_body = serializers.CharField(required=False, allow_blank=True)
    variables_used = serializers.JSONField(required=False)
    source = serializers.CharField(required=False, allow_blank=True)
    ai_error = serializers.CharField(required=False, allow_blank=True)


class AnalyzeResponseSerializer(SessionSerializer):
    analyze = serializers.JSONField(required=False)
    pending_question_ids = serializers.JSONField(required=False)
    questions = serializers.JSONField(required=False)


class ClarifyResponseSerializer(SessionSerializer):
    complete = serializers.BooleanField(required=False)
    pending_question_ids = serializers.JSONField(required=False)
    questions = serializers.JSONField(required=False)


class SuggestMetaResponseSerializer(SessionSerializer):
    suggestions = serializers.JSONField(required=False)


class GenerateResponseSerializer(SessionSerializer):
    generated = GeneratedContentSerializer(required=False)
    apply = serializers.JSONField(required=False)


class ApplyResponseSerializer(SessionSerializer):
    apply = serializers.JSONField(required=False)
