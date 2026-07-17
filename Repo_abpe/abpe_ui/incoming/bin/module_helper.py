#!/usr/bin/env python3
"""
Module Helper für ABpE Portal
"""

import os
import sys
import json
from pathlib import Path

def scan_modules():
    """Scannt alle module.json Dateien"""
    modules_dir = Path("/opt/abpe/backend/apps/abpe_ui/templates/abpe_ui/modules")
    modules = []
    
    if modules_dir.exists():
        for module_dir in modules_dir.iterdir():
            if module_dir.is_dir():
                config_file = module_dir / "module.json"
                if config_file.exists():
                    with open(config_file) as f:
                        config = json.load(f)
                        modules.append(config)
    
    return modules

def main():
    modules = scan_modules()
    print(f"Gefundene Module: {len(modules)}")
    for m in modules:
        print(f"  - {m.get('id', 'unknown')}: {m.get('title', '?')}")

if __name__ == '__main__':
    main()
