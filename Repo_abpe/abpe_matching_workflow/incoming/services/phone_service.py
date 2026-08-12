"""
ABpE Matching Workflow — Click-to-Call via webdial.cgi (Issabel/Asterisk)
User-spezifische Extension aus UserSettings
"""
import logging
import requests
import re
from typing import Dict

logger = logging.getLogger(__name__)


def _global_phone_cfg() -> Dict:
    import json
    from pathlib import Path
    try:
        p = Path(__file__).resolve().parent.parent.parent.parent / 'settings.json'
        return json.loads(p.read_text(encoding='utf-8')).get('matching', {}).get('phone', {})
    except Exception:
        return {}


class PhoneService:
    """Click-to-Call via Asterisk/Issabel webdial.cgi"""

    def __init__(self, user=None):
        cfg = _global_phone_cfg()
        self.webdial_url = cfg.get('webdial_url', 'http://172.20.3.120/cgi-bin/webdial.cgi')
        self.context     = cfg.get('context',     'from-internal')
        self.timeout     = cfg.get('timeout',     10)

        # User-spezifische Extension aus UserSettings
        self.from_ext  = str(cfg.get('from_extension', 12))
        self.channel   = cfg.get('channel', 'SIP/12')
        self.user_name = None
        self.enabled   = True

        if user and hasattr(user, 'usersettings'):
            try:
                us = user.usersettings
                if us.phone_enabled and us.phone_extension:
                    self.from_ext  = us.phone_extension
                    self.channel   = f"SIP/{us.phone_extension}"
                    self.user_name = us.phone_display_name or user.get_full_name() or user.username
                    logger.info(f"PhoneService: User {user.username} → Extension {self.from_ext}")
                elif not us.phone_enabled:
                    self.enabled = False
                    logger.warning(f"PhoneService: User {user.username} hat Telefon deaktiviert")
            except Exception as e:
                logger.warning(f"PhoneService: UserSettings Fehler: {e}")

    def call(self, to: str, pin: str = None) -> Dict:
        """Initiiert Click-to-Call via webdial.cgi"""
        if not self.enabled:
            return {'success': False, 'error': 'Telefon für diesen User nicht aktiviert'}

        clean = self._clean_number(to)
        if not clean:
            return {'success': False, 'error': 'Ungültige Telefonnummer'}

        params = {
            'from':    self.from_ext,
            'channel': self.channel,
            'context': self.context,
            'timeout': self.timeout,
            'to':      clean,
        }

        # PIN falls angegeben (Issabel AMI Auth)
        if pin:
            params['pin'] = pin

        try:
            resp = requests.get(
                self.webdial_url,
                params=params,
                timeout=5,
                verify=False,
            )
            success = resp.status_code == 200
            logger.info(f"Click-to-Call: {self.from_ext} → {clean} — HTTP {resp.status_code}")
            return {
                'success':    success,
                'to':         clean,
                'from':       self.from_ext,
                'status':     resp.status_code,
                'caller':     self.user_name,
            }
        except Exception as e:
            logger.error(f"Click-to-Call Fehler: {e}")
            return {'success': False, 'error': str(e), 'to': clean}

    def _clean_number(self, number: str) -> str:
        cleaned = re.sub(r'[^\d+]', '', number)
        cleaned = cleaned.replace('+', '00')
        return cleaned if len(cleaned) >= 6 else ''
