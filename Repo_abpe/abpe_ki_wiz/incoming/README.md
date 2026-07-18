# abpe_ki_wiz — KI-Wizard Engine (Phase 0)

Zentrale Django-App für wiederverwendbare KI-Assistenten (Email Studio, Matching, Doc Studio, …).

## Phase 0 — Inhalt

- `WizardPrompt` — Prompts im Admin editierbar
- `WizardSession` — Session-Model (Phase 1+)
- Provider-Registry (Stub)
- API: Health + Wizard-Liste
- `sync_wizard_prompts` Management-Command

## Deploy ucs5

### 1. App kopieren

```bash
REPO=/mnt/public/udoo-reprap
BE=/opt/abpe/backend
mkdir -p "$BE/apps/abpe_ki_wiz"
rsync -av --exclude __pycache__ "$REPO/Repo_abpe/abpe_ki_wiz/incoming/" "$BE/apps/abpe_ki_wiz/"
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
curl -s http://127.0.0.1:8000/ki-wizard/api/wizards/
```

Admin: `/admin/abpe_ki_wiz/wizardprompt/`
