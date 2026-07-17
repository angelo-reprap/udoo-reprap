'use strict';
const KampagneUI = {
    _page: 1,
    _pages: 1,
    _total: 0,
    _selected: new Set(),
    _allIds: [],
    _lastRows: [],
    _templates: [],
    _senders: [],

    _t(key, fb) {
        if (window.CRM_I18N) return CRM_I18N.t(key, fb);
        if (typeof window.t === 'function') return window.t(key, fb);
        return fb != null ? fb : key;
    },

    _status(code) {
        if (window.CRM_I18N) return CRM_I18N.status(code);
        return code || '';
    },

    init() {
        this.load();
        this._loadMeta();
    },

    _csrf() {
        return (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';
    },

    async _loadMeta() {
        try {
            const r = await fetch('/crm/api/email/templates/', {headers:{'X-Requested-With':'XMLHttpRequest'}});
            const d = await r.json();
            this._templates = d.templates || [];
            this._senders   = d.senders   || [];
            const ts = document.getElementById('kamp-template');
            const ss = document.getElementById('kamp-sender');
            if (ts) this._templates.forEach(t => { const o=document.createElement('option'); o.value=t.identifier; o.textContent=t.name; ts.appendChild(o); });
            if (ss) this._senders.forEach(s => { const o=document.createElement('option'); o.value=s.id; o.textContent=s.display_name+' <'+s.email+'>'; if(s.is_default) o.selected=true; ss.appendChild(o); });
        } catch(e) { console.warn('Meta-Fehler', e); }
    },

    async load(page) {
        if (page) this._page = page;
        const q      = (document.getElementById('kamp-filter-q')||{}).value || '';
        const typ    = (document.getElementById('kamp-filter-typ')||{}).value || '';
        const status = (document.getElementById('kamp-filter-status')||{}).value || '';
        const kamp   = (document.getElementById('kamp-filter-kampagne')||{}).value;
        const list   = document.getElementById('kamp-list');
        if (list) list.innerHTML = '<div class="crm-list-loading"><i class="bi bi-hourglass-split"></i> ' + this._t('laden', 'Lade…') + '</div>';

        const params = new URLSearchParams({
            q, page: this._page, per_page: 25,
            ...(typ    ? {typ}    : {}),
            ...(status ? {status} : {}),
            ...(kamp !== '' ? {kampagne_ok: kamp} : {}),
        });

        try {
            const r = await fetch('/crm/api/kampagne/list/?' + params, {headers:{'X-Requested-With':'XMLHttpRequest'}});
            const d = await r.json();
            this._pages = d.pages || 1;
            this._total = d.total || 0;
            this._allIds = (d.results || []).map(x => x.email_id);
            this._lastRows = d.results || [];
            this._render(this._lastRows);
            this._updatePagination(d);
        } catch(e) {
            if (list) list.innerHTML = '<div class="crm-list-loading">' + this._t('fehler_beim_laden', 'Fehler beim Laden') + '</div>';
        }
    },

    _render(rows) {
        const T = this._t.bind(this);
        const list = document.getElementById('kamp-list');
        if (!list) return;
        if (!rows.length) { list.innerHTML = '<div class="crm-list-loading">' + T('keine_treffer', 'Keine Treffer') + '</div>'; return; }
        list.innerHTML = rows.map(r => {
            const checked  = this._selected.has(r.email_id) ? 'checked' : '';
            const kampIcon = r.kampagne_ok
                ? '<i class="bi bi-check-circle-fill" style="color:var(--badge-success-text);font-size:12px" title="' + T('kamp_icon_erlaubt', 'Kampagne erlaubt') + '"></i>'
                : '<i class="bi bi-x-circle" style="color:var(--text-muted);font-size:12px" title="' + T('kamp_icon_gesperrt', 'Kampagne gesperrt') + '"></i>';
            const typBadge = r.typ === 'berater'
                ? '<span class="crm-badge crm-badge-passiv">' + T('berater', 'Berater') + '</span>'
                : '<span class="crm-badge" style="background:#e0f2fe;color:#0369a1">' + T('kunde_label', 'Kunde') + '</span>';
            return `<div class="crm-list-item" style="gap:8px">
                <input type="checkbox" ${checked} data-id="${r.email_id}" onchange="KampagneUI.toggleItem('${r.email_id}',this.checked)" style="width:14px;height:14px;flex-shrink:0;cursor:pointer">
                <div class="crm-avatar" style="width:30px;height:30px;font-size:10px;flex-shrink:0">${(r.name||'?')[0].toUpperCase()}</div>
                <div class="crm-item-info">
                    <div class="crm-item-name" style="font-size:12px">${r.name || '—'}</div>
                    <div class="crm-item-sub">${r.email || ''}</div>
                </div>
                <div class="crm-item-right" style="gap:3px;align-items:flex-end">
                    ${typBadge}
                    <div style="display:flex;align-items:center;gap:3px">${kampIcon}<span style="font-size:10px;color:var(--text-muted)">${this._status(r.status)}</span></div>
                </div>
            </div>`;
        }).join('');
    },

    refreshUi() {
        if (this._lastRows.length) this._render(this._lastRows);
        this._updateSelectionUI();
        const info = document.getElementById('kamp-page-info');
        if (info && this._pages) {
            info.textContent = this._t('kamp_seite', 'Seite {page} von {pages} · {total} Einträge')
                .replace('{page}', this._page)
                .replace('{pages}', this._pages)
                .replace('{total}', this._total);
        }
    },

    _updatePagination(d) {
        const info = document.getElementById('kamp-page-info');
        const prev = document.getElementById('kamp-prev');
        const next = document.getElementById('kamp-next');
        if (info) info.textContent = this._t('kamp_seite', 'Seite {page} von {pages} · {total} Einträge')
            .replace('{page}', d.page||1)
            .replace('{pages}', d.pages||1)
            .replace('{total}', d.total||0);
        if (prev) prev.disabled = (d.page||1) <= 1;
        if (next) next.disabled = (d.page||1) >= (d.pages||1);
    },

    toggleItem(id, checked) {
        if (checked) this._selected.add(id);
        else this._selected.delete(id);
        this._updateSelectionUI();
    },

    toggleAll(checked) {
        if (checked) this._allIds.forEach(id => this._selected.add(id));
        else this._allIds.forEach(id => this._selected.delete(id));
        document.querySelectorAll('#kamp-list input[type=checkbox]').forEach(cb => cb.checked = checked);
        this._updateSelectionUI();
    },

    _updateSelectionUI() {
        const n = this._selected.size;
        const info = document.getElementById('kamp-selected-info');
        const badge = document.getElementById('kamp-count-badge');
        const btn = document.getElementById('kamp-send-btn');
        const dlgCount = document.getElementById('kamp-dialog-count');
        const label = document.getElementById('kamp-send-label');
        const sel = this._t('email_kampagne_ausgewaehlt', '{n} ausgewählt').replace('{n}', n);
        const send = this._t('email_kampagne_emails_senden', '{n} E-Mails senden').replace('{n}', n);
        const emp = this._t('email_kampagne_empfaenger', '{n} Empfänger').replace('{n}', n);
        if (info)     info.textContent = sel;
        if (badge)    badge.textContent = sel;
        if (btn)      { btn.disabled = n === 0; btn.style.opacity = n > 0 ? '1' : '.5'; }
        if (dlgCount) dlgCount.textContent = emp;
        if (label)    label.textContent = send;
    },

    prevPage() { if (this._page > 1) { this._page--; this.load(); } },
    nextPage() { if (this._page < this._pages) { this._page++; this.load(); } },

    openSendDialog() {
        if (this._selected.size === 0) return;
        this._updateSelectionUI();
        const dlg = document.getElementById('kamp-dialog');
        if (dlg) dlg.style.display = 'flex';
    },

    closeDialog() {
        const dlg = document.getElementById('kamp-dialog');
        if (dlg) dlg.style.display = 'none';
    },

    async send() {
        const name     = (document.getElementById('kamp-name')||{}).value || 'Kampagne';
        const template = (document.getElementById('kamp-template')||{}).value;
        const sender   = (document.getElementById('kamp-sender')||{}).value;
        if (!template) { alert(this._t('email_kampagne_vorlage_waehlen', 'Bitte Vorlage wählen')); return; }
        if (!sender)   { alert(this._t('email_kampagne_absender_waehlen', 'Bitte Absender wählen')); return; }

        const btn = document.getElementById('kamp-send-confirm');
        if (btn) { btn.disabled = true; btn.innerHTML = '<i class="bi bi-hourglass-split"></i> ' + this._t('email_kampagne_sende', 'Sende…'); }

        try {
            const r = await fetch('/crm/api/kampagne/send/', {
                method: 'POST',
                headers: {'Content-Type':'application/json','X-CSRFToken': this._csrf()},
                body: JSON.stringify({
                    name,
                    template_identifier: template,
                    sender_id: parseInt(sender),
                    email_ids: Array.from(this._selected),
                })
            });
            const d = await r.json();
            this.closeDialog();
            this._showLog(d);
        } catch(e) {
            alert(this._t('fehler_beim_senden', 'Fehler beim Senden') + ': ' + e);
        } finally {
            if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-send"></i> ' + this._t('email_senden', 'Senden'); }
        }
    },

    _showLog(d) {
        const T = this._t.bind(this);
        const panel = document.getElementById('kamp-log-panel');
        const stats = document.getElementById('kamp-log-stats');
        const logList = document.getElementById('kamp-log-list');
        if (!panel) return;

        const results = d.results || [];
        const ok    = results.filter(x => x.ok).length;
        const err   = results.filter(x => !x.ok).length;

        if (stats) stats.innerHTML = [
            [T('kamp_gesendet', 'Gesendet'), results.length, ''],
            [T('kamp_erfolgreich', 'Erfolgreich'), ok, 'color:var(--badge-success-text)'],
            [T('kamp_fehler', 'Fehler'), err, 'color:var(--badge-error-text)'],
        ].map(([l,n,s]) => `<div style="flex:1;text-align:center;background:var(--abcona-gray-card);border-radius:8px;padding:10px">
            <div style="font-size:20px;font-weight:700;${s}">${n}</div>
            <div style="font-size:11px;color:var(--text-muted)">${l}</div>
        </div>`).join('');

        if (logList) logList.innerHTML = '<table style="width:100%;font-size:12px;border-collapse:collapse">' +
            '<thead><tr style="border-bottom:1px solid var(--border-light)">' +
            '<th style="padding:7px 12px;text-align:left;font-weight:500;color:var(--text-muted)">' + T('name', 'Name') + '</th>' +
            '<th style="padding:7px 4px;text-align:left;font-weight:500;color:var(--text-muted)">' + T('e_mail', 'E-Mail') + '</th>' +
            '<th style="padding:7px 12px;text-align:center;font-weight:500;color:var(--text-muted)">' + T('status', 'Status') + '</th>' +
            '</tr></thead><tbody>' +
            results.map(x => `<tr style="border-bottom:1px solid var(--border-light)">
                <td style="padding:7px 12px;color:var(--abcona-blue)">${x.name||''}</td>
                <td style="padding:7px 4px;color:var(--text-muted)">${x.email||''}</td>
                <td style="padding:7px 12px;text-align:center">
                    ${x.ok
                        ? '<span class="crm-badge crm-badge-aktiv">OK</span>'
                        : '<span class="crm-badge crm-badge-error" title="'+( x.error||'')+'">' + T('fehler', 'Fehler') + '</span>'}
                </td>
            </tr>`).join('') +
            '</tbody></table>';

        panel.style.display = 'block';
        panel.scrollIntoView({behavior:'smooth'});
        this._selected.clear();
        this._updateSelectionUI();
    },
};

document.addEventListener('DOMContentLoaded', function() {
    KampagneUI.init();
});
