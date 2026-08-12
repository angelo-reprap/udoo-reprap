/**
 * 10_sp-fop.js — FOP Panel, Schnellwahl, Letzte Anrufe
 * Komplett neu geschrieben — keine hardcodierten Labels, keine Inline-CSS-Farben
 */

Softphone._fopClosedSecs    = {};
Softphone._fopOpenExt       = null;
Softphone._lastCdrRows      = [];
Softphone._recentClosedSecs = { missed: false, incoming: true, outgoing: true };

// ── FOP Panel ─────────────────────────────────────────────
Softphone.toggleFOP = function() {
    var panel = document.getElementById('sp-fop-panel');
    var btn   = document.getElementById('sp-fop-toggle');
    if (!panel) return;
    var open = panel.style.display === 'none' || panel.style.display === '';
    if (open && Softphone._positionPanel) Softphone._positionPanel('sp-fop-panel', 'right');
    panel.style.display = open ? 'block' : 'none';
    if (btn) btn.classList.toggle('sp-toggle-active', open);
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

Softphone._fopToggleSec = function(secId) {
    var sec = document.getElementById('fop-sec-' + secId);
    var arr = document.getElementById('fop-sec-arr-' + secId);
    if (!sec) return;
    var open = sec.style.display !== 'none';
    Softphone._fopClosedSecs[secId] = open;
    sec.style.display = open ? 'none' : 'block';
    if (arr) arr.textContent = open ? '\u25ba' : '\u25bc';
};

Softphone._fopApplySecs = function() {
    Object.keys(Softphone._fopClosedSecs).forEach(function(secId) {
        if (!Softphone._fopClosedSecs[secId]) return;
        var sec = document.getElementById('fop-sec-' + secId);
        var arr = document.getElementById('fop-sec-arr-' + secId);
        if (sec) sec.style.display = 'none';
        if (arr) arr.textContent = '\u25ba';
    });
};

Softphone._fopExtClick = function(row) {
    if (!row || !row.dataset) return;
    var ext = row.dataset.ext;
    Softphone._fopOpenExt = (Softphone._fopOpenExt === ext) ? null : ext;
    Softphone._fopApplyOpen();
};

Softphone._fopApplyOpen = function() {
    var ext = Softphone._fopOpenExt;
    document.querySelectorAll('[id^="fop-act-"]').forEach(function(a) {
        a.style.display = (ext && a.id === 'fop-act-' + ext) ? 'flex' : 'none';
    });
    document.querySelectorAll('.sp-arr').forEach(function(arr) {
        var r = arr.closest('[data-ext]');
        if (r) arr.textContent = (r.dataset.ext === ext) ? '\u25bc' : '\u25ba';
    });
};

// ── Hilfsfunktionen ───────────────────────────────────────
function _secHeader(secId, label, dotClass) {
    return '<div onclick="Softphone._fopToggleSec(\'' + secId + '\')" class="sp-sec-hdr">'
        + '<div class="sp-sec-hdr-left"><span class="sp-status-dot ' + dotClass + '"></span>' + label + '</div>'
        + '<span id="fop-sec-arr-' + secId + '" class="sp-sec-arrow">&#9660;</span>'
        + '</div><div id="fop-sec-' + secId + '">';
}

function _fopRow(content) {
    return '<div class="sp-fop-row">' + content + '</div>';
}

// ── FOP Render ────────────────────────────────────────────
Softphone._renderFOP = function(panel, data) {
    var myExt = Softphone._ext.vm_ext || '';
    var html  = '';

    // ── Extensions ──
    var exts = data.extensions || [];
    Softphone._fopExtCache = exts;
    var hasActive = exts.some(function(r) { return r.status !== 'offline' && r.status !== 'unknown'; });
    html += _secHeader('ext', SP_i18n.t('extensions','EXTENSIONS'), hasActive ? 'sp-dot-active' : 'sp-dot-dim');
    exts.forEach(function(r) {
        var isMe    = myExt && r.extension === myExt;
        var label   = SP_i18n.t('ext_' + r.status, r.status);
        var actBtns = '<span onclick="event.stopPropagation();Softphone.setNumber(\'' + r.extension + '\')" class="sp-fop-act-btn">&#9742; ' + SP_i18n.t('call_btn','Anrufen') + '</span>';
        if (isMe) actBtns += '<span onclick="event.stopPropagation();Softphone.toggleDND()" class="sp-fop-btn-dnd">' + (r.dnd ? SP_i18n.t('dnd_off','DND aus') : SP_i18n.t('dnd_on','DND an')) + '</span>';
        html += '<div onclick="Softphone._fopExtClick(this)" data-ext="' + r.extension + '" class="sp-fop-ext-row">'
            + '<span class="sp-status-dot sp-dot-noevents sp-dot-' + r.status + '"></span>'
            + '<span class="sp-fop-ext-name' + (isMe ? ' sp-fop-ext-me' : '') + '">' + (isMe ? '&#9733; ' : '') + SP_i18n.t('ext_short','Ext.') + ' ' + r.extension + '</span>'
            + '<div class="sp-fop-ext-right">'
            + '<span class="sp-ext-badge sp-ext-' + r.status + '">' + label + '</span>'
            + '<span class="sp-arr sp-sec-arrow">&#9658;</span>'
            + '</div></div>'
            + '<div id="fop-act-' + r.extension + '" class="sp-fop-act-bar" style="display:none">' + actBtns + '</div>';
    });
    html += '</div>';

    // ── Parking ──
    var parkSlots = ['701','702','703','704','705','706','707','708','709'];
    var parkedMap = {};
    (data.parking || []).forEach(function(p) { if (p.slot) parkedMap[p.slot] = p; });
    var hasParked = Object.keys(parkedMap).length > 0;
    html += _secHeader('park', SP_i18n.t('parking','PARKING 700'), hasParked ? 'sp-dot-busy' : 'sp-dot-free');
    parkSlots.forEach(function(slot) {
        var p = parkedMap[slot];
        if (p) {
            html += _fopRow(
                '<span class="sp-status-dot sp-dot-busy"></span>'
                + '<span class="sp-fop-slot-nr">' + slot + '</span>'
                + '<span class="sp-fop-slot-caller">' + (p.caller_name || p.caller_id || '?') + '</span>'
                + '<span onclick="Softphone.setNumber(\'' + slot + '\');Softphone.call()" class="sp-fop-btn-ok">&#9742; ' + SP_i18n.t('pickup_btn','Abholen') + '</span>'
            );
        } else {
            html += '<div class="sp-fop-row sp-fop-row-muted">'
                + '<span class="sp-status-dot sp-dot-inactive"></span>'
                + '<span class="sp-fop-slot-nr">' + slot + '</span>'
                + '<span class="sp-fop-slot-empty">' + SP_i18n.t('empty','leer') + '</span>'
                + '<span onclick="Softphone._parkHere(\'' + slot + '\')" class="sp-fop-btn-info">&#8659; ' + SP_i18n.t('park_btn','Park') + '</span>'
                + '</div>';
        }
    });
    html += '</div>';

    // ── Konferenzen ──
    var confRooms = { '034': 'MeetMeFree', '035': 'MeetMePin', '5555': 'AllHands' };
    var mmMap = {}, cbMap = {};
    (data.meetme    || []).forEach(function(m) { mmMap[m.conference] = m; });
    (data.confbridge|| []).forEach(function(c) { cbMap[c.conference] = c; });
    var hasConf = Object.keys(confRooms).some(function(num) {
        var mm = mmMap[num], cb = cbMap[num];
        return (mm && mm.users && mm.users.length > 0) || (cb && cb.parties > 0);
    });
    html += _secHeader('conf', SP_i18n.t('conferences','KONFERENZEN'), hasConf ? 'sp-dot-busy' : 'sp-dot-free');
    Object.keys(confRooms).forEach(function(num) {
        var name  = confRooms[num];
        var mm    = mmMap[num], cb = cbMap[num];
        var count = mm ? (mm.users ? mm.users.length : 0) : (cb ? (cb.parties || 0) : 0);
        html += _fopRow(
            '<span class="sp-status-dot ' + (count > 0 ? 'sp-dot-active' : 'sp-dot-inactive') + '"></span>'
            + '<span onclick="Softphone.setNumber(\'' + num + '\')" class="sp-fop-conf-num">' + num + '</span>'
            + '<span onclick="Softphone.setNumber(\'' + num + '\')" class="sp-fop-conf-name">' + name + '</span>'
            + '<span class="sp-fop-conf-count">' + (count > 0 ? count + ' ' + SP_i18n.t('participants','Tlnhm.') : SP_i18n.t('empty','leer')) + '</span>'
            + '<span onclick="Softphone._joinConference(\'' + num + '\')" class="sp-fop-btn-ok">&#8594; ' + SP_i18n.t('conf_join','Konf') + '</span>'
        );
    });
    html += '</div>';

    // ── Voicemail ──
    var vm    = data.voicemail || {};
    var hasVm = Object.keys(vm).some(function(e) { return vm[e] > 0; });
    html += _secHeader('vm', SP_i18n.t('voicemail','VOICEMAIL'), hasVm ? 'sp-dot-busy' : 'sp-dot-free');
    Object.keys(vm).forEach(function(ext) {
        var count = vm[ext];
        html += _fopRow(
            '<span class="sp-status-dot ' + (count > 0 ? 'sp-dot-busy' : 'sp-dot-free') + '"></span>'
            + '<span class="sp-fop-vm-ext">' + SP_i18n.t('ext_short','Ext.') + ' ' + ext + '</span>'
            + (count > 0 ? '<span class="sp-fop-vm-badge">' + count + ' ' + SP_i18n.t('vm_new','neu') + '</span>' : '')
            + '<span onclick="Softphone.setNumber(\'*97' + ext + '\');Softphone.call()" class="sp-fop-act-btn">&#9654; ' + SP_i18n.t('vm_listen','Abhören') + '</span>'
        );
    });
    html += '</div>';

    panel.innerHTML = html;
    ['ext','park','conf','vm'].forEach(function(id) {
        if (!(id in Softphone._fopClosedSecs)) Softphone._fopClosedSecs[id] = true;
    });
    if (Softphone._fopApplyOpen) Softphone._fopApplyOpen();
    if (Softphone._fopApplySecs) Softphone._fopApplySecs();
};

// ── Park + Conference ─────────────────────────────────────
Softphone._parkHere = async function(slot) {
    var myExt = (document.getElementById('sp-cfg-user') || {value:''}).value.trim() || Softphone._ext.vm_ext || '';
    if (!myExt) { alert(SP_i18n.t('alert_ext_missing')); return; }
    try {
        var r = await fetch('/crm/api/telefon/park/', {
            method: 'POST',
            headers: {'Content-Type':'application/json','X-CSRFToken':Softphone._csrf()},
            body: JSON.stringify({ extension: myExt })
        });
        var d = await r.json();
        if (!d.success) alert(SP_i18n.t('alert_park_failed') + ': ' + (d.error || SP_i18n.t('unknown')));
    } catch(e) { console.warn('SP-FOP: Park Fehler:', e); }
};

Softphone._joinConference = async function(conference) {
    var myExt = (document.getElementById('sp-cfg-user') || {value:''}).value.trim() || Softphone._ext.vm_ext || '';
    if (!myExt) { alert(SP_i18n.t('alert_ext_missing')); return; }
    try {
        var r = await fetch('/crm/api/telefon/conference/', {
            method: 'POST',
            headers: {'Content-Type':'application/json','X-CSRFToken':Softphone._csrf()},
            body: JSON.stringify({ extension: myExt, conference: conference })
        });
        var d = await r.json();
        if (!d.success) alert(SP_i18n.t('alert_conf_failed') + ': ' + (d.error || SP_i18n.t('unknown')));
    } catch(e) { console.warn('SP-FOP: Conference Fehler:', e); }
};

// ── Schnellwahl ────────────────────────────────────────────
Softphone.toggleSpeedDial = function() {
    var panel = document.getElementById('sp-speed-panel');
    var btn   = document.getElementById('sp-speed-toggle');
    if (!panel) return;
    var open = panel.style.display === 'none' || panel.style.display === '';
    if (open && Softphone._positionPanel) Softphone._positionPanel('sp-speed-panel', 'left');
    panel.style.display = open ? 'block' : 'none';
    if (btn) btn.classList.toggle('sp-toggle-active', open);
    if (open) Softphone._renderSpeedDials();
};

Softphone._renderSpeedDials = async function() {
    var panel = document.getElementById('sp-speed-list');
    if (!panel) return;
    var dials = Softphone._ext.speed_dials || [];
    if (!dials.length) {
        panel.innerHTML = '<div class="sp-fop-hint">'
            + SP_i18n.t('no_speed_dial','Keine Schnellwahl konfiguriert.') + '<br>'
            + SP_i18n.t('speed_dial_hint','Kontakt aus Suche hierher ziehen.') + '</div>';
        return;
    }
    panel.innerHTML = '<div class="sp-fop-hint">' + SP_i18n.t('loading','Lade...') + '</div>';
    try {
        var items = await Promise.all(dials.map(async function(d) {
            if (d.type === 'manual') return d;
            if (d.crm_id && d.crm_type === 'firma') {
                try {
                    var r = await fetch('/crm/api/kunden/' + d.crm_id + '/');
                    var c = await r.json();
                    var ap = (c.ansprechpartner || []).map(function(a) {
                        return { name: (a.contact__first_name||'') + ' ' + (a.contact__last_name||''), phones: a.phones||[] };
                    });
                    return { type:'firma', name: c.name || d.name, ap };
                } catch(e) { return { type:'firma', name: d.name, ap:[] }; }
            }
            if (d.crm_id) {
                try {
                    var r = await fetch('/crm/api/berater/' + d.crm_id + '/');
                    var c = await r.json();
                    return { type:'person', name: c.full_name || d.name, firma: c.account ? c.account.name : '', phones: c.phones || [] };
                } catch(e) { return { type:'person', name: d.name, firma:'', phones:[] }; }
            }
            return d;
        }));
        Softphone._renderSpeedList(panel, items);
    } catch(e) { console.warn('SP-FOP: SpeedDial render Fehler:', e); }
};

Softphone._renderSpeedList = function(panel, items) {
    panel.innerHTML = '';
    items.forEach(function(item, idx) {
        var el  = document.createElement('div');
        el.className = 'sp-spd-item';
        var uid = 'spd-' + idx;

        function numRow(p, cls) {
            var num = p.norm || p.raw || '';
            var lbl = p.label || p.field_name || '';
            return '<div onclick="Softphone.setNumber(\'' + num + '\')" class="sp-spd-num-row ' + (cls||'') + '">'
                + '<span class="sp-text-muted">' + lbl + '</span><span>' + num + '</span></div>';
        }

        var delBtn  = '<span onclick="event.stopPropagation();Softphone._speedDialRemove(' + idx + ')" class="sp-spd-del">&#10005;</span>';
        var arrSpan = '<span class="sp-arr sp-sec-arrow sp-spd-arr">&#9658;</span>';
        var toggleFn = 'var s=document.getElementById(\'' + uid + '\');s.style.display=s.style.display===\'none\'?\'block\':\'none\';this.querySelector(\'.sp-arr\').textContent=s.style.display===\'block\'?\'▼\':\'▶\'';

        if (item.type === 'firma') {
            var apHTML = '';
            (item.ap || []).forEach(function(ap, ai) {
                var auid = uid + '-' + ai;
                var nums = (ap.phones || []).map(function(p) { return numRow(p, 'sp-spd-num-row-deep'); }).join('');
                apHTML += '<div>'
                    + '<div onclick="var s=document.getElementById(\'' + auid + '\');s.style.display=s.style.display===\'none\'?\'block\':\'none\'" class="sp-spd-ap-hdr">'
                    + '<span>' + ap.name.trim() + '</span><span class="sp-sec-arrow">&#9658;</span></div>'
                    + '<div id="' + auid + '" style="display:none">' + nums + '</div></div>';
            });
            el.innerHTML = '<div onclick="' + toggleFn + '" class="sp-spd-hdr">'
                + '<div class="sp-spd-info"><div class="sp-spd-name">' + item.name + '</div>'
                + '<div class="sp-spd-sub">' + (item.ap||[]).length + ' ' + SP_i18n.t('contact_persons','Ansprechpartner') + '</div></div>'
                + arrSpan + delBtn + '</div>'
                + '<div id="' + uid + '" style="display:none">' + apHTML + '</div>';
        } else if (item.type === 'person') {
            var nums = (item.phones || []).map(function(p) { return numRow(p); }).join('');
            el.innerHTML = '<div onclick="' + toggleFn + '" class="sp-spd-hdr">'
                + '<div class="sp-spd-info"><div class="sp-spd-name">' + item.name + '</div>'
                + (item.firma ? '<div class="sp-spd-sub">' + item.firma + '</div>' : '') + '</div>'
                + arrSpan + delBtn + '</div>'
                + '<div id="' + uid + '" style="display:none">' + nums + '</div>';
        } else {
            var num = item.num || '';
            el.innerHTML = '<div onclick="' + toggleFn + '" class="sp-spd-hdr">'
                + '<div class="sp-spd-info"><div class="sp-spd-name">' + item.name + '</div></div>'
                + arrSpan + delBtn + '</div>'
                + '<div id="' + uid + '" style="display:none">'
                + '<div onclick="Softphone.setNumber(\'' + num + '\')" class="sp-spd-num-row">'
                + '<span class="sp-text-muted">' + SP_i18n.t('number','Nummer') + '</span><span>' + num + '</span></div></div>';
        }
        panel.appendChild(el);
    });
};

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
    } catch(e) { console.warn('SP-FOP: SpeedDial speichern fehlgeschlagen:', e); }
};

Softphone._speedDialAddFromContact = async function(contact) {
    if (Softphone._ext.speed_dials.find(function(d) { return d.crm_id === contact.crm_id; })) return;
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
    var f = document.getElementById('sp-speed-add-form');
    if (f) f.style.display = f.style.display === 'flex' ? 'none' : 'flex';
};

Softphone._speedDialCancelManual = function() {
    var f = document.getElementById('sp-speed-add-form');
    if (f) f.style.display = 'none';
    var l = document.getElementById('sp-speed-add-label');
    var n = document.getElementById('sp-speed-add-number');
    if (l) l.value = '';
    if (n) n.value = '';
};

Softphone._speedDialConfirmManual = async function() {
    var label = (document.getElementById('sp-speed-add-label') || {value:''}).value.trim();
    var num   = (document.getElementById('sp-speed-add-number') || {value:''}).value.trim();
    if (!label || !num) return;
    Softphone._ext.speed_dials.push({ type:'manual', name:label, num });
    await Softphone._saveSpeedDials();
    Softphone._renderSpeedDials();
    Softphone._speedDialCancelManual();
};

Softphone._speedDialAddFirma = function() {
    var existing = document.getElementById('sp-firma-search-form');
    if (existing) { existing.remove(); return; }
    var panel = document.getElementById('sp-speed-panel');
    if (!panel) return;
    var form = document.createElement('div');
    form.id = 'sp-firma-search-form';
    form.className = 'sp-firma-search-form';
    form.innerHTML = '<input id="sp-firma-q" class="sp-firma-input" oninput="Softphone._speedDialSearchFirma(this.value)">'
        + '<div id="sp-firma-results" class="sp-firma-results"></div>';
    panel.appendChild(form);
    var fq = document.getElementById('sp-firma-q');
    if (fq) {
        fq.placeholder = SP_i18n.t('company_search','Firmaname suchen...');
        setTimeout(function() { fq.focus(); }, 50);
    }
};

Softphone._speedDialSearchFirma = async function(q) {
    var res = document.getElementById('sp-firma-results');
    if (!res) return;
    if (!q || q.length < 2) { res.innerHTML = ''; return; }
    try {
        var r = await fetch('/crm/api/kunden/?q=' + encodeURIComponent(q) + '&per_page=6');
        var d = await r.json();
        var items = (d.results || []).slice(0, 6);
        if (!items.length) {
            res.innerHTML = '<div class="sp-fop-hint">' + SP_i18n.t('no_results','Keine Treffer') + '</div>';
            return;
        }
        res.innerHTML = items.map(function(a) {
            var dataStr = JSON.stringify({ crm_id: a.crm_id, type:'firma', crm_type:'firma', name: a.name }).replace(/"/g, '&quot;');
            return '<div onclick="Softphone._speedDialAddFirmaEntry(JSON.parse(this.dataset.firma))" data-firma="' + dataStr + '" class="sp-firma-result-item">' + a.name + '</div>';
        }).join('');
    } catch(e) { console.warn('SP-FOP: Firma-Suche Fehler:', e); }
};

Softphone._speedDialAddFirmaEntry = async function(firma) {
    if (!Softphone._ext.speed_dials.find(function(d) { return d.crm_id === firma.crm_id; })) {
        Softphone._ext.speed_dials.push(firma);
        await Softphone._saveSpeedDials();
        Softphone._renderSpeedDials();
    }
    var form = document.getElementById('sp-firma-search-form');
    if (form) form.remove();
};

// ── Letzte Anrufe Panel ────────────────────────────────────
Softphone.showRecent = async function() {
    var vmExts = (Softphone._ext.vm_ext || '').split(',').map(function(e) { return e.trim(); }).filter(Boolean);
    var cfgExt = (document.getElementById('sp-cfg-user') || {value:''}).value.trim();
    var allExts = Array.from(new Set([...vmExts, cfgExt].filter(Boolean)));
    if (!allExts.length) return;
    var panel = document.getElementById('sp-recent-panel');
    if (!panel) return;
    if (panel.style.display === 'block') { Softphone._closeRecent(); return; }
    var body = document.getElementById('sp-recent-body');
    if (body) body.innerHTML = '<div class="sp-fop-hint">' + SP_i18n.t('loading','Lade...') + '</div>';
    Softphone._positionRecent();
    panel.style.display = 'block';
    try {
        var results = await Promise.all(allExts.map(function(e) {
            return fetch('/crm/api/telefon/cdr/?extension=' + e + '&days=7&limit=20').then(function(r) { return r.json(); });
        }));
        var rows = results.flatMap(function(d) { return d.rows || []; })
            .sort(function(a,b) { return new Date(b.calldate||0) - new Date(a.calldate||0); })
            .slice(0, 30);
        Softphone._lastCdrRows = rows;
        Softphone._renderRecent(rows);
    } catch(e) { console.warn('SP-FOP: Letzte Anrufe Fehler:', e); }
};

Softphone.toggleRecent = function() {
    var p = document.getElementById('sp-recent-panel');
    if (p) p.style.display = 'none';
};
Softphone._closeRecent = function() {
    var p = document.getElementById('sp-recent-panel');
    if (p) p.style.display = 'none';
};

Softphone._positionRecent = function() {
    var modal = document.getElementById('sp-modal');
    var panel = document.getElementById('sp-recent-panel');
    if (!modal || !panel) return;
    var r    = modal.getBoundingClientRect();
    var maxH = window.innerHeight - r.bottom - 8;
    panel.style.left      = r.left + 'px';
    panel.style.width     = r.width + 'px';
    panel.style.top       = (r.bottom + 4) + 'px';
    panel.style.maxHeight = Math.max(150, maxH) + 'px';
};

Softphone._renderRecent = function(rows) {
    var body = document.getElementById('sp-recent-body');
    if (!body) return;
    var missed   = rows.filter(function(r) { return r.direction === 'incoming' && r.disposition !== 'ANSWERED'; });
    var incoming = rows.filter(function(r) { return r.direction === 'incoming' && r.disposition === 'ANSWERED'; });
    var outgoing = rows.filter(function(r) { return r.direction === 'outgoing'; });

    function rowHtml(r) {
        var num  = r.direction === 'incoming' ? r.src : r.dst;
        var name = (r.contact && r.contact.name) ? r.contact.name : '';
        var disp = name || num;
        var time = r.calldate ? r.calldate.substring(11,16) + ' ' + r.calldate.substring(5,10) : '';
        var dur  = r.billsec_fmt || '';
        return '<div onclick="Softphone.setNumber(\'' + num + '\');Softphone._closeRecent()" class="sp-recent-row">'
            + '<span class="sp-recent-name">' + disp + '</span>'
            + (name ? '<span class="sp-recent-num">' + num + '</span>' : '')
            + '<span class="sp-recent-time">' + time + '</span>'
            + (dur ? '<span class="sp-recent-dur">' + dur + '</span>' : '')
            + '</div>';
    }

    function secHtml(id, label, dotClass, rows) {
        var closed = Softphone._recentClosedSecs && Softphone._recentClosedSecs[id];
        return '<div onclick="Softphone._recentToggleSec(\'' + id + '\')" class="sp-sec-hdr">'
            + '<div class="sp-sec-hdr-left"><span class="sp-status-dot ' + dotClass + '"></span>' + label + ' (' + rows.length + ')</div>'
            + '<span id="sp-recent-arr-' + id + '" class="sp-sec-arrow">' + (closed ? '&#9658;' : '&#9660;') + '</span></div>'
            + '<div id="sp-recent-sec-' + id + '" style="display:' + (closed ? 'none' : 'block') + '">'
            + (rows.length ? rows.map(rowHtml).join('') : '<div class="sp-fop-hint">' + SP_i18n.t('no_entries','Keine Einträge') + '</div>')
            + '</div>';
    }

    body.innerHTML =
        secHtml('missed',   SP_i18n.t('missed','Abwesenheit'),  missed.length > 0 ? 'sp-dot-busy' : 'sp-dot-free', missed)
      + secHtml('incoming', SP_i18n.t('answered','Angenommen'), 'sp-dot-free',   incoming)
      + secHtml('outgoing', SP_i18n.t('dialed','Gewählt'),      'sp-dot-free',   outgoing);
};

Softphone._recentToggleSec = function(id) {
    var sec = document.getElementById('sp-recent-sec-' + id);
    var arr = document.getElementById('sp-recent-arr-' + id);
    if (!sec) return;
    var open = sec.style.display !== 'none';
    Softphone._recentClosedSecs[id] = open;
    sec.style.display = open ? 'none' : 'block';
    if (arr) arr.textContent = open ? '\u25ba' : '\u25bc';
};
