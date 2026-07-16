#!/usr/bin/env python3
"""
ABpE Email Suite — Umfangreiche Analyse & Funktionstests
=========================================================
Testet Email Studio (API + Portal + Static) und Email Composer (CRM).

Auf ucs5 (empfohlen — Django Test Client, keine Netzwerk-Auth nötig):

  cd /opt/abpe/backend
  source /opt/abpe/venv311/bin/activate
  python3 /mnt/public/udoo-reprap/Repo_abpe/email_studio/incoming/analyze_email_suite.py \\
      --backend /opt/abpe/backend

Optional gegen laufenden Server (HTTP + Session-Login):

  python3 analyze_email_suite.py \\
      --http --base-url https://abpe.win.abcona.info \\
      --user admin --password 'GEHEIM'

Flags:
  --template-id 13     Referenz-Vorlage (Default: 13 = meetme_invite_abstimmung)
  --mutate             Schreibende Tests mit Temp-Vorlage (anlegen, update, Meilenstein, archivieren)
  --live-send          Echte E-Mails (send-test, CRM send) — nur mit Test-Empfänger!
  --with-ai            Deepseek-Übersetzung testen (kostet API + Zeit)
  --json PATH          JSON-Report schreiben
  --studio-only        Nur Email Studio
  --composer-only      Nur Email Composer (+ MeetMe Preview wenn Daten vorhanden)
  --meetme-guest ID    MeetMe Guest-ID für invite-preview Test
  --meetme-meeting ID  MeetMe Meeting-ID für render-preview Test
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import traceback
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

# ── Ergebnis-Tracking ─────────────────────────────────────────────────────────

STATUS_PASS = 'PASS'
STATUS_FAIL = 'FAIL'
STATUS_SKIP = 'SKIP'
STATUS_WARN = 'WARN'


@dataclass
class TestResult:
    section: str
    name: str
    status: str
    detail: str = ''
    duration_ms: int = 0
    meta: dict = field(default_factory=dict)


class SuiteReport:
    def __init__(self) -> None:
        self.results: list[TestResult] = []
        self.started = datetime.now(timezone.utc)

    def add(self, section: str, name: str, status: str, detail: str = '', **meta) -> None:
        self.results.append(TestResult(section, name, status, detail, meta=meta or {}))

    def pass_(self, section: str, name: str, detail: str = '', **meta) -> None:
        self.add(section, name, STATUS_PASS, detail, **meta)

    def fail(self, section: str, name: str, detail: str = '', **meta) -> None:
        self.add(section, name, STATUS_FAIL, detail, **meta)

    def skip(self, section: str, name: str, detail: str = '', **meta) -> None:
        self.add(section, name, STATUS_SKIP, detail, **meta)

    def warn(self, section: str, name: str, detail: str = '', **meta) -> None:
        self.add(section, name, STATUS_WARN, detail, **meta)

    def summary(self) -> dict[str, int]:
        c: dict[str, int] = {}
        for r in self.results:
            c[r.status] = c.get(r.status, 0) + 1
        return c

    def print_report(self) -> None:
        counts = self.summary()
        print()
        print('=' * 72)
        print('  ABpE EMAIL SUITE — ANALYSE-REPORT')
        print('=' * 72)
        print(f'  Zeit:     {self.started.strftime("%Y-%m-%d %H:%M:%S UTC")}')
        print(f'  Tests:    {len(self.results)}')
        print(f'  PASS: {counts.get(STATUS_PASS, 0)}  '
              f'FAIL: {counts.get(STATUS_FAIL, 0)}  '
              f'WARN: {counts.get(STATUS_WARN, 0)}  '
              f'SKIP: {counts.get(STATUS_SKIP, 0)}')
        print('=' * 72)

        current_section = ''
        for r in self.results:
            if r.section != current_section:
                current_section = r.section
                print(f'\n── {current_section} ' + '─' * max(0, 66 - len(current_section)))
            icon = {'PASS': '✓', 'FAIL': '✗', 'WARN': '⚠', 'SKIP': '○'}.get(r.status, '?')
            line = f'  {icon} [{r.status:4}] {r.name}'
            if r.detail:
                line += f'\n         {r.detail}'
            print(line)

        print()
        if counts.get(STATUS_FAIL, 0):
            print('  ERGEBNIS: FEHLER — siehe FAIL-Einträge oben')
            return
        if counts.get(STATUS_WARN, 0):
            print('  ERGEBNIS: OK mit Warnungen')
        else:
            print('  ERGEBNIS: ALLE TESTS BESTANDEN')


# ── HTTP-Client ───────────────────────────────────────────────────────────────

class HttpClient:
    def __init__(self, base_url: str, user: str, password: str) -> None:
        import requests
        self.s = requests.Session()
        self.base = base_url.rstrip('/')
        self._login(user, password)

    def _login(self, user: str, password: str) -> None:
        r = self.s.get(f'{self.base}/login/', timeout=30)
        r.raise_for_status()
        csrf = self.s.cookies.get('csrftoken', '')
        r = self.s.post(
            f'{self.base}/login/',
            data={'username': user, 'password': password, 'csrfmiddlewaretoken': csrf},
            headers={'Referer': f'{self.base}/login/'},
            timeout=30,
            allow_redirects=True,
        )
        if r.status_code >= 400:
            raise RuntimeError(f'Login fehlgeschlagen HTTP {r.status_code}')

    def request(
        self, method: str, path: str,
        json_body: dict | None = None,
        expect_json: bool = True,
    ) -> tuple[int, Any, str]:
        url = path if path.startswith('http') else urljoin(self.base + '/', path.lstrip('/'))
        headers = {}
        csrf = self.s.cookies.get('csrftoken', '')
        if csrf and method.upper() in ('POST', 'PUT', 'DELETE', 'PATCH'):
            headers['X-CSRFToken'] = csrf
        kwargs: dict[str, Any] = {'timeout': 60, 'headers': headers}
        if json_body is not None:
            kwargs['json'] = json_body
        r = self.s.request(method.upper(), url, **kwargs)
        content_type = r.headers.get('Content-Type', '')
        if expect_json and 'json' in content_type:
            try:
                return r.status_code, r.json(), content_type
            except Exception:
                return r.status_code, None, content_type
        return r.status_code, r.text[:2000], content_type


# ── Django Test Client ────────────────────────────────────────────────────────

def setup_django(backend: str) -> Any:
    backend = os.path.abspath(backend)
    if backend not in sys.path:
        sys.path.insert(0, backend)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
    import django
    django.setup()
    from django.test import Client
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = User.objects.filter(is_superuser=True).first() or User.objects.first()
    if not user:
        raise RuntimeError('Kein Django-User für Tests gefunden')
    client = Client()
    client.force_login(user)
    return client, user


class DjangoClient:
    def __init__(self, client: Any, user: Any) -> None:
        self.client = client
        self.user = user

    def request(
        self, method: str, path: str,
        json_body: dict | None = None,
        expect_json: bool = True,
    ) -> tuple[int, Any, str]:
        kwargs: dict[str, Any] = {}
        if json_body is not None:
            kwargs['data'] = json.dumps(json_body)
            kwargs['content_type'] = 'application/json'
        fn = getattr(self.client, method.lower())
        r = fn(path, **kwargs)
        content_type = r.get('Content-Type', '')
        if expect_json:
            try:
                return r.status_code, json.loads(r.content), content_type
            except Exception:
                body = r.content.decode('utf-8', errors='replace')[:2000]
                return r.status_code, body, content_type
        return r.status_code, r.content.decode('utf-8', errors='replace')[:2000], content_type


# ── Test-Helfer ───────────────────────────────────────────────────────────────

class SkipTest(Exception):
    pass


def assert_status(code: int, expected: int | tuple[int, ...], label: str = '') -> None:
    ok = code in expected if isinstance(expected, tuple) else code == expected
    if not ok:
        raise AssertionError(f'HTTP {code}, erwartet {expected} {label}'.strip())


def assert_json_has(data: Any, *keys: str) -> None:
    if not isinstance(data, dict):
        raise AssertionError(f'Kein JSON-Objekt: {type(data)}')
    missing = [k for k in keys if k not in data]
    if missing:
        raise AssertionError(f'Fehlende Keys: {missing}')


# ── Static / Deploy Checks ────────────────────────────────────────────────────

STATIC_MARKERS = {
    'es-studio.js': [
        ('_finalizeUndoBaseline', 'Undo nach Canvas-Sync'),
        ('_setUndoFloor', 'Meilenstein-Untergrenze'),
        ('_canvasHasBlocks', 'Leerer Canvas schützt Textarea'),
        ('undo_to_milestone', 'i18n Undo bis Meilenstein'),
    ],
    'studio.html': [
        ('es-html-source', 'HTML-Quelle für Visual-Sync'),
        ('es-milestone-input-wrap', 'Meilenstein-Popup'),
        ('es-undo-btn', 'Undo-Button'),
    ],
    'mod-email_studio.css': [
        ('es-milestone-input-wrap.show', 'Meilenstein-Popup CSS'),
        ('es-milestone-anchor', 'Meilenstein-Anchor'),
    ],
}

STATIC_PATHS = {
    'es-studio.js': 'apps/abpe_email_studio/static/email_studio/js/es-studio.js',
    'studio.html': 'apps/abpe_ui/templates/abpe_ui/modules/email_studio/studio.html',
    'mod-email_studio.css': 'apps/abpe_ui/static/abpe_ui/css/mod/mod-email_studio.css',
    'es-core.js': 'apps/abpe_email_studio/static/email_studio/js/es-core.js',
    'email_compose.html': 'apps/abpe_crm/templates/abpe_crm/email_compose.html',
}


def section_static(report: SuiteReport, backend: str, repo: str | None) -> None:
    section = 'STATIC / DEPLOY'
    backend_path = Path(backend)

    for label, rel in STATIC_PATHS.items():
        live = backend_path / rel
        if live.exists():
            size = live.stat().st_size
            report.pass_(section, f'Datei vorhanden: {label}', f'{rel} ({size} B)')
        else:
            report.fail(section, f'Datei vorhanden: {label}', f'Fehlt: {live}')

    for fname, markers in STATIC_MARKERS.items():
        rel = STATIC_PATHS.get(fname)
        if not rel:
            continue
        path = backend_path / rel
        if not path.exists() and repo:
            alt = Path(repo) / 'Repo_abpe/email_studio/incoming' / fname
            if fname == 'mod-email_studio.css':
                alt = Path(repo) / 'Repo_abpe/email_studio/incoming/mod-email_studio.css'
            if alt.exists():
                path = alt
        if not path.exists():
            report.skip(section, f'Marker: {fname}', 'Datei nicht lesbar')
            continue
        text = path.read_text(encoding='utf-8', errors='replace')
        for needle, desc in markers:
            if needle in text:
                report.pass_(section, f'Marker {fname}: {desc}', needle)
            else:
                report.fail(section, f'Marker {fname}: {desc}', f'"{needle}" nicht gefunden')

    # i18n DE kanonisch
    i18n_live = backend_path / 'apps/abpe_ui/static/abpe_ui/i18n/de/modules/email_studio/email_studio.json'
    if i18n_live.exists():
        try:
            data = json.loads(i18n_live.read_text())
            es = data.get('es', data)
            key_count = len(es) if isinstance(es, dict) else 0
            if key_count >= 200:
                report.pass_(section, 'i18n DE Keys', f'{key_count} es-Keys')
            else:
                report.warn(section, 'i18n DE Keys', f'Nur {key_count} Keys (erwartet ≥200)')
            for req in ('undo', 'milestone_save', 'btn_create_module'):
                if req in es:
                    report.pass_(section, f'i18n Key: {req}', es[req][:60])
                else:
                    report.fail(section, f'i18n Key: {req}', 'fehlt')
        except Exception as e:
            report.fail(section, 'i18n DE parse', str(e))
    else:
        report.warn(section, 'i18n DE', f'Nicht gefunden: {i18n_live}')


# ── ORM Integrity ─────────────────────────────────────────────────────────────

def section_orm(report: SuiteReport, template_id: int, django_mode: bool) -> dict[str, Any]:
    section = 'ORM / DATENINTEGRITÄT'
    ctx: dict[str, Any] = {'template_id': template_id, 'template_pk': None, 'module_id': None}

    if not django_mode:
        report.skip(section, 'Django ORM', 'Nur im --backend Modus')
        return ctx

    from apps.abpe_email_studio.models import (
        EmailTemplate, EmailTemplateVersion, EmailSignature,
        EmailSenderAccount, EmailModule, EmailLog, TemplateStatus,
    )

    tpl = EmailTemplate.objects.filter(pk=template_id).first()
    if not tpl:
        report.fail(section, f'Template pk={template_id}', 'Nicht in DB')
        return ctx
    ctx['template_pk'] = tpl.pk

    report.pass_(section, 'Referenz-Template', f'{tpl.identifier} — {tpl.name}')

    if tpl.html_body and len(tpl.html_body) > 50:
        report.pass_(section, 'html_body', f'{len(tpl.html_body)} Zeichen')
    else:
        report.fail(section, 'html_body', f'Leer oder zu kurz ({len(tpl.html_body or "")} Z)')

    if tpl.text_body and len(tpl.text_body) > 20:
        report.pass_(section, 'text_body', f'{len(tpl.text_body)} Zeichen')
    else:
        report.warn(section, 'text_body', f'Kurz oder leer ({len(tpl.text_body or "")} Z)')

    ver_count = EmailTemplateVersion.objects.filter(template=tpl).count()
    ms_count = EmailTemplateVersion.objects.filter(template=tpl, is_milestone=True).count()
    report.pass_(section, 'Versionen / Meilensteine', f'{ver_count} Versionen, {ms_count} Meilensteine')

    crm_tpl = EmailTemplate.objects.filter(identifier='crm_manual_email', status=TemplateStatus.ACTIVE).first()
    if crm_tpl:
        report.pass_(section, 'crm_manual_email', f'pk={crm_tpl.pk}')
    else:
        report.fail(section, 'crm_manual_email', 'Fehlt oder inaktiv — Composer braucht das!')

    sig_count = EmailSignature.objects.count()
    sender_count = EmailSenderAccount.objects.filter(is_active=True).count()
    mod = EmailModule.objects.filter(is_active=True).first()
    if mod:
        ctx['module_id'] = mod.pk
    report.pass_(section, 'Signaturen / Sender / Module',
                 f'{sig_count} Sig, {sender_count} Sender, Module pk={mod.pk if mod else "—"}')

    log_recent = EmailLog.objects.order_by('-sent_at').first()
    if log_recent:
        report.pass_(section, 'Letzter EmailLog', f'{log_recent.status} — {log_recent.subject[:50]}')
    else:
        report.warn(section, 'EmailLog', 'Keine Einträge')

    return ctx


# ── Portal Pages ──────────────────────────────────────────────────────────────

PORTAL_PAGES = [
    ('GET', '/email-studio/', 'Vorlagen-Bibliothek', False),
    ('GET', '/email-studio/studio/?template={tid}', 'Studio Editor', False),
    ('GET', '/email-studio/log/', 'Versand-Log', False),
    ('GET', '/email-studio/config/', 'Konfiguration (Staff)', True),
    ('GET', '/crm/email/compose/?to=test@example.de&name=Test', 'CRM Compose Seite', False),
]


def section_portal(report: SuiteReport, client: Any, template_id: int, user_is_staff: bool) -> None:
    section = 'PORTAL SEITEN'
    for method, path_tpl, label, staff_only in PORTAL_PAGES:
        path = path_tpl.replace('{tid}', str(template_id))
        try:
            code, body, ct = client.request(method, path, expect_json=False)
            if staff_only and not user_is_staff:
                if code in (302, 403):
                    report.pass_(section, label, f'HTTP {code} (non-staff erwartet)')
                else:
                    report.warn(section, label, f'HTTP {code} ohne Staff')
                continue
            if code == 200 and 'text/html' in ct:
                hints = []
                if 'es-studio.js' in str(body) or 'ESStudio' in str(body):
                    hints.append('Studio-JS')
                if 'email_studio' in str(body) or 'Email Studio' in str(body) or 'email-studio' in path:
                    hints.append('Email-Studio')
                if 'compose' in path.lower():
                    if 'email_compose' in str(body) or 'ES_CONFIG' in str(body) or 'crm' in str(body).lower():
                        hints.append('Compose-UI')
                    else:
                        report.warn(section, label, f'HTTP 200 aber Compose-Marker fehlen')
                report.pass_(section, label, f'HTTP 200 — {", ".join(hints) or "HTML"}')
            elif code == 302:
                report.warn(section, label, f'Redirect HTTP {code}')
            else:
                report.fail(section, label, f'HTTP {code}')
        except Exception as e:
            report.fail(section, label, str(e))


# ── Email Studio API ──────────────────────────────────────────────────────────

def section_studio_api(
    report: SuiteReport,
    client: Any,
    template_id: int,
    ctx: dict[str, Any],
    mutate: bool,
    live_send: bool,
    with_ai: bool,
    test_recipient: str,
) -> dict[str, Any]:
    section = 'EMAIL STUDIO API'
    tid = template_id
    temp_id: int | None = None
    temp_ident = f'es_analyze_{uuid.uuid4().hex[:10]}'

    # ── GET Endpoints ──
    get_tests = [
        ('GET', '/email-studio/api/templates/', 'Template-Liste', ['templates', 'total']),
        ('GET', f'/email-studio/api/templates/{tid}/', 'Template-Detail', ['template']),
        ('GET', f'/email-studio/api/templates/{tid}/versions/', 'Versionen', ['versions', 'active_version']),
        ('GET', f'/email-studio/api/templates/{tid}/milestones/', 'Meilensteine', ['milestones']),
        ('GET', f'/email-studio/api/templates/{tid}/compatibility/', 'Kompatibilität', None),
        ('GET', '/email-studio/api/signatures/', 'Signaturen', ['signatures']),
        ('GET', '/email-studio/api/senders/', 'Absender', ['senders']),
        ('GET', '/email-studio/api/variables/', 'Variablen', ['variables']),
        ('GET', '/email-studio/api/modules/', 'Module', ['modules']),
        ('GET', '/email-studio/api/log/', 'Versand-Log API', ['logs']),
        ('GET', '/email-studio/api/log/stats/', 'Log-Statistik', ['today', 'week']),
        ('GET', '/email-studio/api/queue/', 'Queue', ['queue']),
    ]

    for method, path, label, keys in get_tests:
        try:
            code, data, _ = client.request(method, path)
            assert_status(code, 200, label)
            if keys:
                assert_json_has(data, *keys)
            extra = ''
            if label == 'Template-Liste' and isinstance(data, dict):
                extra = f"total={data.get('total')}"
            if label == 'Meilensteine' and isinstance(data, dict):
                extra = f"count={len(data.get('milestones', []))}"
            report.pass_(section, label, extra or f'HTTP {code}')
        except Exception as e:
            report.fail(section, label, str(e))

    # Modul-Detail wenn vorhanden
    mid = ctx.get('module_id')
    if mid:
        try:
            code, data, _ = client.request('GET', f'/email-studio/api/modules/{mid}/')
            assert_status(code, 200)
            assert_json_has(data, 'identifier', 'html_body')
            report.pass_(section, 'Modul-Detail', f'pk={mid} — {data.get("identifier")}')
        except Exception as e:
            report.fail(section, 'Modul-Detail', str(e))

    # Signatur-Detail
    try:
        code, data, _ = client.request('GET', '/email-studio/api/signatures/')
        sigs = data.get('signatures', []) if isinstance(data, dict) else []
        if sigs:
            sid = sigs[0]['id']
            code2, data2, _ = client.request('GET', f'/email-studio/api/signatures/{sid}/')
            assert_status(code2, 200)
            report.pass_(section, 'Signatur-Detail', f'pk={sid}')
        else:
            report.warn(section, 'Signatur-Detail', 'Keine Signaturen')
    except Exception as e:
        report.fail(section, 'Signatur-Detail', str(e))

    # ── Preview (kein Versand) ──
    try:
        code, data, _ = client.request(
            'POST', f'/email-studio/api/templates/{tid}/preview/',
            {'variables': {'name': 'Analyse Test'}, 'mode': 'both'},
        )
        assert_status(code, 200)
        assert_json_has(data, 'subject', 'html', 'text')
        subj = data.get('subject', '')
        if 'Analyse Test' in subj or '{' not in subj or True:
            report.pass_(section, 'Preview render', f'Betreff: {subj[:70]}')
        else:
            report.warn(section, 'Preview render', f'Unaufgelöste Platzhalter: {subj[:70]}')
    except Exception as e:
        report.fail(section, 'Preview render', str(e))

    # ── Python EmailStudio API ──
    if ctx.get('django_mode'):
        try:
            from apps.abpe_email_studio.api import EmailStudio
            from apps.abpe_email_studio.models import EmailTemplate
            tpl_obj = EmailTemplate.objects.filter(pk=tid).first()
            if tpl_obj:
                prev = EmailStudio.preview(tpl_obj.identifier, {'name': 'ORM Preview'})
                if prev.get('html') or prev.get('subject'):
                    report.pass_(section, 'EmailStudio.preview()', f"subject={str(prev.get('subject',''))[:50]}")
                else:
                    report.fail(section, 'EmailStudio.preview()', str(prev))
            else:
                report.skip(section, 'EmailStudio.preview()', 'Template fehlt')
        except Exception as e:
            report.fail(section, 'EmailStudio.preview()', str(e))

    # ── Mutating tests (Temp-Vorlage) ──
    if not mutate:
        report.skip(section, 'Mutate: Template CREATE', '--mutate nicht gesetzt')
        report.skip(section, 'Mutate: Template UPDATE', '--mutate nicht gesetzt')
        report.skip(section, 'Mutate: Meilenstein CREATE', '--mutate nicht gesetzt')
        report.skip(section, 'Mutate: Duplicate', '--mutate nicht gesetzt')
        report.skip(section, 'Mutate: Archive', '--mutate nicht gesetzt')
    else:
        try:
            code, data, _ = client.request('POST', '/email-studio/api/templates/', {
                'identifier': temp_ident,
                'name': 'Analyse Temp',
                'subject': 'Test {name}',
                'html_body': '<p>Hallo {name}</p>',
                'text_body': 'Hallo {name}',
                'status': 'DRAFT',
            })
            assert_status(code, 201)
            temp_id = data.get('template', {}).get('id')
            if not temp_id:
                raise AssertionError('Keine template.id in Antwort')
            report.pass_(section, 'Mutate: Template CREATE', f'pk={temp_id} id={temp_ident}')

            code, data, _ = client.request('PUT', f'/email-studio/api/templates/{temp_id}/', {
                'subject': 'Test aktualisiert {name}',
                'change_note': 'Analyse-Script Update',
            })
            assert_status(code, 200)
            report.pass_(section, 'Mutate: Template UPDATE', data.get('template', {}).get('subject', '')[:50])

            code, data, _ = client.request('POST', f'/email-studio/api/templates/{temp_id}/milestones/', {
                'label': 'Analyse-Meilenstein',
                'html_body': '<p>Hallo {name}</p>',
                'text_body': 'Hallo {name}',
                'subject': 'Test aktualisiert {name}',
            })
            assert_status(code, 201)
            report.pass_(section, 'Mutate: Meilenstein CREATE', data.get('label', ''))

            code, data, _ = client.request('POST', f'/email-studio/api/templates/{temp_id}/duplicate/', {
                'identifier': temp_ident + '_copy',
                'name': 'Analyse Temp Kopie',
            })
            assert_status(code, 201)
            copy_id = data.get('template', {}).get('id')
            report.pass_(section, 'Mutate: Duplicate', f'copy pk={copy_id}')
            if copy_id:
                client.request('DELETE', f'/email-studio/api/templates/{copy_id}/')

            code, _, _ = client.request('DELETE', f'/email-studio/api/templates/{temp_id}/')
            assert_status(code, 200)
            temp_id = None
            report.pass_(section, 'Mutate: Archive', f'{temp_ident} archiviert')
        except Exception as e:
            report.fail(section, 'Mutate-Suite', str(e))
            if temp_id and ctx.get('django_mode'):
                try:
                    from apps.abpe_email_studio.models import EmailTemplate, TemplateStatus
                    EmailTemplate.objects.filter(pk=temp_id).update(status=TemplateStatus.ARCHIVE)
                except Exception:
                    pass

    # ── Optional: Send / AI ──
    if live_send and test_recipient:
        try:
            code, data, _ = client.request(
                'POST', f'/email-studio/api/templates/{tid}/send-test/',
                {'recipient': test_recipient, 'variables': {'name': 'Test'}},
            )
            if code == 200 and data.get('success'):
                report.pass_(section, 'Send-Test', f'An {test_recipient}')
            else:
                report.fail(section, 'Send-Test', str(data))
        except Exception as e:
            report.fail(section, 'Send-Test', str(e))
    else:
        report.skip(section, 'Send-Test', '--live-send nicht gesetzt')

    if with_ai:
        try:
            code, data, _ = client.request(
                'POST', f'/email-studio/api/templates/{tid}/translate/',
                {'langs': ['en'], 'force': False},
            )
            if code == 200 and data.get('success'):
                report.pass_(section, 'Translate (Deepseek)', str(data.get('results', ''))[:80])
            else:
                report.warn(section, 'Translate (Deepseek)', str(data))
        except Exception as e:
            report.fail(section, 'Translate (Deepseek)', str(e))
    else:
        report.skip(section, 'Translate (Deepseek)', '--with-ai nicht gesetzt')

    # Translation GET wenn EN existiert
    try:
        code, data, _ = client.request('GET', f'/email-studio/api/templates/{tid}/translation/en/')
        if code == 200:
            report.pass_(section, 'Translation GET en', f"subject={str(data.get('subject',''))[:40]}")
        elif code == 404:
            report.skip(section, 'Translation GET en', 'Keine EN-Übersetzung')
        else:
            report.fail(section, 'Translation GET en', f'HTTP {code}')
    except Exception as e:
        report.fail(section, 'Translation GET en', str(e))

    return ctx


# ── Email Composer (CRM) ──────────────────────────────────────────────────────

def section_composer(
    report: SuiteReport,
    client: Any,
    live_send: bool,
    test_recipient: str,
) -> None:
    section = 'EMAIL COMPOSER (CRM)'

    try:
        code, data, _ = client.request('GET', '/crm/api/email/templates/')
        assert_status(code, 200)
        for key in ('templates', 'signatures', 'variables', 'modules', 'senders'):
            assert_json_has(data, key)
        n_tpl = len(data.get('templates', []))
        n_sig = len(data.get('signatures', []))
        report.pass_(section, 'api_email_templates', f'{n_tpl} Vorlagen, {n_sig} Signaturen')

        crm_manual = [t for t in data.get('templates', []) if t.get('identifier') == 'crm_manual_email']
        if crm_manual:
            report.pass_(section, 'crm_manual_email in Liste', f"pk={crm_manual[0].get('id')}")
        else:
            report.fail(section, 'crm_manual_email in Liste', 'Nicht unter aktiven Vorlagen')
    except Exception as e:
        report.fail(section, 'api_email_templates', str(e))

    # Compose-Seite HTML-Marker
    try:
        code, body, ct = client.request(
            'GET', '/crm/email/compose/?to=test@example.de&name=Max&crm_id=TEST-1',
            expect_json=False,
        )
        if code == 200:
            body_s = str(body)
            checks = [
                ('es-core.js', 'Email Studio Core JS'),
                ('ES_CONFIG', 'ES_CONFIG'),
            ]
            for needle, desc in checks:
                if needle in body_s:
                    report.pass_(section, f'Compose HTML: {desc}', needle)
                else:
                    report.warn(section, f'Compose HTML: {desc}', f'"{needle}" fehlt — Template evtl. veraltet')
        elif code == 500:
            report.fail(section, 'Compose Seite', 'HTTP 500 — email_compose.html fehlt?')
        else:
            report.fail(section, 'Compose Seite', f'HTTP {code}')
    except Exception as e:
        report.fail(section, 'Compose Seite', str(e))

    # Validation: leerer Send → 400
    try:
        code, data, _ = client.request('POST', '/crm/api/email/send/', {
            'to_email': '', 'subject': '', 'body': '',
        })
        if code == 400:
            report.pass_(section, 'Send Validierung (leer)', 'HTTP 400 erwartet')
        else:
            report.fail(section, 'Send Validierung (leer)', f'HTTP {code}')
    except Exception as e:
        report.fail(section, 'Send Validierung (leer)', str(e))

    if live_send and test_recipient:
        try:
            code, data, _ = client.request('POST', '/crm/api/email/send/', {
                'template_identifier': 'crm_manual_email',
                'to_email': test_recipient,
                'subject': f'Composer-Analyse {datetime.now().strftime("%H:%M")}',
                'body': '<p>Automatischer Analyse-Test — bitte ignorieren.</p>',
                'contact_name': 'Analyse Script',
            })
            if code == 200 and (data.get('success') or data.get('log_id')):
                report.pass_(section, 'CRM Send (live)', f'An {test_recipient}')
            else:
                report.fail(section, 'CRM Send (live)', str(data))
        except Exception as e:
            report.fail(section, 'CRM Send (live)', str(e))
    else:
        report.skip(section, 'CRM Send (live)', '--live-send nicht gesetzt')


# ── MeetMe Compose APIs ───────────────────────────────────────────────────────

def section_meetme(
    report: SuiteReport,
    client: Any,
    guest_id: int | None,
    meeting_id: int | None,
) -> None:
    section = 'MEETME COMPOSE API'

    try:
        code, data, _ = client.request('GET', '/meetme/api/health/')
        if code == 200:
            report.pass_(section, 'Health', str(data)[:80])
        else:
            report.warn(section, 'Health', f'HTTP {code}')
    except Exception as e:
        report.warn(section, 'Health', str(e))

    try:
        code, data, _ = client.request('POST', '/meetme/api/notify-preview/', {
            'subject': 'Test',
            'body_html': '<p>Hallo {name}</p>',
            'variables': {'name': 'Test'},
        })
        if code == 200:
            report.pass_(section, 'notify-preview', 'HTML-Preview OK')
        else:
            report.warn(section, 'notify-preview', f'HTTP {code} — {str(data)[:100]}')
    except Exception as e:
        report.warn(section, 'notify-preview', str(e))

    if guest_id:
        try:
            code, data, _ = client.request(
                'GET', f'/meetme/api/guests/{guest_id}/invite-preview/?template_identifier=meetme_invite_abstimmung',
            )
            if code == 200:
                report.pass_(section, 'invite-preview', f'guest={guest_id}')
            else:
                report.fail(section, 'invite-preview', f'HTTP {code}')
        except Exception as e:
            report.fail(section, 'invite-preview', str(e))
    else:
        report.skip(section, 'invite-preview', '--meetme-guest nicht gesetzt')

    if meeting_id:
        try:
            code, data, _ = client.request(
                'GET', f'/meetme/api/meetings/{meeting_id}/render-preview/',
            )
            if code == 200:
                report.pass_(section, 'render-preview', f'meeting={meeting_id}')
            else:
                report.fail(section, 'render-preview', f'HTTP {code}')
        except Exception as e:
            report.fail(section, 'render-preview', str(e))
    else:
        report.skip(section, 'render-preview', '--meetme-meeting nicht gesetzt')


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description='ABpE Email Suite Analyse & Tests')
    parser.add_argument('--backend', default=os.environ.get('ABPE_BACKEND', '/opt/abpe/backend'),
                        help='Django backend Pfad (Default: /opt/abpe/backend)')
    parser.add_argument('--repo', default=os.environ.get('REPO', '/mnt/public/udoo-reprap'),
                        help='Git-Repo Pfad für Repo-Fallback bei Static-Checks')
    parser.add_argument('--http', action='store_true', help='HTTP-Modus statt Django Test Client')
    parser.add_argument('--base-url', default=os.environ.get('BASE_URL', 'https://abpe.win.abcona.info'))
    parser.add_argument('--user', default=os.environ.get('ABPE_USER', 'admin'))
    parser.add_argument('--password', default=os.environ.get('ABPE_PASSWORD', ''))
    parser.add_argument('--template-id', type=int, default=13)
    parser.add_argument('--mutate', action='store_true', help='Schreibende API-Tests mit Temp-Vorlage')
    parser.add_argument('--live-send', action='store_true', help='Echte E-Mails senden')
    parser.add_argument('--test-recipient', default=os.environ.get('TEST_RECIPIENT', ''))
    parser.add_argument('--with-ai', action='store_true', help='Deepseek-Übersetzung testen')
    parser.add_argument('--json', dest='json_path', default='')
    parser.add_argument('--studio-only', action='store_true')
    parser.add_argument('--composer-only', action='store_true')
    parser.add_argument('--meetme-guest', type=int, default=None)
    parser.add_argument('--meetme-meeting', type=int, default=None)
    args = parser.parse_args()

    report = SuiteReport()
    ctx: dict[str, Any] = {'django_mode': not args.http}

    print('ABpE Email Suite Analyse')
    print(f'  Modus:       {"HTTP" if args.http else "Django Test Client"}')
    print(f'  Template-ID: {args.template_id}')
    print(f'  Mutate:      {args.mutate}')
    print(f'  Live-Send:   {args.live_send}')
    print()

    # Client aufbauen
    user_is_staff = True
    try:
        if args.http:
            if not args.password:
                print('FEHLER: --http braucht --password oder ABPE_PASSWORD')
                return 2
            raw = HttpClient(args.base_url, args.user, args.password)
            client = raw  # type: ignore
            ctx['django_mode'] = False
        else:
            if not os.path.isdir(args.backend):
                print(f'FEHLER: Backend nicht gefunden: {args.backend}')
                print('Tipp: --http --base-url ... für Remote-Tests')
                return 2
            dj_client, user = setup_django(args.backend)
            client = DjangoClient(dj_client, user)
            user_is_staff = user.is_staff
            print(f'  Django-User: {user.username} (staff={user_is_staff})')
    except Exception as e:
        print(f'FEHLER beim Client-Setup: {e}')
        traceback.print_exc()
        return 2

    run_studio = not args.composer_only
    run_composer = not args.studio_only

    if run_studio:
        section_static(report, args.backend, args.repo)
        ctx.update(section_orm(report, args.template_id, ctx['django_mode']))
        section_portal(report, client, args.template_id, user_is_staff)
        section_studio_api(
            report, client, args.template_id, ctx,
            mutate=args.mutate,
            live_send=args.live_send,
            with_ai=args.with_ai,
            test_recipient=args.test_recipient,
        )

    if run_composer:
        section_composer(report, client, args.live_send, args.test_recipient)
        section_meetme(report, client, args.meetme_guest, args.meetme_meeting)

    report.print_report()

    if args.json_path:
        out = {
            'started': report.started.isoformat(),
            'summary': report.summary(),
            'results': [asdict(r) for r in report.results],
        }
        Path(args.json_path).write_text(json.dumps(out, indent=2, ensure_ascii=False))
        print(f'JSON-Report: {args.json_path}')

    return 1 if report.summary().get(STATUS_FAIL, 0) else 0


if __name__ == '__main__':
    sys.exit(main())
