#!/usr/bin/env python3
"""
Backup Helper für ABpE Portal
"""

import os
import sys
import shutil
from datetime import datetime

def create_backup(file_path):
    """Erstellt ein Backup einer Datei"""
    if not os.path.exists(file_path):
        print(f"❌ Datei nicht gefunden: {file_path}")
        return False
    
    backup_dir = "/opt/abpe/backend/apps/abpe_ui/archive"
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.basename(file_path)
    backup_name = f"{filename}.{timestamp}.backup"
    backup_path = os.path.join(backup_dir, backup_name)
    
    shutil.copy2(file_path, backup_path)
    print(f"✅ Backup erstellt: {backup_path}")
    return True

def main():
    if len(sys.argv) < 2:
        print("Usage: backup_helper.py <file_path>")
        return
    
    create_backup(sys.argv[1])

if __name__ == '__main__':
    main()
