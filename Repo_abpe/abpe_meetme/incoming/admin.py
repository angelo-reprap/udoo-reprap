from django.contrib import admin
from .models import MeetmeMeeting, MeetmeGuest, MeetmeReminderRule, MeetmeReminderDelivery


class MeetmeGuestInline(admin.TabularInline):
    model = MeetmeGuest
    extra = 0
    fields = ['name', 'email', 'phone', 'status', 'is_active']


class MeetmeReminderRuleInline(admin.TabularInline):
    model = MeetmeReminderRule
    extra = 0
    fields = ['offset_value', 'offset_unit', 'time_of_day', 'mode', 'send_copy_to_owner', 'template_id']


@admin.register(MeetmeMeeting)
class MeetmeMeetingAdmin(admin.ModelAdmin):
    list_display = ['title', 'start_at', 'duration_minutes', 'room_extension', 'status']
    list_filter = ['status', 'room_extension']
    search_fields = ['title', 'account_crm_id']
    inlines = [MeetmeGuestInline, MeetmeReminderRuleInline]


@admin.register(MeetmeGuest)
class MeetmeGuestAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'meeting', 'status', 'is_active']
    list_filter = ['status', 'is_active']
    search_fields = ['name', 'email', 'contact_crm_id']


@admin.register(MeetmeReminderRule)
class MeetmeReminderRuleAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'meeting', 'mode']
    list_filter = ['mode', 'offset_unit']


@admin.register(MeetmeReminderDelivery)
class MeetmeReminderDeliveryAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'scheduled_at', 'status', 'sent_at']
    list_filter = ['status']
    search_fields = ['guest__name', 'guest__email']
