"""JSON-Hilfen für KI-Wizard-Antworten."""
from __future__ import annotations

import json
import re
from typing import Any


_JSON_FENCE = re.compile(r'^```(?:json)?\s*\n?(.*?)\n?```\s*$', re.DOTALL | re.IGNORECASE)


def parse_ai_json(raw: str) -> dict[str, Any]:
    """Parst JSON aus DeepSeek-Antwort (auch mit Markdown-Fence)."""
    text = (raw or '').strip()
    if not text:
        raise ValueError('Leere KI-Antwort')
    m = _JSON_FENCE.match(text)
    if m:
        text = m.group(1).strip()
    # Erstes JSON-Objekt extrahieren
    start = text.find('{')
    end = text.rfind('}')
    if start >= 0 and end > start:
        text = text[start:end + 1]
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError('KI-Antwort ist kein JSON-Objekt')
    return data


def dumps_compact(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)
