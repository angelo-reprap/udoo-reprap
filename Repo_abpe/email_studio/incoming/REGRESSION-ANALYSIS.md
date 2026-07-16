# Email Studio — Regressions-Analyse (Jul 2026)

## Zusammenfassung der kaputten Stände

| Problem | Ursache (Commit) | Fix |
|---------|------------------|-----|
| Meilenstein-Popup öffnet nicht | `e564938`: `.es-milestone-input-wrap.show` durch `.es-milestone-btn:disabled` **ersetzt** | `.show { display:block }` wiederhergestellt |
| Visual zeigt Demo-Skeleton / leer | `b6b62ff` + `e564938`: `_syncCanvasToCode()` beim Init; hardcoded Canvas in `studio.html` | Init ohne Rück-Sync; Canvas nur bei Neu-Vorlagen; `es-html-source` |
| TXT ok, HTML falsch in DB | Skeleton wurde in `html_body` gespeichert, `text_body` nicht | Version restore (Shell) |
| Änderungsnotiz weg | `221c2a3`: bewusst entfernt (gewünscht) | Meilenstein-Popup bleibt für Beschreibung |

## Archiv / Backup

`DEPLOY-undo-i18n.sh` ruft **kein** `Archiv/backup_restore.py` auf.
Vor Deploy auf ucs5 empfohlen:

```bash
cd /opt/abpe/backend
python3 Archiv/backup_restore.py -save apps/abpe_ui/templates/abpe_ui/modules/email_studio/studio.html -m "vor email-studio fix"
python3 Archiv/backup_restore.py -save apps/abpe_email_studio/static/email_studio/js/es-studio.js -m "vor email-studio fix"
python3 Archiv/backup_restore.py -save apps/abpe_ui/static/abpe_ui/css/mod/mod-email_studio.css -m "vor email-studio fix"
```

## Deploy (alle 3 Dateien!)

Nur `es-studio.js` reicht nicht — `studio.html` und `mod-email_studio.css` müssen mit.

```bash
git show origin/cursor/email-studio-undo-i18n-bf44:.../DEPLOY-undo-i18n.sh | bash
```
