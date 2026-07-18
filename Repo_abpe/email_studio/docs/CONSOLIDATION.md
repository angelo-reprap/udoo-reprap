# Email Studio — Konsolidierung

Stand: **2026-07-18** · Live-DB Apply: **VERIFY_OK**  
Deklaration: [`EMAIL_LAYOUT_DECLARATION.md`](./EMAIL_LAYOUT_DECLARATION.md)  
Apply: [`APPLY_CONSOLIDATION.md`](./APPLY_CONSOLIDATION.md)

---

## Status

| Schritt | Status |
|---|---|
| Phase 1 Sync + Snapshot | ✅ |
| Layout-Deklaration | ✅ |
| Live-DB: Footer-Impressum (USt/HRA) | ✅ |
| Live-DB: XOR System-Mails (`signature_mode=NONE`) | ✅ |
| Live-DB: TXT 1:1 alle Vorlagen | ✅ |
| Snapshot Verify (`77213` bytes) | ✅ `VERIFY_OK` |
| KI `layout_rules` / Fragen auf Live | ⏳ Code-Deploy + Sync (`--code-only`) |
| Info-Popover `(i)` chirurgisch | ⏳ später |

Backup Live vor Apply: `/tmp/email_studio_backup_before_consolidation_20260718_164817.json`

---

## Verifiziert im Snapshot (nach Apply)

| Check | Wert |
|---|---|
| `footer_*` enthält DE813519516 | ja |
| leere `text_body` | 0 / 17 |
| `pipeline_*` / `upload_*` | `signature_mode=NONE` |
| CRM / MeetMe | `USER` + TXT befüllt |

---

## Nächster Schritt (KI-Code auf Live, damit Sync nicht zurückdreht)

```bash
cd /mnt/public/udoo-reprap && git pull
bash Repo_abpe/email_studio/incoming/RUN-apply-consolidation.sh --code-only
```

Erwartung: `VERIFY_OK` + **`VERIFY_KI_OK`**

---

## Inventar

24 Module · 17 Vorlagen · 5 Signaturen · 5 Absender
