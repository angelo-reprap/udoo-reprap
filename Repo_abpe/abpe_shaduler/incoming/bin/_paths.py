#!/usr/bin/env python3
"""Gemeinsame Pfade für Shaduler-i18n-Tools.

Sprachdateien liegen im Portal-i18n-Baum (abpe_ui), Modul-Unterordner:

  Live:
    /opt/abpe/backend/apps/abpe_ui/static/abpe_ui/i18n/<lang>/modules/shaduler/shaduler.json

  Repo:
    Repo_abpe/abpe_ui/incoming/i18n/<lang>/modules/shaduler/shaduler.json

Aufruf (Live):
  cd /opt/abpe/backend
  python3 apps/abpe_shaduler/bin/i18n_translator.py --check
"""
from __future__ import annotations

import os
from pathlib import Path

MODULE_REL = Path("modules") / "shaduler"
REF_LANG = "de"

# /opt/abpe/backend  bzw. Override
BASE_DIR = Path(os.environ.get("ABPE_BACKEND", "/opt/abpe/backend")).resolve()
SETTINGS = BASE_DIR / "settings.json"

# Script: .../apps/abpe_shaduler/bin/_paths.py  → parents[1]=abpe_shaduler, [2]=apps
_BIN = Path(__file__).resolve().parent
_APP = _BIN.parent  # apps/abpe_shaduler (live) oder .../incoming (repo)
_THIS_IS_REPO = (_APP.name == "incoming")


def resolve_i18n_dir() -> Path:
    env = os.environ.get("SHADULER_I18N_DIR")
    if env:
        return Path(env).resolve()

    live = BASE_DIR / "apps" / "abpe_ui" / "static" / "abpe_ui" / "i18n"
    if live.is_dir():
        return live

    # Repo: Repo_abpe/abpe_shaduler/incoming/bin → Repo_abpe/abpe_ui/incoming/i18n
    if _THIS_IS_REPO:
        repo = _APP.parent.parent / "abpe_ui" / "incoming" / "i18n"
        if repo.is_dir():
            return repo.resolve()

    return live


def resolve_module_json() -> Path:
    env = os.environ.get("SHADULER_MODULE_JSON")
    if env:
        return Path(env).resolve()

    live = (
        BASE_DIR
        / "apps"
        / "abpe_ui"
        / "templates"
        / "abpe_ui"
        / "modules"
        / "shaduler"
        / "module.json"
    )
    if live.is_file():
        return live

    if _THIS_IS_REPO:
        repo = (
            _APP.parent.parent
            / "abpe_ui"
            / "incoming"
            / "modules"
            / "shaduler"
            / "module.json"
        )
        if repo.is_file():
            return repo.resolve()

    return live


def resolve_translator() -> Path:
    return _BIN / "i18n_translator.py"


def module_dir(lang: str, i18n_dir: Path | None = None) -> Path:
    root = i18n_dir or resolve_i18n_dir()
    return root / lang / MODULE_REL


def shaduler_json(lang: str, i18n_dir: Path | None = None) -> Path:
    return module_dir(lang, i18n_dir) / "shaduler.json"
