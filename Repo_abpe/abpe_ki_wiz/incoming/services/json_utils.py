"""JSON-Hilfen für KI-Wizard-Antworten."""
from __future__ import annotations

import json
import re
from typing import Any


_JSON_FENCE = re.compile(r'^```(?:json)?\s*\n?(.*?)\n?```\s*$', re.DOTALL | re.IGNORECASE)

# Felder die oft HTML mit unescapten " enthalten
_BODY_KEYS = (
    'html_body', 'text_body', 'subject', 'name', 'identifier',
    'description', 'summary', 'module_type',
)


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
            continue
        if in_string and ch == '\t':
            out.append('\\t')
            continue
        out.append(ch)
    return ''.join(out)


def _strip_trailing_commas(text: str) -> str:
    return re.sub(r',\s*([}\]])', r'\1', text)


def _unescape_json_string(value: str) -> str:
    try:
        return json.loads(f'"{value}"')
    except Exception:
        return (
            value
            .replace('\\n', '\n')
            .replace('\\t', '\t')
            .replace('\\"', '"')
            .replace('\\\\', '\\')
        )


def _find_key_starts(text: str) -> list[tuple[int, str]]:
    """Positionen von "key": im JSON-Text (nur Top-Level-ähnlich)."""
    found: list[tuple[int, str]] = []
    for m in re.finditer(r'"([a-zA-Z_][a-zA-Z0-9_]*)"\s*:', text):
        found.append((m.start(), m.group(1)))
    return found


def _extract_string_field(text: str, key: str) -> str | None:
    """
    Extrahiert String-Wert für key auch bei unescapten Anführungszeichen im HTML.

    Strategie: vom "key": " bis zum nächsten bekannten Top-Level-Key oder Ende.
    """
    pat = re.compile(rf'"{re.escape(key)}"\s*:\s*"', re.DOTALL)
    m = pat.search(text)
    if not m:
        return None
    start = m.end()
    keys = _find_key_starts(text)
    # Nächster Key nach unserem Value-Start
    next_pos = len(text)
    for pos, _name in keys:
        if pos >= start:
            # zurück bis vor dem "key"
            # typisches Ende: ",\n  "nextkey"  oder  "\n}
            chunk_end = text.rfind('"', 0, pos)
            # besser: suche rückwärts nach dem Trennzeichen vor dem nächsten Key
            # Pattern: ",\s*"nextkey"
            before = text[start:pos]
            # Trim trailing `",` or `"` before next key
            cut = re.search(r'"\s*,\s*$', before)
            if cut:
                next_pos = start + cut.start()
                break
            # Fallback: letztes " vor dem nächsten Key
            if chunk_end >= start:
                next_pos = chunk_end
            else:
                next_pos = pos
            break
    else:
        # Kein Folgeschlüssel — bis vor schließendem }
        end_m = re.search(r'"\s*}?\s*$', text[start:], re.DOTALL)
        if end_m:
            # finde letztes unescaped " das den String schließt
            next_pos = start + end_m.start()
        else:
            # Truncation: restlichen Text nehmen
            rest = text[start:]
            if rest.endswith('"'):
                next_pos = start + len(rest) - 1
            else:
                next_pos = len(text)

    raw_val = text[start:next_pos]
    # Wenn wir am Ende Truncation ohne schließendes " haben — trotzdem nehmen
    return _unescape_json_string(raw_val)


def _extract_json_array_field(text: str, key: str) -> list[Any] | None:
    pat = re.compile(rf'"{re.escape(key)}"\s*:\s*(\[)', re.DOTALL)
    m = pat.search(text)
    if not m:
        return None
    start = m.start(1)
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if esc:
            esc = False
            continue
        if ch == '\\' and in_str:
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                try:
                    data = json.loads(text[start:i + 1])
                    return data if isinstance(data, list) else None
                except json.JSONDecodeError:
                    return None
    return None


def recover_ai_json_dict(raw: str) -> dict[str, Any]:
    """
    Best-effort: aus kaputtem Generate-JSON die wichtigsten Felder retten.
    Typischer Fehler: HTML mit style="…" bricht JSON-Strings.
    """
    text = _extract_json_blob(raw)
    recovered: dict[str, Any] = {}
    for key in _BODY_KEYS:
        val = _extract_string_field(text, key)
        if val is not None and val.strip():
            recovered[key] = val
    for key in ('variables_used', 'layout_suggestions', 'missing_topics'):
        arr = _extract_json_array_field(text, key)
        if arr is not None:
            recovered[key] = arr
    if not recovered.get('html_body') and not recovered.get('summary'):
        raise ValueError('Keine rettbaren Felder in kaputtem JSON')
    recovered['_recovered'] = True
    return recovered


def parse_ai_json(raw: str) -> dict[str, Any]:
    """Parst JSON aus DeepSeek-Antwort (Fence, Control-Chars, trailing commas, Quote-Repair)."""
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

    # Letzter Versuch: Felder aus kaputtem JSON retten (unescaped " in HTML)
    try:
        return recover_ai_json_dict(raw)
    except ValueError:
        pass

    raise ValueError(str(last_err) if last_err else 'JSON ungültig')


def dumps_compact(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)
