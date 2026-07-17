from rest_framework import serializers
from .models import SchedulerJob, SchedulerJobRun


class SchedulerJobRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchedulerJobRun
        fields = [
            'id', 'scheduled_for', 'started_at', 'finished_at',
            'status', 'attempt', 'leased_at', 'leased_until',
            'response_status', 'response_body', 'error_message',
        ]


class SchedulerJobSerializer(serializers.ModelSerializer):
    runs = SchedulerJobRunSerializer(many=True, read_only=True)

    class Meta:
        model = SchedulerJob
        fields = [
            'id', 'owner_app', 'owner_type', 'owner_ref', 'job_key',
            'schedule_type', 'run_at', 'rrule_string', 'dtstart', 'until', 'timezone',
            'next_run_at', 'delivery_mode', 'callback_url', 'payload',
            'lock_key', 'max_retries', 'retry_backoff_seconds',
            'status', 'created_at', 'updated_at', 'runs',
        ]
        read_only_fields = ['next_run_at', 'created_at', 'updated_at']
        extra_kwargs = {
            'job_key': {'required': False, 'allow_blank': True},
            'lock_key': {'required': False, 'allow_blank': True},
            'callback_url': {'required': False, 'allow_blank': True},
            'rrule_string': {'required': False, 'allow_blank': True},
        }

    def get_unique_together_validators(self):
        # Uniqueness wird bereits manuell in api_job_create (Upsert-Filter)
        # geprueft. Der von DRF automatisch generierte UniqueTogetherValidator
        # macht sonst alle beteiligten Felder (inkl. job_key) intern wieder
        # zur Pflicht, unabhaengig von den extra_kwargs oben.
        return []
