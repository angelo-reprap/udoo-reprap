# Repo_abpe — Staging für Live-Dateien (ucs5 → GitHub)

Dieses Verzeichnis ist die **Spiegelung** von `/mnt/public/Repo_abpe/` auf ucs5.
Hier legst du geänderte Live-Dateien ab, damit der Cloud Agent sie analysieren,
ins richtige Ziel-Repo übernehmen oder als Patch zurückgeben kann.

## Verzeichnisstruktur

```
Repo_abpe/
  <modul>/
    incoming/          ← Dateien vom Live-Server (Upload / cp)
    outgoing/          ← optional: vom Agent erzeugte Patches / Exporte
```

Beispiel (Reporting):

```
Repo_abpe/abpe_reporting/incoming/mod-crm-reporting.js
```

## Typischer Ablauf

### 1. Auf ucs5 — Dateien exportieren

```bash
# Skript aus diesem Repo (nach Clone auf ucs5 oder manuell kopiert):
./scripts/export-to-repo.sh abpe_reporting \
  /opt/abpe/backend/apps/abpe_crm/static/abpe_crm/js/mod-crm-reporting.js
```

Oder mit Backend-Relativpfad:

```bash
./scripts/export-to-repo.sh abpe_crm --from-backend \
  abpe_crm/static/abpe_crm/js/mod-crm-reporting.js
```

Ziel auf ucs5: `/mnt/public/Repo_abpe/<modul>/incoming/`

### 2. Ins Git-Repo (udoo-reprap) bringen

- **Windows:** Freigabe `\\ucs5\...` → Dateien in lokales Clone unter `Repo_abpe/<modul>/incoming/` legen
- **ucs5:** Wenn dort ein Git-Clone liegt: kopieren und `git add` / `git commit` / `git push`
- **Cloud Agent:** New Agent starten und schreiben z. B.:

  > Bitte `Repo_abpe/abpe_reporting/incoming/mod-crm-reporting.js` analysieren und …

### 3. Deploy zurück auf ucs5 (aus GitHub)

Wie bisher per `curl` raw von GitHub oder aus dem PR — Richtung **GitHub → ucs5**.

## Modul-Namen (Vorschlag)

| Modul            | Typischer Live-Pfad unter `/opt/abpe/backend/apps/` |
|------------------|-----------------------------------------------------|
| `abpe_reporting` | Reporting-JS, KPI, CRM-Reporting                    |
| `abpe_crm`       | CRM-App, Templates, Static                          |
| `abpe_core`      | Gemeinsame Backend-Teile                              |

Neues Modul: einfach `Repo_abpe/<neues-modul>/incoming/` anlegen (Ordner reicht).

## Wichtig

| Richtung | Zweck |
|----------|--------|
| ucs5 → `/mnt/public/Repo_abpe/` → **dieses Repo** | Live-Stand sichern, versionieren, PR |
| **dieses Repo** → ucs5 | Deploy aus Repo zurück auf den Server |

`incoming/` enthält **Kopien vom Live-System** — keine Secrets (.env, Keys) ablegen.
