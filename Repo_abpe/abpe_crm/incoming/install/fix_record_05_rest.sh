#!/bin/bash
# ============================================================
# fix_record_05_rest.sh  (v2)
# Holt nach was record_05 Schritt 8 (HTML-Abbruch) nicht schaffte:
#  1. 17 fehlende rec_*-i18n-Keys in de_phone.json
#  2. Hover-CSS in app.css
#  3. setup_password_hint Platzhalter -> {Nebenstelle} (alle 12)
#  4. record_06 nachlaufen
# ============================================================
set -e
cd /opt/abpe/backend
SP=apps/abpe_crm/static/softphone-electron
I18N=$SP/renderer/i18n

echo "=== [1/5] Backups ==="
python3 Archiv/backup_restore.py -save "$I18N/de_phone.json" -m "fix: rec-keys nachtrag" >/dev/null
python3 Archiv/backup_restore.py -save "$SP/renderer/app.css" -m "fix: rec hover-css" >/dev/null
echo "  ok"

echo "=== [2/5] 17 fehlende rec_*-Keys in de_phone.json ==="
python3 "$SP/../../bin/_fix_dekeys.py" 2>/dev/null || python3 - "$I18N/de_phone.json" << 'PYEOF'
import json, sys
from collections import OrderedDict
p = sys.argv[1]
d = json.load(open(p, encoding='utf-8'), object_pairs_hook=OrderedDict)
keys = OrderedDict([
 ('rec_subject_title','Aufnahme - Betreff erfassen'),
 ('rec_subject_hint','Pflicht: Wer, warum wurde aufgezeichnet?'),
 ('rec_subject_ph','z.B. Projektabstimmung, Einwilligung erteilt'),
 ('rec_subject_save','Speichern'),
 ('rec_subject_required','Betreff ist Pflicht!'),
 ('rec_subject_nodismiss','Ohne Betreff bleibt die Aufnahme nicht zugeordnet'),
 ('rec_assign_me','Mir zuordnen'),
 ('rec_search_contact','Anderen Kontakt suchen...'),
 ('rec_target_required','Bitte zuordnen (Mir / Kontakt)'),
 ('rec_assigned_already','zugeordnet'),
 ('rec_no_owner','Kein Besitzer gesetzt (Einstellungen, Telefonie)'),
 ('rec_saved','Aufnahme zugeordnet'),
 ('rec_owner_saved','Besitzer gespeichert'),
 ('rec_owner_none','nicht gesetzt'),
 ('rec_owner_label','Mein CRM-Kontakt (Besitzer)'),
 ('rec_owner_hint','Aufnahmen ohne Zuordnung gehoeren diesem Kontakt.'),
 ('change','aendern'),
])
added = 0
for k, v in keys.items():
    if k not in d:
        d[k] = v; added += 1
json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print("  %d Keys ergaenzt (de_phone.json jetzt %d Keys)." % (added, len(d)))
PYEOF
python3 -c "import json; json.load(open('$I18N/de_phone.json')); print('  JSON valid')"

echo "=== [3/5] Hover-CSS in app.css ==="
python3 - "$SP/renderer/app.css" << 'PYEOF'
import sys
p = sys.argv[1]
s = open(p, encoding='utf-8').read()
if '.rec-cres:hover' in s:
    print("  CSS schon da.")
else:
    s = s.rstrip() + "\n.rec-cres:hover, .owner-res:hover { background: var(--card); }\n"
    open(p, 'w', encoding='utf-8').write(s)
    print("  Hover-CSS ergaenzt.")
PYEOF

echo "=== [4/5] setup_password_hint Platzhalter -> {Nebenstelle} ==="
python3 - "$I18N" << 'PYEOF'
import json, re, glob, os, sys
I18N = sys.argv[1]
fixed = 0
for path in glob.glob(os.path.join(I18N, '*_phone.json')):
    d = json.load(open(path, encoding='utf-8'))
    if 'setup_password_hint' not in d: continue
    val = d['setup_password_hint']
    phs = re.findall(r'\{[^}]+\}', val)
    if phs and phs[0] != '{Nebenstelle}':
        d['setup_password_hint'] = val.replace(phs[0], '{Nebenstelle}')
        json.dump(d, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        fixed += 1
        print("  %s: %s -> {Nebenstelle}" % (os.path.basename(path), phs[0]))
print("  %d Dateien normalisiert." % fixed)
PYEOF

echo "=== [5/5] record_06 nachlaufen (uebersetzt die 17 neuen Keys) ==="
bash apps/abpe_crm/install/record_06_i18n.sh 2>&1 | grep -E "\[|Keys|erfolgreich|Quelle" | tail -20

echo ""
echo "============================================================"
echo "OK fix fertig. Jetzt check_i18n.sh zur Verifikation."
echo "============================================================"

