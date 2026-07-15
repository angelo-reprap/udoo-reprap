# Email Studio i18n — Deploy-Pfade (ucs5)

| Sprache | Live-Pfad |
|---------|-----------|
| Deutsch (Referenz) | `apps/abpe_ui/static/abpe_ui/i18n/de/modules/email_studio/email_studio.json` |
| Englisch | `apps/abpe_ui/static/abpe_ui/i18n/en/modules/email_studio/email_studio.json` |
| Spanisch | `apps/abpe_ui/static/abpe_ui/i18n/es/modules/email_studio/email_studio.json` |
| Italienisch | `apps/abpe_ui/static/abpe_ui/i18n/it/modules/email_studio/email_studio.json` |
| Französisch | `apps/abpe_ui/static/abpe_ui/i18n/fr/modules/email_studio/email_studio.json` |
| Hilfe DE/EN/ES/IT/FR | `apps/abpe_email_studio/static/email_studio/i18n/help_{lang}.json` |

Jede Sprache benötigt `manifest.json` in `.../modules/email_studio/` (für `core-language.js`).

Kopieren aus diesem Export:

```bash
R=Repo_abpe/email_studio/incoming
I18N=/opt/abpe/backend/apps/abpe_ui/static/abpe_ui/i18n
HLP=/opt/abpe/backend/apps/abpe_email_studio/static/email_studio/i18n

for L in de en es it fr; do
  mkdir -p $I18N/$L/modules/email_studio
  cp $R/i18n/$L/email_studio.json $I18N/$L/modules/email_studio/
  cp $R/i18n/$L/modules/email_studio/manifest.json $I18N/$L/modules/email_studio/
  cp $R/help_$L.json $HLP/
done
```

Root-Datei `incoming/email_studio.json` = Spiegel von `i18n/de/` (Referenzsprache).
