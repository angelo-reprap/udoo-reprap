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
    from ..models import MatchResult
    return MatchResult.objects.select_related(
        'project_request', 'consultant_cv'
    ).get(id=match_result_id)


def ensure_project_consultant(mr) -> Any:
    """MatchResult → ProjectConsultant (get_or_create)."""
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
  "why": "2-4 Sätze warum anschreiben",
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

    return {
        'ok': True,
        'match_result_id': str(mr.id),
        'consultant_aid': c.aid,
        'consultant_name': c.full_name,
        'score': round(float(mr.overall_score or 0), 3),
        'existing_reason': mr.match_reason or '',
        'why': parsed.get('why') or '',
        'interest': parsed.get('interest') or 'mittel',
        'reply_likelihood': rl,
        'risks': parsed.get('risks') or [],
        'fit_skills': parsed.get('fit_skills') or [],
        'mismatch_notes': parsed.get('mismatch_notes') or [],
        'talking_points': parsed.get('talking_points') or [],
        'model': model,
    }


def list_outreach_email_templates() -> Dict[str, Any]:
    """ACTIVE Email-Studio-Vorlagen für den Outreach-Wizard."""
    templates: List[Dict[str, Any]] = []
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
    return {
        'ok': True,
        'default': DEFAULT_OUTREACH_TEMPLATE,
        'templates': templates,
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
    score = mr.overall_score or 0
    try:
        score_pct = f'{float(score) * 100:.0f}%'
    except Exception:
        score_pct = str(score)
    return {
        'name': c.full_name or '',
        'first_name': first,
        'last_name': last,
        'berater_name': c.full_name or '',
        'project': title,
        'projekt_titel': title,
        'project_number': project.project_number or '',
        'anfragen_id': project.project_number or str(getattr(project, 'id', '') or ''),
        'customer': customer,
        'kunde': customer,
        'skills': points_s,
        'talking_points': points_s,
        'why': why,
        'match_score': score_pct,
        'signature': '',
        'email': (getattr(c, 'email', None) or '').split(';')[0].strip(),
    }


def _baseline_from_context(ctx: Dict[str, Any]) -> Tuple[str, str]:
    """Hardcoded Fallback wenn Email-Studio-Vorlage fehlt."""
    first = ctx.get('first_name') or ''
    title = ctx.get('project') or 'Projekt'
    customer = ctx.get('customer') or ''
    points_s = ctx.get('skills') or ''
    subject = f'Anfrage {title} — passt das für Sie?'
    body = (
        f'Guten Tag {first},\n\n'
        f'zu unserer aktuellen Kundenanfrage „{title}“'
        + (f' ({customer})' if customer else '')
        + ' möchten wir Sie gerne anfragen.\n'
        f'Passt das thematisch zu Ihrem Profil'
        + (f' (u. a. {points_s})' if points_s else '')
        + '?\n\nViele Grüße'
    )
    return subject, body


def build_letter_draft(
    mr,
    deep: Optional[dict] = None,
    extra_notes: str = '',
    template_identifier: Optional[str] = None,
    use_ai: bool = True,
) -> Dict[str, Any]:
    project = mr.project_request
    c = mr.consultant_cv
    ctx = _outreach_template_context(mr, deep=deep)
    first = ctx['first_name']
    title = ctx['project']
    customer = ctx['customer']
    points_s = ctx['skills']

    ident = (template_identifier or DEFAULT_OUTREACH_TEMPLATE).strip() or DEFAULT_OUTREACH_TEMPLATE
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
                ident = DEFAULT_OUTREACH_TEMPLATE
                tpl_name = tpl.name or ident
                subject = _fill_placeholders(tpl.subject or '', ctx).strip() or f'Anfrage {title} — passt das für Sie?'
                body = _fill_placeholders(_plaintext_from_template(tpl), ctx).strip()
            else:
                subject, body = _baseline_from_context(ctx)
        else:
            subject, body = _baseline_from_context(ctx)

    model = 'template'
    if use_ai:
        system = (
            'Du formulierst kurze, professionelle Anschreiben für Personalvermittler. '
            'Antworte NUR als JSON: {"subject":"...","body":"...","greeting":"..."} '
            'body = Plaintext mit \\n, duzen/siezen: Siezen. Kein HTML. '
            'Behalte den Inhalt der Baseline bei, formuliere nur natürlicher.'
        )
        prompt = f"""Persönliches Anschreiben entwerfen (auf Basis der Vorlage).

Anfrage: {title}
Kunde: {customer}
Beschreibung: {(project.description or '')[:400]}
Berater: {c.full_name}
Warum passend: {(deep or {}).get('why') or mr.match_reason or ''}
Talking Points: {points_s}
Extra-Hinweise des Disponenten: {extra_notes or '(keine)'}
Vorlage: {tpl_name or ident}

Baseline-Betreff: {subject}
Baseline-Text:
{body}

Halte den Stil knapp und freundlich. Maximal 120 Wörter im body.
"""
        raw, model = _deepseek_chat(prompt, system=system, max_tokens=500)
        parsed = _parse_json_blob(raw or '') if raw else None
        if parsed and parsed.get('body'):
            subject = (parsed.get('subject') or subject).strip()
            body = (parsed.get('body') or body).strip()
            greeting = (parsed.get('greeting') or f'Guten Tag {first}').strip()
        else:
            greeting = f'Guten Tag {first}'
            model = model if not raw else (model or 'template')
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
    }


def polish_letter(draft_text: str, keep_style: bool = True) -> Dict[str, Any]:
    system = (
        'Du polierst Anschreiben leicht. Antworte NUR JSON '
        '{"body":"..."} mit Plaintext. Keine Erfindung neuer Fakten.'
    )
    prompt = (
        f'Stil beibehalten={keep_style}. Poliere diesen Text (Klarheit, Grammatik, Kürze):\n\n'
        f'{draft_text}'
    )
    raw, model = _deepseek_chat(prompt, system=system, max_tokens=500)
    parsed = _parse_json_blob(raw or '') if raw else None
    body = (parsed or {}).get('body') if parsed else None
    if not body:
        body = draft_text
        model = model or 'noop'
    return {'ok': True, 'body': body, 'body_text': body, 'model': model}
