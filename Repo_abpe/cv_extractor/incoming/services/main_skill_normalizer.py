"""
main_skill_normalizer.py - Skill-Normalisierung fuer main_pipeline

Ablauf:
1. Input: experience[].technologies[] aus pre_json (RAM)
2. Schritt 1: Bereits in pre_json.skills{} oder skill_ablage? → Kategorie bekannt
3. Schritt 2: In TrainingTerm DB? → Kategorie aus DB
4. Schritt 3: Unbekannt → Sonstige Skills + unknown_skills fuer Self-Learning

WICHTIG:
- Normalizer darf NICHT in TrainingTerm schreiben — das ist Self-Learning Aufgabe
- Normalizer darf NICHT Skill.category_name aendern
- Normalizer schreibt NUR ConsultantSkill + ExperienceTechnology

unknown_skills Format:
  "OSPF.AID-mm_1.2.3.1.exp_42&45.Mustermann.Max"
  → skill_name|AID.exp_id1&exp_id2.last_name.first_name

  Kontext-String fuer LLM (max 3000 Zeichen):
  - Groesstes Projekt zuerst   (max 1500 Zeichen)
  - Aktuellstes Projekt        (max verbleibende Zeichen)
  - Drittes Projekt            (nur wenn noch > 100 Zeichen frei)

Gewichtung:
  Faktor 1: Kumulierte Monate (50%)
  Faktor 2: Projektbreite     (40%)
  Faktor 3: Count             (10%)

Changelog:
  2026-05-12: unknown_skills mit strukturiertem Key + Kontext-String
              experience_map auch in normalize() verfuegbar
              Projekt-Selektion: groesstes + aktuellstes + rest (max 3000 Zeichen)
  2026-05-11: Kompletter Umbau — saubere Aufgabentrennung
              Normalizer liest nur, Self-Learning schreibt TrainingTerm
"""

import json
import logging
import os
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

SKILL_CAT_TO_DB = {
    'programming_languages':   'Programmiersprachen',
    'operating_system':        'Betriebssysteme',
    'database':                'Datenbanken',
    'hardware':                'Hardware',
    'network_protocol':        'Netzwerkprotokolle',
    'it_infrastructure':       'IT-Infrastruktur',
    'methodology':             'Methoden',
    'framework':               'Frameworks und Bibliotheken',
    'cloud_platform':          'Cloud-Plattformen',
    'security_tool':           'Security Tools',
    'devops_tool':             'DevOps Tools',
    'development_environment': 'Entwicklungsumgebungen',
    'documentation_tool':      'Dokumentationstools',
    'monitoring_tool':         'Monitoring Tools',
    'version_control':         'Versionsverwaltung',
    'testing_tool':            'Testing Tools',
    'data_format':             'Datenformate',
    'data_management':         'Datenmanagement',
    'business_software':       'Business Software',
    'special_concept':         'Spezielle Konzepte',
    'soft_skill':              'Soft Skills',
    'virtualization':          'Virtualisierung',
    'ci_cd_tool':              'CI/CD Tools',
    'identity_management':     'Identity Management',
    'communication_tool':      'Kommunikationstools',
    'project_management':      'Projektmanagement Tools',
    'architecture_pattern':    'Architekturmuster',
    'special_skill':           'Sonstige Skills',
}

MAX_CONTEXT_CHARS    = 3000
MAX_FIRST_PROJ_CHARS = 1500
MIN_REMAINING_CHARS  = 100


def _get_workers() -> int:
    try:
        from django.conf import settings
        cfg_path = os.path.join(settings.BASE_DIR, 'settings.json')
        with open(cfg_path) as f:
            cfg = json.load(f)
        return int(cfg.get('pipeline', {}).get('parallel_workers_projects', 10))
    except Exception:
        return 10


def _parse_months(period: str) -> int:
    if not period or not period.strip():
        return 0
    now = datetime.now()

    def _today_month():
        if now.day <= 15:
            return now.year, now.month
        else:
            if now.month == 12:
                return now.year + 1, 1
            return now.year, now.month + 1

    raw = period.strip()

    m = re.search(r'(\d{4})-(\d{2})\s*[–—\-]+\s*(\d{4})-(\d{2})', raw)
    if m:
        from_y = int(m.group(1)); from_m = int(m.group(2))
        to_y   = int(m.group(3)); to_m   = int(m.group(4))
        return max(1, (to_y * 12 + to_m) - (from_y * 12 + from_m) + 1)

    m = re.search(
        r'(\d{4})-(\d{2})\s*[–—\-]+\s*(heute|dato|aktuell|laufend|present|current|now)',
        raw, re.IGNORECASE
    )
    if m:
        from_y = int(m.group(1)); from_m = int(m.group(2))
        end_y, end_m = _today_month()
        return max(6, (end_y * 12 + end_m) - (from_y * 12 + from_m) + 1)

    p = raw.replace('–', '-').replace('—', '-').replace('bis', '-')
    p = p.replace('\\', '/').replace('.', '/')
    p = re.sub(r'[*_~`|]', '', p)
    p = re.sub(r'\s*-+\s*', ' - ', p)
    p = re.sub(r'\s+', ' ', p).strip()

    m = re.search(r'(\d{1,2})[/](\d{4})\s*-\s*(\d{1,2})[/](\d{4})', p)
    if m:
        from_m = int(m.group(1)); from_y = int(m.group(2))
        to_m   = int(m.group(3)); to_y   = int(m.group(4))
        return max(1, (to_y * 12 + to_m) - (from_y * 12 + from_m) + 1)

    m = re.search(
        r'(\d{1,2})[/](\d{4})\s*-\s*(heute|dato|aktuell|laufend|present|current)',
        p, re.IGNORECASE
    )
    if m:
        from_m = int(m.group(1)); from_y = int(m.group(2))
        end_y, end_m = _today_month()
        return max(6, (end_y * 12 + end_m) - (from_y * 12 + from_m) + 1)

    m = re.search(r'seit\s+(\d{1,2})[/](\d{4})', p, re.IGNORECASE)
    if m:
        from_m = int(m.group(1)); from_y = int(m.group(2))
        end_y, end_m = _today_month()
        return max(6, (end_y * 12 + end_m) - (from_y * 12 + from_m) + 1)

    m = re.search(r'(\d{4})\s*-\s*(\d{4})', p)
    if m:
        return max(12, (int(m.group(2)) - int(m.group(1))) * 12)

    m = re.search(
        r'(\d{4})\s*-\s*(heute|dato|aktuell|laufend|present|current)',
        p, re.IGNORECASE
    )
    if m:
        return 6

    m = re.search(r'(\d{1,2})[/](\d{4})', p)
    if m:
        return 6

    return 0


def _get_months(period: str) -> int:
    months = _parse_months(period)
    return max(6, months) if months > 0 else 6


def _get_end_year_month(period: str) -> Tuple[int, int]:
    """
    Gibt (year, month) des Enddatums zurueck — fuer 'aktuellstes Projekt' Sortierung.
    Laufende Projekte bekommen (9999, 12) — sie sind immer aktuellst.
    """
    if not period:
        return (0, 0)
    now = datetime.now()
    p   = period.strip()

    # Laufend
    if re.search(r'(heute|dato|aktuell|laufend|present|current|now)', p, re.IGNORECASE):
        return (9999, 12)

    # YYYY-MM – YYYY-MM
    m = re.search(r'(\d{4})-(\d{2})\s*[–—\-]+\s*(\d{4})-(\d{2})', p)
    if m:
        return (int(m.group(3)), int(m.group(4)))

    # MM/YYYY - MM/YYYY
    m = re.search(r'(\d{1,2})[/](\d{4})\s*-\s*(\d{1,2})[/](\d{4})', p)
    if m:
        return (int(m.group(4)), int(m.group(3)))

    # YYYY - YYYY
    m = re.search(r'(\d{4})\s*-\s*(\d{4})', p)
    if m:
        return (int(m.group(2)), 6)

    # Einzelnes Jahr
    m = re.search(r'\b(19|20)\d{2}\b', p)
    if m:
        return (int(m.group(0)), 6)

    return (0, 0)


def _build_project_context(exp, max_chars: int) -> str:
    """
    Baut einen lesbaren Kontext-String fuer ein Experience-Objekt.
    Felder: period, company, role, activities[], technologies[]
    Gekuerzt auf max_chars.
    """
    parts = []

    period  = getattr(exp, 'period',  '') or ''
    company = getattr(exp, 'company', '') or ''
    role    = getattr(exp, 'role',    '') or getattr(exp, 'title', '') or ''

    if period or company:
        parts.append(f"Projekt: {company} ({period})")
    if role:
        parts.append(f"Rolle: {role}")

    # Aktivitaeten
    activities = []
    try:
        activities = list(exp.activities.values_list('activity_text', flat=True)[:5])
    except Exception:
        pass
    if activities:
        parts.append(f"Aktivitaeten: {'; '.join(str(a) for a in activities)}")

    # Technologien (Co-Skills geben wichtigen Kontext)
    techs = []
    try:
        techs = list(exp.technologies.select_related('skill')
                     .values_list('skill__name', flat=True)[:15])
    except Exception:
        pass
    if techs:
        parts.append(f"Technologien: {', '.join(str(t) for t in techs)}")

    text = '\n'.join(parts)
    if len(text) > max_chars:
        text = text[:max_chars - 3] + '...'
    return text


def _build_unknown_skill_key(skill_name: str, consultant, exp_list: list) -> str:
    """
    Baut den strukturierten Key:
    "OSPF.AID-mm_1.2.3.1.exp_42&45.Mustermann.Max"

    exp_list: Liste von Experience-DB-Objekten (bereits nach Groesse + Datum sortiert)
    Nur die IDs der ausgewaehlten Projekte (max 3) werden eingetragen.
    """
    aid        = getattr(consultant, 'aid',        '') or ''
    last_name  = getattr(consultant, 'last_name',  '') or ''
    first_name = getattr(consultant, 'first_name', '') or ''

    # Nur IDs der uebergebenen Projekte
    exp_ids = '&'.join(str(exp.id) for exp in exp_list) if exp_list else '0'

    # Punkte in Namen/AID schuetzen — ersetze interne Punkte im AID nicht
    # (AID hat Punkte im Versions-Teil — das ist OK, Parser splittet nur die ersten 5)
    key = f"{skill_name}|{aid}.exp_{exp_ids}.{last_name}.{first_name}"
    return key


def _select_projects_for_context(exp_list: list) -> Tuple[list, str]:
    """
    Waehlt max 3 Projekte aus und baut den Kontext-String (max 3000 Zeichen).

    Logik:
      1. Groesstes Projekt  (meiste Monate) → max 1500 Zeichen
      2. Aktuellstes Projekt (neuestes Datum, falls != groesstes) → verbleibende Zeichen
      3. Weiteres Projekt    (falls noch > 100 Zeichen frei)

    Gibt zurueck: (ausgewaehlte_exp_liste, kontext_string)
    """
    if not exp_list:
        return [], ''

    # Monate pro Projekt berechnen
    exp_with_months = []
    for exp in exp_list:
        period = getattr(exp, 'period', '') or ''
        months = _get_months(period)
        end_ym = _get_end_year_month(period)
        exp_with_months.append((exp, months, end_ym))

    # Groesstes Projekt (max Monate)
    biggest = max(exp_with_months, key=lambda x: x[1])

    # Aktuellstes Projekt (max Enddatum) — kann gleich sein wie groesstes
    newest  = max(exp_with_months, key=lambda x: x[2])

    # Reihenfolge aufbauen — Duplikate vermeiden
    ordered = [biggest]
    if newest[0].id != biggest[0].id:
        ordered.append(newest)

    # Weiteres Projekt hinzufuegen (weder groesstes noch aktuellstes)
    used_ids = {e[0].id for e in ordered}
    for item in sorted(exp_with_months, key=lambda x: x[1], reverse=True):
        if item[0].id not in used_ids:
            ordered.append(item)
            break

    # Kontext-String bauen
    context_parts = []
    used_chars    = 0
    selected_exps = []

    for idx, (exp, months, end_ym) in enumerate(ordered):
        if idx == 0:
            max_chars = MAX_FIRST_PROJ_CHARS
        else:
            remaining = MAX_CONTEXT_CHARS - used_chars
            if remaining < MIN_REMAINING_CHARS:
                break
            max_chars = remaining

        proj_text = _build_project_context(exp, max_chars)
        if proj_text:
            context_parts.append(proj_text)
            used_chars += len(proj_text)
            selected_exps.append(exp)

    context_str = '\n---\n'.join(context_parts)
    return selected_exps, context_str


def _count_to_weight(count: int, project_count: int = 1,
                     total_months: int = 0) -> float:
    """
    Gewichtung aus 3 Faktoren:
      Faktor 1: Kumulierte Monate (50%)
      Faktor 2: Projektbreite     (40%)
      Faktor 3: Count             (10%)
    """
    if total_months >= 60:   month_score = 1.0
    elif total_months >= 36: month_score = 0.85
    elif total_months >= 12: month_score = 0.70
    elif total_months >= 6:  month_score = 0.50
    else:                    month_score = 0.30

    if project_count >= 5:   proj_score = 1.0
    elif project_count >= 3: proj_score = 0.75
    elif project_count >= 2: proj_score = 0.50
    else:                    proj_score = 0.25

    if count >= 10:  count_score = 1.0
    elif count >= 5: count_score = 0.75
    elif count >= 2: count_score = 0.50
    else:            count_score = 0.25

    weight = (month_score * 0.50) + (proj_score * 0.40) + (count_score * 0.10)
    return round(min(weight, 0.95), 2)


class SkillNormalizer:

    def normalize(self, tech_counter: Counter, headline: str = '',
                  pre_json: dict = None,
                  experience_map: dict = None,
                  consultant=None) -> Tuple[Dict[str, Dict], List[Dict]]:
        """
        Kategorisiert Projekt-Technologien in 3 Schritten.
        Schreibt NICHTS in DB — nur lesen + kategorisieren.

        Schritt 1: pre_json.skills{} + skill_ablage → Kategorie bekannt
        Schritt 2: TrainingTerm DB → Kategorie aus DB
        Schritt 3: Unbekannt → 'Sonstige Skills' + unknown_skills fuer Self-Learning

        Gibt zurueck:
          result        = {skill_name: {'category': str, 'count': int}}
          unknown_skills = [
            {
              'key':     'OSPF.AID-mm_1.2.3.1.exp_42&45.Mustermann.Max',
              'skill':   'OSPF',
              'context': 'Projekt: Maroc Telekom...\n---\nProjekt: ...',
              'exp_ids': [42, 45],
            },
            ...
          ]
        """
        from ..models import TrainingTerm

        if not tech_counter:
            return {}, []

        # ── Bekannte Skills aus pre_json aufbauen ────────────────────────
        known_skills = {}
        if pre_json:
            ed = pre_json.get('extracted_data', {})
            for cat_key, skill_list in ed.get('skills', {}).items():
                cat_de = SKILL_CAT_TO_DB.get(cat_key, cat_key)
                for name in (skill_list or []):
                    if name:
                        known_skills[name.lower()] = cat_de
            for entry in ed.get('skill_ablage', []):
                if isinstance(entry, dict):
                    name   = entry.get('name', '').strip()
                    cat_de = entry.get('category', 'Sonstige Skills')
                    if name:
                        known_skills[name.lower()] = cat_de

        # ── Duplikate entfernen ───────────────────────────────────────────
        deduped = {}
        for skill, count in tech_counter.items():
            if not skill or len(skill.strip()) < 2:
                continue
            key = skill.strip().lower()
            if key not in deduped or count > deduped[key][1]:
                deduped[key] = (skill.strip(), count)

        remaining = {orig: count for (orig, count) in deduped.values()}
        result    = {}
        unknown_skills = []

        logger.info(f"  SkillNormalizer START: {len(remaining)} Projekt-Skills")

        # ── Schritt 1: pre_json bekannte Skills ──────────────────────────
        matched_known = 0
        for skill, count in list(remaining.items()):
            cat = known_skills.get(skill.lower())
            if cat:
                result[skill] = {'category': cat, 'count': count}
                del remaining[skill]
                matched_known += 1
        logger.info(f"  Schritt 1 (pre_json): {matched_known} bekannt → {len(remaining)} uebrig")

        # ── Schritt 2: TrainingTerm DB ────────────────────────────────────
        db_terms = {t.term.lower(): t.category for t in TrainingTerm.objects.all()}

        matched_db = 0
        for skill, count in list(remaining.items()):
            cat = db_terms.get(skill.lower())
            if cat:
                result[skill] = {'category': cat, 'count': count}
                del remaining[skill]
                matched_db += 1
        logger.info(f"  Schritt 2 (TrainingTerm): {matched_db} gefunden → {len(remaining)} uebrig")

        # ── Schritt 3: Unbekannt → Sonstige Skills + unknown_skills ──────
        # Self-Learning Pipeline lernt diese spaeter via LLM mit Projekt-Kontext
        if remaining:
            for skill, count in remaining.items():
                result[skill] = {'category': 'Sonstige Skills', 'count': count}

                # Projekt-Kontext aufbauen wenn experience_map vorhanden
                exp_list = []
                if experience_map and skill in experience_map:
                    exp_list = experience_map[skill]

                selected_exps, context_str = _select_projects_for_context(exp_list)

                # Strukturierten Key bauen
                key = _build_unknown_skill_key(skill, consultant, selected_exps)

                unknown_skills.append({
                    'key':     key,
                    'skill':   skill,
                    'context': context_str,
                    'exp_ids': [exp.id for exp in selected_exps],
                    'count':   count,
                })

            logger.info(f"  Schritt 3 (unbekannt): {len(remaining)} → 'Sonstige Skills'")
            logger.info(f"  unknown_skills fuer Self-Learning: "
                        f"{[u['key'] for u in unknown_skills[:5]]}")

        logger.info(f"  SkillNormalizer FERTIG: {len(result)} Skills kategorisiert, "
                    f"{len(unknown_skills)} unbekannt")
        return result, unknown_skills

    def save_to_db(self, consultant, normalized: Dict[str, Dict],
                   experience_map: Dict[str, List] = None) -> Dict[str, int]:
        """
        Schreibt normalisierte Skills in DB:
        - ConsultantSkill (Verknuepfung consultant → skill + weight)
        - ExperienceTechnology (Verknuepfung experience → skill)

        Darf NICHT schreiben:
        - TrainingTerm (nur Self-Learning)
        - Skill.category_name wenn bereits gesetzt (Stammdaten)
        """
        from ..models import Skill, ConsultantSkill, SkillCategory, ExperienceTechnology

        if not normalized:
            return {'added': 0, 'updated': 0}

        workers = _get_workers()
        added   = 0
        updated = 0

        for skill_name, info in normalized.items():
            cat_name = info['category']
            count    = info.get('count', 1)

            project_count = 0
            total_months  = 0

            if experience_map and skill_name in experience_map:
                exp_list      = experience_map[skill_name]
                project_count = len(exp_list)
                periods       = [getattr(exp, 'period', '') or '' for exp in exp_list]
                with ThreadPoolExecutor(max_workers=workers) as executor:
                    months_list = list(executor.map(_get_months, periods))
                total_months = sum(months_list)

            project_count = max(1, project_count)
            total_months  = max(6, total_months)
            weight        = _count_to_weight(count, project_count, total_months)

            cat = SkillCategory.objects.filter(name=cat_name).first()

            # Skill anlegen oder holen
            # category_name NUR beim Anlegen setzen — NIEMALS ueberschreiben
            skill, created = Skill.objects.get_or_create(
                name=skill_name[:200],
                defaults={'category': cat, 'category_name': cat_name}
            )

            # ConsultantSkill anlegen oder Gewicht aktualisieren
            cs, cs_created = ConsultantSkill.objects.get_or_create(
                consultant=consultant,
                skill=skill,
                defaults={'weight': weight, 'category_name': cat_name}
            )
            if cs_created:
                added += 1
            else:
                changed = False
                if weight > cs.weight:
                    cs.weight = weight
                    changed = True
                if cs.category_name != cat_name:
                    cs.category_name = cat_name
                    changed = True
                if changed:
                    cs.save(update_fields=['weight', 'category_name'])
                    updated += 1

            # ExperienceTechnology
            if experience_map and skill_name in experience_map:
                for exp in experience_map[skill_name]:
                    ExperienceTechnology.objects.get_or_create(
                        experience=exp, skill=skill
                    )

        logger.info(f"  save_to_db: +{added} neu, {updated} aktualisiert")
        return {'added': added, 'updated': updated}


main_skill_normalizer = SkillNormalizer()
