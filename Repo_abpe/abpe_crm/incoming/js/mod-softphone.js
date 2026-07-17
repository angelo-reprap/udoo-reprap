/**
 * mod-softphone.js — JsSIP Browser Softphone für ABpE CRM
 */
const Softphone = (() => {

    let ua = null;
    let currentSession = null;
    let timerInterval = null;
    let timerSeconds = 0;
    let isMuted = false;
    let _audioEl = null;
    let cfg = { user: '', pass: '', ws: '', name: '' };

    // ── Init ──────────────────────────────────────────────────
    function init() {
        _insertButton();
        _loadSettings().then(() => {
            if (cfg.user && cfg.pass && cfg.ws) {
                _register();
            }
        });
    }

    function _insertButton() {
        const tpl = document.getElementById('softphone-btn-tpl');
        if (!tpl) return;
        const tabBar = document.querySelector('.ts-tab-btn[data-tab="call"]')?.parentElement;
        if (tabBar) tabBar.appendChild(tpl.content.cloneNode(true));
    }

    async function _loadSettings() {
        try {
            const r = await fetch('/crm/api/user-settings/');
            const d = await r.json();
            if (d.success) {
                const s = d.data;
                cfg.user = s.phone_extension || '';
                cfg.pass = s.phone_pin || '';
                cfg.ws   = s.softphone_ws || 'wss://pbx.win.abcona.info:8089/ws';
                cfg.name = s.phone_display_name || cfg.user;
                document.getElementById('sp-cfg-user').value = cfg.user;
                document.getElementById('sp-cfg-pass').value = cfg.pass;
                document.getElementById('sp-cfg-ws').value   = cfg.ws;
                document.getElementById('sp-cfg-name').value = cfg.name;
            }
        } catch(e) { console.warn('Softphone: Settings laden fehlgeschlagen', e); }
    }

    function _register() {
        if (ua) { try { ua.stop(); } catch(e){} }

        const socket = new JsSIP.WebSocketInterface(cfg.ws);
        const config = {
            sockets:            [socket],
            uri:                `sip:${cfg.user}@${new URL(cfg.ws).hostname}`,
            password:           cfg.pass,
            authorization_user: cfg.user,
            realm:              'asterisk',
            display_name:       cfg.name || cfg.user,
            register:           true,
            register_expires:   300,
            session_timers:     false,
        };

        ua = new JsSIP.UA(config);

        ua.on('registered',         () => _setStatus('Registriert · ' + cfg.user, '#22c55e'));
        ua.on('unregistered',       () => _setStatus('Nicht registriert', '#9ca3af'));
        ua.on('registrationFailed', (e) => _setStatus('Fehler: ' + (e.cause || 'unbekannt'), '#ef4444'));

        ua.on('newRTCSession', (e) => {
            // DTLS fix
            e.session.on('sdp', (data) => {
                data.sdp = data.sdp.replace(/a=setup:actpass/g, 'a=setup:passive');
            });

            // Audio beim confirmed Event verdrahten
            e.session.on('confirmed', () => {
                _setupAudio(e.session.connection);
            });

            if (e.originator === 'remote') {
                _handleIncoming(e.session);
            }
        });

        ua.start();
    }

    function _setupAudio(pc) {
        // Altes Audio-Element entfernen
        if (_audioEl) { try { _audioEl.remove(); } catch(e){} }
        _audioEl = document.createElement('audio');
        _audioEl.autoplay = true;
        _audioEl.style.display = 'none';
        document.body.appendChild(_audioEl);

        pc.ontrack = (e) => {
            console.log('Softphone: ontrack fired', e.streams);
            if (e.streams && e.streams[0]) {
                _audioEl.srcObject = e.streams[0];
                _audioEl.play().catch(err => console.warn('Audio play failed:', err));
            }
        };

        // Fallback: alle Remote-Streams prüfen
        setTimeout(() => {
            const receivers = pc.getReceivers();
            if (receivers.length && !_audioEl.srcObject) {
                const stream = new MediaStream(receivers.map(r => r.track));
                _audioEl.srcObject = stream;
                _audioEl.play().catch(err => console.warn('Audio fallback play failed:', err));
            }
        }, 2000);
    }

    function _setStatus(text, color) {
        const dot  = document.getElementById('sp-status-dot');
        const rdot = document.getElementById('sp-reg-dot');
        const txt  = document.getElementById('sp-status-text');
        if (dot)  dot.style.background  = color;
        if (rdot) rdot.style.background = color;
        if (txt)  txt.textContent       = text;
    }

    function toggle() {
        const m = document.getElementById('sp-modal');
        if (!m) return;
        m.style.display = m.style.display === 'none' ? 'block' : 'none';
        if (m.style.display === 'block') _loadRecent();
    }

    function showTab(tab, btn) {
        document.getElementById('sp-tab-dial').style.display     = tab === 'dial'     ? 'block' : 'none';
        document.getElementById('sp-tab-settings').style.display = tab === 'settings' ? 'block' : 'none';
        document.querySelectorAll('.sp-tab-btn').forEach(b => b.classList.remove('sp-tab-active'));
        if (btn) btn.classList.add('sp-tab-active');
    }

    function press(key) {
        if (currentSession?.isEstablished()) {
            try { currentSession.sendDTMF(key); } catch(e) {}
            return;
        }
        const d = document.getElementById('sp-display');
        if (!d) return;
        const cur = d.textContent.trim() === '\u00a0' ? '' : d.textContent.trim();
        d.textContent = cur + key;
    }

    function backspace() {
        const d = document.getElementById('sp-display');
        if (!d) return;
        const cur = d.textContent.trim();
        d.textContent = cur.length > 1 ? cur.slice(0, -1) : '\u00a0';
    }

    function clearDisplay() {
        const d = document.getElementById('sp-display');
        if (d) d.textContent = '\u00a0';
    }

    function setNumber(num) {
        const d = document.getElementById('sp-display');
        if (d) d.textContent = num;
        const m = document.getElementById('sp-modal');
        if (m) m.style.display = 'block';
        showTab('dial', document.querySelector('.sp-tab-btn'));
    }

    function call() {
        if (!ua?.isRegistered()) {
            alert('Softphone nicht registriert. Bitte Einstellungen prüfen.');
            showTab('settings', null);
            return;
        }
        const d = document.getElementById('sp-display');
        const num = (d?.textContent || '').trim();
        if (!num || num === '\u00a0') return;

        const target = `sip:${num}@${new URL(cfg.ws).hostname}`;
        const opts = {
            mediaConstraints: { audio: true, video: false },
            pcConfig: { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] },
        };

        currentSession = ua.call(target, opts);
        Softphone._currentSession = currentSession;
        _bindSessionEvents(currentSession);
        _showCallUI(true);
    }

    function _handleIncoming(session) {
        currentSession = session;
        Softphone._currentSession = currentSession;
        const num = session.remote_identity?.uri?.user || 'Unbekannt';

        _resolveContact(num).then(name => {
            const inc = document.getElementById('sp-incoming');
            document.getElementById('sp-inc-name').textContent = name || num;
            document.getElementById('sp-inc-num').textContent  = num;
            const av = document.getElementById('sp-inc-avatar');
            av.textContent = (name || num).substring(0, 2).toUpperCase();
            if (inc) inc.style.display = 'block';
        });

        session.on('ended',  () => { _hideIncoming(); _resetCallUI(); });
        session.on('failed', () => { _hideIncoming(); _resetCallUI(); });
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
        if (currentSession) { try { currentSession.terminate(); } catch(e){} }
        _resetCallUI();
    }

    function toggleMute() {
        if (!currentSession) return;
        isMuted = !isMuted;
        isMuted ? currentSession.mute() : currentSession.unmute();
        const btn = document.getElementById('sp-mute-btn');
        if (btn) btn.innerHTML = isMuted
            ? '<i class="bi bi-mic-mute-fill"></i>'
            : '<i class="bi bi-mic-fill"></i>';
    }

    function _bindSessionEvents(session) {
        session.on('confirmed', () => _startTimer());
        session.on('ended',     () => { _stopTimer(); _resetCallUI(); });
        session.on('failed',    (e) => {
            _stopTimer(); _resetCallUI();
            console.warn('Anruf fehlgeschlagen:', e.cause);
        });
    }

    function _showCallUI(active) {
        const callBtn     = document.getElementById('sp-call-btn');
        const hangupBtn   = document.getElementById('sp-hangup-btn');
        const muteBtn     = document.getElementById('sp-mute-btn');
        const transferBtn = document.getElementById('sp-transfer-btn');
        const fnBar       = document.getElementById('sp-fn-bar');
        if (callBtn)   callBtn.style.display   = active ? 'none'  : 'flex';
        if (hangupBtn) hangupBtn.style.display = active ? 'flex'  : 'none';
        if (muteBtn)   muteBtn.style.display   = active ? 'block' : 'none';
        if (transferBtn) transferBtn.style.display = active ? 'block' : 'none';
        if (fnBar) fnBar.style.gridTemplateColumns = active ? 'repeat(5,1fr)' : 'repeat(4,1fr)';
        if (!active && typeof Softphone !== 'undefined') {
            var tp = document.getElementById('sp-transfer-panel');
            if (tp) tp.style.display = 'none';
        }
    }

    function _resetCallUI() {
        Softphone._currentSession = null;
        _showCallUI(false);
        _stopTimer();
        isMuted = false;
        const muteBtn = document.getElementById('sp-mute-btn');
        if (muteBtn) muteBtn.innerHTML = '<i class="bi bi-mic-fill"></i>';
        currentSession = null;
    }

    function _hideIncoming() {
        const inc = document.getElementById('sp-incoming');
        if (inc) inc.style.display = 'none';
    }

    function _startTimer() {
        timerSeconds = 0;
        const el = document.getElementById('sp-call-timer');
        if (el) el.style.display = 'block';
        timerInterval = setInterval(() => {
            timerSeconds++;
            const m = Math.floor(timerSeconds / 60);
            const s = timerSeconds % 60;
            if (el) el.textContent = `${m}:${s.toString().padStart(2,'0')}`;
        }, 1000);
    }

    function _stopTimer() {
        clearInterval(timerInterval);
        const el = document.getElementById('sp-call-timer');
        if (el) el.style.display = 'none';
        timerSeconds = 0;
    }

    async function search(q) {
        const res = document.getElementById('sp-search-results');
        if (!q || q.length < 2) { if (res) res.style.display = 'none'; return; }
        try {
            const r = await fetch(`/crm/api/berater/?q=${encodeURIComponent(q)}&per_page=8&typ=alle`);
            const d = await r.json();
            const contacts = (d.results || d.berater || []).slice(0, 8);
            if (!contacts.length) { res.style.display = 'none'; return; }
            res.innerHTML = contacts.map(c => {
                const name   = `${c.first_name || ''} ${c.last_name || ''}`.trim() || c.name || '—';
                const phones = (c.phones || []).filter(p => p.raw || p.norm);
                const mainNum = phones.length ? (phones.find(p => p.is_primary) || phones[0]).norm || (phones.find(p => p.is_primary) || phones[0]).raw : '';
                const cJson = JSON.stringify(c).replace(/"/g, '&quot;');
                const pinBtn = `<span onclick="event.stopPropagation();Softphone._speedDialAddFromContact(JSON.parse(this.dataset.c))" data-c="${cJson}"
                    title="Zur Schnellwahl" class="sp-pin-contact"
                    style="font-size:11px;color:var(--text-muted);cursor:pointer;flex-shrink:0;margin-left:6px;opacity:0;padding:2px 4px;border-radius:3px"
                    onmouseover="this.style.opacity='1';this.style.color='#163258';this.style.background='#dbeafe'"
                    onmouseout="this.style.opacity='0';this.style.color='var(--text-muted)';this.style.background=''">&#128204;</span>`;

                if (phones.length <= 1) {
                    return `<div style="padding:6px 10px;cursor:pointer;border-bottom:1px solid var(--border-color);
                        display:flex;justify-content:space-between;align-items:center"
                        onmouseover="this.style.background='var(--bg-secondary)';this.querySelector('.sp-pin-contact').style.opacity='1'"
                        onmouseout="this.style.background='';this.querySelector('.sp-pin-contact').style.opacity='0'">
                        <span onclick="Softphone.setNumber('${mainNum}')" style="font-weight:500;flex:1">${name}</span>
                        <span onclick="Softphone.setNumber('${mainNum}')" style="color:var(--text-muted);font-size:11px;cursor:pointer">${mainNum}</span>
                        ${pinBtn}
                    </div>`;
                } else {
                    const id = 'sp-ph-' + Math.random().toString(36).slice(2,7);
                    const subItems = phones.map(p => {
                        const num = p.norm || p.raw;
                        const lbl = p.label || p.field_name || '';
                        return `<div onclick="event.stopPropagation();Softphone.setNumber('${num}')"
                            style="padding:4px 10px 4px 20px;cursor:pointer;font-size:11px;
                            display:flex;justify-content:space-between;background:var(--bg-secondary)"
                            onmouseover="this.style.background='var(--border-color)'"
                            onmouseout="this.style.background='var(--bg-secondary)'">
                            <span style="color:var(--text-muted)">${lbl}</span>
                            <span>${num}</span>
                        </div>`;
                    }).join('');
                    return `<div style="border-bottom:1px solid var(--border-color)">
                        <div onclick="document.getElementById('${id}').style.display=document.getElementById('${id}').style.display==='none'?'block':'none'"
                            style="padding:6px 10px;cursor:pointer;display:flex;justify-content:space-between;align-items:center"
                            onmouseover="this.style.background='var(--bg-secondary)';this.querySelector('.sp-pin-contact').style.opacity='1'"
                            onmouseout="this.style.background='';this.querySelector('.sp-pin-contact').style.opacity='0'">
                            <span style="font-weight:500;flex:1">${name}</span>
                            <span style="color:var(--text-muted);font-size:11px">${mainNum} ▾</span>
                            ${pinBtn}
                        </div>
                        <div id="${id}" style="display:none">${subItems}</div>
                    </div>`;
                }
            }).join('');
            res.style.display = 'block';
        } catch(e) { if (res) res.style.display = 'none'; }
    }

    async function _resolveContact(num) {
        if (!num || num.replace(/\D/g, '').length < 5) return null;
        try {
            const r = await fetch(`/crm/api/berater/?q=${encodeURIComponent(num)}&per_page=1&typ=alle`);
            const d = await r.json();
            const c = (d.results || d.berater || [])[0];
            if (c) return `${c.first_name || ''} ${c.last_name || ''}`.trim();
        } catch(e) {}
        return null;
    }

    async function _loadRecent() {
        const el = document.getElementById('sp-recent');
        if (!el) return;
        try {
            const ext = document.getElementById('ts-extension-select')?.value;
            if (!ext) return;
            const r = await fetch(`/crm/api/telefon/cdr/?extension=${ext}&days=7&limit=5`);
            const d = await r.json();
            const rows = (d.rows || []).slice(0, 4);
            if (!rows.length) return;
            el.innerHTML = '<div style="font-size:10px;color:var(--text-muted);margin-bottom:3px;font-weight:500">Zuletzt</div>' +
                rows.map(row => {
                    const num  = row.src || row.dst || '';
                    const name = row.contact_name || '';
                    const disp = name || num;
                    return `<div onclick="Softphone.setNumber('${num}')"
                        style="display:flex;align-items:center;gap:7px;padding:4px 0;cursor:pointer;
                        border-bottom:1px solid var(--border-color)"
                        onmouseover="this.style.background='var(--bg-secondary)'"
                        onmouseout="this.style.background=''">
                        <div style="width:24px;height:24px;border-radius:50%;background:#dbeafe;color:#1e40af;
                            display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:600;flex-shrink:0">
                            ${disp.substring(0,2).toUpperCase()}
                        </div>
                        <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${disp}</span>
                        <span style="color:var(--text-muted);font-size:10px;flex-shrink:0">${num !== disp ? num : ''}</span>
                    </div>`;
                }).join('');
        } catch(e) {}
    }

    async function saveAndRegister() {
        cfg.user = document.getElementById('sp-cfg-user').value.trim();
        cfg.pass = document.getElementById('sp-cfg-pass').value.trim();
        cfg.ws   = document.getElementById('sp-cfg-ws').value.trim();
        cfg.name = document.getElementById('sp-cfg-name').value.trim();

        const msg = document.getElementById('sp-cfg-msg');
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
        setTimeout(() => showTab('dial', document.querySelector('.sp-tab-btn')), 800);
    }

    function _csrf() {
        return document.cookie.split(';').map(c => c.trim())
            .find(c => c.startsWith('csrftoken='))?.split('=')[1] || '';
    }

    return { init, toggle, showTab, press, backspace, clearDisplay, call, hangup,
             answer, reject, toggleMute, search, setNumber, saveAndRegister,
             get _sipServer() { try { return new URL(cfg.ws).hostname; } catch(e) { return 'pbx.win.abcona.info'; } } };

})();

document.addEventListener('click', e => {
    const btn = e.target.closest('[data-sp-call]');
    if (btn) {
        e.preventDefault();
        Softphone.setNumber(btn.dataset.spCall);
    }
});

document.addEventListener('keydown', function(e) {
    const modal = document.getElementById('sp-modal');
    if (!modal || modal.style.display === 'none') return;
    if (['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName)) return;
    if (e.ctrlKey || e.altKey || e.metaKey) {
        if (e.ctrlKey && e.key === 'c') {
            var d = document.getElementById('sp-display');
            var num = d ? d.textContent.trim() : '';
            if (num && num !== '\u00a0') {
                navigator.clipboard.writeText(num).catch(function() {});
            }
        }
        return;
    }
    if (e.key === 'Delete' || e.key === 'Escape') {
        Softphone.clearDisplay();
    } else if (e.key === 'Backspace') {
        Softphone.backspace();
    } else if (e.key === 'Enter') {
        Softphone.call();
    } else if (/^[0-9*#+]$/.test(e.key)) {
        Softphone.press(e.key);
    }
});

document.addEventListener('paste', function(e) {
    const modal = document.getElementById('sp-modal');
    if (!modal || modal.style.display === 'none') return;
    if (['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName)) return;
    var text = (e.clipboardData || window.clipboardData).getData('text');
    if (!text) return;
    var num = text.replace(/[^0-9+*#]/g, '').trim();
    if (num) { e.preventDefault(); Softphone.setNumber(num); }
});

document.addEventListener('DOMContentLoaded', () => Softphone.init());
