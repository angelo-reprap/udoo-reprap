#!/bin/bash
# ============================================================
# update_help.sh — Hilfe um Recording-Features aktualisieren
#  1. help_incall_text: 5 -> 6 Tasten (Aufnahme-Button)
#  2. help_vm_text: Recording-Teil raus (Voicemail bleibt)
#  3. Neuer Abschnitt "Aufnahmen" (HTML + help_rec_title/text)
#  4. Geänderte/neue Keys in 11 Sprachen übersetzen
# ============================================================
set -e
cd /opt/abpe/backend
SP=apps/abpe_crm/static/softphone-electron
I18N=$SP/renderer/i18n

echo "=== [1/5] Backups ==="
python3 Archiv/backup_restore.py -save "$SP/renderer/app.html" -m "help: recording-abschnitt" >/dev/null
python3 Archiv/backup_restore.py -save "$I18N/de_help.json" -m "help: recording-texte" >/dev/null
echo "  ok"

echo "=== [2/5] de_help.json: incall + vm aktualisieren, rec-Keys ergänzen ==="
python3 - << 'PYEOF'
import json
from collections import OrderedDict
p = 'apps/abpe_crm/static/softphone-electron/renderer/i18n/de_help.json'
d = json.load(open(p, encoding='utf-8'), object_pairs_hook=OrderedDict)

d['help_incall_text'] = ("Während eines aktiven Gesprächs stehen sechs Tasten bereit: "
  "Transfer (Gespräch weiterverbinden), Parken (Anruf öffentlich ablegen), "
  "Konferenz (Gegenstelle in einen Konferenzraum holen), Halten (Gespräch pausieren, "
  "der Anrufer hört Wartemusik), Aufnehmen (nimmt das laufende Gespräch auf — das "
  "Symbol wird rot, solange aufgenommen wird) und der rote Hörer zum Auflegen. "
  "Ein gehaltenes Gespräch wird oben mit „Gehalten\" angezeigt.")

d['help_vm_text'] = ("Die Postfach-Symbole oben in der Statusleiste zeigen die Anzahl neuer "
  "Nachrichten je Box. Im Bedienpanel → Voicemail siehst du pro Box, wie viele Nachrichten "
  "neu und wie viele alt sind. Eigene Voicemail hörst du per Wählcode *97 ab, eine bestimmte "
  "Box wählst du mit *98.")

# Neuer Aufnahme-Abschnitt
d['help_rec_title'] = "Aufnahmen"
d['help_rec_text'] = ("Gespräche kannst du auf zwei Wegen aufnehmen: über die Aufnehmen-Taste "
  "in der Gesprächsleiste oder im Bedienpanel bei deiner eigenen Nebenstelle. Wichtig: Hole "
  "vor der Aufnahme die mündliche Einwilligung des Gesprächspartners ein — am besten direkt zu "
  "Beginn, sodass sie mitgeschnitten wird. Nach dem Stoppen musst du einen Betreff angeben "
  "(wer war es, worum ging es) — ohne Betreff bleibt die Aufnahme nicht zugeordnet. Du ordnest "
  "sie einem CRM-Kontakt zu, entweder über die Kontaktsuche im Dialog oder mit dem Knopf "
  "„Mir zuordnen\", wenn du dich unter Einstellungen → Telefonie → Mein CRM-Kontakt als Besitzer "
  "hinterlegt hast. Die Aufnahmen erscheinen anschließend beim jeweiligen Kontakt im Bereich "
  "„Aufnahmen\" mit Abspieler, Dauer und Betreff und lassen sich dort anhören oder löschen. "
  "Das Original bleibt zusätzlich auf der Telefonanlage und ist weiterhin über *96 abhörbar.")

json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print(f"  de_help.json aktualisiert ({len(d)} Keys, +help_rec_title/text).")
PYEOF
python3 -c "import json; json.load(open('$I18N/de_help.json')); print('  JSON valid')"

echo "=== [3/5] Neuer Aufnahme-Abschnitt im HTML (nach Voicemail) ==="
python3 - << 'PYEOF'
p = 'apps/abpe_crm/static/softphone-electron/renderer/app.html'
s = open(p, encoding='utf-8').read()
if 'help_rec_title' in s:
    print("  schon da — übersprungen.")
else:
    # Anker: Ende des Voicemail-body, vor dem Status-Abschnitt
    anchor = """          <p data-i18n="help_vm_text"></p>
        </div>
        <div class="help-section-hdr" onclick="toggleAcc(this)">
          <i class="bi bi-circle-half help-section-icon"></i>
          <span class="help-section-title" data-i18n="help_status_title"></span>"""
    newsec = """          <p data-i18n="help_vm_text"></p>
        </div>
        <div class="help-section-hdr" onclick="toggleAcc(this)">
          <i class="bi bi-record-circle help-section-icon"></i>
          <span class="help-section-title" data-i18n="help_rec_title"></span>
          <span class="help-section-arrow">&#9656;</span>
        </div>
        <div class="help-section-body">
          <p data-i18n="help_rec_text"></p>
        </div>
        <div class="help-section-hdr" onclick="toggleAcc(this)">
          <i class="bi bi-circle-half help-section-icon"></i>
          <span class="help-section-title" data-i18n="help_status_title"></span>"""
    assert s.count(anchor) == 1, f"HTML-Anker {s.count(anchor)}x"
    s = s.replace(anchor, newsec)
    open(p, 'w', encoding='utf-8').write(s)
    print("  Aufnahme-Abschnitt eingefügt.")
PYEOF

echo "=== [4/5] div-Balance-Check ==="
python3 -c "s=open('$SP/renderer/app.html',encoding='utf-8').read(); o=s.count('<div'); c=s.count('</div>'); print(f'  <div:{o} </div>:{c} diff:{o-c}')"

echo "=== [5/5] Geänderte/neue Keys in 11 Sprachen übersetzen ==="
python3 - << 'PYEOF'
import sys, json, re
sys.path.insert(0, '/opt/abpe/backend/apps/abpe_crm/bin')
from i18n_translator import _deepseek_translate, _load_api_key
I18N = '/opt/abpe/backend/apps/abpe_crm/static/softphone-electron/renderer/i18n'
TARGETS = ['en','fr','es','it','pl','ru','ar','zh','pt','ko','ja']

api_key = _load_api_key()
if not api_key:
    print("  ❌ Kein API-Key."); sys.exit(1)

de = json.load(open(f'{I18N}/de_help.json', encoding='utf-8'))
# Die Keys, die wir geändert/ergänzt haben — die müssen neu übersetzt werden
upd_keys = ['help_incall_text', 'help_vm_text', 'help_rec_title', 'help_rec_text']
subset = {k: de[k] for k in upd_keys if k in de}

def ph(t):
    return set(re.findall(r'\{[^}]+\}', t)) | set(re.findall(r'<[^>]+>', t)) if isinstance(t,str) else set()

for L in TARGETS:
    path = f'{I18N}/{L}_help.json'
    try:
        tgt = json.load(open(path, encoding='utf-8'))
    except Exception as e:
        print(f"  [{L}] ❌ {e}"); continue
    print(f"  [{L}] übersetze {len(subset)} Keys...", flush=True)
    tr = _deepseek_translate(subset, 'de', L, api_key)
    if not isinstance(tr, dict):
        print(f"  [{L}] ❌ Übersetzung fehlgeschlagen."); continue
    for k, dev in subset.items():
        v = tr.get(k)
        tgt[k] = v if (isinstance(v,str) and ph(dev)==ph(v)) else dev
    json.dump(tgt, open(path,'w',encoding='utf-8'), ensure_ascii=False, indent=2)
    json.load(open(path, encoding='utf-8'))  # validate
    print(f"  [{L}] ✓")
print("  Fertig.")
PYEOF

echo ""
echo "============================================================"
echo "✅ update_help fertig. Jetzt Build."
echo "============================================================"

