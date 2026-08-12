"""
Gemeinsame Hilfen für HTML/Word-Darstellung (kein Schema).
"""
from __future__ import annotations

import base64
import logging
import mimetypes
import os
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def looks_like_course(name: str) -> bool:
    """
    Heuristik: Kurs/Schulung vs. Zertifikat.
    Vermeidet False-Positives wie 'MCSE – Microsoft Certified System Engineer'
    (enthält 'engineer', ist aber ein Zertifikat).
    """
    x = (name or '').strip().lower()
    if not x:
        return False
    # Klare Kurs-Wörter
    if re.search(r'\b(kurs|schulung|schulungen|training|lehrgang|workshop)\b', x):
        return True
    # Vendor-Kurs mit Versionsnummer + Rolle (Fortinet-Stil)
    if re.search(r'\b\d+\.\d+\b', x) and re.search(
        r'\b(administrator|analyst|operator|engineer|support|core)\b', x
    ):
        return True
    # Fortinet/Kurz-Prefixe
    if re.match(r'^(fcp|fcss|fca|nse)\b', x):
        return True
    # "Certified …" / MCSE/CCNA-Codes → Zertifikat, kein Kurs
    if re.search(r'\bcertified\b', x):
        return False
    if re.match(
        r'^(ccna|ccnp|ccie|ccvp|ciss|mcse|mcsa|clp|cls|lpic|ada|ihk)\b',
        x,
    ):
        return False
    return False


def format_education_line(degree: str, institution: str = '',
                          description: str = '') -> str:
    """Degree + optionale Institution + Curriculum (description) als eine Zeile."""
    desc = (degree or '').strip()
    inst = (institution or '').strip()
    if inst and inst.lower() not in desc.lower():
        desc = f'{desc} @ {inst}' if desc else inst
    curr = (description or '').strip()
    if curr and curr.lower() not in desc.lower():
        # Curriculum-Bullets kompakt anhängen
        curr_clean = re.sub(r'\s*;\s*', ' · ', curr)
        desc = f'{desc} — {curr_clean}' if desc else curr_clean
    return desc


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8')
    except OSError as e:
        logger.warning(f'Asset lesen fehlgeschlagen ({path}): {e}')
        return ''


def _file_as_data_uri(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    mime = mimetypes.guess_type(str(path))[0] or 'application/octet-stream'
    try:
        data = base64.b64encode(path.read_bytes()).decode('ascii')
        return f'data:{mime};base64,{data}'
    except OSError as e:
        logger.warning(f'Data-URI fehlgeschlagen ({path}): {e}')
        return None


def resolve_aid_asset_dirs(base_dir: str) -> dict:
    """Typische Pfade unter Django BASE_DIR / App."""
    base = Path(base_dir)
    app = base / 'apps' / 'cv_extractor'
    return {
        'style': app / 'static' / 'cv_extractor' / 'html' / 'aid-profile' / 'style.css',
        'script': app / 'static' / 'cv_extractor' / 'html' / 'aid-profile' / 'script.js',
        'script_en': app / 'static' / 'cv_extractor' / 'html' / 'aid-profile' / 'script-en.js',
        'logo_candidates': [
            base / 'data' / 'cv' / 'adds' / 'logo_abcona.png',
            app / 'static' / 'cv_extractor' / 'img' / 'logo_abcona.png',
            app / 'data' / 'cv' / 'adds' / 'logo_abcona.png',
            Path('/data/cv/adds/logo_abcona.png'),
        ],
    }


def make_html_offline_friendly(html: str, base_dir: str,
                               language: str = 'de') -> str:
    """
    Ersetzt absolute /static und /data Pfade durch Inline-CSS/JS und Data-URI-Logo.
    Damit file:// und Share-Pfade (X:/…/neu/cv/*.html) ohne Webserver funktionieren.
    """
    if not html:
        return html
    paths = resolve_aid_asset_dirs(base_dir)
    out = html

    # CSS inline
    css = _read_text(paths['style'])
    if css:
        out = re.sub(
            r'<link[^>]+href="[^"]*cv_extractor/html/aid-profile/style\.css"[^>]*>\s*',
            f'<style>\n{css}\n</style>\n',
            out,
            count=1,
            flags=re.IGNORECASE,
        )

    # JS inline (DE/EN)
    script_path = paths['script_en'] if (language or 'de').lower().startswith('en') else paths['script']
    # Fallback: whichever is referenced
    js = _read_text(script_path) or _read_text(paths['script'])
    if js:
        out = re.sub(
            r'<script[^>]+src="[^"]*cv_extractor/html/aid-profile/script(?:-en)?\.js[^"]*"[^>]*>\s*</script>\s*',
            f'<script>\n{js}\n</script>\n',
            out,
            count=1,
            flags=re.IGNORECASE,
        )

    # Logo → data URI
    logo_uri = None
    for cand in paths['logo_candidates']:
        logo_uri = _file_as_data_uri(Path(cand))
        if logo_uri:
            break
    if logo_uri:
        out = re.sub(
            r'(<img[^>]+src=")(/data/cv/adds/logo_abcona\.png|/media/cv/adds/logo_abcona\.png)(")',
            rf'\1{logo_uri}\3',
            out,
            flags=re.IGNORECASE,
        )
    else:
        logger.warning('Logo für Offline-HTML nicht gefunden — Cover ohne Bild')

    return out
