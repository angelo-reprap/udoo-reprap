#!/bin/bash
# ============================================================
# record_04_softphone_ui.sh
# ABpE Call Recording — Etappe 2/3 Frontend (Softphone)
# (1) Nach stopRecording() -> Sync-Endpoint (mit CRM-ID des offenen Reiters)
# (2) Aufnahmen-Akkordeon im Kontakt-Reiter (app_cc_detail.js) + <audio>-Player
# (3) CSS + de-i18n (Übersetzung der 11 Sprachen kommt FINAL)
# KEIN Build — das macht Angelo am Ende (electron-builder).
# ============================================================
set -e
cd /opt/abpe/backend/apps/abpe_crm/static/softphone-electron

R=renderer
echo "=== [1/6] Backups ==="
cd /opt/abpe/backend
for f in renderer/app.js renderer/app_cc_detail.js renderer/app.css; do
  python3 Archiv/backup_restore.py -save "apps/abpe_crm/static/softphone-electron/$f" -m "record_04: vor recording-ui" >/dev/null
done
echo "  Backups ok"
cd apps/abpe_crm/static/softphone-electron

echo "=== [2/6] App-Anbindung: nach stopRecording Sync aufrufen ==="
python3 - << 'PYEOF'
p = 'renderer/app.js'
s = open(p, encoding='utf-8').read()
if 'recordingSyncAfterStop' in s:
    print("  schon vorhanden — übersprungen.")
else:
    # Im stopRecording-Zweig nach Erfolg den Sync triggern.
    OLD = """      window.electronAPI.amiStopRecording(ch.channel)
        .then(r => {
          _recordingActive = false;
          showNotice(r.success ? '✓ ' + t('record_stopped','Aufnahme beendet') : '✗');
          window.electronAPI.amiGetStatus().then(d => { if (d.extensions) _renderExtensions(d.extensions); });
        })
        .catch(e => console.warn(e));"""
    NEW = """      const _recFile = _recordingFile;
      const _recCid  = ch.callerid || '';
      window.electronAPI.amiStopRecording(ch.channel)
        .then(r => {
          _recordingActive = false;
          showNotice(r.success ? '✓ ' + t('record_stopped','Aufnahme beendet') : '✗');
          window.electronAPI.amiGetStatus().then(d => { if (d.extensions) _renderExtensions(d.extensions); });
          if (r.success && _recFile) recordingSyncAfterStop(_recFile, ext, _recCid);
        })
        .catch(e => console.warn(e));"""
    assert s.count(OLD) == 1, f"stopRec-Anker {s.count(OLD)}x"
    s = s.replace(OLD, NEW)

    # Sync-Funktion ergänzen (gibt CRM-ID des offenen Reiters mit -> Auto-Zuordnung)
    func = '''

// Nach Aufnahme-Stop: WAV von PBX zu Django syncen. Wenn ein Kontakt-Reiter offen
// ist, dessen crm_id mitgeben -> direkte Zuordnung der Aufnahme.
function recordingSyncAfterStop(pbxFile, extension, callerid) {
  const body = { pbx_path: pbxFile, extension: extension || '', callerid: callerid || '' };
  // Offener Reiter? -> direkte Zuordnung
  if (typeof _kontaktCurrent !== 'undefined' && _kontaktCurrent && _kontaktCurrent.crm_id) {
    if (_kontaktCurrent.module === 'Accounts') body.account_crm_id = _kontaktCurrent.crm_id;
    else body.contact_crm_id = _kontaktCurrent.crm_id;
  }
  apiFetch(`${CFG.portalUrl}/crm/api/recording/sync/`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  }).then(r => r.json()).then(d => {
    if (d && d.ok) {
      showNotice('✓ ' + t('record_synced','Aufnahme gespeichert') + (d.assigned ? '' : ' (' + t('record_unassigned','nicht zugeordnet') + ')'));
      // Wenn Reiter offen + zugeordnet -> Reiter neu laden (Aufnahme erscheint)
      if (typeof CCDetail !== 'undefined' && _kontaktCurrent && _kontaktCurrent.crm_id) CCDetail.reload();
    } else {
      showNotice('✗ ' + t('record_sync_err','Sync fehlgeschlagen'));
    }
  }).catch(e => console.warn('recording sync', e));
}
'''
    # ans Ende von app.js (vor evtl. window-Exports am Ende ist egal — Funktionsdeklaration)
    s = s.rstrip() + '\n' + func + '\n'
    open(p, 'w', encoding='utf-8').write(s)
    print("  stopRecording -> recordingSyncAfterStop verdrahtet.")
PYEOF
node --check renderer/app.js && echo "  app.js OK"

echo "=== [3/6] sync-body um account/contact erweitern (Backend nimmt das schon) ==="
python3 - << 'PYEOF'
# views_recording _api_sync nimmt aktuell nur filename/extension/callerid.
# Erweitern, damit contact_crm_id/account_crm_id aus dem Body die Zuordnung setzen.
p = '/opt/abpe/backend/apps/abpe_crm/views_recording.py'
s = open(p, encoding='utf-8').read()
if 'data.get(\'contact_crm_id\')' in s:
    print("  schon erweitert — übersprungen.")
else:
    OLD = """    from apps.abpe_crm.services.recording_sync import sync_recording
    try:
        result = sync_recording(remote, extension=data.get('extension'), callerid=data.get('callerid'))"""
    NEW = """    from apps.abpe_crm.services.recording_sync import sync_recording
    try:
        result = sync_recording(
            remote, extension=data.get('extension'), callerid=data.get('callerid'),
            contact_crm_id=data.get('contact_crm_id'), account_crm_id=data.get('account_crm_id'),
        )"""
    assert s.count(OLD) == 1, f"sync-call-Anker {s.count(OLD)}x"
    s = s.replace(OLD, NEW)
    open(p, 'w', encoding='utf-8').write(s)
    print("  _api_sync gibt contact/account weiter.")
PYEOF

# sync_recording-Signatur erweitern
python3 - << 'PYEOF'
p = '/opt/abpe/backend/apps/abpe_crm/services/recording_sync.py'
s = open(p, encoding='utf-8').read()
if 'contact_crm_id=None, account_crm_id=None' in s:
    print("  Signatur schon erweitert — übersprungen.")
else:
    OLD = "def sync_recording(remote_path, extension=None, callerid=None):"
    NEW = "def sync_recording(remote_path, extension=None, callerid=None, contact_crm_id=None, account_crm_id=None):"
    assert s.count(OLD) == 1
    s = s.replace(OLD, NEW)
    # Vorrang: explizite IDs vor CallerID-Auflösung
    OLD2 = """    # Auto-Zuordnung via CallerID
    contact_crm_id = None
    account_crm_id = None
    caller_number = callerid or None"""
    NEW2 = """    # Zuordnung: explizite IDs (offener Reiter) haben Vorrang, sonst CallerID-Auflösung
    caller_number = callerid or None
    if not contact_crm_id and not account_crm_id and caller_number:"""
    assert s.count(OLD2) == 1
    s = s.replace(OLD2, NEW2)
    # den folgenden if-Block einrücken-kompatibel machen: alte "if caller_number:" entfernen
    OLD3 = """    if not contact_crm_id and not account_crm_id and caller_number:
        from apps.abpe_crm.services.normalize_phone_nr import normalize_phone
        norm = normalize_phone(caller_number)
        rel = CrmPhoneBeanRel.objects.filter(phone__phone_norm=norm).select_related('phone').first()
        if rel:"""
    # Der Originalcode hatte "if caller_number:" zwischendrin — wir prüfen, ob er noch da ist
    if "if caller_number:\n" in s:
        s = s.replace("    if caller_number:\n        from apps.abpe_crm.services.normalize_phone_nr import normalize_phone",
                      "        from apps.abpe_crm.services.normalize_phone_nr import normalize_phone")
        # restliche Zeilen des Blocks um 4 Spaces tiefer? -> sie waren schon unter if caller_number (8 spaces). Passt.
    open(p, 'w', encoding='utf-8').write(s)
    print("  sync_recording: explizite IDs mit Vorrang.")
PYEOF
python3 -c "import ast; ast.parse(open('/opt/abpe/backend/apps/abpe_crm/services/recording_sync.py').read()); print('  recording_sync.py OK')"
python3 -c "import ast; ast.parse(open('/opt/abpe/backend/apps/abpe_crm/views_recording.py').read()); print('  views_recording.py OK')"

echo "=== [4/6] Aufnahmen-Render im Modul (app_cc_detail.js) ==="
python3 - << 'PYEOF'
p = 'renderer/app_cc_detail.js'
s = open(p, encoding='utf-8').read()
if 'CCDetail.renderAufnahmen' in s:
    print("  schon vorhanden — übersprungen.")
else:
    func = '''

/* ── Aufnahmen (read-only Liste + <audio>-Player) ───────── */
CCDetail.renderAufnahmen = function(d) {
  const id = d.crm_id;
  const wrapId = 'cc_rec_' + id;
  setTimeout(() => CCDetail.loadAufnahmen(id, wrapId), 30);
  return `<div id="${wrapId}"><div class="cc-empty">${t('loading','Lade...')}</div></div>`;
};

CCDetail.loadAufnahmen = async function(crmId, wrapId) {
  const wrap = document.getElementById(wrapId);
  if (!wrap) return;
  try {
    const resp = await apiFetch(`${CFG.portalUrl}/crm/api/recording/contact/${encodeURIComponent(crmId)}/`);
    if (!resp.ok) { wrap.innerHTML = `<div class="cc-empty">${t('rec_err','Aufnahmen nicht ladbar')}</div>`; return; }
    const data = await resp.json();
    const rows = data.recordings || [];
    if (!rows.length) { wrap.innerHTML = `<div class="cc-empty">${t('rec_none','Keine Aufnahmen')}</div>`; return; }
    wrap.innerHTML = rows.map(r => {
      const dt = (r.recorded_at||'').replace('T',' ').substring(0,16);
      const dur = r.duration_sec ? Math.floor(r.duration_sec/60)+':'+String(r.duration_sec%60).padStart(2,'0') : '';
      const audioUrl = `${CFG.portalUrl}/crm/api/recording/${r.id}/audio/`;
      return `<div class="cc-rec-item">
        <div class="cc-rec-head">
          <i class="bi bi-record-circle cc-rec-ico"></i>
          <div style="flex:1;min-width:0">
            <div class="cc-rec-meta">${dt}${dur?' · '+dur:''} · ${t('rec_ext','Durchwahl')} ${CCDetail.esc(r.extension)}</div>
            ${r.subject?`<div class="cc-rec-subj">${CCDetail.esc(r.subject)}</div>`:''}
          </div>
          <button class="cc-mini cc-del" onclick="CCDetail.deleteAufnahme(${r.id})" title="${t('rec_delete','Löschen')}"><i class="bi bi-trash3"></i></button>
        </div>
        <audio controls preload="none" style="width:100%;height:32px;margin-top:4px">
          <source src="${audioUrl}" type="audio/wav">
        </audio>
      </div>`;
    }).join('');
  } catch(e) {
    wrap.innerHTML = `<div class="cc-empty">${t('rec_err','Aufnahmen nicht ladbar')}</div>`;
  }
};

CCDetail.deleteAufnahme = async function(recId) {
  if (!confirm(t('rec_del_confirm','Aufnahme löschen? (PBX-Original bleibt erhalten)'))) return;
  const resp = await apiFetch(`${CFG.portalUrl}/crm/api/recording/${recId}/delete/`, { method:'POST', headers:{'Content-Type':'application/json'}, body:'{}' });
  const r = await resp.json();
  if (r && r.ok) CCDetail.reload();
};
'''
    s = s.rstrip() + '\n' + func + '\n'
    open(p, 'w', encoding='utf-8').write(s)
    print("  renderAufnahmen + loadAufnahmen + deleteAufnahme angehängt.")
PYEOF
node --check renderer/app_cc_detail.js && echo "  app_cc_detail.js OK"

echo "=== [5/6] Aufnahmen-Akkordeon in _renderBeraterBody + _renderFirmaBody ==="
python3 - << 'PYEOF'
p = 'renderer/app.js'
s = open(p, encoding='utf-8').read()
changed = 0
# Berater: nach Dokumente, vor Verlauf
OLD_B = "  const doks    = _kAcc('bi-file-text',    t('kontakt_acc_dokumente','Dokumente'), CCDetail.renderDokumente(d), false);\n  const verlaufId = 'kverlauf-' + (d.crm_id || 'x');"
if "renderAufnahmen(d), false);\n  const verlaufId = 'kverlauf-'" not in s and OLD_B in s:
    NEW_B = "  const doks    = _kAcc('bi-file-text',    t('kontakt_acc_dokumente','Dokumente'), CCDetail.renderDokumente(d), false);\n  const aufn    = _kAcc('bi-record-circle', t('kontakt_acc_aufnahmen','Aufnahmen'), CCDetail.renderAufnahmen(d), false);\n  const verlaufId = 'kverlauf-' + (d.crm_id || 'x');"
    s = s.replace(OLD_B, NEW_B); changed += 1
# Berater return: aufn einfügen
OLD_BR = "  return notizen + stamm + profil + doks + verlauf;"
if OLD_BR in s:
    s = s.replace(OLD_BR, "  return notizen + stamm + profil + doks + aufn + verlauf;"); changed += 1
# Firma: nach Dokumente, vor Verlauf
OLD_F = "  const doks    = _kAcc('bi-file-text',    t('kontakt_acc_dokumente','Dokumente'), CCDetail.renderDokumente(d), false);\n  const verlaufId = 'kverlauf-acc-' + (d.crm_id || 'x');"
if OLD_F in s:
    NEW_F = "  const doks    = _kAcc('bi-file-text',    t('kontakt_acc_dokumente','Dokumente'), CCDetail.renderDokumente(d), false);\n  const aufnA   = _kAcc('bi-record-circle', t('kontakt_acc_aufnahmen','Aufnahmen'), CCDetail.renderAufnahmen(d), false);\n  const verlaufId = 'kverlauf-acc-' + (d.crm_id || 'x');"
    s = s.replace(OLD_F, NEW_F); changed += 1
OLD_FR = "  return notizen + stamm + aps + anfr + doks + verlauf;"
if OLD_FR in s:
    s = s.replace(OLD_FR, "  return notizen + stamm + aps + anfr + doks + aufnA + verlauf;"); changed += 1
open(p, 'w', encoding='utf-8').write(s)
print(f"  Aufnahmen-Akkordeon eingefügt ({changed} Stellen).")
PYEOF
node --check renderer/app.js && echo "  app.js OK"

echo "=== [6/6] CSS + de-i18n ==="
python3 - << 'PYEOF'
p = 'renderer/app.css'
s = open(p, encoding='utf-8').read()
if '.cc-rec-item' not in s:
    s = s.rstrip() + """
/* ── CCDetail: Aufnahmen ── */
.cc-rec-item { padding: 8px 6px; border-bottom: 1px solid var(--border); }
.cc-rec-head { display: flex; align-items: center; gap: 8px; }
.cc-rec-ico { color: var(--red); font-size: 14px; flex-shrink: 0; }
.cc-rec-meta { font-size: 11px; color: var(--text); }
.cc-rec-subj { font-size: 10px; color: var(--muted); margin-top: 1px; }
""" + "\n"
    open(p, 'w', encoding='utf-8').write(s)
    print("  CSS ergänzt.")
else:
    print("  CSS schon da.")
PYEOF

python3 - << 'PYEOF'
import json
from collections import OrderedDict
p = 'renderer/i18n/de_phone.json'
d = json.load(open(p, encoding='utf-8'), object_pairs_hook=OrderedDict)
keys = {
  'kontakt_acc_aufnahmen':'Aufnahmen',
  'record_synced':'Aufnahme gespeichert','record_unassigned':'nicht zugeordnet',
  'record_sync_err':'Sync fehlgeschlagen',
  'rec_err':'Aufnahmen nicht ladbar','rec_none':'Keine Aufnahmen',
  'rec_ext':'Durchwahl','rec_delete':'Löschen',
  'rec_del_confirm':'Aufnahme löschen? (PBX-Original bleibt erhalten)',
}
for k,v in keys.items(): d[k]=v
json.dump(d, open(p,'w',encoding='utf-8'), ensure_ascii=False, indent=2)
print(f"  {len(keys)} de-i18n-Keys (Übersetzung 11 Sprachen kommt FINAL).")
PYEOF
python3 -c "import json; json.load(open('renderer/i18n/de_phone.json')); print('  JSON valid')"

cd /opt/abpe/backend
python manage.py check 2>&1 | tail -2

echo ""
echo "============================================================"
echo "✅ record_04 fertig (Softphone-UI + App-Anbindung)."
echo ""
echo "JETZT BUILD (manuell, wie gewohnt):"
echo "  cd apps/abpe_crm/static/softphone-electron"
echo "  # version in package.json hoch (z.B. 1.0.12)"
echo "  ./node_modules/.bin/electron-builder --win --x64"
echo "  cd /opt/abpe/backend && python manage.py collectstatic --noinput"
echo ""
echo "MERKER: Softphone-i18n nur DE — 11 Sprachen final übersetzen!"
echo "============================================================"

