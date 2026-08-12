/**
 * 9_sp-transfer.js — Transfer Panel (Inline im Widget)
 */

Softphone._transferClosedSecs = { search: true, exts: false, speed: false, recent: false, missed: true, answered: true, dialed: true };
Softphone._fopExtCache    = Softphone._fopExtCache    || [];
Softphone._heldSession    = null;
Softphone._announceTarget = null;

// ── Inline Transfer Toggle ────────────────────────────────
Softphone.toggleTransfer = function() {
    if (window.SP_STANDALONE) {
        Softphone._toggleTransferExpand();
    } else {
        Softphone._toggleTransferPanel();
    }
};

Softphone._toggleTransferExpand = function() {
    var exp = document.getElementById('sp-transfer-expand');
    if (!exp) return;
    if (exp.style.display === 'block') {
        Softphone._closeTransferExpand();
        return;
    }
    var numEl = document.getElementById('sp-tr-exp-num');
    var disp  = document.getElementById('sp-display');
    if (numEl && disp) numEl.textContent = disp.textContent.trim() !== '\u00a0' ? disp.textContent.trim() : '';
    exp.style.display = 'block';
    Softphone._renderTransferExpandBody();
    setTimeout(function() {
        var inp = document.getElementById('sp-tr-exp-input');
        if (inp) inp.focus();
    }, 80);
};

Softphone._closeTransferExpand = function() {
    var exp = document.getElementById('sp-transfer-expand');
    if (exp) exp.style.display = 'none';
    var inp = document.getElementById('sp-tr-exp-input');
    if (inp) inp.value = '';
    var res = document.getElementById('sp-tr-exp-search-results');
    if (res) res.innerHTML = '';
};

Softphone._toggleTransferPanel = function() {
    var panel = document.getElementById('sp-transfer-panel');
    if (!panel) return;
    if (panel.style.display === 'block') { panel.style.display = 'none'; return; }
    Softphone._positionTransfer();
    panel.style.display = 'block';
    Softphone._renderTransferBody();
    setTimeout(function() {
        var inp = document.getElementById('sp-transfer-input');
        if (inp) inp.focus();
    }, 100);
};

Softphone._positionTransfer = function() {
    var modal = document.getElementById('sp-modal');
    var panel = document.getElementById('sp-transfer-panel');
    if (!modal || !panel) return;
    var r = modal.getBoundingClientRect();
    panel.style.left      = r.left + 'px';
    panel.style.width     = r.width + 'px';
    panel.style.top       = '';
    panel.style.bottom    = (window.innerHeight - r.top + 4) + 'px';
    panel.style.maxHeight = Math.max(200, r.top - 12) + 'px';
};

// ── Inline Body rendern ───────────────────────────────────
Softphone._renderTransferExpandBody = function() {
    var body = document.getElementById('sp-tr-exp-body');
    if (!body) return;
    var BLUE = 'var(--panel-header-bg,#163258)';

    function tBtn(num) {
        return '<button onclick="Softphone._confirmTransfer(\'' + num + '\')" '
            + 'class="sp-panel-hdr" style="font-size:9px;padding:1px 6px;border:none;border-radius:3px;cursor:pointer;flex-shrink:0">&#8594;</button>';
    }

    function secHead(id, label, defaultOpen) {
        var closed = Softphone._transferClosedSecs[id] !== undefined
            ? Softphone._transferClosedSecs[id] : !defaultOpen;
        return '<div onclick="Softphone._transferExpandToggleSec(\'' + id + '\')" '
            + 'style="padding:4px 8px;font-size:9px;font-weight:600;color:#fff;background:' + BLUE + ';'
            + 'display:flex;align-items:center;justify-content:space-between;cursor:pointer;'
            + 'border-top:0.5px solid var(--border-color)" '
            + 'onmouseover="this.style.background=\'var(--panel-header-hover,#1e4080)\'" '
            + 'onmouseout="this.style.background=\'var(--panel-header-bg,#163258)\'">'
            + '<span>' + label + '</span>'
            + '<span id="sp-tr-exp-arr-' + id + '">' + (closed ? '&#9658;' : '&#9660;') + '</span>'
            + '</div>'
            + '<div id="sp-tr-exp-sec-' + id + '" style="display:' + (closed ? 'none' : 'block') + '">';
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

    function subSec(id, label, rows, dotColor) {
        var closed = Softphone._transferClosedSecs[id] !== undefined
            ? Softphone._transferClosedSecs[id] : true;
        var inner = rows.length
            ? rows.slice(0, 8).map(cdrRow).join('')
            : '<div style="padding:4px 8px;font-size:11px;color:var(--text-muted)">' + SP_i18n.t('no_entries', 'Keine Einträge') + '</div>';
        return '<div onclick="Softphone._transferExpandToggleSec(\'' + id + '\')" '
            + 'style="display:flex;align-items:center;justify-content:space-between;'
            + 'padding:4px 8px;font-size:10px;font-weight:600;color:var(--text-primary);'
            + 'cursor:pointer;border-bottom:0.5px solid var(--border-color)" '
            + 'onmouseover="this.style.background=\'var(--bg-secondary)\'" '
            + 'onmouseout="this.style.background=\'\'">'
            + '<span style="display:flex;align-items:center;gap:5px">'
            + '<span style="width:6px;height:6px;border-radius:50%;background:' + dotColor + '"></span>'
            + label + ' (' + rows.length + ')</span>'
            + '<span id="sp-tr-exp-arr-' + id + '">' + (closed ? '&#9658;' : '&#9660;') + '</span>'
            + '</div>'
            + '<div id="sp-tr-exp-sec-' + id + '" style="display:' + (closed ? 'none' : 'block') + '">'
            + inner + '</div>';
    }

    var html = '';

    var freeExts = (Softphone._fopExtCache || []).filter(function(e) { return e.status === 'free'; });
    html += secHead('exts', SP_i18n.t('free_extensions', 'Nebenstellen — frei') + ' (' + freeExts.length + ')', true);
    if (freeExts.length) {
        freeExts.forEach(function(e) {
            html += '<div style="display:flex;align-items:center;gap:6px;padding:4px 8px;'
                + 'border-bottom:0.5px solid var(--border-color);font-size:11px">'
                + '<span style="width:6px;height:6px;border-radius:50%;background:#22c55e;flex-shrink:0"></span>'
                + '<span style="flex:1">' + SP_i18n.t('ext_short','Ext.') + ' ' + e.extension + '</span>'
                + tBtn(e.extension) + '</div>';
        });
    } else {
        html += '<div style="padding:5px 8px;font-size:11px;color:var(--text-muted)">' + SP_i18n.t('no_free_extensions', 'Keine freien Nebenstellen') + '</div>';
    }
    html += '</div>';

    var dials = (Softphone._ext && Softphone._ext.speed_dials) ? Softphone._ext.speed_dials : [];
    html += secHead('speed', SP_i18n.t('speed_dial', 'Schnellwahl') + ' (' + dials.length + ')', true);
    if (dials.length) {
        dials.forEach(function(d) {
            var num = d.num || (d.phones && d.phones[0] ? (d.phones[0].norm || d.phones[0].raw) : '');
            if (!num) return;
            html += '<div style="display:flex;align-items:center;gap:6px;padding:5px 8px;'
                + 'border-bottom:0.5px solid var(--border-color);font-size:11px">'
                + '<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + (d.name || '') + '</span>'
                + '<span style="font-size:9px;color:var(--text-muted);flex-shrink:0">' + num + '</span>'
                + tBtn(num) + '</div>';
        });
    } else {
        html += '<div style="padding:5px 8px;font-size:11px;color:var(--text-muted)">' + SP_i18n.t('no_speed_dial', 'Keine Schnellwahl') + '</div>';
    }
    html += '</div>';

    var allRows  = Softphone._lastCdrRows || [];
    var missed   = allRows.filter(function(r) { return r.direction === 'incoming' && r.disposition !== 'ANSWERED'; });
    var answered = allRows.filter(function(r) { return r.direction === 'incoming' && r.disposition === 'ANSWERED'; });
    var dialed   = allRows.filter(function(r) { return r.direction === 'outgoing'; });
    html += secHead('recent', SP_i18n.t('last_calls', 'Letzte Anrufe'), false);
    html += subSec('missed',   SP_i18n.t('missed',   'Abwesenheit'), missed,   '#ef4444');
    html += subSec('answered', SP_i18n.t('answered', 'Angenommen'),  answered, '#22c55e');
    html += subSec('dialed',   SP_i18n.t('dialed',   'Gewählt'),     dialed,   '#22c55e');
    html += '</div>';

    body.innerHTML = html;
};

Softphone._transferExpandToggleSec = function(id) {
    var sec = document.getElementById('sp-tr-exp-sec-' + id);
    var arr = document.getElementById('sp-tr-exp-arr-' + id);
    if (!sec) return;
    var open = sec.style.display !== 'none';
    Softphone._transferClosedSecs[id] = open;
    sec.style.display = open ? 'none' : 'block';
    if (arr) arr.innerHTML = open ? '&#9658;' : '&#9660;';
};

Softphone._transferExpandSearch = async function(q) {
    var res = document.getElementById('sp-tr-exp-search-results');
    if (!res) return;
    if (!q || q.length < 2) { res.innerHTML = ''; return; }
    try {
        var r = await fetch('/crm/api/berater/?q=' + encodeURIComponent(q) + '&per_page=6&typ=alle');
        var d = await r.json();
        var items = (d.results || []).slice(0, 6);
        if (!items.length) {
            res.innerHTML = '<div style="font-size:10px;color:var(--text-muted);padding:4px 0">' + SP_i18n.t('no_results', 'Keine Treffer') + '</div>';
            return;
        }
        res.innerHTML = items.map(function(c) {
            var phones = (c.phones || []).filter(function(p) { return p.norm || p.raw; });
            if (!phones.length) return '';
            if (phones.length === 1) {
                var num = phones[0].norm || phones[0].raw;
                return '<div style="display:flex;align-items:center;gap:6px;padding:4px 0;'
                    + 'font-size:11px;border-bottom:0.5px solid var(--border-color)">'
                    + '<span style="flex:1">' + (c.full_name || c.name || '') + '</span>'
                    + '<span style="font-size:9px;color:var(--text-muted)">' + num + '</span>'
                    + '<button onclick="Softphone._confirmTransfer(\'' + num + '\')" '
                    + 'class="sp-panel-hdr" style="font-size:9px;padding:1px 6px;border:none;border-radius:3px;cursor:pointer">&#8594;</button>'
                    + '</div>';
            } else {
                var id = 'sp-tr-exp-ph-' + Math.random().toString(36).slice(2, 6);
                var mainNum = phones[0].norm || phones[0].raw;
                var subItems = phones.map(function(p) {
                    var num = p.norm || p.raw;
                    var lbl = p.label || p.field_name || '';
                    return '<div style="display:flex;align-items:center;gap:6px;padding:3px 8px;'
                        + 'font-size:10px;background:var(--bg-secondary);border-bottom:0.5px solid var(--border-color)">'
                        + '<span style="color:var(--text-muted);flex:1">' + lbl + '</span>'
                        + '<span style="flex-shrink:0">' + num + '</span>'
                        + '<button onclick="Softphone._confirmTransfer(\'' + num + '\')" '
                        + 'class="sp-panel-hdr" style="font-size:9px;padding:1px 5px;border:none;border-radius:3px;cursor:pointer">&#8594;</button>'
                        + '</div>';
                }).join('');
                return '<div style="border-bottom:0.5px solid var(--border-color)">'
                    + '<div onclick="var s=document.getElementById(\'' + id + '\');s.style.display=s.style.display===\'none\'?\'block\':\'none\'" '
                    + 'style="display:flex;align-items:center;gap:6px;padding:4px 0;font-size:11px;cursor:pointer">'
                    + '<span style="flex:1">' + (c.full_name || c.name || '') + '</span>'
                    + '<span style="font-size:9px;color:var(--text-muted)">' + mainNum + ' &#9660;</span>'
                    + '</div>'
                    + '<div id="' + id + '" style="display:none">' + subItems + '</div>'
                    + '</div>';
            }
        }).join('');
    } catch(e) { console.warn('SP-Transfer: Suche Fehler:', e); }
};

// ── Transfer Aktionen ─────────────────────────────────────
Softphone.doTransfer = function(num) {
    if (!num || !num.trim()) return;
    num = num.trim();
    var session = Softphone._currentSession;
    if (session && session.isEstablished && session.isEstablished()) {
        try {
            var referNotifier = session.refer('sip:' + num + '@' + (Softphone._sipServer || 'pbx.win.abcona.info'));
            Softphone._closeTransferExpand();
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
        alert(SP_i18n.t('alert_no_session'));
    }
};

Softphone._showTransferSuccess = function(num) {
    var box = document.getElementById('sp-transfer-inline');
    if (box) {
        box.style.display = 'block';
        box.className = 'sp-transfer-inline-ok';
        box.innerHTML = '<div class="sp-transfer-inline-body">'
            + '&#10003; ' + SP_i18n.t('transfer_success','Anruf weitergeleitet an') + ' <b>' + num + '</b></div>';
    }
    Softphone._closeTransferExpand();
    setTimeout(function() { Softphone._hideTransferInline(); Softphone.hangup(); }, 2500);
};

Softphone._hideTransferInline = function() {
    var box = document.getElementById('sp-transfer-inline');
    if (box) { box.style.display = 'none'; box.innerHTML = ''; box.className = ''; }
    Softphone._closeTransferExpand();
    var panel = document.getElementById('sp-transfer-panel');
    if (panel) panel.style.display = 'none';
};

Softphone._confirmTransfer = function(num) {
    if (!num || !num.trim()) return;
    num = num.trim();
    Softphone._closeTransferExpand();
    var panel = document.getElementById('sp-transfer-panel');
    if (panel) panel.style.display = 'none';
    var box = document.getElementById('sp-transfer-inline');
    if (!box) return;
    box.style.display = 'block';
    box.className = 'sp-transfer-inline-warn';
    box.innerHTML = '<div class="sp-transfer-inline-hdr">'
        + '&#8594; ' + SP_i18n.t('transfer_to','Transfer zu') + ' <b>' + num + '</b></div>'
        + '<div style="display:flex;gap:5px;padding:5px 8px">'
        + '<button onclick="Softphone._doBlindTransfer(\'' + num + '\')" '
        + 'class="sp-panel-hdr" style="flex:1;padding:5px 4px;border:none;border-radius:5px;font-size:10px;cursor:pointer">&#8594; ' + SP_i18n.t('direct','Direkt') + '</button>'
        + '<button onclick="Softphone._doAnnounceTransfer(\'' + num + '\')" '
        + 'style="flex:1;padding:5px 4px;background:var(--btn-announce-bg);color:var(--btn-announce-color);border:none;border-radius:5px;font-size:10px;cursor:pointer">&#9742; ' + SP_i18n.t('announce','Ankündigen') + '</button>'
        + '<button onclick="Softphone._hideTransferInline()" '
        + 'style="padding:5px 7px;background:var(--bg-secondary);border:0.5px solid var(--status-warn-border);border-radius:5px;font-size:10px;cursor:pointer;color:var(--status-warn-color)">&#10005;</button>'
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
    Softphone._heldSession    = held;
    Softphone._announceTarget = num;
    var box = document.getElementById('sp-transfer-inline');
    if (box) {
        box.style.display = 'block';
        box.className = 'sp-transfer-inline-warn';
        box.innerHTML = '<div class="sp-transfer-inline-hdr">'
            + '&#9742; ' + SP_i18n.t('announce_to','Ankündigung an') + ' <b>' + num + '</b> \u2026</div>'
            + '<div style="display:flex;gap:5px;padding:5px 8px">'
            + '<button onclick="Softphone._finishAnnounce(\'' + num + '\')" '
            + 'class="sp-panel-hdr" style="flex:1;padding:5px 4px;border:none;border-radius:5px;font-size:10px;cursor:pointer">&#8594; ' + SP_i18n.t('do_transfer','Transferieren') + '</button>'
            + '<button onclick="Softphone._cancelAnnounce()" '
            + 'style="flex:1;padding:5px 4px;background:var(--btn-cancel-bg);color:var(--btn-cancel-color);border:none;border-radius:5px;font-size:10px;cursor:pointer">&#9746; ' + SP_i18n.t('back_btn','Zurück') + '</button>'
            + '</div>';
    }
    Softphone.setNumber(num);
    Softphone.call();
};

Softphone._finishAnnounce = function(num) {
    var held = Softphone._heldSession;
    if (!held || !held.isEstablished || !held.isEstablished()) {
        alert(SP_i18n.t('alert_held_gone'));
        return;
    }
    try {
        var announceSession = Softphone._currentSession;
        var referNotifier   = held.refer('sip:' + num + '@' + (Softphone._sipServer || 'pbx.win.abcona.info'));
        referNotifier.on('requestSucceeded', function() {
            setTimeout(function() {
                try { held.terminate(); } catch(e) {}
                try { if (announceSession) announceSession.terminate(); } catch(e) {}
                Softphone._showTransferSuccess(num);
            }, 500);
        });
    } catch(e) { console.warn('SP-Transfer: finishAnnounce fehlgeschlagen:', e); }
    Softphone._heldSession    = null;
    Softphone._announceTarget = null;
};

Softphone._cancelAnnounce = function() {
    Softphone._hideTransferInline();
    try { Softphone.hangup(); } catch(e) {}
    try { if (Softphone._heldSession) Softphone._heldSession.unhold(); } catch(e) {}
    Softphone._heldSession    = null;
    Softphone._announceTarget = null;
};

// ── Portal-Modal Body ─────────────────────────────────────
Softphone._transferSearch = async function(q) {
    var res = document.getElementById('sp-transfer-search-results');
    if (!res) return;
    if (!q || q.length < 2) { res.innerHTML = ''; return; }
    try {
        var r = await fetch('/crm/api/berater/?q=' + encodeURIComponent(q) + '&per_page=5&typ=alle');
        var d = await r.json();
        var items = (d.results || []).slice(0, 5);
        if (!items.length) { res.innerHTML = '<div style="font-size:10px;color:var(--text-muted);padding:4px 0">' + SP_i18n.t('no_results', 'Keine Treffer') + '</div>'; return; }
        res.innerHTML = items.map(function(c) {
            var phones = (c.phones || []).filter(function(p) { return p.norm || p.raw; });
            if (!phones.length) return '';
            var num = phones[0].norm || phones[0].raw;
            return '<div style="display:flex;align-items:center;gap:6px;padding:4px 0;font-size:11px;border-bottom:0.5px solid var(--border-color)">'
                + '<span style="flex:1">' + (c.full_name || c.name || '') + '</span>'
                + '<span style="font-size:9px;color:var(--text-muted)">' + num + '</span>'
                + '<button onclick="Softphone._confirmTransfer(\'' + num + '\')" class="sp-panel-hdr" style="font-size:9px;padding:1px 6px;border:none;border-radius:3px;cursor:pointer">&#8594;</button>'
                + '</div>';
        }).join('');
    } catch(e) {}
};

Softphone._transferToggleSec = function(id) {
    var sec = document.getElementById('sp-tr-sec-' + id);
    var arr = document.getElementById('sp-tr-arr-' + id);
    if (!sec) return;
    var open = sec.style.display !== 'none';
    Softphone._transferClosedSecs[id] = open;
    sec.style.display = open ? 'none' : 'block';
    if (arr) arr.innerHTML = open ? '&#9658;' : '&#9660;';
};

Softphone._renderTransferBody = function() {
    var body = document.getElementById('sp-transfer-body');
    if (!body) return;
    body.innerHTML = '<div style="padding:8px;font-size:11px;color:var(--text-muted)">' + SP_i18n.t('transfer_panel_portal','Transfer-Panel') + '</div>';
};
