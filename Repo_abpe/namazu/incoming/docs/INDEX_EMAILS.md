# Namazu Mail-Indexer (`abpe_emails`)

## Ursache: gelöschte Mails bleiben im Index

`index_emails` hat historisch **nur geschrieben** (Bulk-Upsert). Outlook-Löschungen
wurden nie aus Elasticsearch entfernt → Posteingang zeigte z.B. 70k „angelo“-Mails,
obwohl die INBOX nur noch wenige enthält.

## Fix

- Nach dem Indexieren: **Prune** im `since-days`-Fenster (Docs, die IMAP nicht mehr hat)
- Einmalig / bei großen Löschaktionen: **`--prune-orphans`** — voller Ordner-Abgleich
  (IMAP `ALL` nur Message-ID vs. ES)

## Live deploy (nur Command, keine Settings!)

```bash
cd /mnt/public/udoo-reprap && git fetch origin cursor/abpe-shaduler-scaffold-7f07
bash <(git show origin/cursor/abpe-shaduler-scaffold-7f07:scripts/SYNC-namazu-index-emails.sh)
```

`email_settings.json` auf Live **nicht** überschreiben (Passwörter).

## Gelöschte aufräumen (empfohlen nach Outlook-Massenlöschung)

Nur INBOX, Account `angelo` — kann bei großen Postfächern dauern:

```bash
cd /opt/abpe/backend
/opt/abpe/venv311/bin/python manage.py index_emails \
  --account angelo --folders INBOX --prune-only --prune-orphans
```

Alle Accounts (INBOX):

```bash
/opt/abpe/venv311/bin/python manage.py index_emails --folders INBOX --prune-only --prune-orphans
```

Danach Index + Index neu (optional Catch-up):

```bash
/opt/abpe/venv311/bin/python manage.py index_emails --since-days 14 --folders INBOX
```

## Periodik

Scheduler-Job `email_index`: **jede Minute**, INBOX, `--since-days 2 --incremental`.
Webhook queued Celery-Task (Scheduler-HTTP-Timeout = 15s — synchron würde abbrechen).

```bash
cd /opt/abpe/backend && /opt/abpe/venv311/bin/python manage.py register_scheduler_jobs
supervisorctl restart abpe-django abpe-celery
```

Manuell (ohne Scheduler):

```bash
/opt/abpe/venv311/bin/python manage.py index_emails --since-days 2 --folders INBOX --incremental
```

Webhook-Test: siehe `UMSETZUNG_SCHEDULER.md`.

Für historische Geister weiterhin gelegentlich `--prune-orphans`.
