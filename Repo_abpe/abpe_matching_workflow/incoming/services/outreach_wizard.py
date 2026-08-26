"""
Outreach Wizard — DeepSeek-Begründung + Anschreiben-Draft.

Arbeitet mit MatchResult (Shortlist-ID) und stellt ProjectConsultant bereit.
Nutzt Email-Studio-Vorlagen (Default: matching_outreach_wizard).
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_OUTREACH_TEMPLATE = 'matching_outreach_wizard'

# Empfohlene Email-Studio-Identifier pro Kanban-Spalte (Default, überschreibbar im UI)
STAGE_TEMPLATE_DEFAULTS = {
    'shortlist': 'matching_outreach_wizard',
    'angeschrieben': 'matching_followup_availability',
    'interesse': 'matching_present_to_client',
    'beim_kunden': 'matching_interview_coord',
    'interview': 'matching_placement_start',
    'vermittelt': 'matching_start_info',
    'absage': 'matching_rejection',
}
_BLOCK_RE = re.compile(r'\{\{\s*block:\w+\s*\}\}', re.I)
_TAG_RE = re.compile(r'<[^>]+>')


def _settings() -> dict:
    try:
        # Repo_abpe/settings.json oder Backend BASE_DIR
        candidates = [
            Path(__file__).resolve().parents[3] / 'settings.json',
            Path('/opt/abpe/backend/settings.json'),
        ]
        for p in candidates:
            if p.is_file():
                return json.loads(p.read_text(encoding='utf-8'))
    except Exception as e:
        logger.debug('settings.json: %s', e)
    return {}


def _deepseek_chat(prompt: str, system: str = '', max_tokens: int = 600) -> Tuple[Optional[str], str]:
    """Returns (text, model_or_error)."""
    cfg = (_settings().get('ai_models') or {}).get('deepseek') or {}
    api_key = cfg.get('api_key') or ''
    if not api_key:
        return None, 'no_api_key'
    model = cfg.get('model') or 'deepseek-chat'
    timeout = int(cfg.get('timeout') or 45)
    messages = []
    if system:
        messages.append({'role': 'system', 'content': system})
    messages.append({'role': 'user', 'content': prompt})
    try:
        import requests
        resp = requests.post(
            'https://api.deepseek.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': model,
                'messages': messages,
                'max_tokens': max_tokens,
                'temperature': 0.35,
            },
            timeout=timeout,
        )
        if resp.status_code != 200:
            return None, f'http_{resp.status_code}'
        text = (resp.json().get('choices') or [{}])[0].get('message', {}).get('content', '').strip()
        return (text or None), model
    except Exception as e:
        logger.warning('DeepSeek outreach: %s', e)
        return None, str(e)


def _skill_names(skills_field) -> list:
    if not skills_field:
        return []
    names = []
    for s in skills_field:
        if isinstance(s, dict):
            n = (s.get('name') or '').strip()
            if n:
                names.append(n)
        elif isinstance(s, str) and s.strip():
            names.append(s.strip())
    return names


def _parse_json_blob(text: str) -> Optional[dict]:
    if not text:
        return None
    text = text.strip()
    # fenced ```json
    m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.S)
    if m:
        text = m.group(1)
    else:
        start, end = text.find('{'), text.rfind('}')
        if start >= 0 and end > start:
            text = text[start:end + 1]
    try:
        return json.loads(text)
    except Exception:
        return None


def resolve_match_result(match_result_id):
    """
    Shortlist: MatchResult-ID.
    Kanban/Workflow: ProjectConsultant-ID → zugehöriges MatchResult
    (oder leichtgewichtig aus PC erzeugen).
    """
    from ..models import MatchResult, ProjectConsultant

    qs = MatchResult.objects.select_related('project_request', 'consultant_cv')
    mr = qs.filter(id=match_result_id).first()
    if mr:
        return mr

    pc = ProjectConsultant.objects.select_related(
        'project', 'consultant_cv',
    ).filter(id=match_result_id).first()
    if not pc:
        raise MatchResult.DoesNotExist(
            f'MatchResult/ProjectConsultant {match_result_id} not found'
        )

    mr = (
        qs.filter(
            project_request_id=pc.project_id,
            consultant_cv_id=pc.consultant_cv_id,
        )
        .order_by('-calculated_at', '-overall_score')
        .first()
    )
    if mr:
        mr._resolved_from_pc = pc  # type: ignore[attr-defined]
        return mr

    md = pc.match_details if isinstance(pc.match_details, dict) else {}
    mr = MatchResult.objects.create(
        project_request=pc.project,
        consultant_cv=pc.consultant_cv,
        overall_score=float(pc.match_score or 0),
        match_reason=pc.match_reason or '',
        matched_skills=list(md.get('matched_skills') or []),
        missing_skills=list(md.get('missing_skills') or []),
        skill_details=md if md else {'from_project_consultant': str(pc.id)},
        calculated_by='outreach_from_pc',
    )
    mr._resolved_from_pc = pc  # type: ignore[attr-defined]
    logger.info(
        'MatchResult aus ProjectConsultant erzeugt: pc=%s mr=%s',
        pc.id, mr.id,
    )
    return mr


def ensure_project_consultant(mr) -> Any:
    """MatchResult → ProjectConsultant (get_or_create)."""
    existing = getattr(mr, '_resolved_from_pc', None)
    if existing is not None:
        return existing
    from ..models import ProjectConsultant
    project = mr.project_request
    consultant = mr.consultant_cv
    pc, created = ProjectConsultant.objects.get_or_create(
        project=project,
        consultant_cv=consultant,
        defaults={
            'match_score': mr.overall_score or 0,
            'match_reason': mr.match_reason or '',
            'match_details': {
                'matched_skills': mr.matched_skills or [],
                'missing_skills': mr.missing_skills or [],
                'from_match_result': str(mr.id),
            },
            'matched_by': 'outreach_wizard',
            'status': 'identified',
        },
    )
    if not created:
        # Score/Reason aus neuestem MatchResult nachziehen wenn leer
        dirty = False
        if (mr.overall_score or 0) and (not pc.match_score or pc.match_score < mr.overall_score):
            pc.match_score = mr.overall_score
            dirty = True
        if mr.match_reason and not pc.match_reason:
            pc.match_reason = mr.match_reason
            dirty = True
        if dirty:
            pc.save(update_fields=['match_score', 'match_reason'])
    return pc


def build_deep_reason(mr) -> Dict[str, Any]:
    project = mr.project_request
    c = mr.consultant_cv
    req = _skill_names(project.required_skills)[:12]
    matched = mr.matched_skills or []
    missing = mr.missing_skills or []
    try:
        cons_skills = [cs.skill.name for cs in c.skills.all()[:15]]
    except Exception:
        cons_skills = []

    system = (
        'Du bist Personalvermittler. Antworte NUR mit einem JSON-Objekt, '
        'keine Markdown-Erklärung außerhalb des JSON.'
    )
    prompt = f"""Bewerte diesen Berater für die Anfrage und gib JSON zurück:

{{
  "why": "2-4 Sätze interne Begründung warum anschreiben (Name ok)",
  "why_letter": "2-3 Sätze fürs Anschreiben in Sie-Form; beginne mit ‚Aus Ihrem Werdegang entnehmen wir, …‘ oder ähnlich; NIEMALS den Berater-Namen in der 3. Person",
  "interest": "hoch|mittel|niedrig",
  "reply_likelihood": 0.0,
  "risks": ["..."],
  "fit_skills": ["..."],
  "mismatch_notes": ["..."],
  "talking_points": ["kurze Stichpunkte fürs Anschreiben"]
}}

Anfrage: {project.title}
Kunde: {getattr(project, 'customer_name', '') or ''}
Beschreibung: {(project.description or '')[:500]}
Gesuchte Skills: {', '.join(req)}

Berater: {c.full_name}
AID: {c.aid}
Standort: {c.location or ''}
Matched Skills: {', '.join(matched[:10]) if isinstance(matched, list) else matched}
Missing Skills: {', '.join(missing[:10]) if isinstance(missing, list) else missing}
Profil-Skills: {', '.join(cons_skills)}
Bestehende Match-Begründung: {(mr.match_reason or '')[:400]}
Score: {mr.overall_score}
"""
    raw, model = _deepseek_chat(prompt, system=system, max_tokens=700)
    parsed = _parse_json_blob(raw or '') if raw else None

    if not parsed:
        # Fallback ohne LLM
        why = mr.match_reason or (
            f"{c.full_name} erreicht Score {mr.overall_score:.0%} auf „{project.title}“."
        )
        fit = matched[:5] if isinstance(matched, list) else []
        parsed = {
            'why': why,
            'why_letter': '',
            'interest': 'mittel',
            'reply_likelihood': float(mr.overall_score or 0.5),
            'risks': (missing[:3] if isinstance(missing, list) else []),
            'fit_skills': fit,
            'mismatch_notes': [],
            'talking_points': fit[:3],
        }
        model = model if raw is None else (model or 'parse_fallback')

    # normalize
    try:
        rl = float(parsed.get('reply_likelihood') or 0)
    except Exception:
        rl = float(mr.overall_score or 0)
    rl = max(0.0, min(1.0, rl))

    fit_skills = parsed.get('fit_skills') or []
    why_text = parsed.get('why') or ''
    why_letter = (parsed.get('why_letter') or '').strip()
    if not why_letter:
        why_letter = _why_letter_sie(
            why_text,
            fit_skills=fit_skills if isinstance(fit_skills, list) else [],
            name=c.full_name or '',
            first=(c.first_name or '').strip(),
        )

    return {
        'ok': True,
        'match_result_id': str(mr.id),
        'consultant_aid': c.aid,
        'consultant_name': c.full_name,
        'score': round(float(mr.overall_score or 0), 3),
        'existing_reason': mr.match_reason or '',
        'why': why_text,
        'why_letter': why_letter,
        'interest': parsed.get('interest') or 'mittel',
        'reply_likelihood': rl,
        'risks': parsed.get('risks') or [],
        'fit_skills': fit_skills,
        'mismatch_notes': parsed.get('mismatch_notes') or [],
        'talking_points': parsed.get('talking_points') or [],
        'model': model,
    }


def list_outreach_email_templates() -> Dict[str, Any]:
    """ACTIVE Email-Studio-Vorlagen + Signaturen für den Outreach-Wizard."""
    templates: List[Dict[str, Any]] = []
    signatures: List[Dict[str, Any]] = []
    try:
        from apps.abpe_email_studio.models import EmailTemplate, TemplateStatus
        qs = EmailTemplate.objects.filter(status=TemplateStatus.ACTIVE).order_by('name')
        for t in qs:
            templates.append({
                'id': t.pk,
                'identifier': t.identifier,
                'name': t.name,
                'subject': t.subject or '',
                'is_default': t.identifier == DEFAULT_OUTREACH_TEMPLATE,
            })
    except Exception as e:
        logger.warning('list_outreach_email_templates: %s', e)
    if not any(t['identifier'] == DEFAULT_OUTREACH_TEMPLATE for t in templates):
        templates.insert(0, {
            'id': None,
            'identifier': DEFAULT_OUTREACH_TEMPLATE,
            'name': 'Matching — Outreach-Wizard Anschreiben',
            'subject': 'Anfrage {project} — passt das für Sie?',
            'is_default': True,
        })
    # Default immer zuerst
    templates.sort(key=lambda t: (0 if t.get('is_default') else 1, (t.get('name') or '').lower()))

    try:
        from apps.abpe_email_studio.models import EmailSignature
        qs_sig = EmailSignature.objects.all().order_by('-is_default', 'name')
        for s in qs_sig:
            signatures.append({
                'id': s.pk,
                'name': s.name or f'Signatur {s.pk}',
                'identifier': getattr(s, 'identifier', '') or '',
                'is_default': bool(getattr(s, 'is_default', False)),
            })
    except Exception as e:
        logger.warning('list_outreach_email_templates signatures: %s', e)

    return {
        'ok': True,
        'default': DEFAULT_OUTREACH_TEMPLATE,
        'stage_defaults': dict(STAGE_TEMPLATE_DEFAULTS),
        'templates': templates,
        'signatures': signatures,
    }


def _fill_placeholders(text: str, ctx: Dict[str, Any]) -> str:
    def _repl(m):
        key = m.group(1)
        val = ctx.get(key)
        return '' if val is None else str(val)
    return re.sub(r'\{(\w+)\}', _repl, text or '')


def _plaintext_from_template(tpl) -> str:
    text = (getattr(tpl, 'text_body', None) or '').strip()
    if not text:
        html = (getattr(tpl, 'html_body', None) or '')
        text = _TAG_RE.sub('', html)
        text = (
            text.replace('&nbsp;', ' ')
            .replace('&amp;', '&')
            .replace('&lt;', '<')
            .replace('&gt;', '>')
            .replace('&quot;', '"')
        )
    text = _BLOCK_RE.sub('', text)
    text = re.sub(r'[ \t]+\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _load_es_template(identifier: str):
    if not identifier:
        return None
    try:
        from apps.abpe_email_studio.models import EmailTemplate, TemplateStatus
        return EmailTemplate.objects.filter(
            identifier=identifier, status=TemplateStatus.ACTIVE,
        ).first()
    except Exception as e:
        logger.warning('Email Studio template load %s: %s', identifier, e)
        return None


def _fmt_date(val) -> str:
    if not val:
        return ''
    try:
        return val.strftime('%d.%m.%Y')
    except Exception:
        return str(val)


def _customer_name_variants(customer: str) -> List[str]:
    """Firmennamen + Basis ohne Rechtsform (Bosch GmbH → Bosch)."""
    raw = re.sub(r'\s+', ' ', (customer or '').strip())
    if not raw:
        return []
    variants = {raw}
    base = re.sub(
        r'\s+(GmbH|AG|SE|KG|OHG|UG|mbH|e\.?\s*V\.?|Inc\.?|Ltd\.?|LLC|'
        r'Co\.?|Corporation|Corp\.?|Group|Holding| & Co\.?)\.?\s*$',
        '',
        raw,
        flags=re.I,
    ).strip(' ,.-')
    if base and len(base) >= 3:
        variants.add(base)
    # längere zuerst, damit „Bosch GmbH“ vor „Bosch“ ersetzt wird
    return sorted(variants, key=len, reverse=True)


def _redact_customer_names(text: str, customer: str) -> str:
    """Firmennamen aus Anschreiben-Text entfernen (Vertraulichkeit)."""
    out = text or ''
    if not out or not (customer or '').strip():
        return out
    for v in _customer_name_variants(customer):
        out = re.sub(re.escape(v), '', out, flags=re.I)
    out = re.sub(r'(?im)^\s*Kunde:\s*$', '', out)
    out = re.sub(r'(?i)\bKunde:\s*(?=\n|$)', '', out)
    out = re.sub(r'\(\s*[,;/–-]*\s*\)', '', out)
    out = re.sub(r'\s+([,;:./])', r'\1', out)
    out = re.sub(r' {2,}', ' ', out)
    out = re.sub(r'[ \t]+\n', '\n', out)
    out = re.sub(r'\n{3,}', '\n\n', out)
    return out.strip()


def _why_short(why: str, max_len: int = 280) -> str:
    text = re.sub(r'\s+', ' ', (why or '').strip())
    if not text:
        return ''
    # Ersten 1–2 Sätze bevorzugen
    parts = re.split(r'(?<=[.!?])\s+', text)
    short = ''
    for p in parts:
        if not p:
            continue
        cand = (short + ' ' + p).strip() if short else p
        if short and len(cand) > max_len:
            break
        short = cand
        if len(short) >= 120:
            break
    if not short:
        short = text
    if len(short) > max_len:
        short = short[: max_len - 1].rstrip(' ,;:') + '…'
    return short


def _why_letter_sie(
    why: str,
    fit_skills: Optional[list] = None,
    name: str = '',
    first: str = '',
) -> str:
    """Sie-Form fürs Anschreiben — kein Name in der 3. Person."""
    text = re.sub(r'\s+', ' ', (why or '').strip())
    names = [n for n in (name, first) if n]
    for n in names:
        # „Max Mustermann verfügt über X“ → Werdegang-Form
        text = re.sub(
            rf'^{re.escape(n)}\s+verfügt\s+über\s+',
            'Aus Ihrem Werdegang entnehmen wir, dass Sie über ',
            text,
            flags=re.I,
        )
        text = re.sub(
            rf'^{re.escape(n)}\s+(bringt|hat|zeigt|zeichnet|erreicht)\s+',
            'Aus Ihrem Werdegang entnehmen wir, dass Sie ',
            text,
            flags=re.I,
        )
        text = re.sub(rf'^{re.escape(n)}\s+', '', text, flags=re.I)
    text = text.strip().rstrip('.')
    if not text:
        skills = [str(s) for s in (fit_skills or []) if s][:3]
        if skills:
            return (
                'Aus Ihrem Werdegang entnehmen wir eine starke Passung zu '
                + ', '.join(skills)
                + ', die für diese Anfrage zentral sind.'
            )
        return 'Aus Ihrem Werdegang entnehmen wir eine gute thematische Passung zu dieser Anfrage.'
    # „… dass Sie über X“ → „… dass Sie über X verfügen.“
    m = re.match(
        r'^(Aus Ihrem Werdegang entnehmen wir, dass Sie über .+?)(?:\s+verfügen)?$',
        text,
        re.I,
    )
    if m:
        text = m.group(1).rstrip() + ' verfügen.'
    elif not re.match(
        r'^(Aus Ihrem|Anhand Ihres|Ihrer Erfahrung|Ihrem Profil|Sie |Ihnen )',
        text,
        re.I,
    ):
        rest = text[0].lower() + text[1:] if text[:1].isupper() else text
        text = f'Aus Ihrem Werdegang entnehmen wir, dass {rest}'
        if not text.endswith('.'):
            text += '.'
    elif not text.endswith('.'):
        text += '.'
    return _why_short(text, 320)


def _outreach_template_context(mr, deep: Optional[dict] = None) -> Dict[str, Any]:
    project = mr.project_request
    c = mr.consultant_cv
    first = (c.first_name or '').strip() or (c.full_name or '').split()[0]
    last = (c.last_name or '').strip()
    customer = getattr(project, 'customer_name', '') or ''
    title = project.title or project.project_number or 'Projekt'
    points = (deep or {}).get('talking_points') or (mr.matched_skills or [])[:4]
    if isinstance(points, list):
        points_s = ', '.join(str(p) for p in points[:5] if p)
    else:
        points_s = str(points or '')
    why = ((deep or {}).get('why') or mr.match_reason or '').strip()
    why_letter = ((deep or {}).get('why_letter') or '').strip()
    if not why_letter:
        why_letter = _why_letter_sie(
            why,
            fit_skills=(deep or {}).get('fit_skills') or (mr.matched_skills or [])[:4],
            name=c.full_name or '',
            first=first,
        )
    why_short = why_letter
    score = mr.overall_score or 0
    try:
        score_pct = f'{float(score) * 100:.0f}%'
    except Exception:
        score_pct = str(score)

    req_skills = _skill_names(getattr(project, 'required_skills', None))[:12]
    req_s = ', '.join(req_skills)
    loc = (getattr(project, 'location', None) or '').strip()
    start = _fmt_date(getattr(project, 'start_date', None))
    months = int(getattr(project, 'duration_months', 0) or 0)
    duration = f'{months} Monat{"e" if months != 1 else ""}' if months else ''
    workload_n = int(getattr(project, 'workload_percent', 0) or 0)
    workload = f'{workload_n} %' if workload_n else ''
    remote = 'möglich' if getattr(project, 'remote_possible', True) else 'vor Ort'
    desc = (project.description or '').strip()
    if len(desc) > 900:
        desc = desc[:897].rstrip() + '…'
    # Vertraulichkeit: Firmennamen nicht ins Anschreiben
    title_letter = _redact_customer_names(title, customer) or title
    desc = _redact_customer_names(desc, customer)
    why_short = _redact_customer_names(why_short, customer)

    detail_lines = [
        f'Was: {title_letter}',
    ]
    # kein „Kunde:“ — Vertraulichkeit
    if loc:
        detail_lines.append(f'Wo: {loc}')
    if start:
        detail_lines.append(f'Wann (Start): {start}')
    if duration:
        detail_lines.append(f'Laufzeit: {duration}')
    if workload:
        detail_lines.append(f'Auslastung: {workload}')
    if remote:
        detail_lines.append(f'Remote: {remote}')
    project_details = '\n'.join(detail_lines)

    return {
        'name': c.full_name or '',
        'first_name': first,
        'last_name': last,
        'berater_name': c.full_name or '',
        'project': title_letter,
        'projekt_titel': title_letter,
        'project_number': project.project_number or '',
        'anfragen_id': project.project_number or str(getattr(project, 'id', '') or ''),
        # Platzhalter leer lassen — Template darf keinen Firmennamen zeigen
        'customer': '',
        'kunde': '',
        'location': loc,
        'standort': loc,
        'start': start,
        'start_date': start,
        'duration': duration,
        'laufzeit': duration,
        'workload': workload,
        'auslastung': workload,
        'remote': remote,
        'description': desc,
        'beschreibung': desc,
        'project_details': project_details,
        'required_skills': req_s,
        'skills': points_s or req_s,
        'talking_points': points_s,
        'why': why,
        'why_short': why_short,
        'match_score': score_pct,
        'signature': '',
        'email': (getattr(c, 'email', None) or '').split(';')[0].strip(),
        '_customer_internal': customer,
    }


def _baseline_from_context(ctx: Dict[str, Any]) -> Tuple[str, str]:
    """Hardcoded Fallback: Begrüßung → Anfrage ausführlich → Warum kurz."""
    first = ctx.get('first_name') or ''
    title = ctx.get('project') or 'Projekt'
    details = (ctx.get('project_details') or f'Was: {title}').strip()
    desc = (ctx.get('description') or '').strip()
    req = (ctx.get('required_skills') or ctx.get('skills') or '').strip()
    why_short = (ctx.get('why_short') or ctx.get('why') or '').strip()

    subject = f'Anfrage {title} — passt das für Sie?'
    parts = [
        f'Guten Tag {first},',
        '',
        'wir möchten Sie persönlich zu folgender Kundenanfrage anfragen:',
        '',
        details,
    ]
    if desc:
        parts.extend(['', desc])
    if req:
        parts.extend(['', f'Gesucht u. a.: {req}'])
    if why_short:
        parts.extend(['', 'Warum wir Sie ansprechen:', why_short])
    parts.extend([
        '',
        'Über eine kurze Rückmeldung freuen wir uns.',
        '',
        'Mit freundlichen Grüßen',
    ])
    return subject, '\n'.join(parts)


def build_letter_draft(
    mr,
    deep: Optional[dict] = None,
    extra_notes: str = '',
    template_identifier: Optional[str] = None,
    use_ai: bool = True,
    stage: str = '',
) -> Dict[str, Any]:
    project = mr.project_request
    c = mr.consultant_cv
    ctx = _outreach_template_context(mr, deep=deep)
    first = ctx['first_name']
    title = ctx['project']
    customer_internal = ctx.get('_customer_internal') or getattr(project, 'customer_name', '') or ''
    points_s = ctx['skills']
    stage_l = (stage or '').strip().lower().replace('-', '_').replace(' ', '_')
    stage_hints = {
        'shortlist': (
            'Erstanschreiben: Interesse wecken, Anfrage kurz vorstellen, '
            'nach Passung/Verfügbarkeit fragen.'
        ),
        'angeschrieben': (
            'Follow-up nach erstem Kontakt: nach Verfügbarkeit/Interesse fragen, '
            'höflich nachfassen.'
        ),
        'interesse': (
            'Berater hat Interesse signalisiert: bedanken, mitteilen dass wir ihn '
            'der Kundenanfrage vorstellen / Profil weiterleiten möchten, '
            'Einverständnis und nächste Schritte klären. KEIN Firmenname.'
        ),
        'beim_kunden': (
            'Beim Kunden vorgestellt: Informieren dass Rückmeldung vom Kunden kommt '
            '(Interview-Wunsch, Termin oder Absage). Offen für Terminvorschläge halten.'
        ),
        'interview': (
            'Interview-Koordination oder Vermittlungs-/Startabstimmung: '
            'Termine oder Startwünsche erfragen.'
        ),
        'vermittelt': (
            'Startinfo nach Vermittlung: Starttermin, Ort/Remote, Ansprechpartner über uns.'
        ),
        'absage': (
            'Freundliche Absage: Dank für Interesse, Kunde hat sich anderweitig entschieden, '
            'Tür für Folgeanfragen offen halten.'
        ),
    }
    stage_hint = stage_hints.get(stage_l, stage_hints['shortlist'])

    ident = (template_identifier or DEFAULT_OUTREACH_TEMPLATE).strip() or DEFAULT_OUTREACH_TEMPLATE
    if not template_identifier and stage_l:
        ident = STAGE_TEMPLATE_DEFAULTS.get(stage_l, ident)
    tpl = _load_es_template(ident)
    tpl_name = ''
    if tpl:
        tpl_name = tpl.name or ident
        subject = _fill_placeholders(tpl.subject or '', ctx).strip() or f'Anfrage {title} — passt das für Sie?'
        body = _fill_placeholders(_plaintext_from_template(tpl), ctx).strip()
        if not body:
            subject, body = _baseline_from_context(ctx)
    else:
        if ident != DEFAULT_OUTREACH_TEMPLATE:
            # Gewählte Vorlage fehlt → Default versuchen
            tpl = _load_es_template(DEFAULT_OUTREACH_TEMPLATE)
            if tpl:
                # Identifier beibehalten wenn Stage-Vorlage fehlt? Besser Default-Inhalt
                # aber Stage-Hinweis in AI nutzen. Ident für UI: angeforderte Stage-ID belassen
                # nur body/subject aus Default-Template wenn Stage-Template fehlt.
                fallback_ident = DEFAULT_OUTREACH_TEMPLATE
                tpl_name = (tpl.name or fallback_ident) + f' (Fallback, {ident} fehlt)'
                subject = _fill_placeholders(tpl.subject or '', ctx).strip() or f'Anfrage {title} — passt das für Sie?'
                body = _fill_placeholders(_plaintext_from_template(tpl), ctx).strip()
            else:
                subject, body = _baseline_from_context(ctx)
        else:
            subject, body = _baseline_from_context(ctx)

    # Leere „Kunde:“-Zeilen aus Template entfernen
    body = re.sub(r'(?im)^\s*Kunde:\s*\n?', '', body or '')
    body = re.sub(r'\n{3,}', '\n\n', body).strip()
    subject = _redact_customer_names(subject, customer_internal)
    body = _redact_customer_names(body, customer_internal)

    model = 'template'
    if use_ai:
        system = (
            'Du formulierst professionelle, persönliche Anschreiben für Personalvermittler. '
            'Antworte NUR als JSON: {"subject":"...","body":"...","greeting":"..."} '
            'body = Plaintext mit \\n, Siezen, kein HTML, keine Signatur im Text. '
            'VERTRAULICHKEIT: Niemals Firmen- oder Kundennamen nennen.'
        )
        prompt = f"""Schreibe ein persönliches Anschreiben an den Berater.

Workflow-Stufe: {stage_l or 'shortlist'}
Ziel dieser Mail: {stage_hint}

ZWINGENDE Struktur (an die Stufe anpassen):
1) Begrüßung mit Vornamen (z. B. „Guten Tag {first},“)
2) Anfrage-/Sachteil passend zur Stufe (Was/Wo/Wann nur wenn Erstanschreiben oder nötig;
   KEINE Zeile „Kunde:“, KEIN Firmenname).
3) Bei Erstanschreiben: Absatz „Warum wir Sie ansprechen:“ — Sie-Form.
   Bei späteren Stufen: klarer nächster Schritt statt neuem Warum-Absatz.
4) Bitte um kurze Rückmeldung + „Mit freundlichen Grüßen“
Keine Signatur / keinen Absendernamen anhängen.

VERTRAULICHKEIT (streng):
- Firmen-/Kundennamen NIEMALS nennen.
- Keine Zeile „Kunde: …“. Formuliere „unsere Kundenanfrage“ / „das Projekt“.
- Interner Kundenname nur zur Info, NICHT verwenden: {customer_internal or '(leer)'}

Anfrage: {title}
Standort: {ctx.get('location') or '—'}
Start: {ctx.get('start') or '—'}
Laufzeit: {ctx.get('duration') or '—'}
Auslastung: {ctx.get('workload') or '—'}
Remote: {ctx.get('remote') or '—'}
Beschreibung (bereits bereinigt): {(ctx.get('description') or '')[:800]}
Gesuchte Skills: {ctx.get('required_skills') or points_s}
Berater (nur intern): {c.full_name}
Warum passend (intern): {(deep or {}).get('why') or mr.match_reason or ''}
Warum fürs Anschreiben (Sie-Form): {ctx.get('why_short') or ''}
Talking Points: {points_s}
Extra-Hinweise: {extra_notes or '(keine)'}
Vorlage: {tpl_name or ident}

Baseline-Betreff: {subject}
Baseline-Text:
{body}

Ca. 120–220 Wörter im body, passend zur Stufe.
"""
        raw, model = _deepseek_chat(prompt, system=system, max_tokens=900)
        parsed = _parse_json_blob(raw or '') if raw else None
        if parsed and parsed.get('body'):
            subject = (parsed.get('subject') or subject).strip()
            body = (parsed.get('body') or body).strip()
            greeting = (parsed.get('greeting') or f'Guten Tag {first}').strip()
        else:
            greeting = f'Guten Tag {first}'
            model = model if not raw else (model or 'template')
        subject = _redact_customer_names(subject, customer_internal)
        body = _redact_customer_names(body, customer_internal)
        body = re.sub(r'(?im)^\s*Kunde:\s*\n?', '', body or '')
        body = re.sub(r'\n{3,}', '\n\n', body).strip()
    else:
        greeting = f'Guten Tag {first}'

    email = ctx.get('email') or ''

    return {
        'ok': True,
        'match_result_id': str(mr.id),
        'to_email': email,
        'subject': subject,
        'body': body,
        'body_text': body,
        'greeting': greeting,
        'model': model,
        'consultant_name': c.full_name,
        'consultant_aid': c.aid,
        'template_identifier': ident,
        'template_name': tpl_name or ident,
        'stage': stage_l or 'shortlist',
        'why_short': ctx.get('why_short') or '',
        'project_details': ctx.get('project_details') or '',
    }


def polish_letter(draft_text: str, keep_style: bool = True) -> Dict[str, Any]:
    system = (
        'Du polierst Anschreiben leicht. Antworte NUR JSON '
        '{"body":"..."} mit Plaintext. Keine Erfindung neuer Fakten. '
        'Behalte die Struktur: Begrüßung → Anfrage → Warum kurz → Abschluss. '
        'Im Warum-Absatz immer Sie-Form '
        '(„Aus Ihrem Werdegang entnehmen wir …“); '
        'keine Namen in der 3. Person.'
    )
    prompt = (
        f'Stil beibehalten={keep_style}. Poliere diesen Text (Klarheit, Grammatik):\n\n'
        f'{draft_text}'
    )
    raw, model = _deepseek_chat(prompt, system=system, max_tokens=900)
    parsed = _parse_json_blob(raw or '') if raw else None
    body = (parsed or {}).get('body') if parsed else None
    if not body:
        body = draft_text
        model = model or 'noop'
    return {'ok': True, 'body': body, 'body_text': body, 'model': model}
