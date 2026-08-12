"""
cv_block_detector.py
====================
Universeller Block-Detektor fuer FL yx.txt Dateien.
Keine Keywords, keine festen Zahlen.

STUFE 1 - Block-Erkennung:
  Liest yx.txt, berechnet Normwerte, schneidet Bloecke, vergibt Labels.

STUFE 2 - Block-Gruppierung:
  Gruppiert Bloecke nach 3 Mustern:
  M1: first_token wiederholt sich regelmaessig → Gruppen-Starter
        # ── M1c: Seitenumbruch-Fortsetzung ──────────────────────────────────────
        # Wenn ein Gruppen-Starter-Block auf einer neuen Seite beginnt
        # und gleichen Fingerprint hat wie letzter Block der vorherigen Gruppe
        # → zur vorherigen Gruppe hinzufuegen statt neue Gruppe zu starten
        if groups:
            revised_groups = []
            skip_indices = set()
            for gi, g in enumerate(groups):
                if gi == 0:
                    revised_groups.append(g)
                    continue
                first_block = g['blocks'][0]
                prev_group = revised_groups[-1]
                prev_last_block = prev_group['blocks'][-1]
                # Gleiche Seite → kein Merge
                if first_block['page'] == prev_last_block['page']:
                    revised_groups.append(g)
                    continue
                # Verschiedene Seite → Fingerprint vergleichen
                fp_first = (
                    round(first_block['lines'][0]['sz'], 1),
                    first_block['lines'][0]['bold'],
                    first_block['lines'][0]['italic'],
                    first_block['lines'][0]['font'],
                )
                fp_prev = (
                    round(prev_last_block['lines'][0]['sz'], 1),
                    prev_last_block['lines'][0]['bold'],
                    prev_last_block['lines'][0]['italic'],
                    prev_last_block['lines'][0]['font'],
                )
                if fp_first == fp_prev and g['label'] == 'EXPERIENCE_GROUP':
                    # Merge in vorherige Gruppe
                    prev_group['blocks'].extend(g['blocks'])
                    prev_group['text'] += ' ' + g['text']
                    prev_group['y_end'] = g['y_end']
                    for b in g['blocks']:
                        grouped[b['index']] = prev_group['group_id']
                else:
                    revised_groups.append(g)
            # groups aktualisieren
            groups.clear()
            groups.extend(revised_groups)

  M2: has_date + langer Text → Engagement-Starter (ungroupierte Bloecke)
  M3: Rest → Einzelgruppen

VERWENDETE ATTRIBUTE (direkt aus yx.txt):
  page, y, x, sz, bold, italic, font, text

BERECHNETE ATTRIBUTE (pro Zeile):
  line_dist   — y[i] - y[i-1] auf gleicher Seite
  is_bullet   — Bullet-Zeichen am Anfang
  has_date    — Datumsmuster erkannt
  is_caps     — >= 70% Grossbuchstaben
  text_len    — Laenge des Textes
  first_token — erstes Wort

NORMWERTE (dokumentweit):
  norm_sz        — haeufigste Schriftgroesse
  norm_font      — Font mit hoechstem cnt * avg_textlaenge
  norm_line_dist — haeufigster Zeilenabstand
  norm_x         — haeufigste x-Position
"""

from pathlib import Path
from collections import Counter
import re
import statistics

# ── Externe Helfer (mit Fallback) ─────────────────────────────────────────────
try:
    from apps.cv_extractor.services.block_patterns import is_bullet, has_date
except ImportError:
    import unicodedata

    def _is_bullet_char(c):
        cp = ord(c)
        if 0xE000 <= cp <= 0xF8FF: return True
        if 0x2022 <= cp <= 0x2027: return True
        if 0x25A0 <= cp <= 0x25FF: return True
        if 0x2700 <= cp <= 0x27BF: return True
        if cp in (0x00B7, 0x2219): return True
        try:
            if unicodedata.category(c) in ('So', 'Pd'): return True
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
    ]
    _RE_DATE = re.compile('|'.join('(?:%s)' % p for p in _DATE_PATS))

    def has_date(text):
        m = _RE_DATE.search(text)
        if not m: return False
        groups = re.findall(r'\d+', m.group(0))
        if any(len(g) > 4 for g in groups): return False
        for g in groups:
            if len(g) == 4 and not (1900 <= int(g) <= 2099): return False
        return True


# ── Konstanten ────────────────────────────────────────────────────────────────
CAPS_THRESHOLD       = 0.70
BULLET_THRESHOLD     = 0.60
TEXT_THRESHOLD       = 0.50
LINE_DIST_FACTOR     = 2.0
HEADING_MAX_LINES    = 3
MIN_PATTERN_REPEAT   = 2
MIN_TOKEN_LEN        = 2
LONG_LINE_THRESHOLD  = 40
GROUP_SCORE_MAX      = 5.0   # Max Varianz/Avg Score fuer Gruppen-Starter M1
GROUP_MIN_COUNT      = 3     # Mindestanzahl Wiederholungen fuer M1
GROUP_MIN_DIST       = 3     # Mindestabstand zwischen Gruppen-Startern


class CVBlockDetector:

    # ── 1. Einlesen ───────────────────────────────────────────────────────────

    def _read_yx(self, yx_path: str) -> list:
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
                    'page':   page,
                    'y':      y,
                    'x':      x,
                    'sz':     sz,
                    'bold':   'B' in bi.upper(),
                    'italic': 'I' in bi.upper(),
                    'font':   font,
                    'text':   text,
                })
            except (ValueError, IndexError):
                continue
        lines.sort(key=lambda l: (l['page'], l['y']))
        return lines

    # ── 2. Normwerte berechnen ────────────────────────────────────────────────

    def _calc_norms(self, lines: list) -> dict:
        sz_cnt  = Counter(round(l['sz'], 1) for l in lines)
        norm_sz = sz_cnt.most_common(1)[0][0] if sz_cnt else 12.0

        font_cnt    = Counter(l['font'] for l in lines if l['font'])
        font_scores = {}
        for f, cnt in font_cnt.items():
            texts   = [l['text'] for l in lines if l['font'] == f]
            avg_len = sum(len(t) for t in texts) / cnt if cnt else 0
            font_scores[f] = avg_len
        norm_font = max(font_scores, key=font_scores.get) if font_scores else ''

        dists = []
        for i in range(1, len(lines)):
            if lines[i]['page'] == lines[i-1]['page']:
                d = lines[i]['y'] - lines[i-1]['y']
                if 0 < d < 100:
                    dists.append(round(d))
        dist_cnt       = Counter(dists)
        norm_line_dist = dist_cnt.most_common(1)[0][0] if dist_cnt else 14

        x_cnt  = Counter(round(l['x'], 0) for l in lines)
        norm_x = x_cnt.most_common(1)[0][0] if x_cnt else 57.0

        return {
            'norm_sz':        norm_sz,
            'norm_font':      norm_font,
            'norm_line_dist': norm_line_dist,
            'norm_x':         norm_x,
        }

    # ── 3. Zeilen anreichern ─────────────────────────────────────────────────

    def _enrich(self, lines: list, norms: dict) -> list:
        for i, l in enumerate(lines):
            if i == 0 or lines[i]['page'] != lines[i-1]['page']:
                l['line_dist'] = 0.0
            else:
                l['line_dist'] = round(lines[i]['y'] - lines[i-1]['y'], 1)

            l['is_bullet'] = is_bullet(l['text'])
            l['has_date']  = has_date(l['text'])

            letters = [c for c in l['text'] if c.isalpha()]
            if letters:
                upper        = sum(1 for c in letters if c.isupper())
                l['is_caps'] = (upper / len(letters)) >= CAPS_THRESHOLD
            else:
                l['is_caps'] = False

            l['text_len'] = len(l['text'])

            t = l['text'].strip()
            if t and not l['is_bullet']:
                words            = t.split()
                fw               = words[0].strip(',:;.()[]') if words else ''
                l['first_token'] = fw if len(fw) >= MIN_TOKEN_LEN else ''
            else:
                l['first_token'] = ''

        return lines

    # ── 4. Fingerprint ───────────────────────────────────────────────────────

    def _fingerprint(self, line: dict) -> tuple:
        return (round(line['sz'], 1), line['bold'], line['italic'], line['font'])

    # ── 5. Bloecke schneiden ─────────────────────────────────────────────────

    def _split_blocks(self, lines: list, norms: dict) -> list:
        if not lines:
            return []

        threshold = norms['norm_line_dist'] * LINE_DIST_FACTOR
        blocks    = []
        current   = [lines[0]]

        for i in range(1, len(lines)):
            prev    = lines[i-1]
            curr    = lines[i]
            fp_same = self._fingerprint(prev) == self._fingerprint(curr)
            split   = False

            if curr['page'] != prev['page']:
                if not fp_same:
                    split = True
            else:
                if curr['line_dist'] > threshold:
                    split = True
                elif not fp_same:
                    split = True

            if split and current:
                blocks.append(current)
                current = []

            current.append(curr)

        if current:
            blocks.append(current)

        return blocks

    # ── 6. Muster erkennen ───────────────────────────────────────────────────

    def _detect_pattern(self, block: list) -> bool:
        if len(block) < MIN_PATTERN_REPEAT:
            return False

        token_cnt = Counter(
            l['first_token'] for l in block
            if l['first_token'] and not l['is_bullet']
        )
        for token, cnt in token_cnt.items():
            if cnt >= MIN_PATTERN_REPEAT:
                return True

        date_text = sum(1 for l in block if l['has_date'] and l['text_len'] > 20)
        if date_text >= MIN_PATTERN_REPEAT:
            return True

        return False

    # ── 7. Block-Label vergeben ───────────────────────────────────────────────

    def _label_block(self, block: list, norms: dict) -> str:
        if not block:
            return 'MIXED'

        first   = block[0]
        n       = len(block)
        norm_sz = norms['norm_sz']
        norm_x  = norms['norm_x']

        is_heading_fmt = (
            first['sz'] > norm_sz or
            first['is_caps'] or
            (first['bold'] and first['text_len'] < 80 and
             abs(first['x'] - norm_x) < 30)
        )
        no_bullets = not any(l['is_bullet'] for l in block)

        if is_heading_fmt and no_bullets and n <= HEADING_MAX_LINES:
            return 'HEADING'

        bullet_count = sum(1 for l in block if l['is_bullet'])
        if n > 0 and (bullet_count / n) >= BULLET_THRESHOLD:
            return 'BULLET_LIST'

        if self._detect_pattern(block):
            return 'PATTERN_BLOCK'

        if first['has_date'] and not first['is_bullet']:
            return 'DATE_BLOCK'

        long_lines = sum(1 for l in block if l['text_len'] > LONG_LINE_THRESHOLD)
        if n > 0 and (long_lines / n) >= TEXT_THRESHOLD:
            return 'TEXT_BLOCK'

        return 'MIXED'

    # ── 8. Hauptmethode detect() ──────────────────────────────────────────────

    # ── 5b. Seitenumbruch-Fortsetzungen zusammenfuehren ──────────────────────

    def _merge_page_continuations(self, raw_blocks: list) -> list:
        """
        Fuegt rohe Zeilengruppen zusammen die durch Seitenumbruch getrennt wurden
        aber gleichen Fingerprint haben (sz, bold, italic, font).
        raw_blocks ist eine Liste von Listen von Zeilen-Dicts.
        """
        if not raw_blocks:
            return raw_blocks

        merged = [list(raw_blocks[0])]
        for i in range(1, len(raw_blocks)):
            prev_lines = merged[-1]
            curr_lines = raw_blocks[i]

            prev_last = prev_lines[-1]
            curr_first = curr_lines[0]

            page_continues = curr_first['page'] == prev_last['page'] + 1
            same_fp = (
                round(prev_last['sz'], 1)  == round(curr_first['sz'], 1) and
                prev_last['bold']          == curr_first['bold'] and
                prev_last['italic']        == curr_first['italic'] and
                prev_last['font']          == curr_first['font']
            )

            if page_continues and same_fp:
                merged[-1] = prev_lines + list(curr_lines)
            else:
                merged.append(list(curr_lines))

        return merged

    def detect(self, yx_path: str) -> dict:
        """
        Stufe 1: Liest yx.txt und gibt Bloecke zurueck.

        Returns:
          {
            'norms':  dict,
            'blocks': [{'index', 'label', 'page', 'y_start', 'y_end', 'lines', 'text'}]
          }
        """
        lines = self._read_yx(yx_path)
        norms = self._calc_norms(lines)
        lines = self._enrich(lines, norms)

        raw_blocks = self._split_blocks(lines, norms)
        raw_blocks = self._merge_page_continuations(raw_blocks)

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

    # ── 9. Stufe 2: Block-Gruppierung ─────────────────────────────────────────

    def group_blocks(self, result: dict) -> list:
        """
        Stufe 2: Gruppiert Bloecke nach 3 Mustern.

        M1: first_token wiederholt sich regelmaessig (niedrige Varianz/Avg)
            → Gruppen-Starter. Alle Bloecke bis zum naechsten Starter = Gruppe.

        M2: Aus ungruppierten Bloecken:
            has_date=True + text_len > 10 + kein Bullet → Engagement-Starter.

        M3: Alle verbleibenden ungruppierten Bloecke → je eine Einzelgruppe.

        Jede Runde arbeitet NUR auf ungruppierten Bloecken.
        Bereits gruppierte Bloecke werden nicht angefasst.

        Returns:
          [{'group_id', 'label', 'page', 'y_start', 'y_end', 'blocks', 'text'}]
        """
        blocks        = result['blocks']
        grouped       = {}
        groups        = []
        group_counter = [0]

        def make_group(label, block_list):
            group_counter[0] += 1
            gid = group_counter[0]
            for b in block_list:
                grouped[b['index']] = gid
            groups.append({
                'group_id': gid,
                'label':    label,
                'page':     block_list[0]['page'],
                'y_start':  block_list[0]['y_start'],
                'y_end':    block_list[-1]['y_end'],
                'blocks':   block_list,
                'text':     ' '.join(b['text'] for b in block_list),
            })

        def ungrouped():
            return [b for b in blocks if b['index'] not in grouped]

        # ── M0: Bloecke aufsplitten die intern Gruppen-Starter enthalten ────────
        # Erst alle first_tokens zaehlen
        all_token_cnt = {}
        for b in blocks:
            ft = b['lines'][0]['first_token']
            if ft:
                all_token_cnt[ft] = all_token_cnt.get(ft, 0) + 1
        # Tokens die haeufig als Block-Starter vorkommen
        frequent_tokens = {t for t, c in all_token_cnt.items() if c >= GROUP_MIN_COUNT}

        # Bloecke aufteilen wenn eine innere Zeile einen frequent_token hat
        split_blocks = []
        next_idx = max(b['index'] for b in blocks) + 1
        for b in blocks:
            if len(b['lines']) < 2:
                split_blocks.append(b)
                continue
            split_at = None
            for li in range(1, len(b['lines'])):
                if b['lines'][li]['first_token'] in frequent_tokens:
                    split_at = li
                    break
            if split_at is None:
                split_blocks.append(b)
            else:
                p1 = b['lines'][:split_at]
                p2 = b['lines'][split_at:]
                if p1:
                    split_blocks.append({
                        'index':   b['index'],
                        'label':   b['label'],
                        'page':    p1[0]['page'],
                        'y_start': p1[0]['y'],
                        'y_end':   p1[-1]['y'],
                        'lines':   p1,
                        'text':    ' '.join(l['text'] for l in p1),
                    })
                if p2:
                    split_blocks.append({
                        'index':   b['index'] + 0.5,
                        'label':   b['label'],
                        'page':    p2[0]['page'],
                        'y_start': p2[0]['y'],
                        'y_end':   p2[-1]['y'],
                        'lines':   p2,
                        'text':    ' '.join(l['text'] for l in p2),
                    })
        blocks = sorted(split_blocks, key=lambda b: b['index'])

        # ── M1: regelmaessiger first_token ────────────────────────────────────
        ub = ungrouped()
        token_positions = {}
        for b in ub:
            ft = b['lines'][0]['first_token']
            if ft:
                if ft not in token_positions:
                    token_positions[ft] = []
                token_positions[ft].append(b['index'])

        starters_m1 = []
        for token, positions in token_positions.items():
            if len(positions) < GROUP_MIN_COUNT:
                continue
            dists = [positions[i+1] - positions[i] for i in range(len(positions)-1)]
            if len(dists) < 2:
                continue
            var = statistics.variance(dists)
            avg = sum(dists) / len(dists)
            if avg < GROUP_MIN_DIST:
                continue
            score = var / avg
            if score < GROUP_SCORE_MAX:
                starters_m1.append((score, token, positions))

        # Wenn kein Starter gefunden -> nochmal mit Token auf 4 Zeichen normalisiert
        if not starters_m1:
            token_positions_short = {}
            for b in ub:
                ft = b['lines'][0]['first_token']
                if ft and len(ft) >= 4:
                    ft_short = ft[:4]
                    if ft_short not in token_positions_short:
                        token_positions_short[ft_short] = []
                    token_positions_short[ft_short].append(b['index'])
            for token, positions in token_positions_short.items():
                if len(positions) < GROUP_MIN_COUNT:
                    continue
                dists = [positions[i+1] - positions[i] for i in range(len(positions)-1)]
                if len(dists) < 2:
                    continue
                var = statistics.variance(dists)
                avg = sum(dists) / len(dists)
                if avg < GROUP_MIN_DIST:
                    continue
                score = var / avg
                if score < GROUP_SCORE_MAX:
                    starters_m1.append((score, token, positions))

        if starters_m1:
            starters_m1.sort(key=lambda x: x[0])
            _, best_token, starter_pos = starters_m1[0]
            for i, start_idx in enumerate(starter_pos):
                end_idx = starter_pos[i+1] - 1 if i+1 < len(starter_pos) else blocks[-1]['index']
                grp = [b for b in blocks if start_idx <= b['index'] <= end_idx
                       and b['index'] not in grouped]
                if grp:
                    make_group('EXPERIENCE_GROUP', grp)

        # ── M1b: Suche nach Gruppen-ENDE Token ──────────────────────────────────
        # Wenn keine Gruppen oder Gruppen zu gross → suche Token am Gruppen-Ende
        m1_starter_count = len(starter_pos) if starters_m1 else 0
        if not groups or (m1_starter_count > 0 and len(groups) < m1_starter_count // 2):
            grouped.clear()
            groups.clear()
            group_counter[0] = 0

            token4_positions = {}
            for b in blocks:
                ft = b['lines'][0]['first_token']
                if ft and len(ft) >= 4:
                    ft4 = ft[:4]
                    if ft4 not in token4_positions:
                        token4_positions[ft4] = []
                    token4_positions[ft4].append(b['index'])

            end_starters = []
            for token4, positions in token4_positions.items():
                if len(positions) < GROUP_MIN_COUNT:
                    continue
                dists = [positions[i+1] - positions[i] for i in range(len(positions)-1)]
                if len(dists) < 2:
                    continue
                var = statistics.variance(dists)
                avg = sum(dists) / len(dists)
                if avg < GROUP_MIN_DIST:
                    continue
                score = var / avg
                if score < GROUP_SCORE_MAX:
                    end_starters.append((score, token4, positions))

            if end_starters:
                end_starters.sort(key=lambda x: (-len(x[2]), x[0]))
                _, end_token4, end_positions = end_starters[0]

                for i, end_idx in enumerate(end_positions):
                    start_idx = end_positions[i-1] + 1 if i > 0 else blocks[0]['index']
                    grp = [b for b in blocks if start_idx <= b['index'] <= end_idx
                           and b['index'] not in grouped]
                    if grp:
                        make_group('EXPERIENCE_GROUP', grp)
                last_end = end_positions[-1]
                grp = [b for b in blocks if b['index'] > last_end
                       and b['index'] not in grouped]
                if grp:
                    make_group('EXPERIENCE_GROUP', grp)

        # ── M2: has_date + langer Text als Starter ────────────────────────────
        ub = ungrouped()
        date_starters = []
        for b in ub:
            fl = b['lines'][0]
            if fl['has_date'] and fl['text_len'] > 10 and not fl['is_bullet']:
                date_starters.append(b['index'])

        if len(date_starters) >= 2:
            ub_indices = [b['index'] for b in ub]
            max_ub_idx = max(ub_indices) if ub_indices else 0
            for i, start_idx in enumerate(date_starters):
                end_idx = date_starters[i+1] - 1 if i+1 < len(date_starters) else max_ub_idx
                grp = [b for b in ub if start_idx <= b['index'] <= end_idx
                       and b['index'] not in grouped]
                if grp:
                    make_group('EXPERIENCE_GROUP', grp)

        # ── M3: Rest als Einzelgruppen ────────────────────────────────────────
        for b in ungrouped():
            make_group(b['label'], [b])

        return sorted(groups, key=lambda g: g['group_id'])

    # ── 10. LLM-Vorbereitung ──────────────────────────────────────────────────

    def prepare_for_llm(self, result: dict) -> str:
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

    def get_block_text(self, result: dict, block_indices: list) -> str:
        """Vollstaendiger Text der angegebenen Block-Indizes."""
        idx_set = set(block_indices)
        return '\n'.join(b['text'] for b in result['blocks']
                         if b['index'] in idx_set)

    def prepare_groups_for_llm(self, groups: list) -> str:
        """Format: G[Nr]|p[Seite]|[label]|[Erste Zeile]"""
        out = []
        for g in groups:
            first_line = g['blocks'][0]['lines'][0]['text'][:80]
            out.append(
                f"G{g['group_id']:03d}|p{g['page']:02d}|"
                f"{g['label']}|{first_line}"
            )
        return '\n'.join(out)


# Singleton
cv_block_detector = CVBlockDetector()
