# Repo_abpe — Staging für Live-Dateien (ucs5 → GitHub)

Spiegelung von `/mnt/public/Repo_abpe/` auf ucs5.

## Schnellstart auf ucs5

```bash
# Einzeldatei
/opt/abpe/scripts/export-to-repo.sh email_studio --from-backend abpe_email_studio/tasks.py

# Portal-Basis komplett (Shell, URLs, settings.json redigiert, Module)
/opt/abpe/scripts/export-portal-baseline.sh
```

Skripte holen:

```bash
mkdir -p /opt/abpe/scripts
BASE="https://raw.githubusercontent.com/angelo-reprap/udoo-reprap/cursor/portal-export-script-bf44/scripts"
curl -fsSL -o /opt/abpe/scripts/export-to-repo.sh "$BASE/export-to-repo.sh"
curl -fsSL -o /opt/abpe/scripts/export-portal-baseline.sh "$BASE/export-portal-baseline.sh"
chmod +x /opt/abpe/scripts/*.sh
```

## Verzeichnisstruktur

```
Repo_abpe/
  <modul>/
    incoming/    ← Live-Kopien vom Server
    outgoing/    ← optional: Patches vom Agent
```

## Module

| Modul | Inhalt |
|-------|--------|
| `abpe_core` | urls.py, settings.json (redigiert), lang_map.json, APPS_MANIFEST |
| `abpe_ui` | base.html, Navigation, Portal-CSS/JS, i18n-Basis |
| `email_studio` | E-Mail-Template-System |
| `abpe_crm` | CRM + Reporting-API |
| `abpe_meetme` | MeetMe-Modul |

## Workflow

1. **ucs5 → Staging:** Export-Skripte ausführen
2. **Staging → GitHub:** In udoo-reprap unter `Repo_abpe/` committen und pushen
3. **GitHub → Agent:** Cloud Agent analysiert / erstellt PR
4. **GitHub → ucs5:** Deploy aus PR/Branch zurück

**Keine Secrets** in `incoming/` ablegen. `settings.json` wird beim Baseline-Export automatisch redigiert.
