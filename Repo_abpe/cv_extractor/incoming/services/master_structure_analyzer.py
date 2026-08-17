"""
master_structure_analyzer.py
Ein LLM-Aufruf analysiert ALLE Blöcke und gibt die komplette Struktur zurück.
"""

from pathlib import Path
import json
import re


class MasterStructureAnalyzer:

    def __init__(self):
        try:
            from apps.cv_extractor.services.deepseek_service import deepseek_service
            self.llm = deepseek_service
        except ImportError:
            self.llm = None

    # ============================================================
    # PROMPT: Analysiert ALLE Blöcke auf einmal
    # ============================================================
    PROMPT = """Du bist ein CV-Analyse Spezialist.

Hier sind ALLE Blöcke eines Lebenslaufs (insgesamt {total_blocks} Blöcke):

{blocks_sample}

AUFGABE:
Analysiere die STRUKTUR dieses CVs vollständig. Erkenne alle Muster und gib zurück:

1. **cv_structure.detected_patterns**:
   - project_sequence: Die Reihenfolge der Blöcke in einem Projekt (z.B. ["project_nr", "period", "company", "industry", "description_start", "bullet_list", "tech_start", "bullet_list"])
   - project_repeat: Wie oft wiederholt sich dieses Muster?
   - typical_blocks_per_project: Wie viele Blöcke hat ein Projekt typischerweise?
   - personal_blocks: Welche Blocknummern enthalten persönliche Daten?
   - skills_blocks: Welche Blocknummern enthalten Skills?
   - certification_blocks: Welche Blocknummern enthalten Zertifikate?
   - education_blocks: Welche Blocknummern enthalten Ausbildung?
   - other_blocks: Alle anderen Blöcke

2. **cv_structure.block_patterns**:
   - Für jedes Muster: regex, examples
   - project_start_pattern: Wie beginnt ein Projekt?
   - period_pattern: Wie sieht ein Zeitraum aus?
   - company_pattern: Wie wird eine Firma genannt?
   - industry_pattern: Wie wird eine Branche genannt?
   - description_start: Womit beginnt die Beschreibung?
   - bullet_pattern: Wie sehen Aufzählungen aus?
   - tech_start: Womit beginnt die Technologie-Liste?

3. **regex_rules**: Für jedes Muster eine Regel mit:
   - pattern_name: Name des Musters
   - regex: Regulärer Ausdruck
   - action: "start_new_group", "continue_group", "collect"
   - field: Feldname für die Extraktion
   - group_type: "experience", "personal", "skills", etc.

4. **block_groups**: Jede logische Gruppe mit:
   - group_id: fortlaufende Nummer
   - blocks: Liste der Blocknummern
   - type: personal, skills, experience, certification, education, kopf, other

Antworte NUR mit JSON. KEINE Erklärungen.

BEISPIEL FÜR DIE JSON-STRUKTUR:
{
  "cv_structure": {
    "total_blocks": 293,
    "detected_patterns": {
      "project_sequence": ["project_nr", "period", "company", "industry", "description_start", "bullet_list", "tech_start", "bullet_list"],
      "project_repeat": 15,
      "typical_blocks_per_project": 8,
      "personal_blocks": [1,2],
      "skills_blocks": [200,230,258,270,288,290],
      "certification_blocks": [],
      "education_blocks": [193,200],
      "other_blocks": [3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20]
    },
    "block_patterns": {
      "project_start_pattern": {
        "regex": "Projekt \\\\d+",
        "examples": ["Projekt 65", "Projekt 64", "Projekt 63"]
      },
      "period_pattern": {
        "regex": "\\\\d{2}/\\\\d{4}\\\\s*[–-]\\\\s*\\\\d{2}/\\\\d{4}",
        "examples": ["06/2024-aktuell", "05/2024-03/2025"]
      }
    }
  },
  "regex_rules": [
    {
      "pattern_name": "project_nr",
      "regex": "Projekt \\\\d+",
      "action": "start_new_group",
      "group_type": "experience"
    }
  ],
  "block_groups": [
    {"group_id": 1, "blocks": [1,2], "type": "personal"},
    {"group_id": 2, "blocks": [3,4,5,6,7,8,9,10,11], "type": "other"}
  ]
}"""

    # ============================================================
    # HILFSFUNKTIONEN
    # ============================================================

    def read_yx(self, yx_path: str) -> list:
        lines = []
        for raw in Path(yx_path).read_text(encoding='utf-8').splitlines():
            if raw.startswith('#') or not raw.strip():
                continue
            parts = raw.split('|')
            if len(parts) < 13:
                continue
            try:
                text = parts[12].strip()
                lines.append({'text': text, 'raw': raw})
            except:
                continue
        return lines

    def split_blocks(self, lines: list) -> list:
        blocks = []
        for i, line in enumerate(lines):
            blocks.append({
                'index': i + 1,
                'text': line['text'],
                'raw': line['raw']
            })
        return blocks

    def blocks_to_summary(self, blocks: list) -> str:
        """Vollständige Liste aller Blöcke (keine Kürzung)."""
        out = []
        for b in blocks:
            text = b['text'][:150].replace('\n', ' ')
            out.append(f"Block {b['index']:3d}: {text}")
        return '\n'.join(out)

    # ============================================================
    # HAUPT-ANALYSE
    # ============================================================

    def analyze(self, yx_path: str) -> dict:
        print(f"[MasterStructureAnalyzer] Analysiere: {Path(yx_path).stem[:30]}")
        
        # 1. Blöcke laden
        lines = self.read_yx(yx_path)
        blocks = self.split_blocks(lines)
        print(f"  Blöcke: {len(blocks)}")
        
        # 2. Vollständige Liste aller Blöcke für LLM
        blocks_summary = self.blocks_to_summary(blocks)
        print(f"  Sende {len(blocks)} Blöcke an LLM ({(len(blocks_summary)//1000)} KB)...")
        
        # 3. LLM-Aufruf
        prompt = self.PROMPT.format(total_blocks=len(blocks), blocks_sample=blocks_summary)
        
        response = self.llm.extract(prompt)
        
        if response.success and response.data:
            result = response.data
            print(f"  ✅ Analyse erfolgreich")
            return result
        else:
            print(f"  ❌ Fehler: {response.error}")
            return {}

    # ============================================================
    # GRUPPEN BAUEN
    # ============================================================

    def build_groups(self, analysis: dict, blocks: list) -> list:
        block_groups = analysis.get('block_groups', [])
        
        groups = []
        for bg in block_groups:
            group_blocks = []
            for block_nr in bg.get('blocks', []):
                if 1 <= block_nr <= len(blocks):
                    group_blocks.append(block_nr)
            
            groups.append({
                'blocks': group_blocks,
                'type': bg.get('type', 'unknown'),
                'label': f"{bg.get('type', 'unknown').upper()}"
            })
        
        return groups


    def analyze_from_spans(self, spans: list) -> dict:
        """
        Wie analyze() aber direkt aus Span-Dicts im RAM — keine yx.txt nötig.
        spans: Liste von dicts mit keys: page, y, x, size/sz, bold, italic, font, text
        """
        # Spans → einfache Block-Liste
        blocks = []
        for i, s in enumerate(spans):
            text = str(s.get('text', '')).strip()
            if text:
                blocks.append({
                    'index': i + 1,
                    'text':  text,
                    'raw':   f"p{s.get('page',1)}|{text}",
                })

        print(f"[MasterStructureAnalyzer] analyze_from_spans: {len(blocks)} Blöcke")

        blocks_summary = self.blocks_to_summary(blocks)
        print(f"  Sende {len(blocks)} Blöcke an LLM ({len(blocks_summary)//1000} KB)...")

        prompt   = self.PROMPT.format(
            total_blocks=len(blocks), blocks_sample=blocks_summary)
        response = self.llm.extract(prompt)

        if response.success and response.data:
            print(f"  ✅ Analyse erfolgreich")
            return response.data
        else:
            print(f"  ❌ Fehler: {getattr(response, 'error', '')}")
            return {}


master_analyzer = MasterStructureAnalyzer()
