"""
Zentrale Settings für ABpE
Liest aus /opt/abpe/backend/settings.json
VOLLSTÄNDIGE Version mit Elasticsearch Support
"""

import json
import os
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class Settings:
    """Einfacher Settings-Loader für JSON"""

    _instance = None
    _settings = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self):
        """Lädt settings.json"""
        settings_path = Path("/opt/abpe/backend/settings.json")

        if not settings_path.exists():
            logger.warning("⚠️ settings.json nicht gefunden, verwende Defaults")
            self._settings = self._get_defaults()
            return

        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                self._settings = json.load(f)
            logger.info("✅ settings.json geladen")
        except Exception as e:
            logger.error(f"❌ Fehler beim Laden von settings.json: {e}")
            self._settings = self._get_defaults()

    def _get_defaults(self):
        """Default-Werte falls keine JSON existiert"""
        return {
            "system": {
                "name": "ABpE",
                "environment": "development",
                "debug": True,
                "timezone": "Europe/Berlin"
            },
            "ai_models": {
                "ollama": {
                    "primary": "qwen2.5:7b",
                    "fallback": "phi3:mini",
                    "timeout": 60,
                    "temperature": 0.1
                },
                "deepseek": {
                    "api_key": "",
                    "model": "deepseek-chat",
                    "timeout": 30,
                    "temperature": 0.1
                }
            },
            "elasticsearch": {
                "enabled": True,
                "hosts": ["http://localhost:9200"],
                "index_name": "abpe_skills_index",
                "min_score": 0.6,
                "knn_candidates": 100
            },
            "namazu": {
                "enabled": False,
                "index_path": "/var/lib/namazu/namazu-index",
                "html_source": "/opt/Namazu/Sugar2Namazu/out/",
                "html_output": "/var/www/namazu/index/",
                "binary": {
                    "namazu": "/usr/bin/namazu",
                    "mknmz": "/usr/bin/mknmz"
                }
            },
            "mysql": {
                "suitecrm": {
                    "host": "172.20.3.150",
                    "port": 3306,
                    "database": "suitecrm",
                    "user": "suitecrm",
                    "password": "3b135fd9a867a884509a13d6ceb8dd5e460f963be10e07619767301f9b9087c7"
                }
            },
            "suitecrm": {
                "soap_endpoint": "https://172.20.3.150/suitecrm/soap.php?wsdl",
                "user": "admin",
                "password": "abcona",
                "linkback_template": "https://ucs.win.abcona.info/suitecrm/index.php?module=Contacts&action=DetailView&record=%s"
            },
            "email": {
                "imap": {
                    "server": "imap.ionos.de",
                    "port": 993,
                    "username": "cv_scan@abcona.de",
                    "password": "",
                    "use_ssl": True,
                    "mailbox": "INBOX"
                }
            },
            "training": {
                "min_confidence_to_save": 0.7,
                "use_deepseek_fallback": True,
                "auto_create_relations": True,
                "max_variations_per_term": 10,
                "use_elasticsearch": True
            },
            "storage": {
                "media_root": "/opt/abpe/backend/media",
                "training_data": "/opt/abpe/backend/media/cv/training",
                "email_attachments": "/opt/abpe/backend/media/email/attachments",
                "cv_adds": "/opt/abpe/backend/media/cv/adds"
            }
        }

    def get(self, key: str, default: Any = None) -> Any:
        """
        Holt einen Wert aus den Settings (Punkt-Notation)
        Beispiel: settings.get('elasticsearch.enabled')
        """
        keys = key.split('.')
        value = self._settings

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value

    # === PROPERTIES für einfachen Zugriff ===
    
    @property
    def deepseek_api_key(self) -> str:
        """Kurzform für Deepseek Key"""
        return self.get('ai_models.deepseek.api_key', '')

    @property
    def elasticsearch_enabled(self) -> bool:
        """Ist Elasticsearch aktiviert?"""
        return self.get('elasticsearch.enabled', True)

    @property
    def elasticsearch_config(self) -> Dict:
        """Gibt Elasticsearch Konfiguration zurück"""
        return self.get('elasticsearch', {})

    @property
    def mysql_suitecrm_config(self) -> Dict:
        """Gibt SuiteCRM MySQL Konfiguration zurück"""
        return self.get('mysql.suitecrm', {})

    @property
    def suitecrm_config(self) -> Dict:
        """Gibt SuiteCRM SOAP Konfiguration zurück"""
        return self.get('suitecrm', {})

    @property
    def namazu_config(self) -> Dict:
        """Gibt Namazu Konfiguration zurück"""
        return self.get('namazu', {})

    @property
    def email_imap_config(self) -> Dict:
        """Gibt Email IMAP Konfiguration zurück"""
        return self.get('email.imap', {})

    @property
    def training_config(self) -> Dict:
        """Gibt Training Konfiguration zurück"""
        return self.get('training', {})

    @property
    def storage_config(self) -> Dict:
        """Gibt Storage Konfiguration zurück"""
        return self.get('storage', {})

    @property
    def ollama_config(self) -> Dict:
        """Gibt Ollama Konfiguration zurück"""
        return self.get('ai_models.ollama', {})

    # === SPEZIELLE METHODEN ===
    
    def get_mysql_connection(self, db_name: str = 'suitecrm'):
        """Erstellt MySQL Verbindung aus settings"""
        config = self.get(f'mysql.{db_name}', {})
        if not config:
            logger.error(f"❌ Keine MySQL Konfiguration für {db_name} gefunden")
            return None

        try:
            import mysql.connector
            conn = mysql.connector.connect(
                host=config.get('host'),
                port=config.get('port', 3306),
                database=config.get('database'),
                user=config.get('user'),
                password=config.get('password'),
                charset='utf8mb4',
                use_unicode=True,
                autocommit=False
            )
            logger.info(f"✅ MySQL Verbindung zu {config.get('host')}/{config.get('database')} hergestellt")
            return conn
        except ImportError:
            logger.error("❌ mysql-connector-python nicht installiert. Bitte installieren: pip install mysql-connector-python")
            return None
        except Exception as e:
            logger.error(f"❌ MySQL Verbindung fehlgeschlagen: {e}")
            return None

    def get_elasticsearch_client(self):
        """Erstellt Elasticsearch Client (optional)"""
        if not self.elasticsearch_enabled:
            return None
        try:
            from elasticsearch import Elasticsearch
            hosts = self.get('elasticsearch.hosts', ['http://localhost:9200'])
            return Elasticsearch(hosts)
        except ImportError:
            logger.warning("⚠️ elasticsearch-py nicht installiert")
            return None
        except Exception as e:
            logger.error(f"❌ Elasticsearch Client Fehler: {e}")
            return None


# Singleton
settings = Settings()
