"""Validierung von KI-Ausgaben."""
from __future__ import annotations

import re
from typing import Any

from apps.abpe_ki_wiz.providers.base import ValidationResult

_VAR_RE = re.compile(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}')
_BLOCK_RE = re.compile(r'\{\{block:([a-zA-Z0-9_-]+)\}\}')
_CLOSE_BLOCK_RE = re.compile(r'\{\{/block\}\}')


def extract_vars(text: str) -> set[str]:
    return set(_VAR_RE.findall(text or ''))


def extract_blocks(text: str) -> set[str]:
    """Modul-/Block-IDs; schließendes {{/block}} ist kein Identifier."""
    return set(_BLOCK_RE.findall(text or ''))


def has_unbalanced_blocks(text: str) -> bool:
    opens = len(_BLOCK_RE.findall(text or ''))
    # Paare zählen: jedes {{/block}} schließt eines; Selbstschließer bleiben „offen“ ok
    closes = len(_CLOSE_BLOCK_RE.findall(text or ''))
    return closes > opens


def validate_email_module_output(
    result: dict[str, Any],
    allowed_vars: set[str],
) -> ValidationResult:
    """Validierung für wizard_id=email_module (Fragment, keine vollständige Mail)."""
    errors: list[str] = []
    warnings: list[str] = []
    html = result.get('html_body') or ''
    text = result.get('text_body') or ''
    if not html.strip():
        errors.append('html_body ist leer')
    for var in extract_vars(html + ' ' + text):
        if var not in allowed_vars:
            warnings.append(f'Variable {{{var}}} — bitte prüfen')
    # Module sollen selten andere {{block:}} einbetten
    nested = extract_blocks(html)
    if nested:
        warnings.append(
            'Modul enthält {{block:…}} — meist unerwünscht in Modul-Fragmenten: '
            + ', '.join(sorted(nested))
        )
    if re.search(r'(?i)border-radius|display:\s*flex|display:\s*grid|<script', html):
        errors.append('MCID: border-radius / flex / grid / script nicht erlaubt')
    ident = (result.get('identifier') or '').strip()
    if ident and not re.fullmatch(r'[a-z][a-z0-9_]{1,59}', ident):
        warnings.append('identifier sollte snake_case sein (a-z, 0-9, _)')
    return ValidationResult(ok=not errors, errors=errors, warnings=warnings)


def validate_email_template_output(
    result: dict[str, Any],
    allowed_vars: set[str],
    allowed_blocks: set[str],
) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    subject = result.get('subject') or ''
    html = result.get('html_body') or ''
    text = result.get('text_body') or ''
    combined = ' '.join([subject, html, text])

    for var in extract_vars(combined):
        if var not in allowed_vars:
            errors.append(f'Unbekannte Variable: {{{var}}}')

    for block in extract_blocks(combined):
        if block not in allowed_blocks:
            errors.append(f'Unbekanntes Modul: {{{{block:{block}}}}}')

    if not html.strip():
        errors.append('html_body ist leer')

    return ValidationResult(ok=not errors, errors=errors, warnings=warnings)
