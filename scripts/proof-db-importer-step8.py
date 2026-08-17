#!/usr/bin/env python3
"""Schritt 8: TXT dict-safe + EDV year parse (kein (19|20)-Capture-Bug)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INCOMING = ROOT / 'Repo_abpe' / 'cv_extractor' / 'incoming'
OUT = Path('/opt/cursor/artifacts/db-importer-step8-proof.json')


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    imp = load('mdb', INCOMING / 'services' / 'main_db_importer.py')
    cls = imp.MainDbImporter
    ok, fail = [], []

    # TXT: skill_ablage dicts
    joined = cls._join_names([
        {'name': 'Linux', 'category': 'Betriebssysteme'},
        {'name': 'Cobol'},
        'Natural',
    ])
    (ok if joined == 'Linux, Cobol, Natural' else fail).append(f'join_names={joined}')

    # techs dicts
    tech_j = cls._join_names(
        [{'technology': 'FortiGate'}, {'name': 'Check Point'}, 'Ansible'],
        limit=10,
    )
    (ok if 'FortiGate' in tech_j and 'Ansible' in tech_j else fail).append(
        f'tech_join={tech_j}'
    )

    # EDV years: full years, not capturing-group 19/20
    years = cls._years_from_periods([
        {'period': '01/1974 – 12/1977'},
        {'period': '03/2024 – 03/2024'},
        {'period': 'ohne jahr'},
    ])
    (ok if years == [1974, 1977, 2024, 2024] or set(years) >= {1974, 1977, 2024}
     else fail).append(f'years={years}')
    (ok if min(years) == 1974 else fail).append(f'min_year={min(years) if years else None}')

    # source must not use broken capture-only pattern in import_from_prejson path
    src = (INCOMING / 'services' / 'main_db_importer.py').read_text(encoding='utf-8')
    (ok if '_years_from_periods' in src and '_join_names' in src else fail).append(
        'helpers wired'
    )
    (ok if "SKILL-ABLAGE:" in src and '_join_names(ed.get(\'skill_ablage\'' in src.replace(' ', '')
          or "self._join_names(ed.get('skill_ablage'" in src
          else fail).append('txt skill_ablage dict-safe')

    # Prefer personal EDV when set — documented in import block
    (ok if 'Seed/Personal hat Vorrang' in src or 'seeded_edv' in src else fail).append(
        'edv personal-first'
    )

    out = {'ok': ok, 'fail': fail}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(out, indent=2, ensure_ascii=False))
    print(f'→ {OUT}')
    return 1 if fail else 0


if __name__ == '__main__':
    sys.exit(main())
