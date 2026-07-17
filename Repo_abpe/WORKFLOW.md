# ABpE — Arbeitsanweisung (Agent + ucs5)

**Immer in dieser Reihenfolge. Nie aus dem Repo blind auf Live deployen.**

```
  1. SYNC     Live (ucs5) → Repo_abpe/incoming/
  2. PATCH    Änderungen nur im Repo (incoming/)
  3. BACKUP   Live-Dateien sichern (Archiv/backup_restore.py)
  4. DEPLOY   Repo → Live (RUN-*.sh mit git show)
```

---

## 1. SYNC — Live ins Repo

**Staging** (`/mnt/public/Repo_abpe/`) und **Git-Clone** (`/mnt/public/udoo-reprap/Repo_abpe/`) sind **zwei Orte**.

```bash
cd /mnt/public/udoo-reprap
EXPORT=/opt/abpe/scripts/export-to-repo.sh
BACKEND=/opt/abpe/backend

# Einzeldateien / Modul
$EXPORT abpe_ui $BACKEND/apps/abpe_ui/templates/abpe_ui/components/header.html
# … weitere Dateien …

# Staging → Git-Clone (nicht vergessen!)
rsync -a /mnt/public/Repo_abpe/abpe_ui/incoming/ \
         Repo_abpe/abpe_ui/incoming/
rsync -a /mnt/public/Repo_abpe/abpe_crm/incoming/ \
         Repo_abpe/abpe_crm/incoming/

# Keine bogus Pfade!
rm -rf Repo_abpe/abpe_ui/incoming/modules/opt

git add Repo_abpe/
git commit -m "Live export: <was>"
git push
```

**Komplett-Export:** `/opt/abpe/scripts/export-portal-baseline.sh`

**i18n-Export:** `bash Repo_abpe/abpe_ui/incoming/RUN-export-i18n-live-ucs5.sh`  
(oder per Branch: `git show origin/<branch>:…/RUN-export-i18n-live-ucs5.sh | bash`)

---

## 2. PATCH — Nur im Repo

- Kanonisch: `Repo_abpe/<modul>/incoming/` (siehe `CANONICAL.md`)
- Agent arbeitet mit dem **exportierten Live-Stand**, nicht mit Annahmen
- Kein zweites i18n-System (`navigation.json` etc.)

---

## 3. BACKUP — Vor jedem Deploy

```bash
cd /opt/abpe/backend
NOTE="vor <kurzbeschreibung>"
python3 Archiv/backup_restore.py -save apps/abpe_ui/templates/abpe_ui/components/header.html -m "$NOTE"
python3 Archiv/backup_restore.py -save apps/abpe_ui/static/abpe_ui/js/core/core-language.js -m "$NOTE"
# … jede Datei die überschrieben wird …
```

**Restore:** `python3 Archiv/backup_restore.py -restore <relativer-pfad>`

---

## 4. DEPLOY — Repo → Live

Skripte **immer per `git show`** ausführen (funktioniert auf jedem Branch):

```bash
cd /mnt/public/udoo-reprap
git fetch origin <branch>
git show origin/<branch>:Repo_abpe/abpe_ui/incoming/RUN-<name>-ucs5.sh | bash
```

Deploy-Skripte rufen intern `backup_restore.py -save` auf, **bevor** sie überschreiben.

---

## Agent-Regeln (Cloud)

**STOP — Kein Analysieren, kein Patchen, kein Deploy-Raten, bevor Live-Sync im Repo liegt.**

1. User führt `RUN-sync-live-ucs5.sh` auf ucs5 aus und pusht
2. Agent: `git fetch` + Dateien aus `incoming/` lesen
3. Erst dann Diagnose / Patch / Deploy-Skript

| ❌ Nicht | ✅ Stattdessen |
|---------|----------------|
| Repo-Stand als Live-Wahrheit | Erst Live-Export abwarten |
| Analyse ohne `email_compose.html` / i18n im Repo | `RUN-sync-live-ucs5.sh` → push → dann lesen |
| `git checkout` auf ucs5 Live überschreiben | `git show … \| bash` oder `export-to-repo.sh` |
| Ohne Backup deployen | `Archiv/backup_restore.py -save` |
| `cp --parents` für module.json | Flach: `modules/<id>/module.json` |

**Sync-Skript (vollständig):** `RUN-sync-live-ucs5.sh` — Compose, Shell, JS, i18n de/en/ar/zh/hu

**Nach Sync im Repo:** Agent analysiert `Repo_abpe/incoming/`, patcht, pusht Branch, liefert `RUN-*-ucs5.sh` mit Backup.

---

## Pfade (ucs5)

| Was | Pfad |
|-----|------|
| Live Backend | `/opt/abpe/backend/` |
| Staging | `/mnt/public/Repo_abpe/` |
| Git | `/mnt/public/udoo-reprap/` |
| Backup-Tool | `/opt/abpe/backend/Archiv/backup_restore.py` |
| Export-Skripte | `/opt/abpe/scripts/export-to-repo.sh` |
