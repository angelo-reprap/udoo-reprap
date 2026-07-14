# Incoming — Dateien von ucs5 zum Patchen

## mod-crm-pbx.js (DeepSeek-Raupe Schritt 2 JS)

**Gepatchte Datei:** `mod-crm-pbx.js` (bereit zum Deploy)

Auf ucs5 einspielen:

```bash
cd /opt/abpe/backend
python apps/abpe_ui/backup_restore.py -save apps/abpe_crm/static/abpe_crm/js/mod-crm-pbx.js -m "vor raupe JS step2"
cp /mnt/public/Repo_abpe/abpe_deepseek_raupe/incoming/mod-crm-pbx.js \
   apps/abpe_crm/static/abpe_crm/js/mod-crm-pbx.js
python manage.py collectstatic --noinput
supervisorctl restart abpe-django   # optional, fuer Static-Cache
```

Prüfen:

```bash
grep -n '_mmRaupeRequest' apps/abpe_crm/static/abpe_crm/js/mod-crm-pbx.js
grep -n 'pbx_sa_apply' apps/abpe_crm/static/abpe_crm/js/mod-crm-pbx.js
```
