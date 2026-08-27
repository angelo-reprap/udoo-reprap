# -*- coding: utf-8 -*-
"""
cleanup_scan_dubletten.py
================================================================================
Räumt die durch den doppelten Scan-Lauf (29.06.2026, zwei parallele dms_scan
--execute) entstandenen DB-Dubletten auf.

Logik: Pro (volume, relative_path) bleibt GENAU EIN Dokument erhalten.
Bevorzugt behalten wird das Dokument, das einen Owner hat (damit die manuelle/
automatische Owner-Zuordnung nicht verloren geht). Bei Gleichstand: niedrigste id
(= zuerst angelegt). Alle anderen Dokumente desselben Pfads werden gelöscht.

WICHTIG: Es werden NUR DB-Einträge gelöscht. Die Dateien auf dem Share bleiben
unangetastet (sie liegen ohnehin nur einmal da).

Aufruf (als Django-Shell-Skript):
  python manage.py shell < cleanup_scan_dubletten.py              # Trockenlauf
  EXECUTE=1 python manage.py shell < cleanup_scan_dubletten.py    # echtes Löschen
================================================================================
"""

import os
from collections import defaultdict
from django.db.models import Count
from apps.abpe_edms.models import CrmDocument, CrmDocumentVersion

EXECUTE = os.environ.get("EXECUTE") == "1"

print("=" * 70)
print(f"  DUBLETTEN-CLEANUP — {'ECHTES LÖSCHEN' if EXECUTE else 'TROCKENLAUF (nichts wird gelöscht)'}")
print("=" * 70)

# 1. Alle Pfade mit mehr als einer Version finden
dupe_paths = (CrmDocumentVersion.objects
              .values("volume", "relative_path")
              .annotate(n=Count("id"))
              .filter(n__gt=1))

total_groups = dupe_paths.count()
print(f"  Doppelte Pfade: {total_groups}")

to_delete_doc_ids = []
kept_with_owner = 0
kept_lowest_id = 0

# 2. Pro Pfad entscheiden, welches Dokument bleibt
for grp in dupe_paths.iterator():
    vol = grp["volume"]
    rel = grp["relative_path"]

    # Alle Versionen dieses Pfads -> zugehörige Dokumente
    versions = (CrmDocumentVersion.objects
                .filter(volume=vol, relative_path=rel)
                .select_related("document"))
    docs = []
    seen_doc = set()
    for v in versions:
        if v.document_id not in seen_doc:
            seen_doc.add(v.document_id)
            docs.append(v.document)

    if len(docs) < 2:
        continue  # zwischenzeitlich schon bereinigt (idempotent)

    # Behalte-Regel: zuerst Dokumente MIT Owner, dann niedrigste id
    def sort_key(d):
        has_owner = d.owners.exists()
        return (0 if has_owner else 1, d.id)

    docs_sorted = sorted(docs, key=sort_key)
    keeper = docs_sorted[0]
    losers = docs_sorted[1:]

    if keeper.owners.exists():
        kept_with_owner += 1
    else:
        kept_lowest_id += 1

    to_delete_doc_ids.extend([d.id for d in losers])

print(f"  Behalten mit Owner:       {kept_with_owner}")
print(f"  Behalten (niedrigste id): {kept_lowest_id}")
print(f"  Zu löschende Dokumente:   {len(to_delete_doc_ids)}")

# 3. Vorher/Nachher-Prognose
before = CrmDocument.objects.count()
print(f"\n  Dokumente vorher:  {before}")
print(f"  Dokumente nachher: {before - len(to_delete_doc_ids)} (erwartet ~24070)")

if not EXECUTE:
    print("\n  >>> TROCKENLAUF — nichts gelöscht.")
    print("  >>> Zum echten Löschen:  EXECUTE=1 python manage.py shell < cleanup_scan_dubletten.py")
else:
    print("\n  Lösche in Batches …")
    BATCH = 500
    deleted = 0
    for i in range(0, len(to_delete_doc_ids), BATCH):
        chunk = to_delete_doc_ids[i:i + BATCH]
        # Cascade löscht zugehörige Versionen/Owner/Events mit
        n, _ = CrmDocument.objects.filter(id__in=chunk).delete()
        deleted += len(chunk)
        print(f"    … {deleted}/{len(to_delete_doc_ids)} gelöscht")
    print(f"\n  FERTIG. {deleted} Dubletten gelöscht.")
    print(f"  Dokumente jetzt: {CrmDocument.objects.count()}")

