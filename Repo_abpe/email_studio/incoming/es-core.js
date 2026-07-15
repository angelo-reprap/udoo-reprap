/**
 * es-core.js — ABpE Email Studio
 * Toggle-System, API-Helper, CSRF, Notifications
 * Nutzt Portal-Logik aus core-init.js (toggleSection bereits global)
 * Ergänzt NUR was für Email Studio zusätzlich gebraucht wird
 */

'use strict';

/* ── Namespace ── */
window.ES = window.ES || {};

/* ── CSRF ── */
ES.csrf = () =>
    document.cookie.split(';')
        .map(c => c.trim())
        .find(c => c.startsWith('csrftoken='))
        ?.split('=')[1] || '';

/* ── API Helper ── */
ES.api = {
    get: async (url) => {
        const r = await fetch(url);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
    },
    post: async (url, data) => {
        const r = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': ES.csrf()
            },
            body: JSON.stringify(data)
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
    },
    put: async (url, data) => {
        const r = await fetch(url, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': ES.csrf()
            },
            body: JSON.stringify(data)
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
    },
    delete: async (url) => {
        const r = await fetch(url, {
            method: 'DELETE',
            headers: { 'X-CSRFToken': ES.csrf() }
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
    }
};

/* ── Toggle-Row (zeilenweise für 1/2/3-spaltige Bereiche) ── */
ES.toggleRow = function(hdr) {
    if (!hdr) return;
    hdr.classList.toggle('open');
    const body = hdr.nextElementSibling;
    if (body) body.classList.toggle('open');
};
window.esToggleRow = ES.toggleRow;

/* ── Toggle (Alias für Portal toggleSection) ── */
ES.toggle = function(hdr) {
    if (typeof window.toggleSection === 'function') {
        window.toggleSection(hdr);
    } else {
        ES.toggleRow(hdr);
    }
};
window.esToggle = ES.toggle;

/* ── i18n Key Resolver (es.confirm_key) ── */
ES._i18n = function(key) {
    const keys = key.split('.');
    let val = window.i18nData;
    for (const k of keys) {
        if (val && typeof val === 'object') val = val[k];
        else return null;
    }
    return typeof val === 'string' ? val : null;
};

/* ── Notifications (kein hardcoded Text — Keys aus i18n) ── */
ES.notify = {
    _show: function(msgKey, type, fallback) {
        const msg = ES._i18n(msgKey) || fallback || msgKey;
        const el = document.createElement('div');
        el.className = `es-notify es-notify-${type}`;
        el.innerHTML = msg;
        document.body.appendChild(el);
        setTimeout(() => el.remove(), 3500);
    },
    success: (key, fallback) => ES.notify._show(key, 'success', fallback),
    error:   (key, fallback) => ES.notify._show(key, 'error',   fallback),
    info:    (key, fallback) => ES.notify._show(key, 'info',    fallback),
    warning: (key, fallback) => ES.notify._show(key, 'warning', fallback),
};

/* ── Clipboard (Variablen kopieren) ── */
ES.copyToClipboard = function(text, chipEl) {
    navigator.clipboard.writeText(text).then(() => {
        if (chipEl) {
            const orig = chipEl.style.background;
            chipEl.style.background = '#10b981';
            chipEl.style.color = 'white';
            setTimeout(() => {
                chipEl.style.background = orig;
                chipEl.style.color = '';
            }, 600);
        }
        console.log('✓ Kopiert:', text);
    });
};
window.esCopy = ES.copyToClipboard;

/* ── Sender-Modus Button Toggle ── */
ES.setSenderMode = function(btn) {
    const wrap = btn.closest('.es-mode-btns');
    if (!wrap) return;
    wrap.querySelectorAll('.es-mode-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const mode = btn.dataset.mode;

    // Absender-Adresse Feld zeigen/verstecken
    const senderField = document.querySelector('[name="sender_account"]');
    if (senderField) {
        senderField.closest('div[name="sender_account"]')
            ?.classList.toggle('d-none', mode !== 'TEMPLATE');
    }

    // Hinweis-Text aktualisieren
    const hint = document.getElementById('es-mode-hint');
    if (hint) {
        const i18n = window.i18nData?.es || {};
        const texts = {
            'USER':     `<i class="bi bi-info-circle es-icon-green"></i> ${i18n.mode_hint_user || ''}`,
            'TEMPLATE': `<i class="bi bi-info-circle es-icon-blue"></i> ${i18n.mode_hint_template || ''}`,
            'AUTO':     `<i class="bi bi-info-circle es-icon-yellow"></i> ${i18n.mode_hint_auto || ''}`,
        };
        hint.innerHTML = texts[mode] || '';
    }

    console.log('Absender-Modus:', mode);
};
window.esSetSenderMode = ES.setSenderMode;

/* ── Preview Client Switch ── */
ES.setPreviewClient = function(btn) {
    const wrap = btn.closest('.es-preview-hdr');
    if (!wrap) return;
    wrap.querySelectorAll('.es-preview-client-btn')
        .forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const client = btn.dataset.client;
    const panel  = btn.closest('.es-preview-panel') ||
                   document.querySelector('.es-preview-panel');
    if (!panel) return;
    panel.querySelectorAll('[data-client-view]').forEach(v => {
        v.style.display = v.dataset.clientView === client ? '' : 'none';
    });
    console.log('Vorschau-Client:', client);
};
window.esSetPreviewClient = ES.setPreviewClient;

/* ── URL Helper ── */
ES.urlBase = () =>
    document.querySelector('meta[name="es-base-url"]')
        ?.getAttribute('content') || '/email-studio/';

ES.apiUrl = (path) => `${ES.urlBase()}api/${path}`;

/* ── Bestätigung ── */
ES.confirm = function(msgKey, fallback) {
    const msg = ES._i18n(msgKey) || fallback || ES._i18n('es.confirm_default') || msgKey;
    return window.confirm(msg);
};

/* ── Init ── */
document.addEventListener('DOMContentLoaded', function() {
    console.log('✓ ES Core initialisiert');
});

/* ══════════════════════════════════════════════════════════════════
 * ESHelp — Hilfe Modal
 * ══════════════════════════════════════════════════════════════════ */
window.ESHelp = {

    _helpData: null,

    open: async function() {
        const modal = document.getElementById('es-help-modal');
        if (!modal) return;
        modal.style.display = 'flex';
        const _curLang = (typeof currentLang !== 'undefined' ? currentLang : null) || window.ABPE_CONFIG?.current_lang || window.ES_CONFIG?.lang || 'de';
        if (!ESHelp._helpData || ESHelp._loadedLang !== _curLang) await ESHelp._loadHelp();
        ESHelp._applyLabels();
        ESHelp.tab('overview', document.querySelector('.es-help-tab[data-tab="overview"]'));
    },

    close: function() {
        const modal = document.getElementById('es-help-modal');
        if (modal) modal.style.display = 'none';
    },

    _loadHelp: async function() {
        const lang = (typeof currentLang !== 'undefined' ? currentLang : null) || window.ABPE_CONFIG?.current_lang || window.ES_CONFIG?.lang || 'de';
        try {
            const r = await fetch(`/static/email_studio/i18n/help_${lang}.json`);
            if (r.ok) {
                ESHelp._helpData = await r.json();
                ESHelp._loadedLang = lang;
            } else {
                const r2 = await fetch('/static/email_studio/i18n/help_de.json');
                ESHelp._helpData = await r2.json();
            }
        } catch(e) {
            console.warn('Hilfe laden fehlgeschlagen:', e);
            ESHelp._helpData = {};
        }
    },

    t: function(key) {
        return ESHelp._helpData?.[key] || key;
    },

    _applyLabels: function() {
        const t = ESHelp.t.bind(ESHelp);
        const set = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.textContent = val;
        };
        set('help-title',          t('help.title'));
        set('help-close',          t('help.close'));
        set('help-tab-overview',   t('help.tab_overview'));
        set('help-tab-modules',    t('help.tab_modules'));
        set('help-tab-vars',       t('help.tab_vars'));
        set('help-tab-translate',  t('help.tab_translate'));
        set('help-tab-tutorial',   t('help.tab_tutorial'));
        set('es-help-btn-label',   window.i18nData?.es?.help_btn || t('help.title'));
    },

    tab: function(name, btn) {
        document.querySelectorAll('.es-help-tab').forEach(b => b.classList.remove('active'));
        if (btn) btn.classList.add('active');
        const content = document.getElementById('es-help-content');
        if (!content) return;
        const t = ESHelp.t.bind(ESHelp);

        const html = {
            overview: `
                <div class="es-help-section">
                    <div class="es-help-h2"><i class="bi bi-info-circle"></i>${t('help.overview.title')}</div>
                    <p>${t('help.overview.text')}</p>
                </div>
                <div class="es-help-section">
                    <div class="es-help-h2"><i class="bi bi-send"></i>${t('help.overview.modes.title')}</div>
                    <div class="es-help-h3"><span class="es-help-badge user">USER</span> ${t('help.overview.user.title')}</div>
                    <p>${t('help.overview.user.text')}</p>
                    <div class="es-help-h3"><span class="es-help-badge template">TEMPLATE</span> ${t('help.overview.template.title')}</div>
                    <p>${t('help.overview.template.text')}</p>
                    <div class="es-help-h3"><span class="es-help-badge auto">AUTO</span> ${t('help.overview.auto.title')}</div>
                    <p>${t('help.overview.auto.text')}</p>
                </div>
                <div class="es-help-section">
                    <div class="es-help-h2"><i class="bi bi-code-slash"></i>${t('help.overview.api.title')}</div>
                    <p>${t('help.overview.api.text')}</p>
                    <div class="es-help-code">from apps.abpe_email_studio.api import EmailStudio

EmailStudio.send(
    template       = 'cv_generated_berater',
    recipient      = 'max@example.de',
    variables      = {'name': 'Max', 'cv_link': '...'},
    user           = request.user,
    task_reference = 'AID-12345',
    app_reference  = 'cv_extractor'
)</div>
                </div>`,

            modules: `
                <div class="es-help-section">
                    <div class="es-help-h2"><i class="bi bi-puzzle"></i>${t('help.modules.title')}</div>
                    <p>${t('help.modules.text')}</p>
                    <div class="es-help-code">{{block:abcona_header_blau}}
{{block:footer_standard}}
{{block:cta_blau}}</div>
                </div>
                <div class="es-help-section">
                    <div class="es-help-h2"><i class="bi bi-list-ul"></i>${t('help.modules.available.title')}</div>
                    <p>📧 ${t('help.modules.header')}</p>
                    <p>📋 ${t('help.modules.footer')}</p>
                    <p>🔘 ${t('help.modules.button')}</p>
                    <p>📄 ${t('help.modules.section')}</p>
                </div>
                <div class="es-help-section">
                    <div class="es-help-h2"><i class="bi bi-123"></i>${t('help.modules.howto.title')}</div>
                    ${[1,2,3,4].map(i => `
                    <div class="es-help-step">
                        <div class="es-help-step-num">${i}</div>
                        <div>${t('help.modules.howto.step'+i)}</div>
                    </div>`).join('')}
                </div>
                <div class="es-help-section">
                    <div class="es-help-h2"><i class="bi bi-code-square"></i>${t('help.modules.example.title')}</div>
                    <div class="es-help-code">&lt;table width="100%"&gt;
  {{block:abcona_header_blau}}
  &lt;tr&gt;&lt;td style="padding:24px;"&gt;
    &lt;p&gt;${t('help.modules.example.line1')}&lt;/p&gt;
    &lt;p&gt;${t('help.modules.example.line2')}&lt;/p&gt;
    {{block:cta_blau}}
  &lt;/td&gt;&lt;/tr&gt;
  {{block:footer_standard}}
&lt;/table&gt;</div>
                </div>`,

            vars: `
                <div class="es-help-section">
                    <div class="es-help-h2"><i class="bi bi-braces"></i>${t('help.vars.title')}</div>
                    <p>${t('help.vars.text')}</p>
                    <div class="es-help-code">{name}  →  Max Mustermann
{email} →  max@example.de
{date}  →  18.05.2026</div>
                </div>
                <div class="es-help-section">
                    <div class="es-help-h3" style="color:#0c447c;">■ ${t('help.vars.context.title')}</div>
                    <p>${t('help.vars.context.text')}</p>
                    <div class="es-help-code" style="background:#e6f1fb;color:#0c447c;">{name}  {first_name}  {last_name}
{email}  {cv_link}  {cv_version}
{created_date}  {task_ref}</div>
                </div>
                <div class="es-help-section">
                    <div class="es-help-h3" style="color:#27500a;">■ ${t('help.vars.user.title')}</div>
                    <p>${t('help.vars.user.text')}</p>
                    <div class="es-help-code" style="background:#eaf3de;color:#27500a;">{sender_name}  {sender_email}  {reply_to}</div>
                </div>
                <div class="es-help-section">
                    <div class="es-help-h3" style="color:#444;">■ ${t('help.vars.system.title')}</div>
                    <p>${t('help.vars.system.text')}</p>
                    <div class="es-help-code" style="background:#f1efe8;color:#444;">{portal_url}  {date}  {year}  {subject}</div>
                </div>`,

            translate: `
                <div class="es-help-section">
                    <div class="es-help-h2"><i class="bi bi-translate"></i>${t('help.translate.title')}</div>
                    ${[1,2,3,4,5].map(i => `
                    <div class="es-help-step">
                        <div class="es-help-step-num">${i}</div>
                        <div>${t('help.translate.step'+i)}</div>
                    </div>`).join('')}
                </div>
                <div class="es-help-section">
                    <div class="es-help-h3">${t('help.translate.api.title')}</div>
                    <div class="es-help-code">EmailStudio.send(
    template  = 'cv_generated_berater',
    recipient = 'marco@example.it',
    variables = {'name': 'Marco'},
    lang      = 'it'   # ← Sprache angeben
)</div>
                </div>
                <div class="es-help-section">
                    <div class="es-help-h3">${t('help.translate.new.title')}</div>
                    <p>${t('help.translate.new.text')}</p>
                </div>`,

            tutorial: (function() {
                const T = ESHelp.t.bind(ESHelp);
                const lbl = [
                    T('help.tutorial.s1.label'),
                    T('help.tutorial.s2.label'),
                    T('help.tutorial.s3.label'),
                    T('help.tutorial.s4.label'),
                    T('help.tutorial.s5.label'),
                ];
                const mk = (sc, step, r) => ({
                    t: T(`help.tutorial.s${sc}.step${step}.title`),
                    d: T(`help.tutorial.s${sc}.step${step}.desc`),
                    r
                });
                const S = (k) => T('help.tutorial.sim.' + k);
                const SC = [
{lbl:lbl[0], steps:[
mk(1,1, ()=>`<div class="es-tut-sim">
  <div class="es-tut-topbar">✉ Email Studio
    <span class="es-tut-pulse" style="background:#fff;color:#163258;padding:2px 8px;border-radius:4px;font-size:9px;font-weight:600;">${S('new_template')}</span>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;padding:8px 12px;font-size:9px;">
    <div style="text-align:center;padding:6px;border-right:1px solid #eee;">
      <div style="font-size:18px;font-weight:600;color:#163258;">6</div>
      <div style="color:#888;font-size:8px;text-transform:uppercase;">${S('stat_templates')}</div>
    </div>
    <div style="text-align:center;padding:6px;border-right:1px solid #eee;">
      <div style="font-size:18px;font-weight:600;color:#28a745;">5</div>
      <div style="color:#888;font-size:8px;text-transform:uppercase;">${S('stat_active')}</div>
    </div>
    <div style="text-align:center;padding:6px;border-right:1px solid #eee;">
      <div style="font-size:18px;font-weight:600;color:#f59e0b;">1</div>
      <div style="color:#888;font-size:8px;text-transform:uppercase;">${S('stat_draft')}</div>
    </div>
    <div style="text-align:center;padding:6px;">
      <div style="font-size:18px;font-weight:600;color:#888;">0</div>
      <div style="color:#888;font-size:8px;text-transform:uppercase;">${S('stat_archive')}</div>
    </div>
  </div>
  <div style="padding:0 12px 8px;font-size:8px;">
    <div style="background:#f8f8f8;border-radius:4px;overflow:hidden;border:1px solid #eee;">
      <div style="display:grid;grid-template-columns:2fr 1fr 1fr 60px;padding:4px 8px;background:#163258;color:#fff;font-size:8px;">
        <span>${S('col_name_id')}</span><span>${S('col_sender')}</span><span>${S('col_status')}</span><span>${S('col_actions')}</span>
      </div>
      <div style="display:grid;grid-template-columns:2fr 1fr 1fr 60px;padding:5px 8px;border-bottom:0.5px solid #eee;font-size:8px;align-items:center;">
        <span><b style="color:#163258;">${S('sample_cv_berater')}</b><br><span style="font-family:monospace;color:#888;font-size:7px;">cv_generated_berater</span></span>
        <span style="color:#28a745;">● ${S('mode_user')}</span>
        <span><span style="background:#28a745;color:#fff;border-radius:3px;padding:1px 5px;font-size:7px;">${S('stat_active')}</span></span>
        <span style="color:#888;font-size:10px;">✏ 📋 👁 ✈</span>
      </div>
      <div style="display:grid;grid-template-columns:2fr 1fr 1fr 60px;padding:5px 8px;font-size:8px;align-items:center;opacity:.5;">
        <span><b style="color:#163258;">${S('sample_pipeline_success')}</b><br><span style="font-family:monospace;color:#888;font-size:7px;">pipeline_success</span></span>
        <span style="color:#f59e0b;">● ${S('mode_auto')}</span>
        <span><span style="background:#28a745;color:#fff;border-radius:3px;padding:1px 5px;font-size:7px;">${S('stat_active')}</span></span>
        <span style="color:#888;font-size:10px;">✏ 📋 👁 ✈</span>
      </div>
    </div>
  </div>
</div>`},
mk(1,2, ()=>`<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="font-size:10px;font-weight:600;color:#163258;margin-bottom:8px;">${S('start_question')}</div>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;font-size:9px;">
    <div class="es-tut-pulse es-tut-crd" style="background:#e6f1fb;text-align:center;padding:10px 6px;">
      <div style="font-size:18px;margin-bottom:4px;">📄</div>
      <div style="font-weight:600;color:#0c447c;">${S('blank_template')}</div>
      <div style="color:#185fa5;margin-top:3px;font-size:8px;">${S('blank_hint')}</div>
    </div>
    <div class="es-tut-crd" style="text-align:center;padding:10px 6px;opacity:.6;">
      <div style="font-size:18px;margin-bottom:4px;">🏗</div>
      <div style="font-weight:600;">${S('skeleton')}</div>
      <div style="color:#666;margin-top:3px;font-size:8px;">${S('skeleton_hint')}</div>
    </div>
    <div class="es-tut-crd" style="text-align:center;padding:10px 6px;opacity:.6;">
      <div style="font-size:18px;margin-bottom:4px;">📋</div>
      <div style="font-weight:600;">${S('duplicate')}</div>
      <div style="color:#666;margin-top:3px;font-size:8px;">${S('duplicate_hint')}</div>
    </div>
  </div>
</div>`},
mk(1,3, ()=>`<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="font-size:10px;font-weight:600;color:#163258;margin-bottom:6px;">${S('copy_settings')}</div>
  <div style="display:flex;flex-direction:column;gap:5px;font-size:9px;">
    <div><div class="es-tut-lbl">${S('lbl_display_name')}</div><div class="es-tut-inp">${S('sample_cv_berater')}</div></div>
    <div><div class="es-tut-lbl">${S('lbl_subject')}</div><div class="es-tut-inp">${S('sample_subject')}</div></div>
    <div><div class="es-tut-lbl">${S('lbl_identifier')}</div>
      <div class="es-tut-pulse" style="border:1px solid #4a90d9;border-radius:4px;padding:3px 6px;font-family:monospace;background:#e6f1fb;color:#0c447c;">cv_generated_berater<span class="es-tut-cur"></span></div>
      <div style="font-size:8px;color:#185fa5;margin-top:2px;">${S('identifier_hint')}</div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:5px;">
      <div><div class="es-tut-lbl">${S('lbl_app_scope')}</div><div class="es-tut-inp">${S('sample_scope')}</div></div>
      <div><div class="es-tut-lbl">${S('lbl_status')}</div><div class="es-tut-inp">${S('stat_active')} ▾</div></div>
    </div>
  </div>
</div>`},
mk(1,4, ()=>`<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="font-size:10px;font-weight:600;color:#163258;margin-bottom:6px;">${S('sender_mode')}</div>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;font-size:9px;">
    <div class="es-tut-crd" style="text-align:center;padding:8px;opacity:.5;">
      <div style="font-size:16px;margin-bottom:3px;">▣</div>
      <div style="font-weight:600;">${S('mode_template')}</div>
      <div style="font-size:8px;color:#666;margin-top:2px;">${S('fixed_address')}</div>
    </div>
    <div class="es-tut-pulse es-tut-crd" style="background:#e6f1fb;text-align:center;padding:8px;">
      <div style="font-size:16px;margin-bottom:3px;">👤</div>
      <div style="font-weight:600;color:#0c447c;">${S('mode_user')}</div>
      <div style="font-size:8px;color:#185fa5;margin-top:2px;">${S('logged_in_employee')}</div>
      <div style="font-size:8px;background:#163258;color:#fff;border-radius:3px;padding:2px 4px;margin-top:4px;">${S('recommended')}</div>
    </div>
    <div class="es-tut-crd" style="text-align:center;padding:8px;opacity:.5;">
      <div style="font-size:16px;margin-bottom:3px;">🖨</div>
      <div style="font-weight:600;">${S('mode_auto')}</div>
      <div style="font-size:8px;color:#666;margin-top:2px;">${S('noreply_system')}</div>
    </div>
  </div>
  <div style="margin-top:6px;background:#e6f1fb;border-radius:4px;padding:4px 7px;font-size:8px;color:#0c447c;">${S('mode_hint_user_short')}</div>
</div>`},
mk(1,5, ()=>`<div class="es-tut-sim" style="padding:8px 10px;">
  <div style="display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:8px;">
    <div>
      <div style="font-size:8px;color:#888;margin-bottom:3px;">${S('editor_tabs')}</div>
      <div style="border:1px solid #eee;border-radius:4px;overflow:hidden;">
        <div style="display:flex;gap:3px;padding:4px 6px;border-bottom:1px solid #eee;background:#f8f8f8;">
          <span class="es-tut-tab-on">${S('tab_visual')}</span><span class="es-tut-tab-off">${S('tab_code')}</span><span class="es-tut-tab-off">TXT</span>
        </div>
        <div style="padding:6px;background:#fff;font-size:9px;">
          <div style="background:#163258;color:#fff;padding:5px 8px;text-align:center;font-weight:600;font-size:9px;border-radius:3px;margin-bottom:4px;">abcona e. K.</div>
          <p style="margin:0 0 3px;font-size:9px;">${S('hello_name')} <span style="background:#dbeafe;color:#1d4ed8;padding:0 3px;border-radius:2px;">{name}</span>,</p>
          <p style="margin:0 0 4px;font-size:9px;">${S('profile_created')}</p>
          <div style="display:inline-block;background:#163258;color:#fff;padding:3px 8px;border-radius:3px;font-size:8px;">${S('view_profile')}</div>
        </div>
      </div>
    </div>
    <div>
      <div style="font-size:8px;color:#888;margin-bottom:3px;">${S('sidebar_vars')}</div>
      <div style="border:1px solid #eee;border-radius:4px;overflow:hidden;">
        <div style="background:#163258;color:#fff;padding:4px 7px;font-size:8px;font-weight:500;">${S('vars_count')}</div>
        <div style="padding:5px 6px;font-size:8px;">
          <div style="color:#888;font-size:7px;text-transform:uppercase;margin-bottom:2px;">${S('from_context')}</div>
          ${['{name}','{email}','{cv_link}','{cv_version}','{created_date}'].map((v,i)=>`<div style="padding:2px 4px;background:#e6f1fb;border-radius:3px;margin-bottom:2px;font-family:monospace;color:#0c447c;font-size:8px;display:flex;justify-content:space-between;${i===0?'border:1.5px solid #163258;':''}" class="${i===0?'es-tut-pulse':''}">${v}<span style="color:#888;">📋</span></div>`).join('')}
          <div style="color:#888;font-size:7px;text-transform:uppercase;margin:4px 0 2px;">${S('user_profile')}</div>
          ${['{sender_name}','{sender_email}'].map(v=>`<div style="padding:2px 4px;background:#eaf3de;border-radius:3px;margin-bottom:2px;font-family:monospace;color:#27500a;font-size:8px;">${v}</div>`).join('')}
        </div>
      </div>
    </div>
  </div>
</div>`},
mk(1,6, ()=>`<div class="es-tut-sim" style="padding:8px 10px;">
  <div style="display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.1fr);gap:8px;">
    <div>
      <div style="border:1px solid #eee;border-radius:4px;overflow:hidden;">
        <div style="background:#163258;color:#fff;padding:4px 7px;font-size:8px;font-weight:500;">${S('send_test')}</div>
        <div style="padding:7px;">
          <div class="es-tut-inp" style="font-size:8px;margin-bottom:5px;">${S('recipient_email')}</div>
          <div class="es-tut-pulse" style="background:#163258;color:#fff;border-radius:4px;padding:3px 8px;font-size:8px;text-align:center;cursor:pointer;">${S('send_btn')}</div>
        </div>
      </div>
    </div>
    <div>
      <div style="border:1px solid #eee;border-radius:4px;overflow:hidden;">
        <div style="background:#163258;color:#fff;padding:4px 7px;font-size:8px;display:flex;align-items:center;justify-content:space-between;">
          <span>${S('live_preview')}</span>
          <div style="display:flex;gap:2px;">
            <span class="es-tut-tab-on" style="font-size:7px;padding:1px 4px;">Outlook</span>
            <span class="es-tut-tab-off" style="font-size:7px;padding:1px 4px;">Gmail</span>
            <span class="es-tut-tab-off" style="font-size:7px;padding:1px 4px;">TXT</span>
          </div>
        </div>
        <div style="padding:0;">
          <div style="font-size:8px;color:#888;padding:3px 6px;background:#f8f8f8;border-bottom:1px solid #eee;">${S('preview_from_to')}</div>
          <div style="background:#163258;color:#fff;padding:5px 8px;font-size:9px;font-weight:600;">abcona e. K.</div>
          <div style="padding:6px 8px;background:#fff;">
            <p style="margin:0 0 3px;font-size:9px;">${S('hello_name')} <b>Max Mustermann</b>,</p>
            <p style="margin:0 0 4px;font-size:9px;">${S('profile_created')}</p>
            <span style="display:inline-block;background:#163258;color:#fff;padding:3px 7px;border-radius:3px;font-size:8px;">${S('view_profile')}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>`},
mk(1,7, ()=>`<div class="es-tut-sim" style="padding:8px 12px;text-align:center;">
  <div style="display:flex;justify-content:flex-end;gap:6px;margin-bottom:10px;">
    <div style="border:1px solid #163258;color:#163258;border-radius:4px;padding:4px 10px;font-size:9px;">${S('save_as')}</div>
    <div class="es-tut-pulse" style="background:#163258;color:#fff;border-radius:4px;padding:4px 10px;font-size:9px;">${S('save')}</div>
  </div>
  <div style="display:flex;gap:8px;align-items:center;justify-content:center;flex-wrap:wrap;margin-bottom:8px;">
    <div style="background:#163258;color:#fff;border-radius:5px;padding:5px 10px;font-size:9px;font-weight:600;">📝 HTML</div>
    <span style="color:#163258;font-size:14px;">→</span>
    <div style="background:#faeeda;color:#633806;border-radius:5px;padding:5px 10px;font-size:9px;border:1px solid #ef9f27;">${S('txt_autogen')}</div>
    <span style="color:#163258;font-size:14px;">→</span>
    <div style="background:#eaf3de;color:#27500a;border-radius:5px;padding:5px 10px;font-size:9px;border:1px solid #97c459;">${S('version_n')}</div>
  </div>
  <div style="background:#163258;color:#fff;border-radius:4px;padding:4px 10px;font-size:9px;display:inline-block;">${S('saved_ok')}</div>
</div>`},
]},
{lbl:lbl[1], steps:[
mk(2,1, ()=>`<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="border:1px solid #eee;border-radius:5px;overflow:hidden;">
    <div style="background:#163258;color:#fff;padding:5px 10px;font-size:9px;display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
      <span class="es-tut-pulse" style="background:rgba(255,255,255,.25);padding:2px 8px;border-radius:3px;">${S('ver_history_official')}</span>
      <span style="opacity:.6;">${S('milestones_0')}</span>
      <span style="opacity:.6;">${S('undo')}</span>
      <span style="opacity:.6;">${S('redo')}</span>
      <span style="opacity:.6;margin-left:auto;">${S('translations_btn')}</span>
      <span style="opacity:.6;">${S('languages_btn')}</span>
      <span style="opacity:.6;">${S('auto_translate_btn')}</span>
    </div>
    <div style="padding:8px;display:flex;gap:8px;align-items:center;">
      <div style="background:#f8f8f8;border:1px solid #eee;border-radius:5px;padding:6px 10px;font-size:8px;text-align:center;opacity:.6;">
        <div style="font-weight:600;">2</div>
        <div style="color:#888;font-size:7px;">${S('auto_version')}</div>
        <div style="color:#888;font-size:7px;">18.05. 15:00</div>
      </div>
      <span style="color:#888;">←</span>
      <div class="es-tut-pulse" style="background:#eaf3de;border:2px solid #28a745;border-radius:5px;padding:6px 10px;font-size:8px;text-align:center;">
        <div style="width:18px;height:18px;border-radius:50%;background:#28a745;color:#fff;font-size:8px;font-weight:600;display:flex;align-items:center;justify-content:center;margin:0 auto 3px;">1</div>
        <div style="font-weight:600;color:#27500a;">${S('initial_active')}</div>
        <div style="color:#3b6d11;font-size:7px;">18.05. 13:22</div>
      </div>
      <div style="font-size:8px;color:#888;">${S('click_restore')}</div>
    </div>
  </div>
</div>`},
mk(2,2, ()=>`<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="border:1px solid #eee;border-radius:5px;overflow:hidden;">
    <div style="background:#163258;color:#fff;padding:5px 10px;font-size:9px;display:flex;align-items:center;gap:5px;flex-wrap:wrap;">
      <span style="opacity:.6;">${S('ver_history_2')}</span>
      <span style="opacity:.6;">${S('milestones_0')}</span>
      <span style="opacity:.6;">↩</span><span style="opacity:.6;">↪</span>
      <span class="es-tut-pulse" style="background:rgba(255,255,255,.3);padding:1px 6px;border-radius:3px;font-size:8px;">${S('mark_milestone')}</span>
      <input style="flex:1;min-width:80px;background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.3);border-radius:3px;padding:2px 5px;color:#fff;font-size:8px;" placeholder="${S('change_note_ph')}">
    </div>
  </div>
  <div style="margin-top:6px;background:#eaf3de;border-radius:4px;padding:4px 7px;font-size:8px;color:#27500a;">${S('milestone_tip')}</div>
</div>`},
mk(2,3, ()=>`<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="background:#fff;border:1px solid #e24b4a;border-radius:5px;padding:10px;font-size:9px;">
    <div style="font-weight:600;color:#e24b4a;margin-bottom:5px;">${S('restore_title')}</div>
    <div style="color:#333;margin-bottom:8px;line-height:1.6;">${S('restore_confirm')}</div>
    <div style="display:flex;gap:6px;justify-content:flex-end;">
      <div style="border:1px solid #eee;border-radius:4px;padding:3px 10px;font-size:9px;color:#666;">${S('cancel')}</div>
      <div class="es-tut-pulse" style="background:#163258;color:#fff;border-radius:4px;padding:3px 10px;font-size:9px;">${S('restore')}</div>
    </div>
  </div>
</div>`},
]},
{lbl:lbl[2], steps:[
mk(3,1, ()=>`<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="border:1px solid #eee;border-radius:5px;overflow:hidden;">
    <div style="background:#163258;color:#fff;padding:5px 10px;font-size:9px;font-weight:500;display:flex;align-items:center;gap:6px;">
      <span>${S('translations_btn')}</span>
      <span style="background:rgba(255,255,255,.2);padding:1px 5px;border-radius:3px;font-size:8px;">2</span>
      <span style="background:#e6f1fb;color:#0c447c;padding:1px 5px;border-radius:3px;font-size:8px;margin-left:auto;">${S('de_ref_hint')}</span>
    </div>
    <div style="padding:5px 8px;font-size:8px;">
      <div style="display:grid;grid-template-columns:50px 1fr 50px 90px 60px;gap:4px;color:#888;font-size:7px;text-transform:uppercase;padding:3px 0;border-bottom:1px solid #eee;">
        <span>${S('col_lang')}</span><span>${S('col_subject')}</span><span>${S('mode_auto')}</span><span>${S('col_translated_at')}</span><span>${S('col_actions')}</span>
      </div>
      <div style="display:grid;grid-template-columns:50px 1fr 50px 90px 60px;gap:4px;padding:4px 0;border-bottom:0.5px solid #eee;align-items:center;">
        <span style="background:#e6f1fb;color:#0c447c;padding:1px 5px;border-radius:3px;font-weight:600;font-size:8px;">EN</span>
        <span style="color:#333;font-size:8px;">Your Consultant Profile is Ready — {name}</span>
        <span style="background:#faeeda;color:#633806;padding:1px 4px;border-radius:3px;font-size:7px;">${S('mode_auto')}</span>
        <span style="color:#888;font-size:7px;">18.05.2026 15:29</span>
        <span style="color:#888;font-size:10px;">✏ 🔄 🗑</span>
      </div>
      <div style="display:grid;grid-template-columns:50px 1fr 50px 90px 60px;gap:4px;padding:4px 0;align-items:center;">
        <span style="background:#e6f1fb;color:#0c447c;padding:1px 5px;border-radius:3px;font-weight:600;font-size:8px;">IT</span>
        <span style="color:#333;font-size:8px;">Il tuo profilo consulente è pronto — {name}</span>
        <span style="background:#faeeda;color:#633806;padding:1px 4px;border-radius:3px;font-size:7px;">${S('mode_auto')}</span>
        <span style="color:#888;font-size:7px;">18.05.2026 16:16</span>
        <span style="color:#888;font-size:10px;">✏ 🔄 🗑</span>
      </div>
    </div>
  </div>
</div>`},
mk(3,2, ()=>`<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="border:1px solid #eee;border-radius:5px;overflow:hidden;">
    <div style="background:#163258;color:#fff;padding:5px 10px;font-size:9px;font-weight:500;">${S('lang_config_title')}</div>
    <div style="padding:8px;">
      <div style="font-size:8px;color:#888;margin-bottom:5px;text-transform:uppercase;font-size:7px;">${S('lang_config_title')}</div>
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:8px;">
        <label style="display:flex;align-items:center;gap:3px;font-size:9px;"><input type="checkbox"> EN English</label>
        <label style="display:flex;align-items:center;gap:3px;font-size:9px;"><input type="checkbox"> ES Spanish</label>
        <label style="display:flex;align-items:center;gap:3px;font-size:9px;"><input type="checkbox"> FR French</label>
        <label style="display:flex;align-items:center;gap:3px;font-size:9px;" class="es-tut-pulse"><input type="checkbox" checked> IT Italian</label>
      </div>
      <div style="border-top:1px solid #eee;padding-top:6px;display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
        <span style="font-size:8px;color:#888;">${S('install_lang')}</span>
        <div class="es-tut-inp" style="font-size:8px;">${S('lang_select')}</div>
        <div style="background:#163258;color:#fff;border-radius:4px;padding:3px 8px;font-size:8px;">${S('install_btn')}</div>
      </div>
    </div>
  </div>
</div>`},
mk(3,3, ()=>`<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="display:flex;gap:8px;align-items:center;justify-content:center;flex-wrap:wrap;margin-bottom:8px;">
    <div style="background:#163258;color:#fff;border-radius:5px;padding:5px 10px;font-size:9px;font-weight:600;">${S('de_basis_tab')}</div>
    <span style="font-size:14px;color:#163258;">→</span>
    <div class="es-tut-pulse" style="background:#faeeda;color:#633806;border-radius:5px;padding:5px 10px;font-size:9px;border:1px solid #ef9f27;">${S('ai_translates')}</div>
    <span style="font-size:14px;color:#163258;">→</span>
    <div style="background:#eaf3de;color:#27500a;border-radius:5px;padding:5px 10px;font-size:9px;border:1px solid #97c459;">${S('en_it_flags')}</div>
  </div>
  <div style="background:#1e1e1e;color:#d4d4d4;font-family:monospace;font-size:8px;border-radius:4px;padding:7px;line-height:1.8;">
<span style="color:#6a9955;">${S('code_de_basis')}</span>
${S('hello_name')} <span style="background:#264f78;">{name}</span>, ${S('html_profile_ready')}
<span style="color:#6a9955;">${S('code_it_auto')}</span>
Ciao <span style="background:#264f78;">{name}</span>, il tuo profilo è pronto.</div>
  <div style="margin-top:5px;background:#eaf3de;border-radius:4px;padding:4px 7px;font-size:8px;color:#27500a;">${S('vars_never_translated')}</div>
</div>`},
mk(3,4, ()=>`<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="border:1px solid #eee;border-radius:5px;overflow:hidden;">
    <div style="background:#163258;color:#fff;padding:5px 10px;font-size:9px;font-weight:500;display:flex;gap:4px;">
      <span style="background:rgba(255,255,255,.15);padding:2px 7px;border-radius:3px;">${S('de_basis_tab')}</span>
      <span style="background:rgba(255,255,255,.15);padding:2px 7px;border-radius:3px;">🇬🇧 EN</span>
      <span class="es-tut-pulse" style="background:#fff;color:#163258;padding:2px 7px;border-radius:3px;font-weight:600;">🇮🇹 IT ✏</span>
    </div>
    <div style="padding:8px;">
      <div style="background:#1e1e1e;color:#d4d4d4;font-family:monospace;font-size:8px;border-radius:4px;padding:6px;line-height:1.8;">Ciao <span style="background:#264f78;">{name}</span>,

Il tuo profilo consulente è pronto.
Clicca qui: <span style="background:#264f78;">{cv_link}</span>

Cordiali saluti, <span style="background:#264f78;">{sender_name}</span><span class="es-tut-cur"></span></div>
      <div style="margin-top:5px;background:#163258;color:#fff;border-radius:4px;padding:4px 7px;font-size:8px;text-align:center;cursor:pointer;">💾 ${S('save')}</div>
    </div>
  </div>
</div>`},
]},
{lbl:lbl[3], steps:[
mk(4,1, ()=>`<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;font-size:8px;">
    <div class="es-tut-crd" style="background:#e6f1fb;">
      <div style="font-weight:600;color:#0c447c;margin-bottom:3px;">HEADER</div>
      <div style="color:#888;font-size:7px;margin-bottom:4px;">${S('mod_header_desc')}</div>
      <div style="background:#163258;color:#fff;padding:4px 6px;border-radius:3px;font-size:8px;text-align:center;font-weight:600;">abcona e. K.</div>
    </div>
    <div class="es-tut-crd" style="background:#eaf3de;">
      <div style="font-weight:600;color:#27500a;margin-bottom:3px;">FOOTER</div>
      <div style="color:#888;font-size:7px;margin-bottom:4px;">${S('mod_footer_desc')}</div>
      <div style="background:#f0f0f0;padding:4px 6px;border-radius:3px;font-size:7px;color:#666;text-align:center;">${S('imprint_unsubscribe')}</div>
    </div>
    <div class="es-tut-crd" style="background:#faeeda;">
      <div style="font-weight:600;color:#633806;margin-bottom:3px;">BUTTON</div>
      <div style="color:#888;font-size:7px;margin-bottom:4px;">${S('mod_button_desc')}</div>
      <div style="display:flex;gap:4px;">
        <div style="background:#163258;color:#fff;border-radius:3px;padding:3px 8px;font-size:8px;">${S('btn_blue')}</div>
        <div style="background:#28a745;color:#fff;border-radius:3px;padding:3px 8px;font-size:8px;">${S('btn_green')}</div>
      </div>
    </div>
    <div class="es-tut-crd" style="background:#f1efe8;">
      <div style="font-weight:600;color:#444;margin-bottom:3px;">SECTION</div>
      <div style="color:#888;font-size:7px;margin-bottom:4px;">${S('support_contact')}</div>
      <div style="background:#fff;border:1px solid #eee;padding:4px 6px;border-radius:3px;font-size:7px;color:#666;">📞 ${S('html_support')}: support@abcona.de</div>
    </div>
  </div>
</div>`},
mk(4,2, ()=>`<div class="es-tut-sim" style="padding:8px 10px;">
  <div style="border:1px solid #eee;border-radius:5px;overflow:hidden;max-width:220px;">
    <div style="background:#163258;color:#fff;padding:5px 10px;font-size:9px;font-weight:500;">${S('modules_panel')}</div>
    <div style="padding:6px 8px;font-size:8px;">
      <div style="color:#888;text-transform:uppercase;font-size:7px;margin-bottom:3px;">BUTTON</div>
      <div class="es-tut-pulse" style="display:flex;align-items:center;gap:5px;padding:4px 7px;border:1px solid #b5d4f4;border-radius:4px;margin-bottom:2px;cursor:pointer;background:#e6f1fb;">
        <span>✈</span><span style="color:#0c447c;font-weight:500;">${S('btn_blue')}</span>
      </div>
      <div style="display:flex;align-items:center;gap:5px;padding:4px 7px;border:1px solid #eee;border-radius:4px;margin-bottom:5px;opacity:.7;">
        <span>✈</span><span>${S('btn_green')}</span>
      </div>
      <div style="color:#888;text-transform:uppercase;font-size:7px;margin-bottom:3px;">FOOTER</div>
      <div style="display:flex;align-items:center;gap:5px;padding:4px 7px;border:1px solid #eee;border-radius:4px;margin-bottom:2px;opacity:.7;"><span>📋</span><span>${S('footer_auto_reply')}</span></div>
      <div style="display:flex;align-items:center;gap:5px;padding:4px 7px;border:1px solid #eee;border-radius:4px;margin-bottom:5px;opacity:.7;"><span>📋</span><span>${S('footer_standard')}</span></div>
      <div style="color:#888;text-transform:uppercase;font-size:7px;margin-bottom:3px;">HEADER</div>
      <div style="display:flex;align-items:center;gap:5px;padding:4px 7px;border:1px solid #eee;border-radius:4px;margin-bottom:2px;opacity:.7;"><span>📋</span><span>${S('header_blue')}</span></div>
      <div style="display:flex;align-items:center;gap:5px;padding:4px 7px;border:1px solid #eee;border-radius:4px;margin-bottom:2px;opacity:.7;"><span>📋</span><span>${S('header_green')}</span></div>
      <div style="display:flex;align-items:center;gap:5px;padding:4px 7px;border:1px solid #eee;border-radius:4px;opacity:.7;"><span>📋</span><span>${S('header_red')}</span></div>
    </div>
  </div>
</div>`},
mk(4,3, ()=>`<div class="es-tut-sim" style="padding:8px 10px;">
  <div style="display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,1fr);gap:8px;">
    <div>
      <div style="font-size:8px;color:#888;margin-bottom:3px;">${S('html_after_insert')}</div>
      <div class="es-tut-editor" style="font-size:8px;"><span style="background:#264f78;">{{block:abcona_header_blau}}</span>
&lt;tr&gt;&lt;td style="padding:24px;"&gt;
  &lt;p&gt;${S('html_hello_profile')}&lt;/p&gt;
  &lt;p&gt;${S('html_profile_ready')}&lt;/p&gt;
  <span style="background:#264f78;">{{block:button_blau}}</span>
&lt;/td&gt;&lt;/tr&gt;
<span style="background:#264f78;">{{block:footer_standard}}</span><span class="es-tut-cur"></span></div>
    </div>
    <div>
      <div style="font-size:8px;color:#888;margin-bottom:3px;">${S('preview_resolved')}</div>
      <div style="border:1px solid #e0e0e0;border-radius:5px;overflow:hidden;">
        <div style="background:#163258;color:#fff;padding:5px 8px;font-size:9px;font-weight:600;">abcona e. K.</div>
        <div style="background:#fff;padding:7px 8px;">
          <p style="margin:0 0 3px;font-size:9px;">${S('hello_name')} <b>{name}</b>,</p>
          <p style="margin:0 0 5px;font-size:9px;">${S('html_profile_ready')}</p>
          <span style="display:inline-block;background:#163258;color:#fff;padding:3px 8px;border-radius:3px;font-size:8px;">${S('view_profile')}</span>
        </div>
        <div style="background:#f0f0f0;padding:3px 8px;font-size:7px;color:#999;">${S('imprint_footer')}</div>
      </div>
    </div>
  </div>
</div>`},
]},
{lbl:lbl[4], steps:[
mk(5,1, ()=>`<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="font-size:9px;font-weight:600;color:#163258;margin-bottom:6px;">${S('typical_situations')}</div>
  ${[['pipeline_success','pipeline_error',S('dup_case1')],
     ['upload_received','upload_error',S('dup_case2')],
     ['cv_generated_de','cv_generated_en',S('dup_case3')]
  ].map(([a,b,d])=>`
  <div style="display:flex;align-items:center;gap:6px;padding:4px 0;border-bottom:0.5px solid #eee;font-size:8px;">
    <code style="background:#f1f1f1;padding:1px 4px;border-radius:2px;">${a}</code>
    <span style="color:#163258;font-weight:600;">→</span>
    <code style="background:#e6f1fb;color:#0c447c;padding:1px 4px;border-radius:2px;">${b}</code>
    <span style="color:#888;">${d}</span>
  </div>`).join('')}
  <div style="margin-top:6px;background:#faeeda;border-radius:4px;padding:4px 7px;font-size:8px;color:#633806;">${S('dup_independent')}</div>
</div>`},
mk(5,2, ()=>`<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="border:1px solid #eee;border-radius:5px;overflow:hidden;">
    <div style="background:#163258;color:#fff;padding:4px 8px;font-size:8px;display:grid;grid-template-columns:2fr 1fr 1fr 80px;">
      <span>${S('col_name_id')}</span><span>${S('col_sender')}</span><span>${S('col_status')}</span><span>${S('col_actions')}</span>
    </div>
    <div style="display:grid;grid-template-columns:2fr 1fr 1fr 80px;padding:6px 8px;font-size:8px;align-items:center;">
      <div><b style="color:#163258;">${S('sample_pipeline_success')}</b><br><span style="font-family:monospace;color:#888;font-size:7px;">pipeline_success</span></div>
      <span style="color:#f59e0b;">● ${S('mode_auto')}</span>
      <span><span style="background:#28a745;color:#fff;border-radius:3px;padding:1px 5px;font-size:7px;">${S('stat_active')}</span></span>
      <div style="display:flex;gap:4px;align-items:center;">
        <span style="color:#888;">✏</span>
        <span class="es-tut-pulse" style="background:#e6f1fb;color:#163258;border-radius:3px;padding:2px 5px;font-size:11px;cursor:pointer;">📋</span>
        <span style="color:#888;">👁 ✈ 🗑</span>
      </div>
    </div>
  </div>
  <div style="margin-top:5px;background:#e6f1fb;border-radius:4px;padding:4px 7px;font-size:8px;color:#0c447c;">${S('dup_click_hint')}</div>
</div>`},
mk(5,3, ()=>`<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="font-size:9px;font-weight:600;color:#163258;margin-bottom:5px;">${S('dup_from')}</div>
  <div style="display:flex;flex-direction:column;gap:5px;font-size:9px;">
    <div><div class="es-tut-lbl">${S('lbl_new_identifier')}</div>
      <div class="es-tut-pulse" style="border:1px solid #4a90d9;border-radius:4px;padding:3px 6px;font-family:monospace;background:#e6f1fb;color:#0c447c;">pipeline_error<span class="es-tut-cur"></span></div>
    </div>
    <div><div class="es-tut-lbl">${S('lbl_new_name')}</div>
      <div class="es-tut-inp">${S('sample_pipeline_error_name')}</div>
    </div>
  </div>
  <div style="margin-top:6px;border:1px solid #eee;border-radius:4px;padding:5px 7px;font-size:8px;">
    <div style="font-weight:500;color:#333;margin-bottom:3px;">${S('what_copied')}</div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;">
      ${['HTML','TXT',S('copy_sender_mode'),T('help.vars.title'),T('help.tab_modules'),S('copy_settings')].map(x=>`<span style="color:#27500a;">✓ ${x}</span>`).join('')}
    </div>
  </div>
</div>`},
mk(5,4, ()=>`<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:8px;">
    <div>
      <div style="font-size:8px;color:#888;margin-bottom:3px;">${S('original_label')}</div>
      <div class="es-tut-editor" style="font-size:8px;opacity:.65;">&lt;h2&gt;${S('html_success_title')}&lt;/h2&gt;
&lt;p style="color:#28a745;"&gt;${S('html_all_ok')}&lt;/p&gt;
&lt;a style="background:#28a745;"&gt;${S('html_view_result')}&lt;/a&gt;</div>
    </div>
    <div>
      <div style="font-size:8px;color:#163258;margin-bottom:3px;">${S('copy_label')}</div>
      <div class="es-tut-editor" style="font-size:8px;">&lt;h2&gt;<span style="background:#264f78;">${S('html_error_occurred')}</span>&lt;/h2&gt;
&lt;p style="color:<span style="background:#264f78;">#e24b4a</span>;"&gt;<span style="background:#264f78;">${S('html_error')}</span>&lt;/p&gt;
&lt;a style="background:<span style="background:#264f78;">#e24b4a</span>;"&gt;<span style="background:#264f78;">${S('html_support')}</span>&lt;/a&gt;<span class="es-tut-cur"></span></div>
    </div>
  </div>
  <div style="margin-top:5px;background:#eaf3de;border-radius:4px;padding:4px 7px;font-size:8px;color:#27500a;">${S('only_3_changes')}</div>
</div>`},
]},
                ]; /* end SC */

                let curSc = 0, curStep = 0, autoTimer = null;

                if (!document.getElementById('es-tut-css')) {
                    const s = document.createElement('style');
                    s.id = 'es-tut-css';
                    s.textContent = `.es-tut-wrap{padding:4px 0;font-family:inherit;}.es-tut-sc-tabs{display:flex;gap:5px;flex-wrap:wrap;margin-bottom:10px;}.es-tut-sc-tab{padding:5px 11px;border-radius:6px;border:0.5px solid #ccc;font-size:10px;cursor:pointer;background:#fff;color:#555;white-space:nowrap;}.es-tut-sc-tab.on{background:#163258;color:#fff;border-color:#163258;}.es-tut-stage{border:0.5px solid #e0e0e0;border-radius:8px;overflow:hidden;background:#fff;}.es-tut-shdr{background:#163258;color:#fff;padding:6px 12px;font-size:10px;display:flex;align-items:center;justify-content:space-between;}.es-tut-ctrl{display:flex;align-items:center;gap:7px;padding:8px 12px;border-top:0.5px solid #e0e0e0;background:#f8f8f8;}.es-tut-bp,.es-tut-bn{padding:4px 11px;border-radius:6px;border:0.5px solid #ccc;font-size:11px;cursor:pointer;background:#fff;color:#333;}.es-tut-bn{background:#163258;color:#fff;border-color:#163258;}.es-tut-bp:disabled,.es-tut-bn:disabled{opacity:.3;cursor:default;}.es-tut-dots{display:flex;gap:4px;flex:1;justify-content:center;}.es-tut-dot{width:6px;height:6px;border-radius:50%;background:#ccc;cursor:pointer;}.es-tut-dot.on{background:#163258;}.es-tut-abtn{padding:3px 8px;border-radius:6px;border:0.5px solid #ccc;font-size:10px;cursor:pointer;background:#fff;color:#666;}.es-tut-ttl{font-size:12px;font-weight:600;color:#163258;margin:8px 0 3px;}.es-tut-dsc{font-size:11px;color:#555;line-height:1.6;margin:0 0 4px;}.es-tut-sim{font-size:10px;padding:10px 12px;}.es-tut-topbar{background:#163258;color:#fff;padding:5px 10px;font-size:9px;border-radius:5px 5px 0 0;display:flex;align-items:center;justify-content:space-between;}.es-tut-editor{background:#1e1e1e;color:#d4d4d4;font-family:monospace;font-size:8px;border-radius:4px;padding:7px;line-height:1.7;white-space:pre;}.es-tut-panel{border:1px solid #e0e0e0;border-radius:5px;overflow:hidden;}.es-tut-phdr{background:#f5f5f5;padding:3px 7px;font-size:8px;font-weight:600;border-bottom:1px solid #e0e0e0;color:#333;}.es-tut-chip{background:#e6f1fb;color:#0c447c;border-radius:3px;padding:2px 5px;font-size:8px;font-family:monospace;display:inline-block;margin:2px;cursor:pointer;}.es-tut-chip-g{background:#eaf3de;color:#27500a;}.es-tut-chip-s{background:#f1efe8;color:#444;}.es-tut-inp{border:1px solid #ddd;border-radius:3px;padding:3px 5px;font-size:8px;background:#fff;color:#333;}.es-tut-lbl{font-size:7px;color:#888;margin-bottom:2px;text-transform:uppercase;}.es-tut-crd{border:1px solid #e0e0e0;border-radius:5px;padding:6px 8px;background:#fff;}.es-tut-tab-on{padding:2px 6px;background:#163258;color:#fff;border-radius:3px;font-size:8px;}.es-tut-tab-off{padding:2px 6px;border:1px solid #ddd;border-radius:3px;font-size:8px;color:#666;}.es-tut-cur{display:inline-block;width:2px;height:10px;background:#fff;vertical-align:middle;animation:es-tut-blink 1s infinite;}.es-tut-pulse{border:2px solid #163258;border-radius:4px;animation:es-tut-pulse 1.2s infinite;}@keyframes es-tut-blink{0%,100%{opacity:1}50%{opacity:0}}@keyframes es-tut-pulse{0%,100%{border-color:#163258}50%{border-color:#4a90d9}}`;
                    document.head.appendChild(s);
                }

                function render() {
                    const sc = SC[curSc], s = sc.steps[curStep], tot = sc.steps.length;
                    document.getElementById('es-tut-shdr-lbl').textContent = sc.lbl;
                    document.getElementById('es-tut-fr-cnt').textContent = T('help.tutorial.step')+' '+(curStep+1)+' '+T('help.tutorial.of')+' '+tot;
                    document.getElementById('es-tut-ttl').textContent = s.t;
                    document.getElementById('es-tut-dsc').textContent = s.d;
                    document.getElementById('es-tut-frames').innerHTML = s.r();
                    document.getElementById('es-tut-dots').innerHTML = sc.steps.map((_,i)=>`<div class="es-tut-dot${i===curStep?' on':''}" onclick="window._esTut.goTo(${i})"></div>`).join('');
                    document.getElementById('es-tut-bp').disabled = curStep===0;
                    const bn=document.getElementById('es-tut-bn');
                    bn.disabled=curStep===tot-1;
                    bn.textContent=curStep===tot-1?'✓ '+T('help.tutorial.done'):T('help.tutorial.next')+' →';
                }
                function nav(d){const n=curStep+d;if(n>=0&&n<SC[curSc].steps.length){curStep=n;render();}}
                function goTo(i){curStep=i;render();}
                function switchSc(i,btn){
                    document.querySelectorAll('.es-tut-sc-tab').forEach(b=>b.classList.remove('on'));
                    btn.classList.add('on');
                    curSc=i;curStep=0;render();
                }
                function toggleAuto(){
                    if(autoTimer){stopAuto();return;}
                    document.getElementById('es-tut-abtn').textContent=T('help.tutorial.stop');
                    const ms=window._esTutSpeed||3200;
                    autoTimer=setInterval(()=>{if(curStep<SC[curSc].steps.length-1){curStep++;render();}else stopAuto();},ms);
                }
                function stopAuto(){
                    if(autoTimer){clearInterval(autoTimer);autoTimer=null;}
                    document.getElementById('es-tut-abtn').textContent=T('help.tutorial.auto');
                }
                window._esTut={nav,goTo,switchSc,toggleAuto};
                window._esTutSpeed=window._esTutSpeed||3200;

                const html=`<div class="es-tut-wrap">
  <div class="es-tut-sc-tabs">
    ${SC.map((s,i)=>`<button class="es-tut-sc-tab${i===0?' on':''}" onclick="window._esTut.switchSc(${i},this)">${s.lbl}</button>`).join('')}
  </div>
  <div class="es-tut-stage">
    <div class="es-tut-shdr">
      <span id="es-tut-shdr-lbl">${SC[0].lbl}</span>
      <span id="es-tut-fr-cnt" style="opacity:.7;">${T('help.tutorial.step')} 1 ${T('help.tutorial.of')} ${SC[0].steps.length}</span>
    </div>
    <div id="es-tut-frames" style="min-height:260px;"></div>
    <div class="es-tut-ctrl">
      <button class="es-tut-bp" id="es-tut-bp" onclick="window._esTut.nav(-1)" disabled>← ${T('help.tutorial.prev')}</button>
      <div class="es-tut-dots" id="es-tut-dots"></div>
      <input type="range" min="1" max="6" value="3" step="1" style="width:50px;" title="${T('help.tutorial.speed')}" oninput="window._esTutSpeed=this.value*1000">
      <button class="es-tut-abtn" id="es-tut-abtn" onclick="window._esTut.toggleAuto()">${T('help.tutorial.auto')}</button>
      <button class="es-tut-bn" id="es-tut-bn" onclick="window._esTut.nav(1)">${T('help.tutorial.next')} →</button>
    </div>
  </div>
  <div>
    <div class="es-tut-ttl" id="es-tut-ttl"></div>
    <div class="es-tut-dsc" id="es-tut-dsc"></div>
  </div>
</div>`;
                return html;
            })()
        };

        content.innerHTML = html[name] || '';
        if (name === 'tutorial') {
            setTimeout(function() {
                if (window._esTut && typeof window._esTut.nav === 'function') {
                    window._esTut.nav(0);
                }
            }, 0);
        }
    }
};

// Modal schließen bei Klick außerhalb
document.addEventListener('click', function(e) {
    const modal = document.getElementById('es-help-modal');
    if (modal && e.target === modal) ESHelp.close();
});
