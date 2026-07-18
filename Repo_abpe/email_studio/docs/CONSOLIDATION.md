# Email Studio — Konsolidierung (Analyse-Report)

Stand: **2026-07-18** · Phase-1 Sync: Commit `7a7949d`  
Snapshot: `Repo_abpe/email_studio/data/email_studio_snapshot_latest.json`  
Deklaration: [`EMAIL_LAYOUT_DECLARATION.md`](./EMAIL_LAYOUT_DECLARATION.md)

**Keine Live-DB-Änderungen in diesem Schritt — nur Inventar + Gap zur Deklaration.**

---

## Phase 1 — erledigt

| Schritt | Status |
|---|---|
| Code-Sync ucs5 → Git | OK (`RUN-phase1-iststand.sh`) |
| DB-Snapshot Module/Vorlagen/Signaturen/Absender | OK (24 / 17 / 5 / 5) |
| Layout-Deklaration | OK |
| Offline-Audit | `python3 Repo_abpe/email_studio/incoming/audit_email_studio_snapshot.py` |

Wiederholen nach jedem funktionierenden Schritt:

```bash
bash Repo_abpe/email_studio/incoming/RUN-phase1-iststand.sh --commit --push
```

---

## Inventar Snapshot

| Modell | Anzahl |
|---|---|
| EmailModule | 24 |
| EmailTemplate | 17 (15 ACTIVE, 2 DRAFT) |
| EmailSignature | 5 |
| EmailSenderAccount | 5 |

### Module (relevant für Deklaration)

| Rolle | Identifier | Ist vs Deklaration |
|---|---|---|
| Header Marke | `abcona_header_blau` | vorhanden, left, 19px (Soll 18px) |
| Header alt | `abcona_header_gruen`, `_rot` | vorhanden — laut Deklaration **nicht mehr als Marken-Kopf** |
| Event | `label_info`, `label_bestaetigt`, `label_warnung` | vorhanden ✓ |
| Footer | `footer_standard`, `footer_auto_reply` | Text noch alt („ABpE — …“), **ohne** USt-ID/HRA |
| CTA | `cta_blau`, `cta_gruen`, `cta_with_secondary` | vorhanden ✓ |
| Sonstige | calendar, fakten_box, support_kontakt, … | 16 SECTION-Module |

Unbekannte `{{block:…}}` in Vorlagen: **keine**.

---

## Gap-Analyse gegen Deklaration

### A. TXT-Fallback — kritisch

**Alle 17 Vorlagen:** `text_body` Länge = **0**.

Deklaration §6: TXT Pflicht, 1:1 aus HTML.  
→ Nächster Konsolidierungs-Schritt: TXT aus HTML ableiten (kein Blind-Overwrite ohne Review).

### B. Signatur XOR Footer — Renderer-Verhalten wichtig

Der Renderer hängt bei `signature_mode != NONE` die Signatur **automatisch ans Ende**, wenn kein `{{block:signature}}` im HTML steht (`services/renderer.py`).

| Muster | Vorlagen | Bewertung |
|---|---|---|
| Header + `{{block:signature}}`, kein Footer | CRM, `cv_generated_berater` | ✓ XOR erfüllt (Sig im Body) |
| Header + Footer, `sig_mode=USER` | `pipeline_*`, `upload_*` | **Konflikt:** Footer im HTML **plus** Auto-Signatur beim Versand |
| Header, kein Footer, `sig_mode=USER` | alle MeetMe | ✓ Impressum über Auto-Sig; kein `{{block:signature}}` sichtbar im Editor |
| Inline-Skeleton | `cv_generated_berater_copy` (DRAFT) | ✗ kein Modul-Header |

**Empfehlung (noch nicht umsetzen):**

1. System-Mails (`pipeline_*`, `upload_*`): `signature_mode=NONE` + Footer mit Impressum-Text §3  
2. Persönliche Mails (MeetMe, CRM): `signature_mode=USER|TEAM` + **kein** Footer; optional `{{block:signature}}` im Body für Editor-Klarheit  
3. Footer-HTML auf Firmen-Impressum aus Deklaration §3 umstellen

### C. Header + Event-Badge

| Gruppe | Header blau | Event-Label | Gap |
|---|---|---|---|
| CRM | ✓ | `label_info` | OK |
| CV generated | ✓ | `label_bestaetigt` | OK |
| Pipeline/Upload success | ✓ | `label_bestaetigt` | OK |
| Pipeline/Upload error | ✓ | `label_warnung` | OK |
| MeetMe cancel | ✓ | `label_warnung` | OK |
| MeetMe invite/reminder/reschedule | ✓ | **fehlt** | optional `label_info` |
| DRAFT copy/test | — | — | aufräumen oder archivieren |

### D. Footer-Inhalt

Ist: „ABpE — Automatisiertes Berater Profil Erfassungssystem…“  
Soll (Deklaration): Firma, Adresse, USt-ID DE813519516, Amtsgericht HRA 3662, Inhaber.

### E. Code / KI-Katalog (Nebenbefund nach Sync)

Nach dem Phase-1-rsync von Live liegen u. a. wieder vor:

- KI-Frage L3: `button_blau` / `button_gruen` (Soll: `cta_*`)
- `variables_registry` / `VariableListAPI`: Live-Stand (nicht die Agent-Erweiterung)

**Absicht:** erst Report, dann gezielt angleichen — kein Misch-Restore.

### F. UI Info-Popover `(i)`

| Feature | Aktueller Git-/Sync-Stand |
|---|---|
| KI-Wizard | vorhanden |
| Clipboard Klick | vorhanden |
| Info-Popover `(i)` | fehlt (nur Branch `cursor/email-studio-vars-hints-bf44`) |

Später **chirurgisch** mergen — kein Voll-Overwrite.

---

## Vorlagen-Matrix (ACTIVE)

| Identifier | Header | Label | Abschluss (HTML) | sig_mode | TXT |
|---|---|---|---|---|---|
| crm_berater_profilupdate | blau | info | `signature` | USER | ✗ |
| crm_firmenprofil | blau | info | `signature` | USER | ✗ |
| crm_manual_email | blau | — | `signature` | USER | ✗ |
| cv_generated_berater | blau | bestätigt | `signature` | USER | ✗ |
| meetme_cancel_standard | blau | warnung | (auto-sig) | USER | ✗ |
| meetme_invite_* / reminder / reschedule | blau | — | (auto-sig) | USER | ✗ |
| pipeline_error | blau | warnung | `footer_auto_reply` | USER | ✗ + XOR-Risiko |
| pipeline_success | blau | bestätigt | `footer_standard` | USER | ✗ + XOR-Risiko |
| upload_error | blau | warnung | `footer_auto_reply` | USER | ✗ + XOR-Risiko |
| upload_received | blau | bestätigt | `footer_auto_reply` | USER | ✗ + XOR-Risiko |

---

## Priorisierte nächste Schritte (eines nach dem anderen)

1. **Du checkst** diesen Report + Deklaration (OK / Korrektur)  
2. **Footer-Modul** auf Impressum-Text §3 (Backup auf ucs5 vorher)  
3. **XOR bereinigen:** System-Mails → `signature_mode=NONE`; persönliche → kein Footer  
4. **TXT** für alle Vorlagen 1:1 generieren (Skript + Review)  
5. **layout_rules / KI-Fragen** an Deklaration (`cta_*`, Header nur blau, Labels, XOR)  
6. Optional: Info-Popover chirurgisch; MeetMe `label_info`; Header grün/rot deaktivieren oder nur intern behalten  

---

## Arbeitsregel

Vor Live-Änderung: `python3 Archiv/backup_restore.py -save <datei> -m "vor: …"`  
Nach funktionierendem Schritt: `RUN-phase1-iststand.sh --commit --push`
