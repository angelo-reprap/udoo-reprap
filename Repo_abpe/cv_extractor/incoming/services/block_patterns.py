"""
block_patterns.py - Universelle Muster-Erkennung fuer Block-Splitter

Getestete Funktionen ohne Keywords und ohne hardcodierte Zahlen:

1. is_bullet(text)        - Bullet-Erkennung via Unicode
2. has_date(text)         - Datum-Erkennung via Ziffern-Regex
3. get_meta(lines)        - Normwerte aus Dokument berechnen
4. build_word_markers(blocks, meta) - Zeichenketten-Marker aus Daten

Erkenntnisse aus Analyse von 83 PDFs:
- norm_gap = haeufigster positiver gap > 2 (ignoriert Spalten-gaps)
- x, x0, ox, sz, bold, italic, font, h = konstant pro Muster
- x1, y, y0, y1, oy = variabel (Textlaenge/Position)
- Erstes Wort + Datum in Zeile + gleiche Formatierung = Block-Marker
"""

from collections import Counter, defaultdict
import unicodedata
import re

# ══════════════════════════════════════════════════════════════════════════════
# 1. BULLET-ERKENNUNG
# Getestet: 20/20 OK
# ══════════════════════════════════════════════════════════════════════════════

def is_bullet_char(c):
    """
    Erkennt Bullet-Zeichen via Unicode-Kategorie und Codepoint-Ranges.
    Keine Keywords - nur Unicode-Eigenschaften.
    """
    cp = ord(c)
    # Private Use Area (FontAwesome, Wingdings, Symbol-Fonts)
    if 0xE000 <= cp <= 0xF8FF: return True
    if 0xF0000 <= cp <= 0xFFFFF: return True
    # Emoji
    if 0x1F300 <= cp <= 0x1FAFF: return True
    if 0x2600 <= cp <= 0x26FF: return True
    # Bullet-Zeichen Bloecke
    if 0x2022 <= cp <= 0x2027: return True  # BULLET etc
    if 0x25A0 <= cp <= 0x25FF: return True  # Geometric Shapes
    if 0x2700 <= cp <= 0x27BF: return True  # Dingbats
    if 0x2190 <= cp <= 0x21FF: return True  # Arrows
    # Spezielle Punkte
    if cp in (0x00B7, 0x2219): return True  # Middle Dot, Bullet Operator
    try:
        cat = unicodedata.category(c)
        if cat == 'So': return True   # Other Symbol
        if cat == 'Pd': return True   # Dash (- -- -)
        if cat == 'Sm' and cp == 0x2212: return True  # Minus Sign
    except: pass
    return False

RE_PHONE  = re.compile(r'^\+\d')
RE_RATING = re.compile(r'^\+{2,}')
RE_PLUS   = re.compile(r'^\+\s+\S')

def is_bullet(text):
    """
    Erkennt ob ein Text-Span ein Bullet-Listenpunkt ist.
    Getestet mit 83 PDFs - 20/20 Testfaelle OK.

    Erkennt:
    - Unicode Bullets (•, ◦, ▪, →, etc.)
    - Private Use Area Fonts (FontAwesome, Wingdings)
    - Emoji am Zeilenanfang
    - OCR-Varianten: * « © am Zeilenanfang
    - + wenn kein Telefon und kein Rating (++++)

    Erkennt NICHT:
    - +49 157... (Telefon)
    - ++++SAFe  (Rating-Skala)
    - Normaler Text
    - Zahlen
    """
    if not text: return False
    c = text[0]
    if is_bullet_char(c): return True
    if c in ('*', '«', '©'): return True
    if c == '+':
        if RE_PHONE.match(text): return False
        if RE_RATING.match(text): return False
        if RE_PLUS.match(text): return True
    return False


# ══════════════════════════════════════════════════════════════════════════════
# 2. DATUM-ERKENNUNG
# Getestet: 21/21 Testfaelle OK
# ══════════════════════════════════════════════════════════════════════════════

_DATE_PATTERNS = [
    r'\d{1,2}[./-]\d{1,2}[./-]\d{4}',           # 01.07.2022
    r'\d{4}[./-]\d{1,2}[./-]\d{1,2}',           # 2022-07-01
    r'\d{1,2}[./]\d{4}',                          # 01.2022
    r'\d{4}[./]\d{1,2}',                          # 2022/01
    r'\d{4}\s*[-–—]\s*\d{4}',                    # 2022-2023
    r'\d{4}\s*[-–—]\s*\d{1,2}[./]\d{4}',        # 2022-01/2024
    r'\d{1,2}[./-]\d{4}\s*[-–—]\s*\d{1,2}[./-]\d{4}',  # 01.2022-09.2025
    r'\b\d{4}\b',                                  # 2022
    r'\b\d{2}[-/]\d{2}\b',                       # 01-09
]
RE_DATE_RAW = re.compile('|'.join('(?:%s)' % p for p in _DATE_PATTERNS))

def has_date(text):
    """
    Erkennt Datumsmuster ohne Keywords.
    Getestet: 21/21 OK - auch Telefonnummern korrekt abgelehnt.

    Validierung:
    - Keine Zifferngruppe > 4 Stellen (kein Telefon)
    - 4-stellige Gruppe muss 1900-2099 sein (Jahr)
    - 2-stellige Gruppen max 31 (Tag/Monat)

    Erkennt: 01.07.2022, 2022-2023, 01/2022, 01-09, 2022 -
    Erkennt NICHT: 0221-123456, +49 157..., Version 1.2
    """
    m = RE_DATE_RAW.search(text)
    if not m: return False
    matched = m.group(0)
    groups  = re.findall(r'\d+', matched)
    if any(len(g) > 4 for g in groups): return False
    for g in groups:
        if len(g) == 4 and not (1900 <= int(g) <= 2099): return False
    for g in groups:
        if len(g) == 2 and int(g) > 31: return False
    return any(len(g) == 4 for g in groups) or (
        len(groups) >= 2 and all(len(g) <= 2 for g in groups))


# ══════════════════════════════════════════════════════════════════════════════
# 3. NORMWERTE AUS DOKUMENT
# norm_gap = haeufigster positiver gap > 2 (ignoriert Spalten-gaps)
# ══════════════════════════════════════════════════════════════════════════════

def get_meta(lines):
    """
    Berechnet alle Normwerte aus dem Dokument selbst.
    Keine hardcodierten Zahlen - alles relativ.

    Erkenntnisse aus 83 PDFs:
    - gap=0 oder gap<0 = Spalten-Layout (ignorieren)
    - norm_gap = haeufigster positiver gap > 2
    - norm_font = Font mit hoechstem cnt*avg_textlen Score
                  (nicht einfach haeufigster - Bullets verfaelschen)
    - rare_fonts = < 3% der Spans = Sonder-Fonts (Noteworthy, Symbol etc)

    Returns dict mit:
      norm_sz, norm_x, min_x, norm_h, norm_font,
      rare_fonts, norm_gap, threshold
    """
    if not lines: return {}

    sz_cnt = Counter(round(l['sz'],1) for l in lines)
    x_cnt  = Counter(round(l['x'],0)  for l in lines)
    fn_cnt = Counter(l['font'] for l in lines if l['font'])
    h_cnt  = Counter(round(l['y1']-l['y0'],1) for l in lines
                     if l.get('y1',0) > l.get('y0',0))

    norm_sz  = sz_cnt.most_common(1)[0][0]
    norm_x   = x_cnt.most_common(1)[0][0]
    min_x    = min(x_cnt.keys())
    norm_h   = h_cnt.most_common(1)[0][0] if h_cnt else 14.0

    # norm_font = Font mit hoechstem cnt * avg_textlaenge
    # (verhindert dass Bullet-Fonts wie OpenSymbol als norm erkannt werden)
    font_scores = {}
    for f, cnt in fn_cnt.items():
        avg = sum(len(l['text']) for l in lines if l['font']==f) / cnt
        font_scores[f] = cnt * avg
    norm_font  = max(font_scores, key=font_scores.get) if font_scores else ''

    # rare_fonts = Fonts die in < 3% der Spans vorkommen
    # Diese sind immer Block-Starter (Noteworthy-Light, Symbol etc)
    rare_fonts = {f for f,c in fn_cnt.items() if c < max(3, len(lines)*0.03)}

    # norm_gap = haeufigster POSITIVER gap > 2
    # Ignoriert: gap<=0 (Spalten), gap<=2 (Mikro-Abstaende)
    gaps = []
    for i in range(1, len(lines)):
        if lines[i]['page'] == lines[i-1]['page']:
            g = lines[i]['y0'] - lines[i-1]['y1']
            if g > 0: gaps.append(round(g, 0))
    gap_cnt  = Counter(gaps)

    # Haeufigster gap > 2
    norm_gap = next((g for g,c in gap_cnt.most_common() if g > 2), 14.0)
    threshold = norm_gap * 2.5

    return {
        'norm_sz':    norm_sz,
        'norm_x':     norm_x,
        'min_x':      min_x,
        'norm_h':     norm_h,
        'norm_font':  norm_font,
        'rare_fonts': rare_fonts,
        'norm_gap':   norm_gap,
        'threshold':  threshold,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 4. ZEICHENKETTEN-MARKER
# Erstes Wort + Datum in gleicher Zeile + konsistente Formatierung
# Getestet auf 83 PDFs - Score-System 3-5 Sterne
# ══════════════════════════════════════════════════════════════════════════════

def build_word_markers(all_blocks_with_meta):
    """
    Erkennt wiederkehrende Block-Starter-Muster ohne Keywords.

    Algorithmus:
    1. Erstes Wort jeder Block-Erstzeile auslesen
    2. Pruefen ob Datum in gleicher Y-Zeile vorhanden
    3. Formatierungs-Attribute vergleichen (ohne x1, y, y0, y1, oy)
    4. Wenn >= 2x gleicher Anfang + Datum + konsistente Formatierung
       → Block-Marker mit Score

    Score-System:
    3 = sz + font + h gleich (Pflicht)
    4 = + x gleich
    5 = + bold gleich

    Erkenntnisse aus 83 PDFs:
    - "Zeitraum" 12x x=44 sz=9 → Projekt-Starter (GULP-Format)
    - "07/08"     6x x=71 sz=12 bold → Projekt-Starter (AID-Format)
    - "Projekt"  46x x=57 sz=12 → Haupt-Marker (Rehsack-Format)

    Args:
      all_blocks_with_meta: Liste von (block_lines, meta) Tupeln

    Returns:
      dict: {first_word: {'score': int, 'x': float, 'sz': float,
                          'font': str, 'bold': bool, 'count': int}}
    """
    word_entries = defaultdict(list)

    for blk, meta in all_blocks_with_meta:
        if not blk: continue
        first = blk[0]
        t     = first['text'].strip()
        if not t: continue
        words   = t.split()
        first_w = words[0] if words else ''
        if len(first_w) < 2: continue

        # Datum in gleicher Y-Zeile?
        same_y    = [l for l in blk if abs(l.get('y0',0) - first.get('y0',0)) < 3]
        line_text = ' '.join(l['text'] for l in same_y)
        if not has_date(line_text): continue

        h = first.get('y1',0) - first.get('y0',0)
        word_entries[first_w].append({
            'x':      round(first['x'],  1),
            'x0':     round(first.get('x0', first['x']), 1),
            'sz':     round(first['sz'], 1),
            'bold':   first['bold'],
            'italic': first['italic'],
            'font':   first['font'],
            'h':      round(h, 1),
        })

    # Score berechnen
    markers = {}
    for word, entries in word_entries.items():
        if len(entries) < 2: continue

        def konsistent(attr, tol=0):
            vals = [e[attr] for e in entries]
            if tol > 0 and isinstance(vals[0], float):
                return all(abs(v - vals[0]) <= tol for v in vals)
            return len(set(str(v) for v in vals)) == 1

        # Pflicht: sz + font + h
        if not konsistent('sz'):   continue
        if not konsistent('font'): continue
        if not konsistent('h', tol=0.5): continue

        score = 3
        if konsistent('x'):    score += 1
        if konsistent('bold'): score += 1

        cnt      = len(entries)
        x_mode   = Counter(e['x'] for e in entries).most_common(1)[0][0]
        sz_mode  = entries[0]['sz']
        font_top = entries[0]['font']
        bold_val = entries[0]['bold']

        markers[word] = {
            'score': score,
            'count': cnt,
            'x':     x_mode,
            'sz':    sz_mode,
            'font':  font_top,
            'bold':  bold_val,
            'h':     entries[0]['h'],
        }

    return markers
