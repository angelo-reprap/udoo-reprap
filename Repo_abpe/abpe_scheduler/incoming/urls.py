from django.urls import path
from . import views

app_name = 'abpe_scheduler'

urlpatterns = [
    path('api/jobs/', views.api_job_list, name='api_job_list'),
    path('api/jobs/create/', views.api_job_create, name='api_job_create'),
    path('api/jobs/due/', views.api_jobs_due, name='api_jobs_due'),
    path('api/jobs/<int:job_id>/', views.api_job_detail, name='api_job_detail'),
    path('api/jobs/<int:job_id>/update/', views.api_job_update, name='api_job_update'),
    path('api/jobs/<int:job_id>/cancel/', views.api_job_cancel, name='api_job_cancel'),
    path('api/jobs/<int:job_id>/run-now/', views.api_job_run_now, name='api_job_run_now'),
    path('api/jobs/<int:job_id>/complete/', views.api_job_complete, name='api_job_complete'),
    path('api/health/', views.api_health, name='api_health'),

]
