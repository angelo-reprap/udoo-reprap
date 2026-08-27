# -*- coding: utf-8 -*-
"""
apps/abpe_edms/services/tika_extractor.py
================================================================================
Tika-Extraktion — die wiederverwendbare Fähigkeit "Datei -> Volltext".

Aktiver EDMS-Bestandteil: wird vom Massenlauf-Command (dms_extract_content)
aufgerufen, kann aber genauso vom Scanner oder Posteingang-Signal genutzt
werden, wenn ein neues Dokument reinkommt.

Prinzip:
  - Tika liest die Datei NICHT vom Filesystem selbst — wir schicken die Bytes
    per HTTP an den Tika-Dienst (LXC 172.20.3.161:9998) und bekommen Text zurück.
  - Whitelist entscheidet, was extrahiert wird (nur echte Dokumente).
  - Pfadauflösung: volume ('office'/'public') + relative_path -> Mount-Pfad.

Schreibt NICHTS in DB/ES — reine Extraktion. Das Aufrufen/Speichern macht der
Command bzw. der jeweilige Aufrufer.
================================================================================
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import requests


# --- Konfiguration -----------------------------------------------------------
TIKA_URL = "http://172.20.3.161:9998"      # oder http://tika.win.abcona.info:9998
TIKA_TIMEOUT = 300                          # Sekunden; OCR (.tif/Scans) kann dauern

# Mount-Punkte der Samba-Shares auf ucs5
MOUNTS = {
    "office": "/mnt/office",
    "public": "/mnt/public",
}

# Nur diese Endungen werden an Tika geschickt (Whitelist — robuster als Blacklist).
# Abgestimmt auf die tatsächliche Formatverteilung des Bestands (24.070 Dateien).
ALLOWED_EXTENSIONS = {
    # PDF / Word / RTF / OpenOffice-Text
    "pdf", "doc", "docx", "docm", "dot", "dotx", "rtf", "odt", "sxw",
    # Tabellen
    "xls", "xlsx", "ods", "csv", "sxc",
    # Präsentationen
    "ppt", "sxi",
    # Text / HTML
    "txt", "htm", "html",
    # Mail (Outlook)
    "msg",
    # Archive (Tika packt aus und liest den Inhalt)
    "zip",
    # Faxe / eingescannte Dokumente -> OCR (Tesseract deutsch ist im Tika-LXC drin)
    "tif", "png",
    # HINWEIS: .png liefert bei Deko-/Signatur-Grafiken oft leeren Text — das ist ok.
    # Whitelist gehört langfristig in die DmsSetting-DB + EDMS-Settings-GUI (geplant),
    # damit sie ohne Code-Patch pflegbar ist.
}

MAX_BYTES = 200 * 1024 * 1024   # 200 MB Sicherheits-Obergrenze pro Datei


@dataclass
class ExtractResult:
    """Ergebnis einer Extraktion."""
    ok: bool
    text: str = ""
    chars: int = 0
    seconds: float = 0.0
    skipped: bool = False
    reason: str = ""           # bei skip/fehler: warum
    abs_path: str = ""         # aufgelöster Mount-Pfad (für Logging)


def _ext(filename: str) -> str:
    return os.path.splitext(filename or "")[1].lower().lstrip(".")


def is_allowed(filename: str) -> bool:
    """True, wenn die Endung in der Whitelist steht."""
    return _ext(filename) in ALLOWED_EXTENSIONS


def resolve_path(volume: str, relative_path: str) -> str | None:
    """volume ('office'/'public') + relative_path -> absoluter Mount-Pfad.
    Gibt None zurück, wenn das Volume unbekannt ist."""
    base = MOUNTS.get((volume or "").lower())
    if not base:
        return None
    # relative_path kann mit / beginnen — sauber zusammensetzen
    rel = (relative_path or "").lstrip("/")
    return os.path.join(base, rel)


def tika_alive() -> tuple[bool, str]:
    """Kurzer Health-Check. (True, version) oder (False, fehler)."""
    try:
        r = requests.get(f"{TIKA_URL}/version", timeout=10)
        return True, r.text.strip()
    except Exception as e:
        return False, str(e)


def extract(volume: str, relative_path: str, filename: str = "",
            skip_ocr: bool = False) -> ExtractResult:
    """
    Kernfunktion: eine Datei an Tika schicken und Volltext zurückgeben.

    Führt selbst die Whitelist- und Existenz-Prüfung durch, damit jeder Aufrufer
    (Command, Scanner, Signal) dieselbe Filter-Logik bekommt.

    skip_ocr=True schaltet die OCR bei Tika ab (Header X-Tika-OCRskipOcr). Damit
    fliegen Text-Dokumente durch (~0,1s), gescannte PDFs/TIF/PNG liefern dann aber
    leeren Text — die holt man in einem zweiten Lauf MIT OCR nach.
    """
    import time

    name = filename or os.path.basename(relative_path or "")

    # 1. Whitelist
    if not is_allowed(name):
        return ExtractResult(
            ok=False, skipped=True,
            reason=f"uebersprungen (endung .{_ext(name) or '?'} nicht in whitelist)",
        )

    # 2. Pfad auflösen
    abs_path = resolve_path(volume, relative_path)
    if not abs_path:
        return ExtractResult(
            ok=False, skipped=True,
            reason=f"unbekanntes volume '{volume}'",
        )

    # 3. Existenz + Größe
    try:
        size = os.path.getsize(abs_path)
    except OSError as e:
        return ExtractResult(
            ok=False, skipped=True, abs_path=abs_path,
            reason=f"datei nicht lesbar: {e}",
        )
    if size == 0:
        return ExtractResult(
            ok=False, skipped=True, abs_path=abs_path,
            reason="0-byte-datei",
        )
    if size > MAX_BYTES:
        return ExtractResult(
            ok=False, skipped=True, abs_path=abs_path,
            reason=f"zu gross ({size/1024/1024:.0f} MB)",
        )

    # 4. An Tika schicken (PUT, streamt die Datei — kein Vollpuffer im RAM)
    headers = {"Accept": "text/plain"}
    if skip_ocr:
        # OCR abschalten: Text-Dokumente fliegen durch, Scans bleiben leer.
        headers["X-Tika-OCRskipOcr"] = "true"
    t0 = time.perf_counter()
    try:
        with open(abs_path, "rb") as fh:
            r = requests.put(
                f"{TIKA_URL}/tika",
                data=fh,
                headers=headers,
                timeout=TIKA_TIMEOUT,
            )
        dt = time.perf_counter() - t0
        if r.status_code != 200:
            return ExtractResult(
                ok=False, seconds=dt, abs_path=abs_path,
                reason=f"tika HTTP {r.status_code}",
            )
        text = r.content.decode("utf-8", errors="replace").strip()
        return ExtractResult(
            ok=True, text=text, chars=len(text),
            seconds=dt, abs_path=abs_path,
        )
    except Exception as e:
        return ExtractResult(
            ok=False, seconds=time.perf_counter() - t0, abs_path=abs_path,
            reason=f"tika-fehler: {e}",
        )

