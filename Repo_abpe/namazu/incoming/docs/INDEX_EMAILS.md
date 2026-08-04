# Namazu Mail-Indexer (`abpe_emails`)

## Ursache des Stillstands

In `index_emails.py` war `size_bytes` **undefiniert** → jede Mail crashte im
`try/except` still → Index blieb bei ~Juni 2026 stehen.
Zusätzlich landeten kaputte Dates (`4501-…`) im Index.

## Fix (Repo)

- `size_bytes = len(raw)`
- `sane_date_iso()` verwirft year∉[2000,2100]; Fallback INTERNALDATE
- `--since-days` (Default 14), Default nur `INBOX`
- `--all-folders` für Vollscan

## Live deploy (nur Command, keine Settings!)

```bash
cd /mnt/public/udoo-reprap && git fetch origin cursor/abpe-shaduler-scaffold-7f07
bash <(git show origin/cursor/abpe-shaduler-scaffold-7f07:scripts/SYNC-namazu-index-emails.sh)
```

`email_settings.json` auf Live **nicht** überschreiben (Passwörter).

## Catch-up + Periodik

```bash
cd /opt/abpe/backend
# einmal aufholen (INBOX, 90 Tage) — kann dauern
/opt/abpe/venv311/bin/python manage.py index_emails --since-days 90

# Shaduler sync (Webhook email-index) + Jobs registrieren
bash <(git show origin/cursor/abpe-shaduler-scaffold-7f07:scripts/SYNC-abpe-shaduler-files.sh)
supervisorctl restart abpe-django
/opt/abpe/venv311/bin/python manage.py register_scheduler_jobs

/opt/abpe/venv311/bin/python manage.py shaduler_inbox_probe --fetch --limit 5
```

Scheduler-Job `email_index`: alle 10 Min, `--since-days 3`, INBOX.
