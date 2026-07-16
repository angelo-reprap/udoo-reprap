# ABpE Portal — Architektur-Regeln

Zielbild: **eine durchgängige UI** mit gleicher Bedienlogik, einheitlicher GUI-Struktur,
strikter Trennung von HTML / CSS / Theme / JS, **kein Hardcoding** — alle Beschriftungen in i18n.

Dieses Dokument ist die Referenz für alle weiteren Phasen (Email Studio → Telefon → Doc Studio → Matching).

---

## 1. Schichtenmodell

```
┌─────────────────────────────────────────────────────────┐
│  abpe_ui/base.html          Portal-Shell (immer)        │
│  ├── core-*.css/js          Layout, Theme, Sprache      │
│  ├── header / sidebar       Navigation                  │
│  └── {% block module_* %}   Modul-spezifisch            │
├─────────────────────────────────────────────────────────┤
│  module.json                Metadaten + Navigation      │
│  mod-<modul>.css            Nur Deltas (CSS-Variablen)  │
│  <prefix>-*.js              Modul-JS (es-, ds-, pbx-)   │
│  i18n/.../modules/<id>/     Alle sichtbaren Texte      │
├─────────────────────────────────────────────────────────┤
│  Django App                 models, api, views, urls    │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Verzeichnisse (Live-Server ucs5)

| Artefakt | Live-Pfad |
|----------|-----------|
| Portal-Shell | `apps/abpe_ui/templates/abpe_ui/base.html` |
| Modul-Templates | `apps/abpe_ui/templates/abpe_ui/modules/<id>/` |
| Modul-Config | `apps/abpe_ui/templates/abpe_ui/modules/<id>/module.json` |
| Portal-CSS | `apps/abpe_ui/static/abpe_ui/css/core/` + `css/mod/` |
| Portal-JS | `apps/abpe_ui/static/abpe_ui/js/core/` |
| i18n | `apps/abpe_ui/static/abpe_ui/i18n/<lang>/` |
| Email Studio App | `apps/abpe_email_studio/` |
| Email Studio JS | `apps/abpe_email_studio/static/email_studio/js/es-*.js` |
| Root-URLs | `abpe_backend/urls.py` |

**Repo-Spiegel:** `Repo_abpe/<modul>/incoming/` — flache Kopien vom Live-System.

---

## 3. module.json — Schema

```json
{
  "id": "email_studio",
  "title": "…",
  "titles": { "de": "…", "en": "…" },
  "icon": "envelope-at",
  "route": "/email-studio/",
  "order": 45,
  "enabled": true,
  "roles": ["!berater"],
  "static": {
    "css": ["mod/mod-email_studio.css"],
    "js": ["email_studio/js/es-core.js"]
  },
  "subpages": [ … ]
}
```

### Regeln

| Regel | Detail |
|-------|--------|
| `static.css` | Pfade relativ zu `abpe_ui/static/abpe_ui/` → Prefix `mod/` |
| `static.js` | Core-Einstieg **eine** Datei; Seiten-Skripte in Template `extra_js` (bis Phase B Loader) |
| `roles` | `!gruppe` = Ausschluss; leer = alle eingeloggt; Staff sieht immer alles |
| `route` | Muss mit `abpe_backend/urls.py` übereinstimmen |
| Kein Phantom-JS | Nur Dateien eintragen die existieren (siehe CANONICAL.md) |

### Bekannter Ist-Zustand (Phase A)

`module_scanner.py` liest `module.json` nur für **Navigation** — `static` wird noch **nicht**
automatisch in Templates geladen. Module verdrahten CSS/JS manuell in `base.html` / `{% block %}`.
Phase B: Loader in `abpe_ui/base.html` aus `module_config.static`.

---

## 4. CSS

- **Core:** `core-base.css`, `core-layout.css`, `core-theme.css` — keine Modul-Farben
- **Module:** `mod-<modul>.css` — Prefix `es-` (Email), `ds-` (Doc), `pbx-` (Telefon)
- **Nur CSS-Variablen:** `var(--abcona-blue)`, `var(--bg-white)` — **kein** `#fff`, **kein** `background:white` inline
- **Dark Mode:** `core-theme.js` + `body.dark-mode` — Theme nicht in `header.html` duplizieren

---

## 5. JavaScript

| Muster | Verwendung |
|--------|------------|
| `window.ES` + `es-*.js` | Email Studio |
| `window.PBX` + `mod-crm-pbx.js` | Telefon (CRM-Tab) |
| `core-language.js` | `loadLanguage(lang, moduleId)` |
| `data-i18n="key"` | HTML-Beschriftungen |

**Verboten:** Hardcoded UI-Texte in JS (nur i18n-Key + minimaler Dev-Fallback).
**Verboten:** Große HTML-Blöcke mit Inline-Styles in JS (Telefon — Refactoring in Phase C).

---

## 6. i18n

```
/static/abpe_ui/i18n/<lang>/core-common.json      # Header, Profil, Suche, …
/static/abpe_ui/i18n/<lang>/modules/<moduleId>/…   # Modul-UI
templates/abpe_ui/modules/<id>/module.json        # Sidebar: titles.de/en/…
```

**Neue Sprache (z.B. Ungarisch):**
```bash
mkdir apps/abpe_ui/static/abpe_ui/i18n/hu/
python3 apps/abpe_ui/bin/i18n_translator.py    # i18n/ + module.json titles.hu
python3 apps/abpe_ui/bin/i18n_validate.py --check
```

**Sidebar:** `data-titles` aus `module.json` → `titles.<lang>` (vom Translator aus `titles.de`).

- HTML: `data-i18n="es.tab_studio"`, `data-i18n-placeholder`, `data-i18n-title`
- JS: `window.i18nData?.es?.key` oder Modul-`t(key, fallback)` nur als Notfall
- **Referenzsprache:** `de` — alle JSON-Dateien zuerst auf Deutsch pflegen
- Email Studio: zusätzlich Server-Inject via `views._load_es_i18n()` (bis i18n-Baum konsolidiert)

---

## 7. Modul-Routing

| Modul | URL | App |
|-------|-----|-----|
| Portal Dashboard | `/` | `abpe_ui` |
| Email Studio | `/email-studio/` | `abpe_email_studio` |
| Doc Studio | `/doc-studio/` | `abpe_doc_studio` |
| CRM / Telefon | `/crm/`, `/crm/telefon/` | `abpe_crm` |
| MeetMe | `/meetme/` | `abpe_meetme` |
| Matching | `/matching/` | `abpe_matching_workflow` |

Email Studio hat **eigene** `urls.py` (nicht nur generisches `module_view`).

---

## 8. Abhängigkeiten (Reihenfolge der Arbeiten)

```
Phase A  Portal-Regeln + module.json + Duplikat-Klärung     ← dieses Dokument
Phase B  Email Studio stabilisieren
Phase C  Telefon/PBX aufräumen (hängt an Email-API)
Phase D  Doc Studio vereinfachen + exportieren
Phase E  Matching-Integration (Berater/Kunde/Telefon/Email/Docs)
```

**Kritische Kante:** `mod-crm-pbx.js` → `/email-studio/api/templates/` + `/signatures/`

---

## 9. Export-Workflow (ucs5 → GitHub)

```bash
/opt/abpe/scripts/export-portal-baseline.sh
# module.json flach kopieren:
for f in /opt/abpe/backend/apps/abpe_ui/templates/abpe_ui/modules/*/module.json; do
  mod=$(basename $(dirname "$f"))
  cp "$f" "/mnt/public/Repo_abpe/abpe_ui/incoming/modules/${mod}/module.json"
done
```

Siehe auch `CANONICAL.md` für gültige Datei-Pfade.
