"""aktivitaet_service — einzige Schreibstelle für den Historie-Strom (Kap. 2.2)."""
from __future__ import annotations

from typing import Any, Optional

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.abpe_shaduler.models import Aktivitaet

User = get_user_model()


def schreiben(
    *,
    medium: str,
    titel: str,
    ref_type: str = '',
    ref_id: str = '',
    user=None,
    deeplink_url: str = '',
    details: Optional[dict[str, Any]] = None,
    zeitpunkt=None,
) -> Aktivitaet:
    """Eine Historienzeile anlegen. Alle Module sollen nur hierüber schreiben."""
    if medium not in {c.value for c in Aktivitaet.Medium}:
        raise ValueError(f'Ungültiges medium: {medium}')
    return Aktivitaet.objects.create(
        zeitpunkt=zeitpunkt or timezone.now(),
        medium=medium,
        titel=(titel or '')[:250],
        ref_type=(ref_type or '')[:20],
        ref_id=str(ref_id or '')[:64],
        deeplink_url=(deeplink_url or '')[:500],
        user=user if (user and getattr(user, 'pk', None)) else None,
        details=details or {},
    )


def fuer_ref(ref_type: str, ref_id: str, limit: int = 50):
    return (
        Aktivitaet.objects
        .filter(ref_type=ref_type, ref_id=str(ref_id))
        .order_by('-zeitpunkt')[:limit]
    )
