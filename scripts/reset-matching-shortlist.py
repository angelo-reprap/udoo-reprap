#!/usr/bin/env bash
# Shortlist einer Matching-Anfrage zurücksetzen (nur identified / shortlist-Stufe).
#
# Auf ucs5:
#   cd /opt/abpe/backend
#   /opt/abpe/venv311/bin/python manage.py shell < \
#     /mnt/public/udoo-reprap/scripts/reset-matching-shortlist.py
#
# Oder mit Projekt-ID/Nummer:
#   MATCH_PROJECT=ABpE-2026-… /opt/abpe/venv311/bin/python manage.py shell < scripts/…
#
# Danach im Portal Shortlist öffnen → „Matching starten“ / „Erneut matchen“.
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')

import django
django.setup()

from apps.abpe_matching_workflow.models import ProjectRequest, ProjectConsultant

try:
    from apps.abpe_matching_workflow.models import MatchResult
except Exception:
    MatchResult = None

ref = (
    os.environ.get('MATCH_PROJECT')
    or os.environ.get('PROJECT_ID')
    or (sys.argv[1] if len(sys.argv) > 1 else '')
).strip()

qs = ProjectRequest.objects.all().order_by('-created_at')
if ref:
    p = (
        ProjectRequest.objects.filter(id=ref).first()
        or ProjectRequest.objects.filter(project_number=ref).first()
        or ProjectRequest.objects.filter(title__icontains=ref).first()
    )
    if not p:
        print(f'FEHLER: Anfrage nicht gefunden: {ref!r}')
        print('Letzte Anfragen:')
        for row in qs[:15]:
            print(f'  {row.id}  {getattr(row, "project_number", "")}  {getattr(row, "title", "")}')
        raise SystemExit(1)
else:
    print('Keine MATCH_PROJECT gesetzt — letzte Anfragen:')
    for row in qs[:15]:
        n = ProjectConsultant.objects.filter(project=row).count()
        print(f'  {row.id}  {getattr(row, "project_number", "")}  matches={n}  {getattr(row, "title", "")}')
    print()
    print('Aufruf z.B.: MATCH_PROJECT=<uuid|project_number> python manage.py shell < reset-matching-shortlist.py')
    raise SystemExit(0)

# Nur „frische“ Shortlist-Treffer löschen — Workflow-Board behalten
KEEP = {
    'contacted', 'interested', 'not_interested', 'unavailable',
    'offer_prepared', 'offer_sent',
    'client_interested', 'client_not_interested', 'client_no_feedback',
    'interview_scheduled', 'interview_done', 'interview_cancelled',
    'accepted', 'rejected', 'placed',
    'followup_sent', 'reminder_sent',
    # mögliche Live-Aliase aus Kanban-UI
    'angeschrieben', 'interesse', 'beim_kunden', 'vermittelt', 'absage',
}
to_delete = ProjectConsultant.objects.filter(project=p).exclude(status__in=KEEP)
# Fallback: wenn Status-Namen anders sind — nur identified löschen
n = to_delete.count()
if n == 0:
    to_delete = ProjectConsultant.objects.filter(project=p, status='identified')
    n = to_delete.count()

ids = list(to_delete.values_list('id', flat=True))
deleted, _ = to_delete.delete()
print(f'OK Projekt {getattr(p, "project_number", p.id)}: {deleted} Shortlist-Treffer gelöscht')

if MatchResult is not None:
    mq = MatchResult.objects.filter(project=p)
    if ids:
        # falls MatchResult an consultant gebunden ist
        try:
            mq = mq.filter(consultant_cv_id__isnull=False)  # keep filter soft
        except Exception:
            pass
    md, _ = MatchResult.objects.filter(project=p).delete()
    print(f'OK MatchResult gelöscht: {md}')

print('Jetzt im Portal: Shortlist → „Matching starten“ / „Erneut matchen“')
