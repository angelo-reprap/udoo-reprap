# Incoming — Dateien von ucs5 zum Patchen

Lege hier Dateien ab, die vom Server kopiert wurden, z.B.:

- `mod-crm-pbx.js` — aus `apps/abpe_crm/static/abpe_crm/js/mod-crm-pbx.js`

Auf ucs5:

```bash
cp /opt/abpe/backend/apps/abpe_crm/static/abpe_crm/js/mod-crm-pbx.js \
   /mnt/public/Repo_abpe/abpe_deepseek_raupe/incoming/mod-crm-pbx.js
```

Dann Repo syncen / upload — Agent patcht und liefert die geänderte Datei zurück.
