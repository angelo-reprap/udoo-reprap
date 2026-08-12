"""
ollama_service.py - Ollama LLM Integration für cv_extractor
Vollständige Version mit allen Optimierungen
"""

import json
import logging
import re
import time
import requests
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LLMExtractionResult:
    """Ergebnis der LLM-Extraktion"""
    success: bool
    data: Dict[str, Any]
    raw_response: str
    confidence: float
    processing_time: float
    error: Optional[str] = None
    model_used: str = "qwen2.5:7b"


class OllamaService:
    """
    Service für Ollama AI-Integration
    Unterstützt:
    - JSON-Extraktion aus LLM-Antworten
    - Konfigurierbare Parameter (Temperature, Top-K, Context Window)
    - Timeout-Handling
    - Fehlerbehandlung
    """

    def __init__(self, model: str = "qwen2.5:7b", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url.rstrip('/')
        self.api_url = f"{self.base_url}/api/generate"
        self.session = requests.Session()
        self.session.verify = False  # Für lokale Entwicklung
        logger.info(f"🚀 OllamaService initialisiert mit Modell: {model}")

    def _get_options(self, temperature: float = 0.0, num_ctx: int = 32768) -> Dict[str, Any]:
        """
        Ollama-Optionen für deterministische Ausgabe
        
        Args:
            temperature: 0 = deterministisch, höher = kreativer
            num_ctx: Context Window Größe (Default 32k, max 128k für qwen2.5)
        """
        return {
            "temperature": temperature,
            "top_k": 1,
            "top_p": 0.1,
            "repeat_penalty": 1.2,
            "num_ctx": num_ctx,
            "seed": 42,  # Feste Seed für Reproduzierbarkeit
        }

    def extract(self, prompt: str, timeout: int = 120, temperature: float = 0.0, num_ctx: int = 32768) -> LLMExtractionResult:
        """
        Sendet Prompt an Ollama und parst JSON-Antwort
        
        Args:
            prompt: Der Prompt für das LLM
            timeout: Timeout in Sekunden
            temperature: Kreativität (0 = deterministisch)
            num_ctx: Context Window Größe
            
        Returns:
            LLMExtractionResult mit extrahierten Daten
        """
        start_time = time.time()

        try:
            request_data = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": self._get_options(temperature=temperature, num_ctx=num_ctx),
            }

            logger.debug(f"Sende Request an Ollama (timeout={timeout}s, num_ctx={num_ctx})")
            
            response = self.session.post(self.api_url, json=request_data, timeout=timeout)

            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.error(error_msg)
                return LLMExtractionResult(
                    success=False, data={}, raw_response="",
                    confidence=0.0, processing_time=time.time() - start_time,
                    error=error_msg
                )

            result = response.json()
            raw_response = result.get('response', '')
            
            # Extrahiere JSON aus der Antwort
            json_data = self._extract_json(raw_response)
            
            # Berechne Confidence
            confidence = 0.0
            if json_data:
                confidence = 0.9
                logger.debug(f"Erfolgreich extrahiert: {len(str(json_data))} Zeichen")
            else:
                logger.warning(f"Kein JSON in Antwort gefunden: {raw_response[:200]}")

            return LLMExtractionResult(
                success=bool(json_data),
                data=json_data or {},
                raw_response=raw_response,
                confidence=confidence,
                processing_time=time.time() - start_time,
                model_used=self.model
            )

        except requests.exceptions.Timeout:
            error_msg = f"Timeout nach {timeout}s"
            logger.error(error_msg)
            return LLMExtractionResult(
                success=False, data={}, raw_response="",
                confidence=0.0, processing_time=time.time() - start_time,
                error=error_msg
            )
            
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Verbindungsfehler zu Ollama: {e}"
            logger.error(error_msg)
            return LLMExtractionResult(
                success=False, data={}, raw_response="",
                confidence=0.0, processing_time=time.time() - start_time,
                error=error_msg
            )
            
        except Exception as e:
            error_msg = str(e)
            logger.exception(f"Unerwarteter Fehler: {error_msg}")
            return LLMExtractionResult(
                success=False, data={}, raw_response="",
                confidence=0.0, processing_time=time.time() - start_time,
                error=error_msg
            )

    def _extract_json(self, text: str) -> Optional[Dict]:
        """
        Extrahiert JSON aus LLM-Antwort.
        Unterstützt:
        - Markdown-Codeblöcke (```json ... ```)
        - Reine JSON-Objekte
        """
        if not text:
            return None

        # 1. Markdown-Codeblock mit json
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 2. Markdown-Codeblock ohne Sprache
        match = re.search(r'```\s*([\s\S]*?)\s*```', text)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 3. Reines JSON-Objekt (von { bis })
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        # 4. JSON-Array (von [ bis ])
        match = re.search(r'\[[\s\S]*\]', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        logger.debug(f"Kein JSON in Antwort gefunden: {text[:100]}")
        return None

    def is_available(self) -> bool:
        """Prüft ob Ollama erreichbar ist"""
        try:
            response = self.session.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False


# Singleton-Instanz
ollama_service = OllamaService()
