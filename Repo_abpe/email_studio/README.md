# abpe_email_studio — Git-Spiegel (ucs5 Live)

Exportiert aus `/opt/abpe/backend/apps/abpe_email_studio/` nach `incoming/`.

## Module (Email Studio UI)

| Datei | Bereich |
|---|---|
| `es-studio.js` | Haupt-Editor, Variablen-Chips, Signatur-Panel |
| `es-templates.js` | Vorlagen |
| `es-core.js` | Kern-Logik |
| `es-config.js` | Konfiguration |
| `views.py` / `api.py` | Backend REST |
| `models.py` | Templates, Signaturen, Variablen, Textbausteine |

## Export von ucs5

```bash
cd /mnt/public/udoo-reprap && git pull
bash scripts/export-portal-full.sh
git add Repo_abpe/email_studio Repo_abpe/abpe_ui Repo_abpe/abpe_core
git commit -m "Export: Portal + Email Studio von ucs5"
git push
```

## Deploy Git → Live

```bash
rsync -av Repo_abpe/email_studio/incoming/*.py /opt/abpe/backend/apps/abpe_email_studio/
# Static/Templates analog — siehe RUN-deploy-* Scripts
supervisorctl restart abpe-django
```

Stand im Repo: Live-Export **2026-07-17** (Branch `cursor/portal-email-studio-export-bf44`).
