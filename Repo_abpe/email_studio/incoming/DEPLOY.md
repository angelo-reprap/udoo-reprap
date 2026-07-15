# Email Studio — Deploy (Dummy-Vorschau)

Zielserver: **ucs5** · Pfad: `/opt/abpe/backend/`

## Vor dem Deploy

```bash
cd /opt/abpe/backend
python3 Archiv/backup_restore.py -save apps/abpe_email_studio/api.py -m "vor dummy preview"
python3 Archiv/backup_restore.py -save apps/abpe_email_studio/services/renderer.py -m "vor dummy preview"
```

## Dateien aus Repo (git show — kein git pull)

```bash
REPO=/pfad/zum/udoo-reprap   # oder Clone auf ucs5
BRANCH=cursor/email-studio-dummy-preview-bf44

git -C "$REPO" fetch origin "$BRANCH"

# Backend
git -C "$REPO" show "origin/$BRANCH:Repo_abpe/email_studio/incoming/api.py" \
  > apps/abpe_email_studio/api.py
git -C "$REPO" show "origin/$BRANCH:Repo_abpe/email_studio/incoming/renderer.py" \
  > apps/abpe_email_studio/services/renderer.py

# Static / Templates
git -C "$REPO" show "origin/$BRANCH:Repo_abpe/email_studio/incoming/es-studio.js" \
  > apps/abpe_email_studio/static/email_studio/js/es-studio.js
git -C "$REPO" show "origin/$BRANCH:Repo_abpe/email_studio/incoming/studio.html" \
  > apps/abpe_ui/templates/abpe_ui/modules/email_studio/studio.html
git -C "$REPO" show "origin/$BRANCH:Repo_abpe/email_studio/incoming/mod-email_studio.css" \
  > apps/abpe_email_studio/static/email_studio/css/mod-email_studio.css
git -C "$REPO" show "origin/$BRANCH:Repo_abpe/email_studio/incoming/email_studio.json" \
  > apps/abpe_ui/static/abpe_ui/i18n/de/modules/email_studio/email_studio.json
```

## Neustart

```bash
supervisorctl restart abpe-django
```

## Prüfen

1. `/email-studio/studio/?template=13` öffnen
2. Vorschau-Spalte: Badge **Beispieldaten** + Button **Aktualisieren**
3. `{termin_datum}`, `{name}` usw. sind ersetzt (nicht mehr als roher Text)
4. Konsole: keine Sandbox-Warnung mehr für `allow-scripts`

## Rollback

```bash
python3 Archiv/backup_restore.py -restore apps/abpe_email_studio/api.py
python3 Archiv/backup_restore.py -restore apps/abpe_email_studio/services/renderer.py
supervisorctl restart abpe-django
```

## Wichtig

- **Niemals** vollständige `views.py` aus dem Repo kopieren (Nav-Deploy-Incident).
- Nur die oben genannten Dateien patchen.
