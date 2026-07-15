# Email Studio — Deploy (Dummy-Vorschau)

Zielserver: **ucs5** · Pfad: `/opt/abpe/backend/` · Repo: `/mnt/public/udoo-reprap`

## Was schiefging beim ersten Versuch?

`-save` macht nur ein **Backup der aktuellen Datei** — es kopiert **keine** neuen Dateien aus dem Repo.
Die `git show`-Zeilen waren auskommentiert (`#`) und wurden nicht ausgeführt.
Deshalb: gleiche Konsole, gleiche Sandbox-Warnung, kein „Aktualisieren“-Button.

## Schnell-Deploy (empfohlen)

```bash
cd /mnt/public/udoo-reprap
git fetch origin cursor/email-studio-dummy-preview-bf44
bash Repo_abpe/email_studio/incoming/DEPLOY-preview.sh
```

Danach im Browser **Hard-Reload** (Strg+Shift+R).

## Manuell (falls kein Script)

```bash
cd /opt/abpe/backend
NOTE="Dummy-Vorschau $(date +%Y-%m-%d)"

# 1. Backup ALLER betroffenen Dateien
python3 Archiv/backup_restore.py -save apps/abpe_email_studio/api.py -m "$NOTE"
python3 Archiv/backup_restore.py -save apps/abpe_email_studio/services/renderer.py -m "$NOTE"
python3 Archiv/backup_restore.py -save apps/abpe_email_studio/static/email_studio/js/es-studio.js -m "$NOTE"
python3 Archiv/backup_restore.py -save apps/abpe_ui/templates/abpe_ui/modules/email_studio/studio.html -m "$NOTE"
python3 Archiv/backup_restore.py -save apps/abpe_ui/static/abpe_ui/css/mod/mod-email_studio.css -m "$NOTE"
python3 Archiv/backup_restore.py -save apps/abpe_ui/static/abpe_ui/i18n/de/modules/email_studio/email_studio.json -m "$NOTE"

# 2. Repo holen
cd /mnt/public/udoo-reprap
git fetch origin cursor/email-studio-dummy-preview-bf44
BR=origin/cursor/email-studio-dummy-preview-bf44
R=Repo_abpe/email_studio/incoming
B=/opt/abpe/backend

# 3. Dateien wirklich kopieren (git show → Live-Pfad)
git show $BR:$R/api.py       > $B/apps/abpe_email_studio/api.py
git show $BR:$R/renderer.py  > $B/apps/abpe_email_studio/services/renderer.py
git show $BR:$R/es-studio.js > $B/apps/abpe_email_studio/static/email_studio/js/es-studio.js
git show $BR:$R/studio.html  > $B/apps/abpe_ui/templates/abpe_ui/modules/email_studio/studio.html
git show $BR:$R/mod-email_studio.css > $B/apps/abpe_ui/static/abpe_ui/css/mod/mod-email_studio.css
git show $BR:$R/email_studio.json    > $B/apps/abpe_ui/static/abpe_ui/i18n/de/modules/email_studio/email_studio.json

# 4. Prüfen ob Dateien wirklich neu sind
grep -l "render_preview" $B/apps/abpe_email_studio/api.py
grep -l "preview_refresh" $B/apps/abpe_ui/templates/abpe_ui/modules/email_studio/studio.html
grep "sandbox" $B/apps/abpe_email_studio/static/email_studio/js/es-studio.js
# Erwartung in es-studio.js: sandbox = 'allow-same-origin' (OHNE allow-scripts)

supervisorctl restart abpe-django
```

## Zielpfade (wichtig!)

| Repo-Datei | Live-Pfad auf ucs5 |
|---|---|
| `api.py` | `apps/abpe_email_studio/api.py` |
| `renderer.py` | `apps/abpe_email_studio/services/renderer.py` |
| `es-studio.js` | `apps/abpe_email_studio/static/email_studio/js/es-studio.js` |
| `studio.html` | `apps/abpe_ui/templates/abpe_ui/modules/email_studio/studio.html` |
| `mod-email_studio.css` | `apps/abpe_ui/static/abpe_ui/css/mod/mod-email_studio.css` ⚠ nicht unter email_studio/ |
| `email_studio.json` | `apps/abpe_ui/static/abpe_ui/i18n/de/modules/email_studio/email_studio.json` |

## Prüfen nach Deploy

1. `/email-studio/studio/?template=13` — **Strg+Shift+R**
2. Vorschau-Spalte: Badge **Beispieldaten** + Button **Aktualisieren**
3. Betreff zeigt Datum statt `{termin_datum}`
4. Konsole: **keine** Sandbox-Warnung `allow-scripts`

## Rollback

```bash
cd /opt/abpe/backend
python3 Archiv/backup_restore.py -restore apps/abpe_email_studio/api.py
python3 Archiv/backup_restore.py -restore apps/abpe_email_studio/services/renderer.py
python3 Archiv/backup_restore.py -restore apps/abpe_email_studio/static/email_studio/js/es-studio.js
python3 Archiv/backup_restore.py -restore apps/abpe_ui/templates/abpe_ui/modules/email_studio/studio.html
python3 Archiv/backup_restore.py -restore apps/abpe_ui/static/abpe_ui/css/mod/mod-email_studio.css
python3 Archiv/backup_restore.py -restore apps/abpe_ui/static/abpe_ui/i18n/de/modules/email_studio/email_studio.json
supervisorctl restart abpe-django
```

## Wichtig

- **Niemals** vollständige `views.py` aus dem Repo kopieren.
- Nach Deploy immer **Hard-Reload** — sonst lädt der Browser altes `es-studio.js` aus dem Cache.
