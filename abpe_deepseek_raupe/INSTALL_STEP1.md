# Schritt 1 — AiPrompt + DeepSeek-Raupe Kern (ucs5)

## Backup

```bash
cd /opt/abpe/backend
python apps/abpe_ui/backup_restore.py -save \
  apps/abpe_email_studio/models.py \
  -m "vor AiPrompt Schritt 1"
cp -a apps/abpe_crm/services/deepseek_api_pbx.py{,.bak-ai-prompt}
cp -a apps/abpe_meetme/views.py{,.bak-ai-prompt}
```

## Paket kopieren

Gesamten Ordner `abpe_deepseek_raupe/` nach `/opt/abpe/backend/abpe_deepseek_raupe/` kopieren
(z.B. von `/mnt/public/Repo_abpe/`).

## Installieren

```bash
cd /opt/abpe/backend
python abpe_deepseek_raupe/apply_step1_ucs5.py
```

Das Skript:

- legt `AiPrompt` Model + Admin an
- kopiert `deepseek_raupe.py` + `sync_ai_prompts`
- patcht `deepseek_api_pbx._get_prompt` → DB + Fallback
- patcht `api_deepseek_suggest` (MeetMe) mit Pipeline
- führt `makemigrations`, `migrate`, `sync_ai_prompts` aus

## Admin prüfen

Django Admin → **KI-Prompts** → Einträge z.B. `meetme_email`, `matching_candidate`

Prompts dort editierbar — **kein Code-Deploy** nötig.

## API (neu)

```http
POST /meetme/api/deepseek-suggest/
{
  "text": "Guten Tag …",
  "prompt_key": "meetme_email",
  "variables": { "name": "…", "title": "…", "sender_name": "…" },
  "subject": "Terminänderung: …",
  "format": "text"
}
```

Response:

```json
{
  "suggestion": "… gerendert …",
  "suggestion_raw": "… DeepSeek roh …"
}
```

## Nächster Schritt (2) — Hotfix auf ucs5

Wenn `manage.py shell` mit `AttributeError: 'tuple' object has no attribute 'success'` scheitert,
fehlt Schritt 2 (alter `suggest()` rief `_chat()` direkt auf):

```bash
cd /opt/abpe/backend
python apps/abpe_ui/backup_restore.py -save apps/abpe_crm/services/deepseek_api_pbx.py -m "vor step2"
python apps/abpe_ui/backup_restore.py -save apps/abpe_email_studio/services/deepseek_raupe.py -m "vor step2"
python abpe_deepseek_raupe/apply_step2_hotfix_ucs5.py
python manage.py collectstatic --noinput
supervisorctl restart abpe-django
```

Test:

```bash
python manage.py shell -c "
from apps.abpe_email_studio.services.deepseek_raupe import deepseek_raupe
r = deepseek_raupe.full_pipeline('Test', {'name':'Max'}, prompt_key='meetme_email')
print(r)
"
```

JS: `variables` aus MeetMe-Kontext, Button **„Vorschlag übernehmen“** (Compose + Notify + Reminder).

## Phase 2 (später)

Email Studio Reiter **KI-Prompts** — gleiche `AiPrompt`-Tabelle, keine zweite Quelle.
