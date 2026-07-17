"""
URL configuration for automail_engine
"""
from django.urls import path
from . import api_views

urlpatterns = [
    # Email Search APIs
    path('api/email/search/', api_views.EmailSearchAPI.as_view(), name='email-search'),
    path('api/email/stats/', api_views.EmailStatsAPI.as_view(), name='email-stats'),
    path('api/email/timeline/', api_views.EmailTimelineAPI.as_view(), name='email-timeline'),
    path('api/email/timeline/<str:person_id>/', api_views.EmailTimelineAPI.as_view(), name='email-timeline-person'),
    path('api/email/reindex/', api_views.EmailReindexAPI.as_view(), name='email-reindex'),
    path('api/email/health/', api_views.EmailHealthAPI.as_view(), name='email-health'),
]
