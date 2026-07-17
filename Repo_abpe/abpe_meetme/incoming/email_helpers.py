"""
abpe_meetme email_helpers -- Variablen-Aufbereitung fuer EmailStudio-Vorlagen
(Einladungen, spaeter auch Terminaenderungs-Hinweise).
"""

from zoneinfo import ZoneInfo

EINWAHL_MAP = {
    "034":  ("06171 8867034", None),
    "035":  ("06171 8867035", "0350"),
    "5555": ("06171 8867036", None),
}

WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
DEFAULT_TIMEZONE = "Europe/Berlin"

_TZ_LABEL = {
    "CEST": "MESZ",
    "CET": "MEZ",
}


def user_timezone(user):
    """Zeitzone des Benutzers (Default: Europe/Berlin / MESZ)."""
    tz_name = DEFAULT_TIMEZONE
    if user is not None:
        settings = getattr(user, "crm_settings", None)
        if settings and getattr(settings, "timezone", None):
            tz_name = settings.timezone
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo(DEFAULT_TIMEZONE)


def _localize(dt, tz):
    if dt is None:
        return None
    if dt.tzinfo is None:
        from django.utils import timezone as dj_tz
        dt = dj_tz.make_aware(dt, dj_tz.utc)
    return dt.astimezone(tz)


def einwahl_info(room_extension):
    nr, pin = EINWAHL_MAP.get(str(room_extension or "").strip(), (None, None))
    if not nr:
        return ""
    return f"Einwahl: {nr}, PIN: {pin}" if pin else f"Einwahl: {nr}"


def format_termin_datum(dt, tz=None):
    if tz:
        dt = _localize(dt, tz)
    tag = WOCHENTAGE[dt.weekday()]
    datum_str = dt.strftime("%d.%m.%Y")
    return f"{tag}, der {datum_str}"


def format_termin_uhrzeit(dt, tz=None):
    if tz:
        dt = _localize(dt, tz)
    uhrzeit_str = dt.strftime("%H:%M")
    tz_abbr = dt.strftime("%Z")
    label = _TZ_LABEL.get(tz_abbr, tz_abbr)
    if label:
        return f"{uhrzeit_str} Uhr ({label})"
    return f"{uhrzeit_str} Uhr"


def _teilnehmer_lines(meeting):
    """Baut pro aktivem Gast eine Zeile 'Name, Telefonnummer' -
    Telefonnummer live aus CrmPhoneBeanRel (dieselbe Quelle wie im
    Anruf-Modal), Fallback auf das gespeicherte guest.phone-Feld."""
    from apps.abpe_crm.views import _get_phones
    lines = []
    for g in meeting.guests.filter(is_active=True):
        phone = ""
        if g.contact_crm_id:
            try:
                phones = _get_phones(g.contact_crm_id, "Contacts")
                primary = next((p for p in phones if p.get("is_primary")), None)
                phone = (primary or (phones[0] if phones else {})).get("raw", "")
            except Exception:
                phone = ""
        if not phone:
            phone = g.phone or ""
        lines.append(f"{g.name}, {phone}" if phone else g.name)
    return lines


def build_meetme_variables(meeting, guest, user=None):
    sender_name = ""
    if user is not None:
        sender_name = f"{user.first_name} {user.last_name}".strip() or user.username
    tz = user_timezone(user)
    teilnehmer = _teilnehmer_lines(meeting)
    return {
        "name": guest.name,
        "title": meeting.title,
        "termin_datum": format_termin_datum(meeting.start_at, tz),
        "termin_uhrzeit": format_termin_uhrzeit(meeting.start_at, tz),
        "raum": meeting.room_extension or "",
        "einwahl_info": einwahl_info(meeting.room_extension),
        "sender_name": sender_name,
        "teilnehmer_liste": "\n".join(teilnehmer),
        "teilnehmer_liste_html": "<br>".join(teilnehmer),
    }
