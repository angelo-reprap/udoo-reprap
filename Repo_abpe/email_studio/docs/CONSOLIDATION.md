# Email Studio — Konsolidierung Module / Blöcke / Variablen

Stand: **2026-07-18** · Snapshot: `Repo_abpe/email_studio/data/email_studio_snapshot_2026-07-18.json`  
Branch-Arbeit: `cursor/email-studio-consolidate-modules-7f07`  
Live-DB: **keine Änderungen ohne Review**

## Ziel-CI (abcona Corporate Layout)

**Verbindlich:** siehe [`EMAIL_LAYOUT_DECLARATION.md`](./EMAIL_LAYOUT_DECLARATION.md) (Abstimmung 2026-07-18).

| Regel | Soll |
|---|---|
| Struktur | `{{block:abcona_header_blau}}` → optional `label_*` → Body → **Signatur XOR Footer** |
| Header | immer nur blau (`abcona_header_blau`) |
| Event | `label_info` (blau) / `label_bestaetigt` (grün) / `label_warnung` (rot) |
| Abschluss | Signatur **oder** Footer (nicht beides) — DE-Impressum |
| Breite | 600px Tabellen-Layout, Outlook-tauglich, inline CSS |
| Typografie Body | Arial 14px, Farbe `#333333`, `text-align:left` |
| TXT | 1:1 aus HTML-Text ableiten |

Quellen: Deklaration, `abpe_ki_wiz/.../layout_rules`, `variables_registry.py`, `help_de.json`.

---

## Phase 1 — Ist-Stand (erledigt auf ucs5)

1. `RUN-sync-from-ucs5.sh` → Code nach `Repo_abpe/email_studio/incoming/`
2. `dumpdata` → `Repo_abpe/email_studio/data/email_studio_snapshot_2026-07-18.json`
3. Commit `ccbe0b1` auf `cursor/email-studio-ki-wizard-phase2-bf44`

Wiederholbar:

```bash
cd /mnt/public/udoo-reprap && git pull
bash Repo_abpe/email_studio/incoming/RUN-phase1-iststand.sh --commit --push
# oder nur DB:
bash Repo_abpe/email_studio/incoming/export-email-studio-data.sh
```

Offline-Audit:

```bash
python3 Repo_abpe/email_studio/incoming/audit_email_studio_snapshot.py
```

---

## Bestandsaufnahme Snapshot

| Modell | Anzahl |
|---|---|
| EmailModule | 24 |
| EmailTemplate | 17 (15 ACTIVE, 2 DRAFT) |
| EmailSignature | 5 |
| EmailSenderAccount | 5 |

### Module nach Typ

| Typ | Identifier |
|---|---|
| HEADER | `abcona_header_blau`, `_gruen`, `_rot` |
| FOOTER | `footer_standard`, `footer_auto_reply` |
| BUTTON | `cta_blau`, `cta_gruen`, `cta_with_secondary` |
| SECTION | `support_kontakt`, Labels, Fakten, Kalender, Progress, … (16) |

Unbekannte `{{block:…}}` in Vorlagen: **keine**.

---

## Formatierungs-Analyse

### Header-Module (Inkonsistent)

| Modul | Align | Font-Size | Padding | Farbe |
|---|---|---|---|---|
| `abcona_header_blau` | **left** ✓ | **19px** | 22px 28px | `#163258` |
| `abcona_header_gruen` | **center** ✗ | 18px | 16px 24px | `#28a745` |
| `abcona_header_rot` | **center** ✗ | 18px | 16px 24px | `#dc3545` |

Soll laut CI: alle Header **linksbündig**, einheitliche Schriftgröße/Padding.

### Footer-Module (weichen von Body-CI ab)

| Modul | Align | Size | Color |
|---|---|---|---|
| `footer_standard` | center | 11px | `#6c757d` |
| `footer_auto_reply` | center | 11px | `#6c757d` |

CI-Prompt sagt Body=Footer Arial 14px `#333333` links.  
Entscheidung nötig: Footer bewusst kleiner/grau zentriert (Marken-Impressum) **oder** CI wörtlich (14px/`#333`/left). Empfehlung: **Impressum-Stil beibehalten**, aber in `layout_rules` klar dokumentieren (`footer_style: imprint`).

### Signaturen

Alle 5 Signaturen: Arial 11–12px, Farben `#163258` / `#333` / `#6c757d`, kein `text-align` (Default left). Relativ einheitlich.

### Vorlagen — Struktur

| Gruppe | Header-Modul | Footer / Signatur | Anmerkung |
|---|---|---|---|
| CRM (`crm_*`) | `abcona_header_blau` | `{{block:signature}}` + `signature_mode=USER` | gut |
| Intake Pipeline / Upload | Header + Labels | `footer_*` | gut; Body oft 12px statt 14px |
| MeetMe (`meetme_*`) | `abcona_header_blau` | **kein** Footer-Block | verlassen sich auf USER-Signatur beim Versand |
| `cv_generated_berater_copy` (DRAFT) | **Inline-HTML** Header/Footer | — | Skeleton-Kopie, nicht modulbasiert |
| `test` (DRAFT) | fehlt | nur signature | Entwurf |

---

## Variablen — Lücken

### In Vorlagen genutzt, fehlend in `variables_registry` (intake/general)

`aid`, `email_id`, `error_code`, `error_detail`, `import_time`, `original_subject`, `solution`, `attachment_count`, `de_editor_url`, `de_html_url`, `en_html_url`, `duration`, `projects`, `skills`, `berater_anzahl`, `body`

### `button_text` / `button_url`

Nur unter Scope `portal` in der Registry — CTA-Module brauchen sie global.

### `VariableListAPI` vs Registry

`api.py` → `VariableListAPI` hat eine **feste, unvollständige Liste** (nur Basis-Kontext/User/System).  
Sidebar nutzt bereits `variables_registry.get_sidebar_variable_groups`.  
→ API muss Registry als Single Source of Truth nutzen (`?scope=`).

### Tests vs Implementierung

`tests/test_variables_registry.py` erwartet z.T. List-API mit Key `meetme` und Identifier-Heuristik — weicht vom aktuellen Dict-Return in `views.py` ab. Tests werden an die Live-API angeglichen; Identifier-Heuristik (`meetme_*` → Telefon-Vars) wird ergänzt.

---

## Bekannte Namens-Inkonsistenzen

| Ort | Ist | Soll |
|---|---|---|
| KI-Wizard `questions/email_template.json` L3 | `button_blau` / `button_gruen` | `cta_blau` / `cta_gruen` |
| Tutorial `es-core.js` | `{{block:button_blau}}` | `{{block:cta_blau}}` |
| Help | bereits `cta_blau` / `cta_gruen` ✓ | — |
| DB-Module | `cta_blau` / `cta_gruen` ✓ | — |
| Corporate Skeleton `views.py` | Inline Header/Footer HTML | `{{block:abcona_header_blau}}` + Body + `{{block:footer_standard}}` / signature |

---

## Phase 3 — Vorschläge (nicht blind deployen)

### A. Code (dieses PR — sicher)

1. `export-email-studio-data.sh` + `RUN-phase1-iststand.sh`
2. `audit_email_studio_snapshot.py`
3. `VariableListAPI` → `variables_registry`
4. Registry: Intake-Vars + globale Button-Vars + `meetme_*`-Identifier
5. KI-Fragen + Tutorial: `cta_*` statt `button_*`
6. Skeleton in `views.py` auf Module umstellen

### B. DB-Module (Review nötig — Fixtures unter `fixtures/ci_modules/`)

Vereinheitlichte Header-HTMLs (left, 18px, padding 16px 24px):

- `abcona_header_blau.html`
- `abcona_header_gruen.html`
- `abcona_header_rot.html`

Nach Freigabe auf ucs5: Backup → `loaddata` oder Admin-Update nur dieser 3 Module.

### C. Vorlagen (Review)

1. MeetMe ACTIVE: optional `{{block:signature}}` ergänzen (oder Signatur-Policy dokumentieren)
2. `cv_generated_berater_copy`: auf Modul-Struktur migrieren oder archivieren
3. Body-Fließtext: wo sinnvoll `font-size:14px;color:#333333;text-align:left` an Body-`<td>`/`<p>`

### D. layout_rules

Footer-Stil explizit machen (`imprint` vs `body_match`), damit KI und Audit dieselbe Wahrheit haben.

---

## Deploy-Hinweis

Nur nach expliziter Freigabe auf ucs5. Vor DB-Änderungen:

```bash
cd /opt/abpe/backend && source /opt/abpe/venv311/bin/activate
python manage.py dumpdata abpe_email_studio.EmailModule \
  abpe_email_studio.EmailTemplate \
  abpe_email_studio.EmailSignature \
  abpe_email_studio.EmailSenderAccount \
  --indent 2 -o /tmp/email_studio_backup_$(date +%Y%m%d_%H%M%S).json
```
