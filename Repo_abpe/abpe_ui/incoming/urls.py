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
from .api.components.language_manager import list_languages, available_languages, add_language, hide_language, show_language, resolve_language

urlpatterns = [
    # ============================================================
    # API ROUTEN (MÜSSEN GANZ OBEN STEHEN!)
    # ============================================================
    # REST API (DRF)
    path('api/', include(router.urls)),

    # SIMPLE JSON API
    path('api/stats/',                views.api_stats,                name='api_stats'),
    path('api/system/',               views.api_system_status,        name='api_system'),
    path('api/recent-consultants/',   views.api_recent_consultants,   name='api_recent_consultants'),
    path('api/recent-emails/',        views.api_recent_emails,        name='api_recent_emails'),
    path('api/user-settings/',        views.api_user_settings,        name='api_user_settings'),

    # KOMPONENTEN API
    path('api/components/stats/',               stats.get_stats,                          name='api_component_stats'),
    path('api/components/system/',              system.get_system_status,                 name='api_component_system'),
    path('api/components/recent-consultants/',  recent_consultants.get_recent_consultants, name='api_component_recent_consultants'),
    path('api/components/recent-emails/',       recent_emails.get_recent_emails,          name='api_component_recent_emails'),
    path('api/components/actions/',             actions.get_actions,                      name='api_component_actions'),
    path('api/components/badge/email/',         badge_email.get_email_badge,              name='api_component_badge_email'),

    # SPRACH-API
    path('api/available-languages/',    get_available_languages,  name='available_languages'),
    path('api/set-language/',           set_language,             name='set_language'),
    path('api/get-language/',           get_language,             name='get_language'),

    # SPRACHPAKET-MANAGER API
    path('api/languages/list/',         list_languages,           name='lang_list'),
    path('api/languages/available/',    available_languages,      name='lang_available'),
    path('api/languages/add/',          add_language,             name='lang_add'),
    path('api/languages/hide/',         hide_language,            name='lang_hide'),
    path('api/languages/show/',         show_language,            name='lang_show'),

    # SWAGGER/OPENAPI
    path('api/schema/',   SpectacularAPIView.as_view(),                               name='schema'),
    path('api/docs/',     SpectacularSwaggerView.as_view(url_name='abpe_ui:schema'),  name='swagger-ui'),
    path('api/redoc/',    SpectacularRedocView.as_view(url_name='abpe_ui:schema'),    name='redoc'),

    # ============================================================
    # AUTH ROUTEN
    # ============================================================
    path('login/',    login_view,    name='login'),
    path('logout/',   logout_view,   name='logout'),
    path('register/', register_view, name='register'),

    path('password-reset/',
         auth_views.PasswordResetView.as_view(template_name='abpe_ui/registration/password_reset_form.html'),
         name='password_reset'),
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(template_name='abpe_ui/registration/password_reset_done.html'),
         name='password_reset_done'),
    path('password-reset/confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(template_name='abpe_ui/registration/password_reset_confirm.html'),
         name='password_reset_confirm'),
    path('password-reset/complete/',
         auth_views.PasswordResetCompleteView.as_view(template_name='abpe_ui/registration/password_reset_complete.html'),
         name='password_reset_complete'),

    # ============================================================
    # HILFE ROUTEN
    # ============================================================
    path('help/',              views.help_page,         name='help'),
    path('help/<str:topic>/',  views.help_detail,       name='help_detail'),

    # ============================================================
    # DOKUMENTATION
    # ============================================================
    path('docs/',              views.documentation_page, {'subpage': 'architecture'}, name='docs'),
    path('docs/<str:subpage>/', views.documentation_page,                             name='docs_subpage'),

    # ============================================================
    # ADMIN PORTAL API
    # ============================================================
    path('api/admin-portal/stats/',                                   views.api_admin_stats,                      name='api_admin_stats'),
    path('api/admin-portal/users/',                                   views.api_admin_users,                      name='api_admin_users'),
    path('api/admin-portal/users/<int:uid>/',                         views.api_admin_user_detail,                name='api_admin_user_detail'),
    path('api/admin-portal/users/<int:uid>/toggle/',                  views.api_admin_user_toggle,                name='api_admin_user_toggle'),
    path('api/admin-portal/groups/',                                  views.api_admin_groups,                     name='api_admin_groups'),
    path('api/admin-portal/modules/',                                 views.api_admin_modules,                    name='api_admin_modules'),
    path('api/admin-portal/modules/<str:mid>/',                       views.api_admin_module_update,              name='api_admin_module_update'),
    path('api/admin-portal/backups/',                                 views.api_admin_backups,                    name='api_admin_backups'),
    path('api/admin-portal/audit-log/',                               views.api_admin_audit_log,                  name='api_admin_audit_log'),
    path('api/admin-portal/users/<int:uid>/module-permissions/',      views.api_admin_user_module_permissions,    name='api_admin_user_module_permissions'),
    path('api/admin-portal/groups/<int:gid>/module-permissions/',     views.api_admin_group_module_permissions,   name='api_admin_group_module_permissions'),

    # ============================================================
    # ============================================================
    # NAMAZU API (Portal-seitig)
    # ============================================================
    path('api/email/view/',       views.api_email_view,     name='api_email_view'),
    path('api/es/search/',        views.api_es_search,      name='api_es_search'),
    path('api/namazu/accounts/',        views.api_namazu_accounts,        name='api_namazu_accounts'),
    path('api/namazu/accounts/update/', views.api_namazu_accounts_update, name='api_namazu_accounts_update'),
    path('api/namazu/search/',   views.api_namazu_search,  name='api_namazu_search'),
    path('api/namazu/status/',   views.api_namazu_status,  name='api_namazu_status'),
    path('api/namazu/reindex/',  views.api_namazu_reindex, name='api_namazu_reindex'),
    path('api/namazu/profile/',  views.api_namazu_profile, name='api_namazu_profile'),

    # FRONTEND (MÜSSEN GANZ UNTEN STEHEN!)
    # ============================================================
    path('cv_editor/',                                    views.cv_editor_view,              name='cv_editor'),
    path('api/cv-editor/consultant/<str:aid>/',           views.api_cv_editor_consultant,    name='api_cv_editor_consultant'),
    path('',                                              views.dashboard,                   name='dashboard'),
    path('<str:module_id>/',                              views.module_view,                 name='module'),
    path('<str:module_id>/<str:subpage>/',                views.module_view,                 name='module_subpage'),
]
