# Email Studio — Konsolidierung (Analyse + Umsetzung)

Stand: **2026-07-18**  
Deklaration: [`EMAIL_LAYOUT_DECLARATION.md`](./EMAIL_LAYOUT_DECLARATION.md)  
Apply: [`APPLY_CONSOLIDATION.md`](./APPLY_CONSOLIDATION.md)

---

## Status

| Schritt | Status |
|---|---|
| Phase 1 Sync + Snapshot | ✅ |
| Layout-Deklaration | ✅ |
| Gap-Analyse | ✅ |
| Footer-Impressum Fixtures | ✅ im Git |
| XOR + TXT im konsolidierten Snapshot | ✅ `data/email_studio_snapshot_latest.json` |
| Apply-Skript | ✅ `incoming/apply_layout_consolidation.py` |
| KI `layout_rules` + Fragen (L1/L2/L3, XOR) | ✅ im Git |
| **Live-DB auf ucs5** | ⏳ du führst `--apply-db` aus (Backup vorher) |
| Info-Popover `(i)` chirurgisch | ⏳ später |

---

## Was der konsolidierte Snapshot enthält

- `footer_standard` / `footer_auto_reply`: Firma, Adresse, USt-ID, HRA, Inhaber  
- System-Mails `pipeline_*`, `upload_*`: `signature_mode=NONE`, `include_signature=False`  
- Alle 17 Vorlagen: `text_body` 1:1 aus HTML (+ Modul-TXT)  
- Modul-`text_body` neu aus HTML (ohne Altlast `=== … ===`)

Offline prüfen:

```bash
python3 Repo_abpe/email_studio/incoming/apply_layout_consolidation.py --dry-run
python3 Repo_abpe/email_studio/incoming/audit_email_studio_snapshot.py
```

---

## Inventar (Counts unverändert)

24 Module · 17 Vorlagen · 5 Signaturen · 5 Absender

---

## Nach Apply auf ucs5

```bash
# 1 Backup + Apply — siehe APPLY_CONSOLIDATION.md
python3 Repo_abpe/email_studio/incoming/apply_layout_consolidation.py --apply-db

# 2 Sync zurück
bash Repo_abpe/email_studio/incoming/RUN-phase1-iststand.sh --commit --push
```

Dann optional: MeetMe `label_info`, Header grün/rot deaktivieren, Info-Popover merge.
