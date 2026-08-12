"""
core/module_scanner.py
Priorität der Berechtigungen:
  1. UserModulePermission (DB)  — user-spezifisch, höchste Priorität
  2. GroupModulePermission (DB) — gruppen-spezifisch, überschreibt module.json
  3. roles in module.json       — Standard-Fallback
"""

import json
from pathlib import Path
from typing import List, Dict, Optional


class ModuleScanner:

    def __init__(self):
        self.base_dir    = Path(__file__).parent.parent
        self.modules_dir = self.base_dir / 'templates' / 'abpe_crm' / 'modules'
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
        user_groups    = []
        is_staff       = False
        denied_user    = set()   # UserModulePermission
        denied_groups  = {}      # {module_id: set(group_names that deny)}
        allowed_groups = {}      # {module_id: set(group_names that allow)}

        if user and user.is_authenticated:
            user_groups = list(user.groups.values_list('name', flat=True))
            is_staff    = user.is_staff

            # 1. User-spezifische Ausschlüsse
            try:
                from apps.abpe_ui.models import UserModulePermission
                denied_user = set(
                    UserModulePermission.objects.filter(
                        user=user, denied=True
                    ).values_list('module_id', flat=True)
                )
            except Exception:
                pass

            # 2. Gruppen-Berechtigungen aus DB laden
            try:
                from apps.abpe_ui.models import GroupModulePermission
                from django.contrib.auth.models import Group
                user_group_ids = Group.objects.filter(
                    name__in=user_groups
                ).values_list('id', flat=True)

                for perm in GroupModulePermission.objects.filter(
                    group_id__in=user_group_ids
                ).select_related('group'):
                    mid = perm.module_id
                    gname = perm.group.name
                    if perm.denied:
                        denied_groups.setdefault(mid, set()).add(gname)
                    else:
                        allowed_groups.setdefault(mid, set()).add(gname)
            except Exception:
                pass

        nav = []
        for module in self.modules:
            mid   = module['id']
            roles = module.get('roles', [])

            # ── Priorität 1: User-spezifisch ──────────────────────────
            if mid in denied_user:
                continue

            # ── Priorität 2: Gruppen-DB-Berechtigungen ────────────────
            if denied_groups or allowed_groups:
                if mid in denied_groups or mid in allowed_groups:
                    # DB-Regel vorhanden — module.json roles ignorieren
                    denied_by  = denied_groups.get(mid, set())
                    allowed_by = allowed_groups.get(mid, set())

                    user_group_set = set(user_groups)

                    # Wenn eine der User-Gruppen explizit gesperrt hat
                    if denied_by & user_group_set:
                        # Nur überspringen wenn KEINE Gruppe explizit erlaubt
                        if not (allowed_by & user_group_set):
                            continue

                    # Wenn allowed_by Einträge existieren aber keine
                    # der User-Gruppen darin ist → kein Zugriff
                    if allowed_by and not (allowed_by & user_group_set):
                        if not is_staff:
                            continue

                    # DB-Regel erlaubt → module.json roles überspringen
                    pass
                else:
                    # Keine DB-Regel → module.json roles prüfen
                    if roles and not self._check_roles(roles, user_groups, is_staff):
                        continue
            else:
                # Keine DB-Regeln → module.json roles prüfen
                if roles and not self._check_roles(roles, user_groups, is_staff):
                    continue

            # Subpages filtern
            subpages = []
            for sp in module.get('subpages', []):
                sp_roles = sp.get('roles', [])
                if sp_roles and not self._check_roles(sp_roles, user_groups, is_staff):
                    continue
                subpages.append({
                    'id':     sp['id'],
                    'title':  sp['title'],
                    'titles': sp.get('titles', {}),
                    'route':  sp['route'],
                })

            nav.append({
                'id':       mid,
                'title':    module['title'],
                'titles':   module.get('titles', {}),
                'icon':     module.get('icon', 'puzzle'),
                'route':    module['route'],
                'order':    module.get('order', 999),
                'subpages': subpages,
            })

        return sorted(nav, key=lambda x: x['order'])

    def _check_roles(self, roles, user_groups, is_staff):
        if is_staff:
            return True
        for role in roles:
            if role.startswith('!') and role[1:] in user_groups:
                return False
        positive = [r for r in roles if not r.startswith('!')]
        if positive:
            return any(g in user_groups for g in positive)
        return True


scanner = ModuleScanner()
