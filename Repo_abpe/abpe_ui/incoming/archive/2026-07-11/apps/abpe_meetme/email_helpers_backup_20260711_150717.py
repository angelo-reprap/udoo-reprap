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
    teilnehmer = _teilnehmer_lines(meeting)
    return {
        "name": guest.name,
        "title": meeting.title,
        "termin_datum": format_termin_datum(meeting.start_at),
        "termin_uhrzeit": format_termin_uhrzeit(meeting.start_at),
        "raum": meeting.room_extension or "",
        "einwahl_info": einwahl_info(meeting.room_extension),
        "sender_name": sender_name,
        "teilnehmer_liste": "\n".join(teilnehmer),
        "teilnehmer_liste_html": "<br>".join(teilnehmer),
    }
