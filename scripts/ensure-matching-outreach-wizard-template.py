#!/usr/bin/env python
"""Deprecated wrapper — do not keep a second body for matching_outreach_wizard.

Kanban-Stage-Vorlagen (inkl. Outreach) leben in:
  scripts/ensure-matching-stage-templates.py

Altes SAFE-Script bleibt lauffähig, schreibt aber denselben Stand wie die
Stage-Vorlagen. Sonst driftet Email Studio auf eine alte Version.
"""
from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).with_name("ensure-matching-stage-templates.py")), run_name="__main__")
