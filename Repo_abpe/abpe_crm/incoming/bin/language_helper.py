#!/usr/bin/env python3
import os
import sys
import django

sys.path.insert(0, '/opt/abpe/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()

from django.contrib.auth.models import User
from apps.abpe_ui.models import UserSettings

def main():
    if len(sys.argv) < 2:
        print("Usage: language_helper.py --stats")
        print("       language_helper.py --list")
        print("       language_helper.py --show <username>")
        print("       language_helper.py --set <username> <de|en|fr>")
        return
    
    cmd = sys.argv[1]
    
    if cmd == '--stats':
        total = User.objects.count()
        with_settings = UserSettings.objects.count()
        print(f"Gesamt User: {total}")
        print(f"Mit Settings: {with_settings}")
        
        # Statistik für alle Sprachen
        languages = ['de', 'en', 'fr']
        for lang in languages:
            count = UserSettings.objects.filter(language=lang).count()
            print(f"  {lang}: {count}")
    
    elif cmd == '--list':
        for settings in UserSettings.objects.select_related('user')[:20]:
            print(f"{settings.user.username}: {settings.language} / {settings.theme}")
    
    elif cmd == '--show' and len(sys.argv) == 3:
        username = sys.argv[2]
        try:
            user = User.objects.get(username=username)
            settings, _ = UserSettings.objects.get_or_create(user=user)
            print(f"Sprache: {settings.language}, Theme: {settings.theme}")
        except User.DoesNotExist:
            print(f"User {username} nicht gefunden")
    
    elif cmd == '--set' and len(sys.argv) == 4:
        username = sys.argv[2]
        language = sys.argv[3]
        if language not in ['de', 'en', 'fr']:
            print(f"Ungültige Sprache: {language}")
            return
        try:
            user = User.objects.get(username=username)
            settings, _ = UserSettings.objects.get_or_create(user=user)
            settings.language = language
            settings.save()
            print(f"✅ Sprache für {username} auf {language} gesetzt")
        except User.DoesNotExist:
            print(f"User {username} nicht gefunden")
    
    else:
        print("Invalid command")

if __name__ == '__main__':
    main()
