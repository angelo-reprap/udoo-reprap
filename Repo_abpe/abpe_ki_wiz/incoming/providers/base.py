"""
WizardDomainProvider — Interface für Fach-Apps.

Implementierung in z. B. apps.abpe_email_studio.wizard.provider (Phase 1).
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationResult:
    ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class WizardDomainProvider(ABC):
    """Jede Domäne (Email, Matching, Doc) implementiert diese Schnittstelle."""

    wizard_id: str = ''
    title: str = ''
    description: str = ''

    def as_dict(self) -> dict[str, Any]:
        return {
            'wizard_id': self.wizard_id,
            'title': self.title,
            'description': self.description,
        }

    @abstractmethod
    def get_catalog(self, **kwargs) -> dict[str, Any]:
        """
        Dynamischer Katalog aus DB/Registry:
        variables, modules, enums, layout_rules, …
        """

    @abstractmethod
    def get_question_catalog(self) -> list[dict[str, Any]]:
        """Klärfragen-Katalog (JSON-Struktur) für diesen Wizard."""

    def resolve_questions(
        self,
        briefing: str,
        answers: dict[str, Any] | None = None,
        analyze_result: dict[str, Any] | None = None,
    ) -> list[str]:
        """
        Gibt question_ids zurück, die noch gestellt werden müssen.
        Default: aus analyze_result.missing_topics.
        """
        answers = answers or {}
        missing = []
        if analyze_result:
            missing = list(analyze_result.get('missing_topics') or [])
        catalog_ids = {q['id'] for q in self.get_question_catalog()}
        return [qid for qid in missing if qid in catalog_ids and qid not in answers]

    @abstractmethod
    def build_checklist(self, answers: dict[str, Any]) -> list[str]:
        """Hakenliste für KI-Prompt aus Antworten + Domänenregeln."""

    def validate_output(self, result: dict[str, Any]) -> ValidationResult:
        """Optional überschreiben — Post-KI-Validierung."""
        return ValidationResult(ok=True)

    def apply_result(
        self,
        result: dict[str, Any],
        session_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Mappt KI-Ergebnis auf Ziel-UI (Editor-Felder, CRM-Formular, …).
        Phase 0: Default passthrough.
        """
        return result

    def default_meta_suggestions(
        self,
        briefing: str,
        answers: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Regelbasierte Metadaten wenn KI ausfällt."""
        answers = answers or {}
        scope = answers.get('S1') or answers.get('app_scope') or 'general'
        name = (briefing or '')[:80].strip() or 'Neue Vorlage'
        ident = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')[:60] or 'new_template'
        return {
            'name': name,
            'identifier': ident,
            'subject': '{subject}',
            'description': (briefing or '')[:500],
            'app_scope': scope,
            'event_type': answers.get('S2') or 'general',
            'sender_mode': answers.get('A1') or 'USER',
            'signature_mode': answers.get('G1') or 'USER',
            'status': 'DRAFT',
            'source': 'rules',
        }
