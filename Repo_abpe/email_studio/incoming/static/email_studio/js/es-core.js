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

/* ── Notifications (kein hardcoded Text — Keys aus i18n) ── */
ES.notify = {
    _show: function(msgKey, type, fallback) {
        const msg = (window.i18nData && window.i18nData[msgKey])
            ? window.i18nData[msgKey]
            : fallback;
        const el = document.createElement('div');
        el.className = `es-notify es-notify-${type}`;
        el.innerHTML = msg;
        document.body.appendChild(el);
        setTimeout(() => el.remove(), 3500);
    },
    success: (key, fallback='OK') => ES.notify._show(key, 'success', fallback),
    error:   (key, fallback='Fehler') => ES.notify._show(key, 'error',   fallback),
    info:    (key, fallback='Info') => ES.notify._show(key, 'info',    fallback),
    warning: (key, fallback='Warnung') => ES.notify._show(key, 'warning', fallback),
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
            'USER':     `<i class="bi bi-info-circle es-icon-green"></i> ${i18n.mode_hint_user || 'From = eingeloggter User'}`,
            'TEMPLATE': `<i class="bi bi-info-circle es-icon-blue"></i> ${i18n.mode_hint_template || 'From = feste Adresse'}`,
            'AUTO':     `<i class="bi bi-info-circle es-icon-yellow"></i> ${i18n.mode_hint_auto || 'From = noreply'}`,
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
    if (window.ESStudio?._loadPreview) {
        window.ESStudio._loadPreview(true);
    }
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
    const msg = (window.i18nData && window.i18nData[msgKey])
        ? window.i18nData[msgKey]
        : (fallback || 'Sind Sie sicher?');
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

    openTutorial: async function() {
        const modal = document.getElementById('es-help-modal');
        if (!modal) return;
        modal.style.display = 'flex';
        const _curLang = (typeof currentLang !== 'undefined' ? currentLang : null) || window.ABPE_CONFIG?.current_lang || window.ES_CONFIG?.lang || 'de';
        if (!ESHelp._helpData || ESHelp._loadedLang !== _curLang) await ESHelp._loadHelp();
        ESHelp._applyLabels();
        ESHelp.tab('tutorial', document.querySelector('.es-help-tab[data-tab="tutorial"]'));
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
        set('es-help-btn-label',   t('help.close') === 'Close' ? 'Help' : 'Hilfe');
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
    &lt;p&gt;Hallo {name},&lt;/p&gt;
    &lt;p&gt;Ihr CV ist fertig.&lt;/p&gt;
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
                const SC = [
{lbl:lbl[0], steps:[
{t:'Vorlagen-Übersicht',
 d:'Klicken Sie oben auf den Tab "Vorlagen". Hier sehen Sie alle E-Mail-Vorlagen — wie viele aktiv, im Entwurf oder archiviert sind. Mit "+ Neue Vorlage" oben rechts starten Sie eine neue E-Mail-Vorlage.',
 r:()=>`<div class="es-tut-sim">
  <div class="es-tut-topbar">✉ Email Studio
    <span class="es-tut-pulse" style="background:#fff;color:#163258;padding:2px 8px;border-radius:4px;font-size:9px;font-weight:600;">+ Neue Vorlage</span>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;padding:8px 12px;font-size:9px;">
    <div style="text-align:center;padding:6px;border-right:1px solid #eee;">
      <div style="font-size:18px;font-weight:600;color:#163258;">6</div>
      <div style="color:#888;font-size:8px;text-transform:uppercase;">Vorlagen</div>
    </div>
    <div style="text-align:center;padding:6px;border-right:1px solid #eee;">
      <div style="font-size:18px;font-weight:600;color:#28a745;">5</div>
      <div style="color:#888;font-size:8px;text-transform:uppercase;">Aktiv</div>
    </div>
    <div style="text-align:center;padding:6px;border-right:1px solid #eee;">
      <div style="font-size:18px;font-weight:600;color:#f59e0b;">1</div>
      <div style="color:#888;font-size:8px;text-transform:uppercase;">Entwurf</div>
    </div>
    <div style="text-align:center;padding:6px;">
      <div style="font-size:18px;font-weight:600;color:#888;">0</div>
      <div style="color:#888;font-size:8px;text-transform:uppercase;">Archiv</div>
    </div>
  </div>
  <div style="padding:0 12px 8px;font-size:8px;">
    <div style="background:#f8f8f8;border-radius:4px;overflow:hidden;border:1px solid #eee;">
      <div style="display:grid;grid-template-columns:2fr 1fr 1fr 60px;padding:4px 8px;background:#163258;color:#fff;font-size:8px;">
        <span>Name / Identifier</span><span>Absender</span><span>Status</span><span>Aktionen</span>
      </div>
      <div style="display:grid;grid-template-columns:2fr 1fr 1fr 60px;padding:5px 8px;border-bottom:0.5px solid #eee;font-size:8px;align-items:center;">
        <span><b style="color:#163258;">CV fertig — Berater</b><br><span style="font-family:monospace;color:#888;font-size:7px;">cv_generated_berater</span></span>
        <span style="color:#28a745;">● User</span>
        <span><span style="background:#28a745;color:#fff;border-radius:3px;padding:1px 5px;font-size:7px;">Aktiv</span></span>
        <span style="color:#888;font-size:10px;">✏ 📋 👁 ✈</span>
      </div>
      <div style="display:grid;grid-template-columns:2fr 1fr 1fr 60px;padding:5px 8px;font-size:8px;align-items:center;opacity:.5;">
        <span><b style="color:#163258;">Pipeline Erfolg</b><br><span style="font-family:monospace;color:#888;font-size:7px;">pipeline_success</span></span>
        <span style="color:#f59e0b;">● Auto</span>
        <span><span style="background:#28a745;color:#fff;border-radius:3px;padding:1px 5px;font-size:7px;">Aktiv</span></span>
        <span style="color:#888;font-size:10px;">✏ 📋 👁 ✈</span>
      </div>
    </div>
  </div>
</div>`},
{t:'Neue Vorlage — Startoptionen',
 d:'Nach Klick auf "+ Neue Vorlage" wählen Sie wie Sie starten möchten: Leeres Template (freie Gestaltung), Corporate Skeleton (mit fertigem Header und Footer), oder eine bestehende Vorlage duplizieren.',
 r:()=>`<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="font-size:10px;font-weight:600;color:#163258;margin-bottom:8px;">Wie möchten Sie starten?</div>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;font-size:9px;">
    <div class="es-tut-pulse es-tut-crd" style="background:#e6f1fb;text-align:center;padding:10px 6px;">
      <div style="font-size:18px;margin-bottom:4px;">📄</div>
      <div style="font-weight:600;color:#0c447c;">Leeres Template</div>
      <div style="color:#185fa5;margin-top:3px;font-size:8px;">HTML von Grund auf schreiben</div>
    </div>
    <div class="es-tut-crd" style="text-align:center;padding:10px 6px;opacity:.6;">
      <div style="font-size:18px;margin-bottom:4px;">🏗</div>
      <div style="font-weight:600;">Corporate Skeleton</div>
      <div style="color:#666;margin-top:3px;font-size:8px;">Mit Header + Footer starten</div>
    </div>
    <div class="es-tut-crd" style="text-align:center;padding:10px 6px;opacity:.6;">
      <div style="font-size:18px;margin-bottom:4px;">📋</div>
      <div style="font-weight:600;">Duplizieren</div>
      <div style="color:#666;margin-top:3px;font-size:8px;">Bestehende Vorlage kopieren</div>
    </div>
  </div>
</div>`},
{t:'Einstellungen ausfüllen',
 d:'Füllen Sie die Felder aus: Anzeigename, Betreff, Technischer Name (Identifier). Der Identifier ist der interne Name der im Python-Code verwendet wird — z.B. cv_generated_berater. Er kann nach dem ersten Speichern nicht mehr geändert werden.',
 r:()=>`<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="font-size:10px;font-weight:600;color:#163258;margin-bottom:6px;">Einstellungen</div>
  <div style="display:flex;flex-direction:column;gap:5px;font-size:9px;">
    <div><div class="es-tut-lbl">ANZEIGENAME</div><div class="es-tut-inp">CV fertig — Berater</div></div>
    <div><div class="es-tut-lbl">BETREFF</div><div class="es-tut-inp">Ihr Berater-Profil ist fertig — {name}</div></div>
    <div><div class="es-tut-lbl">TECHNISCHER NAME (IDENTIFIER) *</div>
      <div class="es-tut-pulse" style="border:1px solid #4a90d9;border-radius:4px;padding:3px 6px;font-family:monospace;background:#e6f1fb;color:#0c447c;">cv_generated_berater<span class="es-tut-cur"></span></div>
      <div style="font-size:8px;color:#185fa5;margin-top:2px;">Wird im Python-Code verwendet: template='cv_generated_berater'</div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:5px;">
      <div><div class="es-tut-lbl">APP-BEREICH</div><div class="es-tut-inp">Intake / CV Upload ▾</div></div>
      <div><div class="es-tut-lbl">STATUS</div><div class="es-tut-inp">Aktiv ▾</div></div>
    </div>
  </div>
</div>`},
{t:'Absender-Modus wählen',
 d:'Wählen Sie wer als Absender erscheint. "User" = die E-Mail kommt vom eingeloggten Mitarbeiter (z.B. angelo@abcona.de) mit seiner Signatur. "Template" = feste Absenderadresse. "Auto" = noreply, für automatische System-Mails.',
 r:()=>`<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="font-size:10px;font-weight:600;color:#163258;margin-bottom:6px;">Absender-Modus</div>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;font-size:9px;">
    <div class="es-tut-crd" style="text-align:center;padding:8px;opacity:.5;">
      <div style="font-size:16px;margin-bottom:3px;">▣</div>
      <div style="font-weight:600;">Template</div>
      <div style="font-size:8px;color:#666;margin-top:2px;">Feste Adresse</div>
    </div>
    <div class="es-tut-pulse es-tut-crd" style="background:#e6f1fb;text-align:center;padding:8px;">
      <div style="font-size:16px;margin-bottom:3px;">👤</div>
      <div style="font-weight:600;color:#0c447c;">User</div>
      <div style="font-size:8px;color:#185fa5;margin-top:2px;">Eingeloggter Mitarbeiter</div>
      <div style="font-size:8px;background:#163258;color:#fff;border-radius:3px;padding:2px 4px;margin-top:4px;">Empfohlen</div>
    </div>
    <div class="es-tut-crd" style="text-align:center;padding:8px;opacity:.5;">
      <div style="font-size:16px;margin-bottom:3px;">🖨</div>
      <div style="font-weight:600;">Auto</div>
      <div style="font-size:8px;color:#666;margin-top:2px;">noreply — System-Mails</div>
    </div>
  </div>
  <div style="margin-top:6px;background:#e6f1fb;border-radius:4px;padding:4px 7px;font-size:8px;color:#0c447c;">From = eingeloggter User · Signatur automatisch aus User-Profil</div>
</div>`},
{t:'HTML schreiben und Variablen einfügen',
 d:'Im mittleren Bereich schreiben Sie den E-Mail-Inhalt. Unter "Variablen" in der Sidebar sehen Sie alle Platzhalter — klicken Sie auf einen um ihn einzufügen. {name} wird beim Versand durch den echten Namen des Empfängers ersetzt.',
 r:()=>`<div class="es-tut-sim" style="padding:8px 10px;">
  <div style="display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:8px;">
    <div>
      <div style="font-size:8px;color:#888;margin-bottom:3px;">HTML-Editor · Visuell / Code / TXT</div>
      <div style="border:1px solid #eee;border-radius:4px;overflow:hidden;">
        <div style="display:flex;gap:3px;padding:4px 6px;border-bottom:1px solid #eee;background:#f8f8f8;">
          <span class="es-tut-tab-on">Visuell</span><span class="es-tut-tab-off">Code</span><span class="es-tut-tab-off">TXT</span>
        </div>
        <div style="padding:6px;background:#fff;font-size:9px;">
          <div style="background:#163258;color:#fff;padding:5px 8px;text-align:center;font-weight:600;font-size:9px;border-radius:3px;margin-bottom:4px;">abcona e. K.</div>
          <p style="margin:0 0 3px;font-size:9px;">Hallo <span style="background:#dbeafe;color:#1d4ed8;padding:0 3px;border-radius:2px;">{name}</span>,</p>
          <p style="margin:0 0 4px;font-size:9px;">Ihr Profil wurde erfolgreich erstellt.</p>
          <div style="display:inline-block;background:#163258;color:#fff;padding:3px 8px;border-radius:3px;font-size:8px;">Profil ansehen</div>
        </div>
      </div>
    </div>
    <div>
      <div style="font-size:8px;color:#888;margin-bottom:3px;">Sidebar — Variablen</div>
      <div style="border:1px solid #eee;border-radius:4px;overflow:hidden;">
        <div style="background:#163258;color:#fff;padding:4px 7px;font-size:8px;font-weight:500;">{} Variablen 13</div>
        <div style="padding:5px 6px;font-size:8px;">
          <div style="color:#888;font-size:7px;text-transform:uppercase;margin-bottom:2px;">Aus Kontext</div>
          ${['{name}','{email}','{cv_link}','{cv_version}','{created_date}'].map((v,i)=>`<div style="padding:2px 4px;background:#e6f1fb;border-radius:3px;margin-bottom:2px;font-family:monospace;color:#0c447c;font-size:8px;display:flex;justify-content:space-between;${i===0?'border:1.5px solid #163258;':''}" class="${i===0?'es-tut-pulse':''}">${v}<span style="color:#888;">📋</span></div>`).join('')}
          <div style="color:#888;font-size:7px;text-transform:uppercase;margin:4px 0 2px;">User-Profil</div>
          ${['{sender_name}','{sender_email}'].map(v=>`<div style="padding:2px 4px;background:#eaf3de;border-radius:3px;margin-bottom:2px;font-family:monospace;color:#27500a;font-size:8px;">${v}</div>`).join('')}
        </div>
      </div>
    </div>
  </div>
</div>`},
{t:'Live-Vorschau und Test-E-Mail',
 d:'Rechts sehen Sie die Live-Vorschau — so sieht die E-Mail beim Empfänger aus. Wechseln Sie zwischen Outlook, Gmail und TXT. In der Sidebar unter "Test-E-Mail senden" können Sie eine echte Test-E-Mail an eine beliebige Adresse schicken.',
 r:()=>`<div class="es-tut-sim" style="padding:8px 10px;">
  <div style="display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.1fr);gap:8px;">
    <div>
      <div style="border:1px solid #eee;border-radius:4px;overflow:hidden;">
        <div style="background:#163258;color:#fff;padding:4px 7px;font-size:8px;font-weight:500;">✈ Test-E-Mail senden</div>
        <div style="padding:7px;">
          <div class="es-tut-inp" style="font-size:8px;margin-bottom:5px;">Empfänger-E-Mail...</div>
          <div class="es-tut-pulse" style="background:#163258;color:#fff;border-radius:4px;padding:3px 8px;font-size:8px;text-align:center;cursor:pointer;">✈ Senden</div>
        </div>
      </div>
    </div>
    <div>
      <div style="border:1px solid #eee;border-radius:4px;overflow:hidden;">
        <div style="background:#163258;color:#fff;padding:4px 7px;font-size:8px;display:flex;align-items:center;justify-content:space-between;">
          <span>👁 Live-Vorschau</span>
          <div style="display:flex;gap:2px;">
            <span class="es-tut-tab-on" style="font-size:7px;padding:1px 4px;">Outlook</span>
            <span class="es-tut-tab-off" style="font-size:7px;padding:1px 4px;">Gmail</span>
            <span class="es-tut-tab-off" style="font-size:7px;padding:1px 4px;">TXT</span>
          </div>
        </div>
        <div style="padding:0;">
          <div style="font-size:8px;color:#888;padding:3px 6px;background:#f8f8f8;border-bottom:1px solid #eee;">Von: angelo@abcona.de · An: max@example.de</div>
          <div style="background:#163258;color:#fff;padding:5px 8px;font-size:9px;font-weight:600;">abcona e. K.</div>
          <div style="padding:6px 8px;background:#fff;">
            <p style="margin:0 0 3px;font-size:9px;">Hallo <b>Max Mustermann</b>,</p>
            <p style="margin:0 0 4px;font-size:9px;">Ihr Profil wurde erfolgreich erstellt.</p>
            <span style="display:inline-block;background:#163258;color:#fff;padding:3px 7px;border-radius:3px;font-size:8px;">Profil ansehen</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>`},
{t:'Speichern — TXT wird automatisch erstellt',
 d:'Klicken Sie oben rechts auf "Speichern". Jedes Speichern legt eine neue Version mit Zeitstempel an. Der TXT-Inhalt (Nur-Text-Version) wird dabei automatisch aus dem HTML generiert — Sie müssen nichts manuell pflegen.',
 r:()=>`<div class="es-tut-sim" style="padding:8px 12px;text-align:center;">
  <div style="display:flex;justify-content:flex-end;gap:6px;margin-bottom:10px;">
    <div style="border:1px solid #163258;color:#163258;border-radius:4px;padding:4px 10px;font-size:9px;">Speichern unter</div>
    <div class="es-tut-pulse" style="background:#163258;color:#fff;border-radius:4px;padding:4px 10px;font-size:9px;">Speichern</div>
  </div>
  <div style="display:flex;gap:8px;align-items:center;justify-content:center;flex-wrap:wrap;margin-bottom:8px;">
    <div style="background:#163258;color:#fff;border-radius:5px;padding:5px 10px;font-size:9px;font-weight:600;">📝 HTML</div>
    <span style="color:#163258;font-size:14px;">→</span>
    <div style="background:#faeeda;color:#633806;border-radius:5px;padding:5px 10px;font-size:9px;border:1px solid #ef9f27;">✨ TXT auto-generiert</div>
    <span style="color:#163258;font-size:14px;">→</span>
    <div style="background:#eaf3de;color:#27500a;border-radius:5px;padding:5px 10px;font-size:9px;border:1px solid #97c459;">🔖 Version 2</div>
  </div>
  <div style="background:#163258;color:#fff;border-radius:4px;padding:4px 10px;font-size:9px;display:inline-block;">✓ Gespeichert</div>
</div>`},
]},
{lbl:lbl[1], steps:[
{t:'Versionsverlauf öffnen',
 d:'Klicken Sie in der blauen Leiste auf "Versionsverlauf". Es öffnet sich ein Panel mit allen gespeicherten Versionen. Die grün markierte Version ist die aktuell aktive. Ältere Versionen können wiederhergestellt werden.',
 r:()=>`<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="border:1px solid #eee;border-radius:5px;overflow:hidden;">
    <div style="background:#163258;color:#fff;padding:5px 10px;font-size:9px;display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
      <span class="es-tut-pulse" style="background:rgba(255,255,255,.25);padding:2px 8px;border-radius:3px;">⏱ Versionsverlauf 2 offiziell</span>
      <span style="opacity:.6;">⭐ 0 Meilensteine</span>
      <span style="opacity:.6;">↩ Rückgängig</span>
      <span style="opacity:.6;">↪ Wiederholen</span>
      <span style="opacity:.6;margin-left:auto;">⇄ Übersetzungen</span>
      <span style="opacity:.6;">Sprachen</span>
      <span style="opacity:.6;">✂ Auto-Übersetzen</span>
    </div>
    <div style="padding:8px;display:flex;gap:8px;align-items:center;">
      <div style="background:#f8f8f8;border:1px solid #eee;border-radius:5px;padding:6px 10px;font-size:8px;text-align:center;opacity:.6;">
        <div style="font-weight:600;">2</div>
        <div style="color:#888;font-size:7px;">Auto-Version</div>
        <div style="color:#888;font-size:7px;">18.05. 15:00</div>
      </div>
      <span style="color:#888;">←</span>
      <div class="es-tut-pulse" style="background:#eaf3de;border:2px solid #28a745;border-radius:5px;padding:6px 10px;font-size:8px;text-align:center;">
        <div style="width:18px;height:18px;border-radius:50%;background:#28a745;color:#fff;font-size:8px;font-weight:600;display:flex;align-items:center;justify-content:center;margin:0 auto 3px;">1</div>
        <div style="font-weight:600;color:#27500a;">Initiale Version · Aktiv</div>
        <div style="color:#3b6d11;font-size:7px;">18.05. 13:22</div>
      </div>
      <div style="font-size:8px;color:#888;">← anklicken zum Wiederherstellen</div>
    </div>
  </div>
</div>`},
{t:'Änderungsnotiz und Meilenstein',
 d:'Geben Sie vor dem Speichern eine kurze Notiz ein (z.B. "Logo aktualisiert"). Klicken Sie auf "Merken" um die aktuelle Version als Meilenstein zu markieren — so finden Sie wichtige Versionen schnell wieder.',
 r:()=>`<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="border:1px solid #eee;border-radius:5px;overflow:hidden;">
    <div style="background:#163258;color:#fff;padding:5px 10px;font-size:9px;display:flex;align-items:center;gap:5px;flex-wrap:wrap;">
      <span style="opacity:.6;">⏱ Versionsverlauf 2</span>
      <span style="opacity:.6;">⭐ 0 Meilensteine</span>
      <span style="opacity:.6;">↩</span><span style="opacity:.6;">↪</span>
      <span class="es-tut-pulse" style="background:rgba(255,255,255,.3);padding:1px 6px;border-radius:3px;font-size:8px;">⭐ Merken</span>
      <input style="flex:1;min-width:80px;background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.3);border-radius:3px;padding:2px 5px;color:#fff;font-size:8px;" placeholder="Änderungsnotiz...">
    </div>
  </div>
  <div style="margin-top:6px;background:#eaf3de;border-radius:4px;padding:4px 7px;font-size:8px;color:#27500a;">Tipp: Notiz eingeben → Speichern → Version ist dokumentiert und auffindbar</div>
</div>`},
{t:'Version wiederherstellen',
 d:'Klicken Sie im Versionsverlauf auf eine ältere Version. Nach Bestätigung wird diese Version wiederhergestellt. Die aktuelle Version bleibt als Backup erhalten — Sie können jederzeit wieder zurückwechseln.',
 r:()=>`<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="background:#fff;border:1px solid #e24b4a;border-radius:5px;padding:10px;font-size:9px;">
    <div style="font-weight:600;color:#e24b4a;margin-bottom:5px;">⚠ Version wiederherstellen</div>
    <div style="color:#333;margin-bottom:8px;line-height:1.6;">Möchten Sie Version 1 (18.05. 13:22) wiederherstellen?<br>Die aktuelle Version bleibt als Backup erhalten.</div>
    <div style="display:flex;gap:6px;justify-content:flex-end;">
      <div style="border:1px solid #eee;border-radius:4px;padding:3px 10px;font-size:9px;color:#666;">Abbrechen</div>
      <div class="es-tut-pulse" style="background:#163258;color:#fff;border-radius:4px;padding:3px 10px;font-size:9px;">Wiederherstellen</div>
    </div>
  </div>
</div>`},
]},
{lbl:lbl[2], steps:[
{t:'Übersetzungs-Panel öffnen',
 d:'Klicken Sie in der blauen Leiste auf "Übersetzungen". Es öffnet sich ein Panel mit allen vorhandenen Übersetzungen. DE ist immer die Referenz-Sprache — alle anderen Sprachen werden aus dem deutschen Text übersetzt.',
 r:()=>`<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="border:1px solid #eee;border-radius:5px;overflow:hidden;">
    <div style="background:#163258;color:#fff;padding:5px 10px;font-size:9px;font-weight:500;display:flex;align-items:center;gap:6px;">
      <span>⇄ Übersetzungen</span>
      <span style="background:rgba(255,255,255,.2);padding:1px 5px;border-radius:3px;font-size:8px;">2</span>
      <span style="background:#e6f1fb;color:#0c447c;padding:1px 5px;border-radius:3px;font-size:8px;margin-left:auto;">— DE ist immer Referenz</span>
    </div>
    <div style="padding:5px 8px;font-size:8px;">
      <div style="display:grid;grid-template-columns:50px 1fr 50px 90px 60px;gap:4px;color:#888;font-size:7px;text-transform:uppercase;padding:3px 0;border-bottom:1px solid #eee;">
        <span>Sprache</span><span>Betreff</span><span>Auto</span><span>Übersetzt am</span><span>Aktionen</span>
      </div>
      <div style="display:grid;grid-template-columns:50px 1fr 50px 90px 60px;gap:4px;padding:4px 0;border-bottom:0.5px solid #eee;align-items:center;">
        <span style="background:#e6f1fb;color:#0c447c;padding:1px 5px;border-radius:3px;font-weight:600;font-size:8px;">EN</span>
        <span style="color:#333;font-size:8px;">Your Consultant Profile is Ready — {name}</span>
        <span style="background:#faeeda;color:#633806;padding:1px 4px;border-radius:3px;font-size:7px;">Auto</span>
        <span style="color:#888;font-size:7px;">18.05.2026 15:29</span>
        <span style="color:#888;font-size:10px;">✏ 🔄 🗑</span>
      </div>
      <div style="display:grid;grid-template-columns:50px 1fr 50px 90px 60px;gap:4px;padding:4px 0;align-items:center;">
        <span style="background:#e6f1fb;color:#0c447c;padding:1px 5px;border-radius:3px;font-weight:600;font-size:8px;">IT</span>
        <span style="color:#333;font-size:8px;">Il tuo profilo consulente è pronto — {name}</span>
        <span style="background:#faeeda;color:#633806;padding:1px 4px;border-radius:3px;font-size:7px;">Auto</span>
        <span style="color:#888;font-size:7px;">18.05.2026 16:16</span>
        <span style="color:#888;font-size:10px;">✏ 🔄 🗑</span>
      </div>
    </div>
  </div>
</div>`},
{t:'Sprachen aktivieren',
 d:'Klicken Sie auf "Sprachen" um das Sprachen-Panel zu öffnen. Setzen Sie Häkchen bei den gewünschten Sprachen. Klicken Sie dann in der Leiste auf "Auto-Übersetzen" — die KI übersetzt alle aktivierten Sprachen automatisch.',
 r:()=>`<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="border:1px solid #eee;border-radius:5px;overflow:hidden;">
    <div style="background:#163258;color:#fff;padding:5px 10px;font-size:9px;font-weight:500;">Übersetzungssprachen für diese Vorlage</div>
    <div style="padding:8px;">
      <div style="font-size:8px;color:#888;margin-bottom:5px;text-transform:uppercase;font-size:7px;">Übersetzungssprachen für diese Vorlage</div>
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:8px;">
        <label style="display:flex;align-items:center;gap:3px;font-size:9px;"><input type="checkbox"> EN English</label>
        <label style="display:flex;align-items:center;gap:3px;font-size:9px;"><input type="checkbox"> ES Spanish</label>
        <label style="display:flex;align-items:center;gap:3px;font-size:9px;"><input type="checkbox"> FR French</label>
        <label style="display:flex;align-items:center;gap:3px;font-size:9px;" class="es-tut-pulse"><input type="checkbox" checked> IT Italian</label>
      </div>
      <div style="border-top:1px solid #eee;padding-top:6px;display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
        <span style="font-size:8px;color:#888;">Weitere Sprache installieren:</span>
        <div class="es-tut-inp" style="font-size:8px;">— Sprache wählen —</div>
        <div style="background:#163258;color:#fff;border-radius:4px;padding:3px 8px;font-size:8px;">+ Installieren</div>
      </div>
    </div>
  </div>
</div>`},
{t:'Auto-Übersetzen',
 d:'Klicken Sie in der blauen Leiste auf "Auto-Übersetzen". Die KI übersetzt den gesamten E-Mail-Inhalt automatisch. Wichtig: Variablen wie {name} oder {cv_link} werden dabei nie übersetzt — sie bleiben immer als Platzhalter erhalten.',
 r:()=>`<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="display:flex;gap:8px;align-items:center;justify-content:center;flex-wrap:wrap;margin-bottom:8px;">
    <div style="background:#163258;color:#fff;border-radius:5px;padding:5px 10px;font-size:9px;font-weight:600;">🇩🇪 DE Basis</div>
    <span style="font-size:14px;color:#163258;">→</span>
    <div class="es-tut-pulse" style="background:#faeeda;color:#633806;border-radius:5px;padding:5px 10px;font-size:9px;border:1px solid #ef9f27;">✨ KI übersetzt</div>
    <span style="font-size:14px;color:#163258;">→</span>
    <div style="background:#eaf3de;color:#27500a;border-radius:5px;padding:5px 10px;font-size:9px;border:1px solid #97c459;">🇬🇧 EN · 🇮🇹 IT</div>
  </div>
  <div style="background:#1e1e1e;color:#d4d4d4;font-family:monospace;font-size:8px;border-radius:4px;padding:7px;line-height:1.8;">
<span style="color:#6a9955;"># DE (Basis-Text):</span>
Hallo <span style="background:#264f78;">{name}</span>, Ihr Profil ist fertig.
<span style="color:#6a9955;"># IT (automatisch — {name} bleibt unverändert):</span>
Ciao <span style="background:#264f78;">{name}</span>, il tuo profilo è pronto.</div>
  <div style="margin-top:5px;background:#eaf3de;border-radius:4px;padding:4px 7px;font-size:8px;color:#27500a;">{name}, {cv_link} usw. werden NIE übersetzt — nur der normale Text</div>
</div>`},
{t:'Übersetzung prüfen und bearbeiten',
 d:'Klicken Sie auf das Stift-Symbol (✏) neben einer Sprache um die Übersetzung zu öffnen. Sie können den Text direkt bearbeiten und korrigieren. Nach dem Speichern ist Ihre Version aktiv und wird beim nächsten Versand verwendet.',
 r:()=>`<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="border:1px solid #eee;border-radius:5px;overflow:hidden;">
    <div style="background:#163258;color:#fff;padding:5px 10px;font-size:9px;font-weight:500;display:flex;gap:4px;">
      <span style="background:rgba(255,255,255,.15);padding:2px 7px;border-radius:3px;">🇩🇪 DE Basis</span>
      <span style="background:rgba(255,255,255,.15);padding:2px 7px;border-radius:3px;">🇬🇧 EN</span>
      <span class="es-tut-pulse" style="background:#fff;color:#163258;padding:2px 7px;border-radius:3px;font-weight:600;">🇮🇹 IT ✏</span>
    </div>
    <div style="padding:8px;">
      <div style="background:#1e1e1e;color:#d4d4d4;font-family:monospace;font-size:8px;border-radius:4px;padding:6px;line-height:1.8;">Ciao <span style="background:#264f78;">{name}</span>,

Il tuo profilo consulente è pronto.
Clicca qui: <span style="background:#264f78;">{cv_link}</span>

Cordiali saluti, <span style="background:#264f78;">{sender_name}</span><span class="es-tut-cur"></span></div>
      <div style="margin-top:5px;background:#163258;color:#fff;border-radius:4px;padding:4px 7px;font-size:8px;text-align:center;cursor:pointer;">💾 Speichern</div>
    </div>
  </div>
</div>`},
]},
{lbl:lbl[3], steps:[
{t:'Was sind Module?',
 d:'Module sind fertige Bausteine die Sie in Vorlagen einbauen können: Header (Kopfbereich mit abcona-Logo), Footer (Fußbereich mit Impressum), Buttons und Sektionen. Ändern Sie ein Modul einmal — es ändert sich automatisch in allen Vorlagen die es verwenden.',
 r:()=>`<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;font-size:8px;">
    <div class="es-tut-crd" style="background:#e6f1fb;">
      <div style="font-weight:600;color:#0c447c;margin-bottom:3px;">HEADER</div>
      <div style="color:#888;font-size:7px;margin-bottom:4px;">Header — Blau / Grün (Erfolg) / Rot (Fehler)</div>
      <div style="background:#163258;color:#fff;padding:4px 6px;border-radius:3px;font-size:8px;text-align:center;font-weight:600;">abcona e. K.</div>
    </div>
    <div class="es-tut-crd" style="background:#eaf3de;">
      <div style="font-weight:600;color:#27500a;margin-bottom:3px;">FOOTER</div>
      <div style="color:#888;font-size:7px;margin-bottom:4px;">Footer Standard / Footer Auto-Reply</div>
      <div style="background:#f0f0f0;padding:4px 6px;border-radius:3px;font-size:7px;color:#666;text-align:center;">Impressum · Abmelden</div>
    </div>
    <div class="es-tut-crd" style="background:#faeeda;">
      <div style="font-weight:600;color:#633806;margin-bottom:3px;">BUTTON</div>
      <div style="color:#888;font-size:7px;margin-bottom:4px;">Button — Blau / Button — Grün</div>
      <div style="display:flex;gap:4px;">
        <div style="background:#163258;color:#fff;border-radius:3px;padding:3px 8px;font-size:8px;">Button — Blau</div>
        <div style="background:#28a745;color:#fff;border-radius:3px;padding:3px 8px;font-size:8px;">Button — Grün</div>
      </div>
    </div>
    <div class="es-tut-crd" style="background:#f1efe8;">
      <div style="font-weight:600;color:#444;margin-bottom:3px;">SECTION</div>
      <div style="color:#888;font-size:7px;margin-bottom:4px;">Support Kontakt</div>
      <div style="background:#fff;border:1px solid #eee;padding:4px 6px;border-radius:3px;font-size:7px;color:#666;">📞 Support: support@abcona.de</div>
    </div>
  </div>
</div>`},
{t:'Modul in der Sidebar finden',
 d:'Scrollen Sie in der linken Sidebar nach unten zu "Module". Die Module sind nach Typ gruppiert: BUTTON, FOOTER, HEADER, SECTION. Klicken Sie auf ein Modul — es wird an der aktuellen Cursor-Position im HTML-Editor eingefügt.',
 r:()=>`<div class="es-tut-sim" style="padding:8px 10px;">
  <div style="border:1px solid #eee;border-radius:5px;overflow:hidden;max-width:220px;">
    <div style="background:#163258;color:#fff;padding:5px 10px;font-size:9px;font-weight:500;">⊞ Module ∧</div>
    <div style="padding:6px 8px;font-size:8px;">
      <div style="color:#888;text-transform:uppercase;font-size:7px;margin-bottom:3px;">BUTTON</div>
      <div class="es-tut-pulse" style="display:flex;align-items:center;gap:5px;padding:4px 7px;border:1px solid #b5d4f4;border-radius:4px;margin-bottom:2px;cursor:pointer;background:#e6f1fb;">
        <span>✈</span><span style="color:#0c447c;font-weight:500;">Button — Blau</span>
      </div>
      <div style="display:flex;align-items:center;gap:5px;padding:4px 7px;border:1px solid #eee;border-radius:4px;margin-bottom:5px;opacity:.7;">
        <span>✈</span><span>Button — Grün</span>
      </div>
      <div style="color:#888;text-transform:uppercase;font-size:7px;margin-bottom:3px;">FOOTER</div>
      <div style="display:flex;align-items:center;gap:5px;padding:4px 7px;border:1px solid #eee;border-radius:4px;margin-bottom:2px;opacity:.7;"><span>📋</span><span>Footer Auto-Reply</span></div>
      <div style="display:flex;align-items:center;gap:5px;padding:4px 7px;border:1px solid #eee;border-radius:4px;margin-bottom:5px;opacity:.7;"><span>📋</span><span>Footer Standard</span></div>
      <div style="color:#888;text-transform:uppercase;font-size:7px;margin-bottom:3px;">HEADER</div>
      <div style="display:flex;align-items:center;gap:5px;padding:4px 7px;border:1px solid #eee;border-radius:4px;margin-bottom:2px;opacity:.7;"><span>📋</span><span>Header — Blau</span></div>
      <div style="display:flex;align-items:center;gap:5px;padding:4px 7px;border:1px solid #eee;border-radius:4px;margin-bottom:2px;opacity:.7;"><span>📋</span><span>Header — Grün (Erfolg)</span></div>
      <div style="display:flex;align-items:center;gap:5px;padding:4px 7px;border:1px solid #eee;border-radius:4px;opacity:.7;"><span>📋</span><span>Header — Rot (Fehler)</span></div>
    </div>
  </div>
</div>`},
{t:'Modul einfügen — Ergebnis',
 d:'Nach dem Klick auf ein Modul erscheint in Ihrem HTML-Code ein Platzhalter wie {{block:abcona_header_blau}}. In der Live-Vorschau rechts sehen Sie sofort wie das Modul aussieht. Beim Versand wird der Platzhalter automatisch durch den echten Inhalt ersetzt.',
 r:()=>`<div class="es-tut-sim" style="padding:8px 10px;">
  <div style="display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,1fr);gap:8px;">
    <div>
      <div style="font-size:8px;color:#888;margin-bottom:3px;">HTML-Code nach Einfügen:</div>
      <div class="es-tut-editor" style="font-size:8px;"><span style="background:#264f78;">{{block:abcona_header_blau}}</span>
&lt;tr&gt;&lt;td style="padding:24px;"&gt;
  &lt;p&gt;Hallo {name},&lt;/p&gt;
  &lt;p&gt;Ihr Profil ist fertig.&lt;/p&gt;
  <span style="background:#264f78;">{{block:button_blau}}</span>
&lt;/td&gt;&lt;/tr&gt;
<span style="background:#264f78;">{{block:footer_standard}}</span><span class="es-tut-cur"></span></div>
    </div>
    <div>
      <div style="font-size:8px;color:#888;margin-bottom:3px;">Live-Vorschau (aufgelöst):</div>
      <div style="border:1px solid #e0e0e0;border-radius:5px;overflow:hidden;">
        <div style="background:#163258;color:#fff;padding:5px 8px;font-size:9px;font-weight:600;">abcona e. K.</div>
        <div style="background:#fff;padding:7px 8px;">
          <p style="margin:0 0 3px;font-size:9px;">Hallo <b>{name}</b>,</p>
          <p style="margin:0 0 5px;font-size:9px;">Ihr Profil ist fertig.</p>
          <span style="display:inline-block;background:#163258;color:#fff;padding:3px 8px;border-radius:3px;font-size:8px;">Profil ansehen</span>
        </div>
        <div style="background:#f0f0f0;padding:3px 8px;font-size:7px;color:#999;">Impressum · Abmelden · abcona e. K.</div>
      </div>
    </div>
  </div>
</div>`},
]},
{lbl:lbl[4], steps:[
{t:'Wann duplizieren?',
 d:'Duplizieren ist sinnvoll wenn Sie eine ähnliche Vorlage brauchen — z.B. eine Erfolgs-Mail und eine Fehler-Mail haben fast denselben Aufbau. Sie sparen die gesamte Grundstruktur und müssen nur die unterschiedlichen Texte anpassen.',
 r:()=>`<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="font-size:9px;font-weight:600;color:#163258;margin-bottom:6px;">Typische Situationen:</div>
  ${[['pipeline_success','pipeline_error','Gleiche Struktur — Erfolg vs. Fehler'],
     ['upload_received','upload_error','Bestätigung vs. Fehlermeldung'],
     ['cv_generated_de','cv_generated_en','Gleicher Inhalt — andere Sprache']
  ].map(([a,b,d])=>`
  <div style="display:flex;align-items:center;gap:6px;padding:4px 0;border-bottom:0.5px solid #eee;font-size:8px;">
    <code style="background:#f1f1f1;padding:1px 4px;border-radius:2px;">${a}</code>
    <span style="color:#163258;font-weight:600;">→</span>
    <code style="background:#e6f1fb;color:#0c447c;padding:1px 4px;border-radius:2px;">${b}</code>
    <span style="color:#888;">${d}</span>
  </div>`).join('')}
  <div style="margin-top:6px;background:#faeeda;border-radius:4px;padding:4px 7px;font-size:8px;color:#633806;">Kopie ist vollständig unabhängig — Änderungen am Original betreffen die Kopie nicht</div>
</div>`},
{t:'Vorlage duplizieren',
 d:'In der Vorlagen-Übersicht klicken Sie auf das Kopier-Symbol 📋 in der Aktionen-Spalte. Es öffnet sich sofort ein Dialog wo Sie der Kopie einen neuen Namen und einen neuen technischen Namen (Identifier) geben.',
 r:()=>`<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="border:1px solid #eee;border-radius:5px;overflow:hidden;">
    <div style="background:#163258;color:#fff;padding:4px 8px;font-size:8px;display:grid;grid-template-columns:2fr 1fr 1fr 80px;">
      <span>Name / Identifier</span><span>Absender</span><span>Status</span><span>Aktionen</span>
    </div>
    <div style="display:grid;grid-template-columns:2fr 1fr 1fr 80px;padding:6px 8px;font-size:8px;align-items:center;">
      <div><b style="color:#163258;">Pipeline Erfolg</b><br><span style="font-family:monospace;color:#888;font-size:7px;">pipeline_success</span></div>
      <span style="color:#f59e0b;">● Auto</span>
      <span><span style="background:#28a745;color:#fff;border-radius:3px;padding:1px 5px;font-size:7px;">Aktiv</span></span>
      <div style="display:flex;gap:4px;align-items:center;">
        <span style="color:#888;">✏</span>
        <span class="es-tut-pulse" style="background:#e6f1fb;color:#163258;border-radius:3px;padding:2px 5px;font-size:11px;cursor:pointer;">📋</span>
        <span style="color:#888;">👁 ✈ 🗑</span>
      </div>
    </div>
  </div>
  <div style="margin-top:5px;background:#e6f1fb;border-radius:4px;padding:4px 7px;font-size:8px;color:#0c447c;">📋 Klicken → Dialog öffnet sich sofort</div>
</div>`},
{t:'Neuen Identifier vergeben',
 d:'Geben Sie der Kopie einen neuen Anzeigenamen und einen neuen Identifier. Der Identifier muss eindeutig sein und darf nicht identisch mit dem Original sein. Alle Inhalte (HTML, Variablen, Module, Einstellungen) werden vollständig kopiert.',
 r:()=>`<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="font-size:9px;font-weight:600;color:#163258;margin-bottom:5px;">📋 Dupliziert von: pipeline_success</div>
  <div style="display:flex;flex-direction:column;gap:5px;font-size:9px;">
    <div><div class="es-tut-lbl">NEUER IDENTIFIER *</div>
      <div class="es-tut-pulse" style="border:1px solid #4a90d9;border-radius:4px;padding:3px 6px;font-family:monospace;background:#e6f1fb;color:#0c447c;">pipeline_error<span class="es-tut-cur"></span></div>
    </div>
    <div><div class="es-tut-lbl">NEUER NAME</div>
      <div class="es-tut-inp">Pipeline Fehler — CV-Verarbeitung fehlgeschlagen</div>
    </div>
  </div>
  <div style="margin-top:6px;border:1px solid #eee;border-radius:4px;padding:5px 7px;font-size:8px;">
    <div style="font-weight:500;color:#333;margin-bottom:3px;">Was wird kopiert?</div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;">
      ${['HTML','TXT','Absender-Modus','Variablen','Module','Einstellungen'].map(x=>`<span style="color:#27500a;">✓ ${x}</span>`).join('')}
    </div>
  </div>
</div>`},
{t:'Nur die Unterschiede anpassen',
 d:'Nach dem Duplizieren öffnet sich sofort das Studio der neuen Vorlage. Ändern Sie nur die Textstellen die sich unterscheiden sollen — z.B. Betreff, Überschrift und Fehlertext. Layout, Header und Footer bleiben automatisch identisch.',
 r:()=>`<div class="es-tut-sim" style="padding:8px 12px;">
  <div style="display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:8px;">
    <div>
      <div style="font-size:8px;color:#888;margin-bottom:3px;">Original: pipeline_success</div>
      <div class="es-tut-editor" style="font-size:8px;opacity:.65;">&lt;h2&gt;Verarbeitung erfolgreich&lt;/h2&gt;
&lt;p style="color:#28a745;"&gt;✓ Alles OK&lt;/p&gt;
&lt;a style="background:#28a745;"&gt;Ergebnis ansehen&lt;/a&gt;</div>
    </div>
    <div>
      <div style="font-size:8px;color:#163258;margin-bottom:3px;">Kopie: pipeline_error</div>
      <div class="es-tut-editor" style="font-size:8px;">&lt;h2&gt;<span style="background:#264f78;">Fehler aufgetreten</span>&lt;/h2&gt;
&lt;p style="color:<span style="background:#264f78;">#e24b4a</span>;"&gt;<span style="background:#264f78;">✗ Fehler</span>&lt;/p&gt;
&lt;a style="background:<span style="background:#264f78;">#e24b4a</span>;"&gt;<span style="background:#264f78;">Support</span>&lt;/a&gt;<span class="es-tut-cur"></span></div>
    </div>
  </div>
  <div style="margin-top:5px;background:#eaf3de;border-radius:4px;padding:4px 7px;font-size:8px;color:#27500a;">Nur 3 Stellen geändert — Rest 1:1 vom Original</div>
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
      <input type="range" min="1" max="6" value="3" step="1" style="width:50px;" title="Geschwindigkeit" oninput="window._esTutSpeed=this.value*1000">
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
