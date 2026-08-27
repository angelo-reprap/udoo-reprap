# EDMS Owner-Matching — Einbau-Anleitung

## Reihenfolge (immer erst Backup, dann patchen — deine Regel)

### 1. Backup der drei Dateien, die wir ersetzen/ändern
```bash
cd /opt/abpe/backend
python3 Archiv/backup_restore.py -save apps/abpe_edms/services/scanner.py -m "vor Account-Match"
python3 Archiv/backup_restore.py -save apps/abpe_edms/management/commands/dms_scan.py -m "vor Schaltern"
python3 Archiv/backup_restore.py -save apps/abpe_edms/models.py -m "vor is_suggestion Feld"
```

### 2. Modell: zwei Felder an CrmDocumentOwner
In `apps/abpe_edms/models.py`, Klasse `CrmDocumentOwner`,
NACH `is_primary = models.BooleanField(default=False)` einfügen:

```python
    is_suggestion = models.BooleanField(
        default=False, db_index=True,
        help_text="Unsicherer Match — muss bestätigt werden",
    )
    match_source = models.CharField(
        max_length=16, blank=True, default="",
        help_text="Wie der Match kam (exact/normalized/substring/path/manual)",
    )
```

### 3. Migration erzeugen + anwenden
```bash
python manage.py makemigrations abpe_edms
python manage.py migrate abpe_edms
```
(Beide Felder haben default -> die ~7.178 bestehenden Berater-Owner
migrieren problemlos, alle werden is_suggestion=False.)

### 4. Scanner + Command ersetzen
```bash
cp scanner.py  apps/abpe_edms/services/scanner.py
cp dms_scan.py apps/abpe_edms/management/commands/dms_scan.py
```

## Testreihenfolge (dry-run zuerst!)

### A. Kunde-Baum trocken ansehen — was WÜRDE gesetzt?
```bash
python manage.py dms_scan --kunde --update
```
Achte auf: `owner_added` (nachgetragen), `owner_suggested` (Vorschläge),
`owner_conflict` (bestätigte, die bleiben). Beispiele mit +OWNER / +VORSCHLAG.

### B. Wenn die Zahlen stimmen — Kunde echt
```bash
python manage.py dms_scan --kunde --update --execute
```

### C. Administration (abcona-Rechnungen) trocken, dann echt
```bash
python manage.py dms_scan --administration --update
python manage.py dms_scan --administration --update --execute
```

### D. Verifizieren an PiraCon
```bash
python manage.py shell -c "
from apps.abpe_edms.models import CrmDocumentVersion
for v in CrmDocumentVersion.objects.filter(relative_path__icontains='aktive/PiraCon', is_active=True)[:5]:
    d=v.document
    print(d.title[:40], '|', list(d.owners.values_list('owner_type','owner_crm_id','is_suggestion','match_source')))
"
```
Erwartung: owner_type='account', crm_id=cbb10fb6-..., is_suggestion=False, match_source='normalized'

## Danach (getrennt)
- Welle 2 OCR: python manage.py dms_extract_content --min-chars 50 --workers 2
- ES-Reindex: python manage.py dms_reindex ...  (content + owner_crm_ids in Index)

