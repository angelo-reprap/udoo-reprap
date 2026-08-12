#!/bin/bash
# ============================================================
# record_07_incall_button.sh
# Aufnahme-Button in der aktiven Anrufleiste (.strip-actions)
# - 6. Button zwischen Halten und Auflegen
# - bi-record-circle -> bi-record-circle-fill + rot beim Aufnehmen
# - toggleCallRecording(): nutzt aktiven Channel (eigene Extension)
# - Stop -> recordingSyncAfterStop -> Betreff-Pflicht-Dialog (record_05)
# - Grid 5 -> 6 Spalten
# ============================================================
set -e
cd /opt/abpe/backend
SP=apps/abpe_crm/static/softphone-electron

echo "=== [1/5] Backups ==="
for f in renderer/app.html renderer/app.css renderer/app.js; do
  python3 Archiv/backup_restore.py -save "$SP/$f" -m "record_07: incall-record-button" >/dev/null
done
echo "  ok"

cd "$SP"

echo "=== [2/5] Button in die Anrufleiste (zwischen Halten und Auflegen) ==="
python3 - << 'PYEOF'
p = 'renderer/app.html'
s = open(p, encoding='utf-8').read()
if 'id="sabRecord"' in s:
    print("  schon da — übersprungen.")
else:
    anchor = """      <button class="sab danger tt" onclick="hangup()" data-tt-key="hangup">"""
    newbtn = """      <button class="sab tt" id="sabRecord" onclick="toggleCallRecording()" data-tt-key="record_toggle">
        <i class="bi bi-record-circle" id="sabRecordIcon"></i>
        <span data-i18n="record_toggle"></span>
      </button>
      <button class="sab danger tt" onclick="hangup()" data-tt-key="hangup">"""
    assert s.count(anchor) == 1, f"hangup-Anker {s.count(anchor)}x"
    s = s.replace(anchor, newbtn)
    open(p, 'w', encoding='utf-8').write(s)
    print("  Aufnahme-Button eingefügt.")
PYEOF

echo "=== [3/5] Grid 5 -> 6 Spalten + roter Aktiv-Zustand (CSS) ==="
python3 - << 'PYEOF'
p = 'renderer/app.css'
s = open(p, encoding='utf-8').read()
OLD = ".strip-actions { display: grid; grid-template-columns: repeat(5,1fr); gap: 4px; padding: 4px 10px 6px; }"
NEW = ".strip-actions { display: grid; grid-template-columns: repeat(6,1fr); gap: 4px; padding: 4px 10px 6px; }"
if OLD in s:
    s = s.replace(OLD, NEW)
    print("  Grid 5 -> 6.")
elif "repeat(6,1fr)" in s:
    print("  Grid schon 6.")
else:
    print("  ⚠ Grid-Anker nicht gefunden — bitte prüfen.")
if '#sabRecord.recording' not in s:
    s = s.rstrip() + """
#sabRecord.recording { color: var(--red); }
#sabRecord.recording .bi { color: var(--red); }
""" + "\n"
    print("  Roter Aktiv-Zustand ergänzt.")
open(p, 'w', encoding='utf-8').write(s)
PYEOF

echo "=== [4/5] toggleCallRecording() in app.js ==="
python3 - << 'PYEOF'
p = 'renderer/app.js'
s = open(p, encoding='utf-8').read()
if 'function toggleCallRecording' in s:
    print("  schon da — übersprungen.")
else:
    func = '''

// Aufnahme-Button in der aktiven Anrufleiste (nutzt eigenen aktiven Channel)
function toggleCallRecording() {
  window.electronAPI.amiGetStatus().then(data => {
    const myCh = (data.channels||[]).find(c => c.extension === CFG.extension);
    if (!myCh) { showNotice('\\u2717 ' + t('record_no_channel','Kein aktiver Kanal')); return; }
    const btn  = document.getElementById('sabRecord');
    const icon = document.getElementById('sabRecordIcon');
    if (_recordingActive) {
      const _recFile = _recordingFile;
      const _recCid  = myCh.callerid || '';
      window.electronAPI.amiStopRecording(myCh.channel).then(r => {
        _recordingActive = false;
        if (btn)  btn.classList.remove('recording');
        if (icon) icon.className = 'bi bi-record-circle';
        showNotice(r.success ? '\\u2713 ' + t('record_stopped','Aufnahme beendet') : '\\u2717');
        if (r.success && _recFile) recordingSyncAfterStop(_recFile, CFG.extension, _recCid);
      }).catch(e => console.warn(e));
    } else {
      window.electronAPI.amiStartRecording(myCh.channel).then(r => {
        _recordingActive = r.success;
        _recordingFile   = r.file || null;
        if (r.success) {
          if (btn)  btn.classList.add('recording');
          if (icon) icon.className = 'bi bi-record-circle-fill';
        }
        showNotice(r.success ? '\\u2713 ' + t('record_started','Aufnahme gestartet') : '\\u2717');
      }).catch(e => console.warn(e));
    }
  });
}
'''
    s = s.rstrip() + '\n' + func + '\n'
    open(p, 'w', encoding='utf-8').write(s)
    print("  toggleCallRecording() ergänzt.")
PYEOF
node --check renderer/app.js && echo "  app.js OK"

echo "=== [5/5] i18n (record_no_channel) in alle 12 Sprachen ==="
python3 - << 'PYEOF'
import json, glob, os
I18N = 'renderer/i18n'
texts = {
 'de':'Kein aktiver Kanal','en':'No active channel','fr':'Aucun canal actif',
 'es':'Sin canal activo','it':'Nessun canale attivo','pl':'Brak aktywnego kanału',
 'ru':'Нет активного канала','ar':'لا توجد قناة نشطة','zh':'无活动通道',
 'pt':'Nenhum canal ativo','ko':'활성 채널 없음','ja':'アクティブなチャンネルがありません',
}
for path in glob.glob(f'{I18N}/*_phone.json'):
    L = os.path.basename(path).split('_')[0]
    if L not in texts: continue
    d = json.load(open(path, encoding='utf-8'))
    if 'record_no_channel' not in d:
        d['record_no_channel'] = texts[L]
        json.dump(d, open(path,'w',encoding='utf-8'), ensure_ascii=False, indent=2)
print("  record_no_channel in alle Sprachen.")
PYEOF
for L in de en fr es it pl ru ar zh pt ko ja; do
  python3 -c "import json; json.load(open('renderer/i18n/${L}_phone.json'))" || echo "FEHLER $L"
done
echo "  alle JSON valid"

echo ""
echo "============================================================"
echo "✅ record_07 fertig (In-Call-Aufnahme-Button)."
echo "Jetzt Build 1.0.12."
echo "============================================================"

