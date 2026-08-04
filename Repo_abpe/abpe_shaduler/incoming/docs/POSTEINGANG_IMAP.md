# Posteingang (Elasticsearch → IMAP-Fallback)

Shaduler zeigt **read-only** Header + Preview.

## Quellen-Reihenfolge

1. **Elasticsearch** Index `abpe_emails` (bereits von ingest/automail indexiert) — **Primär**
2. ingest_email-DB (`EmailMessage`), falls App/Modelle da
3. Direkt-IMAP (Host z.B. `172.20.3.150`) — Fallback

## Elasticsearch (Standard)

Kein Extra-Credential nötig, wenn ES lokal wie im Portal läuft:

- Hosts: `settings.json` → `elasticsearch.hosts` (Default `http://localhost:9200`)
- Index: `abpe_emails` (override: `shaduler.es_mail_index`)

Optional filtern:

```json
{
  "shaduler": {
    "es_mail_index": "abpe_emails",
    "es_mail": {
      "folder": "INBOX",
      "accounts": ["angelo", "vertrieb", "sg"],
      "days": 30
    }
  }
}
```

`days` blendet ältere Treffer aus; ohne Treffer fällt der Service auf ungefiltert zurück.

## Wer befüllt `abpe_emails`?

**Nicht der Shaduler.** Indexer sitzt unter Live `apps/namazu` (IMAP → ES),
gesteuert über `email_settings.json` + Management-Command / SchedulerJob —
nicht Celery-Beat.

Ins Repo holen:

```bash
cd /mnt/public/udoo-reprap && git fetch origin cursor/abpe-shaduler-scaffold-7f07
bash <(git show origin/cursor/abpe-shaduler-scaffold-7f07:scripts/PULL-namazu-mail-indexer-from-live.sh)
# commit/push, dann Cloud Agent repariert Date-Parsing
```

Bekannter Index-Bug: `date=4501-01-01…` (kaputte Werte). Der Posteingang
filtert sie aus (`2000 ≤ date ≤ now+1d`). Root-Cause im namazu-Indexer fixen.

## IMAP aus EmailImportConfig (keine zweite Credential-Ablage)

Felder (Live-Modell):

| Feld | Bedeutung |
|------|-----------|
| `imap_server` / `imap_port` / `use_ssl` | Server |
| `username` / `password` | Login |
| `mailbox` | Ordner (Default `INBOX`) |
| `name` / `email_address` | Anzeige |
| `is_active` | nur aktive Configs |

Fallback nur wenn keine aktive Config: `settings.json` → `shaduler.imap_accounts`.

## DB-Quelle EmailMessage

`status=NEW` → Badge „neu“; Preview aus `body_plain`[:180]; Sortierung `-received_date`.

## ingest_email ins Repo holen (Live → Repo)

**Zuerst fetch** (sonst kennt `origin/…` das Script nicht):

```bash
cd /mnt/public/udoo-reprap
git fetch origin cursor/abpe-shaduler-scaffold-7f07
bash <(git show origin/cursor/abpe-shaduler-scaffold-7f07:scripts/PULL-ingest-email-from-live.sh)
# danach commit/push laut Script-Ausgabe
```

Ohne Script (gleicher Effekt):

```bash
mkdir -p /mnt/public/udoo-reprap/Repo_abpe/ingest_email/incoming
rsync -a --delete --exclude '__pycache__/' --exclude '*.pyc' \
  /opt/abpe/backend/apps/ingest_email/ \
  /mnt/public/udoo-reprap/Repo_abpe/ingest_email/incoming/
cd /mnt/public/udoo-reprap
git checkout cursor/abpe-shaduler-scaffold-7f07
git pull origin cursor/abpe-shaduler-scaffold-7f07
git add Repo_abpe/ingest_email/incoming
git commit -m 'Import: ingest_email von Live nach Repo'
git push -u origin cursor/abpe-shaduler-scaffold-7f07
```

Das kopiert `/opt/abpe/backend/apps/ingest_email/` → `Repo_abpe/ingest_email/incoming/`.
IMAP-Zugänge kommen aus **`EmailImportConfig`** (Konzept).

## SYNC vs. PULL (wichtig)

| Script | Richtung | Was | Überschreibt? |
|--------|----------|-----|----------------|
| `SYNC-abpe-shaduler-files.sh` | **Repo → Live** | `abpe_shaduler` + Shaduler-UI-Dateien | **Ja** (`rsync --delete` auf der App; Live-Migrations `0*.py` geschützt) |
| `PULL-ingest-email-from-live.sh` | **Live → Repo** | `ingest_email` | Repo-Kopie, **nicht** Live |

`SYNC` berührt **`ingest_email` nicht**. Nur Sync + Restart reicht für Shaduler-Code; Credentials/ES müssen schon auf dem Server liegen.

## Live prüfen

```bash
cd /opt/abpe/backend && /opt/abpe/venv311/bin/python manage.py shaduler_inbox_probe
/opt/abpe/venv311/bin/python manage.py shaduler_inbox_probe --fetch --limit 10
# erzwingen IMAP statt ES:
/opt/abpe/venv311/bin/python manage.py shaduler_inbox_probe --fetch --force-imap
```

UI: `/shaduler/?tab=posteingang` — „Aufgabe erzeugen“ legt eine DB-Aufgabe an.
API liefert `source: "elasticsearch"` wenn ES greift.
