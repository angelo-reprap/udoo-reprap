"""
CRM User Timezone — Backend-Patch (live auf ucs5)

Feld: CrmUserSettings.timezone (default Europe/Berlin)
API:  GET/POST /crm/api/user-settings/  →  timezone

Anwenden:
  python Repo_abpe/abpe_crm/incoming/patches/apply_user_timezone.py
  cd /opt/abpe/backend && python manage.py makemigrations abpe_crm --name crmusersettings_timezone
  python manage.py migrate abpe_crm --noinput
"""

DEFAULT_TIMEZONE = "Europe/Berlin"
