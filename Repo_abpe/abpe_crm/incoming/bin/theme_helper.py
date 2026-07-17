#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, '/opt/abpe/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')

import django
django.setup()

from django.contrib.auth.models import User
from apps.abpe_ui.models import UserSettings

def main():
    if len(sys.argv) < 2:
        print("Usage: theme_helper.py get <username>")
        print("       theme_helper.py set <username> <light|dark|system>")
        print("       theme_helper.py stats")
        return
    
    cmd = sys.argv[1]
    
    if cmd == 'get' and len(sys.argv) == 3:
        username = sys.argv[2]
        try:
            user = User.objects.get(username=username)
            settings, _ = UserSettings.objects.get_or_create(user=user)
            print(f"Theme: {settings.theme}")
        except User.DoesNotExist:
            print(f"User {username} nicht gefunden")
    
    elif cmd == 'set' and len(sys.argv) == 4:
        username = sys.argv[2]
        theme = sys.argv[3]
        if theme not in ['light', 'dark', 'system']:
            print(f"Ungültiges Theme: {theme}")
            return
        try:
            user = User.objects.get(username=username)
            settings, _ = UserSettings.objects.get_or_create(user=user)
            settings.theme = theme
            settings.save()
            print(f"Theme für {username} auf {theme} gesetzt")
        except User.DoesNotExist:
            print(f"User {username} nicht gefunden")
    
    elif cmd == 'stats':
        total = User.objects.count()
        with_settings = UserSettings.objects.count()
        print(f"Gesamt User: {total}")
        print(f"Mit Settings: {with_settings}")
        for theme in ['light', 'dark', 'system']:
            count = UserSettings.objects.filter(theme=theme).count()
            print(f"  {theme}: {count}")
    
    else:
        print("Unknown command")

if __name__ == '__main__':
    main()
