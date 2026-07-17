#!/usr/bin/env python3
"""
Idempotentes Patch-Script für CrmUserSettings.timezone + api_crm_user_settings.
Auf ucs5 ausführen (venv aktiv):

  python Repo_abpe/abpe_crm/incoming/patches/apply_user_timezone.py
  cd /opt/abpe/backend && python manage.py makemigrations abpe_crm --name crmusersettings_timezone
  python manage.py migrate abpe_crm --noinput
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(os.environ.get("ABPE_BACKEND", "/opt/abpe/backend"))
MODELS = BACKEND / "apps/abpe_crm/models.py"
VIEWS = BACKEND / "apps/abpe_crm/views.py"

THEME_LINE = "    theme           = models.CharField(max_length=10, default='light', verbose_name='Theme')"
TIMEZONE_FIELD = (
    "    theme           = models.CharField(max_length=10, default='light', verbose_name='Theme')\n"
    "    timezone        = models.CharField(max_length=64, default='Europe/Berlin', verbose_name='Zeitzone')"
)

POST_PATCH = "        if 'timezone'           in data: s.timezone          = data['timezone']\n"
GET_PATCH = "        'timezone':           s.timezone or 'Europe/Berlin',\n"


def patch_models() -> bool:
    text = MODELS.read_text(encoding="utf-8")
    if "timezone" in text and "CrmUserSettings" in text:
        # Feld schon vorhanden?
        if "timezone        = models.CharField" in text or "timezone = models.CharField" in text:
            print("OK: models.py — timezone bereits vorhanden")
            return False
    if THEME_LINE not in text:
        print("FEHLER: models.py — theme-Zeile in CrmUserSettings nicht gefunden", file=sys.stderr)
        sys.exit(1)
    MODELS.write_text(text.replace(THEME_LINE, TIMEZONE_FIELD, 1), encoding="utf-8")
    print("OK: models.py — timezone-Feld eingefügt")
    return True


def patch_views() -> bool:
    text = VIEWS.read_text(encoding="utf-8")
    changed = False
    if "'timezone'" not in text or POST_PATCH.strip() not in text:
        anchor = "        if 'theme'              in data: s.theme             = data['theme']\n"
        if anchor not in text:
            print("FEHLER: views.py — theme POST-Anchor nicht gefunden", file=sys.stderr)
            sys.exit(1)
        if POST_PATCH.strip() not in text:
            text = text.replace(anchor, anchor + POST_PATCH, 1)
            changed = True
            print("OK: views.py — timezone POST eingefügt")
        else:
            print("OK: views.py — timezone POST bereits vorhanden")
    else:
        print("OK: views.py — timezone POST bereits vorhanden")

    if GET_PATCH.strip() not in text:
        get_anchor = "        'theme':              s.theme,\n"
        if get_anchor not in text:
            print("FEHLER: views.py — theme GET-Anchor nicht gefunden", file=sys.stderr)
            sys.exit(1)
        text = text.replace(get_anchor, get_anchor + GET_PATCH, 1)
        changed = True
        print("OK: views.py — timezone GET eingefügt")
    else:
        print("OK: views.py — timezone GET bereits vorhanden")

    if changed:
        VIEWS.write_text(text, encoding="utf-8")
    return changed


def main() -> None:
    for p in (MODELS, VIEWS):
        if not p.is_file():
            print(f"FEHLER: {p} nicht gefunden", file=sys.stderr)
            sys.exit(1)
    patch_models()
    patch_views()
    print("")
    print("Danach auf ucs5:")
    print("  cd /opt/abpe/backend")
    print("  python manage.py makemigrations abpe_crm --name crmusersettings_timezone")
    print("  python manage.py migrate abpe_crm --noinput")


if __name__ == "__main__":
    main()
