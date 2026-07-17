# ABpE — Kanonische Dateien vs. Duplikate

**Regel:** Bei Konflikten gilt immer der Pfad unter `incoming/` des jeweiligen Moduls.
Root-Dateien und `email-studio/` sind ältere Snapshots — nicht deployen ohne Abgleich.

---

## Email Studio

| Kanonisch (deployen) | Duplikat / veraltet | Aktion |
|----------------------|---------------------|--------|
| `email_studio/incoming/*` | `email-studio/*` (Repo-Root) | Duplikat ignorieren / später löschen |
| `abpe_ui/incoming/mod-email_studio.css` | `email_studio/incoming/mod-email_studio.css` | Live: `abpe_ui/static/.../mod/` — CSS dort pflegen |
| `email_studio/incoming/es-core.js` | — | Kanonisch |
| — | `mod-email_studio.js` (fehlte) | **Ersetzt durch** `es-core.js` + Seiten-Skripte |
| `abpe_ui/incoming/core-language.js` | `email_studio/incoming/core-language.js` | **Nur Portal-Version** verwenden (195 Zeilen, neuer) |

### Email Studio JS (tatsächliche Ladereihenfolge)

| Seite | Dateien |
|-------|---------|
| Alle | `es-core.js` (via `base.html` module_js) |
| index | `es-templates.js` |
| studio | `es-studio.js` |
| log | `es-log.js` |
| config | `es-config.js` |

### i18n Email Studio

| Kanonisch (Live) | Im Export |
|------------------|-----------|
| `abpe_ui/static/.../i18n/de/modules/email_studio/email_studio.json` | `email_studio/incoming/i18n/de/email_studio.json` |
| `abpe_ui/static/.../i18n/en/modules/email_studio/email_studio.json` | `email_studio/incoming/i18n/en/email_studio.json` |
| `email_studio/static/.../i18n/help_de.json` | `email_studio/incoming/help_de.json` |

**Referenzsprache:** Deutsch (`i18n/de/`). Englische Datei separat unter `i18n/en/`.

---

## Telefon / CRM

| Kanonisch | Duplikat |
|-----------|----------|
| `abpe_crm/incoming/mod-crm-pbx.js` | `mod-crm-pbx.js`, `mod-crm-pbx_current.js`, `cursor_mod-crm-pbx.js`, `mod-crm-pbx_staticfiles.js` (Repo-Root) |
| `abpe_crm/incoming/urls.py` | — |
| `crm_telefon.json` (Root) | Sollte unter `abpe_ui/i18n/.../crm_telefon.json` |

---

## Doc Studio

| Status | Datei |
|--------|-------|
| ✅ CSS | `abpe_ui/incoming/mod-doc_studio.css` |
| ✅ CSS Editor | `abpe_ui/incoming/mod-doc_studio_editor.css` (noch nicht in module.json) |
| ✅ Config | `abpe_ui/incoming/modules/doc_studio/module.json` |
| ❌ fehlt | `mod-doc_studio.js`, alle HTML-Templates, Django-App |

---

## Portal-Shell

| Kanonisch | Anmerkung |
|-----------|-----------|
| `abpe_ui/incoming/base.html` | Shell |
| `abpe_ui/incoming/modules/<id>/module.json` | Navigation (flach, nicht `modules/opt/...`) |
| `abpe_core/incoming/urls.py` | Root-Router |
| `abpe_core/incoming/settings.json` | Nur redigiert, keine Secrets |

---

## Auf ucs5 prüfen welche Version live ist

```bash
# Email CSS — welche ist neuer?
ls -la /opt/abpe/backend/apps/abpe_ui/static/abpe_ui/css/mod/mod-email_studio.css
ls -la /opt/abpe/backend/apps/abpe_email_studio/static/ 2>/dev/null

# PBX JS
ls -la /opt/abpe/backend/apps/abpe_crm/static/abpe_crm/js/mod-crm-pbx.js

# module.json
cat /opt/abpe/backend/apps/abpe_ui/templates/abpe_ui/modules/email_studio/module.json
```
