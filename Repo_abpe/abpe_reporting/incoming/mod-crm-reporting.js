/* ============================================================
   ABpE CRM — mod-crm-reporting.js
   Sync-Status, Statistiken
   ============================================================ */

const CRM_Reporting = {

    init() {
        this.loadSyncStatus();
    },

    loadSyncStatus() {
        const el = document.getElementById('crm-sync-stats');
        if (!el) return;

        fetch('/crm/api/sync/status/', {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
        .then(r => r.json())
        .then(data => {
            el.innerHTML = `
            <div class="crm-stats-bar" style="margin:12px">
                <div class="crm-stat"><span class="crm-stat-val">${(data.contacts_total||0).toLocaleString()}</span><span class="crm-stat-lbl">Contacts</span></div>
                <div class="crm-stat"><span class="crm-stat-val">${(data.accounts_total||0).toLocaleString()}</span><span class="crm-stat-lbl">Accounts</span></div>
                <div class="crm-stat"><span class="crm-stat-val">${(data.emails_total||0).toLocaleString()}</span><span class="crm-stat-lbl">E-Mails</span></div>
                <div class="crm-stat"><span class="crm-stat-val">${(data.documents_total||0).toLocaleString()}</span><span class="crm-stat-lbl">Dokumente</span></div>
            </div>
            <div style="padding:0 12px 12px">
                <div class="crm-section-label">Letzter Sync</div>
                <div style="font-size:13px;color:var(--abcona-blue)">${data.last_sync || '—'}</div>
            </div>`;
        })
        .catch(() => {
            if (el) el.innerHTML = '<div class="crm-list-loading"><i class="bi bi-exclamation-triangle"></i> Fehler</div>';
        });
    },

    startSync() {
        alert((window.i18nData['sync_gestartet']||'Sync wird gestartet — bitte warten...'));
    },
};

window.CRM_Reporting = CRM_Reporting;
window.crmStartSync = () => CRM_Reporting.startSync();

document.addEventListener('DOMContentLoaded', () => {
    if (window.CRM_TAB === 'reporting') CRM_Reporting.init();
});
