#!/usr/bin/env python3
"""Offline-Proof: Perioden-Anker (Range vs Soft-Wrap-Split) für compare_aid_neu_cv."""
from __future__ import annotations

import re
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD = (
    ROOT
    / 'Repo_abpe/cv_extractor/incoming/management/commands/compare_aid_neu_cv.py'
)


def _load_helpers():
    """Django-frei: nur Helper-Funktionen aus der Command-Datei ausführen."""
    src = MOD.read_text(encoding='utf-8')
    cut = src.find('\nclass Command')
    if cut < 0:
        raise RuntimeError('class Command nicht gefunden')
    stub = types.ModuleType('django.core.management.base')
    stub.BaseCommand = object  # type: ignore
    sys.modules.setdefault('django', types.ModuleType('django'))
    sys.modules.setdefault('django.core', types.ModuleType('django.core'))
    sys.modules.setdefault(
        'django.core.management', types.ModuleType('django.core.management')
    )
    sys.modules['django.core.management.base'] = stub
    ns: dict = {'__name__': 'compare_helpers', 're': re}
    exec(compile(src[:cut], str(MOD), 'exec'), ns)
    return ns


def main() -> int:
    m = _load_helpers()
    # Typischer PDF-Soft-Wrap: Monate ohne Bindestrich in einer Zeile →
    # Roh-Set hat Einzelmonate; neu/cv hat saubere Ranges.
    orig = (
        "Berufliche Erfahrungen\n"
        "01/2015\n"
        "06/2018 Firewall Support\n"
        "02/2006 - 04/2008 Netzwerk\n"
        "Geburtsjahr: 1970\n"
        "Windows 2012/2019\n"
    )
    neu = (
        "Berufliche Erfahrungen\n"
        "01/2015 - 06/2018 Firewall Support\n"
        "02/2006 - 04/2008 Netzwerk\n"
        "Geburtsjahr: 1970\n"
        "Windows 2012/2019\n"
    )

    raw_o = set(m['_periods'](orig))
    raw_n = set(m['_periods'](neu))
    raw_missing = sorted(raw_o - raw_n)

    anc_o = m['_period_anchors'](orig)
    anc_n = m['_period_anchors'](neu)
    anc_missing = sorted(anc_o - anc_n)

    print('=== RAW set-diff (alt, false-positive-anfällig) ===')
    print(f'orig={sorted(raw_o)}')
    print(f'neu ={sorted(raw_n)}')
    print(f'missing={raw_missing}')

    print()
    print('=== ANCHOR set-diff (neu) ===')
    print(f'orig={sorted(anc_o)}')
    print(f'neu ={sorted(anc_n)}')
    print(f'missing={anc_missing}')

    assert '01/2015' in anc_o and '06/2018' in anc_o
    assert not anc_missing, f'unerwartet missing: {anc_missing}'
    assert raw_missing, 'erwartet: Roh-Diff hat Split-False-Positives'

    print()
    print('OK: Anker-Norm entfernt Soft-Wrap-Range False-Positives')
    return 0


if __name__ == '__main__':
    sys.exit(main())
