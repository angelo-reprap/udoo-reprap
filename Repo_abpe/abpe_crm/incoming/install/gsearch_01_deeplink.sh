#!/bin/bash
# ============================================================
# gsearch_01_deeplink.sh
# Globale Suche — Etappe 1: Deep-Link in mod-edms.js.
# ?doc=<uuid> oeffnet direkt die Dokument-Vorschau,
# ?mail_account=&mail_folder=&mail_uid=&mail_message_id=&mail_subject=
# oeffnet direkt die Mail-Ansicht. _openMailHit() wird dafuer in
# _showMailDetail(m) + duennen Wrapper aufgeteilt (Baukasten-
# Wiederverwendung fuer Klick UND Deep-Link, kein Duplikat).
# Kein Backend-Fix noetig - _normalize_hit(mail) hat account/folder/
# message_id/uid bereits.
# ============================================================
set -e
cd /opt/abpe/backend
JS="apps/abpe_crm/static/abpe_crm/js/mod-edms.js"

echo "=== [1/3] Backup ==="
python3 Archiv/backup_restore.py -save "$JS" -m "gsearch_01: deep-link doc/mail"

echo "=== [2/3] Patches ==="
python3 /tmp/gsearch/patch_01.py

echo "=== [3/3] node --check ==="
node --check "$JS" && echo "  Syntax OK"

echo ""
echo "============================================================"
echo "✅ gsearch_01 fertig (Deep-Link)."
echo "Danach: gsearch_02_frontend.sh"
echo "============================================================"
