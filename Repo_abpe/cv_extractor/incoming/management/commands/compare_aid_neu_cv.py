"""
Vergleicht Original-AID-PDF mit neu/cv Ausgabe (Text-Extrakt).

  cd /opt/abpe/backend
  python3 manage.py compare_aid_neu_cv --letter aaa
  python3 manage.py compare_aid_neu_cv --letter aaa --dir aalderen_martin
  python3 manage.py compare_aid_neu_cv --letter aaa --out /mnt/public/udoo-reprap/artifacts/aaa-repro

Schreibt:
  OUT/summary.md          — Übersicht Score + Flags
  OUT/index.json          — maschinenlesbar
  OUT/by_dir/<dir>.md     — Detail Original vs neu/cv
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand


def _pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        return '\n'.join((p.extract_text() or '') for p in reader.pages)
    except Exception as e:
        return f'[PDF_READ_ERROR: {e}]'


def _norm(s: str) -> str:
    s = s or ''
    s = s.replace('\u00a0', ' ')
    s = re.sub(r'[ \t]+', ' ', s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s.strip()


def _periods(text: str) -> list:
    """Roh-Treffer (Ranges + Einzelmonate + Jahreszahlen)."""
    return re.findall(
        r'(?:\d{1,2}/\d{4}\s*[–\-]\s*(?:\d{1,2}/\d{4}|heute|dato)|'
        r'\d{1,2}/\d{4}|\d{4}\s*[–\-]\s*\d{4}|\b\d{4}\b)',
        text or '',
        flags=re.I,
    )


def _period_anchors(text: str) -> set:
    """
    Kanonische Perioden-Anker für fairen Compare.

    Original-PDFs zerlegen Ranges oft per Soft-Wrap in Einzelmonate
    (`01/2015` + `06/2018`), neu/cv schreibt denselben Einsatz als
    `01/2015 - 06/2018`. Roh-Set-Diff würde dann fälschlich „fehlen“ melden.

    Deshalb: Ranges → Start/Ende-Anker; Einzelmonate bleiben Anker;
    nackte Jahreszahlen nur behalten wenn nicht schon als MM/YYYY-Jahr
    abgedeckt (Geburtsjahr/Produktversionen bleiben Rauschen, aber
    Range-vs-Split False-Positives verschwinden).
    """
    raw = _periods(text)
    months: set[str] = set()
    years: set[str] = set()
    for p in raw:
        p = re.sub(r'\s+', ' ', (p or '').strip())
        m = re.match(
            r'^(\d{1,2}/\d{4})\s*[–\-]\s*(\d{1,2}/\d{4}|heute|dato)$',
            p,
            flags=re.I,
        )
        if m:
            months.add(m.group(1))
            end = m.group(2)
            if re.match(r'^\d{1,2}/\d{4}$', end):
                months.add(end)
            else:
                months.add(end.lower())
            continue
        m = re.match(r'^(\d{4})\s*[–\-]\s*(\d{4})$', p)
        if m:
            years.add(m.group(1))
            years.add(m.group(2))
            continue
        if re.match(r'^\d{1,2}/\d{4}$', p):
            mm, yy = p.split('/')
            months.add(f'{int(mm):02d}/{yy}')
            continue
        if re.match(r'^\d{4}$', p):
            years.add(p)
    # Jahreszahl nur zählen, wenn kein MM/YYYY desselben Jahres existiert
    month_years = {m.split('/')[-1] for m in months if '/' in m}
    years -= month_years
    return months | years


def _has_weiterbildung(text: str) -> bool:
    return bool(re.search(r'(?i)weiterbildung', text or ''))


def _has_abschluss(text: str) -> bool:
    return bool(re.search(r'(?i)abschlu[sß]\s*:', text or ''))


def _section_hits(text: str) -> dict:
    keys = [
        'Persönliche Daten', 'Fachbereiche', 'Zertifizierungen',
        'Schulungen', 'Branchen', 'Berufliche Erfahrungen',
        'Technische Kenntnisse', 'Weiterbildung',
    ]
    low = (text or '').lower()
    return {k: (k.lower() in low) for k in keys}


class Command(BaseCommand):
    help = 'Original AID-PDF vs neu/cv PDF vergleichen → artifacts Report'

    def add_arguments(self, parser):
        parser.add_argument('--letter', default='aaa')
        parser.add_argument('--dir', default='', dest='consultant_dir')
        parser.add_argument(
            '--out',
            default='',
            help='Zielordner (Default: <repo>/artifacts/<letter>-repro)',
        )
        parser.add_argument('--root', default='')
        parser.add_argument('--limit', type=int, default=0)

    def handle(self, *args, **opts):
        from apps.cv_extractor.management.commands.import_aid_profiles import (
            SKIP_PERSON_DIRS,
            get_best_pdf,
            resolve_aid_profile_root,
        )

        letter = (opts['letter'] or 'aaa').strip()
        dir_filter = (opts['consultant_dir'] or '').strip()
        root = Path(opts['root']) if opts['root'] else resolve_aid_profile_root()
        letter_dir = root / letter
        if not letter_dir.is_dir():
            self.stderr.write(self.style.ERROR(f'Letter fehlt: {letter_dir}'))
            return

        out = Path(opts['out']) if opts['out'] else (
            Path('/mnt/public/udoo-reprap/artifacts') / f'{letter}-repro'
        )
        by_dir = out / 'by_dir'
        by_dir.mkdir(parents=True, exist_ok=True)

        rows = []
        checked = 0
        for person in sorted(letter_dir.iterdir()):
            if not person.is_dir():
                continue
            if person.name in SKIP_PERSON_DIRS:
                continue
            if person.name.lower().startswith('neuer ordner'):
                continue
            if dir_filter and person.name != dir_filter:
                continue
            if opts['limit'] and checked >= opts['limit']:
                break

            orig = get_best_pdf(person)
            neu_dir = person / 'neu' / 'cv'
            neu_pdfs = sorted(
                neu_dir.glob('AID-*.pdf'),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            ) if neu_dir.is_dir() else []
            neu = neu_pdfs[0] if neu_pdfs else None
            checked += 1

            row = {
                'dir': person.name,
                'orig': str(orig) if orig else None,
                'orig_name': orig.name if orig else None,
                'neu': str(neu) if neu else None,
                'neu_name': neu.name if neu else None,
                'status': 'ok',
                'flags': [],
                'score': None,
            }

            if not orig:
                row['status'] = 'no_orig'
                row['flags'].append('kein Original-AID-PDF')
                rows.append(row)
                continue
            if not neu:
                row['status'] = 'no_neu'
                row['flags'].append('kein neu/cv PDF')
                rows.append(row)
                continue

            ot = _norm(_pdf_text(orig))
            nt = _norm(_pdf_text(neu))
            op = _period_anchors(ot)
            np_ = _period_anchors(nt)
            missing_p = sorted(op - np_)
            extra_p = sorted(np_ - op)

            oh = _section_hits(ot)
            nh = _section_hits(nt)

            flags = []
            if _has_weiterbildung(ot) and not _has_weiterbildung(nt):
                flags.append('Weiterbildung fehlt in neu')
            if _has_abschluss(ot) and not _has_abschluss(nt):
                flags.append('Abschluss-Zeile fehlt in neu')
            if oh.get('Berufliche Erfahrungen') and not nh.get('Berufliche Erfahrungen'):
                flags.append('Sektion Berufliche Erfahrungen fehlt')
            if missing_p:
                flags.append(f'Perioden fehlen ({len(missing_p)})')
            if len(nt) < 0.4 * max(len(ot), 1):
                flags.append('neu-Text deutlich kürzer')

            # grober Score 0–100
            period_score = 100.0
            if op:
                period_score = 100.0 * (1 - len(missing_p) / max(len(op), 1))
            sec_keys = [k for k, v in oh.items() if v]
            sec_ok = sum(1 for k in sec_keys if nh.get(k))
            sec_score = 100.0 * sec_ok / max(len(sec_keys), 1) if sec_keys else 100.0
            score = round(0.6 * period_score + 0.4 * sec_score, 1)
            if flags:
                score = max(0.0, score - 5 * len(flags))

            row.update({
                'status': 'compared',
                'score': score,
                'flags': flags,
                'orig_chars': len(ot),
                'neu_chars': len(nt),
                'orig_periods': len(op),
                'neu_periods': len(np_),
                'missing_periods': missing_p[:20],
                'extra_periods': extra_p[:20],
                'orig_sections': oh,
                'neu_sections': nh,
                'weiterbildung_orig': _has_weiterbildung(ot),
                'weiterbildung_neu': _has_weiterbildung(nt),
            })
            rows.append(row)

            detail = [
                f'# {person.name}',
                '',
                f'- Original: `{orig}`',
                f'- neu/cv:   `{neu}`',
                f'- Score: **{score}**',
                f'- Flags: {", ".join(flags) if flags else "—"}',
                '',
                '## Perioden',
                f'- orig={len(op)} neu={len(np_)} missing={missing_p[:15]}',
                '',
                '## Sektionen',
                f'- orig: {oh}',
                f'- neu:  {nh}',
                '',
                '## Original (Auszug 2k)',
                '```',
                ot[:2000],
                '```',
                '',
                '## neu/cv (Auszug 2k)',
                '```',
                nt[:2000],
                '```',
            ]
            (by_dir / f'{person.name}.md').write_text(
                '\n'.join(detail), encoding='utf-8'
            )

        # summary
        compared = [r for r in rows if r['status'] == 'compared']
        avg = (
            round(sum(r['score'] for r in compared) / len(compared), 1)
            if compared else None
        )
        flagged = [r for r in compared if r['flags']]
        no_neu = [r for r in rows if r['status'] == 'no_neu']

        summary_lines = [
            f'# AID Repro-Vergleich `{letter}`',
            f'Stand: {datetime.now().isoformat(timespec="seconds")}',
            f'Root: `{root}`',
            '',
            f'- Ordner geprüft: **{len(rows)}**',
            f'- verglichen: **{len(compared)}**',
            f'- ohne neu/cv: **{len(no_neu)}**',
            f'- Ø Score: **{avg}**',
            f'- mit Flags: **{len(flagged)}**',
            '',
            '## Top-Probleme (Flags)',
            '',
        ]
        for r in sorted(flagged, key=lambda x: x.get('score') or 0)[:40]:
            summary_lines.append(
                f"- `{r['dir']}` score={r['score']}: {', '.join(r['flags'])}"
            )
        if not flagged:
            summary_lines.append('- (keine)')

        summary_lines += [
            '',
            '## Ohne neu/cv',
            '',
        ]
        for r in no_neu[:80]:
            summary_lines.append(f"- `{r['dir']}` orig=`{r.get('orig_name')}`")
        if not no_neu:
            summary_lines.append('- (keine)')

        summary_lines += [
            '',
            '## Alle Scores',
            '',
            '| dir | score | flags | orig | neu |',
            '|-----|------:|-------|------|-----|',
        ]
        for r in sorted(compared, key=lambda x: -(x.get('score') or 0)):
            summary_lines.append(
                f"| `{r['dir']}` | {r['score']} | "
                f"{', '.join(r['flags']) or '—'} | "
                f"`{r.get('orig_name')}` | `{r.get('neu_name')}` |"
            )

        (out / 'summary.md').write_text('\n'.join(summary_lines) + '\n', encoding='utf-8')
        (out / 'index.json').write_text(
            json.dumps(
                {
                    'letter': letter,
                    'root': str(root),
                    'created': datetime.now().isoformat(timespec='seconds'),
                    'avg_score': avg,
                    'rows': rows,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding='utf-8',
        )

        self.stdout.write(self.style.SUCCESS(
            f'Done: compared={len(compared)} no_neu={len(no_neu)} avg={avg} → {out}'
        ))
        self.stdout.write(
            'Sync ins Git-Repo (damit Cloud-Agent lesen kann):\n'
            f'  cd /mnt/public/udoo-reprap && git add artifacts/{letter}-repro '
            f'&& git commit -m "chore: {letter} repro original vs neu/cv" '
            f'&& git push origin cursor/cv-extractor-7f07'
        )
