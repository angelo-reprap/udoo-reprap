"""
abpe_meetme email_helpers -- Variablen-Aufbereitung fuer EmailStudio-Vorlagen
(Einladungen, spaeter auch Terminaenderungs-Hinweise).
"""

EINWAHL_MAP = {
    "034":  ("06171 8867034", None),
    "035":  ("06171 8867035", "0350"),
    "5555": ("06171 8867036", None),
}

WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


def einwahl_info(room_extension):
    nr, pin = EINWAHL_MAP.get(str(room_extension or "").strip(), (None, None))
    if not nr:
        return ""
    return f"Einwahl: {nr}, PIN: {pin}" if pin else f"Einwahl: {nr}"


def format_termin_datum(dt):
    tag = WOCHENTAGE[dt.weekday()]
    datum_str = dt.strftime("%d.%m.%Y")
    return f"{tag}, der {datum_str}"


def format_termin_uhrzeit(dt):
    uhrzeit_str = dt.strftime("%H:%M")
    return f"{uhrzeit_str} Uhr"


def build_meetme_variables(meeting, guest, user=None):
    sender_name = ""
    if user is not None:
        sender_name = f"{user.first_name} {user.last_name}".strip() or user.username
    return {
        "name": guest.name,
        "title": meeting.title,
        "termin_datum": format_termin_datum(meeting.start_at),
        "termin_uhrzeit": format_termin_uhrzeit(meeting.start_at),
        "raum": meeting.room_extension or "",
        "einwahl_info": einwahl_info(meeting.room_extension),
        "sender_name": sender_name,
    }
