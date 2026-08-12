#!/usr/bin/env bash
# ============================================================
# fill_softphone_modules.sh — 6_sp-core.js bis 10_sp-fop.js
# befüllen aus mod-softphone.js + mod-softphone-ext.js
# Aufruf: bash apps/abpe_crm/install/fill_softphone_modules.sh
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
SP_JS="${APP}/static/abpe_crm/softphone/js"

[[ "$(pwd)" == "$BASE" ]] || err "Bitte aus $BASE ausführen"
[[ -f "$ARCHIVE" ]] || err "Backup-Script nicht gefunden"

echo "════════════════════════════════════════════════════"
info "Softphone Module befüllen (6_sp-core bis 10_sp-fop)"
echo "════════════════════════════════════════════════════"
echo

# ── Backup ────────────────────────────────────────────────
info "Schritt 1/7 — Backups"
for f in 6_sp-core 7_sp-ui 8_sp-status 9_sp-transfer 10_sp-fop; do
    python3 "$ARCHIVE" -save "${SP_JS}/${f}.js" -m "vor module fill: ${f}.js" \
        || err "Backup ${f}.js fehlgeschlagen"
done
ok "Backups OK"
echo

# ── 6_sp-core.js ─────────────────────────────────────────
info "Schritt 2/7 — 6_sp-core.js (JsSIP Init, Call, Audio)"

cat > "${SP_JS}/6_sp-core.js" << 'JSEOF'
/**
 * 6_sp-core.js — JsSIP Init, Register, Call, Hangup, Audio
 * Extrahiert aus mod-softphone.js
 * Globales Objekt: window.Softphone
 */
window.Softphone = (function() {

    let ua = null;
    let currentSession = null;
    let timerInterval = null;
    let timerSeconds = 0;
    let isMuted = false;
    let _audioEl = null;
    let cfg = { user: '', pass: '', ws: '', name: '' };

    // ── Init ──────────────────────────────────────────────
    function init() {
        _loadSettings().then(function() {
            if (cfg.user && cfg.pass && cfg.ws) {
                _register();
            }
        });
    }

    // ── Settings laden ────────────────────────────────────
    async function _loadSettings() {
        // Priorität 1: window.SP_CONFIG (aus Django-Context)
        if (window.SP_CONFIG && window.SP_CONFIG.extension) {
            cfg.user = window.SP_CONFIG.extension;
            cfg.ws   = window.SP_CONFIG.ws || 'wss://pbx.win.abcona.info:8089/ws';
            cfg.name = window.SP_CONFIG.display || cfg.user;
            // Passwort nicht im Template — per API holen
        }
        // Priorität 2: Django API
        try {
            const r = await fetch('/crm/api/user-settings/');
            const d = await r.json();
            if (d.success) {
                const s = d.data;
                cfg.user = s.phone_extension || cfg.user;
                cfg.pass = s.phone_pin       || '';
                cfg.ws   = s.softphone_ws    || cfg.ws || 'wss://pbx.win.abcona.info:8089/ws';
                cfg.name = s.phone_display_name || cfg.name || cfg.user;
            }
        } catch(e) { console.warn('SP-Core: Settings laden fehlgeschlagen', e); }

        // Formular befüllen
        var u = document.getElementById('sp-cfg-user');
        var p = document.getElementById('sp-cfg-pass');
        var w = document.getElementById('sp-cfg-ws');
        var n = document.getElementById('sp-cfg-name');
        if (u) u.value = cfg.user;
        if (p) p.value = cfg.pass;
        if (w) w.value = cfg.ws;
        if (n) n.value = cfg.name;
    }

    // ── SIP Registrierung ─────────────────────────────────
    function _register() {
        if (ua) { try { ua.stop(); } catch(e) {} }

        var socket = new JsSIP.WebSocketInterface(cfg.ws);
        var config = {
            sockets:            [socket],
            uri:                'sip:' + cfg.user + '@' + new URL(cfg.ws).hostname,
            password:           cfg.pass,
            authorization_user: cfg.user,
            realm:              'asterisk',
            display_name:       cfg.name || cfg.user,
            register:           true,
            register_expires:   300,
            session_timers:     false,
        };

        ua = new JsSIP.UA(config);

        ua.on('registered',         function() { _setStatus('Registriert · ' + cfg.user, '#22c55e'); });
        ua.on('unregistered',       function() { _setStatus('Nicht registriert', '#9ca3af'); });
        ua.on('registrationFailed', function(e) { _setStatus('Fehler: ' + (e.cause || 'unbekannt'), '#ef4444'); });

        ua.on('newRTCSession', function(e) {
            // DTLS fix
            e.session.on('sdp', function(data) {
                data.sdp = data.sdp.replace(/a=setup:actpass/g, 'a=setup:passive');
            });
            e.session.on('confirmed', function() {
                _setupAudio(e.session.connection);
            });
            if (e.originator === 'remote') {
                _handleIncoming(e.session);
            }
        });

        ua.start();
    }

    // ── Audio ─────────────────────────────────────────────
    function _setupAudio(pc) {
        if (_audioEl) { try { _audioEl.remove(); } catch(e) {} }
        _audioEl = document.createElement('audio');
        _audioEl.autoplay = true;
        _audioEl.style.display = 'none';
        document.body.appendChild(_audioEl);

        pc.ontrack = function(e) {
            if (e.streams && e.streams[0]) {
                _audioEl.srcObject = e.streams[0];
                _audioEl.play().catch(function(err) { console.warn('Audio play failed:', err); });
            }
        };

        // Fallback
        setTimeout(function() {
            var receivers = pc.getReceivers();
            if (receivers.length && !_audioEl.srcObject) {
                var stream = new MediaStream(receivers.map(function(r) { return r.track; }));
                _audioEl.srcObject = stream;
                _audioEl.play().catch(function(err) { console.warn('Audio fallback:', err); });
            }
        }, 2000);
    }

    // ── Status ────────────────────────────────────────────
    function _setStatus(text, color) {
        var dot  = document.getElementById('sp-status-dot');
        var rdot = document.getElementById('sp-reg-dot');
        var txt  = document.getElementById('sp-status-text');
        if (dot)  dot.style.background  = color;
        if (rdot) rdot.style.background = color;
        if (txt)  txt.textContent       = text;
    }

    // ── UI-Tabs ───────────────────────────────────────────
    function showTab(tab, btn) {
        var dial     = document.getElementById('sp-tab-dial');
        var settings = document.getElementById('sp-tab-settings');
        if (dial)     dial.style.display     = tab === 'dial'     ? 'block' : 'none';
        if (settings) settings.style.display = tab === 'settings' ? 'block' : 'none';
        document.querySelectorAll('.sp-tab-btn').forEach(function(b) {
            b.classList.remove('sp-tab-active');
        });
        if (btn) btn.classList.add('sp-tab-active');
    }

    // ── toggle() — Standalone: kein display:none ──────────
    function toggle() {
        if (window.SP_STANDALONE) return; // Standalone: immer sichtbar
        var m = document.getElementById('sp-modal');
        if (!m) return;
        m.style.display = m.style.display === 'none' ? 'block' : 'none';
        if (m.style.display === 'block') _loadRecent();
    }

    // ── Tastatur ──────────────────────────────────────────
    function press(key) {
        if (currentSession && currentSession.isEstablished()) {
            try { currentSession.sendDTMF(key); } catch(e) {}
            return;
        }
        var d = document.getElementById('sp-display');
        if (!d) return;
        var cur = d.textContent.trim() === '\u00a0' ? '' : d.textContent.trim();
        d.textContent = cur + key;
    }

    function backspace() {
        var d = document.getElementById('sp-display');
        if (!d) return;
        var cur = d.textContent.trim();
        d.textContent = cur.length > 1 ? cur.slice(0, -1) : '\u00a0';
    }

    function clearDisplay() {
        var d = document.getElementById('sp-display');
        if (d) d.textContent = '\u00a0';
    }

    function setNumber(num) {
        var d = document.getElementById('sp-display');
        if (d) d.textContent = num;
        showTab('dial', document.querySelector('.sp-tab-btn'));
    }

    // ── Anruf ─────────────────────────────────────────────
    function call() {
        if (!ua || !ua.isRegistered()) {
            alert('Softphone nicht registriert. Bitte Einstellungen prüfen.');
            showTab('settings', null);
            return;
        }
        var d = document.getElementById('sp-display');
        var num = (d ? d.textContent : '').trim();
        if (!num || num === '\u00a0') return;

        var target = 'sip:' + num + '@' + new URL(cfg.ws).hostname;
        var opts = {
            mediaConstraints: { audio: true, video: false },
            pcConfig: { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] },
        };

        currentSession = ua.call(target, opts);
        Softphone._currentSession = currentSession;
        _bindSessionEvents(currentSession);
        _showCallUI(true);
    }

    // ── Eingehender Anruf ─────────────────────────────────
    function _handleIncoming(session) {
        currentSession = session;
        Softphone._currentSession = currentSession;
        var num = (session.remote_identity && session.remote_identity.uri)
            ? session.remote_identity.uri.user : 'Unbekannt';

        _resolveContact(num).then(function(name) {
            var inc = document.getElementById('sp-incoming');
            var nm  = document.getElementById('sp-inc-name');
            var nu  = document.getElementById('sp-inc-num');
            var av  = document.getElementById('sp-inc-avatar');
            if (nm) nm.textContent = name || num;
            if (nu) nu.textContent = num;
            if (av) av.textContent = (name || num).substring(0, 2).toUpperCase();
            if (inc) inc.style.display = 'block';
        });

        session.on('ended',  function() { _hideIncoming(); _resetCallUI(); });
        session.on('failed', function() { _hideIncoming(); _resetCallUI(); });
    }

    function answer() {
        if (!currentSession) return;
        _hideIncoming();
        currentSession.answer({
            mediaConstraints: { audio: true, video: false },
            pcConfig: { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] },
        });
        _bindSessionEvents(currentSession);
        _showCallUI(true);
    }

    function reject() {
        if (currentSession) currentSession.terminate();
        _hideIncoming();
    }

    function hangup() {
        if (currentSession) { try { currentSession.terminate(); } catch(e) {} }
        _resetCallUI();
    }

    function toggleMute() {
        if (!currentSession) return;
        isMuted = !isMuted;
        isMuted ? currentSession.mute() : currentSession.unmute();
        var btn = document.getElementById('sp-mute-btn');
        if (btn) btn.innerHTML = isMuted
            ? '<i class="bi bi-mic-mute-fill"></i>'
            : '<i class="bi bi-mic-fill"></i>';
    }

    // ── Session Events ────────────────────────────────────
    function _bindSessionEvents(session) {
        session.on('confirmed', function() { _startTimer(); });
        session.on('ended',     function() { _stopTimer(); _resetCallUI(); });
        session.on('failed',    function(e) {
            _stopTimer(); _resetCallUI();
            console.warn('SP-Core: Anruf fehlgeschlagen:', e.cause);
        });
    }

    function _showCallUI(active) {
        var callBtn     = document.getElementById('sp-call-btn');
        var hangupBtn   = document.getElementById('sp-hangup-btn');
        var muteBtn     = document.getElementById('sp-mute-btn');
        var transferBtn = document.getElementById('sp-transfer-btn');
        var fnBar       = document.getElementById('sp-fn-bar');
        if (callBtn)     callBtn.style.display     = active ? 'none'  : 'flex';
        if (hangupBtn)   hangupBtn.style.display   = active ? 'flex'  : 'none';
        if (muteBtn)     muteBtn.style.display     = active ? 'block' : 'none';
        if (transferBtn) transferBtn.style.display = active ? 'block' : 'none';
        if (fnBar) fnBar.style.gridTemplateColumns = active ? 'repeat(5,1fr)' : 'repeat(4,1fr)';
        if (!active) {
            var tp = document.getElementById('sp-transfer-panel');
            if (tp) tp.style.display = 'none';
        }
    }

    function _resetCallUI() {
        Softphone._currentSession = null;
        _showCallUI(false);
        _stopTimer();
        isMuted = false;
        var muteBtn = document.getElementById('sp-mute-btn');
        if (muteBtn) muteBtn.innerHTML = '<i class="bi bi-mic-fill"></i>';
        currentSession = null;
    }

    function _hideIncoming() {
        var inc = document.getElementById('sp-incoming');
        if (inc) inc.style.display = 'none';
    }

    // ── Timer ─────────────────────────────────────────────
    function _startTimer() {
        timerSeconds = 0;
        var el = document.getElementById('sp-call-timer');
        if (el) el.style.display = 'block';
        timerInterval = setInterval(function() {
            timerSeconds++;
            var m = Math.floor(timerSeconds / 60);
            var s = timerSeconds % 60;
            if (el) el.textContent = m + ':' + String(s).padStart(2, '0');
        }, 1000);
    }

    function _stopTimer() {
        clearInterval(timerInterval);
        var el = document.getElementById('sp-call-timer');
        if (el) el.style.display = 'none';
        timerSeconds = 0;
    }

    // ── Kontakt-Suche (Wählen-Tab) ────────────────────────
    async function search(q) {
        var res = document.getElementById('sp-search-results');
        if (!q || q.length < 2) { if (res) res.style.display = 'none'; return; }
        try {
            var r = await fetch('/crm/api/berater/?q=' + encodeURIComponent(q) + '&per_page=8&typ=alle');
            var d = await r.json();
            var contacts = (d.results || d.berater || []).slice(0, 8);
            if (!contacts.length) { if (res) res.style.display = 'none'; return; }
            res.innerHTML = contacts.map(function(c) {
                var name = ((c.first_name || '') + ' ' + (c.last_name || '')).trim() || c.name || '—';
                var phones = (c.phones || []).filter(function(p) { return p.raw || p.norm; });
                var mainNum = phones.length
                    ? (phones.find(function(p) { return p.is_primary; }) || phones[0]).norm ||
                      (phones.find(function(p) { return p.is_primary; }) || phones[0]).raw
                    : '';
                var cJson = JSON.stringify(c).replace(/"/g, '&quot;');
                var pinBtn = '<span onclick="event.stopPropagation();Softphone._speedDialAddFromContact(JSON.parse(this.dataset.c))" data-c="' + cJson + '"'
                    + ' title="Zur Schnellwahl" class="sp-pin-contact"'
                    + ' style="font-size:11px;color:var(--text-muted);cursor:pointer;flex-shrink:0;margin-left:6px;opacity:0;padding:2px 4px;border-radius:3px"'
                    + ' onmouseover="this.style.opacity=\'1\';this.style.color=\'#163258\';this.style.background=\'#dbeafe\'"'
                    + ' onmouseout="this.style.opacity=\'0\';this.style.color=\'var(--text-muted)\';this.style.background=\'\'">&#128204;</span>';

                if (phones.length <= 1) {
                    return '<div style="padding:6px 10px;cursor:pointer;border-bottom:1px solid var(--border-color);display:flex;justify-content:space-between;align-items:center"'
                        + ' onmouseover="this.style.background=\'var(--bg-secondary)\';this.querySelector(\'.sp-pin-contact\').style.opacity=\'1\'"'
                        + ' onmouseout="this.style.background=\'\';this.querySelector(\'.sp-pin-contact\').style.opacity=\'0\'">'
                        + '<span onclick="Softphone.setNumber(\'' + mainNum + '\')" style="font-weight:500;flex:1">' + name + '</span>'
                        + '<span onclick="Softphone.setNumber(\'' + mainNum + '\')" style="color:var(--text-muted);font-size:11px;cursor:pointer">' + mainNum + '</span>'
                        + pinBtn + '</div>';
                } else {
                    var id = 'sp-ph-' + Math.random().toString(36).slice(2, 7);
                    var subItems = phones.map(function(p) {
                        var num = p.norm || p.raw;
                        var lbl = p.label || p.field_name || '';
                        return '<div onclick="event.stopPropagation();Softphone.setNumber(\'' + num + '\')"'
                            + ' style="padding:4px 10px 4px 20px;cursor:pointer;font-size:11px;display:flex;justify-content:space-between;background:var(--bg-secondary)"'
                            + ' onmouseover="this.style.background=\'var(--border-color)\'"'
                            + ' onmouseout="this.style.background=\'var(--bg-secondary)\'">'
                            + '<span style="color:var(--text-muted)">' + lbl + '</span><span>' + num + '</span></div>';
                    }).join('');
                    return '<div style="border-bottom:1px solid var(--border-color)">'
                        + '<div onclick="document.getElementById(\'' + id + '\').style.display=document.getElementById(\'' + id + '\').style.display===\'none\'?\'block\':\'none\'"'
                        + ' style="padding:6px 10px;cursor:pointer;display:flex;justify-content:space-between;align-items:center"'
                        + ' onmouseover="this.style.background=\'var(--bg-secondary)\';this.querySelector(\'.sp-pin-contact\').style.opacity=\'1\'"'
                        + ' onmouseout="this.style.background=\'\';this.querySelector(\'.sp-pin-contact\').style.opacity=\'0\'">'
                        + '<span style="font-weight:500;flex:1">' + name + '</span>'
                        + '<span style="color:var(--text-muted);font-size:11px">' + mainNum + ' \u25be</span>'
                        + pinBtn + '</div>'
                        + '<div id="' + id + '" style="display:none">' + subItems + '</div></div>';
                }
            }).join('');
            res.style.display = 'block';
        } catch(e) { if (res) res.style.display = 'none'; }
    }

    // ── Kontakt aus Nummer auflösen ───────────────────────
    async function _resolveContact(num) {
        if (!num || num.replace(/\D/g, '').length < 5) return null;
        try {
            var r = await fetch('/crm/api/berater/?q=' + encodeURIComponent(num) + '&per_page=1&typ=alle');
            var d = await r.json();
            var c = (d.results || d.berater || [])[0];
            if (c) return ((c.first_name || '') + ' ' + (c.last_name || '')).trim();
        } catch(e) {}
        return null;
    }

    // ── Zuletzt angerufen (Wählen-Tab) ───────────────────
    async function _loadRecent() {
        var el = document.getElementById('sp-recent');
        if (!el) return;
        try {
            var ext = window.SP_CONFIG && window.SP_CONFIG.extension
                ? window.SP_CONFIG.extension
                : (document.getElementById('sp-cfg-user') ? document.getElementById('sp-cfg-user').value : '');
            if (!ext) return;
            var r = await fetch('/crm/api/telefon/cdr/?extension=' + ext + '&days=7&limit=5');
            var d = await r.json();
            var rows = (d.rows || []).slice(0, 4);
            if (!rows.length) return;
            el.innerHTML = '<div style="font-size:10px;color:var(--text-muted);margin-bottom:3px;font-weight:500">Zuletzt</div>'
                + rows.map(function(row) {
                    var num  = row.src || row.dst || '';
                    var name = row.contact_name || '';
                    var disp = name || num;
                    return '<div onclick="Softphone.setNumber(\'' + num + '\')"'
                        + ' style="display:flex;align-items:center;gap:7px;padding:4px 0;cursor:pointer;border-bottom:1px solid var(--border-color)"'
                        + ' onmouseover="this.style.background=\'var(--bg-secondary)\'"'
                        + ' onmouseout="this.style.background=\'\'">'
                        + '<div style="width:24px;height:24px;border-radius:50%;background:#dbeafe;color:#1e40af;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:600;flex-shrink:0">'
                        + disp.substring(0, 2).toUpperCase() + '</div>'
                        + '<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + disp + '</span>'
                        + '<span style="color:var(--text-muted);font-size:10px;flex-shrink:0">' + (num !== disp ? num : '') + '</span>'
                        + '</div>';
                }).join('');
        } catch(e) {}
    }

    // ── Einstellungen speichern ───────────────────────────
    async function saveAndRegister() {
        var uEl = document.getElementById('sp-cfg-user');
        var pEl = document.getElementById('sp-cfg-pass');
        var wEl = document.getElementById('sp-cfg-ws');
        var nEl = document.getElementById('sp-cfg-name');
        cfg.user = uEl ? uEl.value.trim() : '';
        cfg.pass = pEl ? pEl.value.trim() : '';
        cfg.ws   = wEl ? wEl.value.trim() : '';
        cfg.name = nEl ? nEl.value.trim() : '';

        var msg = document.getElementById('sp-cfg-msg');
        try {
            await fetch('/crm/api/user-settings/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': _csrf() },
                body: JSON.stringify({
                    phone_extension:    cfg.user,
                    phone_pin:          cfg.pass,
                    softphone_ws:       cfg.ws,
                    phone_display_name: cfg.name,
                })
            });
            if (msg) { msg.style.color = '#22c55e'; msg.textContent = 'Gespeichert.'; }
        } catch(e) {
            if (msg) { msg.style.color = '#ef4444'; msg.textContent = 'Speichern fehlgeschlagen.'; }
        }

        _register();
        setTimeout(function() { showTab('dial', document.querySelector('.sp-tab-btn')); }, 800);
    }

    function _csrf() {
        var c = document.cookie.split(';').map(function(c) { return c.trim(); })
            .find(function(c) { return c.startsWith('csrftoken='); });
        return c ? c.split('=')[1] : '';
    }

    // ── Öffentliche API ───────────────────────────────────
    return {
        init, toggle, showTab, press, backspace, clearDisplay,
        call, hangup, answer, reject, toggleMute, search, setNumber,
        saveAndRegister,
        get _sipServer() {
            try { return new URL(cfg.ws).hostname; } catch(e) { return 'pbx.win.abcona.info'; }
        }
    };

})();

// Globale Event-Listener (Tastatur, Paste, data-sp-call)
document.addEventListener('click', function(e) {
    var btn = e.target.closest('[data-sp-call]');
    if (btn) { e.preventDefault(); Softphone.setNumber(btn.dataset.spCall); }
});

document.addEventListener('DOMContentLoaded', function() { Softphone.init(); });
JSEOF
node --check "${SP_JS}/6_sp-core.js" && ok "6_sp-core.js Syntax OK" || err "6_sp-core.js Syntax FEHLER"
echo

# ── 7_sp-ui.js ───────────────────────────────────────────
info "Schritt 3/7 — 7_sp-ui.js (Drag, Pin, Position)"

cat > "${SP_JS}/7_sp-ui.js" << 'JSEOF'
/**
 * 7_sp-ui.js — Drag, Pin, Panel-Positionierung
 * Extrahiert aus mod-softphone-ext.js
 * Nur relevant wenn SP_STANDALONE=false (Portal-Modal)
 * Im Standalone: Panels werden relativ zum Modal positioniert
 */

// Drag & Pin — nur im Portal-Modal-Modus
Softphone._pinned = (function() {
    try { return localStorage.getItem('sp_pinned') === '1'; } catch(e) { return false; }
})();

Softphone._applyPinnedPosition = function() {
    if (window.SP_STANDALONE) return;
    var modal = document.getElementById('sp-modal');
    if (!modal) return;
    var fopOpen = document.getElementById('sp-fop-panel') &&
        document.getElementById('sp-fop-panel').style.display === 'block';
    modal.style.left  = '';
    modal.style.right = (200 + (fopOpen ? 164 : 0)) + 'px';
    modal.style.top   = '80px';
};

Softphone._restorePosition = function() {
    if (window.SP_STANDALONE) return;
    var modal = document.getElementById('sp-modal');
    if (!modal) return;
    if (Softphone._pinned) { Softphone._applyPinnedPosition(); return; }
    try {
        var x = localStorage.getItem('sp_modal_x');
        var y = localStorage.getItem('sp_modal_y');
        if (x && y) {
            modal.style.right = '';
            modal.style.left  = x + 'px';
            modal.style.top   = y + 'px';
        } else {
            modal.style.right = '20px';
            modal.style.left  = '';
            modal.style.top   = '80px';
        }
    } catch(e) {}
};

Softphone._initDrag = function() {
    if (window.SP_STANDALONE) return;
    var handle = document.getElementById('sp-drag-handle');
    var modal  = document.getElementById('sp-modal');
    if (!handle || !modal) return;

    var dragging = false, startX, startY, origLeft, origTop;

    handle.addEventListener('mousedown', function(e) {
        if (e.target.closest('button')) return;
        if (Softphone._pinned) return;
        dragging = true;
        var spd = document.getElementById('sp-speed-panel');
        var fop = document.getElementById('sp-fop-panel');
        if (spd && spd.style.display === 'block') Softphone.toggleSpeedDial();
        if (fop && fop.style.display === 'block') Softphone.toggleFOP();
        if (Softphone._closeRecent) Softphone._closeRecent();
        var rect = modal.getBoundingClientRect();
        startX = e.clientX; startY = e.clientY;
        origLeft = rect.left; origTop = rect.top;
        modal.style.right = '';
        modal.style.left  = origLeft + 'px';
        modal.style.top   = origTop  + 'px';
        document.body.style.userSelect = 'none';
    });

    document.addEventListener('mousemove', function(e) {
        if (!dragging) return;
        var newL = Math.max(0, Math.min(window.innerWidth  - 260, origLeft + e.clientX - startX));
        var newT = Math.max(0, Math.min(window.innerHeight - 50,  origTop  + e.clientY - startY));
        modal.style.left = newL + 'px';
        modal.style.top  = newT + 'px';
    });

    document.addEventListener('mouseup', function() {
        if (!dragging) return;
        dragging = false;
        document.body.style.userSelect = '';
        try {
            localStorage.setItem('sp_modal_x', parseInt(modal.style.left));
            localStorage.setItem('sp_modal_y', parseInt(modal.style.top));
        } catch(e) {}
    });
};

Softphone.togglePin = function() {
    if (window.SP_STANDALONE) return;
    Softphone._pinned = !Softphone._pinned;
    try { localStorage.setItem('sp_pinned', Softphone._pinned ? '1' : '0'); } catch(e) {}
    var icon = document.getElementById('sp-pin-icon');
    var btn  = document.getElementById('sp-pin-btn');
    if (Softphone._pinned) {
        if (icon) icon.className = 'bi bi-pin-fill';
        if (btn)  btn.style.color = '#fbbf24';
        Softphone._applyPinnedPosition();
    } else {
        if (icon) icon.className = 'bi bi-arrows-move';
        if (btn)  btn.style.color = 'rgba(255,255,255,0.5)';
    }
};

// Panel-Positionierung (Speed links, FOP rechts vom Modal)
Softphone._positionPanel = function(panelId, side) {
    var modal = document.getElementById('sp-modal');
    var panel = document.getElementById(panelId);
    if (!modal || !panel) return;
    var r = modal.getBoundingClientRect();
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
JSEOF
node --check "${SP_JS}/7_sp-ui.js" && ok "7_sp-ui.js Syntax OK" || err "7_sp-ui.js Syntax FEHLER"
echo

# ── 8_sp-status.js ───────────────────────────────────────
info "Schritt 4/7 — 8_sp-status.js (VM, DND, FWD, Indikatoren)"

cat > "${SP_JS}/8_sp-status.js" << 'JSEOF'
/**
 * 8_sp-status.js — Voicemail, DND, Rufweiterleitung, Status-Indikatoren
 * Extrahiert aus mod-softphone-ext.js
 */

Softphone._csrf = function() {
    var c = document.cookie.split(';').map(function(c) { return c.trim(); })
        .find(function(c) { return c.startsWith('csrftoken='); });
    return c ? c.split('=')[1] : '';
};

Softphone._ext = {
    vm_ext:      '',
    dnd_ext:     '',
    fwd_target:  '',
    speed_dials: [],
    status_exts: [],
    dnd_active:  false,
    fwd_active:  false,
};

Softphone._vmCount = 0;

// Settings laden
Softphone._loadExtSettings = async function() {
    try {
        var r = await fetch('/crm/api/user-settings/');
        var d = await r.json();
        if (d.success) {
            var s = d.data;
            Softphone._ext.vm_ext      = s.softphone_vm_ext      || '';
            Softphone._ext.dnd_ext     = s.softphone_dnd_ext     || '';
            Softphone._ext.fwd_target  = s.softphone_fwd_target  || '';
            Softphone._ext.speed_dials = s.softphone_speed_dials || [];
            Softphone._ext.status_exts = (s.softphone_status_exts || '').split(',')
                .map(function(e) { return e.trim(); }).filter(Boolean);
            Softphone._loadExtSettingsIntoForm(s);
            Softphone._renderSpeedDials();
            if (Softphone._ext.status_exts.length) Softphone._startStatusPolling();
        }
    } catch(e) { console.warn('SP-Status: Settings laden fehlgeschlagen', e); }
};

Softphone._loadExtSettingsIntoForm = function(s) {
    var vmEl  = document.getElementById('sp-cfg-vm-ext');
    var dndEl = document.getElementById('sp-cfg-dnd-ext');
    var stsEl = document.getElementById('sp-cfg-status-exts');
    if (vmEl)  vmEl.value  = s.softphone_vm_ext      || '';
    if (dndEl) dndEl.value = s.softphone_dnd_ext     || '';
    if (stsEl) stsEl.value = s.softphone_status_exts || '';
};

// saveAndRegister erweitern
var _origSaveAndRegister = Softphone.saveAndRegister;
Softphone.saveAndRegister = async function() {
    var vmExt   = (document.getElementById('sp-cfg-vm-ext')     || {value:''}).value.trim();
    var dndExt  = (document.getElementById('sp-cfg-dnd-ext')    || {value:''}).value.trim();
    var stsExts = (document.getElementById('sp-cfg-status-exts')|| {value:''}).value.trim();
    Softphone._ext.vm_ext      = vmExt;
    Softphone._ext.dnd_ext     = dndExt;
    Softphone._ext.status_exts = stsExts.split(',').map(function(e) { return e.trim(); }).filter(Boolean);
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
    } catch(e) { console.warn('SP-Status: Ext-Settings speichern fehlgeschlagen', e); }
    if (Softphone._ext.status_exts.length) Softphone._startStatusPolling();
    await _origSaveAndRegister.call(Softphone);
};

// Voicemail
Softphone.callVoicemail = function() {
    var ext = (Softphone._ext.vm_ext || '').split(',')[0].trim();
    if (!ext) { alert('Bitte VM-Nebenstelle in den Einstellungen konfigurieren.'); return; }
    Softphone.setNumber('*97' + ext);
    Softphone.call();
};

// DND
Softphone.toggleDND = async function() {
    var ext = Softphone._ext.dnd_ext || Softphone._ext.vm_ext;
    if (!ext) { alert('Bitte DND-Nebenstelle in den Einstellungen konfigurieren.'); return; }
    try {
        var r = await fetch('/crm/api/telefon/dnd/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': Softphone._csrf() },
            body: JSON.stringify({ extension: ext, active: !Softphone._ext.dnd_active })
        });
        var d = await r.json();
        if (d.success) {
            Softphone._ext.dnd_active = !Softphone._ext.dnd_active;
            Softphone._updateStatusIndicators();
        }
    } catch(e) { console.warn('SP-Status: DND Fehler:', e); }
};

// Rufweiterleitung
Softphone.callForward = function() {
    if (Softphone._ext.fwd_active) {
        Softphone._ext.fwd_active = false;
        Softphone._ext.fwd_target = '';
        Softphone._updateStatusIndicators();
        Softphone.setNumber('*73');
        Softphone.call();
        return;
    }
    var target = prompt('Weiterleitungsziel:', '');
    if (!target) return;
    Softphone.setNumber('*72' + target);
    Softphone._ext.fwd_target = target;
    Softphone._ext.fwd_active = true;
    Softphone._updateStatusIndicators();
    Softphone.call();
};

// Pickup
Softphone.pickup = function() {
    Softphone.setNumber('*8');
    Softphone.call();
};

// Status-Indikatoren aktualisieren
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
            if (vmLabel) vmLabel.textContent = 'VM \u00b7 ' + vmCount;
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
            bar.innerHTML = '<i class="bi bi-bell-slash" style="margin-right:4px"></i>Nicht st\u00f6ren aktiv';
        } else if (fwdActive && fwdTarget) {
            bar.style.cssText = 'display:block;padding:4px 8px;border-left:3px solid #1e40af;font-size:10px;font-weight:500;color:#1e3a8a;margin:0 0 2px 0';
            bar.innerHTML = '<i class="bi bi-arrow-return-right" style="margin-right:4px"></i>Weiterleitung: ' + fwdTarget;
        } else if (vmCount > 0) {
            bar.style.cssText = 'display:block;padding:4px 8px;border-left:3px solid #b45309;font-size:10px;font-weight:500;color:#92400e;margin:0 0 2px 0';
            bar.innerHTML = '<i class="bi bi-voicemail" style="margin-right:4px"></i>' + vmCount
                + ' neue Voicemail-Nachricht' + (vmCount > 1 ? 'en' : '');
        } else {
            bar.style.display = 'none';
            bar.innerHTML = '';
        }
    }
};

// Extension Status Polling
Softphone._statusInterval = null;

Softphone._startStatusPolling = function() {
    if (Softphone._statusInterval) clearInterval(Softphone._statusInterval);
    Softphone._pollStatus();
    Softphone._statusInterval = setInterval(Softphone._pollStatus, 10000);
};

Softphone._pollStatus = async function() {
    var exts  = Softphone._ext.status_exts;
    var vmExt = Softphone._ext.vm_ext || '';
    if (!exts.length && !vmExt) return;
    try {
        var url = '/crm/api/telefon/fop/?extensions=' + (exts.length ? exts.join(',') : '10')
            + (vmExt ? '&vm_extensions=' + vmExt : '');
        var r = await fetch(url);
        var d = await r.json();
        if (!d.success) return;
        var vm = d.data.voicemail || {};
        Softphone._vmCount = Object.keys(vm).reduce(function(s, e) { return s + (vm[e] || 0); }, 0);
        Softphone._updateStatusIndicators();
        var panel = document.getElementById('sp-status-panel');
        if (panel) Softphone._renderFOP(panel, d.data);
    } catch(e) { console.warn('SP-Status: FOP poll Fehler:', e); }
};

// DOMContentLoaded: Ext-Settings laden
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(function() { Softphone._loadExtSettings(); }, 500);
});
JSEOF
node --check "${SP_JS}/8_sp-status.js" && ok "8_sp-status.js Syntax OK" || err "8_sp-status.js Syntax FEHLER"
echo

# ── 9_sp-transfer.js ─────────────────────────────────────
info "Schritt 5/7 — 9_sp-transfer.js (Transfer, Ankündigung)"

cat > "${SP_JS}/9_sp-transfer.js" << 'JSEOF'
/**
 * 9_sp-transfer.js — Transfer Panel, Blind/Announced Transfer
 * Extrahiert aus mod-softphone-ext.js
 */

Softphone._transferClosedSecs = { search: true, exts: false, speed: false, recent: false, missed: true, answered: true, dialed: true };
Softphone._fopExtCache = Softphone._fopExtCache || [];
Softphone._heldSession = null;
Softphone._announceTarget = null;

Softphone.toggleTransfer = function() {
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
    setTimeout(function() { Softphone._hideTransferInline(); Softphone.hangup(); }, 2500);
};

Softphone._hideTransferInline = function() {
    var box = document.getElementById('sp-transfer-inline');
    if (box) { box.style.display = 'none'; box.innerHTML = ''; }
    var panel = document.getElementById('sp-transfer-panel');
    if (panel) panel.style.display = 'none';
};

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
        + '<button onclick="Softphone._doBlindTransfer(\'' + num + '\')" style="flex:1;padding:5px 4px;background:#163258;color:#fff;border:none;border-radius:5px;font-size:10px;cursor:pointer">&#8594; Direkt</button>'
        + '<button onclick="Softphone._doAnnounceTransfer(\'' + num + '\')" style="flex:1;padding:5px 4px;background:#0f6e56;color:#fff;border:none;border-radius:5px;font-size:10px;cursor:pointer">&#9742; Ankündigen</button>'
        + '<button onclick="Softphone._hideTransferInline()" style="padding:5px 7px;background:var(--bg-secondary,#f3f4f6);border:0.5px solid #fcd34d;border-radius:5px;font-size:10px;cursor:pointer;color:#92400e">&#10005;</button>'
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
            + '&#9742; Ankündigung an <b>' + num + '</b> \u2026</div>'
            + '<div style="display:flex;gap:5px;padding:6px 8px">'
            + '<button onclick="Softphone._finishAnnounce(\'' + num + '\')" style="flex:1;padding:5px 4px;background:#163258;color:#fff;border:none;border-radius:5px;font-size:10px;cursor:pointer">&#8594; Transferieren</button>'
            + '<button onclick="Softphone._cancelAnnounce()" style="flex:1;padding:5px 4px;background:#dc2626;color:#fff;border:none;border-radius:5px;font-size:10px;cursor:pointer">&#9746; Zurück</button>'
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
        var referNotifier = held.refer('sip:' + num + '@' + (Softphone._sipServer || 'pbx.win.abcona.info'));
        referNotifier.on('requestSucceeded', function() {
            setTimeout(function() {
                try { held.terminate(); } catch(e) {}
                try { if (announceSession) announceSession.terminate(); } catch(e) {}
                Softphone._showTransferSuccess(num);
            }, 500);
        });
    } catch(e) { console.warn('SP-Transfer: finishAnnounce fehlgeschlagen:', e); }
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
    var sec = document.getElementById('sp-tr-sec-' + id);
    var arr = document.getElementById('sp-tr-arr-' + id);
    if (!sec) return;
    var open = sec.style.display !== 'none';
    Softphone._transferClosedSecs[id] = open;
    sec.style.display = open ? 'none' : 'block';
    if (arr) arr.innerHTML = open ? '&#9658;' : '&#9660;';
};

Softphone._transferSearch = async function(q) {
    var res = document.getElementById('sp-transfer-search-results');
    if (!res) return;
    if (!q || q.length < 2) { res.innerHTML = ''; return; }
    try {
        var r = await fetch('/crm/api/berater/?q=' + encodeURIComponent(q) + '&per_page=8&typ=alle');
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
    } catch(e) { console.warn('SP-Transfer: Suche Fehler:', e); }
};

Softphone._renderTransferBody = function() {
    var body = document.getElementById('sp-transfer-body');
    if (!body) return;
    var BLUE = '#163258', BLUE_HOV = '#1e4080';

    function tBtn(num) {
        return '<button onclick="Softphone._confirmTransfer(\'' + num + '\')" style="font-size:9px;padding:1px 6px;border:none;border-radius:3px;background:#163258;color:#fff;cursor:pointer;flex-shrink:0">&#8594;</button>';
    }
    function secHead(id, label, defaultOpen) {
        var closed = Softphone._transferClosedSecs[id] !== undefined ? Softphone._transferClosedSecs[id] : !defaultOpen;
        return '<div onclick="Softphone._transferToggleSec(\'' + id + '\')" style="padding:4px 8px;font-size:9px;font-weight:600;color:#fff;background:' + BLUE + ';border-top:0.5px solid #1e4080;display:flex;align-items:center;justify-content:space-between;cursor:pointer" onmouseover="this.style.background=\'#1e4080\'" onmouseout="this.style.background=\'#163258\'">'
            + '<span>' + label + '</span><span id="sp-tr-arr-' + id + '">' + (closed ? '&#9658;' : '&#9660;') + '</span></div>'
            + '<div id="sp-tr-sec-' + id + '" style="display:' + (closed ? 'none' : 'block') + '">';
    }
    function cdrRow(r) {
        var num  = r.direction === 'incoming' ? (r.src || '') : (r.dst || '');
        var name = (r.contact && r.contact.name) ? r.contact.name : num;
        if (!num || num.startsWith('*') || num.length < 3) return '';
        return '<div style="display:flex;align-items:center;gap:6px;padding:4px 8px;border-bottom:0.5px solid var(--border-color);font-size:11px">'
            + '<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + name + '</span>'
            + '<span style="font-size:9px;color:var(--text-muted);flex-shrink:0">' + (name !== num ? num : '') + '</span>'
            + tBtn(num) + '</div>';
    }
    function subSec(id, label, rows, dotColor) {
        var closed = Softphone._transferClosedSecs[id] !== undefined ? Softphone._transferClosedSecs[id] : true;
        var inner = rows.length ? rows.slice(0,10).map(cdrRow).join('')
            : '<div style="padding:4px 8px;font-size:11px;color:var(--text-muted)">Keine Eintr\u00e4ge</div>';
        return '<div onclick="Softphone._transferToggleSec(\'' + id + '\')" style="display:flex;align-items:center;justify-content:space-between;padding:4px 8px;font-size:10px;font-weight:600;color:var(--text-primary);cursor:pointer;border-bottom:0.5px solid var(--border-color)" onmouseover="this.style.background=\'#f3f4f6\'" onmouseout="this.style.background=\'\'">'
            + '<span style="display:flex;align-items:center;gap:5px"><span style="width:6px;height:6px;border-radius:50%;background:' + dotColor + '"></span>' + label + ' (' + rows.length + ')</span>'
            + '<span id="sp-tr-arr-' + id + '">' + (closed ? '&#9658;' : '&#9660;') + '</span></div>'
            + '<div id="sp-tr-sec-' + id + '" style="display:' + (closed ? 'none' : 'block') + '">' + inner + '</div>';
    }

    var html = '';
    // 1. Kontakt suchen
    html += secHead('search', 'Kontakt suchen', false);
    html += '<div style="padding:5px 8px"><input id="sp-tr-search-inp" type="text" placeholder="Name oder Nummer..." oninput="Softphone._transferSearch(this.value)" style="width:100%;box-sizing:border-box;padding:4px 7px;border:0.5px solid var(--border-color);border-radius:5px;font-size:11px;background:var(--bg-primary,#fff);color:var(--text-primary)"><div id="sp-transfer-search-results" style="margin-top:3px"></div></div></div>';
    // 2. Freie Nebenstellen
    var freeExts = (Softphone._fopExtCache || []).filter(function(e) { return e.status === 'free'; });
    html += secHead('exts', 'Nebenstellen \u2014 frei (' + freeExts.length + ')', true);
    if (freeExts.length) {
        freeExts.forEach(function(e) {
            html += '<div style="display:flex;align-items:center;gap:6px;padding:4px 8px;border-bottom:0.5px solid var(--border-color);font-size:11px"><span style="width:6px;height:6px;border-radius:50%;background:#22c55e;flex-shrink:0"></span><span style="flex:1">Ext. ' + e.extension + '</span>' + tBtn(e.extension) + '</div>';
        });
    } else {
        html += '<div style="padding:5px 8px;font-size:11px;color:var(--text-muted)">Keine freien Nebenstellen</div>';
    }
    html += '</div>';
    // 3. Schnellwahl
    var dials = Softphone._ext.speed_dials || [];
    html += secHead('speed', 'Schnellwahl (' + dials.length + ')', true);
    dials.forEach(function(d) {
        var num = d.num || (d.phones && d.phones[0] ? (d.phones[0].norm || d.phones[0].raw) : '');
        if (num) html += '<div style="display:flex;align-items:center;gap:6px;padding:5px 8px;border-bottom:0.5px solid var(--border-color);font-size:11px"><span style="flex:1">' + (d.name||'') + '</span><span style="font-size:9px;color:var(--text-muted)">' + num + '</span>' + tBtn(num) + '</div>';
    });
    if (!dials.length) html += '<div style="padding:5px 8px;font-size:11px;color:var(--text-muted)">Keine Schnellwahl</div>';
    html += '</div>';
    // 4. Letzte Anrufe
    var allRows  = Softphone._lastCdrRows || [];
    var missed   = allRows.filter(function(r) { return r.direction === 'incoming' && r.disposition !== 'ANSWERED'; });
    var answered = allRows.filter(function(r) { return r.direction === 'incoming' && r.disposition === 'ANSWERED'; });
    var dialed   = allRows.filter(function(r) { return r.direction === 'outgoing'; });
    html += secHead('recent', 'Letzte Anrufe', true);
    html += subSec('missed', 'Abwesenheit', missed, '#ef4444');
    html += subSec('answered', 'Angenommen', answered, '#22c55e');
    html += subSec('dialed', 'Gew\u00e4hlt', dialed, '#22c55e');
    html += '</div>';

    body.innerHTML = html;
};
JSEOF
node --check "${SP_JS}/9_sp-transfer.js" && ok "9_sp-transfer.js Syntax OK" || err "9_sp-transfer.js Syntax FEHLER"
echo

# ── 10_sp-fop.js ─────────────────────────────────────────
info "Schritt 6/7 — 10_sp-fop.js (FOP, Schnellwahl, Letzte Anrufe)"

cat > "${SP_JS}/10_sp-fop.js" << 'JSEOF'
/**
 * 10_sp-fop.js — FOP Panel, Schnellwahl, Letzte Anrufe
 * Extrahiert aus mod-softphone-ext.js
 */

Softphone._fopClosedSecs  = {};
Softphone._fopOpenExt     = null;
Softphone._lastCdrRows    = [];
Softphone._recentClosedSecs = { missed: false, incoming: true, outgoing: true };

// ── FOP Panel ─────────────────────────────────────────────
Softphone.toggleFOP = function() {
    var panel = document.getElementById('sp-fop-panel');
    var btn   = document.getElementById('sp-fop-toggle');
    if (!panel) return;
    var open = panel.style.display === 'none' || panel.style.display === '';
    if (open && Softphone._positionPanel) Softphone._positionPanel('sp-fop-panel', 'right');
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

Softphone._renderFOP = function(panel, data) {
    var colors = {
        free:    { bg: '#dcfce7', color: '#14532d', label: 'frei',    dot: '#22c55e' },
        busy:    { bg: '#fef3c7', color: '#92400e', label: 'besetzt', dot: '#ef4444' },
        dnd:     { bg: '#fee2e2', color: '#7f1d1d', label: 'DND',     dot: '#f59e0b' },
        offline: { bg: '#f3f4f6', color: '#6b7280', label: 'offline', dot: '#9ca3af' },
        unknown: { bg: '#f3f4f6', color: '#6b7280', label: '?',       dot: '#9ca3af' },
    };
    var hov  = 'onmouseover="this.style.background=\'var(--bg-secondary)\'" onmouseout="this.style.background=\'\'"';
    var BLUE = '#163258', BLUE_HOV = '#1e4080';
    var myExt = Softphone._ext.vm_ext || '';

    function secHeader(secId, label, dotColor) {
        var color = dotColor || 'rgba(255,255,255,0.25)';
        var dot = '<span style="width:7px;height:7px;border-radius:50%;background:' + color + ';flex-shrink:0;margin-right:5px"></span>';
        return '<div onclick="Softphone._fopToggleSec(\'' + secId + '\')" style="padding:4px 8px;font-size:9px;font-weight:600;color:#fff;background:' + BLUE + ';border-top:0.5px solid #1e4080;display:flex;align-items:center;justify-content:space-between;cursor:pointer" onmouseover="this.style.background=\'' + BLUE_HOV + '\'" onmouseout="this.style.background=\'' + BLUE + '\'">'
            + '<div style="display:flex;align-items:center">' + dot + label + '</div>'
            + '<span id="fop-sec-arr-' + secId + '" style="font-size:9px;opacity:.8">&#9660;</span>'
            + '</div><div id="fop-sec-' + secId + '">';
    }

    var html = '';

    // Extensions
    var exts = data.extensions || [];
    Softphone._fopExtCache = exts;
    var hasActive = exts.some(function(r) { return r.status !== 'offline' && r.status !== 'unknown'; });
    html += secHeader('ext', 'EXTENSIONS', hasActive ? '#22c55e' : 'rgba(255,255,255,0.25)');
    exts.forEach(function(r) {
        var c = colors[r.status] || colors.unknown;
        var isMe = myExt && r.extension === myExt;
        var actStyle = 'display:none;background:var(--bg-secondary,#f8f8f8);border-bottom:0.5px solid var(--border-color);padding:3px 6px;flex-wrap:wrap;gap:3px';
        var actBtns = '<span onclick="event.stopPropagation();Softphone.setNumber(\'' + r.extension + '\')" style="font-size:10px;padding:2px 6px;border:0.5px solid var(--border-color);border-radius:3px;cursor:pointer;background:var(--bg-primary)">&#9742; Anrufen</span>';
        if (isMe) actBtns += '<span onclick="event.stopPropagation();Softphone.toggleDND()" style="font-size:10px;padding:2px 6px;border:0.5px solid #fca5a5;border-radius:3px;cursor:pointer;background:#fee2e2;color:#7f1d1d">' + (r.dnd ? 'DND aus' : 'DND an') + '</span>';
        html += '<div onclick="Softphone._fopExtClick(this)" data-ext="' + r.extension + '" style="display:flex;align-items:center;gap:6px;padding:5px 8px;border-bottom:0.5px solid var(--border-color);font-size:11px;cursor:pointer" ' + hov + '>'
            + '<span style="width:7px;height:7px;border-radius:50%;background:' + c.dot + ';flex-shrink:0;pointer-events:none"></span>'
            + '<span style="font-weight:' + (isMe ? '600' : '400') + ';flex:1;pointer-events:none">' + (isMe ? '&#9733; ' : '') + 'Ext. ' + r.extension + '</span>'
            + '<div style="display:flex;align-items:center;gap:4px;pointer-events:none">'
            + '<span style="background:' + c.bg + ';color:' + c.color + ';padding:1px 5px;border-radius:3px;font-size:9px">' + c.label + '</span>'
            + '<span class="sp-arr" style="font-size:9px;color:var(--text-muted)">&#9658;</span>'
            + '</div></div>'
            + '<div id="fop-act-' + r.extension + '" style="' + actStyle + '">' + actBtns + '</div>';
    });
    html += '</div>';

    // Parking
    var parkSlots = ['701','702','703','704','705','706','707','708','709'];
    var parkedMap = {};
    (data.parking || []).forEach(function(p) { if (p.slot) parkedMap[p.slot] = p; });
    var hasParked = Object.keys(parkedMap).length > 0;
    html += secHeader('park', 'PARKING 700', hasParked ? '#ef4444' : '#22c55e');
    parkSlots.forEach(function(slot) {
        var p = parkedMap[slot];
        if (p) {
            html += '<div style="display:flex;align-items:center;gap:6px;padding:4px 8px;border-bottom:0.5px solid var(--border-color);font-size:11px">'
                + '<span style="width:7px;height:7px;border-radius:50%;background:#ef4444;flex-shrink:0"></span>'
                + '<span style="color:var(--text-muted);width:24px">' + slot + '</span>'
                + '<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + (p.caller_name || p.caller_id || '?') + '</span>'
                + '<span onclick="Softphone.setNumber(\'' + slot + '\');Softphone.call()" style="font-size:10px;padding:1px 5px;border:0.5px solid #86efac;border-radius:3px;cursor:pointer;background:#f0fdf4;color:#14532d">&#9742; Abholen</span>'
                + '</div>';
        } else {
            html += '<div style="display:flex;align-items:center;gap:6px;padding:4px 8px;border-bottom:0.5px solid var(--border-color);font-size:11px;color:var(--text-muted)">'
                + '<span style="width:7px;height:7px;border-radius:50%;background:#d1d5db;flex-shrink:0"></span>'
                + '<span style="width:24px">' + slot + '</span><span style="flex:1">leer</span>'
                + '<span onclick="Softphone._parkHere(\'' + slot + '\')" style="font-size:10px;padding:1px 5px;border:0.5px solid #7dd3fc;border-radius:3px;cursor:pointer;background:#e0f2fe;color:#0c4a6e">&#8659; Park</span>'
                + '</div>';
        }
    });
    html += '</div>';

    // Konferenzen
    var confRooms = { '034': 'MeetMeFree', '035': 'MeetMePin', '5555': 'AllHands' };
    var mmMap = {}, cbMap = {};
    (data.meetme || []).forEach(function(m) { mmMap[m.conference] = m; });
    (data.confbridge || []).forEach(function(c) { cbMap[c.conference] = c; });
    var hasConf = Object.keys(confRooms).some(function(num) {
        var mm = mmMap[num], cb = cbMap[num];
        return (mm && mm.users && mm.users.length > 0) || (cb && cb.parties > 0);
    });
    html += secHeader('conf', 'KONFERENZEN', hasConf ? '#ef4444' : '#22c55e');
    Object.keys(confRooms).forEach(function(num) {
        var name = confRooms[num], mm = mmMap[num], cb = cbMap[num];
        var count = mm ? (mm.users ? mm.users.length : 0) : (cb ? (cb.parties || 0) : 0);
        html += '<div style="display:flex;align-items:center;gap:6px;padding:4px 8px;border-bottom:0.5px solid var(--border-color);font-size:11px">'
            + '<span style="width:7px;height:7px;border-radius:50%;background:' + (count > 0 ? '#22c55e' : '#d1d5db') + ';flex-shrink:0"></span>'
            + '<span onclick="Softphone.setNumber(\'' + num + '\')" style="color:var(--text-muted);width:32px;cursor:pointer">' + num + '</span>'
            + '<span onclick="Softphone.setNumber(\'' + num + '\')" style="flex:1;cursor:pointer">' + name + '</span>'
            + '<span style="font-size:10px;color:var(--text-muted);margin-right:4px">' + (count > 0 ? count + ' Tlnhm.' : 'leer') + '</span>'
            + '<span onclick="Softphone._joinConference(\'' + num + '\')" style="font-size:10px;padding:1px 5px;border:0.5px solid #86efac;border-radius:3px;cursor:pointer;background:#f0fdf4;color:#14532d">&#8594; Konf</span>'
            + '</div>';
    });
    html += '</div>';

    // Voicemail
    var vm = data.voicemail || {};
    var hasVm = Object.keys(vm).some(function(e) { return vm[e] > 0; });
    html += secHeader('vm', 'VOICEMAIL', hasVm ? '#ef4444' : '#22c55e');
    Object.keys(vm).forEach(function(ext) {
        var count = vm[ext];
        html += '<div style="display:flex;align-items:center;gap:6px;padding:5px 8px;border-bottom:0.5px solid var(--border-color);font-size:11px">'
            + '<span style="width:7px;height:7px;border-radius:50%;background:' + (count > 0 ? '#ef4444' : '#22c55e') + ';flex-shrink:0"></span>'
            + '<span style="flex:1">Ext. ' + ext + '</span>'
            + (count > 0 ? '<span style="background:#fee2e2;color:#7f1d1d;padding:1px 5px;border-radius:3px;font-size:10px;font-weight:600;margin-right:4px">' + count + ' neu</span>' : '')
            + '<span onclick="Softphone.setNumber(\'*97' + ext + '\');Softphone.call()" style="font-size:10px;padding:1px 5px;border:0.5px solid var(--border-color);border-radius:3px;cursor:pointer;background:var(--bg-secondary)">&#9654; Abh\u00f6ren</span>'
            + '</div>';
    });
    html += '</div>';

    panel.innerHTML = html;
    ['ext','park','conf','vm'].forEach(function(id) {
        if (!(id in Softphone._fopClosedSecs)) Softphone._fopClosedSecs[id] = true;
    });
    if (Softphone._fopApplyOpen) Softphone._fopApplyOpen();
    if (Softphone._fopApplySecs) Softphone._fopApplySecs();
};

// Park + Conference
Softphone._parkHere = async function(slot) {
    var myExt = (document.getElementById('sp-cfg-user') || {value:''}).value.trim() || Softphone._ext.vm_ext || '';
    if (!myExt) { alert('Bitte eigene Extension in den Einstellungen konfigurieren.'); return; }
    try {
        var r = await fetch('/crm/api/telefon/park/', {
            method: 'POST',
            headers: {'Content-Type':'application/json','X-CSRFToken':Softphone._csrf()},
            body: JSON.stringify({ extension: myExt })
        });
        var d = await r.json();
        if (!d.success) alert('Parken fehlgeschlagen: ' + (d.error || 'Unbekannt'));
    } catch(e) { console.warn('SP-FOP: Park Fehler:', e); }
};

Softphone._joinConference = async function(conference) {
    var myExt = (document.getElementById('sp-cfg-user') || {value:''}).value.trim() || Softphone._ext.vm_ext || '';
    if (!myExt) { alert('Bitte eigene Extension in den Einstellungen konfigurieren.'); return; }
    try {
        var r = await fetch('/crm/api/telefon/conference/', {
            method: 'POST',
            headers: {'Content-Type':'application/json','X-CSRFToken':Softphone._csrf()},
            body: JSON.stringify({ extension: myExt, conference: conference })
        });
        var d = await r.json();
        if (!d.success) alert('Konferenz fehlgeschlagen: ' + (d.error || 'Unbekannt'));
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
    if (btn) btn.style.background = open ? '#dbeafe' : 'var(--bg-secondary,#f8f8f8)';
    if (open) Softphone._renderSpeedDials();
};

Softphone._renderSpeedDials = async function() {
    var panel = document.getElementById('sp-speed-list');
    if (!panel) return;
    var dials = Softphone._ext.speed_dials || [];
    if (!dials.length) {
        panel.innerHTML = '<div style="padding:8px;font-size:10px;color:var(--text-muted)">Keine Schnellwahl konfiguriert.<br>Kontakt aus Suche hierher ziehen.</div>';
        return;
    }
    panel.innerHTML = '<div style="padding:6px 8px;font-size:10px;color:var(--text-muted)">Lade...</div>';
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
        var el = document.createElement('div');
        el.style.cssText = 'border-bottom:0.5px solid var(--border-color)';
        var nameCSS = 'font-weight:500;font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1';
        var subCSS  = 'font-size:10px;color:var(--text-muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap';
        var delCSS  = 'font-size:11px;color:var(--text-muted);cursor:pointer;flex-shrink:0;margin-left:4px';
        var headCSS = 'padding:5px 8px;display:flex;align-items:center;gap:5px;cursor:pointer;';
        var subBG   = 'background:var(--bg-secondary,#f8f8f8)';
        var uid = 'spd-' + idx;

        function numRow(p, indent) {
            var num = p.norm || p.raw || '';
            var lbl = p.label || p.field_name || '';
            return '<div onclick="Softphone.setNumber(\'' + num + '\')" style="padding:4px 10px 4px ' + indent + 'px;font-size:10px;display:flex;justify-content:space-between;cursor:pointer;' + subBG + ';border-top:0.5px solid var(--border-color)" onmouseover="this.style.background=\'var(--border-color)\'" onmouseout="this.style.background=\'var(--bg-secondary,#f8f8f8)\'"><span style="color:var(--text-muted)">' + lbl + '</span><span>' + num + '</span></div>';
        }

        var delBtn = '<span onclick="event.stopPropagation();Softphone._speedDialRemove(' + idx + ')" style="' + delCSS + '">&#10005;</span>';
        var arrSpan = '<span class="sp-arr" style="font-size:9px;color:var(--text-muted);margin-right:4px">&#9658;</span>';
        var toggleFn = 'var s=document.getElementById(\'' + uid + '\');s.style.display=s.style.display===\'none\'?\'block\':\'none\';this.querySelector(\'.sp-arr\').textContent=s.style.display===\'block\'?\'▼\':\'▶\'';

        if (item.type === 'firma') {
            var apHTML = '';
            (item.ap || []).forEach(function(ap, ai) {
                var auid = uid + '-' + ai;
                var nums = (ap.phones || []).map(function(p) { return numRow(p, 24); }).join('');
                apHTML += '<div><div onclick="var s=document.getElementById(\'' + auid + '\');s.style.display=s.style.display===\'none\'?\'block\':\'none\'" style="padding:4px 8px 4px 14px;font-size:11px;display:flex;justify-content:space-between;cursor:pointer;border-top:0.5px solid var(--border-color);' + subBG + '" onmouseover="this.style.filter=\'brightness(0.95)\'" onmouseout="this.style.filter=\'\'"><span>' + ap.name.trim() + '</span><span style="font-size:9px;color:var(--text-muted)">&#9658;</span></div><div id="' + auid + '" style="display:none">' + nums + '</div></div>';
            });
            el.innerHTML = '<div onclick="' + toggleFn + '" style="' + headCSS + 'justify-content:space-between" onmouseover="this.style.background=\'var(--bg-secondary)\'" onmouseout="this.style.background=\'\'"><div style="min-width:0;flex:1"><div style="' + nameCSS + '">' + item.name + '</div><div style="' + subCSS + '">' + (item.ap||[]).length + ' Ansprechpartner</div></div>' + arrSpan + delBtn + '</div><div id="' + uid + '" style="display:none">' + apHTML + '</div>';
        } else if (item.type === 'person') {
            var nums = (item.phones || []).map(function(p) { return numRow(p, 16); }).join('');
            el.innerHTML = '<div onclick="' + toggleFn + '" style="' + headCSS + 'justify-content:space-between" onmouseover="this.style.background=\'var(--bg-secondary)\'" onmouseout="this.style.background=\'\'"><div style="min-width:0;flex:1"><div style="' + nameCSS + '">' + item.name + '</div>' + (item.firma ? '<div style="' + subCSS + '">' + item.firma + '</div>' : '') + '</div>' + arrSpan + delBtn + '</div><div id="' + uid + '" style="display:none">' + nums + '</div>';
        } else {
            var num = item.num || '';
            el.innerHTML = '<div onclick="' + toggleFn + '" style="' + headCSS + 'justify-content:space-between" onmouseover="this.style.background=\'var(--bg-secondary)\'" onmouseout="this.style.background=\'\'"><div style="min-width:0;flex:1"><div style="' + nameCSS + '">' + item.name + '</div></div>' + arrSpan + delBtn + '</div><div id="' + uid + '" style="display:none"><div onclick="Softphone.setNumber(\'' + num + '\')" style="padding:4px 10px 4px 16px;font-size:10px;display:flex;justify-content:space-between;cursor:pointer;' + subBG + ';border-top:0.5px solid var(--border-color)" onmouseover="this.style.background=\'var(--border-color)\'" onmouseout="this.style.background=\'var(--bg-secondary,#f8f8f8)\'"><span style="color:var(--text-muted)">Nummer</span><span>' + num + '</span></div></div>';
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
        crm_id: contact.crm_id,
        crm_type: contact.typ === 'kunde' ? 'firma' : 'person',
        name: contact.full_name || contact.name || '',
        type: contact.typ === 'kunde' ? 'firma' : 'person',
    });
    await Softphone._saveSpeedDials();
    Softphone._renderSpeedDials();
};

Softphone._speedDialAddManual    = function() { var f = document.getElementById('sp-speed-add-form'); if (f) f.style.display = f.style.display === 'flex' ? 'none' : 'flex'; };
Softphone._speedDialCancelManual = function() { var f = document.getElementById('sp-speed-add-form'); if (f) f.style.display = 'none'; var l = document.getElementById('sp-speed-add-label'); var n = document.getElementById('sp-speed-add-number'); if (l) l.value = ''; if (n) n.value = ''; };
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
    form.style.cssText = 'padding:6px 8px;border-top:1px solid var(--border-color);';
    form.innerHTML = '<input id="sp-firma-q" placeholder="Firmaname suchen..." style="font-size:11px;padding:3px 6px;border:1px solid var(--border-color);border-radius:4px;width:100%;box-sizing:border-box;background:var(--bg-secondary,#f8f8f8);color:var(--text-primary)" oninput="Softphone._speedDialSearchFirma(this.value)"><div id="sp-firma-results" style="max-height:120px;overflow-y:auto;margin-top:4px"></div>';
    panel.appendChild(form);
    setTimeout(function() { var q = document.getElementById('sp-firma-q'); if (q) q.focus(); }, 50);
};

Softphone._speedDialSearchFirma = async function(q) {
    var res = document.getElementById('sp-firma-results');
    if (!res) return;
    if (!q || q.length < 2) { res.innerHTML = ''; return; }
    try {
        var r = await fetch('/crm/api/kunden/?q=' + encodeURIComponent(q) + '&per_page=6');
        var d = await r.json();
        var items = (d.results || []).slice(0, 6);
        if (!items.length) { res.innerHTML = '<div style="font-size:10px;color:var(--text-muted);padding:4px">Keine Treffer</div>'; return; }
        res.innerHTML = items.map(function(a) {
            var dataStr = JSON.stringify({ crm_id: a.crm_id, type:'firma', crm_type:'firma', name: a.name }).replace(/"/g, '&quot;');
            return '<div onclick="Softphone._speedDialAddFirmaEntry(JSON.parse(this.dataset.firma))" data-firma="' + dataStr + '" style="padding:4px 6px;font-size:11px;cursor:pointer;border-bottom:0.5px solid var(--border-color)" onmouseover="this.style.background=\'var(--bg-secondary)\'" onmouseout="this.style.background=\'\'">' + a.name + '</div>';
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
    if (body) body.innerHTML = '<div style="padding:8px;font-size:11px;color:var(--text-muted)">Lade...</div>';
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

Softphone.toggleRecent  = function() { var p = document.getElementById('sp-recent-panel'); if (p) p.style.display = 'none'; };
Softphone._closeRecent  = function() { var p = document.getElementById('sp-recent-panel'); if (p) p.style.display = 'none'; };

Softphone._positionRecent = function() {
    var modal = document.getElementById('sp-modal');
    var panel = document.getElementById('sp-recent-panel');
    if (!modal || !panel) return;
    var r = modal.getBoundingClientRect();
    var maxH = window.innerHeight - r.bottom - 8;
    panel.style.left      = r.left + 'px';
    panel.style.width     = r.width + 'px';
    panel.style.top       = (r.bottom + 4) + 'px';
    panel.style.maxHeight = Math.max(150, maxH) + 'px';
};

Softphone._renderRecent = function(rows) {
    var body = document.getElementById('sp-recent-body');
    if (!body) return;
    var BLUE = '#163258', BLUE_HOV = '#1e4080';
    var missed   = rows.filter(function(r) { return r.direction === 'incoming' && r.disposition !== 'ANSWERED'; });
    var incoming = rows.filter(function(r) { return r.direction === 'incoming' && r.disposition === 'ANSWERED'; });
    var outgoing = rows.filter(function(r) { return r.direction === 'outgoing'; });

    function rowHtml(r) {
        var num  = r.direction === 'incoming' ? r.src : r.dst;
        var name = (r.contact && r.contact.name) ? r.contact.name : '';
        var disp = name || num;
        var time = r.calldate ? r.calldate.substring(11,16) + ' ' + r.calldate.substring(5,10) : '';
        var dur  = r.billsec_fmt || '';
        return '<div onclick="Softphone.setNumber(\'' + num + '\');Softphone._closeRecent()" style="display:flex;align-items:center;gap:6px;padding:5px 8px;border-bottom:0.5px solid var(--border-color);font-size:11px;cursor:pointer" onmouseover="this.style.background=\'var(--bg-secondary)\'" onmouseout="this.style.background=\'\'">'
            + '<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + disp + '</span>'
            + (name ? '<span style="font-size:9px;color:var(--text-muted);flex-shrink:0">' + num + '</span>' : '')
            + '<span style="font-size:9px;color:var(--text-muted);flex-shrink:0;margin-left:4px">' + time + '</span>'
            + (dur ? '<span style="font-size:9px;color:var(--text-muted);flex-shrink:0;margin-left:2px">' + dur + '</span>' : '')
            + '</div>';
    }

    function secHtml(id, label, dotColor, rows) {
        var dot    = '<span style="width:7px;height:7px;border-radius:50%;background:' + dotColor + ';flex-shrink:0;margin-right:5px"></span>';
        var closed = Softphone._recentClosedSecs && Softphone._recentClosedSecs[id];
        var arr    = closed ? '&#9658;' : '&#9660;';
        var html   = '<div onclick="Softphone._recentToggleSec(\'' + id + '\')" style="padding:4px 8px;font-size:9px;font-weight:600;color:#fff;background:' + BLUE + ';border-top:0.5px solid #1e4080;display:flex;align-items:center;justify-content:space-between;cursor:pointer" onmouseover="this.style.background=\'' + BLUE_HOV + '\'" onmouseout="this.style.background=\'' + BLUE + '\'">'
            + '<div style="display:flex;align-items:center">' + dot + label + ' (' + rows.length + ')</div>'
            + '<span id="sp-recent-arr-' + id + '" style="font-size:9px;opacity:.8">' + arr + '</span></div>'
            + '<div id="sp-recent-sec-' + id + '" style="display:' + (closed ? 'none' : 'block') + '">';
        html += rows.length ? rows.map(rowHtml).join('') : '<div style="padding:6px 8px;font-size:11px;color:var(--text-muted)">Keine Eintr\u00e4ge</div>';
        html += '</div>';
        return html;
    }

    body.innerHTML =
        secHtml('missed',   'Abwesenheit', missed.length   > 0 ? '#ef4444' : '#22c55e', missed)
      + secHtml('incoming', 'Angenommen',  '#22c55e', incoming)
      + secHtml('outgoing', 'Gew\u00e4hlt', '#22c55e', outgoing);
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
JSEOF
node --check "${SP_JS}/10_sp-fop.js" && ok "10_sp-fop.js Syntax OK" || err "10_sp-fop.js Syntax FEHLER"
echo

# ── Deploy ────────────────────────────────────────────────
info "Schritt 7/7 — Deploy"
python3 manage.py collectstatic --noinput 2>&1 | tail -3
echo
supervisorctl restart abpe-django
sleep 2
supervisorctl status abpe-django
echo

echo "════════════════════════════════════════════════════"
echo -e "${GREEN}Module befüllt und deployed${NC}"
echo "════════════════════════════════════════════════════"
echo
echo "JS-Dateien:"
for f in 6_sp-core 7_sp-ui 8_sp-status 9_sp-transfer 10_sp-fop; do
    bytes=$(wc -c < "${SP_JS}/${f}.js")
    echo "  ${f}.js  — ${bytes} bytes"
done
echo
echo "Browser: Hard-Reload (Ctrl+Shift+R)"
echo
echo "Erwartet — Console (kein Fehler):"
echo "  SP: Service Worker registriert, scope: ..."
echo "  ABpE Softphone bereit."
echo
echo "Erwartet — UI:"
echo "  Softphone-Widget sichtbar, Tastatur bedienbar"
echo "  SIP-Settings werden aus Django-Context vorausgefüllt"
echo "  'Speichern & registrieren' → Verbindung zur PBX"

