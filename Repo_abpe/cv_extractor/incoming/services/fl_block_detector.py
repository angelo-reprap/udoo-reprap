"""
fl_block_detector.py
Universeller Block-Detektor fuer FL yx.txt Dateien.
Basiert auf block_detector.py Logik + yx.txt spezifische Erkenntnisse.

ERKENNTNISSE aus 3 CVs:
  Rehsack:  TimesNewRomanPSMT sz=12 ueberall, OpenSymbol=Bullets
            -> Blöcke nur durch gap + font-wechsel (norm->bullet->norm)
  Szewczyk: Arial-BoldMT sz=24 Name, sz=11 bold=Überschriften
            -> bold-wechsel ist Hauptsignal
  Tonev:    Carlito-Bold sz=28 Name, sz=13 Sektionen, sz=10 bold Projektstarter
            -> sz-wechsel ist Hauptsignal

BLOCK-SCHNITT (analog block_detector.py Schritt 1-5):
  Schritt 1: norm_sz, norm_gap aus Dokument (wie in block_detector)
  Schritt 2: Haupttext-Font = Font mit laengstem avg Text (kein Bullet-Font)
  Schritt 3: Initiale Bloecke durch 6 Formatattribute:
             sz, bold, italic, font, gap, page
  Schritt 4: Seitenumbruch = Fortsetzung wenn gleiche Formatierung
  Schritt 5: Block-Label ohne Keywords

BLOCK-LABELS:
  HEADING     sz > norm_sz ODER is_caps ODER (bold + kurz + norm_x)
  DATE_BLOCK  has_date in erster Zeile
  BULLET_LIST > 60% Bullets
  LABEL_BLOCK erste Zeile endet mit ':'
  TEXT_BLOCK  Fliesstext
  MIXED       alles andere
"""

from pathlib import Path
from collections import Counter
import re

try:
    from apps.cv_extractor.services.block_patterns import is_bullet, has_date
except ImportError:
    import unicodedata

    def _is_bullet_char(c):
        cp = ord(c)
        if 0xE000 <= cp <= 0xF8FF: return True
        if 0x1F300 <= cp <= 0x1FAFF: return True
        if 0x2022 <= cp <= 0x2027: return True
        if 0x25A0 <= cp <= 0x25FF: return True
        if 0x2700 <= cp <= 0x27BF: return True
        if 0x2190 <= cp <= 0x21FF: return True
        if cp in (0x00B7, 0x2219): return True
        try:
            cat = unicodedata.category(c)
            if cat in ('So', 'Pd'): return True
        except Exception:
            pass
        return False

    _RE_PHONE  = re.compile(r'^\+\d')
    _RE_RATING = re.compile(r'^\+{2,}')
    _RE_PLUS   = re.compile(r'^\+\s+\S')

    def is_bullet(text):
        if not text: return False
        c = text[0]
        if _is_bullet_char(c): return True
        if c in ('*', '«', '©'): return True
        if c == '+':
            if _RE_PHONE.match(text): return False
            if _RE_RATING.match(text): return False
            if _RE_PLUS.match(text): return True
        return False

    _DATE_PATS = [
        r'\d{1,2}[./-]\d{1,2}[./-]\d{4}',
        r'\d{4}[./-]\d{1,2}[./-]\d{1,2}',
        r'\d{1,2}[./]\d{4}',
        r'\d{4}[./]\d{1,2}',
        r'\d{4}\s*[-–—]\s*\d{4}',
        r'\d{4}\s*[-–—]\s*\d{1,2}[./]\d{4}',
        r'\d{1,2}[./-]\d{4}\s*[-–—]\s*\d{1,2}[./-]\d{4}',
        r'\b\d{4}\b',
        r'\b\d{2}[-/]\d{2}\b',
    ]
    _RE_DATE = re.compile('|'.join('(?:%s)' % p for p in _DATE_PATS))

    def has_date(text):
        m = _RE_DATE.search(text)
        if not m: return False
        matched = m.group(0)
        groups = re.findall(r'\d+', matched)
        if any(len(g) > 4 for g in groups): return False
        for g in groups:
            if len(g) == 4 and not (1900 <= int(g) <= 2099): return False
        for g in groups:
            if len(g) == 2 and int(g) > 31: return False
        return any(len(g) == 4 for g in groups) or (
            len(groups) >= 2 and all(len(g) <= 2 for g in groups))


class FLBlockDetector:

    # ── 1. Einlesen ───────────────────────────────────────────────────────────

    def _read_yx(self, yx_path):
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
                text = parts[12].strip()
                lines.append({
                    'page': page, 'y': y, 'x': x, 'sz': sz,
                    'bold':   'B' in bi.upper(),
                    'italic': 'I' in bi.upper(),
                    'font': font, 'text': text,
                })
            except (ValueError, IndexError):
                continue
        lines.sort(key=lambda l: (l['page'], l['y']))
        return lines

    # ── 2. Normwerte (identisch zu block_detector.py) ─────────────────────────

    def _calc_norms(self, lines):
        # norm_sz = haeufigste Schriftgroesse
        sz_cnt   = Counter(round(l['sz'], 1) for l in lines)
        norm_sz  = sz_cnt.most_common(1)[0][0] if sz_cnt else 12.0

        # norm_gap = haeufigster positiver gap > 2 (wie block_detector)
        gaps = []
        for i in range(1, len(lines)):
            if lines[i]['page'] == lines[i-1]['page']:
                g = lines[i]['y'] - lines[i-1]['y']
                if 0 < g < 100:
                    gaps.append(round(g))
        gap_cnt  = Counter(gaps)
        norm_gap = gap_cnt.most_common(1)[0][0] if gap_cnt else 14
        threshold = norm_gap * 2

        # norm_font = Font mit groesstem cnt * avg_textlaenge
        # NICHT einfach haeufigster — Bullet-Fonts (OpenSymbol) verfaelschen
        font_cnt = Counter(l['font'] for l in lines if l['font'])
        font_scores = {}
        for f, cnt in font_cnt.items():
            texts = [l['text'] for l in lines if l['font'] == f]
            avg_len = sum(len(t) for t in texts) / cnt
            font_scores[f] = avg_len  # avg Textlaenge — Bullets sind kurz
        norm_font = max(font_scores, key=font_scores.get) if font_scores else ''

        # norm_x = haeufigste x-Position (linker Rand)
        x_cnt  = Counter(round(l['x'], 0) for l in lines)
        norm_x = x_cnt.most_common(1)[0][0] if x_cnt else 57.0

        return {
            'norm_sz':   norm_sz,
            'norm_gap':  norm_gap,
            'threshold': threshold,
            'norm_font': norm_font,
            'norm_x':    norm_x,
        }

    # ── 3. Bloecke schneiden (analog block_detector.py Schritt 3) ─────────────

    def _split_blocks(self, lines, norms):
        """
        6 Formatattribute entscheiden Blockgrenze:
        sz, bold, italic, font, gap, page

        Seitenumbruch + gleiche Formatierung = Fortsetzung (kein Split).
        Seitenumbruch + Formatwechsel = neuer Block.
        """
        threshold = norms['threshold']
        blocks    = []
        current   = []
        prev      = None

        for span in lines:
            split = False

            if prev is not None:
                sz_change     = abs(span['sz'] - prev['sz']) >= 1.0
                bold_change   = span['bold']   != prev['bold']
                italic_change = span['italic'] != prev['italic']
                font_change   = (span['font'] and prev['font'] and
                                 span['font'] != prev['font'])
                fmt_change    = sz_change or bold_change or italic_change or font_change

                if span['page'] != prev['page']:
                    # Seitenumbruch: nur Split wenn Formatwechsel
                    if fmt_change:
                        split = True
                else:
                    gap = span['y'] - prev['y']
                    # Grosser Sprung allein reicht
                    if gap > threshold * 1.5:
                        split = True
                    # Normaler Sprung + Formatwechsel
                    elif gap >= threshold and fmt_change:
                        split = True

            if split and current:
                blocks.append(current)
                current = []

            current.append(span)
            prev = span

        if current:
            blocks.append(current)

        return blocks

    # ── 4. Block-Label ────────────────────────────────────────────────────────

    def _label_block(self, block, norms):
        """
        Strukturelles Label ohne Keywords.
        Nur Formatierungsmerkmale.
        """
        if not block:
            return 'MIXED'

        first    = block[0]
        n        = len(block)
        norm_sz  = norms['norm_sz']
        norm_x   = norms['norm_x']
        norm_font = norms['norm_font']

        # is_caps: >= 70% Grossbuchstaben
        letters = [c for c in first['text'] if c.isalpha()]
        is_caps = (sum(1 for c in letters if c.isupper()) / len(letters) >= 0.70
                   if letters else False)

        # HEADING: groessere sz ODER caps ODER (bold + kurz + linker Rand)
        is_heading = (
            first['sz'] > norm_sz or
            is_caps or
            (first['bold'] and
             len(first['text']) < 60 and
             abs(first['x'] - norm_x) < 20 and
             first['font'] == norm_font)
        )
        if is_heading:
            return 'HEADING'

        # DATE_BLOCK: Datum in erster Zeile
        if first['has_date'] if 'has_date' in first else has_date(first['text']):
            return 'DATE_BLOCK'

        # BULLET_LIST: > 60% Bullets
        bullet_count = sum(1 for l in block
                           if (l['is_bullet'] if 'is_bullet' in l
                               else is_bullet(l['text'])))
        if n > 0 and (bullet_count / n) >= 0.60:
            return 'BULLET_LIST'

        # LABEL_BLOCK: endet mit ':'
        if first['text'].rstrip().endswith(':'):
            return 'LABEL_BLOCK'

        # TEXT_BLOCK: lange Zeilen
        long = sum(1 for l in block if len(l['text']) > 40)
        if n > 0 and (long / n) >= 0.5:
            return 'TEXT_BLOCK'

        return 'MIXED'

    # ── 5. Hauptmethode ───────────────────────────────────────────────────────

    def detect(self, yx_path):
        lines = self._read_yx(yx_path)
        norms = self._calc_norms(lines)

        # gap, has_date + is_bullet pro Zeile vorberechnen
        for i, l in enumerate(lines):
            if i == 0 or lines[i]['page'] != lines[i-1]['page']:
                l['gap'] = 0.0
            else:
                l['gap'] = round(lines[i]['y'] - lines[i-1]['y'], 1)
            l['has_date']  = has_date(l['text'])
            l['is_bullet'] = is_bullet(l['text'])

        raw_blocks = self._split_blocks(lines, norms)

        blocks = []
        for i, block in enumerate(raw_blocks):
            label = self._label_block(block, norms)
            blocks.append({
                'index':   i + 1,
                'label':   label,
                'page':    block[0]['page'],
                'y_start': block[0]['y'],
                'y_end':   block[-1]['y'],
                'lines':   block,
                'text':    ' '.join(l['text'] for l in block),
            })

        return {'norms': norms, 'blocks': blocks}

    # ── LLM-Vorbereitung ──────────────────────────────────────────────────────

    def prepare_for_llm(self, result):
        """Format: B[Nr]|p[Seite]|sz=[Groesse]|[B/.]|[label]|[Erste Zeile]"""
        out = []
        for b in result['blocks']:
            first    = b['lines'][0]
            bold_str = 'B' if first['bold'] else '.'
            out.append(
                f"B{b['index']:03d}|p{b['page']:02d}|"
                f"sz={first['sz']:.1f}|{bold_str}|"
                f"{b['label']}|{first['text'][:80]}"
            )
        return '\n'.join(out)

    def get_block_text(self, result, block_indices):
        """Vollstaendiger Text der angegebenen Block-Indizes."""
        idx_set = set(block_indices)
        return '\n'.join(b['text'] for b in result['blocks']
                         if b['index'] in idx_set)


fl_block_detector = FLBlockDetector()
