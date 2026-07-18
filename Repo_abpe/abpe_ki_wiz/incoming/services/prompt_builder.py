"""Baut [[CONTEXT]]-JSON für KI-Prompts aus Provider + Session."""
from __future__ import annotations

from typing import Any

from apps.abpe_ki_wiz.providers.base import WizardDomainProvider
from apps.abpe_ki_wiz.services.json_utils import dumps_compact


def build_context_payload(
    provider: WizardDomainProvider,
    answers: dict[str, Any] | None = None,
    *,
    app_scope: str = '',
    identifier: str = '',
) -> dict[str, Any]:
    catalog = provider.get_catalog(app_scope=app_scope, identifier=identifier)
    checklist = provider.build_checklist(answers or {})
    return {
        'wizard_id': provider.wizard_id,
        'catalog': catalog,
        'checklist': checklist,
        'answers': answers or {},
        'question_catalog': provider.get_question_catalog(),
    }


def build_context_json(
    provider: WizardDomainProvider,
    answers: dict[str, Any] | None = None,
    **kwargs,
) -> str:
    return dumps_compact(build_context_payload(provider, answers, **kwargs))
