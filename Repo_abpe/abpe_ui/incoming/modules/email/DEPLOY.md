# Navigation Email-Gruppe — Deploy (ucs5)

**Regel: Erst `backup_restore.py -save`, dann deployen.**

Aus `/opt/abpe/backend/` ausführen.

## 1. Backup (Pflicht)

```bash
cd /opt/abpe/backend
B="Nav Email-Gruppe $(date +%Y-%m-%d)"

python3 Archiv/backup_restore.py -save apps/abpe_ui/core/module_scanner.py -m "$B"
python3 Archiv/backup_restore.py -save apps/abpe_ui/templates/abpe_ui/components/_nav_link.html -m "$B"
python3 Archiv/backup_restore.py -save apps/abpe_ui/templates/abpe_ui/components/sidebar.html -m "$B"
python3 Archiv/backup_restore.py -save apps/abpe_ui/templates/abpe_ui/modules/email_studio/module.json -m "$B"
python3 Archiv/backup_restore.py -save apps/abpe_email_studio/views.py -m "$B"
python3 Archiv/backup_restore.py -save apps/abpe_crm/views.py -m "$B"
```

## 2. Deploy aus Repo

```bash
cd /mnt/public/udoo-reprap
git fetch origin cursor/nav-email-group-bf44
BR=origin/cursor/nav-email-group-bf44
R=Repo_abpe

# module.json
mkdir -p /opt/abpe/backend/apps/abpe_ui/templates/abpe_ui/modules/email
git show $BR:$R/abpe_ui/incoming/modules/email/module.json \
  > /opt/abpe/backend/apps/abpe_ui/templates/abpe_ui/modules/email/module.json
git show $BR:$R/abpe_ui/incoming/modules/email_studio/module.json \
  > /opt/abpe/backend/apps/abpe_ui/templates/abpe_ui/modules/email_studio/module.json

# Scanner + Templates
git show $BR:$R/abpe_ui/incoming/module_scanner.py \
  > /opt/abpe/backend/apps/abpe_ui/core/module_scanner.py
git show $BR:$R/abpe_ui/incoming/_nav_link.html \
  > /opt/abpe/backend/apps/abpe_ui/templates/abpe_ui/components/_nav_link.html
git show $BR:$R/abpe_ui/incoming/sidebar.html \
  > /opt/abpe/backend/apps/abpe_ui/templates/abpe_ui/components/sidebar.html

# Views (active=email)
# ⚠ NICHT die ganze views.py kopieren — Live-Code weicht vom Repo ab!
# Nur _base_context patchen (siehe HOTFIX-rollback.sh oder unten):
#
#   sed -i "s/'active_module': 'email_studio',/'active_module': 'email',\n        'active':        'email',\n        'active_subpage': 'studio',/" \
#     /opt/abpe/backend/apps/abpe_email_studio/views.py
#
# CRM compose — zwei Zeilen in ctx.update nach signatures_list:
#   'active': 'email',  'active_subpage': 'compose',
#
# Bei 500 nach Deploy: bash Repo_abpe/abpe_ui/incoming/modules/email/HOTFIX-rollback.sh

supervisorctl restart abpe-django
```

## 3. Prüfen

- Sidebar: **Email** mit Untermenü **Email-Erstellen** + **Email Studio**
- `/crm/email/compose/` → Compose aktiv
- `/email-studio/` → Studio aktiv
- Kein separater Top-Level-Eintrag „Email Studio“

## 4. Rollback

```bash
cd /opt/abpe/backend
python3 Archiv/backup_restore.py -restore apps/abpe_ui/core/module_scanner.py
python3 Archiv/backup_restore.py -restore apps/abpe_ui/templates/abpe_ui/components/_nav_link.html
python3 Archiv/backup_restore.py -restore apps/abpe_ui/templates/abpe_ui/components/sidebar.html
python3 Archiv/backup_restore.py -restore apps/abpe_ui/templates/abpe_ui/modules/email_studio/module.json
python3 Archiv/backup_restore.py -restore apps/abpe_email_studio/views.py
python3 Archiv/backup_restore.py -restore apps/abpe_crm/views.py
rm -f apps/abpe_ui/templates/abpe_ui/modules/email/module.json
rmdir apps/abpe_ui/templates/abpe_ui/modules/email 2>/dev/null
supervisorctl restart abpe-django
```

## Struktur

```
📧 Email
   ├─ Email-Erstellen  → /crm/email/compose/
   └─ Email Studio     → /email-studio/
```

`email_studio/module.json` hat `nav_hidden: true` — erscheint nicht mehr als eigener Top-Level-Punkt.
