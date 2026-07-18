# Email Studio — DB-Snapshots

Hier liegen `dumpdata`-Exporte der Live-DB (ucs5):

- `email_studio_snapshot_YYYY-MM-DD.json` — datierter Export
- `email_studio_snapshot_latest.json` — Kopie des letzten Exports (stabile Agent-Pfade)

Enthaltene Modelle: `EmailModule`, `EmailTemplate`, `EmailSignature`, `EmailSenderAccount`.

Erzeugen auf ucs5:

```bash
bash Repo_abpe/email_studio/incoming/export-email-studio-data.sh
```
