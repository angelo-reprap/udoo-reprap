# CRM Dark Mode — Plan (nur CRM, Phase 0)

## Iststand holen (ucs5)

```bash
cd /mnt/public/udoo-reprap
git fetch origin cursor/crm-dark-mode-bf44
git checkout cursor/crm-dark-mode-bf44
bash Repo_abpe/abpe_crm/incoming/RUN-rsync-crm-theme-ucs5.sh
# optional: AUTO_COMMIT=1 bash ... 
```

**Wichtig:** Bisher fehlten **alle CRM-CSS-Dateien** im Git (nur JS/Templates).
Das Rsync-Script holt jetzt:
- `static/abpe_crm/css/*` → `incoming/css/`
- `mod-edms.css`, `mod-crm-pbx.css`, `softphone/css/`
- JS + Templates (für inline `#fff` / `background:white`)
- `THEME-AUDIT.txt` — automatische Inventur hardcodierter Farben

---

## Architektur (bestätigt)

| Schicht | Datei | Rolle |
|---------|-------|-------|
| Tokens | `core-theme.css` | `:root` + `body.dark-mode` CSS-Variablen |
| Toggle | `core-theme.js` | `ThemeManager`, localStorage, System |
| Shell | `core-layout.css`, `ui-components.css` | Layout, Karten, Modals |
| CRM | `mod-crm.css`, `mod-crm-dokumente.css`, `mod-edms.css`, `mod-crm-pbx.css` | Module |

**Ja — richtig:** Hardcodierte Farben in CSS/JS/HTML → `var(--…)` tauschen,
`core-theme.css` für Dark erweitern. **Hell-Mode Farben bleiben gleich**
(nur ggf. Variablennamen vereinheitlichen).

---

## Lesbarkeit Dark Mode (Design-Regeln)

Ziel: **gut lesbar**, nicht „dunkelblau auf schwarz“.

| Element | Light (unverändert) | Dark (Vorschlag) |
|---------|---------------------|------------------|
| Seiten-Hintergrund | `#eef2f5` | `#121212` (warm-neutral, nicht rein schwarz) |
| Karten/Panels | `#ffffff` / `#f8fafc` | `#1e1e1e` — `#252525` |
| Primärtext | `#1e1e1e` | `#e8e8e8` (Kontrast ≥ 7:1 auf Karten) |
| Sekundärtext | `#6c757d` | `#a3a3a3` |
| Header/Sidebar | `#163258` (Blau) | `#2d2d2d` + **Akzent-Streifen** `#4a7ab8` (Lesbarkeit, nicht graues Blau→Schwarz) |
| Links/Aktionen | `#163258` | `#6eb5ff` (hell genug auf dunklem Grund) |
| Borders | `#dee2e6` | `#3a3a3a` |
| Inputs/Selects | weiß | `#2a2a2a` bg, `#e0e0e0` text |

**Kontrast-Check:** WCAG AA minimum 4.5:1 für Fließtext, 3:1 für große UI-Labels.
Kein `#163258` Text auf `#1a1a1a` — zu wenig Kontrast.

---

## Phasen (CRM only)

### Phase 0 — Iststand ✅ (dieses Script)
Rsync Live → Repo + THEME-AUDIT.txt

### Phase 1 — Plumbing
- `ThemeManager` ↔ CRM `CrmUserSettings.theme` verbinden
- Settings-Modal + Header-Toggle vereinheitlichen
- FOUC-Blocker in `base.html` `<head>`

### Phase 2 — core-theme.css erweitern
- Fehlende Tokens: `--surface-elevated`, `--overlay-bg`, `--input-bg`, `--link-color`
- Dark-Palette nach Lesbarkeits-Regeln oben
- `data-bs-theme="dark"` optional auf `<html>`

### Phase 3 — CSS/JS/HTML bereinigen
- Audit-Liste abarbeiten: `#fff` → `var(--bg-white)` etc.
- Duplikate: flache Kopien vs `js/`/`css/` konsolidieren
- Ungenutzte CSS-Regeln entfernen (nach grep + Browser-Check)

### Phase 4 — Module
Priorität: `header.html` Modals → `mod-crm.css` → EDMS → PBX/Telefon

---

## Dateien laut base.html (Live erwartet)

```
css/core-base.css
css/core-layout.css
css/core-theme.css      ← zentral erweitern
css/core-responsive.css
css/ui-components.css
css/core-gsearch.css
css/mod-crm.css
css/mod-crm-dokumente.css
css/mod-edms.css        (EDMS)
css/mod-crm-pbx.css     (Telefon)
softphone/css/softphone.css
```

Hell-Mode wird **nicht** optisch verändert — nur Token-Namen vereinheitlichen falls nötig.
