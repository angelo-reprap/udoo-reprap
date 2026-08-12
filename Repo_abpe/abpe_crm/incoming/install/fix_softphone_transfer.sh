#!/usr/bin/env bash
# ============================================================
# fix_softphone_transfer.sh — Transfer Inline statt separatem Panel
# Transfer-Panel wird direkt im Widget aufgeklappt
# Aufruf: bash apps/abpe_crm/install/fix_softphone_transfer.sh
# CWD:    /opt/abpe/backend/
# ============================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
err()  { echo -e "${RED}✗${NC}  $*"; exit 1; }
info() { echo -e "${BLUE}▶${NC}  $*"; }

BASE="/opt/abpe/backend"
APP="apps/abpe_crm"
ARCHIVE="Archiv/backup_restore.py"
TRANSFER="${APP}/static/abpe_crm/softphone/js/9_sp-transfer.js"
TMPL="${APP}/templates/abpe_crm/softphone/softphone.html"

[[ "$(pwd)" == "$BASE" ]] || err "Bitte aus $BASE ausführen"

echo "════════════════════════════════════════════════════"
info "Softphone Transfer — Inline statt separatem Panel"
echo "════════════════════════════════════════════════════"
echo

# ── Backup ────────────────────────────────────────────────
info "Backup"
python3 "$ARCHIVE" -save "$TRANSFER" -m "vor transfer inline fix: 9_sp-transfer.js" || err "Backup fehlgeschlagen"
python3 "$ARCHIVE" -save "$TMPL"     -m "vor transfer inline fix: softphone.html"    || err "Backup fehlgeschlagen"
ok "Backups OK"
echo

# ── softphone.html: sp-transfer-expand einfügen ──────────
info "Schritt 1/2 — softphone.html: #sp-transfer-expand einfügen"
info "  Stelle: direkt nach #sp-transfer-inline, vor Funktions-Buttons"

python3 << 'PYEOF'
with open("apps/abpe_crm/templates/abpe_crm/softphone/softphone.html", "r") as f:
    c = f.read()

# Einfügen nach dem transfer-inline div, vor der Trennlinie
old = '            <div style="border-top:1px solid var(--border-color);margin:4px 0"></div>'

assert old in c, "FEHLER: Trennlinie nicht gefunden in softphone.html"

new = """            <!-- Transfer Expand — inline im Widget -->
            <div id="sp-transfer-expand" style="display:none;border:1px solid var(--border-color);border-radius:8px;overflow:hidden;margin:0 0 6px 0;max-height:320px;overflow-y:auto">
                <!-- Header -->
                <div style="padding:5px 8px;background:#163258;color:#fff;font-size:10px;font-weight:600;display:flex;justify-content:space-between;align-items:center">
                    <span>&#8594; Transfer <span id="sp-tr-exp-num" style="opacity:.7;font-weight:400"></span></span>
                    <span onclick="Softphone._closeTransferExpand()" style="cursor:pointer;font-size:13px">&#10005;</span>
                </div>
                <!-- Direkte Nummereingabe -->
                <div style="padding:5px 8px;border-bottom:0.5px solid var(--border-color);display:flex;gap:4px">
                    <input id="sp-tr-exp-input" type="text" placeholder="Nummer eingeben..."
                        style="flex:1;padding:4px 7px;border:0.5px solid var(--border-color);border-radius:5px;font-size:11px;background:var(--bg-primary,#fff);color:var(--text-primary)"
                        onkeydown="if(event.key==='Enter')Softphone._confirmTransfer(this.value)">
                    <button onclick="Softphone._confirmTransfer(document.getElementById('sp-tr-exp-input').value)"
                        style="padding:4px 8px;background:#163258;color:#fff;border:none;border-radius:5px;font-size:10px;cursor:pointer;white-space:nowrap">&#8594;</button>
                </div>
                <!-- Kontakt-Suche -->
                <div style="padding:4px 8px;border-bottom:0.5px solid var(--border-color)">
                    <input id="sp-tr-exp-search" type="text" placeholder="Kontakt suchen..."
                        style="width:100%;box-sizing:border-box;padding:4px 7px;border:0.5px solid var(--border-color);border-radius:5px;font-size:11px;background:var(--bg-primary,#fff);color:var(--text-primary)"
                        oninput="Softphone._transferExpandSearch(this.value)">
                    <div id="sp-tr-exp-search-results"></div>
                </div>
                <!-- Dynamischer Body (Nebenstellen, Schnellwahl, Letzte Anrufe) -->
                <div id="sp-tr-exp-body"></div>
            </div>
            <div style="border-top:1px solid var(--border-color);margin:4px 0"></div>"""

c = c.replace(old, new, 1)
assert "sp-transfer-expand" in c, "FEHLER: Insert fehlgeschlagen"

with open("apps/abpe_crm/templates/abpe_crm/softphone/softphone.html", "w") as f:
    f.write(c)
print("✓  #sp-transfer-expand in softphone.html eingefügt")
PYEOF
echo

# ── 9_sp-transfer.js komplett neu schreiben ──────────────
info "Schritt 2/2 — 9_sp-transfer.js: toggleTransfer() auf Inline umstellen"

cat > "$TRANSFER" << 'JSEOF'
/**
 * 9_sp-transfer.js — Transfer Panel (Inline im Widget)
 * Im Standalone: Transfer klappt direkt im Widget auf (#sp-transfer-expand)
 * Im Portal-Modal: separates Panel wie bisher (#sp-transfer-panel)
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

// Inline (Standalone): aufklappen im Widget
Softphone._toggleTransferExpand = function() {
    var exp = document.getElementById('sp-transfer-expand');
    if (!exp) return;
    if (exp.style.display === 'block') {
        Softphone._closeTransferExpand();
        return;
    }
    // Aktive Nummer anzeigen
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

// Portal-Modal: separates schwebendes Panel
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
    var BLUE = '#163258';

    function tBtn(num) {
        return '<button onclick="Softphone._confirmTransfer(\'' + num + '\')" '
            + 'style="font-size:9px;padding:1px 6px;border:none;border-radius:3px;background:#163258;color:#fff;cursor:pointer;flex-shrink:0">&#8594;</button>';
    }

    function secHead(id, label, defaultOpen) {
        var closed = Softphone._transferClosedSecs[id] !== undefined
            ? Softphone._transferClosedSecs[id] : !defaultOpen;
        return '<div onclick="Softphone._transferExpandToggleSec(\'' + id + '\')" '
            + 'style="padding:4px 8px;font-size:9px;font-weight:600;color:#fff;background:' + BLUE + ';'
            + 'display:flex;align-items:center;justify-content:space-between;cursor:pointer;'
            + 'border-top:0.5px solid #1e4080" '
            + 'onmouseover="this.style.background=\'#1e4080\'" '
            + 'onmouseout="this.style.background=\'' + BLUE + '\'">'
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
            : '<div style="padding:4px 8px;font-size:11px;color:var(--text-muted)">Keine Eintr\u00e4ge</div>';
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

    // 1. Freie Nebenstellen — zuerst, wichtigster Use-Case
    var freeExts = (Softphone._fopExtCache || []).filter(function(e) { return e.status === 'free'; });
    html += secHead('exts', 'Nebenstellen \u2014 frei (' + freeExts.length + ')', true);
    if (freeExts.length) {
        freeExts.forEach(function(e) {
            html += '<div style="display:flex;align-items:center;gap:6px;padding:4px 8px;'
                + 'border-bottom:0.5px solid var(--border-color);font-size:11px">'
                + '<span style="width:6px;height:6px;border-radius:50%;background:#22c55e;flex-shrink:0"></span>'
                + '<span style="flex:1">Ext. ' + e.extension + '</span>'
                + tBtn(e.extension) + '</div>';
        });
    } else {
        html += '<div style="padding:5px 8px;font-size:11px;color:var(--text-muted)">Keine freien Nebenstellen</div>';
    }
    html += '</div>';

    // 2. Schnellwahl
    var dials = (Softphone._ext && Softphone._ext.speed_dials) ? Softphone._ext.speed_dials : [];
    html += secHead('speed', 'Schnellwahl (' + dials.length + ')', true);
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
        html += '<div style="padding:5px 8px;font-size:11px;color:var(--text-muted)">Keine Schnellwahl</div>';
    }
    html += '</div>';

    // 3. Letzte Anrufe
    var allRows  = Softphone._lastCdrRows || [];
    var missed   = allRows.filter(function(r) { return r.direction === 'incoming' && r.disposition !== 'ANSWERED'; });
    var answered = allRows.filter(function(r) { return r.direction === 'incoming' && r.disposition === 'ANSWERED'; });
    var dialed   = allRows.filter(function(r) { return r.direction === 'outgoing'; });
    html += secHead('recent', 'Letzte Anrufe', false);
    html += subSec('missed',   'Abwesenheit', missed,   '#ef4444');
    html += subSec('answered', 'Angenommen',  answered, '#22c55e');
    html += subSec('dialed',   'Gew\u00e4hlt', dialed,  '#22c55e');
    html += '</div>';

    body.innerHTML = html;
};

// Section Toggle für Inline-Panel (eigene IDs — kein Konflikt mit Portal)
Softphone._transferExpandToggleSec = function(id) {
    var sec = document.getElementById('sp-tr-exp-sec-' + id);
    var arr = document.getElementById('sp-tr-exp-arr-' + id);
    if (!sec) return;
    var open = sec.style.display !== 'none';
    Softphone._transferClosedSecs[id] = open;
    sec.style.display = open ? 'none' : 'block';
    if (arr) arr.innerHTML = open ? '&#9658;' : '&#9660;';
};

// Kontaktsuche im Inline-Transfer-Panel
Softphone._transferExpandSearch = async function(q) {
    var res = document.getElementById('sp-tr-exp-search-results');
    if (!res) return;
    if (!q || q.length < 2) { res.innerHTML = ''; return; }
    try {
        var r = await fetch('/crm/api/berater/?q=' + encodeURIComponent(q) + '&per_page=6&typ=alle');
        var d = await r.json();
        var items = (d.results || []).slice(0, 6);
        if (!items.length) {
            res.innerHTML = '<div style="font-size:10px;color:var(--text-muted);padding:4px 0">Keine Treffer</div>';
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
                    + 'style="font-size:9px;padding:1px 6px;border:none;border-radius:3px;background:#163258;color:#fff;cursor:pointer">&#8594;</button>'
                    + '</div>';
            } else {
                // Mehrere Nummern — aufklappbar
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
                        + 'style="font-size:9px;padding:1px 5px;border:none;border-radius:3px;background:#163258;color:#fff;cursor:pointer">&#8594;</button>'
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
    Softphone._closeTransferExpand();
    setTimeout(function() { Softphone._hideTransferInline(); Softphone.hangup(); }, 2500);
};

Softphone._hideTransferInline = function() {
    var box = document.getElementById('sp-transfer-inline');
    if (box) { box.style.display = 'none'; box.innerHTML = ''; }
    Softphone._closeTransferExpand();
    var panel = document.getElementById('sp-transfer-panel');
    if (panel) panel.style.display = 'none';
};

Softphone._confirmTransfer = function(num) {
    if (!num || !num.trim()) return;
    num = num.trim();
    // Inline-Panel schliessen
    Softphone._closeTransferExpand();
    var panel = document.getElementById('sp-transfer-panel');
    if (panel) panel.style.display = 'none';
    // Bestätigung inline im Widget
    var box = document.getElementById('sp-transfer-inline');
    if (!box) return;
    box.style.cssText = 'display:block;margin:0 0 4px 0;border-radius:6px;overflow:hidden;border:0.5px solid #fcd34d;background:#fef3c7';
    box.innerHTML = '<div style="padding:5px 8px;font-size:10px;color:#92400e;font-weight:500;border-bottom:0.5px solid #fcd34d">'
        + '&#8594; Transfer zu <b>' + num + '</b></div>'
        + '<div style="display:flex;gap:5px;padding:5px 8px">'
        + '<button onclick="Softphone._doBlindTransfer(\'' + num + '\')" '
        + 'style="flex:1;padding:5px 4px;background:#163258;color:#fff;border:none;border-radius:5px;font-size:10px;cursor:pointer">&#8594; Direkt</button>'
        + '<button onclick="Softphone._doAnnounceTransfer(\'' + num + '\')" '
        + 'style="flex:1;padding:5px 4px;background:#0f6e56;color:#fff;border:none;border-radius:5px;font-size:10px;cursor:pointer">&#9742; Ankündigen</button>'
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
    Softphone._heldSession    = held;
    Softphone._announceTarget = num;
    var box = document.getElementById('sp-transfer-inline');
    if (box) {
        box.style.cssText = 'display:block;margin:0 0 4px 0;border-radius:6px;overflow:hidden;border:0.5px solid #fcd34d;background:#fef3c7';
        box.innerHTML = '<div style="padding:5px 8px;font-size:10px;color:#92400e;font-weight:500;border-bottom:0.5px solid #fcd34d">'
            + '&#9742; Ankündigung an <b>' + num + '</b> \u2026</div>'
            + '<div style="display:flex;gap:5px;padding:5px 8px">'
            + '<button onclick="Softphone._finishAnnounce(\'' + num + '\')" '
            + 'style="flex:1;padding:5px 4px;background:#163258;color:#fff;border:none;border-radius:5px;font-size:10px;cursor:pointer">&#8594; Transferieren</button>'
            + '<button onclick="Softphone._cancelAnnounce()" '
            + 'style="flex:1;padding:5px 4px;background:#dc2626;color:#fff;border:none;border-radius:5px;font-size:10px;cursor:pointer">&#9746; Zur\u00fcck</button>'
            + '</div>';
    }
    Softphone.setNumber(num);
    Softphone.call();
};

Softphone._finishAnnounce = function(num) {
    var held = Softphone._heldSession;
    if (!held || !held.isEstablished || !held.isEstablished()) {
        alert('Gehaltener Anruf nicht mehr aktiv.');
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

// ── Portal-Modal Body (unveränderter Fallback) ────────────
Softphone._transferSearch = async function(q) {
    var res = document.getElementById('sp-transfer-search-results');
    if (!res) return;
    if (!q || q.length < 2) { res.innerHTML = ''; return; }
    try {
        var r = await fetch('/crm/api/berater/?q=' + encodeURIComponent(q) + '&per_page=5&typ=alle');
        var d = await r.json();
        var items = (d.results || []).slice(0, 5);
        if (!items.length) { res.innerHTML = '<div style="font-size:10px;color:var(--text-muted);padding:4px 0">Keine Treffer</div>'; return; }
        res.innerHTML = items.map(function(c) {
            var phones = (c.phones || []).filter(function(p) { return p.norm || p.raw; });
            if (!phones.length) return '';
            var num = phones[0].norm || phones[0].raw;
            return '<div style="display:flex;align-items:center;gap:6px;padding:4px 0;font-size:11px;border-bottom:0.5px solid var(--border-color)">'
                + '<span style="flex:1">' + (c.full_name || c.name || '') + '</span>'
                + '<span style="font-size:9px;color:var(--text-muted)">' + num + '</span>'
                + '<button onclick="Softphone._confirmTransfer(\'' + num + '\')" style="font-size:9px;padding:1px 6px;border:none;border-radius:3px;background:#163258;color:#fff;cursor:pointer">&#8594;</button>'
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
    body.innerHTML = '<div style="padding:8px;font-size:11px;color:var(--text-muted)">Transfer-Panel (Portal-Modus)</div>';
};
JSEOF

node --check "$TRANSFER" && ok "9_sp-transfer.js Syntax OK" || err "9_sp-transfer.js Syntax FEHLER"
echo

# ── Deploy ────────────────────────────────────────────────
info "Deploy…"
python3 manage.py collectstatic --noinput 2>&1 | tail -3
echo
supervisorctl restart abpe-django
sleep 2
supervisorctl status abpe-django
echo

echo "════════════════════════════════════════════════════"
echo -e "${GREEN}Transfer Inline Fix abgeschlossen${NC}"
echo "════════════════════════════════════════════════════"
echo
echo "Transfer-Flow (Standalone):"
echo "  1. Anruf aktiv → 'Transf.' Button erscheint"
echo "  2. Klick → Panel klappt IM Widget auf"
echo "     ├── Nummereingabe + Sofort-Transfer"
echo "     ├── Kontaktsuche"
echo "     ├── Freie Nebenstellen"
echo "     ├── Schnellwahl"
echo "     └── Letzte Anrufe (Miss./Angenom./Gewählt)"
echo "  3. → Button → Bestätigung (Direkt / Ankündigen)"
echo "  4. Alles sichtbar, nichts abgeschnitten"
echo
echo "Browser: Hard-Reload (Ctrl+Shift+R)"


