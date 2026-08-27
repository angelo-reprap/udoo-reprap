# -*- coding: utf-8 -*-
"""GPU-OCR fuer gescannte Dokumente (Welle 2) — EasyOCR auf lokaler GPU.
Getunt: dpi=100, batch_size hoch, decoder='greedy' (schneller)."""
from __future__ import annotations
import os
from dataclasses import dataclass
import numpy as np

MOUNTS = {"office": "/mnt/office", "public": "/mnt/public"}
OCR_EXTENSIONS = {"pdf", "tif", "tiff", "png", "jpg", "jpeg"}
RENDER_DPI = 100          # war 150 -> kleinere Bilder, schneller
MAX_PAGES = 15
OCR_BATCH = 16            # mehrere Textregionen gleichzeitig auf die GPU
_READER = None


def get_reader():
    global _READER
    if _READER is None:
        import easyocr
        _READER = easyocr.Reader(["de", "en"], gpu=True)
    return _READER


@dataclass
class OcrResult:
    ok: bool
    text: str = ""
    chars: int = 0
    seconds: float = 0.0
    pages: int = 0
    skipped: bool = False
    reason: str = ""


def _ext(filename: str) -> str:
    return os.path.splitext(filename or "")[1].lower().lstrip(".")


def resolve_path(volume: str, relative_path: str):
    base = MOUNTS.get((volume or "").lower())
    if not base:
        return None
    return os.path.join(base, (relative_path or "").lstrip("/"))


def _pdf_to_arrays(abs_path):
    import fitz
    doc = fitz.open(abs_path)
    arrays = []
    for i, page in enumerate(doc):
        if i >= MAX_PAGES:
            break
        pix = page.get_pixmap(dpi=RENDER_DPI)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n)
        if pix.n == 4:
            img = img[:, :, :3]
        arrays.append(img)
    doc.close()
    return arrays


def _image_to_array(abs_path):
    from PIL import Image
    img = Image.open(abs_path).convert("RGB")
    return [np.array(img)]


def extract(volume: str, relative_path: str, filename: str = "") -> OcrResult:
    import time
    name = filename or os.path.basename(relative_path or "")
    ext = _ext(name)
    if ext not in OCR_EXTENSIONS:
        return OcrResult(ok=False, skipped=True, reason=f"kein OCR-Format (.{ext})")
    abs_path = resolve_path(volume, relative_path)
    if not abs_path or not os.path.exists(abs_path):
        return OcrResult(ok=False, skipped=True, reason="datei nicht gefunden")
    reader = get_reader()
    t0 = time.perf_counter()
    try:
        if ext == "pdf":
            arrays = _pdf_to_arrays(abs_path)
        else:
            arrays = _image_to_array(abs_path)
        parts = []
        for img in arrays:
            res = reader.readtext(img, detail=0, paragraph=True,
                                  batch_size=OCR_BATCH, decoder="greedy")
            if res:
                parts.append("\n".join(res))
        text = "\n".join(parts).strip()
        return OcrResult(ok=True, text=text, chars=len(text),
                         seconds=time.perf_counter() - t0, pages=len(arrays))
    except Exception as e:
        return OcrResult(ok=False, seconds=time.perf_counter() - t0,
                         reason=f"ocr-fehler: {e}")
