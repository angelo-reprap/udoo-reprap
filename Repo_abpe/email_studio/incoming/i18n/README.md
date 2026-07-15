# Email Studio i18n — Deploy-Pfade (ucs5)

| Sprache | Live-Pfad |
|---------|-----------|
| Deutsch (Referenz) | `apps/abpe_ui/static/abpe_ui/i18n/de/modules/email_studio/email_studio.json` |
| Englisch | `apps/abpe_ui/static/abpe_ui/i18n/en/modules/email_studio/email_studio.json` |
| Hilfe DE/EN | `apps/abpe_email_studio/static/email_studio/i18n/help_de.json` (+ `help_en.json`) |

Kopieren aus diesem Export:

```bash
cp incoming/i18n/de/email_studio.json \
  /opt/abpe/backend/apps/abpe_ui/static/abpe_ui/i18n/de/modules/email_studio/email_studio.json
cp incoming/i18n/en/email_studio.json \
  /opt/abpe/backend/apps/abpe_ui/static/abpe_ui/i18n/en/modules/email_studio/email_studio.json
```

Root-Datei `incoming/email_studio.json` = Spiegel von `i18n/de/` (Referenzsprache).
