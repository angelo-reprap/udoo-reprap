"""
base_extractor.py - Universeller Extraktor mit DeepSeek API Service
"""

import json
import re
from typing import Dict, Any, Optional

from ..services.deepseek_api import deepseek_api


class UniversalExtractor:
    """Universeller Extraktor - Konfiguration aus DB, nutzt DeepSeek API Service"""

    def __init__(self, stage: str):
        self.stage = stage
        self._config = None

    def _load_config(self) -> Optional[Dict]:
        if self._config is not None:
            return self._config

        try:
            from apps.cv_extractor.models import PromptTemplate

            config = PromptTemplate.objects.filter(
                stage=self.stage,
                is_active=True
            ).first()

            if config:
                self._config = {
                    "name": config.name,
                    "prompt_text": config.prompt_text,
                    "schema": config.schema if hasattr(config, 'schema') else {},
                    "target_path": config.target_path if hasattr(config, 'target_path') else ""
                }
                return self._config
            else:
                print(f"⚠️ Keine Konfiguration für {self.stage} gefunden")
                return None

        except Exception as e:
            print(f"⚠️ Fehler beim Laden der Konfiguration {self.stage}: {e}")
            return None

    def extract(self, text: str) -> Dict[str, Any]:
        if not text or len(text.strip()) < 10:
            return {}

        config = self._load_config()
        if not config:
            return {}

        # Manuelle String-Ersetzung statt format() (wegen JSON-Klammern)
        prompt = config["prompt_text"].replace("{text}", text[:3000])

        # Nutze den existierenden DeepSeek API Service
        result = deepseek_api.extract(prompt, system_prompt="Du bist ein präziser CV-Analyst. Antworte nur mit JSON.")

        if result.success:
            print(f"✅ {config['name']}: extrahiert")
            return result.data
        else:
            print(f"❌ {self.stage}: {result.error}")
            return {}

    def get_target_path(self) -> str:
        config = self._load_config()
        return config.get("target_path", "") if config else ""


BaseExtractor = UniversalExtractor
