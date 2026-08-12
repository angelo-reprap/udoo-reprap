#!/bin/bash
# ============================================================
# fix_3bugs.sh — drei Konsolen-Bugs aus 1.0.13
#  1. ownerContactSearch: esc -> CCDetail.esc (ReferenceError)
#  2. recordingBetreffDialog: fehlende Funktion ergänzen
#  3. Audio 401: <audio src> -> Blob-Load mit Token
# ============================================================
set -e
cd /opt/abpe/backend
SP=apps/abpe_crm/static/softphone-electron

echo "=== Backups (Archiv) ==="
python3 Archiv/backup_restore.py -save "$SP/renderer/app.js" -m "fix_3bugs: vor patch" >/dev/null
python3 Archiv/backup_restore.py -save "$SP/renderer/app_cc_detail.js" -m "fix_3bugs: audio-blob" >/dev/null
echo "  ok"

cd "$SP"

echo "=== [1/3] ownerContactSearch: esc -> CCDetail.esc ==="
python3 - << 'PYEOF'
p = 'renderer/app.js'
s = open(p, encoding='utf-8').read()
# Nur innerhalb ownerContactSearch: die esc(...)-Aufrufe in der map-Zeile
OLD = """rb.innerHTML = rows.map(c=>{const id=c.crm_id||c.id||'';const nm=(c.full_name||((c.first_name||'')+' '+(c.last_name||''))).trim();const comp=c.company||c.account_name||'';return `<div class="owner-res" data-id="${id}" data-name="${esc(nm)}" style="padding:6px 8px;font-size:12px;cursor:pointer;border-radius:5px;border-bottom:1px solid var(--border)">${esc(nm)}${comp?` <span style="color:var(--muted)">· ${esc(comp)}</span>`:''}</div>`;}).join('')"""
NEW = """const _e=(window.CCDetail&&CCDetail.esc)?CCDetail.esc:(x=>String(x==null?'':x).replace(/[&<>"]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m])));
      rb.innerHTML = rows.map(c=>{const id=c.crm_id||c.id||'';const nm=(c.full_name||((c.first_name||'')+' '+(c.last_name||''))).trim();const comp=c.company||c.account_name||'';return `<div class="owner-res" data-id="${id}" data-name="${_e(nm)}" style="padding:6px 8px;font-size:12px;cursor:pointer;border-radius:5px;border-bottom:1px solid var(--border)">${_e(nm)}${comp?` <span style="color:var(--muted)">· ${_e(comp)}</span>`:''}</div>`;}).join('')"""
assert s.count(OLD) == 1, f"owner-Anker {s.count(OLD)}x"
s = s.replace(OLD, NEW)
open(p, 'w', encoding='utf-8').write(s)
print("  esc -> robustes _e (CCDetail.esc oder inline).")
PYEOF

echo "=== [2/3] recordingBetreffDialog ergänzen (fehlt komplett) ==="
python3 - << 'PYEOF'
p = 'renderer/app.js'
s = open(p, encoding='utf-8').read()
if 'function recordingBetreffDialog' in s:
    print("  schon da — übersprungen.")
else:
    block = r'''

// Pflicht-Betreff-Dialog nach Aufnahme-Stop (recordingSyncAfterStop ruft das)
function recordingBetreffDialog(recId, presetContactId) {
  const _e = (window.CCDetail&&CCDetail.esc) ? CCDetail.esc : (x=>String(x==null?'':x));
  const ov = document.createElement('div');
  ov.id = 'rec-betreff-ov';
  ov.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:99999;display:flex;align-items:center;justify-content:center';
  ov.innerHTML = `
    <div style="background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:16px;min-width:300px;max-width:94vw;box-shadow:0 10px 40px rgba(0,0,0,.5)">
      <div style="font-size:14px;font-weight:700;color:var(--text);margin-bottom:4px"><i class="bi bi-record-circle" style="color:var(--red)"></i> ${t('rec_subject_title','Aufnahme - Betreff erfassen')}</div>
      <div style="font-size:11px;color:var(--muted);margin-bottom:12px">${t('rec_subject_hint','Pflicht: Wer, warum wurde aufgezeichnet?')}</div>
      <input id="rec_subj_in" type="text" placeholder="${t('rec_subject_ph','z.B. Projektabstimmung, Einwilligung erteilt')}" style="width:100%;box-sizing:border-box;font-size:13px;padding:8px;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text);margin-bottom:10px">
      <div id="rec_assign_box" style="margin-bottom:10px"></div>
      <button id="rec_subj_save" style="width:100%;background:var(--green);color:#fff;border:none;border-radius:6px;padding:9px;font-size:13px;cursor:pointer"><i class="bi bi-check-lg"></i> ${t('rec_subject_save','Speichern')}</button>
      <div style="font-size:10px;color:var(--muted);margin-top:8px;text-align:center">${t('rec_subject_nodismiss','Ohne Betreff bleibt die Aufnahme nicht zugeordnet')}</div>
    </div>`;
  document.body.appendChild(ov);

  const box = ov.querySelector('#rec_assign_box');
  let chosenContact = presetContactId || null;
  let chosenName = '';
  function renderBox() {
    if (chosenContact) {
      box.innerHTML = `<div style="font-size:12px;color:var(--text);padding:6px 8px;background:var(--card);border-radius:6px;border:1px solid var(--green)"><i class="bi bi-person-check"></i> ${_e(chosenName || t('rec_assigned_already','zugeordnet'))} <a href="#" id="rec_unassign" style="float:right;color:var(--muted)">${t('change','aendern')}</a></div>`;
      const u = box.querySelector('#rec_unassign'); if (u) u.onclick = (e)=>{e.preventDefault();chosenContact=null;renderBox();};
    } else {
      box.innerHTML = `
        <div style="display:flex;gap:6px;margin-bottom:6px">
          <button id="rec_assign_me" style="flex:1;background:var(--card);border:1px solid var(--accent);color:var(--text);border-radius:6px;padding:7px;font-size:12px;cursor:pointer"><i class="bi bi-person-fill"></i> ${t('rec_assign_me','Mir zuordnen')}${CFG.ownerContactName?(' ('+_e(CFG.ownerContactName)+')'):''}</button>
        </div>
        <input id="rec_csearch" type="text" placeholder="${t('rec_search_contact','Anderen Kontakt suchen...')}" style="width:100%;box-sizing:border-box;font-size:12px;padding:6px;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text)">
        <div id="rec_cresults" style="max-height:140px;overflow:auto;margin-top:4px"></div>`;
      const me = box.querySelector('#rec_assign_me');
      if (me) me.onclick = () => { if(!CFG.ownerContactId){showNotice(t('rec_no_owner','Kein Besitzer gesetzt'));return;} chosenContact=CFG.ownerContactId; chosenName=CFG.ownerContactName||''; renderBox(); };
      const si = box.querySelector('#rec_csearch');
      if (si) si.oninput = _recDebounceSearch;
    }
  }
  let _recT=null;
  function _recDebounceSearch(e){ clearTimeout(_recT); const q=e.target.value.trim(); const rb=ov.querySelector('#rec_cresults'); if(q.length<2){rb.innerHTML='';return;} _recT=setTimeout(async()=>{
    try{ const resp=await apiFetch(`${CFG.portalUrl}/crm/api/berater/?q=${encodeURIComponent(q)}&per_page=8&typ=alle`); const d=await resp.json(); const rows=(d.contacts||d.results||(Array.isArray(d)?d:[])||[]);
      rb.innerHTML = rows.map(c=>{const id=c.crm_id||c.id||'';const nm=(c.full_name||((c.first_name||'')+' '+(c.last_name||''))).trim();const comp=c.company||c.account_name||'';return `<div class="rec-cres" data-id="${id}" data-name="${_e(nm)}" style="padding:6px 8px;font-size:12px;cursor:pointer;border-radius:5px">${_e(nm)}${comp?` <span style="color:var(--muted)">· ${_e(comp)}</span>`:''}</div>`;}).join('')||`<div style="font-size:11px;color:var(--muted);padding:4px">${t('no_results','keine Treffer')}</div>`;
      rb.querySelectorAll('.rec-cres').forEach(el=>el.onclick=()=>{chosenContact=el.dataset.id;chosenName=el.dataset.name;renderBox();});
    }catch(err){console.warn(err);}
  },250); }
  renderBox();

  ov.querySelector('#rec_subj_save').onclick = async () => {
    const subj = (ov.querySelector('#rec_subj_in').value||'').trim();
    if (!subj) { ov.querySelector('#rec_subj_in').style.borderColor='var(--red)'; showNotice(t('rec_subject_required','Betreff ist Pflicht!')); return; }
    if (!chosenContact) { showNotice(t('rec_target_required','Bitte zuordnen (Mir / Kontakt)')); return; }
    try {
      const resp = await apiFetch(`${CFG.portalUrl}/crm/api/recording/${recId}/assign/`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ subject: subj, contact_crm_id: chosenContact }) });
      const r = await resp.json();
      if (r && r.ok) { ov.remove(); showNotice('\u2713 ' + t('rec_saved','Aufnahme zugeordnet')); if(typeof CCDetail!=='undefined'&&_kontaktCurrent&&_kontaktCurrent.crm_id)CCDetail.reload(); }
      else showNotice('\u2717 ' + (r.msg||t('error','Fehler')));
    } catch(e){ console.warn(e); showNotice('\u2717 '+t('error','Fehler')); }
  };
}
'''
    s = s.rstrip() + '\n' + block + '\n'
    open(p, 'w', encoding='utf-8').write(s)
    print("  recordingBetreffDialog ergänzt.")
PYEOF
node --check renderer/app.js && echo "  app.js OK"

echo "=== [3/3] Audio 401: Blob-Load mit Token statt <source src> ==="
python3 - << 'PYEOF'
p = 'renderer/app_cc_detail.js'
s = open(p, encoding='utf-8').read()
# Den <audio><source> durch ein audio mit data-rec-id ersetzen + Blob-Loader
OLD = '''        <audio controls preload="none" style="width:100%;height:32px;margin-top:4px">
          <source src="${audioUrl}" type="audio/wav">
        </audio>'''
NEW = '''        <audio controls preload="none" data-rec-id="${r.id}" style="width:100%;height:32px;margin-top:4px"></audio>'''
if OLD in s:
    s = s.replace(OLD, NEW)
    print("  <source src> entfernt (Blob-Load folgt).")
else:
    print("  ⚠ audio-Anker nicht gefunden (evtl. schon gepatcht).")

# Nach loadAufnahmen: die audio-Elemente per Blob laden (Token!)
if 'CCDetail._loadRecAudio' not in s:
    # Am Ende von loadAufnahmen (nach dem .map().join('')) die Blob-Loader anstoßen.
    anchor = "    }).join('');\n  } catch(e) {\n    wrap.innerHTML = `<div class=\"cc-empty\">${t('rec_err','Aufnahmen nicht ladbar')}</div>`;\n  }\n};"
    loader = '''    }).join('');
    // Audio per Blob nachladen (mit Token, da <audio src> keinen Header schickt)
    wrap.querySelectorAll('audio[data-rec-id]').forEach(el => CCDetail._loadRecAudio(el));
  } catch(e) {
    wrap.innerHTML = `<div class="cc-empty">${t('rec_err','Aufnahmen nicht ladbar')}</div>`;
  }
};

CCDetail._loadRecAudio = async function(el) {
  const id = el.getAttribute('data-rec-id');
  if (!id) return;
  try {
    const resp = await apiFetch(`${CFG.portalUrl}/crm/api/recording/${id}/audio/`);
    if (!resp.ok) { console.warn('audio', id, resp.status); return; }
    const blob = await resp.blob();
    el.src = URL.createObjectURL(blob);
  } catch(e) { console.warn('audio-load', id, e); }
};'''
    assert s.count(anchor) == 1, f"loadAufnahmen-Anker {s.count(anchor)}x"
    s = s.replace(anchor, loader)
    print("  Blob-Loader _loadRecAudio ergänzt.")
open(p, 'w', encoding='utf-8').write(s)
PYEOF
node --check renderer/app_cc_detail.js && echo "  app_cc_detail.js OK"

echo ""
echo "============================================================"
echo "✅ fix_3bugs fertig. Jetzt Build 1.0.14."
echo "============================================================"

