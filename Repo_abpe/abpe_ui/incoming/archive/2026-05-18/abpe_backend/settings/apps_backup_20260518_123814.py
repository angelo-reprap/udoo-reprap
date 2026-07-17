"""
ABPE_APPS Configuration
App Definitions - Only defines lists, does not extend INSTALLED_APPS
"""

# ABpE Apps
ABPE_APPS = [
    # Core ABpE
    'apps.abe_admin',
    'apps.abe_audit',
    'apps.abe_core',
    'apps.abe_matching',
    'apps.abpe_scheduler',
    'apps.abpe_identity',
    'apps.abpe_profile', 
    'apps.abpe_presort',
    'apps.abpe_intake',  

    # NEU: Matching Workflow
    'apps.abpe_matching_workflow',

    # CRM Bridge - SuiteCRM Integration
    'apps.crm_bridge',   

    # Intake & Processing
    'apps.ingest_custom',
    'apps.ingest_email',
    'apps.ingest_pdf',
    'apps.ingest_word',
    'apps.parser_word',
    'apps.ingest_csv',
    'apps.ingest_txt',
    'apps.ingest_url.apps.IngestUrlConfig',

    # Processing & AI
    'apps.cv_pipeline',
    'apps.cv_extractor',
    'apps.ai_cv_processor',
    'apps.ai_cv_training',
    'apps.normalizer',
    'apps.parser_html',
    'apps.parser_json',
    'apps.parser_pdf',

    # API & Integration
    'apps.api',
    'apps.auth_ldap',
    'apps.automail_engine',
    'apps.export_suitecrm',
    'apps.legacy_emma',

    # UI & Frontend
    'apps.builder_v5',
    'apps.dashboard',
    'apps.documentation',
    'apps.layout_manager',
    'apps.abpe_search',
    'apps.namazu', 
]

# Third Party Apps
THIRD_PARTY_APPS = [
    # ElasticSearch Integration
    'django_elasticsearch_dsl',
    'django_elasticsearch_dsl_drf',

    # REST & API
    'rest_framework',
    'rest_framework.authtoken',
    'django_filters',
    'corsheaders',
    'drf_spectacular',
    'drf_spectacular_sidecar',

    # Django Extensions - NEU
    'django_extensions', 

    # Django CMS
    'cms',
    'menus',
    'treebeard',
    'sekizai',
    'djangocms_admin_style',
    'djangocms_versioning',
    'djangocms_text_ckeditor',

    # File Management
    'filer',
    'easy_thumbnails',

    # CMS Plugins
    'djangocms_link',
    'djangocms_picture',
    'djangocms_video',
    'djangocms_snippet',
    'djangocms_style',

    # AI CV Prompt Management
    'apps.ai_cv_prompt',

    # 'apps.abpe_intranet_portal'  # ENTFERNT - existiert nicht
]

# Note: INSTALLED_APPS extension happens in __init__.py

# ABpE Portal App
ABPE_APPS += [
    'apps.abpe_portal',
]

ABPE_APPS += [
    'apps.abpe_ui',
]
