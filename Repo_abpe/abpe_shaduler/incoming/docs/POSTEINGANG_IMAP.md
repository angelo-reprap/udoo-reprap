# Posteingang / IMAP (172.20.3.150)

Shaduler liest **read-only** Header + Preview.

## Konfiguration (eine davon)

### A) `settings.json` (empfohlen schnell)

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

Pfad: `/opt/abpe/backend/settings.json`

### B) Django settings

```python
SHADULER_IMAP_ACCOUNTS = [
    {
        'host': '172.20.3.150',
        'port': 993,
        'ssl': True,
        'user': '…',
        'password': '…',
        'folder': 'INBOX',
        'label': 'Dispo',
    },
]
```

### C) ingest_email-Modelle

Wenn `MailAccount` / `EmailAccount` / `EmailMessage` existieren, werden sie
automatisch erkannt (Probe zeigt die Modellnamen).

## Live prüfen

```bash
python manage.py shaduler_inbox_probe
python manage.py shaduler_inbox_probe --fetch --limit 10
# erzwingen IMAP statt DB:
python manage.py shaduler_inbox_probe --fetch --force-imap
```

UI: `/shaduler/?tab=posteingang` — „Aufgabe erzeugen“ legt eine DB-Aufgabe an.
