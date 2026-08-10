"""WizardSession Hilfsfunktionen."""
from __future__ import annotations

import uuid
from typing import Any

from django.contrib.auth.models import AbstractBaseUser

from apps.abpe_ki_wiz.models import WizardPhase, WizardSession, WizardSessionStatus
from apps.abpe_ki_wiz.registry import WizardNotRegisteredError, get_provider


def create_session(wizard_id: str, user: AbstractBaseUser, briefing: str = '') -> WizardSession:
    get_provider(wizard_id)  # wirft wenn unbekannt
    return WizardSession.objects.create(
        wizard_id=wizard_id,
        user=user,
        briefing=(briefing or '').strip(),
        phase=WizardPhase.ANALYZE,
        status=WizardSessionStatus.OPEN,
    )


def get_session_for_user(session_id: uuid.UUID, user: AbstractBaseUser) -> WizardSession:
    return WizardSession.objects.get(id=session_id, user=user)


def merge_answers(session: WizardSession, new_answers: dict[str, Any]) -> dict[str, Any]:
    merged = dict(session.answers or {})
    merged.update(new_answers or {})
    session.answers = merged
    session.save(update_fields=['answers', 'updated_at'])
    return merged


def session_to_dict(session: WizardSession) -> dict[str, Any]:
    return {
        'session_id': str(session.id),
        'wizard_id': session.wizard_id,
        'status': session.status,
        'phase': session.phase,
        'briefing': session.briefing,
        'answers': session.answers,
        'meta_suggestions': session.meta_suggestions,
        'result': session.result,
        'error_message': session.error_message,
    }
