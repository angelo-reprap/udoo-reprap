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
      "accounts": ["vertrieb@", "angelo@"]
    }
  }
}
```

Pfad: `/opt/abpe/backend/settings.json`

## IMAP-Fallback (172.20.3.150)

Nur wenn ES nicht erreichbar:

```json
{
  "shaduler": {
    "imap_accounts": [
      {
        "host": "172.20.3.150",
        "port": 993,
        "ssl": true,
        "user": "DISPO_USER",
        "password": "…",
        "folder": "INBOX",
        "label": "Dispo"
      }
    ]
  }
}
```

## ingest_email ins Repo holen (Live → Repo)

Cloud Agent kann Live nicht lesen. Auf **ucs5**:

```bash
bash <(git -C /mnt/public/udoo-reprap show origin/cursor/abpe-shaduler-scaffold-7f07:scripts/PULL-ingest-email-from-live.sh)
# danach commit/push laut Script-Ausgabe
```

Das kopiert `/opt/abpe/backend/apps/ingest_email/` → `Repo_abpe/ingest_email/incoming/`.

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
