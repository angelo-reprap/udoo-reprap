"""
core/module_scanner.py - Modul-Scanner für ABpE Portal
Scannt module.json Dateien und stellt sie für Navigation bereit.
Berücksichtigt Gruppen-Rollen UND user-spezifische Modul-Ausschlüsse.
"""

import json
from pathlib import Path
from typing import List, Dict, Optional


class ModuleScanner:

    def __init__(self):
        self.base_dir    = Path(__file__).parent.parent
        self.modules_dir = self.base_dir / 'templates' / 'abpe_ui' / 'modules'
        self.modules     = []
        self.scan()

    def scan(self) -> List[Dict]:
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
        for m in self.modules:
            if m['id'] == module_id:
                return m
        return None

    def get_navigation(self, user=None) -> List[Dict]:
        """
        Navigation für Sidebar — gefiltert nach:
        1. Gruppen-Rollen (roles in module.json)
        2. User-spezifische Modul-Ausschlüsse (UserModulePermission)
        """
        user_groups  = []
        is_staff     = False
        denied_modules = set()

        if user and user.is_authenticated:
            user_groups = list(user.groups.values_list('name', flat=True))
            is_staff    = user.is_staff

            # User-spezifische Ausschlüsse aus DB laden
            try:
                from apps.abpe_ui.models import UserModulePermission
                denied_modules = set(
                    UserModulePermission.objects.filter(
                        user=user, denied=True
                    ).values_list('module_id', flat=True)
                )
            except Exception:
                pass

        nav = []
        for module in self.modules:
            module_id = module['id']

            # 1. Gruppen-Rollen prüfen (staff hat immer Zugriff)
            roles = module.get('roles', [])
            if roles and not self._user_has_access(roles, user_groups, is_staff):
                continue

            # 2. User-spezifische Ausschlüsse prüfen
            # staff/superuser sind NICHT ausgenommen — bewusste Entscheidung
            # damit Admin gezielt einzelne Module für sich selbst sperren kann
            if module_id in denied_modules:
                continue

            # Subpages filtern
            subpages = []
            for sp in module.get('subpages', []):
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
                'id':       module_id,
                'title':    module['title'],
                'titles':   module.get('titles', {}),
                'icon':     module.get('icon', 'puzzle'),
                'route':    module['route'],
                'order':    module.get('order', 999),
                'subpages': subpages,
            })

        return sorted(nav, key=lambda x: x['order'])

    def _user_has_access(self, roles: list, user_groups: list, is_staff: bool) -> bool:
        if is_staff:
            return True
        # Negativ-Regeln zuerst prüfen
        for role in roles:
            if role.startswith('!'):
                if role[1:] in user_groups:
                    return False
        # Positiv-Regeln
        positive = [r for r in roles if not r.startswith('!')]
        if positive:
            return any(g in user_groups for g in positive)
        return True


scanner = ModuleScanner()
