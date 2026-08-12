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
            if (s.language && window.SP_Lang) SP_Lang._setLangPublic(s.language, false);
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
        var langVal = (document.getElementById('sp-cfg-lang') || {value:''}).value.trim();
        await fetch('/crm/api/user-settings/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': Softphone._csrf() },
            body: JSON.stringify({
                softphone_vm_ext:      vmExt,
                softphone_dnd_ext:     dndExt,
                softphone_status_exts: stsExts,
                language:              langVal,
            })
        });
        if (langVal && window.SP_Lang) SP_Lang._setLangPublic(langVal, false);
    } catch(e) { console.warn('SP-Status: Ext-Settings speichern fehlgeschlagen', e); }
    if (Softphone._ext.status_exts.length) Softphone._startStatusPolling();
    await _origSaveAndRegister.call(Softphone);
};

// Voicemail
Softphone.callVoicemail = function() {
    var ext = (Softphone._ext.vm_ext || '').split(',')[0].trim();
    if (!ext) { alert(SP_i18n.t('alert_vm_missing')); return; }
    Softphone.setNumber('*97' + ext);
    Softphone.call();
};

// DND
Softphone.toggleDND = async function() {
    var ext = Softphone._ext.dnd_ext || Softphone._ext.vm_ext;
    if (!ext) { alert(SP_i18n.t('alert_dnd_missing')); return; }
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
    var target = prompt(SP_i18n.t('forward_prompt', 'Weiterleitungsziel:'), '');
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
    var vmCount   = Softphone._vmCount || 0;
    var fwdActive = Softphone._ext.fwd_active || false;
    var fwdTarget = Softphone._ext.fwd_target || '';
    var dndActive = Softphone._ext.dnd_active || false;

    function setFnClass(el, activeClass) {
        if (!el) return;
        el.style.cssText = '';
        el.className = 'sp-fn-base' + (activeClass ? ' ' + activeClass : '');
    }

    if (vmBtn) {
        setFnClass(vmBtn, vmCount > 0 ? 'sp-fn-vm-active' : null);
        if (vmLabel) vmLabel.textContent = vmCount > 0 ? SP_i18n.t('voicemail','VM') + ' \u00b7 ' + vmCount : SP_i18n.t('voicemail','VM');
    }
    if (fwdBtn) {
        setFnClass(fwdBtn, fwdActive ? 'sp-fn-fwd-active' : null);
    }
    if (dndBtn) {
        setFnClass(dndBtn, dndActive ? 'sp-fn-dnd-active' : null);
        if (dndIcon) dndIcon.className = dndActive ? 'bi bi-bell-slash' : 'bi bi-bell';
        if (dndLabel) dndLabel.textContent = SP_i18n.t('dnd', 'DND');
    }
    if (bar) {
        if (dndActive) {
            bar.className = 'sp-status-bar-dnd'; bar.style.cssText = 'display:block;padding:4px 8px;border-left:3px solid var(--status-dnd-border);font-size:10px;font-weight:500;color:var(--status-dnd-color);margin:0 0 2px 0';
            bar.innerHTML = '<i class="bi bi-bell-slash" style="margin-right:4px"></i>' + SP_i18n.t('dnd_active', 'Nicht stören aktiv');
        } else if (fwdActive && fwdTarget) {
            bar.style.cssText = 'display:block;padding:4px 8px;border-left:3px solid var(--status-fwd-border);font-size:10px;font-weight:500;color:var(--status-fwd-color);margin:0 0 2px 0';
            bar.innerHTML = '<i class="bi bi-arrow-return-right" style="margin-right:4px"></i>' + SP_i18n.t('forwarding', 'Weiterleitung') + ': ' + fwdTarget;
        } else if (vmCount > 0) {
            bar.style.cssText = 'display:block;padding:4px 8px;border-left:3px solid var(--status-vm-border);font-size:10px;font-weight:500;color:var(--status-vm-color);margin:0 0 2px 0';
            bar.innerHTML = '<i class="bi bi-voicemail" style="margin-right:4px"></i>' + vmCount + ' ' + (vmCount > 1 ? SP_i18n.t('new_voicemails', 'neue Voicemail-Nachrichten') : SP_i18n.t('new_voicemail', 'neue Voicemail-Nachricht'));
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
        // Suchfeld nach DOM-Update leeren (Browser-Autofill)
        var s = document.getElementById('sp-search');
        if (s && s.value === 'admin') s.value = '';
    } catch(e) { console.warn('SP-Status: FOP poll Fehler:', e); }
};

// DOMContentLoaded: Ext-Settings laden
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(function() { Softphone._loadExtSettings(); }, 500);
});
