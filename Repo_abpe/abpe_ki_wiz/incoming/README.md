# abpe_ki_wiz — KI-Wizard Engine (Phase 0)

Zentrale Django-App für wiederverwendbare KI-Assistenten (Email Studio, Matching, Doc Studio, …).

## API-Dokumentation (OpenAPI / Swagger)

| URL | Beschreibung |
|-----|--------------|
| `/ki-wizard/api/schema/` | OpenAPI 3.0 JSON (öffentlich) |
| `/ki-wizard/api/docs/` | Swagger UI (Browser) |

Kein DRF / drf-spectacular — handgeschriebenes Schema in `openapi_schema.py`. Bei späterer DRF-Migration kann drf-spectacular dieses Schema ersetzen.

## Phase 1 — Session-API (neu)

| Methode | URL | Body |
|---------|-----|------|
| POST | `/ki-wizard/api/wizards/email_template/session/` | `{"briefing":"…"}` |
| POST | `/ki-wizard/api/session/<uuid>/analyze/` | — |
| POST | `/ki-wizard/api/session/<uuid>/clarify/` | `{"answers":{"S1":"telefon",…}}` |
| POST | `/ki-wizard/api/session/<uuid>/suggest-meta/` | — |
| POST | `/ki-wizard/api/session/<uuid>/generate/` | — (DeepSeek, Fallback: rules) |
| POST | `/ki-wizard/api/session/<uuid>/apply/` | — |

**Test (eingeloggt als Admin im Browser oder curl mit Session-Cookie):**

```bash
# Health — phase: 1, public_wizards: 1
curl -s http://127.0.0.1:8000/ki-wizard/api/health/ | python -m json.tool
```

Phase 2: UI-Modal in `abpe_ui` + Paste ins Email Studio.

## Phase 0 — Inhalt

- `WizardPrompt` — Prompts im Admin editierbar
- `WizardSession` — Session-Model (Phase 1+)
- Provider-Registry (Stub)
- API: Health + Wizard-Liste
- `sync_wizard_prompts` Management-Command

## Deploy ucs5

### 1. App kopieren

**Variante A — lokales Repo (wenn Branch ausgecheckt):**

```bash
REPO=/mnt/public/udoo-reprap
BE=/opt/abpe/backend
git -C "$REPO" fetch origin cursor/abpe-ki-wiz-phase0-bf44
git -C "$REPO" checkout cursor/abpe-ki-wiz-phase0-bf44
test -f "$REPO/Repo_abpe/abpe_ki_wiz/incoming/urls.py" || { echo "FEHLER: Branch/Dateien fehlen"; exit 1; }
mkdir -p "$BE/apps/abpe_ki_wiz"
rsync -av --exclude __pycache__ "$REPO/Repo_abpe/abpe_ki_wiz/incoming/" "$BE/apps/abpe_ki_wiz/"
```

**Variante B — frischer Clone (wenn `git pull` divergent scheitert):**

```bash
BE=/opt/abpe/backend
TMP=/tmp/udoo-ki-wiz-deploy
rm -rf "$TMP"
git clone --depth 1 --branch cursor/abpe-ki-wiz-phase0-bf44 \
  https://github.com/angelo-reprap/udoo-reprap.git "$TMP"
mkdir -p "$BE/apps/abpe_ki_wiz"
rsync -av --exclude __pycache__ \
  "$TMP/Repo_abpe/abpe_ki_wiz/incoming/" "$BE/apps/abpe_ki_wiz/"
rm -rf "$TMP"
test -f "$BE/apps/abpe_ki_wiz/urls.py" && echo "OK: urls.py vorhanden"
```

### 2. settings (manuell)

`abpe_backend/settings/apps.py` in `ABPE_APPS +=`:

```python
'apps.abpe_ki_wiz',
```

### 3. urls (manuell)

`abpe_backend/urls.py`:

```python
path('ki-wizard/', include('apps.abpe_ki_wiz.urls', namespace='ki_wizard')),
```

### 4. Migration + Prompts

```bash
cd /opt/abpe/backend
source /opt/abpe/venv311/bin/activate
python manage.py makemigrations abpe_ki_wiz   # falls incoming ohne Migration
python manage.py migrate abpe_ki_wiz
python manage.py sync_wizard_prompts
supervisorctl restart abpe-django
```

### 5. Prüfen

```bash
curl -s http://127.0.0.1:8000/ki-wizard/api/health/
curl -s http://127.0.0.1:8000/ki-wizard/api/schema/ | python -m json.tool | head
# Browser: http://127.0.0.1:8000/ki-wizard/api/docs/
curl -s http://127.0.0.1:8000/ki-wizard/api/wizards/
```

Admin: `/admin/abpe_ki_wiz/wizardprompt/`

## Troubleshooting

| Symptom | Ursache | Fix |
|---------|---------|-----|
| `No module named 'apps.abpe_ki_wiz.urls'` | Dateien nicht kopiert | Variante B, dann `ls apps/abpe_ki_wiz/urls.py` |
| `rsync: incoming failed: No such file` | Branch nicht ausgecheckt | Variante B (frischer Clone) |
| `Unknown command: sync_wizard_prompts` | App-Code fehlt | Dateien kopieren |
| `curl health` leer | Django kaputt (URL-Import) | `python manage.py check` nach Datei-Kopie |
| `502 generate` / `no attribute summarize` | CRM `deepseek_pbx` Instanz fehlt | Update auf neuesten Branch — nutzt `deepseek_pbx.summarize` + HTTP-Fallback |
| `complete=False` bei CLARIFY | Optionale Frage M1 offen | M1 ist optional; alle Pflichtfragen (S1,S2,I1,G1,A1) beantworten |
| KI-Verfeinern ändert nichts | Generate-Prompt ohne `[[INSTRUCTION]]` / kein Editor-HTML | Branch aktualisieren; `python manage.py sync_wizard_prompts --force --key wiz_email_generate` |

**Reihenfolge:** Dateien kopieren → settings/urls → migrate → sync_wizard_prompts → restart
