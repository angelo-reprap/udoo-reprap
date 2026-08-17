"""
Gemeinsame Hilfen für HTML/Word-Darstellung (kein Schema).
"""
from __future__ import annotations

import base64
import logging
import mimetypes
import re
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# App-Root: …/apps/cv_extractor (unabhängig von settings.BASE_DIR)
_APP_ROOT = Path(__file__).resolve().parent.parent


def looks_like_course(name: str) -> bool:
    """
    Heuristik: Kurs/Schulung vs. Zertifikat.
    Vermeidet False-Positives wie 'MCSE – Microsoft Certified System Engineer'
    (enthält 'engineer', ist aber ein Zertifikat).
    """
    x = (name or '').strip().lower()
    if not x:
        return False
    if re.search(r'\b(kurs|schulung|schulungen|training|lehrgang|workshop)\b', x):
        return True
    if re.search(r'\b\d+\.\d+\b', x) and re.search(
        r'\b(administrator|analyst|operator|engineer|support|core)\b', x
    ):
        return True
    if re.match(r'^(fcp|fcss|fca|nse)\b', x):
        return True
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
        curr_clean = re.sub(r'\s*;\s*', ' · ', curr)
        desc = f'{desc} — {curr_clean}' if desc else curr_clean
    return desc


def _read_text(path: Path) -> str:
    try:
        if path.is_file():
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


def _first_existing(candidates: List[Path]) -> Optional[Path]:
    for p in candidates:
        try:
            if p.is_file():
                return p
        except OSError:
            continue
    return None


def _django_find_static(rel: str) -> Optional[Path]:
    """STATICFILES finder, falls Django verfügbar."""
    try:
        from django.contrib.staticfiles import finders
        found = finders.find(rel)
        if found:
            return Path(found)
    except Exception:
        pass
    return None


def resolve_aid_assets(base_dir: str = '') -> dict:
    """CSS/JS/Logo-Pfade — App-lokal zuerst, dann BASE_DIR / Django finders."""
    base = Path(base_dir) if base_dir else Path()
    app = _APP_ROOT
    static_aid = app / 'static' / 'cv_extractor' / 'html' / 'aid-profile'

    style = _first_existing([
        static_aid / 'style.css',
        base / 'apps' / 'cv_extractor' / 'static' / 'cv_extractor' / 'html' / 'aid-profile' / 'style.css',
        _django_find_static('cv_extractor/html/aid-profile/style.css') or Path(),
    ])
    script = _first_existing([
        static_aid / 'script.js',
        base / 'apps' / 'cv_extractor' / 'static' / 'cv_extractor' / 'html' / 'aid-profile' / 'script.js',
        _django_find_static('cv_extractor/html/aid-profile/script.js') or Path(),
    ])
    script_en = _first_existing([
        static_aid / 'script-en.js',
        base / 'apps' / 'cv_extractor' / 'static' / 'cv_extractor' / 'html' / 'aid-profile' / 'script-en.js',
        _django_find_static('cv_extractor/html/aid-profile/script-en.js') or Path(),
    ])

    logo_candidates = [
        base / 'data' / 'cv' / 'adds' / 'logo_abcona.png',
        app / 'data' / 'cv' / 'adds' / 'logo_abcona.png',
        Path('/opt/abpe/backend/data/cv/adds/logo_abcona.png'),
        Path('/data/cv/adds/logo_abcona.png'),
        app / 'static' / 'cv_extractor' / 'img' / 'logo_abcona.png',
        _django_find_static('cv_extractor/img/logo_abcona.png') or Path(),
    ]
    # settings.STATIC_ROOT / MEDIA_ROOT falls gesetzt
    try:
        from django.conf import settings
        if getattr(settings, 'STATIC_ROOT', None):
            logo_candidates.insert(
                0, Path(settings.STATIC_ROOT) / 'cv_extractor' / 'img' / 'logo_abcona.png'
            )
        if getattr(settings, 'MEDIA_ROOT', None):
            logo_candidates.insert(
                0, Path(settings.MEDIA_ROOT) / 'cv' / 'adds' / 'logo_abcona.png'
            )
        # oft: BASE_DIR/data/...
        logo_candidates.insert(0, Path(settings.BASE_DIR) / 'data' / 'cv' / 'adds' / 'logo_abcona.png')
    except Exception:
        pass

    return {
        'style': style,
        'script': script,
        'script_en': script_en,
        'logo': _first_existing(logo_candidates),
    }


def is_html_offline(html: str) -> bool:
    """True wenn CSS/JS nicht mehr über /static geladen werden müssen."""
    if not html:
        return False
    if re.search(r'href=["\']/static/[^"\']*aid-profile/style\.css', html, re.I):
        return False
    if re.search(r'src=["\']/static/[^"\']*aid-profile/script', html, re.I):
        return False
    # Inline-CSS ist Pflichtmerkmal
    return '<style' in html.lower()


def repair_broken_css_bullets(html: str) -> str:
    """
    Repariert kaputte Pseudo-Bullets aus re.sub-Oktal-Escape.

    Ursache: CSS ``content: "\\2022"`` in ``re.sub``-Replacement → Python
    interpretiert ``\\202`` als Oktal (U+0082) + Literal ``2`` → Anzeige ``☐2``.
    """
    if not html or '\x82' not in html:
        return html
    # content: "\x822"  bzw. content: '\x822'
    out = re.sub(r'content:\s*(["\'])\x822\1', r"content: '•'", html)
    return out


def _has_broken_css_bullets(html: str) -> bool:
    return bool(html and '\x82' in html and re.search(r'content:\s*["\']\x822', html))


def _re_sub_literal(pattern: str, replacement: str, text: str,
                    count: int = 0, flags: int = 0) -> tuple:
    """
    re.subn mit Literal-Replacement (kein Backslash-/Gruppen-Parsing).

    Wichtig: CSS/JS mit ``\\2022`` o.ä. dürfen nicht durch re.sub als Escape
    interpretiert werden.
    """
    def _repl(_m: re.Match) -> str:
        return replacement

    return re.subn(pattern, _repl, text, count=count, flags=flags)


def make_html_offline_friendly(html: str, base_dir: str = '',
                               language: str = 'de',
                               force: bool = False) -> str:
    """
    Ersetzt absolute /static und /data Pfade durch Inline-CSS/JS und Data-URI-Logo.
    Damit file:// und Share-Pfade (X:/…/neu/cv/*.html) ohne Webserver funktionieren.

    force=True: vorhandenes Inline-CSS/JS neu einbetten (z.B. nach CSS-Fix).
    """
    if not html:
        return html

    # Immer zuerst bekannte Bullet-Korruption heilen (auch schon-offline)
    repaired_bullets = False
    repaired = repair_broken_css_bullets(html)
    if repaired != html:
        html = repaired
        repaired_bullets = True
        logger.info('Offline-HTML: kaputte CSS-Bullets (\\x82+2) repariert')

    if is_html_offline(html) and not force:
        return html

    assets = resolve_aid_assets(base_dir)
    out = html
    changed = []

    css = _read_text(assets['style']) if assets.get('style') else ''
    if css:
        style_tag = f'<style type="text/css">\n{css}\n</style>\n'
        if force and is_html_offline(out):
            # erstes aid-profile-ähnliches <style> ersetzen
            new_out, n = _re_sub_literal(
                r'<style\b[^>]*>[\s\S]*?</style>\s*',
                style_tag,
                out,
                count=1,
                flags=re.IGNORECASE,
            )
            if n:
                out = new_out
                changed.append('css-refresh')
            else:
                new_out, n = _re_sub_literal(
                    r'(</head>)',
                    style_tag + '</head>',
                    out,
                    count=1,
                    flags=re.IGNORECASE,
                )
                if n:
                    out = new_out
                    changed.append('css-refresh-fallback')
        else:
            new_out, n = _re_sub_literal(
                r'<link[^>]+href=["\'][^"\']*cv_extractor/html/aid-profile/style\.css[^"\']*["\'][^>]*>\s*',
                style_tag,
                out,
                count=1,
                flags=re.IGNORECASE,
            )
            if n:
                out = new_out
                changed.append('css')
            else:
                # Fallback: Link entfernen, Style vor </head>
                out = re.sub(
                    r'<link[^>]+href=["\'][^"\']*aid-profile/style\.css[^"\']*["\'][^>]*>\s*',
                    '',
                    out,
                    flags=re.IGNORECASE,
                )
                new_out, n = _re_sub_literal(
                    r'(</head>)',
                    style_tag + '</head>',
                    out,
                    count=1,
                    flags=re.IGNORECASE,
                )
                if n:
                    out = new_out
                changed.append('css-fallback')
    else:
        logger.warning(
            'Offline-HTML: style.css nicht gefunden (gesucht unter %s)',
            _APP_ROOT / 'static/cv_extractor/html/aid-profile',
        )

    use_en = (language or 'de').lower().startswith('en')
    script_path = assets.get('script_en') if use_en else assets.get('script')
    js = _read_text(script_path) if script_path else ''
    if not js and assets.get('script'):
        js = _read_text(assets['script'])
    if js:
        script_tag = f'<script type="text/javascript">\n{js}\n</script>\n'
        if force and '<script' in out.lower():
            # Inline-Script mit Page-Reorg ersetzen (aid-profile)
            new_out, n = _re_sub_literal(
                r'<script\b[^>]*>[\s\S]*?reorganizeExpPages[\s\S]*?</script>\s*',
                script_tag,
                out,
                count=1,
                flags=re.IGNORECASE,
            )
            if n:
                out = new_out
                changed.append('js-refresh')
        if 'js-refresh' not in changed:
            new_out, n = _re_sub_literal(
                r'<script[^>]+src=["\'][^"\']*cv_extractor/html/aid-profile/script(?:-en)?\.js[^"\']*["\'][^>]*>\s*</script>\s*',
                script_tag,
                out,
                count=1,
                flags=re.IGNORECASE,
            )
            if n:
                out = new_out
                changed.append('js')
            elif not force:
                out = re.sub(
                    r'<script[^>]+src=["\'][^"\']*aid-profile/script(?:-en)?\.js[^"\']*["\'][^>]*>\s*</script>\s*',
                    '',
                    out,
                    flags=re.IGNORECASE,
                )
                new_out, n = _re_sub_literal(
                    r'(</head>)',
                    script_tag + '</head>',
                    out,
                    count=1,
                    flags=re.IGNORECASE,
                )
                if n:
                    out = new_out
                changed.append('js-fallback')
    else:
        logger.warning('Offline-HTML: script.js nicht gefunden')

    logo_uri = _file_as_data_uri(assets['logo']) if assets.get('logo') else None
    if logo_uri:
        def _logo_repl_path(m: re.Match) -> str:
            return f'{m.group(1)}{logo_uri}{m.group(3)}'

        def _logo_repl_any(m: re.Match) -> str:
            return f'{m.group(1)}{logo_uri}{m.group(2)}'

        new_out, n = re.subn(
            r'(<img\b[^>]*\bsrc=["\'])(/?(?:data|media)/cv/adds/logo_abcona\.png)(["\'])',
            _logo_repl_path,
            out,
            flags=re.IGNORECASE,
        )
        if n:
            out = new_out
            changed.append('logo')
        else:
            new_out, n = re.subn(
                r'(<img\b[^>]*\bsrc=["\'])[^"\']*logo_abcona\.png(["\'])',
                _logo_repl_any,
                out,
                count=1,
                flags=re.IGNORECASE,
            )
            if n:
                out = new_out
                changed.append('logo-fallback')
    else:
        logger.warning('Offline-HTML: logo_abcona.png nicht gefunden')

    if changed:
        logger.info('Offline-HTML Assets eingebettet: %s', ', '.join(changed))
    elif not repaired_bullets and out == html:
        logger.warning(
            'Offline-HTML: keine Assets eingebettet — Datei bleibt server-abhängig'
        )

    return out


def write_html_offline(src: Path, dest: Path, base_dir: str = '',
                       language: str = 'de') -> Path:
    """HTML lesen, offline machen, nach dest schreiben."""
    html = src.read_text(encoding='utf-8')
    html = make_html_offline_friendly(html, base_dir=base_dir, language=language)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html, encoding='utf-8')
    return dest
