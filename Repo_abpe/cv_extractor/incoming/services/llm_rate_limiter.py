"""
llm_rate_limiter.py - Zentraler LLM-Call-Manager

Verhindert Ueberschreitung des DeepSeek API Limits (max 10 parallele Calls).
Nutzt Redis INCR/DECR fuer atomare Slot-Verwaltung.

Slot-Berechnung:
  max_slots = settings.json["pipeline"]["parallel_workers_projects"]
  Beispiel:  10 Slots total — alle LLM-Calls laufen durch denselben Zaehler
  Redis zaehlt ALLE aktiven Calls (db_enricher + skill_graph + self_learning)

Verwendung:
  from apps.cv_extractor.services.llm_rate_limiter import llm_slot

  with llm_slot():
      result = deepseek_api.extract(prompt)
"""

import json
import logging
import os
import time
from contextlib import contextmanager

logger = logging.getLogger(__name__)

REDIS_KEY     = 'abpe:llm:active_slots'
SLOT_TIMEOUT  = 300   # Max 5 Minuten pro Slot (Sicherheit gegen Leaks)
WAIT_INTERVAL = 0.5   # Sekunden zwischen Slot-Pruefungen
MAX_WAIT      = 120   # Max 2 Minuten warten auf freien Slot


def _get_max_slots() -> int:
    """Liest parallel_workers_projects aus settings.json und zieht 2 ab."""
    try:
        from django.conf import settings
        cfg_path = os.path.join(settings.BASE_DIR, 'settings.json')
        with open(cfg_path) as f:
            cfg = json.load(f)
        workers = int(cfg.get('pipeline', {}).get('parallel_workers_projects', 10))
        slots = max(1, workers)
        return slots
    except Exception:
        return 8  # Fallback


def _get_redis():
    """Redis-Client aus Django Cache."""
    try:
        from django_redis import get_redis_connection
        return get_redis_connection('default')
    except Exception as e:
        logger.warning(f"Redis nicht verfuegbar: {e}")
        return None


def get_active_slots() -> int:
    """Gibt aktuell belegte LLM-Slots zurueck."""
    r = _get_redis()
    if not r:
        return 0
    try:
        val = r.get(REDIS_KEY)
        return int(val) if val else 0
    except Exception:
        return 0


def get_available_slots() -> int:
    """Gibt verfuegbare LLM-Slots zurueck."""
    return max(0, _get_max_slots() - get_active_slots())


@contextmanager
def llm_slot(label: str = ''):
    """
    Context Manager: reserviert einen LLM-Slot, gibt ihn nach dem Call frei.

    Wartet bis ein Slot verfuegbar ist (max MAX_WAIT Sekunden).
    Gibt Slot immer frei — auch bei Exceptions.

    Verwendung:
        with llm_slot(label='self_learning:OSPF'):
            result = deepseek_api.extract(prompt)
    """
    r        = _get_redis()
    max_slots = _get_max_slots()
    acquired  = False
    waited    = 0.0

    try:
        if r:
            # Warten bis Slot frei
            while waited < MAX_WAIT:
                current = int(r.get(REDIS_KEY) or 0)
                if current < max_slots:
                    # Atomares INCR — thread-safe
                    new_val = r.incr(REDIS_KEY)
                    # TTL setzen gegen Leaks (falls Prozess stirbt)
                    r.expire(REDIS_KEY, SLOT_TIMEOUT)
                    acquired = True
                    if label:
                        logger.debug(
                            f"LLM-Slot belegt [{new_val}/{max_slots}]: {label}"
                        )
                    break
                else:
                    if waited == 0:
                        logger.info(
                            f"LLM-Slots voll ({current}/{max_slots}), "
                            f"warte auf freien Slot... [{label}]"
                        )
                    time.sleep(WAIT_INTERVAL)
                    waited += WAIT_INTERVAL

            if not acquired:
                logger.warning(
                    f"LLM-Slot Timeout nach {waited}s [{label}] — "
                    f"fahre ohne Slot-Tracking fort"
                )
        else:
            # Redis nicht verfuegbar → ohne Tracking fortfahren
            logger.debug("Redis nicht verfuegbar — kein Slot-Tracking")

        yield

    finally:
        if acquired and r:
            try:
                new_val = r.decr(REDIS_KEY)
                # Nie unter 0 gehen
                if new_val < 0:
                    r.set(REDIS_KEY, 0)
                if label:
                    logger.debug(
                        f"LLM-Slot freigegeben [{max(0,new_val)}/{max_slots}]: {label}"
                    )
            except Exception as e:
                logger.warning(f"LLM-Slot Freigabe fehlgeschlagen: {e}")
