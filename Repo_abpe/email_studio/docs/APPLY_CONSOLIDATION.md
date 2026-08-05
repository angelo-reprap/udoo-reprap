# Apply Layout-Konsolidierung auf ucs5

Voraussetzung: Branch `cursor/email-studio-consolidate-modules-7f07` ausgecheckt.

> **Reihenfolge:** erst `--apply-db`, **danach** `RUN-phase1-iststand.sh`.  
> Phase-1 allein schreibt nur den **Live**-Stand zurück ins Git — ohne Apply geht die Konsolidierung im Snapshot wieder verloren (und rsync kann KI-Fragen überschreiben).

## Empfohlen: ein Befehl

```bash
cd /mnt/public/udoo-reprap && git pull
bash Repo_abpe/email_studio/incoming/RUN-apply-consolidation.sh
# optional vorher:  …/RUN-apply-consolidation.sh --dry-run
```

Das macht: Backup → `--apply-db` → Phase-1 Sync → Verify (USt / TXT / XOR).

---

## Manuell (falls nötig)

## 1. Backup (Pflicht)

```bash
cd /opt/abpe/backend && source /opt/abpe/venv311/bin/activate
python manage.py dumpdata \
  abpe_email_studio.EmailModule \
  abpe_email_studio.EmailTemplate \
  abpe_email_studio.EmailSignature \
  abpe_email_studio.EmailSenderAccount \
  --indent 2 \
  -o /tmp/email_studio_backup_before_consolidation_$(date +%Y%m%d_%H%M%S).json
```

Optional Dateien sichern:

```bash
python3 Archiv/backup_restore.py -save apps/abpe_email_studio/services/renderer.py -m "vor: layout consolidation"
```

## 2. Dry-Run (nur Log)

```bash
cd /mnt/public/udoo-reprap && git pull
python3 Repo_abpe/email_studio/incoming/apply_layout_consolidation.py --dry-run
```

## 3. Live-DB anwenden

```bash
python3 Repo_abpe/email_studio/incoming/apply_layout_consolidation.py --apply-db
```

Ändert:

- Footer-Module → Firmen-Impressum (USt-ID / HRA)
- `pipeline_*` / `upload_*` → `signature_mode=NONE` (XOR)
- Alle Vorlagen + Module → `text_body` 1:1 aus HTML

## 4. Code (KI layout_rules / Fragen) deployen

Nur nach Check — z. B. die geänderten Dateien aus dem Repo nach `/opt/abpe/backend` kopieren bzw. euer übliches Deploy-Skript. Betroffen u. a.:

- `apps/abpe_ki_wiz/.../providers/email_template.py`
- `apps/abpe_ki_wiz/.../questions/email_template.json`

## 5. Ist-Stand wieder ins Git

```bash
cd /mnt/public/udoo-reprap
bash Repo_abpe/email_studio/incoming/RUN-phase1-iststand.sh --commit --push
```

## Rollback

```bash
python manage.py loaddata /tmp/email_studio_backup_before_consolidation_….json
# oder gezielt Module/Templates im Admin
```
