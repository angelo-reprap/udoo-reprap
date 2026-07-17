"""Berechnung von next_run_at aus RRULE bzw. schedule_type=ONCE."""
from datetime import datetime
from dateutil.rrule import rrulestr


def compute_next_run(job, after: datetime):
    if job.schedule_type == 'ONCE':
        return job.run_at if job.run_at and job.run_at > after else None

    if not job.rrule_string or not job.dtstart:
        return None

    rule = rrulestr(job.rrule_string, dtstart=job.dtstart)
    next_occurrence = rule.after(after, inc=False)

    if job.until and next_occurrence and next_occurrence > job.until:
        return None
    return next_occurrence
