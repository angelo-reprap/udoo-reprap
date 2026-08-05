"""
MCID Regel 1 — Validator für erlaubte HTML-Tags und CSS (inline).

Prüft Modul-Hüllen und Vorlagen-HTML. ``{{block:…}}`` / ``{var}`` werden
vor dem Tag-Scan ausgeblendet.
"""
from __future__ import annotations

import re
from typing import Any

ALLOWED_TAGS = frozenset({
    'table', 'tr', 'td', 'th', 'tbody', 'thead', 'tfoot',
    'img', 'a', 'p', 'br', 'span',
    'strong', 'b', 'em', 'i', 'u',
    'h1', 'h2', 'h3',
    'ul', 'ol', 'li',
    'div', 'hr',
    # oft in Signaturen / Legacy
    'font', 'center',
})

ALLOWED_ATTRS = frozenset({
    'width', 'height', 'align', 'valign', 'bgcolor',
    'cellpadding', 'cellspacing', 'border', 'role',
    'alt', 'href', 'target', 'src', 'style', 'colspan', 'rowspan',
    'class',  # Studio-Vorschau; Warnung wenn in Modul-Hülle
})

ALLOWED_CSS = frozenset({
    'font-family', 'font-size', 'font-weight', 'font-style',
    'line-height', 'text-align', 'text-decoration', 'color',
    'padding', 'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
    'margin', 'margin-top', 'margin-right', 'margin-bottom', 'margin-left',
    'width', 'height', 'max-width', 'min-width',
    'background-color', 'background',
    'border', 'border-top', 'border-right', 'border-bottom', 'border-left',
    'border-collapse', 'border-spacing', 'border-color', 'border-style', 'border-width',
    'vertical-align', 'display',
})

# Regel 1: nicht in der MCID-Basis
FORBIDDEN_CSS = frozenset({
    'border-radius', 'box-shadow', 'text-shadow',
    'position', 'float', 'flex', 'flex-direction', 'flex-wrap',
    'grid', 'grid-template-columns', 'gap', 'transform',
    'opacity',  # oft ok, aber unzuverlässig — warning
})

_TAG_RE = re.compile(r'</?([a-zA-Z][a-zA-Z0-9]*)\b([^>]*)/?>', re.I)
_ATTR_RE = re.compile(r'([a-zA-Z_:][-a-zA-Z0-9_:]*)\s*=\s*("([^"]*)"|\'([^\']*)\'|[^\s>]+)')
_STYLE_PROP_RE = re.compile(r'([a-zA-Z-]+)\s*:')
_BLOCK_TOKEN_RE = re.compile(r'\{\{/?(?:block:[^}]+|[^}]+)\}\}')
_VAR_TOKEN_RE = re.compile(r'\{[a-zA-Z_][a-zA-Z0-9_]*\}')


def _strip_tokens(html: str) -> str:
    t = _BLOCK_TOKEN_RE.sub(' ', html or '')
    t = _VAR_TOKEN_RE.sub(' ', t)
    return t


class McidValidator:
    """Regel-1-Check für HTML-Bausteine / Vorlagen."""

    def validate(self, html: str, *, context: str = 'template') -> dict[str, Any]:
        """
        Returns:
            ok, errors[{code,message,detail}], warnings[{…}], summary
        """
        errors: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        raw = html or ''
        scan = _strip_tokens(raw)

        if re.search(r'(?i)<script\b', scan):
            errors.append({
                'code': 'tag_script',
                'message': 'Script-Tags sind nicht erlaubt',
                'detail': 'script',
            })
        if re.search(r'(?i)<style\b', scan):
            errors.append({
                'code': 'tag_style',
                'message': 'Externe/eingebettete <style>-Blöcke sind nicht erlaubt (nur inline style)',
                'detail': 'style',
            })

        for m in _TAG_RE.finditer(scan):
            tag = m.group(1).lower()
            attrs_blob = m.group(2) or ''
            if tag in ('script', 'style'):
                continue  # schon als Fehler
            if tag not in ALLOWED_TAGS:
                errors.append({
                    'code': 'tag_forbidden',
                    'message': f'Tag <{tag}> ist nach MCID Regel 1 nicht erlaubt',
                    'detail': tag,
                })
                continue

            if tag == 'div' and context == 'module':
                warnings.append({
                    'code': 'div_layout',
                    'message': '<div> nur für Inhalt, nicht als Hauptlayout (Tabellen bevorzugen)',
                    'detail': 'div',
                })

            for am in _ATTR_RE.finditer(attrs_blob):
                attr = am.group(1).lower()
                val = am.group(3) if am.group(3) is not None else (am.group(4) or am.group(2) or '')
                if attr.startswith('on'):
                    errors.append({
                        'code': 'attr_event',
                        'message': f'Event-Attribut {attr}=… ist nicht erlaubt',
                        'detail': attr,
                    })
                    continue
                if attr not in ALLOWED_ATTRS and attr not in ('id', 'name', 'title'):
                    warnings.append({
                        'code': 'attr_unknown',
                        'message': f'Attribut {attr} ist nicht in der MCID-Basis',
                        'detail': attr,
                    })
                if attr == 'style':
                    self._check_styles(val, errors, warnings)

        # Kurzchecks ohne Tag-Kontext
        if re.search(r'(?i)display\s*:\s*flex', scan):
            errors.append({
                'code': 'css_flex',
                'message': 'display:flex ist für E-Mail-Layout nicht erlaubt',
                'detail': 'display:flex',
            })
        if re.search(r'(?i)display\s*:\s*grid', scan):
            errors.append({
                'code': 'css_grid',
                'message': 'display:grid ist für E-Mail-Layout nicht erlaubt',
                'detail': 'display:grid',
            })
        if re.search(r'(?i)border-radius\s*:', scan):
            errors.append({
                'code': 'css_radius',
                'message': 'border-radius ist in der MCID-Basis nicht erlaubt',
                'detail': 'border-radius',
            })

        # Deduplizieren
        errors = _dedupe(errors)
        warnings = _dedupe(warnings)
        ok = len(errors) == 0
        return {
            'ok': ok,
            'overall_ok': ok,
            'errors': errors,
            'warnings': warnings,
            'summary': (
                'MCID Regel 1 OK' if ok else
                f'{len(errors)} Fehler, {len(warnings)} Hinweise'
            ),
            'rule': 'MCID Regel 1 — Tags/CSS',
        }

    def _check_styles(
        self, style: str, errors: list[dict], warnings: list[dict],
    ) -> None:
        for pm in _STYLE_PROP_RE.finditer(style or ''):
            prop = pm.group(1).lower()
            if prop in FORBIDDEN_CSS:
                if prop in ('border-radius', 'position', 'float') or prop.startswith('flex') or prop.startswith('grid'):
                    errors.append({
                        'code': 'css_forbidden',
                        'message': f'CSS-Eigenschaft {prop} ist nach MCID Regel 1 nicht erlaubt',
                        'detail': prop,
                    })
                else:
                    warnings.append({
                        'code': 'css_risky',
                        'message': f'CSS-Eigenschaft {prop} ist unzuverlässig in E-Mails',
                        'detail': prop,
                    })
            elif prop not in ALLOWED_CSS and not prop.startswith('border') and not prop.startswith('padding') and not prop.startswith('margin'):
                warnings.append({
                    'code': 'css_unknown',
                    'message': f'CSS-Eigenschaft {prop} ist nicht in der MCID-Basis gelistet',
                    'detail': prop,
                })


def _dedupe(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, str]] = []
    for it in items:
        key = (it.get('code', ''), it.get('detail', ''))
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out
