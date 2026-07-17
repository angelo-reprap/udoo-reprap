"""
ABpE Settings Package - Modular Configuration
Import Order Matters! Base must come first.
"""

import os

# 1. BASE zuerst (enthält DEBUG, INSTALLED_APPS, etc.)
from .base import *

# 2. Dann Database (benötigt BASE)
from .database import *

# 3. Dann App Definitions (nur Listen, keine Erweiterungen)
from .apps import *

# 4. JETZT INSTALLED_APPS erweitern (nachdem base.py importiert wurde)
INSTALLED_APPS.extend(THIRD_PARTY_APPS)
INSTALLED_APPS.extend(ABPE_APPS)

# 5. Dann CMS (benötigt BASE und erweiterte INSTALLED_APPS)
from .cms import *

# 6. Dann Security (DEBUG wird hier noch nicht verwendet)
from .security import *

# 7. JETZT CORS_ALLOW_ALL_ORIGINS basierend auf DEBUG setzen
# (nachdem security.py importiert wurde, aber DEBUG verfügbar ist)
CORS_ALLOW_ALL_ORIGINS = DEBUG

# 8. Dann Email
from .email import *
from .crm_bridge import *

# 9. Dann Intake (ABpE spezifisch)
from .intake import *

# 10. Dann API
from .api import *

# 11. Dann LDAP Configuration (neu!)
try:
    from .ldap import *
    # LDAP Backend zu AUTHENTICATION_BACKENDS hinzufügen
    AUTHENTICATION_BACKENDS = (
        'django_auth_ldap.backend.LDAPBackend',
        'django.contrib.auth.backends.ModelBackend',  # Fallback für Admin
    )
    print("✅ LDAP Authentication Backend aktiviert")
except ImportError as e:
    print(f"⚠️  LDAP configuration not loaded: {e}")
    AUTHENTICATION_BACKENDS = (
        'django.contrib.auth.backends.ModelBackend',
    )

# 12. Dann Logging (letztes, da es andere Settings verwenden kann)
from .logging import *

# Local overrides (if exists)
try:
    from .local import *
except ImportError:
    pass

# Environment specific
if os.environ.get('DJANGO_ENV') == 'production':
    try:
        from .production import *
    except ImportError:
        pass
elif os.environ.get('DJANGO_ENV') == 'staging':
    try:
        from .staging import *
    except ImportError:
        pass

print("=" * 60)
print("✅ ABpE SETTINGS GELADEN (modular)")
print(f"✅ Django Version: {__import__('django').__version__}")
print(f"✅ Apps: {len(INSTALLED_APPS)} installiert")
print(f"✅ Environment: {os.environ.get('DJANGO_ENV', 'development')}")
print(f"✅ DEBUG: {DEBUG}")
print(f"✅ AUTH Backends: {len(AUTHENTICATION_BACKENDS)} aktiviert")
print("=" * 60)

# ElasticSearch Configuration
try:
    from .elasticsearch_config import *
except ImportError as e:
    print(f"⚠️  ElasticSearch settings not loaded: {e}")

# ABpE UI Settings laden (Context Processors)
from .abpe_ui import *
