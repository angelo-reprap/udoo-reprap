"""
master_post_clean.py
====================
Post-Prozessor fuer den master_merger Output.
Laeuft NACH dem Merger, VOR der Uebersetzung.

Checks (regelbasiert, kein LLM ausser wo markiert):
  1. Duplikat-Raupe        — LLM, sequenziell
  2. Perioden-Plausibilitaet — regelbasiert
  3. Heute-Bereinigung     — regelbasiert
  4. Firmenname-Normalisierung — regelbasiert
  5. Rollen-Bereinigung    — regelbasiert
  6. Technologien-Bereinigung — regelbasiert
  7. Aktivitaeten-Bereinigung — regelbasiert
  8. Vollstaendigkeits-Check — 1x LLM
  9. Checksum/Statistik    — regelbasiert

Singleton: master_post_cleaner
"""

import copy
import json
import logging
import re
from datetime import datetime
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


def _month_minus_one(year: int, month: int) -> Tuple[int, int]:
    """Einen Monat zurueck, mit Jahreswechsel."""
    if month == 1:
        return year - 1, 12
    return year, month - 1


def _format_period(sy: int, sm: int, ey: int, em: int) -> str:
    """Tuple -> lesbarer Periodenstring."""
    start = f"{sm:02d}/{sy}" if sm else str(sy)
    if ey >= 9999:
        end = 'heute'
    else:
        end = f"{em:02d}/{ey}" if em else str(ey)
    return f"{start} – {end}"


class MasterPostCleaner:

    def clean(self, pre_json: dict) -> dict:
        result  = copy.deepcopy(pre_json)
        report  = {'merges': [], 'flags': [], 'fixes': [], 'stats': {}}

        ed = result.setdefault('extracted_data', {})
        exps = ed.get('experience', [])

        if not exps:
            result.setdefault('audit', {})['post_clean'] = report
            return result

        logger.info(f"[PostClean] START: {len(exps)} Projekte")

        exps = self._sort_chronological(exps)
        exps, r1 = self._dedup_raupe(exps)
        report['merges'].extend(r1)

        exps, r2 = self._fix_open_periods(exps)
        report['fixes'].extend(r2)

        exps, r3 = self._normalize_companies(exps)
        report['fixes'].extend(r3)

        exps, r4 = self._clean_roles(exps)
        report['fixes'].extend(r4)

        exps, r5 = self._clean_technologies(exps)
        report['fixes'].extend(r5)

        exps, r6 = self._clean_activities(exps)
        report['fixes'].extend(r6)

        flags = self._check_plausibility(exps, ed)
        report['flags'].extend(flags)

        completeness = self._check_completeness(ed, exps)
        report['flags'].extend(completeness)

        exps, r9 = self._clean_project_content(exps)

        # Punkt 10: EDV seit
        ed['experience'] = exps
        result = self._fix_edv_since(result)
        exps = result['extracted_data']['experience']
        ed = result['extracted_data']
        report['fixes'].extend(r9)

        # Punkt 11: Location aus profil.json (FL-Profil mit Radius)
        result = self._fix_location_from_profil(result)

        report['stats'] = {
            'projects_in':  len(ed.get('experience', [])),
            'projects_out': len(exps),
            'merges':       len(report['merges']),
            'fixes':        len(report['fixes']),
            'flags':        len(report['flags']),
        }

        ed['experience'] = exps
        result.setdefault('audit', {})['post_clean'] = report
        logger.info(
            f"[PostClean] FERTIG: {report['stats']['projects_in']} -> "
            f"{report['stats']['projects_out']} Projekte | "
            f"{report['stats']['merges']} Merges | "
            f"{report['stats']['flags']} Flags"
        )
        return result

    # ── 1. Sortierung ──────────────────────────────────────────────────────

    def _sort_chronological(self, exps: List[dict]) -> List[dict]:
        from apps.cv_extractor.services.master_merger import _normalize_period
        def _key(p):
            sy, sm, ey, em = _normalize_period(p.get('period', ''))
            return -(sy * 12 + (sm if sm else 6))
        return sorted(exps, key=_key)

    # ── 2. Duplikat-Raupe ──────────────────────────────────────────────────

    def _dedup_raupe(self, exps: List[dict]) -> Tuple[List[dict], List[str]]:
        from apps.cv_extractor.services.master_merger import (
            _periods_overlap, _get_prompt, _llm, _period_precision,
            _best_activities, _tech_union, _longer_str
        )
        merges = []
        if len(exps) <= 1:
            return exps, merges

        pt = _get_prompt('master_dedup_projects')
        result = [copy.deepcopy(exps[0])]

        for i in range(1, len(exps)):
            current = exps[i]
            last    = result[-1]

            if not _periods_overlap(
                    last.get('period', ''),
                    current.get('period', ''),
                    tolerance_months=0):
                result.append(copy.deepcopy(current))
                continue

            same = False
            if pt:
                try:
                    doc_a = json.dumps({
                        'period':      last.get('period', ''),
                        'company':     last.get('company', ''),
                        'role':        last.get('role', last.get('title', '')),
                        'technologies':last.get('technologies', []),
                        'activities':  last.get('activities', [])[:3],
                    }, ensure_ascii=False)
                    doc_b = json.dumps({
                        'period':      current.get('period', ''),
                        'company':     current.get('company', ''),
                        'role':        current.get('role', current.get('title', '')),
                        'technologies':current.get('technologies', []),
                        'activities':  current.get('activities', [])[:3],
                    }, ensure_ascii=False)
                    r = _llm(pt.format(proj_a=doc_a, proj_b=doc_b))
                    if r and r.success and isinstance(r.data, dict):
                        same = bool(r.data.get('same', False))
                    elif r and r.success and isinstance(r.data, str):
                        same = r.data.strip().strip('"').lower() in (
                            'true', 'same', 'gleich', 'ja')
                except Exception as e:
                    logger.warning(f"[PostClean] dedup LLM: {e}")

            if same:
                msg = (f"MERGE: '{last.get('period')}' "
                       f"+ '{current.get('period')}'")
                merges.append(msg)
                logger.debug(f"  {msg}")
                for f in ('company', 'role', 'title', 'industry', 'location'):
                    result[-1][f] = _longer_str(
                        result[-1].get(f, ''), current.get(f, ''))
                if (_period_precision(current.get('period', '')) >
                        _period_precision(result[-1].get('period', ''))):
                    result[-1]['period'] = current['period']
                result[-1]['activities']   = _best_activities([
                    result[-1].get('activities', []),
                    current.get('activities', [])])
                result[-1]['technologies'] = _tech_union([
                    result[-1].get('technologies', []),
                    current.get('technologies', [])])
            else:
                result.append(copy.deepcopy(current))

        return result, merges

    # ── 3. Heute-Bereinigung ───────────────────────────────────────────────

    def _fix_open_periods(self, exps: List[dict]) -> Tuple[List[dict], List[str]]:
        """
        Mehrere offene Projekte (Ende=heute):
        - Neuestes (hoechster Startmonat) behaelt 'heute'
        - Aeltere bekommen Startmonat_des_direkt_neueren_Projekts - 1 als Ende
        - Konflikt (gleicher Startmonat): LLM entscheidet parallel vs. duplicate
          - duplicate -> merge, eines behaelt heute
          - parallel  -> beide behalten heute, Flag im Report
        """
        from apps.cv_extractor.services.master_merger import (
            _normalize_period, _get_prompt, _llm,
            _best_activities, _tech_union, _longer_str
        )
        fixes = []

        # Offene Projekte sammeln mit ihrem Start in Monaten
        open_items = []  # (index, sy, sm, start_months)
        for i, exp in enumerate(exps):
            sy, sm, ey, em = _normalize_period(exp.get('period', ''))
            if ey >= 9999 and sy > 0:
                start_m = sy * 12 + (sm if sm else 6)
                open_items.append((i, sy, sm, start_m))

        if len(open_items) <= 1:
            return exps, fixes

        # Absteigend sortieren nach Startmonat (neuestes zuerst)
        open_items.sort(key=lambda x: -x[3])

        # Konflikt-Check: gleicher Startmonat → LLM
        pt = _get_prompt('master_check_parallel_projects')
        to_remove = set()  # Indices die als Duplikat entfernt werden

        i = 0
        while i < len(open_items) - 1:
            idx_a, sy_a, sm_a, start_a = open_items[i]
            idx_b, sy_b, sm_b, start_b = open_items[i + 1]

            if start_a == start_b:
                # Gleicher Startmonat → LLM entscheiden
                exp_a = exps[idx_a]
                exp_b = exps[idx_b]
                is_duplicate = False

                if pt:
                    try:
                        from apps.cv_extractor.services.deepseek_api_label import deepseek_label_api
                        doc_a = json.dumps({
                            'period':      exp_a.get('period', ''),
                            'company':     exp_a.get('company', ''),
                            'role':        exp_a.get('role', exp_a.get('title', '')),
                            'technologies':exp_a.get('technologies', [])[:8],
                            'activities':  exp_a.get('activities', [])[:4],
                        }, ensure_ascii=False)
                        doc_b = json.dumps({
                            'period':      exp_b.get('period', ''),
                            'company':     exp_b.get('company', ''),
                            'role':        exp_b.get('role', exp_b.get('title', '')),
                            'technologies':exp_b.get('technologies', [])[:8],
                            'activities':  exp_b.get('activities', [])[:4],
                        }, ensure_ascii=False)
                        r = deepseek_label_api.extract(pt.format(proj_a=doc_a, proj_b=doc_b))
                        if r and r.success and r.data:
                            data = r.data
                            if isinstance(data, str):
                                import json as _j
                                try: data = _j.loads(data)
                                except: data = {}
                            result_val   = data.get('result', 'parallel') if isinstance(data, dict) else 'parallel'
                            reason       = data.get('reason', '')         if isinstance(data, dict) else ''
                            is_duplicate = (result_val == 'duplicate')
                            logger.info(
                                f"  [PostClean] Parallel-Check: "
                                f"'{exp_a.get('period')}' vs "
                                f"'{exp_b.get('period')}' -> "
                                f"{result_val} ({reason})")
                        else:
                            logger.warning(f"[PostClean] parallel LLM leer: {getattr(r,'error','')}")
                    except Exception as e:
                        logger.warning(f"[PostClean] parallel LLM: {e}")

                if is_duplicate:
                    # Merge: besseres aus beiden nehmen, idx_b entfernen
                    for f in ('company', 'role', 'title', 'industry', 'location'):
                        exps[idx_a][f] = _longer_str(
                            exps[idx_a].get(f, ''), exp_b.get(f, ''))
                    exps[idx_a]['activities']   = _best_activities([
                        exps[idx_a].get('activities', []),
                        exp_b.get('activities', [])])
                    exps[idx_a]['technologies'] = _tech_union([
                        exps[idx_a].get('technologies', []),
                        exp_b.get('technologies', [])])
                    to_remove.add(idx_b)
                    fixes.append(
                        f"PARALLEL-MERGE: "
                        f"'{exp_a.get('period')}' + '{exp_b.get('period')}'")
                    open_items.pop(i + 1)
                    # i nicht erhoehen — naechstes Paar pruefen
                else:
                    # Echte Parallelprojekte — beide behalten heute
                    fixes.append(
                        f"PARALLEL-OK: "
                        f"'{exp_a.get('period')}' || '{exp_b.get('period')}'")
                    i += 1
            else:
                i += 1

        # Duplikate entfernen
        if to_remove:
            exps = [e for i, e in enumerate(exps) if i not in to_remove]
            # open_items Indices neu berechnen nach Entfernung
            removed_before = {}
            removed_count = 0
            new_open_items = []
            for orig_idx, sy, sm, start_m in open_items:
                adj_idx = orig_idx - sum(1 for r in to_remove if r < orig_idx)
                new_open_items.append((adj_idx, sy, sm, start_m))
            open_items = new_open_items

        # Jetzt offene Perioden schliessen (neuestes behaelt heute)
        # open_items ist absteigend nach Startmonat sortiert
        # open_items[0] = neuestes → behaelt heute
        for rank, (idx, sy, sm, start_m) in enumerate(open_items):
            if rank == 0:
                continue  # neuestes behaelt heute

            # Folgeprojekt = das naechst neuere in open_items
            next_idx, next_sy, next_sm, next_start_m = open_items[rank - 1]
            end_y, end_m = _month_minus_one(next_sy, next_sm if next_sm else 1)

            # Pruefen ob Ende vor Start liegt (Einmonats-Projekt)
            start_abs = sy * 12 + (sm if sm else 6)
            end_abs   = end_y * 12 + end_m
            if end_abs < start_abs:
                # Ende waere vor Start — Folgeprojekt startet im gleichen Monat
                # Dann Ende = Startmonat selbst (Einmonats-Projekt)
                end_y, end_m = sy, sm if sm else 1
                fixes.append(
                    f"HEUTE-FIX-EINMONAT: "
                    f"'{exps[idx].get('period')}' -> Ende={end_m:02d}/{end_y}")
            
            old_period = exps[idx].get('period', '')
            new_period = _format_period(sy, sm, end_y, end_m)
            exps[idx] = dict(exps[idx])
            exps[idx]['period'] = new_period

            msg = f"HEUTE-FIX: '{old_period}' -> '{new_period}'"
            fixes.append(msg)
            logger.info(f"  [PostClean] {msg}")

        return exps, fixes

    # ── 4. Firmenname-Normalisierung ───────────────────────────────────────

    def _normalize_companies(self, exps: List[dict]) -> Tuple[List[dict], List[str]]:
        """
        Gruppiert Projekte nach aehnlichem Firmennamen.
        Wenn alle kuerzeren Namen im laengsten enthalten sind
        -> laengsten als kanonischen Namen verwenden.
        Nur innerhalb von Projekten die zeitlich ueberlappen.
        """
        fixes = []

        # Alle Firmennamen sammeln
        companies = list({
            exp.get('company', '').strip()
            for exp in exps
            if exp.get('company', '').strip()
        })

        # Paare finden die aufeinander passen
        canonical = {}  # shorter -> longer
        for i, c1 in enumerate(companies):
            for c2 in companies[i+1:]:
                shorter, longer = (
                    (c1, c2) if len(c1) <= len(c2) else (c2, c1)
                )
                if (len(shorter) >= 4 and
                        shorter.lower() in longer.lower()):
                    canonical[shorter] = longer
                    logger.debug(
                        f"  [PostClean] Firma: '{shorter}' -> '{longer}'")

        if not canonical:
            return exps, fixes

        # Ersetzen
        for exp in exps:
            company = exp.get('company', '').strip()
            if company in canonical:
                old = company
                exp['company'] = canonical[company]
                fixes.append(f"FIRMA: '{old}' -> '{exp['company']}'")

        return exps, fixes

    # ── 5. Rollen-Bereinigung ──────────────────────────────────────────────

    def _clean_roles(self, exps: List[dict]) -> Tuple[List[dict], List[str]]:
        fixes = []
        for exp in exps:
            role  = (exp.get('role',  '') or '').strip()
            title = (exp.get('title', '') or '').strip()

            # Leere Rolle aber Titel vorhanden
            if not role and title:
                exp['role'] = title
                fixes.append(f"ROLLE aus TITLE: '{title}'")

            # Rolle zu lang
            role = exp.get('role', '') or ''
            if len(role) > 80:
                exp['role'] = role[:80].rsplit(' ', 1)[0]
                fixes.append(f"ROLLE gekuerzt: '{exp['role']}'")

        return exps, fixes

    # ── 6. Technologien-Bereinigung ────────────────────────────────────────

    def _clean_technologies(self, exps: List[dict]) -> Tuple[List[dict], List[str]]:
        fixes = []
        STOPWORDS = {
            'und', 'and', 'mit', 'with', 'the', 'or', 'oder',
            'etc', 'u.a.', 'z.b.', 'e.g.', 'various', 'verschiedene',
        }
        for exp in exps:
            techs = exp.get('technologies', [])
            if not techs:
                continue

            seen   = set()
            clean  = []
            for t in techs:
                if not isinstance(t, str):
                    continue
                t = t.strip().rstrip('.,;')
                tl = t.lower()
                if (len(t) < 2 or
                        tl in STOPWORDS or
                        tl in seen):
                    continue
                seen.add(tl)
                clean.append(t)

            if len(clean) != len(techs):
                fixes.append(
                    f"TECH bereinigt: {len(techs)} -> {len(clean)}"
                    f" bei '{exp.get('period', '')}'")
                exp['technologies'] = clean

        return exps, fixes

    # ── 7. Aktivitaeten-Bereinigung ────────────────────────────────────────

    def _clean_activities(self, exps: List[dict]) -> Tuple[List[dict], List[str]]:
        fixes = []
        for exp in exps:
            acts = exp.get('activities', [])
            if not acts:
                continue

            seen  = set()
            clean = []
            for a in acts:
                if not isinstance(a, str):
                    continue
                a = a.strip()
                if len(a) < 10:
                    continue
                key = a.lower()[:60]
                if key in seen:
                    continue
                seen.add(key)
                clean.append(a)

            if len(clean) != len(acts):
                fixes.append(
                    f"ACT bereinigt: {len(acts)} -> {len(clean)}"
                    f" bei '{exp.get('period', '')}'")
                exp['activities'] = clean

        return exps, fixes

    # ── 8. Plausibilitaets-Check ───────────────────────────────────────────

    def _check_plausibility(self, exps: List[dict],
                            ed: dict) -> List[str]:
        from apps.cv_extractor.services.master_merger import _normalize_period
        flags = []

        for exp in exps:
            sy, sm, ey, em = _normalize_period(exp.get('period', ''))
            period = exp.get('period', '')

            # Enddatum vor Startdatum
            if sy > 0 and ey < 9999 and ey > 0:
                start_m = sy * 12 + (sm if sm else 6)
                end_m   = ey * 12 + (em if em else 6)
                if end_m < start_m:
                    flags.append(
                        f"PERIODE_FEHLER: Ende vor Start bei '{period}'")

            # Projekt laenger als 10 Jahre
            if sy > 0 and ey < 9999 and ey > 0:
                duration = (ey - sy) * 12 + (em or 6) - (sm or 6)
                if duration > 120:
                    flags.append(
                        f"PERIODE_LANG: >10 Jahre bei '{period}'")

            # Anonyme Firma
            company = exp.get('company', '')
            anon_patterns = [
                r'konzern', r'unternehmen', r'gruppe', r'group',
                r'corporation', r'automotive', r'telekommunikation',
                r'bank', r'versicherung', r'handel',
            ]
            if company and not any(
                    c.isupper() or c.isnumeric()
                    for c in company[:3]) and any(
                    re.search(p, company.lower())
                    for p in anon_patterns):
                flags.append(
                    f"FIRMA_ANONYM: '{company}' bei '{period}'")

        # Luecken > 2 Jahre
        sorted_exps = sorted(exps, key=lambda p: (
            lambda sy, sm, ey, em: sy * 12 + (sm or 6)
        )(*_normalize_period(p.get('period', ''))))

        for i in range(len(sorted_exps) - 1):
            _, _, ey1, em1 = _normalize_period(
                sorted_exps[i].get('period', ''))
            sy2, sm2, _, _ = _normalize_period(
                sorted_exps[i+1].get('period', ''))
            if ey1 >= 9999 or ey1 == 0 or sy2 == 0:
                continue
            gap = sy2 * 12 + (sm2 or 6) - ey1 * 12 - (em1 or 6)
            if gap > 24:
                flags.append(
                    f"LUECKE: {gap} Monate zwischen "
                    f"'{sorted_exps[i].get('period', '')}' "
                    f"und '{sorted_exps[i+1].get('period', '')}'")

        return flags

    # ── 9. Vollstaendigkeits-Check ─────────────────────────────────────────

    def _check_completeness(self, ed: dict,
                            exps: List[dict]) -> List[str]:
        flags = []

        if not ed.get('personal', {}).get('languages'):
            flags.append("FEHLT: Sprachen")

        if not any(ed.get('skills', {}).values()):
            has_techs = any(e.get('technologies') for e in exps)
            if has_techs:
                flags.append(
                    "FEHLT: Skills leer obwohl Technologien in Projekten")

        if not ed.get('education'):
            flags.append("FEHLT: Bildung")

        if not ed.get('focus_areas'):
            flags.append("FEHLT: Fachbereiche")

        personal = ed.get('personal', {})
        for field in ('location', 'availability', 'summary'):
            if not personal.get(field):
                flags.append(f"FEHLT: personal.{field}")

        projects_without_role = [
            e.get('period', '') for e in exps
            if not e.get('role') and not e.get('title')
        ]
        if projects_without_role:
            flags.append(
                f"KEINE_ROLLE: {len(projects_without_role)} Projekte "
                f"ohne Rolle: {projects_without_role[:3]}")

        projects_without_activities = [
            e.get('period', '') for e in exps
            if not e.get('activities')
        ]
        if projects_without_activities:
            flags.append(
                f"KEINE_ACTIVITIES: "
                f"{len(projects_without_activities)} Projekte "
                f"ohne Tätigkeiten")

        return flags


    # ── 9. Content-Dedup + Deutsch ────────────────────────────────────────

    def _clean_project_content(self, exps: List[dict]) -> Tuple[List[dict], List[str]]:
        """
        Pro Projekt: Activities per LLM bereinigen.
        - Inhaltliche Duplikate (DE/EN) entfernen
        - Beste Version behalten
        - Auf Deutsch ausgeben
        Nur Projekte mit 5+ Activities werden bereinigt (weniger lohnt nicht).
        """
        from apps.cv_extractor.services.master_merger import _get_prompt
        from apps.cv_extractor.services.deepseek_api_label import deepseek_label_api
        from concurrent.futures import ThreadPoolExecutor, as_completed as _as_completed

        fixes = []
        pt = _get_prompt('master_clean_project_content')
        if not pt:
            logger.warning("[PostClean] Prompt master_clean_project_content nicht gefunden")
            return exps, fixes

        def _clean_one(idx_exp):
            idx, exp = idx_exp
            acts = exp.get('activities', [])
            if len(acts) < 5:
                return idx, exp, False
            company = exp.get('company', '') or exp.get('role', '') or ''
            try:
                prompt = pt.format(
                    company=company,
                    activities=json.dumps(acts, ensure_ascii=False)
                )
                r = deepseek_label_api.extract(prompt)
                if r and r.success and isinstance(r.data, dict):
                    cleaned = r.data.get('activities', [])
                    if isinstance(cleaned, list) and len(cleaned) >= 1:
                        return idx, {**exp, 'activities': cleaned}, True
            except Exception as e:
                logger.warning(f"[PostClean] content_clean Fehler: {e}")
            return idx, exp, False

        results = {}
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {
                executor.submit(_clean_one, (i, exp)): i
                for i, exp in enumerate(exps)
            }
            for future in _as_completed(futures):
                idx, exp, changed = future.result()
                results[idx] = (exp, changed)

        cleaned_exps = []
        for i in sorted(results.keys()):
            exp, changed = results[i]
            cleaned_exps.append(exp)
            if changed:
                orig_count = len(exps[i].get('activities', []))
                new_count  = len(exp.get('activities', []))
                fixes.append(
                    f"CONTENT: '{exp.get('period','')}' "
                    f"{orig_count} -> {new_count} Activities")
                logger.info(
                    f"  [PostClean] Content bereinigt: "
                    f"'{exp.get('period','')}' "
                    f"{orig_count} -> {new_count} Activities")

        return cleaned_exps, fixes


    # ── 10. EDV-Erfahrung seit ────────────────────────────────────────────

    def _fix_location(self, pre_json: dict, base_path) -> dict:
        """Location aus profil.json mit Radius korrekt setzen."""
        import json
        from pathlib import Path
        try:
            profil = json.loads(Path(base_path / 'profil.json').read_text(encoding='utf-8'))
            addr   = profil.get('address', {}) or {}
            city   = addr.get('addressLocality', '').strip()
            tc     = profil.get('travelConfiguration') or profil.get('profile', {}).get('travelConfiguration') or {}
            rad    = tc.get('radius')
            noRes  = tc.get('noRestrictions', False)
            remOt  = tc.get('remoteOnly', False)
            isRes  = tc.get('isResidence', False)
            if noRes:
                loc = 'Weltweit'
            elif remOt and isRes and city and rad:
                loc = f'Remote, {city} +{rad} km'
            elif remOt:
                loc = 'Remote'
            elif isRes and city and rad:
                loc = f'{city} +{rad} km'
            elif city:
                loc = city
            else:
                loc = 'nach Absprache'
            pre_json['extracted_data']['personal']['location'] = loc
            logger.info(f"  [PostClean] Location: {loc}")
        except Exception as e:
            logger.warning(f"  [PostClean] Location fix Fehler: {e}")
        return pre_json

    def _fix_location_from_profil(self, result: dict) -> dict:
        """
        Punkt 11: Location aus profil.json lesen und mit Radius setzen.
        Sucht profil.json anhand consultant_dir oder import_id in data/url/fl/.
        """
        import json as _json
        from pathlib import Path
        try:
            # Pfad zur profil.json ermitteln
            meta       = result.get('metadata', {})
            source     = meta.get('source', {}) or {}
            import_id  = str(source.get('import_id', ''))
            cdir       = meta.get('consultant_dir', '')
            base_dir   = Path('data/url/fl')
            profil_path = None

            # 1. via consultant_dir
            if cdir and (base_dir / cdir / 'profil.json').exists():
                profil_path = base_dir / cdir / 'profil.json'
            # 2. via import_id — alle dirs durchsuchen
            if not profil_path and import_id:
                for d in base_dir.iterdir():
                    p = d / 'profil.json'
                    if p.exists():
                        try:
                            raw = _json.loads(p.read_text(encoding='utf-8'))
                            pid = str(raw.get('profile', {}).get('id', ''))
                            if pid == import_id:
                                profil_path = p
                                break
                        except Exception:
                            continue

            if not profil_path:
                return result

            profil = _json.loads(profil_path.read_text(encoding='utf-8'))
            addr   = profil.get('address', {}) or {}
            city   = addr.get('addressLocality', '').strip()
            tc     = profil.get('travelConfiguration') or profil.get('profile', {}).get('travelConfiguration') or {}
            rad    = tc.get('radius')
            noRes  = tc.get('noRestrictions', False)
            remOt  = tc.get('remoteOnly', False)
            isRes  = tc.get('isResidence', False)

            if noRes:
                loc = 'Weltweit'
            elif remOt and isRes and city and rad:
                loc = f'Remote, {city} +{rad} km'
            elif remOt:
                loc = 'Remote'
            elif isRes and city and rad:
                loc = f'{city} +{rad} km'
            elif city:
                loc = city
            else:
                loc = 'nach Absprache'

            result['extracted_data']['personal']['location'] = loc
            logger.info(f"  [PostClean] Location: {loc}")
        except Exception as e:
            logger.warning(f"  [PostClean] Location fix Fehler: {e}")
        return result

    def _fix_edv_since(self, pre_json: dict) -> dict:
        """
        EDV-Erfahrung seit = Jahr des ältesten Projekts.
        Überschreibt den Wert aus der FL-API.
        """
        from apps.cv_extractor.services.master_merger import _normalize_period
        exps = pre_json.get('extracted_data', {}).get('experience', [])
        years = []
        for e in exps:
            sy, sm, ey, em = _normalize_period(e.get('period', ''))
            if sy and sy > 1900:
                years.append(sy)
        if years:
            edv_since = min(years)
            pre_json['extracted_data']['personal']['edv_experience_since'] = edv_since
            logger.info(f"  [PostClean] EDV seit: {edv_since}")
        return pre_json


master_post_cleaner = MasterPostCleaner()
