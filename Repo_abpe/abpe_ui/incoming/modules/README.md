# module.json — Navigation-Config

Flache Spiegelung der Live-Dateien:

```
Live:  apps/abpe_ui/templates/abpe_ui/modules/<id>/module.json
Repo:  Repo_abpe/abpe_ui/incoming/modules/<id>/module.json
```

Export auf ucs5:

```bash
for f in /opt/abpe/backend/apps/abpe_ui/templates/abpe_ui/modules/*/module.json; do
  mod=$(basename $(dirname "$f"))
  mkdir -p "/mnt/public/Repo_abpe/abpe_ui/incoming/modules/${mod}"
  cp "$f" "/mnt/public/Repo_abpe/abpe_ui/incoming/modules/${mod}/module.json"
done
```

**Nicht** mit `cp --parents` — erzeugt verschachtelte `opt/abpe/backend/...` Pfade.

Siehe `Repo_abpe/ARCHITECTURE.md` und `Repo_abpe/CANONICAL.md`.
