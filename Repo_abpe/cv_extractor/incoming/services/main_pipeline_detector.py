"""
master_detector.py
==================
Master CV Detektor Pipeline:

1. yx.txt einlesen (RAM)
2. Blocksplitter: Zeilen -> Bloecke
3. CV-Struktur Analyse (regelbasiert) -> cv_info
4. LLM Gruppierer: 2-Pass mit versetzten 50er Chunks + cv_info Kontext
5. Regelbasierter Format-Split
6. Ausgabe: strukturierte Gruppen (RAM) + Debug-Datei

Eingabe:  yx_path (str)
Ausgabe:  dict {'blocks', 'gruppen', 'text'}
"""

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import unicodedata
import json
import time


def _load_parallel_workers() -> int:
    try:
        import os
        cfg_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..', '..', '..', 'settings.json'
        )
        with open(cfg_path) as f:
            cfg = json.load(f)
        return int(cfg.get('pipeline', {}).get('parallel_workers_projects', 4))
    except Exception:
        return 4


# ── Bullet-Erkennung (generisch, Unicode-basiert) ─────────────────────
_NOT_BULLET = set('.,"\'()[]\\&+-*/©®¢§«»‚„−')

def _is_bullet_char(c: str) -> bool:
    cp = ord(c)
    if 0xE000 <= cp <= 0xF8FF:   return True
    if 0xF0000 <= cp <= 0xFFFFF: return True
    if 0x1F300 <= cp <= 0x1FAFF: return True
    if 0x2022 <= cp <= 0x2027:   return True
    if 0x25A0 <= cp <= 0x25FF:   return True
    if 0x2700 <= cp <= 0x27BF:   return True
    try:
        cat = unicodedata.category(c)
        if cat in ('So', 'Sm') and c not in _NOT_BULLET: return True
        if cat == 'Po' and c not in _NOT_BULLET:         return True
    except Exception:
        pass
    return False

def _is_bullet_block(block: dict) -> bool:
    erste = block.get('lines', [''])[0].strip() if block.get('lines') else ''
    return len(erste) > 0 and _is_bullet_char(erste[0])

def _is_header_block(block: dict) -> bool:
    if _is_bullet_block(block): return False
    if len(block.get('lines', [])) > 3: return False
    erste = block.get('lines', [''])[0].strip()
    return len(erste) >= 2

def _get_fp(block: dict):
    """
    Stufenweiser Fingerprint — lernt das Muster aus dem Dokument selbst.

    Lieber weniger Starter erkennen als zu viele:
    Ein nicht erkannter Starter wird vom LLM korrekt gruppiert.
    Ein falsch erkannter Starter zerschneidet ein zusammengehöriges Projekt.

    Gibt das SPEZIFISCHSTE Tuple zurück das für diesen Block sinnvoll ist.
    detect_section_headers() zählt dann welche Fingerprints >= 3x vorkommen.
    """
    erste = block.get('lines', [''])[0].strip()
    if len(erste) < 2:
        return None
    font    = (block.get('font', '') or '')[:20]
    sz      = round(block.get('sz', block.get('sz', 0)))
    n_lines = min(len(block.get('lines', [])), 3)
    is_ocr  = (font == 'OCR')
    txt4    = '' if is_ocr or len(erste) < 4 else erste[:4].lower()
    # Vollständiger Fingerprint — wird von _fp_stufenweise ausgewertet
    return (font, sz, n_lines, txt4)


def _fp_stufenweise(blocks: list, min_count: int = 3) -> dict:
    """
    Findet Starter-Muster stufenweise aus den Blöcken des Dokuments.

    Stufe 1: font + sz                    (breit)
    Stufe 2: font + sz + n_lines          (enger)
    Stufe 3: font + sz + n_lines + txt4   (spezifisch)

    Pro Block: das spezifischste Muster nehmen das noch >= min_count Treffer hat.
    Gibt {block_index: fp_tuple} zurück — nur Blöcke die als Starter gelten.

    Abstandsregel: Starter müssen avg_abstand > 2.5 haben
    (verhindert dass direkt aufeinanderfolgende Blöcke als Muster gelten)
    """
    from collections import Counter, defaultdict

    # Alle Fingerprints berechnen
    # _is_header_block filtert: Bullets raus, max 3 Zeilen, min 2 Zeichen
    fp_full = {}   # block_index → (font, sz, n_lines, txt4)
    for b in blocks:
        if not _is_header_block(b):
            continue
        fp = _get_fp(b)
        if fp:
            fp_full[b['index']] = fp

    # Zählen auf jeder Stufe
    c1 = Counter((f[0], f[1])           for f in fp_full.values())  # font+sz
    c2 = Counter((f[0], f[1], f[2])     for f in fp_full.values())  # font+sz+n
    c3 = Counter(f                       for f in fp_full.values())  # voll

    def _abstand_ok(block_nrs: list) -> bool:
        """True wenn die Blöcke nicht alle direkt aufeinanderfolgen."""
        if len(block_nrs) < 2:
            return False
        sh  = sorted(block_nrs)
        avg = sum(sh[i+1]-sh[i] for i in range(len(sh)-1)) / (len(sh)-1)
        mn  = min(sh[i+1]-sh[i] for i in range(len(sh)-1))
        return avg > 2.5 and mn >= 2

    # Für jeden Block: spezifischstes Muster mit >= min_count Treffern
    starter = {}
    for idx, fp in fp_full.items():
        fp1 = (fp[0], fp[1])
        fp2 = (fp[0], fp[1], fp[2])
        fp3 = fp

        # Stufe 3 zuerst versuchen (spezifischst)
        if c3[fp3] >= min_count:
            nrs = [i for i, f in fp_full.items() if f == fp3]
            if _abstand_ok(nrs):
                starter[idx] = fp3
                continue

        # Stufe 2
        if c2[fp2] >= min_count:
            nrs = [i for i, f in fp_full.items() if (f[0],f[1],f[2]) == fp2]
            if _abstand_ok(nrs):
                starter[idx] = fp2
                continue

        # Stufe 1 (breiteste — nur wenn wirklich kein spezifischeres Muster)
        if c1[fp1] >= min_count:
            nrs = [i for i, f in fp_full.items() if (f[0],f[1]) == fp1]
            if _abstand_ok(nrs):
                starter[idx] = fp1

    return starter, fp_full

def _fp_label(fp) -> str:
    """Label für Fingerprint — unterstützt Stufe 1 (2 Elemente) bis Stufe 3 (4 Elemente)."""
    if not fp:
        return 'leer'
    if len(fp) == 2:
        return f"font={fp[0][:8]}|sz={fp[1]}"
    if len(fp) == 3:
        return f"font={fp[0][:8]}|sz={fp[1]}|n={fp[2]}"
    return f"font={fp[0][:8]}|sz={fp[1]}|n={fp[2]}|'{fp[3]}'"



# ══════════════════════════════════════════════════════════════════════════════
# SPAN-QUALITÄTS-KONSTANTEN (main_pipeline_detector Erweiterung)
# ══════════════════════════════════════════════════════════════════════════════

QUALITY_RICH    = 'rich'
QUALITY_PARTIAL = 'partial'
QUALITY_OCR     = 'ocr'
QUALITY_MIXED   = 'mixed'


def _load_detector_settings() -> dict:
    """Lädt detector-Einstellungen aus settings.json mit sicheren Defaults."""
    defaults = {
        'ocr_size_factor':      0.72,
        'ocr_heading_factor':   1.4,
        'ocr_caps_threshold':   0.70,
        'ocr_min_heading_size': 13.0,
        'col_x_raster':         20,
        'col_min_gap':          100,
        'col_min_spans':        5,
    }
    try:
        import os as _os, json as _json
        cfg_path = _os.path.join(
            _os.path.dirname(_os.path.abspath(__file__)),
            '..', '..', '..', 'settings.json'
        )
        with open(cfg_path, encoding='utf-8') as f:
            cfg = _json.load(f)
        d = cfg.get('detector', {})
        return {k: type(v)(d.get(k, v)) for k, v in defaults.items()}
    except Exception:
        return defaults


_DET = _load_detector_settings()
OCR_SIZE_FACTOR      = _DET['ocr_size_factor']
OCR_HEADING_FACTOR   = _DET['ocr_heading_factor']
OCR_CAPS_THRESHOLD   = _DET['ocr_caps_threshold']
OCR_MIN_HEADING_SIZE = _DET['ocr_min_heading_size']
COL_X_RASTER         = int(_DET['col_x_raster'])
COL_MIN_GAP          = int(_DET['col_min_gap'])
COL_MIN_SPANS        = int(_DET['col_min_spans'])


def _is_caps(text: str, threshold: float = OCR_CAPS_THRESHOLD) -> bool:
    t = text.strip()
    if len(t) < 3:
        return False
    letters = [c for c in t if c.isalpha()]
    if not letters:
        return False
    return sum(1 for c in letters if c.isupper()) / len(letters) >= threshold


def _has_date_mpd(text: str) -> bool:
    """
    Erkennt Datumsangaben im Text.
    Nutzt _normalize_period aus master_merger — die ausführlichste Implementierung
    (DE/EN/FR/IT/ES Monatsnamen, ISO, Q1-Q4, KW, Halbjahre, Jahreszeiten, ...).
    Fallback auf einfache Regex wenn Import nicht verfügbar.
    """
    if not text or not text.strip():
        return False
    try:
        from apps.cv_extractor.services.master_merger import _normalize_period
        sy, sm, ey, em = _normalize_period(text.strip())
        return sy > 0
    except Exception:
        pass
    # Fallback: einfache Regex
    import re as _re
    return bool(
        _re.search(
            r'\b(\d{1,2}[./]\d{4}|\d{4})\s*[-\u2013\u2014]\s*'
            r'(\d{1,2}[./]\d{4}|\d{4}|heute|dato|aktuell|now|present|current)\b',
            text, _re.IGNORECASE
        ) or _re.search(r'\b\d{1,2}/\d{4}\b', text)
    )


def _calc_median_gap_mpd(spans_sorted: list) -> float:
    from collections import Counter as _C
    gaps = []
    for i in range(1, len(spans_sorted)):
        sp   = spans_sorted[i]
        prev = spans_sorted[i-1]
        pg  = sp.get('page', 1)   if isinstance(sp,   dict) else getattr(sp,   'page', 1)
        ppg = prev.get('page', 1) if isinstance(prev, dict) else getattr(prev, 'page', 1)
        y   = sp.get('y', 0)      if isinstance(sp,   dict) else getattr(sp,   'y', 0)
        py  = prev.get('y', 0)    if isinstance(prev, dict) else getattr(prev, 'y', 0)
        if pg == ppg:
            gap = y - py
            if 0 < gap < 80:
                gaps.append(round(gap))
    if not gaps:
        return 12.0
    return _C(gaps).most_common(1)[0][0]


def _sg(s, attr, default=None):
    """Span-Get: Dict oder Objekt."""
    if isinstance(s, dict):
        return s.get(attr, default)
    return getattr(s, attr, default)

class MasterDetector:

    def __init__(self):
        try:
            from apps.cv_extractor.services.deepseek_service import deepseek_service
            self.llm = deepseek_service
        except ImportError:
            self.llm = None
        self.parallel_workers = _load_parallel_workers()
        self._prompt_group = None


    # ── Span-Qualität ─────────────────────────────────────────────────────────

    def assess_quality(self, spans: list) -> str:
        import statistics as _st
        if not spans:
            return QUALITY_RICH
        total     = len(spans)
        ocr_count = sum(1 for s in spans if _sg(s, 'font', '') == 'OCR')
        ocr_ratio = ocr_count / total
        if ocr_ratio >= 0.80:
            return QUALITY_OCR
        if 0.05 < ocr_ratio < 0.80:
            return QUALITY_MIXED
        sizes      = [round(_sg(s, 'size', 12.0)) for s in spans]
        bold_count = sum(1 for s in spans if _sg(s, 'bold', False))
        bold_ratio = bold_count / total
        try:
            sz_std = _st.stdev(sizes) if len(sizes) > 1 else 0.0
        except Exception:
            sz_std = 0.0
        if sz_std < 1.5 and bold_ratio < 0.05:
            return QUALITY_PARTIAL
        if bold_ratio < 0.02 and sz_std >= 1.5:
            return QUALITY_PARTIAL
        return QUALITY_RICH


    # ── Dokument-adaptive Parameter ───────────────────────────────────────────

    def calc_doc_params(self, spans: list) -> dict:
        """
        Berechnet alle Detektor-Parameter direkt aus den Spans des Dokuments.
        Kein fester Wert — alles adaptiv aus dem eigenen Inhalt.

        Gibt dict zurück das OCR_SIZE_FACTOR etc. für DIESES Dokument überschreibt.
        settings.json-Werte dienen nur als Fallback wenn zu wenig Daten.

        Berechnete Parameter:
          ocr_size_factor      — aus echten y0/y1 vs size Korrelation (OCR)
          ocr_heading_factor   — aus Y-Gap Verteilung (80. Perzentil Grenze)
          ocr_min_heading_size — aus Size-Verteilung (median + 1.5*stddev)
          ocr_caps_threshold   — aus Großbuchstaben-Häufigkeit im Dokument
          col_min_gap          — aus größter X-Lücke im Dokument
          col_min_spans        — aus Gesamt-Span-Anzahl skaliert
        """
        import statistics as _st
        from collections import Counter as _C

        result = {
            'ocr_size_factor':      OCR_SIZE_FACTOR,
            'ocr_heading_factor':   OCR_HEADING_FACTOR,
            'ocr_min_heading_size': OCR_MIN_HEADING_SIZE,
            'ocr_caps_threshold':   OCR_CAPS_THRESHOLD,
            'col_min_gap':          COL_MIN_GAP,
            'col_min_spans':        COL_MIN_SPANS,
        }

        if not spans or len(spans) < 10:
            return result

        # ── 1. ocr_size_factor aus y0/y1 vs size Korrelation ──────────────
        # Nur für OCR-Spans mit Bounding-Box
        size_factors = []
        for s in spans:
            if _sg(s, 'font', '') != 'OCR':
                continue
            y0   = float(_sg(s, 'y0', 0.0) or 0.0)
            y1   = float(_sg(s, 'y1', 0.0) or 0.0)
            size = float(_sg(s, 'size', 0.0) or _sg(s, 'sz', 0.0) or 0.0)
            h    = y1 - y0
            if h > 3 and size > 0:
                size_factors.append(size / h)
        if len(size_factors) >= 5:
            try:
                factor = round(_st.median(size_factors), 3)
                # Plausibilitätscheck: 0.5 – 0.95
                if 0.50 <= factor <= 0.95:
                    result['ocr_size_factor'] = factor
                    print(f"  [DocParams] ocr_size_factor={factor} "
                          f"(aus {len(size_factors)} OCR-Spans)")
            except Exception:
                pass

        # ── 2. ocr_heading_factor aus Y-Gap Verteilung ────────────────────
        # Y-Abstände zwischen aufeinanderfolgenden Spans gleicher Seite
        srt = sorted(spans, key=lambda s: (
            _sg(s, 'page', 1), _sg(s, 'y', 0)
        ))
        gaps = []
        for i in range(1, len(srt)):
            pg  = _sg(srt[i],   'page', 1)
            ppg = _sg(srt[i-1], 'page', 1)
            y   = float(_sg(srt[i],   'y', 0))
            py  = float(_sg(srt[i-1], 'y', 0))
            if pg == ppg:
                gap = y - py
                if 0 < gap < 80:
                    gaps.append(gap)

        if len(gaps) >= 10:
            try:
                normal_gap = _C([round(g) for g in gaps]).most_common(1)[0][0]
                # 80. Perzentil der Gaps
                gaps_sorted = sorted(gaps)
                p80_idx     = int(len(gaps_sorted) * 0.80)
                p80_gap     = gaps_sorted[p80_idx]
                if normal_gap > 0:
                    factor = round(p80_gap / normal_gap, 2)
                    # Plausibilitätscheck: 1.2 – 2.5
                    if 1.2 <= factor <= 2.5:
                        result['ocr_heading_factor'] = factor
                        print(f"  [DocParams] ocr_heading_factor={factor} "
                              f"(normal_gap={normal_gap:.0f} p80={p80_gap:.0f})")
            except Exception:
                pass

        # ── 3. ocr_min_heading_size aus Size-Verteilung ───────────────────
        sizes = []
        for s in spans:
            v = float(_sg(s, 'size', 0.0) or _sg(s, 'sz', 0.0) or 0.0)
            if v > 0:
                sizes.append(v)

        if len(sizes) >= 10:
            try:
                median_sz = _st.median(sizes)
                try:
                    std_sz = _st.stdev(sizes)
                except Exception:
                    std_sz = 1.5
                heading_threshold = round(median_sz + max(1.5, std_sz * 1.0), 1)
                # Plausibilitätscheck: 8 – 36
                if 8.0 <= heading_threshold <= 36.0:
                    result['ocr_min_heading_size'] = heading_threshold
                    print(f"  [DocParams] ocr_min_heading_size={heading_threshold} "
                          f"(median={median_sz:.1f} std={std_sz:.1f})")
            except Exception:
                pass

        # ── 4. ocr_caps_threshold aus Großbuchstaben-Häufigkeit ───────────
        # Wenn das Dokument viele CAPS-Zeilen hat (z.B. Templates)
        # → Schwelle erhöhen damit nicht alles als Überschrift gilt
        caps_ratios = []
        for s in spans:
            text    = (_sg(s, 'text', '') or '').strip()
            letters = [c for c in text if c.isalpha()]
            if len(letters) >= 4:
                ratio = sum(1 for c in letters if c.isupper()) / len(letters)
                caps_ratios.append(ratio)

        if len(caps_ratios) >= 20:
            try:
                # 75. Perzentil der CAPS-Ratios
                caps_sorted = sorted(caps_ratios)
                p75_idx     = int(len(caps_sorted) * 0.75)
                p75_caps    = caps_sorted[p75_idx]
                # Wenn 75% der Zeilen schon > 0.5 CAPS haben
                # → viel CAPS im Dokument → Schwelle höher setzen
                if p75_caps > 0.5:
                    threshold = min(0.90, round(p75_caps + 0.10, 2))
                    result['ocr_caps_threshold'] = threshold
                    print(f"  [DocParams] ocr_caps_threshold={threshold} "
                          f"(p75_caps={p75_caps:.2f} — CAPS-reiches Dokument)")
                else:
                    # Normal → Schwelle bei 0.70 lassen
                    print(f"  [DocParams] ocr_caps_threshold=0.70 "
                          f"(p75_caps={p75_caps:.2f} — normal)")
            except Exception:
                pass

        # ── 5. col_min_gap aus X-Lücken ──────────────────────────────────
        x_vals   = [round(float(_sg(s, 'x', 0)) / COL_X_RASTER) * COL_X_RASTER
                    for s in spans]
        x_counter = _C(x_vals)
        clusters  = sorted(
            x for x, cnt in x_counter.items()
            if cnt >= max(3, len(spans) // 50)
        )
        if len(clusters) >= 2:
            x_gaps = [clusters[i] - clusters[i-1]
                      for i in range(1, len(clusters))]
            max_x_gap = max(x_gaps) if x_gaps else 0
            if max_x_gap > 30:
                # Spalten-Grenze = halbe maximale Lücke, mindestens 40px
                col_gap = max(40, round(max_x_gap * 0.6))
                result['col_min_gap'] = col_gap
                print(f"  [DocParams] col_min_gap={col_gap} "
                      f"(max_x_gap={max_x_gap}px)")

        # ── 6. col_min_spans aus Gesamt-Anzahl ────────────────────────────
        col_spans = max(5, min(20, len(spans) // 20))
        result['col_min_spans'] = col_spans
        print(f"  [DocParams] col_min_spans={col_spans} "
              f"(total_spans={len(spans)})")

        return result

    # ── Attribut-Anreicherung ─────────────────────────────────────────────────

    def enrich_attributes(self, spans: list, quality: str) -> list:
        import statistics as _st
        if quality == QUALITY_RICH:
            return spans
        enriched = []
        for s in spans:
            if isinstance(s, dict):
                enriched.append(dict(s))
            else:
                enriched.append({
                    'page':      _sg(s, 'page',      1),
                    'y':         _sg(s, 'y',         0),
                    'x':         _sg(s, 'x',         0),
                    'size':      _sg(s, 'size',      12.0),
                    'sz':        _sg(s, 'sz',        _sg(s, 'size', 12.0)),
                    'bold':      _sg(s, 'bold',      False),
                    'italic':    _sg(s, 'italic',    False),
                    'font':      _sg(s, 'font',      ''),
                    'text':      _sg(s, 'text',      ''),
                    'width':     _sg(s, 'width',     0.0),
                    'column_id': _sg(s, 'column_id', -1),
                    'x0':        _sg(s, 'x0',        0.0),
                    'y0':        _sg(s, 'y0',        0.0),
                    'x1':        _sg(s, 'x1',        0.0),
                    'y1':        _sg(s, 'y1',        0.0),
                })
        srt        = sorted(enriched, key=lambda s: (s.get('page',1), s.get('y',0), s.get('x',0)))
        median_gap = _calc_median_gap_mpd(srt)
        # Median-Size aus dem Dokument — kein fester Fallback
        all_sizes = []
        for s in srt:
            v = s.get('size') or s.get('sz')
            if v and float(v) > 0:
                all_sizes.append(float(v))
        try:
            median_size = _st.median(all_sizes) if all_sizes else None
        except Exception:
            median_size = None
        # Fallback nur wenn wirklich keine Größen im Dokument
        if not median_size:
            median_size = _st.median([6.0, 8.0, 9.0, 10.0, 11.0, 12.0, 14.0])
        for i, s in enumerate(srt):
            is_ocr    = (s.get('font', '') == 'OCR')
            do_enrich = (
                (quality in (QUALITY_OCR, QUALITY_MIXED) and is_ocr)
                or (quality == QUALITY_PARTIAL)
            )
            if not do_enrich:
                continue
            text = (s.get('text', '') or '').strip()
            if is_ocr:
                y0 = s.get('y0', 0.0)
                y1 = s.get('y1', 0.0)
                if y1 > y0 and (y1 - y0) > 3:
                    est = round((y1 - y0) * OCR_SIZE_FACTOR, 1)
                    s['size'] = max(6.0, min(est, 48.0))
                    s['sz']   = s['size']
            if text and _is_caps(text):
                s['bold'] = True
            sz = s.get('size', s.get('sz', 12.0))
            if sz >= median_size + 1.5:
                s['bold'] = True
            if i < len(srt) - 1:
                nxt = srt[i + 1]
                if nxt.get('page', 1) == s.get('page', 1):
                    if (nxt.get('y', 0) - s.get('y', 0)) > median_gap * OCR_HEADING_FACTOR:
                        s['size'] = max(s.get('size', s.get('sz', 12.0)), OCR_MIN_HEADING_SIZE)
                        s['sz']   = s['size']
                        s['bold'] = True
            if i > 0:
                prv = srt[i - 1]
                if prv.get('page', 1) == s.get('page', 1):
                    if (s.get('y', 0) - prv.get('y', 0)) > median_gap * OCR_HEADING_FACTOR:
                        s['size'] = max(s.get('size', s.get('sz', 12.0)), OCR_MIN_HEADING_SIZE)
                        s['sz']   = s['size']
                        s['bold'] = True
        return srt

    # ── Spalten-Entflechtung ──────────────────────────────────────────────────

    def detect_columns(self, spans: list):
        from collections import Counter as _C
        if not spans:
            return spans, 1
        x_vals   = [round(_sg(s, 'x', 0) / COL_X_RASTER) * COL_X_RASTER for s in spans]
        counter  = _C(x_vals)
        clusters = sorted(x for x, cnt in counter.items() if cnt >= COL_MIN_SPANS)
        if len(clusters) < 2:
            return spans, 1
        split_points = []
        for i in range(1, len(clusters)):
            if clusters[i] - clusters[i-1] >= COL_MIN_GAP:
                split_points.append((clusters[i-1] + clusters[i]) // 2)
        if not split_points:
            return spans, 1
        n_cols = len(split_points) + 1
        result = []
        for s in spans:
            x   = _sg(s, 'x', 0)
            col = 0
            for sp in split_points:
                if x >= sp:
                    col += 1
                else:
                    break
            if isinstance(s, dict):
                sc = dict(s)
            else:
                sc = {
                    'page':      _sg(s, 'page',      1),
                    'y':         _sg(s, 'y',         0),
                    'x':         _sg(s, 'x',         0),
                    'sz':        _sg(s, 'sz',        _sg(s, 'size', 12.0)),
                    'size':      _sg(s, 'size',      _sg(s, 'sz', 12.0)),
                    'bold':      _sg(s, 'bold',      False),
                    'italic':    _sg(s, 'italic',    False),
                    'font':      _sg(s, 'font',      ''),
                    'text':      _sg(s, 'text',      ''),
                    'width':     _sg(s, 'width',     0.0),
                    'x0':        _sg(s, 'x0',        0.0),
                    'y0':        _sg(s, 'y0',        0.0),
                    'x1':        _sg(s, 'x1',        0.0),
                    'y1':        _sg(s, 'y1',        0.0),
                }
            sc['column_id'] = col
            result.append(sc)
        print(f"  Spalten: {n_cols} | splits={split_points}")
        return result, n_cols

    # ── Format-Vergleich ──────────────────────────────────────────────────────

    def _fmt_changed(self, prev, curr) -> bool:
        get = _sg
        return (
            get(curr, 'bold',   False) != get(prev, 'bold',   False)
            or abs(
                get(curr, 'sz', get(curr, 'size', 12.0)) -
                get(prev, 'sz', get(prev, 'size', 12.0))
            ) >= 1.0
            or (
                get(curr, 'font', '') and get(prev, 'font', '')
                and get(curr, 'font', '') != get(prev, 'font', '')
            )
            or get(curr, 'italic', False) != get(prev, 'italic', False)
        )

    # ── Quality-aware Blocksplitter ───────────────────────────────────────────

    def split_blocks_quality(self, lines: list, quality: str) -> list:
        from collections import Counter as _C
        if not lines:
            return []
        y_gaps = []
        for i in range(1, len(lines)):
            if lines[i]['page'] == lines[i-1]['page']:
                gap = lines[i]['y'] - lines[i-1]['y']
                if 0 < gap < 100:
                    y_gaps.append(round(gap))
        normal_gap = _C(y_gaps).most_common(1)[0][0] if y_gaps else 12
        threshold  = normal_gap * 2.2 if quality == QUALITY_OCR else normal_gap * 1.8
        raw_blocks = []
        current    = [lines[0]]
        for i in range(1, len(lines)):
            prev  = lines[i-1]
            curr  = lines[i]
            split = False
            pc = prev.get('column_id', -1)
            cc = curr.get('column_id', -1)
            if pc != cc and pc != -1 and cc != -1:
                split = True
            elif curr['page'] != prev['page']:
                if quality == QUALITY_RICH:
                    if self._fmt_changed(prev, curr):
                        split = True
                else:
                    split = True
            else:
                gap = curr['y'] - prev['y']
                if gap > threshold * 1.5:
                    split = True
                elif gap >= threshold:
                    if quality == QUALITY_RICH:
                        if self._fmt_changed(prev, curr):
                            split = True
                    else:
                        split = True
                elif quality == QUALITY_RICH:
                    if self._fmt_changed(prev, curr):
                        split = True
                if not split:
                    ct = (curr.get('text', '') or '').strip()
                    pt = (prev.get('text', '') or '').strip()
                    if _is_caps(ct) and not _is_caps(pt) and gap > normal_gap * 0.8:
                        split = True
            if split and current:
                raw_blocks.append(current)
                current = []
            current.append(curr)
        if current:
            raw_blocks.append(current)
        print(f"  split_blocks_quality | quality={quality} | normal_gap={normal_gap} | {len(lines)} → {len(raw_blocks)} Blöcke")
        return raw_blocks

    def _get_prompt_group(self) -> str:
        if self._prompt_group is None:
            try:
                from apps.cv_extractor.models import PromptTemplate
                # main_detector_group bevorzugen (hat Spalten-Regel)
                prompt = (
                    PromptTemplate.objects.filter(
                        name="main_detector_group", is_active=True
                    ).first()
                    or PromptTemplate.objects.filter(
                        name="master_detector_group", is_active=True
                    ).first()
                )
                if prompt:
                    self._prompt_group = prompt.prompt_text
                    print(f"  Gruppierer-Prompt: {prompt.name}")
                else:
                    raise Exception("Kein Prompt gefunden")
            except Exception as e:
                print(f"⚠️ Prompt nicht in DB: {e}")
                self._prompt_group = ("""Du bist ein CV-Analyse Spezialist.
{cv_info}{prefix}{chunk_text}
AUFGABE: Blöcke zu Gruppen zusammenfassen.
col=0 (links) und col=1 (rechts) NIEMALS in eine Gruppe!
{{"gruppen": [{{"nr": 1, "blocks": [1,2,3], "label": "..."}}], "rest": []}}""")
        return self._prompt_group

    def _get_prompt_group_boundary(self) -> str:
        try:
            from apps.cv_extractor.models import PromptTemplate
            prompt = (
                PromptTemplate.objects.filter(name="main_detector_group_boundary", is_active=True).first()
                or PromptTemplate.objects.filter(name="master_detector_group_boundary", is_active=True).first()
            )
            if not prompt: raise Exception("Kein group_boundary Prompt")
            return prompt.prompt_text
        except Exception:
            return self._get_prompt_group()

    # ── 1. yx.txt einlesen ───────────────────────────────────────────────────

    def read_yx(self, yx_path: str) -> list:
        lines = []
        for raw in Path(yx_path).read_text(encoding='utf-8').splitlines():
            if raw.startswith('#') or not raw.strip():
                continue
            parts = raw.split('|')
            if len(parts) < 13:
                continue
            try:
                page = int(''.join(c for c in parts[0] if c.isdigit()) or '0')
                y    = float(parts[1].split('=')[-1])
                x    = float(parts[2].split('=')[-1])
                sz   = float(parts[3].split('=')[-1])
                bi   = parts[4].strip()
                font = parts[5].split('=')[-1].strip() if '=' in parts[5] else parts[5].strip()
                x0   = float(parts[6].split('=')[-1])  if len(parts) > 6  else 0.0
                y0   = float(parts[7].split('=')[-1])  if len(parts) > 7  else 0.0
                x1   = float(parts[8].split('=')[-1])  if len(parts) > 8  else 0.0
                y1   = float(parts[9].split('=')[-1])  if len(parts) > 9  else 0.0
                ox   = float(parts[10].split('=')[-1]) if len(parts) > 10 else 0.0
                oy   = float(parts[11].split('=')[-1]) if len(parts) > 11 else 0.0
                text = parts[12].strip()
                lines.append({
                    'page': page, 'y': y, 'x': x, 'sz': sz,
                    'bold': 'B' in bi.upper(), 'italic': 'I' in bi.upper(),
                    'font': font, 'x0': x0, 'y0': y0,
                    'x1': x1, 'y1': y1, 'ox': ox, 'oy': oy,
                    'text': text, 'width': round(x1 - x0, 1),
                })
            except (ValueError, IndexError):
                continue
        lines.sort(key=lambda l: (l['page'], l['y']))
        return lines

    # ── 2. Blocksplitter ─────────────────────────────────────────────────────

    def split_blocks(self, lines: list) -> list:
        if not lines:
            return []
        blocks  = []
        current = [lines[0]]
        for i in range(1, len(lines)):
            prev  = lines[i-1]
            curr  = lines[i]
            split = False
            # Spaltenübergang → immer neuer Block
            prev_col = prev.get('column_id', -1)
            curr_col = curr.get('column_id', -1)
            if prev_col != curr_col and prev_col != -1 and curr_col != -1:
                split = True
            elif curr['page'] != prev['page']:
                split = True
            elif round(curr['sz'], 1) != round(prev['sz'], 1):
                split = True
            elif i >= 2 and lines[i-2]['page'] == curr['page']:
                dist_prev = lines[i-1]['y'] - lines[i-2]['y']
                dist_curr = curr['y'] - prev['y']
                if abs(dist_curr - dist_prev) > 1.0:
                    split = True
            if split and current:
                blocks.append(current)
                current = []
            current.append(curr)
        if current:
            blocks.append(current)

        # ── Zweiter Pass: Header-Kleber-Fix ──────────────────────────────
        # Wenn Block 2+ Zeilen hat UND Y-Abstand zwischen Zeile 1 und Zeile 2
        # groesser als normal_gap * 1.5 → Block aufteilen.
        # Zeile 1 bleibt allein (Header), Zeile 2+ wird neuer Block (CP nicht MV).
        from collections import Counter as _C
        y_gaps = []
        for b in blocks:
            for j in range(1, len(b)):
                if b[j]['page'] == b[j-1]['page']:
                    gap = b[j]['y'] - b[j-1]['y']
                    if 0 < gap < 80:
                        y_gaps.append(round(gap))
        if not y_gaps:
            return blocks
        normal_gap = _C(y_gaps).most_common(1)[0][0]
        threshold  = normal_gap * 1.5

        result = []
        splits = 0
        for b in blocks:
            if len(b) < 2:
                result.append(b)
                continue
            gap_01 = b[1]['y'] - b[0]['y'] if b[1]['page'] == b[0]['page'] else 0
            if gap_01 > threshold:
                # Header allein
                result.append([b[0]])
                # Rest als neuer Block
                result.append(b[1:])
                splits += 1
                print(f"  split_blocks 2nd-pass: '{b[0]['text']}' + '{b[1]['text']}' "
                      f"(gap={gap_01:.0f} > {threshold:.0f}) → aufgetrennt")
            else:
                result.append(b)

        if splits:
            print(f"  split_blocks 2nd-pass: {splits} Header-Kleber behoben")
        return result

    def format_blocks(self, blocks: list) -> list:
        result = []
        for i, b in enumerate(blocks):
            dist       = round(b[1]['y'] - b[0]['y'], 1) if len(b) > 1 else 0
            first      = b[0]
            bold_str   = 'B' if first.get('bold')   else '.'
            italic_str = 'I' if first.get('italic') else '.'
            font       = first.get('font', '')[:20]
            width      = first.get('width', round(first.get('x1', 0) - first.get('x0', 0), 1))
            col_id     = first.get('column_id', -1)
            x_val      = round(first.get('x', 0))
            result.append({
                'index':     i + 1,
                'page':      first['page'],
                'sz':        first['sz'],
                'bold':      first.get('bold',   False),
                'italic':    first.get('italic', False),
                'font':      font,
                'width':     width,
                'column_id': col_id,
                'x':         x_val,
                'lines':     [l['text'] for l in b],
                'text':      ' '.join(l['text'] for l in b),
                'header': (
                    f"{'#'*50} Block {i+1} | p{first['page']:02d} | "
                    f"sz={first['sz']} | {bold_str}{italic_str} | "
                    f"fn={font} | w={width} | "
                    f"{len(b)} Zeilen | ld={dist}"
                ),
            })
        return result

    def blocks_to_text(self, blocks: list, max_zeilen: int = 2) -> str:
        """Gibt max. erste + letzte max_zeilen Zeilen pro Block aus.
        Spalteninformation (col=N) wird im Header angezeigt damit der LLM
        mehrspaltige Layouts korrekt gruppieren kann.
        """
        out = []
        for b in blocks:
            # column_id aus dem Block holen (wird in format_blocks gespeichert)
            col_id  = b.get('column_id', -1)
            col_str = f' | col={col_id}' if col_id >= 0 else ''
            header  = b['header'] + col_str
            out.append(f"\n{header}")
            lines = b['lines']
            if len(lines) <= max_zeilen * 2:
                for l in lines:
                    out.append(f"  {l}")
            else:
                for l in lines[:max_zeilen]:
                    out.append(f"  {l}")
                out.append(f"  ... ({len(lines) - max_zeilen*2} Zeilen)")
                for l in lines[-max_zeilen:]:
                    out.append(f"  {l}")
        return '\n'.join(out)

    # ── 3. CV-Struktur Analyse ────────────────────────────────────────────────

    def detect_section_headers(self, blocks: list) -> dict:
        """
        Regelbasierte CV-Struktur-Analyse.
        Erkennt ohne Keywords oder CV-spezifische Annahmen:
        1. Bullet-Bloecke (Unicode-basiert)
        2. Wiederkehrende Muster (Fingerabdruck)
        3. Sequenz-Muster
        4. Einzel-Header (enden mit ':')
        5. Seiten-Struktur
        6. Gruppengroesse
        7. Schriftgroessen
        8. Inhalt-Bloecke (kein Starter)

        Gibt cv_info dict + formatierten Text fuer LLM-Prompt zurueck.
        """

        # 1. Bullet-Blöcke
        bullet_set = {b['index'] for b in blocks if _is_bullet_block(b)}

        # 2. Fingerabdruck-Analyse (stufenweise)
        starter_map, fp_full = _fp_stufenweise(blocks, min_count=3)

        # starter_map → alle_muster Format (kompatibel mit Rest der Funktion)
        fingerprints = defaultdict(list)
        for block_idx, fp in starter_map.items():
            fingerprints[fp].append(block_idx)

        alle_muster = {}
        for fp, block_nrs in fingerprints.items():
            sh        = sorted(block_nrs)
            abstaende = [sh[i+1] - sh[i] for i in range(len(sh)-1)]
            avg_abst  = sum(abstaende) / len(abstaende) if abstaende else 0
            min_abst  = min(abstaende) if abstaende else 0
            endet_dp  = all(
                ' '.join(blocks[nr-1]['lines']).strip().endswith(':')
                for nr in sh if nr <= len(blocks)
            )
            alle_muster[fp] = {
                'blocks':    sh,
                'avg':       round(avg_abst, 1),
                'min':       min_abst,
                'endet_dp':  endet_dp,
                'gruppengroesse_avg': round(avg_abst, 1),
                'gruppengroesse_min': min_abst,
                'gruppengroesse_max': max(abstaende) if abstaende else 0,
            }

        # 3. Sequenz-Muster — nutzt fp_full aus _fp_stufenweise
        # fp_full wurde in Schritt 2 berechnet (mit _is_header_block Filter)
        sequence_counts = defaultdict(lambda: defaultdict(int))
        for i, b in enumerate(blocks[:-1]):
            nxt_b = blocks[i+1]
            # Fingerprint aus fp_full (bereits gefiltert) oder BULLET
            b_idx   = b['index']
            nxt_idx = nxt_b['index']
            if _is_bullet_block(b):
                curr = 'BULLET'
            elif b_idx in fp_full:
                curr = _fp_label(fp_full[b_idx])
            else:
                curr = None
            if _is_bullet_block(nxt_b):
                nxt = 'BULLET'
            elif nxt_idx in fp_full:
                nxt = _fp_label(fp_full[nxt_idx])
            else:
                nxt = None
            if curr and nxt:
                sequence_counts[curr][nxt] += 1

        # 4. Einzel-Header
        einzel_set = set()
        einzel_liste = []
        for b in blocks:
            if _is_bullet_block(b): continue
            lines = b.get('lines', [])
            if len(lines) > 3: continue
            text = ' '.join(lines).strip()
            if text.endswith(':') and len(text) <= 50:
                einzel_set.add(b['index'])
                einzel_liste.append({'block': b['index'], 'text': text})

        # 5. Starter vs SubHeader klassifizieren
        muster_labels = {_fp_label(fp): fp for fp in alle_muster}
        starter_muster    = []
        subheader_muster  = []
        starter_set       = set()
        subheader_set     = set()

        for fp, info in alle_muster.items():
            label = _fp_label(fp)
            kommt_nach = [
                other for other in muster_labels
                if other != label and sequence_counts[other].get(label, 0) >= 3
            ]
            avg_abst = info.get('avg', info.get('gruppengroesse_avg', 0))
            # SubHeader-Kriterien:
            # 1. endet mit ':' (klassischer SubHeader)
            # 2. kommt immer nach einem anderen Muster (Sequenz-Abhängigkeit)
            # 3. kleiner Abstand + alle auf gleicher Seite = Sidebar/Untergruppe
            alle_gleiche_seite = len(set(
                blocks[nr-1]['page'] for nr in info['blocks'] if nr <= len(blocks)
            )) == 1
            ist_sub = (
                info['endet_dp']
                or len(kommt_nach) > 0
                or (avg_abst > 0 and avg_abst < 8 and alle_gleiche_seite)
            )
            seiten  = sorted(set(blocks[nr-1]['page'] for nr in info['blocks'] if nr <= len(blocks)))
            abst    = [info['blocks'][i+1]-info['blocks'][i] for i in range(len(info['blocks'])-1)]
            m = {
                'label': label, 'anzahl': len(info['blocks']),
                'blocks': info['blocks'], 'avg_abstand': info['avg'],
                'endet_mit_doppelpunkt': info['endet_dp'],
                'kommt_nach': kommt_nach,
                'seiten': seiten,
                'erste_seite': seiten[0] if seiten else 0,
                'letzte_seite': seiten[-1] if seiten else 0,
                'gruppengroesse_avg': round(sum(abst)/len(abst), 1) if abst else 0,
                'gruppengroesse_min': min(abst) if abst else 0,
                'gruppengroesse_max': max(abst) if abst else 0,
            }
            if ist_sub:
                subheader_muster.append(m)
                subheader_set.update(info['blocks'])
            else:
                starter_muster.append(m)
                starter_set.update(info['blocks'])

        # Block 1 ist immer Starter
        starter_set.add(1)

        # Einzel-Header die nicht SubHeader sind = auch Starter
        einzel_starter = einzel_set - subheader_set
        starter_set.update(einzel_starter)

        # 8. Inhalt-Blöcke
        alle_kategorisiert = bullet_set | starter_set | subheader_set | einzel_set
        inhalt_bloecke = [b['index'] for b in blocks if b['index'] not in alle_kategorisiert]

        # 6. Seiten-Struktur
        seiten_struktur = {}
        if starter_muster:
            letzte = max(m['letzte_seite'] for m in starter_muster)
            ab_block = next((b['index'] for b in blocks if b['page'] > letzte), None)
            seiten_struktur = {
                'muster_aktiv_bis_seite': letzte,
                'anderer_bereich_ab_block': ab_block
            }

        # 7. Schriftgroessen
        sz_count = defaultdict(int)
        for b in blocks:
            sz_count[round(b['sz'], 1)] += 1
        schriftgroessen = {
            str(sz): {'anzahl': c, 'prozent': round(c/len(blocks)*100, 1)}
            for sz, c in sorted(sz_count.items())
        }

        # Sequenzen aufbereiten
        sequenzen = []
        for curr, nexts in sequence_counts.items():
            top = [(n, c) for n, c in sorted(nexts.items(), key=lambda x: -x[1]) if c >= 3]
            if top:
                sequenzen.append({
                    'nach': curr,
                    'folgt': [{'muster': n, 'anzahl': c} for n, c in top]
                })

        cv_info = {
            'gesamt_bloecke':  len(blocks),
            'gesamt_seiten':   blocks[-1]['page'] if blocks else 0,
            'bullet_bloecke':  sorted(bullet_set),
            'starter_muster':  starter_muster,
            'subheader_muster': subheader_muster,
            'einzel_header':   einzel_liste,
            'sequenzen':       sequenzen,
            'seiten_struktur': seiten_struktur,
            'schriftgroessen': schriftgroessen,
            'inhalt_bloecke':  inhalt_bloecke,
            'zusammenfassung': {
                'starter':           sorted(starter_set),
                'subheader':         sorted(subheader_set),
                'bullet':            sorted(bullet_set),
                'inhalt':            inhalt_bloecke,
                'wichtige_bloecke':  len(starter_set) + len(subheader_set) + len(einzel_set),
                'unwichtige_bloecke': len(bullet_set) + len(inhalt_bloecke),
            }
        }

        # LLM-Text generieren
        cv_info['llm_text'] = self._format_cv_info_for_llm(cv_info)
        return cv_info

    def _format_cv_info_for_llm(self, cv_info: dict) -> str:
        """Formatiert cv_info als kompakten Text fuer den LLM-Prompt."""
        z = cv_info.get('zusammenfassung', {})
        L = []
        L.append("=" * 60)
        L.append("CV-STRUKTUR (regelbasiert erkannt):")
        L.append("=" * 60)
        L.append(f"Bloecke: {cv_info['gesamt_bloecke']} | Seiten: {cv_info['gesamt_seiten']}")
        L.append("")

        L.append(f"BULLET-BLOECKE ({len(cv_info['bullet_bloecke'])}x) — niemals Gruppen-Header:")
        L.append(f"  {cv_info['bullet_bloecke']}")
        L.append("")

        L.append(f"WIEDERKEHRENDE MUSTER — potenzielle Gruppen-Grenzen:")
        for m in cv_info['starter_muster']:
            L.append(f"  {m['label']} | {m['anzahl']}x | Seiten {m['erste_seite']}-{m['letzte_seite']}")
            L.append(f"  Gruppengroesse: Ø{m['gruppengroesse_avg']} | Min:{m['gruppengroesse_min']} | Max:{m['gruppengroesse_max']}")
            L.append(f"  Bloecke: {m['blocks']}")
        L.append("")

        L.append(f"INTERNE SUB-HEADER — gehoeren zur vorherigen Gruppe:")
        for m in cv_info['subheader_muster']:
            grund = "endet mit ':'" if m['endet_mit_doppelpunkt'] else f"folgt auf {m['kommt_nach']}"
            L.append(f"  {m['label']} | {m['anzahl']}x | {grund}")
            L.append(f"  Bloecke: {m['blocks']}")
        L.append("")

        L.append(f"SEQUENZ-MUSTER:")
        for seq in cv_info['sequenzen']:
            folgt = ', '.join([f"{f['muster']} ({f['anzahl']}x)" for f in seq['folgt']])
            L.append(f"  [{seq['nach']}] → {folgt}")
        L.append("")

        sub_blocks = {b for m in cv_info['subheader_muster'] for b in m['blocks']}
        einzel = [e for e in cv_info['einzel_header'] if e['block'] not in sub_blocks]
        if einzel:
            L.append(f"EINZEL-HEADER — Abschnitts-Beginn (1x):")
            for e in einzel:
                L.append(f"  Block {e['block']}: '{e['text']}'")
            L.append("")

        if cv_info['seiten_struktur']:
            ss = cv_info['seiten_struktur']
            L.append(f"SEITEN-STRUKTUR:")
            L.append(f"  Muster aktiv bis Seite {ss.get('muster_aktiv_bis_seite')}")
            if ss.get('anderer_bereich_ab_block'):
                L.append(f"  Ab Block {ss['anderer_bereich_ab_block']} anderer Bereich")
            L.append("")

        L.append(f"INHALT-BLOECKE ({len(cv_info['inhalt_bloecke'])}x) — kein Gruppen-Starter:")
        L.append(f"  {cv_info['inhalt_bloecke']}")
        L.append("")

        L.append(f"ZUSAMMENFASSUNG:")
        L.append(f"  Wichtige Bloecke (Entscheidung noetig): {z.get('wichtige_bloecke')}")
        L.append(f"  Inhalt-Bloecke  (nur zuordnen):         {z.get('unwichtige_bloecke')}")
        L.append("=" * 60)
        return '\n'.join(L)

    # ── 4. LLM Gruppierer ────────────────────────────────────────────────────

    def llm_group_chunk(self, chunk_blocks: list, rest_blocks: list = [],
                        boundary: bool = False, cv_info: dict = None) -> dict:
        chunk_text = self.blocks_to_text(chunk_blocks)
        rest_text  = self.blocks_to_text(rest_blocks) if rest_blocks else ''
        prefix     = (
            f"VORHERIGER REST (unvollstaendige Gruppe):\n{rest_text}\n\nNEUE BLOECKE:\n"
            if rest_text else "BLOECKE:\n"
        )
        # CV-Info als Kontext vor den Blöcken
        cv_kontext = ''
        if cv_info and cv_info.get('llm_text'):
            cv_kontext = cv_info['llm_text'] + '\n\n'

        prompt_text = self._get_prompt_group_boundary() if boundary else self._get_prompt_group()
        prompt      = prompt_text.format(
            cv_info=cv_kontext,
            prefix=prefix,
            chunk_text=chunk_text
        )
        res = self.llm.extract(prompt)
        if not res.success:
            return {'gruppen': [], 'rest': []}
        return res.data

    def group_blocks(self, blocks: list, chunk_size: int = 50,
                     offset: int = 25, cv_info: dict = None) -> list:
        """
        Einzel-Aufruf: alle Blöcke auf einmal an LLM.
        Blöcke werden auf max 2+2 Zeilen gekürzt (blocks_to_text).
        """
        print(f"  Gruppierung: {len(blocks)} Bloecke in einem Aufruf...")
        result = self.llm_group_chunk(blocks, [], boundary=False, cv_info=cv_info)
        gruppen = result.get('gruppen', [])
        print(f"  Gruppen: {len(gruppen)}")
        return gruppen

    # ── 5. Regelbasierter Format-Split ───────────────────────────────────────

    def split_by_format(self, gruppen: list, blocks: list) -> list:
        """
        Regelbasierter Split: gleicher Font + gleiche Breite (±0.5pt) +
        gleiche Zeilenzahl + gleiche ersten 4 Buchstaben + kein OpenSymbol
        → neue Gruppe
        """
        block_by_nr = {b['index']: b for b in blocks}
        result      = []
        splits      = 0

        for g in gruppen:
            block_nrs = g.get('blocks', [])
            if len(block_nrs) <= 1:
                result.append(g)
                continue

            first_b = block_by_nr.get(block_nrs[0])
            if not first_b:
                result.append(g)
                continue

            first_font  = first_b.get('font', '')
            first_width = first_b.get('width', 0)
            first_lines = len(first_b.get('lines', []))

            if first_lines > 3 or 'OpenSymbol' in first_font:
                result.append(g)
                continue

            erste_zeile_first = first_b.get('lines', [''])[0].strip()
            current_gruppe_blocks = [block_nrs[0]]

            for block_nr in block_nrs[1:]:
                b = block_by_nr.get(block_nr)
                if not b:
                    current_gruppe_blocks.append(block_nr)
                    continue

                b_font  = b.get('font', '')
                b_width = b.get('width', 0)
                b_lines = len(b.get('lines', []))
                erste_zeile_neu = b.get('lines', [''])[0].strip()

                prefix_len = 4
                gleicher_textanfang = (
                    len(erste_zeile_neu)   >= prefix_len and
                    len(erste_zeile_first) >= prefix_len and
                    erste_zeile_neu[:prefix_len].lower() == erste_zeile_first[:prefix_len].lower()
                )

                gleicher_fingerabdruck = (
                    b_font  == first_font and
                    abs(b_width - first_width) <= 0.5 and
                    b_lines == first_lines and
                    b_lines <= 2 and
                    'OpenSymbol' not in b_font
                )

                if gleicher_fingerabdruck and gleicher_textanfang and len(current_gruppe_blocks) > 0:
                    result.append({
                        'blocks': current_gruppe_blocks,
                        'label':  g.get('label', ''),
                    })
                    current_gruppe_blocks = [block_nr]
                    splits += 1
                    print(f"  Format-Split: Block {block_nr} ({b_font} w={b_width} {b_lines}Z) → neue Gruppe")
                else:
                    current_gruppe_blocks.append(block_nr)

            if current_gruppe_blocks:
                result.append({
                    'blocks': current_gruppe_blocks,
                    'label':  g.get('label', ''),
                })

        if splits > 0:
            print(f"  Format-Split: {splits} Splits → {len(result)} Gruppen")
        else:
            print(f"  Format-Split: Keine Splits noetig")

        return result


    # ── 6. Label-Korrektur (Quality-Check) ──────────────────────────────────

    def _get_prompt_quality(self) -> str:
        try:
            from apps.cv_extractor.models import PromptTemplate
            prompt = (
                PromptTemplate.objects.filter(name="main_detector_quality", is_active=True).first()
                or PromptTemplate.objects.filter(name="master_detector_quality", is_active=True).first()
            )
            if not prompt: raise Exception("Kein quality Prompt")
            return prompt.prompt_text
        except Exception as e:
            print(f"⚠️ Quality-Prompt nicht in DB: {e}")
            return None


    def relabel_from_content(self, gruppen: list, blocks: list) -> list:
        """Setzt Labels: erste 3 Woerter Zeile 1 + erste 3 Woerter Zeile 2.
        Wenn Block nur 1 Zeile hat -> zweite Zeile aus naechstem Block."""
        block_by_nr = {b['index']: b for b in blocks}
        result = []
        for g in gruppen:
            label = g.get('label', '')
            block_nrs = g.get('blocks', [])
            if block_nrs:
                b = block_by_nr.get(block_nrs[0])
                if b and b.get('lines'):
                    lines = b['lines']
                    z1 = ' '.join(lines[0].strip().split()[:3]) if len(lines) >= 1 else ''
                    # Zeile 2: aus Block 1 wenn vorhanden, sonst aus Block 2
                    if len(lines) >= 2 and lines[1].strip():
                        z2 = ' '.join(lines[1].strip().split()[:3])
                    elif len(block_nrs) >= 2:
                        b2 = block_by_nr.get(block_nrs[1])
                        if b2 and b2.get('lines') and b2['lines'][0].strip():
                            z2 = ' '.join(b2['lines'][0].strip().split()[:3])
                        else:
                            z2 = ''
                    else:
                        z2 = ''
                    if z1 and z2:
                        label = f"{z1} | {z2}"
                    elif z1:
                        label = z1
            result.append({**g, 'label': label})
        return result

    def quality_check(self, gruppen: list, blocks: list) -> list:
        """Korrigiert nur die Labels — Inhalt und Struktur bleiben unveraendert."""
        block_by_nr = {b['index']: b for b in blocks}

        overview_lines = ["GRUPPEN UEBERSICHT:", "=" * 60]
        for i, g in enumerate(gruppen, 1):
            zeilen = []
            for nr in g.get('blocks', []):
                b = block_by_nr.get(nr)
                if b: zeilen.extend(b['lines'])
            zeilen = [z.strip() for z in zeilen if z.strip()]
            overview_lines.append(f"G{i:03d} | {g.get('label', '')}")
            for z in zeilen[:3]:
                overview_lines.append(f"  {z[:80]}")
            overview_lines.append("")

        overview    = '\n'.join(overview_lines)
        prompt_text = self._get_prompt_quality()
        if not prompt_text:
            print("  Quality-Check: Kein Prompt — uebersprungen")
            return gruppen

        prompt = prompt_text.format(overview=overview)
        print(f"  Quality-Check: Sende {len(overview)} Zeichen an LLM...")
        res = self.llm.extract(prompt)

        if not res.success:
            print("  Quality-Check: LLM-Fehler — keine Aenderungen")
            return gruppen

        korrekturen = res.data.get('korrekturen', [])
        if not korrekturen:
            print("  Quality-Check: Keine Label-Korrekturen noetig")
            return gruppen

        print(f"  Quality-Check: {len(korrekturen)} Label-Korrekturen")
        neue_gruppen = list(gruppen)
        for k in korrekturen:
            raw = str(k.get('gruppe', '0')).lstrip('G').lstrip('0') or '0'
            idx = int(raw) - 1
            if 0 <= idx < len(neue_gruppen):
                altes = neue_gruppen[idx].get('label', '')
                neues = k.get('neues_label', altes)
                neue_gruppen[idx] = dict(neue_gruppen[idx])
                neue_gruppen[idx]['label'] = neues
                print(f"    G{idx+1:03d}: '{altes}' → '{neues}'")
        return neue_gruppen

    # ── 6. Ausgabe formatieren ───────────────────────────────────────────────

    def format_grouped_output(self, gruppen: list, blocks: list) -> str:
        block_by_nr = {b['index']: b for b in blocks}
        out         = []
        for gruppe_nr, g in enumerate(gruppen, 1):
            out.append(f"\n{'='*60} Gruppe {gruppe_nr} | {g.get('label', '')}")
            for block_nr in g.get('blocks', []):
                b = block_by_nr.get(block_nr)
                if b:
                    out.append(f"\n{b['header']}")
                    for l in b['lines']:
                        out.append(f"  {l}")
        return '\n'.join(out)

    # ── Haupt-Pipeline ───────────────────────────────────────────────────────

    def detect(self, yx_path: str, debug_dir: str = '/tmp') -> dict:
        debug_dir = Path(debug_dir)
        name      = Path(yx_path).stem[:30]

        print(f"[MasterDetector] Starte Pipeline fuer: {name}")

        # Schritt 1: yx.txt lesen
        t0    = time.time()
        lines = self.read_yx(yx_path)
        print(f"  Zeilen: {len(lines)} ({time.time()-t0:.1f}s)")

        # Schritt 2: Bloecke splitten
        t0         = time.time()
        raw_blocks = self.split_blocks(lines)
        blocks     = self.format_blocks(raw_blocks)
        print(f"  Bloecke: {len(blocks)} ({time.time()-t0:.1f}s)")

        blocks_file = debug_dir / f"{name}_blocks.txt"
        blocks_file.write_text(self.blocks_to_text(blocks), encoding='utf-8')
        print(f"  Bloecke gespeichert: {blocks_file}")

        # Schritt 3: CV-Struktur Analyse (regelbasiert)
        t0      = time.time()
        cv_info = self.detect_section_headers(blocks)
        print(f"  CV-Struktur: {cv_info['zusammenfassung']['wichtige_bloecke']} wichtige / "
              f"{cv_info['zusammenfassung']['unwichtige_bloecke']} Inhalt-Bloecke ({time.time()-t0:.1f}s)")

        # Schritt 4: LLM Gruppierung (2-Pass parallel) mit cv_info
        t0      = time.time()
        gruppen = self.group_blocks(blocks, cv_info=cv_info)
        print(f"  Gruppen: {len(gruppen)} ({time.time()-t0:.1f}s)")

        raw_groups_file = debug_dir / f"{name}_groups_raw.json"
        raw_groups_file.write_text(
            json.dumps({'gruppen': gruppen}, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )

        # Schritt 5: Regelbasierter Format-Split
        t0      = time.time()
        gruppen = self.split_by_format(gruppen, blocks)
        print(f"  Nach Format-Split: {len(gruppen)} Gruppen ({time.time()-t0:.1f}s)")

        # Schritt 6: Label-Korrektur (Quality-Check)
        t0      = time.time()
        gruppen = self.quality_check(gruppen, blocks)
        print(f"  Nach Quality-Check: {len(gruppen)} Gruppen ({time.time()-t0:.1f}s)")

        # Schritt 7: Regelbasiertes Re-Labeling
        gruppen = self.relabel_from_content(gruppen, blocks)

        # Schritt 8: Ausgabe formatieren
        grouped_text = self.format_grouped_output(gruppen, blocks)

        grouped_file = debug_dir / f"{name}_grouped.txt"
        grouped_file.write_text(grouped_text, encoding='utf-8')
        print(f"  Gruppiert gespeichert: {grouped_file}")

        return {
            'blocks':  blocks,
            'gruppen': gruppen,
            'text':    grouped_text,
            'cv_info': cv_info,
        }


    def detect_from_spans(self, spans: list, debug_dir: str = None) -> dict:
        """
        Wie detect() aber direkt aus Span-Dicts im RAM — keine yx.txt nötig.
        spans: Liste von dicts mit keys: page, y, x, sz, bold, italic, font, text
        debug_dir: None = kein Debug-Output (alles RAM), sonst Pfad
        """
        print(f"[MasterDetector] Starte Pipeline aus Spans ({len(spans)} Spans)")

        # Schritt 0: Span-Qualität messen (NEU)
        t0      = time.time()
        quality = self.assess_quality(spans)
        print(f"  Span-Qualität: {quality} ({time.time()-t0:.2f}s)")

        # Schritt 0a: Dokument-adaptive Parameter berechnen (NEU)
        t0       = time.time()
        doc_params = self.calc_doc_params(spans)
        # Globale Konstanten für diese Pipeline-Instanz überschreiben
        global OCR_SIZE_FACTOR, OCR_HEADING_FACTOR, OCR_MIN_HEADING_SIZE
        global OCR_CAPS_THRESHOLD, COL_MIN_GAP, COL_MIN_SPANS
        OCR_SIZE_FACTOR      = doc_params['ocr_size_factor']
        OCR_HEADING_FACTOR   = doc_params['ocr_heading_factor']
        OCR_MIN_HEADING_SIZE = doc_params['ocr_min_heading_size']
        OCR_CAPS_THRESHOLD   = doc_params['ocr_caps_threshold']
        COL_MIN_GAP          = doc_params['col_min_gap']
        COL_MIN_SPANS        = doc_params['col_min_spans']
        print(f"  Dok-Parameter berechnet ({time.time()-t0:.2f}s)")

        # Schritt 0b: Attribut-Anreicherung für PARTIAL/OCR/MIXED (NEU)
        if quality != QUALITY_RICH:
            t0    = time.time()
            spans = self.enrich_attributes(spans, quality)
            print(f"  Attribute angereichert: {quality} ({time.time()-t0:.2f}s)")

        # Schritt 0c: Spalten-Entflechtung (NEU)
        t0            = time.time()
        spans, n_cols = self.detect_columns(spans)
        if n_cols > 1:
            print(f"  Spalten erkannt: {n_cols} ({time.time()-t0:.2f}s)")

        # Schritt 1: Spans → Lines
        t0    = time.time()
        lines = []
        for s in spans:
            if isinstance(s, dict):
                lines.append({
                    'page':      int(s.get('page', 1)),
                    'y':         float(s.get('y', 0)),
                    'x':         float(s.get('x', 0)),
                    'sz':        float(s.get('sz', s.get('size', 12.0))),
                    'bold':      bool(s.get('bold', False)),
                    'italic':    bool(s.get('italic', False)),
                    'font':      str(s.get('font', '')),
                    'text':      str(s.get('text', '')),
                    'width':     float(s.get('width', 0)),
                    'column_id': int(s.get('column_id', -1)),
                    'x0':        float(s.get('x0', 0.0)),
                    'y0':        float(s.get('y0', 0.0)),
                    'x1':        float(s.get('x1', 0.0)),
                    'y1':        float(s.get('y1', 0.0)),
                    'ox': 0.0, 'oy': 0.0,
                })
            else:
                lines.append({
                    'page':      int(getattr(s, 'page', 1)),
                    'y':         float(getattr(s, 'y', 0)),
                    'x':         float(getattr(s, 'x', 0)),
                    'sz':        float(getattr(s, 'size', getattr(s, 'sz', 12.0))),
                    'bold':      bool(getattr(s, 'bold', False)),
                    'italic':    bool(getattr(s, 'italic', False)),
                    'font':      str(getattr(s, 'font', '')),
                    'text':      str(getattr(s, 'text', '')),
                    'width':     float(getattr(s, 'width', 0)),
                    'column_id': int(getattr(s, 'column_id', -1)),
                    'x0':        float(getattr(s, 'x0', 0.0)),
                    'y0':        float(getattr(s, 'y0', 0.0)),
                    'x1':        float(getattr(s, 'x1', 0.0)),
                    'y1':        float(getattr(s, 'y1', 0.0)),
                    'ox': 0.0, 'oy': 0.0,
                })
        # Spalten-bewusstes Sortieren
        lines.sort(key=lambda l: (l['column_id'] if l['column_id'] >= 0 else 99, l['page'], l['y']))
        print(f"  Zeilen: {len(lines)} ({time.time()-t0:.1f}s)")

        # Schritt 2: Blöcke (quality-aware)
        t0 = time.time()
        if quality == QUALITY_RICH:
            raw_blocks = self.split_blocks(lines)
        else:
            raw_blocks = self.split_blocks_quality(lines, quality)
        blocks = self.format_blocks(raw_blocks)
        print(f"  Blöcke: {len(blocks)} | quality={quality} ({time.time()-t0:.1f}s)")

        if debug_dir:
            _p = Path(debug_dir)
            _p.mkdir(parents=True, exist_ok=True)
            (_p / 'spans_blocks.txt').write_text(
                self.blocks_to_text(blocks), encoding='utf-8')

        # Schritt 3: CV-Struktur
        t0      = time.time()
        cv_info = self.detect_section_headers(blocks)
        print(f"  CV-Struktur: {cv_info['zusammenfassung']['wichtige_bloecke']} wichtige / "
              f"{cv_info['zusammenfassung']['unwichtige_bloecke']} Inhalt-Bloecke ({time.time()-t0:.1f}s)")

        # Schritt 4: LLM Gruppierung
        t0      = time.time()
        gruppen = self.group_blocks(blocks, cv_info=cv_info)
        print(f"  Gruppen: {len(gruppen)} ({time.time()-t0:.1f}s)")

        # Schritt 5: Format-Split
        t0      = time.time()
        gruppen = self.split_by_format(gruppen, blocks)
        print(f"  Nach Format-Split: {len(gruppen)} Gruppen ({time.time()-t0:.1f}s)")

        # Schritt 6: Quality-Check
        t0      = time.time()
        gruppen = self.quality_check(gruppen, blocks)
        print(f"  Nach Quality-Check: {len(gruppen)} Gruppen ({time.time()-t0:.1f}s)")

        # Schritt 7: Re-Labeling
        gruppen = self.relabel_from_content(gruppen, blocks)

        # Schritt 8: Ausgabe formatieren
        grouped_text = self.format_grouped_output(gruppen, blocks)

        if debug_dir:
            (Path(debug_dir) / 'spans_grouped.txt').write_text(
                grouped_text, encoding='utf-8')

        return {
            'blocks':  blocks,
            'gruppen': gruppen,
            'text':    grouped_text,
            'cv_info': cv_info,
        }


# Singleton
master_detector        = MasterDetector()  # Rückwärtskompatibilität
main_pipeline_detector = MasterDetector()  # neuer Name
