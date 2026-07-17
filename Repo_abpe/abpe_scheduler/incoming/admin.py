from django.contrib import admin
from .models import SchedulerJob, SchedulerJobRun


class SchedulerJobRunInline(admin.TabularInline):
    model = SchedulerJobRun
    extra = 0
    fields = ['scheduled_for', 'status', 'attempt', 'started_at', 'finished_at', 'response_status']
    readonly_fields = fields
    can_delete = False
    ordering = ['-scheduled_for']


@admin.register(SchedulerJob)
class SchedulerJobAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'schedule_type', 'delivery_mode', 'status', 'next_run_at']
    list_filter = ['status', 'schedule_type', 'delivery_mode', 'owner_app']
    search_fields = ['owner_app', 'owner_type', 'owner_ref', 'job_key']
    inlines = [SchedulerJobRunInline]


@admin.register(SchedulerJobRun)
class SchedulerJobRunAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'status', 'attempt', 'started_at']
    list_filter = ['status']
