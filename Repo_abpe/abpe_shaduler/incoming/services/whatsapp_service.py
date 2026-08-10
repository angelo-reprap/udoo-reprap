"""whatsapp_service — Übergangslösung bis Composer (Kap. 6): wa.me-Link bauen."""
from __future__ import annotations

from urllib.parse import quote


def build_whatsapp_link(phone: str, text: str = '') -> str:
    """
    Öffnet WhatsApp Web/App mit vorgefülltem Text.
    phone: E.164 ohne + oder mit +, Leerzeichen/Sonderzeichen werden gestrippt.
    """
    digits = ''.join(ch for ch in (phone or '') if ch.isdigit())
    if not digits:
        return ''
    if text:
        return f'https://wa.me/{digits}?text={quote(text)}'
    return f'https://wa.me/{digits}'


def ping():
    return True
