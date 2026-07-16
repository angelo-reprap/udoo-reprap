# i18n — Portal vs CRM

## Portal (`abpe_ui`)

| Was | Wo |
|-----|-----|
| Header, Modals | `static/abpe_ui/i18n/<lang>/core-common.json` |
| Sidebar-Nav | `templates/abpe_ui/modules/*/module.json` → `titles.<lang>` |
| Modul-UI | `static/abpe_ui/i18n/<lang>/modules/…` |

```bash
cd /opt/abpe/backend
python3 apps/abpe_ui/bin/i18n_translator.py      # i18n/ + module.json titles
python3 apps/abpe_ui/bin/i18n_validate.py        # Prüfen (ohne --check)
```

Neue Sprache:
```bash
mkdir -p apps/abpe_ui/static/abpe_ui/i18n/hu
python3 apps/abpe_ui/bin/i18n_translator.py --lang hu
```

## CRM (`abpe_crm`)

| Was | Wo |
|-----|-----|
| CRM-Tabs, Telefon, PBX | `static/abpe_crm/i18n/<lang>/` (crm.json, modules/crm_*) |
| CRM-Sidebar | `templates/abpe_crm/modules/*/module.json` → `titles.<lang>` |
| CRM-Basis-Nav | `apps/abpe_crm/modules.json` → `titles.<lang>` (tabs/modules/navigation) |

```bash
python3 apps/abpe_crm/bin/i18n_translator.py      # i18n/ + module.json + modules.json titles
python3 apps/abpe_crm/bin/i18n_validate.py        # Prüfen + --fix
```

Neue Sprache:
```bash
mkdir -p apps/abpe_crm/static/abpe_crm/i18n/hu
python3 apps/abpe_crm/bin/i18n_translator.py --lang hu
```

## Verwechslungsgefahr

- Portal-Translator: `apps/abpe_ui/bin/i18n_translator.py`
- CRM-Translator: `apps/abpe_crm/bin/i18n_translator.py` (eigenes `abpe_crm/i18n/` + CRM `module.json`/`modules.json`)
