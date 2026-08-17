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
    erste = block.get('lines', [''])[0].strip()
    if len(erste) < 4: return None
    return (
        block.get('font', ''),
        round(block.get('width', 0)),
        len(block.get('lines', [])),
        erste[:4].lower()
    )

def _fp_label(fp) -> str:
    return f"w≈{fp[1]}|{fp[2]}Z|'{fp[3]}'"


class MasterDetector:

    def __init__(self):
        try:
            from apps.cv_extractor.services.deepseek_service import deepseek_service
            self.llm = deepseek_service
        except ImportError:
            self.llm = None
        self.parallel_workers = _load_parallel_workers()
        self._prompt_group = None

    def _get_prompt_group(self) -> str:
        if self._prompt_group is None:
            try:
                from apps.cv_extractor.models import PromptTemplate
                prompt = PromptTemplate.objects.get(
                    name="master_detector_group", is_active=True
                )
                self._prompt_group = prompt.prompt_text
            except Exception as e:
                print(f"⚠️ Prompt nicht in DB: {e}")
                self._prompt_group = """Du bist ein CV-Analyse Spezialist.

{cv_info}{prefix}{chunk_text}

AUFGABE:
Fasse benachbarte Bloecke zu logischen Gruppen zusammen.

Antworte NUR mit JSON:
{{"gruppen": [{{"nr": 1, "blocks": [1,2,3], "label": "kurze Beschreibung"}}], "rest": []}}"""
        return self._prompt_group

    def _get_prompt_group_boundary(self) -> str:
        try:
            from apps.cv_extractor.models import PromptTemplate
            prompt = PromptTemplate.objects.get(
                name="master_detector_group_boundary", is_active=True
            )
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
        return blocks

    def format_blocks(self, blocks: list) -> list:
        result = []
        for i, b in enumerate(blocks):
            dist       = round(b[1]['y'] - b[0]['y'], 1) if len(b) > 1 else 0
            first      = b[0]
            bold_str   = 'B' if first.get('bold')   else '.'
            italic_str = 'I' if first.get('italic') else '.'
            font       = first.get('font', '')[:20]
            width      = first.get('width', round(first.get('x1', 0) - first.get('x0', 0), 1))
            result.append({
                'index':  i + 1,
                'page':   first['page'],
                'sz':     first['sz'],
                'bold':   first.get('bold',   False),
                'italic': first.get('italic', False),
                'font':   font,
                'width':  width,
                'lines':  [l['text'] for l in b],
                'text':   ' '.join(l['text'] for l in b),
                'header': (
                    f"{'#'*50} Block {i+1} | p{first['page']:02d} | "
                    f"sz={first['sz']} | {bold_str}{italic_str} | "
                    f"fn={font} | w={width} | "
                    f"{len(b)} Zeilen | ld={dist}"
                ),
            })
        return result

    def blocks_to_text(self, blocks: list, max_zeilen: int = 2) -> str:
        """Gibt max. erste + letzte max_zeilen Zeilen pro Block aus."""
        out = []
        for b in blocks:
            out.append(f"\n{b['header']}")
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

        # 2. Fingerabdruck-Analyse
        fingerprints = defaultdict(list)
        for b in blocks:
            if not _is_header_block(b): continue
            fp = _get_fp(b)
            if fp: fingerprints[fp].append(b['index'])

        alle_muster = {}
        for fp, block_nrs in fingerprints.items():
            if len(block_nrs) < 3: continue
            sh        = sorted(block_nrs)
            abstaende = [sh[i+1] - sh[i] for i in range(len(sh)-1)]
            avg_abst  = sum(abstaende) / len(abstaende)
            min_abst  = min(abstaende)
            if avg_abst > 2.5 and min_abst >= 2:
                endet_dp = all(
                    ' '.join(blocks[nr-1]['lines']).strip().endswith(':')
                    for nr in sh if nr <= len(blocks)
                )
                alle_muster[fp] = {
                    'blocks': sh, 'avg': round(avg_abst, 1),
                    'min': min_abst, 'endet_dp': endet_dp
                }

        # 3. Sequenz-Muster
        sequence_counts = defaultdict(lambda: defaultdict(int))
        for i, b in enumerate(blocks[:-1]):
            fp_c = _get_fp(b)
            fp_n = _get_fp(blocks[i+1])
            curr = _fp_label(fp_c) if fp_c else None
            nxt  = _fp_label(fp_n) if fp_n else None
            if _is_bullet_block(b):           curr = 'BULLET'
            if _is_bullet_block(blocks[i+1]): nxt  = 'BULLET'
            if curr and nxt: sequence_counts[curr][nxt] += 1

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
            ist_sub = info['endet_dp'] or len(kommt_nach) > 0
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
            prompt = PromptTemplate.objects.get(
                name="master_detector_quality", is_active=True
            )
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

        # Schritt 1: Spans → Lines (bereits als dicts)
        t0    = time.time()
        lines = []
        for s in spans:
            lines.append({
                'page':      s.get('page', 1),
                'y':         float(s.get('y', 0)),
                'x':         float(s.get('x', 0)),
                'sz':        float(s.get('size', s.get('sz', 12.0))),
                'bold':      bool(s.get('bold', False)),
                'italic':    bool(s.get('italic', False)),
                'font':      str(s.get('font', '')),
                'text':      str(s.get('text', '')),
                'width':     float(s.get('width', 0)),
                'column_id': int(s.get('column_id', -1)),
                'x0': 0.0, 'y0': 0.0, 'x1': 0.0, 'y1': 0.0, 'ox': 0.0, 'oy': 0.0,
            })
        # column_id beachten: erst linke Spalte (col=0), dann rechte (col=1)
        lines.sort(key=lambda l: (l['page'], l['column_id'], l['y']))
        print(f"  Zeilen: {len(lines)} ({time.time()-t0:.1f}s)")

        # Schritt 2: Blöcke
        t0         = time.time()
        raw_blocks = self.split_blocks(lines)
        blocks     = self.format_blocks(raw_blocks)
        print(f"  Bloecke: {len(blocks)} ({time.time()-t0:.1f}s)")

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
master_detector = MasterDetector()
