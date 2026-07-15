# Portal i18n — Deploy (ucs5)

Quelldateien: `Repo_abpe/abpe_ui/incoming/i18n/<lang>/`

Ziel (Live): `/opt/abpe/backend/apps/abpe_ui/static/abpe_ui/i18n/<lang>/`

## help-modal.json

Portal-weite Hilfe (`?` Button oben rechts). Wird von `core-language.js` geladen.

```bash
cd /mnt/public/udoo-reprap
R=Repo_abpe/abpe_ui/incoming
I18N=/opt/abpe/backend/apps/abpe_ui/static/abpe_ui/i18n
TPL=/opt/abpe/backend/apps/abpe_ui/templates/abpe_ui/components

for L in de en es it fr; do
  mkdir -p $I18N/$L
  cp $R/i18n/$L/help-modal.json $I18N/$L/
done
cp $R/help_modal.html $TPL/
supervisorctl restart abpe-django
```

## Schlüssel (help-modal.json)

| Key | Inhalt |
|-----|--------|
| `help_title` | Modal-Titel |
| `help_portal` / `help_portal_text` | Portal-Beschreibung |
| `help_nav1`–`help_nav4` | Navigation |
| `help_lang_*` / `help_theme_toggle` | Sprache & Theme |
| `help_mod_*` | Modul-Hilfe (Email Studio etc.) |
| `help_shortcut_*` | Tastaturkürzel |

Referenzsprache: **de**
