# Was gehört zum Shaduler-Patch — und was nicht

## Im Patch / Repo (Modul)

| Stück | Status |
|-------|--------|
| Django-App `apps/abpe_shaduler` | ✅ Skelett |
| Templates `shaduler/index.html` + tabs | ✅ |
| `module.json` Sidebar | ✅ |
| `mod-shaduler.css` (nutzt Theme-Variablen) | ✅ |
| `mod-shaduler.js` + Kalender-JS | ✅ Stub |
| i18n DE/EN `shaduler.json` | ✅ |
| `scheduler_client` + Webhooks | ✅ |
| Migration 0001 | ❌ noch nicht |
| i18n Restsprachen (15) | ❌ später DeepSeek |

## Portal-Core (bereits auf Live — **nicht** im Shaduler-Patch)

| Stück | Rolle |
|-------|--------|
| `core-theme.css` / `core-theme.js` | Dark/Light, CSS-Variablen |
| `core-language.js` / `loadLanguage` | i18n-Loader |
| `themes.py` (falls vorhanden) | Theme-Serverlogik Portal |
| `abpe_ui/base.html` | Shell, Sidebar, ModuleScanner |

Shaduler **hängt sich ein** (extends base, `data-i18n`, `--abcona-*` / `--text-*`).
Wir ersetzen Core nicht.

## Vor Restart zwingend

1. Dateien rsync (sonst `ModuleNotFoundError: apps.abpe_shaduler`)
2. `shaduler/`-URL **vor** `path('', abpe_ui)`
3. `CHECK-abpe-shaduler-live.sh`
4. `supervisorctl restart abpe-django`
