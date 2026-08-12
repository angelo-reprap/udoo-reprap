"""ergebnis_service — Ergebnis anwenden → Status / Folge / Historie (Kap. 1)."""
from __future__ import annotations

from typing import Any, Optional

from django.db import transaction
from django.utils import timezone

from apps.abpe_shaduler.models import Aufgabe, ErgebnisTyp, ProzessRegel

from . import aktivitaet_service, aufgaben_service
from .seed_data import ERGEBNIS_TYPEN


def fx_labels_for(code: str) -> list[str]:
    for row in ERGEBNIS_TYPEN:
        if row['code'] == code:
            return list(row.get('fx_labels') or [])
    return ['Historie-Eintrag']


def get_by_code(code: str) -> Optional[ErgebnisTyp]:
    if not code:
        return None
    return ErgebnisTyp.objects.filter(code=code, aktiv=True).first()


@transaction.atomic
def anwenden(
    *,
    aufgabe: Aufgabe,
    ergebnis: Optional[ErgebnisTyp] = None,
    ergebnis_code: str = '',
    daten: Optional[dict[str, Any]] = None,
    user=None,
) -> dict[str, Any]:
    """
    Drei Wirkungen:
      1) Aufgabe abschließen / snoozen
      2) Optional Folgeaufgaben aus wirkung_regel / Default-Regel zum Code
      3) Aktivitaet schreiben
    """
    daten = daten or {}
    if ergebnis is None and ergebnis_code:
        ergebnis = get_by_code(ergebnis_code)

    created = []
    code = (ergebnis.code if ergebnis else ergebnis_code) or 'erledigt'

    # Snooze ist kein Abschluss
    if code == 'snooze':
        days = int(daten.get('days') or 1)
        aufgaben_service.snooze(aufgabe, days=days, user=user)
        return {
            'ok': True,
            'action': 'snooze',
            'aufgabe_id': str(aufgabe.pk),
            'fx': fx_labels_for('snooze'),
            'created': [],
        }

    if code == 'verworfen':
        aufgabe.status = Aufgabe.Status.VERWORFEN
        aufgabe.erledigt_am = timezone.now()
        aufgabe.erledigt_von = user
        if ergebnis:
            aufgabe.ergebnis = ergebnis
        aufgabe.ergebnis_daten = daten
        aufgabe.save()
        aktivitaet_service.schreiben(
            medium='system',
            titel=f'Verworfen: {aufgabe.titel}',
            ref_type=aufgabe.ref_type,
            ref_id=aufgabe.ref_id,
            user=user,
            details={'aufgabe_id': str(aufgabe.pk), 'ergebnis': code, **daten},
        )
        return {
            'ok': True,
            'action': 'verworfen',
            'aufgabe_id': str(aufgabe.pk),
            'fx': fx_labels_for(code),
            'created': [],
        }

    # Standard: erledigen
    aufgabe.status = Aufgabe.Status.ERLEDIGT
    aufgabe.erledigt_am = timezone.now()
    aufgabe.erledigt_von = user
    if ergebnis:
        aufgabe.ergebnis = ergebnis
    aufgabe.ergebnis_daten = daten
    aufgabe.save()

    aktivitaet_service.schreiben(
        medium=aufgaben_service.AktivitaetMediumForArt(aufgabe.art),
        titel=f'Ergebnis „{(ergebnis.label if ergebnis else code)}“: {aufgabe.titel}',
        ref_type=aufgabe.ref_type,
        ref_id=aufgabe.ref_id,
        user=user,
        details={
            'aufgabe_id': str(aufgabe.pk),
            'ergebnis': code,
            'wirkung_status': (ergebnis.wirkung_status if ergebnis else ''),
            **daten,
        },
    )

    # Folge aus wirkung_regel am Typ oder Regel mit ausloeser ergebnis+code
    regel = None
    if ergebnis and ergebnis.wirkung_regel_id:
        regel = ergebnis.wirkung_regel
    if regel is None:
        regel = (
            ProzessRegel.objects
            .filter(aktiv=True, ausloeser_typ='ergebnis', ausloeser_wert=code)
            .first()
        )
    if regel:
        from . import prozess_engine
        created = prozess_engine.run_regel(
            regel,
            user=user or aufgabe.zugewiesen_an,
            ref_type=aufgabe.ref_type,
            ref_id=aufgabe.ref_id,
            parent=aufgabe,
        )

    return {
        'ok': True,
        'action': 'erledigt',
        'aufgabe_id': str(aufgabe.pk),
        'wirkung_status': (ergebnis.wirkung_status if ergebnis else ''),
        'fx': fx_labels_for(code),
        'created': [str(a.pk) for a in created],
    }
