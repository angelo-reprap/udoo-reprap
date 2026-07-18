# Email Studio — Konsolidierung

Stand: **2026-07-18**  
Deklaration: [`EMAIL_LAYOUT_DECLARATION.md`](./EMAIL_LAYOUT_DECLARATION.md)  
Apply: [`APPLY_CONSOLIDATION.md`](./APPLY_CONSOLIDATION.md)

---

## Status — erledigt

| Schritt | Status |
|---|---|
| Phase 1 Sync + Snapshot | ✅ |
| Layout-Deklaration | ✅ |
| Live-DB: Footer-Impressum (USt/HRA) | ✅ |
| Live-DB: XOR System-Mails (`signature_mode=NONE`) | ✅ |
| Live-DB: TXT 1:1 alle Vorlagen | ✅ |
| Snapshot Verify | ✅ `VERIFY_OK` (77213 bytes) |
| KI `layout_rules` / Fragen / `cta_*` auf Live + Git | ✅ `VERIFY_KI_OK` |

Backup vor Apply: `/tmp/email_studio_backup_before_consolidation_20260718_164817.json`

---

## Verifiziert

| Check | Wert |
|---|---|
| `footer_*` DE813519516 | ja |
| leere `text_body` | 0 / 17 |
| `pipeline_*` / `upload_*` | `NONE` |
| CRM / MeetMe | `USER` + TXT |
| KI `closing_xor` + L2 Labels + `cta_blau` | ja |

---

## Optional später

1. Info-Popover `(i)` chirurgisch (ohne KI-Wizard zu überschreiben)  
2. MeetMe optional `label_info`  
3. Header grün/rot deaktivieren oder nur intern behalten  

---

## Inventar

24 Module · 17 Vorlagen · 5 Signaturen · 5 Absender

Wiederholen bei Bedarf:

```bash
bash Repo_abpe/email_studio/incoming/RUN-apply-consolidation.sh
```
