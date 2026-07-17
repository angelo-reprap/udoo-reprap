/**
 * ABpE Telefon Studio — mod-telefon-studio.js
 */
'use strict';

const TelefonStudio = (() => {

  let _ext = '';
  let _mode = 'all';
  let _days = 30;
  let _statsCache = null;
  let _statusPollTimer = null;

  function init() {
    const root = document.getElementById('telefon-studio-root');
    if (!root) return;
    _bindTabButtons();
    _loadPeers();
    _bindControls();
    _bindCallForm();
    fetch('/crm/api/user-settings/')
      .then(r => r.json())
      .then(d => {
        if (!d.success) return;
        const ext = d.data.phone_extension;
        if (!ext) return;
        const trySet = (n) => {
          const sel = document.getElementById('ts-extension-select');
          if (!sel) return;
          const opt = Array.from(sel.options).find(o => o.value === ext);
          if (opt) { sel.value = ext; TelefonStudio.onExtChange(ext); }
          else if (n > 0) setTimeout(() => trySet(n-1), 400);
        };
        setTimeout(() => trySet(10), 600);
      })
      .catch(() => {});
  }

  function _bindTabButtons() {
    document.querySelectorAll('.ts-tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.ts-tab-btn').forEach(b => b.classList.remove('ts-tab-active'));
        document.querySelectorAll('.ts-tab-panel').forEach(p => p.classList.remove('ts-tab-panel-active'));
        btn.classList.add('ts-tab-active');
        const tab = btn.dataset.tab;
        const panel = document.getElementById('ts-tab-' + tab);
        if (panel) panel.classList.add('ts-tab-panel-active');
        if (tab === 'stats' && _ext) _loadStats();
      });
    });
  }

  function _loadPeers() {
    fetch('/crm/api/telefon/peers/')
      .then(r => r.json())
      .then(data => {
        const sel = document.getElementById('ts-extension-select');
        const callSel = document.getElementById('ts-call-ext');
        sel.innerHTML = '<option value="">— Nebenstelle wählen —</option>';
        if (callSel) callSel.innerHTML = '<option value="">Bitte wählen...</option>';
        (data.peers || []).forEach(p => {
          const label = p.online ? p.name + ' — OK (' + p.ms + ' ms)' : p.name + ' — offline';
          const opt = new Option(label, p.name);
          if (!p.online) opt.style.color = '#94a3b8';
          sel.appendChild(opt.cloneNode(true));
          if (callSel) callSel.appendChild(opt);
        });
      })
      .catch(err => console.error('Peers laden fehlgeschlagen:', err));
  }

  function _bindControls() {
    document.getElementById('ts-extension-select')?.addEventListener('change', e => {
      _ext = e.target.value;
      _stopStatusPoll();
      if (_ext) { _loadCDR(); _loadMiniStats(); _startStatusPoll(); }
      else { _clearTable(); }
    });
    document.getElementById('ts-mode-select')?.addEventListener('change', e => {
      _mode = e.target.value;
      if (_ext) _loadCDR();
    });
    document.getElementById('ts-days-select')?.addEventListener('change', e => {
      _days = parseInt(e.target.value);
      if (_ext) { _loadCDR(); _loadMiniStats(); }
    });
    document.getElementById('ts-refresh-btn')?.addEventListener('click', () => {
      if (_ext) { _loadCDR(); _loadMiniStats(); }
    });
  }

  function _loadCDR() {
    const tbody = document.getElementById('ts-cdr-tbody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="7" class="ts-loading">Lade Anrufe...</td></tr>';
    fetch('/crm/api/telefon/cdr/?extension=' + _ext + '&mode=' + _mode + '&days=' + _days + '&limit=200')
      .then(r => r.json())
      .then(data => _renderCDR(data.rows || []))
      .catch(err => {
        tbody.innerHTML = '<tr><td colspan="7" class="ts-loading" style="color:#ef4444">Fehler: ' + err.message + '</td></tr>';
      });
  }

  function _renderCDR(rows) {
    const tbody = document.getElementById('ts-cdr-tbody');
    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="ts-loading">Keine Anrufe gefunden.</td></tr>';
      return;
    }
    tbody.innerHTML = rows.map(row => {
      const dt = _fmtDate(row.calldate);
      const dir = _dirBadge(row);
      const num = _extNum(row);
      const contact = _contactCell(row.contact, num);
      const status = _statusBadge(row.disposition);
      const dur = row.billsec_fmt || '0:00';
      const callable = num && num.match(/\d{5,}/) && num !== 'anonymous';
      const contactUrl = (row.contact && row.contact.url) ? row.contact.url : '';
      const contactId  = (row.contact && row.contact.crm_id) ? row.contact.crm_id : '';
      const contactType = (row.contact && row.contact.type) ? row.contact.type : '';
      return '<tr class="ts-cdr-row" style="cursor:pointer" data-number="' + _esc(num) + '" data-contact-url="' + _esc(contactUrl) + '" data-callable="' + (callable?'1':'0') + '" data-crm-id="' + _esc(contactId) + '" data-crm-type="' + _esc(contactType) + '">'
        + '<td>' + dt + '</td>'
        + '<td>' + dir + '</td>'
        + '<td><span class="ts-number">' + num + '</span></td>'
        + '<td>' + contact + '</td>'
        + '<td>' + status + '</td>'
        + '<td>' + dur + '</td>'
        + '<td style="text-align:center"><i class="bi bi-three-dots-vertical" style="color:#aaa;font-size:14px;pointer-events:none"></i></td>'
        + '</tr>';
    }).join('');

    // Event-Delegation auf tbody — ein Handler für alles
    tbody.onclick = function(e) {
      // Klick auf "anlegen" Span
      const noContact = e.target.closest('.ts-no-contact');
      if (noContact) {
        e.preventDefault();
        e.stopPropagation();
        _showCreateContactPopup(noContact.dataset.number);
        return;
      }
      // Alle anderen Klicks → Kontext-Menü
      const row = e.target.closest('.ts-cdr-row');
      if (row) {
        e.preventDefault();
        _showRowMenu(row, e);
      }
    };
  }

  function _dirBadge(row) {
    if (row.direction === 'outgoing') return '<span class="ts-badge ts-badge-outgoing"><i class="ti ti-arrow-up-right"></i> ausgehend</span>';
    if (row.disposition === 'ANSWERED') return '<span class="ts-badge ts-badge-answered"><i class="ti ti-arrow-down-left"></i> eingehend</span>';
    return '<span class="ts-badge ts-badge-missed"><i class="ti ti-arrow-down-left"></i> verpasst</span>';
  }

  function _extNum(row) {
    return row.direction === 'incoming' ? (row.src || '') : (row.dst || '');
  }

  function _contactCell(contact, number) {
    if (contact && contact.name) {
      return '<span class="ts-contact-chip" style="display:inline-flex;align-items:center;gap:4px;font-size:12px;padding:2px 8px;border-radius:10px;background:#f0f0f0;border:1px solid #e0e0e0;cursor:pointer">'
        + '<i class="ti ti-user"></i> ' + _esc(contact.name) + '</span>';
    }
    if (!number || number === 'anonymous' || number === 's' || !number.match(/\d{5,}/)) {
      return '<span style="color:#ccc">—</span>';
    }
    return '<span class="ts-no-contact" data-number="' + _esc(number) + '" title="Kontakt anlegen" style="font-size:12px;color:#aaa;cursor:pointer">'
      + '<i class="ti ti-user-plus"></i> anlegen</span>';
  }

  function _statusBadge(disposition) {
    const map = {
      'ANSWERED':   ['ts-badge-answered', 'Angenommen'],
      'NO ANSWER':  ['ts-badge-missed',   'Verpasst'],
      'BUSY':       ['ts-badge-missed',   'Besetzt'],
      'CONGESTION': ['ts-badge-missed',   'Überlastet'],
      'FAILED':     ['ts-badge-unknown',  'Fehlgeschl.'],
    };
    const [cls, label] = map[disposition] || ['ts-badge-unknown', disposition];
    return '<span class="ts-badge ' + cls + '">' + label + '</span>';
  }

  function _showRowMenu(row, e) {
    document.getElementById('ts-row-menu')?.remove();
    const num        = row.dataset.number;
    const contactUrl = row.dataset.contactUrl;
    const callable   = row.dataset.callable === '1';
    const crmId      = row.dataset.crmId || '';
    const crmType    = row.dataset.crmType || '';

    const menu = document.createElement('div');
    menu.id = 'ts-row-menu';
    menu.style.cssText = 'position:fixed;z-index:99999;background:#fff;border:1px solid #ddd;border-radius:8px;'
      + 'box-shadow:0 4px 20px rgba(0,0,0,.15);min-width:190px;overflow:hidden;'
      + 'left:' + Math.min(e.clientX, window.innerWidth - 210) + 'px;'
      + 'top:' + Math.min(e.clientY, window.innerHeight - 150) + 'px';

    const items = [];
    if (callable && _ext)
      items.push('<div class="ts-mi" onclick="TelefonStudio._mCall(\'' + _esc(num) + '\')"><i class="bi bi-telephone" style="color:#163258"></i> Anrufen</div>');
    if (contactUrl)
      items.push('<div class="ts-mi" onclick="window.location.href=\'' + _esc(contactUrl) + '\'"><i class="bi bi-person" style="color:#163258"></i> Kontakt öffnen</div>');
    else if (callable)
      items.push('<div class="ts-mi" onclick="TelefonStudio._mCreate(\'' + _esc(num) + '\')"><i class="bi bi-person-plus" style="color:#163258"></i> Kontakt anlegen</div>');
    items.push('<div class="ts-mi" style="border-top:1px solid #eee" onclick="TelefonStudio._mNote(\'' + _esc(num) + '\',\'' + _esc(crmId) + '\',\'' + _esc(crmType) + '\')" ><i class="bi bi-journal-text" style="color:#163258"></i> Notiz anlegen</div>');

    menu.innerHTML = '<style>.ts-mi{padding:9px 16px;font-size:13px;cursor:pointer;display:flex;align-items:center;gap:8px;color:#333}.ts-mi:hover{background:#f5f5f5}</style>'
      + items.join('');

    document.body.appendChild(menu);
    setTimeout(() => {
      document.addEventListener('click', function handler() {
        menu.remove();
        document.removeEventListener('click', handler);
      });
    }, 50);
  }

  function _loadVoicemailCount() {
    if (!_ext) return;
    fetch('/crm/api/telefon/voicemail/?extension=' + _ext)
      .then(r => r.json())
      .then(data => {
        const newMsg = data.new_messages ?? 0;
        const oldMsg = data.old_messages ?? 0;
        const el = document.getElementById('ts-ms-voicemail');
        if (el) {
          el.textContent = newMsg;
          el.style.color = newMsg > 0 ? '#f59e0b' : '#aaa';
        }
        const btn = document.getElementById('ts-vm-btn');
        if (btn) {
          btn.disabled = (newMsg + oldMsg) === 0;
          btn.title = newMsg + ' neu, ' + oldMsg + ' alt';
        }
      })
      .catch(() => {});
  }

  function _loadMiniStats() {
    fetch('/crm/api/telefon/stats/?extension=' + _ext)
      .then(r => r.json())
      .then(data => {
        const s = data.stats || {};
        const h = s.heute || {};
        const m = s.monat || {};
        _set('ts-ms-heute',  h.total  ?? '—');
        _set('ts-ms-missed', h.missed ?? '—');
        _set('ts-ms-monat',  m.total  ?? '—');
        _set('ts-ms-top',    (s.top_anrufer || [])[0]?.nummer ?? '—');
        _statsCache = s;
      })
      .catch(() => {});
  }

  function _loadStats() {
    if (_statsCache) { _renderStats(_statsCache); return; }
    fetch('/crm/api/telefon/stats/?extension=' + _ext)
      .then(r => r.json())
      .then(data => { _statsCache = data.stats; _renderStats(data.stats || {}); });
  }

  function _renderStats(s) {
    _renderStatCard('ts-stats-heute', s.heute);
    _renderStatCard('ts-stats-woche', s.woche);
    _renderStatCard('ts-stats-monat', s.monat);
    _renderHeatmap(s.stunden || []);
    _renderTopList('ts-stats-top-anrufer',   s.top_anrufer   || [], 'nummer', 'anzahl');
    _renderTopList('ts-stats-top-angerufen', s.top_angerufen || [], 'nummer', 'anzahl');
  }

  function _renderStatCard(id, data) {
    const el = document.getElementById(id);
    if (!el || !data) return;
    const map = { total:'Gesamt', answered:'Angenommen', missed:'Verpasst', incoming:'Eingehend', outgoing:'Ausgehend', talk_sec:'Gesprächszeit' };
    el.innerHTML = Object.entries(data).map(([k, v]) =>
      '<div class="ts-stat-row"><span>' + (map[k]||k) + '</span><span class="ts-stat-val">' + (k==='talk_sec'?_fmtSec(v):v) + '</span></div>'
    ).join('');
  }

  function _renderHeatmap(stunden) {
    const el = document.getElementById('ts-stats-stunden');
    if (!el) return;
    const max = Math.max(...stunden.map(s => s.anrufe || 0), 1);
    el.innerHTML = Array.from({length: 24}, (_, h) => {
      const entry = stunden.find(s => s.stunde === h);
      const count = entry ? entry.anrufe : 0;
      const pct = Math.max(4, Math.round((count / max) * 100));
      return '<div class="ts-heatmap-bar" style="height:' + pct + '%;opacity:' + (0.3 + 0.7*(count/max)) + '" title="' + h + ':00 — ' + count + ' Anrufe"></div>';
    }).join('');
  }

  function _renderTopList(id, items, numKey, countKey) {
    const el = document.getElementById(id);
    if (!el) return;
    if (!items.length) { el.innerHTML = '<p style="color:#aaa;font-size:12px">Keine Daten</p>'; return; }
    el.innerHTML = items.slice(0, 8).map(item =>
      '<div class="ts-stat-row"><span style="font-size:12px">' + item[numKey] + '</span><span class="ts-stat-val">' + item[countKey] + '</span></div>'
    ).join('');
  }

  function _startStatusPoll() {
    _updateStatus();
    _statusPollTimer = setInterval(_updateStatus, 10000);
  }

  function _stopStatusPoll() {
    if (_statusPollTimer) { clearInterval(_statusPollTimer); _statusPollTimer = null; }
  }

  function _updateStatus() {
    if (!_ext) return;
    fetch('/crm/api/telefon/status/?extension=' + _ext)
      .then(r => r.json())
      .then(data => {
        const badge = document.getElementById('ts-ext-status');
        if (!badge) return;
        badge.className = 'ts-status-badge';
        if (data.status === 'free')       badge.classList.add('ts-status-ok');
        else if (data.status === 'busy')  badge.classList.add('ts-status-busy');
        else                              badge.classList.add('ts-status-unknown');
      });
  }

  function _bindCallForm() {
    const destInput = document.getElementById('ts-call-dest');
    const callBtn   = document.getElementById('ts-call-btn');
    const extSel    = document.getElementById('ts-call-ext');
    const normPrev  = document.getElementById('ts-call-norm');
    const sync = () => {
      const ext  = extSel?.value;
      const dest = destInput?.value.trim();
      if (callBtn) callBtn.disabled = !(ext && dest && dest.match(/\d{5,}/));
      if (normPrev && dest) normPrev.textContent = dest.startsWith('0049') ? dest : dest.startsWith('0') ? '0049' + dest.slice(1) : dest;
    };
    destInput?.addEventListener('input', sync);
    extSel?.addEventListener('change', sync);
    callBtn?.addEventListener('click', () => {
      const ext  = extSel?.value;
      const dest = destInput?.value.trim();
      if (ext && dest) _startCall(ext, dest);
    });
  }

  function _startCall(ext, destination) {
    const result = document.getElementById('ts-call-result');
    if (result) { result.style.display='block'; result.className = 'ts-call-result'; result.textContent = 'Verbinde...'; }
    fetch('/crm/api/telefon/call/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': _getCsrf() },
      body: JSON.stringify({ extension: ext, destination }),
    })
    .then(r => r.json())
    .then(data => {
      if (!result) return;
      if (data.success) {
        result.className = 'ts-call-result ts-call-ok';
        result.textContent = '✓ Anruf eingeleitet: ' + ext + ' → ' + data.destination_norm;
      } else {
        result.className = 'ts-call-result ts-call-err';
        result.textContent = '✗ Fehler: ' + (data.error || 'Unbekannt');
      }
      setTimeout(() => { if (result) result.style.display='none'; }, 5000);
    })
    .catch(err => {
      if (result) { result.className = 'ts-call-result ts-call-err'; result.textContent = '✗ Netzwerkfehler: ' + err.message; }
    });
  }

  function _showCreateContactPopup(number) {
    let modal = document.getElementById('ts-new-contact-modal');
    if (modal) modal.remove();
    modal = document.createElement('div');
    modal.id = 'ts-new-contact-modal';
    modal.style.cssText = 'position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,0.5);display:flex;align-items:flex-start;justify-content:center;padding-top:60px';
    modal.innerHTML = '<div style="background:#fff;border-radius:12px;width:460px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,0.25)">'
      + '<div style="background:#163258;padding:14px 18px;display:flex;align-items:center;justify-content:space-between">'
      + '<div style="display:flex;align-items:center;gap:10px;color:#fff"><i class="bi bi-person-plus"></i><span style="font-weight:600;font-size:14px">Neuer Kontakt</span></div>'
      + '<div style="display:flex;align-items:center;gap:8px">'
      + '<span style="background:rgba(255,255,255,0.15);color:#fff;font-size:11px;padding:3px 10px;border-radius:20px"><i class="bi bi-telephone"></i> ' + _esc(number) + '</span>'
      + '<button onclick="document.getElementById(\'ts-new-contact-modal\').remove()" style="background:rgba(255,255,255,0.15);border:none;color:#fff;width:26px;height:26px;border-radius:50%;cursor:pointer;font-size:16px;line-height:1">×</button>'
      + '</div></div>'
      + '<div style="padding:16px 18px;display:flex;flex-direction:column;gap:10px">'
      + '<div style="display:flex;gap:6px">'
      + '<button id="ts-nc-typ-berater" onclick="tsNcSetTyp(\'berater\')" style="padding:4px 14px;border-radius:20px;border:1.5px solid #163258;background:#e8f0fe;color:#163258;font-size:12px;cursor:pointer;font-weight:500">Berater</button>'
      + '<button id="ts-nc-typ-kunde" onclick="tsNcSetTyp(\'kunde\')" style="padding:4px 14px;border-radius:20px;border:1px solid #ccc;background:transparent;font-size:12px;cursor:pointer">Kunde</button>'
      + '</div>'
      + '<div style="display:grid;grid-template-columns:110px 1fr;gap:8px;align-items:center"><label style="font-size:12px;color:#666">Anrede</label>'
      + '<select id="ts-nc-salutation" style="padding:6px 10px;font-size:13px;border:1px solid #ccc;border-radius:7px"><option value="Hr.">Hr.</option><option value="Fr.">Fr.</option><option value="">—</option></select></div>'
      + '<div style="display:grid;grid-template-columns:110px 1fr;gap:8px;align-items:center"><label style="font-size:12px;color:#666">Vorname</label>'
      + '<input id="ts-nc-firstname" type="text" placeholder="Vorname" style="padding:6px 10px;font-size:13px;border:1px solid #ccc;border-radius:7px;width:100%;box-sizing:border-box"></div>'
      + '<div style="display:grid;grid-template-columns:110px 1fr;gap:8px;align-items:center"><label style="font-size:12px;color:#666">Nachname <span style="color:#dc3545">*</span></label>'
      + '<input id="ts-nc-lastname" type="text" placeholder="Nachname (Pflicht)" style="padding:6px 10px;font-size:13px;border:1.5px solid #163258;border-radius:7px;width:100%;box-sizing:border-box"></div>'
      + '<div style="background:#f8f9fa;border-radius:7px;padding:10px 12px;display:flex;align-items:center;gap:8px">'
      + '<i class="bi bi-telephone" style="color:#163258;font-size:15px"></i>'
      + '<div style="flex:1"><div style="font-size:11px;color:#888">Wird automatisch eingetragen</div><div style="font-size:13px;font-weight:600">' + _esc(number) + '</div></div>'
      + '<select id="ts-nc-phone-type" style="padding:4px 8px;font-size:11px;border:1px solid #ccc;border-radius:6px">'
      + '<option value="phone_mobile">Mobil</option><option value="phone_office">Büro</option><option value="phone_other">Sonstiges</option></select></div>'
      + '<div id="ts-nc-msg" style="font-size:12px;min-height:18px;text-align:center"></div>'
      + '</div>'
      + '<div style="padding:12px 18px;border-top:1px solid #eee;display:flex;justify-content:flex-end;gap:8px">'
      + '<button onclick="document.getElementById(\'ts-new-contact-modal\').remove()" style="padding:7px 16px;border-radius:7px;border:1px solid #ccc;background:transparent;font-size:13px;cursor:pointer">Abbrechen</button>'
      + '<button onclick="tsNcSave(false,\'' + _esc(number) + '\')" style="padding:7px 16px;border-radius:7px;border:1px solid #163258;background:transparent;color:#163258;font-size:13px;cursor:pointer;font-weight:500"><i class="bi bi-person-check"></i> Anlegen</button>'
      + '<button onclick="tsNcSave(true,\'' + _esc(number) + '\')" style="padding:7px 16px;border-radius:7px;border:none;background:#163258;color:#fff;font-size:13px;cursor:pointer;font-weight:500"><i class="bi bi-box-arrow-up-right"></i> Anlegen &amp; öffnen</button>'
      + '</div></div>';
    document.body.appendChild(modal);
    modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
    setTimeout(() => document.getElementById('ts-nc-lastname')?.focus(), 100);
  }

  window.tsNcSetTyp = function(typ) {
    ['berater','kunde'].forEach(t => {
      const btn = document.getElementById('ts-nc-typ-' + t);
      if (!btn) return;
      if (t === typ) { btn.style.border='1.5px solid #163258'; btn.style.background='#e8f0fe'; btn.style.color='#163258'; btn.style.fontWeight='500'; }
      else           { btn.style.border='1px solid #ccc';      btn.style.background='transparent'; btn.style.color='inherit'; btn.style.fontWeight='normal'; }
    });
  };

  window.tsNcSave = async function(openAfter, number) {
    const lastname = document.getElementById('ts-nc-lastname')?.value?.trim();
    const msg = document.getElementById('ts-nc-msg');
    if (!lastname) { if(msg){msg.style.color='#dc3545';msg.textContent='Nachname ist Pflichtfeld';} document.getElementById('ts-nc-lastname')?.focus(); return; }
    const salutation = document.getElementById('ts-nc-salutation')?.value || 'Hr.';
    const firstname  = document.getElementById('ts-nc-firstname')?.value?.trim() || '';
    const phoneType  = document.getElementById('ts-nc-phone-type')?.value || 'phone_mobile';
    const typBtn     = document.getElementById('ts-nc-typ-berater');
    const typ        = (typBtn?.style.background === 'rgb(232, 240, 254)') ? 'berater' : 'kunde';
    if (msg) { msg.style.color='#163258'; msg.textContent='Anlegen...'; }
    const csrf = _getCsrf();
    try {
      let crm_id = null;
      if (typ === 'berater') {
        const r = await fetch('/crm/api/berater/new/', {method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf},body:JSON.stringify({salutation,first_name:firstname,last_name:lastname})});
        const d = await r.json();
        if (!d.ok) { if(msg){msg.style.color='#dc3545';msg.textContent=d.error||'Fehler';} return; }
        crm_id = d.crm_id;
      } else {
        const r = await fetch('/crm/api/kunden/new/', {method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf},body:JSON.stringify({name:(firstname+' '+lastname).trim()})});
        const d = await r.json();
        if (!d.ok) { if(msg){msg.style.color='#dc3545';msg.textContent=d.error||'Fehler';} return; }
        crm_id = d.crm_id;
      }
      const updateUrl = typ==='berater' ? '/crm/api/contact/'+crm_id+'/update/' : '/crm/api/account/'+crm_id+'/update/';
      const module    = typ==='berater' ? 'Contacts' : 'Accounts';
      await fetch(updateUrl, {method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf},body:JSON.stringify({action:'phone_add',nummer:number,field_name:phoneType,bean_module:module})});
      document.getElementById('ts-new-contact-modal')?.remove();
      if (openAfter) {
        window.location.href = '/crm/' + (typ==='berater'?'berater':'kunden') + '/?detail=' + crm_id;
      } else {
        setTimeout(() => _loadCDR(), 800);
      }
    } catch(e) { if(msg){msg.style.color='#dc3545';msg.textContent='Netzwerkfehler';} }
  };

  function _set(id, val) { const el = document.getElementById(id); if (el) el.textContent = val; }

  function _esc(str) {
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  }

  function _fmtDate(str) {
    if (!str) return '—';
    const d = new Date(str.replace(' ','T'));
    const now = new Date();
    const time = d.toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit'});
    if (now.toDateString()===d.toDateString()) return 'Heute ' + time;
    return d.toLocaleDateString('de-DE',{day:'2-digit',month:'2-digit'}) + ' ' + time;
  }

  function _fmtSec(sec) {
    if (!sec) return '0:00';
    const s=parseInt(sec), h=Math.floor(s/3600), m=Math.floor((s%3600)/60), ss=s%60;
    return h ? h+':'+String(m).padStart(2,'0')+':'+String(ss).padStart(2,'0') : m+':'+String(ss).padStart(2,'0');
  }

  function _clearTable() {
    const tbody = document.getElementById('ts-cdr-tbody');
    if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="ts-loading">Nebenstelle wählen...</td></tr>';
    ['ts-ms-heute','ts-ms-missed','ts-ms-monat','ts-ms-top'].forEach(id => _set(id, '—'));
  }

  function _getCsrf() {
    const c = document.cookie.split(';').find(c => c.trim().startsWith('csrftoken='));
    return c ? c.split('=')[1].trim() : '';
  }

  return {
    init,
    onExtChange(v) { _ext=v; _stopStatusPoll(); if(v){_loadCDR();_loadMiniStats();_loadVoicemailCount();_startStatusPoll();}else{_clearTable();} },
    reload()       { if(_ext){_loadCDR();_loadMiniStats();} },
    showTab(tab, btn) {
      document.querySelectorAll('.ts-tab-btn').forEach(b=>{b.style.background='#fff';b.style.color='inherit';});
      btn.style.background='var(--abcona-blue)'; btn.style.color='#fff';
      document.querySelectorAll('.ts-panel').forEach(p=>p.style.display='none');
      const el=document.getElementById('ts-tab-'+tab); if(el) el.style.display='block';
      if(tab==='stats'&&_ext) _loadStats();
    },
    updateCallBtn() {
      const ext=document.getElementById('ts-call-ext')?.value;
      const dest=document.getElementById('ts-call-dest')?.value?.trim();
      const btn=document.getElementById('ts-call-btn');
      if(btn) btn.disabled=!(ext&&dest&&dest.match(/\d{5,}/));
    },
    startCall() { const ext=document.getElementById('ts-call-ext')?.value; const dest=document.getElementById('ts-call-dest')?.value?.trim(); if(ext&&dest)_startCall(ext,dest); },
    _mCall(num)   { if(_ext)_startCall(_ext,num); },
    _mCreate(num) { _showCreateContactPopup(num); },
    callVoicemail() { if(_ext) _startCall(_ext, '*97'); },
    _mNote(num, crmId, crmType)   {
      const text=prompt('Notiz für '+num+':');
      if(!text)return;
      const payload = {note_text:text, note_type:'phone'};
      if (crmId && crmType==='contact') payload.contact_crm_id = crmId;
      if (crmId && crmType==='account') payload.account_crm_id = crmId;
      fetch('/crm/api/note/save/',{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':_getCsrf()},body:JSON.stringify(payload)})
        .then(r=>r.json()).then(d=>{if(d.ok)alert('✓ Notiz gespeichert');else alert('Fehler: '+(d.error||'unbekannt'));});
    },
  };
})();

document.addEventListener('DOMContentLoaded', TelefonStudio.init);
document.addEventListener('module:loaded:telefon_studio', TelefonStudio.init);
