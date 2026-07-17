"""
ABpE Settings - Modular Configuration Entry Point
Note: All settings are now in the 'settings/' directory
"""

import os
import sys

# Add project to path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

# Load modular settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')

# Import from settings package
from .settings import *

# Legacy compatibility (temporary)
print("\n🔧 Using modular settings from abpe_backend.settings.*")
print("   Old settings.py is now just an entry point")
