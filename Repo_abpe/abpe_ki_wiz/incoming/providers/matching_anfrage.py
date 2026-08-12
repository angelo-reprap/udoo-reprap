"""Matching — KI-Anfragen-Wizard (E-Mail → Formularfelder)."""
from __future__ import annotations

import logging
import re
from typing import Any

from apps.abpe_ki_wiz.providers.base import ValidationResult, WizardDomainProvider
from apps.abpe_ki_wiz.registry import register

log = logging.getLogger('abpe_ki_wiz.matching_anfrage')

PROMPT_KEY = 'wiz_matching_anfrage_generate'

_REQUIRED_TOP_KEYS = (
    'kunde', 'ansprechpartner', 'weiterleitung', 'titel', 'beschreibung',
    'start', 'dauer_monate', 'standort', 'remote', 'stundensatz_max',
    'skills', 'hinweise',
)

# Soft-/Zusatzskills → niedrigere Matching-Priorität (nice-to-have)
_NICE_SKILL_RE = re.compile(
    r'^(agile(\s+methoden)?|scrum|kanban|coaching|mentoring|'
    r'knowledge\s*transfer|wissenstransfer|kommunikation|'
    r'teamarbeit|präsentation|deutsch|englisch|'
    r'führerschein|reisebereitschaft)$',
    re.I,
)


def _person_name_from_email(email: str) -> str:
    """bob@bobmichaels.ai → Bob Michaels; bob.michaels@x.de → Bob Michaels."""
    m = re.match(r'^([^@]+)@([^@]+)$', (email or '').strip().lower())
    if not m:
        return ''
    local = re.sub(r'[0-9]+', ' ', m.group(1))
    local_parts = [
        p for p in re.split(r'[._+\-\s]+', local)
        if re.fullmatch(r'[a-zäöüß]{2,}', p, re.I)
    ]

    def cap(s: str) -> str:
        return s[:1].upper() + s[1:].lower() if s else ''

    if len(local_parts) >= 2:
        return ' '.join(cap(p) for p in local_parts)
    if len(local_parts) == 1:
        first = local_parts[0].lower()
        domain_core = re.sub(r'[^a-z0-9äöüß]', '', (m.group(2).split('.')[0] or ''), flags=re.I)
        if domain_core.startswith(first) and len(domain_core) > len(first) + 1:
            rest = domain_core[len(first):]
            if re.fullmatch(r'[a-zäöüß]{2,}', rest, re.I):
                return f'{cap(first)} {cap(rest)}'
        return cap(first)
    return ''


class MatchingAnfrageWizardProvider(WizardDomainProvider):
    wizard_id = 'matching_anfrage'
    title = 'KI-Anfragen-Wizard (Matching)'
    description = (
        'Extrahiert Kundendaten und Anfrage-Details aus E-Mail-Text '
        'für das Matching-Formular „Neue Anfrage“ (DeepSeek, Prompt aus DB).'
    )

    def get_catalog(self, **kwargs) -> dict[str, Any]:
        return {
            'target': 'matching_neu',
            'prompt_key': PROMPT_KEY,
            'fields': [
                'kunde', 'ansprechpartner', 'weiterleitung',
                'titel', 'beschreibung', 'start', 'dauer_monate',
                'standort', 'remote', 'stundensatz_max',
                'skills_required', 'skills_nice', 'skills', 'hinweise',
            ],
            'form_map': {
                'kunde.name': 'new-customer',
                'ansprechpartner.name': 'new-contact',
                'titel': 'new-title',
                'beschreibung': 'new-description',
                'start.datum': 'new-start',
                'dauer_monate': 'new-duration',
                'standort': 'new-location',
                'stundensatz_max': 'new-rate-max',
                'skills': 'new-skills',
            },
        }

    def get_question_catalog(self) -> list[dict[str, Any]]:
        # Ein-Schritt-Extraktion — keine Klärfragen-Runde nötig
        return []

    def resolve_questions(
        self,
        briefing: str,
        answers: dict[str, Any] | None = None,
        analyze_result: dict[str, Any] | None = None,
    ) -> list[str]:
        return []

    def build_checklist(self, answers: dict[str, Any]) -> list[str]:
        return [
            'Nur Fakten aus dem E-Mail-Text',
            'Weiterleitungen: Kunde/AP aus innerem Teil',
            'Nur JSON, kein Markdown',
            'stundensatz_max nur bei klarem Kundenbudget',
            'Skills: Qualifikationen priorisieren (Muss vor Nice-to-have)',
        ]

    def validate_output(self, result: dict[str, Any]) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        if not isinstance(result, dict):
            return ValidationResult(ok=False, errors=['Ergebnis ist kein Objekt'])
        for key in _REQUIRED_TOP_KEYS:
            if key not in result:
                warnings.append(f'Fehlender Key: {key}')
        kunde = result.get('kunde')
        if kunde is not None and not isinstance(kunde, dict):
            errors.append('kunde muss Objekt sein')
        start = result.get('start')
        if start is not None and not isinstance(start, dict):
            errors.append('start muss Objekt sein')
        for sk_key in ('skills', 'skills_required', 'skills_nice'):
            val = result.get(sk_key)
            if val is not None and not isinstance(val, list):
                errors.append(f'{sk_key} muss Array sein')
        return ValidationResult(ok=not errors, errors=errors, warnings=warnings)

    def apply_result(
        self,
        result: dict[str, Any],
        session_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Mappt Extrakt auf Matching-Formularfelder."""
        fields = map_extract_to_form_fields(result)
        return {
            'target': 'matching_neu',
            'extract': result,
            'fields': fields,
            'validation': result.get('validation'),
        }

    def generate_fallback(
        self,
        briefing: str,
        answers: dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Minimaler Fallback ohne KI — leeres Schema + Rohtext + Skill-Heuristik."""
        text = (briefing or '').strip()
        heur = extract_skills_from_text(text)
        return {
            'kunde': {'name': None, 'email_domain': None, 'confidence': 0.0},
            'ansprechpartner': {'name': None, 'email': None, 'phone': None, 'confidence': 0.0},
            'weiterleitung': {'ja': False, 'von': None, 'email': None},
            'titel': None,
            'beschreibung': text[:4000] if text else None,
            'start': {'asap': False, 'datum': None},
            'dauer_monate': None,
            'standort': None,
            'remote': None,
            'stundensatz_max': None,
            'skills_required': heur.get('skills_required') or [],
            'skills_nice': heur.get('skills_nice') or [],
            'skills': heur.get('skills') or [],
            'hinweise': ['KI-Extraktion fehlgeschlagen — Rohtext übernommen'],
            'source': 'rules',
        }


def _looks_like_company(name: str) -> bool:
    import re
    s = (name or '').strip()
    if len(s) < 2 or len(s) > 90:
        return False
    if re.search(
        r'\b(engineer|berater|consultant|developer|manager|specialist|architekt)\b',
        s,
        re.I,
    ):
        return False
    if re.search(r'\b(AG|GmbH|SE|KG|Ltd|Inc|UG|Co\.?\s*KG|e\.?\s*V\.?)\b', s, re.I):
        return True
    # Kurzer Eigenname ohne Job-Wörter
    return bool(re.match(r'^[A-ZÄÖÜ0-9][\wÄÖÜäöüß.&\' -]{1,70}$', s))


def _clean_skill_token(raw: str) -> str:
    s = (raw or '').strip()
    s = re.sub(r'^[\s•\-\*–—·]+', '', s)
    s = re.sub(r'[\s.;:]+$', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    if len(s) < 2 or len(s) > 80:
        return ''
    # Keine ganzen Sätze
    if s.count(' ') > 8 or s.endswith('.'):
        return ''
    low = s.lower()
    if low in {
        'remote', 'deutschland', 'vollzeit', 'freiberuflich', 'asap',
        'interessiert', 'kurzbeschreibung', 'rahmeninformationen',
    }:
        return ''
    return s


def _split_skill_line(line: str) -> list[str]:
    """Eine Qualifikationszeile → Tokens; Klammern aufklappen."""
    line = (line or '').strip()
    if not line:
        return []
    line = re.sub(r'^[\s•\-\*–—·\d.)]+', '', line).strip()
    if not line:
        return []
    out: list[str] = []
    # „Mainframe-Entwicklung (COBOL, PL/I oder Assembler)“
    m = re.match(r'^(.+?)\s*\(([^)]+)\)\s*$', line)
    if m:
        head = _clean_skill_token(m.group(1))
        if head:
            out.append(head)
        inner = m.group(2)
        for part in re.split(r'[,;]|(\s+oder\s+|\s+und\s+|\s+or\s+|\s+and\s+)', inner, flags=re.I):
            if not part or re.fullmatch(r'\s*(oder|und|or|and)\s*', part or '', re.I):
                continue
            tok = _clean_skill_token(part)
            if tok:
                out.append(tok)
        return out

    parts: list[str] = []
    if ',' in line or ';' in line:
        parts = [p for p in re.split(r'[,;]', line) if p and p.strip()]
    else:
        parts = [line]

    for part in parts:
        # „Mentoring und Knowledge Transfer“ → zwei Tokens
        sub = re.split(r'\s+oder\s+|\s+und\s+|\s+or\s+|\s+and\s+', part, flags=re.I)
        if len(sub) > 1 and all(len(_clean_skill_token(x) or x.strip()) <= 40 for x in sub):
            for s in sub:
                tok = _clean_skill_token(s)
                if tok:
                    out.append(tok)
        else:
            tok = _clean_skill_token(part)
            if tok:
                out.append(tok)
    return out


def _is_nice_skill(name: str) -> bool:
    return bool(_NICE_SKILL_RE.match((name or '').strip()))


def extract_skills_from_text(text: str) -> dict[str, list[str]]:
    """
    Heuristik: Skills aus Anfrage-Text ohne KI.
    Quellen: „• Skills: …“, „Ihre Qualifikationen“-Listen, Bullet-Tech-Zeilen.
    Reihenfolge: Muss-Skills zuerst, Nice-to-have danach.
    """
    raw = text or ''
    required: list[str] = []
    nice: list[str] = []
    seen: set[str] = set()

    def _add(token: str, force_nice: bool = False) -> None:
        tok = _clean_skill_token(token)
        if not tok:
            return
        key = tok.lower()
        if key in seen:
            return
        seen.add(key)
        if force_nice or _is_nice_skill(tok):
            nice.append(tok)
        else:
            required.append(tok)

    # 1) Explizite „• Skills: …“ / „Skills: …“ Zeile (oft vom Wizard angehängt)
    for m in re.finditer(
        r'(?:^|\n)\s*(?:[•\-\*–—]\s*)?Skills\s*:\s*(.+?)(?=\n\s*(?:[•\-\*–—]\s*)?[A-ZÄÖÜ]|\n\n|\Z)',
        raw,
        re.I | re.S,
    ):
        chunk = m.group(1).strip()
        # eine Zeile bevorzugen
        first_line = chunk.split('\n', 1)[0]
        for tok in _split_skill_line(first_line.replace('•', ',')):
            _add(tok)

    # 2) Abschnitt „Ihre Qualifikationen“ / „Must-have“ / „Anforderungen“
    sec = re.search(
        r'(?:Ihre\s+Qualifikationen|Qualifikationen|Must[- ]?haves?|'
        r'Anforderungen|Skills\s*/\s*Tools|Technologien)\s*[:\n]+'
        r'(.+?)(?=\n\s*(?:Ihre\s+Aufgaben|Aufgaben|Kurzbeschreibung|'
        r'Nice[- ]?to[- ]?haves?|Interessiert|Rahmeninformationen|'
        r'Wir\s+freuen|Ansprechpartner)\b|\Z)',
        raw,
        re.I | re.S,
    )
    if sec:
        block = sec.group(1)
        for line in block.splitlines():
            line = line.strip()
            if not line or len(line) < 2:
                continue
            if re.match(r'^(referenz|einsatzort|starttermin|arbeitszeit|dauer|sprachen)\b', line, re.I):
                continue
            for tok in _split_skill_line(line):
                _add(tok)

    # 3) Nice-to-have Abschnitt
    nice_sec = re.search(
        r'(?:Nice[- ]?to[- ]?haves?|Wünschenswert|von\s+Vorteil)\s*[:\n]+'
        r'(.+?)(?=\n\s*(?:Ihre\s+Aufgaben|Aufgaben|Kurzbeschreibung|Interessiert)\b|\Z)',
        raw,
        re.I | re.S,
    )
    if nice_sec:
        for line in nice_sec.group(1).splitlines():
            for tok in _split_skill_line(line):
                _add(tok, force_nice=True)

    skills = required + [s for s in nice if s.lower() not in {x.lower() for x in required}]
    return {
        'skills_required': required[:18],
        'skills_nice': nice[:12],
        'skills': skills[:20],
    }


def normalize_skills_from_extract(extract: dict[str, Any] | None) -> dict[str, Any]:
    """
    skills_required + skills_nice + skills → geordnete Listen + weights.
    Falls KI nichts liefert: Heuristik aus beschreibung.
    """
    data = extract if isinstance(extract, dict) else {}

    def _as_list(val: Any) -> list[str]:
        if isinstance(val, list):
            out = []
            for item in val:
                if isinstance(item, dict):
                    name = item.get('name') or item.get('skill') or ''
                else:
                    name = item
                tok = _clean_skill_token(str(name) if name is not None else '')
                if tok:
                    out.append(tok)
            return out
        if isinstance(val, str) and val.strip():
            return [t for p in re.split(r'[,;|\n]+', val) if (t := _clean_skill_token(p))]
        return []

    required = _as_list(data.get('skills_required'))
    nice = _as_list(data.get('skills_nice'))
    plain = _as_list(data.get('skills'))

    if not required and not nice and not plain:
        heur = extract_skills_from_text(
            (data.get('beschreibung') or '') + '\n' + (data.get('titel') or '')
        )
        required = heur['skills_required']
        nice = heur['skills_nice']
        plain = heur['skills']

    # plain ohne Aufteilung: Softskills ans Ende
    if plain and not required and not nice:
        for s in plain:
            if _is_nice_skill(s):
                nice.append(s)
            else:
                required.append(s)
        plain = []

    seen: set[str] = set()
    req_out: list[str] = []
    nice_out: list[str] = []

    def _push(lst: list[str], token: str) -> None:
        key = token.lower()
        if key in seen:
            return
        seen.add(key)
        lst.append(token)

    for s in required:
        (_push(nice_out, s) if _is_nice_skill(s) else _push(req_out, s))
    for s in plain:
        if s.lower() in seen:
            continue
        (_push(nice_out, s) if _is_nice_skill(s) else _push(req_out, s))
    for s in nice:
        _push(nice_out, s)

    skills = req_out + nice_out
    weights = (
        [{'name': s, 'weight': 1.0} for s in req_out]
        + [{'name': s, 'weight': 0.55} for s in nice_out]
    )
    return {
        'skills_required': req_out[:18],
        'skills_nice': nice_out[:12],
        'skills': skills[:20],
        'required_skills': weights[:20],
    }


def derive_customer_name(extract: dict[str, Any] | None) -> str:
    """Fallback wenn kunde.name leer: Titel-Prefix, E-Mail-Domain-Hinweis."""
    data = extract if isinstance(extract, dict) else {}
    kunde = data.get('kunde') if isinstance(data.get('kunde'), dict) else {}
    name = (kunde.get('name') or '').strip()
    if name:
        return name

    title = (data.get('titel') or '').strip()
    for sep in (' - ', ' – ', ' — ', ' | ', ': '):
        if sep in title:
            left = title.split(sep, 1)[0].strip()
            if _looks_like_company(left):
                return left

    ap = data.get('ansprechpartner') if isinstance(data.get('ansprechpartner'), dict) else {}
    email = (ap.get('email') or '').strip()
    domain = (kunde.get('email_domain') or '').strip()
    if not domain and '@' in email:
        domain = email.split('@', 1)[1].strip().lower()
    # hays.de → Hays (nur als schwacher Fallback, AG oft im Titel)
    if domain and '.' in domain:
        base = domain.split('.')[0]
        if base and base.isalpha() and len(base) >= 3:
            guess = base[:1].upper() + base[1:]
            # nur wenn Titel die Firma enthält
            if title and guess.lower() in title.lower():
                # bevorzuge längeren Titel-Treffer mit Rechtsform
                import re
                m = re.search(
                    rf'({re.escape(guess)}[^-\u2013\u2014|]{{0,40}}?\b(?:AG|GmbH|SE|KG)\b)',
                    title,
                    re.I,
                )
                if m:
                    return m.group(1).strip()
                return guess
    return ''


def map_extract_to_form_fields(extract: dict[str, Any] | None) -> dict[str, Any]:
    """Extrakt-JSON → Matching create/form Payload."""
    from datetime import date

    data = extract if isinstance(extract, dict) else {}
    kunde = data.get('kunde') if isinstance(data.get('kunde'), dict) else {}
    ap = data.get('ansprechpartner') if isinstance(data.get('ansprechpartner'), dict) else {}
    start = data.get('start') if isinstance(data.get('start'), dict) else {}
    wl = data.get('weiterleitung') if isinstance(data.get('weiterleitung'), dict) else {}

    location = data.get('standort')
    if data.get('remote') is True:
        loc = (location or '').strip()
        if loc and 'remote' not in loc.lower():
            location = f'{loc} / Remote'
        elif not loc:
            location = 'Remote'

    description = data.get('beschreibung') or ''
    hinweise = data.get('hinweise') if isinstance(data.get('hinweise'), list) else []
    skill_pack = normalize_skills_from_extract(data)
    skills = skill_pack['skills']
    skills_required = skill_pack['skills_required']
    skills_nice = skill_pack['skills_nice']
    required_skills = skill_pack['required_skills']
    notes: list[str] = []
    if wl.get('ja') and (wl.get('von') or wl.get('email')):
        notes.append(
            'Weiterleitung von: '
            + ', '.join(x for x in [wl.get('von'), wl.get('email')] if x)
        )
    start_asap = bool(start.get('asap'))
    start_date = start.get('datum') or None
    # Kein konkretes Datum + asap → Formular-Default = heute („sofort“)
    if not start_date and start_asap:
        start_date = date.today().isoformat()
        notes.append('Start: asap / ab sofort (Formular: heutiges Datum)')
    elif start_asap and start_date:
        notes.append(f'Start: asap / ab sofort ({start_date})')
    for h in hinweise:
        if h and str(h) not in notes:
            notes.append(str(h))
    # Skills nicht nochmal in die Beschreibung hängen, wenn schon „Skills:“ drin —
    # Matching-Feld ist die Quelle; Bullet nur als Lesenotiz wenn Beschreibung noch keine hat.
    if skills and not re.search(r'(?:^|\n)\s*(?:[•\-\*–—]\s*)?Skills\s*:', description or '', re.I):
        notes.append('Skills: ' + ', '.join(str(s) for s in skills[:20] if s))

    if notes:
        block = '\n'.join(f'• {n}' for n in notes)
        description = (description.rstrip() + '\n\n---\n' + block).strip() if description else block

    dauer = data.get('dauer_monate')
    try:
        dauer_int = int(dauer) if dauer is not None else None
    except (TypeError, ValueError):
        dauer_int = None

    rate = data.get('stundensatz_max')
    try:
        rate_int = int(rate) if rate is not None else None
    except (TypeError, ValueError):
        rate_int = None

    customer_name = derive_customer_name(data)
    email_domain = (kunde.get('email_domain') or '').strip()
    ap_email = (ap.get('email') or '').strip()
    if not email_domain and '@' in ap_email:
        email_domain = ap_email.split('@', 1)[1].strip().lower()

    contact_name = (ap.get('name') or '').strip()
    # Nie Firmenname als Person übernehmen (a2a Experts + bob@…)
    if contact_name and customer_name:
        cn = re.sub(r'[^a-z0-9]+', ' ', contact_name.lower()).strip()
        fn = re.sub(r'[^a-z0-9]+', ' ', customer_name.lower()).strip()
        if cn == fn or cn in fn or fn in cn:
            contact_name = ''
    if contact_name and re.search(
        r'\b(gmbh|ag|se|kg|ug|ltd|inc|experts?|consulting|solutions?)\b',
        contact_name,
        re.I,
    ):
        contact_name = ''
    if not contact_name and ap_email:
        contact_name = _person_name_from_email(ap_email)

    return {
        'customer_name': customer_name,
        'contact_name': contact_name,
        'contact_email': ap_email,
        'contact_phone': ap.get('phone') or ap.get('telefon') or '',
        'title': data.get('titel') or '',
        'description': description,
        'start_date': start_date,
        'start_asap': start_asap,
        'duration_months': dauer_int,
        'location': location or '',
        'rate_max': rate_int,
        'skills': skills,
        'skills_required': skills_required,
        'skills_nice': skills_nice,
        'required_skills': required_skills,
        'hinweise': hinweise,
        'weiterleitung': wl,
        'kunde_email_domain': email_domain,
    }


def register_matching_anfrage_provider() -> None:
    register(MatchingAnfrageWizardProvider())
