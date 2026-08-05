"""
Wizard-Provider-Registry.

Fach-Apps registrieren Provider in AppConfig.ready():
    from apps.abpe_ki_wiz.registry import register
    register(EmailTemplateWizardProvider())
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .providers.base import WizardDomainProvider

log = logging.getLogger('abpe_ki_wiz.registry')

_PROVIDERS: dict[str, WizardDomainProvider] = {}


class WizardNotRegisteredError(LookupError):
    pass


def register(provider: WizardDomainProvider) -> None:
    wizard_id = provider.wizard_id
    if wizard_id in _PROVIDERS:
        log.warning('Wizard-Provider überschrieben: %s', wizard_id)
    _PROVIDERS[wizard_id] = provider
    log.debug('Wizard-Provider registriert: %s', wizard_id)


def unregister(wizard_id: str) -> None:
    _PROVIDERS.pop(wizard_id, None)


def get_provider(wizard_id: str) -> WizardDomainProvider:
    try:
        return _PROVIDERS[wizard_id]
    except KeyError as exc:
        raise WizardNotRegisteredError(
            f'Kein Wizard-Provider für wizard_id={wizard_id!r} registriert'
        ) from exc


def list_providers() -> list[WizardDomainProvider]:
    return list(_PROVIDERS.values())


def list_wizard_ids() -> list[str]:
    return sorted(_PROVIDERS.keys())


def provider_info() -> list[dict]:
    return [p.as_dict() for p in list_providers()]
