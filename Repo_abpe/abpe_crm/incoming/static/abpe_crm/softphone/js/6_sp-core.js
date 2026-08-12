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
        _initStatus();
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

        ua.on('registered',         function() { _setStatus(SP_i18n.t('registered', 'Registriert') + ' · ' + cfg.user, '#22c55e'); });
        ua.on('unregistered',       function() { _setStatus(SP_i18n.t('not_registered', 'Nicht registriert'), 'var(--dot-offline)'); });
        ua.on('registrationFailed', function(e) { _setStatus(SP_i18n.t('error', 'Fehler') + ': ' + (e.cause || SP_i18n.t('unknown', 'unbekannt')), '#ef4444'); });

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

    function _initStatus() {
        _setStatus(SP_i18n.t('not_connected', 'Nicht verbunden'), 'var(--dot-offline)');
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
        // i18n nach Tab-Wechsel neu anwenden
        if (window.SP_i18n && SP_i18n.isLoaded()) SP_i18n.apply();
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
            alert(SP_i18n.t('not_registered_alert', 'Softphone nicht registriert.'));
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
        _bindSessionEvents(currentSession, true);
        _showCallUI(true);
    }

    // ── Eingehender Anruf ─────────────────────────────────
    function _handleIncoming(session) {
        currentSession = session;
        Softphone._currentSession = currentSession;
        var num = (session.remote_identity && session.remote_identity.uri)
            ? session.remote_identity.uri.user : SP_i18n.t('unknown', 'Unbekannt');

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
        _bindSessionEvents(currentSession, true);
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
    function _bindSessionEvents(session, isMain) {
        session.on('confirmed', function() { if (isMain) _startTimer(); });
        session.on('ended',     function() {
            if (isMain || session === currentSession) { _stopTimer(); _resetCallUI(); }
        });
        session.on('failed',    function(e) {
            if (isMain || session === currentSession) { _stopTimer(); _resetCallUI(); }
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
                    + ' title="' + SP_i18n.t('speed_dial_title','Zur Schnellwahl') + '" class="sp-pin-contact"'
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
            el.innerHTML = '<div style="font-size:10px;color:var(--text-muted);margin-bottom:3px;font-weight:500">' + SP_i18n.t('recent', 'Zuletzt') + '</div>'
                + rows.map(function(row) {
                    var num  = row.src || row.dst || '';
                    var name = row.contact_name || '';
                    var disp = name || num;
                    return '<div onclick="Softphone.setNumber(\'' + num + '\')"'
                        + ' style="display:flex;align-items:center;gap:7px;padding:4px 0;cursor:pointer;border-bottom:1px solid var(--border-color)"'
                        + ' onmouseover="this.style.background=\'var(--bg-secondary)\'"'
                        + ' onmouseout="this.style.background=\'\'">'
                        + '<div style="width:24px;height:24px;border-radius:50%;background:var(--avatar-cdr-bg);color:var(--avatar-cdr-color);display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:600;flex-shrink:0">'
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
            if (msg) { msg.style.color = '#22c55e'; msg.textContent = SP_i18n.t('saved', 'Gespeichert.'); }
        } catch(e) {
            if (msg) { msg.style.color = '#ef4444'; msg.textContent = SP_i18n.t('save_failed', 'Speichern fehlgeschlagen.'); }
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

// Init wird von 11_sp-init.js aufgerufen — nicht hier
