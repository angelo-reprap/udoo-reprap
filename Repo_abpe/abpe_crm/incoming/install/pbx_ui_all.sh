#!/usr/bin/env bash
# ============================================================
#  pbx_ui_all.sh — Telefon-Cockpit UI (Template + CSS + JS + i18n)
#  Ausfuehren aus /opt/abpe/backend:  chmod +x pbx_ui_all.sh && ./pbx_ui_all.sh
# ============================================================
set -e
cd /opt/abpe/backend
echo ">> Backups..."
python3 Archiv/backup_restore.py -save apps/abpe_crm/templates/abpe_crm/telefon.html            -m "pbx-ui neubau" || true
python3 Archiv/backup_restore.py -save apps/abpe_crm/templates/abpe_crm/tabs/telefon_tab.html    -m "pbx-ui neubau" || true
python3 Archiv/backup_restore.py -save apps/abpe_crm/views.py                                     -m "pbx-ui telefon ctx" || true
python3 Archiv/backup_restore.py -save apps/abpe_crm/static/abpe_crm/i18n/de/crm.json             -m "pbx-ui i18n" || true

echo ">> telefon.html (Wirts-Template)..."
cat > apps/abpe_crm/templates/abpe_crm/telefon.html <<'TELEFON_HTML_EOF'
{% extends "abpe_crm/base.html" %}
{% load static %}
{% block title %}{{ page_title }}{% endblock %}

{% block module_css %}
<link href="{% static 'abpe_crm/css/mod-crm-pbx.css' %}" rel="stylesheet">
{% endblock %}

{% block module_js %}
<script>
window.CRM_SKIP_SEARCH = true;
window.PBX_CONFIG = {
    api_base:  '{{ pbx_api_base|default:"/crm/api" }}',
    extension: '{{ pbx_extension|default:"12" }}',
};
</script>
<script src="{% static 'abpe_crm/js/mod-crm-pbx.js' %}"></script>
{% endblock %}

{% block content %}
{% include "abpe_crm/tabs/telefon_tab.html" %}
{% endblock %}
TELEFON_HTML_EOF

echo ">> tabs/telefon_tab.html (reines HTML)..."
cat > apps/abpe_crm/templates/abpe_crm/tabs/telefon_tab.html <<'TAB_HTML_EOF'
{% load static %}
<div id="pbx-root" class="crm-full-panel" style="margin-bottom:12px">
  <div class="section-header" style="display:flex;align-items:center;gap:8px;padding:10px 14px;background:var(--abcona-blue);color:#fff">
    <i class="bi bi-telephone-fill"></i>
    <span style="font-size:13px;font-weight:600" data-i18n="pbx_title">Telefonanlage</span>
    <span id="pbx-call-count" class="pbx-count">—</span>
  </div>

  <!-- Reiter -->
  <div class="pbx-tabbar">
    <button class="pbx-tabbtn pbx-tab-active" data-tab="hud"><i class="bi bi-grid-3x3-gap-fill"></i> <span data-i18n="pbx_tab_hud">HUD</span></button>
    <button class="pbx-tabbtn" data-tab="park"><i class="bi bi-p-square-fill"></i> <span data-i18n="pbx_tab_park">Parken</span></button>
    <button class="pbx-tabbtn" data-tab="konf"><i class="bi bi-collection-fill"></i> <span data-i18n="pbx_tab_konf">Konferenz</span></button>
    <button class="pbx-tabbtn" data-tab="queue"><i class="bi bi-people-fill"></i> <span data-i18n="pbx_tab_queue">Queues</span></button>
    <button class="pbx-tabbtn" data-tab="cdr"><i class="bi bi-list-ul"></i> <span data-i18n="pbx_tab_cdr">Anrufliste</span></button>
    <button class="pbx-tabbtn" data-tab="stats"><i class="bi bi-bar-chart-fill"></i> <span data-i18n="pbx_tab_stats">Statistik</span></button>
    <button class="pbx-tabbtn" data-tab="vm"><i class="bi bi-voicemail"></i> <span data-i18n="pbx_tab_vm">Voicemail</span></button>
  </div>

  <!-- HUD -->
  <div id="pbx-panel-hud" class="pbx-panel">
    <div class="pbx-secttl"><i class="bi bi-telephone-outbound"></i> <span data-i18n="pbx_dial_head">Wählen · Click-to-Dial</span></div>
    <div class="pbx-dialbar">
      <label class="pbx-lbl" data-i18n="pbx_from">Von</label>
      <select id="pbx-dial-ext" class="pbx-select"></select>
      <div class="pbx-dial-wrap">
        <input id="pbx-dial-input" class="pbx-input" type="text" autocomplete="off" data-i18n-placeholder="pbx_dial_ph" placeholder="Kontakt suchen oder Nummer…">
        <div id="pbx-dial-results" class="pbx-dial-results"></div>
      </div>
      <button class="pbx-act pbx-act-green" onclick="PBX.dialGo()"><i class="bi bi-telephone-outbound"></i> <span data-i18n="pbx_dial">Anrufen</span></button>
    </div>

    <div class="pbx-secttl"><i class="bi bi-broadcast"></i> <span data-i18n="pbx_active_head">Aktive Gespräche</span></div>
    <div id="pbx-callstrip" class="pbx-callstrip"></div>

    <div class="pbx-secttl"><i class="bi bi-grid"></i> <span data-i18n="pbx_ext_head">Nebenstellen</span></div>
    <div id="pbx-extgrid" class="pbx-grid pbx-grid-ext"></div>
  </div>

  <!-- Parken -->
  <div id="pbx-panel-park" class="pbx-panel" style="display:none">
    <div class="pbx-secttl"><i class="bi bi-p-square"></i> <span data-i18n="pbx_park_head">Parkplätze</span></div>
    <div id="pbx-parkgrid" class="pbx-grid pbx-grid-park"></div>
  </div>

  <!-- Konferenz -->
  <div id="pbx-panel-konf" class="pbx-panel" style="display:none">
    <div class="pbx-hint" data-i18n="pbx_konf_hint">Live-Konferenz-Cockpit. MeetMe-Planung (Termine, Gäste, Einladung) folgt.</div>
    <div id="pbx-confwrap"></div>
  </div>

  <!-- Queues -->
  <div id="pbx-panel-queue" class="pbx-panel" style="display:none">
    <div class="pbx-secttl"><i class="bi bi-people"></i> <span data-i18n="pbx_queue_head">Warteschlangen</span></div>
    <div id="pbx-queuegrid" class="pbx-grid pbx-grid-queue"></div>
  </div>

  <!-- Anrufliste -->
  <div id="pbx-panel-cdr" class="pbx-panel" style="display:none">
    <div class="pbx-tablewrap">
      <table class="pbx-cdr">
        <thead>
          <tr>
            <th data-i18n="pbx_col_time">Zeit</th>
            <th data-i18n="pbx_col_dir">Richtung</th>
            <th data-i18n="pbx_col_number">Nummer</th>
            <th data-i18n="pbx_col_contact">Kontakt</th>
            <th data-i18n="pbx_col_status">Status</th>
            <th data-i18n="pbx_col_dur">Dauer</th>
          </tr>
        </thead>
        <tbody id="pbx-cdr-tbody">
          <tr><td colspan="6" class="pbx-empty" data-i18n="pbx_loading">Lade…</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- Statistik -->
  <div id="pbx-panel-stats" class="pbx-panel" style="display:none">
    <div id="pbx-stats" class="pbx-statgrid"></div>
  </div>

  <!-- Voicemail -->
  <div id="pbx-panel-vm" class="pbx-panel" style="display:none">
    <div class="pbx-secttl"><i class="bi bi-voicemail"></i> <span data-i18n="pbx_vm_head">Mailboxen</span></div>
    <div id="pbx-vmgrid" class="pbx-grid pbx-grid-vm"></div>
  </div>
</div>
TAB_HTML_EOF

echo ">> css/mod-crm-pbx.css..."
cat > apps/abpe_crm/static/abpe_crm/css/mod-crm-pbx.css <<'PBX_CSS_EOF'
/* ============================================================
   mod-crm-pbx.css — Telefon-Cockpit (HUD/Parken/Konferenz/...)
   Nutzt ausschliesslich die Variablen aus core-theme.css.
   Status-Kacheln: VOLLER 4-seitiger Rahmen in Statusfarbe.
   ============================================================ */

/* Kopf-Zaehler */
.pbx-count { background: rgba(255,255,255,.2); font-size: 11px; padding: 1px 8px; border-radius: 20px; margin-left: 4px; }

/* Reiter */
.pbx-tabbar { display: flex; gap: 4px; padding: 8px 12px; flex-wrap: wrap; border-bottom: 1px solid var(--border-color); background: var(--abcona-gray-card); }
.pbx-tabbtn { padding: 6px 12px; border: 1px solid var(--border-color); border-radius: 7px; font-size: 12px; cursor: pointer; background: var(--bg-white); color: var(--text-primary); display: inline-flex; align-items: center; gap: 5px; white-space: nowrap; }
.pbx-tabbtn:hover { border-color: var(--abcona-blue); }
.pbx-tab-active { background: var(--abcona-blue); color: #fff; border-color: var(--abcona-blue); }

/* Panels */
.pbx-panel { padding: 14px; }
.pbx-secttl { font-size: 12px; font-weight: 600; color: var(--abcona-blue); margin: 4px 0 10px; display: flex; align-items: center; gap: 6px; }
.pbx-hint { font-size: 11px; color: var(--text-muted); margin-bottom: 12px; }
.pbx-empty { padding: 20px; text-align: center; color: var(--text-muted); font-size: 12px; }

/* Click-to-Dial */
.pbx-dialbar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 14px; }
.pbx-lbl { font-size: 12px; color: var(--text-muted); }
.pbx-select, .pbx-input { padding: 6px 9px; border: 1px solid var(--border-color); border-radius: 7px; font-size: 12px; background: var(--bg-white); color: var(--text-primary); }
.pbx-dial-wrap { position: relative; flex: 1; min-width: 240px; }
.pbx-dial-wrap .pbx-input { width: 100%; box-sizing: border-box; }
.pbx-dial-results { display: none; position: absolute; top: calc(100% + 2px); left: 0; right: 0; background: var(--bg-white); border: 1px solid var(--border-color); border-radius: 8px; z-index: 30; max-height: 220px; overflow: auto; box-shadow: 0 6px 20px rgba(0,0,0,.12); }
.pbx-dial-hit { padding: 8px 11px; cursor: pointer; border-bottom: 1px solid var(--border-color); font-size: 12px; }
.pbx-dial-hit:hover { background: var(--abcona-gray-bg); }
.pbx-dial-hit b { color: var(--text-primary); }
.pbx-dial-hit span { color: var(--text-muted); }

/* Aktive Gespraeche */
.pbx-callstrip { display: flex; flex-direction: column; gap: 8px; margin-bottom: 14px; }
.pbx-call { display: flex; align-items: center; gap: 10px; padding: 8px 12px; border: 1px solid var(--border-color); border-radius: 10px; background: var(--abcona-gray-card); }
.pbx-call-info { flex: 1; min-width: 0; }
.pbx-call-who { font-size: 13px; font-weight: 600; color: var(--text-primary); }
.pbx-call-meta { font-size: 11px; color: var(--text-muted); font-variant-numeric: tabular-nums; }

/* Grids */
.pbx-grid { display: grid; gap: 10px; }
.pbx-grid-ext   { grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); }
.pbx-grid-park  { grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); }
.pbx-grid-queue { grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); }
.pbx-grid-vm    { grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); }

/* Status-Punkte */
.pbx-dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; flex: none; background: var(--text-muted); }
.pbx-dot-free    { background: var(--status-green); }
.pbx-dot-busy    { background: var(--status-red); }
.pbx-dot-ringing { background: var(--status-yellow); }
.pbx-dot-away, .pbx-dot-offline { background: var(--text-muted); }

/* Status-Kacheln: VOLLER Rahmen in Statusfarbe */
.pbx-extcard, .pbx-parkcard, .pbx-queuecard, .pbx-vmcard {
    border: 1.5px solid var(--border-color); border-radius: var(--border-radius-card, 12px);
    padding: 10px 12px; background: var(--bg-white);
}
.pbx-st-free    { border-color: var(--status-green); }
.pbx-st-busy    { border-color: var(--status-red); }
.pbx-st-ringing { border-color: var(--status-yellow); }
.pbx-st-warn    { border-color: var(--status-yellow); }
.pbx-st-away    { border-color: var(--border-color); }

/* Nebenstellen-Kachel */
.pbx-ext-top { display: flex; align-items: center; gap: 6px; }
.pbx-ext-nr { font-weight: 600; font-size: 14px; color: var(--text-primary); }
.pbx-ext-proto { font-size: 9px; color: var(--text-muted); text-transform: uppercase; margin-left: auto; }
.pbx-ext-name { font-size: 11px; color: var(--text-secondary); margin: 3px 0 8px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pbx-ext-actions { display: flex; gap: 5px; }

/* Aktionen */
.pbx-act { border: none; border-radius: 7px; padding: 5px 9px; font-size: 12px; cursor: pointer; display: inline-flex; align-items: center; gap: 5px; font-weight: 500; color: #fff; }
.pbx-act:hover { filter: brightness(1.08); }
.pbx-act-green { background: var(--status-green); }
.pbx-act-red   { background: var(--status-red); }
.pbx-act-blue  { background: var(--abcona-blue-light); }
.pbx-act-warn  { background: var(--status-yellow); }
.pbx-act-gray  { background: var(--abcona-gray-bg); color: var(--text-primary); border: 1px solid var(--border-color); }

/* Parken */
.pbx-park-slot { font-size: 20px; font-weight: 700; color: var(--abcona-blue); }
.pbx-park-who { font-size: 12px; color: var(--text-primary); margin: 2px 0; }
.pbx-park-meta { font-size: 11px; color: var(--text-muted); margin-bottom: 8px; font-variant-numeric: tabular-nums; }
.pbx-urgent { color: var(--status-red); font-weight: 600; }

/* Konferenz-Cockpit */
.pbx-conf-bar { margin-bottom: 12px; }
.pbx-confroom { border: 1.5px solid var(--abcona-blue-light); border-radius: var(--border-radius-card, 12px); padding: 12px; margin-bottom: 12px; background: var(--bg-white); }
.pbx-conf-head { display: flex; align-items: center; gap: 8px; font-weight: 600; font-size: 13px; color: var(--text-primary); margin-bottom: 8px; }
.pbx-conf-head .pbx-tgl { margin-left: auto; }
.pbx-cmembers { display: flex; flex-direction: column; gap: 5px; }
.pbx-cmember { display: flex; align-items: center; gap: 8px; padding: 5px 8px; border-radius: 7px; background: var(--abcona-gray-bg); }
.pbx-talking { background: var(--status-green-bg); }
.pbx-talkdot { width: 8px; height: 8px; border-radius: 50%; background: var(--text-muted); flex: none; }
.pbx-talkdot.on { background: var(--status-green); }
.pbx-cnm { flex: 1; font-size: 12px; color: var(--text-primary); }
.pbx-badge { font-size: 10px; padding: 1px 8px; border-radius: 20px; background: var(--abcona-gray-bg); color: var(--text-muted); border: 1px solid var(--border-color); white-space: nowrap; }
.pbx-badge.pbx-ok { background: var(--status-green-bg); color: var(--status-green-text); }
.pbx-badge.pbx-miss { background: var(--status-red-bg); color: var(--status-red-text); }
.pbx-tgl { font-size: 11px; padding: 4px 9px; border-radius: 7px; border: 1px solid var(--border-color); cursor: pointer; background: var(--bg-white); color: var(--text-secondary); display: inline-flex; align-items: center; gap: 4px; }
.pbx-tgl.on { background: var(--status-yellow); color: #fff; border-color: var(--status-yellow); }

/* Queues */
.pbx-queue-top { display: flex; align-items: center; gap: 6px; }
.pbx-queue-top b { color: var(--text-primary); }
.pbx-queue-top .pbx-badge { margin-left: auto; }
.pbx-queue-wait { font-size: 12px; color: var(--text-secondary); margin-top: 6px; }

/* Voicemail */
.pbx-vm-top { display: flex; align-items: baseline; gap: 6px; }
.pbx-vm-top b { color: var(--text-primary); }
.pbx-vm-top span { font-size: 11px; color: var(--text-muted); }
.pbx-vm-count { font-size: 12px; color: var(--text-secondary); margin: 4px 0; }
.pbx-vm-new { color: var(--status-yellow); font-weight: 700; }
.pbx-vm-bar { height: 6px; border-radius: 4px; background: var(--abcona-gray-bg); overflow: hidden; }
.pbx-vm-bar > div { height: 100%; background: var(--abcona-blue-light); }
.pbx-vm-meta { font-size: 10px; color: var(--text-muted); margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* Anrufliste */
.pbx-tablewrap { overflow-x: auto; }
.pbx-cdr { width: 100%; border-collapse: collapse; font-size: 12px; }
.pbx-cdr th { text-align: left; padding: 7px 10px; border-bottom: 2px solid var(--border-color); color: var(--text-secondary); white-space: nowrap; }
.pbx-cdr td { padding: 6px 10px; border-bottom: 1px solid var(--border-color); color: var(--text-primary); }

/* Statistik */
.pbx-statgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }
.pbx-statcard { border: 1px solid var(--border-color); border-radius: var(--border-radius-card, 12px); padding: 12px; background: var(--abcona-gray-card); }
.pbx-statcard h4 { margin: 0 0 8px; font-size: 12px; color: var(--text-muted); font-weight: 600; }
.pbx-statrow { display: flex; justify-content: space-between; font-size: 12px; padding: 2px 0; color: var(--text-primary); }

/* Toast */
.pbx-toast { position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%); background: var(--abcona-blue); color: #fff; padding: 9px 18px; border-radius: 8px; font-size: 13px; opacity: 0; transition: opacity .2s; pointer-events: none; z-index: 9999; }
.pbx-toast.show { opacity: 1; }
PBX_CSS_EOF

echo ">> js/mod-crm-pbx.js..."
cat > apps/abpe_crm/static/abpe_crm/js/mod-crm-pbx.js <<'PBX_JS_EOF'
/* ============================================================
   ABpE CRM — mod-crm-pbx.js
   Telefon-Cockpit (HUD, Parken, Konferenz, Queues, Anrufliste,
   Statistik, Voicemail) — spricht die /crm/api/telefon/* Endpoints.
   Muster wie mod-edms.js: Namespace-Objekt + t()/csrf().
   Alle sichtbaren Texte via PBX.t('pbx_*') -> window.i18nData.
   ============================================================ */

const PBX = {
    cfg:  {},
    tab:  'hud',
    ext:  '',
    data: { extensions: [], channels: [], parked: [], confbridge: [], queues: [], voicemail: [] },
    _pollTimer: null,
    _tickTimer: null,
    _call: null,          // aktiver 1:1-Ruf (Kunde-Koenig): {name, nr}

    api: {
        hud:        '/crm/api/telefon/hud/',
        dial:       '/crm/api/telefon/dial/',
        call:       '/crm/api/telefon/call/',
        hangup:     '/crm/api/telefon/hangup/',
        redirect:   '/crm/api/telefon/redirect/',
        park:       '/crm/api/telefon/park/',
        record:     '/crm/api/telefon/record/',
        dnd:        '/crm/api/telefon/dnd/',
        fwd:        '/crm/api/telefon/fwd/',
        fwdSet:     '/crm/api/telefon/fwd/set/',
        confDetail: '/crm/api/conf/detail/',
        confMember: '/crm/api/conf/member/',
        confLock:   '/crm/api/conf/lock/',
        confInvite: '/crm/api/conf/invite/',
        conference: '/crm/api/telefon/conference/',
        pullPartner:'/crm/api/conf/pull-partner/',
        joinSelf:   '/crm/api/conf/join-self/',
        queues:     '/crm/api/telefon/queues/',
        queueMember:'/crm/api/telefon/queue-member/',
        voicemail:  '/crm/api/telefon/voicemail/',
        vmboxes:    '/crm/api/telefon/vmboxes/',
        stats:      '/crm/api/telefon/stats/',
        cdr:        '/crm/api/telefon/cdr/',
        contacts:   '/crm/api/softphone/contacts/',
        protokoll:  '/crm/api/telefon/protokoll/',
        notiz:      '/crm/api/telefon/notiz/',
    },

    /* ---- Helfer ---- */
    t(key, fb) { return (window.i18nData && window.i18nData[key]) || fb || key; },
    csrf() { return (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || ''; },
    esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); },
    fmtDur(sec) { sec = parseInt(sec || 0, 10); const m = Math.floor(sec / 60), s = sec % 60; return m + ':' + String(s).padStart(2, '0'); },
    $(id) { return document.getElementById(id); },

    async get(url) {
        const r = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
        return r.json();
    },
    async post(url, body) {
        const r = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrf(), 'X-Requested-With': 'XMLHttpRequest' },
            body: JSON.stringify(body || {}),
        });
        return r.json();
    },

    toast(msg) {
        let t = this.$('pbx-toast');
        if (!t) { t = document.createElement('div'); t.id = 'pbx-toast'; t.className = 'pbx-toast'; document.body.appendChild(t); }
        t.innerHTML = msg;
        t.classList.add('show');
        clearTimeout(this._toastT);
        this._toastT = setTimeout(() => t.classList.remove('show'), 2200);
    },

    /* ---- Init ---- */
    init() {
        this.cfg = window.PBX_CONFIG || {};
        this.ext = this.cfg.extension || '12';
        this.bindTabs();
        this.bindDial();
        const de = this.$('pbx-dial-ext'); if (de) de.value = this.ext;
        this.poll();                          // sofort
        this._pollTimer = setInterval(() => this.poll(), 4000);
        this._tickTimer = setInterval(() => this.tick(), 1000);
        if (window.applyTranslations) window.applyTranslations();
    },

    bindTabs() {
        document.querySelectorAll('#pbx-root .pbx-tabbtn').forEach(btn => {
            btn.addEventListener('click', () => this.showTab(btn.getAttribute('data-tab'), btn));
        });
    },

    showTab(tab, btn) {
        this.tab = tab;
        document.querySelectorAll('#pbx-root .pbx-tabbtn').forEach(b => b.classList.remove('pbx-tab-active'));
        if (btn) btn.classList.add('pbx-tab-active');
        document.querySelectorAll('#pbx-root .pbx-panel').forEach(p => p.style.display = 'none');
        const panel = this.$('pbx-panel-' + tab);
        if (panel) panel.style.display = '';
        if (tab === 'cdr') this.loadCdr();
        if (tab === 'stats') this.loadStats();
        if (tab === 'vm') this.loadVm();
    },

    /* ---- Polling ---- */
    async poll() {
        try {
            const res = await this.get(this.api.hud);
            if (res && res.success) {
                this.data = res.data;
                this.renderHud();
                this.renderPark();
                this.renderKonf();
                this.renderQueues();
                this.updateCount();
            }
        } catch (e) { /* still */ }
    },

    updateCount() {
        const busy = (this.data.channels || []).length;
        const el = this.$('pbx-call-count');
        if (el) el.textContent = busy + ' ' + this.t('pbx_active_calls', 'aktiv');
    },

    tick() {
        // laufende Dauer-Anzeigen hochzaehlen (Kacheln, Park-Countdown)
        document.querySelectorAll('#pbx-root [data-tick]').forEach(el => {
            let v = parseInt(el.getAttribute('data-tick') || '0', 10) + 1;
            el.setAttribute('data-tick', v);
            el.textContent = this.fmtDur(v);
        });
        document.querySelectorAll('#pbx-root [data-countdown]').forEach(el => {
            let v = parseInt(el.getAttribute('data-countdown') || '0', 10) - 1;
            if (v < 0) v = 0;
            el.setAttribute('data-countdown', v);
            el.textContent = this.fmtDur(v);
            if (v <= 10) el.classList.add('pbx-urgent');
        });
    },

    /* ======================= HUD ======================= */
    renderHud() {
        // Aktive Gespraeche
        const strip = this.$('pbx-callstrip');
        if (strip) {
            const chans = this.data.channels || [];
            if (!chans.length) {
                strip.innerHTML = '<div class="pbx-empty" data-i18n="pbx_no_calls">' + this.t('pbx_no_calls', 'Keine aktiven Gespräche') + '</div>';
            } else {
                strip.innerHTML = chans.map(c => this._callCard(c)).join('');
            }
        }
        // Nebenstellen-Grid
        const grid = this.$('pbx-extgrid');
        if (grid) {
            const exts = this.data.extensions || [];
            grid.innerHTML = exts.map(e => this._extCard(e)).join('') ||
                '<div class="pbx-empty" data-i18n="pbx_no_ext">' + this.t('pbx_no_ext', 'Keine Nebenstellen') + '</div>';
        }
    },

    _callCard(c) {
        const who = this.esc(c.calleridname || c.callerid || c.connectednum || c.extension);
        const partner = c.bridge_channel ? this.esc(c.connectedname || c.connectednum || '') : '';
        const dur = parseInt((c.duration || '0:0:0').split(':').reduce((a, b) => a * 60 + (+b), 0)) || 0;
        return `<div class="pbx-call">
            <span class="pbx-dot pbx-dot-busy"></span>
            <div class="pbx-call-info">
                <div class="pbx-call-who">${who}${partner ? ' → ' + partner : ''}</div>
                <div class="pbx-call-meta"><span data-tick="${dur}">${this.fmtDur(dur)}</span> · ${this.esc(c.channel)}</div>
            </div>
            <button class="pbx-act pbx-act-warn" title="${this.t('pbx_park', 'Parken')}" onclick="PBX.doPark('${this.esc(c.extension)}')"><i class="bi bi-p-square"></i></button>
            <button class="pbx-act pbx-act-blue" title="${this.t('pbx_to_conf', 'In Konferenz legen')}" onclick="PBX.pullToConf('${this.esc(c.extension)}')"><i class="bi bi-collection"></i></button>
            <button class="pbx-act pbx-act-gray" title="${this.t('pbx_record', 'Aufnahme')}" onclick="PBX.doRecord('${this.esc(c.channel)}')"><i class="bi bi-record-circle"></i></button>
            <button class="pbx-act pbx-act-red" title="${this.t('pbx_hangup', 'Auflegen')}" onclick="PBX.doHangup('${this.esc(c.channel)}')"><i class="bi bi-telephone-x"></i></button>
        </div>`;
    },

    _extCard(e) {
        const st = e.status || 'away';
        return `<div class="pbx-extcard pbx-st-${st}">
            <div class="pbx-ext-top">
                <span class="pbx-dot pbx-dot-${st}"></span>
                <span class="pbx-ext-nr">${this.esc(e.ext)}</span>
                <span class="pbx-ext-proto">${this.esc(e.proto)}</span>
            </div>
            <div class="pbx-ext-name">${this.esc(e.name)}</div>
            <div class="pbx-ext-actions">
                <button class="pbx-act pbx-act-green" title="${this.t('pbx_dial', 'Anrufen')}" onclick="PBX.dialExt('${this.esc(e.ext)}')"><i class="bi bi-telephone"></i></button>
                <button class="pbx-act pbx-act-gray" title="${this.t('pbx_dnd', 'DND')}" onclick="PBX.toggleDnd('${this.esc(e.ext)}')"><i class="bi bi-bell-slash"></i></button>
                <button class="pbx-act pbx-act-gray" title="${this.t('pbx_fwd', 'Umleitung')}" onclick="PBX.promptFwd('${this.esc(e.ext)}')"><i class="bi bi-arrow-return-right"></i></button>
            </div>
        </div>`;
    },

    /* ---- Click-to-Dial (HUD-Kopf) ---- */
    bindDial() {
        const inp = this.$('pbx-dial-input');
        if (inp) {
            inp.addEventListener('input', () => this.dialSearch(inp.value));
            inp.addEventListener('keydown', e => { if (e.key === 'Enter') this.dialGo(); });
        }
        document.addEventListener('click', e => {
            if (!e.target.closest('#pbx-dial-input') && !e.target.closest('#pbx-dial-results')) {
                const r = this.$('pbx-dial-results'); if (r) r.style.display = 'none';
            }
        });
    },

    async dialSearch(q) {
        const box = this.$('pbx-dial-results');
        if (!box) return;
        q = (q || '').trim();
        this._dialNr = '';
        if (q.length < 2) { box.style.display = 'none'; return; }
        try {
            const res = await this.get(this.api.contacts + '?q=' + encodeURIComponent(q));
            const list = (res.contacts || res.results || []).slice(0, 8);
            box.innerHTML = list.length ? list.map(c => {
                const nr = c.phone || c.number || c.phone_norm || '';
                const nm = this.esc(c.name || c.full_name || nr);
                return `<div class="pbx-dial-hit" onclick="PBX.dialPick('${this.esc(nr)}','${nm.replace(/'/g, '')}')"><b>${nm}</b> <span>${this.esc(nr)}</span></div>`;
            }).join('') : `<div class="pbx-dial-hit pbx-empty">${this.t('pbx_no_hits', 'keine Treffer — Enter wählt die Eingabe')}</div>`;
            box.style.display = 'block';
        } catch (e) { box.style.display = 'none'; }
    },

    dialPick(nr, name) {
        const inp = this.$('pbx-dial-input');
        inp.value = name + ' · ' + nr;
        this._dialNr = nr;
        this.$('pbx-dial-results').style.display = 'none';
    },

    async dialGo() {
        const inp = this.$('pbx-dial-input');
        const nr = this._dialNr || (inp ? inp.value.trim() : '');
        const desk = (this.$('pbx-dial-ext') || {}).value || this.ext;
        if (!nr) { this.toast(this.t('pbx_enter_number', 'Nummer oder Kontakt eingeben')); return; }
        const r = this.$('pbx-dial-results'); if (r) r.style.display = 'none';
        const res = await this.post(this.api.dial, { desk, target: nr });
        this.toast(res.success
            ? '<i class="bi bi-telephone-outbound"></i> ' + this.t('pbx_ringing', 'Tischtelefon klingelt') + ' → ' + this.esc(nr)
            : (res.error || this.t('pbx_dial_failed', 'Anruf fehlgeschlagen')));
    },

    async dialExt(target) {
        const desk = (this.$('pbx-dial-ext') || {}).value || this.ext;
        const res = await this.post(this.api.dial, { desk, target });
        this.toast(res.success ? this.t('pbx_ringing', 'Tischtelefon klingelt') + ' → ' + target : (res.error || 'Fehler'));
    },

    /* ---- Anruf-Aktionen ---- */
    async doHangup(channel) {
        const res = await this.post(this.api.hangup, { channel });
        this.toast(res.success ? this.t('pbx_hung_up', 'Aufgelegt') : (res.error || 'Fehler'));
        this.poll();
    },
    async doPark(extension) {
        const res = await this.post(this.api.park, { extension });
        this.toast(res.success ? this.t('pbx_parked', 'Geparkt') : (res.error || 'Fehler'));
        this.poll();
    },
    async doRecord(channel) {
        const res = await this.post(this.api.record, { channel, action: 'start' });
        this.toast(res.success ? this.t('pbx_recording', 'Aufnahme läuft') : (res.error || 'Fehler'));
    },
    async pullToConf(extension) {
        const res = await this.post(this.api.pullPartner, { extension, room: '5555' });
        this.toast(res.success
            ? '<i class="bi bi-box-arrow-in-right"></i> ' + this.t('pbx_in_conf', 'In Konferenz 5555 gelegt')
            : (res.error || this.t('pbx_no_partner', 'Kein Gesprächspartner')));
        this.poll();
    },
    async toggleDnd(extension) {
        const res = await this.post(this.api.dnd, { extension, active: true });
        this.toast(res.success ? 'DND ' + extension : (res.error || 'Fehler'));
    },
    async promptFwd(extension) {
        const cur = await this.get(this.api.fwd + '?extension=' + encodeURIComponent(extension));
        const target = window.prompt(this.t('pbx_fwd_prompt', 'Umleitungsziel (leer = aus):'), cur.target || '');
        if (target === null) return;
        const res = await this.post(this.api.fwdSet, { extension, target: target.trim() });
        this.toast(res.success ? (target.trim() ? this.t('pbx_fwd_set', 'Umleitung aktiv') : this.t('pbx_fwd_off', 'Umleitung aus')) : (res.error || 'Fehler'));
    },

    /* ======================= PARKEN ======================= */
    renderPark() {
        const grid = this.$('pbx-parkgrid');
        if (!grid) return;
        const p = this.data.parked || [];
        grid.innerHTML = p.length ? p.map(x => this._parkCard(x)).join('')
            : '<div class="pbx-empty">' + this.t('pbx_no_parked', 'Keine geparkten Anrufe') + '</div>';
    },
    _parkCard(x) {
        const rem = parseInt(x.timeout || 0, 10);
        return `<div class="pbx-parkcard pbx-st-busy">
            <div class="pbx-park-slot">${this.esc(x.slot)}</div>
            <div class="pbx-park-who">${this.esc(x.caller_name || x.caller_id)}</div>
            <div class="pbx-park-meta">${this.t('pbx_timeout', 'Timeout')}: <span data-countdown="${rem}">${this.fmtDur(rem)}</span></div>
            <button class="pbx-act pbx-act-green" title="${this.t('pbx_pickup', 'Abholen')}" onclick="PBX.pickupPark('${this.esc(x.slot)}')"><i class="bi bi-telephone-inbound"></i> ${this.t('pbx_pickup', 'Abholen')}</button>
        </div>`;
    },
    async pickupPark(slot) {
        // Abholen = Originate vom eigenen Tischtelefon auf den Slot
        const res = await this.post(this.api.dial, { desk: this.ext, target: slot });
        this.toast(res.success ? this.t('pbx_pickup', 'Abholen') + ' ' + slot : (res.error || 'Fehler'));
        this.poll();
    },

    /* ======================= KONFERENZ ======================= */
    renderKonf() {
        const wrap = this.$('pbx-confwrap');
        if (!wrap) return;
        const rooms = this.data.confbridge || [];
        let html = `<div class="pbx-conf-bar">
            <button class="pbx-act pbx-act-blue" onclick="PBX.joinSelf('5555')"><i class="bi bi-headset"></i> ${this.t('pbx_join_self', 'Selbst beitreten')} (${this.esc(this.ext)})</button>
        </div>`;
        if (!rooms.length) {
            html += '<div class="pbx-empty">' + this.t('pbx_no_conf', 'Keine laufende Konferenz') + '</div>';
        } else {
            html += rooms.map(r => this._confRoom(r)).join('');
        }
        wrap.innerHTML = html;
    },
    _confRoom(r) {
        const members = (r.members || []).map(m => `
            <div class="pbx-cmember ${m.talking ? 'pbx-talking' : ''}">
                <span class="pbx-talkdot ${m.talking ? 'on' : ''}"></span>
                <span class="pbx-cnm">${this.esc(m.name || m.callerid)}</span>
                ${m.admin ? '<span class="pbx-badge">' + this.t('pbx_admin', 'Admin') + '</span>' : ''}
                <button class="pbx-act ${m.muted ? 'pbx-act-warn' : 'pbx-act-gray'}" title="${this.t('pbx_mute', 'Stumm')}" onclick="PBX.confMute('${this.esc(r.conference)}','${this.esc(m.channel)}',${m.muted})"><i class="bi ${m.muted ? 'bi-mic-mute' : 'bi-mic'}"></i></button>
                <button class="pbx-act pbx-act-red" title="${this.t('pbx_kick', 'Entfernen')}" onclick="PBX.confKick('${this.esc(r.conference)}','${this.esc(m.channel)}')"><i class="bi bi-person-x"></i></button>
            </div>`).join('');
        return `<div class="pbx-confroom">
            <div class="pbx-conf-head">
                <span><i class="bi bi-collection"></i> ${this.t('pbx_conf', 'Konferenz')} ${this.esc(r.conference)}</span>
                <span class="pbx-badge">${(r.members || []).length} ${this.t('pbx_participants', 'Teilnehmer')}</span>
                <button class="pbx-tgl ${r.locked ? 'on' : ''}" onclick="PBX.confLock('${this.esc(r.conference)}',${r.locked})"><i class="bi ${r.locked ? 'bi-lock-fill' : 'bi-lock'}"></i> ${r.locked ? this.t('pbx_locked', 'Gesperrt') : this.t('pbx_lock', 'Sperren')}</button>
            </div>
            <div class="pbx-cmembers">${members}</div>
        </div>`;
    },
    async confMute(room, channel, isMuted) {
        const res = await this.post(this.api.confMember, { room, channel, action: isMuted ? 'unmute' : 'mute' });
        this.toast(res.success ? (isMuted ? this.t('pbx_unmuted', 'Laut') : this.t('pbx_muted', 'Stumm')) : (res.error || 'Fehler'));
        this.poll();
    },
    async confKick(room, channel) {
        const res = await this.post(this.api.confMember, { room, channel, action: 'kick' });
        this.toast(res.success ? this.t('pbx_kicked', 'Entfernt') : (res.error || 'Fehler'));
        this.poll();
    },
    async confLock(room, isLocked) {
        const res = await this.post(this.api.confLock, { room, action: isLocked ? 'unlock' : 'lock' });
        this.toast(res.success ? (isLocked ? this.t('pbx_unlocked', 'Entsperrt') : this.t('pbx_locked', 'Gesperrt')) : (res.error || 'Fehler'));
        this.poll();
    },
    async joinSelf(room) {
        const res = await this.post(this.api.joinSelf, { desk: this.ext, room });
        this.toast(res.success ? this.t('pbx_joining', 'Trete Konferenz bei') + ' ' + room : (res.error || 'Fehler'));
    },

    /* ======================= QUEUES ======================= */
    renderQueues() {
        const grid = this.$('pbx-queuegrid');
        if (!grid) return;
        const q = this.data.queues || [];
        grid.innerHTML = q.length ? q.map(x => this._queueCard(x)).join('')
            : '<div class="pbx-empty">' + this.t('pbx_no_queues', 'Keine Warteschlangen') + '</div>';
    },
    _queueCard(x) {
        const waiting = (x.callers || []).length;
        const mem = (x.members || []).length;
        return `<div class="pbx-queuecard ${waiting ? 'pbx-st-busy' : 'pbx-st-free'}">
            <div class="pbx-queue-top"><b>${this.esc(x.name)}</b><span class="pbx-badge">${mem} ${this.t('pbx_agents', 'Agenten')}</span></div>
            <div class="pbx-queue-wait">${waiting} ${this.t('pbx_waiting', 'wartend')}</div>
        </div>`;
    },

    /* ======================= VOICEMAIL ======================= */
    async loadVm() {
        const grid = this.$('pbx-vmgrid');
        if (!grid) return;
        grid.innerHTML = '<div class="pbx-empty">' + this.t('pbx_loading', 'Lade…') + '</div>';
        try {
            const res = await this.get(this.api.vmboxes);
            const v = res.boxes || [];
            grid.innerHTML = v.length ? v.map(b => this._vmCard(b)).join('')
                : '<div class="pbx-empty">' + this.t('pbx_no_vm', 'Keine Mailboxen') + '</div>';
        } catch (e) {
            grid.innerHTML = '<div class="pbx-empty">' + this.t('pbx_load_error', 'Fehler beim Laden') + '</div>';
        }
    },
    _vmCard(b) {
        const pct = b.max ? Math.min(100, Math.round((b.new + b.old) / b.max * 100)) : 0;
        return `<div class="pbx-vmcard ${b.new ? 'pbx-st-warn' : 'pbx-st-free'}">
            <div class="pbx-vm-top"><b>${this.esc(b.box)}</b> <span>${this.esc(b.user)}</span></div>
            <div class="pbx-vm-count"><span class="pbx-vm-new">${b.new}</span> ${this.t('pbx_new', 'neu')} · ${b.old} ${this.t('pbx_old', 'alt')}</div>
            <div class="pbx-vm-bar"><div style="width:${pct}%"></div></div>
            <div class="pbx-vm-meta">${b.new + b.old}/${b.max} · ${this.esc(b.email || '')}</div>
        </div>`;
    },

    /* ======================= ANRUFLISTE (CDR) ======================= */
    async loadCdr() {
        const body = this.$('pbx-cdr-tbody');
        if (!body) return;
        body.innerHTML = `<tr><td colspan="6" class="pbx-empty">${this.t('pbx_loading', 'Lade…')}</td></tr>`;
        try {
            const res = await this.get(this.api.cdr + '?extension=' + encodeURIComponent(this.ext) + '&mode=all&days=30&limit=100');
            const rows = res.rows || [];
            body.innerHTML = rows.length ? rows.map(r => this._cdrRow(r)).join('')
                : `<tr><td colspan="6" class="pbx-empty">${this.t('pbx_no_cdr', 'Keine Anrufe')}</td></tr>`;
        } catch (e) {
            body.innerHTML = `<tr><td colspan="6" class="pbx-empty">${this.t('pbx_load_error', 'Fehler beim Laden')}</td></tr>`;
        }
    },
    _cdrRow(r) {
        const dir = r.direction === 'outgoing'
            ? '<i class="bi bi-telephone-outbound" style="color:var(--abcona-blue)"></i>'
            : '<i class="bi bi-telephone-inbound" style="color:var(--status-green)"></i>';
        const nr = r.direction === 'incoming' ? r.src : r.dst;
        const contact = r.contact ? this.esc(r.contact.name) : '—';
        const ok = r.disposition === 'ANSWERED';
        return `<tr>
            <td>${this.esc((r.calldate || '').slice(0, 16))}</td>
            <td>${dir}</td>
            <td>${this.esc(nr)}</td>
            <td>${contact}</td>
            <td><span class="pbx-badge ${ok ? 'pbx-ok' : 'pbx-miss'}">${this.esc(r.disposition || '')}</span></td>
            <td>${this.esc(r.billsec_fmt || '')}</td>
        </tr>`;
    },

    /* ======================= STATISTIK ======================= */
    async loadStats() {
        const wrap = this.$('pbx-stats');
        if (!wrap) return;
        wrap.innerHTML = `<div class="pbx-empty">${this.t('pbx_loading', 'Lade…')}</div>`;
        try {
            const res = await this.get(this.api.stats + '?extension=' + encodeURIComponent(this.ext));
            const s = res.stats || {};
            const box = (title, o) => `<div class="pbx-statcard"><h4>${title}</h4>` +
                Object.entries(o || {}).map(([k, v]) => `<div class="pbx-statrow"><span>${this.esc(k)}</span><span>${this.esc(v)}</span></div>`).join('') + '</div>';
            wrap.innerHTML = box(this.t('pbx_today', 'Heute'), s.heute) + box(this.t('pbx_week', 'Woche'), s.woche) + box(this.t('pbx_month', 'Monat'), s.monat);
        } catch (e) {
            wrap.innerHTML = `<div class="pbx-empty">${this.t('pbx_load_error', 'Fehler beim Laden')}</div>`;
        }
    },
};

document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('pbx-root')) PBX.init();
});
PBX_JS_EOF

echo ">> i18n-Keys nach /tmp und mergen..."
cat > /tmp/pbx_i18n_de.json <<'PBX_I18N_EOF'
{
  "pbx_title": "Telefonanlage",
  "pbx_tab_hud": "HUD",
  "pbx_tab_park": "Parken",
  "pbx_tab_konf": "Konferenz",
  "pbx_tab_queue": "Queues",
  "pbx_tab_cdr": "Anrufliste",
  "pbx_tab_stats": "Statistik",
  "pbx_tab_vm": "Voicemail",
  "pbx_dial_head": "Wählen · Click-to-Dial",
  "pbx_from": "Von",
  "pbx_dial_ph": "Kontakt suchen oder Nummer…",
  "pbx_dial": "Anrufen",
  "pbx_active_head": "Aktive Gespräche",
  "pbx_ext_head": "Nebenstellen",
  "pbx_park_head": "Parkplätze",
  "pbx_konf_hint": "Live-Konferenz-Cockpit. MeetMe-Planung (Termine, Gäste, Einladung) folgt.",
  "pbx_queue_head": "Warteschlangen",
  "pbx_vm_head": "Mailboxen",
  "pbx_col_time": "Zeit",
  "pbx_col_dir": "Richtung",
  "pbx_col_number": "Nummer",
  "pbx_col_contact": "Kontakt",
  "pbx_col_status": "Status",
  "pbx_col_dur": "Dauer",
  "pbx_active_calls": "aktiv",
  "pbx_no_calls": "Keine aktiven Gespräche",
  "pbx_no_ext": "Keine Nebenstellen",
  "pbx_park": "Parken",
  "pbx_to_conf": "In Konferenz legen",
  "pbx_record": "Aufnahme",
  "pbx_hangup": "Auflegen",
  "pbx_dnd": "DND",
  "pbx_fwd": "Umleitung",
  "pbx_no_hits": "keine Treffer — Enter wählt die Eingabe",
  "pbx_enter_number": "Nummer oder Kontakt eingeben",
  "pbx_ringing": "Tischtelefon klingelt",
  "pbx_dial_failed": "Anruf fehlgeschlagen",
  "pbx_hung_up": "Aufgelegt",
  "pbx_parked": "Geparkt",
  "pbx_recording": "Aufnahme läuft",
  "pbx_in_conf": "In Konferenz 5555 gelegt",
  "pbx_no_partner": "Kein Gesprächspartner",
  "pbx_fwd_prompt": "Umleitungsziel (leer = aus):",
  "pbx_fwd_set": "Umleitung aktiv",
  "pbx_fwd_off": "Umleitung aus",
  "pbx_no_parked": "Keine geparkten Anrufe",
  "pbx_timeout": "Timeout",
  "pbx_pickup": "Abholen",
  "pbx_join_self": "Selbst beitreten",
  "pbx_no_conf": "Keine laufende Konferenz",
  "pbx_conf": "Konferenz",
  "pbx_participants": "Teilnehmer",
  "pbx_admin": "Admin",
  "pbx_mute": "Stumm",
  "pbx_kick": "Entfernen",
  "pbx_lock": "Sperren",
  "pbx_locked": "Gesperrt",
  "pbx_unlocked": "Entsperrt",
  "pbx_muted": "Stumm",
  "pbx_unmuted": "Laut",
  "pbx_kicked": "Entfernt",
  "pbx_joining": "Trete Konferenz bei",
  "pbx_no_queues": "Keine Warteschlangen",
  "pbx_agents": "Agenten",
  "pbx_waiting": "wartend",
  "pbx_no_vm": "Keine Mailboxen",
  "pbx_new": "neu",
  "pbx_old": "alt",
  "pbx_no_cdr": "Keine Anrufe",
  "pbx_loading": "Lade…",
  "pbx_load_error": "Fehler beim Laden",
  "pbx_today": "Heute",
  "pbx_week": "Woche",
  "pbx_month": "Monat"
}
PBX_I18N_EOF
python3 - <<'PYMERGE'
import json
base = 'apps/abpe_crm/static/abpe_crm/i18n/de/crm.json'
add  = json.load(open('/tmp/pbx_i18n_de.json'))
d    = json.load(open(base, encoding='utf-8'))
n = 0
for k, v in add.items():
    if k not in d:
        d[k] = v; n += 1
json.dump(d, open(base, 'w', encoding='utf-8'), ensure_ascii=False, indent=4)
print(f'   {n} pbx-Keys ergaenzt (gesamt {len(d)})')
PYMERGE

echo ">> View telefon() um pbx_extension erweitern..."
python3 - <<'PYPATCH'
p = 'apps/abpe_crm/views.py'
s = open(p, encoding='utf-8').read()
if 'pbx_extension' in s:
    print('   bereits gepatcht - skip')
else:
    OLD = "    ctx['tab'] = 'telefon'\n    return render(request, 'abpe_crm/telefon.html', ctx)"
    NEW = ("    ctx['tab'] = 'telefon'\n"
           "    from apps.abpe_crm.models import CrmUserSettings\n"
           "    _s = CrmUserSettings.objects.filter(user=request.user).first()\n"
           "    ctx['pbx_extension'] = (_s.phone_extension if _s and _s.phone_extension else '12')\n"
           "    ctx['pbx_api_base'] = '/crm/api'\n"
           "    return render(request, 'abpe_crm/telefon.html', ctx)")
    assert s.count(OLD) == 1, ('OLD nicht eindeutig', s.count(OLD))
    open(p, 'w', encoding='utf-8').write(s.replace(OLD, NEW))
    print('   telefon() gepatcht')
PYPATCH

echo ">> collectstatic + check + restart..."
python manage.py collectstatic --noinput >/dev/null
python manage.py check
supervisorctl restart abpe-django

echo ""
echo "============================================================"
echo " FERTIG. Browser: /crm/telefon/  (Strg+Shift+R fuer Hard-Reload)"
echo " Bei Problemen: python3 Archiv/backup_restore.py -restore <pfad>"
echo "============================================================"

