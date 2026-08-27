# -*- coding: utf-8 -*-
"""
services/preview.py
================================================================================
Vorschau-Erzeugung für den EDMS-Viewer (Spalte 3).

Strategie:
  - PDF            -> direkt (keine Konvertierung)
  - DOC / DOCX     -> via LibreOffice headless nach PDF, Ergebnis gecacht
  - .msg / sonst.  -> kein Inline-Preview (Frontend zeigt Download/Outlook)

Cache:
  Schlüssel = SHA256 der Version (inhaltsbasiert -> identische Dateien teilen
  sich dasselbe Cache-PDF; geänderte Datei = neue Prüfsumme = Neukonvertierung).
  Ablage: <OFFICE_MOUNT>/abpe/_preview_cache/<sha256>.pdf

LibreOffice-Aufruf identisch zum Doc Studio (exporter.py):
  libreoffice --headless --convert-to pdf --outdir <dir> <datei>
================================================================================
"""

import os
import subprocess
import tempfile
import shutil

from django.conf import settings

from . import storage

# LibreOffice-Binary (wie im Doc Studio)
LIBREOFFICE_BIN = getattr(settings, "LIBREOFFICE_BIN", "/usr/bin/libreoffice")

# Cache-Verzeichnis unter dem office-Mount
PREVIEW_CACHE_DIR = getattr(
    settings, "DMS_PREVIEW_CACHE_DIR",
    os.path.join(storage.OFFICE_MOUNT, storage.ABPE_SUBDIR, "_preview_cache"),
)

# Welche Endungen via LibreOffice konvertiert werden
CONVERTIBLE_EXT = {".doc", ".docx", ".rtf", ".odt"}
# Welche direkt als PDF durchgereicht werden
PDF_EXT = {".pdf"}

# Konvertierungs-Timeout (Sekunden) — LibreOffice kann bei großen Dateien hängen
CONVERT_TIMEOUT = getattr(settings, "DMS_PREVIEW_TIMEOUT", 90)


def _ext(filename):
    return os.path.splitext(filename or "")[1].lower()


def preview_kind(version):
    """Klassifiziert, wie eine Version dargestellt wird:
    'pdf'      -> direkt streamen
    'convert'  -> via LibreOffice nach PDF
    'download' -> kein Inline-Preview (msg, xls, …)
    """
    ext = _ext(version.filename)
    if ext in PDF_EXT:
        return "pdf"
    if ext in CONVERTIBLE_EXT:
        return "convert"
    return "download"


def cache_path_for(version):
    """Pfad des gecachten Vorschau-PDF (SHA256-basiert)."""
    checksum = version.checksum or ""
    if not checksum:
        return None
    return os.path.join(PREVIEW_CACHE_DIR, f"{checksum}.pdf")


def get_preview_pdf(version):
    """Liefert einen absoluten Pfad zu einem anzeigbaren PDF — oder None, wenn
    die Version nicht inline darstellbar ist (download-Fall).

    Bei 'convert' wird bei Bedarf einmalig konvertiert und gecacht.
    """
    kind = preview_kind(version)

    if kind == "pdf":
        # Original-PDF direkt vom Share
        abs_path = storage.absolute_path(version)
        return abs_path if abs_path and os.path.exists(abs_path) else None

    if kind != "convert":
        return None

    # --- convert-Fall: Cache prüfen, sonst konvertieren ---
    cache_pdf = cache_path_for(version)
    if cache_pdf and os.path.exists(cache_pdf):
        return cache_pdf  # Cache-Treffer

    src = storage.absolute_path(version)
    if not src or not os.path.exists(src):
        return None

    pdf = _convert_to_pdf(src)
    if not pdf:
        return None

    # In den Cache verschieben (atomar via os.replace)
    if cache_pdf:
        os.makedirs(PREVIEW_CACHE_DIR, exist_ok=True)
        try:
            shutil.move(pdf, cache_pdf)
            return cache_pdf
        except Exception:
            # Falls move scheitert: das frisch erzeugte PDF direkt zurückgeben
            return pdf
    return pdf


def _convert_to_pdf(src_path):
    """Konvertiert eine Datei via LibreOffice headless nach PDF.
    Gibt den Pfad des erzeugten PDF zurück (in einem temp-Verzeichnis) oder None.
    """
    tmpdir = tempfile.mkdtemp(prefix="dms_preview_")
    try:
        proc = subprocess.run(
            [LIBREOFFICE_BIN, "--headless", "--convert-to", "pdf",
             "--outdir", tmpdir, src_path],
            capture_output=True, timeout=CONVERT_TIMEOUT,
        )
        # LibreOffice legt <basename>.pdf im outdir ab
        base = os.path.splitext(os.path.basename(src_path))[0]
        out_pdf = os.path.join(tmpdir, base + ".pdf")
        if os.path.exists(out_pdf):
            # In ein stabiles Temp-File außerhalb des gleich gelöschten tmpdir
            fd, stable = tempfile.mkstemp(suffix=".pdf", prefix="dms_prev_")
            os.close(fd)
            shutil.move(out_pdf, stable)
            return stable
        return None
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)



# =============================================================================
#  Generische Vorschau für rohe Bytes (z. B. Mail-Anhänge) — nutzt dieselbe
#  LibreOffice-Pipeline + denselben SHA256-Cache wie EDMS-Dokumente.
# =============================================================================
import hashlib as _hashlib


def preview_kind_for_name(filename):
    """Wie preview_kind, aber nur anhand des Dateinamens (ohne version-Objekt)."""
    ext = _ext(filename)
    if ext in PDF_EXT:
        return "pdf"
    if ext in CONVERTIBLE_EXT:
        return "convert"
    return "download"


def get_preview_pdf_for_bytes(content, filename):
    """Liefert (kind, pdf_path) für rohe Datei-Bytes.
      kind 'pdf'      -> pdf_path zeigt auf ein direkt anzeigbares PDF
      kind 'convert'  -> wurde via LibreOffice konvertiert (gecacht)
      kind 'download' -> pdf_path None (kein Inline-Preview möglich)
    Der Cache-Key ist der SHA256 über die Bytes (identische Datei = ein Cache-Eintrag).
    """
    kind = preview_kind_for_name(filename)
    if kind == "download":
        return "download", None

    checksum = _hashlib.sha256(content).hexdigest()
    cache_pdf = os.path.join(PREVIEW_CACHE_DIR, f"{checksum}.pdf")

    # Cache-Treffer (gilt für PDF wie convert gleichermaßen)
    if os.path.exists(cache_pdf):
        return kind, cache_pdf

    os.makedirs(PREVIEW_CACHE_DIR, exist_ok=True)

    if kind == "pdf":
        # PDF direkt in den Cache legen (atomar)
        fd, tmp = tempfile.mkstemp(suffix=".pdf", prefix="dms_attpdf_")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(content)
            try:
                shutil.move(tmp, cache_pdf)
                return "pdf", cache_pdf
            except Exception:
                return "pdf", tmp
        except Exception:
            return "download", None

    # convert-Fall: Bytes in Temp-Datei mit korrekter Endung, dann LibreOffice
    ext = _ext(filename) or ".bin"
    fd, src = tempfile.mkstemp(suffix=ext, prefix="dms_attsrc_")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
        pdf = _convert_to_pdf(src)
        if not pdf:
            return "download", None
        try:
            shutil.move(pdf, cache_pdf)
            return "convert", cache_pdf
        except Exception:
            return "convert", pdf
    finally:
        try:
            os.remove(src)
        except Exception:
            pass


