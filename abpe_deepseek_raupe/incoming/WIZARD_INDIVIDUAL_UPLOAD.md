# Upload für Wizard Individuell-Modus

Bitte diese Dateien von ucs5 nach `public` kopieren und hochladen:

```bash
cd /opt/abpe/backend
DEST=/mnt/public/Repo_abpe/abpe_deepseek_raupe/incoming
mkdir -p "$DEST"

# 1) Pflicht — Wizard, Notify, Chips, Versand
cp apps/abpe_crm/static/abpe_crm/js/mod-crm-pbx.js "$DEST/"

# 2) Backend — send-adhoc, notify-bulk, deepseek-suggest
cp apps/abpe_meetme/views.py "$DEST/meetme_views.py"
cp apps/abpe_meetme/email_helpers.py "$DEST/meetme_email_helpers.py" 2>/dev/null || true
cp apps/abpe_meetme/urls.py "$DEST/meetme_urls.py" 2>/dev/null || true

# 3) Optional — CSS fuer Modals/Chips (falls vorhanden)
cp apps/abpe_crm/static/abpe_crm/css/*.css "$DEST/" 2>/dev/null || true
# oder gezielt:
# find apps/abpe_crm/static -name '*.css' -exec grep -l 'pbx-meetme\|pbx-sa-chip' {} \;
```

Minimum fuer den Start: **`mod-crm-pbx.js`** (+ `meetme_views.py` wenn Versand-API angepasst werden soll).
