#!/bin/bash
# ============================================================
# settings_badges.sh — Live-Status im Settings-Header
#  - Verbindung: UA.isRegistered() -> grün "Registriert (124)" / rot
#  - AMI Host:   amiGetStatus() liefert data -> grün "Verbunden" / rot
#  Badge rechts im zugeklappten Header (wie Besitzer-Header)
# ============================================================
set -e
cd /opt/abpe/backend
SP=apps/abpe_crm/static/softphone-electron

echo "=== [1/6] Backups ==="
for f in renderer/app.html renderer/app.css renderer/app.js; do
  python3 Archiv/backup_restore.py -save "$SP/$f" -m "settings-badges" >/dev/null
done
echo "  ok"
cd "$SP"

echo "=== [2/6] Badge-Span in Verbindung-Header ==="
python3 - << 'PYEOF'
p = 'renderer/app.html'
s = open(p, encoding='utf-8').read()
OLD = '''        <div class="settings-section-hdr open" onclick="toggleAcc(this)">
          <i class="bi bi-reception-4 settings-section-icon"></i>
          <span class="settings-section-title" data-i18n="grp_connection"></span>
          <span class="settings-section-arrow">▶</span>
        </div>'''
NEW = '''        <div class="settings-section-hdr open" onclick="toggleAcc(this)">
          <i class="bi bi-reception-4 settings-section-icon"></i>
          <span class="settings-section-title" data-i18n="grp_connection"></span>
          <span class="hdr-status" id="hdrStatusConn"></span>
          <span class="settings-section-arrow">▶</span>
        </div>'''
assert s.count(OLD) == 1, f"Verbindung-Anker {s.count(OLD)}x"
s = s.replace(OLD, NEW)
open(p, 'w', encoding='utf-8').write(s)
print("  Verbindung-Badge eingefügt.")
PYEOF

echo "=== [3/6] Badge-Span in AMI-Host-Header ==="
python3 - << 'PYEOF'
p = 'renderer/app.html'
s = open(p, encoding='utf-8').read()
# AMI-Host-Header finden (grp_ami oder ami_host)
import re
# Suche den Header mit dem AMI-Title-Key
cand = None
for key in ['grp_ami', 'ami_host', 'grp_ami_host']:
    if f'data-i18n="{key}"' in s:
        cand = key; break
assert cand, "AMI-Header-Key nicht gefunden"
# Den arrow-span direkt nach dem AMI-Title um das Badge ergänzen
import re
pat = re.compile(r'(<span class="settings-section-title" data-i18n="'+re.escape(cand)+r'"></span>\s*\n\s*)(<span class="settings-section-arrow">)')
m = pat.search(s)
assert m, "AMI-Header-Struktur nicht gefunden"
s = s[:m.start()] + m.group(1) + '<span class="hdr-status" id="hdrStatusAmi"></span>\n          ' + m.group(2) + s[m.end():]
open(p, 'w', encoding='utf-8').write(s)
print(f"  AMI-Badge eingefügt (Header-Key: {cand}).")
PYEOF

echo "=== [4/6] CSS für hdr-status ==="
python3 - << 'PYEOF'
p = 'renderer/app.css'
s = open(p, encoding='utf-8').read()
if '.hdr-status' not in s:
    s = s.rstrip() + """
.hdr-status { margin-left: auto; margin-right: 8px; font-size: 10px; display: inline-flex; align-items: center; gap: 5px; color: var(--muted); white-space: nowrap; }
.hdr-status .hdr-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--muted); display: inline-block; flex-shrink: 0; }
.hdr-status.ok   .hdr-dot { background: var(--green); }
.hdr-status.bad  .hdr-dot { background: var(--red); }
.hdr-status.ok   { color: var(--green); }
.hdr-status.bad  { color: var(--muted); }
""" + "\n"
    print("  CSS ergänzt.")
else:
    print("  CSS schon da.")
open(p, 'w', encoding='utf-8').write(s)
PYEOF

echo "=== [5/6] updateSettingsBadges() + Aufrufe in app.js ==="
python3 - << 'PYEOF'
p = 'renderer/app.js'
s = open(p, encoding='utf-8').read()
if 'function updateSettingsBadges' not in s:
    func = '''

// Live-Status in den Settings-Headern (Verbindung + AMI)
function updateSettingsBadges() {
  // Verbindung: SIP registriert?
  const cEl = document.getElementById('hdrStatusConn');
  if (cEl) {
    const reg = (typeof UA !== 'undefined' && UA && typeof UA.isRegistered === 'function') ? UA.isRegistered() : false;
    cEl.className = 'hdr-status ' + (reg ? 'ok' : 'bad');
    cEl.innerHTML = '<span class="hdr-dot"></span>' + (reg ? (t('conn_test_ok','Registriert') + ' (' + (CFG.extension||'?') + ')') : t('conn_test_fail','Nicht registriert'));
  }
  // AMI: liefert amiGetStatus Daten?
  const aEl = document.getElementById('hdrStatusAmi');
  if (aEl) {
    if (typeof window.electronAPI !== 'undefined' && window.electronAPI.amiGetStatus) {
      window.electronAPI.amiGetStatus().then(data => {
        const okAmi = !!(data && (data.extensions || data.channels || data.conferences || data.parked));
        aEl.className = 'hdr-status ' + (okAmi ? 'ok' : 'bad');
        aEl.innerHTML = '<span class="hdr-dot"></span>' + (okAmi ? t('ami_connected','Verbunden') : t('ami_disconnected','Getrennt'));
      }).catch(() => {
        aEl.className = 'hdr-status bad';
        aEl.innerHTML = '<span class="hdr-dot"></span>' + t('ami_disconnected','Getrennt');
      });
    }
  }
}
'''
    s = s.rstrip() + '\n' + func + '\n'
    print("  updateSettingsBadges() ergänzt.")
else:
    print("  Funktion schon da.")

# Aufrufe einhängen: bei registered/unregistered + initial
# a) nach UA.on('registered', ...) und ('unregistered', ...)
import re
if "updateSettingsBadges()" not in s.split('function updateSettingsBadges')[0]:
    # In die registered/unregistered-Handler einhängen
    s = s.replace(
        "UA.on('registered',         () => { setStatus('', t('registered','Bereit')); window.electronAPI.setTrayStatus('online'); });",
        "UA.on('registered',         () => { setStatus('', t('registered','Bereit')); window.electronAPI.setTrayStatus('online'); updateSettingsBadges(); });", 1)
    s = s.replace(
        "UA.on('unregistered',       () => { setStatus('offline', t('not_registered')); window.electronAPI.setTrayStatus('offline'); });",
        "UA.on('unregistered',       () => { setStatus('offline', t('not_registered')); window.electronAPI.setTrayStatus('offline'); updateSettingsBadges(); });", 1)
    print("  Aufrufe in registered/unregistered eingehängt.")

open(p, 'w', encoding='utf-8').write(s)
PYEOF
node --check renderer/app.js && echo "  app.js OK"

echo "=== [6/6] i18n (ami_connected/disconnected) in 12 Sprachen ==="
python3 - << 'PYEOF'
import json, glob, os
I18N = 'renderer/i18n'
conn = {'de':'Verbunden','en':'Connected','fr':'Connecté','es':'Conectado','it':'Connesso',
 'pl':'Połączono','ru':'Подключено','ar':'متصل','zh':'已连接','pt':'Conectado','ko':'연결됨','ja':'接続済み'}
disc = {'de':'Getrennt','en':'Disconnected','fr':'Déconnecté','es':'Desconectado','it':'Disconnesso',
 'pl':'Rozłączono','ru':'Отключено','ar':'غير متصل','zh':'已断开','pt':'Desconectado','ko':'연결 끊김','ja':'切断'}
for path in glob.glob(f'{I18N}/*_phone.json'):
    L = os.path.basename(path).split('_')[0]
    if L not in conn: continue
    d = json.load(open(path, encoding='utf-8'))
    ch = False
    if 'ami_connected' not in d: d['ami_connected'] = conn[L]; ch = True
    if 'ami_disconnected' not in d: d['ami_disconnected'] = disc[L]; ch = True
    if ch: json.dump(d, open(path,'w',encoding='utf-8'), ensure_ascii=False, indent=2)
print("  ami_connected/disconnected in alle Sprachen.")
PYEOF
for L in de en fr es it pl ru ar zh pt ko ja; do
  python3 -c "import json; json.load(open('renderer/i18n/${L}_phone.json'))" || echo "FEHLER $L"
done
echo "  JSON valid"

echo ""
echo "============================================================"
echo "✅ settings_badges fertig. ERST F12-TEST, dann Build."
echo "   Test in Konsole: updateSettingsBadges()"
echo "============================================================"


