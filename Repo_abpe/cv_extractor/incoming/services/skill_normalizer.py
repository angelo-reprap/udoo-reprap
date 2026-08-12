"""
skill_normalizer.py - Skill-Normalisierung via normalize_skill_* Prompts

Ablauf:
1. Input: Counter {skill_name: count} aus Projekt-Technologien (RAM)
2. Duplikate entfernen (case-insensitive)
3. Sequenziell durch NORMALIZE_ORDER (spezifisch → generisch)
   Pro Kategorie: ALLE übrigen Skills auf einmal in einen Prompt
   → bestätigt → Kategorie + Weight zugewiesen → raus aus Liste
   → übrig → nächste Kategorie
4. Rest → Sonstige Skills
5. save_to_db() → ConsultantSkill + ExperienceTechnology in DB

Gewichtung:
  Faktor 1: Kumulierte Monate (50%) — wie lange mit dem Skill gearbeitet
  Faktor 2: Projektbreite     (40%) — in wie vielen Projekten
  Faktor 3: Count             (10%) — wie oft erwähnt

  _parse_months()     → Regex (schnell)
  _parse_months_llm() → LLM Fallback wenn Regex 0 zurückgibt
  _get_months()       → Hauptfunktion: Regex → bei 0 → LLM
  Parallelisierung:   → parallel_workers_projects aus settings.json

Changelog:
  2026-04-28: Pattern 0 + 0b für GULP Format YYYY-MM – YYYY-MM hinzugefügt
              Bereinigung greift NACH GULP-Pattern-Prüfung
"""

import json
import logging
import os
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger(__name__)

# Reihenfolge: spezifisch → generisch → Sonstige Skills immer letzter
NORMALIZE_ORDER = [
    # 1. Sehr spezifisch / selten
    'CI/CD Tools',
    'Testing Tools',
    'Versionsverwaltung',
    'Dokumentationstools',
    'Kommunikationstools',
    'Architekturmuster',
    'Spezielle Konzepte',
    'Methoden',
    'Datenformate',
    'Datenmanagement',
    'Identity Management',
    'Cloud-Plattformen',
    'Monitoring Tools',
    'Projektmanagement Tools',
    'Business Software',
    'Soft Skills',
    # 2. Mittel
    'Security Tools',
    'Netzwerkprotokolle',
    'Entwicklungsumgebungen',
    'Frameworks und Bibliotheken',
    'Virtualisierung',
    'DevOps Tools',
    # 3. Häufig
    'Programmiersprachen',
    'Betriebssysteme',
    'Datenbanken',
    # 4. Sehr häufig
    'Hardware',
    'IT-Infrastruktur',
    # 5. Immer letzter!
    'Sonstige Skills',
]


def _get_workers() -> int:
    """Liest parallel_workers_projects aus settings.json."""
    try:
        from django.conf import settings
        cfg_path = os.path.join(settings.BASE_DIR, 'settings.json')
        with open(cfg_path) as f:
            cfg = json.load(f)
        return int(cfg.get('pipeline', {}).get('parallel_workers_projects', 10))
    except Exception:
        return 10


def _parse_months(period: str) -> int:
    """
    Parst einen Zeitraum-String via Regex.
    Gibt 0 zurück wenn nicht parsebar → dann LLM Fallback.

    Unterstützte Formate:
      "2025-01 – 2025-09"   → 9 Monate  (GULP Format)
      "2023-01 – heute"     → n Monate  (GULP Format offen)
      "01/2023 - 06/2025"   → 30 Monate
      "01/2022 - 12/2022"   → 12 Monate
      "seit 01/2024"        → bis heute
      "2020 - 2024"         → 48 Monate
      "2024 - heute"        → 6 Monate (default)
    """
    if not period or not period.strip():
        return 0

    now = datetime.now()

    def _today_month():
        """Enddatum heute: Tag ≤ 15 → aktueller Monat, Tag > 15 → nächster Monat."""
        if now.day <= 15:
            return now.year, now.month
        else:
            if now.month == 12:
                return now.year + 1, 1
            return now.year, now.month + 1

    raw = period.strip()

    # ── GULP-Formate: VOR Bereinigung prüfen ─────────────────────────────────
    # Pattern 0: "YYYY-MM – YYYY-MM" oder "YYYY-MM - YYYY-MM"
    m = re.search(r'(\d{4})-(\d{2})\s*[–—\-]+\s*(\d{4})-(\d{2})', raw)
    if m:
        from_y = int(m.group(1))
        from_m = int(m.group(2))
        to_y   = int(m.group(3))
        to_m   = int(m.group(4))
        months = (to_y * 12 + to_m) - (from_y * 12 + from_m) + 1
        return max(1, months)

    # Pattern 0b: "YYYY-MM – heute/dato/aktuell/now" (GULP offen)
    m = re.search(
        r'(\d{4})-(\d{2})\s*[–—\-]+\s*(heute|dato|aktuell|laufend|present|current|now)',
        raw, re.IGNORECASE
    )
    if m:
        from_y   = int(m.group(1))
        from_m   = int(m.group(2))
        end_y, end_m = _today_month()
        months   = (end_y * 12 + end_m) - (from_y * 12 + from_m) + 1
        return max(6, months)

    # ── Bereinigung für klassische Formate ───────────────────────────────────
    p = raw
    p = p.replace('–', '-').replace('—', '-').replace('bis', '-')
    p = p.replace('\\', '/').replace('.', '/')
    p = re.sub(r'[*_~`|]', '', p)
    p = re.sub(r'\s*-+\s*', ' - ', p)
    p = re.sub(r'\s+', ' ', p).strip()

    # Pattern 1: "MM/YYYY - MM/YYYY"
    m = re.search(r'(\d{1,2})[/](\d{4})\s*-\s*(\d{1,2})[/](\d{4})', p)
    if m:
        from_m = int(m.group(1))
        from_y = int(m.group(2))
        to_m   = int(m.group(3))
        to_y   = int(m.group(4))
        months = (to_y * 12 + to_m) - (from_y * 12 + from_m) + 1
        return max(1, months)

    # Pattern 2: "MM/YYYY - heute/dato/aktuell/laufend"
    m = re.search(
        r'(\d{1,2})[/](\d{4})\s*-\s*(heute|dato|aktuell|laufend|present|current)',
        p, re.IGNORECASE
    )
    if m:
        from_m   = int(m.group(1))
        from_y   = int(m.group(2))
        end_y, end_m = _today_month()
        months   = (end_y * 12 + end_m) - (from_y * 12 + from_m) + 1
        return max(6, months)

    # Pattern 3: "seit MM/YYYY"
    m = re.search(r'seit\s+(\d{1,2})[/](\d{4})', p, re.IGNORECASE)
    if m:
        from_m   = int(m.group(1))
        from_y   = int(m.group(2))
        end_y, end_m = _today_month()
        months   = (end_y * 12 + end_m) - (from_y * 12 + from_m) + 1
        return max(6, months)

    # Pattern 4: "YYYY - YYYY" (nur Jahre)
    m = re.search(r'(\d{4})\s*-\s*(\d{4})', p)
    if m:
        from_y = int(m.group(1))
        to_y   = int(m.group(2))
        return max(12, (to_y - from_y) * 12)

    # Pattern 5: "YYYY - heute/aktuell"
    m = re.search(
        r'(\d{4})\s*-\s*(heute|dato|aktuell|laufend|present|current)',
        p, re.IGNORECASE
    )
    if m:
        return 6

    # Pattern 6: einzelne MM/YYYY
    m = re.search(r'(\d{1,2})[/](\d{4})', p)
    if m:
        return 6

    return 0  # → LLM Fallback


def _parse_months_llm(period: str) -> int:
    """
    LLM Fallback wenn Regex 0 zurückgibt.
    Hardcoded Prompt — allgemeingültig, kein DB-Prompt nötig.
    """
    from .deepseek_api import deepseek_api

    now = datetime.now()

    if now.day <= 15:
        today_str = f"{now.month:02d}/{now.year}"
    else:
        if now.month == 12:
            today_str = f"01/{now.year + 1}"
        else:
            today_str = f"{now.month + 1:02d}/{now.year}"

    prompt = f"""Berechne die Anzahl der Monate fuer diesen Zeitraum: "{period}"

Regeln:
- Heute / aktuell / laufend / dato = {today_str}
- Nur Jahreszahlen ohne Monate (z.B. "2020 - 2024"): pro Jahr 12 Monate rechnen
- Nur ein Jahr ohne Ende (z.B. "2024 bis heute"): 6 Monate zurueckgeben
- Minimum immer 6 Monate
- Ergebnis = Endmonat - Startmonat + 1

Antworte NUR mit einer einzigen Zahl. Beispiele:
"01/2023 - 06/2025" → 30
"2020 - 2022" → 24
"2024 bis heute" → 6"""

    try:
        r = deepseek_api.extract(prompt, system_prompt='Antworte NUR mit einer einzigen Zahl.')
        if r.success and r.data:
            raw  = str(r.data).strip()
            nums = re.findall(r'\d+', raw)
            if nums:
                months = int(nums[0])
                return max(6, months)
    except Exception as e:
        logger.warning(f"  _parse_months_llm fehlgeschlagen fuer '{period}': {e}")

    return 6  # fallback


def _get_months(period: str) -> int:
    """
    Hauptfunktion: Regex versuchen → bei 0 → LLM Fallback.
    Minimum immer 6 Monate.
    """
    months = _parse_months(period)
    if months == 0:
        logger.debug(f"  Regex fehlgeschlagen fuer '{period}' → LLM Fallback")
        months = _parse_months_llm(period)
    return max(6, months)


def _count_to_weight(count: int, project_count: int = 1,
                     total_months: int = 0) -> float:
    """
    Gewichtung aus 3 Faktoren:
      Faktor 1: Kumulierte Monate (50%) — wichtigster Faktor
      Faktor 2: Projektbreite     (40%) — in wie vielen Projekten
      Faktor 3: Count             (10%) — wie oft erwähnt
    """
    # Faktor 1: Kumulierte Monate
    if total_months >= 60:   month_score = 1.0   # 5+ Jahre
    elif total_months >= 36: month_score = 0.85  # 3+ Jahre
    elif total_months >= 12: month_score = 0.70  # 1+ Jahr
    elif total_months >= 6:  month_score = 0.50  # 6+ Monate
    else:                    month_score = 0.30  # < 6 Monate

    # Faktor 2: Projektbreite
    if project_count >= 5:   proj_score = 1.0
    elif project_count >= 3: proj_score = 0.75
    elif project_count >= 2: proj_score = 0.50
    else:                    proj_score = 0.25

    # Faktor 3: Count
    if count >= 10:  count_score = 1.0
    elif count >= 5: count_score = 0.75
    elif count >= 2: count_score = 0.50
    else:            count_score = 0.25

    # Gewichtete Kombination: Monate 50%, Projekte 40%, Count 10%
    weight = (month_score * 0.50) + (proj_score * 0.40) + (count_score * 0.10)
    return round(min(weight, 0.95), 2)


class SkillNormalizer:

    def normalize(self, tech_counter: Counter, headline: str = "") -> Dict[str, Dict]:
        """
        Input:  Counter {skill_name: count}
        Output: {skill_name: {'category': cat_name, 'count': int}}
        Sequenziell durch NORMALIZE_ORDER — Pflicht wegen Abhängigkeit!
        """
        from ..models import PromptTemplate
        from .deepseek_api import deepseek_api

        if not tech_counter:
            return {}

        # Prompts laden
        prompts = {}
        for pt in PromptTemplate.objects.filter(
            stage__startswith='normalize_skill_', is_active=True
        ):
            cat = pt.stage.replace('normalize_skill_', '')
            prompts[cat] = pt.prompt_text

        # Duplikate entfernen (case-insensitive) — höherer Count gewinnt
        deduped = {}
        for skill, count in tech_counter.items():
            if not skill or len(skill.strip()) < 2:
                continue
            key = skill.strip().lower()
            if key not in deduped or count > deduped[key][1]:
                deduped[key] = (skill.strip(), count)

        # Arbeitsliste: {original_name: count}
        remaining = {orig: count for (orig, count) in deduped.values()}
        result    = {}  # {skill_name: {category, count}}

        total_start = len(remaining)
        logger.info(f"  SkillNormalizer START: {total_start} Skills")

        # Sequenziell durch NORMALIZE_ORDER (Pflicht — Abhängigkeit!)
        for cat in NORMALIZE_ORDER:
            if not remaining:
                logger.info(f"  Alle Skills kategorisiert!")
                break

            if cat == 'Sonstige Skills':
                logger.info(f"  Sonstige Skills: {len(remaining)} nicht zugeordnet")
                for skill, count in remaining.items():
                    result[skill] = {
                        'category': 'Sonstige Skills',
                        'count':    count,
                    }
                remaining = {}
                break

            if cat not in prompts:
                logger.warning(f"  Kein Prompt fuer: {cat}")
                continue

            # Alle übrigen Skills auf einmal in einen Prompt
            skills_list = list(remaining.keys())
            context     = f"Berater-Kontext: {headline}\n\n" if headline else ""
            prompt      = context + prompts[cat].replace('{text}', ', '.join(skills_list))
            r           = deepseek_api.extract(prompt,
                              system_prompt='Antworte NUR mit JSON.')

            confirmed = []
            if r.success and r.data:
                data = r.data if isinstance(r.data, dict) else {}
                for v in data.values():
                    if isinstance(v, list):
                        confirmed.extend([str(x).strip() for x in v])

            # Case-insensitive matching
            confirmed_lower = {c.lower() for c in confirmed}
            matched = [
                s for s in skills_list
                if s.lower() in confirmed_lower
                or any(s.lower() in c for c in confirmed_lower)
            ]

            if matched:
                logger.info(
                    f"  {cat}: {len(matched)} Skills → "
                    f"{len(remaining) - len(matched)} übrig"
                )
                for skill in matched:
                    result[skill] = {
                        'category': cat,
                        'count':    remaining[skill],
                    }
                    del remaining[skill]
            else:
                logger.info(f"  {cat}: 0 Skills")

        logger.info(f"  SkillNormalizer FERTIG: {len(result)} Skills kategorisiert")
        return result

    def save_to_db(self, consultant, normalized: Dict[str, Dict],
                   experience_map: Dict[str, List] = None) -> Dict[str, int]:
        """
        Schreibt normalisierte Skills in:
        - ConsultantSkill (mit Kategorie + Gewichtung)
        - ExperienceTechnology (Verknüpfung Projekt → Skill)

        Gewichtung berechnet aus:
        - count:         wie oft Skill insgesamt erwähnt
        - project_count: in wie vielen Projekten
        - total_months:  kumulierte Laufzeit — parallel berechnet!
        """
        from ..models import Skill, ConsultantSkill, SkillCategory, ExperienceTechnology

        if not normalized:
            return {'added': 0, 'updated': 0}

        workers = _get_workers()
        added   = updated = 0

        for skill_name, info in normalized.items():
            cat_name = info['category']
            count    = info.get('count', 1)

            # project_count + total_months aus experience_map berechnen
            project_count = 0
            total_months  = 0

            if experience_map and skill_name in experience_map:
                exp_list      = experience_map[skill_name]
                project_count = len(exp_list)

                # Periods sammeln
                periods = [
                    getattr(exp, 'period', '') or ''
                    for exp in exp_list
                ]

                # Parallel parsen — LLM Fallbacks laufen gleichzeitig!
                with ThreadPoolExecutor(max_workers=workers) as executor:
                    months_list = list(executor.map(_get_months, periods))

                total_months = sum(months_list)

                logger.debug(
                    f"  {skill_name}: periods={periods} → "
                    f"months={months_list} → total={total_months}"
                )

            # Minimum: 1 Projekt, 6 Monate
            project_count = max(1, project_count)
            total_months  = max(6, total_months)

            weight = _count_to_weight(count, project_count, total_months)

            logger.info(
                f"  {skill_name}: count={count}, "
                f"projekte={project_count}, "
                f"monate={total_months}, "
                f"weight={weight}"
            )

            # SkillCategory FK
            cat = SkillCategory.objects.filter(name=cat_name).first()

            # Skill get_or_create
            skill, created = Skill.objects.get_or_create(
                name=skill_name[:200],
                defaults={
                    'category':      cat,
                    'category_name': cat_name,
                }
            )

            # Kategorie updaten falls besser
            if not skill.category_name or skill.category_name == 'Sonstige Skills':
                if cat_name != 'Sonstige Skills':
                    skill.category      = cat
                    skill.category_name = cat_name
                    skill.save(update_fields=['category', 'category_name'])

            # ConsultantSkill
            cs, cs_created = ConsultantSkill.objects.get_or_create(
                consultant=consultant,
                skill=skill,
                defaults={'weight': weight, 'category_name': cat_name}
            )
            if cs_created:
                added += 1
            elif weight > cs.weight:
                cs.weight = weight
                cs.save(update_fields=['weight'])
                updated += 1

            # ExperienceTechnology — Verknüpfung zu Projekten
            if experience_map and skill_name in experience_map:
                for exp in experience_map[skill_name]:
                    ExperienceTechnology.objects.get_or_create(
                        experience=exp,
                        skill=skill
                    )

        logger.info(f"  save_to_db: +{added} neu, {updated} aktualisiert")
        return {'added': added, 'updated': updated}


skill_normalizer = SkillNormalizer()
