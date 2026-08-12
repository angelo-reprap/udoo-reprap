#!/bin/bash
# ============================================================
# record_05_betreff_owner_dauer.sh
# ABpE Call Recording — Etappe 3 (final Softphone)
# (4) Dauer aus WAV-Header beim Sync + Nachtrag bestehende
# (Besitzer) Softphone-Besitzer-Contact in Settings/Telefonie
# (1) Nicht-zugeordnet-UI + Sofort-Betreff-Dialog nach Stop
# REGEL: is_assigned=True NUR mit (Contact/Account) UND subject!
# KEIN Build — macht Angelo final.
# ============================================================
set -e
cd /opt/abpe/backend

echo "=== [1/8] Backups ==="
for f in apps/abpe_crm/services/recording_sync.py apps/abpe_crm/views_recording.py; do
  python3 Archiv/backup_restore.py -save "$f" -m "record_05: betreff-pflicht+dauer" >/dev/null
done
SP=apps/abpe_crm/static/softphone-electron
for f in renderer/app.js renderer/app_cc_detail.js renderer/app.css renderer/app.html; do
  python3 Archiv/backup_restore.py -save "$SP/$f" -m "record_05: betreff+owner ui" >/dev/null
done
echo "  Backups ok"

echo "=== [2/8] Dauer aus WAV-Header beim Sync (recording_sync.py) ==="
python3 - << 'PYEOF'
p = 'apps/abpe_crm/services/recording_sync.py'
s = open(p, encoding='utf-8').read()
if '_wav_duration' in s:
    print("  schon vorhanden — übersprungen.")
else:
    # Hilfsfunktion am Dateianfang nach den Imports
    helper = '''

def _wav_duration(path):
    """Dauer einer WAV in Sekunden (aus Header). None bei Fehler."""
    try:
        import wave
        with wave.open(path, 'rb') as w:
            fr = w.getframerate()
            if fr:
                return int(round(w.getnframes() / float(fr)))
    except Exception:
        pass
    return None
'''
    anchor = "PBX_MONITOR_BASE = '/var/spool/asterisk/monitor'"
    assert s.count(anchor) == 1
    s = s.replace(anchor, anchor + '\n' + helper)

    # Beim create() duration_sec mitgeben
    OLD = "        file_size=local_size,\n        synced_at=timezone.now(),"
    NEW = "        file_size=local_size,\n        duration_sec=_wav_duration(local_path),\n        synced_at=timezone.now(),"
    assert s.count(OLD) == 1, f"create-Anker {s.count(OLD)}x"
    s = s.replace(OLD, NEW)

    # REGEL verschärfen: is_assigned nur mit subject — sync setzt KEIN subject,
    # also ist eine frisch gesyncte Aufnahme NIE komplett 'assigned' allein durch Contact.
    # Wir führen 'has_contact' separat, is_assigned bleibt False bis Betreff da ist.
    OLD2 = "        is_assigned=bool(contact_crm_id or account_crm_id),"
    NEW2 = "        is_assigned=False,  # erst True wenn Contact UND Betreff (siehe assign)"
    assert s.count(OLD2) == 1
    s = s.replace(OLD2, NEW2)
    open(p, 'w', encoding='utf-8').write(s)
    print("  Dauer + Regelverschärfung (is_assigned erst mit Betreff).")
PYEOF
python3 -c "import ast; ast.parse(open('apps/abpe_crm/services/recording_sync.py').read()); print('  recording_sync.py OK')"

echo "=== [3/8] Nachtrag-Dauer für bestehende Aufnahmen ==="
python manage.py shell << 'PYEOF' 2>&1 | grep -E "Nachtrag|OK|Fehler" || true
import wave, os
from apps.abpe_crm.models import CrmCallRecording
n = 0
for r in CrmCallRecording.objects.filter(duration_sec__isnull=True):
    if r.local_path and os.path.exists(r.local_path):
        try:
            with wave.open(r.local_path,'rb') as w:
                fr=w.getframerate()
                if fr: r.duration_sec=int(round(w.getnframes()/float(fr))); r.save(); n+=1
        except Exception as e:
            print("Fehler", r.id, e)
print(f"Nachtrag: {n} Aufnahmen mit Dauer ergänzt. OK")
PYEOF

echo "=== [4/8] assign-Regel: is_assigned NUR mit (Contact/Account) UND subject ==="
python3 - << 'PYEOF'
p = 'apps/abpe_crm/views_recording.py'
s = open(p, encoding='utf-8').read()
OLD = "    rec.is_assigned = bool(rec.contact_crm_id or rec.account_crm_id)\n    rec.save()\n    return JsonResponse({'ok': True, 'id': rec.id, 'is_assigned': rec.is_assigned})"
if 'subject_required' in s:
    print("  schon angepasst — übersprungen.")
else:
    NEW = """    # REGEL: vollständig zugeordnet nur mit Contact/Account UND Betreff
    has_target = bool(rec.contact_crm_id or rec.account_crm_id)
    has_subject = bool(rec.subject and rec.subject.strip())
    if has_target and not has_subject:
        return JsonResponse({'ok': False, 'error': 'subject_required',
                             'msg': 'Betreff/Grund ist Pflicht'}, status=400)
    rec.is_assigned = bool(has_target and has_subject)
    rec.save()
    return JsonResponse({'ok': True, 'id': rec.id, 'is_assigned': rec.is_assigned})"""
    assert s.count(OLD) == 1, f"assign-Anker {s.count(OLD)}x"
    s = s.replace(OLD, NEW)
    open(p, 'w', encoding='utf-8').write(s)
    print("  assign: Betreff-Pflicht erzwungen.")
PYEOF
python3 -c "import ast; ast.parse(open('apps/abpe_crm/views_recording.py').read()); print('  views_recording.py OK')"

echo "=== [5/8] _row um has_target/needs_subject erweitern (für UI-Hinweis) ==="
python3 - << 'PYEOF'
p = 'apps/abpe_crm/views_recording.py'
s = open(p, encoding='utf-8').read()
if "'needs_subject'" in s:
    print("  schon da — übersprungen.")
else:
    OLD = "        'is_assigned': r.is_assigned, 'is_private': r.is_private,"
    NEW = """        'is_assigned': r.is_assigned, 'is_private': r.is_private,
        'has_target': bool(r.contact_crm_id or r.account_crm_id),
        'needs_subject': bool((r.contact_crm_id or r.account_crm_id) and not (r.subject or '').strip()),"""
    assert s.count(OLD) == 1
    s = s.replace(OLD, NEW)
    open(p, 'w', encoding='utf-8').write(s)
    print("  _row erweitert.")
PYEOF

echo "=== [6/8] unassigned-Endpoint: auch 'Betreff fehlt' einschließen ==="
python3 - << 'PYEOF'
p = 'apps/abpe_crm/views_recording.py'
s = open(p, encoding='utf-8').read()
OLD = "    qs = CrmCallRecording.objects.filter(is_assigned=False, is_private=False).order_by('-recorded_at')"
if 'unvollständig' in s or '_already_patched_unassigned' in s:
    print("  schon angepasst — übersprungen.")
else:
    # is_assigned=False fängt jetzt automatisch auch 'Contact aber kein Betreff' (da is_assigned erst mit Betreff True wird)
    NEW = "    # is_assigned=False umfasst: gar nicht zugeordnet UND zugeordnet-aber-Betreff-fehlt\n    qs = CrmCallRecording.objects.filter(is_assigned=False, is_private=False).order_by('-recorded_at')  # _already_patched_unassigned"
    assert s.count(OLD) == 1
    s = s.replace(OLD, NEW)
    open(p, 'w', encoding='utf-8').write(s)
    print("  unassigned umfasst jetzt auch Betreff-fehlt-Fälle.")
PYEOF
python3 -c "import ast; ast.parse(open('apps/abpe_crm/views_recording.py').read()); print('  views_recording.py OK')"

cd "$SP"

echo "=== [7/8] Frontend: Besitzer-Feld + Betreff-Dialog + Nicht-zugeordnet-UI ==="
python3 - << 'PYEOF'
p = 'renderer/app.js'
s = open(p, encoding='utf-8').read()
done = []

# (A) recordingSyncAfterStop: nach Sync IMMER Betreff-Dialog (auch wenn Contact da)
if 'recordingBetreffDialog' not in s:
    OLD = """    if (d && d.ok) {
      showNotice('✓ ' + t('record_synced','Aufnahme gespeichert') + (d.assigned ? '' : ' (' + t('record_unassigned','nicht zugeordnet') + ')'));
      // Wenn Reiter offen + zugeordnet -> Reiter neu laden (Aufnahme erscheint)
      if (typeof CCDetail !== 'undefined' && _kontaktCurrent && _kontaktCurrent.crm_id) CCDetail.reload();
    } else {"""
    NEW = """    if (d && d.ok) {
      showNotice('✓ ' + t('record_synced','Aufnahme gespeichert'));
      // Betreff ist PFLICHT — Dialog immer zeigen (Contact ggf. schon gesetzt)
      recordingBetreffDialog(d.id, body.contact_crm_id || body.account_crm_id || null);
    } else {"""
    assert s.count(OLD) == 1, "syncAfterStop-Anker"
    s = s.replace(OLD, NEW)
    done.append("syncAfterStop->Betreff-Dialog")

# (B) Betreff-Dialog + Nicht-zugeordnet-Funktionen anhängen
if 'recordingBetreffDialog' not in s:
    block = r'''

// ============================================================
// CALL RECORDING — Betreff-Pflicht-Dialog + Zuordnung
// ============================================================
function recordingBetreffDialog(recId, presetContactId) {
  const ov = document.createElement('div');
  ov.id = 'rec-betreff-ov';
  ov.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:99999;display:flex;align-items:center;justify-content:center';
  const ownerName = CFG.ownerContactName || '';
  ov.innerHTML = `
    <div style="background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:16px;min-width:300px;max-width:94vw;box-shadow:0 10px 40px rgba(0,0,0,.5)">
      <div style="font-size:14px;font-weight:700;color:var(--text);margin-bottom:4px"><i class="bi bi-record-circle" style="color:var(--red)"></i> ${t('rec_subject_title','Aufnahme — Betreff erfassen')}</div>
      <div style="font-size:11px;color:var(--muted);margin-bottom:12px">${t('rec_subject_hint','Pflicht: Wer, warum wurde aufgezeichnet?')}</div>
      <input id="rec_subj_in" type="text" placeholder="${t('rec_subject_ph','z.B. Projektabstimmung mit Kunde, Einwilligung erteilt')}" style="width:100%;box-sizing:border-box;font-size:13px;padding:8px;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text);margin-bottom:10px">
      <div id="rec_assign_box" style="margin-bottom:10px"></div>
      <div style="display:flex;gap:6px">
        <button id="rec_subj_save" style="flex:1;background:var(--green);color:#fff;border:none;border-radius:6px;padding:9px;font-size:13px;cursor:pointer"><i class="bi bi-check-lg"></i> ${t('rec_subject_save','Speichern')}</button>
      </div>
      <div style="font-size:10px;color:var(--muted);margin-top:8px;text-align:center">${t('rec_subject_nodismiss','Ohne Betreff bleibt die Aufnahme nicht zugeordnet')}</div>
    </div>`;
  document.body.appendChild(ov);

  // Zuordnungs-Anzeige: entweder schon Contact, oder "Mir zuordnen" + Suche
  const box = ov.querySelector('#rec_assign_box');
  let chosenContact = presetContactId || null;
  let chosenName = '';
  function renderBox() {
    if (chosenContact) {
      box.innerHTML = `<div style="font-size:12px;color:var(--text);padding:6px 8px;background:var(--card);border-radius:6px;border:1px solid var(--green)"><i class="bi bi-person-check"></i> ${esc(chosenName || t('rec_assigned_already','zugeordnet'))} <a href="#" id="rec_unassign" style="float:right;color:var(--muted)">${t('change','ändern')}</a></div>`;
      const u = box.querySelector('#rec_unassign'); if (u) u.onclick = (e)=>{e.preventDefault();chosenContact=null;renderBox();};
    } else {
      box.innerHTML = `
        <div style="display:flex;gap:6px;margin-bottom:6px">
          <button id="rec_assign_me" style="flex:1;background:var(--card);border:1px solid var(--accent);color:var(--text);border-radius:6px;padding:7px;font-size:12px;cursor:pointer"><i class="bi bi-person-fill"></i> ${t('rec_assign_me','Mir zuordnen')}${CFG.ownerContactName?(' ('+esc(CFG.ownerContactName)+')'):''}</button>
        </div>
        <input id="rec_csearch" type="text" placeholder="${t('rec_search_contact','Anderen Kontakt suchen...')}" style="width:100%;box-sizing:border-box;font-size:12px;padding:6px;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text)">
        <div id="rec_cresults" style="max-height:140px;overflow:auto;margin-top:4px"></div>`;
      const me = box.querySelector('#rec_assign_me');
      if (me) me.onclick = () => { if(!CFG.ownerContactId){showNotice(t('rec_no_owner','Kein Besitzer gesetzt (Einstellungen→Telefonie)'));return;} chosenContact=CFG.ownerContactId; chosenName=CFG.ownerContactName||''; renderBox(); };
      const si = box.querySelector('#rec_csearch');
      if (si) si.oninput = _recDebounceSearch;
    }
  }
  let _recT=null;
  function _recDebounceSearch(e){ clearTimeout(_recT); const q=e.target.value.trim(); const rb=ov.querySelector('#rec_cresults'); if(q.length<2){rb.innerHTML='';return;} _recT=setTimeout(async()=>{
    try{ const resp=await apiFetch(`${CFG.portalUrl}/crm/api/berater/?q=${encodeURIComponent(q)}&per_page=8&typ=alle`); const d=await resp.json(); const rows=d.results||d.contacts||d.data||[];
      rb.innerHTML = rows.map(c=>`<div class="rec-cres" data-id="${c.crm_id}" data-name="${esc((c.full_name||((c.first_name||'')+' '+(c.last_name||''))).trim())}" style="padding:6px 8px;font-size:12px;cursor:pointer;border-radius:5px">${esc((c.full_name||((c.first_name||'')+' '+(c.last_name||''))).trim())}${c.account_name?` <span style="color:var(--muted)">· ${esc(c.account_name)}</span>`:''}</div>`).join('')||`<div style="font-size:11px;color:var(--muted);padding:4px">${t('no_results','keine Treffer')}</div>`;
      rb.querySelectorAll('.rec-cres').forEach(el=>el.onclick=()=>{chosenContact=el.dataset.id;chosenName=el.dataset.name;renderBox();});
    }catch(err){console.warn(err);}
  },250); }
  renderBox();

  ov.querySelector('#rec_subj_save').onclick = async () => {
    const subj = (ov.querySelector('#rec_subj_in').value||'').trim();
    if (!subj) { ov.querySelector('#rec_subj_in').style.borderColor='var(--red)'; showNotice(t('rec_subject_required','Betreff ist Pflicht!')); return; }
    if (!chosenContact) { showNotice(t('rec_target_required','Bitte zuordnen (Mir / Kontakt)')); return; }
    const payload = { subject: subj, contact_crm_id: chosenContact };
    try {
      const resp = await apiFetch(`${CFG.portalUrl}/crm/api/recording/${recId}/assign/`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
      const r = await resp.json();
      if (r && r.ok) { ov.remove(); showNotice('✓ ' + t('rec_saved','Aufnahme zugeordnet')); if(typeof CCDetail!=='undefined'&&_kontaktCurrent&&_kontaktCurrent.crm_id)CCDetail.reload(); }
      else showNotice('✗ ' + (r.msg||t('error','Fehler')));
    } catch(e){ console.warn(e); showNotice('✗ '+t('error','Fehler')); }
  };
}
'''
    s = s.rstrip() + '\n' + block + '\n'
    done.append("Betreff-Dialog+Zuordnung")

# (C) Besitzer-Feld speichern (saveOwnerContact)
if 'saveOwnerContact' not in s:
    ownerfn = r'''

// Softphone-Besitzer (Mein CRM-Kontakt) — pro Installation, in CFG
async function saveOwnerContact(crmId, name) {
  CFG.ownerContactId = crmId || '';
  CFG.ownerContactName = name || '';
  await window.electronAPI.saveConfig(CFG);
  showNotice('✓ ' + t('rec_owner_saved','Besitzer gespeichert') + (name?(': '+name):''));
  const lbl = document.getElementById('cfgOwnerLabel');
  if (lbl) lbl.textContent = name || t('rec_owner_none','nicht gesetzt');
}
function ownerContactSearch(q) {
  const rb = document.getElementById('cfgOwnerResults');
  if (!rb) return;
  if ((q||'').trim().length < 2) { rb.innerHTML=''; return; }
  clearTimeout(window._ownerT);
  window._ownerT = setTimeout(async()=>{
    try{ const resp=await apiFetch(`${CFG.portalUrl}/crm/api/berater/?q=${encodeURIComponent(q)}&per_page=8&typ=alle`); const d=await resp.json(); const rows=d.results||d.contacts||d.data||[];
      rb.innerHTML = rows.map(c=>{const nm=(c.full_name||((c.first_name||'')+' '+(c.last_name||''))).trim();return `<div class="owner-res" data-id="${c.crm_id}" data-name="${esc(nm)}" style="padding:6px 8px;font-size:12px;cursor:pointer;border-radius:5px;border-bottom:1px solid var(--border)">${esc(nm)}${c.account_name?` <span style="color:var(--muted)">· ${esc(c.account_name)}</span>`:''}</div>`;}).join('')||`<div style="font-size:11px;color:var(--muted);padding:4px">${t('no_results','keine Treffer')}</div>`;
      rb.querySelectorAll('.owner-res').forEach(el=>el.onclick=()=>{ saveOwnerContact(el.dataset.id, el.dataset.name); rb.innerHTML=''; const si=document.getElementById('cfgOwnerSearch'); if(si)si.value=el.dataset.name; });
    }catch(e){console.warn(e);}
  },250);
}
'''
    s = s.rstrip() + '\n' + ownerfn + '\n'
    done.append("Besitzer-Funktionen")

# (D) Besitzer-Label beim Settings-Laden füllen
if "_setVal('cfgExtNames'" in s and 'cfgOwnerLabel' not in s.split("_setVal('cfgExtNames'")[0]:
    OLD = "  _setVal('cfgExtNames',     formatExtNames(CFG.extNames || {}));"
    NEW = OLD + "\n  { const _ol=document.getElementById('cfgOwnerLabel'); if(_ol)_ol.textContent=CFG.ownerContactName||t('rec_owner_none','nicht gesetzt'); }"
    if s.count(OLD)==1:
        s = s.replace(OLD, NEW); done.append("Besitzer-Label-Init")

open(p, 'w', encoding='utf-8').write(s)
print("  app.js:", ", ".join(done) if done else "nichts (schon da)")
PYEOF
node --check renderer/app.js && echo "  app.js OK"

echo "=== [8/8] Besitzer-Feld HTML (Telefonie) + CSS + i18n ==="
python3 - << 'PYEOF'
p = 'renderer/app.html'
s = open(p, encoding='utf-8').read()
if 'cfgOwnerSearch' in s:
    print("  HTML schon da - uebersprungen.")
else:
    anchor = """          </div>
        </div>
        <!-- ===== GRUPPE 4: SYSTEM ===== -->"""
    owner_block = """          </div>
        </div>
        <div class="settings-section-hdr" onclick="toggleAcc(this)">
          <i class="bi bi-person-vcard settings-section-icon"></i>
          <span class="settings-section-title" data-i18n="rec_owner_label">Mein CRM-Kontakt (Besitzer)</span>
          <span id="cfgOwnerLabel" style="margin-left:auto;margin-right:8px;font-size:12px;color:var(--muted)">nicht gesetzt</span>
          <span class="settings-section-arrow">&#9654;</span>
        </div>
        <div class="settings-section-body">
          <div class="settings-hint" data-i18n="rec_owner_hint">Aufnahmen ohne Zuordnung gehoeren diesem Kontakt.</div>
          <div class="settings-row" style="flex-direction:column;align-items:stretch;gap:6px">
            <input id="cfgOwnerSearch" type="text" placeholder="Kontakt suchen..."
              oninput="ownerContactSearch(this.value)"
              style="width:100%;box-sizing:border-box;padding:8px;font-size:13px;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text)">
            <div id="cfgOwnerResults" style="max-height:160px;overflow:auto;border-radius:6px"></div>
          </div>
        </div>
        <!-- ===== GRUPPE 4: SYSTEM ===== -->"""
    assert s.count(anchor) == 1, f"HTML-Anker {s.count(anchor)}x"
    s = s.replace(anchor, owner_block)
    open(p, 'w', encoding='utf-8').write(s)
    print("  Besitzer-Akkordeon sauber nach ext_names eingefuegt.")
PYEOF

python3 - << 'PYEOF'
# CSS Hover für Suchergebnisse
p = 'renderer/app.css'
s = open(p, encoding='utf-8').read()
if '.rec-cres:hover' not in s:
    s = s.rstrip() + """
.rec-cres:hover, .owner-res:hover { background: var(--card); }
""" + "\n"
    open(p,'w',encoding='utf-8').write(s)
    print("  CSS ok")
else:
    print("  CSS schon da")
PYEOF

python3 - << 'PYEOF'
import json
from collections import OrderedDict
p = 'renderer/i18n/de_phone.json'
d = json.load(open(p, encoding='utf-8'), object_pairs_hook=OrderedDict)
keys = {
 'rec_subject_title':'Aufnahme — Betreff erfassen',
 'rec_subject_hint':'Pflicht: Wer, warum wurde aufgezeichnet?',
 'rec_subject_ph':'z.B. Projektabstimmung, Einwilligung erteilt',
 'rec_subject_save':'Speichern','rec_subject_required':'Betreff ist Pflicht!',
 'rec_subject_nodismiss':'Ohne Betreff bleibt die Aufnahme nicht zugeordnet',
 'rec_assign_me':'Mir zuordnen','rec_search_contact':'Anderen Kontakt suchen...',
 'rec_target_required':'Bitte zuordnen (Mir / Kontakt)','rec_assigned_already':'zugeordnet',
 'rec_no_owner':'Kein Besitzer gesetzt (Einstellungen→Telefonie)',
 'rec_saved':'Aufnahme zugeordnet','rec_owner_saved':'Besitzer gespeichert',
 'rec_owner_none':'nicht gesetzt','rec_owner_label':'Mein CRM-Kontakt (Besitzer)',
 'rec_owner_hint':'Aufnahmen ohne Zuordnung gehören diesem Kontakt.',
 'change':'ändern','no_results':'keine Treffer',
}
for k,v in keys.items(): d[k]=v
json.dump(d, open(p,'w',encoding='utf-8'), ensure_ascii=False, indent=2)
print(f"  {len(keys)} de-i18n-Keys.")
PYEOF
python3 -c "import json; json.load(open('renderer/i18n/de_phone.json')); print('  JSON valid')"

cd /opt/abpe/backend
python manage.py check 2>&1 | tail -2

echo ""
echo "============================================================"
echo "✅ record_05 fertig (Betreff-Pflicht + Besitzer + Dauer)."
echo "⚠️  HTML-Einfügung des Besitzer-Felds war heuristisch —"
echo "    nach dem Build visuell prüfen (Einstellungen→Telefonie)."
echo ""
echo "DANN BUILD 1.0.12 (wie gewohnt)."
echo "============================================================"

