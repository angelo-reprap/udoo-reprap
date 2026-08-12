/**
 * mod-softphone-ext.js — Erweiterungen für ABpE Softphone
 * Voicemail, DND, Rufweiterleitung, Pickup, Letzte Anrufe, Schnellwahl, Ext. Status
 */

// ── Config aus Settings ────────────────────────────────────
// _csrf lokal implementieren (da privat in IIFE)
Softphone._csrf = function() {
    return document.cookie.split(';').map(c => c.trim())
        .find(c => c.startsWith('csrftoken='))?.split('=')[1] || '';
};

Softphone._ext = {
    vm_ext:     '',   // z.B. "22"
    dnd_ext:    '',   // z.B. "22"
    fwd_target: '',
    speed_dials: [],
    status_exts: [],
    dnd_active:  false,
    fwd_active:  false,
};

// Settings laden (wird nach _loadSettings aufgerufen)
const _origLoadSettings = Softphone.init;
Softphone._loadExtSettings = async function() {
    try {
        const r = await fetch('/crm/api/user-settings/');
        const d = await r.json();
        if (d.success) {
            const s = d.data;
            Softphone._ext.vm_ext      = s.softphone_vm_ext      || '';
            Softphone._ext.dnd_ext     = s.softphone_dnd_ext     || '';
            Softphone._ext.fwd_target  = s.softphone_fwd_target  || '';
            Softphone._ext.speed_dials = s.softphone_speed_dials || [];
            Softphone._ext.status_exts = (s.softphone_status_exts || '').split(',').map(e => e.trim()).filter(Boolean);
            Softphone._loadExtSettingsIntoForm(s);
            Softphone._renderSpeedDials();
            if (Softphone._ext.status_exts.length) Softphone._startStatusPolling();
        }
    } catch(e) { console.warn('Softphone-ext: Settings laden fehlgeschlagen', e); }
};

// ── Voicemail ──────────────────────────────────────────────
Softphone.callVoicemail = function() {
    const ext = (Softphone._ext.vm_ext || '').split(',')[0].trim();
    if (!ext) { alert('Bitte VM-Nebenstelle in den Einstellungen konfigurieren.'); return; }
    Softphone.setNumber('*97' + ext);
    Softphone.call();
};

// ── DND ────────────────────────────────────────────────────
Softphone.toggleDND = async function() {
    const ext = Softphone._ext.dnd_ext || Softphone._ext.vm_ext;
    if (!ext) { alert('Bitte DND-Nebenstelle in den Einstellungen konfigurieren.'); return; }
    try {
        const r = await fetch('/crm/api/telefon/dnd/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': Softphone._csrf() },
            body: JSON.stringify({ extension: ext, active: !Softphone._ext.dnd_active })
        });
        const d = await r.json();
        if (d.success) {
            Softphone._ext.dnd_active = !Softphone._ext.dnd_active;
            Softphone._updateStatusIndicators();
        }
    } catch(e) { console.warn('DND Fehler:', e); }
};

Softphone._vmCount = 0;

Softphone._updateStatusIndicators = function() {
    var vmBtn    = document.getElementById('sp-vm-btn');
    var vmLabel  = document.getElementById('sp-vm-label');
    var fwdBtn   = document.getElementById('sp-fwd-btn');
    var dndBtn   = document.getElementById('sp-dnd-btn');
    var dndIcon  = document.getElementById('sp-dnd-icon');
    var dndLabel = document.getElementById('sp-dnd-label');
    var bar      = document.getElementById('sp-status-bar');
    var NS  = 'padding:5px 2px;border-radius:6px;font-size:9px;cursor:pointer;text-align:center;line-height:1.3;';
    var OFF = NS + 'border:0.5px solid #d1d5db;background:#f9fafb;color:#374151;';
    var vmCount   = Softphone._vmCount || 0;
    var fwdActive = Softphone._ext.fwd_active || false;
    var fwdTarget = Softphone._ext.fwd_target || '';
    var dndActive = Softphone._ext.dnd_active || false;
    if (vmBtn) {
        if (vmCount > 0) {
            vmBtn.style.cssText = NS + 'border:0.5px solid #b45309;background:#fffbeb;color:#92400e;font-weight:600;';
            if (vmLabel) vmLabel.textContent = 'VM · ' + vmCount;
        } else {
            vmBtn.style.cssText = OFF;
            if (vmLabel) vmLabel.textContent = 'VM';
        }
    }
    if (fwdBtn) {
        fwdBtn.style.cssText = fwdActive
            ? NS + 'border:0.5px solid #1e40af;background:#eff6ff;color:#1e3a8a;font-weight:600;'
            : OFF;
    }
    if (dndBtn) {
        if (dndActive) {
            dndBtn.style.cssText = NS + 'border:0.5px solid #991b1b;background:#fff1f2;color:#991b1b;font-weight:600;';
            if (dndIcon) dndIcon.className = 'bi bi-bell-slash';
        } else {
            dndBtn.style.cssText = OFF;
            if (dndIcon) dndIcon.className = 'bi bi-bell';
        }
        if (dndLabel) dndLabel.textContent = 'DND';
    }
    if (bar) {
        if (dndActive) {
            bar.style.cssText = 'display:block;padding:4px 8px;border-left:3px solid #991b1b;font-size:10px;font-weight:500;color:#991b1b;margin:0 0 2px 0';
            bar.innerHTML = '<i class="bi bi-bell-slash" style="margin-right:4px"></i>Nicht stören aktiv';
        } else if (fwdActive && fwdTarget) {
            bar.style.cssText = 'display:block;padding:4px 8px;border-left:3px solid #1e40af;font-size:10px;font-weight:500;color:#1e3a8a;margin:0 0 2px 0';
            bar.innerHTML = '<i class="bi bi-arrow-return-right" style="margin-right:4px"></i>Weiterleitung: ' + fwdTarget;
        } else if (vmCount > 0) {
            bar.style.cssText = 'display:block;padding:4px 8px;border-left:3px solid #b45309;font-size:10px;font-weight:500;color:#92400e;margin:0 0 2px 0';
            bar.innerHTML = '<i class="bi bi-voicemail" style="margin-right:4px"></i>' + vmCount + ' neue Voicemail-Nachricht' + (vmCount > 1 ? 'en' : '');
        } else {
            bar.style.display = 'none';
            bar.innerHTML = '';
        }
    }
};

// ── Rufweiterleitung ───────────────────────────────────────
Softphone.callForward = function() {
    if (Softphone._ext.fwd_active) {
        Softphone._ext.fwd_active = false;
        Softphone._ext.fwd_target = '';
        Softphone._updateStatusIndicators();
        Softphone.setNumber('*73');
        Softphone.call();
        return;
    }
    const target = prompt('Weiterleitungsziel:', '');
    if (!target) return;
    Softphone.setNumber('*72' + target);
    Softphone._ext.fwd_target = target;
    Softphone._ext.fwd_active = true;
    Softphone._updateStatusIndicators();
    Softphone.call();
};

// ── Pickup ─────────────────────────────────────────────────
Softphone.pickup = function() {
    Softphone.setNumber('*8');
    Softphone.call();
};

// ── Letzte Anrufe ──────────────────────────────────────────
Softphone.showRecent = async function() {
    const vmExts = (Softphone._ext.vm_ext || '').split(',').map(e => e.trim()).filter(Boolean);
    const cfgExt = document.getElementById('sp-cfg-user')?.value.trim();
    const allExts = [...new Set([...vmExts, cfgExt].filter(Boolean))];
    if (!allExts.length) return;
    const panel = document.getElementById('sp-recent-panel');
    if (!panel) return;
    if (panel.style.display === 'block') { Softphone.toggleRecent(); return; }
    document.getElementById('sp-recent-body').innerHTML =
        '<div style="padding:8px;font-size:11px;color:var(--text-muted)">Lade...</div>';
    Softphone._positionRecent();
    panel.style.display = 'block';
    try {
        const results = await Promise.all(allExts.map(e =>
            fetch('/crm/api/telefon/cdr/?extension=' + e + '&days=7&limit=20').then(r => r.json())
        ));
        const rows = results.flatMap(d => d.rows || [])
            .sort((a,b) => new Date(b.calldate||0) - new Date(a.calldate||0))
            .slice(0, 30);
        Softphone._lastCdrRows = rows;
        Softphone._renderRecent(rows);
    } catch(e) { console.warn('Letzte Anrufe Fehler:', e); }
};

Softphone.toggleRecent = function() {
    const panel = document.getElementById('sp-recent-panel');
    if (panel) panel.style.display = 'none';
};

Softphone._positionRecent = function() {
    const modal = document.getElementById('sp-modal');
    const panel = document.getElementById('sp-recent-panel');
    if (!modal || !panel) return;
    const r = modal.getBoundingClientRect();
    const maxH = window.innerHeight - r.bottom - 8;
    panel.style.left      = r.left + 'px';
    panel.style.width     = r.width + 'px';
    panel.style.top       = (r.bottom + 4) + 'px';
    panel.style.maxHeight = Math.max(150, maxH) + 'px';
};

Softphone._renderRecent = function(rows) {
    const body = document.getElementById('sp-recent-body');
    if (!body) return;
    const BLUE = '#163258';
    const BLUE_HOV = '#1e4080';

    const missed   = rows.filter(r => r.direction === 'incoming' && r.disposition !== 'ANSWERED');
    const incoming = rows.filter(r => r.direction === 'incoming' && r.disposition === 'ANSWERED');
    const outgoing = rows.filter(r => r.direction === 'outgoing');

    function rowHtml(r) {
        const num  = r.direction === 'incoming' ? r.src : r.dst;
        const name = (r.contact && r.contact.name) ? r.contact.name : '';
        const disp = name || num;
        const time = r.calldate ? r.calldate.substring(11,16) + ' ' + r.calldate.substring(5,10) : '';
        const dur  = r.billsec_fmt || '';
        return '<div onclick="Softphone.setNumber(\'' + num + '\');Softphone._closeRecent()" '
            + 'style="display:flex;align-items:center;gap:6px;padding:5px 8px;'
            + 'border-bottom:0.5px solid var(--border-color);font-size:11px;cursor:pointer" '
            + 'onmouseover="this.style.background=\'var(--bg-secondary)\'" '
            + 'onmouseout="this.style.background=\'\'">'
            + '<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + disp + '</span>'
            + (name ? '<span style="font-size:9px;color:var(--text-muted);flex-shrink:0">' + num + '</span>' : '')
            + '<span style="font-size:9px;color:var(--text-muted);flex-shrink:0;margin-left:4px">' + time + '</span>'
            + (dur ? '<span style="font-size:9px;color:var(--text-muted);flex-shrink:0;margin-left:2px">' + dur + '</span>' : '')
            + '</div>';
    }

    function secHtml(id, label, dotColor, rows) {
        const dot = '<span style="width:7px;height:7px;border-radius:50%;background:' + dotColor + ';flex-shrink:0;margin-right:5px"></span>';
        const closed = Softphone._recentClosedSecs && Softphone._recentClosedSecs[id];
        const arr = closed ? '&#9658;' : '&#9660;';
        let html = '<div onclick="Softphone._recentToggleSec(\'' + id + '\')" '
            + 'style="padding:4px 8px;font-size:9px;font-weight:600;color:#fff;background:' + BLUE + ';'
            + 'border-top:0.5px solid #1e4080;display:flex;align-items:center;justify-content:space-between;cursor:pointer" '
            + 'onmouseover="this.style.background=\'' + BLUE_HOV + '\'" '
            + 'onmouseout="this.style.background=\'' + BLUE + '\'">'
            + '<div style="display:flex;align-items:center">' + dot + label + ' (' + rows.length + ')</div>'
            + '<span id="sp-recent-arr-' + id + '" style="font-size:9px;opacity:.8">' + arr + '</span>'
            + '</div>'
            + '<div id="sp-recent-sec-' + id + '" style="display:' + (closed ? 'none' : 'block') + '">';
        if (rows.length) {
            html += rows.map(rowHtml).join('');
        } else {
            html += '<div style="padding:6px 8px;font-size:11px;color:var(--text-muted)">Keine Einträge</div>';
        }
        html += '</div>';
        return html;
    }

    body.innerHTML =
        secHtml('missed',   'Abwesenheit', missed.length   > 0 ? '#ef4444' : '#22c55e', missed)
      + secHtml('incoming', 'Angenommen',  incoming.length > 0 ? '#22c55e' : '#22c55e', incoming)
      + secHtml('outgoing', 'Gewählt',     outgoing.length > 0 ? '#22c55e' : '#22c55e', outgoing);
};

Softphone._recentClosedSecs = { missed: false, incoming: true, outgoing: true };

Softphone._recentToggleSec = function(id) {
    const sec = document.getElementById('sp-recent-sec-' + id);
    const arr = document.getElementById('sp-recent-arr-' + id);
    if (!sec) return;
    const open = sec.style.display !== 'none';
    Softphone._recentClosedSecs[id] = open;
    sec.style.display = open ? 'none' : 'block';
    if (arr) arr.textContent = open ? '\u25ba' : '\u25bc';
};

Softphone._closeRecent = function() {
    const panel = document.getElementById('sp-recent-panel');
    if (panel) panel.style.display = 'none';
};
// ── Extension Status Polling ───────────────────────────────
Softphone._statusInterval = null;
Softphone._startStatusPolling = function() {
    if (Softphone._statusInterval) clearInterval(Softphone._statusInterval);
    Softphone._pollStatus();
    Softphone._statusInterval = setInterval(Softphone._pollStatus, 10000);
};

Softphone._pollStatus = async function() {
    const exts = Softphone._ext.status_exts;
    const vmExt = Softphone._ext.vm_ext || '';
    if (!exts.length && !vmExt) return;
    try {
        const url = '/crm/api/telefon/fop/?extensions=' + (exts.length ? exts.join(',') : '10')
            + (vmExt ? '&vm_extensions=' + vmExt : '');
        const r = await fetch(url);
        const d = await r.json();
        if (!d.success) return;
        const vm = d.data.voicemail || {};
        Softphone._vmCount = Object.keys(vm).reduce(function(s, e) { return s + (vm[e] || 0); }, 0);
        Softphone._updateStatusIndicators();
        const panel = document.getElementById('sp-status-panel');
        if (!panel) return;
        Softphone._renderFOP(panel, d.data);
    } catch(e) { console.warn('FOP poll Fehler:', e); }
};

Softphone._renderFOP = function(panel, data) {
    const colors = {
        free:    { bg: '#dcfce7', color: '#14532d', label: 'frei',     dot: '#22c55e' },
        busy:    { bg: '#fef3c7', color: '#92400e', label: 'besetzt',  dot: '#ef4444' },
        dnd:     { bg: '#fee2e2', color: '#7f1d1d', label: 'DND',      dot: '#f59e0b' },
        offline: { bg: '#f3f4f6', color: '#6b7280', label: 'offline',  dot: '#9ca3af' },
        unknown: { bg: '#f3f4f6', color: '#6b7280', label: '?',        dot: '#9ca3af' },
    };
    const hov = "onmouseover=\"this.style.background='var(--bg-secondary)'\" onmouseout=\"this.style.background=''\"";
    const BLUE = '#163258';
    const BLUE_HOV = '#1e4080';

    function secHeader(secId, label, hasDot, dotColor) {
        const color = dotColor || (hasDot ? '#22c55e' : 'rgba(255,255,255,0.25)');
        const dot = '<span style="width:7px;height:7px;border-radius:50%;background:' + color + ';flex-shrink:0;margin-right:5px"></span>';
        return '<div onclick="Softphone._fopToggleSec(\'' + secId + '\')" '
            + 'style="padding:4px 8px;font-size:9px;font-weight:600;color:#fff;background:' + BLUE + ';'
            + 'border-top:0.5px solid #1e4080;display:flex;align-items:center;justify-content:space-between;cursor:pointer" '
            + 'onmouseover="this.style.background=\'' + BLUE_HOV + '\'" '
            + 'onmouseout="this.style.background=\'' + BLUE + '\'">'
            + '<div style="display:flex;align-items:center">' + dot + label + '</div>'
            + '<span id="fop-sec-arr-' + secId + '" style="font-size:9px;opacity:.8">&#9660;</span>'
            + '</div>'
            + '<div id="fop-sec-' + secId + '">';
    }

    let html = '';
    const myExt = Softphone._ext.vm_ext || '';

    // ── EXTENSIONS ──
    const exts = data.extensions || [];
    Softphone._fopExtCache = exts;
    const hasActiveExt = exts.some(function(r) { return r.status !== 'offline' && r.status !== 'unknown'; });
    html += secHeader('ext', 'EXTENSIONS', true, hasActiveExt ? '#22c55e' : 'rgba(255,255,255,0.25)');
    exts.forEach(function(r) {
        const c = colors[r.status] || colors.unknown;
        const isMe = myExt && r.extension === myExt;
        const actStyle = 'display:none;background:var(--bg-secondary,#f8f8f8);border-bottom:0.5px solid var(--border-color);padding:3px 6px;flex-wrap:wrap;gap:3px';
        let actBtns = '<span onclick="event.stopPropagation();Softphone.setNumber(\'' + r.extension + '\')" style="font-size:10px;padding:2px 6px;border:0.5px solid var(--border-color);border-radius:3px;cursor:pointer;background:var(--bg-primary)">&#9742; Anrufen</span>';
        if (isMe) {
            actBtns += '<span onclick="event.stopPropagation();Softphone.toggleDND()" style="font-size:10px;padding:2px 6px;border:0.5px solid #fca5a5;border-radius:3px;cursor:pointer;background:#fee2e2;color:#7f1d1d">' + (r.dnd ? 'DND aus' : 'DND an') + '</span>';
        }
        html += '<div onclick="Softphone._fopExtClick(this)" data-ext="' + r.extension + '" style="display:flex;align-items:center;gap:6px;padding:5px 8px;border-bottom:0.5px solid var(--border-color);font-size:11px;cursor:pointer" ' + hov + '>';
        html += '<span style="width:7px;height:7px;border-radius:50%;background:' + c.dot + ';flex-shrink:0;pointer-events:none"></span>';
        html += '<span style="font-weight:' + (isMe ? '600' : '400') + ';flex:1;pointer-events:none">' + (isMe ? '&#9733; ' : '') + 'Ext. ' + r.extension + '</span>';
        html += '<div style="display:flex;align-items:center;gap:4px;pointer-events:none">';
        html += '<span style="background:' + c.bg + ';color:' + c.color + ';padding:1px 5px;border-radius:3px;font-size:9px">' + c.label + '</span>';
        html += '<span class="sp-arr" style="font-size:9px;color:var(--text-muted)">&#9658;</span>';
        html += '</div></div>';
        html += '<div id="fop-act-' + r.extension + '" style="' + actStyle + '">' + actBtns + '</div>';
    });
    html += '</div>';

    // ── PARKING ──
    const parkSlots = ['701','702','703','704','705','706','707','708','709'];
    const parkedMap = {};
    (data.parking || []).forEach(function(p) { if (p.slot) parkedMap[p.slot] = p; });
    const hasParked = Object.keys(parkedMap).length > 0;
    html += secHeader('park', 'PARKING 700', true, hasParked ? '#ef4444' : '#22c55e');
    parkSlots.forEach(function(slot) {
        const p = parkedMap[slot];
        if (p) {
            html += '<div style="display:flex;align-items:center;gap:6px;padding:4px 8px;border-bottom:0.5px solid var(--border-color);font-size:11px">';
            html += '<span style="width:7px;height:7px;border-radius:50%;background:#ef4444;flex-shrink:0"></span>';
            html += '<span style="color:var(--text-muted);width:24px">' + slot + '</span>';
            html += '<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + (p.caller_name || p.caller_id || '?') + '</span>';
            html += '<span style="font-size:10px;color:var(--text-muted);margin-right:4px">' + (p.duration || '') + 's</span>';
            html += '<span onclick="Softphone.setNumber(\'' + slot + '\');Softphone.call()" '
                + 'style="font-size:10px;padding:1px 5px;border:0.5px solid #86efac;border-radius:3px;cursor:pointer;background:#f0fdf4;color:#14532d">&#9742; Abholen</span>';
            html += '</div>';
        } else {
            html += '<div style="display:flex;align-items:center;gap:6px;padding:4px 8px;border-bottom:0.5px solid var(--border-color);font-size:11px;color:var(--text-muted)">';
            html += '<span style="width:7px;height:7px;border-radius:50%;background:#d1d5db;flex-shrink:0"></span>';
            html += '<span style="width:24px">' + slot + '</span>';
            html += '<span style="flex:1">leer</span>';
            html += '<span onclick="Softphone._parkHere(\'' + slot + '\')" '
                + 'style="font-size:10px;padding:1px 5px;border:0.5px solid #7dd3fc;border-radius:3px;cursor:pointer;background:#e0f2fe;color:#0c4a6e">&#8659; Park</span>';
            html += '</div>';
        }
    });
    html += '</div>';

    // ── KONFERENZEN ──
    const confRooms = { '034': 'MeetMeFree', '035': 'MeetMePin', '5555': 'AllHands' };
    const mmMap = {};
    (data.meetme || []).forEach(function(m) { mmMap[m.conference] = m; });
    const cbMap = {};
    (data.confbridge || []).forEach(function(c) { cbMap[c.conference] = c; });
    const hasConf = Object.keys(confRooms).some(function(num) {
        const mm = mmMap[num]; const cb = cbMap[num];
        return (mm && mm.users && mm.users.length > 0) || (cb && cb.parties > 0);
    });
    html += secHeader('conf', 'KONFERENZEN', true, hasConf ? '#ef4444' : '#22c55e');
    Object.keys(confRooms).forEach(function(num) {
        const name = confRooms[num];
        const mm = mmMap[num]; const cb = cbMap[num];
        const count = mm ? (mm.users ? mm.users.length : 0) : (cb ? (cb.parties || 0) : 0);
        html += '<div style="display:flex;align-items:center;gap:6px;padding:4px 8px;border-bottom:0.5px solid var(--border-color);font-size:11px">';
        html += '<span style="width:7px;height:7px;border-radius:50%;background:' + (count > 0 ? '#22c55e' : '#d1d5db') + ';flex-shrink:0"></span>';
        html += '<span onclick="Softphone.setNumber(\'' + num + '\')" style="color:var(--text-muted);width:32px;cursor:pointer">' + num + '</span>';
        html += '<span onclick="Softphone.setNumber(\'' + num + '\')" style="flex:1;cursor:pointer">' + name + '</span>';
        html += '<span style="font-size:10px;color:var(--text-muted);margin-right:4px">' + (count > 0 ? count + ' Tlnhm.' : 'leer') + '</span>';
        html += '<span onclick="Softphone._joinConference(\'' + num + '\')" '
            + 'style="font-size:10px;padding:1px 5px;border:0.5px solid #86efac;border-radius:3px;cursor:pointer;background:#f0fdf4;color:#14532d">&#8594; Konf</span>';
        html += '</div>';
    });
    html += '</div>';

    // ── VOICEMAIL ──
    const vm = data.voicemail || {};
    const vmKeys = Object.keys(vm);
    const hasVm = vmKeys.some(function(e) { return vm[e] > 0; });
    html += secHeader('vm', 'VOICEMAIL', true, hasVm ? '#ef4444' : '#22c55e');
    vmKeys.forEach(function(ext) {
        const count = vm[ext];
        const dotColor = count > 0 ? '#ef4444' : '#22c55e';
        html += '<div style="display:flex;align-items:center;gap:6px;padding:5px 8px;border-bottom:0.5px solid var(--border-color);font-size:11px">';
        html += '<span style="width:7px;height:7px;border-radius:50%;background:' + dotColor + ';flex-shrink:0"></span>';
        html += '<span style="flex:1">Ext. ' + ext + '</span>';
        if (count > 0) {
            html += '<span style="background:#fee2e2;color:#7f1d1d;padding:1px 5px;border-radius:3px;font-size:10px;font-weight:600;margin-right:4px">' + count + ' neu</span>';
        }
        html += '<span onclick="Softphone.setNumber(\'*97' + ext + '\');Softphone.call()" '
            + 'style="font-size:10px;padding:1px 5px;border:0.5px solid var(--border-color);border-radius:3px;cursor:pointer;background:var(--bg-secondary)">&#9654; Abhören</span>';
        html += '</div>';
    });
    html += '</div>';

    panel.innerHTML = html;
    ['ext','park','conf','vm'].forEach(function(id) {
        if (!(id in Softphone._fopClosedSecs)) Softphone._fopClosedSecs[id] = true;
    });
    if (Softphone._fopApplyOpen) Softphone._fopApplyOpen();
    if (Softphone._fopApplySecs) Softphone._fopApplySecs();
}
Softphone._fopOpenExt = null;

Softphone._fopExtClick = function(row) {
    if (!row || !row.dataset) return;
    const ext = row.dataset.ext;
    Softphone._fopOpenExt = (Softphone._fopOpenExt === ext) ? null : ext;
    Softphone._fopApplyOpen();
};

Softphone._fopApplyOpen = function() {
    const ext = Softphone._fopOpenExt;
    document.querySelectorAll('[id^="fop-act-"]').forEach(function(a) {
        a.style.display = (ext && a.id === 'fop-act-' + ext) ? 'flex' : 'none';
    });
    document.querySelectorAll('.sp-arr').forEach(function(arr) {
        const r = arr.closest('[data-ext]');
        if (r) arr.textContent = (r.dataset.ext === ext) ? '\u25bc' : '\u25ba';
    });
};
// ── Schnellwahl Panel ──────────────────────────────────────
Softphone._renderSpeedDials = async function() {
    const panel = document.getElementById('sp-speed-list');
    if (!panel) return;
    const dials = Softphone._ext.speed_dials;
    if (!dials.length) {
        panel.innerHTML = '<div style="padding:8px;font-size:10px;color:var(--text-muted)">Keine Schnellwahl konfiguriert.<br>Kontakt aus Suche hierher ziehen.</div>';
        return;
    }
    panel.innerHTML = '<div style="padding:6px 8px;font-size:10px;color:var(--text-muted)">Lade...</div>';
    try {
        const items = await Promise.all(dials.map(async d => {
            if (d.type === 'manual') return d;
            if (d.crm_id && d.crm_type === 'firma') {
                try {
                    const r = await fetch('/crm/api/kunden/' + d.crm_id + '/');
                    const c = await r.json();
                    const ap = (c.ansprechpartner || []).map(a => ({
                        name:   (a.contact__first_name || '') + ' ' + (a.contact__last_name || ''),
                        phones: a.phones || [],
                    }));
                    return { type:'firma', name: c.name || d.name, ap };
                } catch(e) { return { type:'firma', name: d.name, ap:[] }; }
            }
            if (d.crm_id) {
                try {
                    const r = await fetch('/crm/api/berater/' + d.crm_id + '/');
                    const c = await r.json();
                    return {
                        type:   'person',
                        name:   c.full_name || d.name,
                        firma:  c.account ? c.account.name : '',
                        phones: c.phones || [],
                    };
                } catch(e) { return { type:'person', name: d.name, firma:'', phones:[] }; }
            }
            return d;
        }));
        Softphone._ext._speed_items = items;
        Softphone._renderSpeedList(panel, items);
    } catch(e) { console.warn('SpeedDial render Fehler:', e); }
};

Softphone._renderSpeedList = function(panel, items) {
    panel.innerHTML = '';
    items.forEach(function(item, idx) {
        const el = document.createElement('div');
        el.style.cssText = 'border-bottom:0.5px solid var(--border-color)';

        const nameCSS = 'font-weight:500;font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1';
        const subCSS  = 'font-size:10px;color:var(--text-muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap';
        const delCSS  = 'font-size:11px;color:var(--text-muted);cursor:pointer;flex-shrink:0;margin-left:4px';
        const headCSS = 'padding:5px 8px;display:flex;align-items:center;gap:5px;cursor:pointer;';
        const subBG   = 'background:var(--bg-secondary,#f8f8f8)';

        function numRow(p, indent) {
            const num = p.norm || p.raw || '';
            const lbl = p.label || p.field_name || '';
            return '<div onclick="Softphone.setNumber(\'' + num + '\')" '
                + 'style="padding:4px 10px 4px ' + indent + 'px;font-size:10px;display:flex;'
                + 'justify-content:space-between;cursor:pointer;' + subBG + ';'
                + 'border-top:0.5px solid var(--border-color)" '
                + 'onmouseover="this.style.background=\'var(--border-color)\'" '
                + 'onmouseout="this.style.background=\'var(--bg-secondary,#f8f8f8)\'">'
                + '<span style="color:var(--text-muted)">' + lbl + '</span>'
                + '<span>' + num + '</span></div>';
        }

        const uid = 'spd-' + idx;

        if (item.type === 'firma') {
            let apHTML = '';
            (item.ap || []).forEach(function(ap, ai) {
                const auid = uid + '-' + ai;
                const nums = (ap.phones || []).map(function(p) { return numRow(p, 24); }).join('');
                apHTML += '<div>'
                    + '<div onclick="const s=document.getElementById(\'' + auid + '\');s.style.display=s.style.display===\'none\'?\'block\':\'none\';this.querySelector(\'.sp-arr\').textContent=s.style.display===\'block\'?\'&#9660;\':\'&#9658;\'" '
                    + 'style="padding:4px 8px 4px 14px;font-size:11px;display:flex;justify-content:space-between;'
                    + 'cursor:pointer;border-top:0.5px solid var(--border-color);' + subBG + '" '
                    + 'onmouseover="this.style.filter=\'brightness(0.95)\'" onmouseout="this.style.filter=\'\'"> '
                    + '<span>' + ap.name.trim() + '</span>'
                    + '<span class="sp-arr" style="font-size:9px;color:var(--text-muted)">&#9658;</span></div>'
                    + '<div id="' + auid + '" style="display:none">' + nums + '</div></div>';
            });
            el.innerHTML = '<div onclick="const s=document.getElementById(\'' + uid + '\');s.style.display=s.style.display===\'none\'?\'block\':\'none\';this.querySelector(\'.sp-arr\').textContent=s.style.display===\'block\'?\'&#9660;\':\'&#9658;\'" '
                + 'style="' + headCSS + 'justify-content:space-between" '
                + 'onmouseover="this.style.background=\'var(--bg-secondary)\'" onmouseout="this.style.background=\'\'">'
                + '<div style="min-width:0;flex:1">'
                + '<div style="' + nameCSS + '">' + item.name + '</div>'
                + '<div style="' + subCSS + '">' + (item.ap||[]).length + ' Ansprechpartner</div>'
                + '</div>'
                + '<span class="sp-arr" style="font-size:9px;color:var(--text-muted);margin-right:4px">&#9658;</span>'
                + '<span onclick="event.stopPropagation();Softphone._speedDialRemove(' + idx + ')" style="' + delCSS + '">&#10005;</span>'
                + '</div>'
                + '<div id="' + uid + '" style="display:none">' + apHTML + '</div>';

        } else if (item.type === 'person') {
            const nums = (item.phones || []).map(function(p) { return numRow(p, 16); }).join('');
            el.innerHTML = '<div onclick="const s=document.getElementById(\'' + uid + '\');s.style.display=s.style.display===\'none\'?\'block\':\'none\';this.querySelector(\'.sp-arr\').textContent=s.style.display===\'block\'?\'&#9660;\':\'&#9658;\'" '
                + 'style="' + headCSS + 'justify-content:space-between" '
                + 'onmouseover="this.style.background=\'var(--bg-secondary)\'" onmouseout="this.style.background=\'\'">'
                + '<div style="min-width:0;flex:1">'
                + '<div style="' + nameCSS + '">' + item.name + '</div>'
                + (item.firma ? '<div style="' + subCSS + '">' + item.firma + '</div>' : '')
                + '</div>'
                + '<span class="sp-arr" style="font-size:9px;color:var(--text-muted);margin-right:4px">&#9658;</span>'
                + '<span onclick="event.stopPropagation();Softphone._speedDialRemove(' + idx + ')" style="' + delCSS + '">&#10005;</span>'
                + '</div>'
                + '<div id="' + uid + '" style="display:none">' + nums + '</div>';

        } else {
            const num = item.num || '';
            el.innerHTML = '<div onclick="const s=document.getElementById(\'' + uid + '\');s.style.display=s.style.display===\'none\'?\'block\':\'none\';this.querySelector(\'.sp-arr\').textContent=s.style.display===\'block\'?\'&#9660;\':\'&#9658;\'" '
                + 'style="' + headCSS + 'justify-content:space-between" '
                + 'onmouseover="this.style.background=\'var(--bg-secondary)\'" onmouseout="this.style.background=\'\'">'
                + '<div style="min-width:0;flex:1">'
                + '<div style="' + nameCSS + '">' + item.name + '</div>'
                + '</div>'
                + '<span class="sp-arr" style="font-size:9px;color:var(--text-muted);margin-right:4px">&#9658;</span>'
                + '<span onclick="event.stopPropagation();Softphone._speedDialRemove(' + idx + ')" style="' + delCSS + '">&#10005;</span>'
                + '</div>'
                + '<div id="' + uid + '" style="display:none">'
                + '<div onclick="Softphone.setNumber(\'' + num + '\')" '
                + 'style="padding:4px 10px 4px 16px;font-size:10px;display:flex;justify-content:space-between;cursor:pointer;'
                + 'background:var(--bg-secondary,#f8f8f8);border-top:0.5px solid var(--border-color)" '
                + 'onmouseover="this.style.background=\'var(--border-color)\'" '
                + 'onmouseout="this.style.background=\'var(--bg-secondary,#f8f8f8)\'" >'
                + '<span style="color:var(--text-muted)">Nummer</span>'
                + '<span>' + num + '</span></div>'
                + '</div>';
        }

        panel.appendChild(el);
    });
}
Softphone._speedDialRemove = function(idx) {
    Softphone._ext.speed_dials.splice(idx, 1);
    Softphone._saveSpeedDials();
    Softphone._renderSpeedDials();
};

Softphone._saveSpeedDials = async function() {
    try {
        await fetch('/crm/api/user-settings/', {
            method: 'POST',
            headers: {'Content-Type':'application/json','X-CSRFToken':Softphone._csrf()},
            body: JSON.stringify({ softphone_speed_dials: Softphone._ext.speed_dials })
        });
    } catch(e) { console.warn('SpeedDial speichern fehlgeschlagen:', e); }
};

Softphone._speedDialAddFromContact = async function(contact) {
    const already = Softphone._ext.speed_dials.find(d => d.crm_id === contact.crm_id);
    if (already) return;
    Softphone._ext.speed_dials.push({
        crm_id:   contact.crm_id,
        crm_type: contact.typ === 'kunde' ? 'firma' : 'person',
        name:     contact.full_name || contact.name || '',
        type:     contact.typ === 'kunde' ? 'firma' : 'person',
    });
    await Softphone._saveSpeedDials();
    Softphone._renderSpeedDials();
};

Softphone._speedDialAddManual = function() {
    const f = document.getElementById('sp-speed-add-form');
    if (f) { f.style.display = f.style.display === 'flex' ? 'none' : 'flex'; }
};

Softphone._speedDialCancelManual = function() {
    const f = document.getElementById('sp-speed-add-form');
    if (f) f.style.display = 'none';
    const l = document.getElementById('sp-speed-add-label');
    const n = document.getElementById('sp-speed-add-number');
    if (l) l.value = ''; if (n) n.value = '';
};

Softphone._speedDialConfirmManual = async function() {
    const label = document.getElementById('sp-speed-add-label')?.value.trim();
    const num   = document.getElementById('sp-speed-add-number')?.value.trim();
    if (!label || !num) return;
    Softphone._ext.speed_dials.push({ type:'manual', name:label, num });
    await Softphone._saveSpeedDials();
    Softphone._renderSpeedDials();
    Softphone._speedDialCancelManual();
};

// ── Settings laden erweitern ──────────────────────────────
Softphone._loadExtSettingsIntoForm = function(s) {
    const vmEl   = document.getElementById('sp-cfg-vm-ext');
    const dndEl  = document.getElementById('sp-cfg-dnd-ext');
    const stsEl  = document.getElementById('sp-cfg-status-exts');
    if (vmEl)  vmEl.value  = s.softphone_vm_ext      || '';
    if (dndEl) dndEl.value = s.softphone_dnd_ext     || '';
    if (stsEl) stsEl.value = s.softphone_status_exts || '';
};

// saveAndRegister überschreiben um neue Felder mitzuspeichern
const _origSaveAndRegister = Softphone.saveAndRegister;
Softphone.saveAndRegister = async function() {
    const vmExt   = document.getElementById('sp-cfg-vm-ext')?.value.trim()  || '';
    const dndExt  = document.getElementById('sp-cfg-dnd-ext')?.value.trim() || '';
    const stsExts = document.getElementById('sp-cfg-status-exts')?.value.trim() || '';
    Softphone._ext.vm_ext      = vmExt;
    Softphone._ext.dnd_ext     = dndExt;
    Softphone._ext.status_exts = stsExts.split(',').map(e => e.trim()).filter(Boolean);
    try {
        await fetch('/crm/api/user-settings/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': Softphone._csrf() },
            body: JSON.stringify({
                softphone_vm_ext:      vmExt,
                softphone_dnd_ext:     dndExt,
                softphone_status_exts: stsExts,
            })
        });
    } catch(e) { console.warn('Ext-Settings speichern fehlgeschlagen:', e); }
    if (Softphone._ext.status_exts.length) Softphone._startStatusPolling();
    await _origSaveAndRegister.call(Softphone);
};

// ── Panel Toggle ──────────────────────────────────────────
Softphone._positionPanel = function(panelId, side) {
    const modal = document.getElementById('sp-modal');
    const panel = document.getElementById(panelId);
    if (!modal || !panel) return;
    const r = modal.getBoundingClientRect();
    panel.style.position = 'fixed';
    panel.style.top      = r.top + 'px';
    panel.style.zIndex   = '10000';
    if (side === 'left') {
        panel.style.left  = '';
        panel.style.right = (window.innerWidth - r.left + 4) + 'px';
    } else {
        panel.style.right = '';
        panel.style.left  = (r.right + 4) + 'px';
    }
};

Softphone.toggleSpeedDial = function() {
    const panel = document.getElementById('sp-speed-panel');
    const btn   = document.getElementById('sp-speed-toggle');
    if (!panel) return;
    const open = panel.style.display === 'none';
    if (open) Softphone._positionPanel('sp-speed-panel', 'left');
    panel.style.display = open ? 'block' : 'none';
    if (btn) btn.style.background = open ? '#dbeafe' : 'var(--bg-secondary,#f8f8f8)';
    if (open) Softphone._renderSpeedDials();
};

Softphone.toggleFOP = function() {
    const panel = document.getElementById('sp-fop-panel');
    const btn   = document.getElementById('sp-fop-toggle');
    if (!panel) return;
    const open = panel.style.display === 'none';
    if (open) Softphone._positionPanel('sp-fop-panel', 'right');
    panel.style.display = open ? 'block' : 'none';
    if (btn) btn.style.background = open ? '#dbeafe' : 'var(--bg-secondary,#f8f8f8)';
    if (open) {
        Softphone._pollStatus();
        if (!Softphone._statusInterval) Softphone._startStatusPolling();
    } else {
        if (Softphone._statusInterval) {
            clearInterval(Softphone._statusInterval);
            Softphone._statusInterval = null;
        }
    }
};

// ── Init aufrufen ──────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => Softphone._loadExtSettings(), 500);
});

// ── Drag & Pin ─────────────────────────────────────────────
Softphone._pinned = localStorage.getItem('sp_pinned') === '1';

Softphone._applyPinnedPosition = function() {
    const modal = document.getElementById('sp-modal');
    if (!modal) return;
    const fopOpen = document.getElementById('sp-fop-panel')?.style.display === 'block';
    const fopW    = fopOpen ? 164 : 0;
    modal.style.left  = '';
    modal.style.right = (200 + fopW) + 'px';
    modal.style.top   = '80px';
};

Softphone._restorePosition = function() {
    const modal = document.getElementById('sp-modal');
    if (!modal) return;
    if (Softphone._pinned) {
        Softphone._applyPinnedPosition();
        return;
    }
    const x = localStorage.getItem('sp_modal_x');
    const y = localStorage.getItem('sp_modal_y');
    if (x && y) {
        modal.style.right = '';
        modal.style.left  = x + 'px';
        modal.style.top   = y + 'px';
    } else {
        modal.style.right = '20px';
        modal.style.left  = '';
        modal.style.top   = '80px';
    }
};

Softphone._initDrag = function() {
    const handle = document.getElementById('sp-drag-handle');
    const modal  = document.getElementById('sp-modal');
    if (!handle || !modal) return;

    let dragging = false;
    let startX, startY, origLeft, origTop;

    handle.addEventListener('mousedown', function(e) {
        if (e.target.closest('button')) return;
        if (Softphone._pinned) return;
        dragging = true;
        const spd = document.getElementById('sp-speed-panel');
        const fop = document.getElementById('sp-fop-panel');
        if (spd && spd.style.display === 'block') Softphone.toggleSpeedDial();
        if (fop && fop.style.display === 'block') Softphone.toggleFOP();
        Softphone._closeRecent();
        const rect = modal.getBoundingClientRect();
        startX   = e.clientX;
        startY   = e.clientY;
        origLeft = rect.left;
        origTop  = rect.top;
        modal.style.right = '';
        modal.style.left  = origLeft + 'px';
        modal.style.top   = origTop  + 'px';
        document.body.style.userSelect = 'none';
    });

    document.addEventListener('mousemove', function(e) {
        if (!dragging) return;
        const dx   = e.clientX - startX;
        const dy   = e.clientY - startY;
        const newL = Math.max(0, Math.min(window.innerWidth  - 260, origLeft + dx));
        const newT = Math.max(0, Math.min(window.innerHeight - 50,  origTop  + dy));
        modal.style.left = newL + 'px';
        modal.style.top  = newT + 'px';
    });

    document.addEventListener('mouseup', function(e) {
        if (!dragging) return;
        dragging = false;
        document.body.style.userSelect = '';
        localStorage.setItem('sp_modal_x', parseInt(modal.style.left));
        localStorage.setItem('sp_modal_y', parseInt(modal.style.top));
    });
};

Softphone.togglePin = function() {
    Softphone._pinned = !Softphone._pinned;
    localStorage.setItem('sp_pinned', Softphone._pinned ? '1' : '0');
    const icon = document.getElementById('sp-pin-icon');
    const btn  = document.getElementById('sp-pin-btn');
    if (Softphone._pinned) {
        if (icon) icon.className = 'bi bi-pin-fill';
        if (btn)  btn.style.color = '#fbbf24';
        Softphone._applyPinnedPosition();
    } else {
        if (icon) icon.className = 'bi bi-arrows-move';
        if (btn)  btn.style.color = 'rgba(255,255,255,0.5)';
    }
};

// toggle() erweitern: Position beim Öffnen wiederherstellen + Drag init
const _origToggle = Softphone.toggle;
Softphone.toggle = function() {
    _origToggle.call(Softphone);
    const modal = document.getElementById('sp-modal');
    if (modal && modal.style.display === 'block') {
        Softphone._restorePosition();
        Softphone._initDrag();
        // Panels schliessen beim Oeffnen
        const spd = document.getElementById('sp-speed-panel');
        const fop = document.getElementById('sp-fop-panel');
        if (spd && spd.style.display === 'block') Softphone.toggleSpeedDial();
        if (fop && fop.style.display === 'block') Softphone.toggleFOP();
        // Pin-Icon beim Öffnen korrekt setzen
        const icon = document.getElementById('sp-pin-icon');
        const btn  = document.getElementById('sp-pin-btn');
        if (Softphone._pinned) {
            if (icon) icon.className = 'bi bi-pin-fill';
            if (btn)  btn.style.color = '#fbbf24';
        } else {
            if (icon) icon.className = 'bi bi-arrows-move';
            if (btn)  btn.style.color = 'rgba(255,255,255,0.5)';
        }
    }
};

// ── Schnellwahl: Firma hinzufügen ──────────────────────────
Softphone._speedDialAddFirma = function() {
    const existing = document.getElementById('sp-firma-search-form');
    if (existing) { existing.remove(); return; }
    const panel = document.getElementById('sp-speed-panel');
    if (!panel) return;
    const form = document.createElement('div');
    form.id = 'sp-firma-search-form';
    form.style.cssText = 'padding:6px 8px;border-top:1px solid var(--border-color);';
    form.innerHTML =
        '<input id="sp-firma-q" placeholder="Firmaname suchen..." '
        + 'style="font-size:11px;padding:3px 6px;border:1px solid var(--border-color);border-radius:4px;'
        + 'width:100%;box-sizing:border-box;background:var(--bg-secondary,#f8f8f8);color:var(--text-primary)" '
        + 'oninput="Softphone._speedDialSearchFirma(this.value)">'
        + '<div id="sp-firma-results" style="max-height:120px;overflow-y:auto;margin-top:4px"></div>';
    panel.appendChild(form);
    setTimeout(() => document.getElementById('sp-firma-q')?.focus(), 50);
};

Softphone._speedDialSearchFirma = async function(q) {
    const res = document.getElementById('sp-firma-results');
    if (!res) return;
    if (!q || q.length < 2) { res.innerHTML = ''; return; }
    try {
        const r = await fetch('/crm/api/kunden/?q=' + encodeURIComponent(q) + '&per_page=6');
        const d = await r.json();
        const items = (d.results || []).slice(0, 6);
        if (!items.length) { res.innerHTML = '<div style="font-size:10px;color:var(--text-muted);padding:4px">Keine Treffer</div>'; return; }
        res.innerHTML = items.map(function(a) {
            const dataStr = JSON.stringify({
                crm_id: a.crm_id, type: 'firma', crm_type: 'firma', name: a.name
            }).replace(/"/g, '&quot;');
            return '<div onclick="Softphone._speedDialAddFirmaEntry(JSON.parse(this.dataset.firma))" '
                + 'data-firma="' + dataStr + '" '
                + 'style="padding:4px 6px;font-size:11px;cursor:pointer;border-bottom:0.5px solid var(--border-color)" '
                + 'onmouseover="this.style.background=\'var(--bg-secondary)\'" '
                + 'onmouseout="this.style.background=\'\'">'
                + a.name + '</div>';
        }).join('');
    } catch(e) { console.warn('Firma-Suche Fehler:', e); }
};

Softphone._speedDialAddFirmaEntry = async function(firma) {
    const already = Softphone._ext.speed_dials.find(function(d) { return d.crm_id === firma.crm_id; });
    if (!already) {
        Softphone._ext.speed_dials.push(firma);
        await Softphone._saveSpeedDials();
        Softphone._renderSpeedDials();
    }
    const form = document.getElementById('sp-firma-search-form');
    if (form) form.remove();
};

// ── FOP Section Toggle ─────────────────────────────────────
Softphone._fopClosedSecs = {};

Softphone._fopToggleSec = function(secId) {
    const sec = document.getElementById('fop-sec-' + secId);
    const arr = document.getElementById('fop-sec-arr-' + secId);
    if (!sec) return;
    const open = sec.style.display !== 'none';
    Softphone._fopClosedSecs[secId] = open;
    sec.style.display = open ? 'none' : 'block';
    if (arr) arr.textContent = open ? '\u25ba' : '\u25bc';
};

Softphone._fopApplySecs = function() {
    Object.keys(Softphone._fopClosedSecs).forEach(function(secId) {
        if (!Softphone._fopClosedSecs[secId]) return;
        const sec = document.getElementById('fop-sec-' + secId);
        const arr = document.getElementById('fop-sec-arr-' + secId);
        if (sec) sec.style.display = 'none';
        if (arr) arr.textContent = '\u25ba';
    });
};

// ── FOP Park ──────────────────────────────────────────────
Softphone._parkHere = async function(slot) {
    const myExt = document.getElementById('sp-cfg-user')?.value.trim() || Softphone._ext.vm_ext || '';
    if (!myExt) { alert('Bitte eigene Extension in den Einstellungen konfigurieren.'); return; }
    try {
        const r = await fetch('/crm/api/telefon/park/', {
            method: 'POST',
            headers: {'Content-Type':'application/json','X-CSRFToken':Softphone._csrf()},
            body: JSON.stringify({ extension: myExt })
        });
        const d = await r.json();
        if (d.success) {
            console.log('Geparkt auf Slot ' + slot);
        } else {
            alert('Parken fehlgeschlagen: ' + (d.error || 'Unbekannter Fehler'));
        }
    } catch(e) { console.warn('Park Fehler:', e); }
};

// ── FOP Conference ────────────────────────────────────────
Softphone._joinConference = async function(conference) {
    const myExt = document.getElementById('sp-cfg-user')?.value.trim() || Softphone._ext.vm_ext || '';
    if (!myExt) { alert('Bitte eigene Extension in den Einstellungen konfigurieren.'); return; }
    try {
        const r = await fetch('/crm/api/telefon/conference/', {
            method: 'POST',
            headers: {'Content-Type':'application/json','X-CSRFToken':Softphone._csrf()},
            body: JSON.stringify({ extension: myExt, conference: conference })
        });
        const d = await r.json();
        if (!d.success) {
            alert('Konferenz fehlgeschlagen: ' + (d.error || 'Unbekannter Fehler'));
        }
    } catch(e) { console.warn('Conference Fehler:', e); }
};

// ── Transfer Panel ────────────────────────────────────────
Softphone.toggleTransfer = function() {
    const panel = document.getElementById('sp-transfer-panel');
    if (!panel) return;
    if (panel.style.display === 'block') {
        panel.style.display = 'none';
        return;
    }
    Softphone._positionTransfer();
    panel.style.display = 'block';
    // Aktive Nummer anzeigen
    const num = document.getElementById('sp-display')?.value || '';
    const el = document.getElementById('sp-transfer-active-num');
    if (el && num) el.textContent = num;
    Softphone._renderTransferBody();
    setTimeout(() => document.getElementById('sp-transfer-input')?.focus(), 100);
};

Softphone._positionTransfer = function() {
    const modal = document.getElementById('sp-modal');
    const panel = document.getElementById('sp-transfer-panel');
    if (!modal || !panel) return;
    const r = modal.getBoundingClientRect();
    panel.style.left      = r.left + 'px';
    panel.style.width     = r.width + 'px';
    panel.style.top       = '';
    panel.style.bottom    = (window.innerHeight - r.top + 4) + 'px';
    panel.style.maxHeight = Math.max(200, r.top - 12) + 'px';
};

Softphone.doTransfer = function(num) {
    if (!num || !num.trim()) return;
    num = num.trim();
    var session = Softphone._currentSession;
    if (session && session.isEstablished && session.isEstablished()) {
        try {
            var referNotifier = session.refer('sip:' + num + '@' + (Softphone._sipServer || 'pbx.win.abcona.info'));
            var panel = document.getElementById('sp-transfer-panel');
            if (panel) panel.style.display = 'none';
            referNotifier.on('requestSucceeded', function() {
                setTimeout(function() {
                    try { session.terminate(); } catch(e) {}
                    Softphone._showTransferSuccess(num);
                }, 500);
            });
        } catch(e) {
            Softphone.setNumber('##' + num);
            Softphone.call();
        }
    } else {
        alert('Kein aktives Gespräch für Transfer.');
    }
};

Softphone._showTransferSuccess = function(num) {
    var box = document.getElementById('sp-transfer-inline');
    if (box) {
        box.style.cssText = 'display:block;margin:0 0 4px 0;border-radius:6px;overflow:hidden;border:0.5px solid #86efac;background:#dcfce7';
        box.innerHTML = '<div style="padding:8px;text-align:center;font-size:11px;font-weight:500;color:#14532d">'
            + '&#10003; Anruf weitergeleitet an <b>' + num + '</b></div>';
    }
    setTimeout(function() {
        Softphone._hideTransferInline();
        Softphone.hangup();
    }, 2500);
};

Softphone._hideTransferInline = function() {
    var box = document.getElementById('sp-transfer-inline');
    if (box) { box.style.display = 'none'; box.innerHTML = ''; }
    var panel = document.getElementById('sp-transfer-panel');
    if (panel) panel.style.display = 'none';
};

Softphone._renderTransferBody = function() {
    const body = document.getElementById('sp-transfer-body');
    if (!body) return;
    const BLUE     = '#163258';
    const BLUE_HOV = '#1e4080';

    function tBtn(num) {
        return '<button onclick="Softphone._confirmTransfer(\'' + num + '\')" '
            + 'style="font-size:9px;padding:1px 6px;border:none;border-radius:3px;'
            + 'background:#163258;color:#fff;cursor:pointer;flex-shrink:0">&#8594;</button>';
    }

    function secHead(id, label, defaultOpen) {
        var closed = (Softphone._transferClosedSecs && Softphone._transferClosedSecs[id] !== undefined)
            ? Softphone._transferClosedSecs[id] : !defaultOpen;
        return '<div onclick="Softphone._transferToggleSec(\'' + id + '\')" '
            + 'style="padding:4px 8px;font-size:9px;font-weight:600;color:#fff;background:' + BLUE + ';'
            + 'border-top:0.5px solid #1e4080;display:flex;align-items:center;justify-content:space-between;cursor:pointer" '
            + 'onmouseover="this.style.background=\'#1e4080\'" '
            + 'onmouseout="this.style.background=\'#163258\'">'
            + '<span>' + label + '</span>'
            + '<span id="sp-tr-arr-' + id + '">' + (closed ? '&#9658;' : '&#9660;') + '</span>'
            + '</div>'
            + '<div id="sp-tr-sec-' + id + '" style="display:' + (closed ? 'none' : 'block') + '">';
    }

    function subSec(id, label, rows, dotColor) {
        var closed = (Softphone._transferClosedSecs && Softphone._transferClosedSecs[id] !== undefined)
            ? Softphone._transferClosedSecs[id] : true;
        var inner = rows.length
            ? rows.slice(0,10).map(cdrRow).join('')
            : '<div style="padding:4px 8px;font-size:11px;color:var(--text-muted)">Keine Eintr\u00e4ge</div>';
        return '<div onclick="Softphone._transferToggleSec(\'' + id + '\')" '
            + 'style="display:flex;align-items:center;justify-content:space-between;padding:4px 8px;'
            + 'font-size:10px;font-weight:600;color:var(--text-primary);cursor:pointer;'
            + 'border-bottom:0.5px solid var(--border-color)" '
            + 'onmouseover="this.style.background=\'#f3f4f6\'" onmouseout="this.style.background=\'\'">'
            + '<span style="display:flex;align-items:center;gap:5px">'
            + '<span style="width:6px;height:6px;border-radius:50%;background:' + dotColor + '"></span>'
            + label + ' (' + rows.length + ')</span>'
            + '<span id="sp-tr-arr-' + id + '">' + (closed ? '&#9658;' : '&#9660;') + '</span>'
            + '</div>'
            + '<div id="sp-tr-sec-' + id + '" style="display:' + (closed ? 'none' : 'block') + '">'
            + inner
            + '</div>';
    }

    function cdrRow(r) {
        var num  = r.direction === 'incoming' ? (r.src || '') : (r.dst || '');
        var name = (r.contact && r.contact.name) ? r.contact.name : num;
        if (!num || num.startsWith('*') || num.length < 3) return '';
        return '<div style="display:flex;align-items:center;gap:6px;padding:4px 8px;'
            + 'border-bottom:0.5px solid var(--border-color);font-size:11px">'
            + '<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + name + '</span>'
            + '<span style="font-size:9px;color:var(--text-muted);flex-shrink:0">' + (name !== num ? num : '') + '</span>'
            + tBtn(num) + '</div>';
    }

    var html = '';

    // 1. Kontakt suchen
    html += secHead('search', 'Kontakt suchen', false);
    html += '<div style="padding:5px 8px">'
        + '<input id="sp-tr-search-inp" type="text" placeholder="Name oder Nummer..." '
        + 'oninput="Softphone._transferSearch(this.value)" '
        + 'style="width:100%;box-sizing:border-box;padding:4px 7px;border:0.5px solid var(--border-color);'
        + 'border-radius:5px;font-size:11px;background:var(--bg-primary,#fff);color:var(--text-primary)">'
        + '<div id="sp-transfer-search-results" style="margin-top:3px"></div>'
        + '</div>';
    html += '</div>';

    // 2. Nebenstellen frei
    var extCache = Softphone._fopExtCache || [];
    var freeExts = extCache.filter(function(e) { return e.status === 'free'; });
    html += secHead('exts', 'Nebenstellen \u2014 frei (' + freeExts.length + ')', true);
    if (freeExts.length) {
        freeExts.forEach(function(e) {
            html += '<div style="display:flex;align-items:center;gap:6px;padding:4px 8px;'
                + 'border-bottom:0.5px solid var(--border-color);font-size:11px">'
                + '<span style="width:6px;height:6px;border-radius:50%;background:#22c55e;flex-shrink:0"></span>'
                + '<span style="flex:1">Ext. ' + e.extension + '</span>'
                + tBtn(e.extension)
                + '</div>';
        });
    } else {
        html += '<div style="padding:5px 8px;font-size:11px;color:var(--text-muted)">Keine freien Nebenstellen</div>';
    }
    html += '</div>';

    // 3. Schnellwahl
    var dials = Softphone._ext.speed_dials || [];
    html += secHead('speed', 'Schnellwahl (' + dials.length + ')', true);
    if (dials.length) {
        dials.forEach(function(d) {
            var nums = d.phones || (d.num ? [{norm: d.num}] : []);
            var name = d.name || '';
            if (d.type === 'manual' && d.num) {
                html += '<div style="display:flex;align-items:center;gap:6px;padding:5px 8px;'
                    + 'border-bottom:0.5px solid var(--border-color);font-size:11px">'
                    + '<span style="flex:1">' + name + '</span>'
                    + '<span style="font-size:9px;color:var(--text-muted)">' + d.num + '</span>'
                    + tBtn(d.num) + '</div>';
            } else if (nums.length) {
                var num = nums[0].norm || nums[0].raw || '';
                if (num) {
                    html += '<div style="display:flex;align-items:center;gap:6px;padding:5px 8px;'
                        + 'border-bottom:0.5px solid var(--border-color);font-size:11px">'
                        + '<span style="flex:1">' + name + '</span>'
                        + '<span style="font-size:9px;color:var(--text-muted)">' + num + '</span>'
                        + tBtn(num) + '</div>';
                }
            }
        });
    } else {
        html += '<div style="padding:5px 8px;font-size:11px;color:var(--text-muted)">Keine Schnellwahl</div>';
    }
    html += '</div>';

    // 4. Letzte Anrufe
    var allRows  = Softphone._lastCdrRows || [];
    var missed   = allRows.filter(function(r) { return r.direction === 'incoming' && r.disposition !== 'ANSWERED'; });
    var answered = allRows.filter(function(r) { return r.direction === 'incoming' && r.disposition === 'ANSWERED'; });
    var dialed   = allRows.filter(function(r) { return r.direction === 'outgoing'; });
    html += secHead('recent', 'Letzte Anrufe', true);
    html += subSec('missed',   'Abwesenheit', missed,   '#ef4444');
    html += subSec('answered', 'Angenommen',  answered, '#22c55e');
    html += subSec('dialed',   'Gew\u00e4hlt', dialed,  '#22c55e');
    html += '</div>';

    body.innerHTML = html;
};

Softphone._transferClosedSecs = { search: true, exts: false, speed: false, recent: false, missed: true, answered: true, dialed: true };

Softphone._fopExtCache = Softphone._fopExtCache || [];

Softphone._confirmTransfer = function(num) {
    if (!num || !num.trim()) return;
    num = num.trim();
    var box = document.getElementById('sp-transfer-inline');
    if (!box) return;
    var panel = document.getElementById('sp-transfer-panel');
    if (panel) panel.style.display = 'none';
    box.style.cssText = 'display:block;margin:0 0 4px 0;border-radius:6px;overflow:hidden;border:0.5px solid #fcd34d;background:#fef3c7';
    box.innerHTML = '<div style="padding:6px 8px;font-size:10px;color:#92400e;font-weight:500;border-bottom:0.5px solid #fcd34d">'
        + '&#8594; Transfer zu <b>' + num + '</b></div>'
        + '<div style="display:flex;gap:5px;padding:6px 8px">'
        + '<button onclick="Softphone._doBlindTransfer(\'' + num + '\')" '
        + 'style="flex:1;padding:5px 4px;background:#163258;color:#fff;border:none;border-radius:5px;font-size:10px;cursor:pointer">&#8594; Direkt</button>'
        + '<button onclick="Softphone._doAnnounceTransfer(\'' + num + '\')" '
        + 'style="flex:1;padding:5px 4px;background:#0f6e56;color:#fff;border:none;border-radius:5px;font-size:10px;cursor:pointer">&#9742; Ankuendigen</button>'
        + '<button onclick="Softphone._hideTransferInline()" '
        + 'style="padding:5px 7px;background:var(--bg-secondary,#f3f4f6);border:0.5px solid #fcd34d;border-radius:5px;font-size:10px;cursor:pointer;color:#92400e">&#10005;</button>'
        + '</div>';
};

Softphone._doBlindTransfer = function(num) {
    Softphone._hideTransferInline();
    Softphone.doTransfer(num);
};

Softphone._doAnnounceTransfer = function(num) {
    var held = Softphone._currentSession;
    if (!held) return;
    try { held.hold(); } catch(e) {}
    Softphone._heldSession = held;
    Softphone._announceTarget = num;
    var box = document.getElementById('sp-transfer-inline');
    if (box) {
        box.style.cssText = 'display:block;margin:0 0 4px 0;border-radius:6px;overflow:hidden;border:0.5px solid #fcd34d;background:#fef3c7';
        box.innerHTML = '<div style="padding:6px 8px;font-size:10px;color:#92400e;font-weight:500;border-bottom:0.5px solid #fcd34d">'
            + '&#9742; Ankuendigung an <b>' + num + '</b> …</div>'
            + '<div style="display:flex;gap:5px;padding:6px 8px">'
            + '<button onclick="Softphone._finishAnnounce(\'' + num + '\')" '
            + 'style="flex:1;padding:5px 4px;background:#163258;color:#fff;border:none;border-radius:5px;font-size:10px;cursor:pointer">&#8594; Transferieren</button>'
            + '<button onclick="Softphone._cancelAnnounce()" '
            + 'style="flex:1;padding:5px 4px;background:#dc2626;color:#fff;border:none;border-radius:5px;font-size:10px;cursor:pointer">&#9746; Zurück</button>'
            + '</div>';
    }
    Softphone.setNumber(num);
    Softphone.call();
};

Softphone._finishAnnounce = function(num) {
    var bar = document.getElementById('sp-announce-bar');
    if (bar) bar.remove();
    var held = Softphone._heldSession;
    if (!held || !held.isEstablished || !held.isEstablished()) {
        alert('Gehaltener Anruf nicht mehr aktiv.');
        return;
    }
    try {
        var announceSession = Softphone._currentSession;
        var referNotifier = held.refer('sip:' + num + '@' + (Softphone._sipServer || 'pbx.win.abcona.info'));
        referNotifier.on('requestSucceeded', function() {
            setTimeout(function() {
                try { held.terminate(); } catch(e) {}
                try { if (announceSession) announceSession.terminate(); } catch(e) {}
                Softphone._showTransferSuccess(num);
            }, 500);
        });
    } catch(e) {
        console.warn('finishAnnounce refer fehlgeschlagen:', e);
    }
    Softphone._heldSession = null;
    Softphone._announceTarget = null;
};

Softphone._cancelAnnounce = function() {
    Softphone._hideTransferInline();
    try { Softphone.hangup(); } catch(e) {}
    try { if (Softphone._heldSession) Softphone._heldSession.unhold(); } catch(e) {}
    Softphone._heldSession = null;
    Softphone._announceTarget = null;
};

Softphone._transferToggleSec = function(id) {
    const sec = document.getElementById('sp-tr-sec-' + id);
    const arr = document.getElementById('sp-tr-arr-' + id);
    if (!sec) return;
    const open = sec.style.display !== 'none';
    Softphone._transferClosedSecs[id] = open;
    sec.style.display = open ? 'none' : 'block';
    if (arr) arr.innerHTML = open ? '&#9658;' : '&#9660;';
};

Softphone._transferSearch = async function(q) {
    const res = document.getElementById('sp-transfer-search-results');
    if (!res) return;
    if (!q || q.length < 2) { res.innerHTML = ''; return; }
    try {
        const r = await fetch('/crm/api/berater/?q=' + encodeURIComponent(q) + '&per_page=8&typ=alle');
        const d = await r.json();
        const items = (d.results || []).slice(0, 5);
        if (!items.length) { res.innerHTML = '<div style="font-size:10px;color:var(--text-muted);padding:4px 0">Keine Treffer</div>'; return; }
        res.innerHTML = items.map(function(c) {
            const phones = (c.phones || []).filter(function(p) { return p.norm || p.raw; });
            if (!phones.length) return '';
            const num = phones[0].norm || phones[0].raw;
            return '<div style="display:flex;align-items:center;gap:6px;padding:4px 0;font-size:11px;border-bottom:0.5px solid var(--border-color)">'
                + '<span style="flex:1">' + (c.full_name || c.name || '') + '</span>'
                + '<span style="font-size:9px;color:var(--text-muted)">' + num + '</span>'
                + '<button onclick="Softphone._confirmTransfer(\'' + num + '\')" '
                + 'style="font-size:9px;padding:1px 6px;border:none;border-radius:3px;background:#163258;color:#fff;cursor:pointer">&#8594;</button>'
                + '</div>';
        }).join('');
    } catch(e) { console.warn('Transfer-Suche Fehler:', e); }
};
