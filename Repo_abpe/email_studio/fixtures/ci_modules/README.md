# CI-Modul-Fixtures

| Datei | Zweck |
|---|---|
| `abcona_header_*.html` | Header vereinheitlicht (left, 18px) — optional |
| `abcona_header_blau_adresse.html` | Header Blau + www / Tel / Mail |
| `footer_standard.html` / `.txt` | Firmen-Impressum (Deklaration §3) |
| `footer_auto_reply.html` / `.txt` | Impressum + „Bitte nicht antworten“ |

Anwenden über:

```bash
python3 Repo_abpe/email_studio/incoming/apply_layout_consolidation.py --apply-db
```

Siehe `docs/APPLY_CONSOLIDATION.md`. Vorher Backup.
