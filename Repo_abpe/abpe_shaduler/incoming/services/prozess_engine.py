"""prozess_engine — ProzessRegel/Schritte ausführen (V1-Grundfunktionen)."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

from django.utils import timezone

from apps.abpe_shaduler.models import Aufgabe, ProzessRegel, ProzessSchritt

from . import aufgaben_service


def _parse_offset(offset: str, base=None):
    """Frist-Offset wie +2d / +0d / -1d → date."""
    base = base or timezone.localdate()
    s = (offset or '').strip()
    if not s:
        return base
    sign = 1
    if s[0] in '+-':
        sign = -1 if s[0] == '-' else 1
        s = s[1:]
    try:
        n = int(''.join(ch for ch in s if ch.isdigit()) or '0')
    except ValueError:
        return base
    unit = ''.join(ch for ch in s if ch.isalpha()) or 'd'
    if unit.startswith('w'):
        return base + timedelta(weeks=sign * n)
    return base + timedelta(days=sign * n)


def run_regel(
    regel: ProzessRegel,
    *,
    user,
    ref_type: str = '',
    ref_id: str = '',
    parent: Optional[Aufgabe] = None,
) -> list[Aufgabe]:
    """Führt aktive Schritte der Regel aus (V1: vor allem aufgabe_erzeugen)."""
    created = []
    if not regel.aktiv:
        return created
    for schritt in regel.schritte.all().order_by('reihenfolge'):
        aufgabe = _run_schritt(
            schritt,
            user=user,
            ref_type=ref_type,
            ref_id=ref_id,
            parent=parent,
            regel=regel,
        )
        if aufgabe:
            created.append(aufgabe)
    return created


def _run_schritt(
    schritt: ProzessSchritt,
    *,
    user,
    ref_type: str,
    ref_id: str,
    parent: Optional[Aufgabe],
    regel: ProzessRegel,
) -> Optional[Aufgabe]:
    params: dict[str, Any] = schritt.parameter or {}
    if schritt.aktion_art == ProzessSchritt.AktionArt.AUFGABE_ERZEUGEN:
        art = params.get('art') or Aufgabe.Art.INTERN
        titel = params.get('titel') or f'{regel.name} · Schritt {schritt.reihenfolge}'
        offset = schritt.frist_offset or params.get('frist_offset') or '+0d'
        return aufgaben_service.erstellen(
            art=art,
            titel=titel,
            zugewiesen_an=user,
            faellig_am=_parse_offset(offset),
            prioritaet=int(params.get('prioritaet') or 3),
            beschreibung=params.get('beschreibung') or '',
            kanal=params.get('kanal') or '',
            ref_type=ref_type or (parent.ref_type if parent else ''),
            ref_id=ref_id or (parent.ref_id if parent else ''),
            quelle=Aufgabe.Quelle.REGEL,
            regel=regel,
            parent=parent,
            user=user,
        )
    # email_senden / whatsapp_vorbereiten / status_setzen / warten — V1.1+
    return None


def on_status(instance, alt: str, neu: str, user=None) -> list[Aufgabe]:
    """Matching-Signal-Hook: Statuswechsel → passende Regeln."""
    from . import aktivitaet_service
    aktivitaet_service.schreiben(
        medium='system',
        titel=f'Status {alt or "—"} → {neu}',
        ref_type='match',
        ref_id=str(getattr(instance, 'pk', '')),
        user=user,
        details={'alt': alt, 'neu': neu},
    )
    created = []
    qs = ProzessRegel.objects.filter(
        aktiv=True,
        ausloeser_typ='status_wechsel',
        ausloeser_wert=neu,
    )
    for regel in qs:
        created.extend(run_regel(
            regel,
            user=user or getattr(instance, 'owner', None),
            ref_type='match',
            ref_id=str(getattr(instance, 'pk', '')),
        ))
    return created


def tick_zeit_ohne_reaktion() -> dict:
    """
    Scheduler-Job prozess_tick (V1):
      - offene überfällige Aufgaben zählen
      - Regeln ausloeser_typ=zeit_ohne_reaktion: wenn Aufgabe länger als N Tage
        offen ohne Aktivität → Folgeaufgabe laut Regel (max. 1× pro Aufgabe/Regel)
    """
    from . import aktivitaet_service
    from apps.abpe_shaduler.models import Aktivitaet

    today = timezone.localdate()
    offen = Aufgabe.objects.filter(status=Aufgabe.Status.OFFEN)
    overdue = offen.filter(faellig_am__lt=today).count()

    created = []
    checked = 0
    rules = list(ProzessRegel.objects.filter(aktiv=True, ausloeser_typ='zeit_ohne_reaktion'))
    for regel in rules:
        try:
            days = int(''.join(ch for ch in (regel.ausloeser_wert or '5') if ch.isdigit()) or '5')
        except ValueError:
            days = 5
        cutoff = today - timedelta(days=days)
        qs = offen.filter(faellig_am__lte=cutoff)
        for aufgabe in qs.select_related('zugewiesen_an')[:50]:
            checked += 1
            # schon Folge aus dieser Regel?
            if Aufgabe.objects.filter(
                parent=aufgabe, regel=regel, status=Aufgabe.Status.OFFEN,
            ).exists():
                continue
            last = (
                Aktivitaet.objects
                .filter(details__aufgabe_id=str(aufgabe.pk))
                .order_by('-zeitpunkt')
                .first()
            )
            if last and last.zeitpunkt.date() >= cutoff:
                continue
            user = aufgabe.zugewiesen_an
            if not user:
                continue
            neu = run_regel(
                regel,
                user=user,
                ref_type=aufgabe.ref_type,
                ref_id=aufgabe.ref_id,
                parent=aufgabe,
            )
            if neu:
                created.extend(neu)
                aktivitaet_service.schreiben(
                    medium='system',
                    titel=f'Zeit ohne Reaktion ({days}d): {regel.name}',
                    ref_type=aufgabe.ref_type,
                    ref_id=aufgabe.ref_id,
                    user=user,
                    details={
                        'aufgabe_id': str(aufgabe.pk),
                        'regel_id': str(regel.pk),
                        'created': [str(a.pk) for a in neu],
                    },
                )

    return {
        'ok': True,
        'overdue': overdue,
        'checked': checked,
        'created': len(created),
        'created_ids': [str(a.pk) for a in created],
    }
