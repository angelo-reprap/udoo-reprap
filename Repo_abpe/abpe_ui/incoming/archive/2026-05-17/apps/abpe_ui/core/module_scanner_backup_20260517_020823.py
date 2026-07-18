"""
core/module_scanner.py - Modul-Scanner für ABpE Portal
Scannt module.json Dateien und stellt sie für Navigation bereit
"""

import json
from pathlib import Path
from typing import List, Dict, Optional


class ModuleScanner:
    """Scanner für module.json Dateien"""

    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.modules_dir = self.base_dir / 'templates' / 'abpe_ui' / 'modules'
        self.modules = []
        self.scan()

    def scan(self) -> List[Dict]:
        """Scannt alle module.json Dateien"""
        self.modules = []

        if not self.modules_dir.exists():
            return self.modules

        for module_dir in self.modules_dir.iterdir():
            if module_dir.is_dir():
                config_file = module_dir / 'module.json'
                if config_file.exists():
                    with open(config_file, 'r') as f:
                        config = json.load(f)
                    if config.get('enabled', True):
                        self.modules.append(config)

        self.modules.sort(key=lambda x: x.get('order', 999))
        return self.modules

    def get_module(self, module_id: str) -> Optional[Dict]:
        """Gibt ein bestimmtes Modul zurück"""
        for m in self.modules:
            if m['id'] == module_id:
                return m
        return None

    def get_navigation(self, user=None) -> List[Dict]:
        """
        Gibt Navigation für Sidebar zurück.
        Filtert nach roles wenn user übergeben wird.

        Rollen-Logik:
          - roles fehlt oder leer  → für alle sichtbar
          - roles: ["admin"]       → nur Admins
          - roles: ["!berater"]    → alle AUSSER Berater
        """
        nav = []
        user_groups = []
        is_staff = False

        if user and user.is_authenticated:
            user_groups = list(user.groups.values_list('name', flat=True))
            is_staff = user.is_staff

        for module in self.modules:
            roles = module.get('roles', [])

            if roles:
                if not self._user_has_access(roles, user_groups, is_staff):
                    continue

            subpages = []
            for sp in module.get('subpages', []):
                # Subpages können auch eigene roles haben
                sp_roles = sp.get('roles', [])
                if sp_roles and not self._user_has_access(sp_roles, user_groups, is_staff):
                    continue
                subpages.append({
                    'id':     sp['id'],
                    'title':  sp['title'],
                    'titles': sp.get('titles', {}),
                    'route':  sp['route'],
                })

            nav.append({
                'id':       module['id'],
                'title':    module['title'],
                'titles':   module.get('titles', {}),
                'icon':     module.get('icon', 'puzzle'),
                'route':    module['route'],
                'order':    module.get('order', 999),
                'subpages': subpages,
            })

        return sorted(nav, key=lambda x: x['order'])

    def _user_has_access(self, roles: list, user_groups: list, is_staff: bool) -> bool:
        """
        Prüft ob ein User Zugriff hat.

        Positiv-Liste:  ["admin", "disponent"]  → User muss in einer dieser Gruppen sein
        Negativ-Liste:  ["!berater"]             → User darf NICHT in dieser Gruppe sein
        Gemischt:       ["admin", "!berater"]    → admin UND nicht berater
        Superuser/staff haben immer Zugriff.
        """
        if is_staff:
            return True

        for role in roles:
            if role.startswith('!'):
                # Negativ-Regel: User darf diese Gruppe NICHT haben
                excluded = role[1:]
                if excluded in user_groups:
                    return False
            else:
                # Positiv-Regel: mindestens eine muss zutreffen
                pass

        # Positiv-Regeln prüfen (ohne ! prefix)
        positive = [r for r in roles if not r.startswith('!')]
        if positive:
            return any(g in user_groups for g in positive)

        # Nur Negativ-Regeln vorhanden und alle OK
        return True


# Singleton für globale Nutzung
scanner = ModuleScanner()
