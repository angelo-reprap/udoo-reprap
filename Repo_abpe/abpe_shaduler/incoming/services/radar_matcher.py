"""radar_matcher — Stub (Architektur Kap. 1). Implementierung folgt V1/V2."""

from .firma_normalizer import normalize_firma_name


def ping():
    return True


def firma_match_key(name: str) -> str:
    """Gleiche Normalisierung wie Sperrliste — für Radar-Abgleich."""
    return normalize_firma_name(name)
