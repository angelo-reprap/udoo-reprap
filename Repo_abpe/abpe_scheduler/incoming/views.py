"""abpe_scheduler API — generischer Zeitplaner, reines Backend.
Vollstaendig dokumentiert via drf-spectacular."""
from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import SchedulerJob, SchedulerJobRun
from .recurrence import compute_next_run
from .serializers import SchedulerJobSerializer, SchedulerJobRunSerializer


def _get_job_or_404(job_id):
    return get_object_or_404(SchedulerJob, id=job_id)


@extend_schema(
    summary="Scheduler-Job anlegen (Upsert via job_key)",
    request=SchedulerJobSerializer,
    responses=SchedulerJobSerializer,
)
@api_view(['POST'])
def api_job_create(request):
    data = request.data
    job_key = data.get('job_key', '')
    job = None
    if job_key:
        job = SchedulerJob.objects.filter(
            owner_app=data.get('owner_app'),
            owner_type=data.get('owner_type'),
            owner_ref=data.get('owner_ref'),
            job_key=job_key,
        ).first()

    serializer = SchedulerJobSerializer(instance=job, data=data)
    serializer.is_valid(raise_exception=True)
    job = serializer.save()

    # Beim ERSTEN Anlegen gilt: ONCE-Jobs feuern beim naechsten Tick sofort,
    # auch wenn run_at bereits in der Vergangenheit liegt (z. B. ueberfaellige
    # Erinnerung). compute_next_run() wird hier bewusst NICHT verwendet, da
    # diese Funktion "nach einem abgeschlossenen Lauf" beantwortet, nicht
    # "beim allerersten Anlegen".
    if job.schedule_type == 'ONCE':
        job.next_run_at = job.run_at
    else:
        job.next_run_at = compute_next_run(job, after=timezone.now())
    job.save(update_fields=['next_run_at'])
    return Response(SchedulerJobSerializer(job).data, status=status.HTTP_201_CREATED)


@extend_schema(
    summary="Scheduler-Jobs auflisten",
    parameters=[
        OpenApiParameter('owner_app', str, description="Filter: aufrufende App"),
        OpenApiParameter('owner_type', str, description="Filter: fachlicher Typ"),
        OpenApiParameter('status', str, description="Filter: Status"),
    ],
    responses=SchedulerJobSerializer(many=True),
)
@api_view(['GET'])
def api_job_list(request):
    qs = SchedulerJob.objects.all()
    for field in ('owner_app', 'owner_type', 'status'):
        value = request.query_params.get(field)
        if value:
            qs = qs.filter(**{field: value})
    return Response(SchedulerJobSerializer(qs, many=True).data)


@extend_schema(summary="Scheduler-Job Detail inkl. Run-Historie", responses=SchedulerJobSerializer)
@api_view(['GET'])
def api_job_detail(request, job_id):
    return Response(SchedulerJobSerializer(_get_job_or_404(job_id)).data)


@extend_schema(summary="Scheduler-Job aendern", request=SchedulerJobSerializer, responses=SchedulerJobSerializer)
@api_view(['PATCH'])
def api_job_update(request, job_id):
    job = _get_job_or_404(job_id)
    serializer = SchedulerJobSerializer(job, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    job = serializer.save()
    if 'run_at' in request.data or 'rrule_string' in request.data:
        job.next_run_at = compute_next_run(job, after=timezone.now())
        job.save(update_fields=['next_run_at'])
    return Response(SchedulerJobSerializer(job).data)


@extend_schema(summary="Scheduler-Job abbrechen", responses={204: None})
@api_view(['DELETE'])
def api_job_cancel(request, job_id):
    job = _get_job_or_404(job_id)
    job.status = 'CANCELLED'
    job.next_run_at = None
    job.save(update_fields=['status', 'next_run_at'])
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(summary="Job sofort ausloesen (unabhaengig von next_run_at)", responses=SchedulerJobRunSerializer)
@api_view(['POST'])
def api_job_run_now(request, job_id):
    job = _get_job_or_404(job_id)
    from .tasks import execute_job
    execute_job.delay(job.id)
    return Response({'queued': True})


@extend_schema(
    summary="Pull-Modus: faellige Jobs abholen und leasen",
    parameters=[OpenApiParameter('owner_app', str, required=True)],
    responses=SchedulerJobSerializer(many=True),
)
@api_view(['GET'])
def api_jobs_due(request):
    owner_app = request.query_params.get('owner_app')
    if not owner_app:
        return Response({'error': 'owner_app erforderlich'}, status=400)

    now = timezone.now()
    lease_seconds = int(request.query_params.get('lease_seconds', 120))
    due = SchedulerJob.objects.filter(
        owner_app=owner_app, status='ACTIVE', delivery_mode='PULL',
        next_run_at__lte=now,
    )

    leased = []
    for job in due:
        run, created = SchedulerJobRun.objects.get_or_create(
            job=job, scheduled_for=job.next_run_at,
            defaults={'status': 'RUNNING', 'started_at': now,
                      'leased_at': now, 'leased_until': now + timedelta(seconds=lease_seconds)},
        )
        if created or (run.leased_until and run.leased_until < now):
            leased.append(job)

    return Response(SchedulerJobSerializer(leased, many=True).data)


@extend_schema(
    summary="Pull-Modus: Ergebnis eines abgeholten Jobs melden",
    request={'application/json': {'type': 'object', 'properties': {
        'success': {'type': 'boolean'}, 'message': {'type': 'string'}}}},
    responses={200: SchedulerJobRunSerializer},
)
@api_view(['POST'])
def api_job_complete(request, job_id):
    job = _get_job_or_404(job_id)
    run = job.runs.filter(status='RUNNING').order_by('-scheduled_for').first()
    if not run:
        return Response({'error': 'kein offener Run gefunden'}, status=404)

    success = bool(request.data.get('success'))
    run.status = 'SUCCESS' if success else 'FAILED'
    run.error_message = request.data.get('message', '')[:2000]
    run.finished_at = timezone.now()
    run.save()

    if job.schedule_type == 'ONCE':
        job.status = 'COMPLETED'
        job.next_run_at = None
    else:
        job.next_run_at = compute_next_run(job, after=timezone.now())
        if job.next_run_at is None:
            job.status = 'COMPLETED'
    job.save(update_fields=['status', 'next_run_at'])
    return Response(SchedulerJobRunSerializer(run).data)


@extend_schema(summary="Health-Check", responses={200: None})
@api_view(['GET'])
@permission_classes([AllowAny])
def api_health(request):
    return Response({'status': 'ok', 'active_jobs': SchedulerJob.objects.filter(status='ACTIVE').count()})
