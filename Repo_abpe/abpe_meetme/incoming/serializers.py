from rest_framework import serializers
from .models import MeetmeMeeting, MeetmeGuest, MeetmeReminderRule, MeetmeReminderDelivery


class MeetmeGuestSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetmeGuest
        fields = [
            'id', 'meeting', 'contact_crm_id', 'name', 'email', 'phone',
            'status', 'is_active', 'invited_at',
            'last_notified_start_at', 'notified_cancelled',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class MeetmeReminderRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetmeReminderRule
        fields = [
            'id', 'meeting', 'guest', 'offset_value', 'offset_unit', 'time_of_day',
            'mode', 'send_copy_to_owner', 'template_id', 'subject', 'body', 'attachment_refs',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class MeetmeReminderDeliverySerializer(serializers.ModelSerializer):
    guest_name = serializers.CharField(source='guest.name', read_only=True)
    guest_email = serializers.EmailField(source='guest.email', read_only=True)

    class Meta:
        model = MeetmeReminderDelivery
        fields = [
            'id', 'rule', 'guest', 'guest_name', 'guest_email',
            'scheduled_at', 'status', 'subject', 'body',
            'sent_at', 'failed_reason', 'email_log_id', 'scheduler_job_id',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at', 'scheduler_job_id']


class MeetmeMeetingSerializer(serializers.ModelSerializer):
    guests = MeetmeGuestSerializer(many=True, read_only=True)
    reminder_rules = MeetmeReminderRuleSerializer(many=True, read_only=True)

    class Meta:
        model = MeetmeMeeting
        fields = [
            'id', 'title', 'description', 'start_at', 'duration_minutes',
            'room_extension', 'meetme_number', 'status', 'account_crm_id',
            'created_by', 'guests', 'reminder_rules', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']
