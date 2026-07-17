"""
apps/abpe_crm/services/deepseek_api_pbx.py

DeepSeek fuer das Telefon-/Konferenz-Modul.
Formuliert aus groben Konferenz-Mitschriften ein sauberes Protokoll
(TXT oder JSON) bzw. optimiert einzelne Gespraechsnotizen.

Nutzt denselben API-Key wie der CV-Extractor (settings.json ->
ai_models.deepseek.api_key), SSL-Verify aus (Dev), Modell deepseek-chat.

PROMPTS: als Modul-Konstanten (DEFAULT_PROMPTS). _get_prompt(key) liest
spaeter aus einem DB-Model PbxPrompt(key, system, user_template, aktiv) und
faellt auf die Konstanten hier zurueck (Fallback). Solange das Model nicht
existiert, gelten immer die Konstanten. -> DB+Admin ist ein spaeterer,
abgegrenzter Schritt, ohne diese Datei erneut anzufassen.

Platzhalter in den user-Templates (per _fill ersetzt, KEIN str.format wegen
JSON-Klammern):  [[KOPF]] [[NOTES]] [[CONTEXT]] [[TEXT]] [[INSTRUCTION]]

Verwendung:
    from apps.abpe_crm.services.deepseek_api_pbx import deepseek_pbx
    res = deepseek_pbx.format_protocol(notes, meta={...}, output='txt')
    res = deepseek_pbx.format_note(note, context='...')
"""
import json
import re
import time
import logging
import requests
from typing import Optional, Any
from dataclasses import dataclass

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

SETTINGS_PATH = '/opt/abpe/backend/settings.json'


# ============================================================
# PROMPTS (Fallback-Konstanten; spaeter DB-ueberschreibbar)
# ============================================================
DEFAULT_PROMPTS = {
    'protokoll_txt': {
        'system': (
            "Du bist ein praeziser Protokoll-Assistent fuer geschaeftliche "
            "Telefonkonferenzen. Schreibe ein sauberes, sachliches deutsches "
            "Protokoll. Keine Floskeln, keine erfundenen Inhalte."
        ),
        'user': (
            "[[KOPF]]Erstelle aus diesen groben Stichpunkten ein professionelles "
            "Konferenzprotokoll mit den Abschnitten: Teilnehmer, Ergebnisse, "
            "Offene Punkte, Aufgaben (mit Verantwortlichem und Frist, falls "
            "genannt). Bewahre alle Fakten, formuliere in ganzen Saetzen, "
            "erfinde nichts.\n\nStichpunkte:\n[[NOTES]]"
        ),
    },
    'protokoll_json': {
        'system': (
            "Du bist ein praeziser Protokoll-Assistent fuer geschaeftliche "
            "Telefonkonferenzen. Antworte AUSSCHLIESSLICH mit JSON, ohne "
            "Markdown, ohne Vorspann."
        ),
        'user': (
            "[[KOPF]]Erstelle aus diesen groben Stichpunkten ein strukturiertes "
            "Konferenzprotokoll. Bewahre alle Fakten, formuliere sachlich in "
            "ganzen Saetzen, erfinde nichts.\n\nStichpunkte:\n[[NOTES]]\n\n"
            'Gib GENAU dieses JSON zurueck:\n'
            '{"titel": "", "datum": "", "teilnehmer": [], '
            '"ergebnisse": [], "offene_punkte": [], '
            '"aufgaben": [{"was": "", "wer": "", "faellig": ""}]}'
        ),
    },
    'notiz': {
        'system': (
            "Du bist ein knapper, sachlicher Assistent fuer Telefon-/Gespraechs"
            "notizen. Formuliere die Stichpunkte zu einer klaren, kurzen Notiz "
            "in ganzen Saetzen. Keine Floskeln, nichts erfinden, Fakten bewahren."
        ),
        'user': (
            "[[CONTEXT]]Formuliere aus diesen Stichpunkten eine saubere "
            "Gespraechsnotiz:\n\n[[NOTES]]"
        ),
    },
    'summarize': {
        'system': "Du bist ein knapper, sachlicher Assistent. Antworte auf Deutsch.",
        'user': "[[INSTRUCTION]]\n\n[[TEXT]]",
    },
}


def _get_prompt(key: str):
    """(system, user_template) — spaeter DB (PbxPrompt), jetzt Fallback-Konstanten."""
    d = DEFAULT_PROMPTS.get(key, {'system': '', 'user': ''})
    try:
        from apps.abpe_crm.models import PbxPrompt  # existiert erst spaeter
        row = PbxPrompt.objects.filter(key=key, aktiv=True).first()
        if row:
            return (row.system or d['system'], row.user_template or d['user'])
    except Exception:
        pass  # Model/DB nicht da -> Konstanten
    return (d['system'], d['user'])


def _fill(template: str, **kw) -> str:
    for k, v in kw.items():
        template = template.replace('[[' + k.upper() + ']]', v or '')
    return template


@dataclass
class PbxAIResult:
    success: bool
    text: str = ""            # bei output='txt' / Notiz
    data: Any = None          # bei output='json'
    raw: str = ""
    error: Optional[str] = None
    processing_time: float = 0.0


class DeepSeekPBXService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or self._load_api_key()
        self.base_url = "https://api.deepseek.com/v1/chat/completions"
        self.model = "deepseek-chat"
        self.session = requests.Session()
        self.session.verify = False

    def _load_api_key(self) -> Optional[str]:
        try:
            with open(SETTINGS_PATH, 'r') as f:
                cfg = json.load(f)
            return cfg.get('ai_models', {}).get('deepseek', {}).get('api_key')
        except Exception as e:
            logger.warning(f'DeepSeek API-Key laden fehlgeschlagen: {e}')
            return None

    def is_available(self) -> bool:
        return bool(self.api_key)

    # ---- Roh-Call ----
    def _chat(self, system_prompt: str, user_prompt: str,
              temperature: float = 0.2, max_tokens: int = 2500) -> tuple:
        if not self.is_available():
            return '', 'Kein DeepSeek API-Key (settings.json)'
        try:
            r = self.session.post(
                self.base_url,
                headers={"Authorization": f"Bearer {self.api_key}",
                         "Content-Type": "application/json"},
                json={"model": self.model,
                      "messages": [{"role": "system", "content": system_prompt},
                                   {"role": "user", "content": user_prompt}],
                      "temperature": temperature, "max_tokens": max_tokens},
                timeout=90,
            )
            if r.status_code != 200:
                return '', f'HTTP {r.status_code}: {r.text[:200]}'
            return r.json()['choices'][0]['message']['content'], None
        except Exception as e:
            return '', str(e)

    # ---- JSON robust extrahieren ----
    @staticmethod
    def _extract_json(content: str):
        s = content.strip()
        if s.startswith('```'):
            s = re.sub(r'^```(?:json)?\s*', '', s)
            s = re.sub(r'\s*```$', '', s).strip()
        try:
            return json.loads(s)
        except Exception:
            pass
        for oc, cc in [('{', '}'), ('[', ']')]:
            start = s.find(oc)
            if start == -1:
                continue
            depth, in_str, esc = 0, False, False
            for i in range(start, len(s)):
                ch = s[i]
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
                if ch == oc:
                    depth += 1
                elif ch == cc:
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(s[start:i + 1])
                        except Exception:
                            break
        return None

    # ---- Protokoll ----
    def format_protocol(self, notes: str, meta: Optional[dict] = None,
                        output: str = 'txt') -> PbxAIResult:
        t0 = time.time()
        meta = meta or {}
        kopf = []
        if meta.get('titel'):
            kopf.append(f"Titel: {meta['titel']}")
        if meta.get('datum'):
            kopf.append(f"Datum: {meta['datum']}")
        if meta.get('teilnehmer'):
            tn = meta['teilnehmer']
            kopf.append("Teilnehmer: " + (", ".join(tn) if isinstance(tn, list) else str(tn)))
        kopf_txt = ("\n".join(kopf) + "\n\n") if kopf else ""

        key = 'protokoll_json' if output == 'json' else 'protokoll_txt'
        system, user_tpl = _get_prompt(key)
        user = _fill(user_tpl, kopf=kopf_txt, notes=notes)
        content, err = self._chat(system, user,
                                  temperature=0.1 if output == 'json' else 0.2)
        if err:
            return PbxAIResult(False, error=err, raw=content, processing_time=time.time() - t0)
        if output == 'json':
            data = self._extract_json(content)
            if data is None:
                return PbxAIResult(False, error='Kein JSON in Antwort', raw=content,
                                   processing_time=time.time() - t0)
            return PbxAIResult(True, data=data, raw=content, processing_time=time.time() - t0)
        return PbxAIResult(True, text=content.strip(), raw=content,
                           processing_time=time.time() - t0)

    # ---- Einzelne Notiz ----
    def format_note(self, note: str, context: Optional[str] = None) -> PbxAIResult:
        t0 = time.time()
        ctx = f"Kontext: {context}\n\n" if context else ""
        system, user_tpl = _get_prompt('notiz')
        user = _fill(user_tpl, context=ctx, notes=note)
        content, err = self._chat(system, user, temperature=0.2, max_tokens=1000)
        if err:
            return PbxAIResult(False, error=err, raw=content, processing_time=time.time() - t0)
        return PbxAIResult(True, text=content.strip(), raw=content,
                           processing_time=time.time() - t0)

    # ---- Generisch ----
    def summarize(self, text: str, instruction: str = "Fasse kurz zusammen.") -> PbxAIResult:
        t0 = time.time()
        system, user_tpl = _get_prompt('summarize')
        user = _fill(user_tpl, instruction=instruction, text=text)
        content, err = self._chat(system, user, temperature=0.2, max_tokens=800)
        if err:
            return PbxAIResult(False, error=err, processing_time=time.time() - t0)
        return PbxAIResult(True, text=content.strip(), raw=content,
                           processing_time=time.time() - t0)


deepseek_pbx = DeepSeekPBXService()

