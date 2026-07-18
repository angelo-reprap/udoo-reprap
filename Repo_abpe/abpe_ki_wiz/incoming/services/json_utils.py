"""JSON-Hilfen für KI-Wizard-Antworten."""
from __future__ import annotations

import json
import re
from typing import Any


_JSON_FENCE = re.compile(r'^```(?:json)?\s*\n?(.*?)\n?```\s*$', re.DOTALL | re.IGNORECASE)


def _extract_json_blob(text: str) -> str:
    text = (text or '').strip()
    if not text:
        raise ValueError('Leere KI-Antwort')
    m = _JSON_FENCE.match(text)
    if m:
        text = m.group(1).strip()
    # Manche Modelle liefern Text vor/nach dem Objekt
    start = text.find('{')
    end = text.rfind('}')
    if start >= 0 and end > start:
        text = text[start:end + 1]
    return text


def _escape_newlines_in_strings(text: str) -> str:
    """
    Repariert häufiges Modell-Problem: echte Zeilenumbrüche innerhalb von JSON-Strings
    → Unterminated string / Invalid control character.
    """
    out: list[str] = []
    in_string = False
    escape = False
    for ch in text:
        if escape:
            out.append(ch)
            escape = False
            continue
        if ch == '\\' and in_string:
            out.append(ch)
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            out.append(ch)
            continue
        if in_string and ch in ('\n', '\r'):
            if ch == '\n':
                out.append('\\n')
            # \r drop / ignore
            continue
        if in_string and ch == '\t':
            out.append('\\t')
            continue
        out.append(ch)
    return ''.join(out)


def _strip_trailing_commas(text: str) -> str:
    return re.sub(r',\s*([}\]])', r'\1', text)


def parse_ai_json(raw: str) -> dict[str, Any]:
    """Parst JSON aus DeepSeek-Antwort (Fence, Control-Chars, trailing commas)."""
    text = _extract_json_blob(raw)
    attempts = [
        text,
        _escape_newlines_in_strings(text),
        _strip_trailing_commas(text),
        _strip_trailing_commas(_escape_newlines_in_strings(text)),
    ]
    last_err: Exception | None = None
    for candidate in attempts:
        try:
            data = json.loads(candidate)
            if not isinstance(data, dict):
                raise ValueError('KI-Antwort ist kein JSON-Objekt')
            return data
        except (json.JSONDecodeError, ValueError) as exc:
            last_err = exc
            continue
    raise ValueError(str(last_err) if last_err else 'JSON ungültig')


def dumps_compact(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)
