"""
build_namazu_training_terms.py

Liest Namazu HTMLs, extrahiert Skills und kategorisiert sie
in die 28 cv_extractor.SkillCategory Kategorien.

Ablauf:
  1. HTML parsen → Profiltexte (gulp, ogo, freelancermap)
  2. Tokens extrahieren (Regex, min 3 Zeichen)
  3. Gegen cv_extractor.TrainingTerm prüfen → bekannte Skills direkt (method='regex')
  4. Unbekannte → Deepseek API → Kategorie (method='llm')
  5. Ergebnis in NamazuTrainingTerm speichern

Nutzung:
  python manage.py build_namazu_training_terms
  python manage.py build_namazu_training_terms --limit 100 --dry-run
  python manage.py build_namazu_training_terms --workers 5 --llm-batch 20
  python manage.py build_namazu_training_terms --no-llm
"""

import re
import time
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.conf import settings as django_settings

logger = logging.getLogger(__name__)

# ── Stoppwörter ───────────────────────────────────────────────────────────────
STOPWORDS = {
    # Deutsch
    'der', 'die', 'das', 'und', 'oder', 'mit', 'von', 'für', 'auf', 'bei',
    'aus', 'als', 'zur', 'zum', 'des', 'dem', 'den', 'ein', 'eine', 'einen',
    'einer', 'einem', 'auch', 'sich', 'ist', 'sind', 'war', 'wird', 'hat',
    'haben', 'hatte', 'nach', 'über', 'unter', 'vor', 'seit', 'durch',
    'nicht', 'sehr', 'aber', 'noch', 'mehr', 'alle', 'beim', 'kann',
    'wurde', 'wurden', 'sowie', 'bis', 'wie', 'bzw', 'etc', 'ggf', 'inkl',
    'neu', 'alt', 'gut', 'neu', 'kein', 'keine', 'keinen', 'verschiedene',
    'verschiedenen', 'weitere', 'weiteren', 'anderen', 'andere', 'anderen',
    'erste', 'ersten', 'zweite', 'zweiten', 'dabei', 'dadurch', 'davon',
    'dazu', 'dabei', 'hierfür', 'hierbei', 'hiermit', 'wobei', 'worüber',
    'wenn', 'dann', 'dass', 'weil', 'damit', 'sodass', 'obwohl', 'falls',
    'zwar', 'jedoch', 'allerdings', 'insbesondere', 'beispielsweise',
    'entsprechend', 'bereich', 'bereichen', 'system', 'systeme', 'systemen',
    'lösung', 'lösungen', 'konzept', 'konzepte', 'konzepten', 'prozess',
    'prozesse', 'prozessen', 'projekt', 'projekte', 'projekten',
    'aufgabe', 'aufgaben', 'benutzer', 'nutzer', 'kunde', 'kunden',
    'stand', 'datum', 'profil', 'erstellt', 'geändert', 'lesen',
    'direktkontakt', 'projektanfragen', 'verfügbar', 'einsatz',
    # Englisch
    'the', 'and', 'for', 'with', 'this', 'that', 'from', 'are', 'was',
    'were', 'has', 'have', 'had', 'not', 'but', 'they', 'their', 'will',
    'been', 'being', 'more', 'also', 'can', 'all', 'one', 'out', 'its',
    'any', 'our', 'you', 'his', 'her', 'its', 'who', 'what', 'how',
    'when', 'where', 'which', 'into', 'than', 'then', 'them', 'these',
    'those', 'some', 'such', 'each', 'both', 'few', 'new', 'old', 'own',
    'same', 'other', 'used', 'using', 'based', 'well', 'may', 'use',
    # Zu kurz / Zahlen-ähnlich
    'der', 'die', 'das',
}

# ── Mindest-Token-Länge ───────────────────────────────────────────────────────
MIN_TOKEN_LEN = 3

# ── Deepseek Batch-Größe (wie viele unbekannte Skills pro LLM-Call) ───────────
DEFAULT_LLM_BATCH = 30

# ── Max parallele LLM-Calls ───────────────────────────────────────────────────
DEFAULT_WORKERS = 10


def _load_settings() -> dict:
    """Liest settings.json"""
    try:
        cfg_path = Path(django_settings.BASE_DIR) / 'settings.json'
        with open(cfg_path) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"settings.json nicht lesbar: {e}")
        return {}


def _parse_html(html_path: Path) -> Dict[str, str]:
    """
    Parst eine Namazu HTML-Datei.
    Gibt dict mit: gulp, ogo, freelancermap, full_name
    """
    result = {'gulp': '', 'ogo': '', 'freelancermap': '', 'full_name': ''}
    try:
        with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        soup = BeautifulSoup(content, 'html.parser')

        # Name aus h1
        h1 = soup.find('h1')
        if h1:
            result['full_name'] = h1.get_text().strip()

        # Profile aus profile-section
        for section in soup.find_all('div', class_='profile-section'):
            header = section.find('div', class_='profile-header')
            if not header:
                continue
            title_div = header.find('div', class_='profile-title')
            if not title_div:
                continue
            title = ''
            for child in reversed(title_div.contents):
                if isinstance(child, str) and child.strip():
                    title = child.strip()
                    break
            pre = section.find('pre')
            text = pre.get_text().strip() if pre else ''
            if not text or len(text) < 20:
                continue
            if 'Gulp' in title:
                result['gulp'] = text
            elif 'Ogo' in title:
                result['ogo'] = text
            elif 'Freelancermap' in title:
                result['freelancermap'] = text

    except Exception as e:
        logger.warning(f"HTML Parse Fehler {html_path.name}: {e}")

    return result


def _extract_tokens(text: str) -> List[str]:
    """
    Extrahiert Token aus Profil-Text.
    Nur alphanumerisch + Sonderzeichen die in IT-Skills vorkommen: . # + /
    Mindestlänge MIN_TOKEN_LEN.
    """
    if not text:
        return []

    # Token-Pattern: Wörter mit optionalen . # + / (für C#, C++, .NET, etc.)
    tokens = re.findall(r'\b[A-Za-z][A-Za-z0-9#\+\./\-]{2,}\b', text)

    result = []
    seen = set()
    for t in tokens:
        t_clean = t.strip('.-/')
        if len(t_clean) < MIN_TOKEN_LEN:
            continue
        if t_clean.lower() in STOPWORDS:
            continue
        if t_clean.lower() in seen:
            continue
        # Keine reinen Zahlen
        if re.match(r'^\d+$', t_clean):
            continue
        seen.add(t_clean.lower())
        result.append(t_clean)

    return result


def _call_deepseek_batch(terms: List[str], categories: List[str],
                          api_key: str) -> Dict[str, str]:
    """
    Sendet einen Batch von unbekannten Skills an Deepseek.
    Gibt dict {term: category} zurück.
    Verwendet deepseek_api_label Logik (bracket-matching, retry).
    """
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    cat_list = '\n'.join(f'- {c}' for c in categories)
    terms_list = '\n'.join(f'{i+1}. {t}' for i, t in enumerate(terms))

    prompt = (
        f"Du bist ein IT-Skill-Kategorisierungs-Experte für Lebensläufe.\n\n"
        f"Ordne jeden der folgenden Begriffe GENAU EINER Kategorie zu.\n"
        f"Wenn ein Begriff kein IT-Skill ist → Kategorie: 'Sonstige Skills'\n\n"
        f"KATEGORIEN:\n{cat_list}\n\n"
        f"BEGRIFFE:\n{terms_list}\n\n"
        f"Antworte NUR mit JSON-Array:\n"
        f'[{{"term": "Begriff1", "category": "Kategoriename"}}, ...]\n\n'
        f"REGELN:\n"
        f"- Exakt {len(terms)} Einträge zurückgeben\n"
        f"- Nur Kategorienamen aus der Liste verwenden\n"
        f"- Kein Markdown, keine Erklärungen"
    )

    for attempt in range(3):
        try:
            r = requests.post(
                'https://api.deepseek.com/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'deepseek-chat',
                    'messages': [
                        {'role': 'system', 'content': 'Antworte NUR mit JSON-Array. Kein Markdown.'},
                        {'role': 'user',   'content': prompt}
                    ],
                    'temperature': 0,
                    'max_tokens': 2000
                },
                timeout=60,
                verify=False
            )

            if r.status_code == 429:
                wait = 2 ** (attempt + 1)
                logger.warning(f"Deepseek 429 — warte {wait}s")
                time.sleep(wait)
                continue

            content = r.json()['choices'][0]['message']['content']

            # JSON extrahieren (bracket-matching)
            stripped = content.strip()
            if stripped.startswith('```'):
                stripped = re.sub(r'^```(?:json)?\s*', '', stripped)
                stripped = re.sub(r'\s*```$', '', stripped).strip()

            # Array suchen
            start = stripped.find('[')
            if start == -1:
                logger.warning(f"Kein JSON-Array in Antwort (Versuch {attempt+1})")
                continue

            depth = 0
            end = -1
            in_str = False
            esc = False
            for i, ch in enumerate(stripped[start:], start):
                if esc:
                    esc = False
                    continue
                if ch == '\\' and in_str:
                    esc = True
                    continue
                if ch == '"':
                    in_str = not in_str
                    continue
                if in_str:
                    continue
                if ch == '[':
                    depth += 1
                elif ch == ']':
                    depth -= 1
                    if depth == 0:
                        end = i
                        break

            if end == -1:
                continue

            data = json.loads(stripped[start:end+1])
            result = {}
            for item in data:
                if isinstance(item, dict):
                    term = item.get('term', '').strip()
                    cat  = item.get('category', '').strip()
                    if term and cat:
                        result[term] = cat
            return result

        except Exception as e:
            logger.warning(f"Deepseek Fehler (Versuch {attempt+1}): {e}")
            time.sleep(2)

    return {}


class Command(BaseCommand):
    help = 'Baut NamazuTrainingTerm DB aus Namazu HTML-Dateien'

    def add_arguments(self, parser):
        parser.add_argument('--limit',     type=int,   default=None,
                            help='Max Anzahl HTML-Dateien (Test)')
        parser.add_argument('--dry-run',   action='store_true',
                            help='Nur analysieren, nichts speichern')
        parser.add_argument('--no-llm',    action='store_true',
                            help='Kein Deepseek — nur bekannte Skills per Regex')
        parser.add_argument('--workers',   type=int,   default=None,
                            help='Parallele LLM-Calls (default: aus settings.json)')
        parser.add_argument('--llm-batch', type=int,   default=None,
                            help='Skills pro LLM-Call (default: 30)')
        parser.add_argument('--html-path', type=str,   default=None,
                            help='HTML-Verzeichnis (default: aus settings.json)')

    def handle(self, *args, **options):
        start_time = time.time()
        cfg = _load_settings()

        # ── Parameter ────────────────────────────────────────────────────
        html_path  = Path(options['html_path'] or
                          cfg.get('namazu', {}).get('html_source', '/var/www/namazu/index/'))
        limit      = options['limit']
        dry_run    = options['dry_run']
        no_llm     = options['no_llm']
        workers    = options['workers'] or min(
                        cfg.get('pipeline', {}).get('parallel_workers_projects', 10),
                        DEFAULT_WORKERS)
        llm_batch  = options['llm_batch'] or DEFAULT_LLM_BATCH
        api_key    = cfg.get('ai_models', {}).get('deepseek', {}).get('api_key', '')

        self.stdout.write(f"📂 HTML-Pfad:    {html_path}")
        self.stdout.write(f"🔄 Dry-Run:      {dry_run}")
        self.stdout.write(f"🤖 LLM aktiv:    {not no_llm}")
        self.stdout.write(f"👷 Workers:      {workers}")
        self.stdout.write(f"📦 LLM-Batch:    {llm_batch}")

        if not html_path.exists():
            self.stderr.write(f"❌ Pfad nicht gefunden: {html_path}")
            return

        # ── Bekannte Terms aus cv_extractor laden ─────────────────────────
        from apps.cv_extractor.models import TrainingTerm as CvTrainingTerm, SkillCategory
        from apps.ai_cv_training.models import NamazuTrainingTerm

        known_terms = {
            t.term.lower(): t.category
            for t in CvTrainingTerm.objects.all()
        }
        categories = list(SkillCategory.objects.filter(
            is_active=True).order_by('sort_order', 'name').values_list('name', flat=True))

        self.stdout.write(f"📚 Bekannte Terms: {len(known_terms)}")
        self.stdout.write(f"🏷️  Kategorien:    {len(categories)}")

        # ── HTML-Dateien einlesen ─────────────────────────────────────────
        html_files = sorted(html_path.glob('*.html'))
        if limit:
            html_files = html_files[:limit]
        total = len(html_files)
        self.stdout.write(f"📄 HTML-Dateien:  {total}")

        # ── Schritt 1+2: HTML parsen + Tokens sammeln ─────────────────────
        self.stdout.write("\n⏳ Schritt 1/3 — HTML parsen + Tokens sammeln...")
        global_counter: Counter = Counter()
        parsed = 0
        errors = 0

        for i, f in enumerate(html_files):
            try:
                data = _parse_html(f)
                text = ' '.join([data['gulp'], data['ogo'], data['freelancermap']])
                tokens = _extract_tokens(text)
                for t in tokens:
                    global_counter[t.lower()] += 1
                parsed += 1
            except Exception as e:
                errors += 1
                if errors < 5:
                    self.stderr.write(f"  ⚠️ {f.name}: {e}")
            if (i + 1) % 1000 == 0:
                self.stdout.write(f"  {i+1}/{total} geparst — {len(global_counter)} unique Tokens")

        self.stdout.write(f"✅ Geparst: {parsed} Dateien, {len(global_counter)} unique Tokens, {errors} Fehler")

        # ── Schritt 3: Bekannte vs. Unbekannte trennen ─────────────────────
        self.stdout.write("\n⏳ Schritt 2/3 — Bekannte Skills kategorisieren...")
        known_results:   Dict[str, Tuple[str, int]] = {}  # term → (category, freq)
        unknown_terms:   List[Tuple[str, int]] = []

        for term, freq in global_counter.items():
            cat = known_terms.get(term.lower())
            if cat:
                known_results[term] = (cat, freq)
            else:
                unknown_terms.append((term, freq))

        self.stdout.write(f"  ✅ Bekannt (regex):   {len(known_results)}")
        self.stdout.write(f"  ❓ Unbekannt (→ LLM): {len(unknown_terms)}")

        # ── Schritt 4: LLM für unbekannte Skills ──────────────────────────
        llm_results: Dict[str, Tuple[str, int]] = {}

        if not no_llm and unknown_terms and api_key:
            self.stdout.write(f"\n⏳ Schritt 3/3 — Deepseek kategorisiert {len(unknown_terms)} unbekannte Skills...")
            self.stdout.write(f"   Batches à {llm_batch} Skills, {workers} parallel")

            # Nur Terms mit Frequenz >= 2 per LLM — Einzel-Treffer sind meist Rauschen
            llm_candidates = [(t, f) for t, f in unknown_terms if f >= 2]
            skipped_singles = len(unknown_terms) - len(llm_candidates)
            self.stdout.write(f"   LLM-Kandidaten (freq>=2): {len(llm_candidates)} ({skipped_singles} Einzel-Treffer übersprungen)")

            # Batches aufteilen
            batches = []
            for i in range(0, len(llm_candidates), llm_batch):
                batch_terms = [t for t, _ in llm_candidates[i:i+llm_batch]]
                batch_freqs = {t: f for t, f in llm_candidates[i:i+llm_batch]}
                batches.append((batch_terms, batch_freqs))

            processed_batches = 0
            categorized = 0

            def _process_batch(batch_data):
                terms_list, freqs = batch_data
                result = _call_deepseek_batch(terms_list, categories, api_key)
                return result, freqs

            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {executor.submit(_process_batch, b): b for b in batches}
                for future in as_completed(futures):
                    try:
                        result, freqs = future.result()
                        for term, cat in result.items():
                            if cat in categories:
                                llm_results[term] = (cat, freqs.get(term, 1))
                                categorized += 1
                        processed_batches += 1
                        if processed_batches % 5 == 0:
                            self.stdout.write(f"   Batch {processed_batches}/{len(batches)} — {categorized} kategorisiert")
                        time.sleep(1)  # Rate-Limit-Pause
                    except Exception as e:
                        self.stderr.write(f"  ❌ Batch Fehler: {e}")

            self.stdout.write(f"  ✅ LLM kategorisiert: {categorized}")

        elif no_llm:
            self.stdout.write("\n⏭️  LLM übersprungen (--no-llm)")
        elif not api_key:
            self.stdout.write("\n⚠️  Kein Deepseek API-Key — LLM übersprungen")

        # ── Schritt 5: In DB speichern ─────────────────────────────────────
        all_results = {**known_results, **llm_results}
        self.stdout.write(f"\n📊 Gesamt zu speichern: {len(all_results)} Terms")

        if dry_run:
            self.stdout.write("\n🔍 DRY-RUN — Vorschau (Top 30):")
            for term, (cat, freq) in sorted(all_results.items(),
                                            key=lambda x: x[1][1], reverse=True)[:30]:
                method = 'regex' if term in known_results else 'llm'
                self.stdout.write(f"  {freq:>5}x  [{method:5}]  {cat:<35}  {term}")
            self.stdout.write(f"\n✅ DRY-RUN abgeschlossen — nichts gespeichert")
            return

        # Speichern
        saved = 0
        updated = 0
        for term, (cat, freq) in all_results.items():
            method = 'regex' if term in known_results else 'llm'
            obj, created = NamazuTrainingTerm.objects.get_or_create(
                term=term[:200],
                defaults={
                    'category':   cat,
                    'confidence': 0.90 if method == 'regex' else 0.80,
                    'frequency':  freq,
                    'method':     method,
                }
            )
            if created:
                saved += 1
            else:
                # Frequenz aktualisieren
                if freq > obj.frequency:
                    obj.frequency = freq
                    obj.save(update_fields=['frequency', 'updated_at'])
                updated += 1

        duration = time.time() - start_time
        self.stdout.write(self.style.SUCCESS(
            f"\n✅ FERTIG:\n"
            f"   📄 HTML-Dateien:    {parsed}\n"
            f"   🔤 Unique Tokens:   {len(global_counter)}\n"
            f"   ✅ Bekannt (regex): {len(known_results)}\n"
            f"   🤖 LLM kategoris.: {len(llm_results)}\n"
            f"   💾 Neu gespeichert: {saved}\n"
            f"   🔄 Aktualisiert:    {updated}\n"
            f"   ⏱️  Dauer:           {duration:.1f}s"
        ))
