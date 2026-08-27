# -*- coding: utf-8 -*-
"""
apps/abpe_edms/services/storage.py
================================================================================
Storage-Service: schreibt Dokument-Dateien in die "neue Welt" unter abpe/ auf den
Samba-Shares (CIFS-Mounts auf ucs5) und legt die zugehörige CrmDocumentVersion an.

Ablage-Konvention (29.06.2026):
  Geschäftsdokumente -> /mnt/office/abpe/{kategorie}/{INITIALE}/{nachname_vorname}/
  CVs / Profile      -> /mnt/public/abpe/{nachname_vorname}/        (neue Welt)
  Altdaten (office-Wurzel, public/Berater/...) bleiben unangetastet daneben.

Zugriff: direkter Dateizugriff auf den gemounteten Pfad (wie CrmCallRecording,
open(local_path)). KEIN SFTP/SMB im Code — der Mount erledigt das. Django läuft
als root, der Mount ist uid=0 -> Schreibrechte vorhanden.

Sicherheit beim Schreiben:
  - atomar: erst in <ziel>.part schreiben, fsync, dann os.replace() (kein halb
    geschriebenes File bei Abbruch).
  - SHA256 beim Schreiben mitberechnet (Dedup/Integrität).
  - Dedup-Suffix _NN, falls der Zielname schon existiert (anderer Inhalt).
================================================================================
"""

import hashlib
import os
import re
import unicodedata
from datetime import date

from django.conf import settings
from django.utils import timezone

from apps.abpe_crm.models import CrmContact, CrmAccount
from ..models import (
    CrmDocument, CrmDocumentVersion, DmsDocumentEvent,
    StorageVolume, EventType,
)

# ---------------------------------------------------------------------------
# Wurzeln. WICHTIG: relative_path in der DB ist IMMER relativ zur MOUNT-Wurzel
# (/mnt/office bzw. /mnt/public). Damit funktionieren sowohl neue Dateien
# (unter abpe/...) als auch vom Scanner erfasste Altdaten (Berater/..., Kunde/...)
# mit derselben absolute_path()-Logik.
# ---------------------------------------------------------------------------
OFFICE_MOUNT = getattr(settings, "DMS_OFFICE_MOUNT", "/mnt/office")
PUBLIC_MOUNT = getattr(settings, "DMS_PUBLIC_MOUNT", "/mnt/public")

# Unterordner "abpe/" für NEU geschriebene Dokumente (put_document).
ABPE_SUBDIR = getattr(settings, "DMS_ABPE_SUBDIR", "abpe")

# Rückwärtskompatible Aliase (falls anderswo importiert)
OFFICE_ROOT = os.path.join(OFFICE_MOUNT, ABPE_SUBDIR)
PUBLIC_ROOT = os.path.join(PUBLIC_MOUNT, ABPE_SUBDIR)

_VOLUME_MOUNT = {
    StorageVolume.OFFICE: OFFICE_MOUNT,
    StorageVolume.PUBLIC: PUBLIC_MOUNT,
}

# ---------------------------------------------------------------------------
# Windows-Laufwerksbuchstaben (für die Anzeige im Frontend zum Kopieren in den
# Explorer). Das Mapping lebt eigentlich auf den Windows-Clients (Gruppen-
# richtlinie), der Server kennt es nicht — daher hier als Konstante hinterlegt.
# Später per DB-Settings-GUI änderbar.
# ---------------------------------------------------------------------------
WIN_DRIVE_OFFICE = getattr(settings, "DMS_WIN_DRIVE_OFFICE", "O:")
WIN_DRIVE_PUBLIC = getattr(settings, "DMS_WIN_DRIVE_PUBLIC", "X:")
# Alternativ UNC-Pfad (funktioniert clientunabhängig), falls Laufwerk uneinheitlich
WIN_UNC_OFFICE = getattr(settings, "DMS_WIN_UNC_OFFICE", r"\\172.20.3.150\office")
WIN_UNC_PUBLIC = getattr(settings, "DMS_WIN_UNC_PUBLIC", r"\\172.20.3.150\public")

_VOLUME_WIN_DRIVE = {
    StorageVolume.OFFICE: WIN_DRIVE_OFFICE,
    StorageVolume.PUBLIC: WIN_DRIVE_PUBLIC,
}
_VOLUME_WIN_UNC = {
    StorageVolume.OFFICE: WIN_UNC_OFFICE,
    StorageVolume.PUBLIC: WIN_UNC_PUBLIC,
}


def win_path(version):
    """Windows-Explorer-Pfad einer Version, z. B.
    O:\\Berater\\aktive\\nowka_matthias\\datei.pdf
    (relative_path liegt 1:1 unter dem Laufwerk, / wird zu \\)."""
    drive = _VOLUME_WIN_DRIVE.get(version.volume, WIN_DRIVE_OFFICE)
    rel = (version.relative_path or "").replace("/", "\\")
    return f"{drive}\\{rel}"


def unc_path(version):
    """UNC-Variante (clientunabhängig), z. B. \\\\172.20.3.150\\office\\Berater\\..."""
    base = _VOLUME_WIN_UNC.get(version.volume, WIN_UNC_OFFICE)
    rel = (version.relative_path or "").replace("/", "\\")
    return f"{base}\\{rel}"


# ===========================================================================
#  Hilfsfunktionen: Slug, Initiale, Owner-Auflösung
# ===========================================================================

def slugify_name(value):
    """'Müller-Lüdenscheidt' -> 'mueller_luedenscheidt'. Dateisystem-sicher,
    Umlaute ausgeschrieben, nur [a-z0-9_]."""
    if not value:
        return "unbekannt"
    repl = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
            "Ä": "ae", "Ö": "oe", "Ü": "ue"}
    for k, v in repl.items():
        value = value.replace(k, v)
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value or "unbekannt"


def owner_slug(last_name, first_name=""):
    """nachname_vorname als Ordnername."""
    parts = [slugify_name(last_name)]
    if first_name:
        parts.append(slugify_name(first_name))
    return "_".join(p for p in parts if p and p != "unbekannt") or "unbekannt"


def initial_of(last_name):
    """Erste Buchstabe des (slugifizierten) Nachnamens als A-Z-Gruppe, sonst '#'."""
    s = slugify_name(last_name)
    ch = s[0:1].upper()
    return ch if ch.isalpha() else "#"


def resolve_owner_folder(doc):
    """Ermittelt (volume, owner_slug, initiale) aus dem PRIMÄREN Owner des
    Dokuments. Fällt auf den ersten Owner zurück, wenn keiner als primary
    markiert ist."""
    owners = list(doc.owners.all())
    if not owners:
        return None, "unbekannt", "#"

    primary = next((o for o in owners if o.is_primary), owners[0])

    if primary.owner_type == "contact":
        c = CrmContact.objects.filter(crm_id=primary.owner_crm_id).first()
        if c:
            return primary, owner_slug(c.last_name, c.first_name), initial_of(c.last_name)
    elif primary.owner_type == "account":
        a = CrmAccount.objects.filter(crm_id=primary.owner_crm_id).first()
        if a:
            return primary, owner_slug(a.name), initial_of(a.name)

    # Fallback: crm_id selbst als Ordnername
    return primary, slugify_name(primary.owner_crm_id), "#"


# ===========================================================================
#  Pfad-Aufbau
# ===========================================================================

def build_relative_path(doc):
    """Baut den relativen Akte-Pfad (ohne Wurzel, ohne Dateiname).

    office: {kategorie}/{INITIALE}/{nachname_vorname}/
    public: {nachname_vorname}/            (CV-Welt, flacher)
    """
    doctype = doc.doctype
    volume = doctype.default_volume if doctype else StorageVolume.OFFICE
    kategorie = doctype.key if doctype else "sonstiges"

    _, oslug, initiale = resolve_owner_folder(doc)

    if volume == StorageVolume.PUBLIC:
        # CV / Profile: public/abpe/{nachname_vorname}/
        rel = os.path.join(oslug)
    else:
        # Geschäftsdokumente: office/abpe/{kategorie}/{A-Z}/{nachname_vorname}/
        rel = os.path.join(kategorie, initiale, oslug)

    return volume, rel


def safe_filename(name):
    """Verhindert Pfad-Traversal und unsaubere Zeichen im Dateinamen."""
    name = os.path.basename(name or "datei")
    name = name.replace("\x00", "")
    # Windows-/Unix-problematische Zeichen ersetzen, Punkt/Bindestrich behalten
    name = re.sub(r'[<>:"/\\|?*]+', "_", name).strip()
    return name or "datei"


def _dedup_target(folder_abs, filename):
    """Liefert einen freien Zielpfad. Wenn 'name.pdf' existiert -> 'name_01.pdf' …"""
    target = os.path.join(folder_abs, filename)
    if not os.path.exists(target):
        return target
    base, ext = os.path.splitext(filename)
    for n in range(1, 1000):
        cand = os.path.join(folder_abs, f"{base}_{n:02d}{ext}")
        if not os.path.exists(cand):
            return cand
    raise RuntimeError(f"Zu viele Namenskollisionen für {filename}")


# ===========================================================================
#  Kern: put_document
# ===========================================================================

def put_document(doc, fileobj, filename, *, actor=None, comment="",
                 make_active=True, source_path_original=""):
    """Schreibt eine Datei in die Akte des Dokuments und legt eine
    CrmDocumentVersion an.

    Parameter:
      doc                 CrmDocument (muss gespeichert sein, braucht Owner für Pfad)
      fileobj             offenes, lesbares Datei-Objekt (binary) ODER bytes
      filename            gewünschter Dateiname (z. B. 'Rahmenvertrag.pdf')
      actor               User (für das Audit-Event), optional
      comment             Versions-Notiz
      make_active         neue Version als aktive markieren (alte -> inaktiv)
      source_path_original  Herkunftspfad (für Scanner-Reconcile)

    Rückgabe: die angelegte CrmDocumentVersion.
    """
    volume, rel_dir = build_relative_path(doc)
    mount = _VOLUME_MOUNT[volume]
    # NEU geschriebene Dokumente landen unter abpe/<rel_dir>
    rel_dir_mount = os.path.join(ABPE_SUBDIR, rel_dir)  # z. B. abpe/vertrag/A/...
    folder_abs = os.path.join(mount, rel_dir_mount)

    # Zielordner anlegen (legt abpe/ + Unterordner beim ersten Mal an)
    os.makedirs(folder_abs, exist_ok=True)

    fname = safe_filename(filename)
    target_abs = _dedup_target(folder_abs, fname)
    tmp_abs = target_abs + ".part"

    # --- atomar schreiben + SHA256 ----------------------------------------
    sha = hashlib.sha256()
    size = 0
    try:
        with open(tmp_abs, "wb") as out:
            if isinstance(fileobj, (bytes, bytearray)):
                out.write(fileobj)
                sha.update(fileobj)
                size = len(fileobj)
            else:
                for chunk in iter(lambda: fileobj.read(1024 * 256), b""):
                    out.write(chunk)
                    sha.update(chunk)
                    size += len(chunk)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp_abs, target_abs)  # atomarer Rename
    except Exception:
        # Aufräumen, falls etwas schiefging
        if os.path.exists(tmp_abs):
            try:
                os.remove(tmp_abs)
            except OSError:
                pass
        raise

    checksum = sha.hexdigest()
    final_name = os.path.basename(target_abs)
    rel_path = os.path.join(rel_dir_mount, final_name)  # mount-relativ, inkl. abpe/

    # --- Versionsnummer bestimmen -----------------------------------------
    last = doc.versions.order_by("-version_no").first()
    version_no = (last.version_no + 1) if last else 1

    if make_active:
        doc.versions.filter(is_active=True).update(is_active=False)

    mimetype = _guess_mime(final_name)

    version = CrmDocumentVersion.objects.create(
        document=doc,
        version_no=version_no,
        volume=volume,
        relative_path=rel_path,
        filename=final_name,
        mimetype=mimetype,
        size_bytes=size,
        checksum=checksum,
        checksum_algo="sha256",
        is_active=make_active,
        comment=comment,
        source_path_original=source_path_original,
        created_by=actor,
    )

    # --- Audit ------------------------------------------------------------
    DmsDocumentEvent.objects.create(
        document=doc,
        document_uuid=doc.uuid,
        event_type=EventType.VERSION_NEU if version_no > 1 else EventType.ERSTELLT,
        actor=actor,
        actor_label="" if actor else "storage",
        detail={
            "version_no": version_no,
            "volume": volume,
            "relative_path": rel_path,
            "size_bytes": size,
            "checksum": checksum,
        },
    )
    return version


def absolute_path(version):
    """Liefert den absoluten Dateipfad einer Version (zum Lesen/Streamen).
    relative_path ist mount-relativ -> Mount-Wurzel + relative_path."""
    mount = _VOLUME_MOUNT.get(version.volume, OFFICE_MOUNT)
    return os.path.join(mount, version.relative_path)


def _guess_mime(filename):
    import mimetypes
    mt, _ = mimetypes.guess_type(filename)
    return mt or "application/octet-stream"

