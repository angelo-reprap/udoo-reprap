"""Phase-0 Stub-Provider zum Testen der Registry und API."""
from __future__ import annotations

from typing import Any

from apps.abpe_ki_wiz.registry import register
from .base import WizardDomainProvider


class StubWizardProvider(WizardDomainProvider):
    wizard_id = '_stub'
    title = 'Stub (intern)'
    description = 'Nur für Phase-0-Tests — nicht in Produktion verwenden.'

    def get_catalog(self, **kwargs) -> dict[str, Any]:
        return {
            'variables': [],
            'modules': [],
            'note': 'Stub-Provider — Phase 1 liefert echte Kataloge',
        }

    def get_question_catalog(self) -> list[dict[str, Any]]:
        return [
            {
                'id': 'S1',
                'question': 'Stub: App-Bereich?',
                'type': 'select',
                'options': [{'value': 'general', 'label': 'Allgemein'}],
            },
        ]

    def build_checklist(self, answers: dict[str, Any]) -> list[str]:
        return ['Stub-Checklist — Phase 1 ersetzt dies']


# Registrierung beim Import (Phase 0)
register(StubWizardProvider())
