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
    
    def get_navigation(self) -> List[Dict]:
        """Gibt Navigation für Sidebar zurück"""
        nav = []
        for module in self.modules:
            # Subpages mit titles weitergeben
            subpages = []
            for sp in module.get('subpages', []):
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


# Singleton für globale Nutzung
scanner = ModuleScanner()
