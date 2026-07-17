from django.urls import path, include
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from . import views
from .api import ConsultantViewSet, CVViewSet, EmailViewSet
from .views_auth import login_view, logout_view, register_view
from django.contrib.auth import views as auth_views

app_name = 'abpe_ui'

# API Router
router = DefaultRouter()
router.register(r'consultants', ConsultantViewSet, basename='consultant')
router.register(r'cvs', CVViewSet, basename='cv')
router.register(r'emails', EmailViewSet, basename='email')

# ============================================================
# KOMPONENTEN-API (aus api/components/)
# ============================================================
from .api.components import stats, system, recent_consultants, recent_emails, badge_email, actions
from .api.components.available_languages import get_available_languages
from .api.components.set_language import set_language, get_language

urlpatterns = [
    # ============================================================
    # API ROUTEN (MÜSSEN GANZ OBEN STEHEN!)
    # ============================================================
    # REST API (DRF)
    path('api/', include(router.urls)),
    
    # SIMPLE JSON API
    path('api/stats/', views.api_stats, name='api_stats'),
    path('api/system/', views.api_system_status, name='api_system'),
    path('api/recent-consultants/', views.api_recent_consultants, name='api_recent_consultants'),
    path('api/recent-emails/', views.api_recent_emails, name='api_recent_emails'),
    path('api/set-language/', views.api_set_language, name='api_set_language'),
    path('api/user-settings/', views.api_user_settings, name='api_user_settings'),
    
    # KOMPONENTEN API
    path('api/components/stats/', stats.get_stats, name='api_component_stats'),
    path('api/components/system/', system.get_system_status, name='api_component_system'),
    path('api/components/recent-consultants/', recent_consultants.get_recent_consultants, name='api_component_recent_consultants'),
    path('api/components/recent-emails/', recent_emails.get_recent_emails, name='api_component_recent_emails'),
    path('api/components/actions/', actions.get_actions, name='api_component_actions'),
    path('api/components/badge/email/', badge_email.get_email_badge, name='api_component_badge_email'),
    path('api/available-languages/', get_available_languages, name='available_languages'),
    path('api/set-language/', set_language, name='set_language'),
    path('api/get-language/', get_language, name='get_language'),
    
    # SWAGGER/OPENAPI
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='abpe_ui:schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='abpe_ui:schema'), name='redoc'),
    
    # ============================================================
    # AUTH ROUTEN
    # ============================================================
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('register/', register_view, name='register'),
    
    path('password-reset/',
         auth_views.PasswordResetView.as_view(template_name='abpe_ui/registration/password_reset_form.html'),
         name='password_reset'),
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(template_name='abpe_ui/registration/password_reset_done.html'),
         name='password_reset_done'),
    
    # ============================================================
    # HILFE ROUTEN
    # ============================================================
    path('help/', views.help_page, name='help'),
    path('help/<str:topic>/', views.help_detail, name='help_detail'),
    
    # ============================================================
    # DOKUMENTATION
    # ============================================================
    path('docs/', views.documentation_page, {'subpage': 'architecture'}, name='docs'),
    path('docs/<str:subpage>/', views.documentation_page, name='docs_subpage'),
    
    # ============================================================
    # FRONTEND (MÜSSEN GANZ UNTEN STEHEN!)
    # ============================================================
    path('', views.dashboard, name='dashboard'),
    path('<str:module_id>/', views.module_view, name='module'),
    path('<str:module_id>/<str:subpage>/', views.module_view, name='module_subpage'),
]
